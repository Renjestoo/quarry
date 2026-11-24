---
description: Configure a repository for quarry (tracker, mesh, mode, domain docs)
---

Configure once per repository. Explore first, then present findings with recommended
answers, confirm, then write.

**Checks** (report each):

0. `$QUARRY_PYTHON`: every quarry command in these skills invokes it. Unset means every
   one of them fails, so check it first and stop if it is missing: the host supplies it
   from `settings.json` (`"env": { "QUARRY_PYTHON": "<interpreter>" }`). Any Python 3.11
   or later runs the engine. When it is missing, ask the user which interpreter to use;
   never write the setting without their answer.
1. `bd --version`: v0.60+ required. Missing: do check 7 now, which proposes and installs
   bd, then return here. Stop only when bd is still missing after check 7.
2. `bd info` (or `bd list`): is this repo initialized? If not, `bd init <prefix>` is a
   human step: ask the user to run it (the wizard skill can help).
3. Engine: run
   `"$QUARRY_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/quarry.py" init`
   which creates `.quarry/` (units + mesh.json).
4. **Atlas**: `graft --version`. Present but no `graft/` graph in the repo? Run
   `graft build` (deterministic, no key) and confirm `graft/` is gitignored; the
   atlas is a regenerable cache (see the quarry skill's ATLAS resource). graft absent:
   check 7 proposes it. If the user declines, continue: interactive skill use works
   without an atlas and the skills skip their atlas steps, but `quarry drive` does not run.
5. Codex host? Nothing to copy: the plugin's own manifest declares its hooks, and installing
   it registers them. Confirm with `codex app-server --stdio` and a `hooks/list` request,
   which reports each hook's `pluginId` and `trustStatus`. Codex registers a new plugin's
   hooks as `untrusted` and does not run them until a human trusts them, so tell the user that
   trusting quarry's hooks in Codex is the one step only they can take.
6. **Fleet lock**: ask whether this project will ever run more than one agent at once. If
   yes, `bd merge-slot create` makes the one lock that serialises conflict resolution, and
   it is a per-repository one-time step. If no, skip it: a slot nobody acquires is a bead
   nobody reads. The `parallel-agents` skill covers when to want one.
7. **Harness parts**: propose each part that is not ready, then install the parts the user
   chooses. [PARTS.md](../../resources/PARTS.md) says what each part does.
   1. Run `"$QUARRY_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/quarry.py" doctor` and show its
      output verbatim. When every part is present, go to step 7.
   2. Run `"$QUARRY_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/quarry.py" install --dry-run all`.
      It prints, for each part that is not present, the commands that make it ready and
      the step that stays manual. It runs nothing.
   3. Ask the user one multi-select question: which of these parts to install. For each
      part give its purpose in one line, whether it is required or optional, and the
      commands from step 2. An install is a human gate in both interaction modes: the
      answer agent never decides it.
   4. Run `"$QUARRY_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/quarry.py" install <names>` with
      the names the user chose. A part whose installer program is missing (npm, npx, uv,
      winget, brew, or sh with curl) or whose step fails is reported and skipped: tell the
      user what it needs.
   5. task-observer has one manual step, its activation block. Read "The activation block"
      in `~/.claude/skills/task-observer/references/environments.md`, fill the workspace
      path as that file instructs, show the user the block and the target file, and append
      it to `~/.claude/CLAUDE.md` only on their yes.
   6. Run `doctor` again and show its output. Tell the user to restart the host: hooks,
      skills and MCP servers load when a session starts.
   7. Two parts have wiring for this repository. Ask before each one:
      `graft init --no-statusline` adds graft's own hooks and MCP server
      (`graft init --dry-run` lists every file first), and `graphify claude install`
      adds a graphify section to this project's `CLAUDE.md` with a PreToolUse hook.

   A non-zero `doctor` exit means a required part blocks a harness run (`quarry drive`);
   interactive skill use continues.

**Write `docs/agents/quarry.md`** (create dirs as needed):

```markdown
# Quarry configuration

Interaction mode: interactive

## Triage labels

| Role | bd label |
|---|---|
| needs-triage | `needs-triage` |
| needs-info | `needs-info` |
| ready-for-agent | `ready-for-agent` |
| ready-for-human | `ready-for-human` |
| wontfix | `wontfix` |
```

Ask which interaction mode to seed (default `interactive`; explain yolo; the answer
agent decides, NEEDS HUMAN escalates). Only override the label column if the project
already uses different label strings.

**Seed `CONTEXT.md`** if absent: title plus a `## Vocabulary` section with one starter
term; the project's own name for itself. Do not invent a glossary.

**Leave `CHARTER.md` unwritten**, and say so rather than skipping it in silence. It is the
fourth decision file and the only one setup does not seed, on purpose: an objective needs a
measure that could actually be checked, and a non-goal needs a decision somebody actually
made, and neither exists yet at setup. The reasoning that seeds `CONTEXT.md` with one real
term rather than a glossary applies harder here, and `/quarry:charter` puts it plainly, do
not invent objectives to make the board look organised. Tell the user the file is theirs to
write when the first outcome or the first deliberate exclusion is real, and that
`/quarry:charter` says what goes in it. Until then the board reports the project as having
no charter, which is true rather than a gap.

**Install the bd reference** into `CLAUDE.md` and `AGENTS.md` (create either if absent,
with a one-line title). Copy the block between the `QUARRY BD REFERENCE` markers in
[BD-COMMANDS.md](../../resources/BD-COMMANDS.md), markers included, and append it. If the
markers are already present, replace what is between them instead of appending a second
copy. Keep the block outside any `BEGIN BEADS INTEGRATION` markers: bd regenerates that
block from a content hash (`bd setup claude`, `bd setup codex`) and would overwrite an
edit made inside it. Report which files were written and whether it was an install or a
refresh.

**Finish** with a one-screen summary: what was configured, what remains human (bd init
if skipped), and the suggested first command (`/quarry:grill <idea>` for a new effort,
`/quarry:ready` to resume).
