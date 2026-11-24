"""Check decision dispatch of `quarry drive`: constructed inputs, then real runs.

Usage: `dispatch_check.py [fixture] [probe] [real]`, `fixture` by default. `fixture` runs no
model turn: it feeds replies, questions files and constructed result frames to the driver's own
functions in a scratch project with a real bd tracker. `probe` runs one real decider session
that must read a project file. `real` drives three real runs, each
with real Claude Code sessions: one whose question point a decider decides, one whose goal
cannot settle its question, and one forced red three times. Prints every phase and exits 1
at the first failed expectation.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import os
import re
import sys
import tempfile
from pathlib import Path

import driver_check
from driver_check import SCRATCH_PARENT, SCRIPTS_DIR, VERDICT, CheckFailed
from marks_check import INIT, result, stream

sys.path.insert(0, str(SCRIPTS_DIR))
dispatch = importlib.import_module("quarry_lib.dispatch")
driver = importlib.import_module("quarry_lib.driver")
observe = importlib.import_module("quarry_lib.observe")
sessions = importlib.import_module("quarry_lib.sessions")
stages = importlib.import_module("quarry_lib.stages")
store = importlib.import_module("quarry_lib.store")
transcripts = importlib.import_module("quarry_lib.transcripts")

RUNS = ("fixture", "probe", "real")
REAL_MODEL = "claude-haiku-5-5"
PROBE_FILE = "warehouse.txt"
PROBE_NAME = "ZETA-417"
PROBE_GOAL = (
    "Record in CONTEXT.md which warehouse ships the Widget. The file warehouse.txt in the "
    "project root names that warehouse."
)
PROBE_QUESTION = (
    "Which warehouse ships the Widget? The answer is the warehouse name, exactly as the file "
    "warehouse.txt in the project root gives it.",
    "The warehouse that warehouse.txt names.",
)
GOAL = "A Widget is the add-on part a Gadget carries. Record the term Widget in CONTEXT.md."
QUESTION = dispatch.Question(
    "Does the glossary entry for Widget list 'add-on' under Avoid?",
    "No: the goal itself calls a Widget an add-on part.",
    ("CONTEXT.md",),
)
ROWS = [
    {"question": QUESTION.question, "recommended": QUESTION.recommended,
     "pointers": ["CONTEXT.md"]},
    {"question": "Is Widget singular in the heading?", "recommended": "Yes."},
]
BAD_FILES = ("not json", "{}", "[]", '[{"question": "q"}]', '[{"question": "q", '
             '"recommended": "r", "pointers": "x"}]', '["q"]')
REAL_GOALS = {
    "decided": (
        "This project sells Gadgets. A Widget is the add-on part that a Gadget carries. Record "
        "the term Widget in CONTEXT.md. One question point is open and must go to decision "
        "dispatch: whether the entry lists the word 'add-on' under Avoid."
    ),
    "human": (
        "Record in CONTEXT.md which of our two warehouses ships the Widget. Nothing in this "
        "text or in the project names the warehouses: that is the one question point, and it "
        "must go to decision dispatch."
    ),
    "red": (
        "Reply with the two characters OK. Change no file and write no questions file, "
        "whatever a later message asks."
    ),
}
DECIDER = re.compile(r"decided by: decider session ([0-9a-f-]{36})")
FILED = re.compile(r"halted for the user as (\S+?)[, ]")


def main(argv: list[str]) -> int:
    """Run the requested checks."""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    runs = argv or ["fixture"]
    unknown = [run for run in runs if run not in RUNS]
    if unknown:
        print(f"unknown run(s) {unknown}; choose from {list(RUNS)}")
        return 2
    scratch = Path(tempfile.mkdtemp(prefix="quarry-dispatch-check-", dir=SCRATCH_PARENT))
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    print(f"scratch project: {scratch}", flush=True)
    try:
        driver_check.setup(scratch, env)
        if "fixture" in runs:
            check_reply()
            check_decider()
            check_questions(scratch)
            check_mode(scratch)
            check_round(scratch, env)
            check_retries(scratch, env)
            check_repeat(scratch, env)
            check_observation(scratch)
        if "probe" in runs:
            check_probe(scratch)
        if "real" in runs:
            check_real_decided(scratch, env)
            check_real_halt(scratch, env, "human", retries=0)
            check_real_halt(scratch, env, "red", retries=driver.RETRIES)
    except CheckFailed as error:
        print(f"CHECK FAILED: {error}", flush=True)
        return 1
    finally:
        driver_check.remove(scratch)
    print(f"ALL CHECKS PASSED: {', '.join(runs)}", flush=True)
    return 0


def check_reply() -> None:
    """D1: a reply on the format gives its verdict; a reply off it is a NEEDS HUMAN."""
    print("phase: D1 decider replies", flush=True)
    cases = (
        ("DECISION: No.\nRATIONALE: The goal calls it an add-on.", dispatch.DECISION, "No."),
        ("```\nDECISION: Keep\nit.\nRATIONALE: Settled.\n```", dispatch.DECISION, "Keep it."),
        ("NEEDS HUMAN: Which warehouse?\nRATIONALE: Not named.", dispatch.NEEDS_HUMAN,
         "Which warehouse?"),
        ("I think the answer is no.", dispatch.NEEDS_HUMAN, QUESTION.question),
        ("DECISION: X\nRATIONALE: a\n\nNEEDS HUMAN: Which?\nRATIONALE: b", dispatch.NEEDS_HUMAN,
         QUESTION.question),
        ("Here it is.\nDECISION: X\nRATIONALE: a", dispatch.NEEDS_HUMAN, QUESTION.question),
        ("", dispatch.NEEDS_HUMAN, QUESTION.question),
    )
    for reply, kind, text in cases:
        verdict = dispatch.parse_reply(QUESTION, reply, "check")
        if (verdict.kind, verdict.text) != (kind, text) or not verdict.rationale:
            raise CheckFailed(f"D1: reply {reply!r} gave {verdict}")
        print(f"CHECK D1: {reply[:30]!r} -> {verdict.kind}: {verdict.rationale[:60]}", flush=True)


def check_decider() -> None:
    """D2: the decider is spawned read-only, prompted with the four inputs, and checked."""
    print("phase: D2 decider spawn options, prompt and record", flush=True)
    given = dispatch.DECIDER_OPTIONS
    allowed = set(given[given.index("--tools") + 1].split(","))
    denied = set(given[given.index("--disallowedTools") + 1].split(","))
    writers = {"Write", "Edit", "Bash"}
    if allowed & (writers | denied) or not writers <= denied:
        raise CheckFailed(f"D2: tools {allowed}, disallowed {denied}")
    if "bypassPermissions" in given or "--strict-mcp-config" not in given:
        raise CheckFailed(f"D2: the decider options are {given}")
    if json.loads(given[given.index("--settings") + 1]) != {"disableAllHooks": True}:
        raise CheckFailed(f"D2: the decider settings do not switch every hook off: {given}")
    print(f"CHECK D2: tools {sorted(allowed)}, disallowed {sorted(denied)}, hooks off", flush=True)
    prompt = dispatch.decider_prompt(GOAL, QUESTION)
    for part in (GOAL, QUESTION.question, QUESTION.recommended, "- CONTEXT.md", "DECISION:",
                 "NEEDS HUMAN:", "RATIONALE:"):
        if part not in prompt:
            raise CheckFailed(f"D2: the decider prompt lacks {part!r}")
    if prompt.lstrip().startswith("---") or "name: quarry-answer-agent" in prompt:
        raise CheckFailed("D2: the decider prompt carries the agent file's frontmatter")
    print(f"CHECK D2: prompt of {len(prompt)} characters holds the four inputs and the format")
    wrote = stream(INIT, {
        "type": "assistant", "parent_tool_use_id": None,
        "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": "x"}}]},
    }, result(1_000_000))
    reason = dispatch._overstepped(wrote)
    if reason is None or "Bash" not in reason or dispatch._overstepped(stream(INIT)) is not None:
        raise CheckFailed(f"D2: a decider record with a Bash call gave {reason!r}")
    print(f"CHECK D2: {reason}", flush=True)
    for name, expected in (("mcp__docs__update", True), ("Read", False)):
        called = stream(INIT, {
            "type": "assistant", "parent_tool_use_id": None,
            "message": {"content": [{"type": "tool_use", "name": name, "input": {}}]},
        })
        if (dispatch._overstepped(called) is not None) != expected:
            raise CheckFailed(f"D2: a decider call of {name} is refused: {not expected}")
    print("CHECK D2: an MCP tool call fails the dispatch, a Read call does not", flush=True)


def check_questions(scratch: Path) -> None:
    """D3: the questions file is taken once, and a malformed one is refused with its cause."""
    print("phase: D3 questions file", flush=True)
    path = scratch / dispatch.QUESTIONS_FILE
    if dispatch.take_questions(scratch) != []:
        raise CheckFailed("D3: an absent questions file gave question points")
    path.write_text(json.dumps(ROWS), encoding="utf-8")
    taken = dispatch.take_questions(scratch)
    if taken[0] != QUESTION or len(taken) != 2 or taken[1].pointers != () or path.exists():
        raise CheckFailed(f"D3: took {taken}, file still present {path.exists()}")
    print("CHECK D3: two question points taken, file removed", flush=True)
    for text in BAD_FILES:
        path.write_text(text, encoding="utf-8")
        try:
            dispatch.take_questions(scratch)
        except dispatch.QuestionsError as error:
            print(f"CHECK D3: {text[:24]!r} refused: {error}", flush=True)
        else:
            raise CheckFailed(f"D3: the malformed file {text!r} was accepted")
        if path.exists():
            raise CheckFailed(f"D3: the malformed file {text!r} was left in place")


def check_mode(scratch: Path) -> None:
    """D4: the interaction mode is read from the project's quarry configuration."""
    print("phase: D4 interaction mode", flush=True)
    path = scratch / dispatch.MODE_FILE
    if dispatch.mode(scratch) != dispatch.YOLO:
        raise CheckFailed("D4: a project without the mode file is not yolo")
    path.parent.mkdir(parents=True, exist_ok=True)
    for text, expected in (("Interaction mode: interactive\n", dispatch.INTERACTIVE),
                           ("# x\n\nInteraction mode: YOLO\n", dispatch.YOLO)):
        path.write_text(text, encoding="utf-8")
        if dispatch.mode(scratch) != expected:
            raise CheckFailed(f"D4: {text!r} did not give {expected}")
    path.write_text("Interaction mode: auto\n", encoding="utf-8")
    try:
        dispatch.mode(scratch)
    except ValueError as error:
        print(f"CHECK D4: absent is yolo, both modes read, unknown refused: {error}", flush=True)
    else:
        raise CheckFailed("D4: an unknown mode was accepted")
    path.unlink()


def new_run(scratch: Path, goal: str) -> object:
    """Return a driver run in interactive mode on a new bd issue of the scratch project."""
    issue = driver._issue(scratch, goal, None)
    return driver._Run(
        scratch, store.MeshStore(scratch / ".quarry"), Path("no-claude-in-this-check"), goal,
        None, issue, dispatch.INTERACTIVE, stages.GRILL, stages.GRILL.snapshot(scratch),
    )


def ended() -> object:
    """Return a constructed stage session whose turn just ended cleanly."""
    return stream(INIT, result(1_000_000))


def human_issue(scratch: Path, env: dict[str, str], issue: str, run_issue: str, part: str) -> None:
    """Expect `issue` to be labelled for the human, to name the run issue and to hold `part`."""
    shown = driver_check.tool(scratch, env, ["bd", "show", issue, "--long"])
    if driver.HUMAN_LABEL not in shown or run_issue not in shown or part not in shown:
        raise CheckFailed(f"bd show {issue} lacks the label, {run_issue} or {part!r}:\n{shown}")


def check_round(scratch: Path, env: dict[str, str]) -> None:
    """D5: a round is dispatched, noted in bd and answered; a NEEDS HUMAN halts and is filed."""
    print("phase: D5 a round of question points, asked on stdin", flush=True)
    run = new_run(scratch, GOAL)
    path = scratch / dispatch.QUESTIONS_FILE
    path.write_text(json.dumps(ROWS), encoding="utf-8")
    real_stdin, sys.stdin = sys.stdin, io.StringIO("No, keep add-on usable.\n\n")
    try:
        message = run.follow_up(ended())
        shown = driver_check.tool(scratch, env, ["bd", "show", run.issue, "--long"])
        for part in ("DECISION: No, keep add-on usable.", "DECISION: Yes.", ROWS[1]["question"]):
            if message is None or part not in message or part not in shown:
                raise CheckFailed(f"D5: {part!r} missing from the answer or from bd:\n{message}")
        if shown.count("decision dispatch") != 2 or run.humans:
            raise CheckFailed(f"D5: {shown.count('decision dispatch')} decision notes")
        print(f"CHECK D5: two decisions answered and noted on {run.issue}", flush=True)
        run = new_run(scratch, GOAL)
        path.write_text(json.dumps(ROWS[:1]), encoding="utf-8")
        sys.stdin = io.StringIO("")
        if run.follow_up(ended()) is not None or len(run.humans) != 1:
            raise CheckFailed(f"D5: a closed stdin gave humans {run.humans}")
    finally:
        sys.stdin = real_stdin
    filed = driver._halt(run, "unused")
    if len(filed) != 1:
        raise CheckFailed(f"D5: one NEEDS HUMAN filed {filed}")
    human_issue(scratch, env, filed[0], run.issue, QUESTION.question)
    human_issue(scratch, env, filed[0], run.issue, GOAL)
    print(f"CHECK D5: NEEDS HUMAN ends the session and is filed as {filed[0]}", flush=True)


def check_retries(scratch: Path, env: dict[str, str]) -> None:
    """D6: a red check is retried twice with its detail, then halts and is filed."""
    print("phase: D6 a stage forced red three times", flush=True)
    run = new_run(scratch, GOAL)
    for number in range(1, driver.RETRIES + 1):
        message = run.follow_up(ended())
        expected = f"retry {number} of {driver.RETRIES}"
        if message is None or expected not in message or "changed neither" not in message:
            raise CheckFailed(f"D6: red turn {number} gave {message!r}")
    if run.follow_up(ended()) is not None or "changed neither" not in str(run.red):
        raise CheckFailed(f"D6: the third red turn left red {run.red!r}")
    filed = driver._halt(run, run.red)
    human_issue(scratch, env, filed[0], run.issue, f"after {driver.RETRIES} retries")
    print(f"CHECK D6: {driver.RETRIES} retries, then {filed[0]}: {run.red}", flush=True)
    (scratch / dispatch.QUESTIONS_FILE).write_text("not json", encoding="utf-8")
    fresh = new_run(scratch, GOAL)
    message = fresh.follow_up(ended())
    if message is None or "not valid JSON" not in message or fresh.retries != 1:
        raise CheckFailed(f"D6: a malformed questions file gave {message!r}")
    (scratch / stages.GLOSSARY).write_text("# changed\n\n### Widget\n\nAn add-on.\n", "utf-8")
    if fresh.follow_up(ended()) is not None or fresh.red or fresh.humans:
        raise CheckFailed("D6: a stage that changed CONTEXT.md was not left to end green")
    print("CHECK D6: a malformed file is a retry; a changed CONTEXT.md ends the session")
    failed = stream(INIT, result(1_000_000, is_error=True))
    if new_run(scratch, GOAL).follow_up(failed) is not None:
        raise CheckFailed("D6: a session that reported is_error got a follow-up")
    print("CHECK D6: a failed session gets no follow-up", flush=True)


def check_repeat(scratch: Path, env: dict[str, str]) -> None:
    """D7: a decided question is never dispatched again, and a stage's decisions are bounded.

    The second and third turns run with a closed stdin, where every dispatch would be a
    NEEDS HUMAN: no NEEDS HUMAN means no dispatch ran.
    """
    print("phase: D7 the questions file written again with the decisions in it", flush=True)
    run = new_run(scratch, GOAL)
    path = scratch / dispatch.QUESTIONS_FILE
    path.write_text(json.dumps(ROWS), encoding="utf-8")
    real_stdin, sys.stdin = sys.stdin, io.StringIO("No.\n\n")
    limit = driver.DECISIONS
    try:
        first = run.follow_up(ended())
        if first is None or f"Never record a decision in {dispatch.QUESTIONS_FILE}" not in first:
            raise CheckFailed(f"D7: the answer does not keep decisions out of the file: {first}")
        sys.stdin = io.StringIO("")
        again = [{**row, "question": f"  {row['question'].upper()} ", "decision": "x"}
                 for row in ROWS]
        path.write_text(json.dumps(again), encoding="utf-8")
        message = run.follow_up(ended())
        shown = driver_check.tool(scratch, env, ["bd", "show", run.issue, "--long"])
        if run.humans or shown.count("decision dispatch") != 2 or path.exists():
            raise CheckFailed(f"D7: a decided round was dispatched again: {run.humans}")
        if message is None or "retry 1 of" not in message or "changed neither" not in message:
            raise CheckFailed(f"D7: a round with no new question gave {message!r}")
        print("CHECK D7: the same round again starts no dispatch; the stage check answers the "
              "turn with retry 1", flush=True)
        sys.stdin = io.StringIO("Blue.\n")
        new = {"question": "Which colour is a Widget?", "recommended": "Grey."}
        path.write_text(json.dumps([*ROWS, new]), encoding="utf-8")
        mixed = run.follow_up(ended())
        for part in ("DECISION: No.", "DECISION: Yes.", "DECISION: Blue."):
            if mixed is None or part not in mixed:
                raise CheckFailed(f"D7: a round with one new question lacks {part!r}: {mixed}")
        print("CHECK D7: one new question is asked once; the decided ones come back as recorded")
        driver.DECISIONS = len(run.decided)
        path.write_text(json.dumps([{"question": "One more?", "recommended": "No."}]), "utf-8")
        if run.follow_up(ended()) is not None or f"at most {driver.DECISIONS}" not in str(run.red):
            raise CheckFailed(f"D7: a decision past the bound left red {run.red!r}")
        if run.humans or len(run.decided) != driver.DECISIONS:
            raise CheckFailed("D7: a decision past the bound was dispatched")
        print(f"CHECK D7: red, {run.red}", flush=True)
    finally:
        sys.stdin, driver.DECISIONS = real_stdin, limit


def staged(run: object, questions: list[dict] | None = None) -> tuple[object, str]:
    """Run `driver._stage` on constructed sessions that are not sealed; return fact and output.

    Each constructed session writes `questions`, when given, to the questions file, ends its
    turn cleanly and gets the driver's follow-up, as a real session would at each result
    frame, until the follow-up is None.
    """
    def constructed(*_args: object) -> object:
        if questions is not None:
            (run.project_root / dispatch.QUESTIONS_FILE).write_text(
                json.dumps(questions), encoding="utf-8"
            )
        session = ended()
        while run.follow_up(session) is not None:
            session = ended()
        return session

    real_run, real_seal, captured = sessions.run, driver._seal, io.StringIO()
    sessions.run, driver._seal = constructed, lambda _store, _session: None
    try:
        with contextlib.redirect_stdout(captured):
            fact = driver._stage(run, None, [], driver._unreported)
    finally:
        sessions.run, driver._seal = real_run, real_seal
    print(captured.getvalue(), end="", flush=True)
    return fact, captured.getvalue()


def check_observation(scratch: Path) -> None:
    """D8: a red stage end writes one observation; a NEEDS HUMAN halt writes none.

    The observation goes to a scratch workspace through `TASK_OBSERVER_WORKSPACE`.
    """
    print("phase: D8 the observation of a red stage end", flush=True)
    if not (Path.home() / observe.HELPER).is_file():
        print("CHECK D8: skipped, task-observer (an optional companion) is not installed")
        return
    log = scratch / "observer" / observe.LOG_DIR
    (log / "archive").mkdir(parents=True)
    saved = os.environ.get(observe.WORKSPACE_ENV)
    os.environ[observe.WORKSPACE_ENV] = log.parents[1].as_posix()
    real_stdin, sys.stdin = sys.stdin, io.StringIO("")
    try:
        fact, output = staged(new_run(scratch, GOAL))
        notes = list(log.glob("*.md"))
        if fact is not None or "[drive] observation: written " not in output or len(notes) != 1:
            raise CheckFailed(f"D8: a red end gave fact {fact}, {len(notes)} observations")
        print(f"CHECK D8: a red end writes {notes[0].name}", flush=True)
        human = new_run(scratch, GOAL)
        fact, output = staged(human, ROWS[:1])
        if fact is not None or not human.humans or "observation:" in output:
            raise CheckFailed(f"D8: a NEEDS HUMAN halt gave fact {fact}, humans {human.humans}")
        if len(list(log.glob("*.md"))) != 1:
            raise CheckFailed("D8: a NEEDS HUMAN halt wrote an observation")
        print("CHECK D8: a NEEDS HUMAN halt writes no observation", flush=True)
    finally:
        sys.stdin = real_stdin
        if saved is None:
            os.environ.pop(observe.WORKSPACE_ENV, None)
        else:
            os.environ[observe.WORKSPACE_ENV] = saved


def check_probe(scratch: Path) -> None:
    """Expect one real decider session to read a project file and reply on the format.

    The answer is a name that only the file holds, so a DECISION that carries it proves the
    Read ran; a hook that refused a call or added a turn would show in the transcript or
    put the reply off the format.
    """
    print("phase: probe, one real decider session that must read a file", flush=True)
    (scratch / PROBE_FILE).write_text(f"The Widget ships from warehouse {PROBE_NAME}.\n", "utf-8")
    question = dispatch.Question(*PROBE_QUESTION, (PROBE_FILE,))
    verdict, decider = dispatch.decide(
        sessions.claude_cli(), scratch, PROBE_GOAL, question, REAL_MODEL, dispatch.YOLO
    )
    called = [name for name, _ in decider.tool_calls]
    print(f"phase: probe verdict {verdict.kind}: {verdict.text} ({verdict.rationale}); "
          f"tools {called}", flush=True)
    refused = "hook error" in transcripts.find_claude_transcript(decider.session_id).read_text(
        encoding="utf-8"
    )
    if verdict.kind != dispatch.DECISION or PROBE_NAME not in verdict.text or refused:
        raise CheckFailed(f"probe: verdict {verdict}, a hook refused a call: {refused}")
    if "Read" not in called and "Grep" not in called:
        raise CheckFailed(f"probe: the decider named {PROBE_NAME} without a read: {called}")
    print(f"CHECK probe: DECISION names {PROBE_NAME} after {called}, no hook refused a call",
          flush=True)


def real_run(scratch: Path, env: dict[str, str], name: str) -> tuple[int, str, str, str]:
    """Drive one real goal; return exit code, output, verdict and the run issue."""
    code, output = driver_check.drive(
        scratch, env, ["--until", "grill", "--model", REAL_MODEL, REAL_GOALS[name]]
    )
    match = VERDICT.search(output)
    if match is None:
        raise CheckFailed(f"{name}: the driver printed no verdict line")
    return code, output, match.group(1), match.group(2)


def check_real_decided(scratch: Path, env: dict[str, str]) -> None:
    """Expect a real run whose question point a separate, read-only session decides."""
    code, _, verdict, issue = real_run(scratch, env, "decided")
    shown = driver_check.tool(scratch, env, ["bd", "show", issue, "--long"])
    deciders = DECIDER.findall(shown)
    if code != 0 or verdict != "green" or not deciders or "DECISION:" not in shown:
        raise CheckFailed(f"decided: exit {code}, verdict {verdict}, deciders {deciders}")
    sealed = {unit.session_id for unit in store.MeshStore(scratch / ".quarry").load_units()}
    for decider in deciders:
        path = transcripts.find_claude_transcript(decider)
        called = re.findall(r'"type":\s*"tool_use".*?"name":\s*"(\w+)"', path.read_text("utf-8"))
        forbidden = set(called) - set(dispatch.DECIDER_TOOLS.split(","))
        if forbidden or decider not in sealed:
            raise CheckFailed(f"decided: decider {decider} called {called}, sealed "
                              f"{decider in sealed}")
        print(f"CHECK decided: decider {decider} called {called or 'no tool'}, sealed", flush=True)
    print(f"CHECK decided: exit 0, green, {len(deciders)} decision(s) noted on {issue}", flush=True)


def check_real_halt(scratch: Path, env: dict[str, str], name: str, retries: int) -> None:
    """Expect a real run to halt: non-zero exit and a bd issue labelled for the human."""
    code, output, verdict, issue = real_run(scratch, env, name)
    filed = FILED.search(output)
    seen = output.count("; retry ")
    if code == 0 or verdict != "red" or filed is None or seen != retries:
        raise CheckFailed(f"{name}: exit {code}, verdict {verdict}, filed {filed}, retries {seen}")
    human_issue(scratch, env, filed.group(1), issue, dispatch.NEEDS_HUMAN)
    print(f"CHECK {name}: exit {code}, red after {seen} retries, {filed.group(1)} filed")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
