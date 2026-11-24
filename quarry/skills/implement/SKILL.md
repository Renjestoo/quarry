---
name: implement
description: "Execute one ticket end to end in a fresh context: claim it from bd, load its contract and sealed history, build it test-first at the spec's seams, run a two-axis review, and close it with verified reason. Use when the user says 'implement', names a ticket to build, or asks to work the next item in the ready queue."
metadata:
  short-description: "Execute one ticket test-first and close it"
---

# Implement

One ticket, one fresh context window. The ticket is the contract; everything else the
conversation once held is recoverable; that is the point of quarry.

1. **Claim first.** `bd update <id> --claim`. If no id given: `bd ready`, take the
   highest priority, confirm with the user (or in yolo, proceed).
2. **Load the contract.** `bd show <id> --long`: description (what), design (how),
   acceptance criteria (done). Read `CONTEXT.md` and ADRs touching the area.
3. **Load the history.** If the ticket references discussion ("as agreed", "per the
   spec conversation"), Ask_Knowledge it. If a previous session left notes on this
   ticket, they are the starting state, continue, don't restart.
4. **Ask the atlas** (when `graft/` exists, see the quarry skill's ATLAS resource):
   `graft ask "<ticket title>"` for where the work lives, `graft skeleton <file>`
   before reading whole files. The atlas is the map; the ticket is the contract; do
   not explore by hand what the atlas already ranked.
5. **Find the seam.** The spec's Testing Decisions named it. If the seam is missing in
   the code, the tdd skill governs how to add one; if the ticket cannot be tested at
   any seam, that is a `blocked` report, not a heroically-coupled test.
6. **Build test-first** (tdd skill): red, green, refactor, at the seam, never
   around it.
7. **Check the blast radius** (atlas present): `graft blast` on your diff before
   review, surface anything your change touches that the ticket did not name; those
   are discoveries or scope questions, not surprises for the reviewer.
8. **Sort each discovery: blocker or parked** (the quarry skill's TRACKER resource,
   "Discovery pattern"). A discovery is a blocker only when it makes one of this
   ticket's acceptance criteria, or the epic's goal check, fail. A blocker becomes
   `bd create` with `discovered-from:<id>`, a `blocks` edge, and the red check (its
   command and its output) in the description. Every other discovery is one line on the
   epic's parking list: `bd note <parking-list-id> "<what>, <file:line>, found in <id>"`.
   A parked discovery gets no ticket and no fix in this session.
9. **Review** (code-review skill): Standards axis and Spec axis, reported separately.
   Fix the blockers it returns, then rerun. Two review rounds at most: if the second
   round still returns a blocker, set the ticket blocked with the finding and stop.
10. **Close with a reason**: what was done and how it was verified, "tests pass" plus
    the observable check against acceptance criteria. Run the project's checks
    (typecheck, lint, tests) before claiming done.
11. **Leave the trail**: if the work surfaced a decision worth keeping, write the ADR
    now. Update notes only if the ticket stays open.

## Guardrails

- Never work unclaimed; never close incomplete (set blocked with an explanation).
- Never widen the ticket silently. New scope is a discovery, and step 8 sorts it.
- Never fix a parked discovery "while here". It waits on the parking list for retro.
- Before review, run the removal test (quarry skill, least-architecture law) over what
  you added: remove each layer, interface or option and name the acceptance criterion
  that then fails. Anything that survives without one comes out before the diff is read.
- If compaction hits mid-ticket, the notes are the handoff: keep them current.
- In yolo mode, mid-implementation decision points go to the answer agent; NEEDS
  HUMAN stops the line rather than guessing.

## Routes

**From** `tickets` or a `triage` agent brief · **To** `tdd` and `code-review` run inline; close → `bd ready` → the next ticket
**Alternates** the task agent for hands-off runs; `diagnosing-bugs` when the ticket is a live breakage
**Lost** `/quarry:workflow`

