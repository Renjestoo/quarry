---
name: writing-great-skills
description: "The doctrine for writing and editing quarry skills themselves, invocation, description triggers, progressive disclosure, and predictability as the root virtue. Use when creating or revising any SKILL.md, when a skill fires wrongly or never fires, or when its body needs pruning."
metadata:
  short-description: "Doctrine for writing skills themselves"
---

# Writing great skills

The root virtue is **predictability**: a skill must fire when its situation occurs
and only then, do the same thing every time, and cost nothing when idle. Every rule
below serves that.

## Invocation

- The `description` is the trigger surface. It names the situations in the user's
  likely words, including quoted phrases they might type. A description that only
  names the topic ("grilling skill") fires on vibes; one that names situations fires
  on events.
- Model-invoked skills (most of quarry) pay permanent context load for their
  descriptions, keep them to what firing needs. A user who wants a skill by name
  can always invoke it explicitly.
- One skill, one load-bearing mechanism. If a skill has two, it is two skills, or
  one skill with a missing abstraction.

## Anatomy

```
frontmatter: name, description (trigger-rich)
body:        what it is (1 line) → when to use → the method (steps) → rules
companion:   formats and branch detail, in separate files, reached by pointer
```

- The body carries the procedure; formats and branch-specific detail belong in
  companion files (`FORMAT.md`, `*-PATTERNS.md`), pointed to explicitly, SCREAMING-
  SNAKE-named to signal "reference, not narrative".
- Progressive disclosure is an economy: frontmatter → body → companion. Each tier is
  paid for only when used.

## Steering vs reference

- **Steering** (steps, rules, guardrails) changes behavior, keep it in the body,
  imperative, unambiguous.
- **Reference** (glossaries, templates, tables) informs, keep it in companions.
  Mixing them makes the procedure unreadable and the reference unfindable.

## The pruning loop

On every edit, remove:

- duplicated knowledge (one home per fact, pointers elsewhere),
- environment-as-truth (what the host or runtime already provides),
- no-op steps (delete the step; if nothing breaks, it was decoration),
- sediment (rules whose stated reason no longer holds, either the reason returns to
  the text or the rule goes).

## Predictability checks

Before calling a skill done:

1. Fire test: would the description trigger in its named situations, and *not* in
   adjacent ones?
2. Cold test: could an agent with zero conversation context execute the body?
3. Drift test: does any sentence duplicate something the environment states
   (bd prime, --help, another skill)?
4. Size test: body one screen or less; what doesn't fit moves to a companion.

If a skill keeps misfiring, fix the description; the mechanism is almost never the
problem. If it keeps needing re-explaining after firing, the body's hierarchy is
wrong: steps are hiding in reference or reference is masquerading as steps.

## Routes

**From** authoring or revising a SKILL.md · **To** quarry's own skills stay predictable
**Alternates** `writing-for-agents` for every other agent-read document
**Lost** `/quarry:workflow`

