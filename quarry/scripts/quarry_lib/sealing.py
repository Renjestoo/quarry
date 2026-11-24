"""Byte-exact copies and digests for immutable sealed evidence."""

from __future__ import annotations

import contextlib
import hashlib
import os
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path

from quarry_lib.freeze import FrozenUnit

COPY_CHUNK_BYTES = 1024 * 1024
TAIL_SCAN_BYTES = 65536
LOCK_NAME = "seal.lock"
LOCK_TIMEOUT_SECONDS = 120.0
LOCK_POLL_SECONDS = 0.05


class SealingError(RuntimeError):
    """Report a refusal to write or verify a sealed byte range."""


@contextlib.contextmanager
def mesh_lock(root: Path, timeout: float = LOCK_TIMEOUT_SECONDS) -> Iterator[None]:
    """Hold the exclusive right to seal into `root`, so concurrent seals queue instead of race.

    Sealing is a read-modify-write across three steps: choosing the next unit id from the
    index, writing the evidence copy under that id, and recording the unit. Interleaving two
    of those sequences loses one seal and can leave a unit whose metadata names one session
    while its evidence holds another, because the evidence digest is taken from the written
    file rather than from the source range, so the substitution still verifies. Serialising
    the whole sequence is what prevents both, and it is why this is one lock rather than
    three atomic steps.

    Args:
        timeout: seconds to wait for a holder to finish before refusing. Refuses loudly and
            names the lock file: a seal that silently gave up would lose the history this
            module exists to keep.

    Raises:
        SealingError: the lock was still held when `timeout` elapsed.
    """
    path = root / LOCK_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    while True:
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise SealingError(
                    f"another seal has held {path} for over {timeout:.0f}s. If no seal is "
                    f"running, delete that file: it is a lock, not evidence."
                ) from None
            time.sleep(LOCK_POLL_SECONDS)
            continue
        break
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(f"{os.getpid()}\n")
        yield
    finally:
        path.unlink(missing_ok=True)


def hash_range(path: Path, start: int, end: int) -> str:
    """Return the sha256 of `path` bytes `start` (inclusive) to `end` (exclusive)."""
    digest = hashlib.sha256()
    remaining = end - start
    with path.open("rb") as handle:
        handle.seek(start)
        while remaining > 0:
            chunk = handle.read(min(COPY_CHUNK_BYTES, remaining))
            if not chunk:
                raise SealingError(f"{path} ended before byte {end}")
            digest.update(chunk)
            remaining -= len(chunk)
    return digest.hexdigest()


def line_complete_end(path: Path) -> int:
    """Return the largest byte offset of `path` that ends on a newline."""
    size = path.stat().st_size
    if size == 0:
        return 0
    with path.open("rb") as handle:
        handle.seek(size - 1)
        if handle.read(1) == b"\n":
            return size
        window_start = max(0, size - TAIL_SCAN_BYTES)
        handle.seek(window_start)
        tail = handle.read(size - window_start)
    cut = tail.rfind(b"\n")
    return window_start + cut + 1 if cut >= 0 else 0


def write_segment(source: Path, destination: Path, start: int, end: int) -> None:
    """Copy bytes `[start, end)` of `source` to `destination` atomically, never replacing.

    Both ends must land on line boundaries, so a sealed segment always parses as whole
    records, and an interrupted copy can never leave a partial file at `destination`.
    """
    source_size = source.stat().st_size
    if start < 0 or end <= start or end > source_size:
        raise SealingError(f"invalid sealed range {start}-{end}/{source_size}: {source}")
    with source.open("rb") as handle:
        if start > 0:
            handle.seek(start - 1)
            if handle.read(1) != b"\n":
                raise SealingError(f"sealed range start is not line-complete: {start}")
        handle.seek(end - 1)
        if handle.read(1) != b"\n":
            raise SealingError(f"sealed range end is not line-complete: {end}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise SealingError(f"refusing to replace sealed evidence: {destination}")
    descriptor, name = tempfile.mkstemp(
        prefix=f".{destination.name}-", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(name)
    try:
        remaining = end - start
        with source.open("rb") as reader, os.fdopen(descriptor, "wb") as writer:
            reader.seek(start)
            while remaining > 0:
                chunk = reader.read(min(COPY_CHUNK_BYTES, remaining))
                if not chunk:
                    raise SealingError(f"{source} ended before byte {end}")
                writer.write(chunk)
                remaining -= len(chunk)
            writer.flush()
            os.fsync(writer.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def write_text_once(path: Path, text: str) -> None:
    """Write generated evidence text to `path` atomically, never replacing.

    The evidence copies of zcode seals are re-serialized message arrays rather than
    byte ranges of a source file, so they are written through this helper with the
    same atomicity and write-once refusal as copied segments.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise SealingError(f"refusing to replace sealed evidence: {path}")
    descriptor, name = tempfile.mkstemp(
        prefix=f".{path.name}-", suffix=".tmp", dir=path.parent
    )
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def verify_unit_source(unit: FrozenUnit) -> None:
    """Raise unless a unit's sealed evidence copy is still exactly the bytes that were frozen.

    Called before a unit's preserved text is trusted, so text that no longer matches the
    evidence it was rendered from is refused rather than searched.
    """
    if unit.source_sha256 is None:
        return
    if unit.source_path is None:
        raise SealingError(f"{unit.unit_id} has a source hash without a source path")
    path = Path(unit.source_path)
    if not path.is_file():
        raise SealingError(f"sealed evidence is missing: {path}")
    size = path.stat().st_size
    if unit.source_bytes is not None and size != unit.source_bytes:
        raise SealingError(f"sealed evidence size changed: {path}")
    if hash_range(path, 0, size) != unit.source_sha256:
        raise SealingError(f"sealed evidence changed: {path}")
