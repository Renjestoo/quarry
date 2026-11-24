---
name: wizard
description: "Generate an interactive bash script that walks a human through steps only they can do (opening URLs, capturing secrets, confirming external state), writing results where the project needs them. Use for setup steps quarry cannot do itself (bd init, credentials, third-party dashboards), or whenever a procedure needs the hands of a human."
metadata:
  short-description: "Guided script for human-only setup steps"
---

# Wizard

Some steps need the human's hands: their browser, their credentials, their payment
card, their judgement on a third-party dashboard. The wizard skill turns those steps
into a script the human runs and *answers*, rather than a document they squint at.

## Process

1. **Enumerate the human-only steps** from the setup at hand. Each must genuinely
   need the human, anything an agent can do stays an agent step, named in the
   script's header as "the agent handles this before/after you run this".
2. **Generate the script** at `./<purpose>-wizard.sh` from the fixed template
   structure: a standard helper library (prompt/confirm/capture-secret/write-env/
   open-url) above a `# STAGES` marker, then the stages. Ephemeral by default:
   the script offers to delete itself on completion; anything it must persist
   (`.env`, config files) it writes explicitly and says so.
3. **Stage shape**:
   - says what it is doing and why in one line,
   - opens the URL (or prints it if `open` is unavailable),
   - captures what came back, secrets with hidden input, stored to `.env` or
     `gh secret set`, never echoed, never committed,
   - confirms success before moving on ("paste the webhook URL", then verifies
     shape),
   - on failure: explains, offers retry, does not silently continue.
4. **Finish line**: prints what was accomplished, what was written where, and what
   the agent should be told ("run this when done: <the next command>").

## Rules

- Secrets: hidden entry, straight to `.env`/secret store, never in argv (visible in
  shell history), never in the transcript if avoidable.
- Idempotent where possible: re-running a completed stage skips it.
- The wizard never edits project source; it writes configuration and credentials
  only.
- In yolo mode the wizard is *more* relevant, not less: it is how the human gates
  stay human.

## Routes

**From** setup steps only a human can do (often surfaced by `/quarry:setup`) · **To** the interrupted setup continues

**Lost** `/quarry:workflow`

