"""Distill rendered session entries into the searchable text a sealed unit preserves."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any

TEXT_SUFFIX = ".md"
TOOL_CALL_PREFIX = "TOOL "
TOOL_RESULT_PREFIX = "TOOL RESULT"
RECALL_TOOL = "Ask_Knowledge"
RECALL_ENVELOPE = "These are the results from Ask_Knowledge:"
RECALL_FOUND_NOTHING = "nothing found"
ADDRESS_LINE = re.compile(r"[A-Za-z0-9_-]{1,64}:\d+(?:-\d+)?")
ROLE_HEADER = re.compile(r"[A-Z][A-Z ]*:\n")
MIN_REPEATED_BLOCK_LINES = 3
MAX_ARGUMENT_CHARS = 120
REPEATED_BLOCK_MARKER = "[repeated block already preserved above]"
REPEATED_RESULT_MARKER = "[identical tool result already preserved above]"


@dataclass(frozen=True)
class FrozenUnit:
    """One immutable sealed segment, searched as preserved text.

    Every unit owns two files: the sealed byte-exact evidence copy in the format it was
    captured in, and the searchable distilled rendering of it. `sha256` covers the
    rendering, `source_sha256` the evidence copy, so either being altered is detectable.

    Args:
        content: the distilled rendering recall greps; citations resolve against it by
            line number.
        source: stable identity of the sealed segment, which distinguishes one window of
            a session from another.
        source_path: the sealed evidence copy the rendering was derived from, which stays
            the evidence of record.
    """

    snapshot_id: str
    unit_id: str
    content: str
    token_count: int
    sha256: str
    source: str
    provider: str
    session_id: str
    text_path: str | None = None
    text_sha256: str | None = None
    model: str = ""
    source_path: str | None = None
    source_sha256: str | None = None
    source_bytes: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-safe persisted form of every field."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FrozenUnit:
        """Restore a unit from its persisted form."""
        return cls(
            snapshot_id=str(data["snapshot_id"]),
            unit_id=str(data["unit_id"]),
            content=str(data["content"]),
            token_count=int(data["token_count"]),
            sha256=str(data["sha256"]),
            source=str(data["source"]),
            provider=str(data.get("provider", "")),
            session_id=str(data.get("session_id", "")),
            text_path=_optional_str(data.get("text_path")),
            text_sha256=_optional_str(data.get("text_sha256")),
            model=str(data.get("model", "")),
            source_path=_optional_str(data.get("source_path")),
            source_sha256=_optional_str(data.get("source_sha256")),
            source_bytes=_optional_int(data.get("source_bytes")),
        )


def estimate_tokens(text: str) -> int:
    """Approximate the token count as whitespace-separated words.

    Reported rather than used to bound anything, since recall greps the text instead of
    loading it whole.
    """
    return len(re.findall(r"\S+", text))


def hash_text(text: str) -> str:
    """Return the sha256 of `text` encoded as UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def join_entries(entries: list[str]) -> str:
    """Join rendered entries into one searchable document."""
    if not entries:
        raise ValueError("transcript distilled to no preserved content")
    return "\n\n".join(entries)


def distill(entries: list[str]) -> list[str]:
    """Reduce rendered session entries to their information, in original order.

    A session transcript repeats itself heavily: instruction blocks re-injected on every
    turn, tool arguments carrying whole file bodies, and identical tool results from
    repeated reads. Recall greps this text and reads the lines it matched, so that
    repetition is not merely bulk, it is noise that matches searches and wastes reads.

    Lossy by design, and safe because it is: the sealed evidence copy keeps every byte, so
    a distilled rendering can be produced again from evidence if these rules change.
    """
    seen_blocks: set[str] = set()
    seen_results: set[str] = set()
    kept = [_distilled(entry, seen_blocks, seen_results) for entry in entries]
    return [entry for entry in kept if entry]


def _distilled(entry: str, seen_blocks: set[str], seen_results: set[str]) -> str:
    """Distil one entry block by block.

    Blocks are routed rather than whole entries because the two shapes differ: a provider
    session makes every tool call its own entry, while a rendered turn may include its
    tool traffic as one.

    A recall result is the exception, taken whole before splitting: it arrives as rendered
    text whose passages are separated by blank lines, which the block splitter would
    otherwise tear into fragments and preserve as ordinary prose.
    """
    text = entry.strip("\n")
    if not text.strip():
        return ""
    recall = _entry_recall(text)
    if recall:
        return recall
    kept: list[str] = []
    for index, block in enumerate(_blocks(text)):
        distilled = _distilled_block(block, index, seen_blocks, seen_results)
        if distilled == REPEATED_BLOCK_MARKER and kept and kept[-1] == REPEATED_BLOCK_MARKER:
            continue
        if distilled:
            kept.append(distilled)
    return "\n\n".join(kept)


def _distilled_block(
    block: str,
    index: int,
    seen_blocks: set[str],
    seen_results: set[str],
) -> str:
    if block.startswith(TOOL_RESULT_PREFIX):
        return _distilled_result(block, seen_results)
    if block.startswith(TOOL_CALL_PREFIX):
        return _distilled_call(block)
    return _distilled_prose(block, index, seen_blocks)


def _distilled_result(text: str, seen: set[str]) -> str:
    """Return the result, or a marker when this exact output was already preserved.

    Keyed on the output itself, so a re-read that returns different content is kept: only
    output the mesh already holds verbatim is replaced.
    """
    if _is_recall_result(text):
        return _distilled_recall(text)
    digest = hash_text(_collapsed(text))
    if digest in seen:
        return REPEATED_RESULT_MARKER
    seen.add(digest)
    return text


def _entry_recall(text: str) -> str:
    """Return the whole entry as the addresses it cited, when the entry is one recall result.

    The tool result may carry the role header its provider wraps every record in, so the
    header is set aside and put back. Without that, a transcript that labels each record
    leaves the recall to the block splitter, which tears its passages apart at the blank
    lines between them and preserves the copied lines as ordinary prose.
    """
    header = None if text.startswith(TOOL_RESULT_PREFIX) else ROLE_HEADER.match(text)
    body = text[header.end() :] if header else text
    if not body.startswith(TOOL_RESULT_PREFIX) or not _is_recall_result(body):
        return ""
    return (header.group() if header else "") + _distilled_recall(body)


def _is_recall_result(text: str) -> bool:
    """Report whether a tool result is the mesh answering, rather than new evidence.

    The envelope must open the result rather than appear anywhere inside it: a file whose
    contents merely quote that wording is a real read, and collapsing it to addresses
    would replace the file with lines it never held.
    """
    header, _, body = text.partition("\n")
    return RECALL_TOOL in header or body.lstrip().startswith(RECALL_ENVELOPE)


def _distilled_recall(text: str) -> str:
    """Return a recall result as the addresses it cited, dropping the lines it copied.

    A recall result is not new evidence. It is a copy of preserved text that already
    exists, unchanged, at the addresses it names, so freezing it duplicates the mesh into
    itself: the copy competes with its own source and dilutes the rarity that made those
    lines findable. The addresses stay because which history a session was shown is part
    of what happened, and they lead to the original rather than to a second copy of it.
    """
    header, _, body = text.partition("\n")
    addresses = _recall_addresses(body)
    return f"{header} {' '.join(addresses) if addresses else RECALL_FOUND_NOTHING}"


def _recall_addresses(body: str) -> list[str]:
    """Return the unit:line addresses a recall reported, from either result shape.

    A recorded result may be JSON; a rendered one heads each passage with its address
    alone.
    """
    try:
        decoded = json.loads(body)
    except json.JSONDecodeError:
        found = [
            line.strip()
            for line in body.splitlines()
            if ADDRESS_LINE.fullmatch(line.strip())
        ]
        return list(dict.fromkeys(found))
    passages = decoded.get("passages", []) if isinstance(decoded, dict) else []
    return list(
        dict.fromkeys(
            str(item["address"])
            for item in passages
            if isinstance(item, dict) and item.get("address")
        )
    )


def _distilled_call(text: str) -> str:
    """Return the call as one line, keeping the arguments that identify what it acted on.

    The call is compressed rather than dropped: a result with no call above it loses which
    file was read or which question was asked, which is usually the part a later question
    is about.
    """
    header, _, body = text.partition("\n")
    arguments = _identifying(body.strip())
    return f"{header} {arguments}".rstrip() if arguments else header


def _identifying(body: str) -> str:
    if not body:
        return ""
    try:
        decoded = json.loads(body)
    except json.JSONDecodeError:
        return _elided(body)
    if not isinstance(decoded, dict):
        return _elided(json.dumps(decoded, ensure_ascii=True))
    return " ".join(f"{key}={_elided(_rendered(value))}" for key, value in decoded.items())


def _rendered(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=True)


def _elided(value: str) -> str:
    flat = " ".join(value.split())
    return flat if len(flat) <= MAX_ARGUMENT_CHARS else f"<{len(flat)} chars>"


def _distilled_prose(block: str, index: int, seen: set[str]) -> str:
    """Return the block, or a marker when this wording is already preserved above.

    Args:
        index: position within its entry. The opening block carries the role header, so it
            is never replaced; an entry whose body is entirely repetition still records
            that the turn happened and who took it.
    """
    key = hash_text(_collapsed(block))
    repeated = key in seen and len(block.splitlines()) >= MIN_REPEATED_BLOCK_LINES
    seen.add(key)
    return REPEATED_BLOCK_MARKER if repeated and index > 0 else block


def _blocks(text: str) -> list[str]:
    return [block.strip("\n") for block in re.split(r"\n\s*\n", text) if block.strip()]


def _collapsed(text: str) -> str:
    return " ".join(text.split())


def _optional_str(value: Any) -> str | None:
    return str(value) if value is not None else None


def _optional_int(value: Any) -> int | None:
    return int(value) if value is not None else None
