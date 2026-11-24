"""Durable home of immutable sealed units and their mesh index."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from quarry_lib.freeze import TEXT_SUFFIX, FrozenUnit, hash_text

EVIDENCE_SUFFIX = ".jsonl"


@dataclass(frozen=True)
class SnapshotRecord:
    """Seal metadata for one snapshot."""

    snapshot_id: str
    source: str
    unit_ids: tuple[str, ...]


class MeshStore:
    """Persist immutable sealed units under a project's `.quarry` directory.

    Each unit is three files in `units/`: its metadata as JSON, the searchable distilled
    text as `<unit>.md`, and the sealed byte-exact evidence copy as `<unit>.jsonl`. Recall
    searches the text; the evidence copy stays the record. `mesh.json` indexes snapshots
    and remembers how far each transcript source has been sealed.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.units_dir = root / "units"
        self.index_path = root / "mesh.json"

    def initialize(self) -> None:
        """Create the mesh directories and index, idempotently."""
        self.units_dir.mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self._write_index({"snapshots": [], "progress": {}})

    def save_frozen_unit(self, unit: FrozenUnit) -> FrozenUnit:
        """Persist one unit, write its searchable text, and add it to the index."""
        if unit.snapshot_id != self.next_snapshot_id():
            raise ValueError(
                f"expected next snapshot {self.next_snapshot_id()}, got {unit.snapshot_id}"
            )
        stored = self.write_text(unit)
        self.save_snapshot(SnapshotRecord(stored.snapshot_id, stored.source, (stored.unit_id,)))
        self.save_units([stored])
        return stored

    def write_text(self, unit: FrozenUnit) -> FrozenUnit:
        """Write the unit's preserved text and stamp its path and digest onto the unit.

        Written once and never replaced, because every citation resolves against it by
        line number; rewriting it would silently re-point citations already issued.
        """
        self.units_dir.mkdir(parents=True, exist_ok=True)
        path = self.units_dir / f"{unit.unit_id}{TEXT_SUFFIX}"
        content = unit.content if unit.content.endswith("\n") else unit.content + "\n"
        if path.exists():
            if path.read_text(encoding="utf-8") != content:
                raise ValueError(f"immutable unit text already differs: {path}")
        else:
            path.write_text(content, encoding="utf-8", newline="\n")
        return replace(unit, text_path=str(path), text_sha256=hash_text(content))

    def next_snapshot_id(self) -> str:
        """Return the snapshot id the next sealed unit will take."""
        return f"K{len(self.snapshots()) + 1}"

    def snapshots(self) -> list[SnapshotRecord]:
        """Return every recorded snapshot, in seal order."""
        data = self._read_index()
        return [self._snapshot_from_dict(item) for item in data.get("snapshots", [])]

    def save_snapshot(self, record: SnapshotRecord) -> None:
        """Append one snapshot record to the index."""
        data = self._read_index()
        data.setdefault("snapshots", []).append(
            {
                "snapshot_id": record.snapshot_id,
                "source": record.source,
                "unit_ids": list(record.unit_ids),
            }
        )
        self._write_index(data)

    def save_units(self, units: list[FrozenUnit]) -> None:
        """Write each unit's metadata JSON next to its text."""
        self.units_dir.mkdir(parents=True, exist_ok=True)
        for unit in units:
            path = self.units_dir / f"{unit.unit_id}.json"
            path.write_text(json.dumps(unit.to_dict(), indent=2), encoding="utf-8")

    def load_units(self) -> list[FrozenUnit]:
        """Return every sealed unit, in mesh order."""
        if not self.units_dir.exists():
            return []
        units = [self._load_unit(path) for path in sorted(self.units_dir.glob("K*.json"))]
        return sorted(units, key=_unit_sort_key)

    def progress(self, source_path: str) -> int:
        """Return the byte offset through which one transcript source is already sealed."""
        data = self._read_index()
        record = data.get("progress", {}).get(source_path)
        return int(record["bytes"]) if isinstance(record, dict) else 0

    def set_progress(self, source_path: str, unit_id: str, end: int) -> None:
        """Record how far one transcript source has been sealed."""
        data = self._read_index()
        data.setdefault("progress", {})[source_path] = {"unit": unit_id, "bytes": end}
        self._write_index(data)

    def progress_messages(self, source_path: str) -> int:
        """Return the message count through which one snapshot source is already sealed."""
        data = self._read_index()
        record = data.get("progress", {}).get(source_path)
        return int(record["messages"]) if isinstance(record, dict) else 0

    def set_progress_messages(self, source_path: str, unit_id: str, messages: int) -> None:
        """Record how many messages of one snapshot source are sealed."""
        data = self._read_index()
        data.setdefault("progress", {})[source_path] = {"unit": unit_id, "messages": messages}
        self._write_index(data)

    def _load_unit(self, path: Path) -> FrozenUnit:
        data = json.loads(path.read_text(encoding="utf-8"))
        return FrozenUnit.from_dict(data)

    def _read_index(self) -> dict[str, Any]:
        if not self.index_path.exists():
            return {"snapshots": []}
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def _write_index(self, data: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @staticmethod
    def _snapshot_from_dict(data: dict[str, Any]) -> SnapshotRecord:
        return SnapshotRecord(
            snapshot_id=str(data["snapshot_id"]),
            source=str(data["source"]),
            unit_ids=tuple(str(item) for item in data["unit_ids"]),
        )


def _unit_sort_key(unit: FrozenUnit) -> int:
    return int(unit.snapshot_id.removeprefix("K"))
