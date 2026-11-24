"""Write one driver run as JSON Lines, the machine-readable form of `quarry drive --json`.

Each line on the output is one JSON object with an `event` key:

| event | fields | when |
|---|---|---|
| `run` | `goal`, `stages` (the stage names, in run order) | once, first |
| `stage` | `stage`, `state` (`running`), `issue` | a stage starts |
| `check` | `stage`, `result`, `detail`, `issue`, `session`, `epics` | check is decided |
| `log` | `text` | each line the driver prints for a person |
| `error` | `detail` | the run stopped before a check could be decided |
| `end` | `exit` | once, last; the command's exit code |

`result` is `green` or `red`. `epics` lists the bd epics the stage created, green or red;
it is empty for a stage that creates none.
"""

from __future__ import annotations

import json
from typing import Any, TextIO


class EventStream:
    """A stand-in for stdout that turns each printed line into a `log` event on `out`."""

    def __init__(self, out: TextIO) -> None:
        self._out = out
        self._pending = ""

    def write(self, text: str) -> int:
        """Buffer `text` and write one `log` event for each complete line."""
        *lines, self._pending = (self._pending + text).split("\n")
        for line in lines:
            self._emit({"event": "log", "text": line})
        return len(text)

    def flush(self) -> None:
        """Flush the underlying stream; an unfinished line stays buffered."""
        self._out.flush()

    def event(self, kind: str, **fields: Any) -> None:
        """Write one event, after any unfinished printed line, so the order is kept."""
        if self._pending:
            self._emit({"event": "log", "text": self._pending})
            self._pending = ""
        self._emit({"event": kind, **fields})

    def _emit(self, event: dict[str, Any]) -> None:
        self._out.write(json.dumps(event, ensure_ascii=False) + "\n")
        self._out.flush()
