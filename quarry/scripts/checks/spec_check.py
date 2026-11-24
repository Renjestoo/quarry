"""Check the spec stage of `quarry drive`: constructed inputs, then one real run.

Usage: `spec_check.py [fixture] [real]`, `fixture` by default. `fixture` runs no model turn:
it feeds a scratch project with a real bd tracker and a real mesh to the stage's own check,
prompt and retry functions, and runs the engine CLI only where it refuses before a session.
`real` drives one goal through grill and spec with real Claude Code sessions: two stage
sessions, and one decider session for each question point a stage sends. The real goal
settles every product choice itself, so that the run proves the chain and not how a decider
judges an open question. Prints every phase and exits 1 at the first failed expectation.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import sys
import tempfile
import uuid
from pathlib import Path

import driver_check
from driver_check import PREFIX, SCRATCH_PARENT, SCRIPTS_DIR, CheckFailed
from marks_check import INIT, MODEL, result, stream, transcript_records

sys.path.insert(0, str(SCRIPTS_DIR))
dispatch = importlib.import_module("quarry_lib.dispatch")
driver = importlib.import_module("quarry_lib.driver")
stages = importlib.import_module("quarry_lib.stages")
store = importlib.import_module("quarry_lib.store")
transcripts = importlib.import_module("quarry_lib.transcripts")

RUNS = ("fixture", "real")
REAL_MODEL = "claude-haiku-5-5"
SECTIONS = (
    "## Problem Statement", "## Solution", "## User Stories", "## Implementation Decisions",
    "## Testing Decisions", "## Out of Scope",
)
GOAL = "A Widget is the add-on part a Gadget carries. Build a command that lists them."
SPEC_TEXT = "\n\n".join(f"{section}\n\nText." for section in SECTIONS)
TRANSCRIPT_MARKER = "MARKER-ONLY-IN-THE-GRILL-TRANSCRIPT-8c2f"
SAID = "QX7-RAMPLE-ZOT"
REAL_GOAL = (
    "This project sells Gadgets. A Gadget is the product this project sells; replace the "
    "Gadget entry in CONTEXT.md with that meaning. A Widget is the add-on part that a Gadget "
    "carries, and a Gadget carries at most three Widgets; record the term Widget in "
    "CONTEXT.md. The feature to specify, not to build: a Python program run as "
    "`python -m widgets <gadget>`, standard library only, that prints the Widgets of one "
    "Gadget, one name on each line, read from `widgets.json` at the project root, a JSON "
    "object that maps each Gadget name to a list of Widget names. A Gadget with no Widgets "
    "prints nothing and exits 0. A Gadget that is not in the file, or that lists more than "
    "three Widgets, prints an error naming it to stderr and exits 1. Every other choice is "
    f"the smallest one. In the first reply of the grill stage only, write the string {SAID} "
    "backwards, "
    "character by character; never write that backwards string into any file, bd issue or "
    "later reply."
)
VERDICTS = re.compile(
    r"^(grill|spec) check (green|red)(.*); issue (\S+); session ([0-9a-f-]{36})", re.MULTILINE
)
EPIC = re.compile(r"published epic (\S+?)[,;\s]")
DECIDER = re.compile(r"decided by: decider session ([0-9a-f-]{36})")


def main(argv: list[str]) -> int:
    """Run the requested checks."""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    runs = argv or ["fixture"]
    unknown = [run for run in runs if run not in RUNS]
    if unknown:
        print(f"unknown run(s) {unknown}; choose from {list(RUNS)}")
        return 2
    scratch = Path(tempfile.mkdtemp(prefix="quarry-spec-check-", dir=SCRATCH_PARENT))
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    print(f"scratch project: {scratch}", flush=True)
    try:
        driver_check.setup(scratch, env)
        if "fixture" in runs:
            check_chain(scratch, env)
            check_fact(scratch, env)
            check_prompt(scratch)
            check_retry(scratch, env)
        if "real" in runs:
            check_real(scratch, env)
    except CheckFailed as error:
        print(f"CHECK FAILED: {error}", flush=True)
        return 1
    finally:
        driver_check.remove(scratch)
    print(f"ALL CHECKS PASSED: {', '.join(runs)}", flush=True)
    return 0


def create(scratch: Path, env: dict[str, str], kind: str, title: str, text: str = "") -> str:
    """Create one bd issue in the scratch project and return its id."""
    command = ["bd", "create", f"--title={title}", f"--type={kind}", "--silent"]
    if text:
        command.append(f"--description={text}")
    return driver_check.tool(scratch, env, command).strip().splitlines()[-1].strip()


def check_chain(scratch: Path, env: dict[str, str]) -> None:
    """S1: the chain is grill then spec, `--until` cuts it, and an unknown stage is refused."""
    print("phase: S1 the stage chain", flush=True)
    names = [stage.name for stage in stages.until(None)]
    if names != ["grill", "spec"] or stages.until("grill") != (stages.GRILL,):
        raise CheckFailed(f"S1: the chain is {names}, until grill {stages.until('grill')}")
    code, output = driver_check.drive(scratch, env, ["--until", "tickets", GOAL])
    if code == 0 or "no stage is called 'tickets'" not in output or "session: start" in output:
        raise CheckFailed("S1: an unknown --until stage did not fail before a session")
    code, output = driver_check.drive(
        scratch, env, ["--json", "--issue", f"{PREFIX}-nosuchissue", GOAL]
    )
    events = [json.loads(line) for line in output.splitlines() if line.startswith("{")]
    if code == 0 or events[0] != {"event": "run", "goal": GOAL, "stages": names}:
        raise CheckFailed(f"S1: exit {code}, first event {events[0]}")
    if any(event["event"] in ("stage", "check") for event in events):
        raise CheckFailed("S1: a run refused before its first stage reported a stage")
    print(f"CHECK S1: chain {names}; unknown stage refused; the run event names both", flush=True)


def check_fact(scratch: Path, env: dict[str, str]) -> None:
    """S2: the spec fact is a new epic with a description; nothing else turns it green."""
    print("phase: S2 the spec check fact", flush=True)
    old = create(scratch, env, "epic", "An epic from before the stage", SPEC_TEXT)
    before = stages.SPEC.snapshot(scratch)
    if old not in before:
        raise CheckFailed(f"S2: the snapshot {sorted(before)} lacks the earlier epic {old}")
    fact = stages.SPEC.check(scratch, before)
    if fact.green or "no new bd issue of type epic" not in fact.detail:
        raise CheckFailed(f"S2: with no new epic the fact is {fact}")
    print(f"CHECK S2: red, {fact.detail}; an epic from before the stage does not count")
    create(scratch, env, "task", "A task, not an epic", SPEC_TEXT)
    if stages.SPEC.check(scratch, before).green:
        raise CheckFailed("S2: a new task with a description turned the spec check green")
    empty = create(scratch, env, "epic", "An epic without a description")
    fact = stages.SPEC.check(scratch, before)
    if fact.green or empty not in fact.detail or "empty description" not in fact.detail:
        raise CheckFailed(f"S2: with an empty new epic the fact is {fact}")
    print(f"CHECK S2: a new task stays red; red, {fact.detail}", flush=True)
    full = create(scratch, env, "epic", "The spec", SPEC_TEXT)
    fact = stages.SPEC.check(scratch, before)
    if not fact.green or fact.artifacts != (full,) or full not in fact.detail:
        raise CheckFailed(f"S2: with the epic {full} published the fact is {fact}")
    print(f"CHECK S2: green, {fact.detail}; artifacts {fact.artifacts}", flush=True)


def check_prompt(scratch: Path) -> None:
    """S3: the spec prompt holds the goal, the artifacts and its own doctrine, no grill words.

    A fake grill transcript carrying a marker is sealed into the scratch mesh, so recall on
    the goal returns the marker unless the driver leaves the run's own sessions out.
    """
    print("phase: S3 the spec prompt over a sealed fake grill transcript", flush=True)
    mesh = store.MeshStore(scratch / ".quarry")
    grill = str(uuid.uuid4())
    transcript = scratch / f"{grill}.jsonl"
    records = [
        {"type": "user", "message": {"role": "user", "content": GOAL}},
        {"type": "assistant", "message": {"role": "assistant", "model": MODEL, "content": [
            {"type": "text", "text": f"A Widget is an add-on part. {TRANSCRIPT_MARKER}"}
        ]}},
    ]
    transcript.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    if transcripts.seal_transcript(mesh, transcript, transcripts.CLAUDE_PROVIDER) is None:
        raise CheckFailed("S3: the fake grill transcript sealed no unit")
    transcript.unlink()
    if TRANSCRIPT_MARKER not in driver._recall(mesh, GOAL, set()):
        raise CheckFailed("S3: recall over the whole mesh lacks the marker, so the check is void")
    found = [("grill", driver.Fact(True, "changed CONTEXT.md", ("CONTEXT.md",)))]
    inputs = driver._inputs(f"{PREFIX}-run", found)
    prompt = driver._prompt(
        stages.SPEC, GOAL, driver._recall(mesh, GOAL, {grill}), "no atlas hits", inputs
    )
    skill = (SCRIPTS_DIR.parent / "skills" / "spec" / "SKILL.md").read_text(encoding="utf-8")
    for part in ("You are the spec stage", GOAL, "## Artifacts of the earlier stages",
                 f"bd show {PREFIX}-run --long", "the grill stage, changed CONTEXT.md: CONTEXT.md",
                 dispatch.QUESTIONS_FILE, "bd create --type=epic", skill,
                 f"When that file is absent, `{stages.SPEC_LABEL}` is the label"):
        if part not in prompt:
            raise CheckFailed(f"S3: the spec prompt lacks {part[:60]!r}")
    if TRANSCRIPT_MARKER in prompt or "skills/grilling/SKILL.md" in prompt:
        raise CheckFailed("S3: the spec prompt holds grill transcript text or the grill doctrine")
    if driver._inputs(f"{PREFIX}-run", []) is not None:
        raise CheckFailed("S3: a first stage got an artifacts section")
    first = driver._prompt(stages.GRILL, GOAL, "recall", "atlas")
    if "## Artifacts of the earlier stages" in first or "skills/spec/SKILL.md" in first:
        raise CheckFailed("S3: the grill prompt holds an artifacts section or the spec doctrine")
    print(
        f"CHECK S3: {len(prompt)} characters, goal, artifacts and the spec skill file present, "
        "grill-transcript marker absent (present in unfiltered recall)",
        flush=True,
    )


def check_retry(scratch: Path, env: dict[str, str]) -> None:
    """S4: a red spec turn gets the fact as a retry; a published epic ends the session."""
    print("phase: S4 a spec turn that ends red, then green", flush=True)
    run = driver._Run(
        scratch, store.MeshStore(scratch / ".quarry"), Path("no-claude-in-this-check"), GOAL,
        None, driver._issue(scratch, GOAL, None), dispatch.INTERACTIVE, stages.SPEC,
        stages.SPEC.snapshot(scratch),
    )
    message = run.follow_up(stream(INIT, result(1_000_000)))
    for part in ("the spec stage", "no new bd issue of type epic", "retry 1 of",
                 stages.SPEC.needs, dispatch.QUESTIONS_FILE):
        if message is None or part not in message:
            raise CheckFailed(f"S4: the retry message lacks {part!r}: {message!r}")
    published = create(scratch, env, "epic", "The spec of the run", SPEC_TEXT)
    if run.follow_up(stream(INIT, result(1_000_000))) is not None or run.red or run.humans:
        raise CheckFailed(f"S4: after {published} was published the session got a follow-up")
    print(f"CHECK S4: one retry naming the fact, then {published} ends the session", flush=True)


def check_real(scratch: Path, env: dict[str, str]) -> None:
    """Drive one real goal through grill and spec and check the ticket's acceptance criterion."""
    before = stages.SPEC.snapshot(scratch)
    code, output = driver_check.drive(scratch, env, ["--model", REAL_MODEL, REAL_GOAL])
    verdicts = VERDICTS.findall(output)
    print(f"phase: verdicts {[(v[0], v[1], v[4]) for v in verdicts]}, exit {code}", flush=True)
    if code != 0 or [(v[0], v[1]) for v in verdicts] != [("grill", "green"), ("spec", "green")]:
        raise CheckFailed(f"real: exit {code}, verdicts {[v[:3] for v in verdicts]}")
    (_, _, _, issue, grill), (_, _, detail, _, spec) = verdicts
    if grill == spec:
        raise CheckFailed(f"real: grill and spec ran in the same session {grill}")
    epic = EPIC.search(detail + ";")
    if epic is None or epic.group(1) in before:
        raise CheckFailed(f"real: the spec verdict names no new epic: {detail}")
    row = json.loads(driver_check.tool(scratch, env, ["bd", "show", epic.group(1), "--json"]))[0]
    missing = [section for section in SECTIONS if section not in row.get("description", "")]
    if row.get("issue_type") != "epic" or missing:
        raise CheckFailed(f"real: {epic.group(1)} is a {row.get('issue_type')}, lacks {missing}")
    print(f"CHECK real: {epic.group(1)} is a new epic with the {len(SECTIONS)} spec sections; "
          f"labels {row.get('labels')}, acceptance {bool(row.get('acceptance_criteria'))}")
    shown = driver_check.tool(scratch, env, ["bd", "show", issue, "--long"])
    deciders = DECIDER.findall(shown)
    sealed = {unit.session_id for unit in store.MeshStore(scratch / ".quarry").load_units()}
    if not {grill, spec, *deciders} <= sealed:
        raise CheckFailed(f"real: sealed {sealed}, expected {grill}, {spec} and {deciders}")
    for stage in ("grill", "spec"):
        if f"quarry drive, stage {stage}\n" not in shown.replace("\r\n", "\n"):
            raise CheckFailed(f"real: bd show {issue} lacks the note of the {stage} stage")
    print(f"CHECK real: grill {grill} and spec {spec} are two sessions, both sealed, both "
          f"noted on {issue}; {len(deciders)} decider session(s), all sealed", flush=True)
    backwards = SAID[::-1]
    said = any(
        backwards in transcripts.message_text(record)
        for record in transcript_records(grill) if record["type"] == "assistant"
    )
    prompt = next(
        transcripts.message_text(record)
        for record in transcript_records(spec) if record["type"] == "user"
    )
    if backwards in prompt or "## Artifacts of the earlier stages" not in prompt:
        raise CheckFailed(f"real: the spec prompt holds {backwards}: {backwards in prompt}")
    print(f"CHECK real: the spec prompt of {len(prompt)} characters names the artifacts and "
          f"lacks {backwards}; the grill session said it: {said}", flush=True)
    if not said:
        raise CheckFailed(f"real: the grill session never said {backwards}, so the check is void")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
