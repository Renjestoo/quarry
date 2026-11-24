"""Check `quarry doctor`, `quarry install` and the parts notice as real subprocesses.

Doctor runs plain, with RTK, bd and Graphify hidden, as JSON, and with a scratch home that
lacks the Graphify skill. Install runs only as a dry run, with an unknown name, and on a part
that is present, so no check installs anything; the step runner runs constructed steps of
this interpreter. Graphify is hidden by a PATH without it and an interpreter whose scripts
folder lacks it: a throwaway venv in the temp folder. Prints every phase and exits 1 at the first
failed expectation.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

QUARRY = Path(__file__).resolve().parents[1] / "quarry.py"
SCRATCH_PARENT = Path(tempfile.gettempdir())
TIMEOUT_SECONDS = 300
PARTS = (
    "Matt Pocock's skills", "bd", "Trailcode", "RTK", "task-observer", "Headroom", "Graphify",
)
RTK_INIT = "rtk init -g --auto-patch"
WINGET = (
    "winget install rtk-ai.rtk --accept-source-agreements --accept-package-agreements "
    "--disable-interactivity"
)
RTK_PLATFORM = {"win32": WINGET, "darwin": "brew install rtk"}.get(
    sys.platform,
    "brew install rtk" if shutil.which("brew") else (
        "sh -c 'curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/"
        "install.sh | sh'"
    ),
)
INSTALLS = {
    "RTK": f"install: {RTK_PLATFORM}, then {RTK_INIT}",
    "bd": "install: npm install -g @beads/bd",
    "Graphify": "install: uv tool install graphifyy, then graphify install",
}
VALID_PARTS = ("rtk", "bd", "trailcode", "task-observer", "headroom", "graphify")
HIDDEN_RTK: dict[str, str] = {}

sys.path.insert(0, str(QUARRY.parent))
doctor_module = importlib.import_module("quarry_lib.doctor")
install_module = importlib.import_module("quarry_lib.install")


class CheckFailed(Exception):
    """One expectation of the check did not hold."""


def main() -> int:
    """Run every check and report the first failed expectation."""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    scratch = Path(tempfile.mkdtemp(prefix="quarry-doctor-check-", dir=SCRATCH_PARENT))
    print(f"scratch: {scratch}", flush=True)
    HIDDEN_RTK.update(LOCALAPPDATA=str(scratch / "appdata"), RTK_INSTALL_DIR=str(scratch / "nortk"))
    try:
        plain_code = check_plain()
        check_hidden("RTK", "rtk", sys.executable, plain_code)
        check_hidden("bd", "bd", sys.executable)
        venv = make_venv(scratch)
        check_hidden("Graphify", "graphify", venv, plain_code)
        check_tool_folder(scratch, venv, "Graphify", "graphify", "UV_TOOL_BIN_DIR")
        check_tool_folder(scratch, venv, "RTK", "rtk", "RTK_INSTALL_DIR")
        check_json()
        check_skill_missing(scratch)
        check_dry_run()
        check_unknown()
        check_present()
        check_runner(scratch)
        check_session_start(scratch)
    except CheckFailed as error:
        print(f"CHECK FAILED: {error}", flush=True)
        return 1
    finally:
        remove(scratch)
    print("ALL CHECKS PASSED: G1 plain, G2 RTK, G3 bd, G4 Graphify hidden, G5 JSON fields, "
          "G6 Graphify and Headroom unconfigured, G7 dry run, G8 unknown part, G9 present part, "
          "G10 step runner, G11 SessionStart notice, G12 uv tool folder", flush=True)
    return 0


def check_tool_folder(scratch: Path, python: str, part: str, binary: str, variable: str) -> None:
    """G12: a tool found only in the folder its installer uses is not reported absent."""
    print(f"phase: G12 {binary} only in the folder {variable} names", flush=True)
    folder = scratch / f"bin-{binary}"
    folder.mkdir()
    name, body = (
        (f"{binary}.cmd", f"@echo {binary} 9.9.9\n")
        if sys.platform == "win32"
        else (binary, f"#!/bin/sh\necho {binary} 9.9.9\n")
    )
    (folder / name).write_text(body, encoding="utf-8")
    (folder / name).chmod(0o755)
    _, rows, output = doctor(python, hidden_path(binary), {**HIDDEN_RTK, variable: str(folder)})
    if rows[part][1] == "absent" or "9.9.9" not in output:
        raise CheckFailed(f"G12: {part} in its installer's folder reported {rows[part][1]}")
    print(f"CHECK G12: {part} found in {folder}, version 9.9.9", flush=True)


def quarry(
    args: list[str], path: str, python: str = sys.executable,
    home: Path | None = None, cwd: Path | None = None, extra: dict[str, str] | None = None,
) -> tuple[int, str]:
    """Run `quarry.py` with PATH `path`, and `home` as the home folder; return code and output.

    `extra` adds environment variables. `HIDDEN_RTK` names folders without rtk, because the
    doctor also looks for rtk in the folders its installers use, outside PATH.
    """
    env = {**os.environ, "PATH": path, **(extra or {})}
    if home is not None:
        env |= {"USERPROFILE": str(home), "HOME": str(home)}
    done = subprocess.run(
        [python, str(QUARRY), *args],
        env=env,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=TIMEOUT_SECONDS,
        check=False,
    )
    output = done.stdout + done.stderr
    for line in output.splitlines():
        print(f"  | {line}", flush=True)
    print(f"quarry {' '.join(args)} exited {done.returncode}", flush=True)
    return done.returncode, output


def doctor(
    python: str, path: str, extra: dict[str, str] | None = None
) -> tuple[int, dict[str, list[str]], str]:
    """Run `quarry doctor` with `python` and PATH `path`; return exit code, part rows, output."""
    code, output = quarry(["doctor"], path, python, extra=extra)
    rows = {}
    for name in PARTS:
        line = next((x for x in output.splitlines() if x.startswith(f"{name} ")), None)
        if line is None:
            raise CheckFailed(f"no report line for {name}")
        rows[name] = line[len(name):].split()
    return code, rows, output


def hidden_path(binary: str) -> str:
    """Return PATH without the folders that hold `binary`."""
    entries = os.environ["PATH"].split(os.pathsep)
    kept = [entry for entry in entries if not shutil.which(binary, path=entry)]
    print(f"removed {len(entries) - len(kept)} PATH folder(s) holding {binary}", flush=True)
    return os.pathsep.join(kept)


def expected_code(rows: dict[str, list[str]]) -> int:
    """Return the exit code the rule demands: 1 when a required part is not present."""
    return int(any(row[0] == "required" and row[1] != "present" for row in rows.values()))


def check_plain() -> int:
    """G1: seven lines, each with a state, and an exit code that follows the rule."""
    print("phase: G1 plain run", flush=True)
    code, rows, _ = doctor(sys.executable, os.environ["PATH"])
    bad = {name: row[:2] for name, row in rows.items()
           if row[0] not in ("required", "optional")
           or row[1] not in ("present", "absent", "degraded")}
    if bad:
        raise CheckFailed(f"G1: malformed rows {bad}")
    if code != expected_code(rows):
        raise CheckFailed(f"G1: exit {code}, the rule demands {expected_code(rows)}")
    if code != 0:
        raise CheckFailed(f"G1: exit {code}; on this machine every required part must be present")
    print(f"CHECK G1: seven parts reported, exit {code} follows the rule", flush=True)
    return code


def check_hidden(part: str, binary: str, python: str, plain_code: int | None = None) -> None:
    """Hide `binary` from PATH; expect `part` absent with its install, and the right exit code."""
    print(f"phase: hide {binary} from PATH", flush=True)
    code, rows, output = doctor(python, hidden_path(binary), HIDDEN_RTK)
    if rows[part][1] != "absent" or INSTALLS[part] not in output:
        raise CheckFailed(f"{part} hidden: reported {rows[part][1]}, install line missing")
    if plain_code is None and code == 0:
        raise CheckFailed(f"{part} hidden: a required part is absent, yet exit 0")
    if plain_code is not None and code != plain_code:
        raise CheckFailed(f"{part} hidden: exit {code}, the plain run exited {plain_code}")
    print(f"CHECK {part} hidden: absent, install printed, exit {code}", flush=True)


def doctor_json(home: Path | None = None) -> dict[str, dict]:
    """Run `quarry doctor --json`, with `home` as the home folder; return the parts by name."""
    _, output = quarry(["doctor", "--json"], os.environ["PATH"], home=home)
    line = next((x for x in output.splitlines() if x.startswith("{")), None)
    if line is None:
        raise CheckFailed("doctor --json printed no JSON object")
    return {part["name"]: part for part in json.loads(line)["parts"]}


def check_json() -> None:
    """G5: every part in `doctor --json` holds `steps` and `manual`."""
    print("phase: G5 doctor --json fields", flush=True)
    parts = doctor_json()
    lacking = [name for name, part in parts.items() if "steps" not in part or "manual" not in part]
    if lacking or len(parts) != len(PARTS):
        raise CheckFailed(f"G5: {len(parts)} parts, these lack steps or manual: {lacking}")
    print("CHECK G5: every part holds steps and manual", flush=True)


def check_skill_missing(scratch: Path) -> None:
    """G6: in a scratch home Graphify lacks its skill and Headroom its MCP configuration.

    Both binaries still work, so each is degraded with its configure step only.
    """
    print("phase: G6 Graphify skill file missing", flush=True)
    home = scratch / "home"
    (home / ".claude").mkdir(parents=True)
    skill = home / ".claude" / "skills" / "graphify" / "SKILL.md"
    parts = doctor_json(home)
    graphify = parts["Graphify"]
    steps = graphify["steps"]
    if graphify["state"] != "degraded" or str(skill) not in graphify["reason"]:
        raise CheckFailed(f"G6: Graphify {graphify['state']}, reason {graphify['reason']!r}")
    if len(steps) != 1 or Path(steps[0][0]).stem != "graphify" or steps[0][1:] != ["install"]:
        raise CheckFailed(f"G6: Graphify steps {steps}, expected one `graphify install`")
    print(f"CHECK G6: Graphify degraded, names {skill}, step {steps[0]}", flush=True)
    headroom = parts["Headroom"]
    steps = headroom["steps"]
    if headroom["state"] != "degraded" or "Not configured" not in headroom["reason"]:
        raise CheckFailed(f"G6: Headroom {headroom['state']}, reason {headroom['reason']!r}")
    configure = ["mcp", "install"]
    if len(steps) != 1 or Path(steps[0][0]).stem != "headroom" or steps[0][1:] != configure:
        raise CheckFailed(f"G6: Headroom steps {steps}, expected one `headroom mcp install`")
    print(f"CHECK G6: Headroom not configured is degraded, step {steps[0]}", flush=True)
    companions = {name: parts[name] for name in ("RTK", "task-observer", "Headroom", "Graphify")}
    wrong = [name for name, part in companions.items() if part["required"]]
    missing = [name for name, part in companions.items() if part["state"] == "present"]
    if wrong or missing:
        raise CheckFailed(f"G6: required companions {wrong}; present in an empty home {missing}")
    print("CHECK G6: the four companions are not ready in an empty home and all optional")


def check_dry_run() -> None:
    """G7: a dry run with RTK hidden lists its install and configure steps and installs nothing."""
    print("phase: G7 install --dry-run rtk with rtk hidden", flush=True)
    path = hidden_path("rtk")
    code, output = quarry(["install", "--dry-run", "rtk"], path, extra=HIDDEN_RTK)
    if code != 0 or RTK_PLATFORM not in output or RTK_INIT not in output:
        raise CheckFailed(f"G7: exit {code}, expected exit 0 with {RTK_PLATFORM!r}, {RTK_INIT!r}")
    if shutil.which("rtk", path=path):
        raise CheckFailed("G7: rtk is on the hidden PATH after the dry run")
    print("CHECK G7: both RTK steps listed, exit 0, rtk still absent", flush=True)


def check_unknown() -> None:
    """G8: an unknown part name exits 1 and names the valid parts."""
    print("phase: G8 install nosuchpart", flush=True)
    code, output = quarry(["install", "nosuchpart"], os.environ["PATH"])
    unnamed = [name for name in VALID_PARTS if name not in output]
    if code != 1 or "nosuchpart" not in output or unnamed:
        raise CheckFailed(f"G8: exit {code}, valid parts not named: {unnamed}")
    print("CHECK G8: exit 1, every valid part named", flush=True)


def check_present() -> None:
    """G9: installing Graphify where it is present runs nothing and exits 0."""
    print("phase: G9 install graphify where it is present", flush=True)
    state = doctor_module.PROBES["Graphify"]("Graphify").state
    if state != doctor_module.PRESENT:
        raise CheckFailed(f"G9: Graphify is {state} here, so the check refuses to install it")
    code, output = quarry(["install", "graphify"], os.environ["PATH"])
    if code != 0 or "already present" not in output or "run: " in output:
        raise CheckFailed(f"G9: exit {code}, expected 'already present', no step run, exit 0")
    print("CHECK G9: already present, no step ran, exit 0", flush=True)


def check_runner(scratch: Path) -> None:
    """G10: the step runner stops at the first failing step and reports its exit code."""
    print("phase: G10 step runner", flush=True)
    marker = scratch / "third-step-ran"
    steps = (
        (sys.executable, "--version"),
        (sys.executable, "-c", "raise SystemExit(3)"),
        (sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"),
    )
    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        code = install_module.run_steps(steps)
    for line in printed.getvalue().splitlines():
        print(f"  | {line}", flush=True)
    if code != 3 or "exit 3" not in printed.getvalue() or marker.exists():
        raise CheckFailed(f"G10: returned {code}, third step ran: {marker.exists()}")
    print("CHECK G10: exit 3 reported, the third step never ran", flush=True)


def check_session_start(scratch: Path) -> None:
    """G11: SessionStart names a required part that is hidden, and no optional one.

    bd is required, so hiding it shows the notice. RTK is an optional companion, so hiding
    it shows none.
    """
    print("phase: G11 SessionStart parts notice", flush=True)
    project = scratch / "project"
    (project / ".quarry").mkdir(parents=True)
    for label, path, expected in (
        ("bd hidden", hidden_path("bd"), True),
        ("rtk hidden", hidden_path("rtk"), False),
        ("normal PATH", os.environ["PATH"], False),
    ):
        code, output = quarry(["hook", "SessionStart"], path, cwd=project, extra=HIDDEN_RTK)
        whole = "Quarry: work here survives" in output and "quarry hook" not in output
        if code != 0 or not whole:
            raise CheckFailed(f"G11 {label}: exit {code}, the injection is not whole")
        notice = next((x for x in output.splitlines() if x.startswith("Harness parts:")), "")
        if bool(notice) != expected or (expected and "bd" not in notice):
            raise CheckFailed(f"G11 {label}: notice {notice!r}, expected shown: {expected}")
        print(f"CHECK G11 {label}: notice {'shown' if expected else 'absent'}", flush=True)


def make_venv(scratch: Path) -> str:
    """Create a pip-less venv in the scratch folder and return its interpreter."""
    print("phase: create a throwaway venv", flush=True)
    venv = scratch / "venv"
    subprocess.run(
        [sys.executable, "-m", "venv", "--without-pip", str(venv)],
        check=True,
        timeout=TIMEOUT_SECONDS,
    )
    python = next(p for p in (venv / "Scripts" / "python.exe", venv / "bin" / "python")
                  if p.is_file())
    print(f"venv interpreter: {python}", flush=True)
    return str(python)


def remove(scratch: Path) -> None:
    """Delete the scratch folder, which must be the one this run made in the temp folder."""
    if scratch.resolve().parent != SCRATCH_PARENT.resolve():
        print(f"refusing to delete {scratch}: not directly under {SCRATCH_PARENT}", flush=True)
        return

    def clear_readonly(function, path, _info) -> None:
        os.chmod(path, stat.S_IWRITE)
        function(path)

    shutil.rmtree(scratch, onerror=clear_readonly)
    print(f"removed {scratch}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
