---
name: wait-what
description: "One-move corrective, re-pitch the last message in plain Simplified Technical English using the project's CONTEXT.md vocabulary. Use when the user is confused ('wait, what?', 'I'm lost', 'explain that again simply') and jargon overload is the likely cause."
metadata:
  short-description: "Re-pitch the last message plainly"
---

# Wait, what?

Re-pitch the last message under three constraints:

1. **Simplified Technical English**: short sentences, one instruction each, only the
   1000-ish core words plus the project's own terms; no idioms, no metaphor chains,
   no "essentially/basically/arguably".
2. **Glossary vocabulary**: every domain term used must exist in `CONTEXT.md`. If the
   last message leaned on an unglossed term, that term gets defined inline in one
   clause, and flagged for domain-modeling (it earned a glossary entry).
3. **Same content, less packaging**: do not drop information to simplify; reorder it
   so the action comes first, the reason second, the detail last.

No questions back, no apology theater, no restating the entire session; the last
message, re-pitched, nothing else.

## Routes

**From** anywhere, on confusion · **To** straight back to what was happening

**Lost** `/quarry:workflow`

