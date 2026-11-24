"""Record which workflow lane a project is pinned to, so the pin outlives the conversation."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

FLOW_FILE = Path(".quarry") / "flow.json"
LANES: dict[str, str] = {
    "flow-new-feature": "A",
    "flow-inbound-issue": "B",
    "flow-something-broke": "C",
    "flow-too-foggy": "D",
    "flow-phase-running": "E",
    "flow-cold-resume": "F",
}
OVERRIDE_PHRASE = "flow override"
ALIASES = {"grill": "grilling"}


def allowed_skills(lane: str, plugin_root: Path) -> frozenset[str]:
    """Return the skills a lane permits, derived from the same table the paths page draws.

    Built from `guide.LANES` rather than listed by hand, so a lane cannot permit one set of
    skills while the board shows another. Every step and branch is reduced to a bare name
    and kept only when a skill of that name actually ships, which drops the steps that are
    not skills at all, such as `bd close` or `reproduce`.
    """
    from webapp import guide

    lanes = {entry["id"]: entry for entry in guide.LANES}
    if lane not in lanes:
        return frozenset()
    tokens = [cmd for cmd, _sub in lanes[lane]["main"]]
    tokens += [branch[1] for branch in lanes[lane]["branches"]]
    named = {ALIASES.get(token, token) for token in
             (raw.removeprefix("/quarry:").strip() for raw in tokens)}
    skills = plugin_root / "skills"
    return frozenset(name for name in named if (skills / name / "SKILL.md").is_file())


def pinned(project_root: Path) -> dict[str, Any] | None:
    """Return the lane this project is pinned to, or None when it is free to go anywhere.

    Never raises. This is read by the prompt-submit hook on every turn, so a truncated or
    hand-edited file has to mean no lane rather than a broken session. An unknown lane name
    also reads as no lane, since a pin nothing can explain cannot be enforced.
    """
    try:
        record = json.loads((project_root / FLOW_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict) or record.get("skill") not in LANES:
        return None
    return record


def pin(project_root: Path, skill: str) -> dict[str, Any]:
    """Pin this project to one lane, replacing any lane already pinned.

    Replacing rather than stacking is the whole point: two lanes at once would contradict
    each other, and the feature exists to narrow what an agent may do, not to branch it.

    The record deliberately does not say which session pinned the lane, nor how far along it
    the work has reached. Both fields existed and neither was ever read: the session id was
    always an empty string, and the step counter was written as 0 here and advanced by
    nothing. A pin is project state that outlives the session precisely so a later one
    inherits it, so whose turn set it decides nothing, and a position nothing maintains is a
    number that can only mislead.

    Raises:
        ValueError: `skill` is not one of `LANES`, refused here so an unknown lane can
            never reach the file that the hook and the audit both trust.
    """
    if skill not in LANES:
        raise ValueError(f"unknown lane {skill!r}; expected one of {', '.join(sorted(LANES))}")
    record = {
        "skill": skill,
        "lane": LANES[skill],
        "pinned_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    path = project_root / FLOW_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def release(project_root: Path) -> dict[str, Any] | None:
    """Unpin the project and return the lane that was released, or None if none was."""
    record = pinned(project_root)
    (project_root / FLOW_FILE).unlink(missing_ok=True)
    return record
