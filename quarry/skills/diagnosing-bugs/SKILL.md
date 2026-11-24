---
name: diagnosing-bugs
description: "Six-phase bug discipline that starts by building a tight, red-capable, deterministic feedback loop before any theorizing. Use on any bug that is not instantly obvious, when a failure needs reproducing before it can be fixed, or when a hunt has started to wander."
metadata:
  short-description: "Feedback loop first, then hypotheses"
---

# Diagnosing bugs

The core move is phase 1, and skipping it is why bug hunts wander: **build the
feedback loop before theorizing.**

## Phases

1. **Feedback loop.** A command that (a) exercises the bug, (b) fails red while the
   bug exists, (c) passes green when it is fixed, (d) is deterministic (no sleeps, no
   network order, no flakiness, freeze time, seed randomness, isolate the fs), (e)
   runs in seconds, (f) an agent can run unattended. If it needs a human in the loop,
   script the human's part (prompt-and-capture loop, recorded responses). No loop, no
   diagnosis, only guessing with extra steps.
2. **Reproduce and minimize.** Shrink to the smallest input that still fails red.
   Every fact removed from the repro is a hypothesis eliminated. With a graft atlas,
   locating code is its job, not your grep's: `graft grep "<pattern>"` groups hits by
   enclosing symbol, and `graft callers <symbol>` (`-d 2`) traces who feeds whom,
   two of the classic "where does this even come from" hypotheses, answered in one
   command each.
3. **Hypotheses.** 3–5, ranked by likelihood × cheapness to test. Each must be
   *falsifiable by the loop*, "maybe cosmic rays" is not a hypothesis. Write them
   down before testing any (with the plan-the-backward-tree mindset: which
   hypothesis, if true, would explain the most).
4. **Instrument.** Test the ranked hypotheses with the cheapest probe each needs,
   one log line, one breakpoint, one bisect run. Bisect when the loop can date the
   breakage: ~log₂(commits) probes. One probe at a time; adjust ranks after each.
5. **Fix at the seam.** The fix lands where the tdd skill puts tests: an observable
   boundary. The loop from phase 1 becomes the regression test. A fix that cannot
   become a test means no seam exists, if you add one, fine; if the area resists
   seams entirely, that is an improve-codebase-architecture finding: file it
   (`bd create ... discovered-from:<this bug>`).
6. **Cleanup and post-mortem.** Remove instrumentation. Write the post-mortem where
   it survives: the close reason gets one paragraph (root cause, why the tests missed
   it, the guard added); a surprising, hard-to-reverse lesson becomes an ADR.

## Redaction

Logs, screenshots, and repros you paste anywhere are scrubbed first: tokens,
credentials, personal data, customer names. No exceptions, including inside
sub-agent prompts.

## Rules

- Never fix during phases 1–4. A fix without a diagnosis is a hypothesis wearing a
  commit message.
- Never mark a bug closed that cannot fail red in someone's CI.
- In yolo mode, hypothesis-ranking judgment calls may go to the answer agent; the
  human-only gate is "ship the fix or not" on anything outward-facing.

## Routes

**From** "something is broken" (entry) · **To** the fix lands via `implement`/`tdd` at a seam; `improve-codebase-architecture` when no seam exists
**Alternates** `triage` when the bug arrived from outside and needs the label machine first
**Lost** `/quarry:workflow`

