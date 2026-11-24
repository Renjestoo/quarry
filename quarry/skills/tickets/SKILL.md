---
name: tickets
description: "Break a spec or epic into tracer-bullet tickets published as bd issues with blocking dependency edges, so bd ready becomes the plan. Use after a spec is published as an epic, or when the user asks to break an epic into workable tickets."
metadata:
  short-description: "Slice a spec into tracer-bullet bd tickets"
---

# Tickets

A ticket is a **tracer bullet**: a vertical slice through every layer, real input to
real output, sized so one fresh context window can implement it, and declaring its
blocking edges so any frontier ticket can be picked up cold.

## Process

1. **Read the spec.** `bd show <epic-id> --long`. Pull the user stories and
   implementation decisions apart into buildable increments. Ask_Knowledge for any
   discussion the spec summarizes ("what did we decide about <x>"): the spec is the
   contract, the history is the context.
2. **Slice vertically.** Each ticket crosses storage, logic, and interface. A ticket
   that only creates a schema, or only adds a function, is a horizontal layer, not a
   tracer bullet, reject it. First ticket = thinnest end-to-end path; last = nothing
   (the epic closes when the stories are done, not when a cleanup list empties). A
   ticket whose deliverable is scaffolding for tickets that do not exist yet fails the
   least-architecture law and is not sliced, it is deleted.
3. **Plan the edges backward.** For each ticket ask "what does this need before it can
   start?" in *X needs Y* language, and add `blocks` edges accordingly
   (`bd dep add <dependent> <prerequisite>`). The ready set is the plan; a correct
   graph matters more than an accurate schedule. Unrelated tickets get no edge,
   false seriality wastes parallelism. When the slices really do come out independent
   and each is sized to its own window, that parallelism can be spent rather than
   merely preserved: `parallel-agents` covers working several at once.
4. **Quiz on granularity** (mode-aware, user, or answer agent in yolo): are any
   tickets bigger than one fresh context window? Any pair that always ships together
   and should be one ticket? Any edge that could be removed by reordering? Adjust.
5. **Publish.** One `bd create` per ticket: title in glossary vocabulary, description
   = what and why (referencing the story), `design` = how if the spec settled it,
   `acceptance_criteria` = observable done, `--parent <epic-id>`. Label
   `ready-for-agent`.
6. **Report the frontier**: `bd dep tree <first-ticket>` and `bd ready`: show the
   user the shape of the work, then point at the implement skill or the task agent.

## Expand-contract (wide refactors)

When a ticket widens an interface others use: one ticket to add the new path, tickets
to migrate callers one at a time (these block each other only when they touch the same
caller), a final ticket to remove the old path. Never one big-bang ticket.

## Rules

- Titles use `CONTEXT.md` terms. A ticket title is read cold; jargon without a
  glossary entry fails the next agent.
- Acceptance criteria say what success looks like, never how to build it.
- No ticket without an epic (or a standalone bug). Orphans are how work vanishes.
- No file paths or line numbers in descriptions; they go stale; name modules and
  interfaces instead.

## Routes

**From** `spec` · **To** `implement` (or dispatch the task agent on the ready queue)
**Alternates** `wayfinder` decision tickets, when the slices are really unknowns rather than work
**Lost** `/quarry:workflow`

