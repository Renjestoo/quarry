"""Check the task-observer observation that `quarry drive` writes for a red stage end.

Usage: `observe_check.py`. Runs the real `new-observation.sh` and `session-start-scan.sh` of
the installed task-observer on a scratch workspace in the temp folder, never on the real log, and
runs no model turn. Prints every phase and exits 1 at the first failed expectation.
"""

from __future__ import annotations

import importlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import driver_check
from driver_check import SCRATCH_PARENT, SCRIPTS_DIR, CheckFailed

sys.path.insert(0, str(SCRIPTS_DIR))
observe = importlib.import_module("quarry_lib.observe")

REAL_LOG = Path.home() / ".claude" / observe.LOG_DIR
SCAN = Path.home() / observe.HELPER.parent / "session-start-scan.sh"
SCAN_TIMEOUT_SECONDS = 120
SKILLS = ("grilling", "domain-modeling")
DETAIL = (
    'the stage changed neither "CONTEXT.md" nor docs/adr/: the session wrote C:\\x\n'
    "and stopped on a second line"
)
WRITTEN = "written "


def main() -> int:
    """Run the observation cases on a scratch workspace and compare the real log around them."""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    before = files(REAL_LOG)
    print(f"phase: real log holds {before} files before the check", flush=True)
    scratch = Path(tempfile.mkdtemp(prefix="quarry-observe-check-", dir=SCRATCH_PARENT))
    saved = os.environ.pop(observe.WORKSPACE_ENV, None)
    print(f"scratch: {scratch}", flush=True)
    try:
        workspace = make_workspace(scratch / "workspace")
        os.environ[observe.WORKSPACE_ENV] = workspace.as_posix()
        check_written(scratch, workspace)
        check_two(scratch, workspace)
        check_hostile(scratch, workspace)
        os.environ.pop(observe.WORKSPACE_ENV)
        check_no_workspace(scratch, workspace)
        check_no_helper(scratch)
    except CheckFailed as error:
        print(f"CHECK FAILED: {error}", flush=True)
        return 1
    finally:
        if saved is None:
            os.environ.pop(observe.WORKSPACE_ENV, None)
        else:
            os.environ[observe.WORKSPACE_ENV] = saved
        driver_check.remove(scratch)
    after = files(REAL_LOG)
    if after != before:
        print(f"CHECK FAILED: C5 the real log held {before} files and now holds {after}")
        return 1
    print(f"CHECK C5: the real log still holds {after} files", flush=True)
    print("ALL CHECKS PASSED", flush=True)
    return 0


def files(folder: Path) -> int:
    """Return the number of files under `folder`, at any depth."""
    return sum(1 for path in folder.rglob("*") if path.is_file())


def make_workspace(root: Path) -> Path:
    """Make the folders the helper requires under `root`, and return `root`."""
    (root / observe.LOG_DIR / "archive").mkdir(parents=True)
    return root


def red(scratch: Path, home: Path | None = None, detail: str = DETAIL) -> str:
    """Record one constructed red grill stage end; return what `observe.record` returned."""
    text = observe.record(
        "grill", SKILLS, detail, ("session-a", "session-b"), ("scr-9",),
        scratch / "project", "scr-1", home,
    )
    print(f"phase: observation: {text}", flush=True)
    return text


def written(text: str, workspace: Path) -> Path:
    """Return the file a `written <path>` result names; it must lie in the scratch log."""
    if not text.startswith(WRITTEN):
        raise CheckFailed(f"expected {WRITTEN}<path>, got {text!r}")
    path = Path(text[len(WRITTEN):])
    if not path.is_file() or path.resolve().parent != (workspace / observe.LOG_DIR).resolve():
        raise CheckFailed(f"{path} is not a file in the scratch log")
    return path


def header(path: Path) -> list[str]:
    """Return the header lines of an observation file, between its two `---` lines."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return lines[1:lines.index("---", 1)]


def identity(path: Path) -> str:
    """Return the numeric id of an observation's header."""
    found = [line for line in header(path) if re.fullmatch(r"id: \d+", line)]
    if len(found) != 1:
        raise CheckFailed(f"{path.name} has no numeric id: line")
    return found[0].split()[1]


def check_written(scratch: Path, workspace: Path) -> None:
    """C1: a red stage gives a file whose header the scan parses and finds not suspect."""
    print("phase: C1 one red stage end", flush=True)
    path = written(red(scratch), workspace)
    lines, text = header(path), path.read_text(encoding="utf-8")
    skill = next((line for line in lines if line.startswith("skill:")), "")
    for line in ("status: open", "type: internal"):
        if line not in lines:
            raise CheckFailed(f"C1: {path.name} lacks {line!r}")
    if not all(name in skill for name in SKILLS) or DETAIL not in text:
        raise CheckFailed(f"C1: skill line {skill!r}, detail in body {DETAIL in text}")
    print(f"CHECK C1: {path.name} id {identity(path)}, {skill}, the body holds the detail")
    done = subprocess.run(
        [str(observe._bash()), SCAN.as_posix(), workspace.as_posix()],
        cwd=str(scratch), capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=SCAN_TIMEOUT_SECONDS, check=False,
    )
    last = next((line for line in reversed(done.stdout.splitlines()) if line.strip()), "")
    if done.returncode != 0 or "suspect: 0 " not in last or "parsed: 1 " not in last:
        raise CheckFailed(f"C1: the scan exited {done.returncode}, last line {last[:200]!r}")
    print(f"CHECK C1: the scan reads {last[:90]}", flush=True)


def check_two(scratch: Path, workspace: Path) -> None:
    """C2: two red stage ends in a row give two files with different ids."""
    print("phase: C2 two red stage ends in a row", flush=True)
    first, second = (written(red(scratch), workspace) for _ in range(2))
    if first == second or identity(first) == identity(second):
        raise CheckFailed(f"C2: {first.name} and {second.name} share an id")
    print(f"CHECK C2: ids {identity(first)} and {identity(second)}", flush=True)


def check_hostile(scratch: Path, workspace: Path) -> None:
    """C6: escape codes, a lone surrogate and 300 quotes give a clean file and a short title."""
    print("phase: C6 a detail with escape codes, a lone surrogate and 300 quotes", flush=True)
    detail = "\x1b[31mred\x1b[0m \ud800 " + '"' * 300 + " end"
    path = written(red(scratch, detail=detail), workspace)
    text = path.read_text(encoding="utf-8")
    unprintable = sorted({hex(ord(char)) for char in text if not char.isprintable()} - {"0xa"})
    if unprintable:
        raise CheckFailed(f"C6: {path.name} holds the characters {unprintable}")
    title = next(line for line in header(path) if line.startswith("title: "))
    inside = title[len('title: "'):-1]
    if len(inside) > observe.TITLE_CHARS or not title.endswith('"') or inside.endswith("\\"):
        raise CheckFailed(f"C6: the title holds {len(inside)} characters: {title[:80]!r}")
    print(f"CHECK C6: no control character, the title holds {len(inside)} characters", flush=True)


def scratch_home(scratch: Path, name: str, claude_md: str | None) -> Path:
    """Return a scratch home holding a copy of the real helper and, when given, a CLAUDE.md."""
    home = scratch / name
    (home / observe.HELPER).parent.mkdir(parents=True)
    shutil.copy2(Path.home() / observe.HELPER, home / observe.HELPER)
    if claude_md is not None:
        (home / observe.CLAUDE_MD).write_text(claude_md, encoding="utf-8")
    return home


def check_no_workspace(scratch: Path, workspace: Path) -> None:
    """C3: no workspace, or one without a log, is a skip; a CLAUDE.md line names one."""
    print("phase: C3 the environment variable unset", flush=True)
    log = workspace / observe.LOG_DIR
    count = files(log)
    for name, claude_md in (("home-bare", None), ("home-other", "# Global\n\nNo pin here.\n")):
        text = red(scratch, scratch_home(scratch, name, claude_md))
        if not text.startswith("skipped, no task-observer workspace") or files(log) != count:
            raise CheckFailed(f"C3: {name} gave {text!r}, log files {count} -> {files(log)}")
    pinned = f"## Task observer\n\n{observe.WORKSPACE_LINE}\n\n  {workspace.as_posix()}\n"
    written(red(scratch, scratch_home(scratch, "home-pinned", pinned)), workspace)
    bare = f"{observe.WORKSPACE_LINE}\n{(scratch / 'no-log').as_posix()}\n"
    text = red(scratch, scratch_home(scratch, "home-no-log", bare))
    if not text.startswith("skipped, the workspace"):
        raise CheckFailed(f"C3: a workspace without a log gave {text!r}")
    print("CHECK C3: no workspace skips, a pinned CLAUDE.md line writes, no log skips")


def check_no_helper(scratch: Path) -> None:
    """C4: a home without the helper is a skip."""
    print("phase: C4 task-observer not installed", flush=True)
    home = scratch / "home-empty"
    home.mkdir()
    text = red(scratch, home)
    if not text.startswith("skipped, task-observer is not installed"):
        raise CheckFailed(f"C4: gave {text!r}")
    print("CHECK C4: skipped", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
