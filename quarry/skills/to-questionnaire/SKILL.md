---
name: to-questionnaire
description: "The inverse of grilling: interview the user about a request they must send to a third party, then write a discovery questionnaire that person can answer async. Use when the user needs information from someone else ('ask the vendor', 'I need to ask the client'), and that person cannot be interviewed live."
metadata:
  short-description: "Package grilling for an absent answerer"
---

# To questionnaire

You cannot grill someone who is not here. This skill packages the grilling for
delivery: the questions get answered by the third party, in their own time, and come
back as decisions the main flow can use.

## Process

1. **Interview the send** (the user; this is about *their* request, never yolo'd):
   - Who is answering, and what do they know about? (Sets vocabulary: a technical
     counterpart gets different questions than a business owner.)
   - What decision hangs on their answers? (Every question must serve a decision
     your project will make with the reply.)
   - What is the deadline and the channel?
2. **Derive the questions** from that decision, grilling-style: each with why you
     are asking, and (where you can) the options or format you expect ("a number",
     "a name of their system", "yes/no plus a comment"). Recommended answers for
     *their* side are usually wrong; instead give examples of a useful answer.
3. **Write `to-questionnaire-<slug>.md`**:

```markdown
# <What this is about>: questions from <project>

<One paragraph of context they need: who you are, what you are building, why you
are asking them. No jargon from CONTEXT.md that they do not share.>

1. **<Question>**
   We ask because <one line>. Useful shape of an answer: <format/example>.

2. ...

## If it is easier to answer in one go

<One free-text prompt covering the theme, for people who hate forms.>
```

4. **Trim**: every question must pass "a decision uses this answer". Cut the rest;
   a questionnaire over ~10 questions gets answered badly.
5. **Deliver**: the file path and a suggested cover note. Park the work it blocks
   (`bd update <id>` → blocked, reason "awaiting <slug> questionnaire").

## On return

When answers come back: they enter the grilling session that spawned the
questionnaire as if the user had answered, recorded into their homes (CONTEXT.md,
ADRs, the ticket) with provenance ("per <party>'s reply, <date>").

## Routes

**From** a needed answer held by an absent person · **To** the reply re-enters `grilling` as answered decisions
**Alternates** `research` when the source is documentation or code, not a person
**Lost** `/quarry:workflow`

