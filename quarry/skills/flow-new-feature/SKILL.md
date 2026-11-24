---
name: flow-new-feature
description: "Pin this project to the new-feature lane and refuse every other route until it is released. Use when the user says 'lock the flow', 'follow the new feature path', 'stay on lane A', or starts a feature and wants the full grill to spec to tickets to implement sequence enforced rather than suggested."
metadata:
  short-description: "Pin the idea-to-shipped lane"
---

# Flow: new feature

Lane A from the paths page, pinned. An idea becomes recorded decisions, then a spec, then
tickets, then one implemented ticket at a time.

Pin it on invocation:

```
"$QUARRY_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/quarry.py" flow flow-new-feature
```

## Steps

`Steps: idea -> /quarry:grill -> /quarry:spec -> /quarry:tickets -> /quarry:implement -> bd close -> bd ready`

1. **idea** the intent, stated in one sentence.
2. **`/quarry:grill`** decisions, landing in `CONTEXT.md` and ADRs as they are made.
3. **`/quarry:spec`** the settled conversation synthesised into a bd epic.
4. **`/quarry:tickets`** tracer-bullet issues with `blocks` edges, so `bd ready` is the plan.
5. **`/quarry:implement`** one ticket, tdd at the seam the spec named.
6. **`bd close`** with a reason that says what was verified.
7. **`bd ready`** the next ticket. Steps 5 to 7 repeat per ticket.

## Branches this lane allows

- After `/quarry:grill`, take **research** when you lack facts, or **prototype** when you
  need to feel it. Both return to the grill.
- After `/quarry:spec`, take **domain-modeling** when the terms are unclear.

## Refused while pinned

Anything that is not a step or a branch above. In particular: do not start `triage`,
`diagnosing-bugs`, `wayfinder`, `next-step` or `next-workflow` from here. Those are other
lanes, and switching mid-flight is the drift this pin exists to prevent. Do not skip
ahead either: a spec without a grill, or tickets without a spec, is the same departure
taken forwards.

If the work turns out to belong to another lane, that is a real finding. Say so and
release the pin deliberately rather than quietly doing the other thing.

## Leaving

`/quarry:flow-cancel` releases the pin. A single turn may depart when the user writes
`flow override` themselves. Both rules are defined once in the `quarry` skill's Flow locks
section, which is also what the guard and the audit enforce.

## Routes

**From** an idea (entry) · **To** the lane runs to `bd ready`, then repeats per ticket
**Alternates** `flow-too-foggy` when the idea cannot be grilled yet; `flow-inbound-issue` when somebody else filed it
**Lost** `/quarry:workflow`
