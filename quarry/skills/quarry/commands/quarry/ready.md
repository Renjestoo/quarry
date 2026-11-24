---
description: Show unblocked work from the bd tracker (the ready queue)
argument-hint: "[--json]"
---

Run `bd ready $ARGUMENTS`.

Present the frontier to the user: each ready issue with id, priority, and title, sorted
by priority. If a claimed issue is in progress, mention it first (`bd list --status
in_progress`).

Then recommend the next move:

- User wants to drive: suggest `/quarry:show <id>` on the highest-priority issue.
- User wants autonomy: offer to dispatch the quarry task agent on the queue.

If nothing is ready, run `bd blocked` and show what the blockers are instead.
