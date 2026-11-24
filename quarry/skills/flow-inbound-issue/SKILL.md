---
name: flow-inbound-issue
description: "Pin this project to the inbound-issue lane and refuse every other route until it is released. Use when the user says 'lock the flow', 'follow the inbound path', 'stay on lane B', or hands over a bug report, a CI failure or a pasted user request that must go through triage before anything is built."
metadata:
  short-description: "Pin the triage-to-shipped lane"
---

# Flow: inbound issue

Lane B from the paths page, pinned. Work somebody else filed, verified before it reaches
an agent.

Pin it on invocation:

```
"$QUARRY_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/quarry.py" flow flow-inbound-issue
```

## Steps

`Steps: issue arrives -> triage -> agent brief -> /quarry:implement -> bd close`

1. **issue arrives** labelled `needs-triage`.
2. **triage** verify the claims before trusting them. Reproduce the bug, run the command,
   check the file exists. An unverified report never reaches `ready-for-agent`.
3. **agent brief** written on the issue, and it is labelled `ready-for-agent`.
4. **`/quarry:implement`** build it against that brief.
5. **`bd close`** done, with the evidence.

## Branches this lane allows

Each of these **ends the lane** rather than continuing it:

- After triage, **`wontfix`** when the premise is wrong. Record it in `.out-of-scope/`.
- After triage, **`needs-info`** when only the author can answer.
- After the brief, **`ready-for-human`** when the work needs judgement an agent lacks.

## Refused while pinned

Anything not listed above. Do not skip triage and implement directly, which is the whole
failure this lane exists to prevent: an unverified report becomes wasted work and a
plausible-sounding fix for a problem nobody confirmed. Do not start `wayfinder`,
`/quarry:grill` or a phase workflow from here.

If triage shows the report is really a live breakage you should chase now, that is the
`flow-something-broke` lane. Say so and release the pin rather than drifting into it.

## Leaving

`/quarry:flow-cancel` releases the pin. A single turn may depart when the user writes
`flow override` themselves. Both rules are defined once in the `quarry` skill's Flow locks
section, which is also what the guard and the audit enforce.

## Routes

**From** inbound work (entry) · **To** `/quarry:implement`, or one of the three endings
**Alternates** `flow-something-broke` when the report is a reproducible breakage worth chasing immediately
**Lost** `/quarry:workflow`
