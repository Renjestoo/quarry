"""Predict which files an issue will touch, so a fleet is not dispatched onto one file."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

ATLAS_DIRNAME = "graft"
ATLAS_TIMEOUT_SECONDS = 120.0
DEFAULT_HITS = 8
QUERY_CHARS = 1200
SCORE_SHARE = 0.6


class CollideError(RuntimeError):
    """The atlas could not be consulted, so nothing can be predicted."""


def has_atlas(project_root: Path) -> bool:
    """Report whether this project carries a graft atlas to predict against."""
    return (project_root / ATLAS_DIRNAME).is_dir()


def contention(
    project_root: Path,
    rows: list[dict[str, Any]],
    hits: int = DEFAULT_HITS,
) -> dict[str, Any]:
    """Return each file more than one of these issues is predicted to touch.

    The prediction is the atlas ranking an issue's own words, so it is a warning to check
    rather than a fact: an issue whose text names no code ranks nothing, and two issues can
    share a ranked file without either editing it. It answers the one question bd cannot
    answer at all, which is whether two issues with no dependency edge are heading for the
    same lines. bd knows only the edges somebody declared.

    Reported per file rather than per pair. Twenty ready issues make a hundred and ninety
    pairs and a wall of text nobody reads, while the same data grouped by file is one line
    per contended path and says the thing a dispatcher needs: these issues are heading for
    this file, so do not hand them out at once.

    Args:
        rows: bd issue records, each needing `id` and carrying `title` and `description`.
        hits: ranked atlas nodes to take per issue. Wider catches more real overlap and
            more coincidence.

    Raises:
        CollideError: the atlas is missing, slow, or unreadable.
    """
    predicted = {
        str(row["id"]): _paths(project_root, _query(row), hits)
        for row in rows
        if row.get("id")
    }
    tally: dict[str, list[str]] = defaultdict(list)
    for issue_id, paths in predicted.items():
        for path in paths:
            tally[path].append(issue_id)
    return {
        "predicted": {key: sorted(value) for key, value in predicted.items()},
        "checked": len(predicted),
        "contended": {path: sorted(ids) for path, ids in tally.items() if len(ids) > 1},
    }


def _query(row: dict[str, Any]) -> str:
    """Return the issue's own words, capped so the lexical query stays focused."""
    words = " ".join(
        part
        for part in (str(row.get("title") or ""), str(row.get("description") or ""))
        if part
    )
    return words[:QUERY_CHARS]


def _paths(project_root: Path, query: str, hits: int) -> frozenset[str]:
    """Return the paths the atlas ranks confidently for this text.

    Keeps only hits scoring at least `SCORE_SHARE` of the top hit, rather than every hit
    asked for. The cut is relative because the scores are not normalised across queries, and
    it adapts: a query with one dominant match keeps almost nothing, a diffuse one keeps
    more. Measured against four issues whose real edits are known, the file actually edited
    ranked first or second every time, with a cliff below that; taking all eight hits made
    two issues in unrelated areas of the codebase appear to collide.
    """
    if not query.strip():
        return frozenset()
    payload = _atlas(project_root, ["ask", "--json", "-n", str(hits), query])
    ranked = payload.get("hits") or []
    if not ranked:
        return frozenset()
    floor = float(ranked[0].get("score") or 0.0) * SCORE_SHARE
    found = set()
    for hit in ranked:
        if float(hit.get("score") or 0.0) < floor:
            continue
        pointer = str(hit.get("pointer") or "")
        head, separator, tail = pointer.rpartition(":")
        path = head if separator and tail.startswith("L") else pointer
        if path:
            found.add(path)
    return frozenset(found)


def _atlas(project_root: Path, args: list[str]) -> dict[str, Any]:
    """Run one graft command in the project and return its JSON.

    Resolves the executable through `shutil.which` because graft ships as a shim on
    Windows, which bare `subprocess` will not find by name.

    Raises:
        CollideError: graft is missing, timed out, exited non-zero, or answered without
            JSON.
    """
    executable = shutil.which("graft")
    if executable is None:
        raise CollideError("graft is not on PATH; the atlas is what predicts the paths")
    try:
        done = subprocess.run(
            [executable, *args],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=ATLAS_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise CollideError(
            f"graft {args[0]} did not answer within {ATLAS_TIMEOUT_SECONDS:.0f}s"
        ) from error
    if done.returncode != 0:
        detail = (done.stderr or done.stdout or "").strip().splitlines()
        raise CollideError(f"graft {args[0]} failed: {detail[0] if detail else 'no output'}")
    raw = done.stdout.strip()
    start = raw.find("{")
    if start == -1:
        raise CollideError(f"graft {args[0]} returned no JSON: {raw[:200]}")
    try:
        return json.loads(raw[start:])
    except json.JSONDecodeError as error:
        raise CollideError(f"graft {args[0]} returned invalid JSON: {error}") from error
