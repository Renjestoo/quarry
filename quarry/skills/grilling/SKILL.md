---
name: grilling
description: "The interview primitive: relentlessly question an idea as a design tree worked in rounds, separating facts (looked up by sub-agents) from decisions (answered by the user, or by the answer agent in yolo mode). Use when shaping a new feature, before writing a spec, when an idea is vague, or when the user says 'grill me', 'interview me', or 'question this idea'."
metadata:
  short-description: "Interview an idea into recorded decisions"
---

# Grilling

Decisions as a design tree, worked in rounds. Each round asks only the questions whose
prerequisites are already settled (the frontier); answers re-shape the tree; repeat
until the frontier is empty.

**The split that makes it work**: facts vs decisions.

- **Facts** (what the code does, what a library supports, what the spec says) are
  looked up, never asked. Dispatch a sub-agent to read the source or docs and bring
  back the answer. Asking the user a fact is an interrogation failure.
- **Decisions** (trade-offs only the project owner can settle) are asked, one
  numbered question at a time, each with a recommended answer and one line of why.

## Mode

Read `docs/agents/quarry.md` first. In `yolo`, decision questions go to the answer
agent (question + recommended answer + the user's original description); record its
DECISION as if the user gave it and collect NEEDS HUMAN questions for one batched
escalation. In `interactive`, ask the user directly.

## Method

1. State the idea under examination in one sentence. If it cannot be stated, that is
   question 1.
2. Build the design tree: root = the idea; children = the decisions it depends on;
   leaves = the facts those decisions need. Work at the granularity where a wrong
   answer would change what you build.
3. Each round, present the frontier questions in dependency order:
   `1. <question>? Recommended: <answer>, <one line of why>.`
   Never more than five in a round. Never a question whose parent is unanswered.
4. Dispatch fact sub-agents in parallel while the decisions are being answered.
5. After each round, update the tree: answers collapse branches, open new ones, or
   invalidate previously-settled ones (say so explicitly when they do).
6. **Record as you go** (this is the domain-modeling discipline, running inline): a
   term the project now uses → `CONTEXT.md`; a hard-to-reverse, surprising choice with
   a real trade-off → an ADR and a `bd create --type decision` bead. A decision that
   only lives in the conversation will be re-litigated after compaction; that is the
   failure this whole skill exists to prevent.
7. Before answering any question from memory, check sealed history with Ask_Knowledge
   ("what did we decide about <x>"): the tree may already have been half-climbed in
   an earlier session.

The session is done at whichever exit comes first. **Exhaustion**: the frontier is empty
and every decision is recorded. **Sufficiency**: every question still on the frontier is
below the deliberation threshold, meaning its answer could not change correctness,
security, maintainability, performance, or architecture. A question below that line gets
its recommended answer recorded as the decision and stops being asked; it is not worth a
round, and asking it anyway is how an interview becomes its own purpose. Say which exit
was reached, then point at the next step: synthesize into a tracked spec
(`/quarry:spec`).

## Rules

- One question at a time in yolo mode (the answer agent decides independently); in
  interactive mode, batch by round.
- Every question has a recommended answer. A question without one is an unexplored
  fact, not a decision.
- Stop expanding scope: questions outside what the idea needs to be buildable are
  parked (`bd create --type chore --deps discovered-from:...` or a note), not asked.

## Routes

**From** an idea (entry, or `/quarry:grill`) · **To** `spec` once the frontier empties; `domain-modeling` runs inline while grilling
**Alternates** `research` when a question needs facts, `prototype` when it needs feel, `to-questionnaire` when the answerer is absent, `wayfinder` when the fog outlives the session
**Lost** `/quarry:workflow`

