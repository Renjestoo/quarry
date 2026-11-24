---
description: Close a bd issue with a reason and report what it unblocked
argument-hint: "<id> --reason <what was done and how it was verified>"
---

Before closing, verify the acceptance criteria are demonstrably met; a close is a
claim that work is done, not that work stopped. If criteria are not met, say so and
offer to set the issue blocked with an explanation instead.

Close: `bd close $1 --reason "$2"`. If no reason was given, ask for one (or derive it
from the issue's notes): "done" is not a reason.

Then:

1. Run `bd ready` and report what this close just unblocked, closing a blocker
   promotes its dependents; that is the scheduler working.
2. If the work settled a hard-to-reverse, surprising decision with a real trade-off,
   offer to write the ADR and/or the decision bead now, while the reasoning is fresh.
3. If notes contain state a successor might need, distill them into the close reason or
   the ADR, notes on a closed issue stop being maintained.
