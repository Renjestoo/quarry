---
name: flow-cold-resume
description: "Pin this project to the cold-resume lane and refuse every other route until it is released. Use when the user says 'lock the flow', 'follow the resume path', 'stay on lane F', or a fresh session must pick up existing work from durable state instead of guessing what was happening."
metadata:
  short-description: "Pin the resume-from-durable-state lane"
---

# Flow: cold resume

Lane F from the paths page, pinned. A session holding none of the conversation
reconstructs its position from the four homes, in order, and continues.

Pin it on invocation:

```
"$QUARRY_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/quarry.py" flow flow-cold-resume
```

## Steps

`Steps: session start -> bd ready -> Ask_Knowledge -> /quarry:implement`

1. **session start** the injected index lists the sealed windows that exist to be asked
   about. Read it rather than scrolling for context that is not there.
2. **`bd ready`** the frontier. Work whose blockers are closed is the plan; nothing has to
   be remembered for it to be correct.
3. **`Ask_Knowledge`** before re-deciding anything. Ask in plain language and quote what
   comes back.
4. **`/quarry:implement`** continue, and closing promotes whatever it blocked.

## Branches this lane allows

- After **`bd ready`**, take **`bd show <id> --long`** when work is already claimed. The
  notes are the state a previous worker left, in the COMPLETED / IN PROGRESS / NEXT /
  BLOCKER / KEY DECISION form.

## Refused while pinned

Inventing what an earlier session decided. If it is not in context and `Ask_Knowledge` did
not return it, you do not know it, and saying otherwise is the exact failure the mesh
exists to prevent. Also refused: re-deciding a settled question because you cannot see
that it was settled, restarting claimed work instead of continuing it, and starting a new
effort through `/quarry:grill` or `wayfinder` while the point of this lane is to resume an
old one.

## Leaving

`/quarry:flow-cancel` releases the pin. A single turn may depart when the user writes
`flow override` themselves. Both rules are defined once in the `quarry` skill's Flow locks
section, which is also what the guard and the audit enforce.

## Routes

**From** a fresh session (entry) · **To** `/quarry:implement` on the resumed ticket
**Alternates** `flow-phase-running` when the resumed work is a phase epic rather than a loose ticket
**Lost** `/quarry:workflow`
