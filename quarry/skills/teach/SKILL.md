---
name: teach
description: "Run a stateful multi-session learning workspace in the current directory (mission, curated resources, learning records, lessons) using retrieval practice and spaced repetition rather than summaries. Use when the user says 'teach me <topic>', asks to learn something across multiple sessions, or wants a study workspace rather than a summary."
metadata:
  short-description: "Retrieval-practice learning workspace"
---

# Teach

A learning workspace, not a summary generator. The learner's brain does the work;
the workspace arranges the effort.

## State (created lazily in the current directory)

| File | Role |
|---|---|
| `MISSION.md` | why this learning exists, in the learner's words |
| `RESOURCES.md` | curated high-trust sources + communities |
| `NOTES.md` | the learner's preferences (pace, style, language) |
| `reference/*.html` | printable cheat sheets the learner builds |
| `learning-records/*.md` | what was learned, what is shaky; one per session |
| `lessons/*.html` | tiny, beautiful, one win each |
| `assets/` | reusable components for the above |

`MISSION.md` is quoted verbatim from the user at the start; it is the filter for
everything else ("does this serve the mission?").

## Method

1. **Never trust parametric knowledge for facts**: every fact comes from
   `RESOURCES.md` sources or primary documentation, fetched now, not remembered.
2. **Calibrate the zone of proximal development**: first session = a diagnostic
   conversation; the learning-records thereafter keep the map of what is solid vs
   shaky, and sessions target the shaky edge, not the comfortable middle.
3. **Retrieval practice over review**: sessions ask the learner to produce, explain,
   predict, build, before showing anything. Summaries feel like learning and are
   not; retrieval is.
4. **Spacing and interleaving**: open each session by retrieving 2–3 items from
   earlier sessions (the records say which were shaky); interleave adjacent topics
   rather than blocking one.
5. **Fluency vs storage**: mark in the records whether a slip was "never stored" or
   "stored, not fluent"; the fix differs (re-teach vs re-drill).
6. **End every session with a learning record**:

```markdown
# <date>: <topic edge>

Retrieved solidly: <items>
Shaky: <items, next session starts here>
New: <items taught this session>
Mission check: <one line: closer, or not, and why>
```

7. **Lessons**: when something lands (a concept clicks, a win happens), build one
   tiny `lessons/*.html`: Tufte-style, one idea, no chrome. The lesson is built by
   the *learner* explaining; the agent formats.

## Rules

- The workspace state is the curriculum; a session that ignores the records restarts
  the spiral, which is the failure mode this skill exists to prevent.
- The learner produces first, always. An answer given before asked for is a summary,
  and summaries are not teaching.
- Cheat sheets are built by the learner, not generated for them.

## Routes

**From** a learning goal (entry; a standalone domain) · **To** nothing downstream; the workspace is the product

**Lost** `/quarry:workflow`

