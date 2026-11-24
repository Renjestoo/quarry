---
description: Show the complete quarry catalog - every skill, every command, and when to use each
argument-hint: "[topic]"
---

Present the quarry catalog to the user **in full**: every skill and command below,
nothing skipped or collapsed. If `$ARGUMENTS` names a topic (e.g. "sealing", "yolo",
"atlas"), open with that section and still show the rest. Format for reading, not for
scanning past: short lines, bold names, one "when to reach for it" per entry.

---

# Quarry: the whole map

Quarry makes agent work survive context loss. Four homes for state, one law each:
**decisions in files** (`CONTEXT.md`, ADRs) · **work in bd** (issues; `bd ready` is the
plan) · **history in the mesh** (sealed units, `Ask_Knowledge`) · **the code in the
atlas** (a graft graph). Compaction, `/clear`, session end; none of them lose work.

## The main flow: idea → shipped

The route most work travels. One session for steps 1–3, a fresh window per step 4.

1. **`grilling`** (enter via `/quarry:grill <idea>`): the interview that sharpens an
   idea. Facts get looked up by sub-agents; decisions get answered by you (or, in
   **yolo mode**, by the answer agent). Every answer lands in `CONTEXT.md`/ADRs as it
   is given. Done when there are no questions left whose prerequisites are settled.
2. **`spec`**: synthesizes the settled decisions into a spec, published as a bd epic.
   No interviewing; pure capture. Confirms the seams (where tests will live).
3. **`tickets`**: slices the spec into tracer-bullet bd issues with `blocks`
   dependencies. From here the dependency graph IS the plan: `bd ready` shows the
   frontier, nobody maintains a schedule.
4. **`implement`**: one ticket per fresh window: claim → read the contract → ask the
   atlas and sealed history → build test-first (`tdd`) → review (`code-review`) →
   close with a verified reason. A discovery that blocks the ticket becomes an issue;
   every other one is a line on the epic's parking list, never silent scope. The task agent can run this loop hands-off.

## Flow lanes (pin one route, and refuse every other)

Pinning a lane narrows what the agent may do until it is released, checked before the call
rather than audited after, and it is project-wide, so it constrains every agent at once.
Release with `/quarry:flow-cancel`, or ask for a single departure by writing
"flow override".

- **`flow-new-feature`** (lane A): the grill, spec, tickets, implement sequence enforced
  rather than suggested.
- **`flow-inbound-issue`** (lane B): a bug report, a CI failure or a pasted request goes
  through triage before anything is built.
- **`flow-something-broke`** (lane C): a failure that is not obvious, with the feedback
  loop built before anybody theorises.
- **`flow-too-foggy`** (lane D): too big and too unknown to spec, so unknowns become
  decisions one session at a time.
- **`flow-phase-running`** (lane E): an open `workflow:` epic drives the work step by
  verified step.
- **`flow-cold-resume`** (lane F): a fresh session picks up existing work from durable
  state instead of guessing what was happening.

## On-ramps (starting situations that merge onto the flow)

- **`triage`**: incoming issues you didn't create (bug reports, user requests).
  Verifies claims, runs the label machine, leaves an agent brief on ready issues.
- **`diagnosing-bugs`**: "something is broken." Builds a red feedback loop FIRST,
  then ranked hypotheses; the fix lands at a seam with a regression test.
- **`wayfinder`**: an effort too big and foggy to spec. Charts a map of decision
  tickets, one per session, until ordinary `spec` becomes possible.

## Detours (answer one question, feed back in)

- **`research`**: a sub-agent investigates against primary sources, leaves cited
  notes in `docs/research/`.
- **`prototype`**: throwaway code answering ONE design question, kept on a
  `prototype/` branch as the primary source.
- **`to-questionnaire`**: the answer lives with someone absent: package the questions
  for them to answer async.

## Vocabulary (run beneath everything)

- **`domain-modeling`**: keeps `CONTEXT.md` a clean glossary; ADRs for
  hard-to-reverse decisions.
- **`codebase-design`**: the deep-modules dictionary (seam, depth, adapter) for
  judging a module's shape.

## Upkeep

- **`improve-codebase-architecture`**: surveys hot spots (git history + atlas map),
  reports candidates as HTML, grills the chosen one into tracked work.

## Session tools

- **`handoff`**: seal + a doc that REFERENCES artifacts, for a successor agent,
  another harness, or a colleague.
- **`next-step`**: verifies the active `workflow:` epic's ready tickets against
  evidence, closes the done ones, names the exact next ticket.
- **`next-workflow`**: closes the finished phase epic (bd keeps the history),
  interviews the next phase into a new epic with ordered tickets.
- **`parallel-agents`**: several agents on one tracker, using bd's swarms, merge slot,
  gates, worktrees and the `hooked` status. Available, never automatic; one agent on
  one ticket stays the default.
- **`wait-what`**: "re-explain that simply": re-pitches the last message in plain
  English with glossary words.

## Standalone

- **`resolving-merge-conflicts`**: hunk by hunk, resolved by intent traced to each
  side's source; both intents survive.
- **`wizard`**: generates a guided script for steps only a human can do (URLs,
  secrets, dashboards).
- **`teach`**: a stateful learning workspace: missions, records, lessons,
  retrieval practice over summaries.
- **`writing-for-agents`**: doctrine for any document an agent will read.
- **`writing-great-skills`**: the same doctrine, specialized for SKILL.md files.
- **`quarry`** (the core skill): the router: the situation table above, the decision
  test, the cold-start protocol.

## Commands

| Command | Does |
|---|---|
| `/quarry:grill <idea>` | enter the interview |
| `/quarry:spec` · `/quarry:tickets` | publish the epic, slice the tickets |
| `/quarry:ready` · `/quarry:show <id>` | the frontier; one issue's full context |
| `/quarry:create` · `/quarry:close <id>` · `/quarry:dep <a> <b>` | tracker edits |
| `/quarry:implement <id>` | one ticket, end to end |
| `/quarry:ask <question>` | ask sealed history (fallback for Ask_Knowledge) |
| `/quarry:seal` · `/quarry:units` | seal now; list sealed units |
| `/quarry:mode [yolo\|interactive]` | flip autonomy |
| `/quarry:workflow` | where am I, and the exact next command |
| `/quarry:dashboard` | start this project's board, and give me its address |
| `/quarry:charter` | the objectives, their measures, and the non-goals |
| `/quarry:flow-cancel` | release the pinned lane, or report which one is pinned |
| `/quarry:setup` | configure a repo (bd, mesh, atlas, mode) |
| `/quarry:help` | this catalog |

## Modes and memory

**Yolo** (`/quarry:mode yolo`): decision points go to the answer agent instead of
you; unanswerable ones return NEEDS HUMAN in one batch. Destructive, outward-facing,
and credential actions stay yours in both modes. **Sealing** is automatic before
compaction on Claude and ZCode; `/quarry:seal` forces it. **Ask_Knowledge** answers
"what did we say/decide"; the atlas answers "where is it in the code".

**Lost?** `/quarry:workflow` reads the live state and names your next command.
