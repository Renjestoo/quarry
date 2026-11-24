# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

The repository is a local Claude plugin marketplace (`.claude-plugin/marketplace.json`)
that ships one plugin, `quarry/`. Read `quarry/README.md` for the full design: four homes
for state (decisions in files, work in bd, history in the sealed mesh, code in the graft
atlas) and the lifecycle skills on top.

Work is complete when it is committed. Push only when the owner asks for it.

The public repository is `Renjestoo/quarry` on GitHub. Its history starts at one clean
commit, on the local branch `public` (remote branch `main`). Push only that branch. Never
push a branch that holds the history from before that commit: those commits hold private
project state.

## Build & Test

There is no test suite. The quality gates are lint, the version check, and a real run of
the engine. No git hook runs them: run them before each commit.

```bash
python -m ruff check .                 # lint, config in ruff.toml and quarry/ruff.toml
python scripts/check_version.py        # version agrees in all 6 places
python quarry/scripts/quarry.py <cmd>  # engine CLI: init, seal, ask, list, mcp, dashboard,
                                       # stop, url, flow, behaviour, hook, guard, doctor,
                                       # drive, delete-epic, install
```

`quarry/scripts/checks/` holds the engine's check scripts. `quarry/README.md` says what each
one checks and which runs cost a real Claude turn.

## Architecture Overview

- `quarry/.claude-plugin/`, `.codex-plugin/`, `.zcode-plugin/`: one manifest per host. The
  Claude manifest declares the hooks inline; `quarry/hooks/codex-template.json` is the
  Codex hook file. Hosts get different hook coverage (README "Compatibility").
- `quarry/scripts/quarry.py` + `quarry/scripts/quarry_lib/`: the stdlib-only engine. Hooks,
  the `Ask_Knowledge` MCP server (`mcp_server.py`, stdio JSON-RPC), sealing (`store.py`,
  `MeshStore`), recall (`ask.py`) and the driver (`driver.py`) all enter through `quarry.py`.
- `quarry/webapp/`: the dashboard. `server.py` serves the static UI in `static/`;
  `tracker.py` runs `bd` for every read and write, it never touches the database.
- `quarry/skills/`, `quarry/agents/`: the lifecycle skills and the task and answer agents.
- `scripts/check_version.py`: the version gate of the repository, not part of the plugin.
- `README.md`, `assets/`: the GitHub page of the repository (banner, logo, install steps,
  credits). `quarry/README.md` is the design reference.
- `quarry/ruff.toml` is not a duplicate of the root file: it makes `quarry/` the lint root,
  so ruff sorts `webapp` and `quarry_lib` as first-party imports.
- `graft/`: the code atlas, a local cache that `graft build` regenerates. Not committed.

## Conventions & Patterns

- **One version, six places.** A release bumps the same SemVer string in
  `.claude-plugin/marketplace.json`, the three `quarry/.*-plugin/plugin.json` manifests,
  the `serverInfo` literal in `quarry/scripts/quarry_lib/mcp_server.py`, and
  `quarry/pyproject.toml`. `scripts/check_version.py` lists them.
- **No plugin file names a path on a machine.** Skills and commands use `"$QUARRY_PYTHON"`.
  The Claude hooks and `quarry/.mcp.json` use `${QUARRY_PYTHON:-python}`. The Codex and
  ZCode files name plain `python`. `python` in this file means a Python 3.11 or later.
- **Installing a changed plugin takes two steps.** Copying files into the plugin cache does
  not change what Claude loads. Run `claude plugin update quarry@renjestoo`, then restart
  the host, and check the version in the registry entry.
- **Hook failures never interrupt the host.** Report on stderr and continue; a failed seal
  must never block a compaction.
- **Sealed units are immutable.** Never edit a `K<n>` file. Retirement rules are in
  `quarry/README.md` "Retention".
- **This repository keeps no project state of its own.** `.quarry/` (a session's sealed
  mesh) is ignored by git here. The decision records (ADRs) were removed with the project
  history; their text is in git history at commit `1c20893`.
