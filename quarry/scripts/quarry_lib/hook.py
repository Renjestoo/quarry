"""Dispatch host lifecycle hook events for the quarry plugin."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from quarry_lib import doctor
from quarry_lib.ask import KnowledgeController, render_index
from quarry_lib.audit import audit_flow, audit_scope, audit_stop, audit_stop_graft
from quarry_lib.store import MeshStore
from quarry_lib.transcripts import (
    CLAUDE_PROVIDER,
    CODEX_PROVIDER,
    seal_transcript,
    seal_zcode_session,
    zcode_rollout_path,
)
from webapp import behaviour, flow
from webapp.server import live_endpoint as live_dashboard

AUTO_SEAL_MIN_MESSAGES = 6
HOST_CONTEXT_LIMIT = 10_000
SEPARATOR = "\n\n"
RECALL_NUDGE = (
    "Quarry recall contract: if this reply depends on anything an earlier session "
    "settled, call Ask_Knowledge first and quote what it returns; never browse "
    ".quarry/units or substitute bd memories for recall."
)
ATLAS_NUDGE = (
    "Quarry atlas contract: before exploring code by hand, ask the graft atlas "
    "(graft ask / skeleton / callers); grep and file-walking are the last resort."
)
TRACKER_NUDGE = (
    "Quarry tracker contract: work state lives in bd (bd create, bd update --claim, "
    "bd close --reason), never in TodoWrite, TaskCreate or markdown task lists."
)
REFRESH_HEADER = (
    "Quarry refresh: this session's context was compacted. The sealed-memory index below "
    "lists what survived; use Ask_Knowledge before re-deciding anything."
)
ATLAS_STANZA = (
    "Code atlas: this repo has a graft graph. Ask it before exploring files by hand, "
    "`graft ask \"<task>\"` (ranked nodes), `graft skeleton <file>` (signatures only), "
    "`graft callers <symbol>` / `graft blast` (impact), `graft map` (orientation). "
    "The atlas answers WHERE things are; Ask_Knowledge answers WHAT was said or decided."
)
ORIENT_STANZA = (
    "Quarry: work here survives context loss in four homes, decisions in files, work in bd, "
    "history in a sealed mesh, code in a graft atlas. You are starting without the "
    "conversation that filled them, so reconnoitre before you act, and keep the recon "
    "read-only.\n"
    "Read the open work first (`bd ready`, `bd list --status open`, and `bd show <id> --long` "
    "for anything already claimed), then ask Ask_Knowledge what those issues settled and the "
    "atlas where their code lives. The tracker's own workflow rules come from `bd prime`: "
    "the beads plugin injects them at session start where it is installed, so run it "
    "yourself only when no `# Beads Workflow Context` block is in your context. An empty "
    "tracker view means it was not read, never that there is no work. Creating, "
    "editing, claiming, closing, labelling or linking an issue is not reconnaissance: none of "
    "it happens until you have stated your position, which outranks `bd prime`'s rule about "
    "filing an issue before writing code, right once you know the work and wrong in the "
    "minute when you know least.\n"
    "The full map is the `quarry` skill, and `/quarry:help` prints every skill and command."
)


def handle(event: str, project_root: Path) -> int:
    """Run one hook event, never raising past the host boundary.

    A failed hook must not break the host session, so every failure is reported on stderr
    and swallowed; sealing failures especially must never block a compaction the host is
    about to perform.
    """
    try:
        return _dispatch(event, project_root)
    except Exception as error:
        print(f"quarry hook {event} failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 0


def _dispatch(event: str, project_root: Path) -> int:
    if event == "SessionStart":
        _emit_injection(project_root)
        return 0
    if event == "PreCompact":
        _seal_from_hook(project_root)
        return 0
    if event == "PostCompact":
        _marker_path(project_root).write_text("refresh", encoding="utf-8")
        return 0
    if event == "UserPromptSubmit":
        _auto_seal(project_root)
        nudges = "\n".join(_contract_lines(project_root))
        marker = _marker_path(project_root)
        if marker.is_file():
            marker.unlink(missing_ok=True)
            _emit_injection(project_root, REFRESH_HEADER, nudges)
        elif nudges:
            print(nudges)
        return 0
    if event == "Stop":
        payload = {} if sys.stdin.isatty() else _hook_payload()
        if payload.get("stop_hook_active"):
            return 0
        transcript = _named_transcript(payload)
        decision = audit_stop(project_root, transcript)
        if decision == 0:
            decision = audit_stop_graft(project_root, transcript)
        if decision == 0:
            decision = audit_flow(project_root, transcript)
        if decision == 0:
            decision = audit_scope(project_root, transcript)
        return decision
    print(f"quarry hook: unknown event {event}", file=sys.stderr)
    return 0


def _flow_line(project_root: Path) -> str:
    """Return the pinned lane's contract, empty when the project is free to go anywhere.

    Re-stated every turn on purpose. A pin that is only mentioned when it is set is gone
    the moment the context compacts, which is exactly when an agent drifts back to doing
    whatever it likes; the lane has to arrive with every prompt to survive that.
    """
    current = flow.pinned(project_root)
    if current is None:
        return ""
    return (
        f"Quarry flow lock: this project is pinned to {current['skill']} (lane "
        f"{current['lane']}). Follow that lane's steps and its declared branches only, and "
        "take no other route. Read the skill for the steps if they are not in context. "
        f"Release it with /quarry:flow-cancel. A departure is allowed for one turn only "
        f"when the user writes \"{flow.OVERRIDE_PHRASE}\" in their own message; you writing "
        "that phrase grants nothing."
    )


def _contract_lines(project_root: Path) -> list[str]:
    """Return the per-prompt contract lines for the substrates this repo actually has."""
    lines = []
    pinned = _flow_line(project_root)
    if pinned:
        lines.append(pinned)
    store = MeshStore(project_root / ".quarry")
    if store.units_dir.is_dir() and any(store.units_dir.glob("K*.md")):
        lines.append(RECALL_NUDGE)
    if (project_root / "graft").is_dir():
        lines.append(ATLAS_NUDGE)
    if (project_root / ".beads").is_dir():
        lines.append(TRACKER_NUDGE)
    return lines


def _emit_injection(project_root: Path, header: str = "", trailer: str = "") -> None:
    """Print the sealed index, the substrate stanzas, and what quarry is, for host injection.

    `trailer` is printed last and counted against the same cap, since a host measures one
    hook's stdout whole.

    The orientation stanza goes last and is emitted on every session start rather than only
    after a compaction. Three of the four sources a host reports (startup, clear, compact)
    begin with no conversation in hand, so the distinction buys little, and reading the
    payload to tell them apart would mean reading stdin here: a hook input stream that never
    closes would then hang the session before it began.

    `bd prime` is deliberately not run: the beads plugin's own SessionStart hook injects it
    wherever that plugin is installed, so running it here would inject it twice. It was also
    slow once, a median of 54.5s over seven calls, though re-measured on 2026-11-06 it took a
    median of 0.47s over five.

    The whole injection is kept within HOST_CONTEXT_LIMIT. Claude Code caps a hook's plain
    stdout at 10,000 characters, and over the cap it replaces all of it with a file path and
    a 2,000-character preview the agent is never asked to open. In this repo 10.8k to 12.9k
    character injections arrived as previews ending inside the sealed index, so the
    orientation, atlas, dashboard and behaviour stanzas never reached the agent at all. The
    fixed stanzas are kept whole; the sealed index, then the behaviour ledger, get what is left.
    """
    atlas = ATLAS_STANZA if (project_root / "graft").is_dir() else ""
    board = _dashboard_stanza(project_root)
    harness = _harness_stanza()
    fixed = [part for part in (header, atlas, board, harness, ORIENT_STANZA, trailer) if part]
    budget = HOST_CONTEXT_LIMIT - _host_size(SEPARATOR.join(fixed) + SEPARATOR * 2 + "\n")
    index = _fitted_index(project_root, budget)
    measured = _behaviour_stanza(project_root, budget - _host_size(index))
    parts = [header, index, atlas, board, measured, harness, ORIENT_STANZA, trailer]
    print(SEPARATOR.join(part for part in parts if part))


def _host_size(text: str) -> int:
    """Return text's size as the host may count it: UTF-8 bytes, plus one per CRLF newline."""
    return len(text.encode("utf-8")) + text.count("\n")


def _fitted_index(project_root: Path, budget: int) -> str:
    """Return the sealed-memory index within `budget`, listing the newest windows that fit.

    Older windows left out are counted in the index itself, since Ask_Knowledge searches
    every window whether listed or not. Empty when the mesh holds none or nothing fits.
    """
    entries = KnowledgeController(MeshStore(project_root / ".quarry")).index_entries()
    if not entries:
        return ""
    for omitted in range(len(entries) + 1):
        listed = entries[omitted:]
        if omitted:
            listed = [
                f"({omitted} older windows are not listed here; Ask_Knowledge searches "
                "them too)",
                *listed,
            ]
        rendered = render_index(listed)
        if _host_size(rendered) <= budget:
            return rendered
    return ""


def _behaviour_stanza(project_root: Path, budget: int) -> str:
    """Return the measured-behaviour ledger for injection, empty when nothing is recorded.

    Pushed rather than waited for, because the facts worth carrying are exactly the ones a
    fresh agent does not suspect and so would never think to ask about: nobody asks whether
    a command can take two minutes until it has.

    A fact due for re-measurement is marked rather than hidden. A dated observation is still
    evidence even when it is old, while dropping it silently turns a known trap back into one
    that has to be re-learned from scratch.

    Facts that do not fit `budget` are left off the end and counted, with the command that
    lists them all: past the host's cap the agent would see none of them, not some.
    """
    rows = behaviour.facts(project_root)
    if not rows:
        return ""
    engine = f'"{sys.executable}" "{Path(sys.argv[0]).resolve()}"'
    intro = (
        "Measured behaviour here, each fact with the evidence that established it and the "
        "date it was taken. These are observations, not decisions: decisions live in "
        "CHARTER.md, CONTEXT.md and docs/adr/, and nothing here overrides them. A fact "
        f"marked DUE was measured more than {behaviour.STALE_AFTER_DAYS} days ago, so "
        "confirm it before relying on it."
    )
    facts = [
        f"- {fact['claim']}{' [DUE]' if behaviour.due(fact) else ''}\n"
        f"  measured {fact['measured']}: {fact['evidence']}"
        for fact in rows
    ]
    closing = (
        f"Measured something a later session would not think to ask about? Record it with "
        f"`{engine} behaviour --record \"<claim>\" --evidence \"<what you observed>\"`, and "
        "drop one a re-check disproves with `--drop \"<claim>\"`."
    )
    for shown in range(len(facts), -1, -1):
        lines = [intro, *facts[:shown]]
        if shown < len(facts):
            lines.append(
                f"{len(facts) - shown} more measured fact(s) are not shown here, to keep this "
                f"injection inside the host's context cap; list them all with "
                f"`{engine} behaviour`."
            )
        lines.append(closing)
        text = "\n".join(lines)
        if _host_size(text) <= budget:
            return text
    return ""


def _harness_stanza() -> str:
    """Return the notice naming the harness parts that are not ready, empty when all are.

    Judged by file reads and PATH lookups only, so it costs the session start no process. A
    read that fails is reported on stderr and leaves the notice out rather than the whole
    injection.
    """
    try:
        names = doctor.not_ready()
    except (OSError, ValueError, KeyError) as error:
        print(f"quarry hook: harness parts not checked: {error!r}", file=sys.stderr)
        return ""
    if not names:
        return ""
    return (
        f"Harness parts: {', '.join(names)} not ready on this machine. Tell the user once, "
        "and offer `/quarry:setup`: it proposes each part, the optional ones too, and installs "
        "and configures the ones the user chooses. Install nothing without the user's answer."
    )


def _dashboard_stanza(project_root: Path) -> str:
    """Return the line telling the session where the dashboard is, or how to reach it.

    Never returns empty: a session that is told nothing concludes there is no dashboard,
    and the SessionStart hook races the MCP server that records the endpoint, so silence
    here is indistinguishable from absence exactly on a project's first cold start.
    """
    running = live_dashboard(project_root)
    if running is not None:
        return (
            f"Dashboard: {running['url']} is serving this project's tracker graph, ready "
            "queue, sealed strata and activity, and it can create, claim, close and link "
            "issues. Give the user that address when they ask to see the board."
        )
    engine = f'"{sys.executable}" "{Path(sys.argv[0]).resolve()}"'
    return (
        "Dashboard: this project has a web dashboard showing the tracker graph, board, "
        "roadmap, ready queue, sealed strata and activity, and it can create, claim, close "
        "and link issues. It is not running: it starts on request, not with the MCP server. "
        f"When the user asks to see the board, start it with `{engine} dashboard` in the "
        f"background, then give them the address `{engine} url` prints. Starting it twice "
        "is safe, the second start joins the running board rather than opening a second one."
    )


def _seal_from_hook(project_root: Path) -> None:
    """Seal the transcript named by the host's hook input before compaction discards it."""
    payload = _hook_payload()
    transcript_path = payload.get("transcript_path")
    rollout_path = payload.get("rollout_path")
    raw_path = transcript_path or rollout_path
    if not raw_path:
        print(
            "quarry PreCompact: no transcript path in hook input; seal manually with "
            "`quarry seal` if this session should be preserved",
            file=sys.stderr,
        )
        return
    provider = CODEX_PROVIDER if rollout_path else CLAUDE_PROVIDER
    unit = seal_transcript(MeshStore(project_root / ".quarry"), Path(str(raw_path)), provider)
    if unit is not None:
        print(
            f"quarry sealed {unit.unit_id} from {unit.session_id} "
            f"({unit.source_bytes} evidence bytes, "
            f"{len(unit.content.splitlines())} preserved lines)",
            file=sys.stderr,
        )


def _auto_seal(project_root: Path) -> None:
    """Seal this session's new history on prompt submit, silently.

    Hosts without a compaction event cannot seal "just before compaction", so every
    prompt submit seals once enough new conversation has accumulated, whatever
    compaction takes later was already preserved. The session is located from the
    `CLAUDE_SESSION_ID` environment variable, which prompt-submit-capable hosts inject;
    stdin is never read here because a hook input stream that never closes would block
    every prompt. Only stderr is written: prompt-submit stdout is injected into the
    conversation, and seal chatter is not context.
    """
    session_id = os.environ.get("CLAUDE_SESSION_ID", "")
    if not session_id:
        return
    path = zcode_rollout_path(session_id)
    if not path.is_file():
        return
    seal_zcode_session(MeshStore(project_root / ".quarry"), path, AUTO_SEAL_MIN_MESSAGES)


def _named_transcript(payload: dict[str, Any]) -> Path | None:
    """Return the transcript path the host put in this hook's payload, or None.

    Claude and Codex both name the session's own transcript there, which is the session
    itself rather than an inference about it. Left to guess, the audit picks the newest
    Claude transcript touching the project and so audits a Claude conversation when Codex
    spawned the hook; Codex publishes no session variable to consult instead.

    The Stop branch reads stdin only when something is piped, so `quarry.py hook Stop` run
    by hand at a terminal returns rather than blocking on input that will never arrive. It
    also allows the stop outright when `stop_hook_active` is set: the host sets it when a
    Stop hook already blocked this turn, and a second block on the same evidence (a skill
    call or a sentence already in the transcript) could only repeat until the host's cap.
    """
    named = str(payload.get("transcript_path") or "")
    if not named:
        return None
    path = Path(named)
    return path if path.is_file() else None


def _hook_payload() -> dict[str, Any]:
    """Return the hook input object from stdin, empty when none was piped."""
    try:
        data = json.load(sys.stdin)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _marker_path(project_root: Path) -> Path:
    """Return the one-shot post-compaction refresh marker, unique per project, in temp."""
    digest = hashlib.sha256(str(project_root).encode("utf-8")).hexdigest()[:12]
    return Path(tempfile.gettempdir()) / f"quarry-refresh-{digest}"
