"""The stage templates of a driver run: each stage's doctrine, brief and check fact.

`CHAIN` is the run order. The driver runs the stages it is given and knows nothing of what a
stage does.
"""

from __future__ import annotations

import json
from pathlib import Path

from quarry_lib import dispatch
from quarry_lib.driver import BD_TIMEOUT_SECONDS, DriverError, Fact, Stage, tool

GLOSSARY = "CONTEXT.md"
ADR_DIR = "docs/adr"
SPEC_LABEL = "ready-for-agent"
GRILL_BRIEF = f"""\
Work the goal below with the grilling method and the domain-modeling discipline in the two \
skill files at the end. Look up each fact yourself.

Record each decision in a file, because a decision that exists only in this conversation is \
lost: a term goes into {GLOSSARY} in the glossary format of domain-modeling, and a \
hard-to-reverse decision with a real trade-off goes into an ADR under {ADR_DIR}/."""
SPEC_BRIEF = f"""\
Write the spec for the goal below and publish it as one bd epic, with the spec skill file at \
the end as the method. No conversation precedes this session: where the skill says "the \
conversation", read the durable artifacts that the section "Artifacts of the earlier stages" \
names. They hold every decision that the grill stage settled. Use the terms of {GLOSSARY} \
throughout the spec.

Step 2 of the skill settles the seams. Do not confirm them with a user and do not dispatch an \
answer agent yourself: send your seam sketch to decision dispatch as a question point.

Publish with `bd create --type=epic`. Write the spec, in the template of the skill, to a file \
first and pass that file as the description with `--body-file`, because a long text on a \
command line breaks in the shell. Give the epic the acceptance criterion that the skill names \
and the label `{SPEC_LABEL}`, unless {dispatch.MODE_FILE} names another label for work that \
an agent can take. When that file is absent, `{SPEC_LABEL}` is the label: a missing file is \
a default, never a question point. Publish exactly one epic. The stage is complete when \
that epic exists; do not break it into tickets."""


def decision_files(project_root: Path) -> dict[str, bytes]:
    """Return the content of CONTEXT.md and of every file under docs/adr/, by path."""
    adr_root = project_root / ADR_DIR
    paths = [project_root / GLOSSARY, *(adr_root.rglob("*") if adr_root.is_dir() else ())]
    return {
        path.relative_to(project_root).as_posix(): path.read_bytes()
        for path in paths
        if path.is_file()
    }


def _decided(project_root: Path, before: dict[str, bytes]) -> Fact:
    """Return the grill fact: a decision file differs from `before`; a new empty file is none."""
    after = decision_files(project_root)
    changed = sorted(
        path for path in before.keys() | after.keys()
        if before.get(path, b"") != after.get(path, b"")
    )
    if not changed:
        return Fact(False, f"the stage changed neither {GLOSSARY} nor {ADR_DIR}/")
    return Fact(True, f"changed {', '.join(changed)}", tuple(changed))


def epics(project_root: Path) -> dict[str, str]:
    """Return every bd issue of type epic, open or closed, as its id and its description.

    Raises:
        DriverError: bd failed, or its answer is not a JSON array of issues.
    """
    raw = tool(
        project_root, "bd", ["list", "--type=epic", "--all", "--limit=0", "--json"],
        BD_TIMEOUT_SECONDS,
    )
    try:
        rows = json.loads(raw)
        return {row["id"]: str(row.get("description") or "") for row in rows}
    except (ValueError, TypeError, KeyError) as error:
        raise DriverError(f"bd list --type=epic gave no list of issues: {error}") from error


def _published(project_root: Path, before: frozenset[str]) -> Fact:
    """Return the spec fact: an epic that is not in `before` has a description that is not empty."""
    new = {issue: text for issue, text in epics(project_root).items() if issue not in before}
    created = tuple(sorted(new))
    filled = tuple(sorted(issue for issue, text in new.items() if text.strip()))
    if filled:
        return Fact(True, f"published epic {', '.join(filled)}", filled, created)
    if new:
        return Fact(
            False, f"the new epic {', '.join(created)} has an empty description", epics=created
        )
    return Fact(False, "no new bd issue of type epic exists")


GRILL = Stage(
    name="grill",
    skills=("grilling", "domain-modeling"),
    brief=GRILL_BRIEF,
    needs=f"record each decision in {GLOSSARY} or in an ADR under {ADR_DIR}/",
    snapshot=decision_files,
    check=_decided,
)
SPEC = Stage(
    name="spec",
    skills=("spec",),
    brief=SPEC_BRIEF,
    needs="publish the spec as a new bd issue of type epic whose description holds the spec",
    snapshot=lambda project_root: frozenset(epics(project_root)),
    check=_published,
)
CHAIN = (GRILL, SPEC)


def until(name: str | None) -> tuple[Stage, ...]:
    """Return the chain up to and including the stage called `name`; the whole chain for None.

    Raises:
        DriverError: no stage of the chain has that name.
    """
    names = [stage.name for stage in CHAIN]
    if name is None:
        return CHAIN
    if name not in names:
        raise DriverError(f"no stage is called {name!r}; the chain is {', '.join(names)}")
    return CHAIN[:names.index(name) + 1]
