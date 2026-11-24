---
name: flow-too-foggy
description: "Pin this project to the too-foggy lane and refuse every other route until it is released. Use when the user says 'lock the flow', 'follow the wayfinding path', 'stay on lane D', or faces an effort too big and too unknown to spec, where unknowns must become decisions one session at a time."
metadata:
  short-description: "Pin the chart-the-fog lane"
---

# Flow: too foggy

Lane D from the paths page, pinned. Unknowns become decisions, deliberately slowly, until
a spec becomes possible.

Pin it on invocation:

```
"$QUARRY_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/quarry.py" flow flow-too-foggy
```

## Steps

`Steps: wayfinder -> decision tickets -> resolve one -> /quarry:spec -> /quarry:tickets`

1. **wayfinder** chart the effort as a map epic: decisions needed, fog written down as a
   list rather than gestured at, and what is out of scope.
2. **decision tickets** one child per unknown, with `blocks` edges where one decision
   gates another.
3. **resolve one** exactly one per session, leaving a durable trace: an ADR, cited notes,
   or a prototype branch. The close reason alone is not enough.
4. **`/quarry:spec`** once the remaining decisions are ordinary engineering choices.
5. **`/quarry:tickets`** back on the main line.

## Branches this lane allows

- From **decision tickets**, take **research** for what is true, or **prototype** for what
  feels right. Both are agent-finishable.
- From **resolve one**, take **`/quarry:grill`** for what we want, which needs the user.

## Refused while pinned

Resolving more than one decision ticket per session. Wayfinding that rushes re-litigates,
and the one-per-session rule is the entire discipline. Also refused: jumping to
`/quarry:spec` while the fog list still holds entries that gate it, and starting
`/quarry:implement` on anything other than a decision ticket. Building is not how fog
lifts here.

## Leaving

`/quarry:flow-cancel` releases the pin. A single turn may depart when the user writes
`flow override` themselves. Both rules are defined once in the `quarry` skill's Flow locks
section, which is also what the guard and the audit enforce.

## Routes

**From** a foggy mega-effort (entry) · **To** `/quarry:spec` once the remaining decisions are ordinary
**Alternates** `flow-new-feature` when the idea turns out to be grillable in one session after all
**Lost** `/quarry:workflow`
