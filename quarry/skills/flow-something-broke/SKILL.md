---
name: flow-something-broke
description: "Pin this project to the something-broke lane and refuse every other route until it is released. Use when the user says 'lock the flow', 'follow the bug path', 'stay on lane C', or reports a failure that is not instantly obvious and wants the feedback loop built before anybody theorises."
metadata:
  short-description: "Pin the diagnose-before-fixing lane"
---

# Flow: something broke

Lane C from the paths page, pinned. The loop comes before the theory, and the fix comes
after the diagnosis.

Pin it on invocation:

```
"$QUARRY_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/quarry.py" flow flow-something-broke
```

## Steps

`Steps: diagnosing-bugs -> reproduce -> root cause -> tdd -> /quarry:implement -> bd close`

1. **diagnosing-bugs** build the red loop first: a command that fails while the bug lives,
   passes when it dies, and is deterministic.
2. **reproduce** shrink to the smallest input that still fails red. Every fact removed is
   a hypothesis eliminated.
3. **root cause** the cause, not a symptom that correlates with it.
4. **tdd** a test that fails red for exactly this reason.
5. **`/quarry:implement`** fix at the seam, never around it.
6. **`bd close`** with the guard that means it cannot regress.

## Branches this lane allows

- After **root cause**, take **improve-codebase-architecture** when no seam exists to fix
  at. That is a design finding, not a mocking problem.
- At **diagnosing-bugs**, take **triage** when the report came from outside and its claims
  have not been verified yet.

## Refused while pinned

Fixing before diagnosing. That is the one thing this lane exists to stop, and it is the
tempting move every time: a plausible change that makes the symptom disappear is not a
fix, it is a hypothesis wearing a commit message. Do not close a bug that cannot fail red.
Do not start `/quarry:grill`, `wayfinder` or a phase workflow from here.

## Leaving

`/quarry:flow-cancel` releases the pin. A single turn may depart when the user writes
`flow override` themselves. Both rules are defined once in the `quarry` skill's Flow locks
section, which is also what the guard and the audit enforce.

## Routes

**From** a live breakage (entry) · **To** the fix lands through `/quarry:implement` at a seam
**Alternates** `flow-inbound-issue` when the report arrived from outside and needs verifying first
**Lost** `/quarry:workflow`
