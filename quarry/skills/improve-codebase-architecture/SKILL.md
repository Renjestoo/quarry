---
name: improve-codebase-architecture
description: "Survey the codebase for deepening opportunities weighted by change frequency, present them as a self-contained HTML report, then grill the chosen candidate into tracked work. Use for upkeep ('improve the architecture', 'this codebase hurts', 'tech debt pass'), on a cadence, or when diagnosing-bugs keeps finding missing seams in the same area."
metadata:
  short-description: "Find and deepen hot spots"
---

# Improve codebase architecture

Upkeep loop: find where change hurts, deepen it, feed the results back into the main
flow as tracked work.

## 1. Survey

Dispatch a sub-agent over the codebase looking for deepening opportunities, weighted
by **change frequency** (a shallow module touched weekly pays back deepening; one
touched twice a year does not):

- `git log --format=format: --name-only | sort | uniq -c | sort -rn | head -30`: the
  hot files. With a graft atlas, `graft map` adds the structural view the history
  misses: hub symbols many others call, and clusters that always change together.
- For each hot area: shallow modules (wide interface, little depth), duplicated
  knowledge, missing seams (the diagnosing-bugs finding), dead abstraction (one
  implementation, no boundary reason), tangled locality (a change to one concept
  always touches the same N far-apart files).

Candidates are findings with evidence, not aesthetics: "the checkout validation
logic is duplicated in 3 of the top-10 hot files" beats "this could be cleaner".

## 2. Report

Render a self-contained HTML report (no external assets, Tailwind CDN is fine,
inline everything else) to the OS temp dir. One card per candidate:

- **What**: the finding, in one sentence.
- **Evidence**: the hot-file stats, the duplication sites, the missing-seam history.
- **Deepening move**: the concrete change (extract module X, narrow interface Y,
  add seam Z) and what becomes easier after.
- **Cost**: rough scope.

Plus one Mermaid diagram of the worst dependency tangle among the candidates, and a
tone that states trade-offs rather than selling a refactor.

## 3. Grill the choice

The user picks a candidate (mode-aware: in yolo the answer agent picks, grounded in
the description). Grill it (grilling skill) until the deepening move is decided,
update `CONTEXT.md`/ADRs inline as the design sharpens: a refactor that renames
concepts without updating the glossary breaks the vocabulary the lifecycle depends on.

## 4. Feed the main flow

The chosen candidate becomes tracked work, not a crusade: one `bd create -t feature`
epic (or a ticket on an existing one) describing the deepening, sliced by the tickets
skill if it is wide, typically expand-contract. Link the evidence from the report
into the issue so the "why" survives the temp dir (the report file itself is
ephemeral; the issue is not).

## Rules

- Frequency-weighted: no deepening cold code.
- One candidate at a time into the flow; the report keeps the rest for later.
- Refactors follow the same lifecycle as features, spec, tickets, implement. "Just
  do the refactor" is how branches diverge for weeks.

## Routes

**From** upkeep (entry) or repeated `diagnosing-bugs` seam findings · **To** the chosen candidate goes through `grilling` → `spec`/`tickets`
**Alternates** `code-review` when the findings belong to one diff, not the codebase
**Lost** `/quarry:workflow`

