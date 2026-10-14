"""The sitting page's HTML: every view of a sitting, drawn from a sitting.View, with nothing in it but text.

Everything an item, a run report, or a record holds was written by the agent, by a third party, or typed by the
Founder, so all of it is shown as text and none of it is ever markup:

- Every piece of text reaches the page through tag(), which escapes it. Only what tag() itself returns (H) is markup,
  and tag() refuses a style attribute and every event attribute, so no view can make one.
- An item is laid out by its lines, a heading line, a list line, a quoted line, a table row (document), so it reads
  as it does in its file; the text inside a line is shown exactly as written. Nothing in it becomes a link, an image,
  a style, a script, a form, or a tag.
- Every address the page links to, posts to, or loads is built here from the page's own secret base and a route, never
  from anything an item says. The page loads only its own style sheet, script, and icon, and a post's own video file.

serve.py adds the content security policy that forbids everything else.
"""

from __future__ import annotations

import html
import re
from collections.abc import Iterable, Mapping, Sequence
from urllib.parse import quote

from . import exchange, founder, sitting
from .exchange import plural
from .sitting import COUNT_LABELS, COUNTS, END, ITEM, START, Entry, Message, Recruiting, Saved, View

VOID = ("br", "hr", "input", "link", "meta", "source")
KIND_NAMES = {
    "post": "Post",
    "filming-plan": "Filming plan",
    "message": "Message",
    "weekly-read-decision": "Weekly Read decision",
    "dispatch-request": "Dispatch request",
    "package-change-proposal": "Package-change proposal",
    "notice": "Notice",
}
TALLY = "checked="  # how state.Tally.line, the first line of a run report's Summary, begins
TABLE_RULE = re.compile(r"\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?")
# A line that opens with one bold label, as the launcher writes "**Hook**, frozen in ...": the label, then the rest.
LEAD_LABEL = re.compile(r"\*\*([^*]+)\*\*(.*)", re.DOTALL)


class H(str):
    """Markup the page itself made. Any other string is text, and is escaped wherever it is used."""


def text(value: object) -> H:
    return H(html.escape(str(value), quote=True))


def join(parts: Iterable[object]) -> H:
    return H("".join(part if isinstance(part, H) else text(part) for part in parts if part is not None))


def tag(name: str, /, *children: object, **attributes: object) -> H:
    """One element. A child that is not markup of the page's own is escaped as text, and so is every attribute value;
    a style or an event attribute is refused, so nothing shown on the page can carry either."""
    parts = [name]
    for key, value in attributes.items():
        key = key.rstrip("_").replace("_", "-")
        if key == "style" or key.startswith("on"):
            raise ValueError(f"the sitting page never sets {key}")
        if value is None or value is False:
            continue
        parts.append(key if value is True else f'{key}="{html.escape(str(value), quote=True)}"')
    opening = "<" + " ".join(parts) + ">"
    return H(opening) if name in VOID else H(opening + join(children) + f"</{name}>")


# An item's text, laid out by its lines.


def cells(line: str) -> list[str]:
    row = line.strip()
    row = row[1:] if row.startswith("|") else row
    row = row[:-1] if row.endswith("|") and not row.endswith("\\|") else row
    return [cell.replace("\\|", "|").strip() for cell in re.split(r"(?<!\\)\|", row)]


def document(source: str) -> H:
    """A section of an item, laid out by its lines and shown as text.

    A line that starts a list item, a quotation, a table row, or a heading is laid out as one; a bold label that is
    a whole line, or that opens one, is shown as a label; every other line is a line of a paragraph. The rest of a
    line is never read for markup: a link, an image, a tag, or an emphasis mark in it is shown as the characters it is
    written with.
    """
    lines = source.replace("\r\n", "\n").split("\n")
    blocks: list[H] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        began = index
        if not stripped:
            index += 1
        elif stripped.startswith("```"):
            index += 1
            body = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                body.append(lines[index])
                index += 1
            index += 1
            blocks.append(tag("pre", "\n".join(body), class_="doc-code"))
        elif stripped.startswith("|") and index + 1 < len(lines) and TABLE_RULE.fullmatch(lines[index + 1].strip()):
            head = cells(line)
            index += 2
            rows = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append(cells(lines[index]))
                index += 1
            blocks.append(
                tag(
                    "div",
                    tag(
                        "table",
                        tag("thead", tag("tr", *(tag("th", cell) for cell in head))),
                        tag("tbody", *(tag("tr", *(tag("td", cell) for cell in row)) for row in rows)),
                    ),
                    class_="doc-table wide" if len(head) > 3 else "doc-table",
                )
            )
        elif stripped.startswith(">"):
            quoted = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quoted.append(lines[index].strip()[1:].lstrip(" ") if lines[index].strip() != ">" else "")
                index += 1
            blocks.append(tag("blockquote", "\n".join(quoted), class_="doc-quote"))
        elif line.startswith("- "):
            items = []
            while index < len(lines) and lines[index].startswith("- "):
                first = lines[index][2:]
                index += 1
                more = []
                while index < len(lines) and lines[index].startswith((" ", "\t")) and lines[index].strip():
                    more.append(lines[index])
                    index += 1
                indent = min((len(line) - len(line.lstrip()) for line in more), default=0)
                rest = document("\n".join(line[indent:] for line in more)) if more else None
                items.append(tag("li", tag("span", first, class_="doc-line"), rest))
            blocks.append(tag("ul", *items, class_="doc-list"))
        elif re.fullmatch(r"#{1,6} .+", stripped):
            index += 1
            blocks.append(tag("p", stripped.lstrip("#").strip(), class_="doc-label"))
        elif re.fullmatch(r"\*\*[^*]+\*\*:?", stripped):
            index += 1
            blocks.append(tag("p", stripped.strip("*:"), class_="doc-label"))
        else:
            paragraph = []
            while index < len(lines) and lines[index].strip() and not starts_block(lines, index):
                paragraph.append(lines[index].strip())
                index += 1
            lead = LEAD_LABEL.match(paragraph[0]) if paragraph else None
            if lead:
                rest = "\n".join([lead[2]] + paragraph[1:])
                blocks.append(tag("p", tag("span", lead[1], class_="doc-lead"), rest, class_="doc-text"))
            else:
                blocks.append(tag("p", "\n".join(paragraph), class_="doc-text"))
        if index == began:
            # No line is ever read twice: whatever a line is, it is shown as text and the layout moves on.
            blocks.append(tag("p", line, class_="doc-text"))
            index += 1
    return tag("div", *blocks, class_="doc")


def starts_block(lines: Sequence[str], index: int) -> bool:
    """Whether a line starts something other than a paragraph, so a paragraph ends before it."""
    line, stripped = lines[index], lines[index].strip()
    table = stripped.startswith("|") and index + 1 < len(lines) and TABLE_RULE.fullmatch(lines[index + 1].strip())
    return bool(
        stripped.startswith(("```", ">"))
        or line.startswith("- ")
        or table
        or re.fullmatch(r"#{1,6} .+", stripped)
        or re.fullmatch(r"\*\*[^*]+\*\*:?", stripped)
    )


# Words for dates, records, and states.


def moment(value: str) -> str:
    """A recorded time, in the Mac's local time, in words; the text as it stands when it is no time."""
    parsed = exchange.parse_datetime(value) if value else None
    return f"{parsed.astimezone():%A %Y-%m-%d %H:%M}" if parsed else value


def said(decision: exchange.Decision | Mapping[str, object], kind: str) -> str:
    """A decision in the words the Founder gave it."""
    get = decision.get if isinstance(decision, Mapping) else lambda key: getattr(decision, key)
    if get("decision") == exchange.APPROVE:
        word = "Acknowledged" if kind == "notice" else "Approved"
        return f"{word}, with the note: {get('note')}" if get("note") else f"{word}, with no note"
    return f"Rejected, with the reason: {get('reason')}"


def ended(words: str) -> str:
    """Words as a sentence: the Founder's own line already ends one when it closes with a mark of its own."""
    return words if words.rstrip().endswith((".", "!", "?")) else words + "."


def saved_words(saved: Saved) -> str:
    """What a record other than a decision says, in words, from the record as it was read back."""
    record = saved.record
    if saved.kind == founder.SITTINGS:
        return f"The sitting on {record.get('date')} took {plural(record.get('minutes'), 'minute')}."
    if saved.kind == founder.BETA_REPORTS:
        counts = ", ".join(
            f"{COUNT_LABELS[key].lower()} {'not reported' if record.get(key) is None else record.get(key)}"
            for key in exchange.BETA_COUNTS
        )
        return f"{record.get('product')}, on {record.get('date')}: {counts}."
    if saved.kind == founder.BETA_BUILDS:
        approved = f"{record.get('product')}: Beta Build approved on {record.get('approved_on')}"
        if record.get("recruiting") == exchange.RECRUITING_OPEN:
            return f"{approved}; recruiting is open."
        return f"{approved}; recruiting stopped on {record.get('stopped_on')}."
    if saved.kind == founder.OUTREACH:
        reply = f"a reply came on {record.get('replied_on')}" if record.get("replied_on") else "no reply recorded"
        wait = record.get("follow_up_wait_days")
        waits = f"; a follow-up waits {plural(wait, 'day')}" if wait is not None else ""
        return f"{record.get('item')}: sent on {record.get('sent_on')}; {reply}{waits}."
    return ""


def saved_lines(saved: Saved) -> list[tuple[str, str]]:
    """Every field of a record as it was read back from its file, so the Founder sees exactly what was saved."""
    return [(key, "not given" if value is None else str(value)) for key, value in saved.record.items()]


class Page:
    """The views of one sitting, each a whole HTML page. base is the page's own address with its secret, which every
    link, form, and file the page uses starts with."""

    def __init__(self, base: str):
        self.base = base

    def url(self, *parts: str, **query: str) -> str:
        path = "/".join([self.base] + [quote(part, safe="") for part in parts])
        asked = "&".join(f"{quote(key)}={quote(value, safe='')}" for key, value in query.items() if value)
        return path + ("/" if not parts else "") + (f"?{asked}" if asked else "")

    def step_url(self, step: tuple[str, str], **query: str) -> str:
        kind, key = step
        if kind == ITEM:
            return self.url("item", key, **query)
        if kind == COUNTS:
            return self.url("counts", key, **query)
        return self.url("end", **query) if kind == END else self.url(**query)

    def form(self, action: str, *children: object, **attributes: object) -> H:
        return tag("form", *children, method="post", action=action, **attributes)

    # The frame every view sits in.

    def frame(self, title: str, view: View | None, state: sitting.Sitting | None, here: str, *body: object) -> str:
        links = []
        if view is not None and not view.queue_problem:
            decided = sum(1 for entry in view.entries if entry.decided)
            label = f"Queue {decided} of {len(view.entries)} decided" if view.entries else "Queue"
            links.append(tag("a", label, href=self.url("queue"), class_="here" if here == "queue" else None))
        links.append(tag("a", "What I did", href=self.url("did"), class_="here" if here == "did" else None))
        links.append(tag("a", "End the sitting", href=self.url("end"), class_="here" if here == END else None))
        clock = None
        if state is not None and state.began is not None:
            clock = tag(
                "span",
                f"{state.minutes()} min",
                class_="clock",
                title="How long this sitting has taken, as the page measured it",
                data_minutes=state.minutes(),
            )
        head = tag(
            "head",
            tag("meta", charset="utf-8"),
            tag("meta", name="viewport", content="width=device-width, initial-scale=1"),
            tag("title", f"{title} - gr0wthlab sitting"),
            tag("link", rel="icon", href=self.url("static", "icon.svg"), type="image/svg+xml"),
            tag("link", rel="stylesheet", href=self.url("static", "page.css")),
            tag("script", src=self.url("static", "page.js"), defer=True),
        )
        bar = tag(
            "header",
            tag("a", tag("span", "gr0wthlab", class_="mark-name"), " sitting", href=self.url(), class_="mark"),
            tag("nav", *links, aria_label="Sitting"),
            clock,
            class_="bar",
        )
        return "<!doctype html>\n" + tag("html", head, tag("body", bar, tag("main", *body)), lang="en")

    def notes(self, view: View) -> H | None:
        """What the Founder should know before anything else: the run due has not finished, or a run finished and
        changed the queue since the sitting began."""
        notes = []
        if view.overdue:
            notes.append(
                tag(
                    "p",
                    tag("strong", "The weekly run due has not finished. "),
                    f"It was due {moment(view.next_run)}, so the queue and the report here are from the earlier run"
                    f" that ended {moment(view.updated_at)}. What you decide now is kept: an item that run replaces"
                    " comes back as a new item, with your decision shown beside it.",
                    class_="note warn",
                )
            )
        if view.changed:
            notes.append(
                tag(
                    "p",
                    tag("strong", "A run finished since you began. "),
                    f"The queue below is the new one, written {moment(view.updated_at)}. Every decision you gave is"
                    " kept.",
                    class_="note",
                )
            )
        return tag("div", *notes, class_="notes") if notes else None

    def refusal(self, reasons: Sequence[str]) -> H | None:
        if not reasons:
            return None
        return tag(
            "div",
            tag("p", tag("strong", "Nothing was saved.")),
            tag("ul", *(tag("li", reason[:1].upper() + reason[1:] + ".") for reason in reasons)),
            class_="refused",
            role="alert",
        )

    def record(self, saved: Saved | None, title: str = "Saved", words: str = "", folded: bool = False) -> H | None:
        """A record as it was read back from its file: every field of it, under what it says in words."""
        if saved is None:
            return None
        rows = [tag("div", tag("dt", key), tag("dd", value)) for key, value in saved_lines(saved)]
        return tag(
            "div",
            tag("p", tag("strong", f"{title}. "), words or saved_words(saved)),
            tag(
                "details",
                tag("summary", "The record, as it was read back from ", tag("code", saved.path)),
                tag("dl", *rows, class_="record"),
                open=not folded,
            ),
            class_="saved",
            role="status",
        )

    def before(self, last: tuple[Saved, Entry] | None) -> list[H | None]:
        """What was just saved for the item before this one, read back from its file, with the way to change it."""
        if last is None:
            return []
        saved, entry = last
        return [
            self.record(
                saved, "Saved", ended(f"{entry.entry.get('ask')}: {said(saved.record, entry.kind)}"), folded=True
            ),
            tag("a", "Change that decision", href=self.url("item", entry.id), class_="quiet-link"),
        ]

    def line_field(self, name: str, label: str, value: str = "", required: bool = False, hint: str = "") -> H:
        return tag(
            "label",
            tag("span", label, class_="field-name"),
            tag(
                "input",
                type="text",
                name=name,
                value=value,
                maxlength=exchange.MAX_LINE,
                required=required,
                autocomplete="off",
                spellcheck="true",
                data_counted=True,
            ),
            tag("span", hint or sitting.ONE_LINE, class_="hint"),
            class_="field",
        )

    def small_field(self, name: str, label: str, value: str = "", hint: str = "", required: bool = False) -> H:
        return tag(
            "label",
            tag("span", label, class_="field-name"),
            tag("input", type="text", name=name, value=value, required=required, autocomplete="off", class_="small"),
            tag("span", hint, class_="hint") if hint else None,
            class_="field",
        )

    # The walk.

    def start(self, view: View, state: sitting.Sitting, reasons: Sequence[str] = (), gone: str = "") -> str:
        """The first view. reasons say why an act on an item that is no longer open saved nothing, and gone names an
        item asked for that is not open, so the start view is never shown in its place without saying why."""
        why = [self.refusal(reasons)]
        if gone:
            why.append(
                tag(
                    "p",
                    "The item ",
                    tag("code", gone),
                    " is not open in the Review Queue, so there is nothing to decide on it.",
                    class_="note warn",
                )
            )
        if view.queue_problem:
            sheet = tag(
                "section",
                tag("p", "The sitting", class_="eyebrow"),
                tag("h1", "There is no Review Queue to show"),
                tag("p", view.queue_problem[:1].upper() + view.queue_problem[1:] + "."),
                tag(
                    "p",
                    "A run writes the queue: ",
                    tag("code", "src/bin/gr0wthlab run"),
                    ". You can still record what you did, and how long this sitting took.",
                ),
                class_="sheet",
            )
            answer = tag(
                "aside",
                tag("a", "What I did", href=self.url("did"), class_="button"),
                tag("a", "End the sitting", href=self.url("end"), class_="button quiet"),
                class_="answer",
            )
            return self.frame(
                "The sitting", view, state, START, *why, self.stray(view), tag("div", sheet, answer, class_="walk")
            )
        undecided = [entry for entry in view.entries if not entry.decided]
        counts: dict[str, int] = {}
        for entry in view.entries:
            counts[entry.kind] = counts.get(entry.kind, 0) + 1
        kinds = ", ".join(plural(count, KIND_NAMES.get(kind, kind).lower()) for kind, count in counts.items())
        carried = sum(1 for entry in view.entries if entry.entry.get("carried_over"))
        summary = (
            tag(
                "ul",
                # The report's first line is the launcher's own tally of the run; it is shown whole, as a figure.
                *(tag("li", line, class_="tally" if line.startswith(TALLY) else None) for line in view.summary),
                class_="summary",
            )
            if view.summary
            else tag("p", f"The run report's summary cannot be shown: {view.summary_problem}.", class_="note warn")
        )
        sheet = tag(
            "section",
            tag("p", "The sitting", class_="eyebrow"),
            tag("h1", "What the last run reports"),
            tag("p", f"Run {view.run}, written {moment(view.updated_at)}.", class_="meta"),
            summary,
            tag("p", "The whole report: ", tag("code", f"ledger/{view.report}"), class_="meta"),
            class_="sheet",
        )
        if not view.entries:
            ask = [tag("h2", "Nothing is waiting for you"), tag("p", "The Review Queue has no open item.")]
        else:
            ask = [
                tag("h2", plural(len(view.entries), "item") + " to decide"),
                tag("p", kinds[:1].upper() + kinds[1:] + "."),
            ]
            if carried:
                ask.append(tag("p", f"{plural(carried, 'item')} carried over from an earlier sitting."))
            done = len(view.entries) - len(undecided)
            if done:
                ask.append(tag("p", f"{done} already decided and waiting for the next run."))
        first = next((step for step in view.steps() if step[0] == ITEM and not view.find(step[1]).decided), None)
        target = first or view.after((START, ""))
        answer = tag(
            "aside",
            *ask,
            tag("a", "Begin" if view.entries else "Go on", href=self.step_url(target), class_="button primary"),
            tag("p", "One thing at a time. What you click is what is saved.", class_="hint"),
            class_="answer",
        )
        return self.frame(
            "The sitting",
            view,
            state,
            START,
            *why,
            self.notes(view),
            self.stray(view),
            tag("div", sheet, answer, class_="walk"),
        )

    def stray(self, view: View) -> H | None:
        """Files among the Founder's records that are no record, which the next run reports too."""
        if not view.stray:
            return None
        return tag(
            "div",
            tag("p", tag("strong", "Some files among your records are not records. "), "Nothing was taken from them:"),
            tag("ul", *(tag("li", f"{name}: {why}") for name, why in view.stray)),
            class_="note warn",
        )

    def position(self, view: View, step: tuple[str, str]) -> H:
        steps = view.steps()
        index = steps.index(step)
        items = [found for found in steps if found[0] == ITEM]
        where = f"Item {items.index(step) + 1} of {len(items)}" if step in items else ""
        return tag(
            "div",
            tag("a", "Back", href=self.step_url(view.before(step)), class_="step") if index else None,
            tag("span", where, class_="where"),
            tag("progress", value=index, max=len(steps) - 1, aria_label="How far through the sitting"),
            class_="position",
        )

    def facts(self, entry: Entry) -> list[H]:
        """What the Review Queue says of an item, beside its own text."""
        data = entry.entry
        facts = [tag("span", KIND_NAMES.get(entry.kind, entry.kind), class_="kind")]
        if data.get("product"):
            facts.append(tag("span", str(data["product"])))
        if data.get("window") and data.get("day"):
            facts.append(tag("span", f"Window {data['window']}, day {data['day']}"))
        if data.get("slot"):
            facts.append(tag("span", f"Slot {moment(str(data['slot']))}"))
        return facts

    def flags(self, entry: Entry) -> list[H]:
        data = entry.entry
        flags = []
        if data.get("carried_over"):
            flags.append(tag("p", f"Carried over from the sitting on {data.get('carried_over_from')}.", class_="flag"))
        if data.get("supersedes"):
            replaced = [tag("code", str(data["supersedes"])), "."]
            if entry.replaced is not None:
                given = f" Your decision on it, given {moment(entry.replaced.decided_at)}: "
                replaced += [given, ended(said(entry.replaced, entry.kind))]
            flags.append(tag("p", "It replaces ", *replaced, class_="flag"))
        if entry.kind == "package-change-proposal":
            declared = data.get("new_angle")
            words = {
                "yes": "This proposal declares that it adds or changes an Angle or Hook.",
                "no": "This proposal declares that it adds or changes no Angle or Hook.",
            }.get(str(declared), "This proposal declares nothing about Angles or Hooks.")
            flags.append(
                tag(
                    "p", words, " The launcher never checks that against its wording: you are the check.", class_="flag"
                )
            )
        return flags

    def item(
        self,
        view: View,
        entry: Entry,
        state: sitting.Sitting,
        reasons: Sequence[str] = (),
        typed: Mapping[str, str] | None = None,
        last: tuple[Saved, Entry] | None = None,
    ) -> str:
        typed = typed or {}
        step = (ITEM, entry.id)
        heading = [tag("p", *self.facts(entry), class_="eyebrow facts"), tag("h1", str(entry.entry.get("ask", "")))]
        heading.append(tag("p", tag("code", entry.id), class_="meta"))
        heading += self.flags(entry)
        if entry.item is None:
            body = [
                tag(
                    "p",
                    f"This item's file cannot be shown: {entry.problem}. It cannot be decided until a run has written"
                    " it again.",
                    class_="note warn",
                )
            ]
        else:
            body = []
            if entry.video is not None:
                body.append(self.video(entry))
            body += [
                tag("h2", exchange.KINDS[entry.kind]),
                document(entry.item.body),
                tag("h2", "Touches"),
                document(entry.item.touches),
                tag("h2", "Evidence"),
                document(entry.item.evidence),
            ]
        sheet = tag("section", *heading, *body, class_="sheet")
        answer = tag(
            "aside",
            self.position(view, step),
            *self.before(last),
            self.refusal(reasons),
            *self.answer(view, entry, typed),
            class_="answer",
        )
        return self.frame(
            str(entry.entry.get("ask", "")),
            view,
            state,
            ITEM,
            self.notes(view),
            tag("div", sheet, answer, class_="walk"),
        )

    def video(self, entry: Entry) -> H:
        if entry.video.problem:
            return tag(
                "p",
                f"This post shows a video, and it cannot be played here: {entry.video.problem}. The video and its copy"
                " are approved together, so this post cannot be approved until its video can be shown. ",
                tag("code", "src/bin/gr0wthlab rebuild-asset"),
                " makes a finished video again from its record and the footage.",
                class_="note warn",
            )
        return tag(
            "figure",
            tag(
                "video",
                tag("source", src=self.url("video", entry.id), type="video/mp4"),
                controls=True,
                preload="metadata",
                playsinline=True,
            ),
            tag(
                "figcaption",
                "The finished video this post shows, ",
                tag("code", str(entry.entry.get("asset"))),
                ". Approving this item approves the video and its copy together.",
            ),
            class_="video",
        )

    def answer(self, view: View, entry: Entry, typed: Mapping[str, str]) -> list[H | None]:
        """The Founder's answer to one item: approve, reject, or leave for later; or what was already saved."""
        step = (ITEM, entry.id)
        onward = tag("a", "Leave for later", href=self.step_url(view.after(step)), class_="button quiet")
        notice = entry.kind == "notice"
        if entry.taken_in:
            words = said(entry.decision, entry.kind) if entry.decision else "A decision"
            return [
                tag("h2", "Decided"),
                tag("p", f"{ended(words)} A run has taken this decision in, so it can no longer be changed."),
                tag("a", "Next", href=self.step_url(view.after(step)), class_="button primary"),
            ]
        if entry.decision is not None and not typed.get("change"):
            return [
                tag("h2", "Saved"),
                tag("p", ended(said(entry.decision, entry.kind)), class_="said"),
                tag(
                    "p",
                    f"Given {moment(entry.decision.decided_at)}. You can change it or take it back until a run takes"
                    " it in.",
                    class_="hint",
                ),
                tag("a", "Next", href=self.step_url(view.after(step)), class_="button primary"),
                tag("a", "Change it", href=self.url("item", entry.id, change="1"), class_="button quiet"),
                self.form(
                    self.url("item", entry.id, "take-back"),
                    tag("button", "Take it back", type="submit", class_="button quiet"),
                ),
            ]
        blocked = entry.may_approve()
        parts: list[H | None] = [tag("h2", "Your answer")]
        if entry.record_problem:
            parts.append(
                tag(
                    "p",
                    f"A record stands for this item that cannot be used ({entry.record_problem}), so it is not a"
                    " decision. Decide the item again and it is replaced.",
                    class_="note warn",
                )
            )
        decide = self.url("item", entry.id, "decide")
        if entry.item is not None:
            if blocked:
                parts.append(tag("p", blocked[:1].upper() + blocked[1:] + ".", class_="note warn"))
            else:
                parts.append(
                    self.form(
                        decide,
                        tag("input", type="hidden", name="decision", value=exchange.APPROVE),
                        self.line_field("line", "A note, if you want one", typed.get("note", "")),
                        tag("button", "Acknowledge" if notice else "Approve", type="submit", class_="button approve"),
                        class_="choice",
                    )
                )
            parts.append(
                self.form(
                    decide,
                    tag("input", type="hidden", name="decision", value=exchange.REJECT),
                    self.line_field("line", "The reason, in one line", typed.get("reason", ""), required=True),
                    tag("button", "Reject", type="submit", class_="button reject"),
                    class_="choice",
                )
            )
        parts.append(onward)
        if entry.decision is not None:
            parts.append(tag("a", "Keep what is saved", href=self.url("item", entry.id), class_="quiet-link"))
        parts.append(tag("p", sitting.NO_PERSON, class_="hint rule"))
        return parts

    def counts(
        self,
        view: View,
        found: Recruiting,
        state: sitting.Sitting,
        reasons: Sequence[str] = (),
        typed: Mapping[str, str] | None = None,
        saved: Saved | None = None,
        last: tuple[Saved, Entry] | None = None,
    ) -> str:
        step = (COUNTS, found.product)
        given = dict(found.today.counts) if found.today else {}
        typed = (
            typed if typed is not None else {key: "" if value is None else str(value) for key, value in given.items()}
        )
        latest = found.latest
        before = (
            tag(
                "p",
                f"Last given on {latest.day}: "
                + ", ".join(
                    f"{COUNT_LABELS[key].lower()} "
                    + ("not reported" if latest.counts.get(key) is None else str(latest.counts[key]))
                    for key in exchange.BETA_COUNTS
                )
                + ".",
                class_="meta",
            )
            if latest
            else tag("p", "No counts have been given yet.", class_="meta")
        )
        sheet = tag(
            "section",
            tag("p", tag("span", "Beta Cohort", class_="kind"), tag("span", found.product), class_="eyebrow facts"),
            tag("h1", f"How is {found.product}'s Beta Cohort going?"),
            tag(
                "p",
                "Each count is a total to date, not this week's change. They are the only Evidence gr0wthlab has of"
                " what happened after you sent invitations.",
            ),
            before,
            class_="sheet",
        )
        fields = [
            self.small_field(key, COUNT_LABELS[key], typed.get(key, ""), "A whole number, or leave it blank")
            for key in exchange.BETA_COUNTS
        ]
        answer = tag(
            "aside",
            self.position(view, step) if step in view.steps() else None,
            *self.before(last),
            self.record(saved),
            self.refusal(reasons),
            tag("h2", f"The counts on {state.day}"),
            self.form(
                self.url("counts", found.product),
                *fields,
                tag("p", "A count you leave blank is recorded as not reported, never as zero.", class_="hint"),
                tag("button", "Save the counts", type="submit", class_="button primary"),
                class_="choice",
            ),
            tag(
                "a",
                "Next" if saved else "Nothing to report",
                href=self.step_url(view.after(step)) if step in view.steps() else self.url("did"),
                class_="button quiet",
            ),
            class_="answer",
        )
        return self.frame(
            f"{found.product} Beta Cohort counts",
            view,
            state,
            COUNTS,
            self.notes(view),
            tag("div", sheet, answer, class_="walk"),
        )

    def end(
        self,
        view: View,
        state: sitting.Sitting,
        reasons: Sequence[str] = (),
        typed: Mapping[str, str] | None = None,
        last: tuple[Saved, Entry] | None = None,
    ) -> str:
        """The last view, and the one way to end a sitting from the page: one click records how long it took and
        stops the page."""
        rows = []
        for entry in view.entries:
            if entry.decision is not None:
                state_words, mark = said(entry.decision, entry.kind), entry.decision.decision
            elif entry.record_problem:
                state_words, mark = "Its record cannot be used, so it is undecided", "later"
            else:
                state_words, mark = "Left for later", "later"
            rows.append(
                tag(
                    "li",
                    tag("a", str(entry.entry.get("ask", "")), href=self.url("item", entry.id)),
                    tag("span", state_words, class_=f"state {mark}"),
                )
            )
        decided = sum(1 for entry in view.entries if entry.decided)
        left = len(view.entries) - decided
        sheet = tag(
            "section",
            tag("p", "The sitting", class_="eyebrow"),
            tag("h1", "The end of the sitting"),
            tag("p", f"{plural(decided, 'item')} decided, {left} left for later.") if view.entries else None,
            tag("ol", *rows, class_="queue") if rows else tag("p", "The Review Queue had no open item."),
            tag(
                "p",
                "The next run takes each decision in. Once this sitting is recorded, an item left for later comes"
                " back marked carried over at the next sitting.",
                class_="meta",
            ),
            class_="sheet",
        )
        measured, earlier = state.minutes(), state.earlier
        if typed is not None:
            minutes, note = typed.get("minutes", ""), typed.get("note", "")
        else:
            minutes = str(min(exchange.MAX_MINUTES, earlier + measured))
            note = (view.sitting.note or "") if view.sitting else ""
        how = f"The page measured {plural(measured, 'minute')} for this sitting."
        if earlier:
            how += (
                f" {plural(earlier, 'minute')} {'was' if earlier == 1 else 'were'} already recorded for {state.day}"
                " when it began, so the two are added below."
            )
        answer = tag(
            "aside",
            *self.before(last),
            self.refusal(reasons),
            tag("h2", "How long it took"),
            tag("p", how + " Correct the number if it is wrong.", class_="hint"),
            self.form(
                self.url("end"),
                self.small_field(
                    "minutes", "Minutes", minutes, f"A whole number from 1 to {exchange.MAX_MINUTES}", True
                ),
                self.line_field("note", "A note, if you want one", note),
                tag("button", "Record the sitting and stop the page", type="submit", class_="button primary"),
                tag(
                    "p",
                    "The page shows what was saved, then stops. To record something else first, go to What I did.",
                    class_="hint",
                ),
                class_="choice",
            ),
            tag("a", "What I did", href=self.url("did"), class_="button quiet"),
            tag(
                "p",
                "Ctrl-C in the page's terminal stops it without this record, and keeps every record you gave. The"
                " next run then knows this sitting took place only from a decision given at it. With one, it marks"
                " what you left as carried over and reports the sitting's time as not recorded. With none, the"
                " sitting leaves no mark: what you left comes back without the carried-over mark, nothing records"
                " its time, and the run report has no line for it.",
                class_="hint",
            ),
            class_="answer",
        )
        return self.frame(
            "The end of the sitting", view, state, END, self.notes(view), tag("div", sheet, answer, class_="walk")
        )

    # Beside the walk.

    def queue(self, view: View, state: sitting.Sitting) -> str:
        rows = []
        for number, entry in enumerate(view.entries, 1):
            if entry.decision is not None:
                words, mark = said(entry.decision, entry.kind), entry.decision.decision
            else:
                words, mark = "Not decided", "later"
            carried = (
                f"Carried over from {entry.entry.get('carried_over_from')}" if entry.entry.get("carried_over") else None
            )
            rows.append(
                tag(
                    "li",
                    tag("span", str(number), class_="number"),
                    tag(
                        "span",
                        tag("a", str(entry.entry.get("ask", "")), href=self.url("item", entry.id)),
                        tag("span", KIND_NAMES.get(entry.kind, entry.kind), class_="kind"),
                        tag("span", carried, class_="carried") if carried else None,
                        class_="what",
                    ),
                    tag("span", words, class_=f"state {mark}"),
                )
            )
        body = tag("ol", *rows, class_="queue numbered") if rows else tag("p", "The Review Queue has no open item.")
        sheet = tag(
            "section",
            tag("p", "The Review Queue", class_="eyebrow"),
            tag("h1", "Every open item, in the order of the sitting"),
            tag("p", view.queue_problem[:1].upper() + view.queue_problem[1:] + ".") if view.queue_problem else body,
            class_="sheet wide",
        )
        return self.frame("The Review Queue", view, state, "queue", self.notes(view), sheet)

    def did(
        self,
        view: View,
        state: sitting.Sitting,
        reasons: Sequence[str] = (),
        typed: Mapping[str, str] | None = None,
        saved: Saved | None = None,
        at: str = "",
    ) -> str:
        """The plain place for what the Founder did: a message sent, a reply received, the wait before a follow-up,
        a Beta Build approved, recruiting stopped or reopened."""
        typed = typed or {}
        top = [self.record(saved), self.refusal(reasons) if not at else None]
        builds = [
            self.build(found, state, reasons if at == f"build:{found.product}" else (), typed)
            for found in view.recruiting
        ]
        messages = [
            self.message(
                message,
                state,
                reasons if at == f"sent:{message.id}" else (),
                typed if at == f"sent:{message.id}" else {},
            )
            for message in view.messages
        ]
        sheet = tag(
            "section",
            tag("p", "Beside the sitting", class_="eyebrow"),
            tag("h1", "What I did"),
            tag(
                "p",
                "gr0wthlab sends nothing and sees no inbox, so these records are the only way it learns what you did."
                " Each can be corrected by giving it again.",
            ),
            *top,
            tag("h2", "Beta Builds"),
            *(builds or [tag("p", "No Product recruits a Beta Cohort.", class_="meta")]),
            tag("h2", "Messages you approved"),
            *(messages or [tag("p", "No message is approved yet.", class_="meta")]),
            class_="sheet wide",
        )
        return self.frame("What I did", view, state, "did", self.stray(view), sheet)

    def build(self, found: Recruiting, state: sitting.Sitting, reasons: Sequence[str], typed: Mapping[str, str]) -> H:
        product, build = found.product, found.build
        if build is None:
            warning = (
                tag(
                    "p",
                    f"A record stands for {product} that cannot be used ({found.build_problem}), so nothing shows an"
                    " approval. Recording the approval again replaces it.",
                    class_="note warn",
                )
                if found.build_problem
                else None
            )
            return tag(
                "div",
                tag("h3", product),
                tag("p", "No Beta Build is recorded, so gr0wthlab does nothing about its Beta Cohort."),
                warning,
                self.refusal(reasons),
                self.form(
                    self.url("did", "beta-build", product),
                    self.small_field(
                        "approved_on", "The day Apple approved it", typed.get("approved_on", ""), "YYYY-MM-DD", True
                    ),
                    self.line_field(
                        "build",
                        "The build's label, if you want one",
                        typed.get("build", ""),
                        hint="Such as 1.0 (42). One line.",
                    ),
                    tag(
                        "button",
                        f"Record that a {product} Beta Build passed Apple's review",
                        type="submit",
                        class_="button primary",
                    ),
                    tag(
                        "p",
                        "Only record this once Apple has approved the build for external testing: it starts Beta"
                        " Cohort recruiting at the next run.",
                        class_="hint",
                    ),
                    class_="choice",
                ),
                class_="card",
            )
        label = f", build {build.build}" if build.build else ""
        if found.open:
            standing = "Recruiting is open."
            act = self.form(
                self.url("did", "recruiting", product),
                tag("input", type="hidden", name="recruiting", value="stop"),
                self.small_field(
                    "stopped_on", "The day recruiting stopped", typed.get("stopped_on", state.day), "YYYY-MM-DD", True
                ),
                tag("button", "Stop recruiting", type="submit", class_="button reject"),
                class_="choice",
            )
        else:
            standing = f"Recruiting has been stopped since {build.stopped_on}."
            act = self.form(
                self.url("did", "recruiting", product),
                tag("input", type="hidden", name="recruiting", value="reopen"),
                tag("button", "Reopen recruiting", type="submit", class_="button primary"),
                class_="choice",
            )
        return tag(
            "div",
            tag("h3", product),
            tag("p", f"Beta Build approved on {build.approved_on}{label}. {standing}"),
            self.refusal(reasons),
            act,
            tag("a", "Give the Beta Cohort counts", href=self.url("counts", product), class_="quiet-link"),
            class_="card",
        )

    def message(self, message: Message, state: sitting.Sitting, reasons: Sequence[str], typed: Mapping[str, str]) -> H:
        record = message.record
        if record is None:
            standing = "Not recorded as sent."
        elif record.replied_on:
            standing = f"Sent on {record.sent_on}; a reply came on {record.replied_on}."
        else:
            standing = f"Sent on {record.sent_on}; no reply recorded."
        values = {
            "sent_on": record.sent_on if record else state.day,
            "replied_on": (record.replied_on or "") if record else "",
            "wait_days": str(record.wait_days) if record and record.wait_days else "",
            "note": (record.note or "") if record else "",
        }
        values.update(typed)
        warning = (
            tag(
                "p",
                f"A record stands for this message that cannot be used ({message.record_problem}). Recording it again"
                " replaces it.",
                class_="note warn",
            )
            if message.record_problem
            else None
        )
        return tag(
            "div",
            tag("h3", str(message.entry.get("ask", ""))),
            tag("p", tag("code", message.id), f" {standing}", class_="meta"),
            warning,
            self.refusal(reasons),
            self.form(
                self.url("did", "sent", message.id),
                tag(
                    "div",
                    self.small_field("sent_on", "Sent on", values["sent_on"], "YYYY-MM-DD", True),
                    self.small_field("replied_on", "A reply came on", values["replied_on"], "YYYY-MM-DD, or blank"),
                    self.small_field(
                        "wait_days",
                        "Days to wait before a follow-up",
                        values["wait_days"],
                        f"1 to {exchange.MAX_WAIT_DAYS}, or blank for the wait the message stated",
                    )
                    if message.followed_up
                    else None,
                    class_="row",
                ),
                self.line_field("note", "A note, if you want one", values["note"]),
                tag("button", "Record it" if record is None else "Correct it", type="submit", class_="button primary"),
                class_="choice",
            ),
            class_="card",
            id=f"sent-{message.id}",
        )

    # Pages that stand alone.

    def finished(self, saved: Saved) -> str:
        """What ends a sitting: the sitting record as it was read back from its file, on a page that needs nothing
        more from the server, which stops once it has sent it."""
        return self.plain(
            "The sitting has ended",
            f"Saved. {saved_words(saved)}",
            f"The record, as it was read back from {saved.path}:",
            *(f"{key}: {value}" for key, value in saved_lines(saved)),
            "Everything you saved is in ledger/founder/, and the next run takes it in.",
            "The page has stopped. You can close this tab.",
        )

    def plain(self, title: str, *lines: str) -> str:
        """A page with nothing on it but words, for an address that is not the page's or a page that has stopped."""
        return "<!doctype html>\n" + tag(
            "html",
            tag("head", tag("meta", charset="utf-8"), tag("title", title)),
            tag("body", tag("h1", title), *(tag("p", line) for line in lines)),
            lang="en",
        )
