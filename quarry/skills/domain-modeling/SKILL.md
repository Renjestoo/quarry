---
name: domain-modeling
description: "Maintain the project's ubiquitous language: challenge fuzzy terms against the CONTEXT.md glossary, sharpen them, stress-test with scenarios, and record only hard-to-reverse decisions as minimal ADRs. Use whenever a term is being defined or challenged, before writing specs or tickets, when the code and the conversation use different words for the same thing, or when a decision with a real trade-off gets made and needs recording."
metadata:
  short-description: "Maintain the CONTEXT.md glossary and ADRs"
---

# Domain modeling

Shared vocabulary is load-bearing: every spec, ticket, test name, and review finding
the lifecycle emits uses these terms. A term with two meanings or two terms with one
meaning will surface later as a bug or a wasted afternoon.

## CONTEXT.md: the glossary

Format, one entry per term:

```markdown
### <Term>

<1–2 sentences: what it means in this project.>

_Avoid_: <aliases and near-neighbors this term replaces, with one line on why they mislead.>
```

Discipline:

- Challenge every fuzzy word the conversation produces ("handler", "item", "sync"):
  either it earns an entry or it gets replaced by a term that has one.
- Stress-test with a scenario before writing the entry: two sentences of concrete
  usage. If the term cannot survive a scenario, it is not a term yet.
- Cross-reference code: if the codebase calls it something else, the entry says so,
  and one of the two names is marked to change.
- Entries are updated in place; the _Avoid_ list grows, never shrinks silently.

## ADRs: the decisions

`docs/adr/NNNN-slug.md`, minimal:

```markdown
# <Decision in a sentence>

## Decision

<What was decided.>

## Rationale

<Why, including the trade-off accepted.>

## Alternatives

<What was rejected, one line each.>
```

Record a decision only when it is **hard to reverse**, **surprising**, and has a
**real trade-off**. Everything else is ordinary engineering judgment and goes in the
spec or the issue. Supersede rather than edit: a changed decision gets a new ADR whose
Rationale names the old one.

Also file `bd create --type decision` for each ADR: the tracker records that it was
made and when; the ADR records what it means. Link the two via the issue's
description.

## Mode

In `yolo`, term challenges and ADR-worthiness calls go to the answer agent like any
other decision point. Glossary wording still follows the user's description; the
answer agent decides, it does not author new vocabulary from nothing; if the
description settles no wording, that is NEEDS HUMAN.

## Routes

**From** inline inside `grilling`/`triage`/`improve-codebase-architecture`, or directly when a term is challenged · **To** `spec` consumes the glossary
**Alternates** `codebase-design`: the same discipline for the code's vocabulary, not the domain's
**Lost** `/quarry:workflow`

