"""A Beta Cohort recruiting Draft: the message the agent writes for the Founder to send, and every deterministic check
it must pass before the launcher offers it.

Two messages share one shape. The invitation goes to the Waitlist entries the launcher chose; the Waitlist ask goes
to people who have not signed up, when the pool is too small to fill the cohort. Neither names anyone: the agent
never learns who is invited, and the Founder resolves addresses and sends.

The checks decide only what text can decide. Nothing in the file looks like an email address, and a Draft that does
is removed, never quoted in any record (FR-11). The message carries no link, since how the Founder invites is the
Founder's undecided call. Every package line it cites is in Mandu, word for word, on the line it names. Every number
it states is in one of those lines, so a spot count the package does not hold cannot be invented. An invitation cites
the thesis's K8 files and says that the first session is recorded and how many minutes it takes. Every field passes
the brand lint, whose one rule source is Mandu's brand-rules.json. Whether the message is identity-framed and reads
well is the agent's judgment and the Founder's.
"""

from __future__ import annotations

import hashlib
import re
import stat
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from . import package
from .drafts import Verdict, norm, sections, text_of
from .lint import Copy, Rules, snippet
from .waitlist import looks_like_address

INVITATION = "beta-invitation"
WAITLIST_ASK = "waitlist-ask"
PURPOSES = (INVITATION, WAITLIST_ASK)
FRONT_KEYS = ("draft", "product", "purpose")
SECTIONS = ("Subject", "Message", "Sources")
SOURCE_LINES = ("Quote", "File")
FILE_LINE = re.compile(r"`([^`]+)` line (\d+)")
MIN_QUOTE_WORDS = 4
MAX_QUOTE = 300
MAX_MESSAGE = 2500
UNREAD = "could not be read"  # how a cited line's problem starts when its file is there and the read failed
# A web address: a scheme, www., or a dotted name ending in letters, such as testflight.apple.com or reptoday.app.
LINK = re.compile(
    r"\b[a-z][a-z0-9+.-]*://\S+|\bwww\.\S+|(?<![\w.@-])(?:[a-z0-9-]+\.)+[a-z]{2,}(?![\w-])", re.IGNORECASE
)
DIGITS = re.compile(r"\d+(?:[.,]\d+)*")
# Numbers written as words, read as the figure they state; "one" is left out, since it is rarely a count.
NUMBER_WORDS = {
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
    "dozen": "12",
    "fifteen": "15",
    "twenty": "20",
    "thirty": "30",
    "forty": "40",
    "fifty": "50",
    "sixty": "60",
    "ninety": "90",
    "hundred": "100",
    "thousand": "1000",
}
WORD = re.compile(r"[A-Za-z]+")
MINUTES = re.compile(r"(\d+)[\s-]*(?:minutes?|mins?)\b", re.IGNORECASE)
SPELLED_MINUTES = re.compile(rf"\b({'|'.join(NUMBER_WORDS)})[\s-]*(?:minutes?|mins?)\b", re.IGNORECASE)
RECORDED = re.compile(r"\brecord(?:ed|ing|ings|s)?\b", re.IGNORECASE)
HOLDS_ADDRESS = (
    "holds something that looks like an email address; a recruiting Draft never carries one, and the Founder resolves"
    " addresses when sending"
)


@dataclass(frozen=True)
class Citation:
    quote: str
    path: str
    line: int


@dataclass
class MessageDraft:
    path: str
    sha256: str
    holds_address: bool = False
    fields: dict[str, str] = field(default_factory=dict)
    title: str = ""
    subject: str = ""
    message: str = ""
    citations: list[Citation] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def purpose(self) -> str:
        return self.fields.get("purpose", "")

    def copies(self) -> list[Copy]:
        """What the person who gets the message reads."""
        return [Copy("subject", self.subject), Copy("message", self.message)]


@dataclass
class Context:
    """What every recruiting Draft of one run is checked against."""

    product: str
    mandu: Path
    citable: Sequence[package.Source]  # the package sources this workflow reads, so a Draft may cite their lines
    k8: str  # the Mandu-relative folder of the thesis and its K8 rubric
    rules: Rules | None
    rules_problem: str = ""


# Reading a Draft.


def parse(text: str, path: str) -> MessageDraft:
    """A recruiting Draft, or one whose problems say what does not follow the format. A Draft holding anything that
    looks like an email address is not read further, so no problem and no record ever repeats what it holds."""
    draft = MessageDraft(path, hashlib.sha256(text.encode("utf-8")).hexdigest())
    if looks_like_address(text):
        draft.holds_address = True
        return draft
    problems = draft.problems
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---" or "---" not in [line.strip() for line in lines[1:]]:
        problems.append("the Draft must start with front matter between --- lines")
        return draft
    end = 1 + [line.strip() for line in lines[1:]].index("---")
    for line in lines[1:end]:
        key, colon, value = line.partition(":")
        key = key.strip()
        if not colon or key not in FRONT_KEYS or key in draft.fields:
            problems.append(f"front matter line {line.strip()!r} is not one of: {', '.join(FRONT_KEYS)}, once each")
        else:
            draft.fields[key] = value.strip()
    if draft.fields.get("draft") != "message":
        problems.append("front matter needs draft: message")
    if draft.purpose not in PURPOSES:
        problems.append(f"front matter needs purpose: one of {', '.join(PURPOSES)}")
    if not draft.fields.get("product"):
        problems.append("front matter needs product")
    body = lines[end + 1 :]
    found = sections(body, "## ")
    first = next((index for index, line in enumerate(body) if line.startswith("## ")), len(body))
    titles = [line for line in body[:first] if line.startswith("# ")]
    if len(titles) != 1:
        problems.append("the Draft needs exactly one # title line, above its sections")
    else:
        draft.title = titles[0][2:].strip()
    names = [name for name, _ in found]
    if names != list(SECTIONS):
        problems.append(f"the Draft holds exactly these sections, in order: {', '.join('## ' + n for n in SECTIONS)}")
        return draft
    content = dict(found)
    draft.subject = text_of(content["Subject"])
    draft.message = text_of(content["Message"])
    if not draft.subject or "\n" in draft.subject:
        problems.append("## Subject holds the subject on one line")
    if not draft.message:
        problems.append("## Message is empty")
    elif len(draft.message) > MAX_MESSAGE:
        problems.append(f"## Message is {len(draft.message)} characters; keep it under {MAX_MESSAGE}")
    parse_sources(draft, content["Sources"])
    return draft


def parse_sources(draft: MessageDraft, lines: Sequence[str]) -> None:
    items: list[list[str]] = []
    for line in lines:
        if line.startswith("- "):
            items.append([line[2:]])
        elif line.startswith("  ") and line.strip() and items:
            items[-1].append(line.strip())
        elif line.strip():
            draft.problems.append(f"## Sources holds only source items; found {snippet(line)!r}")
    shape = '- Quote: "<words copied from the package line>", then File: `<path in Mandu>` line <n>'
    for item in items:
        values = dict(part.partition(":")[::2] for part in item)
        values = {label.strip(): value.strip() for label, value in values.items()}
        located = FILE_LINE.fullmatch(values.get("File", ""))
        quote = values.get("Quote", "")
        if list(values) != list(SOURCE_LINES) or not located or len(quote) < 2 or quote[0] != '"' or quote[-1] != '"':
            draft.problems.append(f"each source is {shape}; got {snippet(item[0])!r}")
            continue
        draft.citations.append(Citation(quote[1:-1].strip(), located.group(1), int(located.group(2))))
    if not items:
        draft.problems.append(f"## Sources needs at least one source: {shape}")


# Checking a Draft.


def numbers(text: str) -> list[str]:
    """Every figure the text states, as digits: the numbers written in digits, and those written as words."""
    found = [match.group(0).replace(",", "") for match in DIGITS.finditer(text)]
    return found + [NUMBER_WORDS[word.casefold()] for word in WORD.findall(text) if word.casefold() in NUMBER_WORDS]


def cited_line(context: Context, citation: Citation) -> tuple[str | None, str]:
    """The line a citation names, read from Mandu, or why it cannot be used. Only a file of a package source this
    workflow reads may be cited, so the path the agent wrote never reaches anywhere else."""
    relative = citation.path
    if relative.startswith("/") or ".." in relative.split("/"):
        return None, "is not a path inside Mandu"
    if not any(source.covers(relative) for source in context.citable):
        return None, "is not a package file this workflow reads; cite the files the brief names"
    path = context.mandu / relative
    try:
        if package.file_type(path) != stat.S_IFREG:
            return None, "is not a file in Mandu"
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        return None, f"{UNREAD} ({getattr(error, 'strerror', None) or type(error).__name__})"
    if not 1 <= citation.line <= len(lines):
        return None, f"has no line {citation.line}"
    return lines[citation.line - 1], ""


def check_citations(draft: MessageDraft, context: Context, verdict: Verdict) -> list[Citation]:
    """The citations whose quote is on the line they name, word for word; every other one blocks the Draft."""
    verified = []
    for citation in draft.citations:
        where = f"`{citation.path}` line {citation.line}"
        if len(citation.quote.split()) < MIN_QUOTE_WORDS or len(citation.quote) > MAX_QUOTE:
            verdict.block(
                "source-quote",
                f"the quote from {where} must be {MIN_QUOTE_WORDS} words or more and at most {MAX_QUOTE} characters:"
                " only the words the message uses",
            )
            continue
        line, problem = cited_line(context, citation)
        if line is None:
            # A package file that is there and could not be read says nothing of the quote.
            lost = f"{where} in Mandu {problem}" if problem.startswith(UNREAD) else ""
            verdict.block("source-quote", f"{where} {problem}", unread=lost)
        elif norm(citation.quote) not in norm(line):
            verdict.block("source-quote", f"{where} does not hold the quote {snippet(citation.quote, 80)!r}")
        else:
            verified.append(citation)
    return verified


def check_session(draft: MessageDraft, context: Context, verified: Sequence[Citation], verdict: Verdict) -> None:
    """An invitation explains the first session K8 needs: it cites the thesis's K8 files, says the session is
    recorded, so nobody agrees without knowing, and says how many minutes it takes."""
    if not any(citation.path.startswith(context.k8) for citation in verified):
        verdict.block(
            "k8-citation",
            f"cites no line of the thesis's K8 files in `{context.k8}`; an invitation explains the first session K8"
            " needs and cites it",
        )
    if not RECORDED.search(draft.message):
        verdict.block("session-recorded", "does not say that the first session is recorded", "message")
    if not MINUTES.search(draft.message) and not SPELLED_MINUTES.search(draft.message):
        verdict.block(
            "session-length",
            "does not say how many minutes the first session takes, as a package line the Draft cites gives it",
            "message",
        )


def evaluate(draft: MessageDraft, context: Context, purpose: str) -> Verdict:
    """Every deterministic check of one recruiting Draft; it is offered to the Founder only when nothing blocks it."""
    verdict = Verdict()
    if draft.holds_address:
        # Nothing else is checked, so no finding can quote the Draft.
        verdict.block("no-address", HOLDS_ADDRESS)
        return verdict
    if context.rules is None:
        lost = "brand-rules.json could not be used"
        verdict.block("brand-rules.json", f"could not be used: {context.rules_problem}", unread=lost)
    if draft.problems:
        for problem in draft.problems:
            verdict.block("format", problem)
        return verdict
    if draft.purpose != purpose:
        verdict.block("format", f"this file holds the {purpose} Draft, so its front matter says purpose: {purpose}")
    if draft.fields["product"] != context.product:
        verdict.block("format", f"the Product recruiting its Beta Cohort is {context.product}")
    for copy in draft.copies():
        for match in LINK.finditer(copy.text):
            verdict.block(
                "no-link",
                f"carries a link or web address, {match.group(0)!r}; how the Founder invites is the Founder's call,"
                " so a recruiting Draft carries none",
                copy.field,
            )
    verified = check_citations(draft, context, verdict)
    backed = {figure for citation in verified for figure in numbers(citation.quote)}
    for copy in draft.copies():
        for figure in sorted(set(numbers(copy.text)) - backed, key=int_or_zero):
            verdict.block(
                "unbacked-number",
                f"states the figure {figure}, which no package line the Draft cites holds; a recruiting Draft states"
                " no count, spot number, or figure of its own",
                copy.field,
            )
    if purpose == INVITATION:
        check_session(draft, context, verified, verdict)
    if context.rules is not None:
        verdict.add(context.rules.check(draft.copies()))
    return verdict


def int_or_zero(figure: str) -> float:
    try:
        return float(figure)
    except ValueError:
        return 0.0
