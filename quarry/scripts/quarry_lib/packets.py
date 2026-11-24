"""Addressed passages and the recall result that carries them."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Passage:
    """One run of preserved lines, addressed by the unit and line range it was taken from."""

    unit: str
    start: int
    end: int
    text: str

    @property
    def address(self) -> str:
        """Return the location as `unit:line` or `unit:start-end`."""
        if self.start == self.end:
            return f"{self.unit}:{self.start}"
        return f"{self.unit}:{self.start}-{self.end}"

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe persisted form of the passage."""
        return {
            "unit": self.unit,
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "address": self.address,
        }


@dataclass(frozen=True)
class AskResult:
    """Preserved passages matching one question, with the evidence of how they were found.

    Args:
        terms: the words actually matched against the preserved text, after stopwords and
            short words were dropped. An empty result means nothing without them, since a
            question whose wording shares nothing with the history looks identical to a
            history that never covered it.
        truncated: more lines matched than were returned, so these passages are the
            best-scoring sample rather than every match.
    """

    question: str
    passages: tuple[Passage, ...]
    terms: tuple[str, ...]
    searched_units: int
    matched_lines: int
    truncated: bool = False

    @property
    def found(self) -> bool:
        """Report whether any preserved passage matched."""
        return bool(self.passages)

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe persisted form of the result."""
        return {
            "question": self.question,
            "passages": [passage.to_dict() for passage in self.passages],
            "terms": list(self.terms),
            "searched_units": self.searched_units,
            "matched_lines": self.matched_lines,
            "truncated": self.truncated,
            "found": self.found,
        }
