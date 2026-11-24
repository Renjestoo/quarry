---
description: "Seal the current session into the mesh now: locates it by session id, newest file only as a fallback; sealed units land in .quarry/units"
argument-hint: "[rare override: path to a specific session transcript to preserve from]"
---

Sealing is normally automatic (PreCompact / prompt-submit hooks). Seal manually when
the user asks, or before ending a session that produced decisions worth preserving
verbatim.

**No arguments**: run the engine's `seal` with no flags. It locates the session by asking
for an exact id first and guessing only when it must, in this order: the ZCode session env
id (`~/.zcode/cli/rollout/model-io-sess_*.jsonl`), then Claude Code's own
`CLAUDE_CODE_SESSION_ID`, which names this session exactly and so is immune to a subagent
or a second window writing more recently, then the newest transcript **for this project**
(`~/.claude/projects/<mangled-project-path>/*.jsonl`), and last the newest Codex rollout
whose recorded cwd is this project (`~/.codex/sessions/**/*.jsonl`). Newest-by-time is the
fallback for when no id is in the environment, never the rule. Output names which source it
sealed, so a fallback is visible rather than silent, and sealing never crosses projects: if
no host has a session for this one, nothing is sealed and the note says why.

```
"$QUARRY_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/quarry.py" seal
```

**With a path** (the rare override, for preserving a specific old session file): pass
it as `--transcript`, `--rollout`, or `--zcode-session <id>`. Sealed units are always
written to the project's `.quarry/units/`: a path argument only ever says what to
read from.

Then run the `units` command's listing and report: which unit was created (or that
the session had nothing new), its line count, and what its opening line was. Remind
the user that `.quarry/` belongs in version control.
