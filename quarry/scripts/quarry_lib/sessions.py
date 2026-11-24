"""Run one headless Claude Code session and read its stream-json frames.

A session is one `claude -p` process fed stream-json on stdin. Its context use is measured
from the usage each assistant frame reports, and the context marks are applied to it: a
freeze and a hand-off instruction written to its stdin, and a kill of its process tree at the
stop mark. After each result frame the caller may answer with one more user message, which
starts a further turn on the same session.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from quarry_lib import doctor

SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills"
CLAUDE_ENV = "QUARRY_CLAUDE"
SUMMARY_CHARS = 100
SUMMARY_KEYS = ("file_path", "notebook_path", "command", "pattern", "skill", "url", "description")
CONTEXT_KEYS = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
FREEZE = "freeze"
HANDOFF = "hand off"
STOP = "stop"
FREEZE_MARK = 220_000
HANDOFF_MARK = 250_000
STOP_MARK = 300_000
WINDOW_SHARE = 0.9
SESSION_ENV = {"DISABLE_AUTO_COMPACT": "1"}
HANDOFF_DIR = "docs/handoff"
HANDOFF_SKILL = SKILLS_DIR / "handoff" / "SKILL.md"
FREEZE_INSTRUCTION = (
    "The Quarry driver measured {context} tokens of context in this session, past the freeze "
    "mark of {mark}. Start nothing new: finish only the work already in hand, then end the "
    "session."
)
HANDOFF_INSTRUCTION = (
    "The Quarry driver measured {context} tokens of context in this session, past the "
    "hand-off mark of {mark}. Finish only the item in hand. Then write a handoff document for "
    "the fresh session that continues this goal, at {document}: read {skill} for what the "
    "document holds, but write it at that path, and do not seal: the driver seals this "
    "session. Then end your turn."
)


@dataclass
class Session:
    """What one headless session reported: its frames, its context use and its marks.

    `result` is the result frame of the turn that ended last, None while a turn runs;
    `results` holds the result frame of every turn.
    """

    session_id: str
    model: str | None = None
    result: dict[str, Any] | None = None
    results: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    context: int = 0
    frozen: bool = False
    handed_off: bool = False
    stopped: bool = False
    compactions: list[Any] = field(default_factory=list)
    returncode: int | None = None
    stderr: str = ""


def phase(text: str) -> None:
    """Print one driver progress line immediately."""
    print(f"[drive] {text}", flush=True)


def claude_cli() -> Path:
    """Return the claude CLI: QUARRY_CLAUDE, then PATH, then the desktop app's newest copy.

    Raises:
        FileNotFoundError: none of the three gives a file; the message says what to set.
    """
    configured = os.environ.get(CLAUDE_ENV)
    if configured:
        if not Path(configured).is_file():
            raise FileNotFoundError(f"{CLAUDE_ENV} names {configured}, which is not a file")
        return Path(configured)
    found = shutil.which("claude")
    if found:
        return Path(found)
    appdata = os.environ.get("APPDATA")
    installed = (
        sorted(
            Path(appdata).glob("Claude/claude-code/*/*/claude.exe"),
            key=lambda path: path.stat().st_mtime,
        )
        if appdata
        else []
    )
    if installed:
        return installed[-1]
    raise FileNotFoundError(
        f"no claude CLI found: set {CLAUDE_ENV} to its path, put `claude` on PATH, or "
        "install Claude Code so that %APPDATA%\\Claude\\claude-code\\<version>\\<build>\\"
        "claude.exe exists"
    )


def handoff_document(session_id: str) -> str:
    """Return the project-relative path of the handoff document a session writes."""
    return f"{HANDOFF_DIR}/{session_id}.md"


def run(
    claude: Path,
    project_root: Path,
    prompt: str,
    model: str | None,
    options: list[str],
    env: dict[str, str],
    follow_up: Callable[[Session], str | None] | None = None,
) -> Session:
    """Run one headless session on `prompt`, printing each tool call as it arrives.

    Args:
        options: further `claude` options, such as the permission mode and the tool limits.
        env: variables added to this process's environment for the session.
        follow_up: called at each result frame; the text it returns is sent as the next
            user message and starts a further turn, and None ends the session.

    stdin stays open until a result frame gets no follow-up, so the freeze and hand-off
    instructions reach the running session: the CLI absorbs a user message written mid-turn
    at its next tool result. At the stop mark the session's process tree is killed.
    """
    session = Session(session_id=str(uuid.uuid4()))
    command = [
        str(claude),
        "-p",
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
        "--verbose",
        "--session-id",
        session.session_id,
        *options,
    ]
    if model:
        command += ["--model", model]
    phase(f"session: start {session.session_id}")
    with (
        tempfile.TemporaryFile() as stderr_file,
        subprocess.Popen(
            command,
            cwd=str(project_root),
            env={**os.environ, **SESSION_ENV, **env},
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr_file,
            text=True,
            encoding="utf-8",
            errors="replace",
        ) as process,
    ):
        _send(process, prompt)
        for line in process.stdout:
            mark = take_frame(session, line)
            if mark == FREEZE:
                phase(f"mark: freeze at {session.context} tokens (mark {FREEZE_MARK}), "
                      "told the session to start nothing new")
                _send(process, FREEZE_INSTRUCTION.format(
                    context=session.context, mark=FREEZE_MARK
                ))
            elif mark == HANDOFF:
                document = project_root / handoff_document(session.session_id)
                document.parent.mkdir(parents=True, exist_ok=True)
                phase(f"mark: hand off at {session.context} tokens (mark {HANDOFF_MARK}), "
                      f"told the session to finish the item in hand and write "
                      f"{handoff_document(session.session_id)}")
                _send(process, HANDOFF_INSTRUCTION.format(
                    context=session.context, mark=HANDOFF_MARK, document=document,
                    skill=HANDOFF_SKILL,
                ))
            elif mark == STOP:
                phase(f"mark: stop at {session.context} tokens (mark {STOP_MARK}), "
                      "ending the session")
                doctor.kill_tree(process)
                break
            if session.result is not None and not process.stdin.closed:
                answer = follow_up(session) if follow_up else None
                if answer is None:
                    with contextlib.suppress(OSError, ValueError):
                        process.stdin.close()
                else:
                    session.result = None
                    _send(process, answer)
        session.returncode = process.wait()
        stderr_file.seek(0)
        session.stderr = stderr_file.read().decode("utf-8", errors="replace")
    return session


def _send(process: subprocess.Popen, text: str) -> None:
    """Write one stream-json user message to the session's stdin on a writer thread.

    The CLI writes hook frames to stdout before it reads its first message, so a prompt
    larger than the pipe buffer written from the reading thread deadlocks both sides.
    """
    line = json.dumps({"type": "user", "message": {"role": "user", "content": text}}) + "\n"
    threading.Thread(target=_write, args=(process.stdin, line), daemon=True).start()


def _write(stdin: Any, line: str) -> None:
    """Write and flush one line; a session that already closed its stdin is left as it is."""
    with contextlib.suppress(OSError, ValueError):
        stdin.write(line)
        stdin.flush()


def take_frame(session: Session, line: str) -> str | None:
    """Record one stream-json frame on the session; return the mark it crosses, if any."""
    text = line.strip()
    if not text:
        return None
    try:
        frame = json.loads(text)
    except json.JSONDecodeError:
        print(f"  claude: {text[:SUMMARY_CHARS]}", flush=True)
        return None
    kind = frame.get("type")
    if kind == "system" and frame.get("subtype") == "init":
        session.model = frame.get("model")
        print(f"  session open: model {session.model}", flush=True)
    elif kind == "system" and frame.get("subtype") == "compact_boundary":
        pre_tokens = (frame.get("compact_metadata") or {}).get("pre_tokens")
        session.compactions.append(pre_tokens)
        print(f"  compaction: pre_tokens {pre_tokens}", flush=True)
    elif kind == "assistant":
        for block in (frame.get("message") or {}).get("content") or []:
            if block.get("type") == "tool_use":
                name, tool_input = str(block.get("name")), block.get("input") or {}
                session.tool_calls.append((name, tool_input))
                print(f"  tool {name}: {summary(tool_input)}", flush=True)
        return _mark(session, frame)
    elif kind == "result":
        session.result = frame
        session.results.append(frame)
        print(
            f"  result: is_error {frame.get('is_error')}, {frame.get('num_turns')} turns",
            flush=True,
        )
    return None


def _mark(session: Session, frame: dict[str, Any]) -> str | None:
    """Update the context use from a main-thread assistant frame; return the mark crossed.

    Context use is the latest API call's input: `input_tokens + cache_read_input_tokens +
    cache_creation_input_tokens` of the frame's usage, never a sum over turns. A subagent's
    frame carries a non-null `parent_tool_use_id` and its own context, so it does not count.
    The freeze and hand-off marks fire once per session; a freeze not yet sent when the
    hand-off mark fires is never sent, since the hand off already ends the session.
    """
    usage = (frame.get("message") or {}).get("usage")
    if frame.get("parent_tool_use_id") is not None or not usage:
        return None
    session.context = sum(int(usage.get(key) or 0) for key in CONTEXT_KEYS)
    if session.context >= STOP_MARK:
        session.stopped = True
        return STOP
    if session.context >= HANDOFF_MARK and not session.handed_off:
        session.handed_off = True
        return HANDOFF
    if session.context >= FREEZE_MARK and not (session.frozen or session.handed_off):
        session.frozen = True
        return FREEZE
    return None


def summary(tool_input: dict[str, Any]) -> str:
    """Return one short line naming what a tool call acts on."""
    for key in SUMMARY_KEYS:
        if tool_input.get(key):
            return " ".join(str(tool_input[key]).split())[:SUMMARY_CHARS]
    return ""


def failure(session: Session) -> str | None:
    """Return why the session failed, or None when it ended cleanly.

    The window arrives only in the result frame, so the fixed marks apply during the
    session and the stop mark is checked against 90% of the window afterwards.
    """
    if session.stopped:
        return (
            f"the driver ended the session at the stop mark {STOP_MARK}: "
            f"{session.context} tokens of context"
        )
    if session.compactions:
        pre_tokens = ", ".join(str(tokens) for tokens in session.compactions)
        return f"the session compacted (compact_boundary), pre_tokens {pre_tokens}"
    if session.result is None:
        detail = session.stderr.strip().splitlines()
        said = detail[0] if detail else "nothing on stderr"
        return f"the session ended without a result frame (exit {session.returncode}): {said}"
    if session.result.get("is_error") is not False:
        said = " ".join(str(session.result.get("result") or "").split())[:SUMMARY_CHARS]
        return f"the session reported is_error: {said}"
    if session.returncode != 0:
        return f"claude exited {session.returncode} after a clean result frame"
    window = ((session.result.get("modelUsage") or {}).get(session.model) or {}).get(
        "contextWindow"
    )
    if not window:
        return f"the result frame reports no contextWindow for model {session.model}"
    if WINDOW_SHARE * window < STOP_MARK:
        return (
            f"the stop mark {STOP_MARK} exceeds 90% of the window {window} the session "
            f"reported ({int(WINDOW_SHARE * window)})"
        )
    return None


def denials(session: Session) -> list[str]:
    """Return each call a result frame lists under `permission_denials`, one line each.

    Every turn's result frame is read. A malformed frame never raises: a non-list value
    yields nothing, a non-object entry is skipped, and an entry whose `tool_input` is not
    an object is named by its tool alone.
    """
    lines = []
    for result in session.results:
        listed = result.get("permission_denials") if isinstance(result, dict) else None
        for denial in listed if isinstance(listed, list) else []:
            if isinstance(denial, dict):
                tool_input = denial.get("tool_input")
                shown = summary(tool_input) if isinstance(tool_input, dict) else ""
                lines.append(f"{denial.get('tool_name')} {shown}".rstrip())
    return lines
