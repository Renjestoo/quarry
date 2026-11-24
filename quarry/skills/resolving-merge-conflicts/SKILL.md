---
name: resolving-merge-conflicts
description: "Resolve merge conflicts hunk by hunk by tracing each side's intent to its primary source (the commit, PR, or bd issue that produced it), preserving both intents. Use whenever a rebase or merge reports conflicts and the user asks for help resolving them."
metadata:
  short-description: "Resolve conflicts by traced intent"
---

# Resolving merge conflicts

A conflict is two intents for one region. The resolution is not "pick the nicer
side"; it is finding what each side *meant*, from its primary source, and writing
code that is true to both. `--abort` is a last resort reported to the user, never a
default.

## Process

0. **Take the slot, when other agents share this repository**: `bd merge-slot acquire`,
   and release it the moment the resolution lands. Conflict resolution is the one step
   quarry serialises, because two agents resolving at once produce fresh conflicts out of
   each other's fixes. Alone in the repository, skip this. See `parallel-agents`.
1. **Map the conflict**: `git status`, then read each conflicted hunk. For each,
   name the two intents in one line each ("ours: extract the validation helper;
   theirs: add the currency field to the same struct").
2. **Trace each intent to its primary source**: the commits touching the hunk
   (`git log --merge -- <file>`), the PRs, the bd issues (`bd show` on the ids in the
   branch/commit messages). The diff tells you what changed; the source tells you
   *why*, which is what the resolution must preserve.
3. **Resolve hunk by hunk**, smallest first (imports, then formatting, then logic,
   early easy wins build the map for the hard one). Each resolution must be defensible
   in one sentence: "kept the helper extraction, applied the field to the extracted
   helper's args; both intents live."
4. **Never invent a third behavior**: if the two intents are genuinely exclusive
   (one deleted what the other extended), stop and surface the decision with the
   sources; that is a human/mode decision point, not a merge choice.
5. **Run the project's checks** (typecheck, lint, tests, at minimum the tests
   covering the conflicted files). A merge resolved but unverified is a conflict
   postponed.
6. **Finish the operation**: complete the merge/rebase; if discoveries were filed
   along the way, link them `discovered-from` the affected issues.

## Rules

- Both intents survive, or the decision escalates. "Roughly merge the text" is how
  bugs get committed with a clean-looking history.
- No `--abort`, no force-push, no history rewriting without the user's explicit say.
- If the conflict spans generated files or vendored code, regenerate instead of
  hand-merging; hand-merged generated code is corruption with extra steps.

## Routes

**From** a conflicted merge or rebase (entry) · **To** the interrupted `implement` continues

**Lost** `/quarry:workflow`

