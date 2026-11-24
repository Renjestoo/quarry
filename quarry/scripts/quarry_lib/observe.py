"""Write one task-observer observation for a red end of a driver stage.

task-observer is an optional companion. The only write path of its log is its helper script
`new-observation.sh`, run here through bash; when the helper, the workspace, the log or a usable
bash is missing, the write is skipped and the run goes on unchanged.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from quarry_lib import doctor

HELPER = Path(".claude", "skills", "task-observer", "scripts", "new-observation.sh")
CLAUDE_MD = Path(".claude", "CLAUDE.md")
WORKSPACE_ENV = "TASK_OBSERVER_WORKSPACE"
WORKSPACE_LINE = "The task-observer workspace for this project is:"
LOG_DIR = Path("skill-observations", "observation-log")
HELPER_TIMEOUT_SECONDS = 120
TITLE_CHARS = 200
SIBLINGS = "none: written by the quarry driver, which runs no sibling check"
SUGGESTION = (
    "None stated. The driver records the red end; the review decides whether a skill change "
    "follows."
)
PRINCIPLE = "Not stated: the driver cannot judge one."


def record(
    stage: str,
    skills: Sequence[str],
    detail: str,
    session_ids: Sequence[str],
    halts: Sequence[str],
    project_root: Path,
    issue: str,
    home: Path | None = None,
) -> str:
    """Write one observation for a red stage end; return `written <path>` or `skipped, <reason>`.

    Args:
        skills: the directory names of the skill files the stage loads.
        session_ids: the sessions of the stage, stage and decider sessions alike.
        halts: the bd issues the halt filed.
        home: the user's home folder; None reads `Path.home()`.

    Never raises and has no effect on the run's verdict: every failure is a skip reason. The
    workspace is `TASK_OBSERVER_WORKSPACE`, else the line after `WORKSPACE_LINE` in
    `~/.claude/CLAUDE.md`. The helper is killed with its process tree after
    `HELPER_TIMEOUT_SECONDS`.
    """
    try:
        return _attempt(
            stage, skills, _printable(detail), session_ids, halts, project_root, issue,
            home or Path.home(),
        )
    except (OSError, ValueError) as error:
        return f"skipped, the observation could not be written: {error}"


def _attempt(
    stage: str,
    skills: Sequence[str],
    detail: str,
    session_ids: Sequence[str],
    halts: Sequence[str],
    project_root: Path,
    issue: str,
    home: Path,
) -> str:
    """Write the observation; return `written <path>` or `skipped, <reason>`.

    Raises:
        OSError: a file or folder could not be read.
        ValueError: the entry could not be encoded.
    """
    helper = home / HELPER
    if not helper.is_file():
        return f"skipped, task-observer is not installed: {helper.as_posix()} is missing"
    workspace = _workspace(home)
    if workspace is None:
        return (
            f"skipped, no task-observer workspace: {WORKSPACE_ENV} is unset and "
            f"{(home / CLAUDE_MD).as_posix()} names none"
        )
    if not (workspace / LOG_DIR).is_dir():
        return f"skipped, the workspace {workspace.as_posix()} has no {LOG_DIR.as_posix()}"
    bash = _bash()
    if bash is None:
        return "skipped, no bash that can run the helper: Git's bash not found, System32 refused"
    entry = _entry(stage, skills, detail, session_ids, halts, project_root, issue)
    try:
        handle, name = tempfile.mkstemp(prefix="quarry-observation-", suffix=".md")
    except OSError as error:
        return f"skipped, the entry file could not be created: {error}"
    entry_file = Path(name)
    try:
        with open(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(entry)
        return _run_helper(bash, helper, entry_file, f"drive-{stage}-red", workspace)
    except (OSError, ValueError) as error:
        return f"skipped, the helper could not run: {error}"
    finally:
        with contextlib.suppress(OSError):
            entry_file.unlink()


def _workspace(home: Path) -> Path | None:
    """Return the task-observer workspace root, or None when nothing names one."""
    named = os.environ.get(WORKSPACE_ENV, "").strip()
    if named:
        return Path(named)
    try:
        lines = (home / CLAUDE_MD).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    for index, line in enumerate(lines):
        if WORKSPACE_LINE in line:
            return next((Path(rest.strip()) for rest in lines[index + 1:] if rest.strip()), None)
    return None


def _bash() -> Path | None:
    """Return the bash that runs the helper, or None.

    On Windows `bash` on PATH can be the WSL launcher in System32, which cannot run the helper
    on Windows paths, so Git's own bash comes first, its `bin/bash.exe` launcher (which puts
    Git's tools on PATH) before `usr/bin/bash.exe`.
    """
    found = shutil.which("bash")
    if sys.platform != "win32":
        return Path(found) if found else None
    git = shutil.which("git")
    if git:
        for root in Path(git).resolve().parents:
            for candidate in (root / "bin" / "bash.exe", root / "usr" / "bin" / "bash.exe"):
                if candidate.is_file():
                    return candidate
    if found and "system32" not in Path(found).resolve().as_posix().casefold().split("/"):
        return Path(found)
    return None


def _run_helper(bash: Path, helper: Path, entry_file: Path, slug: str, workspace: Path) -> str:
    """Run the helper on the entry file; return `written <path>` or `skipped, <reason>`.

    Raises:
        OSError: bash could not start.
    """
    process = subprocess.Popen(
        [str(bash), helper.as_posix(), "--body", entry_file.as_posix(), slug,
         workspace.as_posix()],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        stdout, stderr = process.communicate(timeout=HELPER_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        doctor.kill_tree(process)
        return f"skipped, {helper.name} gave no answer within {HELPER_TIMEOUT_SECONDS}s"
    if process.returncode != 0:
        said = next((line.strip() for line in stderr.splitlines() if line.strip()), "")
        return f"skipped, {helper.name} exited {process.returncode}: {said or 'nothing on stderr'}"
    printed = stdout.strip().splitlines()
    if not printed:
        return f"skipped, {helper.name} exited 0 and printed no path"
    return f"written {printed[-1].strip()}"


def _printable(text: str) -> str:
    """Return `text` with each control character and lone surrogate replaced by a space.

    Line breaks and tabs stay. A check detail can hold terminal escape codes, which a YAML
    double-quoted scalar may not hold, and a lone surrogate, which UTF-8 cannot encode.
    """
    return "".join(char if char.isprintable() or char in "\n\t" else " " for char in text)


def _quoted(text: str) -> str:
    """Return `text` as a one-line YAML double-quoted scalar, its whitespace collapsed."""
    one_line = " ".join(_printable(text).split())
    return '"' + one_line.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _title(stage: str, detail: str) -> str:
    """Return the quoted title, cut so its text inside the quotes stays within `TITLE_CHARS`."""
    text = " ".join(f"quarry drive: the {stage} stage ended red: {detail}".split())[:TITLE_CHARS]
    while len(_quoted(text)) - 2 > TITLE_CHARS:
        text = text[:-1]
    return _quoted(text.rstrip())


def _entry(
    stage: str,
    skills: Sequence[str],
    detail: str,
    session_ids: Sequence[str],
    halts: Sequence[str],
    project_root: Path,
    issue: str,
) -> str:
    """Return the complete entry, its header in the field order of the helper's skeleton."""
    return "\n".join([
        "---",
        "id: __ID__",
        f"title: {_title(stage, detail)}",
        "status: open",
        "type: internal",
        f"skill: [{', '.join(skills)}]",
        "proposes_skill: []",
        "target_file: []",
        f"siblings_checked: {_quoted(SIBLINGS)}",
        f"area: {_quoted(f'quarry drive, {stage} stage check')}",
        "date: __DATE__",
        f"session_context: {_quoted(f'quarry drive in {project_root.name}, run issue {issue}')}",
        "parked_until:",
        "resolved:",
        "resolution:",
        "reference:",
        'commands_verified: "none"',
        "next_actor:",
        "use_evidence:",
        "escalated:",
        "---",
        "",
        f"**Issue:** The {stage} stage check of quarry drive ended red: {detail}",
        "",
        f"Sessions of the stage: {', '.join(session_ids) or 'none'}.",
        f"Halt issues filed: {', '.join(halts) or 'none'}.",
        "",
        f"**Suggested improvement:** {SUGGESTION}",
        "",
        f"**Principle:** {PRINCIPLE}",
        "",
    ])
