"""Read and change the bd issue tracker on behalf of the dashboard."""

from __future__ import annotations

import json
import statistics
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

STAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

# bd succeeded at 146.6s here under ordinary board load; below that it aborts real work.
BD_TIMEOUT_SECONDS = 180
BLOCKING_TYPE = "blocks"
STATUSES: tuple[str, ...] = (
    "open",
    "in_progress",
    "blocked",
    "deferred",
    "closed",
)
CLOSED_STATUS = "closed"
DEFERRED_STATUS = "deferred"
CLAIMED_STATUSES = frozenset({"in_progress"})
COORDINATION_LABEL = "gt:slot"
COORDINATION_TYPE = "molecule"
PRIORITIES = frozenset(range(5))


class TrackerError(RuntimeError):
    """Report that a bd command failed or returned something unusable."""


class TrackerTimeout(TrackerError):
    """Report that bd did not answer in time, which is not the same as refusing.

    A refusal is an answer: bd considered the request and said no, so retrying repeats it.
    A timeout says nothing about whether the work happened, and for a write bd may well
    have completed it, so an unaware retry is how duplicates get made. Callers that can
    only render one of these as an error would otherwise present them identically.
    """


def snapshot(project_root: Path) -> dict[str, Any]:
    """Return the whole tracker as one graph: nodes, edges, counts, and bd's statuses.

    `statuses` is the full vocabulary in board order, not merely the statuses in use, so
    the board can show every column including the empty ones.

    Every edge type bd holds is carried, each tagged with its `kind`, because a
    relationship the tracker records and the board drops reads as no relationship at all:
    a correctly linked pair was indistinguishable from an unlinked one. Measured on this
    project, `related` was the most common edge between two open issues and none of it
    reached the page.

    Only `blocks` feeds `blocked_by`, `depth` and `blocking`, matching bd's own rule that
    no other edge gates readiness, so widening what is drawn never widens what blocks.
    Closed issues are included so history stays visible.

    The edges are read from the rows `bd list --all --json` already carries under
    `dependencies`, omitted like every empty key when an issue has none, and not fetched
    with `bd dep list`. Measured on 223 issues: the one list call took 1.16 s and returned
    the same 161 edges that two batched dep list calls returned in 16.4 s. bd holds every
    other caller waiting while it answers, so a snapshot built from three calls kept the
    tracker busy for about 15 s of every poll, and a plain `bd show` in a terminal waited
    up to 65 s behind it.
    """
    rows = _issues(project_root)
    by_id = {row["id"]: row for row in rows}
    links = [
        edge
        for row in rows
        for edge in (row.get("dependencies") or [])
        if isinstance(edge, dict)
        and edge.get("type")
        and edge.get("issue_id") in by_id
        and edge.get("depends_on_id") in by_id
    ]

    blockers: dict[str, list[str]] = {issue_id: [] for issue_id in by_id}
    blocking: dict[str, int] = {issue_id: 0 for issue_id in by_id}
    for edge in links:
        if edge["type"] != BLOCKING_TYPE:
            continue
        dependent, prerequisite = edge["issue_id"], edge["depends_on_id"]
        blockers[dependent].append(prerequisite)
        blocking[prerequisite] += 1

    depth = _chain_lengths(
        {
            issue_id: [b for b in blocked_by if _is_open(by_id.get(b, {}))]
            for issue_id, blocked_by in blockers.items()
        }
    )
    stage = _chain_lengths(blockers)
    nodes = [
        _node(
            row,
            blockers[row["id"]],
            blocking[row["id"]],
            depth[row["id"]],
            stage[row["id"]],
            by_id,
        )
        for row in rows
    ]
    order = {"claimed": 0, "claimed_blocked": 1, "ready": 2, "blocked": 3, "closed": 4}
    nodes.sort(key=lambda n: (order.get(n["state"], 9), n["priority"], n["id"]))

    return {
        "nodes": nodes,
        "statuses": list(STATUSES),
        "edges": [
            {
                "from": edge["depends_on_id"],
                "to": edge["issue_id"],
                "kind": edge["type"],
            }
            for edge in links
        ],
        "counts": _counts(nodes),
    }


def activity(nodes: list[dict[str, Any]], limit: int = 40) -> list[dict[str, Any]]:
    """Return the most recent tracker events, newest first, derived from issue timestamps.

    bd exposes no event log, so each issue contributes the moments it actually records:
    when it was closed, when it last changed, and when it was created.
    """
    events: list[dict[str, Any]] = []
    for node in nodes:
        if node.get("closed_at"):
            events.append(_event(node, node["closed_at"], "closed", node["close_hint"],
                                 _elapsed(node.get("created_at"), node["closed_at"])))
        if node.get("updated_at") and node["updated_at"] != node.get("created_at"):
            events.append(_event(node, node["updated_at"], "updated", node["title"]))
        if node.get("created_at"):
            events.append(_event(node, node["created_at"], "filed", node["title"]))
    events.sort(key=lambda e: e["at"], reverse=True)
    return events[:limit]


def timing(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    """Return median lead and cycle times over closed issues, plus lead time for bugs alone.

    Lead time is `closed_at` minus `created_at`: how long the work waited plus ran. Cycle
    time is `closed_at` minus `started_at`: how long it ran once somebody picked it up. All
    three stamps come from bd, so both are measured rather than estimated. The median is
    reported instead of the mean because a few long-lived issues drag an average away from
    what the typical issue actually took.

    An issue closed without ever being claimed carries no `started_at` and is left out of
    the cycle figure rather than counted as instant, so `cycle_counted` is normally smaller
    than `closed`. Reporting both is the honest way to say the sample differs.

    Returns seconds, or None where nothing qualifies, which is a different fact from zero.
    """
    closed = [node for node in nodes if node.get("state") == "closed"]
    leads = [
        seconds
        for node in closed
        if (seconds := _elapsed(node.get("created_at"), node.get("closed_at"))) is not None
    ]
    cycles = [
        seconds
        for node in closed
        if (seconds := _elapsed(node.get("started_at"), node.get("closed_at"))) is not None
    ]
    bugs = [
        seconds
        for node in closed
        if node.get("type") == "bug"
        and (seconds := _elapsed(node.get("created_at"), node.get("closed_at"))) is not None
    ]
    return {
        "closed": len(leads),
        "lead_seconds": statistics.median(leads) if leads else None,
        "cycle_counted": len(cycles),
        "cycle_seconds": statistics.median(cycles) if cycles else None,
        "bugs_closed": len(bugs),
        "bug_lead_seconds": statistics.median(bugs) if bugs else None,
    }


def create(project_root: Path, title: str, issue_type: str, priority: int) -> str:
    """Create one issue and return its new id.

    The type is passed through to bd rather than checked against a list here. bd owns the
    type vocabulary, rejects an unknown one non-zero with a clearer message than a
    second-guess could give, and gains types (and custom ones) without the board being
    told; a copy of that list here went stale twice and blocked three real types.

    Raises:
        TrackerError: the title is blank, or bd refused the issue.
    """
    if not title.strip():
        raise TrackerError("an issue needs a title")
    out = _bd(
        project_root,
        [
            "create",
            f"--title={title.strip()}",
            f"--type={issue_type}",
            f"--priority={int(priority)}",
        ],
    )
    for token in out.replace(":", " ").split():
        if "-" in token and token[0].isalpha():
            return token
    raise TrackerError(f"bd create gave no issue id: {out.strip()[:200]}")


def close(project_root: Path, issue_id: str, reason: str) -> None:
    """Close one issue with the reason recorded against it."""
    args = ["close", issue_id]
    if reason.strip():
        args.append(f"--reason={reason.strip()}")
    _bd(project_root, args)


def claim(project_root: Path, issue_id: str) -> None:
    """Claim one issue, setting it in progress and assigned to the current actor."""
    _bd(project_root, ["update", issue_id, "--claim"])


def prioritize(project_root: Path, issue_id: str, priority: int) -> None:
    """Set one issue's priority, 0 critical through 4 backlog.

    Raises:
        TrackerError: the priority is outside the range bd accepts, refused here rather
            than passed on, so the board never reports a change bd did not make.
    """
    if priority not in PRIORITIES:
        raise TrackerError(f"priority must be 0 through 4, not {priority}")
    _bd(project_root, ["priority", issue_id, str(priority)])


def reopen(project_root: Path, issue_id: str, reason: str) -> None:
    """Reopen one closed issue."""
    args = ["reopen", issue_id]
    if reason.strip():
        args.append(f"--reason={reason.strip()}")
    _bd(project_root, args)


def link(project_root: Path, dependent: str, prerequisite: str) -> None:
    """Make `dependent` wait on `prerequisite` with a blocking edge."""
    if dependent == prerequisite:
        raise TrackerError("an issue cannot block itself")
    _bd(project_root, ["dep", "add", dependent, prerequisite])


def unlink(project_root: Path, dependent: str, prerequisite: str) -> None:
    """Remove the blocking edge between two issues."""
    _bd(project_root, ["dep", "remove", dependent, prerequisite])


def delete(project_root: Path, issue_id: str) -> None:
    """Delete one issue and any edges referring to it."""
    _bd(project_root, ["delete", issue_id, "--force"])


def detail(project_root: Path, issue_id: str) -> dict[str, Any]:
    """Return one issue's full record, including the long text fields."""
    row = bd_json(project_root, ["show", issue_id, "--json"])
    if isinstance(row, list):
        if not row:
            raise TrackerError(f"no such issue: {issue_id}")
        row = row[0]
    if not isinstance(row, dict):
        raise TrackerError(f"unexpected bd show output for {issue_id}")
    return row


def ready(project_root: Path, limit: int) -> list[dict[str, Any]]:
    """Return the rows bd reports ready: open, with no active blocker.

    Args:
        limit: how many rows to ask bd for. Passed rather than defaulted because `bd ready`
            stops at ten of its own accord, and a frontier silently cut to ten reads to a
            caller exactly like a complete one.
    """
    rows = bd_json(project_root, ["ready", "--json", "--limit", str(limit)])
    return [row for row in rows or [] if isinstance(row, dict) and row.get("id")]


def records(project_root: Path, issue_ids: list[str]) -> list[dict[str, Any]]:
    """Return the full record of each named issue, in one bd call."""
    if not issue_ids:
        return []
    rows = bd_json(project_root, ["show", *issue_ids, "--json"])
    return [row for row in rows or [] if isinstance(row, dict) and row.get("id")]


def _issues(project_root: Path) -> list[dict[str, Any]]:
    rows = bd_json(project_root, ["list", "--all", "--json"])
    if not isinstance(rows, list):
        raise TrackerError("bd list did not return an array")
    return [row for row in rows if isinstance(row, dict) and row.get("id")]


def _chain_lengths(blockers: dict[str, list[str]]) -> dict[str, int]:
    """Return each issue's longest blocker chain, cycle-safe.

    Used twice over different edge sets: over open blockers it measures how far an issue
    still is from being startable, and over every blocker it measures where the issue sits
    in the planned order.
    """
    length: dict[str, int] = {}
    walking: set[str] = set()

    def measure(issue_id: str) -> int:
        if issue_id in length:
            return length[issue_id]
        if issue_id in walking:
            return 0
        walking.add(issue_id)
        length[issue_id] = 1 + max(
            (measure(blocker) for blocker in blockers.get(issue_id, ())), default=-1
        )
        walking.discard(issue_id)
        return length[issue_id]

    for issue_id in blockers:
        measure(issue_id)
    return length


def _node(
    row: dict[str, Any],
    blockers: list[str],
    blocking: int,
    depth: int,
    stage: int,
    by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    open_blockers = [b for b in blockers if _is_open(by_id.get(b, {}))]
    return {
        "id": row["id"],
        "title": row.get("title", ""),
        "status": row.get("status", "open"),
        "state": _state(row, open_blockers),
        "type": row.get("issue_type", "task"),
        "priority": int(row.get("priority", 2) or 2),
        "blocking": blocking,
        "blocked_by": open_blockers,
        "labels": [str(label) for label in (row.get("labels") or [])],
        "depth": depth,
        "stage": stage,
        "assignee": str(row.get("assignee") or ""),
        "holder": _holder(row),
        "created_at": row.get("created_at", ""),
        "started_at": row.get("started_at", ""),
        "updated_at": row.get("updated_at", ""),
        "closed_at": row.get("closed_at", ""),
        "close_hint": (row.get("close_reason", "") or row.get("title", "")).split("\n")[0],
        "acceptance": row.get("acceptance_criteria", "") or "",
    }


def _holder(row: dict[str, Any]) -> str:
    """Return who holds this bead, which bd records in metadata rather than in assignee.

    The merge slot is the case that matters: `bd merge-slot acquire` writes the actor into
    `metadata.holder` and leaves assignee empty, so a held lock read as claimed by nobody.
    """
    metadata = row.get("metadata")
    return str(metadata.get("holder") or "") if isinstance(metadata, dict) else ""


def _state(row: dict[str, Any], open_blockers: list[str]) -> str:
    """Return the issue's real board state, blocked-ness checked ahead of claimed-ness.

    A claimed issue with an open blocker cannot actually be worked despite `in_progress`
    saying otherwise, so it reports `claimed_blocked` rather than the plain `claimed` a
    naive claimed-first check would give it, which hid the block entirely.

    Deferred is checked before either, and before blockers, because bd hides a deferred
    issue from `bd ready` outright: without this it fell through to `ready` and the board
    offered work bd would not. Measured on this repository, the board called 22 issues ready
    where bd named 17, and all five extras were deferred. Deferral is also the deliberate
    act, so it is the more useful answer when an issue is both deferred and blocked.
    """
    status = row.get("status", "open")
    if not _is_open(row):
        return "closed"
    if status == DEFERRED_STATUS:
        return DEFERRED_STATUS
    claimed = status in CLAIMED_STATUSES
    if open_blockers:
        return "claimed_blocked" if claimed else "blocked"
    return "claimed" if claimed else "ready"


def _is_open(row: dict[str, Any]) -> bool:
    """Report whether an issue is still live, closed being bd's only terminal status.

    Derived rather than enumerated so a status bd gains later counts as live instead of
    being silently filed as closed.
    """
    return str(row.get("status", "")) != CLOSED_STATUS


def _counts(nodes: list[dict[str, Any]]) -> dict[str, int]:
    """Tally nodes by board state, counting work and not the beads that coordinate it.

    A claimed-but-blocked issue cannot actually be worked, so it counts toward the
    summary bar's `blocked` figure rather than inflating `claimed` with issues that are
    not truly available.

    Coordination beads are left out of the state figures, and bd creates two kinds. The merge
    slot is an ordinary issue carrying `gt:slot` that goes `in_progress` while held, so
    counting rows reported a held lock as an agent at work: measured with three agents holding
    tickets, the board said four claimed while the fleet view said three active. A swarm
    creates a `molecule`, which `bd ready` does not offer at all; counting it put a bead no
    agent can claim in the ready figure, measured in an arena where bd named three ready rows
    and the board named a different three.

    `total` still counts every node, because it labels the graph and board tabs and those
    draw both kinds like any other bead. The two figures answer different questions, how much
    work there is and how much is on screen, and only the first one excludes coordination.
    """
    work = [
        node
        for node in nodes
        if COORDINATION_LABEL not in node["labels"] and node["type"] != COORDINATION_TYPE
    ]
    tally = {"ready": 0, "claimed": 0, "blocked": 0, "deferred": 0, "closed": 0,
             "total": len(nodes)}
    for node in work:
        state = "blocked" if node["state"] == "claimed_blocked" else node["state"]
        tally[state] = tally.get(state, 0) + 1
    return tally


def _event(
    node: dict[str, Any],
    at: str,
    kind: str,
    text: str,
    after: float | None = None,
) -> dict[str, Any]:
    return {
        "at": at,
        "kind": kind,
        "id": node["id"],
        "text": text,
        "state": node["state"],
        "after": after,
    }


def _elapsed(start: str | None, end: str | None) -> float | None:
    """Return the seconds between two bd stamps, None when either is missing or malformed."""
    if not start or not end:
        return None
    try:
        began = datetime.strptime(start, STAMP_FORMAT)
        ended = datetime.strptime(end, STAMP_FORMAT)
    except ValueError:
        return None
    seconds = (ended - began).total_seconds()
    return seconds if seconds >= 0 else None


def bd_json(project_root: Path, args: list[str]) -> Any:
    """Return one bd command's JSON output.

    A bare `null` is an answer, not a failure: `bd gate list --json` prints exactly that
    when the project has no gates, and scanning for a bracket or a brace reported the
    ordinary empty case as unreadable output.

    Public because `coordination` runs bd for the same project through the same rules, and
    a second copy of this would be a second place for those rules to drift.
    """
    raw = _bd(project_root, args).strip()
    if not raw:
        return []
    if raw == "null":
        return None
    start = min(
        (i for i in (raw.find("["), raw.find("{")) if i != -1),
        default=-1,
    )
    if start == -1:
        raise TrackerError(f"bd {args[0]} returned no JSON: {raw[:200]}")
    try:
        return json.loads(raw[start:])
    except json.JSONDecodeError as error:
        raise TrackerError(f"bd {args[0]} returned invalid JSON: {error}") from error


def _bd(project_root: Path, args: list[str]) -> str:
    """Run one bd command in the project and return its stdout.

    The failure message carries the exit code, not only the first line bd said. A board once
    reported `bd list --all --json failed: no output`, and that message is what made the cause
    unfindable: bd had exited non-zero with both streams empty, and the exit code, the one
    fact that separates a process that was killed from one that refused, had been dropped.

    Raises:
        TrackerError: bd is missing or exited non-zero.
        TrackerTimeout: bd did not answer within `BD_TIMEOUT_SECONDS`.
    """
    try:
        done = subprocess.run(
            ["bd", *args],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=BD_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError as error:
        raise TrackerError("bd is not on PATH; the dashboard needs the bd CLI") from error
    except subprocess.TimeoutExpired as error:
        raise TrackerTimeout(
            f"bd {args[0]} did not answer within {BD_TIMEOUT_SECONDS}s. It may still have "
            f"done the work, so check the tracker before repeating this."
        ) from error
    if done.returncode != 0:
        detail = (done.stderr or done.stdout or "").strip().splitlines()
        said = detail[0] if detail else "no output on either stream"
        raise TrackerError(f"bd {' '.join(args)} failed (exit {done.returncode}): {said}")
    return done.stdout
