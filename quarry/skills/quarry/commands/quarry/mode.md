---
description: Show or flip the project's interaction mode (interactive or yolo)
argument-hint: "[yolo|interactive]"
---

The mode lives in `docs/agents/quarry.md` under `Interaction mode:`.

**No argument**: read the file and report the current mode and what it means.
`interactive`: lifecycle skills ask the user at every decision point; `yolo`: they
dispatch the answer agent instead, surfacing only NEEDS HUMAN questions.

**With argument**: validate it is exactly `yolo` or `interactive`, edit that line, and
confirm. Explain the change in one sentence, including the standing exception:
destructive, outward-facing, or credential-bearing actions stay human gates in both modes.

**When the file or its `Interaction mode:` line is absent**, in either branch: report the
project as unconfigured and route to `/quarry:setup`. Never create it here. The engine
refuses the same write, and `set_mode` in `webapp/settings.py` records the reason, so this
command follows that rule rather than restating it.
