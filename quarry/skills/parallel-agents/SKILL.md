---
name: parallel-agents
description: "Coordinate more than one agent on a single bd tracker using bd's own primitives: swarm molecules over an epic DAG, the merge slot that serialises conflict resolution, async gates, worktrees, the hooked status and readonly worker sandboxes. Use when dispatching several sub-agents or teammates at one repository, when two sessions share a project, when parallel work risks two agents claiming the same ticket or colliding on a merge, or when the user asks about swarms, fleets, or running agents in parallel."
metadata:
  short-description: "Run several agents on one tracker safely"
---

# Parallel agents

Quarry's default is one agent, one ticket, one fresh context window. That default is a
choice about **context economics**, not a limit of the tracker: bd ships a coordination
layer for fleets, and this skill is where it lives. Nothing here fires on its own, and
nothing here is required. The default remains right for most work.

## Decide before you dispatch

The deliberation threshold from the quarry skill applies to the fleet itself. Parallelism
earns its cost when the ready queue holds **several tickets with no edge between them**,
each sized to its own window, and the work is genuinely separable. It does not when the
tickets share a seam, when one will teach you what the next should be, or when there are
simply not enough ready tickets to keep two agents busy. Two agents on serial work is one
agent plus overhead and a merge.

`bd swarm validate <epic-id>` answers the structural half: it checks whether an epic and
its children actually form a DAG worth swarming.

`quarry collide [ids...]` answers the half bd cannot. bd knows only the edges somebody
declared, so two tickets with no edge between them are offered in parallel however much code
they share, and `bd ready` will argue for exactly that. The command ranks each ticket's own
words against the graft atlas and reports every file more than one of them is predicted to
touch, over the ids you name or the ready queue by default, exiting 1 when it finds one so a
dispatch script can branch on it. It predicts from words rather than from a diff, so a
contended file is a question, not a verdict: a file central to an area is predicted for most
tickets about it. Sequence a real overlap with a `blocks` edge, or give the agents worktrees
and expect to hold the merge slot. Without an atlas nothing can answer this at all, and the
command says so rather than reporting all clear.

## Starting one, and what that choice rests on

Nothing in this skill dispatches anything. Every host does that itself, and the two shapes a
fleet can take depend on different things being true.

**Claude Code** ships an orchestrator. The Workflow tool runs a script that fans agents out
and collects structured results; the Agent tool spawns them singly, and concurrently when
several calls go out together. The Workflow route was measured against a real bd tracker,
four agents claiming under distinct actors at once.

**Codex** ships no orchestrator and every piece needed to build one. `codex exec` takes
`-C <dir>` to put an agent in its own worktree, `--output-schema` for a structured final
answer, `-o` to capture it, `--json` for an event stream, and `-s` for a per-agent write
policy. The supervisor is a script you write.

**ZCode** dispatches subagents of its own, keeping a transcript and a result per agent under
`~/.zcode/cli/agents/<session>/<agent>/`.

**An orchestrator that hands each agent a ticket does not rely on the claim for exclusion.**
No two agents are given the same id, so claiming degrades to bookkeeping and `--actor`
identity: both worth having, neither the safety property. What correctness rests on is the
partition, and nothing in bd computes one. Run `quarry collide` over the set before fanning
out, and read the queue again rather than trusting a plan fixed before any agent started,
because the tracker moves while the fleet runs.

**An agent pulling from `bd ready` does rely on the claim**, and it is the only model whose
correctness rests on the mechanism this skill names. That mechanism holds: with four agents
racing one ticket, one won and three were refused with exit 1 naming the winner. Two costs
come with it. Every agent reads the same frontier, so the losers each pay a process round
trip to be told no. And the refusal is an exit code and a line of stderr rather than a
structured answer, so "that one is taken, take the next" is a property of the agent's prompt
and not of bd.

## The primitives

| Need | Command |
|---|---|
| turn an epic into coordinated parallel work | `bd swarm create <epic-id>`, then `bd swarm status` |
| stop two agents resolving conflicts at once | `bd merge-slot acquire` / `check` / `release` |
| create that lock, once per repository | `bd merge-slot create` |
| wait on something outside the tracker | `bd gate create` (`human`, `timer`, `gh:run`, `gh:pr`, `bead`) |
| wait on another project's bead | a `bead` gate whose await id is `<rig>:<bead-id>` |
| give each agent its own checkout | `bd worktree create <name>` |
| let a worker read but never write | the global `--readonly` flag |
| say which agent did what | the global `--actor <name>` flag |
| mark an issue as attached to an agent | status `hooked` |

Worktrees share one `.beads/` through git's common-directory discovery, so agents in
separate checkouts work the same tracker with no redirect configuration.

## Rules

- **Claiming is the coordination primitive.** `bd update <id> --claim` is atomic, so it,
  not etiquette, is what stops two agents taking one ticket. Claim before work, always,
  and the rule matters more in a fleet than alone.
- **The ready queue is still the plan.** Parallelism changes how many agents read the
  frontier, never how the frontier is computed. Only `blocks` edges gate readiness.
- **Hold the merge slot for conflict resolution, never for the whole task.** It is an
  exclusive lock; a held slot idles every other agent that needs it. `resolving-merge-conflicts`
  is the work it protects.
- **Pass `--actor`** when several agents share a repository, or the audit trail records one
  name for all of them and `bd audit` stops being able to answer who did what.
- **`--readonly` for any agent that only reads.** A reviewer, a researcher, or a question
  answerer has no reason to hold write access to the tracker.
- **Discoveries are still sorted, one per finding.** A fleet multiplies discoveries; it does
  not license absorbing them. A blocker gets a ticket, and every other one is a line on the
  epic's parking list (TRACKER resource, "Discovery pattern").

## What parallelism does not change

The four homes, and their precedence when two disagree. Sealing stays per session: each
agent seals its own transcript into the same mesh. The flow lock is **project-wide**, so a
pinned lane constrains every agent in that project at once, which is what makes it a
useful fleet-wide constraint and a blunt one.

A pinned lane also denies *this* skill, since no lane lists it. That is the lock working
rather than a defect: pinning a lane is a deliberate narrowing, and widening to a fleet is
a route decision the lane did not include. Release the pin and say why, or ask the user
for a `flow override`.

## Known limits, stated rather than discovered later

- **Concurrent seals queue, they do not race.** Sealing takes an exclusive lock on the mesh
  (`.quarry/seal.lock`) across choosing the unit id, writing the evidence and recording the
  unit, so two agents sealing at once both succeed, one after the other. A seal that waits
  longer than two minutes refuses and names the lock file rather than giving up quietly, so
  a lock left behind by a killed process is visible and removable.
- **The board's Fleet tab shows the coordination**, beside Kanban and Roadmap: who holds the
  merge slot, what is waiting on a gate, and each swarm's progress with its ready, active,
  blocked and completed counts. It is fetched when you open the tab rather than with every
  poll, because the bd commands behind it are slow.
- **Neither lock has a lease, so an agent that dies strands its work.** A claim and the merge
  slot both persist until something clears them, and bd tells other agents to queue behind a
  held slot, so a slot held by a dead process idles everyone waiting on it. Both recover
  without touching the database, and any actor may do it:

  ```
  bd merge-slot release
  bd update <id> --status open --assignee ""
  ```

  `release` succeeds from an actor that never held the slot, which is what makes recovery
  possible and equally means nothing stops a wrong release. On the claim, both flags are
  needed: `--status open` on its own leaves the dead agent's name in `assignee`, so the
  ticket returns to `bd ready` still looking owned.
- **Nothing finds the stranded work for you inside a day.** `bd stale -s in_progress` is the
  discovery tool and its window will not go below one day; `-d 0` is refused with
  `--days must be at least 1`. A fleet that ran for twenty minutes is invisible to it. At
  fleet timescale the route is `bd list --status in_progress --json` compared against the
  actors you actually launched. That comparison is why a fleet wants a supervisor: bd
  records who holds what, never who is still alive, and only the thing that started the
  agents knows which of them should still be running.

## Routes

**From** a ready queue with genuinely independent tickets, or a user asking for a fleet · **To** `implement` per agent, `resolving-merge-conflicts` under the slot
**Alternates** stay single-agent when the tickets are serial; `wayfinder` when there is not enough settled work to parallelise
**Lost** `/quarry:workflow`
