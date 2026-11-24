---
name: writing-for-agents
description: "The doctrine for any document an agent will read, skills, specs, tickets, agent briefs, ADRs, notes: context pointers that decide firing, information hierarchy, and completion criteria. Use whenever writing or editing an artifact whose reader is an agent rather than a person."
metadata:
  short-description: "Doctrine for agent-read documents"
---

# Writing for agents

An agent reader differs from a human one: it has no situational memory, pays for
every token, fires skills on descriptions, and follows what is written with literal
fidelity. Write for that reader.

## Context pointers (wording decides firing)

- A description is a **trigger surface**: the words in it are what a future agent
  matches a situation against. Name the situations ("use when the user asks X",
  "before writing a spec"), not just the topic.
- Point to where the truth lives ("bd prime is the source of truth for syntax")
  instead of copying the truth; copies drift, pointers do not.

## Two loads

- **Context load**: what sits in the window permanently (descriptions, headers).
  Minimize ruthlessly, every permanent token competes with the actual work.
- **Cognitive load**: what the reader must hold in working memory to act. Reduce by
  ordering steps so each depends only on what precedes it.

## Information hierarchy

Three tiers, and the reader should always know which tier it is in:

1. **Steps**: the procedure, in the body, imperative, one action per step.
2. **In-file reference**: tables, formats, anti-pattern lists: same file, below the
   steps, consulted on demand.
3. **Disclosed reference**: separate files (companion docs, resources), reached by
   explicit pointer, loaded only when the pointer is followed.

Wrong-tier symptoms: steps buried in reference; reference duplicated into every
file that uses it; a companion file nobody points to.

## Completion criteria

An agent-facing document is done when it is **clear** (a cold reader can act without
guessing) and **demanding** (it states what "done" observes, so the reader cannot
declared-victory past it). Both, or it isn't done.

## Style

- Lead words first: the verb, the name, the number, before the qualifier.
- Negation fails: "don't use mocks for in-process code" is weaker than "mock only at
  system boundaries". Say what to do; the anti-pattern table can carry the rest.
- No hedging theater, no motivational padding, no "simply/just/obviously".

## Pruning

Remove on every edit: duplicated knowledge (keep one home, point from the rest),
environment-as-truth (what the runtime already knows, file lists, versions),
no-ops (steps whose absence changes nothing), and sediment (rules whose reason died;
  if the reason is gone, the rule is gone, or the reason gets re-stated).

The test of a pruned document: every sentence survives "if I delete this, what
breaks?" with an answer.

## Routes

**From** authoring or editing any agent-read artifact · **To** every downstream artifact gets clearer
**Alternates** `writing-great-skills` when the artifact is a SKILL.md itself
**Lost** `/quarry:workflow`

