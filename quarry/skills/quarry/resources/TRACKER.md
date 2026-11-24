# Tracker doctrine

> Adapted from the beads issue-tracker discipline. `bd prime` is the live source of
> truth for command syntax; this file carries only the judgment.

## Why bd

Conversation state dies with the context window. bd keeps work state in a Dolt-backed
graph that survives compaction, syncing like git. The decision test from the quarry
skill applies: work you'll need in two weeks lives here, not in TodoWrite.

bd is the execution substrate, not an integration to work around. Quarry defines the
workflow semantics and bd provides the durable dependency graph they run through: spec to
epic, tickets to issues with `blocks` edges, the frontier to the plan, claim to close, and
closing a blocker as the mechanism that promotes the next work. The atlas is genuinely
optional and degrades orientation when absent; without bd there is no lifecycle at all,
only skills with nowhere to put their output.

## The working set

- Statuses bd accepts that quarry's lifecycle actually uses: `open` `in_progress`
  `blocked` `deferred` `closed`. Only `closed` is terminal.
  `hooked` ("attached to an agent's hook") is bd's multi-agent primitive, and it marks an
  issue a running agent is attached to rather than one merely claimed. Quarry's default is
  still one agent on one ticket, for context economics rather than because the tracker
  requires it, so `hooked` stays unused by the default lifecycle. It is available, along
  with swarms, gates, the merge slot and worktrees, when a project deliberately runs a
  fleet: see the `parallel-agents` skill, which is the one home for that.
- Priorities: P0 critical … P4 backlog.
- Types, the whole set bd accepts: `task` `bug` `feature` `epic` `chore` `decision`
  `spike` `story` `milestone`. Aliases: `feat`/`enhancement` to feature, `dec`/`adr` to
  decision. `bd types` prints the live list with a description of each; this file is the
  only place quarry restates it, so a skill that needs a type points here rather than
  listing them again. Do not take the list from `bd create --help`, whose `--type` line
  still names only the first six: that is where quarry's own stale list came from.
  `spike` is bd's timeboxed investigation, which is what wayfinder's research and
  prototype tickets are. `story` and `milestone` go unused on purpose: quarry keeps user
  stories inside the spec epic rather than as separate issues, and an epic already marks
  a set of related work, so a marker issue holding no work would duplicate it. Revisit if
  either stops being true.
  Anything outside the set is refused with `invalid issue type`, so a kind quarry cares
  about that bd genuinely has no type for is carried as a label, not invented as a type.
- Per issue: `description` (WHAT, stable), `design` (HOW, mutable), and
  `acceptance_criteria` (the definition of done). Never blur the three: acceptance
  criteria say what success looks like, not how to build it.
- `notes` are the living handoff state, see RESUMABILITY.md.

## Dependencies

Ten edge types, read from `bd dep add --help`, whose `-t` flag is the live list and
defaults to `blocks`:

`blocks` `tracks` `related` `parent-child` `discovered-from` `until` `caused-by`
`validates` `relates-to` `supersedes`

Only `blocks` affects readiness. Five carry quarry's lifecycle:

| Type | Meaning | How it is written |
|---|---|---|
| `blocks` | hard prerequisite | `bd dep add <dependent> <prerequisite>`, "from needs to" |
| `related` | symmetric soft link | `bd dep add <a> <b> --type related`, either way |
| `parent-child` | epic hierarchy | epic to subtask |
| `discovered-from` | provenance | discovery to the issue it was found while working |
| `supersedes` | a record replaced by a later one | `bd supersede <old> --with <new>` |

The other five, `tracks` `until` `caused-by` `validates` `relates-to`, are available and go
unused. Their meanings are deliberately not restated here: this file carries only what has
been read from the installed bd, and a definition guessed from a type's name is the same
staleness the types list above warns about. Read `bd dep add --help` before reaching for
one, and add it here once its meaning has been checked rather than assumed.

Plan backward from the goal in "X needs Y" language; the ready set, issues whose
blockers are all closed, *is* the plan, so a correct dependency graph is worth more
than a detailed schedule. Verify with `bd dep tree` (up = blockers) and `bd dep cycles`.

## Session discipline

1. `bd ready` → 2. `bd show <id> --long` → 3. `bd update <id> --claim` (atomic
   claim-and-start) → 4. notes while working → 5. `bd close <id> --reason "..."`.
   Closing a blocker promotes what it blocked into ready; check `bd ready` after every
   close.

## Discovery pattern

Work reveals work, and work that is filed without a limit never ends. So each discovery
is sorted before anything is created.

**A blocker** makes an acceptance criterion of the current ticket fail, or the goal check
of its epic. It gets a ticket: `bd create "..." -t bug --deps discovered-from:<current-id>`,
a `blocks` edge, and the red check (its command and its output) in the description. Mark
the current issue blocked with an explanation.

**Everything else is parked.** It is one line on the epic's parking list, and it gets no
ticket: `bd note <parking-list-id> "<what>, <file:line>, found in <current-id>"`. The
parking list is one deferred bead for each epic, titled `Parking list: <epic-id>`. Find it
with `bd children <epic-id>`. If it does not exist, create it once:
`bd create "Parking list: <epic-id>" -t chore --parent <epic-id>`, then `bd defer <new-id>`.
A ticket with no epic uses one project-wide bead titled `Parking list`.

A deferred bead stays visible in `bd list` and does not appear in `bd ready`, which is the
point: recorded, not lost, not in the way. Nothing on the parking list is worked during the
run; it is read once, afterwards. Never silently absorb a discovery into the current issue,
and never fix a parked one "while here".

A `--until` date is not just a note to a human: bd's own CLI states it plainly ("Defer
date ... is in the past. Issue will appear in bd ready immediately" is the real warning
for a stale date), so once the date passes the issue is live for readiness purposes on
its own. An indefinite defer (no `--until`) is the one that never resurfaces by itself,
`bd ready` will never show it, and nothing periodically sweeps `bd list --status
deferred` unless a skill does. When starting a new phase or picking the next ticket
(`next-workflow`, `wayfinder`'s re-chart, or simply between tickets), check it:
`bd undefer <id>` brings one back to `open` explicitly, which is required for anything
deferred indefinitely and good practice even for a dated one.

## Decisions

Record hard-to-reverse choices as `bd create --type decision` with
Decision / Rationale / Alternatives / Affects, and supersede rather than edit when a
decision changes. `bd supersede <old> --with <new>` is that move: it writes the
`supersedes` edge and closes the old record carrying a reference to its replacement, so
both survive and the order between them is readable. Editing the old record in place would
destroy the thing a decision log exists to keep. If the choice is also surprising with a
real trade-off, it deserves an ADR file as well (see domain-modeling skill); the bd
decision records that it was made, the ADR records what it means.

## Phased workflows

A multi-phase effort is tracked entirely in bd, never in markdown: each phase is an
epic titled `workflow: <goal>` (title prefix, because `bd list --json` does not expose
labels), its steps are child tickets with `blocks` edges encoding the order, and the
exit criterion is the final child ticket, held to demonstration. `next-step` verifies
and closes evidence-done steps; `next-workflow` closes the finished epic and authors
the next. Closed issues are the history (`bd list --status closed`) with nothing
archived to files.

## Boundaries

bd stores work state, not knowledge: do not use it as a glossary or a reference store
(sealed memory and `CONTEXT.md` are for that), and do not track single-session linear
tasks in it; that is what TodoWrite is for in repos without a phase structure; in
bd-tracked repos the guard enforces that bd is the only tracker.
