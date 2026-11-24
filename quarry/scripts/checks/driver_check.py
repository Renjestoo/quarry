"""Check `quarry drive` end to end: a scratch project, a real bd tracker, real sessions.

Usage: `driver_check.py [green] [red]`, both runs by default. Each run is one real Claude
Code session. Prints every phase and exits 1 at the first failed expectation.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
QUARRY = SCRIPTS_DIR / "quarry.py"
SCRATCH_PARENT = Path(tempfile.gettempdir())
PREFIX = "scr"
TOOL_TIMEOUT_SECONDS = 300
GOALS = {
    "green": "Decide what the term Widget means in this project and record it in CONTEXT.md.",
    "red": "Reply with the two characters OK. Change no file.",
}
CONTEXT = (
    "# Scratch: project vocabulary\n\n## Vocabulary\n\n### Gadget\n\n"
    "A small tool this scratch project ships.\n\n_Avoid_: device.\n"
)
TRAILCODE_INSTALL = "npm install -g @trailhq/trail-code"
HEADROOM_ABSENT = re.compile(r"^Headroom\s+optional\s+absent\b", re.MULTILINE)
VERDICT = re.compile(r"grill check (green|red).*; issue (\S+); session ([0-9a-f-]{36})")


class CheckFailed(Exception):
    """One expectation of the check did not hold."""


def main(argv: list[str]) -> int:
    """Run the setup, the cheap refusal check and the requested driver runs."""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    runs = argv or list(GOALS)
    unknown = [run for run in runs if run not in GOALS]
    if unknown:
        print(f"unknown run(s) {unknown}; choose from {list(GOALS)}")
        return 2
    scratch = Path(tempfile.mkdtemp(prefix="quarry-driver-check-", dir=SCRATCH_PARENT))
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    print(f"scratch project: {scratch}", flush=True)
    venv_folder = None
    try:
        setup(scratch, env)
        check_unknown_issue(scratch, env)
        check_missing_part(scratch, env)
        venv_folder, venv_python = make_venv()
        for run in runs:
            check_run(scratch, env, run, venv_python if run == "red" else sys.executable)
    except CheckFailed as error:
        print(f"CHECK FAILED: {error}", flush=True)
        return 1
    finally:
        remove(scratch)
        if venv_folder is not None:
            remove(venv_folder)
    print(f"ALL CHECKS PASSED: {', '.join(runs)}", flush=True)
    return 0


def tool(scratch: Path, env: dict[str, str], command: list[str]) -> str:
    """Run one command in the scratch project, print its phase, and return its stdout."""
    executable = shutil.which(command[0]) or command[0]
    print(f"phase: {' '.join(command[:3])}", flush=True)
    done = subprocess.run(
        [executable, *command[1:]],
        cwd=str(scratch),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=TOOL_TIMEOUT_SECONDS,
        check=False,
    )
    if done.returncode != 0:
        raise CheckFailed(
            f"{' '.join(command[:3])} exited {done.returncode}: "
            f"{(done.stderr or done.stdout).strip()[:300]}"
        )
    return done.stdout


def setup(scratch: Path, env: dict[str, str]) -> None:
    """Make the scratch project: git, bd, a small CONTEXT.md, the atlas and the mesh."""
    tool(scratch, env, ["git", "init", "-q"])
    top = Path(tool(scratch, env, ["git", "rev-parse", "--show-toplevel"]).strip())
    if top.resolve() != scratch.resolve():
        raise CheckFailed(f"git resolved the repository to {top}, not the scratch {scratch}")
    (scratch / "CONTEXT.md").write_text(CONTEXT, encoding="utf-8")
    tool(scratch, env, [
        "bd", "init", "--prefix", PREFIX, "--non-interactive", "--quiet",
        "--skip-agents", "--skip-hooks",
    ])
    tool(scratch, env, ["graft", "build"])
    tool(scratch, env, [sys.executable, str(QUARRY), "init"])
    print("setup: done", flush=True)


def drive(
    scratch: Path, env: dict[str, str], args: list[str], python: str = sys.executable
) -> tuple[int, str]:
    """Run `quarry drive` under `python` as a real subprocess, echoing its output."""
    print(f"phase: quarry drive {' '.join(args)}", flush=True)
    lines = []
    with subprocess.Popen(
        [python, str(QUARRY), "drive", *args],
        cwd=str(scratch),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    ) as process:
        for line in process.stdout:
            print(f"  | {line.rstrip()}", flush=True)
            lines.append(line)
        code = process.wait()
    print(f"quarry drive exited {code}", flush=True)
    return code, "".join(lines)


def check_unknown_issue(scratch: Path, env: dict[str, str]) -> None:
    """Expect an unknown --issue to fail loudly before any session starts."""
    code, output = drive(scratch, env, ["--issue", f"{PREFIX}-nosuchissue", GOALS["red"]])
    refused = "quarry drive failed" in output and f"{PREFIX}-nosuchissue" in output
    if code == 0 or not refused or "session: start" in output:
        raise CheckFailed("an unknown --issue did not fail before the session started")
    print("CHECK unknown issue: refused before any session", flush=True)


def check_missing_part(scratch: Path, env: dict[str, str]) -> None:
    """Expect a run with Trailcode hidden from PATH to stop before any session."""
    entries = env["PATH"].split(os.pathsep)
    kept = [e for e in entries if not any(shutil.which(b, path=e) for b in ("graft", "trail"))]
    print(f"phase: hide Trailcode, {len(entries) - len(kept)} PATH folder(s) removed", flush=True)
    code, output = drive(scratch, {**env, "PATH": os.pathsep.join(kept)}, [GOALS["red"]])
    refused = "Trailcode is absent" in output and TRAILCODE_INSTALL in output
    if code == 0 or not refused or "session: start" in output:
        raise CheckFailed("a run without Trailcode did not stop before the session")
    print("CHECK Trailcode hidden: refused before any session, install printed", flush=True)


def make_venv() -> tuple[Path, str]:
    """Create a pip-less venv outside the scratch project; return its folder and python."""
    folder = Path(tempfile.mkdtemp(prefix="quarry-driver-venv-", dir=SCRATCH_PARENT))
    print(f"phase: create a throwaway venv in {folder}", flush=True)
    subprocess.run(
        [sys.executable, "-m", "venv", "--without-pip", str(folder / "venv")],
        check=True,
        timeout=TOOL_TIMEOUT_SECONDS,
    )
    python = next(
        p for p in (folder / "venv" / "Scripts" / "python.exe", folder / "venv" / "bin" / "python")
        if p.is_file()
    )
    return folder, str(python)


def decision_files(scratch: Path) -> dict[str, bytes]:
    """Return CONTEXT.md and every file under docs/adr/, by path."""
    adr = scratch / "docs" / "adr"
    paths = [scratch / "CONTEXT.md", *(adr.rglob("*") if adr.is_dir() else ())]
    return {str(path): path.read_bytes() for path in paths if path.is_file()}


def unit_lines(scratch: Path, env: dict[str, str]) -> list[str]:
    """Return the unit lines `quarry list` prints in the scratch project."""
    listed = tool(scratch, env, [sys.executable, str(QUARRY), "list"])
    return [line for line in listed.splitlines() if line.startswith("K")]


def check_run(scratch: Path, env: dict[str, str], run: str, python: str) -> None:
    """Drive one goal and check exit code, verdict, files, the bd note and the new unit.

    The red run uses a venv interpreter, where Headroom is absent: the run must report it
    and still start its session.
    """
    before_files = decision_files(scratch)
    before_units = unit_lines(scratch, env)
    code, output = drive(scratch, env, ["--until", "grill", GOALS[run]], python)
    if python != sys.executable and not HEADROOM_ABSENT.search(output):
        raise CheckFailed(f"{run}: Headroom is absent under {python}, but the run did not say so")
    match = VERDICT.search(output)
    if match is None:
        raise CheckFailed(f"{run}: the driver printed no verdict line")
    verdict, issue, session_id = match.groups()
    expect_green = run == "green"
    if (code == 0) != expect_green or verdict != run:
        raise CheckFailed(f"{run}: exit {code} with verdict {verdict}")
    if not expect_green and "changed neither" not in output:
        raise CheckFailed(f"{run}: the check is red for another cause than an unchanged project")
    changed = decision_files(scratch) != before_files
    if changed != expect_green:
        raise CheckFailed(f"{run}: decision files changed is {changed}")
    shown = tool(scratch, env, ["bd", "show", issue])
    if session_id not in shown or "quarry drive, stage grill" not in shown:
        raise CheckFailed(f"{run}: bd show {issue} lacks the driver's note for {session_id}")
    after_units = unit_lines(scratch, env)
    if len(after_units) != len(before_units) + 1:
        raise CheckFailed(f"{run}: units went from {len(before_units)} to {len(after_units)}")
    sys.path.insert(0, str(SCRIPTS_DIR))
    from quarry_lib.store import MeshStore

    sessions = {unit.session_id for unit in MeshStore(scratch / ".quarry").load_units()}
    if session_id not in sessions:
        raise CheckFailed(f"{run}: no sealed unit belongs to session {session_id}")
    print(
        f"CHECK {run}: exit {code}, verdict {verdict}, issue {issue} carries the note, "
        f"unit sealed for {session_id}",
        flush=True,
    )


def remove(scratch: Path) -> None:
    """Delete the scratch project, which must be the one this run made in the temp folder."""
    if scratch.resolve().parent != SCRATCH_PARENT.resolve():
        print(f"refusing to delete {scratch}: not directly under {SCRATCH_PARENT}", flush=True)
        return

    def clear_readonly(function, path, _info) -> None:
        os.chmod(path, stat.S_IWRITE)
        function(path)

    shutil.rmtree(scratch, onerror=clear_readonly)
    print(f"removed {scratch}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
