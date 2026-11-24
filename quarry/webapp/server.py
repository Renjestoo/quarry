"""Serve the quarry dashboard and its API on loopback, started with the MCP server."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from webapp import charter, coordination, guide, mesh, settings, tracker
from webapp.board import ENDPOINT_FILE, Dashboard
from webapp.tracker import TrackerError, TrackerTimeout

HOST = "127.0.0.1"
PREFERRED_PORT = 7777
PORT_SCAN = 24
STATIC_DIR = Path(__file__).resolve().parent / "static"
PROBE_TIMEOUT_SECONDS = 0.4
POLL_MS = 30000
WATCH_INTERVAL_SECONDS = 0.75
KEEPALIVE_SECONDS = 15.0
IDLE_CHECK_SECONDS = 30.0
MAX_BODY_BYTES = 64 * 1024
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".json": "application/json; charset=utf-8",
    ".woff2": "font/woff2",
}


def start(project_root: Path) -> Dashboard | None:
    """Start the dashboard on a background thread and record where it is listening.

    Adopts a dashboard already serving this project instead of starting a rival one, so
    every session in a project shares one board; an adopted board reports `adopted` and
    carries the other process's endpoint. Republishes the endpoint either way, so adopting
    also repairs a record that was lost while the board kept running and `url` can find it
    again. Announcing the address is left to the caller, which knows whether stdout is free
    or reserved for a protocol.

    A board that reports it could not reach bd is replaced rather than adopted. Adoption
    otherwise decides on identity alone, so a board whose tracker access is broken looks
    exactly like a healthy one, and starting again joins it instead of curing it; the board
    then serves an empty graph and zero counts, which reads as an empty project rather than
    as a fault. The probe stays cheap because the board reports a fact it already knows from
    its last snapshot, and no bd call enters the probe path.

    A board this process owns stops itself once it falls idle, because it normally outlives
    the session that asked for it and nothing else would ever end it. Returns None when no
    port could be bound, and never raises.
    """
    board = Dashboard(project_root)
    adopted = _serving(project_root)
    if adopted is not None and adopted.get("reached_tracker") is False:
        print(
            f"quarry dashboard: replacing the board on {adopted.get('url')}, which is serving "
            "this project but cannot reach bd",
            file=sys.stderr,
        )
        stop(project_root)
        adopted = None
    if adopted is not None:
        board.endpoint = adopted
        board.adopted = True
        _publish(project_root, adopted)
        return board
    try:
        server = _bind(board)
    except OSError as error:
        print(f"quarry dashboard did not start: {error}", file=sys.stderr)
        return None
    board.server = server
    board.endpoint = {
        "url": f"http://{HOST}:{server.server_port}",
        "host": HOST,
        "port": server.server_port,
        "pid": os.getpid(),
        "project": str(project_root),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    threading.Thread(target=server.serve_forever, name="quarry-dashboard", daemon=True).start()
    threading.Thread(
        target=_reap, args=(board,), name="quarry-dashboard-reaper", daemon=True
    ).start()
    _publish(project_root, board.endpoint)
    return board


def stop(project_root: Path) -> str:
    """Ask the dashboard serving this project to shut down; return its address, empty if none.

    Finds the board the same way starting one does, by record and then by sweeping the
    ports, so a board whose record was lost is still reachable; that orphan is the one most
    worth stopping. Probes before asking, so a stale record, or another project's board
    holding the port this project's record names, is never told to stop.
    """
    running = _serving(project_root)
    if running is None:
        return ""
    asked = Request(
        f"{running['url']}/api/shutdown",
        data=b"{}",
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(asked, timeout=PROBE_TIMEOUT_SECONDS):
            return str(running["url"])
    except (URLError, OSError):
        return ""


def _reap(board: Dashboard) -> None:
    """Stop a board that has gone idle, so one nobody is watching does not linger forever."""
    while not board.stopped.wait(IDLE_CHECK_SECONDS):
        if board.idle():
            board.stopped.set()


def endpoint(project_root: Path) -> dict[str, Any] | None:
    """Return the recorded endpoint of a dashboard running for this project, if any."""
    path = project_root / ".quarry" / ENDPOINT_FILE
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return record if isinstance(record, dict) and record.get("url") else None


def watched(project_root: Path) -> list[Path]:
    """Return the few files whose mtime moves when this project's work or memory changes.

    Deliberately a short list rather than a directory walk: the tracker's dolt store alone
    holds dozens of files, and the watch runs on every connected browser.

    The dolt manifest is deliberately not among them. Every bd call rewrites it, reads
    included (measured: `bd show`, `bd list` and `bd dep list` each moved it, every time),
    so a board that watched it re-polled on its own snapshot: the snapshot's bd calls moved
    the manifest, the watch reported a change, every open tab polled again, and the loop
    kept bd busy for as long as a tab stayed open. A write is seen through the export files
    bd rewrites with it, and the page's timer poll covers a project whose export is off.
    """
    beads = project_root / ".beads"
    paths = [beads / "issues.jsonl", beads / "export-state.json"]
    paths.append(project_root / ".quarry" / "mesh.json")
    paths.append(project_root / charter.CHARTER_FILE)
    paths.append(project_root / settings.MODE_FILE)
    return paths


def fingerprint(project_root: Path) -> str:
    """Return a stamp that changes when any watched file changes, cheap enough to poll."""
    stamps = []
    for path in watched(project_root):
        try:
            stamps.append(f"{path.name}:{path.stat().st_mtime_ns}")
        except OSError:
            continue
    return "|".join(stamps)


def live_endpoint(project_root: Path) -> dict[str, Any] | None:
    """Return the endpoint of a dashboard currently serving this project, else None.

    Probes the recorded address rather than trusting the record: `webapp.json` outlives the
    process that wrote it, and another project's dashboard may hold that port now.
    """
    record = endpoint(project_root)
    if record is None:
        return None
    live = _identify(record.get("port"))
    return live if live and live.get("project") == str(project_root) else None


def _serving(project_root: Path) -> dict[str, Any] | None:
    """Return the dashboard already serving this project, sweeping the ports one could hold.

    The record alone is not enough to find a board: it can be missing or stale while a
    server for this project is up. Starting one then leaves two boards on the same project,
    and stopping one leaves an orphan that no record points at, which is the state this
    sweep exists to reach.

    The ports are probed together rather than one after another. A port nothing listens on
    is not necessarily refused: measured here, every free port cost the full probe timeout
    instead of answering at once, which made a serial sweep of `PORT_SCAN` ports take that
    timeout multiplied by the port count, and put roughly ten seconds in front of every
    start and every stop. Probing concurrently costs one timeout in total and decides
    exactly what the serial sweep decided, so no board can be missed to buy the speed.
    """
    found = live_endpoint(project_root)
    if found is not None:
        return found
    ports = [PREFERRED_PORT + offset for offset in range(PORT_SCAN)]
    with ThreadPoolExecutor(max_workers=len(ports)) as pool:
        for live in pool.map(_identify, ports):
            if live and live.get("project") == str(project_root):
                return live
    return None


def _identify(port: Any) -> dict[str, Any] | None:
    """Ask the dashboard on a loopback port who it is, None when nothing usable answers."""
    if not isinstance(port, int):
        return None
    try:
        with urlopen(f"http://{HOST}:{port}/api/endpoint", timeout=PROBE_TIMEOUT_SECONDS) as answer:
            live = json.loads(answer.read().decode("utf-8"))
    except (URLError, OSError, ValueError):
        return None
    return live if isinstance(live, dict) and live.get("url") else None


class _Server(ThreadingHTTPServer):
    """Bind without SO_REUSEADDR so a taken port is refused rather than stolen.

    `HTTPServer` sets `allow_reuse_address`, which on Windows lets a second process take a
    live listening socket from the first. That defeats the port scan below: every session
    would bind the preferred port and silently replace the dashboard already there,
    including one serving a different project.
    """

    allow_reuse_address = False
    daemon_threads = True

    def handle_error(self, request: Any, client_address: Any) -> None:
        """Stay quiet when a client hangs up, and report anything else.

        A browser closing a tab, reloading, or dropping the event stream aborts a keep-alive
        connection while the server is already blocked reading the next request line, which
        raises before any route is entered and so never reaches the handler's own guard. The
        default prints a full traceback for each one, so ordinary navigation buried the log
        in WinError 10053. Only that family is swallowed; a real fault still surfaces.
        """
        if isinstance(sys.exc_info()[1], ConnectionError):
            return
        super().handle_error(request, client_address)


def _bind(dashboard: Dashboard) -> ThreadingHTTPServer:
    """Bind the preferred port, then nearby ports, then any free one."""
    handler = _handler_for(dashboard)
    for port in [PREFERRED_PORT + offset for offset in range(PORT_SCAN)] + [0]:
        try:
            return _Server((HOST, port), handler)
        except OSError:
            continue
    raise OSError(f"no free port on {HOST}")


def _publish(project_root: Path, endpoint_record: dict[str, Any]) -> None:
    mesh_dir = project_root / ".quarry"
    try:
        mesh_dir.mkdir(parents=True, exist_ok=True)
        (mesh_dir / ENDPOINT_FILE).write_text(
            json.dumps(endpoint_record, indent=2), encoding="utf-8"
        )
    except OSError as error:
        print(f"quarry dashboard endpoint not recorded: {error}", file=sys.stderr)


def _handler_for(dashboard: Dashboard) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "quarry-dashboard"
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args: Any) -> None:
            """Stay silent: the host reads this process's stdout as the MCP channel."""

        def do_GET(self) -> None:
            self._guarded(self._get)

        def do_POST(self) -> None:
            self._guarded(self._post)

        def do_DELETE(self) -> None:
            self._guarded(self._delete)

        def _get(self, path: str) -> None:
            if path == "/api/snapshot":
                payload, etag = dashboard.snapshot()
                if self.headers.get("If-None-Match") == etag:
                    self.send_response(304)
                    self.send_header("ETag", etag)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                self._json(payload, etag=etag)
                return
            if path.startswith("/api/issues/"):
                issue_id = unquote(path[len("/api/issues/") :])
                self._json(tracker.detail(dashboard.project_root, issue_id))
                return
            if path == "/api/guide":
                self._json(guide.guide())
                return
            if path == "/api/fleet":
                self._json(coordination.coordination(dashboard.project_root))
                return
            if path == "/api/settings":
                self._json(
                    settings.settings(
                        dashboard.project_root, dashboard.endpoint, POLL_MS, dashboard.health()
                    )
                )
                return
            if path == "/api/events":
                self._events()
                return
            if path == "/api/endpoint":
                self._json({
                    **dashboard.endpoint,
                    "reached_tracker": dashboard.reached_tracker(),
                })
                return
            if path.startswith("/api/"):
                self._fail(404, f"no such endpoint: {path}")
                return
            self._static(path)

        def _post(self, path: str) -> None:
            body = self._body()
            root = dashboard.project_root
            if path == "/api/recall":
                self._json(mesh.recall(root, str(body.get("question", ""))))
                return
            if path == "/api/issues":
                new_id = tracker.create(
                    root,
                    str(body.get("title", "")),
                    str(body.get("type", "task")),
                    int(body.get("priority", 2)),
                )
                dashboard.invalidate()
                self._json({"id": new_id}, status=201)
                return
            if path == "/api/deps":
                tracker.link(root, str(body["dependent"]), str(body["prerequisite"]))
                dashboard.invalidate()
                self._json({"ok": True})
                return
            if path == "/api/shutdown":
                dashboard.stopped.set()
                self._json({"stopping": True})
                return
            if path == "/api/settings/mode":
                try:
                    mode = settings.set_mode(root, str(body.get("mode", "")))
                except settings.SettingsError as error:
                    self._fail(400, str(error))
                    return
                self._json({"mode": mode})
                return
            action = _action(path)
            if action is None:
                self._fail(404, f"no such endpoint: {path}")
                return
            issue_id, verb = action
            handlers: dict[str, Callable[[], None]] = {
                "close": lambda: tracker.close(root, issue_id, str(body.get("reason", ""))),
                "claim": lambda: tracker.claim(root, issue_id),
                "priority": lambda: tracker.prioritize(root, issue_id, int(body["priority"])),
                "reopen": lambda: tracker.reopen(root, issue_id, str(body.get("reason", ""))),
            }
            handler = handlers.get(verb)
            if handler is None:
                self._fail(404, f"no such action: {verb}")
                return
            handler()
            dashboard.invalidate()
            self._json({"ok": True})

        def _delete(self, path: str) -> None:
            root = dashboard.project_root
            if path == "/api/deps":
                body = self._body()
                tracker.unlink(root, str(body["dependent"]), str(body["prerequisite"]))
                dashboard.invalidate()
                self._json({"ok": True})
                return
            if path.startswith("/api/issues/"):
                tracker.delete(root, unquote(path[len("/api/issues/") :]))
                dashboard.invalidate()
                self._json({"ok": True})
                return
            self._fail(404, f"no such endpoint: {path}")

        def _events(self) -> None:
            """Hold the connection open and push one event whenever a watched file changes.

            The browser stops polling and waits here instead, so a change made in a terminal
            reaches an open tab without the page asking for the whole snapshot on a timer.
            Runs until the client goes away, which raises a ConnectionError the caller
            swallows, or until the board is stopped; keepalive comments stop an idle proxy
            or browser closing it first. This stream deliberately does not hold the board
            open against the idle reaper: the page's own polling is what marks it in use.
            """
            root = dashboard.project_root
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            self.wfile.write(b"retry: 2000\n\n")
            self.wfile.flush()
            seen = fingerprint(root)
            spoke = time.monotonic()
            while not dashboard.stopped.wait(WATCH_INTERVAL_SECONDS):
                now = fingerprint(root)
                if now != seen:
                    seen = now
                    dashboard.invalidate()
                    self.wfile.write(b"event: changed\ndata: {}\n\n")
                    self.wfile.flush()
                    spoke = time.monotonic()
                elif time.monotonic() - spoke > KEEPALIVE_SECONDS:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    spoke = time.monotonic()

        def _guarded(self, route: Callable[[str], None]) -> None:
            """Run one route, turning every failure into a JSON error the page can show.

            A client that navigates away mid-response raises while the reply is being
            written, and every such error is a ConnectionError: aborted, reset or broken
            pipe. It is swallowed rather than reported, because there is nobody left to
            report it to, and it must be caught before the generic branch, whose own
            `_fail` write would raise again on the same dead socket.
            """
            path = urlparse(self.path).path
            dashboard.note_request()
            if not self._same_origin():
                self._fail(403, "cross-origin requests are refused")
                return
            started = time.perf_counter()
            try:
                route(path)
            except ConnectionError:
                return
            except TrackerTimeout as error:
                self._fail(504, str(error))
            except TrackerError as error:
                self._fail(400, str(error))
            except (KeyError, ValueError) as error:
                self._fail(400, f"bad request: {error}")
            except Exception as error:
                self._fail(500, f"{type(error).__name__}: {error}")
            finally:
                if path != "/api/events":
                    dashboard.note_served(time.perf_counter() - started)

        def _same_origin(self) -> bool:
            """Refuse requests a browser sends from another site, since routes mutate state."""
            origin = self.headers.get("Origin")
            if origin is None:
                return True
            return urlparse(origin).netloc == f"{HOST}:{self.server.server_port}"

        def _body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0:
                return {}
            if length > MAX_BODY_BYTES:
                raise ValueError("request body too large")
            raw = self.rfile.read(length)
            decoded = json.loads(raw.decode("utf-8"))
            if not isinstance(decoded, dict):
                raise ValueError("request body must be a JSON object")
            return decoded

        def _static(self, path: str) -> None:
            relative = "index.html" if path in ("/", "") else path.lstrip("/")
            target = (STATIC_DIR / relative).resolve()
            if not target.is_file() or STATIC_DIR.resolve() not in target.parents:
                self._fail(404, "not found")
                return
            payload = target.read_bytes()
            kind = CONTENT_TYPES.get(target.suffix, "application/octet-stream")
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def _json(self, payload: Any, status: int = 200, etag: str = "") -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            if etag:
                self.send_header("ETag", etag)
            self.end_headers()
            self.wfile.write(body)

        def _fail(self, status: int, message: str) -> None:
            dashboard.note_failure()
            self._json({"error": message}, status=status)

    return Handler


def _action(path: str) -> tuple[str, str] | None:
    """Split `/api/issues/<id>/<verb>` into its issue id and verb."""
    if not path.startswith("/api/issues/"):
        return None
    rest = path[len("/api/issues/") :]
    issue_id, separator, verb = rest.rpartition("/")
    if not separator or not issue_id or not verb:
        return None
    return unquote(issue_id), verb
