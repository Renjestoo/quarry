---
description: Show full context for one bd issue
argument-hint: "<id>"
---

Run `bd show $1 --long` (if $1 is empty, run `bd ready` and ask which issue).

Present the issue's description (what), design (how), acceptance criteria (done),
status, priority, dependencies, and notes.

If the notes reference decisions or history your context does not hold, or the issue
says "as discussed", "per the conversation", or similar, call `Ask_Knowledge` with a
plain-language question about it and present the passages verbatim with their
addresses. Never summarize what you cannot see; quote it or say it is not recoverable.

Finish with the next action: claim it (`bd update <id> --claim`), or block it, or
dispatch the task agent.
