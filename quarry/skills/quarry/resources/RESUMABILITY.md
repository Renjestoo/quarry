# Resuming cold

How any quarry session picks up exactly where the last one left off, after compaction,
after `/clear`, after a weekend.

## Cold-start protocol

1. **Read the injected index** (SessionStart hook): one line per sealed unit, what
   survived. No index: nothing is sealed yet; the mesh starts at the first
   `/quarry:seal` or PreCompact.
2. **`bd ready`**: the frontier. `bd list --status in_progress` if you were mid-work.
3. **Ask_Knowledge before re-deciding.** The trap of a cold start is re-litigating a
   settled question because you cannot see that it was settled. Ask first:
   "what did we decide about <x>".
4. **`bd show <id> --long`** for the issue you resume: description (what), design
   (how), acceptance criteria (done), notes (where you left off).
5. **Read `CONTEXT.md` and the ADRs touching the area** before exploring code; the
   glossary prevents rediscovering the domain from scratch.

**All five steps are read-only, and that is the rule rather than a coincidence.**
Reconnaissance ends when you state your position; creating, editing, claiming, closing,
labelling or linking an issue is not part of it. This outranks `bd prime`, which arrives in
the same injection and says to file an issue before writing code: that is right once you
know what the work is, and wrong in the minute when you know least. A ticket filed during
recon is usually a duplicate of one the queue already holds, or a decision the mesh already
settled, and it costs more to find and merge than it saved.

## Notes are the handoff

The `notes` field of an in-progress issue is written for a successor with zero context,
and it is **overwritten, never appended**: stale detail is worse than missing detail:

```
COMPLETED: <verified outcomes>
IN PROGRESS: <current focus>
NEXT: <the immediate next action, concrete enough to execute without guessing>
BLOCKER: <what is stuck and why, or "none">
KEY DECISION: <decisions a successor must not re-litigate>
```

Update the notes at every natural pause and before ending work on the issue. Notes are
compaction insurance: they are the difference between resuming and reconstructing.

For complex technical work, add an implementation guide to the notes:

```
IMPLEMENTATION GUIDE
Working code: <the current state, as code or precise description>
API response samples: <real responses, not idealized>
Desired output format: <what "done" looks like on the screen or wire>
Research context: <what was already tried and eliminated>
```

## The three-way check

When a cold session is about to act, verify the load-bearing facts against their homes:

| Claim | Verify against |
|---|---|
| "It was decided that…" | an ADR, a decision bead, or Ask_Knowledge returning the passage |
| "This work is ready" | `bd ready`, not memory |
| "This term means…" | `CONTEXT.md`, not inference |

If a check fails, the conversation was the only place it lived, fix the home (write the
ADR, seal the history, claim the term) so the next cold start passes.

## When two homes disagree

The check above assumes the homes agree. When they do not, apply this order rather than
guessing:

1. **Current recorded decisions**: `CONTEXT.md`, `docs/adr/`, `docs/agents/quarry.md`.
   Newer record wins on the same point; a superseding ADR says so in its own text.
2. **Current work contracts and state**: the issue's description, design, acceptance
   criteria, notes, status and edges, and the spec epic behind them.
3. **Sealed history**: evidence of what was said, and when.
4. **The code and the atlas**: what the repo does today.

Sealed history never outranks a current record on the same point, and is never skipped
either: it is how you learn that two records disagree and which came first, so recall
before applying the order. Code is last on intent and first on fact: code contradicting a
recorded decision is a defect to file, not a decision silently reversed.

A conflict that survives the order is a real disagreement, not a lookup problem. Cite both
sources at their addresses and put it to the user; never pick a winner silently.

## When sealing breaks

If `quarry seal` reports a boundary error, the host rewrote its transcript file (line
endings or a rewrite) and the recorded seal offset no longer lands on a record boundary.
The seal refuses rather than seal corrupt evidence, correct behavior. Historical units
stay valid; that source just stops sealing until re-initialized. Delete the source's
entry in `.quarry/mesh.json` progress map (or the whole `.quarry/` if starting over) and
seal again.
