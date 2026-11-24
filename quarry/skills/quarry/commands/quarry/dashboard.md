---
description: Start this project's dashboard if it is not up, and give the user its address
---

The dashboard starts on request, not with the MCP server, so assume it is not running.

Start it in the background, so it outlives the command that launched it:

```
"$QUARRY_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/quarry.py" dashboard
```

Then read the address:

```
"$QUARRY_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/quarry.py" url
```

Give the user that address and say what is on it: the dependency graph, a board with a
Kanban of every bd status and a roadmap in execution order, the ready queue, the sealed
strata, the activity feed, and the guide, with create, claim, reprioritize, close and link
available from the board itself. The activity page also reports median lead time, from
filed to closed, and median cycle time, from claimed to closed, over the issues that were
actually claimed.

**Run one dashboard per project, never one per session.** Starting it again is safe and
is the correct move when you are unsure: `start` adopts a board already serving this
project instead of binding a rival port, so a second start reports the running address.
Do not start another because a previous session started one, and do not start another
when `url` already prints an address.

If `url` exits 1 with `no dashboard running` right after starting it, the server is still
binding; read the address again rather than starting a second one.

The board serves this project's own bd tracker and sealed mesh, so the address stays
valid for as long as that process lives. **Never tell the user this project has no
dashboard.** If none is running, the answer is to start one.

## Stopping it

```
"$QUARRY_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/quarry.py" stop
```

Use this rather than hunting for a process id. It finds this project's board by its
recorded address and then by sweeping the ports, so it reaches one whose record was lost,
and it asks the server which project it serves before stopping anything, so another
project's board is never taken down. A board nobody has asked anything of for half an hour
also stops itself, which is what keeps an abandoned board from outliving every session
that could have used it.
