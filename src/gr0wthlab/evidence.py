"""Listening Evidence: one record for every quote, and the checks that decide whether the launcher keeps it.

The agent writes a record for a quote as workspace/evidence/listening/<document id>.md; the launcher, outside the
sandbox, checks it against the snapshot it fetched before the agent started, and keeps only a record that passes, in
ledger/evidence/listening/quotes/, which the agent can read and never write. The checks are the ones a reader cannot
make by eye: the record names a document the run fetched, carries that document's https link and the date it was read,
repeats no link already recorded, and its quote stands in the fetched text word for word, so a quote can never be
invented or altered. Which words to quote, the theme, the Fit, and the intent are the agent's judgment.

A kept record is all that outlives the run of what was fetched: the words the agent quoted, their link, the date
read, and a hash of the document they came from. The snapshot itself is removed when the run ends.

Confidence is never the agent's to state: it is counted here, from the independent, unprompted sources behind a set of
quotes. High needs three or more, Medium two, and Low one.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from . import exchange
from .areas import Store, UnsafeFile, read_plain
from .exchange import plural
from .sources import POST, REVIEW, Document, Snapshot, flat, link_key
from .waitlist import looks_like_address

KIND = "listening"
FOLDER = ("evidence", "listening")
QUOTES = (*FOLDER, "quotes")
FRONT_KEYS = ("evidence", "product", "document", "link", "read_on", "theme", "fit", "intent", "answerable")
SECTIONS = ("Quote", "Context")
THEME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
FITS = ("strong", "partial", "none", "unclear")
INTENTS = ("asking", "venting", "comparing", "sharing", "other")
ANSWERS = ("yes", "no")
QUOTED_KINDS = (POST, REVIEW)
MIN_QUOTE_WORDS = 3
MAX_QUOTE = 600
MAX_CONTEXT = 400
MAX_THEME = 40
HIGH = "High"
MEDIUM = "Medium"
LOW = "Low"


# A record as the agent wrote it.


@dataclass
class Record:
    path: str
    fields: dict[str, str] = field(default_factory=dict)
    quote: str = ""
    context: str = ""
    problems: list[str] = field(default_factory=list)


def front_matter(lines: Sequence[str], keys: Sequence[str], problems: list[str]) -> tuple[dict[str, str], int]:
    """The key: value lines between two --- lines, each key once and one of keys, and the index after them."""
    stripped = [line.strip() for line in lines]
    if not lines or stripped[0] != "---" or "---" not in stripped[1:]:
        problems.append("the file must start with front matter between --- lines")
        return {}, 0
    end = 1 + stripped[1:].index("---")
    fields: dict[str, str] = {}
    for number, line in enumerate(lines[1:end], 2):
        key, colon, value = line.partition(":")
        key = key.strip()
        if not colon or key not in keys or key in fields:
            problems.append(f"line {number} of the front matter is not one of: {', '.join(keys)}, once each")
        else:
            fields[key] = value.strip()
    return fields, end + 1


def sections(lines: Sequence[str], wanted: Sequence[str], problems: list[str]) -> dict[str, str]:
    """The text under each ## heading, which must be exactly the wanted ones, in order."""
    found: list[tuple[str, list[str]]] = []
    for line in lines:
        if line.startswith("## "):
            found.append((line[3:].strip(), []))
        elif found:
            found[-1][1].append(line)
        elif line.strip() and not line.startswith("# "):
            problems.append("nothing may come before the first ## section but the # title line")
    if [name for name, _ in found] != list(wanted):
        problems.append(f"the sections must be exactly: {', '.join('## ' + name for name in wanted)}")
    return {name: "\n".join(body).strip() for name, body in found}


def parse(text: str, path: str) -> Record:
    """A quote record, or one whose problems say what does not follow the format."""
    record = Record(path)
    lines = text.splitlines()
    record.fields, start = front_matter(lines, FRONT_KEYS, record.problems)
    content = sections(lines[start:], SECTIONS, record.problems) if start else {}
    record.quote = content.get("Quote", "")
    record.context = content.get("Context", "")
    return record


# A record the launcher keeps.


@dataclass(frozen=True)
class Quote:
    """One validated quote. document_sha256 is the hash of the fetched document it came from, which two quotes share
    when they are one source said twice, and unprompted says the person spoke without being asked: the opening post
    of a thread, or a review."""

    id: str
    product: str
    link: str
    read_on: str
    quote: str
    context: str
    theme: str
    fit: str
    intent: str
    answerable: bool
    source: str
    kind: str
    published: str
    document_sha256: str
    unprompted: bool
    recorded_by_run: str

    def as_json(self) -> dict[str, object]:
        return dict(self.__dict__)


def check(
    record: Record,
    snapshot: Snapshot,
    recorded: Mapping[str, Quote],
    product: str,
    fit_readable: bool,
    run_id: str,
) -> tuple[Quote | None, list[str]]:
    """Every deterministic check of one record, and the quote it becomes when nothing fails."""
    problems = list(record.problems)
    fields = record.fields
    if problems:
        return None, problems
    if fields.get("evidence") != KIND:
        problems.append(f"front matter needs evidence: {KIND}")
    if fields.get("product") != product:
        problems.append(f"product must be {product}")
    document = snapshot.documents.get(fields.get("document", ""))
    link = fields.get("link", "")
    if not link:
        problems.append("a quote needs its link: the https address of the thread or review it was read from")
    elif not link.startswith("https://"):
        problems.append("the link must be an https:// address")
    read_on = fields.get("read_on", "")
    if not exchange.valid_date(read_on):
        problems.append("read_on must be the date the quote was read, as YYYY-MM-DD")
    elif read_on != snapshot.read_on:
        problems.append(f"read_on must be {snapshot.read_on}, the date this run read its sources")
    if document is None:
        problems.append(
            "the document it names is not a document in this run's snapshot; a quote is recorded only from text the"
            " launcher fetched this run"
        )
    elif document.kind not in QUOTED_KINDS:
        problems.append(f"document {document.id} is a {document.kind}; a quote is taken only from a thread or a review")
    else:
        problems += document_problems(record, document, link, recorded)
    theme = fields.get("theme", "")
    if not THEME.fullmatch(theme) or len(theme) > MAX_THEME:
        problems.append("theme must be one tag in lowercase-with-hyphens, such as lost-the-routine")
    if fields.get("fit") not in FITS:
        problems.append(f"fit must be one of: {', '.join(FITS)}")
    elif not fit_readable and fields["fit"] != "unclear":
        problems.append(
            "the package's Fit definition could not be read this run, so fit must be unclear, never a guess"
        )
    if fields.get("intent") not in INTENTS:
        problems.append(f"intent must be one of: {', '.join(INTENTS)}")
    if fields.get("answerable") not in ANSWERS:
        problems.append("answerable must be yes or no: whether the Product genuinely answers what was said")
    context = record.context
    if not context:
        problems.append("## Context is empty: say in a sentence or two where this was said and about what")
    elif len(context) > MAX_CONTEXT or "\n\n" in context:
        problems.append(f"## Context is one short paragraph of at most {MAX_CONTEXT} characters")
    if looks_like_address(record.quote) or looks_like_address(context):
        problems.append("the record holds something that looks like an email address, which no Evidence may hold")
    if problems or document is None:
        return None, problems
    return (
        Quote(
            document.id,
            product,
            document.link,
            snapshot.read_on,
            flat(record.quote),
            flat(context),
            theme,
            fields["fit"],
            fields["intent"],
            fields["answerable"] == "yes",
            document.source,
            document.kind,
            document.published,
            document.sha256,
            document.kind in QUOTED_KINDS,
            run_id,
        ),
        [],
    )


def document_problems(record: Record, document: Document, link: str, recorded: Mapping[str, Quote]) -> list[str]:
    """The checks that tie a record to the document it names: its file, its link, no repeat, and the quote itself."""
    problems = []
    if Path(record.path).stem != document.id:
        problems.append(f"name the file {document.id}.md, after the document it quotes: one record for each document")
    if link.startswith("https://") and link_key(link) != link_key(document.link):
        problems.append(f"the link is not the one document {document.id} was read from: {document.link}")
    earlier = recorded.get(document.id) or next(
        (quote for quote in recorded.values() if link_key(quote.link) == link_key(document.link)), None
    )
    if earlier is not None:
        problems.append(
            f"its link is already recorded as Evidence `{earlier.id}`, read {earlier.read_on}; a link is recorded once"
        )
    quote = flat(record.quote)
    if not quote:
        problems.append("## Quote is empty")
    elif len(quote.split()) < MIN_QUOTE_WORDS or len(quote) > MAX_QUOTE:
        problems.append(f"the quote must be {MIN_QUOTE_WORDS} words or more and at most {MAX_QUOTE} characters")
    elif quote not in flat(document.text) and quote not in flat(document.title):
        problems.append(
            f"the quote is not in the text fetched from its link, word for word; copy it from document {document.id}"
            " in the snapshot without changing, joining, or trimming inside it"
        )
    return problems


# The ledger's quotes.


def load(store: Store) -> tuple[dict[str, Quote], list[str]]:
    """Every quote the launcher has kept, by identifier, and each record there that could not be read."""
    quotes: dict[str, Quote] = {}
    problems: list[str] = []
    folder = store.path(*QUOTES)
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            data = json.loads(read_plain(path).decode("utf-8"))
            quote = Quote(**{key: data[key] for key in Quote.__dataclass_fields__})
            quotes[quote.id] = quote
        except (OSError, UnsafeFile, ValueError, KeyError, TypeError) as error:
            problems.append(f"`{store.relative(path)}` could not be read as Listening Evidence ({error})")
    return quotes, problems


def keep(store: Store, quote: Quote) -> str:
    """Write one validated quote into the ledger; its path there."""
    path = store.path(*QUOTES, f"{quote.id}.json")
    store.write_json(path, quote.as_json())
    return store.relative(path)


def file_of(quote_id: str) -> str:
    """A quote's path among the launcher's records, relative to ledger/."""
    return "/".join((*QUOTES, f"{quote_id}.json"))


def records(store: Store) -> set[str]:
    """The path of every quote the launcher keeps, relative to ledger/: what an item's Evidence names to cite one."""
    return {file_of(key) for key in load(store)[0]}


# Confidence.


def independent_sources(quotes: Sequence[Quote]) -> int:
    """How many independent, unprompted sources stand behind the quotes: one text said twice counts once."""
    return len({quote.document_sha256 for quote in quotes if quote.unprompted})


def confidence(count: int) -> str:
    return HIGH if count >= 3 else MEDIUM if count == 2 else LOW


def confidence_line(quotes: Sequence[Quote]) -> str:
    """The confidence a set of quotes carries, as a proposal cites it: "High: 4 independent unprompted sources"."""
    count = independent_sources(quotes)
    if not count:
        return "None: no independent unprompted source"
    return f"{confidence(count)}: {plural(count, 'independent unprompted source')}"


def by_theme(quotes: Sequence[Quote]) -> dict[str, list[Quote]]:
    themes: dict[str, list[Quote]] = {}
    for quote in sorted(quotes, key=lambda quote: (quote.theme, quote.read_on, quote.id)):
        themes.setdefault(quote.theme, []).append(quote)
    return themes


def cite(quote: Quote, limit: int = 300) -> str:
    """One quote as an Evidence line of a Review Queue item: where it was read and when, then the words, marked as
    every item marks a third party's text."""
    words = quote.quote if len(quote.quote) <= limit else quote.quote[: limit - 3].rstrip() + "..."
    what = "A review" if quote.kind == REVIEW else "A thread"
    lines = [f"- {what}, theme `{quote.theme}`, read {quote.read_on}: {quote.link}"]
    return "\n".join(lines + exchange.third_party(words, "  "))
