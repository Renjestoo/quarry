"""Delete one bd epic with its child issues, through bd's own delete command.

`quarry delete-epic <id>` previews; with `--force` it deletes. Only the epic and the issues
whose parent chain leads to it are named; no issue is chosen by its title or text. The
sealed mesh is never touched.
"""

from __future__ import annotations

import json
from pathlib import Path

from quarry_lib.driver import BD_TIMEOUT_SECONDS, DriverError, tool


def _rows(project_root: Path, args: list[str]) -> list[dict]:
    raw = tool(project_root, "bd", [*args, "--json"], BD_TIMEOUT_SECONDS)
    try:
        rows = json.loads(raw) if raw.strip() else []
    except ValueError as error:
        raise DriverError(f"bd {args[0]} gave no JSON: {error}") from error
    if not isinstance(rows, list):
        raise DriverError(f"bd {args[0]} gave no list of issues")
    return rows


def plan(project_root: Path, epic: str) -> dict:
    """Return the epic and every issue under it, children first by depth.

    Raises:
        DriverError: the issue does not exist, is not an epic, or bd failed.
    """
    shown = _rows(project_root, ["show", epic])
    if len(shown) != 1 or shown[0].get("id") != epic:
        raise DriverError(f"bd has no issue {epic}")
    if shown[0].get("issue_type") != "epic":
        raise DriverError(f"{epic} is a {shown[0].get('issue_type')}, not an epic; nothing deleted")
    children: list[str] = []
    frontier = [epic]
    while frontier:
        parent = frontier.pop(0)
        for row in _rows(project_root, ["children", parent]):
            child = str(row.get("id"))
            if child not in children and child != epic:
                children.append(child)
                frontier.append(child)
    return {"epic": epic, "title": shown[0].get("title", ""), "children": children}


def delete(project_root: Path, epic: str) -> dict:
    """Delete the epic and the issues under it with `bd delete --force`; return what went."""
    found = plan(project_root, epic)
    tool(
        project_root, "bd", ["delete", *found["children"], epic, "--force"], BD_TIMEOUT_SECONDS
    )
    return {**found, "deleted": [*found["children"], epic]}
