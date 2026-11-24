---
name: flow-phase-running
description: "Pin this project to the phase-running lane and refuse every other route until it is released. Use when the user says 'lock the flow', 'follow the phase path', 'stay on lane E', or an open bd epic titled 'workflow: <goal>' should drive the work step by verified step."
metadata:
  short-description: "Pin the open-phase-epic lane"
---

# Flow: phase running

Lane E from the paths page, pinned. A phased effort lives in bd as an epic titled
`workflow: <goal>`, and the lane walks it.

Pin it on invocation:

```
"$QUARRY_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/quarry.py" flow flow-phase-running
```

## Steps

`Steps: /quarry:workflow -> next-step -> /quarry:implement -> next-workflow`

1. **`/quarry:workflow`** locate the position from live state, never from memory.
2. **next-step** verify the phase's ready tickets against real evidence, close the ones
   demonstrably done, and name the single next ticket.
3. **`/quarry:implement`** that named ticket, not one you would rather do.
4. **next-workflow** once every child is closed, retire the epic and author the next phase.

## Branches this lane allows

- At **`/quarry:implement`**, fall back to **`/quarry:ready`** when there is no phase epic
  open after all. The lane assumed one; if none exists, that assumption is the finding.

## Refused while pinned

Closing a phase ticket you cannot demonstrate. Positive evidence only: the file exists,
the test passes, the commit landed. "Should be done" is not done, and a gate ticket is
held harder still. Also refused: inventing an order the `blocks` edges do not carry, and
authoring the next phase while the current one has open children. Do not start
`wayfinder`, `triage` or `diagnosing-bugs` from here.

## Leaving

`/quarry:flow-cancel` releases the pin. A single turn may depart when the user writes
`flow override` themselves. Both rules are defined once in the `quarry` skill's Flow locks
section, which is also what the guard and the audit enforce.

## Routes

**From** an open `workflow:` epic (entry) · **To** the next phase, authored by `next-workflow`
**Alternates** `flow-too-foggy` when the next phase is mostly unknowns rather than steps
**Lost** `/quarry:workflow`
