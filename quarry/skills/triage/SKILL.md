---
name: triage
description: "Move inbound issues through a label state machine, verify claims, grill what survives, and leave a durable agent brief on ready-for-agent issues. Use on untriaged bd issues ('triage this', 'triage inbound'), or when reviewing a queue of incoming reports before any of them reach an agent."
metadata:
  short-description: "Move inbound issues through the label machine"
---

# Triage

Inbound work (issues someone else filed, bugs from CI, requests pasted from users)
enters through here and merges onto the main flow at implement.

Label names come from `docs/agents/quarry.md` (defaults: `needs-triage`,
`needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`).

## State machine

```
                    ┌──────────────┐
        arrives ──▶ │ needs-triage │
                    └──────┬───────┘
              verified? no │  claims check out
              ┌────────────┤
              ▼            ▼
        ┌──────────┐  questions only
        │ wontfix  │  the user can answer
        └──────────┘        │
              ▲             ▼
              │       ┌────────────┐   answered    ┌─────────────────┐
              └───────┤ needs-info │ ───────────▶ │ ready-for-agent │──▶ implement
                drop  └────────────┘              ├─────────────────┤
                                        human-only└─────────────────┘
                                        work       ┌─────────────────┐
                                                   │ ready-for-human │
                                                   └─────────────────┘
```

## Per issue

1. **Read it cold**: `bd show <id> --long`. What is being asked, and is it for us?
2. **Verify the claims**: reproduce the bug, run the command, check the file exists.
   With a graft atlas, `graft ask "<the claim>"` locates the code a report names
   before you trust or distrust it. An issue whose claims are false goes back
   `needs-info` with what you actually observed (or `wontfix` if the premise is
   simply wrong). Never relay an unverified report into ready-for-agent.
3. **Grill what survives** (grilling skill, abbreviated): the questions whose answers
   the fix needs. Facts via sub-agents; decisions via the mode (user, or answer agent
   in yolo). Unanswerable-by-anyone questions → `needs-info` on the issue, asking its
   author exactly those things.
4. **Decide the destination**:
   - A cold agent could do it unaided → write the **agent brief** (below), label
     `ready-for-agent`, done.
   - Only a human can do it (credentials, judgment, physical access) → label
     `ready-for-human` with one line on what the human must decide.
   - Not worth doing → `wontfix` with the reason, and record the rejection in
     `.out-of-scope/<slug>.md` (decision, reason, prior requests) so the next
     identical request finds the answer.
5. **Post the brief as a comment** on the issue.

## Agent brief (the handoff contract)

```markdown
**Agent brief**

- **Goal:** <one sentence, in glossary vocabulary>
- **Context:** <files/modules to read first; the ADRs that govern this area>
- **Approach:** <the settled approach, if one was chosen; otherwise "agent's choice">
- **Done:** <observable acceptance criteria>
- **Out of scope:** <what not to touch, adjacent bugs to file separately>
```

Every comment you post on the issue carries an AI disclaimer line ("triaged by an
AI agent, <date>").

## Rules

- One issue at a time through the machine; batch reports, not batch processing.
- Never edit the reporter's words, add a comment instead.
- A duplicate of a wontfix: point at the `.out-of-scope/` entry and close it the same
  way, updating the prior-requests list.

## Routes

**From** inbound issues (entry) · **To** an agent brief → `implement`; `ready-for-human`; `wontfix`
**Alternates** `diagnosing-bugs` when the inbound report is a reproducible breakage you should chase now
**Lost** `/quarry:workflow`

