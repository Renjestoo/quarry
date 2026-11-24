---
description: Add a dependency edge between two bd issues
argument-hint: "<dependent-id> <prerequisite-id> [blocks|related|parent-child|discovered-from]"
---

Direction rule: **from needs to**. `bd dep add $1 $2` means issue `$1` cannot start
until `$2` is closed. Most edges are `blocks` (the only type that affects readiness);
use `related` for soft links, `parent-child` for epic hierarchy, `discovered-from` for
provenance.

Run `bd dep add $1 $2`, adding the edge type the user named if it is not `blocks`
(check `bd dep add --help` for the exact flag). Then run `bd dep tree $1` (up shows
blockers) and show the user where the edge landed.

If the user phrases the relation the other way ("A blocks B" usually means B needs A,
or does it?), confirm the direction against the "needs" phrasing before adding:
dependency-direction inversion is the classic planning bug, and a backwards graph makes
`bd ready` lie.
