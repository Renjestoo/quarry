---
name: code-review
description: "Two-axis review of the changes on the current branch: Standards (repo-documented rules plus a fixed smell baseline) and Spec (faithfulness to the originating bd issue), run as two independent passes and reported separately. Use when the user asks for a review of the current branch, or before closing a ticket that changed code."
metadata:
  short-description: "Two-axis review: Standards and Spec"
---

# Code review

Two axes, two independent passes (dispatch them as parallel sub-agents when the diff
is nontrivial), never merged: a finding that is fine on one axis and wrong on the
other must not average away.

The diff under review: `git diff <fixed-point>...HEAD`: the fixed point is where the
ticket's branch started. Confirm it with the user if ambiguous. When the repo has a
graft atlas, run `graft blast --base <fixed-point>` first: the blast radius is the
reviewer's map of everything the diff can affect, and findings outside it are where
surprises hide.

## Axis 1: Standards

What this repository has written down governs first:

1. Repo-documented standards: `CONTEXT.md`, ADRs, `CLAUDE.md`/`AGENTS.md`, lint and
   type configuration, and visible conventions of the touched files.
2. The fixed baseline (report only what is actually present in the diff):
   duplicated logic that should be one module; a function doing two jobs; boolean
   parameters that fork behavior; magic numbers with units; swallowed or re-raised
   exceptions losing context; tests coupled to implementation; missing error paths at
   boundaries; dead code the change leaves behind; unearned complexity, meaning an
   abstraction, layer, indirection, configuration knob, piece of infrastructure or
   extensibility point that no current requirement, no second use today and no
   architectural boundary asks for; naming that contradicts the glossary.

Unearned complexity is judged by the removal test rather than by taste: remove it, then
name the stated requirement that becomes impossible, unsafe, incorrect, or materially
harder to maintain. Nothing named means it comes out. The law is the quarry skill's; this
axis is only where a diff meets it.

Each finding: severity, file:line, what is wrong, the minimal fix. Praise nothing,
summarize nothing, findings only.

## Axis 2: Spec

Faithfulness to the originating issue. Pull `bd show <id> --long` for the ticket the
branch implements:

- Does every acceptance criterion have a corresponding observable change in the diff?
- Does anything in the diff go beyond the ticket: an adjacent improvement taken because
  the file was open, or a subsystem redesign entered while chasing the root cause? Silent
  scope growth is flagged even when the work is good.
- Does the implementation contradict an Implementation Decision or an ADR?
- Do test names and new terms use the glossary's vocabulary?

## Report

```
## Standards axis
- [P1] <file>:<line>, <what> → <minimal fix>

## Spec axis
- <criterion>: satisfied | missing | contradicted (where)

## Verdict
clean | fix-first (blockers) | blocked-on-spec (list)

## Parked
- <what>, <file>:<line>
```

Sort every finding of both axes before the verdict. A finding is a **blocker** only when
an acceptance criterion is missing or contradicted, the epic's goal check fails, or the
diff contains a destructive, outward-facing or credential-bearing action. Every other
finding is **parked**, whatever its severity: list it under `Parked`, and add each one as a
line to the epic's parking list (the quarry skill's TRACKER resource, "Discovery pattern").
A parked finding gets no ticket.

The verdict `clean` requires no blocker. Only blockers go back to implement, with the
finding attached. Do not fix during review; reviewing and fixing in the same pass hides the
second look. Review the same work two times at most: when the second review still finds a
blocker, the verdict is `blocked-on-spec`, and a person decides.

## Routes

**From** `implement` (its review step) · **To** blockers return to `implement`; a clean verdict closes the ticket
**Alternates** `improve-codebase-architecture` when the findings are systemic rather than diff-local
**Lost** `/quarry:workflow`

