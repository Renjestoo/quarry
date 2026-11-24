---
description: Show this project's objectives and non-goals, and what work serves each
---

The charter answers what work is *for*, which nothing else in quarry records. bd holds
what to build and in what order; the charter holds the outcome that order serves and the
exclusions bounding it. It lives in `CHARTER.md` at the project root.

Read it:

```
"$QUARRY_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/quarry.py" charter
```

Report each objective with its measure, the state of that measure, how many issues carry
its label, and the non-goals. The board's Roadmap tab shows the same thing laid out.

**A closed ticket is not a met objective.** The count beside an objective is work that
finished; whether the measure holds is a separate judgement nobody can compute, so it is
written down. Each objective may carry a `Status:` line reading `met`, `at-risk`,
`not-met` or `unassessed`, optionally followed by a note saying how it was checked:

```markdown
Status: met, guide._drift() reports empty in all four directions
```

An objective with no `Status:` line, or one whose first word is not a state, reads as
`unassessed`, so a typo can never report an objective as met. Keep it to one line: like
`Why:` and `Measure:`, only the first line is read.

**A ticket serves an objective by carrying its label**, the objective id lowercased:

```
bd label add <issue-id> obj-2
```

Use `bd label list <id>` to see what a ticket already serves, and
`bd label propagate <epic-id>` to push an epic's objective down to its children.

## When to write to it

- **A new objective** when work starts serving an outcome none of the existing ones name.
  Give it an id, a why, and a measure that could actually be checked. An objective with no
  measure is a slogan.
- **A new non-goal** whenever a decision is made *not* to build something. This is the
  point of the file: without it the decision survives only in conversation, and a later
  session re-proposes the same work having no way to know the absence was deliberate.
- **A changed `Status:`** when work serving that objective closes, or when the measure is
  checked and the answer moved. Re-assess at the close, while the evidence is in hand;
  a status nobody revisits decays into the same decoration as an unevaluated measure.

## What not to do

Do not invent objectives to make the board look organised. Work no objective claims is
shown as unclaimed on purpose; that is information, not a defect. If most work is
unclaimed, the honest reading is that the charter is incomplete or the work is drifting,
and either is worth saying out loud rather than papering over with labels.
