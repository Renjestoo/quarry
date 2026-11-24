"""Run the steps that make chosen harness parts ready, as `quarry install` does."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

from quarry_lib.doctor import PRESENT, PROBES, TOOLS, Part, find_binary, probe, report_line

ALL = "all"
MISSING_PROGRAM = 127
UNRUNNABLE_PROGRAM = 126
NEEDS = {
    "npm": "npm on PATH (Node.js)",
    "npx": "npx on PATH (Node.js)",
    "uv": "uv on PATH",
    "winget": "winget",
    "brew": "brew",
}


def run(names: list[str], dry_run: bool) -> int:
    """Install and configure the named parts, or `all` that are not present; return the exit code.

    Names match the doctor's part names case-insensitively. An unknown name runs nothing and
    returns 1. A dry run prints each chosen part's steps and manual text and returns 0;
    otherwise the code is 0 only when every chosen part is present after its steps.
    """
    by_name = {name.lower(): name for name in PROBES}
    wanted = {name.lower() for name in names}
    unknown = [name for name in names if name.lower() not in by_name and name.lower() != ALL]
    if unknown:
        valid = ", ".join([*by_name, ALL])
        print(f"install: unknown part {', '.join(unknown)}; valid parts: {valid}", flush=True)
        return 1
    if ALL in wanted:
        chosen = [part for part in probe() if part.name.lower() in wanted or part.state != PRESENT]
    else:
        chosen = [PROBES[name](name) for key, name in by_name.items() if key in wanted]
    if not chosen:
        print("install: every part is present, nothing to install", flush=True)
        return 0
    if dry_run:
        for part in chosen:
            _show(part)
        print("install: dry run, nothing ran", flush=True)
        return 0
    ready = [_install(part) for part in chosen]
    failed = [part.name for part, is_ready in zip(chosen, ready, strict=True) if not is_ready]
    code = 1 if failed else 0
    summary = f"not ready: {', '.join(failed)}" if failed else "every chosen part present"
    print(f"install: {summary}; exit {code}", flush=True)
    return code


def run_steps(steps: tuple[tuple[str, ...], ...]) -> int:
    """Run steps in order with output streamed to the terminal and stdin closed.

    Each program is resolved just before its step runs, so a step can use a program an
    earlier step installed. Returns 0, or at the first failing step its exit code: 127 when
    its program is not found, 126 when it cannot start. Later steps never run.
    """
    for step in steps:
        print(f"run: {shlex.join(step)}", flush=True)
        executable = _resolve(step[0])
        if executable is None:
            print(f"stopped: needs {_needs(step[0])}", flush=True)
            return MISSING_PROGRAM
        try:
            code = subprocess.run(
                [executable, *step[1:]], stdin=subprocess.DEVNULL, check=False
            ).returncode
        except OSError as error:
            print(f"stopped: {executable} could not start: {error}", flush=True)
            return UNRUNNABLE_PROGRAM
        if code != 0:
            print(f"stopped: `{shlex.join(step)}` failed with exit {code}", flush=True)
            return code
    return 0


def _install(part: Part) -> bool:
    """Run one part's steps, probe it again and print its doctor line; return whether present."""
    print(f"phase: {part.name}: start", flush=True)
    if part.state == PRESENT:
        print(f"{part.name}: already present", flush=True)
        return True
    missing = _missing_programs(part)
    if missing:
        print(f"{part.name}: needs {', '.join(missing)}; skipped, no step ran", flush=True)
    elif part.steps and run_steps(part.steps) == 0:
        print(f"{part.name}: every step passed", flush=True)
    after = PROBES[part.name](part.name)
    print(report_line(after), flush=True)
    if after.manual:
        print(f"{part.name}: left for you: {after.manual}", flush=True)
    return after.state == PRESENT


def _missing_programs(part: Part) -> list[str]:
    """Return what the part's steps need that is not found, before any of them runs.

    A step after the first whose program is the part's own tool is left out: an earlier step
    installs it, so it is resolved when its step runs.
    """
    own = TOOLS.get(part.name, ((), ()))[0]
    return [
        _needs(step[0])
        for index, step in enumerate(part.steps)
        if not (index and Path(step[0]).stem.lower() in own) and _resolve(step[0]) is None
    ]


def _resolve(program: str) -> str | None:
    """Return the executable a step's program names, or None when it is not found.

    A Windows npm tool is a `.cmd` shim, which only a resolved path runs without a shell.
    A tool that `uv tool install` just put outside PATH is found in its part's extra folders.
    """
    return find_binary(program) or (program if Path(program).is_file() else None)


def _needs(program: str) -> str:
    """Return the missing program as the user should read it."""
    return NEEDS.get(Path(program).stem.lower(), f"{program} on PATH")


def _show(part: Part) -> None:
    """Print a part with its state, its steps and its manual text, running nothing."""
    print(f"phase: {part.name}: {part.state}", flush=True)
    if part.state == PRESENT:
        print(f"{part.name}: already present", flush=True)
        return
    for number, step in enumerate(part.steps, 1):
        print(f"  step {number}: {shlex.join(step)}", flush=True)
    if part.manual:
        print(f"  left for you: {part.manual}", flush=True)
