"""Hold one dashboard's own state: its cached snapshot, its liveness, and its health."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from webapp import charter, mesh, tracker

ENDPOINT_FILE = "webapp.json"
SNAPSHOT_TTL_SECONDS = 1.0
IDLE_TIMEOUT_SECONDS = 1800.0


class Dashboard:
    """Hold the project a board serves, cache its snapshot, and track whether it is in use.

    The cache exists because several open tabs poll independently and each snapshot costs
    a bd subprocess call; within the TTL they share one result.

    A board counts as in use for `IDLE_TIMEOUT_SECONDS` after its last request of any kind.
    Requests are the signal rather than open event streams, because an abandoned stream is
    indistinguishable from a watched one until a write to it happens to fail, which a
    half-closed socket may never cause; an open page polls regardless, so real use always
    shows up as traffic. Disuse is the only honest signal available, since the process that
    started a board is normally gone long before the board should be.

    Two locks, deliberately. `_lock` guards the snapshot cache and is held for as long as a
    build takes, which is a bd call; `_meter` guards the liveness and health counters,
    which every request touches. Sharing one lock puts a bd call in front of every request,
    including the probe that decides whether this board is alive at all.
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.endpoint: dict[str, Any] = {}
        self.adopted = False
        self.server: ThreadingHTTPServer | None = None
        self.stopped = threading.Event()
        self._lock = threading.Lock()
        self._cached: dict[str, Any] | None = None
        self._cached_at = 0.0
        self._etag = ""
        self._meter = threading.Lock()
        self._last_seen = time.monotonic()
        self._started = time.monotonic()
        self._served = 0
        self._failed = 0
        self._spent = 0.0
        self._slowest = 0.0
        self._reached_tracker: bool | None = None

    def snapshot(self, force: bool = False) -> tuple[dict[str, Any], str]:
        """Return the current dashboard state and its ETag, rebuilding when stale.

        The ETag covers the content and deliberately not `generated_at`, which is when the
        data was gathered rather than part of it. Including it made the hash differ on every
        rebuild, so a client's conditional request never matched, the 304 path never fired,
        and the page ran a full redraw on a timer whether or not any work had changed.
        """
        with self._lock:
            fresh = time.monotonic() - self._cached_at
            if not force and self._cached is not None and fresh < SNAPSHOT_TTL_SECONDS:
                return self._cached, self._etag
            try:
                payload = self._build()
            except Exception:
                self._note_tracker(reached=False)
                raise
            else:
                self._note_tracker(reached=True)
            content = {key: value for key, value in payload.items() if key != "generated_at"}
            body = json.dumps(content, sort_keys=True).encode("utf-8")
            self._cached = payload
            self._etag = hashlib.sha256(body).hexdigest()[:32]
            self._cached_at = time.monotonic()
            return self._cached, self._etag

    def invalidate(self) -> None:
        """Drop the cached snapshot so the next poll reflects a change just made."""
        with self._lock:
            self._cached_at = 0.0

    def note_request(self) -> None:
        """Record that a client just asked for something, which restarts the idle clock."""
        with self._meter:
            self._last_seen = time.monotonic()

    def note_served(self, seconds: float) -> None:
        """Record one finished request and how long it took."""
        with self._meter:
            self._served += 1
            self._spent += seconds
            self._slowest = max(self._slowest, seconds)

    def note_failure(self) -> None:
        """Record one request answered with an error rather than a result."""
        with self._meter:
            self._failed += 1

    def reached_tracker(self) -> bool | None:
        """Report whether this board's last snapshot reached bd; None before it has tried.

        None and True are both adoptable: a board that has not been asked for anything yet has
        proved nothing against itself. Only False, an attempt that actually failed, marks a
        board as one another process should replace rather than join.
        """
        with self._meter:
            return self._reached_tracker

    def _note_tracker(self, *, reached: bool) -> None:
        """Record the outcome of one snapshot build.

        Recorded around the whole build rather than around the bd call alone, and on any
        exception rather than on tracker errors only, because the question this answers is
        whether the board can serve a snapshot at all. A board that cannot, for any reason, is
        one a second process should not adopt, and the specific cause belongs in the error the
        page already shows.
        """
        with self._meter:
            self._reached_tracker = reached

    def health(self) -> dict[str, Any]:
        """Return what this board can say about its own running, in seconds and milliseconds.

        Event streams are excluded from the timings by the caller: one is held open for as
        long as a tab watches the board, so counting it would report the length of a visit as
        the cost of a request. Request times are expected from `perf_counter`, since
        `monotonic` is granular to about 15ms on Windows and would report every fast request
        as having taken no time at all.
        """
        with self._meter:
            served, failed = self._served, self._failed
            spent, slowest = self._spent, self._slowest
        return {
            "served": served,
            "failed": failed,
            "uptime_seconds": round(time.monotonic() - self._started, 1),
            "mean_ms": round(spent / served * 1000, 1) if served else 0.0,
            "slowest_ms": round(slowest * 1000, 1),
        }

    def idle(self) -> bool:
        """Report that nothing has asked this board for anything in `IDLE_TIMEOUT_SECONDS`."""
        with self._meter:
            return time.monotonic() - self._last_seen > IDLE_TIMEOUT_SECONDS

    def close(self) -> None:
        """Stop serving and withdraw the endpoint record, so nothing points at a dead board."""
        self.stopped.set()
        server, self.server = self.server, None
        if server is not None:
            server.shutdown()
            server.server_close()
        withdraw(self.project_root, self.endpoint)

    def _build(self) -> dict[str, Any]:
        graph = tracker.snapshot(self.project_root)
        return {
            "project": self.project_root.name,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "nodes": graph["nodes"],
            "edges": graph["edges"],
            "counts": graph["counts"],
            "statuses": graph["statuses"],
            "charter": charter.charter(self.project_root),
            "activity": tracker.activity(graph["nodes"]),
            "timing": tracker.timing(graph["nodes"]),
            "mesh": mesh.strata(self.project_root),
        }


def withdraw(project_root: Path, endpoint_record: dict[str, Any]) -> None:
    """Delete the endpoint record, but only while it still describes this process."""
    path = project_root / ".quarry" / ENDPOINT_FILE
    try:
        recorded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if isinstance(recorded, dict) and recorded.get("pid") == endpoint_record.get("pid"):
        path.unlink(missing_ok=True)
