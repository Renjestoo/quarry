"""Report each of the harness's seven parts as present, absent or degraded.

The probes only look: each runs a part's version or status call or reads its files, and
installs nothing. For a part that is not present the part carries the steps that make it
ready on this platform and the manual text no command covers; `quarry install` runs them.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import sysconfig
import tomllib
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

PRESENT = "present"
ABSENT = "absent"
DEGRADED = "degraded"
PLUGIN_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = PLUGIN_ROOT / "skills"
LIFECYCLE_SKILLS = ("grilling", "domain-modeling", "spec", "tickets", "implement", "code-review")
CLAUDE_HOME = Path.home() / ".claude"
TASK_OBSERVER_SKILL = CLAUDE_HOME / "skills" / "task-observer" / "SKILL.md"
GRAPHIFY_SKILL = CLAUDE_HOME / "skills" / "graphify" / "SKILL.md"
ACTIVATION_MARKER = "task-observer activation block"
VERSION_TIMEOUT_SECONDS = 30
NAME_WIDTH = 22
VERSION_NUMBER = re.compile(r"\d+(?:\.\d+)+")
RTK_HOOK_CALL = re.compile(r"(?<![\w.-])rtk(?:\.exe)?\s+hook\b", re.IGNORECASE)
HOOK_SCRIPT_BYTES = 65_536
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---", re.DOTALL)
FRONTMATTER_VERSION = re.compile(r"^\s*version:\s*[\"']?([^\"'\s]+)", re.MULTILINE)
HEADROOM_AGENT = "Claude Code:"
SKILLS_PART = "Matt Pocock's skills"
TASK_OBSERVER_PART = "task-observer"
UV_TOOL_BIN = os.environ.get("UV_TOOL_BIN_DIR") or str(
    Path(os.environ.get("XDG_BIN_HOME") or Path.home() / ".local" / "bin")
)
TOOL_FOLDERS = (sysconfig.get_path("scripts"), UV_TOOL_BIN)
RTK_FOLDERS = (
    str(Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "Microsoft" / "WinGet" / "Links"),
    os.environ.get("RTK_INSTALL_DIR") or str(Path.home() / ".local" / "bin"),
)
TOOLS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "bd": (("bd",), ()),
    "Trailcode": (("trail", "graft"), ()),
    "RTK": (("rtk",), RTK_FOLDERS),
    "Headroom": (("headroom",), TOOL_FOLDERS),
    "Graphify": (("graphify",), TOOL_FOLDERS),
}
PLUGIN_INSTALL = "claude plugin update quarry@renjestoo, then restart the host"
BD_STEPS = (("npm", "install", "-g", "@beads/bd"),)
TRAILCODE_STEPS = (("npm", "install", "-g", "@trailhq/trail-code"),)
RTK_INIT = ("init", "-g", "--auto-patch")
RTK_SCRIPT = "https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh"
TASK_OBSERVER_STEPS = ((
    "npx", "--yes", "skills@1.8.1", "add", "rebelytics/one-skill-to-rule-them-all",
    "--skill", "task-observer", "--global", "--agent", "claude-code", "--yes",
),)
ACTIVATION_MANUAL = (
    "add the task-observer activation block from "
    f"{TASK_OBSERVER_SKILL.parent / 'references' / 'environments.md'} to "
    f"{CLAUDE_HOME / 'CLAUDE.md'}"
)
HEADROOM_STEPS = (("uv", "tool", "install", "headroom-ai[all]"), ("headroom", "mcp", "install"))
GRAPHIFY_STEPS = (("uv", "tool", "install", "graphifyy"), ("graphify", "install"))


@dataclass(frozen=True)
class Part:
    """One part's probe result; `reason`, `steps` and `manual` are empty when it is present.

    `steps` are the argv lists that make the part ready on this platform, in run order, and
    `manual` is what a person or agent must do that no command does. `install` is derived:
    each step as a shell-quoted line, then the manual text, joined with ", then ".
    """

    name: str
    required: bool
    state: str
    version: str = ""
    reason: str = ""
    steps: tuple[tuple[str, ...], ...] = ()
    manual: str = ""
    install: str = field(init=False)

    def __post_init__(self) -> None:
        """Derive `install` from `steps` and `manual`."""
        lines = [shlex.join(step) for step in self.steps] + ([self.manual] if self.manual else [])
        object.__setattr__(self, "install", ", then ".join(lines))


def probe() -> list[Part]:
    """Probe the seven parts in report order, running each installed tool's version call."""
    return [check(name) for name, check in PROBES.items()]


def not_ready() -> list[str]:
    """Return the names of the required parts that are not ready, judged without running a program.

    The required parts are the ones quarry's own code calls: the bundled skills, bd and
    Trailcode. A tool counts as ready when its binary is found, so a binary whose version
    call fails is seen only by `probe`. The optional companions (RTK, task-observer, Headroom,
    Graphify) are left out: `probe` and `/quarry:setup` report them, and a user who declined
    one is not told again at each session start.
    """
    ready = {
        SKILLS_PART: _skills(SKILLS_PART).state == PRESENT,
        "bd": _locate("bd") is not None,
        "Trailcode": _locate("Trailcode") is not None,
    }
    return [name for name, is_ready in ready.items() if not is_ready]


def report_line(part: Part) -> str:
    """Return the part's report line: name, required or optional, state, version, and why not."""
    line = (
        f"{part.name:<{NAME_WIDTH}}{'required' if part.required else 'optional':<10}"
        f"{part.state:<10}{part.version or '-'}"
    )
    if part.state != PRESENT:
        line += f"  reason: {part.reason}  install: {part.install}"
    return line


def print_report(parts: list[Part]) -> int:
    """Print one line per part and a summary; return 1 when a required part is not present."""
    for part in parts:
        print(report_line(part), flush=True)
    blocking = [part for part in parts if part.required and part.state != PRESENT]
    missing = [part for part in parts if not part.required and part.state != PRESENT]
    code = 1 if blocking else 0
    required = (
        "required parts not ready: " + ", ".join(f"{p.name} ({p.state})" for p in blocking)
        if blocking
        else "every required part present"
    )
    optional = (
        "; optional parts not present: " + ", ".join(f"{p.name} ({p.state})" for p in missing)
        if missing
        else ""
    )
    print(f"doctor: {required}{optional}; exit {code}", flush=True)
    return code


def print_json(parts: list[Part]) -> int:
    """Print the parts as one JSON object, `{"parts": [...], "exit": code}`; return the code.

    Each part holds the fields of `Part`. The code is 1 when a required part is not present,
    as in `print_report`.
    """
    code = 1 if any(part.required and part.state != PRESENT for part in parts) else 0
    print(json.dumps({"parts": [asdict(part) for part in parts], "exit": code}), flush=True)
    return code


def find_binary(binary: str) -> str | None:
    """Return the executable of a program from PATH, then from the extra folders of its part.

    The extra folders are the running interpreter's scripts folder and the folder where
    `uv tool install` puts executables (`UV_TOOL_BIN_DIR`, else `XDG_BIN_HOME`, else
    `~/.local/bin`), which is often not on PATH just after an install.
    """
    if found := shutil.which(binary):
        return found
    for binaries, folders in TOOLS.values():
        for folder in folders if binary in binaries else ():
            if found := shutil.which(binary, path=folder):
                return found
    return None


def _locate(name: str) -> tuple[str, str] | None:
    """Return the command to run a tool part by and its executable, or None when not found.

    The command is the bare binary name when it is on PATH, else the full path found in one
    of the part's extra folders, so a step still finds a tool that is not on PATH.
    """
    for binary in TOOLS[name][0]:
        if found := find_binary(binary):
            return (binary if shutil.which(binary) else found), found
    return None


def _tool(name: str, required: bool, steps: tuple[tuple[str, ...], ...]) -> Part:
    """Return the part for the first of its binaries on PATH, then in its extra folders."""
    located = _locate(name)
    if located is None:
        binaries, folders = TOOLS[name]
        where = "on PATH" + "".join(f" or in {folder}" for folder in folders)
        reason = f"no {' or '.join(binaries)} {where}"
        return Part(name, required, ABSENT, reason=reason, steps=steps)
    return _versioned(name, required, steps, located[1])


def _call(argv: list[str]) -> tuple[int, str, str]:
    """Run one probe call; return its exit code, stdout and stderr.

    Raises:
        OSError: the program could not start.
        subprocess.TimeoutExpired: no answer within VERSION_TIMEOUT_SECONDS; the process
            tree is killed first.
    """
    process = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        stdout, stderr = process.communicate(timeout=VERSION_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        kill_tree(process)
        raise
    return process.returncode, stdout, stderr


def _versioned(
    name: str, required: bool, steps: tuple[tuple[str, ...], ...], executable: str
) -> Part:
    """Return the part present with its version, or degraded when its version call fails."""
    label = Path(executable).stem
    try:
        code, stdout, stderr = _call([executable, "--version"])
    except OSError as error:
        return Part(name, required, DEGRADED, reason=f"{executable}: {error}", steps=steps)
    except subprocess.TimeoutExpired:
        reason = f"{executable} --version gave no answer within {VERSION_TIMEOUT_SECONDS}s"
        return Part(name, required, DEGRADED, reason=reason, steps=steps)
    if code != 0:
        detail = (stderr or stdout).strip().splitlines()
        said = detail[0] if detail else "no output on either stream"
        reason = f"{executable} --version failed (exit {code}): {said}"
        return Part(name, required, DEGRADED, reason=reason, steps=steps)
    lines = (stdout.strip() or stderr.strip()).splitlines()
    if not lines:
        reason = f"{executable} --version printed nothing"
        return Part(name, required, DEGRADED, reason=reason, steps=steps)
    number = VERSION_NUMBER.search(lines[-1])
    version = number.group(0) if number else lines[-1].strip()
    return Part(name, required, PRESENT, version=f"{version} ({label})")


def kill_tree(process: subprocess.Popen) -> None:
    """Kill a process with its children, then collect its remaining output.

    An npm tool is a `.cmd` shim on Windows: killing only cmd.exe leaves its node child
    holding the output pipes open, and collecting the output would then wait for ever.
    """
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(process.pid)],
            capture_output=True,
            check=False,
        )
    else:
        process.kill()
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.communicate(timeout=VERSION_TIMEOUT_SECONDS)


def _skills(name: str) -> Part:
    """Return the bundled lifecycle skills, present when every one ships in the plugin."""
    missing = [
        skill for skill in LIFECYCLE_SKILLS if not (SKILLS_DIR / skill / "SKILL.md").is_file()
    ]
    if missing:
        reason = f"{SKILLS_DIR} lacks {', '.join(missing)}"
        return Part(name, True, ABSENT, reason=reason, manual=PLUGIN_INSTALL)
    plugin = tomllib.loads((PLUGIN_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    count = len(list(SKILLS_DIR.glob("*/SKILL.md")))
    return Part(name, True, PRESENT, version=f"{plugin['project']['version']} ({count} skills)")


def _rtk_install() -> tuple[str, ...]:
    """Return the command that installs RTK on this platform."""
    if sys.platform == "win32":
        return (
            "winget", "install", "rtk-ai.rtk", "--accept-source-agreements",
            "--accept-package-agreements", "--disable-interactivity",
        )
    if sys.platform == "darwin" or shutil.which("brew"):
        return ("brew", "install", "rtk")
    return ("sh", "-c", f"curl -fsSL {RTK_SCRIPT} | sh")


def _rtk(name: str) -> Part:
    """Return RTK, degraded when its binary works but no Claude hook runs it."""
    part = _tool(name, False, (_rtk_install(), ("rtk", *RTK_INIT)))
    if part.state != PRESENT:
        return part
    missing_hook = _rtk_hook_missing()
    if missing_hook is None:
        return part
    steps = ((_locate(name)[0], *RTK_INIT),)
    return Part(name, False, DEGRADED, part.version, reason=missing_hook, steps=steps)


def _rtk_hook_missing() -> str | None:
    """Return why no command hook in the user's Claude settings runs rtk, or None if one does.

    A hook runs rtk when its command, an argument, or the text of a script file an argument
    names calls `rtk hook`, RTK's own hook entry point. A hook whose script is missing or
    no longer calls it does not count.
    """
    settings = CLAUDE_HOME / "settings.json"
    try:
        loaded = json.loads(settings.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return f"{settings} does not exist, so no hook runs rtk"
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return f"{settings} could not be read: {error}"
    hooks = loaded.get("hooks") if isinstance(loaded, dict) else None
    if not isinstance(hooks, dict):
        return f"{settings} has no hooks map"
    if loaded.get("disableAllHooks") is True:
        return f"{settings} sets disableAllHooks, so no hook runs rtk"
    for groups in hooks.values():
        for group in groups if isinstance(groups, list) else []:
            entries = group.get("hooks") if isinstance(group, dict) else None
            for hook in entries if isinstance(entries, list) else []:
                if isinstance(hook, dict) and _calls_rtk(hook):
                    return None
    return f"no hook in {settings} calls `rtk hook`"


def _calls_rtk(hook: dict) -> bool:
    """Return whether one command hook calls `rtk hook`, directly or through a script it names."""
    args = hook.get("args")
    words = [str(hook.get("command", "")), *map(str, args if isinstance(args, list) else [])]
    texts = list(words)
    for word in words:
        path = Path(word)
        with contextlib.suppress(OSError, ValueError, UnicodeDecodeError):
            if path.is_file() and path.stat().st_size <= HOOK_SCRIPT_BYTES:
                texts.append(path.read_text(encoding="utf-8"))
    return any(RTK_HOOK_CALL.search(text) for text in texts)


def _task_observer(name: str) -> Part:
    """Return task-observer, degraded without a version or without its activation block."""
    if not TASK_OBSERVER_SKILL.is_file():
        reason = f"{TASK_OBSERVER_SKILL} does not exist"
        return Part(
            name, False, ABSENT, reason=reason, steps=TASK_OBSERVER_STEPS, manual=ACTIVATION_MANUAL
        )
    try:
        skill_text = TASK_OBSERVER_SKILL.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        reason = f"{TASK_OBSERVER_SKILL} could not be read: {error}"
        return Part(
            name, False, DEGRADED, reason=reason, steps=TASK_OBSERVER_STEPS,
            manual=ACTIVATION_MANUAL,
        )
    frontmatter = FRONTMATTER.match(skill_text)
    found = frontmatter and FRONTMATTER_VERSION.search(frontmatter.group(1))
    if not found:
        reason = f"the frontmatter of {TASK_OBSERVER_SKILL} declares no version"
        return Part(
            name, False, DEGRADED, reason=reason, steps=TASK_OBSERVER_STEPS,
            manual=ACTIVATION_MANUAL,
        )
    version = found.group(1)
    instructions = CLAUDE_HOME / "CLAUDE.md"
    try:
        activated = ACTIVATION_MARKER in instructions.read_text(encoding="utf-8", errors="replace")
        reason = f"no line in {instructions} contains '{ACTIVATION_MARKER}'"
    except OSError as error:
        activated = False
        reason = f"{instructions} could not be read: {error}"
    if not activated:
        return Part(name, False, DEGRADED, version, reason=reason, manual=ACTIVATION_MANUAL)
    return Part(name, False, PRESENT, version=version)


def _headroom(name: str) -> Part:
    """Return Headroom, degraded when `headroom mcp status` does not show Claude Code configured."""
    part = _tool(name, False, HEADROOM_STEPS)
    if part.state != PRESENT:
        return part
    command, executable = _locate(name)
    unconfigured = _headroom_unconfigured(executable)
    if unconfigured is None:
        return part
    steps = ((command, "mcp", "install"),)
    return Part(name, False, DEGRADED, part.version, reason=unconfigured, steps=steps)


def _headroom_unconfigured(executable: str) -> str | None:
    """Return why Headroom's MCP status does not show Claude Code configured, or None if it does.

    Configured means a line naming `Claude Code:` holds the capitalised word `Configured` and
    no `Not `, so `Not configured` and `Not detected` both count as not configured.
    """
    called = f"{executable} mcp status"
    try:
        code, stdout, stderr = _call([executable, "mcp", "status"])
    except OSError as error:
        return f"{called}: {error}"
    except subprocess.TimeoutExpired:
        return f"{called} gave no answer within {VERSION_TIMEOUT_SECONDS}s"
    if code != 0:
        detail = (stderr or stdout).strip().splitlines()
        said = detail[0] if detail else "no output on either stream"
        return f"{called} failed (exit {code}): {said}"
    line = next((x.strip() for x in stdout.splitlines() if HEADROOM_AGENT in x), None)
    if line is None:
        return f"{called} names no '{HEADROOM_AGENT}' line"
    if "Configured" in line and "Not " not in line:
        return None
    return f"{called} reports '{line}'"


def _graphify(name: str) -> Part:
    """Return Graphify, degraded when its binary works but its Claude skill file is missing."""
    part = _tool(name, False, GRAPHIFY_STEPS)
    if part.state != PRESENT or GRAPHIFY_SKILL.is_file():
        return part
    steps = ((_locate(name)[0], "install"),)
    reason = f"{GRAPHIFY_SKILL} does not exist"
    return Part(name, False, DEGRADED, part.version, reason=reason, steps=steps)


PROBES: dict[str, Callable[[str], Part]] = {
    SKILLS_PART: _skills,
    "bd": lambda name: _tool(name, True, BD_STEPS),
    "Trailcode": lambda name: _tool(name, True, TRAILCODE_STEPS),
    "RTK": _rtk,
    TASK_OBSERVER_PART: _task_observer,
    "Headroom": _headroom,
    "Graphify": _graphify,
}
