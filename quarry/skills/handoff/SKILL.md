---
name: handoff
description: "Hand the current session's state to a fresh agent: seal the transcript, write a handoff document that references (never duplicates) durable artifacts, and hand off mid-phase with boundaries intact. Use when switching agents, harnesses, or machines, or when handing work to a colleague who has none of this context."
metadata:
  short-description: "Seal and hand state to a fresh agent"
---

# Handoff

Narrow tool, wide consequences. Use it when the next worker is a *different* context
entirely: new harness, new machine, a colleague, or a genuinely mid-phase pivot. For
"same work, next window", `/clear` plus quarry's durable state is enough; the
handoff doc is for when artifacts alone do not carry the phase.

## Process

1. **Seal first.** `/quarry:seal`: the transcript becomes recallable evidence; the
   handoff doc then *points* at it instead of summarizing it.
2. **Write the handoff doc** to the OS temp dir (`handoff-<slug>-<date>.md`): it is
   a courier artifact, not project state. If its contents matter beyond the handoff,
   that content belongs in a durable home (issue notes, ADR, spec) and the doc
   references it.
3. **Contents**:
   - **State in one paragraph**: what phase, what is next.
   - **References, not copies**: the bd issues (ids), the spec epic, `CONTEXT.md`,
     relevant ADRs, research files, prototype branches. The next agent reads the
     artifacts; a handoff that restates them creates a second source that drifts.
   - **What is not durable yet**: anything that lives only in this conversation and
     matters, capture it *into its home* now (a note on the issue, a decision
     record), then reference it. If you cannot name a home for it, say so plainly.
   - **Suggested skills** for the successor: which quarry skills the next phase
     needs (implement, diagnosing-bugs, …).
   - **How to resume memory**: tell the successor to ask Ask_Knowledge about this
     session's topics; the seal in step 1 is their access.
4. **Redact**: no tokens, credentials, or personal data. The doc crosses contexts;
     assume it will be pasted somewhere dumb.
5. **Deliver**: the path, plus one sentence of what the successor should do first.

## Rules

- Reference, never duplicate. A handoff doc that contains a full copy of the spec is
  a spec with a second, drifting body.
- No file paths that go stale if avoidable; issue ids and artifact names instead.
- After handing off, stop working, two agents on one unclaimed ticket is worse than
  one.

## Routes

**From** any boundary where the successor is a different context · **To** the successor resumes from artifacts + `Ask_Knowledge`
**Alternates** `/clear` when the durable artifacts alone carry the next phase, no doc needed
**Lost** `/quarry:workflow`

