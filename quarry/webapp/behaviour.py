"""Hold measured facts about how things behave, each with its evidence and its date.

The four homes hold decisions, work, history and code. None of them holds a measured fact
about how a tool behaves, which is neither a decision nor history: it was true when it was
taken and may not be true now. Every record therefore carries the evidence that established
it and the date it was measured, and falls due for re-checking on a schedule instead of
being trusted forever.

This is deliberately not a fifth place to look for a decision. A record that cannot name
what was observed is refused, and a decision has a rationale rather than an observation.
"""

from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path
from typing import Any

BEHAVIOUR_FILE = Path(".quarry") / "behaviour.json"
STALE_AFTER_DAYS = 30


def facts(project_root: Path) -> list[dict[str, Any]]:
    """Return the recorded facts in the file's own claim order; never raises.

    Read by the session-start hook, so a truncated or hand-edited file has to mean no facts
    rather than a session that cannot begin. A record missing a claim, its evidence, or its
    date is dropped rather than shown, because a fact that cannot be dated cannot be
    re-checked, which is the one property this ledger exists to provide.
    """
    try:
        loaded = json.loads((project_root / BEHAVIOUR_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(loaded, list):
        return []
    return [row for row in loaded if _usable(row)]


def record(project_root: Path, claim: str, evidence: str) -> dict[str, Any]:
    """Record a measured fact, replacing any earlier record making the same claim.

    Replacing rather than appending is what makes re-verification cheap: measuring the same
    thing again refreshes its date in place, so a fact that keeps being true stops being
    reported as due.

    Args:
        claim: what is true, stated so a reader can act on it.
        evidence: what was observed to establish it, specific enough to repeat.

    Raises:
        ValueError: either argument is blank. A claim with no evidence is exactly what this
            ledger exists to keep out, and refusing it here is the only structural barrier
            between a measurement and an assumption.
    """
    if not claim.strip():
        raise ValueError("a fact needs a claim")
    if not evidence.strip():
        raise ValueError(
            f"the claim {claim.strip()!r} needs evidence; without it this is an assumption"
        )
    entry = {
        "claim": claim.strip(),
        "evidence": evidence.strip(),
        "measured": time.strftime("%Y-%m-%d", time.gmtime()),
    }
    kept = [row for row in facts(project_root) if row["claim"] != entry["claim"]]
    _write(project_root, [*kept, entry])
    return entry


def drop(project_root: Path, claim: str) -> dict[str, Any] | None:
    """Remove the fact making this claim, returning it, or None when none matched.

    Re-checking has two outcomes and a ledger that can only express one of them lies: a
    claim a later measurement disproves has to be removable, not merely re-dated.
    """
    kept, removed = [], None
    for row in facts(project_root):
        if row["claim"] == claim.strip() and removed is None:
            removed = row
        else:
            kept.append(row)
    if removed is not None:
        _write(project_root, kept)
    return removed


def due(fact: dict[str, Any], today: date | None = None) -> bool:
    """Report whether this fact is old enough to need measuring again.

    An unparseable date reads as due, so a hand-edited record is re-checked rather than
    trusted indefinitely.
    """
    try:
        measured = date.fromisoformat(str(fact.get("measured")))
    except ValueError:
        return True
    return ((today or date.today()) - measured).days > STALE_AFTER_DAYS


def _usable(row: Any) -> bool:
    """Report whether a loaded row carries the three fields every fact must have."""
    return isinstance(row, dict) and all(
        isinstance(row.get(field), str) and row[field].strip()
        for field in ("claim", "evidence", "measured")
    )


def _write(project_root: Path, entries: list[dict[str, Any]]) -> None:
    """Replace the ledger with these entries, creating `.quarry` if it is not there yet."""
    path = project_root / BEHAVIOUR_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = sorted(entries, key=lambda row: str(row["claim"]))
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
