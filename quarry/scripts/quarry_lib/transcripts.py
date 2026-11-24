"""Read Claude and Codex session transcripts, render sealable entries, and seal them."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from quarry_lib.freeze import (
    FrozenUnit,
    distill,
    estimate_tokens,
    hash_text,
    join_entries,
)
from quarry_lib.sealing import (
    hash_range,
    line_complete_end,
    mesh_lock,
    write_segment,
    write_text_once,
)
from quarry_lib.store import EVIDENCE_SUFFIX, MeshStore

CLAUDE_PROVIDER = "claude"
CODEX_PROVIDER = "codex"
ZCODE_PROVIDER = "zcode"
PROVIDERS = (CLAUDE_PROVIDER, CODEX_PROVIDER, ZCODE_PROVIDER)
ZCODE_ROLLOUT_PREFIX = "model-io-sess_"
ZCODE_ROLLOUT_SUFFIX = ".jsonl"
HOST_SESSION_ENV = "CLAUDE_CODE_SESSION_ID"
SUBAGENT_PREFIX = "agent-"
TAIL_SCAN_LIMIT_BYTES = 64 * 1024 * 1024


class TranscriptError(RuntimeError):
    """Report a transcript location, parse, or sealing failure."""


def claude_root() -> Path:
    """Return the transcript directory of the Claude CLI this process drives.

    Honours CLAUDE_CONFIG_DIR, so a harness driving an isolated provider finds the
    sessions it spawned. Use `host_claude_root` instead to find the transcript of the
    session doing the driving.
    """
    configured = os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(configured).expanduser() if configured else Path.home() / ".claude"
    return (base / "projects").resolve()


def host_claude_root() -> Path:
    """Return where the host Claude Code session writes, ignoring CLAUDE_CONFIG_DIR.

    That variable isolates a driven provider CLI and must not redirect the search for the
    transcript of the session doing the sealing: when it did, auto-location silently sealed
    an unrelated driven session into this project's mesh instead of failing.
    """
    return (Path.home() / ".claude" / "projects").resolve()


def host_claude_transcript(session_id: str, project_root: Path) -> Path | None:
    """Return this project's host transcript for `session_id`, or None if it is not there.

    Scoped to the project's own store directory rather than searched globally, so an exact
    id can never pull a session filed under a different project into this mesh.
    """
    path = host_claude_root() / mangled_project_dir(project_root) / f"{session_id}.jsonl"
    return path if path.is_file() else None


def codex_root() -> Path:
    """Return the directory the Codex CLI writes session rollouts into."""
    configured = os.environ.get("CODEX_HOME")
    base = Path(configured).expanduser() if configured else Path.home() / ".codex"
    return (base / "sessions").resolve()


def find_claude_transcript(session_id: str) -> Path:
    """Return the one Claude transcript belonging to `session_id`."""
    matches = list(claude_root().rglob(f"{session_id}.jsonl"))
    if len(matches) != 1:
        raise TranscriptError(
            f"expected one Claude transcript for {session_id}, found {len(matches)}"
        )
    return matches[0]


def record_spans(
    path: Path,
    start: int,
    end: int,
    provider: str,
) -> Iterator[tuple[dict[str, Any], int, int]]:
    """Yield each main-thread record within bytes `[start, end)` with its byte range.

    Claude transcripts mark subagent sidechains with `isSidechain`; those turns belong to
    a different conversation, so they are skipped rather than sealed as this session's
    words.

    A line `decode` cannot read is skipped, which is why decodability is tested before the
    record is asked anything. Tested after, the sidechain check reached `None.get` and every
    caller of this function raised on a single blank or truncated line; because the hook
    swallows exceptions to keep the host alive, a PreCompact seal then failed to stderr and
    lost the window it existed to preserve.
    """
    offset = 0
    with path.open("rb") as handle:
        for raw in handle:
            record_end = offset + len(raw)
            if record_end <= start:
                offset = record_end
                continue
            if record_end > end:
                return
            record = decode(raw)
            sealable = record is not None and (
                provider != CLAUDE_PROVIDER or not record.get("isSidechain")
            )
            if sealable:
                yield record, offset, record_end
            offset = record_end


def decode(raw: bytes) -> dict[str, Any] | None:
    """Decode one transcript line, or None when it is not a JSON object."""
    line = raw.decode("utf-8", "replace").strip()
    if not line:
        return None
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def claude_entries(path: Path, start: int, end: int) -> list[str]:
    """Return the preserved entries rendered from one Claude transcript byte range."""
    texts: list[str] = []
    for record, _start, _end in record_spans(path, start, end, CLAUDE_PROVIDER):
        kind = record.get("type")
        if kind not in {"user", "assistant"} or record.get("isMeta"):
            continue
        thinking = message_thinking(record)
        if thinking:
            texts.append(f"ASSISTANT REASONING:\n{thinking}")
        text = message_text(record)
        if text:
            texts.append(f"{str(kind).upper()}:\n{text}")
    return texts


def codex_entries(path: Path, start: int, end: int) -> list[str]:
    """Return the preserved entries rendered from one Codex rollout byte range."""
    texts: list[str] = []
    for record, _start, _end in record_spans(path, start, end, CODEX_PROVIDER):
        outer = record.get("type")
        payload = record.get("payload") or {}
        if outer == "event_msg" and payload.get("type") in {"user_message", "agent_message"}:
            role = "USER" if payload["type"] == "user_message" else "ASSISTANT"
            texts.append(f"{role}:\n{payload.get('message', '')}")
        elif outer == "response_item":
            reasoning = _reasoning_text(payload) if payload.get("type") == "reasoning" else ""
            rendered = f"ASSISTANT REASONING:\n{reasoning}" if reasoning else _tool_record(payload)
            if rendered:
                texts.append(rendered)
    return texts


def render_entries(path: Path, provider: str, start: int, end: int) -> list[str]:
    """Return the preserved entries for one provider's transcript byte range."""
    if provider == CLAUDE_PROVIDER:
        return claude_entries(path, start, end)
    if provider == CODEX_PROVIDER:
        return codex_entries(path, start, end)
    raise TranscriptError(f"unknown transcript provider: {provider}")


def last_boundary_end(path: Path, provider: str) -> int:
    """Return the end offset of the newest compaction boundary record, zero when none.

    Records a host compaction has already superseded are never re-sealed: compaction is
    the host summarizing what the mesh already holds verbatim.
    """
    boundary = 0
    for record, _start, record_end in record_spans(path, 0, line_complete_end(path), provider):
        if provider == CLAUDE_PROVIDER:
            if record.get("type") == "system" and record.get("subtype") == "compact_boundary":
                boundary = record_end
        elif (
            record.get("type") == "compacted"
            or (record.get("payload") or {}).get("type") == "context_compacted"
        ):
            boundary = record_end
    return boundary


def session_model(path: Path, provider: str) -> str:
    """Return the model the sealed session ran under, when the transcript records one."""
    model = ""
    for record, _start, _end in record_spans(path, 0, line_complete_end(path), provider):
        if provider == CLAUDE_PROVIDER:
            if record.get("type") == "assistant":
                model = str((record.get("message") or {}).get("model") or model)
        elif record.get("type") == "turn_context":
            model = str((record.get("payload") or {}).get("model") or model)
    return model


def seal_transcript(store: MeshStore, path: Path, provider: str) -> FrozenUnit | None:
    """Seal the unsealed tail of one transcript into `store`; return the new unit or None.

    Sealing is incremental and idempotent: everything already sealed, and everything a
    host compaction has superseded, stays sealed, and only the records after that point
    are rendered. A tail holding no new preserved content advances the seal offset
    without creating a unit.

    Held under the mesh lock from reading the seal offset through recording the unit,
    because those steps are one read-modify-write over shared state: two agents sealing the
    same project at once otherwise lose a seal and can leave a unit whose metadata names one
    session while its evidence holds another.
    """
    with mesh_lock(store.root):
        end = line_complete_end(path)
        start = max(store.progress(str(path)), last_boundary_end(path, provider))
        if end <= start:
            return None
        entries = render_entries(path, provider, start, end)
        distilled = [entry for entry in distill(entries) if entry]
        session_id = path.stem
        if not distilled:
            store.set_progress(str(path), "", end)
            return None
        content = join_entries(distilled)
        snapshot_id = store.next_snapshot_id()
        sealed_path = store.units_dir / f"{snapshot_id}{EVIDENCE_SUFFIX}"
        write_segment(path, sealed_path, start, end)
        unit = FrozenUnit(
            snapshot_id=snapshot_id,
            unit_id=snapshot_id,
            content=content,
            token_count=estimate_tokens(content),
            sha256=hash_text(content),
            source=f"{provider}:{session_id}:{start}-{end}",
            provider=provider,
            session_id=session_id,
            model=session_model(path, provider),
            source_path=str(sealed_path),
            source_sha256=hash_range(sealed_path, 0, end - start),
            source_bytes=end - start,
        )
        stored = store.save_frozen_unit(unit)
        store.set_progress(str(path), stored.unit_id, end)
        return stored


def zcode_rollout_path(session_id: str) -> Path:
    """Return the model-I/O rollout file one ZCode session writes."""
    name = f"{ZCODE_ROLLOUT_PREFIX}{session_id}{ZCODE_ROLLOUT_SUFFIX}"
    return Path.home() / ".zcode" / "cli" / "rollout" / name


def _newest(pattern_root: Path, glob: str) -> Path | None:
    """Return the most recently modified file matching `glob` under `pattern_root`."""
    candidates = [p for p in pattern_root.rglob(glob) if p.is_file()]
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def mangled_project_dir(project_root: Path) -> str:
    """Return the store directory name a host derives from a project path.

    Claude Code encodes `E:\\x\\y` as `E--x-y`: every character outside
    `[A-Za-z0-9._-]` becomes a dash.
    """
    return "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in str(project_root))


def newest_claude_transcript(project_root: Path) -> Path | None:
    """Return the newest non-subagent Claude transcript in this project's host store.

    A guess by modification time, and only the fallback for when the session id is not in
    the environment: prefer `host_claude_transcript`. Subagent transcripts share the
    directory and are excluded, because one finishing last would otherwise outrank the
    session and be sealed in its place. Concurrent sessions on the same project remain
    indistinguishable here, which is the reason the id is preferred.

    Other projects' stores are never consulted: sealing across projects would pollute this
    mesh with unrelated history, so absence here means no Claude session, not a fallback.
    """
    scoped = host_claude_root() / mangled_project_dir(project_root)
    candidates = [
        path for path in scoped.rglob("*.jsonl")
        if path.is_file() and not path.name.startswith(SUBAGENT_PREFIX)
    ]
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


def newest_codex_rollout(project_root: Path) -> Path | None:
    """Return the newest Codex rollout whose recorded cwd is this project.

    Rollouts live in one shared store, so the file's session metadata is read to
    match the project path; the newest matching rollout is the current session.
    """
    sessions = Path.home() / ".codex" / "sessions"
    if not sessions.is_dir():
        return None
    target = str(project_root).replace("\\", "/").casefold()
    for path in sorted(sessions.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with path.open("rb") as handle:
                head = b"".join(handle.readline() for _ in range(10))
        except OSError:
            continue
        for marker in (b'"cwd":', b'"cwd": '):
            index = head.find(marker)
            if index == -1:
                continue
            start = index + len(marker)
            snippet = head[start : start + 400].decode("utf-8", "replace")
            recorded = snippet.split('"', 1)[0].replace("\\\\", "/").casefold()
            if recorded.startswith(target.rstrip("/")):
                return path
    return None


def newest_zcode_rollout() -> Path | None:
    """Return the newest ZCode model-I/O rollout file."""
    return _newest(
        Path.home() / ".zcode" / "cli" / "rollout", f"{ZCODE_ROLLOUT_PREFIX}*{ZCODE_ROLLOUT_SUFFIX}"
    )


def seal_auto(store: MeshStore, project_root: Path) -> tuple[FrozenUnit | None, str]:
    """Seal the current session into `store`, locating its transcript by host order.

    Exact ids first, guesses last. The ZCode env id when present, then Claude Code's own
    CLAUDE_CODE_SESSION_ID, which names this session exactly and so is immune to a subagent
    or a second window writing more recently. Only then the newest transcript in this
    project's store, and finally the newest Codex rollout whose recorded cwd is this
    project. Sealing never crosses projects silently: if no host has a session for
    this project, nothing is sealed and the note says why; an explicit path argument
    is the deliberate way to preserve a foreign session file.
    """
    session_id = os.environ.get("CLAUDE_SESSION_ID", "")
    if session_id:
        path = zcode_rollout_path(session_id)
        if path.is_file():
            return seal_zcode_session(store, path), f"zcode session {session_id} (env id)"
    host_id = os.environ.get(HOST_SESSION_ENV, "")
    if host_id:
        exact = host_claude_transcript(host_id, project_root)
        if exact is not None:
            return (seal_transcript(store, exact, CLAUDE_PROVIDER),
                    f"claude session {host_id} (env id)")
    transcript = newest_claude_transcript(project_root)
    if transcript is not None:
        return seal_transcript(store, transcript, CLAUDE_PROVIDER), f"claude {transcript}"
    rollout = newest_codex_rollout(project_root)
    if rollout is not None:
        return seal_transcript(store, rollout, CODEX_PROVIDER), f"codex {rollout}"
    return None, "no session transcript found for this project on any host (pass a path to force)"


def zcode_session_id(path: Path) -> str:
    """Return the session id a ZCode rollout filename carries."""
    return path.stem.removeprefix(ZCODE_ROLLOUT_PREFIX)


def last_main_record(path: Path) -> dict[str, Any] | None:
    """Return the newest complete main-turn record in a ZCode rollout.

    Rollouts interleave metadata calls (title generation and the like) with
    conversation turns, and every turn record replays the whole conversation as a
    snapshot, so only the newest main record is read, from the file tail, never the
    whole file, which can grow to hundreds of megabytes. A main turn announces itself
    by `querySource` "main_turn" in current formats or `model.role` "main" in older
    ones; both are accepted because a single long rollout can span the change.
    """
    size = path.stat().st_size
    window_start = max(0, size - TAIL_SCAN_LIMIT_BYTES)
    with path.open("rb") as handle:
        handle.seek(window_start)
        tail = handle.read()
    for line in reversed(tail.splitlines()):
        if not line.strip():
            continue
        record = decode(line + b"\n")
        if record is None:
            continue
        model = record.get("model")
        by_role = isinstance(model, dict) and model.get("role") == "main"
        by_source = record.get("querySource") == "main_turn"
        if (by_role or by_source) and isinstance(
            ((record.get("request") or {}).get("body") or {}).get("messages"), list
        ):
            return record
    return None


def seal_zcode_session(store: MeshStore, path: Path, min_messages: int = 1) -> FrozenUnit | None:
    """Seal the unsealed conversation messages of one ZCode rollout into `store`.

    ZCode rollouts are snapshot logs: each main record's `request.body.messages` holds
    the whole conversation again, so seal progress counts messages rendered, and each
    seal renders only `messages[sealed:]`: a byte-delta approach would duplicate every
    prior unit. The evidence copy is the sealed message array re-serialized as JSON,
    hashed and write-once, because byte-exact ranges of a snapshot format do not exist.

    Held under the mesh lock for the same reason `seal_transcript` is: choosing the unit id,
    writing the evidence, and recording the unit are one read-modify-write over shared state.

    Args:
        min_messages: fewest new messages a seal requires; below it nothing is sealed.
    """
    record = last_main_record(path)
    if record is None:
        return None
    body = ((record.get("request") or {}).get("body") or {})
    messages = body.get("messages")
    if not isinstance(messages, list):
        return None
    with mesh_lock(store.root):
        source_key = str(path)
        sealed = store.progress_messages(source_key)
        fresh = [m for m in messages[sealed:] if isinstance(m, dict)]
        if len(fresh) < min_messages:
            return None
        entries = _zcode_entries(fresh)
        distilled = [entry for entry in distill(entries) if entry]
        session_id = zcode_session_id(path)
        if not distilled:
            store.set_progress_messages(source_key, "", len(messages))
            return None
        content = join_entries(distilled)
        snapshot_id = store.next_snapshot_id()
        sealed_path = store.units_dir / f"{snapshot_id}{EVIDENCE_SUFFIX}"
        written = json.dumps(fresh, indent=2, ensure_ascii=False) + "\n"
        write_text_once(sealed_path, written)
        model_info = record.get("model") or {}
        unit = FrozenUnit(
            snapshot_id=snapshot_id,
            unit_id=snapshot_id,
            content=content,
            token_count=estimate_tokens(content),
            sha256=hash_text(content),
            source=f"zcode:{session_id}:{sealed}-{len(messages)}",
            provider=ZCODE_PROVIDER,
            session_id=session_id,
            model=str(model_info.get("modelId", "")),
            source_path=str(sealed_path),
            source_sha256=hash_text(written),
            source_bytes=len(written.encode("utf-8")),
        )
        stored = store.save_frozen_unit(unit)
        store.set_progress_messages(source_key, stored.unit_id, len(messages))
        return stored


def _zcode_entries(messages: list[dict[str, Any]]) -> list[str]:
    """Return the preserved entries rendered from ZCode conversation messages.

    The messages arrive in the provider request format; the same content block shapes
    the Claude record renderer reads, so each is wrapped as a record and rendered
    through it under its role header.
    """
    texts: list[str] = []
    for message in messages:
        kind = str(message.get("role", ""))
        wrapped = {"message": message}
        thinking = message_thinking(wrapped)
        if thinking:
            texts.append(f"ASSISTANT REASONING:\n{thinking}")
        text = message_text(wrapped)
        if text:
            texts.append(f"{kind.upper()}:\n{text}")
    return texts


def message_text(record: dict[str, Any]) -> str:
    """Return the readable text of one record, including its tool traffic."""
    content = (record.get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            parts.append(str(block.get("text", "")))
        elif block.get("type") == "tool_use":
            parts.append(f"TOOL {block.get('name')}:\n{json.dumps(block.get('input'))}")
        elif block.get("type") == "tool_result":
            parts.append(f"TOOL RESULT:\n{result_text(block.get('content'))}")
    return "\n\n".join(part for part in parts if part)


def message_thinking(record: dict[str, Any]) -> str:
    """Return the reasoning text of one record, empty when it carries none."""
    content = (record.get("message") or {}).get("content")
    if not isinstance(content, list):
        return ""
    return "\n\n".join(
        str(block.get("thinking", ""))
        for block in content
        if isinstance(block, dict) and block.get("type") == "thinking" and block.get("thinking")
    )


def result_text(content: Any) -> str:
    """Return a tool result as readable text, whatever shape it arrived in."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            str(item.get("text", "")) if isinstance(item, dict) else str(item) for item in content
        )
    return json.dumps(content, ensure_ascii=True)


def _tool_record(payload: dict[str, Any]) -> str | None:
    kind = payload.get("type")
    if kind in {"function_call", "custom_tool_call"}:
        name = payload.get("name") or payload.get("tool_name") or "tool"
        arguments = payload.get("arguments") or payload.get("input") or ""
        return f"TOOL {name}:\n{arguments}"
    if kind in {"function_call_output", "custom_tool_call_output"}:
        output = payload.get("output") or payload.get("content") or ""
        return f"TOOL RESULT:\n{output}"
    return None


def _reasoning_text(payload: dict[str, Any]) -> str:
    summary = payload.get("summary")
    if isinstance(summary, list):
        parts = [
            str(item.get("text", ""))
            for item in summary
            if isinstance(item, dict) and item.get("text")
        ]
        if parts:
            return "\n\n".join(parts)
    text = payload.get("text")
    return text if isinstance(text, str) else ""
