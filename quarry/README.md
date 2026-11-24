# Quarry

An agent plugin for three hosts, with a single thesis: **agent work must survive context
loss.** Seal (evidence, never replaced by a summary) → track (dependency-gated) →
decide (in files) → resume cold.

Durable state is the foundation, not the whole product. On top of it quarry ships an
opinionated development lifecycle: requirements discovery, specification,
dependency-gated tickets, implementation, review, research, prototyping, triage,
autonomous execution, and workflow routing.

Four homes for state, one law each:

1. **Decisions live in files**: `CONTEXT.md` + `docs/adr/`.
2. **Work lives in [bd](https://github.com/gastownhall/beads)**: a dependency-gated
   ready queue; closing a blocker promotes what it blocked.
3. **History lives in the mesh**: transcripts sealed byte-for-byte into immutable,
   line-addressed units (`.quarry/`), recalled verbatim through one tool,
   `Ask_Knowledge`, with deterministic model-free search. Recall searches a derived
   rendering of each unit; the evidence copy it was rendered from stays byte-exact
   (see "Evidence and rendering").
4. **The code lives in the atlas**: a [graft](https://github.com/nanonets/graft)
   graph of the repo, consulted automatically by the skills before hand exploration.
   The atlas answers WHERE things are; `Ask_Knowledge` answers WHAT was said.

The division is the point. Files say what was decided, bd says what work exists and
what is ready, the mesh says what was previously said, and the atlas says where the
code lives. Each answers a question the others cannot, and none substitutes for
another, so an agent holding no conversation at all can still reconstruct enough
authoritative state to keep working.

The four are not equally optional. **bd is the execution substrate**, not an integration
quarry can do without: quarry defines the workflow semantics and bd provides the durable
dependency graph they execute through. A spec becomes an epic, tickets become issues with
`blocks` edges, the graph's frontier is the plan, work is claimed and closed against it,
and closing a blocker is the mechanism that promotes the next work. Without bd there is no
lifecycle, only skills with nowhere to put their output. The atlas is the opposite case:
optional, regenerable, and its absence costs orientation only.

## Authority

### Preserved history is not authoritative state

Sealing and recording a decision do different jobs, and auto-seal does not do the second
one. Sealing preserves what was said, byte for byte, as citable evidence. The
authoritative answer to "what do we do" lives in the files and in bd, which is why every
lifecycle skill promotes a decision out of the conversation and into `CONTEXT.md`, an ADR,
a spec, or tracker state at the moment it is made.

A decision that exists only inside sealed history is recoverable but not authoritative. A
later agent reading a transcript cannot tell a settled conclusion from a suggestion that
was raised and dropped, so it re-litigates. Auto-seal protects you from losing the record;
it does not save you from having to write the decision down where it governs.

### When work becomes durable

"Agent work must survive context loss" is the design principle. The operational contract
is narrower, and worth stating separately, because quarry can only preserve what has
reached a home:

- A **decision** is durable once it is written into `CONTEXT.md`, an ADR, a spec, or a
  ticket field. Said in conversation and nowhere else, it is perishable until the next
  seal, and even then it is evidence rather than authority (see above).
- **Work state** is durable once it exists as a bd issue, with its status, edges and
  notes current. An intention to file a ticket is not a ticket.
- **History** is durable once a unit exists for it. Sealing is incremental, so the tail
  since the last seal is the perishable part, and how large that tail gets depends on the
  host (see Compatibility).
- **Code** is durable when it is committed. Nothing in quarry changes that.

So the guarantee begins at the write, not at the utterance. Three failure modes remain
open by construction, and quarry states them rather than pretending otherwise: a decision
nobody recorded, a seal that failed (hook failures never interrupt the host, so work
continues while new history may be unprotected), and an agent that never wrote its work
state down. The first and third are protocol, which is exactly why they sit in the
protocol list rather than the enforced one.

### When two homes disagree

The same fact can sit in `CONTEXT.md`, an ADR, a spec epic, a ticket's description or
notes, sealed history, and the code at once. A cold-resuming agent needs a precedence, not
just a list of places to look:

1. **Current recorded decisions**: `CONTEXT.md`, `docs/adr/`, `docs/agents/quarry.md`.
   Where two records cover the same point the newer wins, and an ADR that supersedes
   another says so in its own text.
2. **Current work contracts and state**: the bd issue's description, design, acceptance
   criteria, notes, status and edges, plus the spec epic they came from.
3. **Sealed history**: evidence of what was said, and when.
4. **The code and the atlas**: what the repository does today.

Two qualifications keep that order honest. Sealed history never outranks a current record
on the same point, but it is not merely lower either: it is how you find out that two
records disagree and which came first, so consult it before applying the order rather than
after. And the code is last on intent while being first on fact: code contradicting a
recorded decision is a defect to file, never evidence that the decision was reversed.

A conflict that survives the order is a real disagreement, not a lookup problem. Say so,
cite both sources at their addresses, and let the user settle it. Picking a winner
silently is the failure the four homes exist to prevent.

## Lifecycle

On top of the four homes sits the rewritten lifecycle, grill → spec → tickets →
implement → review, shipped as 32 skills, plus on-ramps (triage, bug diagnosis,
wayfinding, research, prototyping) and support skills (handoff, phase workflows,
architecture upkeep, and more).

Each step hands the next a durable artifact rather than a conversation: grilling
records decisions, the spec becomes a bd epic, tickets become the dependency-gated
ready queue, and implement works one ticket against that queue. Nothing in the chain
depends on the previous step still being in context, which is what makes the whole
lifecycle resumable cold.

## Several agents, one tracker

One agent on one ticket in one fresh window is the default, and it is a choice about
context economics rather than a limit of the tracker. bd ships a coordination layer for
fleets, and quarry makes it reachable without making it automatic: swarm molecules over an
epic DAG, the merge slot that serialises conflict resolution so two agents cannot fight
over the same hunk, async gates (human, timer, GitHub run or PR, and cross-project bead
waits), worktrees that share one `.beads/` through git's common directory, the `hooked`
status, and `--readonly` for a worker that may read the tracker but never write it.

Nothing here fires on its own and no guard enforces it. The claim is what actually
coordinates, because `bd update --claim` is atomic, so it rather than etiquette is what
stops two agents taking one ticket. The `parallel-agents` skill is the one home for when
this is worth its cost and how to run it. Sealing is safe under a fleet: it takes an
exclusive lock on the mesh across choosing a unit id, writing the evidence and recording the
unit, so concurrent seals queue rather than race. The dashboard's board carries a **Fleet**
tab beside Kanban and Roadmap showing who holds the merge slot, what waits on a gate, and
each swarm's progress with its ready, active, blocked and completed counts, fetched when the
tab is opened rather than on every poll.

## YOLO mode

Not an interaction style. YOLO transfers decision authority, and the setting lives per
repo in `docs/agents/quarry.md`:

- `Interaction mode: interactive`: questions go to the user, one numbered batch per
  round, each with a recommended answer.
- `Interaction mode: yolo`: question points dispatch the **answer agent**, which
  decides from the user's original description with one line of rationale.

What makes the second a transfer rather than a shortcut: the answer agent's decisions
persist into the same durable artifacts a human answer would, the spec section, the ADR,
the `CONTEXT.md` term, the ticket field. A decision made autonomously is therefore
indistinguishable in the record from one the user made, and a later session will treat it
as settled and build on it. The rationale line and the sealed history are what make it
auditable after the fact; nothing marks it as machine-decided in the artifact itself.

The authority has two edges, and they hold in both modes. A question the description
genuinely cannot answer returns `NEEDS HUMAN` and is batched to the user rather than
guessed. Destructive, outward-facing and credential-bearing actions are human gates
regardless of mode.

Flip anytime with `/quarry:mode yolo|interactive`.

## Requirements

The harness combines seven parts. `quarry doctor` probes each one and prints
one line per part: required or optional, present, absent or degraded, its version, and for
a part that is not present the reason and the install command. `doctor` itself installs
nothing. It exits 1 when a required part is absent or degraded, and 0 otherwise, so a
missing optional part never fails it.

Three things bring a missing part to the user:

- **At session start** the hook names the required parts that are not ready and points to
  `/quarry:setup`. This check runs no program, so it does not slow the start. It leaves
  out the optional parts, so a user who declined one is not told again each session.
- **`/quarry:setup`** shows the `doctor` report, proposes each part that is not ready with
  its commands, and asks which ones to install.
- **`quarry install <part>...`** runs the install and configure commands of the chosen
  parts, then probes each part again. `--dry-run` prints the commands and runs nothing.
  `all` selects each part that is not present. It needs the installer of each part on
  PATH (npm, npx, uv, and for RTK winget, brew, or sh with curl) and says which one is
  missing. A tool that its installer puts outside PATH is still found: the uv tool folder
  for Headroom and Graphify, the winget links folder and `~/.local/bin` for RTK.

An install is a human gate. Setup asks in both interaction modes, and in a driver session
the gate guard denies `quarry install`.

| Part | For a harness run | How the probe finds it |
|---|---|---|
| Matt Pocock's skills | required, bundled | the plugin's own `skills/`, which must hold the lifecycle skills |
| bd | required | `bd --version` on PATH |
| Trailcode | required | `trail --version` or `graft --version` on PATH, whichever exists |
| RTK | optional | `rtk --version` on PATH, and a hook in `~/.claude/settings.json` that runs rtk; without the hook it is degraded |
| task-observer | optional | `~/.claude/skills/task-observer/SKILL.md` with a version, and its activation block in `~/.claude/CLAUDE.md`; without the block it is degraded |
| Headroom | optional | `headroom --version` on PATH, then in the running interpreter's scripts folder, and `headroom mcp status` reporting Claude Code as configured; without that it is degraded |
| Graphify | optional | `graphify --version` on PATH, then in the running interpreter's scripts folder, and `~/.claude/skills/graphify/SKILL.md`; without the skill it is degraded |

Three parts are required, because the lifecycle cannot run without them: the bundled
skills, bd and Trailcode. A missing one stops `quarry drive`. The other four are optional
companions. They work at the host level, through a hook, an instruction block, an MCP
server or a skill, and a missing one stops nothing. Quarry proposes them, installs and configures the ones the
user chooses, and checks them. It uses two of them where they are present: the `research`
skill queries a Graphify graph of `docs/research/`, and a red driver stage writes a
task-observer observation. `skills/quarry/resources/PARTS.md` tells the agent when to use
each one.

Also needed:

- `bd init <prefix>` run once in the repo (a human step; the wizard skill can walk you
  through it).
- A built Trailcode graph (`graft build`, deterministic, no API key) for the atlas.
  Interactive skill use works without Trailcode; see "Running without the atlas" below for
  what that costs.
- **Python 3.11** for the engine.

## Compatibility

Three manifests ship, and the hosts differ in which lifecycle events they expose, so
they get different amounts of quarry. Skills, commands, the engine CLI, the tracker and
recall work everywhere; what varies is what fires on its own.

| | Claude Code | ZCode | Codex |
|---|---|---|---|
| Manifest | `.claude-plugin/plugin.json` | `.zcode-plugin/plugin.json` | `.codex-plugin/plugin.json` |
| Skills | yes | yes | yes |
| `/quarry:*` commands | yes | yes | not declared by the manifest |
| `Ask_Knowledge` over MCP | yes | yes | yes |
| Auto-seal | PreCompact, the last moment before compaction | every prompt submit, after six new messages | PreCompact from the manifest, not yet observed; `quarry seal` is the verified route |
| Prompt-submit contracts | yes | no | yes |
| Stop audits (recall, atlas, flow, scope) | yes | no | recall and scope only |
| PreToolUse guards (atlas, tracker, recall, flow lane, human gates in driver sessions) | yes | no | no |
| Harness driver (`quarry drive`) | grill and spec stages | no | no |

Host limitations, stated rather than implied:

- **ZCode** exposes no compaction event, so sealing is driven by message count instead
  (six new conversation messages) and the residual gap is covered by the next
  prompt's seal. Its manifest declares no hooks, so the guards and the Stop audits do
  not exist there: the protocol promises in "What is enforced, and what is protocol"
  fall back to being protocol only.
- **Codex** hands its hooks the same payload Claude does, measured off a live turn:
  `session_id`, `transcript_path`, `cwd`, `hook_event_name`, and for tool events
  `tool_name` "Bash" with `tool_input` holding `command`, even though Codex records the
  same call as its own `exec` tool everywhere else. The manifest declares
  `hooks/codex-template.json`, which registers SessionStart, PreCompact, PostCompact,
  UserPromptSubmit and Stop; SessionStart and UserPromptSubmit are observed firing there.
  Every hook needs one-time trust in Codex's `/hooks` screen before it runs, and Codex is
  silent when it skips an untrusted one; `--dangerously-bypass-hook-trust` makes hooks run
  without trust but discards any decision they return. The Stop audits read the rollout
  the payload names; recall and scope can fire on one, atlas and flow cannot, because a
  rollout records no read tool call and no skill invocation.
- **Claude Code** is the only host that honours a PreToolUse denial. Codex runs the guard
  and discards its answer, for both the exit-2 and the JSON decision forms and in every
  sandbox mode, so the guards are not registered there: a guard that cannot fire is not a
  weaker guard, it is absent, and the same rule then holds only if the agent follows it.

### Running without the atlas

graft is an orientation and optimization layer, and it sits outside the durability
guarantee entirely: the graph in `graft/` is a regenerable cache, gitignored, rebuilt by
`graft build`. Losing it costs orientation, never memory or work state, and no sealed
unit, ticket, decision or recall address depends on it.

What changes without it: code navigation stops being ranked and becomes conventional
file reading and searching, which costs more context per question and finds things in a
less predictable order. `graft skeleton` (signatures at roughly a tenth of the tokens),
`graft callers` and `graft blast` have no substitute other than reading the files. The
skills skip their atlas steps silently, `/quarry:setup` reports graft as optional and
continues, and the atlas Stop audit only fires where a `graft/` graph exists, so a
project without one is never nagged about it.

## Install (Claude Code)

The repository root is a marketplace named `renjestoo`, and quarry is the plugin in it:

```
claude plugin marketplace add <path of the cloned repository>
claude plugin install quarry@renjestoo
```

Hooks (SessionStart injects `bd prime` + the memory index; PreCompact seals) are
declared inline in `.claude-plugin/plugin.json`.

Updating a running host needs a restart: `claude plugin update quarry@renjestoo`
swaps the files, but a live session keeps the skill metadata it loaded at startup.

## Install (Codex-style hosts)

Add the repository root as a marketplace and install from it; the manifest declares
`hooks/codex-template.json`, so the five-event lifecycle registers with the plugin. Each
hook then needs one-time trust in Codex's `/hooks` screen, and until it has it Codex skips
it without saying so. `/quarry:setup` can also copy the same file to a project's
`.codex/hooks.json`. SessionStart injects the tracker state and memory index; PreCompact
seals; PostCompact writes a refresh marker; the next UserPromptSubmit consumes that marker
and re-injects the index once, so a compacted session gets its memory back on the first
prompt after the compaction; Stop runs the audits against the rollout the payload names.

## Machine-specific values

**One** value is machine-specific: the Python interpreter. No file of the plugin names a
path on a machine. The engine uses the standard library only, so any Python 3.11 or later
runs it.

Skills and commands invoke `"$QUARRY_PYTHON"`, which the host supplies from `settings.json`:

```json
"env": { "QUARRY_PYTHON": "<full path of a Python 3.11 or later>" }
```

Set it once per machine. The skills and commands fail without it.

The files that *start* quarry on Claude Code, `.claude-plugin/plugin.json` (the hooks) and
`.mcp.json` (the `Ask_Knowledge` server), use `${QUARRY_PYTHON:-python}`: the same variable,
and the `python` on PATH when it is not set. The hook commands need a POSIX shell for that
form: `sh` on macOS and Linux, Git Bash on Windows. On a machine where `python` is not on
PATH (many macOS and Linux installs have only `python3`), set `QUARRY_PYTHON`.

The Codex and ZCode files (`.codex-plugin/plugin.json`, `.zcode-plugin/plugin.json`,
`hooks/codex-template.json`) name plain `python`: whether those hosts expand a variable in a
command is **unverified**. Put a full path there when `python` on PATH is not the
interpreter you want.

Everything else resolves through `${CLAUDE_PLUGIN_ROOT}`. That expansion is verified on the
Claude host, both in the manifest and, before it was removed, in a standalone hook file. It
is **unverified** on the Codex and ZCode hosts; if either does not expand it, that host's
manifest needs a literal path until it does.

`hooks/hooks.json` used to carry a second copy of the same hooks. Both files loaded, so
every hook fired twice and the two had already drifted apart, one carrying a guard the
other lacked. The manifest is now the only home.

## Per-repo setup

Run `/quarry:setup` in the project once: it verifies bd, initializes `.quarry/`,
writes `docs/agents/quarry.md` (interaction mode + triage label mapping), seeds
`CONTEXT.md`, and offers the codex hooks copy.

### Committing the mesh, and when not to

`.quarry/` is the project's memory, and committing it is the default. Know what that puts
into version history before you do it. Sealed units are byte-exact conversation evidence,
they are immutable, and they accumulate: one session in this repository produced a single
evidence copy of 5,896,566 bytes. Three consequences follow.

- **The repository grows and does not shrink.** Units are never rewritten, so the history
  only gets larger.
- **Anything said in a session enters git history permanently.** Deleting a unit later does
  not remove it from earlier commits, and it stays recoverable from them.
- **Every contributor with repository access can read every sealed conversation**, including
  ones they were not part of.

Redaction is therefore not optional hygiene here. `handoff`, `research`, `diagnosing-bugs`
and `wizard` each carry a rule about keeping tokens, credentials and personal data out of
what they write, and `wizard` names the transcript itself as somewhere secrets must not
land. A sealed unit is one more place they are being kept out of.

If that is unacceptable for a project, do not commit the mesh: add `.quarry/` to
`.gitignore` and accept the trade, which is that memory becomes local to the machine and
does not travel to a clone or a colleague. Recall still works exactly as before on that
machine. What you lose is the sharing and the backup, not the guarantee. Choosing that is
a decision worth recording as a non-goal in `CHARTER.md`, so a later session does not
quietly re-enable it.

`.beads/` follows bd's own rules.

## Auto-seal

Sealing fires automatically so `K<n>` units exist before compaction can discard
anything: Claude Code seals on PreCompact (the literal last moment, declared in the
plugin manifest); ZCode, which has no compaction
hook event, seals on every prompt submit once at least six new conversation messages
have accumulated (the threshold bounds unit count; the residual gap is
covered by the next prompt's seal). On Codex the PreCompact hook is registered by the
manifest and receives the rollout's path in its payload, but a Codex compaction has not
yet been observed sealing, so `quarry seal` (it auto-locates the newest rollout whose cwd
is this project) is the verified route there. Manual `/quarry:seal` and the explicit
`--transcript|--rollout|--session|--zcode-session` flags remain everywhere. ZCode
rollouts are snapshot logs, so progress counts messages and each unit holds only the
delta.

## Cold resume

What a fresh agent does with all of it, holding none of the conversation:

1. **SessionStart injects the durable state, and says what quarry is.** The hook emits the
   sealed-memory index, the atlas and dashboard stanzas where those exist, and last an
   orientation stanza: the four homes in one sentence, a pointer to the `quarry` skill and
   `/quarry:help` for the rest, and the read-only reconnaissance contract. Nothing is
   created, edited, claimed, closed, labelled or linked until position has been reported.

   `bd prime` is not among them, deliberately. Measured here over seven consecutive calls
   it took a median of 54.5s (min 1.8s, max 74.4s), so any budget large enough to catch it
   would stall every session start by about a minute, and the 15s budget it used to have
   missed five runs in seven while still costing that wait, silently. The stanza tells the
   agent to run it instead, which costs nothing at startup, and adds the warning that an
   unread tracker is not an empty one. Where the beads plugin is installed it injects
   `bd prime` on its own SessionStart hook anyway, so quarry's copy was also a duplicate
   of roughly 5.7 KB whenever it did succeed.
2. **`bd ready` establishes the frontier.** Work whose blockers are closed is the plan;
   nothing has to be remembered for it to be correct.
3. **A claimed ticket restores itself.** `bd show <id> --long` carries the description,
   design, acceptance criteria, and the notes the previous worker left in the
   COMPLETED / IN PROGRESS / NEXT / BLOCKER / KEY DECISION form.
4. **`Ask_Knowledge` recalls what was said.** Anything settled in an earlier window
   comes back as preserved lines at citable addresses, rather than being guessed at.
5. **The atlas locates the code.** `graft ask` ranks where to start, so orientation
   does not cost a file-by-file crawl.
6. **Implementation continues**, and closing the ticket promotes whatever it blocked.

No step depends on the previous session still being in context. That is the whole
reason the four homes are separate.

## Dashboard

The dashboard starts on request, never with the MCP server. A host launches one MCP
server per session and per project, so starting a board there would run one nobody asked
for in every project the user opens, all reaching for the same port. `quarry dashboard`
starts it and `quarry url` prints where it landed.

One board per project, not one per session. `start` looks for a dashboard already serving
this project before binding anything: it probes the address recorded in
`.quarry/webapp.json`, then sweeps the ports one could hold, and adopts what it finds
rather than opening a rival. A second start therefore joins the running board and reports
its address, and the endpoint record is rewritten either way, which also repairs a record
lost while the board kept running. Binding is loopback only, takes port 7777 when free and
the next free port otherwise, and leaves `SO_REUSEADDR` off deliberately, so a port
already held is refused instead of stolen from whoever holds it. A dashboard that cannot
bind at all is reported on stderr and skipped: recall never depends on it.

A board ends three ways, and none of them is finding its process id. `quarry stop` ends
this project's board on request, finding it by record and then by sweeping the ports, so a
board whose record was lost is still reachable; ctrl-c ends one running in a foreground
terminal; and a board nobody has asked anything of for half an hour ends itself. That last
one matters because a board normally outlives the session that started it: the host owns
the MCP server and reaps it on exit, but nothing owns the board, so without a timeout an
abandoned one would hold its port until the machine restarted. Traffic is what counts as
use, not an open event stream, because an abandoned stream looks exactly like a watched one
until a write to it happens to fail; an open page polls regardless, so real use always
shows up as requests. Stopping asks the server which project it serves first, so one
project can never stop another's board.

SessionStart tells the session about the board either way. It probes rather than trusting
the record, because `webapp.json` outlives the process that wrote it and another project
may hold that port by now, and it never stays silent: with no board running it hands the
agent the commands to start one, since a session told nothing concludes there is no
dashboard.

Eight pages over live state, one of them carrying three tabs. The **dependency graph** lays the open issues out by force,
clustered by connectivity, each radius set by how much that issue blocks; click one to
trace its neighbours, drag to pin it. The **board** carries three tabs: a **Kanban** under
every status bd has, empty columns included, a **Roadmap** in execution order, grouped
by the objective a ticket serves through its label and closed by the non-goals, both read
from `CHARTER.md`, and a **Fleet** tab reading bd's coordination primitives when several
agents share the tracker. Each objective also shows whether its measure currently holds, met, at
risk, not met or unassessed, because closed tickets are throughput and attainment is a
separate judgement nobody can compute. Then the **ready queue**, the **workflow paths**,
the **guide** (which reports its own drift against the plugin on disk), the **strata** of
sealed units sized by preserved lines, an **activity** feed carrying median lead time from
filed to closed and median cycle time from claimed to closed, and **settings**, where the
interaction mode is written back to the same `docs/agents/quarry.md` line `/quarry:mode`
reads, beside the board's own health: requests served, failures, uptime and request timing.

Both timings are measured rather than estimated, from stamps bd already records, and the
cycle figure counts only issues that were actually claimed, so its sample is smaller than
the lead one and the page says so. Estimates, velocity and burndown stay out; see the
non-goals in `CHARTER.md`.

Updates are pushed rather than polled: the page holds an SSE connection open while the
server watches the few files whose mtime moves when work or memory changes, so an edit
made in a terminal reaches an open tab on its own. A 30 second poll remains as the
fallback, revalidated with an ETag, so an unchanged tracker costs one 304 and no
repainting. Issues can be created, claimed, reprioritized, closed, reopened, linked and
deleted from the page; every write runs the matching `bd` command rather than touching the
database, so bd keeps computing readiness and writing history. The `in_progress` column
says when more than one issue is claimed at once, measured against quarry's own rule that
an agent takes one at a time.

Sealed history is searched, never browsed: the strata view offers a question box backed
by `Ask_Knowledge` and returns passages at their addresses, because a unit browser would
be exactly the whole-unit read the recall guard exists to prevent.

## Engine

`scripts/quarry.py` (stdlib-only Python):

| Command | Does |
|---|---|
| `init` | create `.quarry/` |
| `seal --transcript\|--rollout\|--session` | seal a transcript's unsealed tail |
| `ask "<question>"` | recall from sealed history (CLI fallback for Ask_Knowledge) |
| `index` / `list` | the memory index / one line per unit |
| `mcp` | serve `Ask_Knowledge` over stdio JSON-RPC, and the dashboard beside it |
| `dashboard` | run the dashboard in the foreground, without an MCP host |
| `stop` | stop the dashboard serving this project |
| `flow [lane] [--cancel]` | pin this project to one workflow lane, report it, or release it |
| `url` | print where the running dashboard is listening |
| `hook <event>` | host lifecycle dispatcher |
| `drive "<goal>" [--issue <id>] [--model <id>] [--until <stage>] [--json]` | the harness driver: run grill, then spec, on one goal unattended; `--until grill` ends the run after the grill check; `--json` writes the run as JSON Lines events (`quarry_lib/events.py` holds the table) |
| `delete-epic <id> [--force]` | print, as JSON, a bd epic and every issue under it; with `--force` delete them with `bd delete`; the sealed mesh is not touched |
| `doctor [--json]` | report each harness part as present, absent or degraded; installs nothing; `--json` prints `{"parts": [...], "exit": <code>}` |
| `install [--dry-run] <part>...` | run the install and configure commands of the named parts (`all`: each part that is not present), then probe them again; `--dry-run` prints the commands only |

### Harness

`quarry drive "<goal>"` is the first part of the harness, on Claude Code only.
Today it runs two stages in one run, grill and then spec. A stage starts only when the
check of the stage before it is green, in a session of its own, and `--until <stage>` ends
the run after that stage. The stage templates (skill files, brief, check) are in
`quarry_lib/stages.py`. Step 1 is done once for a run and steps 2 to 11 for each stage; step 12 is what differs for
spec.

1. It records the run in bd: a new task issue that holds the goal verbatim, or the issue
   that `--issue` names.
2. It runs recall (`Ask_Knowledge`) and the atlas lookup (`graft ask`) on the goal text.
3. It builds the prompt from the stage's skill files (grill: `skills/grilling/SKILL.md` and
   `skills/domain-modeling/SKILL.md`), the goal and the two lookup results.
4. It runs a fresh `claude -p --input-format stream-json --output-format stream-json
   --verbose --permission-mode bypassPermissions` session in the project, with the real
   Claude home and `DISABLE_AUTO_COMPACT=1`, and prints each tool call as it arrives. The
   prompt goes in as one user message; stdin stays open until a result frame gets no
   answer from the driver (step 10).
5. It applies the context marks to the session's context use: the latest main-thread
   assistant frame's `input_tokens + cache_read_input_tokens + cache_creation_input_tokens`
   (subagent frames do not count). At the freeze mark, 220,000 tokens, it writes one user
   message telling the session to start nothing new; the CLI absorbs it at the next tool
   result. At the stop mark, 300,000 tokens, it kills the session's process tree and the
   stage is red. Each mark is the lower of its number and 90% of the window, and the window
   (`modelUsage[<model>].contextWindow`) arrives only in the result frame: the fixed marks
   apply, and a stop mark above 90% of the reported window makes the stage red.
6. It refuses the human gates (gate 3) before they run. Before each session it
   writes `.quarry/gate.json` with the stage's step scope (grill may write) and names it in
   `QUARRY_GATE_FILE`; it removes the file when the session ends. The `gate` guard
   (`quarry guard gate`, on Bash, PowerShell and the write tools) is registered per driver
   session through `claude --settings`, never in the plugin manifest, so interactive
   sessions run no gate process at all. It denies, with a reason that
   names the gate and says the user does this step personally: a push, a force push, a history
   rewrite (`git reset` with `--hard`, `--soft` or `--mixed`, or to a ref such as `HEAD~1`
   or `origin/main`; `git reset HEAD file` only unstages and passes), a branch or tag delete,
   an install, a delete outside the project (a target it cannot resolve from the text counts
   as outside), a credential-bearing command (`.env` and `.env.*` except `.env.example`),
   and, while the step scope denies writing, the write tools and write-shaped commands. A
   payload it cannot read is denied. Shell keywords (`if`, `do`, `!`) and wrappers
   (`timeout`, `env`, `xargs`, `sudo`) are skipped to find the command word. The gates never
   vary between stages, so they are one table in `quarry_lib/gate.py`, not part of the file.
   This is pattern matching over shell text and cannot be complete: a command built at run
   time (`eval`, a variable holding the program), a script or alias that does the step
   itself (`python push.py`, a git alias), a delete through a symlink and a `git reset` to a
   bare branch name all pass. `gate.py` lists the known holes.
7. It seals each session into the mesh and appends a bd note from its tool-call record
   (session id, check, handoff document, tools with counts, files written, the calls the
   result frame lists under `permission_denials`, usage), green or red; the same denials
   go on a `denied:` phase line.
8. The hand off: at the hand-off mark, 250,000 tokens, it writes one user
   message telling the session to finish the item in hand, write a handoff document at
   `docs/handoff/<session-id>.md` in the project (it points the session at
   `skills/handoff/SKILL.md` for what the document holds) and end its turn. When that
   session ends, a missing or empty document makes the stage red, naming the path. Else
   it starts a fresh session (new session id) on the same issue, whose prompt holds the
   goal, the handoff document, fresh recall and atlas results and the skill files, never
   the earlier transcript: recall leaves out the units sealed from this stage's sessions.
   A stage runs at most three sessions; a third session that also crosses the hand-off
   mark makes the stage red because the work does not fit the work budget and must be
   split. No hand off follows a stop.
9. After the last session it checks the stage: green only when the stage's fact holds (grill:
   `CONTEXT.md` or a file under `docs/adr/` changed since before the first session), the
   result frame has `is_error` false, and no `compact_boundary` frame arrived (that one is
   red with its `pre_tokens`).
10. Decision dispatch. The stage session decides no question point itself: it
    writes the question points of a round to `.quarry/questions.json` (a JSON array of
    objects with `question`, `recommended` and an optional `pointers` list) and ends its
    turn. At the result frame the driver takes the file and decides each question, with the
    goal text as the grounding. In yolo mode (`Interaction mode:` in `docs/agents/quarry.md`,
    yolo when the line is absent) the decider is a separate headless session: its prompt is
    `agents/answer-agent.md` and the four inputs, its built-in tools are Read, Glob and
    Grep, the write and shell tools are disallowed at spawn, it runs with
    `--permission-mode dontAsk`, `--strict-mcp-config` and every hook off
    (`--settings {"disableAllHooks": true}`), and a call of any other tool in
    its record fails the dispatch. In interactive mode the driver asks on its own terminal; an empty line takes
    the recommended answer. Each decider session is sealed, and each question with its
    verdict is appended to the run's bd issue. The decisions return to the stage session as
    its next user message. A question the stage already got decided is never dispatched
    again: it gets its recorded verdict back, and a file with no new question starts no
    decider session. One stage gets at most 20 decisions; a stage that asks for more is red.
11. Retries and the halt. A turn that ends with no question points while the check is red
    gets the check's detail as its next user message, at most two times. A NEEDS HUMAN, a
    dispatch that fails, a reply off the output format, and every red end of the stage halt
    the run: the driver files a bd issue labelled `ready-for-human` that names the run's
    issue (`discovered-from`), one for each NEEDS HUMAN of the round or one with the check's
    detail. A red end that is not a NEEDS HUMAN also writes one task-observer observation
    that names the stage's skills, through that skill's own `new-observation.sh`, so
    repeated stage failures reach the skill review. Where task-observer is not installed
    or has no workspace, the driver prints why it skipped the write and the run is not
    affected. `scripts/checks/observe_check.py` checks this in a scratch workspace, with no
    model turn.
12. The spec stage. Its prompt holds `skills/spec/SKILL.md`, the goal, and
    the artifacts of the grill stage as ids and paths: the run's bd issue, which carries the
    note of each dispatched decision, and the decision files the grill check found changed.
    It holds no text of the grill transcript: recall leaves out the units sealed from every
    earlier session of the run, the decider sessions included. The session sends its seam
    sketch to decision dispatch and publishes the spec with `bd create --type=epic`, labelled
    `ready-for-agent` unless `docs/agents/quarry.md` names another label; an absent file is
    a default, not a question point. The
    check is green only when a bd issue of type epic exists that did not exist before the
    stage and its description is not empty. The driver does not check the spec's sections.

It exits 0 when every stage is green and 1 on a halt or on any failure. `bd` and `graft` (with a built
`graft/` graph) are required. The CLI is `QUARRY_CLAUDE`, else `claude` on PATH, else the
newest `%APPDATA%\Claude\claude-code\<version>\<build>\claude.exe`. `--model` takes a full
model id, never an alias. The end-to-end check is `scripts/checks/driver_check.py`; each of
its runs costs one real Claude turn. `scripts/checks/marks_check.py` replays recorded frames
through the marks and checks the hand off on constructed cases with no model turn; its
`real` run drives one session past the freeze and stop marks, its `handoff` run drives a
first session across the hand-off mark and a second session that continues it.
`scripts/checks/gate_check.py` feeds PreToolUse payloads to `quarry guard gate` and a
constructed result frame to the note, with no model turn.
`scripts/checks/dispatch_check.py` checks decision dispatch, the retries and the halt on
constructed inputs in a scratch project with a real bd tracker, with no model turn; its
`probe` run is one real decider session that must read a project file; its `real` run drives three real runs (a decided question, a NEEDS HUMAN, a stage forced red).
`scripts/checks/spec_check.py` checks the chain, the spec fact, the spec prompt and its retry
in a scratch project with a real bd tracker, with no model turn; its `real` run drives one
goal through grill and spec (two stage sessions, and one decider session for each question
point) and checks the new epic, the two sealed sessions and the spec session's prompt. Every
other real run passes `--until grill`.
`scripts/checks/doctor_check.py` runs `quarry doctor` as a real subprocess, plain and then
with RTK, bd and Graphify hidden, with no model turn.

### What is enforced, and what is protocol

Quarry makes two kinds of promise, and they have very different reliability. Read the
first list as a property, the second as a discipline.

**Enforced by the engine, whatever the agent does:**

- Sealed sources never change: SHA-256 is verified before and after every recall.
- Every returned passage is preserved text at a checkable address (`K1:12-18`).
- Recall is deterministic and model-free, and empty results name the terms they tried.
- Sealing is incremental and idempotent: each seal captures only records after the last
  seal and after any compaction boundary the host already summarized.
- Five PreToolUse guards deny outright rather than advise, each only where its substrate
  exists: a search of source files the atlas indexed (logs, data, docs and unindexed
  source stay searchable), `TodoWrite` or `TaskCreate` in a bd repo,
  direct reads of `.quarry/units` that would bypass recall, a `Skill` call that leaves
  a pinned flow lane, and, in a driver session only, a human gate (Harness, step 6).

**Agent protocol, true only when the agent complies:**

- Decisions get recorded in `CONTEXT.md`, an ADR, or a spec as they are made.
- Issue notes stay current, so a successor resumes instead of reconstructing.
- `Ask_Knowledge` is consulted before re-deciding a settled question.
- The atlas is consulted before hand exploration.
- The pinned flow lane is followed.

Behind the second list are prompt-submit nudges and four Stop audits: recall (a reply
that reconstructs earlier sessions without calling `Ask_Knowledge`), atlas (heavy file
reading with no `graft` call), flow (a skill the pinned lane excludes), and scope (a turn
that built structure justified only by what it would allow later). That last one is the
only machine enforcement the least-architecture law has, so leaving it out of this list
documented the doctrine and hid its mechanism. Those audits are heuristics over the
current turn (from the last user prompt on), they block a turn at most once (a host's
`stop_hook_active` retry passes), they fire after the reply rather than before it, and they cannot see what
was never written down. So they raise the cost of departing from the protocol; they do not
make it impossible, and no promise in the second list should be relied on without
checking.

### What gets preserved

More than the visible conversation, which matters both for what recall can find and for
what enters version control. The rendering a unit is searched through carries:

- user and assistant messages;
- **assistant reasoning**, under an `ASSISTANT REASONING` header, where the host records
  it;
- **tool calls with their arguments** (`TOOL <name>`) and **tool results**
  (`TOOL RESULT`).

Two things are dropped from that rendering: host meta records, and Claude sub-agent
sidechains, which belong to a different conversation and are skipped rather than sealed
as this session's words.

The evidence copy is broader still on Claude and Codex, because it is a byte-exact
segment of the transcript file rather than a selection from it: it holds what the
rendering skipped too. On ZCode, whose rollouts are snapshot logs rather than append-only
ones, the evidence copy is the sealed message array re-serialized, since byte ranges of a
snapshot format do not exist.

### Evidence and rendering

Each unit is two files, hashed separately so either being altered is detectable: the
byte-exact evidence copy in the format it was captured in, and a distilled rendering
that recall actually searches.

The rendering is deliberately lossy. Instruction blocks re-injected every turn collapse
to a marker, identical tool results collapse, call arguments past 120 characters are
replaced by their length, and a recall result is reduced to the addresses it cited so
the mesh does not duplicate itself into itself. This is safe precisely because it is
derived: the evidence copy keeps every byte, so a rendering can be regenerated from it
if the rules change.

The guarantee is therefore narrower and stronger than "never summarize": evidence is
never replaced by a summary. What recall reads is condensed; what the mesh preserves is
not.

### Retention

Immutability governs how a unit changes, which is never. Retention governs whether a unit
stays, which is a separate question, and the default answer is **retain indefinitely**: a
mesh is small next to the code it discusses, and an old decision being citable years later
is the entire point.

Three ways history leaves, none of which edits a unit:

- **Retire one unit.** Delete `K<n>.json`, `K<n>.md` and `K<n>.jsonl` **together**.
  Deleting only the evidence copy breaks every recall in the project, not just that
  unit's: integrity is verified across all units before and after each answer, so one
  missing evidence file makes the whole mesh refuse (measured: `sealed evidence is
  missing: ...K2.jsonl` raised on a question about K1). Leave the `mesh.json` snapshot
  entry alone.
- **Archive.** The same three files, moved somewhere outside the repository instead of
  deleted. Recall cannot reach an archived unit; nothing else changes.
- **Reset.** Delete `.quarry/` and initialize again. This is the one move that recycles
  addresses: the new mesh starts at `K1`, so old citations do not merely stop resolving,
  they point at different content. Never reset a mesh whose addresses have been cited
  anywhere; retire or archive instead.

What happens to addresses: retiring or archiving `K2` leaves `K1` and `K3` exactly where
they were, and the next seal is still `K4`, because numbering comes from the index rather
than from the files present (both measured). Citations of the retired unit dangle: recall
simply stops returning it, and a `K2:118-140` written into an issue, ADR or handoff no
longer resolves. Record a retirement where the citations live, in a decision bead or an
ADR, saying which unit went and why.

One thing retention cannot do: a committed unit stays in git history. Retiring it removes
it from the working tree and from recall, not from earlier commits, and getting it out of
those means rewriting history, which is the project's decision and outside quarry.

## Flow locks

The six lanes the paths page draws also ship as skills that pin the project to one of
them: `flow-new-feature`, `flow-inbound-issue`, `flow-something-broke`, `flow-too-foggy`,
`flow-phase-running`, `flow-cold-resume`. The pin lives in `.quarry/flow.json`, so it
outlives the conversation that set it, and the prompt-submit hook re-states it every turn,
because a constraint mentioned once is gone the moment the context compacts.

Enforcement has two layers, and they cover different things. A PreToolUse guard on the
`Skill` tool denies an out-of-lane call before it runs, which reaches the case the lock is
for: the agent wandering off the lane by itself. It cannot reach a slash command the user
types, because that path does not go through the `Skill` tool, and it should not: the lock
exists to constrain the agent, never to refuse the user their own command. The Stop audit
is therefore still the backstop, denying a completed reply that used a skill the lane
excludes and naming the lane and what it expected.

Each lane's permitted set is derived from the `LANES` table the paths page draws, so a
lane and the board cannot disagree, and both layers read the same set.

`/quarry:flow-cancel` releases the pin. A single departure without releasing is allowed
when the **user** writes `flow override` in their own message; the audit looks for that
phrase in a user record specifically, so an agent cannot grant itself the exception by
writing it.

## Known limits

Hook failures never interrupt the host. Every failure is reported on stderr and
swallowed, and a failed seal especially must not block a compaction the host is about
to perform. State the consequence plainly: work continues while newly generated history
may be unprotected. Previously sealed units stay valid, a failed seal never corrupts
them, and the failure is surfaced rather than hidden.

If a host rewrites its transcript file (line endings, in-place rewrite), the recorded
seal offset can stop landing on a record boundary and that source stops sealing,
loudly, never corruptly. See `skills/quarry/resources/RESUMABILITY.md` for the
recovery.

## Layout

```
.claude-plugin/plugin.json    Claude manifest (skills, commands, inline hooks)
.codex-plugin/plugin.json     Codex manifest
.zcode-plugin/plugin.json     ZCode manifest
hooks/codex-template.json     five-event codex hooks, declared by the Codex manifest
.mcp.json                     Ask_Knowledge stdio server
agents/                       task-agent, answer-agent (YOLO)
scripts/                      the engine
webapp/                       the dashboard: HTTP server, bd and mesh readers, static UI
skills/quarry/                core skill: 16 commands + 7 doctrine resources
skills/<31 siblings>          the rewritten lifecycle collection
```

## Attribution

Quarry stands on three design sources, rewritten and fused: **beads** (Steve Yegge,
MIT) for the tracker substrate, hook lifecycle, and plugin packaging patterns;
**Frozen Context Mesh** for the seal/distill/recall engine and memory doctrine;
**Matt Pocock's** agent workflow collection, completely rewritten quarry-native
(no copied skill text), for the lifecycle and its artifacts. All engine code and
skill content in this plugin was written for quarry; where a doctrine parallels a
source closely, the file says so.
