"""Human gate 3: refuse in a driver session, before it runs, what the user does personally.

The driver names a gate file in `GATE_ENV` for each session it starts; everywhere else the
variable is unset and the `gate` guard allows at once. The file holds only what varies between
stages, the step scope: whether the stage may write. The gates never vary, so they live here,
one row per gate in `GATES`, beside the delete check, which needs path arithmetic, not a pattern.

This is pattern matching over shell text and it cannot be complete. A command is split at `&&`,
`||`, `;`, `|`, `&` and newlines outside quotes; `bash -c`, `cmd /c`, `powershell -Command` and
`$( )` are opened; heredoc bodies are dropped; each part is judged by its command word, after
shell keywords (`if`, `do`, `!`) and wrappers (`timeout`, `env`, `xargs`, `sudo`) are skipped. A
quoted argument holding whitespace is prose to the patterns, so `echo "git push"` is allowed.

`git reset` is a history rewrite with `--hard`, `--soft`, `--mixed`, `--merge` or `--keep`, or
when its first operand looks like a ref (`HEAD~1`, `HEAD^`, `@{u}`, `origin/x`, a hex id of
7 to 40 characters with a digit); `git reset HEAD file` and `git reset file` only unstage.

Known holes: a command built at run time (`eval`, `Invoke-Expression`, `-EncodedCommand`, a
variable holding the program, backtick substitution); a script, program or alias that does the
step itself (`python push.py`, `python -c`, an interpreter fed a heredoc, a git alias or hook,
`Start-Process`, `wsl`); a delete through a symlink or junction, since paths resolve as text,
or after `popd`; a wrapper's long option with a separate value (`sudo --user root git push`);
a `git reset` to a bare branch name; and every tool or flag these patterns do not name.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shlex
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from quarry_lib.guard import GATE_ENV, SHELL_TOOLS

GATE_FILE = ".quarry/gate.json"
HOOK_MATCHER = "Bash|PowerShell|Write|Edit|MultiEdit|NotebookEdit"
HOOK_TIMEOUT_SECONDS = 20
WRITE_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})
WRITE_GATE = "write"
DELETE_GATE = "delete outside the project"
PY_M = r"(?:python[\d.]*|py)(?:\s+-[\w.]+)*\s+-m\s+"
GIT = (
    r"^git(?:\s+(?:-[Cc]\s+\S+"
    r"|--(?:git-dir|work-tree|namespace|exec-path|config-env|super-prefix|attr-source)\s+\S+"
    r"|--?[\w-]+(?:=\S*)?))*\s+"
)
RESET_REF = (
    r"(?:\S*\w[~^]\S*|\S*@\{\S*|(?:origin|upstream|remotes|refs)/\S+"
    r"|(?=[0-9a-f]*\d)[0-9a-f]{7,40}(?=\s|$))"
)
GATES = (
    ("force push", re.compile(
        GIT + r"push\b(?=.*\s(?:-[a-z]*f[a-z]*|--force\S*|--mirror|\+\S+)(?:\s|$))", re.I,
    )),
    ("branch or tag delete", re.compile(
        GIT + r"(?:(?:branch|tag)\b(?=.*\s(?:-[a-z]*d[a-z]*|--delete)(?:\s|$))"
        r"|push\b(?=.*\s(?:-d|--delete|:\S+)(?:\s|$)))",
        re.I,
    )),
    ("history rewrite", re.compile(
        GIT + r"(?:(?:rebase|filter-branch|filter-repo|update-ref)\b|reflog\s+expire\b"
        r"|reset\b(?=.*\s--(?:hard|soft|mixed|merge|keep)(?:\s|$))"
        r"|reset\b(?:\s+(?!--(?:\s|$))-\S+)*\s+" + RESET_REF
        + r"|branch\b(?=.*\s(?:-[a-z]*f[a-z]*|--force)(?:\s|$))"
        r"|commit\b(?=.*\s--amend(?:\s|$))|gc\b(?=.*\s--prune))|^git-filter-repo\b",
        re.I,
    )),
    ("push", re.compile(GIT + r"push\b", re.I)),
    ("install", re.compile(
        r"^(?:pip[\d.]*|" + PY_M + r"pip[\d.]*|(?:" + PY_M + r")?uv\s+(?:pip|tool))\s+install\b"
        r"|^(?:" + PY_M + r")?uv\s+add\b"
        r"|^(?:npm|pnpm)\b(?=.*\s(?:-g|--global)(?:\s|$))(?=.*\s(?:install|i|add)(?:\s|$))"
        r"|^yarn\s+global\s+add\b"
        r"|^(?:winget|choco|scoop|apt|apt-get|brew|cargo|go|conda|mamba|micromamba|pipx)"
        r"\s+install\b"
        r"|^install-(?:module|package|script|packageprovider)\b"
        r"|^claude\s+plugins?\s+(?:install|i|update)\b"
        r"|(?:^|\s)(?:\S*[/\\])?quarry\.py\s+install\b",
        re.I,
    )),
    ("credential", re.compile(
        r"^(?:gh\s+auth|npm\s+(?:login|adduser)|docker\s+login|aws\s+configure"
        r"|claude\s+(?:auth|setup-token))\b|" + GIT + r"credential"
        r"|(?:^|[\s/\\=:])(?:\.env(?:\.(?!(?:example|sample|template|dist)(?:$|[\s;,)]))[\w.-]+)?"
        r"|id_rsa|id_ed25519|\.npmrc|\.netrc|credentials\.json"
        r"|\.aws[/\\]credentials)(?=$|[\s;,)])",
        re.I,
    )),
)
ENGINE = "quarry.py"
WRITES = re.compile(
    r"(?<![<>=-])>{1,2}(?![>&])(?!\s*(?:/dev/null|\$null|nul)(?:\s|$))"
    r"|^(?:tee|touch|mkdir|md|mv|move|cp|copy|rm|rmdir|rd|del|erase|ln|unlink|set-content"
    r"|add-content|out-file|new-item|remove-item|move-item|copy-item|rename-item|clear-content"
    r"|sc|ac|ni|ri|mi|cpi|rni)\b"
    r"|^(?:sed|perl)\b(?=.*\s(?:-i\S*|--in-place\S*)(?:\s|$))"
    r"|" + GIT + r"(?:add|commit|merge|checkout|switch|restore|stash|apply|am|cherry-pick"
    r"|revert|reset|rm|mv|clean|pull)\b",
    re.I,
)
DELETERS = frozenset({"rm", "rmdir", "rd", "del", "erase", "unlink", "remove-item", "ri"})
CHANGE_DIR = frozenset({"cd", "chdir", "pushd", "set-location", "sl", "push-location"})
SHELLS = frozenset({"bash", "sh", "zsh", "dash", "cmd", "powershell", "pwsh"})
KEYWORDS = frozenset({
    "if", "then", "else", "elif", "fi", "for", "while", "until", "do", "done", "case", "esac",
    "!", "{", "}", "(", ")",
})
WRAPPERS = {
    "sudo": frozenset({"-u", "-g", "-C", "-h", "-p"}),
    "env": frozenset({"-u", "-C", "-S"}),
    "xargs": frozenset({"-a", "-d", "-E", "-I", "-L", "-n", "-P", "-s"}),
    "nice": frozenset({"-n"}),
    "timeout": frozenset({"-k", "-s"}),
    "command": frozenset(),
    "exec": frozenset(),
    "nohup": frozenset(),
    "time": frozenset(),
    "builtin": frozenset(),
}
OPTION_VALUE = re.compile(r"-[A-Za-z][\w-]*[:=](?!\$(?:true|false)$)(.+)", re.I)
COMMAND_FLAG = re.compile(r"-[a-z]*c|-command|/[ck]", re.I)
SWITCH = re.compile(r"/[a-z]", re.I)
ASSIGNMENT = re.compile(r"[A-Za-z_]\w*=\S*")
SEPARATOR = re.compile(r"\|\||&&|(?<![<>])&(?!>)|\||;|\r?\n")
QUOTED = re.compile(r'"[^"]*"|\'[^\']*\'')
HEREDOC = re.compile(r"(<<-?[ \t]*(['\"]?)([\w.-]+)\2[^\n]*)\n.*?\n[ \t]*\3[ \t]*(?=\r?\n|$)", re.S)
CONTINUATION = re.compile(r"[\\`]\r?\n")
SUBSTITUTION = re.compile(r"\$\(([^()]*)\)")
UNRESOLVED = re.compile(r"[$%`]")
DOT_GLOB = re.compile(r"(?:^|[/\\])\.[*?\[]")
GIT_BASH_DRIVE = re.compile(r"^/([a-zA-Z])(?=/|$)")
EXECUTABLE_SUFFIX = re.compile(r"\.(?:exe|cmd|bat|com|ps1)$", re.I)


@contextlib.contextmanager
def stage_scope(project_root: Path, stage: str, writing: bool) -> Iterator[dict[str, str]]:
    """Write the gate file for one driver session, yield the environment naming it, remove it.

    The file is replaced atomically, so the guard never reads half of it; a missing or
    unreadable file denies writing.
    """
    path = project_root / GATE_FILE
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"stage": stage, "writing": writing}), encoding="utf-8")
    os.replace(temporary, path)
    try:
        yield {GATE_ENV: str(path)}
    finally:
        path.unlink(missing_ok=True)


def hook_settings() -> dict[str, Any]:
    """Return the settings that register the human-gate hook for one driver session only.

    The hook is passed with `--settings` and never declared in the plugin manifest, so an
    interactive session starts no gate process on its tool calls.
    """
    engine = (Path(__file__).resolve().parents[1] / "quarry.py").as_posix()
    hook = {
        "type": "command",
        "command": f'"{Path(sys.executable).as_posix()}" "{engine}" guard gate',
        "timeout": HOOK_TIMEOUT_SECONDS,
    }
    return {"hooks": {"PreToolUse": [{"matcher": HOOK_MATCHER, "hooks": [hook]}]}}


def judge(tool_name: str, tool_input: dict[str, Any], cwd: str | None, gate_file: Path) -> str:
    """Return the deny reason for one tool call in a driver session, or "" to allow it.

    Args:
        cwd: the payload's working directory, against which relative paths resolve; None
            falls back to this process's own.
        gate_file: the file the driver named in `GATE_ENV`; the project is the folder that
            holds its `.quarry/`, and a delete must stay strictly inside that folder.
    """
    scope = _scope(gate_file)
    if tool_name in WRITE_TOOLS:
        return _reason(WRITE_GATE, scope) if scope else ""
    if tool_name not in SHELL_TOOLS:
        return ""
    root = os.path.abspath(gate_file.parent.parent)
    return _command(str(tool_input.get("command", "")), cwd or os.getcwd(), root, scope)


def _scope(gate_file: Path) -> str | None:
    """Return why the step scope denies writing, or None when the stage may write."""
    try:
        state = json.loads(gate_file.read_text(encoding="utf-8"))
        if state["writing"] is True:
            return None
        return f"the {state['stage']} stage's step scope denies writing"
    except (OSError, ValueError, KeyError, TypeError):
        return f"the gate file {gate_file} is missing or unreadable, so writing is denied"


def _command(text: str, cwd: str | None, root: str, scope: str | None) -> str:
    """Return the deny reason for the first part of a shell command that meets a gate."""
    text = CONTINUATION.sub(" ", HEREDOC.sub(r"\1", text))
    for inner in SUBSTITUTION.findall(text):
        if reason := _command(inner, cwd, root, scope):
            return reason
    for part in _parts(text):
        words = _words(part)
        if not words:
            continue
        program = words[0]
        nested = _nested(words) if program in SHELLS else None
        if nested is not None:
            if reason := _command(nested, cwd, root, scope):
                return reason
            continue
        line = " ".join([program, *(_shown(word) for word in words[1:])])
        for gate, pattern in GATES:
            if pattern.search(line):
                return _reason(gate, f"`{' '.join(part.split())}` is one")
        if program in CHANGE_DIR:
            targets = _targets(words[1:])
            cwd = _location(targets[0] if targets else "~", cwd)
        elif program in DELETERS:
            for target in _targets(words[1:]):
                if reason := _delete(target, cwd, root):
                    return reason
        if scope and WRITES.search(line):
            return _reason(WRITE_GATE, scope)
    return ""


def _parts(text: str) -> Iterator[str]:
    """Yield the commands of a shell line, split at the separators that stand outside quotes."""
    masked = QUOTED.sub(lambda match: " " * len(match.group()), text)
    start = 0
    for match in SEPARATOR.finditer(masked):
        yield text[start:match.start()]
        start = match.end()
    yield text[start:]


def _words(part: str) -> list[str]:
    """Return a command's words, keywords and wrappers dropped and the program name bare."""
    text = part.strip(" \t\r{}()")
    try:
        words = shlex.split(text, posix=False)
    except ValueError:
        words = text.split()
    while words:
        name = _bare(words[0])
        if name in KEYWORDS or ASSIGNMENT.fullmatch(words[0]):
            words.pop(0)
        elif name in WRAPPERS:
            words.pop(0)
            while words and len(words[0]) > 1 and words[0].startswith("-"):
                if words.pop(0) in WRAPPERS[name] and words:
                    words.pop(0)
            if name == "timeout" and words:
                words.pop(0)
        else:
            words[0] = name
            break
    return words


def _bare(word: str) -> str:
    """Return a program word as its lower-case name without directory or executable suffix."""
    name = _unquote(word).replace("\\", "/").rsplit("/", 1)[-1]
    return EXECUTABLE_SUFFIX.sub("", name).lower()


def _nested(words: list[str]) -> str | None:
    """Return the command a shell wrapper runs from its `-c`, `/c` or `-Command`, or None."""
    for index, word in enumerate(words[1:], 1):
        if COMMAND_FLAG.fullmatch(word):
            return " ".join(_unquote(rest) for rest in words[index + 1:])
    return None


def _unquote(word: str) -> str:
    """Return a word without the matching quotes around it."""
    if len(word) >= 2 and word[0] == word[-1] and word[0] in "'\"":
        return word[1:-1]
    return word


def _shown(word: str) -> str:
    """Return a word as the patterns see it: a quoted word holding whitespace becomes ''.

    A quoted path to `quarry.py` in a folder whose name holds a space stays `quarry.py`, so
    the install gate still sees the engine command.
    """
    bare = _unquote(word)
    if bare == word or not any(char.isspace() for char in bare):
        return bare
    return ENGINE if bare.replace("\\", "/").rsplit("/", 1)[-1].lower() == ENGINE else "''"


def _targets(words: list[str]) -> list[str]:
    """Return a command's operands: non-switch words and option values joined by `:` or `=`."""
    targets = []
    for word in words:
        joined = OPTION_VALUE.fullmatch(word)
        if joined:
            targets.append(_unquote(joined.group(1)))
        elif not (word.startswith("-") or SWITCH.fullmatch(word)):
            targets.append(_unquote(word))
    return targets


def _location(target: str, cwd: str | None) -> str | None:
    """Return the absolute path a target names, or None when the command text cannot tell."""
    if UNRESOLVED.search(target) or DOT_GLOB.search(target):
        return None
    if os.name == "nt":
        target = GIT_BASH_DRIVE.sub(r"\1:/", target)
    target = os.path.expanduser(target)
    if cwd is None and not os.path.isabs(target):
        return None
    return os.path.normpath(os.path.join(cwd or "", target))


def _delete(target: str, cwd: str | None, root: str) -> str:
    """Return the deny reason when a delete target is not strictly inside the project."""
    path = _location(target, cwd)
    if path is None:
        return _reason(DELETE_GATE, (
            f"{target} cannot be resolved from the command text (a variable, a glob that can "
            "match .., or a cd that could not be followed), so it counts as outside"
        ))
    if os.path.normcase(path).startswith(os.path.normcase(root) + os.sep):
        return ""
    return _reason(DELETE_GATE, f"{target} resolves to {path}, not inside the project {root}")


def _reason(gate: str, detail: str) -> str:
    """Return the deny message: the gate's name, why it applies, and who does the step."""
    return (
        f"human gate: {gate}. The user does this step personally, so the Quarry driver refused "
        f"it before it ran: {detail}. Do not retry it another way; leave it for the user."
    )
