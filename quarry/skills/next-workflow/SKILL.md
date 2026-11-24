---
name: next-workflow
description: "Retire a finished bd workflow epic (all steps closed, history preserved by bd itself) and author the next phase as a new workflow epic with ordered child tickets, through a mode-aware interview. Use when a phase is complete, or next-step reports every step closed."
metadata:
  short-description: "Close the finished phase epic, author the next"
---

# Next workflow

Phases live in bd as epics titled `workflow: <goal>`. Retiring a phase is closing
its epic; bd's closed issues are the history, queryable (`bd list --status closed`),
never a file to archive. Authoring the next phase is creating its epic and tickets.

## Gate

The active `workflow:` epic must have every child ticket closed. Open ones? Run the
`next-step` skill first: it closes the demonstrably done ones. Genuinely unfinished
work stops this skill, report it instead of absorbing it.

## Retire

1. `bd close <epic-id> --reason "phase complete: <one-line outcome> + how it was
   verified"`: the close reason is the phase's summary; the children's close
   reasons are its detail. Nothing is copied to markdown; bd keeps both forever.
2. If the user wants a human-readable log, show where the history lives
   (`bd list --status closed --json` scoped to the epic's children); do not create
   a file by default.

## Author the next phase

Interview (mode-aware: the user, or the answer agent in yolo, grounded in the user's
description of the next phase):

1. **Goal**: one sentence, becomes the epic title: `workflow: <goal>`.
2. **Exit criterion**: one observable state; becomes the final child ticket, held
   to demonstration.
3. **Knowns**: settled decisions the plan leans on, read them (ADRs, closed
   epics, `Ask_Knowledge` for the discussions), never re-ask.
4. **Route**: from the quarry map (main flow or an on-ramp).

Then create, in bd:

```
bd create --title "workflow: <goal>" --type epic --priority 1
bd create --title "<step 1>" --type task --parent <epic-id> --acceptance "<criteria>"
bd dep add <step-2> <step-1>
```

Every step gets acceptance criteria a cold agent can verify; ordering edges only
where one step genuinely needs another (in *X needs Y* order: `bd dep add <later>
<earlier>`); the exit-criterion ticket is blocked by everything that matters.

## Rules

- One phase open at a time; do not pre-author phase N+1 "while you're at it".
- The interview's answers go into the epic description and tickets, not just the
  conversation.
- In yolo, goal or exit-criterion questions that return NEEDS HUMAN block
  authoring; a phase whose exit nobody can state is a `wayfinder` case.

## Routes

**From** the `next-step` skill reporting every step closed · **To** the new phase's first ready ticket (via `next-step` or `implement`)
**Alternates** the `wayfinder` skill when the next phase is mostly unknowns rather than steps
**Lost** `/quarry:workflow`
