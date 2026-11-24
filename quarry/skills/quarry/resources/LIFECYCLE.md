# Lifecycle and YOLO

> The workflow layer, rewritten for quarry from the spec-driven lifecycle whose design
> source inspired it. The tracker is bd; the memory is the mesh; decisions are files.

## The map

```
idea
 └─ grilling            interview the idea; decisions land in CONTEXT.md/ADRs as
    │                   side effects; facts via sub-agents, decisions via the mode
    ├─ (unanswerable?) ── research or prototype, then back
    └─ spec             synthesize the conversation into a spec; publish as a bd epic
        └─ tickets      break into tracer-bullet tickets: bd issues with blocks edges
            └─ implement  claim → tdd at the spec's seams → code-review → close
```

On-ramps that merge onto the map: incoming issues from elsewhere → `triage`; something
broken → `diagnosing-bugs`; an effort too foggy for one session → `wayfinder`; upkeep →
`improve-codebase-architecture`.

The dependency graph makes the map executable: tickets published with `blocks` edges
turn `bd ready` into the frontier, so scheduling is a property of the graph, not a plan
someone maintains.

## Tracer bullets

Each ticket is a vertical slice through every layer (real input to real output), sized
to one fresh context window, declaring its blocking edges. A frontier ticket can be
picked up cold by an agent with zero conversation context: `bd show` supplies the
contract, `Ask_Knowledge` supplies the history, `CONTEXT.md` supplies the vocabulary.

## Phase boundaries

Context is the scarcest resource. At each boundary, prefer the cheapest move that keeps
primary sources primary:

1. **Continue**: same window, still making progress. Default.
2. **`/clear`**: thinking done, artifacts durable (files + bd + mesh); start doing.
3. **`handoff` skill**: a successor needs the state; seal + handoff doc.
4. **Sub-agent**: a side question would flood the window; dispatch it out.
5. **Compact**: last resort, never the first reach: every non-Continue move converts
   primary sources into lossy secondary ones. If compaction is coming anyway, the
   PreCompact hook has already sealed, so after it, trust the index and Ask_Knowledge,
   not your summary of what you remember.

Rule of thumb: grill → spec → tickets in one unbroken window; every implement fresh.

## Mode: interactive vs yolo

The mode lives in `docs/agents/quarry.md` (`Interaction mode: interactive|yolo`).
**Every question point in every lifecycle skill reads it first.** `yolo` transfers
decision authority rather than changing tone: what the answer agent decides persists into
the same artifacts a human answer would, so a later session cannot tell the two apart and
will build on either as settled. The rationale line and the sealed history are what keep
it auditable. In `yolo`:

- Dispatch the answer agent (quarry-answer-agent) with the question, the recommended
  answer, and the user's original description. It returns `DECISION` + `RATIONALE` or
  `NEEDS HUMAN`.
- Record every answer exactly where a human answer would have gone, spec section,
  ADR, ticket field, decision log. Same auditable trail.
- `NEEDS HUMAN` questions collect into one batch surfaced to the user at the next
  natural stop; they do not silently vanish and they do not get guessed.
- Destructive, outward-facing, or credential-bearing actions are never yolo'd; they
  are human gates regardless of mode.

In `interactive`, ask the user directly, one numbered question at a time, each with a
recommended answer.

## Vocabulary

Two reference skills run beneath the whole map: `domain-modeling` (the project's
ubiquitous language in `CONTEXT.md`) and `codebase-design` (modules, interfaces,
depth, seams). Every artifact the lifecycle emits, ticket titles, test names, review
findings, uses the glossary's terms. A ticket that invents a synonym for a settled
term is a bug in the ticket.
