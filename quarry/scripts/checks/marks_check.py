"""Check the marks of `quarry drive`: recorded frames replayed, constructed streams, real runs.

Usage: `marks_check.py [fixture] [real] [handoff]`, `fixture` by default. `fixture` runs no
model turn. `real` drives one real Claude Code session in a scratch project past the freeze
and the stop mark. `handoff` drives one real run whose first session crosses the hand-off
mark, so a second session continues it. Prints every phase and exits 1 at the first failed
expectation.
"""

from __future__ import annotations

import importlib
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import driver_check
from driver_check import QUARRY, SCRATCH_PARENT, SCRIPTS_DIR, VERDICT, CheckFailed

sys.path.insert(0, str(SCRIPTS_DIR))
driver = importlib.import_module("quarry_lib.driver")
sessions = importlib.import_module("quarry_lib.sessions")
stages = importlib.import_module("quarry_lib.stages")
store = importlib.import_module("quarry_lib.store")
transcripts = importlib.import_module("quarry_lib.transcripts")

FIXTURE = Path(__file__).resolve().parent / "marks_fixture.jsonl"
MODEL = "claude-fable-5-2"
INIT = {"type": "system", "subtype": "init", "model": MODEL}
COMPACT_FRAME = {
    "type": "system",
    "subtype": "compact_boundary",
    "compact_metadata": {"trigger": "auto", "pre_tokens": 93359, "post_tokens": 28516},
}
READ_FILES = 6
READ_LINES = 580
READ_WORDS = (
    "river", "stone", "lamp", "quiet", "orange", "metal", "window", "garden", "paper",
    "thunder", "silver", "basket", "candle", "harbor", "pencil", "meadow", "engine", "cotton",
)
REAL_GOAL = (
    "Run the Bash command `echo DAC=$DISABLE_AUTO_COMPACT` once. Then read the six files "
    "part1.txt to part6.txt in this project in full, in three messages of two Read calls "
    "each: part1 and part2, then part3 and part4, then part5 and part6. The reading is one "
    "item of work already in hand: finish all of it. Then decide what the term Widget means "
    "in this project and record it in CONTEXT.md."
)
PROCESS_QUERY = (
    "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,CreationDate "
    "| ConvertTo-Json -Compress"
)
RUNS = ("fixture", "real", "handoff")
SAID = "QX7-RAMPLE-ZOT"
SAID_BACKWARDS = SAID[::-1]
HANDOFF_FILES = 8
HANDOFF_LINES = 320
HANDOFF_GOAL = (
    "Run the Bash command `echo DAC=$DISABLE_AUTO_COMPACT` once, and in the same reply write "
    f"the string {SAID} backwards, character by character; never write that backwards string "
    f"into any file. Then read the {HANDOFF_FILES} files part1.txt to part{HANDOFF_FILES}.txt "
    "in this project in full, one Read call per message, in order. Each part file is its own "
    "item of work: under a freeze mark, reading on to the next part is work already in hand; "
    "at a hand-off mark, the item in hand is only the part being read, so read no further "
    "part, and name in the handoff document the parts already read. Never read a part file "
    "that a handoff document says was read. When every part is read, decide what the term "
    "Widget means in this project and record it in CONTEXT.md."
)
CONSTRUCTED_GOAL = "Decide what the term Widget means in this project and record it in CONTEXT.md."
TRANSCRIPT_MARKER = "MARKER-ONLY-IN-THE-FIRST-TRANSCRIPT-5d1e"
DOCUMENT_TEXT = "State: Widget is not decided yet. Next: decide it. References: CONTEXT.md."
SESSION_START = re.compile(r"session: start ([0-9a-f-]{36})")


def main(argv: list[str]) -> int:
    """Run the requested checks."""
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    runs = argv or ["fixture"]
    unknown = [run for run in runs if run not in RUNS]
    if unknown:
        print(f"unknown run(s) {unknown}; choose from {list(RUNS)}")
        return 2
    try:
        if "fixture" in runs:
            check_replay()
            check_keys()
            check_compaction()
            check_window()
            check_continuation()
            check_handoff_failure()
        if "real" in runs:
            check_real()
        if "handoff" in runs:
            check_handoff_real()
    except CheckFailed as error:
        print(f"CHECK FAILED: {error}", flush=True)
        return 1
    print(f"ALL CHECKS PASSED: {', '.join(runs)}", flush=True)
    return 0


def context_use(frame: dict) -> int | None:
    """Return the context use the check expects for a main-thread assistant frame."""
    if frame.get("type") != "assistant" or frame.get("parent_tool_use_id") is not None:
        return None
    return sum(frame["message"]["usage"].values())


def check_replay() -> None:
    """Replay the recorded frames through the driver's frame handling and check its marks."""
    print(f"phase: replay {FIXTURE.name}", flush=True)
    lines = FIXTURE.read_text(encoding="utf-8").splitlines()[1:]
    frames = [json.loads(line) for line in lines]
    uses = [context_use(frame) for frame in frames]
    first_freeze = next(i for i, use in enumerate(uses) if use and use >= sessions.FREEZE_MARK)
    first_handoff = next(i for i, use in enumerate(uses) if use and use >= sessions.HANDOFF_MARK)
    first_stop = next(i for i, use in enumerate(uses) if use and use >= sessions.STOP_MARK)
    if not first_freeze < first_handoff < first_stop:
        raise CheckFailed(f"the fixture crosses the marks at {first_freeze}, {first_handoff}, "
                          f"{first_stop}, not one frame after another")
    subagent = [i for i, frame in enumerate(frames) if frame.get("parent_tool_use_id")]
    if not subagent:
        raise CheckFailed("the fixture holds no subagent frame")
    session = sessions.Session(session_id="fixture")
    marks = []
    for index, line in enumerate(lines):
        mark = sessions.take_frame(session, line)
        if mark:
            marks.append((index, mark, session.context))
        if index == subagent[-1]:
            main_use = next(uses[i] for i in range(index, -1, -1) if uses[i] is not None)
            own = sum(frames[index]["message"]["usage"].values())
            if session.context != main_use or own == main_use:
                raise CheckFailed(
                    f"after subagent frame {index} (own use {own}) the context use is "
                    f"{session.context}, expected the main thread's {main_use}"
                )
            print(f"CHECK subagent frames ignored: context {main_use}, not {own}", flush=True)
        if mark == sessions.STOP:
            break
    expected = [
        (first_freeze, sessions.FREEZE, uses[first_freeze]),
        (first_handoff, sessions.HANDOFF, uses[first_handoff]),
        (first_stop, sessions.STOP, uses[first_stop]),
    ]
    if marks != expected:
        raise CheckFailed(f"marks {marks}, expected {expected}")
    print(
        f"CHECK replay: freeze once at frame {first_freeze} ({uses[first_freeze]} tokens), "
        f"hand off once at frame {first_handoff} ({uses[first_handoff]} tokens), "
        f"stop at frame {first_stop} ({uses[first_stop]} tokens)",
        flush=True,
    )


def stream(*frames: dict) -> sessions.Session:
    """Return the session the driver's frame handling makes of `frames`, exit code 0."""
    session = sessions.Session(session_id="constructed")
    for frame in frames:
        sessions.take_frame(session, json.dumps(frame))
    session.returncode = 0
    return session


def result(window: int, is_error: bool = False) -> dict:
    """Return a result frame reporting `window` as the model's context window."""
    return {
        "type": "result",
        "is_error": is_error,
        "result": "done",
        "modelUsage": {MODEL: {"contextWindow": window}},
    }


def check_keys() -> None:
    """Expect output tokens to stay out of the context use: 100,000 in, 50,000 out is no mark."""
    print("phase: constructed frame with output tokens", flush=True)
    usage = {
        "input_tokens": 10,
        "cache_read_input_tokens": 90_000,
        "cache_creation_input_tokens": 9_990,
        "output_tokens": 50_000,
    }
    session = sessions.Session(session_id="constructed")
    frame = {"type": "assistant", "parent_tool_use_id": None, "message": {"usage": usage}}
    mark = sessions.take_frame(session, json.dumps(frame))
    if mark is not None or session.context != 100_000:
        raise CheckFailed(f"output tokens counted: mark {mark}, context {session.context}")
    print("CHECK keys: context 100000, output tokens not counted, no mark", flush=True)


def check_compaction() -> None:
    """Expect a compact_boundary frame to make the stage red, naming pre_tokens."""
    print("phase: constructed stream with and without a compact_boundary frame", flush=True)
    clean = sessions.failure(stream(INIT, result(1_000_000)))
    if clean is not None:
        raise CheckFailed(f"a clean stream failed: {clean}")
    reason = sessions.failure(stream(INIT, COMPACT_FRAME, result(1_000_000)))
    if reason is None or "pre_tokens" not in reason or "93359" not in reason:
        raise CheckFailed(f"a compacted stream gave {reason!r}")
    print(f"CHECK compaction: red, {reason}", flush=True)


def check_window() -> None:
    """Expect a stop mark above 90% of the reported window to fail, and an error frame not."""
    print("phase: constructed streams reporting a small window", flush=True)
    reason = sessions.failure(stream(INIT, result(200_000)))
    if reason is None or str(sessions.STOP_MARK) not in reason or "180000" not in reason:
        raise CheckFailed(f"a 200000 window gave {reason!r}")
    print(f"CHECK window: red, {reason}", flush=True)
    errored = sessions.failure(stream(INIT, result(200_000, is_error=True)))
    if errored is None or "is_error" not in errored or "window" in errored:
        raise CheckFailed(f"an is_error result frame gave {errored!r}")
    print(f"CHECK window: an is_error result is not counted, {errored}", flush=True)


def check_continuation() -> None:
    """Expect the continuation prompt to hold the goal and the document, no first-transcript text.

    A fake first transcript carrying a marker is sealed into a scratch mesh, so recall on the
    goal returns the marker unless the driver leaves that session's unit out.
    """
    print("phase: constructed continuation prompt over a sealed fake first transcript", flush=True)
    scratch = Path(tempfile.mkdtemp(prefix="quarry-handoff-check-", dir=SCRATCH_PARENT))
    try:
        mesh = store.MeshStore(scratch / ".quarry")
        mesh.initialize()
        first = str(uuid.uuid4())
        transcript = scratch / f"{first}.jsonl"
        records = [
            {"type": "user", "message": {"role": "user", "content": CONSTRUCTED_GOAL}},
            {"type": "assistant", "message": {"role": "assistant", "model": MODEL, "content": [
                {"type": "text", "text": f"The term Widget is still open. {TRANSCRIPT_MARKER}"}
            ]}},
        ]
        transcript.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
        if transcripts.seal_transcript(mesh, transcript, transcripts.CLAUDE_PROVIDER) is None:
            raise CheckFailed("the fake first transcript sealed no unit")
        if TRANSCRIPT_MARKER not in driver._recall(mesh, CONSTRUCTED_GOAL, set()):
            raise CheckFailed("recall over the whole mesh lacks the marker, so the check is void")
        recall = driver._recall(mesh, CONSTRUCTED_GOAL, {first})
        document = scratch / f"{first}.md"
        document.write_text(DOCUMENT_TEXT, encoding="utf-8")
        prompt = driver._prompt(
            stages.GRILL, CONSTRUCTED_GOAL, recall, "no atlas hits", handoff=document
        )
        if CONSTRUCTED_GOAL not in prompt or DOCUMENT_TEXT not in prompt:
            raise CheckFailed("the continuation prompt lacks the goal or the handoff document")
        if TRANSCRIPT_MARKER in prompt:
            raise CheckFailed("the continuation prompt holds text of the first transcript")
        print(
            f"CHECK continuation: {len(prompt)} characters, goal and document present, "
            f"first-transcript marker absent (present in unfiltered recall)",
            flush=True,
        )
    finally:
        driver_check.remove(scratch)


def check_handoff_failure() -> None:
    """Expect a hand off without a document, or by the last session, to make the stage red."""
    print("phase: constructed hand offs with and without a document", flush=True)
    scratch = Path(tempfile.mkdtemp(prefix="quarry-handoff-check-", dir=SCRATCH_PARENT))
    try:
        session = sessions.Session(session_id=str(uuid.uuid4()), handed_off=True)
        document = scratch / sessions.handoff_document(session.session_id)
        missing = driver._handoff_failure(scratch, session, 1)
        if missing is None or str(document) not in missing:
            raise CheckFailed(f"a hand off without a document gave {missing!r}")
        print(f"CHECK missing document: red, {missing}", flush=True)
        document.parent.mkdir(parents=True)
        document.write_text(" \n", encoding="utf-8")
        if driver._handoff_failure(scratch, session, 1) is None:
            raise CheckFailed("a hand off with an empty document was not red")
        document.write_text(DOCUMENT_TEXT, encoding="utf-8")
        if (written := driver._handoff_failure(scratch, session, 1)) is not None:
            raise CheckFailed(f"a hand off with its document was red: {written}")
        budget = driver._handoff_failure(scratch, session, driver.MAX_SESSIONS)
        if budget is None or "does not fit the work budget" not in budget:
            raise CheckFailed(f"session {driver.MAX_SESSIONS} handing off gave {budget!r}")
        print(f"CHECK empty document red, written document passes; last session: red, {budget}")
    finally:
        driver_check.remove(scratch)


def processes() -> dict[int, tuple[int, str]]:
    """Return every live process as pid: (parent pid, creation date)."""
    done = subprocess.run(
        ["powershell", "-NoProfile", "-Command", PROCESS_QUERY],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=driver_check.TOOL_TIMEOUT_SECONDS, check=True,
    )
    return {
        row["ProcessId"]: (row["ParentProcessId"], str(row["CreationDate"]))
        for row in json.loads(done.stdout)
    }


def descendants(root: int) -> dict[int, str]:
    """Return the live descendants of `root` as pid: creation date."""
    table = processes()
    found: dict[int, str] = {}
    frontier = [root]
    while frontier:
        parent = frontier.pop()
        for pid, (ppid, created) in table.items():
            if ppid == parent and pid not in found:
                found[pid] = created
                frontier.append(pid)
    return found


def write_reads(scratch: Path, files: int, lines: int) -> None:
    """Write the files a real goal reads, each under the Read tool's page cap."""
    rng = random.Random(4)
    for index in range(1, files + 1):
        rows = (" ".join(rng.choice(READ_WORDS) for _ in range(13)) for _ in range(lines))
        (scratch / f"part{index}.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"phase: wrote part1..part{files}, {lines} lines each", flush=True)


def run_drive(scratch: Path, env: dict[str, str]) -> tuple[int, str, dict[int, str]]:
    """Drive the real goal; return exit code, output and the tree seen at the freeze line."""
    print("phase: quarry drive (real session)", flush=True)
    lines, tree = [], {}
    with subprocess.Popen(
        [sys.executable, str(QUARRY), "drive", "--until", "grill", REAL_GOAL],
        cwd=str(scratch), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
    ) as process:
        for line in process.stdout:
            print(f"  | {line.rstrip()}", flush=True)
            lines.append(line)
            if "mark: freeze" in line and not tree:
                tree = descendants(process.pid)
                print(f"phase: {len(tree)} descendant process(es) at the freeze", flush=True)
        code = process.wait()
    print(f"quarry drive exited {code}", flush=True)
    return code, "".join(lines), tree


def transcript_evidence(session_id: str) -> tuple[bool, bool, bool]:
    """Return whether the transcript shows the freeze delivered, DAC=1, and a compaction."""
    delivered = dac = compacted = False
    path = transcripts.find_claude_transcript(session_id)
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        attachment = record.get("attachment") or {}
        if record.get("type") == "attachment" and "past the freeze mark" in str(
            attachment.get("prompt")
        ):
            delivered = True
        if record.get("subtype") == "compact_boundary":
            compacted = True
        content = (record.get("message") or {}).get("content")
        if record.get("type") == "user" and isinstance(content, list):
            dac = dac or any(
                block.get("type") == "tool_result" and "DAC=1" in json.dumps(block)
                for block in content
            )
    return delivered, dac, compacted


def check_real() -> None:
    """Drive one real session past both marks and check freeze, stop, seal, note and tree."""
    scratch = Path(tempfile.mkdtemp(prefix="quarry-marks-check-", dir=SCRATCH_PARENT))
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    print(f"scratch project: {scratch}", flush=True)
    try:
        driver_check.setup(scratch, env)
        write_reads(scratch, READ_FILES, READ_LINES)
        code, output, tree = run_drive(scratch, env)
        match = VERDICT.search(output)
        if match is None:
            raise CheckFailed("the driver printed no verdict line")
        verdict, issue, session_id = match.groups()
        if output.count("mark: freeze") != 1 or not tree:
            raise CheckFailed(f"freeze lines {output.count('mark: freeze')}, tree {tree}")
        delivered, dac, compacted = transcript_evidence(session_id)
        if not delivered or not dac or compacted or "compaction:" in output:
            raise CheckFailed(f"delivered {delivered}, DAC=1 {dac}, compacted {compacted}")
        print("CHECK freeze: one phase line, delivered mid-session, DAC=1, no compaction")
        stop = f"stop mark {sessions.STOP_MARK}"
        if code == 0 or verdict != "red" or "mark: stop" not in output or stop not in output:
            raise CheckFailed(f"exit {code}, verdict {verdict}, stop reported {stop in output}")
        alive = {pid for pid, (_, created) in processes().items() if tree.get(pid) == created}
        if alive:
            raise CheckFailed(f"process(es) {sorted(alive)} of the session tree still run")
        shown = driver_check.tool(scratch, env, ["bd", "show", issue])
        if session_id not in shown or stop not in shown:
            raise CheckFailed(f"bd show {issue} lacks the stop note for {session_id}")
        mesh = store.MeshStore(scratch / ".quarry")
        sealed = {unit.session_id for unit in mesh.load_units()}
        if session_id not in sealed:
            raise CheckFailed(f"no sealed unit belongs to session {session_id}")
        print(
            f"CHECK stop: exit {code}, verdict red at the {stop}, {len(tree)} process(es) "
            f"gone, note on {issue}, unit sealed for {session_id}",
            flush=True,
        )
    finally:
        driver_check.remove(scratch)


def transcript_records(session_id: str) -> list[dict]:
    """Return the main-thread user and assistant records of a session's transcript."""
    path = transcripts.find_claude_transcript(session_id)
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return [
        record for record in records
        if record.get("type") in ("user", "assistant") and not record.get("isMeta")
        and not record.get("isSidechain")
    ]


def check_handoff_real() -> None:
    """Drive one real run across the hand-off mark and check the hand off end to end."""
    scratch = Path(tempfile.mkdtemp(prefix="quarry-handoff-check-", dir=SCRATCH_PARENT))
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    print(f"scratch project: {scratch}", flush=True)
    try:
        driver_check.setup(scratch, env)
        write_reads(scratch, HANDOFF_FILES, HANDOFF_LINES)
        code, output = driver_check.drive(scratch, env, ["--until", "grill", HANDOFF_GOAL])
        match = VERDICT.search(output)
        if match is None:
            raise CheckFailed("the driver printed no verdict line")
        verdict, issue, last = match.groups()
        sessions = SESSION_START.findall(output)
        print(f"phase: sessions {sessions}, verdict {verdict}, exit {code}", flush=True)
        if output.count("mark: hand off") != 1 or len(set(sessions)) != 2 or last != sessions[1]:
            raise CheckFailed(f"hand-off lines {output.count('mark: hand off')}, "
                              f"sessions {sessions}, last {last}")
        first, second = sessions
        document = sessions.handoff_document(first)
        path = scratch / document
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        if not text.strip():
            raise CheckFailed(f"no handoff document at {scratch / document}")
        print(f"CHECK hand off: one phase line, {document} holds {len(text)} characters")
        sealed = {unit.session_id for unit in store.MeshStore(scratch / ".quarry").load_units()}
        if not {first, second} <= sealed:
            raise CheckFailed(f"sealed sessions {sealed}, expected {first} and {second}")
        shown = driver_check.tool(scratch, env, ["bd", "show", issue])
        notes = shown.count(f"quarry drive, stage {stages.GRILL.name}")
        if notes != 2 or document not in shown:
            raise CheckFailed(f"bd show {issue}: {notes} driver note(s), document named "
                              f"{document in shown}")
        print(f"CHECK record: units sealed for both sessions, {notes} notes on {issue}, "
              f"the first names {document}", flush=True)
        said = any(
            SAID_BACKWARDS in transcripts.message_text(record)
            for record in transcript_records(first) if record["type"] == "assistant"
        )
        prompt = next(
            transcripts.message_text(record)
            for record in transcript_records(second) if record["type"] == "user"
        )
        if not said or SAID_BACKWARDS in prompt or document not in prompt:
            raise CheckFailed(f"said by session 1 {said}, in prompt 2 {SAID_BACKWARDS in prompt}, "
                              f"document in prompt 2 {document in prompt}")
        print(f"CHECK prompt of session 2: {len(prompt)} characters, holds {document}, "
              f"lacks {SAID_BACKWARDS}, which session 1 said", flush=True)
        checks = [line for line in output.splitlines() if "[drive] check: " in line]
        print(f"OBSERVED final verdict: {verdict}; {checks[-1]}", flush=True)
    finally:
        driver_check.remove(scratch)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
