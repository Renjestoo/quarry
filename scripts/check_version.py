"""Fail when the plugin version disagrees across the files that declare it."""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFESTS = (
    Path(".claude-plugin/marketplace.json"),
    Path("quarry/.claude-plugin/plugin.json"),
    Path("quarry/.codex-plugin/plugin.json"),
    Path("quarry/.zcode-plugin/plugin.json"),
)
ENGINE = Path("quarry/scripts/quarry_lib/mcp_server.py")
PACKAGE = Path("quarry/pyproject.toml")
SERVER_INFO_VERSION = re.compile(r'"serverInfo":\s*\{[^}]*"version":\s*"([^"]+)"')


def manifest_version(path: Path) -> str:
    """Return the version declared by a plugin manifest or a marketplace entry."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if "plugins" in data:
        return str(data["plugins"][0]["version"])
    return str(data["version"])


def engine_version(path: Path) -> str:
    """Return the version the MCP server reports in its initialize response.

    Raises:
        ValueError: the serverInfo version literal is absent, which means the
            engine would answer initialize with something this check cannot see.
    """
    match = SERVER_INFO_VERSION.search(path.read_text(encoding="utf-8"))
    if match is None:
        raise ValueError(f"no serverInfo version literal found in {path}")
    return match.group(1)


def package_version(path: Path) -> str:
    """Return the version the engine package declares to its build backend.

    Raises:
        KeyError: `[project] version` is absent, which means the package would build
            under a version this check cannot see.
    """
    return str(tomllib.loads(path.read_text(encoding="utf-8"))["project"]["version"])


def main() -> int:
    """Print every declared version and return 1 when they disagree."""
    found = {relative: manifest_version(REPO_ROOT / relative) for relative in MANIFESTS}
    found[ENGINE] = engine_version(REPO_ROOT / ENGINE)
    found[PACKAGE] = package_version(REPO_ROOT / PACKAGE)
    for relative, version in found.items():
        print(f"{version:>10}  {relative.as_posix()}")
    distinct = set(found.values())
    if len(distinct) == 1:
        print(f"\nversion consistent across {len(found)} locations: {distinct.pop()}")
        return 0
    print(
        f"\nVERSION MISMATCH across {len(found)} locations: {sorted(distinct)}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
