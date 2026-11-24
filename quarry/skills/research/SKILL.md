---
name: research
description: "Dispatch a background agent to investigate one question against primary sources and return a cited markdown file committed to the repo. Use when a decision needs facts you do not have ('what does library X support', 'how does service Y rate-limit'), and the answer must come from primary sources."
metadata:
  short-description: "Cited answers from primary sources"
---

# Research

One question, primary sources, a durable answer. Facts for decisions, never a
substitute for making them.

## Dispatch

Send a sub-agent (background when the caller continues without it) with exactly:

1. **The question**, stated so a stranger could answer it.
2. **The constraint**: primary sources only, official docs, source code, specs,
   changelogs, the project's own sealed history (Ask_Knowledge counts: "what did we
   already learn about this"). Blog posts and AI answers are leads to primary
   sources, not citations.
3. **The output contract**: a markdown file at `docs/research/<slug>.md`:

```markdown
# <Question>

<Answer in 3–8 sentences, direct, no hedging theater.>

## Evidence

- <claim>: <source URL or file path>, <the line or section that proves it>

## Open

<What the sources did not settle.>
```

4. **The redaction rule**: scrub tokens and credentials from anything pasted.

## The research graph (when Graphify is present)

Graphify is an optional companion. Use it when `quarry doctor` reports it present.

1. **Before a dispatch**, when `docs/research/graphify-out/graph.json` exists, run
   `graphify query "<the question>" --graph docs/research/graphify-out/graph.json`.
   A note that already answers the question ends the dispatch: cite that note. A note that
   answers part of it goes into the dispatch as "already known", with its path.
2. **After a return** that adds a note, rebuild the graph with the `graphify` skill on
   `docs/research`. The skill reads the notes through the agent, so it needs no API key.
3. `graphify-out/` is a cache that the skill makes again. Keep it out of git.

Without Graphify, skip this section: list `docs/research/` and read the notes whose
names fit the question.

## On return

- Read the file; if Evidence does not support the Answer, send it back once with the
  specific gap.
- Record the load-bearing findings: a settled "library X cannot do Y" that kills an
  approach belongs in a decision bead (and an ADR if it is surprising and
  hard-to-reverse), not only in the research file.
- Link it: the requesting ticket (or grilling session) references
  `docs/research/<slug>.md`; the file back-references the question's origin.

## Rules

- One question per dispatch. A two-headed research task returns one answer to neither.
- No synthesis from memory: if the agent cannot find a primary source for a claim,
  the claim goes under Open, clearly marked.
- The file is committed; research that lives in the conversation is lost at the next
  compaction, which is the failure quarry exists to prevent.

## Routes

**From** inline, `grilling` rounds, `wayfinder` research tickets, or directly · **To** the cited answer returns to its caller; settled findings become decision beads
**Alternates** `prototype` when the question is about how something feels, not what is true
**Lost** `/quarry:workflow`

