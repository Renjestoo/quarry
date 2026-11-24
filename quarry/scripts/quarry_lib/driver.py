"""Run the stages of one goal, each in fresh headless Claude Code sessions.

A stage is a `Stage` template; `stages` holds the templates and the run order. For each stage
the driver does recall and the atlas lookup itself, builds the prompt from the plugin's own
skill files, runs a `claude -p` session in the project, checks the stage on a fact, records
each session in bd and seals it. The next stage starts only on a green check, in a session of
its own, from the artifacts the earlier checks found: ids and paths, never a transcript.
Context use and the marks are in `sessions`; at the
hand-off mark the stage goes on in a fresh session that starts from the handoff document,
never from the transcript. Each session runs under the gate file of `gate.stage_scope`, so
the human gates are refused before they run, and the note lists every denied call.

At each result frame the driver answers the stage session. Question points the
session wrote to `dispatch.QUESTIONS_FILE` go to decision dispatch, one at a time, and the
decisions return as the next user message. A red check returns as its detail, at most
`RETRIES` times. A NEEDS HUMAN, and every red end of the stage, halts the run: the driver
files a bd issue labelled `HUMAN_LABEL` and exits non-zero.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from quarry_lib import dispatch, doctor, gate, observe, sessions
from quarry_lib.ask import KnowledgeController, render_result
from quarry_lib.sessions import Session, phase
from quarry_lib.store import MeshStore
from quarry_lib.transcripts import (
    CLAUDE_PROVIDER,
    TranscriptError,
    find_claude_transcript,
    seal_transcript,
)

STAGE_WRITES = True
STAGE_OPTIONS = ["--permission-mode", "bypassPermissions"]
BD_TIMEOUT_SECONDS = 300
ATLAS_TIMEOUT_SECONDS = 120
ATLAS_HITS = 8
ATLAS_QUERY_CHARS = 400
TITLE_CHARS = 60
USAGE_KEYS = (
    "input_tokens",
    "output_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)
MAX_SESSIONS = 3
RETRIES = 2
DECISIONS = 20
HUMAN_LABEL = "ready-for-human"
CONTINUATION = (
    "An earlier session of this stage reached the hand-off mark of the work budget, so the "
    "driver ended it and started this fresh session. Continue the goal from the handoff "
    "document below and the artifacts it names; work it records as done is done."
)
RETRY = (
    "The Quarry driver checked the {stage} stage and the check is red: {detail}. This is "
    "retry {number} of {retries}. Do what the check needs: {needs}, or write the open "
    f"question points to {dispatch.QUESTIONS_FILE} and end your turn."
)
OPENING = (
    "You are the {stage} stage of a Quarry harness run, started unattended by the driver. "
    "Nobody reads this session while it runs."
)
QUESTIONS = f"""\
Never decide a question point yourself: decision dispatch decides it, grounded in the words \
of the goal. To send a round of question points, write them to {dispatch.QUESTIONS_FILE} as \
a JSON array of objects, each with the strings "question" and "recommended" (your \
recommended answer) and an optional "pointers" array of strings (files, issues or terms that \
bear on the question), then end your turn. The driver replies in this session with a \
DECISION and a RATIONALE for each question. Take each decision as if the user gave it."""
CLOSING = """\
The goal text is the authority. Where it limits what you may change, keep to that limit even \
where the method says to record something.

The harness already ran recall and the atlas lookup for this goal; both results are below. \
The harness records this run in bd and seals this session itself."""
INPUTS = (
    "This stage starts cold. The earlier stages of this run left the durable artifacts below, "
    "and you get no transcript of them. Read each artifact before you write.\n\n"
    "- the bd issue of this run, {issue}: `bd show {issue} --long` gives the goal and one "
    "note for each decision that decision dispatch made"
)


class DriverError(RuntimeError):
    """A part the driver needs is missing or refused, so the stage cannot run or finish."""


@dataclass(frozen=True)
class Fact:
    """What one stage check found: green or red, the detail, and the artifacts it names.

    `artifacts` are the ids and paths a green check found (changed files, bd issue ids); the
    next stage gets them as its inputs. `epics` are the bd epics the stage created, green or
    red; the `check` event reports them, so a run's epic can be found without reading text.
    """

    green: bool
    detail: str
    artifacts: tuple[str, ...] = ()
    epics: tuple[str, ...] = ()


@dataclass(frozen=True)
class Stage:
    """One stage template: doctrine, brief and check fact.

    `skills` names the plugin skill files the prompt carries. `needs` ends the retry message:
    what a session does to turn a red check green. `snapshot` reads, before the stage's first
    session, the state that `check` compares the project with; `check` never reads what a
    session reported.
    """

    name: str
    skills: tuple[str, ...]
    brief: str
    needs: str
    snapshot: Callable[[Path], Any]
    check: Callable[[Path, Any], Fact]


@dataclass
class _Run:
    """One stage run: what the driver needs to answer the stage session at a result frame.

    `before` is the stage's snapshot. `done` holds the id of every session the whole run has
    sealed so far, stage and decider sessions alike; the stages of one run share the list.
    """

    project_root: Path
    store: MeshStore
    claude: Path
    goal: str
    model: str | None
    issue: str
    interaction: str
    stage: Stage
    before: Any
    done: list[str] = field(default_factory=list)
    decided: dict[str, dispatch.Verdict] = field(default_factory=dict)
    retries: int = 0
    red: str | None = None
    humans: list[tuple[dispatch.Question, dispatch.Verdict]] = field(default_factory=list)

    def follow_up(self, session: Session) -> str | None:
        """Return the next user message for a stage session whose turn ended, or None to end it.

        A round of question points is dispatched whole, so every NEEDS HUMAN of the round
        is known before the run halts. A question the stage already got decided is never
        dispatched again: it gets its recorded verdict back, and a file that holds no new
        question is no round, so the stage check decides the turn. A stage that asks for
        more than `DECISIONS` decisions is red. A session that failed, compacted or crossed the
        hand-off mark gets no answer. A bd or file failure while answering ends the session
        and makes the stage red, so the session is still sealed and the halt recorded.
        """
        if (
            session.result.get("is_error") is not False
            or session.handed_off
            or session.compactions
        ):
            return None
        try:
            questions = dispatch.take_questions(self.project_root)
            new = {_asked(question) for question in questions} - self.decided.keys()
            if len(self.decided) + len(new) > DECISIONS:
                self.red = (
                    f"the stage asked for {len(self.decided) + len(new)} decisions, and the "
                    f"driver dispatches at most {DECISIONS} for one stage"
                )
                return None
            if new:
                for question in questions:
                    if _asked(question) not in self.decided:
                        self.decided[_asked(question)] = self._decide(question)
                answered = [(question, self.decided[_asked(question)]) for question in questions]
                self.humans = [pair for pair in answered if pair[1].kind == dispatch.NEEDS_HUMAN]
                return None if self.humans else dispatch.answers(answered)
            if questions:
                phase(f"questions: all {len(questions)} are decided already, none dispatched")
            fact = self.stage.check(self.project_root, self.before)
        except dispatch.QuestionsError as error:
            return self._retry(f"the file {dispatch.QUESTIONS_FILE} is not usable: {error}")
        except (DriverError, OSError) as error:
            self.red = f"the driver could not answer the stage session: {error}"
            return None
        return None if fact.green else self._retry(fact.detail)

    def _decide(self, question: dispatch.Question) -> dispatch.Verdict:
        """Dispatch one question point, seal its decider session and note the verdict in bd."""
        verdict, decider = dispatch.decide(
            self.claude, self.project_root, self.goal, question, self.model, self.interaction
        )
        if decider is not None:
            self.done.append(decider.session_id)
            try:
                _seal(self.store, decider)
            except DriverError as error:
                verdict = dispatch.Verdict(
                    dispatch.NEEDS_HUMAN, question.question, str(error), verdict.source
                )
        phase(f"dispatch: {verdict.kind}: {verdict.text[:sessions.SUMMARY_CHARS]}")
        _append_note(
            self.project_root, self.issue, _decision_note(self.stage.name, question, verdict)
        )
        return verdict

    def _retry(self, detail: str) -> str | None:
        """Return the retry message carrying a red check's detail; None once retries are spent."""
        if self.retries >= RETRIES:
            self.red = f"{detail}, still after {RETRIES} retries"
            return None
        self.retries += 1
        phase(f"check: red, {detail}; retry {self.retries} of {RETRIES}")
        return RETRY.format(
            stage=self.stage.name, detail=detail, number=self.retries, retries=RETRIES,
            needs=self.stage.needs,
        )


def _asked(question: dispatch.Question) -> str:
    """Return the text that identifies a question point: its words, case and spacing aside."""
    return " ".join(question.question.split()).casefold()


def _unreported(_kind: str, **_fields: Any) -> None:
    """Drop a run event: the run has no machine reader."""


def drive(
    project_root: Path,
    store: MeshStore,
    goal: str,
    issue_id: str | None,
    model: str | None,
    stages: Sequence[Stage],
    report: Callable[..., None] = _unreported,
) -> int:
    """Run `stages` on `goal`, in order; return 0 when every check is green, 1 at a red halt.

    Args:
        issue_id: an existing bd issue to record the run on; None creates a task issue
            holding the goal text verbatim.
        model: a full model id passed to `claude --model`, for the stage and the decider
            sessions; None leaves the CLI default.
        stages: the stages to run; `quarry_lib.stages.until` gives the chain up to one stage.
        report: called as `report(kind, **fields)` with the `run`, `stage` and `check`
            events that `quarry_lib.events` documents.

    Before anything else runs, the `doctor` report is printed; a required part that is
    absent or degraded stops the run before any session starts. A stage starts only when the
    check of the stage before it is green, and no stage follows a red one.

    Raises:
        DriverError: the goal is empty, the model is an alias, the interaction mode is
            unknown, a required part is not ready, the mesh, the claude CLI, a skill file or
            the answer agent file is missing, a bd or graft call failed, or a stage session
            could not be sealed.
    """
    report("run", goal=goal, stages=[stage.name for stage in stages])
    if not goal.strip():
        raise DriverError("the goal text is empty")
    if model is not None and "claude-" not in model:
        raise DriverError(f"--model takes a full model id such as claude-opus-5-5, not {model!r}")
    if not store.root.is_dir():
        raise DriverError(f"no mesh at {store.root}; run `quarry init` in the project first")
    for needed in (sessions.HANDOFF_SKILL, dispatch.ANSWER_AGENT):
        if not needed.is_file():
            raise DriverError(f"the driver reads {needed}, which is missing")
    try:
        interaction = dispatch.mode(project_root)
    except ValueError as error:
        raise DriverError(str(error)) from error
    phase("parts: start")
    parts = doctor.probe()
    if doctor.print_report(parts) != 0:
        blocking = "; ".join(
            f"{part.name} is {part.state}, install: {part.install}"
            for part in parts
            if part.required and part.state != doctor.PRESENT
        )
        raise DriverError(f"a required part is not ready, so no session starts: {blocking}")
    phase("parts: every required part present")
    try:
        claude = sessions.claude_cli()
    except FileNotFoundError as error:
        raise DriverError(str(error)) from error
    phase(f"claude CLI: {claude}")
    phase(f"interaction mode: {interaction}")

    phase("issue: start")
    issue = _issue(project_root, goal, issue_id)
    phase(f"issue: {issue}")

    options = [*STAGE_OPTIONS, "--settings", json.dumps(gate.hook_settings())]
    done: list[str] = []
    found: list[tuple[str, Fact]] = []
    for stage in stages:
        phase(f"stage: {stage.name}")
        report("stage", stage=stage.name, state="running", issue=issue)
        run = _Run(
            project_root, store, claude, goal, model, issue, interaction, stage,
            stage.snapshot(project_root), done,
        )
        fact = _stage(run, _inputs(issue, found), options, report)
        if fact is None:
            return 1
        found.append((stage.name, fact))
    return 0


def _stage(
    run: _Run, inputs: str | None, options: list[str], report: Callable[..., None]
) -> Fact | None:
    """Run one stage to its check; return the green fact, or None once a red end is halted.

    Args:
        inputs: the prompt section that names the earlier stages' artifacts; None for the
            first stage of a run.

    A session that crosses the hand-off mark and ends cleanly with its handoff document
    written is sealed and noted, and a fresh session continues the stage, at most
    `MAX_SESSIONS` in all. The check compares the project with the stage's snapshot. A red
    end files one bd issue labelled `HUMAN_LABEL` for each NEEDS HUMAN, or one holding the
    check's detail; a red end with no NEEDS HUMAN also writes one task-observer observation,
    or skips it, and either way the verdict stays the same.
    """
    stage, project_root, first = run.stage, run.project_root, len(run.done)
    handoff: Path | None = None
    for number in range(1, MAX_SESSIONS + 1):
        phase("recall: start")
        recall = _recall(run.store, run.goal, set(run.done))
        phase("recall: done")
        phase("atlas: start")
        atlas = _atlas(project_root, run.goal)
        phase("atlas: done")
        prompt = _prompt(stage, run.goal, recall, atlas, inputs, handoff)
        phase(f"prompt: {len(prompt)} characters")
        phase(f"session {number} of {MAX_SESSIONS}")
        if (project_root / dispatch.QUESTIONS_FILE).is_file():
            (project_root / dispatch.QUESTIONS_FILE).unlink()
            phase(f"questions: removed an unanswered {dispatch.QUESTIONS_FILE} left before "
                  "this session; the session asks again what is still open")
        with gate.stage_scope(project_root, stage.name, STAGE_WRITES) as gate_env:
            session = sessions.run(
                run.claude, project_root, prompt, run.model, options, gate_env, run.follow_up
            )
        run.done.append(session.session_id)
        phase(f"session: done (exit {session.returncode})")
        phase("denied: " + ("; ".join(sessions.denials(session)) or "none"))
        _seal(run.store, session)
        failure = sessions.failure(session) or _handoff_failure(project_root, session, number)
        if failure is not None or run.humans or run.red or not session.handed_off:
            break
        handoff = project_root / sessions.handoff_document(session.session_id)
        phase(f"handoff document: {sessions.handoff_document(session.session_id)} present")
        _record(run, session, "handed off to a fresh session", None)

    fact = stage.check(project_root, run.before)
    needs = "; ".join(
        f"{dispatch.NEEDS_HUMAN}: {verdict.text} ({verdict.rationale})" for _, verdict in run.humans
    )
    detail = "; ".join(part for part in (failure, needs, run.red) if part) or (
        None if fact.green else fact.detail
    )
    if detail is None:
        verdict = f"green, {fact.detail}"
    else:
        filed = _halt(run, detail)
        if not run.humans:
            phase("observation: " + observe.record(
                stage.name, stage.skills, detail, run.done[first:], filed, project_root, run.issue
            ))
        verdict = f"red, {detail}; halted for the user as {', '.join(filed)} ({HUMAN_LABEL})"
    phase(f"check: {verdict}")
    _record(run, session, verdict, failure)
    report(
        "check", stage=stage.name, result="green" if detail is None else "red", detail=verdict,
        issue=run.issue, session=session.session_id, epics=list(fact.epics),
    )
    print(
        f"{stage.name} check {verdict}; issue {run.issue}; session {session.session_id}",
        flush=True,
    )
    return fact if detail is None else None


def _inputs(issue: str, found: list[tuple[str, Fact]]) -> str | None:
    """Return the prompt section naming what the earlier stages left; None for a first stage."""
    if not found:
        return None
    lines = [INPUTS.format(issue=issue)]
    for name, fact in found:
        lines.append(f"- the {name} stage, {fact.detail}: {', '.join(fact.artifacts)}")
    return "\n".join(lines)


def _halt(run: _Run, detail: str) -> list[str]:
    """File the bd issues that hand a halted run to the user; return their ids.

    One issue for each NEEDS HUMAN of the round, or one holding the red check's detail.
    """
    phase("halt: start")
    stage = run.stage.name
    grounding = f"## Goal, verbatim\n\n{run.goal}"
    halts = [
        (
            f"{dispatch.NEEDS_HUMAN}: {question.question}",
            "\n".join([
                f"quarry drive halted in the {stage} stage; the run is recorded on {run.issue}.",
                "",
                f"{dispatch.NEEDS_HUMAN}: {verdict.text}",
                f"RATIONALE: {verdict.rationale}",
                f"Recommended answer: {question.recommended}",
                "Pointers: " + (", ".join(question.pointers) or "none"),
                f"Decided by: {verdict.source}",
                "",
                grounding,
            ]),
        )
        for question, verdict in run.humans
    ] or [(
        f"{dispatch.NEEDS_HUMAN}: the {stage} check is red",
        f"quarry drive halted in the {stage} stage; the run is recorded on {run.issue}.\n\n"
        f"The check is red: {detail}\n\n{grounding}",
    )]
    filed = []
    for title, body in halts:
        out = tool(
            run.project_root,
            "bd",
            [
                "create",
                f"--title={' '.join(title.split())[:TITLE_CHARS + len(dispatch.NEEDS_HUMAN)]}",
                "--type=task",
                f"--labels={HUMAN_LABEL}",
                f"--deps=discovered-from:{run.issue}",
                "--stdin",
                "--silent",
            ],
            BD_TIMEOUT_SECONDS,
            stdin=body,
        ).strip()
        if not out:
            raise DriverError("bd create gave no issue id for the halt")
        filed.append(out.splitlines()[-1].strip())
    phase(f"halt: filed {', '.join(filed)}, labelled {HUMAN_LABEL}")
    return filed


def _decision_note(stage: str, question: dispatch.Question, verdict: dispatch.Verdict) -> str:
    """Return the bd note that records one dispatched question point and its verdict."""
    return "\n".join([
        f"quarry drive, stage {stage}, decision dispatch",
        f"question: {question.question}",
        f"recommended: {question.recommended}",
        f"{verdict.kind}: {verdict.text}",
        f"RATIONALE: {verdict.rationale}",
        f"decided by: {verdict.source}",
    ])


def _seal(store: MeshStore, session: Session) -> None:
    """Seal the session's transcript into the mesh."""
    phase("seal: start")
    try:
        unit = seal_transcript(
            store, find_claude_transcript(session.session_id), CLAUDE_PROVIDER
        )
    except (TranscriptError, OSError, ValueError) as error:
        raise DriverError(f"sealing session {session.session_id} failed: {error}") from error
    phase(
        f"seal: sealed {unit.unit_id} from {session.session_id}"
        if unit
        else f"seal: nothing new to seal for {session.session_id}"
    )


def _record(run: _Run, session: Session, verdict: str, failure: str | None) -> None:
    """Append the session's note to the bd issue of the run."""
    phase("note: start")
    note = _note(run.project_root, run.stage.name, session, verdict, failure)
    _append_note(run.project_root, run.issue, note)
    phase(f"note: written to {run.issue}")


def _append_note(project_root: Path, issue: str, note: str) -> None:
    """Append one note to the bd issue that records the run."""
    tool(project_root, "bd", ["update", issue, "--append-notes", note], BD_TIMEOUT_SECONDS)


def _recall(store: MeshStore, goal: str, done: set[str]) -> str:
    """Return recall on the goal, leaving out every unit sealed from the sessions in `done`.

    A fresh session after a hand off never starts from the earlier transcript, and recall
    would otherwise return that transcript's own sealed lines word for word.
    """
    own = frozenset(
        unit.unit_id for unit in store.load_units() if unit.session_id in done
    )
    return render_result(KnowledgeController(store).ask(goal, exclude=own))


def tool(
    project_root: Path,
    name: str,
    args: list[str],
    timeout: int,
    stdin: str | None = None,
) -> str:
    """Run one external part (bd or graft) in the project and return its stdout.

    Resolves the executable through `shutil.which` because graft ships as a shim on
    Windows, which bare `subprocess` will not find by name.
    """
    executable = shutil.which(name)
    if executable is None:
        raise DriverError(f"{name} is not on PATH; the driver cannot run the stage without it")
    try:
        done = subprocess.run(
            [executable, *args],
            cwd=str(project_root),
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise DriverError(
            f"{name} {args[0]} did not answer within {timeout}s; it may still have done the "
            "work, so check before repeating this"
        ) from error
    if done.returncode != 0:
        detail = (done.stderr or done.stdout or "").strip().splitlines()
        said = detail[0] if detail else "no output on either stream"
        raise DriverError(f"{name} {args[0]} failed (exit {done.returncode}): {said}")
    return done.stdout


def _atlas(project_root: Path, goal: str) -> str:
    """Return the atlas hits for the goal's own words, one `pointer  title` line each.

    The query is the goal reduced to its words on one line. graft is a `.cmd` shim on
    Windows, so its arguments pass through cmd.exe, which cuts an argument at a newline
    and interprets quotes, `&` and `%`.
    """
    query = " ".join(re.findall(r"\w+", goal))[:ATLAS_QUERY_CHARS]
    raw = tool(
        project_root,
        "graft",
        ["ask", "--json", "-n", str(ATLAS_HITS), query, str(project_root)],
        ATLAS_TIMEOUT_SECONDS,
    ).strip()
    start = raw.find("{")
    try:
        payload = json.loads(raw[start:]) if start != -1 else None
    except json.JSONDecodeError as error:
        raise DriverError(f"graft ask returned invalid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise DriverError(f"graft ask returned no JSON: {raw[:200]}")
    hits = payload.get("hits") or []
    if not hits:
        return "The atlas holds no node matching this goal."
    return "\n".join(f"- {hit.get('pointer')}  {hit.get('title')}" for hit in hits)


def _issue(project_root: Path, goal: str, issue_id: str | None) -> str:
    """Return the bd issue recording this run, creating one that holds the goal verbatim."""
    if issue_id:
        tool(project_root, "bd", ["show", issue_id, "--json"], BD_TIMEOUT_SECONDS)
        return issue_id
    title = f"Drive: {' '.join(goal.split())[:TITLE_CHARS]}"
    out = tool(
        project_root,
        "bd",
        ["create", f"--title={title}", "--type=task", "--stdin", "--silent"],
        BD_TIMEOUT_SECONDS,
        stdin=goal,
    ).strip()
    if not out:
        raise DriverError("bd create gave no issue id")
    return out.splitlines()[-1].strip()


def _prompt(
    stage: Stage,
    goal: str,
    recall: str,
    atlas: str,
    inputs: str | None = None,
    handoff: Path | None = None,
) -> str:
    """Return the stage prompt: brief, goal verbatim, inputs, handoff, recall, atlas, skills.

    Args:
        inputs: the section naming the earlier stages' artifacts; None for a first stage.
        handoff: the handoff document of the session this one continues; None for the
            first session of a stage.
    """
    brief = "\n\n".join([OPENING.format(stage=stage.name), stage.brief, QUESTIONS, CLOSING])
    sections = [brief, f"## Goal, verbatim\n\n{goal}"]
    if inputs is not None:
        sections.append(f"## Artifacts of the earlier stages\n\n{inputs}")
    if handoff is not None:
        document = handoff.read_text(encoding="utf-8", errors="replace")
        sections.append(
            f"## Hand off\n\n{CONTINUATION}\n\nThe handoff document, "
            f"{sessions.HANDOFF_DIR}/{handoff.name}:\n\n{document}"
        )
    sections += [
        f"## Recall (Ask_Knowledge, run by the harness)\n\n{recall}",
        f"## Atlas (graft ask, run by the harness)\n\n{atlas}",
    ]
    for name in stage.skills:
        path = sessions.SKILLS_DIR / name / "SKILL.md"
        if not path.is_file():
            raise DriverError(f"the {stage.name} stage reads {path}, which is missing")
        sections.append(
            f"## Skill file: skills/{name}/SKILL.md\n\n{path.read_text(encoding='utf-8')}"
        )
    return "\n\n".join(sections)


def _handoff_failure(project_root: Path, session: Session, number: int) -> str | None:
    """Return why a session that crossed the hand-off mark fails the stage, or None.

    Args:
        number: the session's place in the stage, 1-based; the last session a stage may
            run cannot hand off, so its crossing means the work exceeds the budget.
    """
    if not session.handed_off:
        return None
    if number >= MAX_SESSIONS:
        return (
            f"session {number} of {MAX_SESSIONS} also crossed the hand-off mark "
            f"{sessions.HANDOFF_MARK}: the work does not fit the work budget and must be split"
        )
    document = project_root / sessions.handoff_document(session.session_id)
    if not document.is_file() or not document.read_text(encoding="utf-8", errors="replace").strip():
        return (
            f"the session crossed the hand-off mark {sessions.HANDOFF_MARK} and ended without "
            f"a handoff document at {document}"
        )
    return None


def _note(
    project_root: Path, stage: str, session: Session, verdict: str, failure: str | None
) -> str:
    """Return the bd note for this session, built from its tool-call record."""
    counts = Counter(name for name, _ in session.tool_calls)
    written = sorted({
        _relative(project_root, str(tool_input.get("file_path") or tool_input.get("notebook_path")))
        for name, tool_input in session.tool_calls
        if name in gate.WRITE_TOOLS
        and (tool_input.get("file_path") or tool_input.get("notebook_path"))
    })
    usage = (session.result or {}).get("usage") or {}
    document = sessions.handoff_document(session.session_id)
    return "\n".join([
        f"quarry drive, stage {stage}",
        f"session: {session.session_id}",
        f"check: {verdict}",
        *([f"handoff document: {document}"] if (project_root / document).is_file() else []),
        "tools: " + (", ".join(f"{name} x{count}" for name, count in counts.most_common())
                     or "none"),
        "files written: " + (", ".join(written) or "none"),
        *([f"denied: {call}" for call in sessions.denials(session)] or ["denied: none"]),
        "usage: " + (
            "not counted, the session failed"
            if failure
            else ", ".join(f"{key} {usage.get(key, 0)}" for key in USAGE_KEYS)
        ),
    ])


def _relative(project_root: Path, path: str) -> str:
    """Return `path` relative to the project when it lies inside it, else as given."""
    resolved = Path(path).resolve()
    return (
        resolved.relative_to(project_root.resolve()).as_posix()
        if resolved.is_relative_to(project_root.resolve())
        else path
    )
