---
name: spec
description: "Synthesize the current conversation into a spec (no interview, just capture) and publish it to the tracker as a bd epic. Use when grilling has settled the decisions and the user says 'write the spec', 'turn this into a spec', or after a grilling session has emptied its question frontier."
metadata:
  short-description: "Synthesize the conversation into a tracked spec"
---

# Spec

Synthesis, not interviewing: the decisions are already made (grilling) or the user
asked too early (say so and suggest grilling first, but still write what exists).

## Process

1. **Load the vocabulary.** Read `CONTEXT.md` and the ADRs touching this area. The
   spec uses glossary terms throughout; a spec that invents synonyms is a bug in the
   spec.
2. **Settle the seams.** Sketch where this feature will be tested: existing seams over
   new ones, the highest seam that can see the behavior, ideally one seam total. In
   `interactive`, confirm the seams with the user. In `yolo`, dispatch the answer
   agent ("do these seams match the description?"): seams are the one place a wrong
   guess costs the most.
3. **Write the spec** (template below) into the epic's description.
4. **Publish**: `bd create "<title>" -t epic -p <priority>` with the spec as the
   description, then label it `ready-for-agent` (label names come from
   `docs/agents/quarry.md`).
5. **File the decisions**: every Implementation Decision below that is hard to
   reverse, surprising, and traded-off gets its ADR + decision bead now, referencing
   the epic.

## Template

```markdown
## Problem Statement

<The problem, from the user's perspective.>

## Solution

<The solution, from the user's perspective.>

## User Stories

<numbered list, extensive: "As an <actor>, I want <capability>, so that <benefit>".>

## Implementation Decisions

<modules built/modified, their interfaces, technical clarifications, architectural
choices, schema changes, API contracts. The smallest complete design these requirements
demand (the quarry skill's least-architecture law): name the complexity that is
essential here and why, and do not design for a requirement nobody stated. No file
paths, no code; they go stale.
Exception: a prototype-produced snippet that encodes a decision (state machine,
schema, type shape) may be inlined, trimmed to the decision, marked prototype-sourced.>

## Testing Decisions

<what makes a good test here (external behavior only), which modules are tested,
prior art in the codebase, and the seams chosen in step 2.>

## Out of Scope

<what this spec deliberately does not do.>
```

When you finish, point at `/quarry:tickets <epic-id>`: the spec becomes executable
work there. The epic's `acceptance_criteria` field gets the one-line definition of
done; the body keeps the detail.

## Routes

**From** `grilling` with decisions settled · **To** `tickets` (`/quarry:tickets <epic-id>`)
**Alternates** `wayfinder` when the effort is still too foggy to spec; `research`/`prototype` for the last open questions before writing it
**Lost** `/quarry:workflow`

