---
name: tdd
description: "Red-green-refactor at pre-agreed seams: write tests against public interfaces, never implementation details, and mock only at system boundaries. Use while implementing any ticket, when writing or reviewing tests, when a test is coupled to implementation detail, or when deciding where a test belongs."
metadata:
  short-description: "Red-green-refactor at pre-agreed seams"
---

# TDD

The loop: **red** (a failing test that states the behavior), **green** (the smallest
change that passes), **refactor** (remove duplication, rename to vocabulary, keep
green). Small steps; run constantly.

## Seams

A seam is a place where behavior is observable and replaceable; a public function's
arguments and return, an HTTP boundary, a CLI's exit code and output, an emitted
event. Tests live at seams:

- The spec names the seam; the implement step found it. Test there, not one layer
  lower (brittle), not one higher (slow, indirect).
- The highest seam that can see the behavior without pain is the right one. Fewer
  seams across the codebase is better; one is ideal.
- A test that reaches past the seam into internals is testing the implementation, and
  it will break on every refactor that preserves behavior. That is a false alarm
  factory, fix the test, not the refactoring.
- A missing seam is a design finding: the behavior has no observable surface. Add the
  seam (small interface, adapter over the boundary), then test at it. If no seam can
  exist, the code is telling you the module boundary is wrong; that is an
  improve-codebase-architecture finding, not a mocking problem.

## What a good test looks like

- States behavior: "retry stops after the cap is reached", not "calls backoff twice".
- Arranges the world, acts once, asserts observably.
- Fails for exactly one reason; the name is the reason.
- Uses `CONTEXT.md` vocabulary; a test name is documentation.
- Prior art: find the closest existing test and match its shape before inventing one.

## Anti-patterns

| Smell | Why it fails |
|---|---|
| Tautological (asserts the mock returns what it was told to return) | verifies setup, not behavior |
| Implementation-coupled (asserts call counts, private state) | breaks every refactor |
| Horizontal (tests each layer separately for one behavior) | N tests for 1 behavior, all brittle |
| Snapshot-of-everything | the failure says nothing, the pass means nothing |

## Mocking

Mock **only at system boundaries**: networks, clocks, filesystems you don't own,
randomness, processes. Everything in-process stays real: real objects, real
calculations. If a test needs a mock for an in-process dependency, the seam is in the
wrong place; move the boundary (ports-and-adapters: an interface the domain owns, an
adapter the test replaces) rather than mocking the call.

Rule: replace, don't layer; the test substitutes the adapter; it does not stack spies
on top of the real one.

## Routes

**From** `implement` (its build step) · **To** return to `implement` green
**Alternates** `diagnosing-bugs` when red for an unknown reason; that is a diagnosis, not a test problem
**Lost** `/quarry:workflow`

