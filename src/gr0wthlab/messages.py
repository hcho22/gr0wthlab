"""A message Draft: a reply to a thread, a personal-network ask, or a message to a creator, and every deterministic
check it must pass before the launcher offers it to the Founder, who alone sends or posts it.

The agent writes each Draft under workspace/drafts/messages/. The launcher, outside the sandbox, checks it and queues a
message item only for one that passes, so a message reaches the Review Queue no other way (FR-1, FR-6):

- every message cites an Angle in the bank, passes the brand lint, whose one rule source is Mandu's brand-rules.json,
  shows the code behind each behavioral claim it lists, and holds nothing that looks like an email address
  (Guardrail G6);
- a reply answers a thread whose quote the launcher validated and whose Evidence says the Product answers it, in a
  subreddit whose rules the Founder confirmed, and carries no link of any kind;
- a personal-network ask carries the personal-network Source link exactly as the Waitlist Dispatch request defines
  it, and no other link;
- a message to a creator offers one of the three things the plan allows and asks for nothing paid.

Whether the words are right, how long a message runs, and whether an ask ends on a line a friend could forward are
judgment: the agent's first, then the Founder's.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import dispatch, evidence, exchange
from .areas import Areas, Store, UnsafeFile, read_plain
from .drafts import BLOCKS, DONE, OPEN, ChecklistLine, Claim, ClaimResult, Context, Verdict, claim_pattern, none
from .drafts import parse_claims as parse_claim_items
from .exchange import plural, quoted
from .lint import APPLIED, Copy, snippet
from .queue import APPROVED, REJECTED, SUPERSEDED, Ledger
from .queue import OPEN as OPEN_ITEM
from .waitlist import looks_like_address

DRAFTS = ("messages",)
FRONT_KEYS = ("draft", "product", "purpose", "to", "angle", "offer")
SECTIONS = ("Message", "Notes", "Claims")
REPLY = "reply"
NETWORK = "network-ask"
CREATOR = "creator"
FOLLOW_UP = "creator-follow-up"
PURPOSES = (REPLY, NETWORK, CREATOR, FOLLOW_UP)
TO_CREATOR = (CREATOR, FOLLOW_UP)
# The three things the plan lets a message to a creator offer, as US-ME14 names them; never a sponsorship.
OFFERS = ("early-access", "founder-conversation", "story-material")
OFFER_WORDS = dict(zip(OFFERS, ("early access", "a founder conversation", "story material")))
MAX_NOTES = 600

# What became of a message this run.
QUEUED = "queued"
KEPT = "kept"
BLOCKED = "blocked"
MISSING = "no Draft"
APPROVED_BEFORE = "approved earlier"
REPEATED = "not queued again"
NOT_DUE = "not due"
STATUSES = (QUEUED, KEPT, BLOCKED, MISSING, APPROVED_BEFORE, REPEATED, NOT_DUE)

# Anything a reader could follow: an address with its scheme, a www. name, a bare domain, or a Markdown link.
LINK = re.compile(
    r"(?:https?://|www\.)[^\s<>\"]+"
    r"|(?<![\w@./-])(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}(?![a-z0-9-])(?:/[^\s<>\"]*)?",
    re.IGNORECASE,
)
MARKDOWN_LINK = re.compile(r"\]\(")
# Reddit turns r/name and u/name into links wherever they are typed.
MENTION = re.compile(r"(?<![\w/])[ru]/[A-Za-z0-9_-]{2,}")


# A Source link as the Waitlist Dispatch request writes it: `site/tag`, in backticks.
SOURCE_LINK = re.compile(r"`((?:[a-z0-9-]+\.)+[a-z]{2,}/([a-z0-9-]+))`")


def source_links(repo_root: Path, products: Sequence[str], tags: Sequence[str]) -> dict[str, tuple[str, str]]:
    """Each Source's link exactly as a reviewed Dispatch request defines it, with the request's path: the one place
    a link in a message may come from, so none is ever invented."""
    found: dict[str, tuple[str, str]] = {}
    for request in dispatch.load(repo_root, products)[0]:
        for link, tag in SOURCE_LINK.findall(request.item.body):
            if tag in tags:
                found.setdefault(tag, (link, request.path))
    return found


def links(text: str) -> list[str]:
    """Everything in a text a reader could follow as a link, as written, without the punctuation that ends a
    sentence."""
    found = [match.group(0).rstrip(".,;:!?)'") for match in LINK.finditer(text)]
    return found + ["a Markdown link"] * len(MARKDOWN_LINK.findall(text))


def same_link(written: str, wanted: str) -> bool:
    """Whether a link in a message is the wanted one, with or without its scheme, in any letter case."""

    def bare(link: str) -> str:
        return re.sub(r"^https?://", "", link.strip(), flags=re.IGNORECASE).rstrip("/").casefold()

    return bare(written) == bare(wanted)


# Reading a Draft.


@dataclass
class MessageDraft:
    path: str
    sha256: str
    fields: dict[str, str] = field(default_factory=dict)
    title: str = ""
    message: str = ""
    notes: str = ""
    claims: list[Claim] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def purpose(self) -> str:
        return self.fields.get("purpose", "")

    @property
    def to(self) -> str:
        return self.fields.get("to", "")

    @property
    def words(self) -> int:
        return len(self.message.split())

    def sent(self) -> list[Copy]:
        """What the person on the other side would read, named as the Founder sees it."""
        return [Copy("message", self.message)]


def parse(text: str, path: str) -> MessageDraft:
    """A message Draft, or one whose problems say what does not follow the format."""
    draft = MessageDraft(path, hashlib.sha256(text.encode("utf-8")).hexdigest())
    problems = draft.problems
    lines = text.splitlines()
    draft.fields, start = evidence.front_matter(lines, FRONT_KEYS, problems)
    if not start:
        return draft
    if draft.fields.get("draft") != "message":
        problems.append("front matter needs draft: message")
    if draft.purpose not in PURPOSES:
        problems.append(f"purpose must be one of: {', '.join(PURPOSES)}")
    for key in ("product", "to", "angle"):
        if not draft.fields.get(key):
            problems.append(f"front matter needs {key}")
    body = lines[start:]
    titles = [line for line in body if line.startswith("# ")]
    if len(titles) != 1:
        problems.append("the Draft needs exactly one # title line")
    else:
        draft.title = titles[0][2:].strip()
    content = evidence.sections(body, SECTIONS, problems)
    draft.message = content.get("Message", "")
    draft.notes = "" if none(content.get("Notes", "")) else content.get("Notes", "")
    claims = content.get("Claims", "")
    if not none(claims):
        parse_claim_items(draft, claims.splitlines())
    return draft


def read(areas: Areas, path: Path) -> tuple[MessageDraft | None, str]:
    """A Draft file the agent wrote, read without following links; None with the reason when there is none."""
    if not path.exists() and not path.is_symlink():
        return None, ""
    folder = areas.check(path.parent)
    if not areas.real_folder(folder):
        return None, f"`{areas.relative(folder)}` is not a real folder, so its Drafts were not read"
    try:
        text = read_plain(path).decode("utf-8")
    except (UnsafeFile, OSError, UnicodeDecodeError) as error:
        return None, f"`{areas.relative(path)}` could not be read ({error})"
    return parse(text, areas.relative(path)), ""


# Who a message is for, and what the run knows about them.


@dataclass
class Target:
    """One message a run may offer. reason says why none may be offered for it at all, such as a follow-up that is
    not due; everything else is what the checks and the item need about the person or thread it is for."""

    purpose: str
    key: str
    label: str
    reason: str = ""
    source_link: str = ""  # a personal-network ask: the Source link it must carry
    link_source: str = ""  # where that link is defined
    quote: evidence.Quote | None = None  # a reply: the validated quote it answers
    place: str = ""  # a reply: the subreddit, as r/name
    confirmed: str = ""  # a reply: the rules notice the Founder acknowledged
    wait_days: int = 0  # a creator: the waiting period before the one follow-up
    sent_on: str = ""  # a follow-up: when the Founder recorded the first message as sent
    plan: str = ""  # the package file that names this kind of outreach

    @property
    def public(self) -> bool:
        return self.purpose == REPLY


@dataclass(frozen=True)
class Limits:
    """What bounds every message of a run: the Product's own site, which a reply may not name in any spelling, and
    whether the Waitlist is live, before which the personal-network ask is not to be sent."""

    site: str = ""
    waitlist_live: bool = False


def run_limits(repo_root: Path, registry: Mapping, waitlist_live: bool) -> tuple[Limits, dict[str, tuple[str, str]]]:
    """A run's limits, and each Waitlist Source's link as source_links reads it; the Product's own site is the one
    those links are on."""
    products = [str(product["name"]) for product in registry.get("products", [])]
    tags = [
        tag
        for product in registry.get("products", [])
        for tag in (product.get("waitlist") or {}).get("source_tags") or ()
    ]
    links = source_links(repo_root, products, tags)
    site = next((link.split("/", 1)[0] for link, _ in links.values()), "")
    return Limits(site, waitlist_live), links


# Checking a Draft.


def site_pattern(site: str) -> re.Pattern | None:
    """The Product's site spelled so that it is no link but reads as one: its words with a spaced-out dot, or the
    word dot, between them."""
    words = [re.escape(word) for word in re.split(r"[^A-Za-z0-9]+", site) if word]
    between = r"\s*(?:\.|[(\[]?\s*dot\s*[)\]]?)\s*"
    return re.compile(between.join(words), re.IGNORECASE) if len(words) > 1 else None


def check_links(draft: MessageDraft, target: Target, limits: Limits, verdict: Verdict) -> None:
    """Which links a message may carry: a reply none, and a personal-network ask its Source link and no other."""
    for copy in draft.sent():
        found = links(copy.text)
        if draft.purpose == REPLY:
            for link in found:
                verdict.block(
                    "no-link", f"a reply carries no link of any kind; found {snippet(link, 80)!r}", copy.field
                )
            for mention in MENTION.findall(copy.text):
                verdict.block("no-link", f"{mention!r} becomes a link when it is posted", copy.field)
            pattern = site_pattern(limits.site)
            if pattern and pattern.search(copy.text) and not found:
                verdict.block("no-link", f"names the Product's site ({limits.site}), which reads as a link", copy.field)
        elif draft.purpose == NETWORK:
            for link in found:
                if not target.source_link or not same_link(link, target.source_link):
                    verdict.block(
                        "source-link",
                        f"carries {snippet(link, 80)!r}; the only link is the personal-network Source link"
                        f" `{target.source_link or 'which could not be read'}`, never an invented one",
                        copy.field,
                    )
            if target.source_link and not any(same_link(link, target.source_link) for link in found):
                verdict.block("source-link", f"does not carry the Source link `{target.source_link}`", copy.field)


def check_purpose(draft: MessageDraft, target: Target, verdict: Verdict) -> None:
    """What only one kind of message must hold."""
    if draft.purpose == REPLY:
        quote = target.quote
        if quote is None:
            verdict.block(
                "reply-evidence", f"{draft.to!r} is not validated Listening Evidence, so nothing shows the thread"
            )
        elif not quote.answerable:
            verdict.block(
                "reply-evidence",
                f"Evidence `{quote.id}` says the Product does not answer this thread, so it gets no reply",
            )
    if draft.purpose in TO_CREATOR:
        if draft.fields.get("offer") not in OFFERS:
            verdict.block(
                "ask-free", f"offer must be one of: {', '.join(OFFERS)}; a message to a creator asks for nothing else"
            )
    elif "offer" in draft.fields:
        verdict.block("format", "only a message to a creator has offer")


def checklist_status(draft: MessageDraft, context: Context, public: bool) -> list[ChecklistLine]:
    """Each pre-publication checklist line's status for a message. An open line about one named claim blocks a
    message that carries the claim; any other open line blocks only what is public, which of these is a reply."""
    carried = "\n".join([copy.text for copy in draft.sent()] + [claim.text for claim in draft.claims])
    lines = []
    for item in context.kit.checklist:
        if item.checked:
            lines.append(ChecklistLine(item, DONE, "checked"))
        elif item.claim and item.gates_social:
            if claim_pattern(item.claim).search(carried):
                lines.append(ChecklistLine(item, BLOCKS, f"the message carries the {item.claim!r} claim"))
            else:
                lines.append(ChecklistLine(item, OPEN, f"blocks only what uses the {item.claim!r} claim"))
        elif item.gates_social and public:
            lines.append(ChecklistLine(item, BLOCKS, f"open, and it blocks {', '.join(item.scope or ())}"))
        else:
            scope = f"blocks {', '.join(item.scope)}" if item.scope else "names nothing it blocks"
            lines.append(ChecklistLine(item, OPEN, scope))
    return lines


def check(draft: MessageDraft, context: Context, target: Target, limits: Limits) -> Verdict:
    """Every deterministic check of one message Draft; it is offered only when nothing blocks it."""
    verdict = Verdict()
    kit = context.kit
    for role in ("angles", "checklist"):
        if role in kit.problems:
            verdict.block("kit", f"{context.paths.get(role, role)} could not be used: {kit.problems[role]}")
    if context.rules is None:
        verdict.block("brand-rules.json", f"could not be used: {context.rules_problem}")
    if draft.problems:
        for problem in draft.problems:
            verdict.block("format", problem)
        return verdict
    if target.reason:
        verdict.block("not-offered", target.reason)
    if draft.fields["product"] != context.product:
        verdict.block("format", f"product must be {context.product}")
    if (draft.purpose, draft.to) != (target.purpose, target.key):
        verdict.block(
            "format",
            f"this file's front matter must read `purpose: {target.purpose}` and `to: {target.key}`; it reads"
            f" `purpose: {draft.purpose}` and `to: {draft.to}`",
        )
    verdict.angle = kit.angles.get(draft.fields["angle"])
    if verdict.angle is None and "angles" not in kit.problems:
        bank = context.paths.get("angles", "the Angle bank")
        verdict.block("angle-bank", f"Angle {draft.fields['angle']} is not in {bank}")
    if not draft.message.strip():
        verdict.block("format", "## Message is empty")
    if len(draft.notes) > MAX_NOTES:
        verdict.block("format", f"## Notes is at most {MAX_NOTES} characters")
    whole = "\n".join([draft.title, draft.message, draft.notes] + [claim.text for claim in draft.claims])
    if looks_like_address(whole):
        verdict.block("email-address", "the Draft holds something that looks like an email address; no Draft ever may")
    check_links(draft, target, limits, verdict)
    check_purpose(draft, target, verdict)
    if context.rules is not None:
        verdict.add(context.rules.check(draft.sent()))
        if draft.purpose in TO_CREATOR:
            for copy in draft.sent():
                verdict.add(context.rules.sponsorship(copy))
    for claim in draft.claims:
        unsupported = none(claim.location)
        problem = "no code supports it" if unsupported else context.code.verify(claim.location, claim.excerpt)
        verdict.claims.append(ClaimResult(claim, problem))
        if problem:
            verdict.block("claim-unsupported" if unsupported else "claim-location", f"{claim.text!r}: {problem}")
    verdict.checklist = checklist_status(draft, context, target.public)
    checklist = context.paths.get("checklist", "the pre-publication checklist")
    for line in verdict.checklist:
        if line.status == BLOCKS:
            verdict.block(f"{checklist} line {line.item.line}", f"{line.item.title}: {line.note}")
    return verdict


# The message item.


def excerpt(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit].rpartition(" ")[0] + " ..."


def ask(draft: MessageDraft, target: Target) -> str:
    lead = {
        REPLY: f"Approve reply in {target.place or 'a thread'}",
        NETWORK: "Approve personal-network ask",
        CREATOR: f"Approve message to {target.label}",
        FOLLOW_UP: f"Approve the one follow-up to {target.label}",
    }[draft.purpose]
    return f"{lead}: {draft.title}"[: exchange.MAX_TITLE]


def intro_lines(draft: MessageDraft, target: Target, context: Context, limits: Limits) -> list[str]:
    """What the message is, who sends it, and what the Founder should know before sending."""
    product = context.product
    if draft.purpose == REPLY:
        quote = target.quote
        return [
            f"A reply for you to post yourself, from your own account, in this {target.place} thread: {quote.link}",
            "It carries no link of any kind. gr0wthlab posts nothing and has no Reddit account.",
            f"You confirmed {target.place}'s self-promotion rules in `{target.confirmed}`.",
        ]
    if draft.purpose == NETWORK:
        live = (
            "The Waitlist is live."
            if limits.waitlist_live
            else f"Do not send it until the {product} Waitlist is live: the link does not work before then."
        )
        return [
            "A message for you to send, in your own name, to people in your own network who fit; you choose who.",
            f"It carries the personal-network Source link `{target.source_link}`, so each sign-up counts under that"
            " Source.",
            live,
        ]
    offer = OFFER_WORDS.get(draft.fields.get("offer", ""), "nothing")
    lines = [
        f"A message for you to send to {target.label}, in your own name; gr0wthlab sends nothing and holds no address.",
        f"It offers {offer} and asks for nothing: no sponsorship, no post, no reply owed.",
    ]
    if draft.purpose == CREATOR:
        lines.append(
            f"One follow-up may be offered {plural(target.wait_days, 'day')} after you record this message as sent in"
            " Mandu, only while no reply is recorded, and after it nothing more. Approving this item approves that"
            " waiting period; to set another, give it in the record when you send."
        )
    else:
        lines.append(
            f"This is the one follow-up: the first message was recorded as sent on {target.sent_on}, no reply is"
            " recorded, and the waiting period you approved has passed. After it there is no further contact."
        )
    lines.append(
        f"If {target.label} ever posts about {product} after receiving early access, that is a material connection"
        " they must disclose."
    )
    return lines


def check_lines(draft: MessageDraft, target: Target, context: Context, verdict: Verdict) -> list[str]:
    """What was checked, so no line says more than was."""
    rules = context.rules
    warnings = sorted({finding.line() for finding in verdict.warnings})
    pending = (rules.pending() if rules else []) + (
        rules.creator_pending() if rules and draft.purpose in TO_CREATOR else []
    )
    line = "- Brand lint (`brand-rules.json`, from Mandu) on the message: passed"
    if warnings:
        line += "; warnings: " + "; ".join(warnings)
    if pending:
        line += f"; rule types still waiting for their lists in Mandu, so yours to judge: {', '.join(pending)}"
    lines = [line + "."]
    if draft.purpose == REPLY:
        lines.append("- No link of any kind, no subreddit or user mention, and no site name: checked.")
    elif draft.purpose == NETWORK:
        lines.append(
            f"- The Source link is `{target.source_link}`, as `{target.link_source}` defines it, and there is no other"
            " link: checked."
        )
    elif rules and rules.has("sponsorship_asks"):
        lines.append("- No sponsorship ask the brand rules list: checked.")
    else:
        lines.append(
            "- Sponsorship asks: Mandu holds no sponsorship list yet, so no phrase check ran; whether it asks for one"
            " is yours to judge."
        )
    lines.append("- No email address: checked.")
    waiting = [line for line in verdict.checklist if line.status not in (DONE, BLOCKS)]
    if waiting:
        numbers = ", ".join(str(line.item.line) for line in waiting)
        public = "a reply is public, and none of them blocks it" if target.public else "they gate what is public"
        lines.append(
            f"- Pre-publication checklist (`{context.paths.get('checklist', 'pre-publication-checklist.md')}`): open"
            f" line{'s' if len(waiting) > 1 else ''} {numbers}; {public}."
        )
    return lines


def render(draft: MessageDraft, verdict: Verdict, context: Context, target: Target, limits: Limits) -> exchange.Item:
    """The Review Queue item for a Draft that passed: the message itself, what it rests on, and what was checked."""
    angle = verdict.angle
    roles = context.paths
    body = intro_lines(draft, target, context, limits)
    body += ["", f"**Message** ({plural(draft.words, 'word')})", ""] + quoted(draft.message)
    if draft.notes.strip():
        body += ["", "**Notes for you, never sent**", ""] + quoted(draft.notes)
    body += ["", f"**Claims, checked against {context.product} `{context.code.branch}` at `{context.code.short}`**", ""]
    if draft.claims:
        body += [f"- {claim.text} `{claim.location}` shows `{claim.excerpt}`" for claim in draft.claims]
        body.append("Only the claims listed here were checked; anything else it says the app does is yours to judge.")
    else:
        body.append(
            "It lists no behavioral claim, so none was checked; anything it says the app does is yours to judge."
        )
    body += ["", "**Checks**", ""] + check_lines(draft, target, context, verdict)
    what = {
        REPLY: f"The reply in {target.place or 'the thread'}, which only you post",
        NETWORK: "The personal-network ask, which only you send",
        CREATOR: f"The message to {target.label}, which only you send",
        FOLLOW_UP: f"The one follow-up to {target.label}, which only you send",
    }[draft.purpose]
    touches = [
        f"- {what}",
        f"- Its Draft: `{draft.path}`, in gr0wthlab's workspace",
    ]
    lines = [
        f"- Angle {angle.id}, {angle.name}: `{roles['angles']}` line {angle.line}",
        f"- Sourced pain: {excerpt(angle.pain, 300)}: `{roles['angles']}` line {angle.line}",
    ]
    if draft.purpose == REPLY:
        quote = target.quote
        lines += [
            evidence.cite(quote),
            f"- The Listening Evidence it answers: `{evidence.file_of(quote.id)}`",
            f"- {target.place}'s rules, which you confirmed: `review-queue/items/{target.confirmed}.md`",
        ]
    elif draft.purpose == NETWORK:
        lines.append(f"- The personal-network Source link: `{target.link_source}`")
        if target.plan:
            lines.append(f"- The personal-network ask and its framing: `{target.plan}`")
    elif target.plan:
        lines.append(f"- {target.label}, and what a message to a creator may offer: `{target.plan}`")
    fields = {"kind": "message", "product": context.product}
    return exchange.Item(fields, ask(draft, target), "\n".join(body), "\n".join(touches), "\n".join(lines))


# Offering a message.


@dataclass
class Slot:
    """One message a run may offer, with where its Draft is and how its earlier items stand in the Review Queue."""

    target: Target
    path: Path
    required: bool = True  # a Draft is due this run, so having none is a gap
    open: dict[str, object] | None = None
    approved: dict[str, object] | None = None
    rejected: list[dict[str, object]] = field(default_factory=list)

    def standing(self) -> str:
        if self.approved:
            return f"approved as `{self.approved['id']}`; do not draft it again"
        if self.target.reason:
            return f"not offered: {self.target.reason}"
        if self.open:
            return f"open as `{self.open['id']}` from its Draft; rewrite the Draft only to change it"
        if self.rejected:
            latest = self.rejected[-1]
            return f"rejected as `{latest['id']}`: {latest.get('reason', 'no reason recorded')}; rewrite it to answer"
        return "nothing yet; write it"


@dataclass
class Outcome:
    target: Target
    status: str
    detail: str = ""
    item: str | None = None
    draft: str | None = None
    sha256: str | None = None
    verdict: Verdict | None = None
    withdrawn: str | None = None


def marker(target: Target) -> dict[str, str]:
    """How a queue entry names the message it holds."""
    return {"purpose": target.purpose, "to": target.key}


def entries_for(ledger: Ledger, product: str, target: Target) -> list[dict[str, object]]:
    return sorted(
        (
            entry
            for entry in ledger.entries.values()
            if entry["kind"] == "message" and entry.get("product") == product and entry.get("message") == marker(target)
        ),
        key=lambda entry: (str(entry["published_at"]), str(entry["id"])),
    )


def slot_for(ledger: Ledger, product: str, target: Target, path: Path, required: bool = True) -> Slot:
    entries = entries_for(ledger, product, target)
    return Slot(
        target,
        path,
        required,
        next((entry for entry in entries if entry["status"] == OPEN_ITEM), None),
        next((entry for entry in entries if APPROVED in (entry["status"], entry.get("decided"))), None),
        [entry for entry in entries if REJECTED in (entry["status"], entry.get("decided"))],
    )


def slot_record(slot: Slot) -> dict[str, object]:
    """A slot's standing, as the launcher fixes it before the agent starts, for the agent's own check."""
    return {"open": slot.open, "approved": slot.approved, "rejected": slot.rejected, "reason": slot.target.reason}


def slug(target: Target) -> str:
    kind = {NETWORK: "network-ask", REPLY: "reply", CREATOR: "creator", FOLLOW_UP: "follow-up"}[target.purpose]
    return f"message-{kind}" if target.purpose == NETWORK else f"message-{kind}-{target.key}"[:60].rstrip("-")


def take(
    slot: Slot,
    context: Context,
    limits: Limits,
    areas: Areas,
    store: Store,
    ledger: Ledger,
    run_id: str,
    now: datetime,
    products: Sequence[str],
    publish: bool = True,
) -> Outcome | None:
    """Check one message's Draft and queue it when it passes; None when it has no Draft and none is due. With
    publish off nothing is written, and the outcome says what a run would do."""
    target = slot.target
    if slot.approved:
        detail = "the Founder approved it, so it is not asked again"
        return Outcome(target, APPROVED_BEFORE, detail, str(slot.approved["id"]))
    if target.reason:
        # Nothing may be offered for it, whatever its Draft says: an item still open is taken back, never left.
        return Outcome(target, NOT_DUE, target.reason, withdrawn=str(slot.open["id"]) if slot.open else None)
    draft, problem = read(areas, slot.path)
    if draft is None:
        if problem:
            return Outcome(target, BLOCKED, problem, withdrawn=str(slot.open["id"]) if slot.open else None)
        if slot.open:
            return Outcome(target, KEPT, "no new Draft; the open item stands", str(slot.open["id"]))
        return Outcome(target, MISSING, f"no Draft at `{areas.relative(slot.path)}`") if slot.required else None
    verdict = check(draft, context, target, limits)
    outcome = Outcome(target, BLOCKED, "", None, draft.path, draft.sha256, verdict)
    item = None
    if verdict.passed:
        item = render(draft, verdict, context, target, limits)
        text = exchange.render_item(item.fields, item.ask, item.body, item.touches, item.evidence)
        found = exchange.check_item(text, products)
        if found.item is None:
            verdict.block("item", "; ".join(found.problems))
    if not verdict.passed:
        outcome.withdrawn = str(slot.open["id"]) if slot.open else None
        return outcome
    if slot.open and slot.open.get("draft_sha256") == draft.sha256:
        outcome.status, outcome.item, outcome.detail = KEPT, str(slot.open["id"]), "its Draft is unchanged and passes"
        return outcome
    rejected = next((entry for entry in slot.rejected if entry.get("draft_sha256") == draft.sha256), None)
    if rejected:
        outcome.status, outcome.item = REPEATED, str(rejected["id"])
        outcome.detail = "the Founder rejected this Draft, so it is not asked again until it changes"
        return outcome
    outcome.status = QUEUED
    if not publish:
        return outcome
    if slot.open:
        fields = dict(item.fields, supersedes=str(slot.open["id"]))
        item = exchange.Item(fields, item.ask, item.body, item.touches, item.evidence)
    extra = {"draft": draft.path, "draft_sha256": draft.sha256, "message": marker(target)}
    identifier = ledger.publish(store, item, slug(target), run_id, now, extra)
    if slot.open:
        ledger.close(ledger.entries[str(slot.open["id"])], SUPERSEDED, run_id, now, superseded_by=identifier)
        outcome.detail = f"replaces `{slot.open['id']}`"
    outcome.item = identifier
    return outcome


def withdraw(ledger: Ledger, outcomes: Sequence[Outcome], notice: str | None, run_id: str, now: datetime) -> None:
    """Take each open message whose Draft no longer passes off the queue, as replaced by the notice that says why."""
    for outcome in outcomes:
        entry = ledger.entries.get(outcome.withdrawn or "")
        if entry and entry["status"] == OPEN_ITEM:
            ledger.close(entry, SUPERSEDED, run_id, now, superseded_by=notice or "", withdrawn=True)


# What the run report and the notice say of a set of messages.


def failing(outcome: Outcome) -> list[str]:
    """Each failing check of a blocked message on one line, the same rule and detail once with every field it is in."""
    if outcome.verdict is None:
        return [outcome.detail] if outcome.detail else []
    lines: dict[tuple[str, str], list[str]] = {}
    for finding in outcome.verdict.blocks:
        fields = lines.setdefault((finding.rule, finding.detail), [])
        if finding.field and finding.field not in fields:
            fields.append(finding.field)
    return [
        f"{rule}: {detail}" + (f" ({', '.join(fields)})" if fields else "") for (rule, detail), fields in lines.items()
    ]


def counts(outcomes: Sequence[Outcome]) -> list[str]:
    """How many messages ended each way, such as "3 queued", in a fixed order, leaving out the ways none did."""
    found = [(status, sum(1 for outcome in outcomes if outcome.status == status)) for status in STATUSES]
    return [f"{count} {status}" for status, count in found if count]


def outcome_detail(outcome: Outcome) -> str:
    parts = []
    if outcome.item and outcome.status in (QUEUED, KEPT, APPROVED_BEFORE, REPEATED):
        parts.append(f"`{outcome.item}`")
    if outcome.status == BLOCKED:
        parts += failing(outcome)
    elif outcome.detail:
        parts.append(outcome.detail)
    if outcome.withdrawn:
        parts.append(f"the open `{outcome.withdrawn}` was withdrawn")
    return "; ".join(part for part in parts if part)


def record(outcome: Outcome) -> dict[str, object]:
    """One message's outcome, for the launcher's Evidence of the run."""
    verdict = outcome.verdict
    return {
        "purpose": outcome.target.purpose,
        "to": outcome.target.key,
        "status": outcome.status,
        "detail": outcome.detail,
        "item": outcome.item,
        "withdrawn": outcome.withdrawn,
        "draft": outcome.draft,
        "draft_sha256": outcome.sha256,
        "blocks": [finding.__dict__ for finding in verdict.blocks] if verdict else [],
        "warnings": [finding.__dict__ for finding in verdict.warnings] if verdict else [],
        "claims": [
            {"claim": result.claim.text, "code": result.claim.location, "problem": result.problem}
            for result in (verdict.claims if verdict else [])
        ],
    }


def describe_rules(context: Context, creator: bool) -> list[str]:
    """What the brand lint will read in a message, for the agent's brief."""
    rules = context.rules
    if rules is None:
        return [f"- `brand-rules.json` could not be used ({context.rules_problem}), so every message is blocked."]
    applied = [row.rule for row in rules.statuses() if row.status == APPLIED]
    pending = rules.pending() + (rules.creator_pending() if creator else [])
    lines = [
        f"- Every message passes the brand lint (`{context.paths.get('brand_rules', 'brand-rules.json')}`), read on"
        f" everything that is sent: {', '.join(applied)}."
    ]
    if rules.data.get("hook_must_not_be_question"):
        lines.append("  So a message asks no question: no question mark anywhere in it.")
    if pending:
        lines.append(f"  Pending until Mandu adds their lists, so yours to keep by judgment: {', '.join(pending)}.")
    return lines
