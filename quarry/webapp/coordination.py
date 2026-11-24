"""Read bd's fleet primitives for the board: the merge slot, open gates, and swarms.

Separate from `tracker` because this is a different question about the same repository.
`tracker` answers what the work is and how it depends on itself, from two bd calls every
open tab pays for. This answers who is coordinating right now, from commands measured
between 1.08s and 49.76s that only a fleet ever needs, and it reports absence rather than
raising, because a project with no slot and no swarms is normal rather than broken.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from webapp.tracker import TrackerError, bd_json


def coordination(project_root: Path) -> dict[str, Any]:
    """Return the merge slot, open gates and swarms, for a board watching a fleet.

    Deliberately not part of `snapshot`. Measured here, these three commands took between
    1.08s and 49.76s, and the snapshot is polled by every open tab; folding them in would
    tax every project for a view only a fleet needs. They run concurrently for the same
    reason the port sweep does, so the wait is the slowest single call rather than the sum.

    Each section reports its own failure instead of raising, because absence is the normal
    case: a project with no slot, no gates and no swarms is not a broken project, and a
    board that returns 500 when one primitive is missing would be useless exactly where it
    is most needed.
    """
    with ThreadPoolExecutor(max_workers=3) as pool:
        slot = pool.submit(_bd_section, project_root, ["merge-slot", "check", "--json"])
        gates = pool.submit(_bd_section, project_root, ["gate", "list", "--json"])
        swarms = pool.submit(_bd_section, project_root, ["swarm", "list", "--json"])
    return {
        "slot": slot.result(),
        "gates": _gate_list(gates.result()),
        "swarms": _swarm_detail(project_root, _swarm_list(swarms.result())),
    }


def _swarm_detail(project_root: Path, listed: dict[str, Any]) -> dict[str, Any]:
    """Attach each swarm's ready, blocked, active and completed breakdown.

    `bd swarm list` already carries the headline figures (`progress_percent`,
    `total_issues`, `completed_issues`), so this is the drill-down rather than the progress
    itself: `bd swarm status` names which issues are ready, blocked and done. It takes an
    epic id and refuses without one, so it is one call per swarm, run concurrently. A
    project with no swarms makes none of them, which is why the cost lands only where a
    fleet is actually running.
    """
    active = listed.get("active") or []
    if not active:
        return listed
    with ThreadPoolExecutor(max_workers=min(8, len(active))) as pool:
        details = list(pool.map(
            lambda swarm: _bd_section(
                project_root,
                ["swarm", "status", str(swarm.get("epic_id") or swarm.get("id", "")), "--json"],
            ),
            active,
        ))
    for swarm, detail in zip(active, details, strict=True):
        swarm["progress"] = detail
    return listed


def _bd_section(project_root: Path, args: list[str]) -> Any:
    """Return one bd command's JSON, or an `unavailable` object when it could not be read.

    Keyed `unavailable` rather than `error` on purpose: bd puts its own `error` inside a
    successful answer to mean absence, as `merge-slot check` does with "not found", and
    sharing the key made a project with no slot read as a project whose slot could not be
    read.
    """
    try:
        return bd_json(project_root, args)
    except TrackerError as error:
        return {"unavailable": str(error)}


def _gate_list(payload: Any) -> dict[str, Any]:
    """Normalise `bd gate list --json`, which answers `null` rather than `[]` when empty."""
    if isinstance(payload, dict) and "unavailable" in payload:
        return payload
    rows = payload if isinstance(payload, list) else []
    return {"open": [row for row in rows if isinstance(row, dict)]}


def _swarm_list(payload: Any) -> dict[str, Any]:
    """Normalise `bd swarm list --json`, which wraps its rows in a `swarms` key."""
    if isinstance(payload, dict) and "unavailable" in payload:
        return payload
    rows = payload.get("swarms") if isinstance(payload, dict) else None
    return {"active": [row for row in rows or [] if isinstance(row, dict)]}
