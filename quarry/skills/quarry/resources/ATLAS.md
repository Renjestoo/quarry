# Code atlas

> Quarry wraps [graft](https://github.com/nanonets/graft) as its atlas substrate, the
> way it wraps bd as its tracker. Quarry parses no source code itself.

## The division of knowledge

| Question | Answered by |
|---|---|
| WHERE is X in the code? What does it call / call it? | the atlas (`graft ask`, `graft callers`) |
| WHAT was said or decided about X? | sealed memory (`Ask_Knowledge`) |
| WHAT work exists around X? | the tracker (`bd`) |
| WHAT does X mean here? | the glossary (`CONTEXT.md`) |

Asking the wrong home wastes a turn: grep-ing for a decision the mesh holds verbatim, or
asking memory where a function lives. Route the question to its home.

## What the atlas is

A graft graph in `graft/` (regenerable, gitignored): tree-sitter-parsed symbols and
call edges across 22 languages, deterministic, no API key, no LLM. Curated concept
nodes and summaries exist only if someone ran `graft build --deep`; quarry never
requires them. Every query fingerprints the working tree (~3ms) and rebuilds the
structural layer if files moved, so answers reflect uncommitted edits.

## The surfaces quarry uses

| Need | Command |
|---|---|
| "where do I start for this task?" | `graft ask "<task>"`: ranked nodes + file:line |
| read a file cheaply before editing | `graft skeleton <file>`: signatures, ~1/10 tokens |
| impact before/after a change | `graft blast`: blast radius of the diff (`--base <ref>`) |
| who calls this? | `graft callers <symbol>` (`-d N` transitive) |
| orient on an unfamiliar repo | `graft map`: token-budgeted clusters, hubs, hotspots |
| exhaustive search | `graft grep "<regex>"`: grouped by enclosing symbol |

## Rules

- **Atlas before exploration**: before Glob/Grep-ing a grafted repo by hand, ask the
  atlas. Hand exploration is the expensive habit graft exists to replace.
- The atlas is advisory structure, not truth: it ranks and locates, it does not decide.
  Reading the actual file still wins over trusting a summary node.
- No graph (`graft/` absent) is a normal state: skip atlas steps silently and explore
  by hand; `/quarry:setup` offers to build one. The atlas sits outside the durability
  guarantee: it is regenerable, so losing it costs orientation, never memory or work
  state, and no unit, ticket, decision or recall address depends on it. What degrades is
  navigation, which becomes conventional reading and searching: more context spent per
  question, and no substitute for `skeleton`, `callers` or `blast` other than opening the
  files.
- `graft check` reports drift if you ever need to know how stale a hand-copied node is.
- Never edit `graft/` by hand; it is a regenerable cache, like node_modules.
