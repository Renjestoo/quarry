"""Read and change the project's interaction mode, and report the server's own settings."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

MODE_FILE = Path("docs") / "agents" / "quarry.md"
MODE_LINE = re.compile(r"^(\s*Interaction mode:[ \t]*)(\S+)[ \t]*$", re.IGNORECASE | re.MULTILINE)
MODES = ("interactive", "yolo")
MODE_MEANING = {
    "interactive": "lifecycle skills ask you at every decision point",
    "yolo": "lifecycle skills dispatch the answer agent instead, surfacing only NEEDS HUMAN",
}


class SettingsError(RuntimeError):
    """Report that the mode could not be read or written."""


def settings(
    project_root: Path,
    endpoint: dict[str, Any],
    poll_ms: int,
    health: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the project's mode, the connection facts the page needs, and the board's health.

    Args:
        health: what the running board can say about itself, as `Dashboard.health` reports
            it. Absent means the caller had no board to ask, not a board with nothing to say.
    """
    mode, configured = _read_mode(project_root)
    return {
        "mode": mode,
        "configured": configured,
        "modes": list(MODES),
        "meaning": MODE_MEANING,
        "mode_file": MODE_FILE.as_posix(),
        "poll_ms": poll_ms,
        "host": endpoint.get("host", ""),
        "port": endpoint.get("port", 0),
        "project": endpoint.get("project", str(project_root)),
        "health": health or {},
    }


def set_mode(project_root: Path, mode: str) -> str:
    """Write the interaction mode into the same line `/quarry:mode` reads, and return it.

    Rewrites only that line so the rest of the agent brief survives. Refuses to create the
    file: a project with no brief is unconfigured, and inventing one here would hide that
    from `/quarry:setup` rather than fix it.

    Raises:
        SettingsError: the mode is not one of MODES, or the file or its line is missing.
    """
    wanted = mode.strip().lower()
    if wanted not in MODES:
        raise SettingsError(f"mode must be one of {', '.join(MODES)}, not {mode!r}")
    path = project_root / MODE_FILE
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise SettingsError(
            f"{MODE_FILE.as_posix()} is missing; run /quarry:setup to configure this project"
        ) from error
    if not MODE_LINE.search(text):
        raise SettingsError(
            f"{MODE_FILE.as_posix()} has no 'Interaction mode:' line; run /quarry:setup"
        )
    updated = MODE_LINE.sub(lambda found: f"{found.group(1)}{wanted}", text, count=1)
    try:
        path.write_text(updated, encoding="utf-8", newline="")
    except OSError as error:
        raise SettingsError(f"could not write {MODE_FILE.as_posix()}: {error}") from error
    return wanted


def _read_mode(project_root: Path) -> tuple[str, bool]:
    try:
        text = (project_root / MODE_FILE).read_text(encoding="utf-8")
    except (OSError, ValueError):
        return "", False
    found = MODE_LINE.search(text)
    if not found:
        return "", False
    mode = found.group(2).strip().lower()
    return (mode, True) if mode in MODES else (mode, False)
