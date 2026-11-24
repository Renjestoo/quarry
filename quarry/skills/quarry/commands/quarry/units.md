---
description: List the project's sealed memory units
---

Run:

```
"$QUARRY_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/quarry.py" list
```

Present one line per sealed unit: id, preserved line count, and the request that opened
it. If the user asks what a unit contains, follow up with `Ask_Knowledge`: reading a
unit whole defeats the point of recall; search it instead.

If there are no units yet, say when the mesh will start (first PreCompact or manual
`/quarry:seal`) and stop.
