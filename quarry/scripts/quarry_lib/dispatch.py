"""Decision dispatch: decide one question point of a stage.

A stage session writes the question points of a round to `QUESTIONS_FILE` and ends its
turn. The driver takes the file and sends each question here. In yolo mode the decider is a
separate headless session that reads the project and can change nothing: its built-in tools
are limited to `DECIDER_TOOLS`, the write and shell tools are disallowed at spawn, no MCP
server is loaded, and a call of any other tool in its record fails the dispatch. It runs
with every hook off (`disableAllHooks`): a hook written for a working session asks for a
tool the decider does not have, so it refused the decider's reads, and a Stop hook added a
turn whose text replaced the verdict. In
interactive mode the same primitive asks the user on the driver's own stdin. Every outcome
is a `Verdict`; a dispatch that fails is a NEEDS HUMAN, never a guess.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quarry_lib import sessions

QUESTIONS_FILE = ".quarry/questions.json"
MODE_FILE = "docs/agents/quarry.md"
MODE_LINE = re.compile(r"^\s*Interaction mode:[ \t]*(\S+)[ \t]*$", re.IGNORECASE | re.MULTILINE)
YOLO = "yolo"
INTERACTIVE = "interactive"
DECISION = "DECISION"
NEEDS_HUMAN = "NEEDS HUMAN"
ANSWER_AGENT = Path(__file__).resolve().parents[2] / "agents" / "answer-agent.md"
DECIDER_TOOLS = "Read,Glob,Grep"
DISALLOWED_TOOLS = "Write,Edit,MultiEdit,NotebookEdit,Bash,PowerShell"
DECIDER_OPTIONS = [
    "--permission-mode", "dontAsk",
    "--tools", DECIDER_TOOLS,
    "--disallowedTools", DISALLOWED_TOOLS,
    "--strict-mcp-config",
    "--settings", json.dumps({"disableAllHooks": True}),
]
REPLY = re.compile(
    r"(?:```\w*\s*\n)?(DECISION|NEEDS HUMAN):[ \t]*((?:(?!\nRATIONALE:).)+?)\s*"
    r"\nRATIONALE:[ \t]*([^\n]+?)\s*(?:\n```)?",
    re.DOTALL,
)
REPLY_CHARS = 200
READ_ONLY = (
    "This session is the decider of a Quarry harness run. You can read the project and you "
    "can change nothing: you have no tool that writes or runs a command. Reply with the "
    "output format above and nothing else."
)
ANSWERS = (
    "Decision dispatch decided the question points you wrote to {file}. Record each decision, "
    "with its rationale, in the artifacts that this stage produces, then continue the stage. "
    "Never record a decision in {file}: the driver removed that file, and you write it again "
    "only to send question points that are new. A question that is decided stays decided."
)


class QuestionsError(ValueError):
    """The questions file a stage wrote does not hold a list of question points."""


@dataclass(frozen=True)
class Question:
    """One question point: the question, its recommended answer, and where to look."""

    question: str
    recommended: str
    pointers: tuple[str, ...] = ()


@dataclass(frozen=True)
class Verdict:
    """The outcome of one dispatch.

    `kind` is `DECISION` or `NEEDS_HUMAN`. `text` is the chosen answer, or the question
    restated when a human must answer. `source` names who decided, for the record in bd.
    """

    kind: str
    text: str
    rationale: str
    source: str


def mode(project_root: Path) -> str:
    """Return the project's interaction mode; yolo when `MODE_FILE` names none.

    Raises:
        ValueError: the mode line names a mode that is neither yolo nor interactive.
    """
    path = project_root / MODE_FILE
    found = MODE_LINE.search(path.read_text(encoding="utf-8")) if path.is_file() else None
    if found is None:
        return YOLO
    value = found.group(1).lower()
    if value not in (YOLO, INTERACTIVE):
        raise ValueError(f"{MODE_FILE} names the mode {value!r}, not yolo or interactive")
    return value


def take_questions(project_root: Path) -> list[Question]:
    """Return the question points in `QUESTIONS_FILE` and remove the file; [] when absent.

    Raises:
        QuestionsError: the file is not a JSON array of objects that each hold a non-empty
            `question` and `recommended` string and, optionally, a `pointers` list of strings.
    """
    path = project_root / QUESTIONS_FILE
    if not path.is_file():
        return []
    raw = path.read_text(encoding="utf-8", errors="replace")
    path.unlink()
    try:
        rows = json.loads(raw)
    except json.JSONDecodeError as error:
        raise QuestionsError(f"not valid JSON: {error}") from error
    if not isinstance(rows, list) or not rows:
        raise QuestionsError("not a JSON array holding at least one question point")
    return [_question(index, row) for index, row in enumerate(rows, 1)]


def _question(index: int, row: Any) -> Question:
    """Return the question point in one row of the questions file."""
    if not isinstance(row, dict):
        raise QuestionsError(f"entry {index} is not an object")
    texts = [row.get("question"), row.get("recommended")]
    if not all(isinstance(text, str) and text.strip() for text in texts):
        raise QuestionsError(f"entry {index} lacks a non-empty question or recommended string")
    pointers = row.get("pointers", [])
    if not isinstance(pointers, list) or not all(isinstance(item, str) for item in pointers):
        raise QuestionsError(f"entry {index} has pointers that are not a list of strings")
    return Question(texts[0].strip(), texts[1].strip(), tuple(pointers))


def decide(
    claude: Path,
    project_root: Path,
    goal: str,
    question: Question,
    model: str | None,
    interaction: str,
) -> tuple[Verdict, sessions.Session | None]:
    """Decide one question point; return the verdict and the decider session, if one ran.

    Args:
        goal: the user's original description, verbatim: the grounding of the decision.
        interaction: `YOLO` runs a read-only decider session; `INTERACTIVE` asks the user
            on this process's stdin and runs no session.
    """
    if interaction == INTERACTIVE:
        return ask_user(question), None
    sessions.phase(f"dispatch: {question.question[:sessions.SUMMARY_CHARS]}")
    decider = sessions.run(
        claude, project_root, decider_prompt(goal, question), model, DECIDER_OPTIONS, {}
    )
    source = f"decider session {decider.session_id}, tools: {_tools(decider)}"
    failed = sessions.failure(decider) or _overstepped(decider)
    if failed:
        return Verdict(
            NEEDS_HUMAN, question.question, f"decision dispatch failed: {failed}", source
        ), decider
    return parse_reply(question, str(decider.result.get("result") or ""), source), decider


def _tools(session: sessions.Session) -> str:
    """Return the names of the tools a session called, in order, or "none"."""
    return ", ".join(name for name, _ in session.tool_calls) or "none"


def _overstepped(decider: sessions.Session) -> str | None:
    """Return why a decider's record is not that of a read-only session, or None."""
    if decider.handed_off:
        return f"the decider crossed the hand-off mark {sessions.HANDOFF_MARK}"
    other = sorted({name for name, _ in decider.tool_calls} - set(DECIDER_TOOLS.split(",")))
    if other:
        return f"the decider called {', '.join(other)}, and a decider may call only {DECIDER_TOOLS}"
    return None


def decider_prompt(goal: str, question: Question) -> str:
    """Return the decider's prompt: the answer agent's doctrine and the four inputs.

    Raises:
        FileNotFoundError: the plugin's answer agent file is missing.
    """
    doctrine = ANSWER_AGENT.read_text(encoding="utf-8").split("---", 2)[-1].strip()
    pointers = "\n".join(f"- {pointer}" for pointer in question.pointers) or "None given."
    return "\n\n".join([
        doctrine,
        READ_ONLY,
        f"## The user's original description, verbatim\n\n{goal}",
        f"## Question\n\n{question.question}",
        f"## Recommended answer\n\n{question.recommended}",
        f"## Pointers\n\n{pointers}",
    ])


def parse_reply(question: Question, reply: str, source: str) -> Verdict:
    """Return the verdict in a decider's reply; a reply off the format is a NEEDS HUMAN."""
    found = REPLY.fullmatch(reply.strip())
    if found is None:
        said = " ".join(reply.split())[:REPLY_CHARS] or "an empty reply"
        return Verdict(
            NEEDS_HUMAN,
            question.question,
            f"the decider's reply did not follow the output format: {said}",
            source,
        )
    kind, text, rationale = found.groups()
    return Verdict(kind, " ".join(text.split()), " ".join(rationale.split()), source)


def ask_user(question: Question) -> Verdict:
    """Ask the user one question point on stdin; an empty line takes the recommended answer.

    A closed stdin is a NEEDS HUMAN: nobody is there to answer.
    """
    source = "the user, on the driver's stdin"
    print(f"\nQUESTION: {question.question}", flush=True)
    print(f"RECOMMENDED: {question.recommended}", flush=True)
    for pointer in question.pointers:
        print(f"POINTER: {pointer}", flush=True)
    print("Your answer (an empty line takes the recommended answer): ", end="", flush=True)
    line = sys.stdin.readline()
    if not line:
        return Verdict(
            NEEDS_HUMAN, question.question, "interactive mode, and the driver's stdin is closed",
            source,
        )
    answer = line.strip()
    if not answer:
        return Verdict(DECISION, question.recommended, "the user took the recommendation", source)
    return Verdict(DECISION, answer, "the user's own answer", source)


def answers(decided: list[tuple[Question, Verdict]]) -> str:
    """Return the user message that carries a round's decisions back to the stage session."""
    blocks = [ANSWERS.format(file=QUESTIONS_FILE)]
    for number, (question, verdict) in enumerate(decided, 1):
        blocks.append(
            f"{number}. QUESTION: {question.question}\n"
            f"DECISION: {verdict.text}\nRATIONALE: {verdict.rationale}"
        )
    return "\n\n".join(blocks)
