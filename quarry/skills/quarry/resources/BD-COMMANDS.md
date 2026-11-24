# bd command reference

The block below is what `/quarry:setup` installs into a project's `CLAUDE.md` and
`AGENTS.md`, carrying its own opening and closing HTML comment markers with it. Those
markers sit outside bd's `BEGIN BEADS INTEGRATION` block, which bd regenerates from a
content hash, so an edit inside bd's block would be overwritten and an edit inside
quarry's is not.

Nothing above this line is installed, and the marker text appears exactly twice in this
file, once to open the block and once to close it. An installer that finds the block by
searching for its markers depends on that.

Install or refresh it by re-running `/quarry:setup`. Update the text here, never in the
installed copies: they are generated from this one.

<!-- BEGIN QUARRY BD REFERENCE -->
## bd command reference

Transcribed from `bd --help` on bd 1.0.3. There is no beads MCP server; every bd operation goes
through this CLI. Per-command flags and options are read with `bd <command> --help`.

### Global flags

Accepted by every command.

| Flag | Effect |
|---|---|
| `--actor <string>` | Actor name for the audit trail. Defaults to `$BEADS_ACTOR`, then git `user.name`, then `$USER`. |
| `--db <string>` | Database path. Defaults to auto-discovery of `.beads/*.db`. |
| `--dolt-auto-commit <off\|on\|batch>` | Dolt auto-commit policy. `on` commits after each write. `batch` defers to `bd dolt commit`, keeping uncommitted changes in the working set; SIGTERM and SIGHUP flush pending batch commits. Default `off`. Config key `dolt.auto-commit`. |
| `--global` | Use the global shared-server database `beads_global`. |
| `-h`, `--help` | Help for the command. |
| `--json` | Output in JSON format. |
| `--profile` | Generate a CPU profile for performance analysis. |
| `-q`, `--quiet` | Suppress non-essential output, errors only. |
| `--readonly` | Block write operations, for worker sandboxes. |
| `--sandbox` | Disable auto-sync. |
| `-v`, `--verbose` | Verbose/debug output. |
| `-V`, `--version` | Print version information. |

### Working with issues

| Command | Purpose |
|---|---|
| `assign` | Assign an issue to someone |
| `children` | List child beads of a parent |
| `close` | Close one or more issues |
| `comment` | Add a comment to an issue |
| `comments` | View or manage comments on an issue (`add`) |
| `create` | Create a new issue, or batch from markdown/graph JSON |
| `create-form` | Create a new issue using an interactive form |
| `delete` | Delete one or more issues and clean up references |
| `edit` | Edit an issue field in `$EDITOR` |
| `gate` | Manage async coordination gates (`add-waiter`, `check`, `create`, `discover`, `list`, `resolve`, `show`) |
| `label` | Manage issue labels (`add`, `list`, `list-all`, `propagate`, `remove`) |
| `link` | Link two issues with a dependency |
| `list` | List issues |
| `merge-slot` | Manage merge-slot gates for serialized conflict resolution (`acquire`, `check`, `create`, `release`) |
| `note` | Append a note to an issue |
| `priority` | Set the priority of an issue |
| `promote` | Promote a wisp to a permanent bead |
| `q` | Quick capture: create an issue and output only the ID |
| `query` | Query issues using a simple query language |
| `reopen` | Reopen one or more closed issues |
| `search` | Search issues by text query |
| `set-state` | Set operational state, creating an event and updating the label |
| `show` | Show issue details |
| `state` | Query the current value of a state dimension (`list`) |
| `tag` | Add a label to an issue |
| `todo` | Manage TODO items, a convenience wrapper for task issues (`add`, `done`, `list`) |
| `update` | Update one or more issues |

### Views and reports

| Command | Purpose |
|---|---|
| `count` | Count issues matching filters |
| `diff` | Show changes between two commits or branches |
| `find-duplicates` | Find semantically similar issues using text analysis or AI |
| `history` | Show version history for an issue |
| `lint` | Check issues for missing template sections |
| `stale` | Show stale issues, not updated recently |
| `status` | Show issue database overview and statistics |
| `statuses` | List valid issue statuses |
| `types` | List valid issue types |

### Dependencies and structure

| Command | Purpose |
|---|---|
| `dep` | Manage dependencies (`add`, `cycles`, `list`, `relate`, `remove`, `tree`, `unrelate`) |
| `duplicate` | Mark an issue as a duplicate of another |
| `duplicates` | Find and optionally merge duplicate issues |
| `epic` | Epic management commands (`status`) |
| `graph` | Display the issue dependency graph (`check`) |
| `supersede` | Mark an issue as superseded by a newer one |
| `swarm` | Swarm management for structured epics (`create`, `list`, `status`, `validate`) |

### Sync and data

| Command | Purpose |
|---|---|
| `backup` | Back up the beads database (`init`, `remove`, `restore`, `status`, `sync`) |
| `branch` | List or create branches |
| `export` | Export issues to JSONL format |
| `federation` | Manage peer-to-peer federation with other workspaces (`add-peer`, `list-peers`, `status`, `sync`) |
| `import` | Import issues from a JSONL file or stdin into the database |
| `restore` | Restore full history of a compacted issue from Dolt history |
| `vc` | Version control operations (`commit`, `merge`, `status`) |

### Setup and configuration

| Command | Purpose |
|---|---|
| `bootstrap` | Non-destructive database setup for fresh clones and recovery |
| `config` | Manage configuration settings (`apply`, `drift`, `get`, `list`, `set`, `set-many`, `show`, `unset`, `validate`) |
| `context` | Show effective backend identity and repository context |
| `dolt` | Configure Dolt database settings |
| `forget` | Remove a persistent memory |
| `hooks` | Manage git hooks for beads integration |
| `human` | Show essential commands for human users |
| `info` | Show database information |
| `init` | Initialize bd in the current directory |
| `kv` | Key-value store commands |
| `memories` | List or search persistent memories |
| `onboard` | Display a minimal snippet for an agent instructions file |
| `prime` | Output AI-optimized workflow context |
| `quickstart` | Quick start guide for bd |
| `recall` | Retrieve a specific memory |
| `remember` | Store a persistent memory |
| `setup` | Set up integration with AI editors |
| `where` | Show the active beads location |

### Maintenance

| Command | Purpose |
|---|---|
| `batch` | Run multiple write operations in a single database transaction |
| `compact` | Squash old Dolt commits to reduce history size |
| `doctor` | Check and fix beads installation health, the place to start |
| `flatten` | Squash all Dolt history into a single commit |
| `gc` | Garbage collect: decay old issues, compact Dolt commits, run Dolt GC |
| `migrate` | Database migration commands |
| `ping` | Check database connectivity |
| `preflight` | Show the PR readiness checklist |
| `prune` | Delete old closed beads to reclaim space and shrink exports |
| `purge` | Delete closed ephemeral beads to reclaim space |
| `rename-prefix` | Rename the issue prefix for all issues in the database |
| `rules` | Audit and compact Claude rules |
| `sql` | Execute raw SQL against the beads database |
| `upgrade` | Check and manage bd version upgrades |
| `worktree` | Manage git worktrees for parallel development |

### Integrations and advanced

| Command | Purpose |
|---|---|
| `admin` | Administrative commands for database maintenance |
| `ado` | Azure DevOps integration commands |
| `github` | GitHub integration commands |
| `gitlab` | GitLab integration commands |
| `jira` | Jira integration commands |
| `linear` | Linear integration commands |
| `mail` | Delegate to a mail provider, for example `gt mail` |
| `notion` | Notion integration commands |
| `repo` | Manage multiple repository configuration |

### Other

| Command | Purpose |
|---|---|
| `audit` | Record and label agent interactions, append-only JSONL |
| `blocked` | Show blocked issues |
| `completion` | Generate the autocompletion script for a shell |
| `cook` | Compile a formula into a proto, ephemeral by default |
| `defer` | Defer one or more issues for later |
| `formula` | Manage workflow formulas |
| `help` | Help about any command |
| `init-safety` | Explain `bd init` flag semantics and the destroy-token format |
| `mol` | Molecule commands, work templates |
| `orphans` | Identify orphaned issues, referenced in commits but still open |
| `ready` | Show ready work: open, no active blockers |
| `rename` | Rename an issue ID |
| `ship` | Publish a capability for cross-project dependencies |
| `undefer` | Undefer one or more issues, restoring them to open |
| `version` | Print version information |

### Things that are not obvious

- **`bd list --json` omits empty keys.** A field missing from one row does not mean bd has
  no such field. Check `bd export` or `bd show` on a row that should carry it.
- **`bd show --json` returns an array**, not an object, even for one issue.
- **`bd ready` defaults to `--limit 10`.** A count that disagrees with a dashboard is
  usually this, not a defect.
- **`bd edit` opens `$EDITOR` and will hang an agent.** Use `bd update` instead.
- **`bd batch`** runs several writes in one transaction, which is how to avoid paying
  process startup per write in a loop.
- **`bd sql` bypasses the storage layer**, and bd says so. Acceptable for a read-only
  `SELECT` while debugging, wrong for writes.
- **Writes go through the CLI, never the database file or the JSONL export.**
  `.beads/issues.jsonl` is an export, not the source of truth.

`bd prime` stays the live source of truth for workflow syntax; this table is a map of what
exists, so nobody has to guess whether a command is there.
<!-- END QUARRY BD REFERENCE -->
