"""Serve the one Ask_Knowledge tool over stdio JSON-RPC."""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO

from quarry_lib.ask import KnowledgeController, render_result

TOOL_NAME = "Ask_Knowledge"
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INTERNAL_ERROR = -32603
TOOL_DESCRIPTION = (
    "Ask this project's preserved history one plain-language question. Every earlier "
    "context window is searched at once and the exact preserved lines are returned; you "
    "never name a unit, a line, or a search pattern."
)


def serve(controller: KnowledgeController, stdin: TextIO | None = None) -> None:
    """Read newline-delimited JSON-RPC requests and write one response line each."""
    input_stream = stdin or sys.stdin
    for line in input_stream:
        if line.strip():
            response = _answered(line, controller)
            if response is not None:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()


def _answered(line: str, controller: KnowledgeController) -> dict[str, Any] | None:
    """Return one request's response, reporting any failure as a JSON-RPC error.

    This server outlives the session that depends on it, so a malformed line or a failed
    recall is answered and stepped over. Ending the process would take away the calling
    session's only route to its own history over one bad request.
    """
    try:
        request = json.loads(line)
    except json.JSONDecodeError as error:
        return _error({}, PARSE_ERROR, f"invalid JSON-RPC request: {error}")
    if not isinstance(request, dict):
        return _error({}, INVALID_REQUEST, "JSON-RPC request must be an object")
    try:
        return _handle(request, controller)
    except Exception as error:
        return _error(request, INTERNAL_ERROR, f"{type(error).__name__}: {error}")


def _handle(
    request: dict[str, Any],
    controller: KnowledgeController,
) -> dict[str, Any] | None:
    """Return the JSON-RPC response for one request; `Ask_Knowledge` is the only tool."""
    if "id" not in request:
        return None
    method = request.get("method")
    if method == "initialize":
        result = _initialize_result()
    elif method == "tools/list":
        result = {"tools": [_tool_schema()]}
    elif method == "tools/call":
        result = _call_tool(request, controller)
    else:
        return _error(request, METHOD_NOT_FOUND, f"unknown method: {method}")
    return {"jsonrpc": "2.0", "id": request.get("id"), "result": result}


def _initialize_result() -> dict[str, Any]:
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "quarry", "version": "0.21.4"},
    }


def _tool_schema() -> dict[str, Any]:
    return {
        "name": TOOL_NAME,
        "description": TOOL_DESCRIPTION,
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "One question or search sentence, in plain language.",
                }
            },
            "required": ["question"],
        },
    }


def _call_tool(request: dict[str, Any], controller: KnowledgeController) -> dict[str, Any]:
    params = request.get("params", {})
    if params.get("name") != TOOL_NAME:
        raise ValueError("unknown tool")
    question = str(params.get("arguments", {}).get("question", ""))
    result = controller.ask(question)
    return {"content": [{"type": "text", "text": render_result(result)}], "isError": False}


def _error(request: dict[str, Any], code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request.get("id"),
        "error": {"code": code, "message": message},
    }
