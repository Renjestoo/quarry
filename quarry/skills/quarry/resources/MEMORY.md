# Sealed memory

> Adapted from the Frozen Context Mesh architecture (design source for quarry's engine).

## The position

Compaction is the bug, not the window size. When a context fills, quarry seals the
session transcript byte-for-byte as an immutable unit and lets the host compact what it
wants, nothing that mattered was in the host's hands anymore. A fresh session is told
which sealed units exist and reaches old material through exactly one tool:
`Ask_Knowledge`.

Guarantees the engine enforces, whatever an agent does:

- Sealed sources never change. SHA-256 is verified before and after every recall.
- Every returned passage is preserved text at a checkable address, like `K1:12-18`.
- Nothing picks a winner between conflicting passages; chronology distinguishes
  supersession from contradiction.
- Recall is deterministic and model-free: same question, same answer, zero inference.

What the mesh does **not** give you is current truth. Sealing preserves what was said,
as evidence; the authoritative answer lives in `CONTEXT.md`, an ADR, a spec, or bd.
A decision found only in sealed history is recoverable but not authoritative, because a
transcript cannot distinguish a settled conclusion from a suggestion that was dropped.
Promote it to its home, then cite the passage as the evidence behind it. Sealing is why
you never lose the record; it is not a substitute for writing the decision down.

Known limit, disclosed rather than hidden: vocabulary mismatch. An empty result names
the exact words it tried. Re-ask in the project's own vocabulary; a name, a file, a
decision, before giving up.

## How sealing happens

- **Automatically**: the PreCompact hook seals the transcript before the host compacts
  it. On codex hosts, PostCompact/UserPromptSubmit re-inject the index once.
- **Incrementally**: each seal captures only the records after the last seal and after
  any compaction boundary the host already summarized. Re-sealing a transcript that has
  not grown is a no-op.
- **Manually**: `/quarry:seal` or `quarry seal --transcript <path>` / `--rollout <path>`
  / `--session <id>`.

Files, per unit, under `.quarry/units/`:

| File | Role |
|---|---|
| `K<n>.md` | the searchable distilled text; citations resolve against it by line number |
| `K<n>.jsonl` | the sealed byte-exact evidence copy |
| `K<n>.json` | unit metadata and digests |

`.quarry/mesh.json` indexes the units and remembers how far each transcript source has
been sealed.

Commit `.quarry/`: it is the project's memory, and committing is the default. Know the
trade first. Units are immutable and they accumulate, so the repository grows and never
shrinks; anything said in a session enters git history permanently and stays recoverable
from earlier commits even if the unit is deleted later; and every contributor with
repository access can read every sealed conversation, including ones they were not part
of. `handoff`, `research`, `diagnosing-bugs` and `wizard` each carry a redaction rule for
that reason, and a sealed unit is one more place tokens, credentials and personal data
must not land. A project that cannot accept those three consequences should
`.gitignore` `.quarry/` instead: recall keeps working exactly as before on that machine,
and what is given up is sharing and backup, not any guarantee above.

## What a unit holds

More than the visible conversation: user and assistant messages, assistant reasoning
under an `ASSISTANT REASONING` header where the host records it, tool calls with their
arguments (`TOOL <name>`), and tool results (`TOOL RESULT`). Host meta records and Claude
sub-agent sidechains are left out of the rendering, since a sidechain is a different
conversation. The evidence copy is wider than the rendering on Claude and Codex, being a
byte-exact segment of the transcript rather than a selection from it.

## Retention

Immutability says a unit never changes. Retention says whether it stays, and the default
is to keep everything: recall exists so an old decision is still citable.

- **Retire one unit**: delete `K<n>.json`, `K<n>.md` and `K<n>.jsonl` together. Deleting
  only the evidence copy makes every recall in the project fail, because integrity is
  verified across all units before and after each answer.
- **Archive**: move the same three files out of the repository. Recall cannot reach them.
- **Reset**: delete `.quarry/` and start over. Only this recycles addresses, so old
  citations point at different content afterwards. Never reset a mesh that has been cited.

Retiring `K2` leaves `K1` and `K3` addressed as they were and the next seal is still `K4`,
because numbering comes from the index, not from the files present. Citations of a retired
unit stop resolving, so record the retirement in a decision bead or ADR: which unit, and
why. A committed unit also stays in git history; retiring it does not reach earlier
commits.

## Distillation

The `.md` is a lossy rendering of the evidence, reduced by deterministic rules: repeated
blocks collapse to markers; tool calls compress to one line keeping identifying
arguments; identical tool results are kept once; a recall result is preserved as the
addresses it cited, never the lines it copied, freezing the copy would duplicate the
mesh into itself and bury the original under its own echo. The evidence copy keeps every
byte, so the rendering can always be produced again.

## Using Ask_Knowledge

Ask in plain language. Never name a unit, a line, or a pattern; the one-string surface
is deliberate: it makes "I searched" mean "every window was searched".

- Prefer it over every other tool for anything the project may have settled before:
  decisions, names, constraints, preferences, what a file held, what was agreed and why.
- Quote, don't paraphrase, when it matters. The passage is the truth source.
- Empty result: re-ask with the project's own nouns once; then other tools; then the
  user.
- **Never invent what an earlier window said.** If it is not in your context and
  Ask_Knowledge did not return it, you do not know it.

CLI fallback: `quarry ask "<question>"`: same engine, same guarantees.
