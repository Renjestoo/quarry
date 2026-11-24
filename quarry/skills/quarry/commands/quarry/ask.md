---
description: Ask the project's sealed history one plain-language question
argument-hint: "<question>"
---

Call the `Ask_Knowledge` MCP tool with the question `$ARGUMENTS`.

If the tool is unavailable, fall back to the CLI, same engine, same guarantees:

```
"$QUARRY_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/quarry.py" ask "$ARGUMENTS"
```

Present the result faithfully:

- **Passages**: show them verbatim with their addresses (`K1:12-18`). When it matters,
  quote rather than paraphrase; the passage is the truth source.
- **Empty result**: report the terms it tried, and ask yourself whether the project
  would have used different words (a name, a file, a decision). If yes, ask once more
  with those words before concluding the history does not cover it.

Never fabricate a passage. If nothing was found, say so.
