"""Stop-hook audit: an answer about earlier sessions must come from recall, not reconstruction."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from quarry_lib.store import MeshStore
from quarry_lib.transcripts import (
    HOST_SESSION_ENV,
    host_claude_transcript,
    newest_claude_transcript,
    newest_codex_rollout,
    zcode_rollout_path,
)
from webapp import flow

DENY = 2
AUDIT_TAIL_BYTES = 262144
CALL_VALUE = r'"(?:command|input|code)"\s*:\s*"(?:[^"\\]|\\.)*?'
RECALL_CALL = re.compile(
    r'"(?:name|tool)"\s*:\s*"[^"]*Ask_Knowledge[^"]*"'
    r"|" + CALL_VALUE + r"quarry\.py\W{1,6}ask\b"
)
ATLAS_TOOL = "graft"
ATLAS_CALL = re.compile(CALL_VALUE + r"\bgraft\b")
AGENT_RECORD = ('"type":"assistant"', '"role":"assistant"', '"type":"agent_message"')
GRAFT_READ_THRESHOLD = 4
READ_CALL = re.compile(r'"name":\s*"Read"')
SKILL_CALL = re.compile(r'"skill":\s*"([a-z0-9-]+)"')
PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
READ_REQUEST = re.compile(
    r"read (?:me |them |it )?(?:all|every|each|the whole|the entire|through)\b"
    r"|read [^.\n]{0,60}\bin full\b"
    r"|(?:all|every) [^.\n]{0,40}\bfiles?\b[^.\n]{0,40}\bread\b",
    re.IGNORECASE,
)
ATLAS_DENY_MESSAGE = (
    "quarry stop-audit: this session explored code by reading file after file without "
    "ever consulting the graft atlas this repo carries. Call graft ask (or graft "
    "skeleton for the files you were reading) before continuing; the atlas exists so "
    "this exploration is ranked, not brute-force."
)
WRITE_CALL = re.compile(
    r'"name":\s*"(?:Write|Edit|NotebookEdit)"|"type":\s*"patch_apply_end"'
)
SPECULATION = re.compile(
    r"(?:easy|easier|simple|simpler) to (?:add|extend|swap|plug)"
    r"|for (?:future|later) (?:extensibility|flexibility|use|needs|growth)"
    r"|in case (?:we|you|it) (?:later|ever|need|want)"
    r"|(?:when|if) (?:we|you) (?:later |ever )?(?:add|need|want) (?:another|a second|more)"
    r"|so (?:we|you) can (?:later |easily )?(?:swap|extend|plug|add another)"
    r"|future[- ]proof|extensib(?:le|ility) for"
    r"|allows? (?:us |you )?to add (?:more|new|other)"
    r"|ready for (?:future|additional|other) (?:providers|backends|implementations)",
    re.IGNORECASE,
)
GROUNDED = re.compile(
    r"removal test|second concrete use|two concrete uses|already has two"
    r"|architectural boundary|stated requirement|the ticket requires|required by the",
    re.IGNORECASE,
)
SCOPE_DENY_MESSAGE = (
    "quarry stop-audit: this turn wrote code and justified structure by what it would make "
    "easier later, without naming a requirement that needs it now. Apply the removal test "
    "from the quarry skill: remove the layer, interface or option, and name the stated "
    "requirement that becomes impossible, unsafe, incorrect, or materially harder to "
    "maintain. If nothing does, delete it and say so. If the boundary is architectural "
    "(authorization, storage, external providers, transactions) or a second concrete use "
    "exists today, say which, and the structure stays."
)
RECONSTRUCTION = re.compile(
    r"don'?t (?:\w+ ){0,2}have (?:any )?memory|no memory of (?:the|that|last|previous)"
    r"|wasn'?t in (?:that|the) (?:previous |last )?session"
    r"|have no recall|don'?t recall (?:the|that|it|any)"
    r"|cannot recall|reading what (?:it|they) recorded"
    r"|reconstruct(?:ing)? (?:this|that|the) from",
    re.IGNORECASE,
)
DENY_MESSAGE = (
    "quarry stop-audit: this reply reconstructs earlier sessions from records instead of "
    "recalling them. Call Ask_Knowledge with the underlying question, quote the passages it "
    "returns, and re-answer from them. Browsing .quarry or substituting bd memories for "
    "recall is what this audit exists to stop."
)


def audit_stop(project_root: Path, transcript: Path | None = None) -> int:
    """Deny (exit 2) when the session answered prior-session questions without recall.

    Fires only where recall was possible at all: a mesh with sealed units and a
    locatable session transcript. The transcript tail is scanned for reconstruction
    phrasing ("I don't have memory of that session") and for a recall call; the deny
    lands only when the phrasing is present and the tool was never called, so sessions
    that recall, or never touch history, pass untouched.

    A call, never a mention. Quarry's own injected contract names the tool, so accepting
    the bare word let quarry clear its own audit: counted across this project, roughly
    2,800 mentions under content, stdout, text, message, attributionMcpTool, hookName and
    a tool-search query, against 177 real calls. Both hosts record a call under a key the
    prose cannot occupy, Claude as the tool_use block's `name`
    (mcp__plugin_quarry_quarry_knowledge__Ask_Knowledge) and Codex as the MCP
    invocation's `tool`, which is what this matches.

    The CLI is recall too. A Codex session was denied for recalling four times through
    `quarry.py ask` from its own code, recorded under `input` and `code` rather than as an
    MCP call, so a `quarry.py ... ask` inside a command, input or code value counts. The
    value is scanned past escaped quotes, since code and quoted paths put a quote before
    the program name.

    The call is looked for in the whole transcript, the phrasing only in the tail. A recall
    made early in a long session, or followed by a large result, sits before the audited
    window (100 real calls across 363 rollouts, none inside its own tail), and denying a
    session for a call it made is worse than missing one. A 40 MB transcript scans in
    about 65 ms, measured, which the Stop hook can afford.
    """
    tail = _tail(project_root, require_mesh=True, transcript=transcript)
    if tail is None:
        return 0
    if _called(project_root, transcript, RECALL_CALL):
        return 0
    if RECONSTRUCTION.search(tail):
        print(DENY_MESSAGE, file=sys.stderr)
        return DENY
    return 0


def audit_stop_graft(project_root: Path, transcript: Path | None = None) -> int:
    """Deny (exit 2) when a session explored code heavily without ever consulting the atlas.

    Fires only where the atlas exists. Exploration-heavy means at least
    GRAFT_READ_THRESHOLD Read tool calls in the transcript tail; a session that ran
    any graft command passes, and so does one that merely edited a known file or two.

    The graft call is looked for in the whole transcript, the Read count only in the
    tail, since the count measures the current reply's exploration. A session that asked
    the atlas, was pushed past the audited window by a workflow launch and two recall
    results, then read six files was denied for never consulting it; a whole-file scan
    costs 51 ms on 39.8 MB, measured, the same trade audit_stop makes for recall.

    Ran, not mentioned. Quarry's own injected routing table names graft on every session,
    so the bare word cleared this audit before it counted anything (65 mentions in one
    Codex tail, the first being that table). An atlas use is a shell call whose command
    names graft, recorded under `command` on Claude and `input` or `code` on Codex, keys
    that injected prose never occupies. The value is scanned past escaped quotes: a
    pattern that stopped at the first quote saw none of a session's `cd "E:/..." &&
    graft ask` calls, and could not see a graft call from inside code at all.

    The Read count has no Codex counterpart and this audit cannot fire there. Codex's exec
    tool runs code rather than commands on this machine (14,577 exec calls, all JS, none
    beginning with a reader verb), so a file read is a line inside a program and leaves no
    record of its own to count.

    A user who asked for the files themselves passes too. Reading every file in a directory
    on request is not exploration, and the atlas cannot stand in for it: graft ranks and
    summarises, which is the opposite of what such a request asks for. The instruction is
    read from `user` records only, the same trust rule the flow override uses, so the agent
    cannot excuse its own hand-exploration by writing the words itself.
    """
    if not (project_root / ATLAS_TOOL).is_dir():
        return 0
    tail = _tail(project_root, require_mesh=False, transcript=transcript)
    if tail is None:
        return 0
    if _called(project_root, transcript, ATLAS_CALL):
        return 0
    if _user_asked_for_the_files(tail):
        return 0
    if len(READ_CALL.findall(tail)) >= GRAFT_READ_THRESHOLD:
        print(ATLAS_DENY_MESSAGE, file=sys.stderr)
        return DENY
    return 0


def audit_scope(project_root: Path, transcript: Path | None = None) -> int:
    """Deny (exit 2) when a turn built structure justified only by what it would allow later.

    Fires on the agent's own words rather than on a reading of the code, for the same reason
    the flow audit refuses to guess: an audit that judges intent teaches the agent to argue
    with it. The observable fact is a turn that wrote files and justified some of what it
    wrote by future benefit ("makes it easy to add another provider") while naming no present
    requirement for it.

    Grounded reasoning clears it: the removal test, a second concrete use today, an
    architectural boundary, or a stated requirement. Essential complexity is never described
    this way, so error handling, validation, concurrency control, persistence and security
    boundaries pass without special-casing.

    A write is a Write, Edit or NotebookEdit tool call on Claude and a patch_apply_end
    event on Codex, which is how that host records every apply_patch (22,215 such events
    across the rollouts on this machine, none under a Claude tool name).

    Both phrasings are read from the agent's own records only. Quarry's injected
    instructions name the removal test and stated requirements in every session, so read
    from the whole tail the grounding clause was satisfied by quarry rather than by the
    agent, and satisfied only when the injection happened to fall inside the audited
    window. The same trust rule the flow override applies, in the other direction: the
    user's words for instructions, the agent's words for what it argued.
    """
    tail = _tail(project_root, require_mesh=False, transcript=transcript)
    if tail is None:
        return 0
    if not WRITE_CALL.search(tail):
        return 0
    said = "\n".join(_agent_lines(tail))
    if GROUNDED.search(said):
        return 0
    if SPECULATION.search(said):
        print(SCOPE_DENY_MESSAGE, file=sys.stderr)
        return DENY
    return 0


def audit_flow(project_root: Path, transcript: Path | None = None) -> int:
    """Deny (exit 2) when the reply used a skill the pinned lane excludes.

    Fires only where a lane is pinned. The departure has to be observable in the transcript
    as a skill invocation naming a skill the lane does not permit; nothing is denied on an
    impression of intent, because an audit that guesses teaches the agent to argue with it.

    Claude records that invocation as a Skill tool call. Codex records no skill invocation
    at all (its call records are custom_tool_call, function_call and mcp_tool_call_end,
    none of them a skill), so on that host this audit cannot fire and does not pretend to.

    The override is honoured only when the user wrote it. The phrase is looked for in
    records of type `user`, never anywhere in the tail, since the tail also holds the
    agent's own words and it must not be able to grant itself an exception.
    """
    current = flow.pinned(project_root)
    if current is None:
        return 0
    tail = _tail(project_root, require_mesh=False, transcript=transcript)
    if tail is None:
        return 0
    allowed = flow.allowed_skills(current["lane"], PLUGIN_ROOT) | set(flow.LANES)
    invoked = {name for name in SKILL_CALL.findall(tail)}
    departed = sorted(name for name in invoked - allowed
                      if (PLUGIN_ROOT / "skills" / name / "SKILL.md").is_file())
    if not departed:
        return 0
    if _user_granted_override(tail):
        return 0

    print(
        f"quarry flow lock: this project is pinned to {current['skill']} (lane "
        f"{current['lane']}), and this reply used {', '.join(departed)}, which that lane "
        f"excludes. Either stay on the lane, release it with /quarry:flow-cancel and say "
        f"why, or ask the user to write \"{flow.OVERRIDE_PHRASE}\" for a single departure.",
        file=sys.stderr,
    )
    return DENY


def override_granted(project_root: Path) -> bool:
    """Report whether the user granted a single flow departure in this session's transcript."""
    tail = _tail(project_root, require_mesh=False)
    return bool(tail) and _user_granted_override(tail)


def _user_granted_override(tail: str) -> bool:
    """Report whether the user themselves wrote the override phrase in this session's tail."""
    return any(flow.OVERRIDE_PHRASE in line.casefold() for line in _user_lines(tail))


def _user_asked_for_the_files(tail: str) -> bool:
    """Report whether the user themselves asked for files to be read exhaustively."""
    return any(READ_REQUEST.search(line) for line in _user_lines(tail))


def _user_lines(tail: str) -> list[str]:
    """Return the tail's `user` records, the only place an instruction to the agent comes from.

    Both callers depend on this exclusion rather than on scanning the tail: the tail also
    holds the agent's own words, and an audit an agent can talk itself out of enforces
    nothing.
    """
    return [line for line in tail.splitlines() if '"type":"user"' in line.replace(" ", "")]


def _agent_lines(tail: str) -> list[str]:
    """Return the tail's records that are the agent's own: what it said and what it called.

    Claude keeps those under `type: assistant`; Codex splits them across `agent_message`
    events and `role: assistant` response items. Injected hook text lives in neither (an
    `attachment` on Claude, a non-assistant message on Codex), which is the whole reason to
    filter: an audit that reads the instructions it was given as the agent's reasoning
    excuses the agent for having been instructed.
    """
    return [line for line in tail.splitlines()
            if any(key in line.replace(" ", "") for key in AGENT_RECORD)]


def _called(project_root: Path, transcript: Path | None, call: re.Pattern[str]) -> bool:
    """Report whether the session made the call anywhere in its transcript, not only its tail."""
    path = _current_transcript(project_root, transcript)
    if path is None:
        return False
    try:
        return call.search(path.read_bytes().decode("utf-8", "replace")) is not None
    except OSError:
        return False


def _tail(project_root: Path, require_mesh: bool,
          transcript: Path | None = None) -> str | None:
    """Return the current turn of the session transcript, or None when there is nothing to audit.

    The turn starts at the last real user prompt inside the final AUDIT_TAIL_BYTES. Every
    audit judges the reply in hand: read from the whole tail, a sentence or skill call from
    an earlier turn denied every later turn until it scrolled out, and a one-turn flow
    override granted departures for as long as it stayed in the window.
    """
    if require_mesh:
        store = MeshStore(project_root / ".quarry")
        if not store.units_dir.is_dir() or not any(store.units_dir.glob("K*.md")):
            return None
    transcript = _current_transcript(project_root, transcript)
    if transcript is None:
        return None
    try:
        size = transcript.stat().st_size
        with transcript.open("rb") as handle:
            handle.seek(max(0, size - AUDIT_TAIL_BYTES))
            return _current_turn(handle.read().decode("utf-8", "replace"))
    except OSError:
        return None


def _current_turn(tail: str) -> str:
    """Return the tail from its last real user prompt on, or the whole tail when none is in it.

    A real prompt is a Claude `user` record that is neither a tool result (`toolUseResult`)
    nor host-injected (`isMeta`, which is how a Stop hook's own feedback is recorded, so a
    turn continued after a block stays one turn), or a Codex `user_message` event.
    """
    lines = tail.splitlines()
    for index in range(len(lines) - 1, -1, -1):
        if '"user' not in lines[index]:
            continue
        try:
            record = json.loads(lines[index])
        except ValueError:
            continue
        if not isinstance(record, dict):
            continue
        claude_prompt = (record.get("type") == "user" and "toolUseResult" not in record
                         and not record.get("isMeta"))
        payload = record.get("payload")
        codex_prompt = isinstance(payload, dict) and payload.get("type") == "user_message"
        if claude_prompt or codex_prompt:
            return "\n".join(lines[index:])
    return tail


def _current_transcript(project_root: Path, provided: Path | None = None) -> Path | None:
    """Return the current session's transcript on any host, or None.

    Exact ids before guesses, for the same reason sealing prefers them: auditing the wrong
    session is worse than auditing none, and modification time cannot tell this session
    from a subagent or a second window on the same project.

    A path the host named in its hook payload outranks everything else, being the session
    itself rather than an inference about it. Without it the Claude scan below wins on any
    machine where Claude has touched this project, so a Codex hook audited a Claude
    conversation; Codex exports no session variable to reach instead (its 53 CODEX_* names
    carry no session, thread or transcript id).
    """
    if provided is not None and provided.is_file():
        return provided
    session_id = os.environ.get("CLAUDE_SESSION_ID", "")
    if session_id:
        path = zcode_rollout_path(session_id)
        if path.is_file():
            return path
    host_id = os.environ.get(HOST_SESSION_ENV, "")
    if host_id:
        exact = host_claude_transcript(host_id, project_root)
        if exact is not None:
            return exact
    transcript = newest_claude_transcript(project_root)
    if transcript is not None:
        return transcript
    return newest_codex_rollout(project_root)
