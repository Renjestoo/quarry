---
name: quarry
description: "Durable agent work that survives compaction, and the router for every workflow in this plugin. Load this skill when the user expresses any work intent and the right next step is unclear: 'what should I work on', 'help me plan/build/add X', 'I have a bug', 'triage this', 'resume where I left off', 'what did we decide', 'which quarry skill do I use', 'track this work', 'seal this', 'what's ready'. Also the entry point for sealed-memory recall and the bd tracker surface."
metadata:
  short-description: "Durable work router: memory, tracker, atlas, lifecycle"
---

# Quarry

Work that survives context loss. Four homes for state, one law each:

1. **Decisions live in files**: what the work is for in `CHARTER.md` (objectives with
   measures, and the non-goals bounding them), terms and constraints in `CONTEXT.md`,
   hard-to-reverse choices in `docs/adr/`. Never in conversation.
2. **Work lives in bd**: issues with dependency edges; `bd ready` is the frontier, and
   closing a blocker promotes what it blocked.
3. **History lives in the mesh**: transcripts sealed byte-for-byte into immutable,
   line-addressed units under `.quarry/`, recalled verbatim through `Ask_Knowledge`.
4. **The code lives in the atlas**: a graft graph of the repo under `graft/`,
   consulted automatically before hand exploration.

Compaction, `/clear`, session end: none of them lose work, because none of the four
homes is the conversation. **If the user is unsure which workflow to use, this map
decides; they should never have to guess.** In `interactive` mode, present the route
and confirm before dispatching; in `yolo` (see `docs/agents/quarry.md`), route and go,
dispatching the answer agent at question points.

## Least architecture (the law about what you build)

The four homes answer where state lives. This one answers how much to build in them:
**the smallest complete solution the stated requirements demand.**

Complexity that comes from the problem is essential and gets built: authentication,
concurrency, transactional integrity, persistence, recovery, security boundaries, real
error handling, migrations, validation, state transitions. Complexity added for
requirements nobody stated is accidental and does not.

**The removal test**, run against every component, layer, interface, option and
configuration knob before it ships: remove it, then name the stated requirement that
becomes impossible, unsafe, incorrect, or materially harder to maintain. If nothing does,
it should not exist. One implementation needs no registry, one provider no factory, one
background job no framework. Generalize when a second concrete use exists *today*, or
when the boundary itself is architectural (authorization, storage, external providers,
transactions), which can earn an abstraction at one implementation.

**The deliberation threshold** governs thinking the way the removal test governs
building: weigh alternatives only when the choice could change correctness, security,
maintainability, performance, or architecture. Otherwise take the conventional direct
approach and proceed. A component that is naturally one function is not a design
question, and a requirement that already names its answer is not a trade-off.

**Missing information is a question, not a requirement.** When it is not clear which way
something should work, resolve it: ask, measure, or read the source. Building for every
answer you might get is not neutrality, it commits to all of them at once, and the
configurability outlives the uncertainty that produced it. When it genuinely cannot be
resolved now, name the assumption, build the one way, and say what would change it.

**Stop when the requirements are met.** "I could make this more extensible" is not a
reason to keep designing, and neither is symmetry, completeness, nor discomfort at an
interface that looks too plain. Done is when the stated requirements are satisfied and the
removal test finds nothing left to delete.

Both tests cut one way only, and the opposite failure is just as real: stripping
necessary complexity to make something look smaller is the same defect inverted. Simple
is not simplistic. `codebase-design` holds the tests that apply this to one module.

## Scripts report while they run

A script that prints nothing until it exits is indistinguishable from a hung one, so
**every script an agent writes reports its phases as they start and finish**, and wraps a
materially long loop in a progress bar. This is for the person watching as much as for the
agent: work nobody can see is work nobody can interrupt.

`print` and the standard library `logging` satisfy it, as do `tqdm`, `rich`, `loguru`,
`structlog`, `click`, `typer`, `alive_progress` and their kin; frameworks that report their
own progress (`lightning`, `transformers`, `keras`, `fastai`, `optuna`, `ray`) already do.
A trivial loop needs no progress bar, but the script still says what it did. A PreToolUse
guard parses the script and refuses to run a silent one, so this is enforced rather than
advised.

## Which skill do I use? (situation → route)

| The user's situation | Route | Produces |
|---|---|---|
| "I have an idea / want to build X" | `/quarry:grill X` (grilling + domain-modeling) | recorded decisions, `CONTEXT.md` terms, ADRs |
| "Grilling is done, write it up" | `/quarry:spec` (spec skill) | a bd epic holding the spec |
| "Break the spec into work" | `/quarry:tickets` (tickets skill) | bd issues with `blocks` edges → `bd ready` |
| "Do the next ticket" / "implement" | `/quarry:implement` or `/quarry:ready` first | a claimed ticket, built test-first, reviewed, closed |
| "An issue/PR arrived from outside" | `triage` skill | verified, labeled issue + agent brief |
| "Something is broken" | `diagnosing-bugs` skill | red feedback loop → root cause → fixed at a seam |
| "This effort is huge and foggy" | `wayfinder` skill | a map epic of decision tickets, one per session |
| "We need facts before deciding" | `research` skill | cited notes in `docs/research/` |
| "We need to feel it before deciding" | `prototype` skill | throwaway answer on `prototype/<slug>` |
| "The codebase hurts / tech debt" | `improve-codebase-architecture` | HTML report → grilled candidate → tracked epic |
| "Where was I? / what's next?" | `/quarry:workflow` | your position on the map + paste-ready next command |
| "What did we decide about X?" | `Ask_Knowledge` (or `/quarry:ask X`) | verbatim passages at addresses |
| "Where is X in the code? / what does it touch?" | the atlas: `graft ask "X"`, `graft callers`, `graft blast` | ranked nodes, call chains, impact (see [ATLAS.md](resources/ATLAS.md)) |
| "Orient me on this codebase" | `graft map` (via the atlas) | token-budgeted repo orientation |
| "Run several agents at once / swarm this" | `parallel-agents` skill | bd's swarm, merge slot, gates, worktrees and the hooked status |
| "Hand this to another agent/colleague" | `handoff` skill | sealed session + handoff doc that references artifacts |
| "Ask someone who isn't here" | `to-questionnaire` skill | an async questionnaire file |
| "Merge conflicts" | `resolving-merge-conflicts` skill | both intents preserved, checks green |
| "Teach me <topic>" | `teach` skill | a learning workspace with records |
| "I'm lost / re-explain simply" | `wait-what` skill | the last message re-pitched plainly |
| "Show me the board / dashboard / a UI" | `/quarry:dashboard` | the loopback URL of this project's live dashboard |
| "What is this work for? / why are we building this?" | `/quarry:charter` | objectives with measures, non-goals, and what serves each |
| "What can quarry do? / help / overview" | `/quarry:help` | the full catalog: every skill, command, and when to use each |
| Setup steps only a human can do | `wizard` skill | a guided script (secrets handled) |

When two rows could apply, the main flow below breaks the tie, and `/quarry:workflow`
always answers "where am I and what's next" from live state, not memory.

## The main flow

```
idea ──▶ grilling ──▶ spec ──▶ tickets ──▶ implement ──▶ ready ──▶ implement ──▶ …
        (decisions)   (bd epic)  (bd issues   (one ticket per fresh context:
         in files                with blocks   tdd at the spec's seams +
                                  edges)       code-review, then close)
```

**grilling**: the interview that separates facts (sub-agents look them up) from
decisions (you answer, numbered questions with recommended answers, or the answer
agent does, in yolo). Every answer lands in a file as it's given. Done when the design
tree's frontier is empty.

**spec**: synthesis, not interviewing: the conversation becomes a spec published as a
bd epic (`/quarry:spec`). Seams are confirmed here; they decide where tests live.

**tickets**: the spec becomes tracer-bullet slices: vertical, one-context-window-sized
bd issues with `blocks` edges. From here on, **`bd ready` is the plan**: nobody
maintains a schedule; the dependency graph is it.

**implement**: one claimed ticket per fresh context window: `bd show` for the
contract, `Ask_Knowledge` for the history, tdd at the seams, code-review (Standards
axis + Spec axis), close with a verified reason. A discovery that blocks gets a ticket; every other one is
a line on the epic's parking list, never absorbed and never a ticket.
The `task-agent` can run this loop autonomously.

On-ramps merge onto this flow: `triage` for inbound work, `diagnosing-bugs` for
breakage, `wayfinder` for efforts that need decisions before a spec can exist,
`research`/`prototype` as detours that answer one question and feed back in.

## Phase boundaries (context economics)

Grill → spec → tickets in **one unbroken window**; every implement **fresh**. At each
boundary prefer the cheapest move: continue → `/clear` (artifacts are durable) →
`handoff` → sub-agent → compact last (if compaction comes anyway, the PreCompact hook
sealed, then trust the index and `Ask_Knowledge`, not memory). Full doctrine:
[LIFECYCLE.md](resources/LIFECYCLE.md).

## Cold-start protocol

1. Read the injected index (SessionStart hook): one line per sealed unit.
2. `bd ready`: the frontier.
3. `Ask_Knowledge` before re-deciding anything: *never invent what an earlier window
   said. If it is not in your context and Ask_Knowledge did not return it, you do not
   know it.*
4. Resuming claimed work: `bd show <id> --long`, read the notes.

Full protocol and the notes format: [RESUMABILITY.md](resources/RESUMABILITY.md).

## Commands and engine

`/quarry:ready · show · create · close · dep · ask · seal · units · mode · workflow ·
setup · grill · dashboard · charter · flow-cancel · help`: the state, memory, and mode
surface (`/quarry:help` prints the full catalog). Engine CLI:

```
"$QUARRY_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/quarry.py" <init|seal|ask|index|list|mcp|dashboard|stop|url|flow|collide|charter|behaviour|hook|guard|doctor|install>
```

**The dashboard is real, and it starts on request.** `mcp` does not start it: that would
run a board in every project the user opens. When the user asks to see it, run
`dashboard` in the background and give them the address `url` prints. It is scoped to
the project, not the session, so every session in the project shares one board and a
second `dashboard` joins the running one instead of opening a rival. Never tell the user
no dashboard exists; if none is running, start it.

A board outlives the session that started it on purpose, so it stops two other ways:
`stop` ends this project's board on request, and a board nobody has asked anything of for
half an hour ends itself. Neither can touch another project's board, which is checked by
asking the server which project it serves before anything is stopped.

The board is also a write surface, not just a view: issues can be created, claimed,
reprioritized, closed, reopened, linked and deleted from it, every write running the
matching `bd` command. It reports what it can prove and nothing else: objective attainment
comes from a hand-written `Status:` in `CHARTER.md` rather than a ticket count, lead and
cycle times come from bd's own stamps, and the board's own health comes from counting its
requests.

## Flow locks

The six lanes on the dashboard's paths page also ship as skills that **pin** the project
to one lane: `flow-new-feature`, `flow-inbound-issue`, `flow-something-broke`,
`flow-too-foggy`, `flow-phase-running`, `flow-cold-resume`. A pin is recorded in
`.quarry/flow.json`, so it survives compaction and a new session, and it is re-injected on
every prompt for the same reason.

Enforcement is two-layered. A PreToolUse guard on the `Skill` tool denies an out-of-lane
call before it runs, which covers the agent leaving the lane on its own; a slash command
the user types does not pass through that tool and is not the target. The Stop audit stays
the backstop, denying a completed reply that used a skill the lane excludes. Release with
`/quarry:flow-cancel`. A single departure is allowed when **the user** writes
`flow override` in their own message; the agent writing that phrase grants nothing, which
both layers check by requiring the phrase in a user record.

Each lane's permitted skills are derived from the same `LANES` table the paths page draws,
so a lane and the board cannot disagree about what it allows.

## Reference layers

| Layer | Files |
|---|---|
| Sealed memory doctrine | [MEMORY.md](resources/MEMORY.md) |
| Tracker doctrine | [TRACKER.md](resources/TRACKER.md) |
| Every bd command, and what is not obvious | [BD-COMMANDS.md](resources/BD-COMMANDS.md) |
| Several agents, one tracker | `parallel-agents` skill |
| Lifecycle + YOLO rules | [LIFECYCLE.md](resources/LIFECYCLE.md) |
| Resuming cold | [RESUMABILITY.md](resources/RESUMABILITY.md) |
| Code atlas doctrine | [ATLAS.md](resources/ATLAS.md) |
| The seven harness parts, and when to use each | [PARTS.md](resources/PARTS.md) |
| Design vocabulary | `codebase-design`, `domain-modeling` skills |
| Writing for agents | `writing-for-agents`, `writing-great-skills` skills |

## Prerequisites

`bd` CLI v0.60+ in PATH, `bd init` run once by a human, Python 3.11 for the engine
(machine-specific interpreter path; see the plugin README). `bd prime` is the live
source of truth for tracker syntax; this file never duplicates it.
