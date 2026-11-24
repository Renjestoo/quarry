"""Check the human gates with no model turn: `quarry guard gate` as a subprocess, then the note.

G1 to G4 feed PreToolUse payloads on stdin to `quarry.py guard gate`, with the driver's gate
variable naming a gate file in a scratch project in the temp folder. G5 feeds a constructed result
frame through the driver's own frame and note functions. Prints every phase and exits 1 at the
first failed expectation.
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

QUARRY = Path(__file__).resolve().parents[1] / "quarry.py"
SCRIPTS_DIR = QUARRY.parent
SCRATCH_PARENT = Path(tempfile.gettempdir())
TIMEOUT_SECONDS = 60
DENY = 2
HUMAN_STEP = "The user does this step personally"

sys.path.insert(0, str(SCRIPTS_DIR))
driver = importlib.import_module("quarry_lib.driver")
sessions = importlib.import_module("quarry_lib.sessions")
gate = importlib.import_module("quarry_lib.gate")

DENIED = (
    ("Bash", "git push", "push"),
    ("Bash", "git push --force origin main", "force push"),
    ("Bash", "echo ok && git push", "push"),
    ("Bash", 'bash -c "git push"', "push"),
    ("Bash", "git rebase -i HEAD~2", "history rewrite"),
    ("Bash", "git reset --hard HEAD~1", "history rewrite"),
    ("Bash", "git commit --amend -m x", "history rewrite"),
    ("Bash", "git branch -D old", "branch or tag delete"),
    ("Bash", "pip install requests", "install"),
    ("Bash", "npm install -g x", "install"),
    ("Bash", "rm -rf ../other", "delete outside the project"),
    ("PowerShell", r"Remove-Item C:\Windows\Temp\x", "delete outside the project"),
    ("Bash", "gh auth login", "credential"),
    ("Bash", "cat .env", "credential"),
    ("Bash", "cat .env.local", "credential"),
    ("PowerShell", "type .env.production", "credential"),
    ("Bash", "if true; then git push; fi", "push"),
    ("Bash", "for x in a; do git push; done", "push"),
    ("Bash", "! git push", "push"),
    ("Bash", "timeout 60 git push", "push"),
    ("Bash", "env -i git push", "push"),
    ("Bash", "xargs git push", "push"),
    ("Bash", "git --git-dir .git push", "push"),
    ("Bash", "git --git-dir=.git push", "push"),
    ("Bash", "git --work-tree . push origin main", "push"),
    ("Bash", "git --namespace x push", "push"),
    ("PowerShell", r"Remove-Item -Path:C:\Windows\Temp\x", "delete outside the project"),
    ("PowerShell", "Push-Location ..; Remove-Item -Recurse other", "delete outside the project"),
    ("Bash", "conda install numpy", "install"),
    ("Bash", "mamba install x", "install"),
    ("Bash", "uv add requests", "install"),
    ("Bash", "py -3 -m pip install x", "install"),
    ("Bash", "python -m pip install x", "install"),
    ("Bash", "pipx install x", "install"),
    ("PowerShell", "Install-Module x", "install"),
    ("PowerShell", "Install-Package x", "install"),
    ("Bash", "git reset --soft HEAD~3", "history rewrite"),
    ("Bash", "git reset --mixed HEAD~1", "history rewrite"),
    ("Bash", "git reset HEAD^", "history rewrite"),
    ("Bash", "git reset origin/main", "history rewrite"),
    ("Bash", "git branch -f main HEAD~3", "history rewrite"),
    ("Bash", "git update-ref -d refs/heads/x", "history rewrite"),
    ("Bash", "git update-ref refs/heads/main HEAD~1", "history rewrite"),
    ("Bash", "python quarry.py install bd", "install"),
    ("Bash", '"$QUARRY_PYTHON" "x/scripts/quarry.py" install all', "install"),
    ("Bash", '"$QUARRY_PYTHON" "C:/Users/Jo Doe/plugins/quarry.py" install bd', "install"),
)
ALLOWED = (
    "git status",
    "git log --oneline -5",
    'git commit -m "work"',
    "python -m ruff check .",
    "rm -rf build",
    'echo "git push is forbidden"',
    "git log --grep push",
    "git reset HEAD file.txt",
    "git reset -- HEAD~1",
    "pytest -k install",
    'echo "if then git push"',
    "cat .env.example",
    "timeout 60 pytest -k install",
    "git --git-dir .git status",
    "Remove-Item -Recurse:$true build",
    "python quarry.py doctor",
)
SCOPE_DENIED = ("echo x > a.txt", "git commit -m x", "sed -i s/a/b/ f.txt")
SCOPE_ALLOWED = ("git status", "cat README.md")


class CheckFailed(Exception):
    """One expectation of the check did not hold."""


def main() -> int:
    """Run G1 to G5 and report the first failed expectation."""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    scratch = Path(tempfile.mkdtemp(prefix="quarry-gate-check-", dir=SCRATCH_PARENT))
    project = scratch / "project"
    (project / ".quarry").mkdir(parents=True)
    print(f"scratch project: {project}", flush=True)
    try:
        with gate.stage_scope(project, "grill", True) as env:
            check_denied(project, env)
            check_allowed(project, env)
            check_malformed(project, env)
        with gate.stage_scope(project, "check", False) as env:
            check_scope(project, env)
        check_inert(project)
        check_note(project)
    except CheckFailed as error:
        print(f"CHECK FAILED: {error}", flush=True)
        return 1
    finally:
        remove(scratch)
    print("ALL CHECKS PASSED: G1 gates deny, G2 ordinary work allowed, G3 step scope, "
          "G4 inert outside the driver, G5 denials in the note", flush=True)
    return 0


def guard(project: Path, env: dict[str, str], tool: str, tool_input: dict,
          raw: str | None = None) -> tuple[int, str]:
    """Run `quarry.py guard gate` on one payload, or on `raw` text; return exit code and stderr."""
    payload = {
        "session_id": "gate-check",
        "transcript_path": str(project / "transcript.jsonl"),
        "cwd": str(project),
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": tool_input,
    }
    base = {key: value for key, value in os.environ.items() if key != gate.GATE_ENV}
    done = subprocess.run(
        [sys.executable, str(QUARRY), "guard", "gate"],
        cwd=str(project),
        env={**base, **env},
        input=json.dumps(payload) if raw is None else raw,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=TIMEOUT_SECONDS,
        check=False,
    )
    return done.returncode, done.stderr.strip()


def expect(project: Path, env: dict[str, str], label: str, tool: str, tool_input: dict,
           gate_name: str | None) -> None:
    """Expect a deny naming `gate_name`, or an allow when it is None."""
    code, reason = guard(project, env, tool, tool_input)
    shown = tool_input.get("command") or tool_input.get("file_path")
    if gate_name is None:
        if code != 0:
            raise CheckFailed(f"{label}: {tool} {shown!r} exited {code}, expected allow: {reason}")
        print(f"CHECK {label}: allow {tool} {shown!r}", flush=True)
        return
    if code != DENY or f"human gate: {gate_name}." not in reason or HUMAN_STEP not in reason:
        raise CheckFailed(
            f"{label}: {tool} {shown!r} exited {code}, expected deny by {gate_name!r}: {reason!r}"
        )
    print(f"CHECK {label}: deny {tool} {shown!r} -> human gate: {gate_name}", flush=True)


def check_denied(project: Path, env: dict[str, str]) -> None:
    """G1: every gated command is denied with a reason naming its gate."""
    print("phase: G1 gated commands", flush=True)
    for tool, command, gate_name in DENIED:
        expect(project, env, "G1", tool, {"command": command}, gate_name)


def check_allowed(project: Path, env: dict[str, str]) -> None:
    """G2: ordinary work and a Write inside the project are allowed while the stage writes."""
    print("phase: G2 ordinary work", flush=True)
    for command in ALLOWED:
        expect(project, env, "G2", "Bash", {"command": command}, None)
    write = {"file_path": str(project / "CONTEXT.md"), "content": "x"}
    expect(project, env, "G2", "Write", write, None)


def check_malformed(project: Path, env: dict[str, str]) -> None:
    """G2: a payload that is not a JSON object is denied in a driver session, else allowed."""
    print("phase: G2 malformed payloads", flush=True)
    for raw in ("not json", "[1, 2]", '{"tool_name": "Bash", "tool_input": "git push"}'):
        code, reason = guard(project, env, "", {}, raw=raw)
        if code != DENY or "could not be read" not in reason:
            raise CheckFailed(f"G2: payload {raw!r} exited {code}, expected deny: {reason!r}")
        print(f"CHECK G2: deny malformed payload {raw!r}", flush=True)
        code, reason = guard(project, {}, "", {}, raw=raw)
        if code != 0:
            raise CheckFailed(f"G2: payload {raw!r} outside a driver session exited {code}")
        print(f"CHECK G2: allow malformed payload {raw!r} outside a driver session", flush=True)


def check_scope(project: Path, env: dict[str, str]) -> None:
    """G3: a step scope that denies writing denies the write tools and write-shaped commands."""
    print("phase: G3 step scope denies writing", flush=True)
    write = {"file_path": str(project / "CONTEXT.md"), "content": "x"}
    expect(project, env, "G3", "Write", write, gate.WRITE_GATE)
    for command in SCOPE_DENIED:
        expect(project, env, "G3", "Bash", {"command": command}, gate.WRITE_GATE)
    for command in SCOPE_ALLOWED:
        expect(project, env, "G3", "Bash", {"command": command}, None)


def check_inert(project: Path) -> None:
    """G4: with the driver's variable unset the rule allows even a push."""
    print("phase: G4 outside a driver session", flush=True)
    expect(project, {}, "G4", "Bash", {"command": "git push"}, None)


def check_note(project: Path) -> None:
    """G5: each call a result frame lists under permission_denials appears in the note."""
    print("phase: G5 denials recorded from the result frame", flush=True)
    written = str(project / "CONTEXT.md")
    frame = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "num_turns": 3,
        "result": "done",
        "permission_denials": [
            {"tool_name": "Bash", "tool_use_id": "toolu_1",
             "tool_input": {"command": "git push origin main"}},
            {"tool_name": "Write", "tool_use_id": "toolu_2",
             "tool_input": {"file_path": written, "content": "x"}},
        ],
    }
    session = sessions.Session(session_id="gate-check")
    sessions.take_frame(session, json.dumps(frame))
    note = driver._note(project, "grill", session, "red, gate check", None)
    for line in ("denied: Bash git push origin main", f"denied: Write {written}"):
        if line not in note.splitlines():
            raise CheckFailed(f"G5: {line!r} missing from the note:\n{note}")
        print(f"CHECK G5: note carries {line!r}", flush=True)
    clean = sessions.Session(session_id="gate-check-clean")
    sessions.take_frame(clean, json.dumps({**frame, "permission_denials": []}))
    if "denied: none" not in driver._note(project, "grill", clean, "green", None).splitlines():
        raise CheckFailed("G5: a result frame without denials does not give 'denied: none'")
    print("CHECK G5: no denials gives 'denied: none'", flush=True)
    for shape in (5, "abc", None):
        odd = sessions.Session(session_id="gate-check-odd")
        odd.results = [{"permission_denials": shape}]
        if sessions.denials(odd) != []:
            raise CheckFailed(f"G5: denials {shape!r} did not give an empty list")
        print(f"CHECK G5: malformed denials {shape!r} give an empty list", flush=True)
    mixed = sessions.Session(session_id="gate-check-mixed")
    mixed.results = [{"permission_denials": [
        "x",
        {"tool_name": "Bash", "tool_input": "git push"},
        {"tool_name": "Bash", "tool_input": ["x"]},
        {"tool_name": "Bash", "tool_input": {"command": "git push"}},
    ]}]
    listed = sessions.denials(mixed)
    if listed != ["Bash", "Bash", "Bash git push"]:
        raise CheckFailed(f"G5: mixed entries not listed by what can be named: {listed}")
    print("CHECK G5: mixed malformed entries listed by what can be named", flush=True)


def remove(scratch: Path) -> None:
    """Delete the scratch folder, which must be the one this run made in the temp folder."""
    if scratch.resolve().parent != SCRATCH_PARENT.resolve():
        print(f"refusing to delete {scratch}: not directly under {SCRATCH_PARENT}", flush=True)
        return
    shutil.rmtree(scratch)
    print(f"removed {scratch}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
