---
name: prototype
description: "Throwaway code that answers exactly one design question, on a throwaway branch, with the answer folded back into the real code or spec. Use when a decision needs the feel of a thing ('will this interaction work?', 'is this state machine right?'), or before committing to an interaction or a data shape."
metadata:
  short-description: "Throwaway code answering one design question"
---

# Prototype

A prototype exists to answer **one design question**. State the question before
writing a line: "does a single-file reducer make the scheduling rules legible to a
non-programmer?" If you cannot state the question, you are not prototyping, you are
building the feature badly.

## Branches by question

**LOGIC**: the question is about rules, state, or flow:

- One self-contained HTML file: the reducer/state machine in plain JS, no build step,
  no dependencies, opens from disk.
- Free-play controls (every action is a button) plus 2–4 guided scenarios that walk
  the interesting paths.
- Built to be *read* by the person deciding: a non-developer must be able to open it,
  click, and see the rules behave.

**UI**: the question is about layout or hierarchy:

- 3–5 structurally different variants of the one route in question (`?variant=N`,
  floating switcher). Different *structure* (arrangement, hierarchy, density), not
  five themes of the same page.

## Method

1. State the question; write it at the top of the file.
2. `git switch -c prototype/<slug>` from a clean base. The branch is the boundary,
   no prototype touches a shared branch.
3. Build the smallest thing that answers it. Ugly is fine; wrong-but-fast beats
   polished-but-unasked.
4. **Answer the question explicitly**: a paragraph, in the prototype file and to the
   user: what the prototype showed, and what it decides.
5. **Fold the answer back**: the decision lands in the grilling session / spec /
   ADR. If the prototype produced a snippet that encodes the decision better than
   prose (state machine, schema, type shape), it may be inlined into the spec,
   trimmed to the decision-rich part and marked prototype-sourced.
6. **Keep the branch** as the primary source (do not merge, do not delete): a later
   question can resume from it. Note its name in the decision's trail
   (`discovered-from`-style provenance on the bd issue it served).

## Rules

- One question per prototype. A second question is a second prototype.
- Never refactor toward production on the prototype branch; the temptation to "just
  finish it" is the failure mode this skill exists to prevent.
- No secrets, no real customer data in prototypes; they end up attached to decisions
  and shown to people.

## Routes

**From** inline, `grilling`, `wayfinder` prototype tickets · **To** the answer folds back into the deciding session; the branch stays as primary source
**Alternates** `research` when the question is settled by facts rather than feel
**Lost** `/quarry:workflow`

