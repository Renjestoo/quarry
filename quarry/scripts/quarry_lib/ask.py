"""Answer one question from preserved text by matching it and returning the lines around it."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from quarry_lib.packets import AskResult, Passage
from quarry_lib.sealing import verify_unit_source
from quarry_lib.search import read_lines, unit_lines, unit_texts
from quarry_lib.store import MeshStore

TERM_PATTERN = re.compile(r"[0-9a-z]+")
MIN_TERM_CHARS = 3
MIN_STEM_CHARS = 4
MAX_TERMS = 12
OPENING_CHARS = 96
USER_HEADER = "USER:"
SUFFIXES = ("ings", "ing", "ies", "ed", "es", "ly", "s")
LENGTH_BALANCE = 0.75

STOPWORDS = frozenset({
    "about", "after", "again", "against", "all", "also", "and", "any", "are", "because",
    "been", "before", "being", "between", "both", "but", "can", "cant", "could", "did",
    "does", "doing", "done", "dont", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "her", "here", "hers", "him", "his", "how",
    "into", "its", "itself", "just", "like", "made", "make", "many", "may", "might",
    "more", "most", "much", "must", "not", "now", "off", "once", "only", "other", "our",
    "out", "over", "own", "same", "she", "should", "since", "some", "such", "than",
    "that", "the", "their", "them", "then", "there", "these", "they", "this", "those",
    "through", "too", "under", "until", "use", "used", "using", "very", "was", "way",
    "well", "were", "what", "when", "where", "which", "while", "who", "whom", "why",
    "will", "with", "would", "you", "your", "yours",
})


@dataclass(frozen=True)
class AskSettings:
    """Tunable recall policy for one project mesh.

    Args:
        max_passages: most passages one answer may return. When more lines matched, the
            best-scoring ones are kept and the result is marked truncated. Measured on a
            real mesh, a terse line that answers a question can rank in the teens behind
            prose discussing it, so a tight cap throws away what better ranking just found.
        context_lines: fewest lines returned on either side of a matching line, because a
            matching line alone rarely settles a question. Block expansion widens a passage
            past this and never below it.
        max_characters: most preserved text one answer may return. The result lands in the
            caller's context window, so an uncapped one can leave no room for the turn that
            asked. The default is sized for a frontier window at a quarter of its capacity,
            converted at the densest measured content, about 1.4 characters per token.
        max_block_lines: largest blank-line-delimited block returned whole. Preserved text
            separates paragraphs, role-tagged turns, and code stanzas by blank lines, so a
            block is the unit the text was written in; a run of lines with no blank in it
            at all is not, and would otherwise spend the whole answer on one match.
        anchor_units: units the passages are drawn from, chosen by how much of the
            question's evidence each one carries, and then taking turns. A line answering a
            question is often outranked across the whole mesh by commoner lines elsewhere
            while being the strongest line in its own unit, so the units are settled before
            the lines are. Zero takes the best-scoring lines wherever they fall, as ranking
            alone would.
    """

    max_passages: int = 20
    context_lines: int = 3
    max_characters: int = 70_000
    max_block_lines: int = 24
    anchor_units: int = 4


class KnowledgeController:
    """Return the preserved passages that match one plain-language question.

    Every unit is scanned in one pass; the caller supplies only the question and never a
    unit, a line, or a pattern.
    """

    def __init__(self, store: MeshStore, settings: AskSettings | None = None) -> None:
        self.store = store
        self.settings = settings or AskSettings()

    def ask(self, question: str, exclude: frozenset[str] = frozenset()) -> AskResult:
        """Return every preserved passage matching `question`, best-scoring first in mesh order.

        Args:
            exclude: unit ids left out before ranking, so they take no anchor slot and no
                share of the passage and character budgets.

        Raises:
            SealingError: a unit's sealed evidence no longer matches what was frozen,
                checked both before the preserved text is read and again afterwards.
        """
        units = unit_texts(self.store.units_dir)
        terms = question_terms(question)
        if not units or not terms:
            return AskResult(question, (), terms, len(units), 0)
        self._verify_sources()
        scored = [line for line in self._scored_lines(units, terms) if line[1] not in exclude]
        seeds = _anchored(scored, self.settings)
        passages, shortened = self._passages(seeds)
        result = AskResult(
            question=question,
            passages=passages,
            terms=terms,
            searched_units=len(units),
            matched_lines=len(scored),
            truncated=shortened or len(scored) > len(seeds),
        )
        self._verify_sources()
        return result

    def index_entries(self) -> list[str]:
        """Return one line per unit: its id, its length, and the request that opened it."""
        entries = []
        for unit in unit_texts(self.store.units_dir):
            lines = unit_lines(self.store.units_dir, unit)
            entries.append(f"{unit} ({len(lines)} lines): {opening_line(lines)}")
        return entries

    def index(self) -> str:
        """Return the index of sealed context windows, empty when the mesh holds none."""
        entries = self.index_entries()
        return render_index(entries) if entries else ""

    def _verify_sources(self) -> None:
        """Raise unless every sealed unit is still exactly the bytes that were frozen.

        Checked again after the search as well as before it. The second check is the one
        that matters: it catches a recall that altered the very evidence it was reading,
        which is the single failure that would quietly destroy the guarantee the mesh
        exists to provide.
        """
        for unit in self.store.load_units():
            verify_unit_source(unit)

    def _scored_lines(
        self,
        units: list[str],
        terms: tuple[str, ...],
    ) -> list[tuple[tuple[float, int, int], str, int]]:
        """Return every matching line keyed for ranking: strongest evidence first, mesh order after.

        Counting matched words alone ranks prose discussing a topic above the terse line
        that answers it, because a table row or an assignment carries few of the question's
        words. A word is therefore weighted by how rare it is across the mesh, and the
        total is divided by how long the line is, since a long line gets more chances to
        match without being more relevant.
        """
        stems = [_stem(term) for term in terms]
        matches, frequency, lines, characters = self._matched_lines(units, stems)
        if not matches:
            return []
        weight = {stem: math.log(1 + lines / count) for stem, count in frequency.items()}
        average = characters / lines
        return [
            ((-sum(weight[s] for s in present) / _length_penalty(size, average), order, number),
             unit, number)
            for order, unit, number, present, size in matches
        ]

    def _matched_lines(
        self,
        units: list[str],
        stems: list[str],
    ) -> tuple[list[tuple[int, str, int, tuple[str, ...], int]], Counter[str], int, int]:
        """Scan every unit once, returning the matching lines and the corpus statistics.

        The statistics are gathered in the same pass that finds the matches, so rarity
        weighting costs no extra read of the preserved text.
        """
        matches: list[tuple[int, str, int, tuple[str, ...], int]] = []
        frequency: Counter[str] = Counter()
        lines = 0
        characters = 0
        for order, unit in enumerate(units):
            for number, line in enumerate(unit_lines(self.store.units_dir, unit), 1):
                lines += 1
                characters += len(line)
                lowered = line.casefold()
                present = tuple(stem for stem in stems if stem in lowered)
                if present:
                    frequency.update(present)
                    matches.append((order, unit, number, present, len(line)))
        return matches, frequency, lines, characters

    def _passages(
        self,
        seeds: list[tuple[tuple[float, int, int], str, int]],
    ) -> tuple[tuple[Passage, ...], bool]:
        """Return the strongest passages that fit the character budget, and whether any were cut.

        Spending the budget in score order rather than mesh order matters: the line that
        answers the question is often not the earliest one, and filling up on early
        passages would drop it. What survives is put back into mesh order, so supersession
        still reads in the order it happened.
        """
        ranges = self._seed_ranges(seeds)
        candidates = sorted(
            (_best_seed(seeds, unit, start, end), unit, start, end)
            for unit, spans in ranges.items()
            for start, end in spans
        )
        order = {unit: key[1] for key, unit, _number in seeds}
        kept: list[Passage] = []
        remaining = self.settings.max_characters
        shortened = False
        for _rank, unit, start, end in candidates:
            text = read_lines(self.store.units_dir, unit, start, end)
            if len(text) > remaining:
                shortened = True
                text = _whole_lines_within(text, remaining) or _first_line(text, kept)
                if not text:
                    continue
            kept.append(Passage(unit, start, start + text.count("\n"), text))
            remaining -= len(text)
        kept.sort(key=lambda passage: (order[passage.unit], passage.start))
        return tuple(kept), shortened

    def _seed_ranges(
        self,
        seeds: list[tuple[tuple[float, int, int], str, int]],
    ) -> dict[str, list[tuple[int, int]]]:
        """Return the line ranges to read from each unit, with overlaps already merged.

        A match is widened to the blank-line-delimited block holding it, because that block
        is the unit the text was written in: a paragraph, a role-tagged turn, or one stanza
        of code. A block too large to return whole falls back to the fixed context window,
        so a run of lines carrying no blank at all cannot spend the entire answer.

        The context window is a floor rather than an alternative. A short block is narrower
        than it, and a match sitting alone under its own heading would otherwise come back
        without the lines that answer it.
        """
        seeded: dict[str, list[int]] = {}
        for _key, unit, number in seeds:
            seeded.setdefault(unit, []).append(number)
        widened: dict[str, list[tuple[int, int]]] = {}
        for unit, numbers in seeded.items():
            lines = unit_lines(self.store.units_dir, unit)
            widened[unit] = _merged([self._widened(lines, number) for number in numbers])
        return widened

    def _widened(self, lines: list[str], number: int) -> tuple[int, int]:
        context = self.settings.context_lines
        start, end = max(1, number - context), number + context
        block_start, block_end = _block_range(lines, number)
        if block_end - block_start + 1 > self.settings.max_block_lines:
            return start, end
        return min(start, block_start), max(end, block_end)


def question_terms(question: str) -> tuple[str, ...]:
    """Return the words from `question` worth matching, in the order it used them.

    Stopwords and words shorter than three characters are dropped, because they match
    almost every line and would bury the lines that actually answer the question. A
    question left with no terms matches nothing rather than everything.
    """
    kept: list[str] = []
    for word in TERM_PATTERN.findall(question.casefold()):
        if len(word) < MIN_TERM_CHARS or word in STOPWORDS or word in kept:
            continue
        kept.append(word)
        if len(kept) == MAX_TERMS:
            break
    return tuple(kept)


def render_result(result: AskResult) -> str:
    """Return one recall answer exactly as the asking session receives it."""
    if result.found:
        passages = "".join(f"{passage.address}\n{passage.text}\n\n" for passage in result.passages)
        return (
            "These are the results from Ask_Knowledge:\n"
            "--------------------------------------------------------------\n"
            f"{passages}"
            "--------------------------------------------------------------\n"
            "This is preserved word for word from your own earlier context windows.\n"
            "Use it as the truth source for what you remember, and quote it rather than "
            "paraphrasing when it matters."
        )
    terms = ", ".join(result.terms)
    detail = (
        f"Nothing preserved contains: {terms}.\n"
        "Preserved history uses the wording it was written in, not the wording of your "
        "question. Before giving up, ask once more using the words the project itself "
        "would have used, for example a name, a file, or a decision rather than a "
        "description of one."
        if terms
        else "That question carried no words worth searching for. Ask again using the "
        "specific nouns you are after."
    )
    return (
        "There is no known knowledge about this question or request.\n"
        f"{detail}\n"
        "If asking again also comes back empty, use other known tools to find the answer, "
        "or ask the user directly."
    )


def render_index(entries: list[str]) -> str:
    """Return the session-start index of sealed context windows for host injection."""
    listed = "\n".join(f"- {entry}" for entry in entries)
    return (
        "This index lists context windows of yours that filled up before this session. "
        "They are part of this same conversation: everything in them was said by you or "
        "to you, and all of it was preserved word for word. None of it is in your context "
        "right now.\n\n"
        f"{listed}\n\n"
        "Use Ask_Knowledge whenever you need something you cannot already see in your "
        "context, and prefer it over every other tool for anything this project may have "
        "settled before: decisions, names, constraints, preferences, what a file held, "
        "what was agreed and why.\n"
        "Ask it in plain language. It searches every window listed above at once and "
        "returns the exact preserved lines, so you never name a window, a line, or a "
        "search pattern yourself.\n"
        "If it comes back with nothing, fall back to your other tools. If those cannot "
        "answer either, ask the user.\n"
        "Never invent what an earlier window said. If it is not in your context and "
        "Ask_Knowledge did not return it, you do not know it."
    )


def _length_penalty(size: int, average: int | float) -> float:
    """Return the divisor that stops a long line outranking a short one by sheer surface area.

    `LENGTH_BALANCE` is how much of the divisor ignores length. Measured on a real mesh,
    normalizing harder than this promotes trivially short lines that happen to hold a rare
    word, such as a bare import, over the line that answers the question.
    """
    return LENGTH_BALANCE + (1 - LENGTH_BALANCE) * (size / average)


def _stem(word: str) -> str:
    """Return `word` without its inflection, so a question matches how history worded it.

    Matching is by substring, so stripping the suffix from the asked word is what lets
    "booking" find "booked": the shortened form is a prefix of every inflection of it.
    Deliberately crude, since a wrong stem costs a few irrelevant lines and never an error.
    """
    for suffix in SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= MIN_STEM_CHARS:
            return word[: -len(suffix)]
    return word


def _best_seed(
    seeds: list[tuple[tuple[float, int, int], str, int]],
    unit: str,
    start: int,
    end: int,
) -> int:
    """Return the rank of the strongest seed inside a merged range, seeds being best first."""
    return min(
        position
        for position, (_key, seed_unit, number) in enumerate(seeds)
        if seed_unit == unit and start <= number <= end
    )


def _first_line(text: str, kept: list[Passage]) -> str:
    """Return the opening line when nothing else fits and nothing has been returned yet.

    A single preserved line longer than the whole budget is the one case the cap cannot
    honour, because the alternative is either an empty answer or text that is no longer
    what that line says. The line wins, and the result is marked truncated.
    """
    return "" if kept else text.split("\n", 1)[0]


def _whole_lines_within(text: str, budget: int) -> str:
    """Return as many leading lines of `text` as fit in `budget`, never splitting one.

    A passage is preserved wording at the address it names, so it is shortened by dropping
    whole lines and reporting the shorter range. Cutting inside a line would return text
    that is no longer what that line says, which is the one thing a passage may never be.
    """
    kept: list[str] = []
    used = 0
    for line in text.split("\n"):
        needed = len(line) + (1 if kept else 0)
        if used + needed > budget:
            break
        kept.append(line)
        used += needed
    return "\n".join(kept)


def _anchored(
    scored: list[tuple[tuple[float, int, int], str, int]],
    settings: AskSettings,
) -> list[tuple[tuple[float, int, int], str, int]]:
    """Return the lines to widen, drawn in turn from the units carrying the most evidence.

    A unit's evidence is the total score of every line in it that matched, so a unit
    answering the question throughout outranks one holding a single lucky line. Those
    units then take turns contributing their best remaining line.

    Taking turns is what makes this work rather than merely filtering. Measured on a real
    mesh, an answer ranked 34th across the whole mesh was the strongest line in its own
    unit, and any filter loose enough to keep a second unit also keeps the lines that were
    burying it. A turn of its own reaches it; a smaller candidate pool does not.
    """
    ranked = sorted(scored, key=lambda item: item[0])
    if not ranked or settings.anchor_units <= 0:
        return ranked[: settings.max_passages]
    evidence: dict[str, float] = {}
    for key, unit, _number in ranked:
        evidence[unit] = evidence.get(unit, 0.0) - key[0]
    chosen = sorted(evidence, key=lambda unit: -evidence[unit])[: settings.anchor_units]
    lanes = {unit: [item for item in ranked if item[1] == unit] for unit in chosen}
    drawn = [
        lanes[unit][depth]
        for depth in range(max(len(lane) for lane in lanes.values()))
        for unit in chosen
        if depth < len(lanes[unit])
    ]
    return drawn[: settings.max_passages]


def _block_range(lines: list[str], number: int) -> tuple[int, int]:
    """Return the 1-indexed bounds of the run of non-blank lines holding line `number`."""
    start = number
    while start > 1 and lines[start - 2].strip():
        start -= 1
    end = number
    while end < len(lines) and lines[end].strip():
        end += 1
    return start, end


def _merged(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Fold overlapping or touching line ranges together, so no line is returned twice."""
    merged: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def opening_line(lines: list[str]) -> str:
    """Return what opened the unit, read from its first line rather than found anywhere in it.

    Searching the whole unit for a role header finds one inside preserved text that merely
    quotes a conversation, and reports that quotation as the thing that opened the session.

    Public because the dashboard's strata page asks the same question of the same units. It
    once carried its own copy, which had already drifted to a different clip width for no
    stated reason, so both surfaces now clip at `OPENING_CHARS`.
    """
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        if line.strip() == USER_HEADER:
            return _clipped(next((rest for rest in lines[index + 1 :] if rest.strip()), ""))
        return _clipped(line)
    return ""


def _clipped(line: str) -> str:
    text = " ".join(line.split())
    return text if len(text) <= OPENING_CHARS else f"{text[:OPENING_CHARS]}..."
