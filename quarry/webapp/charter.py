"""Read the project's charter: the objectives work serves and the non-goals bounding them."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

CHARTER_FILE = "CHARTER.md"
OBJECTIVES_SECTION = "objectives"
NON_GOALS_SECTION = "non-goals"
OBJECTIVE = re.compile(r"^###\s+(OBJ-\d+)\s*:\s*(.+?)\s*$")
HEADING = re.compile(r"^(#{1,3})\s+(.*?)\s*$")
BULLET = re.compile(r"^[-*]\s+(.*?)\s*$")
FIELD = re.compile(r"^(measure|why|status)\s*:\s*(.*?)\s*$", re.IGNORECASE)
STATES = ("met", "at-risk", "not-met", "unassessed")
UNASSESSED = "unassessed"


def charter(project_root: Path) -> dict[str, Any]:
    """Return the project's objectives and non-goals, `declared` false when it has none.

    An objective's label is its id lowercased, which is the bd label a ticket carries to say
    it serves that objective. Missing or unreadable is not an error: a project without a
    charter is a project that has not written one yet, and the board says so.

    Each objective also reports `state`, one of `STATES`, saying whether its measure
    currently holds. It is written by hand and defaults to `unassessed`, because a measure
    nobody has checked is exactly that, and counting closed tickets would report throughput
    while claiming attainment.
    """
    path = project_root / CHARTER_FILE
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return {"declared": False, "path": CHARTER_FILE, "objectives": [], "non_goals": []}
    objectives, non_goals = _parse(text.splitlines())
    return {
        "declared": bool(objectives or non_goals),
        "path": CHARTER_FILE,
        "objectives": objectives,
        "non_goals": non_goals,
    }


def _parse(lines: list[str]) -> tuple[list[dict[str, str]], list[str]]:
    objectives: list[dict[str, str]] = []
    non_goals: list[str] = []
    section = ""
    current: dict[str, str] | None = None

    for line in lines:
        heading = HEADING.match(line)
        objective = OBJECTIVE.match(line)
        if objective and section == OBJECTIVES_SECTION:
            current = {
                "id": objective.group(1),
                "label": objective.group(1).lower(),
                "title": objective.group(2),
                "why": "",
                "measure": "",
                "state": UNASSESSED,
                "assessment": "",
            }
            objectives.append(current)
            continue
        if heading:
            if len(heading.group(1)) <= 2:
                section = heading.group(2).strip().lower()
                current = None
            continue
        if section == NON_GOALS_SECTION:
            bullet = BULLET.match(line)
            if bullet:
                non_goals.append(bullet.group(1))
            continue
        if current is not None:
            _absorb(current, line)
    return objectives, non_goals


def _absorb(objective: dict[str, str], line: str) -> None:
    field = FIELD.match(line.strip())
    if field:
        name, value = field.group(1).lower(), field.group(2)
        if name == "status":
            objective["state"], objective["assessment"] = _status(value)
        else:
            objective[name] = value
        return
    body = line.strip()
    if body and not objective["why"]:
        objective["why"] = body


def _status(value: str) -> tuple[str, str]:
    """Split a Status line into one of `STATES` and the note explaining it.

    An unrecognised opening word is kept whole as the note and left unassessed, so a
    hand-written charter is never reported as met on the strength of a typo.
    """
    head, _, rest = value.strip().partition(" ")
    state = head.strip().lower().rstrip(",.")
    if state in STATES:
        return state, rest.strip().lstrip(",").strip()
    return UNASSESSED, value.strip()
