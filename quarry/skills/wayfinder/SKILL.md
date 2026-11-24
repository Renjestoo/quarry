---
name: wayfinder
description: "Chart a foggy mega-effort as a bd map epic with child decision tickets (research, prototype, grilling, task) resolved at most one per session, converting unknowns into decisions until spec becomes possible. Use when an effort is too big or too unclear for one session and the user says 'chart this', 'too foggy', or 'where do we even start', or when an effort needs decisions before a spec can exist."
metadata:
  short-description: "Chart foggy efforts as decision tickets"
---

# Wayfinder

Some efforts cannot be planned because they are mostly *unknown*. Wayfinding converts
unknowns into decisions, deliberately slowly, until the fog lifts enough for a spec.

**Deliverables are decisions, not code.** The map is done when enough is decided that
`spec` can synthesize the rest.

## The map

`bd create "<effort name>" -t epic`: the map issue. Its description holds three
sections:

- **Decisions needed**: the child tickets (below).
- **Fog**: everything currently marked *"Not yet specified"*; the honest state of
  the effort.
- **Out of scope**: what wayfinding will not explore.

## Decision tickets

Each unknown becomes a child of the map, one of four **kinds** (the type vocabulary lives
in [TRACKER.md](../quarry/resources/TRACKER.md), not here):

| Kind | Resolves | Filed as | Resolved by |
|---|---|---|---|
| research | what is true (a library's limits, an API's shape) | `--type=spike --labels kind:research` | research skill, AFK |
| prototype | what feels right (an interaction, a data shape) | `--type=spike --labels kind:prototype` | prototype skill, AFK |
| grilling | what we want (a trade-off only the owner can settle) | `--type=task --labels kind:grilling` | grilling, HITL |
| task | a concrete step already understood, not yet worth the main flow | `--type=task` | implement, AFK |

Research and prototype are **spikes** in bd's own words, "timeboxed investigation to
reduce uncertainty before committing to a story", so `bd list --type spike` finds every
open investigation without depending on the label convention. The label still says which
sort of investigation it is.

Grilling stays a task on purpose. bd's `decision` type is where quarry records a decision
already made (see `domain-modeling`), and filing an unanswered question as one would mix
settled and unsettled in the same query. A kind bd has no type for is carried as a label,
never invented as a type: `bd create --type=grilling` fails with `invalid issue type`.

Mark each ticket's disposition (HITL needs the user; AFK an agent can finish) in its
description.

## Protocol

1. **Chart**: list the unknowns; for each, the decision it gates and the cheapest
   ticket type that resolves it. Dependent decisions get `blocks` edges; the map is
   a graph, and its frontier is the ready set, exactly like the main flow.
2. **Claim then resolve**: one decision ticket per session (`bd update --claim`).
   Resolving = the ticket's findings recorded in its close reason, plus whatever
   artifact it produced (cited notes, a prototype on a throwaway branch, an ADR), plus
   the map updated: fog entries that are now decided move out of *Not yet specified*.
3. **Re-chart as fog lifts**: new unknowns discovered mid-ticket become new children
   (`discovered-from` the one being resolved). The map is allowed to change shape;
   that is it working.
4. **Exit**: when the remaining decisions are ordinary implementation choices, close
   the map with a summary of what was decided, and hand the settled ground to
   `spec`. If the effort dies, close the map `wontfix`-style with the reason; a
   killed exploration with recorded reasons is a success of the process.

## Rules

- One decision ticket per session. Wayfinding that rushes re-litigates.
- Fog is written down, never gestured at: "Not yet specified" is a list, not a vibe.
- Every closed ticket leaves a durable trace (ADR, notes file, decision bead):
  a decision that lives only in the close reason will be re-climbed after compaction.

## Routes

**From** foggy mega-efforts (entry) · **To** `spec` once the remaining decisions are ordinary
**Alternates** `grilling` when the fog is one session's worth of questions rather than a map of unknowns
**Lost** `/quarry:workflow`

