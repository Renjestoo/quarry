"""Read back the preserved lines of sealed units at citable addresses."""

from __future__ import annotations

import re
from pathlib import Path

from quarry_lib.freeze import TEXT_SUFFIX

UNIT_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}")


class SearchError(ValueError):
    """Report an unknown unit or a line range outside a unit."""


def unit_texts(units_dir: Path) -> list[str]:
    """Return every unit id that has preserved text, in mesh order."""
    if not units_dir.exists():
        return []
    return sorted((path.stem for path in units_dir.glob(f"*{TEXT_SUFFIX}")), key=_mesh_order)


def unit_lines(units_dir: Path, unit_id: str) -> list[str]:
    """Return one unit's preserved text as lines, without their terminators."""
    return _text_path(units_dir, unit_id).read_text(encoding="utf-8").splitlines()


def read_lines(units_dir: Path, unit_id: str, start: int, end: int) -> str:
    """Return lines `start` to `end` inclusive of one unit's preserved text, 1-indexed."""
    lines = unit_lines(units_dir, unit_id)
    if start < 1 or end < start:
        raise SearchError(f"invalid line range {start}-{end} for {unit_id}")
    if start > len(lines):
        raise SearchError(f"{unit_id} has {len(lines)} lines, so line {start} does not exist")
    return "\n".join(lines[start - 1 : end])


def _text_path(units_dir: Path, unit_id: str) -> Path:
    """Return the unit's text file, refusing any id that could escape the units directory.

    The id may arrive from a model, so it is matched against a strict pattern rather than
    merely joined onto the directory.
    """
    if UNIT_PATTERN.fullmatch(unit_id) is None:
        raise SearchError(f"unknown unit: {unit_id}")
    path = units_dir / f"{unit_id}{TEXT_SUFFIX}"
    if not path.is_file():
        raise SearchError(f"unknown unit: {unit_id}")
    return path


def _mesh_order(unit_id: str) -> tuple[int, str]:
    digits = "".join(character for character in unit_id if character.isdigit())
    return (int(digits) if digits else 0, unit_id)
