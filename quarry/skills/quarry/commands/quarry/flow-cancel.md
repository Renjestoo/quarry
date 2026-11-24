---
description: Release the pinned workflow lane, or report which one is pinned
---

Release the pin:

```
"$QUARRY_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/quarry.py" flow --cancel
```

Report the current lane without changing it:

```
"$QUARRY_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/quarry.py" flow
```

Tell the user which lane was released, or that none was pinned. Both commands exit 1 when
nothing is pinned, which is a fact rather than a failure.

## When to release

- **The work is done**, and the lane ran to its end.
- **The work belongs to another lane.** Say which one and why before releasing, then pin
  that lane deliberately. Silently drifting is what the pin exists to prevent, and
  releasing without saying why is the same drift with an extra step.
- **The lane is wrong for this project.** That is worth recording, not just undoing.

## What this does not do

It does not undo work, close issues, or touch the tracker. The pin is only a constraint on
which route the agent may take; releasing it returns every route, nothing more.

For a single departure without giving up the lane, the user writes `flow override` in
their own message. That is per-turn and cannot be granted by the agent, so it is never a
substitute for cancelling when the lane is genuinely finished.
