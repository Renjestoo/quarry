"""Quarry command line: seal transcripts, recall history, serve MCP, dispatch hooks, drive.

Each subcommand imports only the modules it uses. The PreToolUse guards run this file on
every tool call, and importing the whole engine up front cost them about 0.2 s per call.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

MESH_DIRNAME = ".quarry"
READY_LIMIT = 20


def find_project_root() -> Path:
    """Return the nearest ancestor of the working directory holding `.quarry`, else the cwd."""
    current = Path.cwd().resolve()
    for candidate in (current, *current.parents):
        if (candidate / MESH_DIRNAME).is_dir():
            return candidate
    return current


def run_init(_args: argparse.Namespace) -> int:
    """Create the project mesh directory and its index, idempotently."""
    from quarry_lib.store import MeshStore

    store = MeshStore(find_project_root() / MESH_DIRNAME)
    store.initialize()
    print(f"quarry mesh ready at {store.root}")
    return 0


def run_seal(args: argparse.Namespace) -> int:
    """Seal the current session into the mesh; explicit flags override auto-location."""
    from quarry_lib.store import MeshStore
    from quarry_lib.transcripts import (
        CLAUDE_PROVIDER,
        CODEX_PROVIDER,
        TranscriptError,
        find_claude_transcript,
        seal_auto,
        seal_transcript,
        seal_zcode_session,
        zcode_rollout_path,
    )

    store = MeshStore(find_project_root() / MESH_DIRNAME)
    try:
        if args.zcode_session:
            unit = seal_zcode_session(store, zcode_rollout_path(args.zcode_session))
            source = f"zcode session {args.zcode_session}"
        elif args.session:
            unit = seal_transcript(
                store, find_claude_transcript(args.session), CLAUDE_PROVIDER
            )
            source = f"claude session {args.session}"
        elif args.rollout:
            unit = seal_transcript(store, Path(args.rollout), CODEX_PROVIDER)
            source = f"codex rollout {args.rollout}"
        elif args.transcript:
            unit = seal_transcript(store, Path(args.transcript), CLAUDE_PROVIDER)
            source = f"claude transcript {args.transcript}"
        else:
            unit, source = seal_auto(store, find_project_root())
    except (TranscriptError, OSError, ValueError) as error:
        print(f"quarry seal failed: {error}", file=sys.stderr)
        return 1
    if unit is None:
        print(f"nothing new to seal ({source}): the session tail holds no unsealed records")
        return 0
    print(
        f"sealed {unit.unit_id} from {unit.session_id} via {source}: "
        f"{len(unit.content.splitlines())} preserved lines, {unit.source_bytes} evidence bytes"
    )
    return 0


def run_ask(args: argparse.Namespace) -> int:
    """Ask the project's preserved history one plain-language question."""
    from quarry_lib.ask import KnowledgeController, render_result
    from quarry_lib.store import MeshStore

    controller = KnowledgeController(MeshStore(find_project_root() / MESH_DIRNAME))
    print(render_result(controller.ask(args.question)))
    return 0


def run_index(_args: argparse.Namespace) -> int:
    """Print the sealed-memory index the session-start hook injects."""
    from quarry_lib.ask import KnowledgeController
    from quarry_lib.store import MeshStore

    controller = KnowledgeController(MeshStore(find_project_root() / MESH_DIRNAME))
    rendered = controller.index()
    print(rendered if rendered else "no sealed units yet; the mesh starts at the first seal")
    return 0


def run_list(_args: argparse.Namespace) -> int:
    """Print one line per sealed unit: id, length, and what opened it."""
    from quarry_lib.ask import KnowledgeController
    from quarry_lib.store import MeshStore

    controller = KnowledgeController(MeshStore(find_project_root() / MESH_DIRNAME))
    entries = controller.index_entries()
    if not entries:
        print("no sealed units yet")
        return 0
    for entry in entries:
        print(entry)
    return 0


def run_mcp(_args: argparse.Namespace) -> int:
    """Serve Ask_Knowledge over stdio.

    Deliberately starts no dashboard. A host launches one MCP server per session and per
    project, so starting a board here would run one nobody asked for in every project the
    user opens, all reaching for the same port. The dashboard is started on request.
    """
    from quarry_lib.ask import KnowledgeController
    from quarry_lib.mcp_server import serve
    from quarry_lib.store import MeshStore

    project_root = find_project_root()
    controller = KnowledgeController(MeshStore(project_root / MESH_DIRNAME))
    serve(controller)
    return 0


def run_dashboard(_args: argparse.Namespace) -> int:
    """Run the dashboard in the foreground, or report the one already serving this project.

    Returns when the board stops: on ctrl-c, on `quarry stop`, or on its own once it has
    been idle long enough, which is what keeps an abandoned board from outliving every
    session that could have used it.
    """
    from webapp.server import start as start_dashboard

    board = start_dashboard(find_project_root())
    if board is None:
        return 1
    if board.adopted:
        print(f"quarry dashboard already on {board.endpoint['url']}")
        return 0
    print(f"quarry dashboard on {board.endpoint['url']}  (ctrl-c to stop)")
    with contextlib.suppress(KeyboardInterrupt):
        board.stopped.wait()
    board.close()
    print("quarry dashboard stopped")
    return 0


def run_stop(_args: argparse.Namespace) -> int:
    """Stop this project's dashboard, after proving the board answering is this project's."""
    from webapp.server import stop as stop_dashboard

    stopped = stop_dashboard(find_project_root())
    if not stopped:
        print("no dashboard running for this project")
        return 1
    print(f"quarry dashboard on {stopped} is stopping")
    return 0


def run_url(_args: argparse.Namespace) -> int:
    """Print where the dashboard for this project is listening, after proving it answers."""
    from webapp.server import live_endpoint as live_dashboard

    running = live_dashboard(find_project_root())
    if running is None:
        print("no dashboard running; start one with: quarry dashboard")
        return 1
    print(running["url"])
    return 0


def run_flow(args: argparse.Namespace) -> int:
    """Pin this project to one workflow lane, report the pinned one, or release it."""
    from webapp import flow

    project_root = find_project_root()
    if args.cancel:
        released = flow.release(project_root)
        if released is None:
            print("no flow pinned; nothing to release")
            return 1
        print(f"released {released['skill']} (lane {released['lane']})")
        return 0
    if args.skill:
        try:
            pinned = flow.pin(project_root, args.skill)
        except ValueError as error:
            print(f"quarry flow: {error}", file=sys.stderr)
            return 1
        print(f"pinned {pinned['skill']} (lane {pinned['lane']}); "
              f"release with: quarry flow --cancel")
        return 0
    current = flow.pinned(project_root)
    if current is None:
        print("no flow pinned; every route is open")
        return 1
    print(f"{current['skill']} (lane {current['lane']}), pinned {current['pinned_at']}")
    return 0


def run_collide(args: argparse.Namespace) -> int:
    """Report which issues the atlas predicts will touch the same files, before a fleet runs.

    Exits 1 when an overlap is predicted, or when nothing could be checked, so a dispatch
    script can branch on it. An overlap is a warning about the filesystem, never a claim
    that the issues are wrong: the tracker serialises work by declared edges, and two issues
    with no edge between them are exactly the pair bd will offer in parallel regardless.
    """
    from webapp import collide, tracker

    project_root = find_project_root()
    if not collide.has_atlas(project_root):
        print(
            "no graft atlas in this project, so nothing here can predict which files an "
            "issue touches. Dispatch on the ready queue alone and expect git's merge to be "
            "the first thing that notices a collision.",
            file=sys.stderr,
        )
        return 1
    try:
        rows = (
            tracker.records(project_root, args.issues)
            if args.issues
            else tracker.ready(project_root, READY_LIMIT)
        )
        found = collide.contention(project_root, rows)
    except (tracker.TrackerError, collide.CollideError) as error:
        print(f"quarry collide: {error}", file=sys.stderr)
        return 1
    titles = {str(row.get("id")): str(row.get("title") or "") for row in rows}
    print(f"checked {found['checked']} issue(s) against the atlas")
    if not args.issues and len(rows) == READY_LIMIT:
        print(f"the ready queue filled the {READY_LIMIT} checked; name issue ids to go wider")
    contended = found["contended"]
    if not contended:
        print("no predicted file overlap; these can be dispatched in parallel")
        return 0
    for path, issues in sorted(contended.items(), key=lambda pair: (-len(pair[1]), pair[0])):
        print(f"\n{path}  {len(issues)} issues")
        for issue in issues:
            print(f"    {issue}: {titles.get(issue, '')}")
    print(
        f"\n{len(contended)} contended file(s). This ranks each issue's own words against "
        f"the atlas, so it is not a diff: a file central to an area is predicted for most "
        f"issues about it. Sequence a real overlap with a blocks edge, or give the agents "
        f"worktrees and expect to hold the merge slot."
    )
    return 1


def run_charter(_args: argparse.Namespace) -> int:
    """Print this project's objectives, their measures and its non-goals, as JSON.

    A subcommand rather than something `/quarry:charter` reaches into the package for: the
    command used a relative `sys.path`, so it only resolved from a directory that happened
    to contain the checkout, and failed with ModuleNotFoundError everywhere the plugin is
    actually installed.
    """
    from webapp import charter

    print(json.dumps(charter.charter(find_project_root()), indent=2))
    return 0


def run_behaviour(args: argparse.Namespace) -> int:
    """Record, drop, or list measured facts about how things behave here.

    Listing marks the facts due for re-measurement and exits 1 when any is, so a check can
    tell "nothing is stale" from "something needs re-measuring" without parsing the text.
    """
    from webapp import behaviour

    project_root = find_project_root()
    if args.drop:
        removed = behaviour.drop(project_root, args.drop)
        if removed is None:
            print(f"no fact claims {args.drop!r}; nothing dropped", file=sys.stderr)
            return 1
        print(f"dropped: {removed['claim']}")
        return 0
    if args.record:
        try:
            entry = behaviour.record(project_root, args.record, args.evidence or "")
        except ValueError as error:
            print(f"quarry behaviour: {error}", file=sys.stderr)
            return 1
        print(f"recorded {entry['measured']}: {entry['claim']}")
        return 0
    rows = behaviour.facts(project_root)
    if not rows:
        print("no measured behaviour recorded yet")
        return 0
    overdue = 0
    for fact in rows:
        stale = behaviour.due(fact)
        overdue += 1 if stale else 0
        print(f"{'DUE ' if stale else '    '}{fact['measured']}  {fact['claim']}")
        print(f"                  evidence: {fact['evidence']}")
    print(f"\n{len(rows)} fact(s), {overdue} due for re-measurement "
          f"(older than {behaviour.STALE_AFTER_DAYS} days)")
    return 1 if overdue else 0


def run_drive(args: argparse.Namespace) -> int:
    """Run the stage chain on one goal, each stage in fresh headless Claude Code sessions.

    `--until` ends the run after the green check of the stage it names. With `--json` the run
    is written as the JSON Lines events of `quarry_lib.events`, and a refused run is an
    `error` event on stdout instead of a line on stderr.
    """
    from quarry_lib.driver import DriverError, drive
    from quarry_lib.stages import until
    from quarry_lib.store import MeshStore

    project_root = find_project_root()
    if args.json:
        from quarry_lib.events import EventStream

        stream = EventStream(sys.stdout)
        with contextlib.redirect_stdout(stream):
            try:
                code = drive(
                    project_root, MeshStore(project_root / MESH_DIRNAME), args.goal,
                    args.issue, args.model, until(args.until), stream.event,
                )
            except DriverError as error:
                stream.event("error", detail=str(error))
                code = 1
            stream.event("end", exit=code)
        return code
    try:
        return drive(
            project_root, MeshStore(project_root / MESH_DIRNAME), args.goal, args.issue,
            args.model, until(args.until),
        )
    except DriverError as error:
        print(f"quarry drive failed: {error}", file=sys.stderr)
        return 1


def run_delete_epic(args: argparse.Namespace) -> int:
    """Preview, or with --force delete, one bd epic and the issues under it.

    Prints one JSON object: `epic`, `title`, `children` and, after a delete, `deleted`; or
    `error` with exit 1.
    """
    from quarry_lib.driver import DriverError
    from quarry_lib.epic_delete import delete, plan

    project_root = find_project_root()
    try:
        result = (delete if args.force else plan)(project_root, args.epic)
    except DriverError as error:
        print(json.dumps({"error": str(error)}))
        return 1
    print(json.dumps(result))
    return 0


def run_doctor(args: argparse.Namespace) -> int:
    """Report each harness part as present, absent or degraded; exit 1 if a required one is not."""
    from quarry_lib.doctor import print_json, print_report, probe

    return (print_json if args.json else print_report)(probe())


def run_install(args: argparse.Namespace) -> int:
    """Install and configure the chosen harness parts; exit 1 unless each ends present."""
    from quarry_lib.install import run as install_run

    return install_run(args.parts, args.dry_run)


def run_hook(args: argparse.Namespace) -> int:
    """Dispatch one host lifecycle hook event."""
    from quarry_lib.hook import handle as handle_hook

    return handle_hook(args.event, find_project_root())


def run_guard(args: argparse.Namespace) -> int:
    """Judge one PreToolUse call from stdin; exit 2 denies the call."""
    from quarry_lib.guard import run as guard_run

    return guard_run(args.rule, find_project_root())


def build_parser() -> argparse.ArgumentParser:
    from webapp import flow

    parser = argparse.ArgumentParser(prog="quarry", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="create the project mesh directory")
    init_parser.set_defaults(run=run_init)

    seal_parser = subparsers.add_parser(
        "seal", help="seal the current session into the mesh (auto-locates its transcript)"
    )
    source = seal_parser.add_mutually_exclusive_group()
    source.add_argument("--transcript", help="override: path to a Claude transcript .jsonl")
    source.add_argument("--rollout", help="override: path to a Codex rollout .jsonl")
    source.add_argument("--session", help="override: Claude session id to locate and seal")
    source.add_argument("--zcode-session", help="override: ZCode session id to locate and seal")
    seal_parser.set_defaults(run=run_seal)

    ask_parser = subparsers.add_parser("ask", help="ask preserved history a question")
    ask_parser.add_argument("question", help="one plain-language question")
    ask_parser.set_defaults(run=run_ask)

    index_parser = subparsers.add_parser("index", help="print the sealed-memory index")
    index_parser.set_defaults(run=run_index)

    list_parser = subparsers.add_parser("list", help="list sealed units")
    list_parser.set_defaults(run=run_list)

    mcp_parser = subparsers.add_parser("mcp", help="serve Ask_Knowledge over stdio")
    mcp_parser.set_defaults(run=run_mcp)

    dashboard_parser = subparsers.add_parser(
        "dashboard", help="run the web dashboard in the foreground"
    )
    dashboard_parser.set_defaults(run=run_dashboard)

    stop_parser = subparsers.add_parser(
        "stop", help="stop the web dashboard serving this project"
    )
    stop_parser.set_defaults(run=run_stop)

    url_parser = subparsers.add_parser("url", help="print the running dashboard's address")
    url_parser.set_defaults(run=run_url)

    flow_parser = subparsers.add_parser(
        "flow", help="pin this project to one workflow lane, report it, or release it"
    )
    flow_parser.add_argument(
        "skill", nargs="?", help=f"lane to pin: {', '.join(sorted(flow.LANES))}"
    )
    flow_parser.add_argument(
        "--cancel", action="store_true", help="release the pinned lane"
    )
    flow_parser.set_defaults(run=run_flow)

    collide_parser = subparsers.add_parser(
        "collide",
        help="predict which issues would touch the same files if dispatched in parallel",
    )
    collide_parser.add_argument(
        "issues", nargs="*", help="issue ids to check; default is the ready queue"
    )
    collide_parser.set_defaults(run=run_collide)

    charter_parser = subparsers.add_parser(
        "charter", help="print this project's objectives and non-goals as JSON"
    )
    charter_parser.set_defaults(run=run_charter)

    behaviour_parser = subparsers.add_parser(
        "behaviour",
        help="list, record or drop measured facts about how things behave here",
    )
    behaviour_parser.add_argument("--record", help="the claim to record; needs --evidence")
    behaviour_parser.add_argument("--evidence", help="what was observed to establish the claim")
    behaviour_parser.add_argument("--drop", help="remove the fact making this exact claim")
    behaviour_parser.set_defaults(run=run_behaviour)

    drive_parser = subparsers.add_parser(
        "drive", help="run grill, then spec, on one goal in fresh headless Claude Code sessions"
    )
    drive_parser.add_argument("goal", help="the goal text, recorded verbatim")
    drive_parser.add_argument("--issue", help="record the run on this bd issue, not a new one")
    drive_parser.add_argument("--model", help="full model id for the session, never an alias")
    drive_parser.add_argument(
        "--until", metavar="STAGE", help="end the run after this stage's green check: grill or spec"
    )
    drive_parser.add_argument(
        "--json", action="store_true", help="write the run as JSON Lines events on stdout"
    )
    drive_parser.set_defaults(run=run_drive)

    delete_parser = subparsers.add_parser(
        "delete-epic", help="preview, or with --force delete, a bd epic and the issues under it"
    )
    delete_parser.add_argument("epic", help="the bd id of the epic")
    delete_parser.add_argument(
        "--force", action="store_true", help="delete; without it nothing changes"
    )
    delete_parser.set_defaults(run=run_delete_epic)

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="report each harness part as present, absent or degraded; it installs nothing, "
        "`install` does",
    )
    doctor_parser.add_argument(
        "--json", action="store_true", help="print the parts as one JSON object"
    )
    doctor_parser.set_defaults(run=run_doctor)

    install_parser = subparsers.add_parser(
        "install", help="run the steps that install and configure the chosen harness parts"
    )
    install_parser.add_argument(
        "parts", nargs="+", metavar="part",
        help="a part name as doctor prints it (rtk, bd, trailcode, task-observer, headroom, "
        "graphify), or all for every part that is not present",
    )
    install_parser.add_argument(
        "--dry-run", action="store_true", help="print the steps and run nothing"
    )
    install_parser.set_defaults(run=run_install)

    hook_parser = subparsers.add_parser("hook", help="dispatch one host hook event")
    hook_parser.add_argument(
        "event",
        help="SessionStart, PreCompact, PostCompact, UserPromptSubmit, or Stop",
    )
    hook_parser.set_defaults(run=run_hook)

    guard_parser = subparsers.add_parser(
        "guard", help="enforce one machine rule on a PreToolUse call from stdin"
    )
    guard_parser.add_argument(
        "rule", help="grep, todo, recall, flow, or gate; the rule to enforce"
    )
    guard_parser.set_defaults(run=run_guard)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run one quarry subcommand, with UTF-8 pinned on the streams it writes.

    Sealed passages, bd output and hook injections all carry non-ASCII, and a Windows
    console whose locale codec is GBK cannot encode it: without this the write raises and
    the caller receives nothing at all.

    `guard <rule>` is dispatched before the parser is built: guards run on every tool call,
    and building the parser imports the workflow module for the `flow` help text.
    """
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) == 2 and arguments[0] == "guard":
        return run_guard(argparse.Namespace(rule=arguments[1]))
    args = build_parser().parse_args(arguments)
    return args.run(args)


if __name__ == "__main__":
    raise SystemExit(main())
