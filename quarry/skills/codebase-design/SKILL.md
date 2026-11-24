---
name: codebase-design
description: "The design vocabulary beneath the lifecycle (modules, interfaces, depth, seams, adapters, locality) and the tests that tell deep from shallow. Use when designing a module or interface, when tdd says a seam is missing, when deciding what becomes a module boundary, and when judging whether an abstraction earns its place."
metadata:
  short-description: "Deep-modules vocabulary: seams, depth, adapters"
---

# Codebase design

A vocabulary for judging structure, because structure is judged in words before it is
judged in code. These terms run beneath every other quarry skill: tdd's seams,
tickets' slices, code-review's findings, improve-codebase-architecture's candidates.

## The vocabulary

| Term | Meaning |
|---|---|
| **Module** | anything with a name and a boundary: function, class, package, service |
| **Interface** | what a caller must know to use a module, surface, not syntax |
| **Implementation** | what the module does behind the interface |
| **Depth** | how much the module does relative to what the caller must know |
| **Seam** | a place where behavior is observable and replaceable |
| **Adapter** | a thin module translating between a boundary and the domain |
| **Leverage** | work done once that every caller inherits |
| **Locality** | changes to one concept landing in one place |

## Deep vs shallow

```
deep:   interface ▁        shallow: interface ▂▄▆█
        implementation ███▊           implementation ▂
```

A deep module hides much behind little (`file.read()`: buffering, encodings, syscalls).
A shallow one makes the caller know almost everything it does. Deep is the goal;
shallowness is only justified at true system boundaries, where the interface IS the
information.

**Tests that tell them apart:**

- **Deletion test**: delete the module, inline its code at every call site. If the
  code gets *simpler*, the module was shallow; its interface was ceremony. If it
  gets dramatically worse, the module was deep; keep it.
- **Interface-is-the-test-surface**: the interface a caller uses is the seam a test
  uses. If tests need more than callers do, the interface is leaking
  implementation.
- **One-adapter rule**: one adapter over an external boundary is a seam; two, or an
  adapter over an in-process dependency, is a hypothetical abstraction waiting for a
  requirement, delete it until the requirement arrives.

## Designing an interface

1. **Design it twice, once it clears the threshold**: draft one interface and proceed,
   unless the choice could change correctness, security, maintainability, performance
   or architecture, or the interface is hard to reverse. When it does clear, draft two
   radically different interfaces under different constraints (dispatch two sub-agents
   for genuine independence), then compare on depth and locality; the winner is usually
   a hybrid neither draft would reach alone. A module that is naturally one function
   never clears it, and doubling the design work there is the cost with none of the
   benefit.
2. **Push complexity down, not out**: the module absorbs the hard part so callers
   don't each re-implement it. A module that hands its hard parts back is a
   pass-through with a name.
3. **Width costs**: every exported name is interface every caller carries and every
   test must cover. Make the narrowest interface that serves the real callers, then
   stop, no options without a present user.
4. **Locality over graphs**: prefer that one concept's changes land in one module.
   If a change always walks the same N far-apart files, the boundaries are drawn
   along the wrong lines; that is an improve-codebase-architecture finding.

## Dependency classes (what may depend on what)

| Class | Example | Test replacement |
|---|---|---|
| in-process | another domain module | real, never mock |
| local-substitutable | the project's own port | swap the adapter |
| external boundary | network, clock, fs, process | replace the adapter (mock lives here) |
| hypothetical | "we might swap databases" | nothing, delete the interface until real |

## In the lifecycle

- **grilling**: design rounds use these words; a decision phrased as "deep module X
  with interface Y" is testable by the deletion test.
- **spec**: Implementation Decisions name modules and interfaces, never files.
- **tickets**: a tracer bullet's slice follows locality; one concept, end to end.
- **tdd**: a missing seam is a design finding, and this skill's vocabulary is how it
  gets reported.

## Routes

**From** anywhere a module or seam is being judged · **To** `tdd` turns seams into test surfaces; `improve-codebase-architecture` turns findings into tracked work
**Alternates** `domain-modeling` when the terms at stake are the domain's, not the code's
**Lost** `/quarry:workflow`

