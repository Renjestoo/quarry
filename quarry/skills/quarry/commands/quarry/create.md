---
description: Create a bd issue, linking it to the work it came from
argument-hint: "<title> [--type <see TRACKER.md>] [--priority 0-4] [--parent <epic-id>]"
---

Create the issue: `bd create $ARGUMENTS`. The first argument is the title; treat any
further flags the user passed as bd flags. Infer sensible defaults: bugs found mid-task
get `-t bug`, ideas get `-t task` or `-t feature` by scope, nothing gets P0 without the
user saying so.

The type list is not repeated here. TRACKER.md's working set is the one place quarry
restates it, and a partial copy in an argument hint is how the last stale type list
started; `bd types` prints the live one.

**Discovery rule**: if you are working an issue right now and this new issue came out of
that work (a bug you hit, a TODO you found, a question you had to park), add
`--deps discovered-from:<current-issue-id>` so the graph keeps its provenance.

Then judge the edges:

- Does the new issue **block** current work? Say so and offer the `blocks` edge.
- Is it **blocked by** something? Offer that edge too.
- No relation? Leave it unconnected.

Use the project's `CONTEXT.md` vocabulary in the title. Report the new id and where it
sits in the graph (`bd dep tree <id>` if it has edges).
