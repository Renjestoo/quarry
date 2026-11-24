# Harness parts

Quarry works with seven parts: three required parts and four optional companions.
`quarry doctor` reports each one. `quarry install <part>` runs the commands that make a
part ready, and `/quarry:setup` proposes them to the user. Install a part only after the
user chose it.

- **Required** (the lifecycle cannot run without them, and a missing one stops
  `quarry drive`): the lifecycle skills, bd, Trailcode.
- **Optional companions** (a missing one stops nothing): RTK, task-observer, Headroom,
  Graphify.

## What each part does, and how it is used

| Part | What it does | How quarry uses it |
|---|---|---|
| Lifecycle skills (`doctor` prints "Matt Pocock's skills") | The grill, spec, tickets, implement and review skills | Bundled in the plugin. The driver loads skill files into stage prompts. |
| bd | The issue tracker with dependency edges | The engine calls `bd` for each tracker read and write: the dashboard, the driver, the stage checks. |
| Trailcode (`graft`) | A graph of the code: symbols, files, callers | The driver calls `graft ask`. A guard denies a hand search of indexed source. The skills start code work with it. |
| RTK | A host hook that makes shell command output shorter | The engine does not call it. The hook is active in each session, and in each driver stage session. |
| task-observer | A skill that logs corrections and repeated work as skill improvements | Its activation block in `~/.claude/CLAUDE.md` loads it in each session. When a driver stage ends red, the driver writes one observation that names the stage's skills. |
| Headroom | Compression of large content, with retrieval of the original | The engine does not call it. The agent uses its MCP tools. |
| Graphify | A knowledge graph of any input: documents, papers, images, code | The `research` skill keeps a graph of `docs/research/` and queries it before a new dispatch. |

Quarry's code depends on the first three parts. The last four work at the host level:
quarry checks that each one is installed and configured, and this file tells you when to
use it. Two of them get one use by quarry itself when they are present: the driver runs
task-observer's helper for a red stage, and the `research` skill queries Graphify.

## When to use the host-level parts

- **RTK**: no action. For the full output of one command, run `rtk proxy <command>`.
- **task-observer**: follow its activation block. It decides when it logs.
- **Headroom**: when content shows a compression marker and you need the full text, call
  `headroom_retrieve`. Before you put a large paste or log into the conversation, call
  `headroom_compress`.
- **Graphify**: for a body of documents that is not code (research notes, papers, a
  folder of specifications), build a graph with the `graphify` skill and query it. The
  atlas stays the home for code: see [ATLAS.md](ATLAS.md).

## What "ready" means

| Part | Present when |
|---|---|
| Lifecycle skills | The plugin holds the lifecycle skills. |
| bd | `bd --version` answers. |
| Trailcode | `trail --version` or `graft --version` answers. |
| RTK | `rtk --version` answers, and a hook in `~/.claude/settings.json` calls `rtk hook`. |
| task-observer | Its `SKILL.md` has a version, and `~/.claude/CLAUDE.md` holds its activation block. |
| Headroom | `headroom --version` answers, and `headroom mcp status` reports Claude Code as configured. |
| Graphify | `graphify --version` answers, and `~/.claude/skills/graphify/SKILL.md` exists. |

A part that is installed but not configured is `degraded`. `quarry install` then runs only
the configure step.

`doctor` finds a tool on PATH first. It also looks in the folders the installers use:
the uv tool folder for Headroom and Graphify, and the winget links folder and
`~/.local/bin` for RTK. A new install is often not on PATH until the next terminal.

The notice at session start names only the required parts. `/quarry:setup` proposes the
optional companions too.

## Per-repository steps that `quarry install` does not do

- `bd init <prefix>`: a human step, one time for each repository.
- `graft build`: `/quarry:setup` runs it.
