---
description: Interview an idea (or the current topic) into recorded decisions
argument-hint: "[idea or topic]"
---

Enter the `grilling` skill and run it against `$ARGUMENTS` (or, if empty, the idea the
user has been discussing, infer from the conversation; ask only if genuinely
ambiguous).

This is the stateful entry: grilling plus domain-modeling. The session is done when the
design-tree frontier is empty, at which point every decision has landed in
`CONTEXT.md`/ADRs, then suggest `/quarry:spec` (the quarry command) to synthesize the
conversation into a tracked spec.

Respect the interaction mode from `docs/agents/quarry.md`: in `yolo`, question points
go to the answer agent, and only NEEDS HUMAN questions reach the user.
