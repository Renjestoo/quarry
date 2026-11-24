"""PreToolUse deny guards turning the machine rules into enforced behavior.

Registered on Claude only. A Codex host sends the same payload and would be judged the
same, but a hook there runs under bypassed trust and its decision is discarded: measured
across all three sandbox modes and both deny conventions, the call proceeded every time.
Registering them there would spawn a process per tool call and enforce nothing, so Codex
keeps the Stop audit as its backstop instead.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Any

DENY = 2
GREP_DENY = (
    "quarry guard: this repo has a graft atlas and the machine rules forbid grep for "
    "code. Use the atlas instead: graft ask \"<what you are looking for>\", "
    "graft grep <pattern> (grouped by symbol), graft callers <symbol>, "
    "graft skeleton <file>. Shell commands that themselves invoke graft are allowed."
)
TODO_DENY = (
    "quarry guard: this repo tracks work in bd (the machine rules forbid TodoWrite and "
    "TaskCreate here). Use the tracker: bd create, bd update <id> --claim, bd close <id> "
    "--reason. Notes carry the handoff state; bd ready shows the frontier."
)
TASK_LIST_TOOLS = frozenset({"TodoWrite", "TaskCreate"})
RECALL_DENY = (
    "quarry guard: sealed units are searched, never read whole. Ask_Knowledge is the "
    "recall interface: it searches every unit at once and returns verbatim passages "
    "at citable addresses. Reading .quarry/units files directly defeats the recall "
    "budget and bypasses the immutability contract."
)
SKILL_TOOL = "Skill"
SHELL_TOOLS = frozenset({"Bash", "PowerShell"})
GATE_ENV = "QUARRY_GATE_FILE"
GATE_UNREADABLE = (
    "human gate: the tool call payload could not be read (not a JSON object with a "
    "tool_input object), so the Quarry driver refused it before it ran. Do not retry it "
    "another way; leave it for the user."
)
PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
SHELL_GREP = re.compile(r"(?:^|[;&|]\s*(?:sudo\s+)?)(?:grep|rg|findstr)\b")
QUOTED_SEGMENT = re.compile(r'"[^"]*"|\'[^\']*\'')
UNITS_PATH = ".quarry/units"
LEADING = r"^(?:sudo\s+)?(?:\w+=\S*\s+)*"
UNIT_READER = re.compile(
    LEADING + r"(?:cat|type|more|less|head|tail|sed|awk|strings|nl|od|xxd|ls|dir|tree|find"
    r"|Get-Content|gc|Get-ChildItem|gci|Select-String)\b",
    re.IGNORECASE,
)
INTERPRETER = re.compile(LEADING + r"\S*(?:python|node|pwsh)\S*\b", re.IGNORECASE)
COMMAND_SEPARATOR = re.compile(r"[;&|]+")
TRACKED_TOOL = re.compile(LEADING + r"(?:git|bd)\b")
SEARCH_PROGRAMS = frozenset({"grep", "rg", "findstr"})
NON_CODE_SUFFIXES = frozenset({
    "log", "txt", "md", "rst", "json", "jsonl", "yaml", "yml", "toml", "csv", "tsv", "xml",
    "ini", "cfg", "lock", "out",
})
NON_CODE_TYPES = frozenset({
    "md", "markdown", "json", "jsonl", "yaml", "toml", "txt", "log", "csv", "xml",
})
VALUE_OPTIONS = frozenset({"-e", "-f", "-g", "-t", "-A", "-B", "-C", "-m", "--regexp", "--file",
                           "--glob", "--type", "--include", "--max-count"})
FILTER_OPTIONS = frozenset({"-g", "-t", "--glob", "--type", "--include"})
RECURSIVE_OPTIONS = frozenset({"-r", "-R", "--recursive", "/s", "/S"})
GLOB_SUFFIX = re.compile(r"\.\{?([A-Za-z0-9,]+)\}?$")


def run(name: str, project_root: Path) -> int:
    """Judge one PreToolUse call from the hook payload on stdin; 2 denies, 0 allows.

    Host-neutral by measurement, not by assumption: a Codex PreToolUse payload captured
    from a real turn carries the same field names and the same tool vocabulary as Claude,
    `tool_name` "Bash" with `tool_input` an object holding `command`, even though that
    host records the call as its own `exec` tool everywhere else. Nothing here needs to
    know which host it is running under.

    The gate rule acts only in a session the driver started, which names its gate file in
    `GATE_ENV`. With the variable unset it allows before parsing the payload or importing
    the gate module, but still drains stdin, so the host never writes a large Write payload
    into a closed pipe. With it set, a payload that cannot be read is denied; the other
    rules allow one.

    Args:
        name: which rule to enforce: grep, todo, recall, flow, or gate.
        project_root: the project whose state (graft graph, bd database, mesh, pinned
            lane) decides whether the rule applies at all; absent substrate means allow.
    """
    gate_file = os.environ.get(GATE_ENV, "") if name == "gate" else None
    if gate_file == "":
        sys.stdin.buffer.read()
        return 0
    try:
        payload = json.load(sys.stdin)
    except (OSError, ValueError):
        payload = None
    tool_input = payload.get("tool_input") if isinstance(payload, dict) else None
    if not isinstance(tool_input, dict):
        if gate_file is None:
            return 0
        print(GATE_UNREADABLE, file=sys.stderr)
        return DENY
    tool_name = str(payload.get("tool_name", ""))
    if gate_file is not None:
        from quarry_lib.gate import judge

        cwd = payload.get("cwd")
        message = judge(tool_name, tool_input, str(cwd) if cwd else None, Path(gate_file))
    else:
        handler = {
            "grep": _grep,
            "todo": _todo,
            "recall": _recall,
            "flow": _flow,
        }.get(name)
        if handler is None:
            print(f"quarry guard: unknown guard {name}", file=sys.stderr)
            return 0
        message = handler(tool_name, tool_input, project_root)
    if message:
        print(message, file=sys.stderr)
        return DENY
    return 0


def _grep(tool_name: str, tool_input: dict[str, Any], root: Path) -> str:
    """Return the deny message when a code search bypasses the graft atlas.

    Only a search the atlas could answer is denied: one whose target holds a file the atlas
    indexed. Logs, data, docs and source the atlas never indexed (a reference tree, a
    folder outside the indexed repos) have no atlas answer, so grep is the right tool there
    and denying it left no way to search them at all. A filter (`glob`, `type`, `--include`)
    naming only data or doc formats is not a code search either.

    Quoted strings are stripped before finding the command word: a command word is never
    inside quotes, while prose arguments (issue reasons, commit messages) often carry the
    words harmlessly, and a semicolon inside such prose is punctuation, not a separator.

    Grep is a Claude tool with no Codex counterpart, where every search runs through the
    shell; the command half below covers that host on its own.
    """
    if not (root / "graft").is_dir():
        return ""
    if tool_name == "Grep":
        filters = [str(tool_input.get(key)) for key in ("glob", "type") if tool_input.get(key)]
        if filters and all(_non_code_filter(value) for value in filters):
            return ""
        target = root / str(tool_input.get("path") or ".")
        return GREP_DENY if _indexed(target, root) else ""
    if tool_name in SHELL_TOOLS:
        command = str(tool_input.get("command", ""))
        if "graft" in command:
            return ""
        for segment in COMMAND_SEPARATOR.split(command):
            searches = SHELL_GREP.search(QUOTED_SEGMENT.sub("", segment.strip()))
            if searches and _shell_search_indexed(segment, root):
                return GREP_DENY
    return ""


def _shell_search_indexed(segment: str, root: Path) -> bool:
    """Report whether one grep, rg or findstr command searches files the atlas indexed.

    Without a path operand the search reads stdin, unless it recurses (rg always does),
    in which case it searches the working directory.
    """
    try:
        tokens = [token.strip("\"'") for token in shlex.split(segment, posix=False)]
    except ValueError:
        return True
    names = [Path(token).stem.lower() for token in tokens]
    start = next((i for i, name in enumerate(names) if name in SEARCH_PROGRAMS), None)
    if start is None:
        return True
    program = names[start]
    positional, filters, explicit_pattern = [], [], False
    recursive = program == "rg"
    words = iter(tokens[start + 1:])
    for token in words:
        name, _, attached = token.partition("=")
        if name in VALUE_OPTIONS:
            value = attached or next(words, "")
            explicit_pattern |= name in {"-e", "-f", "--regexp", "--file"}
            if name in FILTER_OPTIONS:
                filters.append(value)
        elif token in RECURSIVE_OPTIONS:
            recursive = True
        elif not token.startswith("-") and not (program == "findstr" and token.startswith("/")):
            positional.append(token)
    if filters and all(_non_code_filter(value) for value in filters):
        return False
    paths = positional if explicit_pattern else positional[1:]
    if not paths:
        return recursive and _indexed(Path.cwd(), root)
    return any(_indexed(Path.cwd() / path, root) for path in paths)


def _non_code_filter(value: str) -> bool:
    """Report whether a glob or file-type filter names only data or documentation formats."""
    if value.lower() in NON_CODE_TYPES:
        return True
    match = GLOB_SUFFIX.search(value.replace("\\", "/").rsplit("/", 1)[-1])
    suffixes = match.group(1).lower().split(",") if match else []
    return bool(suffixes) and all(suffix in NON_CODE_SUFFIXES for suffix in suffixes)


def _indexed(target: Path, root: Path) -> bool:
    """Report whether an atlas holds a card for this file, or for any file under this folder.

    graft mirrors each indexed source file as `graft/<path without suffix>.md`, so a card's
    presence is the index itself; a path outside the project is never indexed. A workspace
    whose root is not a repository keeps no cards at the root: `graft/workspace.json` names
    the child repositories, and each child keeps its own `graft/` beside its sources.
    """
    try:
        target = target.resolve()
        bases = [root.resolve()]
        workspace = root / "graft" / "workspace.json"
        if workspace.is_file():
            children = json.loads(workspace.read_text(encoding="utf-8")).get("children", [])
            bases += [(root / str(child)).resolve() for child in children]
    except (OSError, ValueError, AttributeError):
        return False
    for base in bases:
        if target.is_dir() and base != target and target in base.parents:
            if any((base / "graft").rglob("*.md")):
                return True
            continue
        try:
            cards = base / "graft" / target.relative_to(base)
        except ValueError:
            continue
        if target.is_dir() and cards.is_dir() and any(cards.rglob("*.md")):
            return True
        if not target.is_dir() and cards.with_suffix(".md").is_file():
            return True
    return False


def _flow(tool_name: str, tool_input: dict[str, Any], root: Path) -> str:
    """Return the deny message when a Skill call leaves the lane this project is pinned to.

    Reaches only the agent's own skill calls. A user typing `/skill-name` does not go
    through the Skill tool, so no PreToolUse hook sees it, which is the right split: the
    lock exists to stop the agent wandering, never to refuse the user their own command.
    The Stop audit stays the backstop for everything this cannot see.

    Only skills quarry ships are judged, so an unrelated skill is never denied on the
    strength of a lane that says nothing about it.

    No Skill tool call has been observed reaching a Codex PreToolUse hook, so even were
    the guards registered there this one would have nothing to judge.

    The workflow and audit modules are imported here, not at module level: the other
    guards run on every Read, Grep and shell call and need neither.
    """
    from quarry_lib.audit import override_granted
    from webapp import flow

    current = flow.pinned(root)
    if tool_name != SKILL_TOOL or current is None:
        return ""
    requested = str(tool_input.get("skill", "")).strip().rsplit(":", 1)[-1]
    if not (PLUGIN_ROOT / "skills" / requested / "SKILL.md").is_file():
        return ""
    if requested in flow.allowed_skills(current["lane"], PLUGIN_ROOT) | set(flow.LANES):
        return ""
    if override_granted(root):
        return ""
    return (
        f"quarry flow lock: this project is pinned to {current['skill']} (lane "
        f"{current['lane']}), which does not include {requested}. Either stay on the lane, "
        f"release it with /quarry:flow-cancel and say why, or ask the user to write "
        f"\"{flow.OVERRIDE_PHRASE}\" for a single departure."
    )


def _todo(tool_name: str, _tool_input: dict[str, Any], root: Path) -> str:
    """Return the deny message when a session task list is started in a bd-tracked repo.

    Claude Code disables TodoWrite by default in favour of TaskCreate, TaskGet, TaskList and
    TaskUpdate, so a guard on TodoWrite alone never fired. Denying TaskCreate is enough: the
    other three only act on tasks it created.
    """
    if tool_name in TASK_LIST_TOOLS and (root / ".beads").is_dir():
        return TODO_DENY
    return ""


def _recall(tool_name: str, tool_input: dict[str, Any], _root: Path) -> str:
    """Return the deny message when sealed units are treated as files to browse.

    Covers reading and grepping unit files, and shell commands that list or walk the
    units directory: browsing the mesh to reconstruct history is the exact bypass the
    recall interface exists to replace.

    Naming the path is not itself a bypass. A command is denied only when it also shows
    intent to read: a reader or lister verb outside quotes, an interpreter that could open
    the file, or the path standing unquoted as an operand. git and bd are exempt because
    staging a sealed unit or quoting its path in an issue reason never puts unit contents
    in front of an agent, and denying those blocked committing the mesh itself.

    Judged one shell segment at a time, so `cd repo && git add <unit>` is exempt while
    `cat <unit> && git status` is not. Exempting a whole command line because git appears
    somewhere in it would make the guard trivially avoidable by appending a git call, and
    anchoring the exemption to the start of the line instead denied the ordinary ways of
    committing the mesh: a cd first, a chained commit, an inline env assignment.
    """
    target = str(tool_input.get("file_path") or tool_input.get("path") or "")
    if UNITS_PATH in target.replace("\\", "/"):
        return RECALL_DENY
    if tool_name not in SHELL_TOOLS:
        return ""
    command = str(tool_input.get("command", "")).replace("\\", "/")
    if UNITS_PATH not in command:
        return ""
    for segment in COMMAND_SEPARATOR.split(command):
        piece = segment.strip()
        if UNITS_PATH not in piece or TRACKED_TOOL.match(piece):
            continue
        unquoted = QUOTED_SEGMENT.sub("", piece)
        if UNIT_READER.match(piece) or INTERPRETER.match(piece) or UNITS_PATH in unquoted:
            return RECALL_DENY
    return ""
