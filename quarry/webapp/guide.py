"""Serve the two reference sheets: the workflow paths, and every command and skill."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PLUGIN_ROOT / "skills"
COMMANDS_DIR = SKILLS_DIR / "quarry" / "commands" / "quarry"

LANES: tuple[dict[str, Any], ...] = (
    {
        "id": "A",
        "name": "new feature",
        "when": "you have an idea",
        "main": (
            ("idea", "the intent"),
            ("/quarry:grill", "decisions, in files"),
            ("/quarry:spec", "a bd epic"),
            ("/quarry:tickets", "issues + blocks edges"),
            ("/quarry:implement", "tdd at the seam"),
            ("bd close", "verified reason"),
            ("bd ready", "next ticket"),
        ),
        "loop": {"label": "repeats per ticket"},
        "branches": (
            ("/quarry:grill", "research", "facts you lack", "needs facts", False),
            ("/quarry:grill", "prototype", "how it feels", "needs feel", False),
            ("/quarry:spec", "domain-modeling", "glossary + ADR", "terms unclear", False),
        ),
    },
    {
        "id": "B",
        "name": "inbound issue",
        "when": "someone else filed it",
        "main": (
            ("issue arrives", "needs-triage"),
            ("triage", "verify the claims"),
            ("agent brief", "ready-for-agent"),
            ("/quarry:implement", "build it"),
            ("bd close", "done"),
        ),
        "loop": None,
        "branches": (
            ("triage", "wontfix", "out of scope", "premise wrong", True),
            ("triage", "needs-info", "ask the author", "unanswerable", True),
            ("agent brief", "ready-for-human", "human only", "judgment needed", True),
        ),
    },
    {
        "id": "C",
        "name": "something broke",
        "when": "a bug, not obvious",
        "main": (
            ("diagnosing-bugs", "red loop first"),
            ("reproduce", "deterministic"),
            ("root cause", "not a symptom"),
            ("tdd", "fails red"),
            ("/quarry:implement", "fix at the seam"),
            ("bd close", "cannot regress"),
        ),
        "loop": None,
        "branches": (
            ("root cause", "improve-codebase-architecture", "no seam exists", "no seam", False),
            ("diagnosing-bugs", "triage", "came from outside", "inbound first", False),
        ),
    },
    {
        "id": "D",
        "name": "too foggy",
        "when": "big and unknown",
        "main": (
            ("wayfinder", "map epic"),
            ("decision tickets", "one per session"),
            ("resolve one", "ADR or notes"),
            ("/quarry:spec", "fog lifted"),
            ("/quarry:tickets", "back on the main line"),
        ),
        "loop": {"label": "one decision per session"},
        "branches": (
            ("decision tickets", "research", "what is true", "AFK", False),
            ("decision tickets", "prototype", "what feels right", "AFK", False),
            ("resolve one", "/quarry:grill", "what we want", "HITL", False),
        ),
    },
    {
        "id": "E",
        "name": "phase running",
        "when": "a workflow epic is open",
        "main": (
            ("/quarry:workflow", "where am I"),
            ("next-step", "verify + name it"),
            ("/quarry:implement", "the named ticket"),
            ("next-workflow", "author the next phase"),
        ),
        "loop": None,
        "branches": (
            ("/quarry:implement", "/quarry:ready", "no phase epic", "unphased", False),
        ),
    },
    {
        "id": "F",
        "name": "cold resume",
        "when": "a fresh session",
        "main": (
            ("session start", "index injected"),
            ("bd ready", "the frontier"),
            ("Ask_Knowledge", "what was settled"),
            ("/quarry:implement", "continue"),
        ),
        "loop": None,
        "branches": (
            ("bd ready", "bd show --long", "notes are the state", "claimed work", False),
        ),
    },
)

COMMANDS: tuple[tuple[str, str], ...] = (
    ("workflow", "/quarry:workflow"),
    ("ready", "/quarry:ready"),
    ("show", "/quarry:show <id>"),
    ("create", "/quarry:create"),
    ("close", "/quarry:close <id>"),
    ("dep", "/quarry:dep"),
    ("ask", '/quarry:ask "<q>"'),
    ("seal", "/quarry:seal"),
    ("units", "/quarry:units"),
    ("mode", "/quarry:mode"),
    ("grill", "/quarry:grill <idea>"),
    ("setup", "/quarry:setup"),
    ("dashboard", "/quarry:dashboard"),
    ("charter", "/quarry:charter"),
    ("flow-cancel", "/quarry:flow-cancel"),
    ("help", "/quarry:help"),
)

GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("the router", "router", ("quarry",)),
    ("the main line", "skill",
     ("grilling", "spec", "tickets", "implement", "tdd", "code-review")),
    ("ways in", "skill",
     ("triage", "diagnosing-bugs", "wayfinder", "research", "prototype")),
    ("design vocabulary", "skill",
     ("codebase-design", "domain-modeling", "improve-codebase-architecture")),
    ("phases", "skill", ("next-step", "next-workflow")),
    ("support", "skill",
     ("handoff", "parallel-agents", "resolving-merge-conflicts", "to-questionnaire",
      "teach", "wait-what", "wizard")),
    ("writing doctrine", "skill", ("writing-for-agents", "writing-great-skills")),
    ("flow locks", "skill",
     ("flow-new-feature", "flow-inbound-issue", "flow-something-broke", "flow-too-foggy",
      "flow-phase-running", "flow-cold-resume")),
)

MEANS: dict[str, str] = {
    "workflow":
        "Where am I, and what is the exact next command. Reads live state, never memory.",
    "ready":
        "The frontier: issues whose blockers are all closed.",
    "show":
        "Full context for one issue: description, design, acceptance, notes.",
    "create":
        "File an issue, linked to the work it came from.",
    "close":
        "Close with a reason, and report what it unblocked.",
    "dep":
        "Add a dependency edge between two issues.",
    "ask":
        "Ask sealed history one plain-language question.",
    "seal":
        "Seal this session into the mesh now.",
    "dashboard":
        "The address of this board. Scoped to the project, shared by every session in it.",
    "charter":
        "What the work is for: objectives with measures, and the non-goals bounding them.",
    "units":
        "List the sealed memory units.",
    "mode":
        "Show or flip interactive versus yolo.",
    "grill":
        "Interview an idea into recorded decisions.",
    "setup":
        "Configure a repository for quarry, once.",
    "flow-cancel":
        "Release the pinned lane, or report which one is pinned.",
    "flow-new-feature":
        "Pin lane A: idea to grill to spec to tickets to implement, and refuse the rest.",
    "flow-inbound-issue":
        "Pin lane B: triage verifies the claims before anything reaches an agent.",
    "flow-something-broke":
        "Pin lane C: the red loop is built before anybody theorises about the cause.",
    "flow-too-foggy":
        "Pin lane D: unknowns become decisions, one ticket per session, until a spec fits.",
    "flow-phase-running":
        "Pin lane E: walk the open workflow epic, verifying each step against evidence.",
    "flow-cold-resume":
        "Pin lane F: rebuild position from durable state rather than guessing at it.",
    "help":
        "Print the whole catalog.",
    "quarry":
        "The map itself. Fires when you express work intent and the right next step "
        "is unclear.",
    "grilling":
        "Interview an idea as a design tree. Facts get looked up, decisions get asked.",
    "spec":
        "Synthesise the settled conversation into a spec, published as a bd epic.",
    "tickets":
        "Break the spec into tracer-bullet issues with blocking edges, so bd ready "
        "becomes the plan.",
    "implement":
        "One ticket, one fresh context: claim, contract, build, review, close.",
    "tdd":
        "Red, green, refactor at the seams the spec named. Mock only at system "
        "boundaries.",
    "code-review":
        "Two independent passes: repo standards, and faithfulness to the ticket.",
    "triage":
        "Inbound issues through a label machine. Verify claims before anything "
        "reaches an agent.",
    "diagnosing-bugs":
        "Build a red, deterministic loop before theorising. No fix without a diagnosis.",
    "wayfinder":
        "Chart a foggy effort as decision tickets, at most one resolved per session.",
    "research":
        "Dispatch one question to primary sources, returning cited notes committed "
        "to the repo.",
    "prototype":
        "Throwaway code answering exactly one design question, on a throwaway branch.",
    "codebase-design":
        "Modules, interfaces, depth and seams, and the tests that tell deep from shallow.",
    "domain-modeling":
        "Keep the project vocabulary sharp. Record only hard-to-reverse choices as ADRs.",
    "improve-codebase-architecture":
        "Survey for deepening opportunities weighted by change frequency.",
    "next-step":
        "Verify a phase epic against evidence, close what is done, name the one next "
        "ticket.",
    "next-workflow":
        "Retire a finished phase and author the next one.",
    "handoff":
        "Seal, then write a doc that points at durable artifacts instead of copying them.",
    "parallel-agents":
        "Several agents on one tracker: swarms, the merge slot, gates and worktrees. "
        "Available, never automatic.",
    "resolving-merge-conflicts":
        "Trace each side to its source so both intents survive.",
    "to-questionnaire":
        "Package a grilling for someone who is not here to answer.",
    "teach":
        "A stateful learning workspace using retrieval practice, not summaries.",
    "wait-what":
        "One corrective move: re-pitch the last message in plain language.",
    "wizard":
        "Generate a script that walks a human through steps only they can do.",
    "writing-for-agents":
        "How to write anything an agent will read.",
    "writing-great-skills":
        "How to write the skills themselves. Predictability is the root virtue.",
}


def guide() -> dict[str, Any]:
    """Return the paths and the catalog, with any drift from the plugin on disk named.

    The descriptions are curated rather than lifted from frontmatter, so they can fall
    behind the plugin. `drift` reports what exists on disk but is missing here, and what
    is listed here but no longer on disk, so neither passes unnoticed.
    """
    return {"paths": _paths(), "catalog": _catalog(), "drift": _drift()}


def _paths() -> list[dict[str, Any]]:
    return [
        {
            "id": lane["id"],
            "name": lane["name"],
            "when": lane["when"],
            "steps": [
                {"cmd": cmd, "sub": sub, "last": index == len(lane["main"]) - 1}
                for index, (cmd, sub) in enumerate(lane["main"])
            ],
            "loop": lane["loop"],
            "branches": [
                {"after": after, "cmd": cmd, "sub": sub, "when": when, "ends": ends}
                for after, cmd, sub, when, ends in lane["branches"]
            ],
        }
        for lane in LANES
    ]


def _catalog() -> dict[str, Any]:
    return {
        "commands": [
            {"name": shown, "detail": MEANS[key]} for key, shown in COMMANDS
        ],
        "groups": [
            {
                "name": name,
                "kind": kind,
                "items": [{"name": item, "detail": MEANS[item]} for item in items],
            }
            for name, kind, items in GROUPS
        ],
    }


def _drift() -> dict[str, list[str]]:
    listed_skills = {item for _, _, items in GROUPS for item in items}
    listed_commands = {key for key, _ in COMMANDS}
    on_disk_skills = (
        {p.parent.name for p in SKILLS_DIR.glob("*/SKILL.md")} if SKILLS_DIR.is_dir() else set()
    )
    on_disk_commands = (
        {p.stem for p in COMMANDS_DIR.glob("*.md")} if COMMANDS_DIR.is_dir() else set()
    )
    in_prose = _router_commands()
    help_commands, help_names = _help_catalog()
    return {
        "skills_missing_from_catalog": sorted(on_disk_skills - listed_skills),
        "skills_listed_but_absent": sorted(listed_skills - on_disk_skills),
        "commands_missing_from_catalog": sorted(on_disk_commands - listed_commands),
        "commands_listed_but_absent": sorted(listed_commands - on_disk_commands),
        "commands_missing_from_router": sorted(on_disk_commands - in_prose),
        "commands_in_router_but_absent": sorted(in_prose - on_disk_commands),
        "commands_missing_from_help": sorted(on_disk_commands - help_commands),
        "skills_missing_from_help": sorted(on_disk_skills - help_names),
    }


def _help_catalog() -> tuple[set[str], set[str]]:
    """Return the commands and the backticked names the help catalog actually mentions.

    `/quarry:help` opens by promising every skill and command, "nothing skipped or
    collapsed", and that promise is why it needs checking: a catalog claiming completeness
    while omitting three commands and eight skills is worse than an unannotated list, and it
    went unreported because drift compared the router's prose and never this file. Absent or
    unreadable reads as empty, which surfaces as drift rather than as silence.
    """
    path = COMMANDS_DIR / "help.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return set(), set()
    return (
        set(re.findall(r"/quarry:([a-z0-9-]+)", text)),
        {name.strip() for name in re.findall(r"`([^`]+)`", text)},
    )


def _router_commands() -> set[str]:
    """Return the commands the router skill names in its own prose command list.

    The catalog tuples in this module and the files on disk can agree perfectly while the
    sentence a reader actually reads names something else. That happened: fifteen commands
    shipped while `SKILL.md` listed fourteen, and drift reported empty throughout, because
    nothing compared the prose to anything. Absent or unparseable reads as the empty set,
    which surfaces as drift rather than as silence.
    """
    router = SKILLS_DIR / "quarry" / "SKILL.md"
    try:
        text = router.read_text(encoding="utf-8")
    except OSError:
        return set()
    listed = re.search(r"`/quarry:([^`]*·[^`]*)`", text, re.DOTALL)
    if listed is None:
        return set()
    return {part.strip() for part in listed.group(1).split("·") if part.strip()}
