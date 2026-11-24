"""Expose sealed memory to the dashboard: the strata of units, and recall over them."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quarry_lib.ask import KnowledgeController, opening_line
from quarry_lib.search import unit_lines, unit_texts
from quarry_lib.store import MeshStore

MAX_QUESTION_CHARS = 400


def strata(project_root: Path) -> dict[str, Any]:
    """Return every sealed unit with its size and opening line, in mesh order.

    Sizes are reported in preserved lines rather than bytes because that is the unit the
    addresses recall hands back are counted in.
    """
    store = MeshStore(project_root / ".quarry")
    if not store.units_dir.is_dir():
        return {"units": [], "total_lines": 0}
    units = []
    for unit_id in unit_texts(store.units_dir):
        lines = unit_lines(store.units_dir, unit_id)
        units.append(
            {"id": unit_id, "lines": len(lines), "opening": opening_line(lines)}
        )
    return {"units": units, "total_lines": sum(u["lines"] for u in units)}


def recall(project_root: Path, question: str) -> dict[str, Any]:
    """Answer one plain-language question from sealed history.

    Returns the preserved passages at their citable addresses, never whole units, so the
    dashboard cannot become a way around the recall budget.
    """
    text = question.strip()[:MAX_QUESTION_CHARS]
    if not text:
        return {"question": "", "found": False, "terms": [], "passages": []}
    controller = KnowledgeController(MeshStore(project_root / ".quarry"))
    result = controller.ask(text)
    return {
        "question": text,
        "found": bool(result.found),
        "terms": list(result.terms),
        "searched_units": result.searched_units,
        "matched_lines": result.matched_lines,
        "truncated": bool(result.truncated),
        "passages": [
            {
                "address": passage.address,
                "unit": passage.unit,
                "start": passage.start,
                "end": passage.end,
                "text": passage.text,
            }
            for passage in result.passages
        ],
    }


