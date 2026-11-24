---
name: next-step
description: "Verify the active bd workflow epic's ready tickets against real evidence, close the demonstrably done ones with reasons, and report the single next ticket with its paste-ready command. Use when the user asks 'what's next', 'next step', or 'where was I' in a repo running a phased workflow."
metadata:
  short-description: "The exact next ticket from the bd workflow"
---

# Next step

A phased workflow lives in bd: the open epic whose title starts with `workflow:` is
the active phase, its child tickets are the steps, and their `blocks` edges are the
order. Nothing lives in markdown; bd is the board, the checklist, and the history.

## Process

1. **Locate the phase**: `bd list --type epic --status open --json` and take the epic
   whose title starts with `workflow:`. None open? Say so and point at
   `/quarry:workflow` (or the `next-workflow` skill to author the first phase).
2. **Verify with positive evidence only**: for each READY child ticket
   (`bd ready`, scoped to the epic's children), check its acceptance criteria
   against reality; the file exists, the test passes, the commit landed. "Should be
   done" is not done. Gate tickets are held to demonstration even harder.
3. **Close what passed**: `bd close <id> --reason "<the evidence>"`. Closing a
   blocker promotes the next ticket into ready; that is the workflow advancing.
   Never close a ticket whose criteria you cannot demonstrate.
4. **Report the frontier**: one or two sentences of position ("phase 2 of the
   advisor: 5 of 8 steps closed, 1 ready, 2 blocked"), then the exact next ticket
   and its paste-ready command (usually `/quarry:implement <id>`), plus any boundary
   owed before it (fresh window, `/clear`, handoff).

## Rules

- Never invent order: the `blocks` DAG is the order. If it looks wrong, that is a
  finding to surface, not a sequence to override.
- One step. This skill answers "what is next", not "what is the rest",
  `/quarry:workflow` draws the wider map.
- Every step closed while verifying is closed with its evidence as the reason.

## Routes

**From** a repo with an open `workflow:` epic (via `/quarry:workflow` or directly) · **To** the named ticket via `implement`
**Alternates** `/quarry:workflow` when no phased workflow exists; the `next-workflow` skill when the phase is finished
**Lost** `/quarry:workflow`
