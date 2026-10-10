"""A post Draft: the file the agent writes for one calendar day, and every deterministic check it must pass before the
launcher offers it to the Founder.

The checks follow US-ME08 and the kit in Mandu: the Draft is the calendar's day (its Angle, pair leg, and Product);
its Hook is the frozen text, opens the video and every caption, and no other Angle's Hook appears; both platforms
carry identical content; an A/B leg differs from its other leg only in the Hook; every field passes the brand-rules
lint and the platform limits; no competitor is named; every behavioral claim shows the code that supports it; and
its status against the pre-publication checklist lets it be offered. Judgment (the words themselves, and which
claims a Draft makes) is the agent's; these checks decide only what can be decided from text.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field, replace
from itertools import zip_longest

from .codebase import Code
from .kit import Angle, ChecklistItem, FrozenHook, Kit, all_hooks, frozen_hook, recut_hooks
from .lint import Copy, Finding, Platform, Rules, check_platform, hashtags, plain

FRONT_KEYS = ("draft", "product", "window", "day", "angle", "pair", "leg")
BEAT_HEADING = re.compile(r"Beat (\d+)( \(hook\))?: (\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)s")
BEAT_LINES = {"Visual action": "visual", "Spoken line": "spoken", "On-screen text": "on_screen"}
CLAIM_LINES = ("Claim", "Code", "Shows")
UNITS = (
    (r"milliseconds?|ms|msecs?", r"(?:ms|msecs?|milliseconds?)"),
    (r"seconds?|secs?", r"(?:s|secs?|seconds?)"),
    (r"minutes?|mins?", r"(?:mins?|minutes?)"),
)
DONE = "done"
OPEN = "open"
BLOCKS = "blocks"


def norm(text: str) -> str:
    """Text compared as written: typographic quotes made plain and spacing collapsed, case kept."""
    return " ".join(plain(text).split())


def none(text: str) -> bool:
    return norm(text).casefold() in ("", "none")


@dataclass
class Beat:
    number: int
    hook: bool
    start: float
    end: float
    visual: str = ""
    spoken: str = ""
    on_screen: str = ""


@dataclass
class Claim:
    text: str
    location: str
    excerpt: str


@dataclass
class PostDraft:
    path: str
    sha256: str
    fields: dict[str, str] = field(default_factory=dict)
    title: str = ""
    hook: str = ""
    beats: list[Beat] = field(default_factory=list)
    platforms: dict[str, dict[str, str]] = field(default_factory=dict)
    claims: list[Claim] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    def number(self, key: str) -> int | None:
        value = self.fields.get(key, "")
        return int(value) if re.fullmatch(r"[0-9]+", value) else None

    @property
    def day(self) -> int | None:
        return self.number("day")

    def copies(self) -> list[Copy]:
        """Every field a viewer reads, named as the Founder sees it."""
        copies = [Copy("Hook", self.hook, hook=True)]
        for beat in self.beats:
            for key, label in (("spoken", "spoken line"), ("on_screen", "on-screen text")):
                text = getattr(beat, key)
                if not none(text):
                    copies.append(Copy(f"beat {beat.number} {label}", text))
        for platform, values in self.platforms.items():
            copies += [
                Copy(f"{platform} {name.lower()}", text, description=name == "Alt text")
                for name, text in values.items()
                if not none(text)
            ]
        return copies


# Reading a Draft.


def sections(lines: Sequence[str], marker: str) -> list[tuple[str, list[str]]]:
    found: list[tuple[str, list[str]]] = []
    for line in lines:
        if line.startswith(marker):
            found.append((line[len(marker) :].strip(), []))
        elif found:
            found[-1][1].append(line)
    return found


def text_of(lines: Sequence[str]) -> str:
    return "\n".join(lines).strip()


def parse(text: str, path: str) -> PostDraft:
    """A post Draft, or one whose problems say what does not follow the format."""
    draft = PostDraft(path, hashlib.sha256(text.encode("utf-8")).hexdigest())
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
    if draft.fields.get("draft") != "post":
        problems.append("front matter needs draft: post")
    for key in ("product", "window", "day", "angle"):
        if not draft.fields.get(key):
            problems.append(f"front matter needs {key}")
    for key in ("window", "day"):
        if draft.fields.get(key) and draft.number(key) is None:
            problems.append(f"{key} must be a whole number")
    if ("pair" in draft.fields) != ("leg" in draft.fields):
        problems.append("a pair leg names both pair and leg")
    body = lines[end + 1 :]
    titles = [line for line in body if line.startswith("# ")]
    if len(titles) != 1:
        problems.append("the Draft needs exactly one # title line")
    else:
        draft.title = titles[0][2:].strip()
    found = sections(body, "## ")
    names = [name for name, _ in found]
    for name in ("Hook", "Beats", "Claims"):
        if names.count(name) != 1:
            problems.append(f"the Draft needs exactly one ## {name} section")
    content = {name: section for name, section in found}
    draft.hook = text_of(content.get("Hook", []))
    if not draft.hook or "\n" in draft.hook:
        problems.append("## Hook holds the Hook on one line")
    parse_beats(draft, content.get("Beats", []))
    for name, section in found:
        if name in ("Hook", "Beats", "Claims"):
            continue
        if name in draft.platforms:
            problems.append(f"## {name} appears twice")
        values: dict[str, str] = {}
        for field_name, field_lines in sections(section, "### "):
            if field_name in values:
                problems.append(f"## {name} names ### {field_name} twice")
            values[field_name] = text_of(field_lines)
        draft.platforms[name] = values
    parse_claims(draft, content.get("Claims", []))
    return draft


def parse_beats(draft: PostDraft, lines: Sequence[str]) -> None:
    found = sections(lines, "### ")
    if not found:
        draft.problems.append("## Beats needs at least the hook beat, as ### Beat 1 (hook): 0-3s")
    for heading, section in found:
        match = BEAT_HEADING.fullmatch(heading)
        if not match:
            draft.problems.append(f"beat heading {heading!r} must read like Beat 2: 3-8s, with (hook) on beat 1")
            continue
        beat = Beat(int(match.group(1)), bool(match.group(2)), float(match.group(3)), float(match.group(4)))
        for line in section:
            label, colon, value = line.removeprefix("- ").partition(":") if line.startswith("- ") else ("", "", "")
            if colon and label in BEAT_LINES:
                setattr(beat, BEAT_LINES[label], value.strip())
            elif line.strip():
                draft.problems.append(f"beat {beat.number}: {line.strip()!r} is not one of {', '.join(BEAT_LINES)}")
        for label, key in BEAT_LINES.items():
            if not getattr(beat, key):
                draft.problems.append(f"beat {beat.number} needs - {label}: (write none if there is none)")
        draft.beats.append(beat)
    numbers = [beat.number for beat in draft.beats]
    if draft.beats and numbers != list(range(1, len(numbers) + 1)):
        draft.problems.append("beats are numbered 1, 2, 3, ... in order")
    if draft.beats and (not draft.beats[0].hook or draft.beats[0].start != 0):
        draft.problems.append("beat 1 is the hook beat, marked (hook), starting at 0s")
    if any(beat.hook for beat in draft.beats[1:]):
        draft.problems.append("only beat 1 is the hook beat")
    for earlier, later in zip(draft.beats, draft.beats[1:]):
        if later.start < earlier.end or later.end <= later.start:
            draft.problems.append(f"beat {later.number}'s time must follow beat {earlier.number}'s")


def parse_claims(draft: PostDraft, lines: Sequence[str]) -> None:
    items: list[list[str]] = []
    for line in lines:
        if line.startswith("- "):
            items.append([line[2:]])
        elif line.startswith("  ") and line.strip() and items:
            items[-1].append(line.strip())
        elif line.strip():
            draft.problems.append(f"## Claims holds only claim items; found {line.strip()!r}")
    for item in items:
        values: dict[str, str] = {}
        for line in item:
            label, colon, value = line.partition(":")
            if colon and label.strip() in CLAIM_LINES:
                values[label.strip()] = value.strip()
        if list(values) != list(CLAIM_LINES):
            draft.problems.append(
                f"each claim is - Claim:, then Code: `path:line`, then Shows: `code`; got {item[0]!r}"
            )
            continue
        location, excerpt = values["Code"].strip("`"), values["Shows"]
        if excerpt.startswith("`") and excerpt.endswith("`") and len(excerpt) > 1:
            excerpt = excerpt[1:-1]
        draft.claims.append(Claim(values["Claim"], location, excerpt))


# Checking a Draft.


@dataclass
class ChecklistLine:
    item: ChecklistItem
    status: str
    note: str


@dataclass
class ClaimResult:
    claim: Claim
    problem: str | None


@dataclass
class Verdict:
    blocks: list[Finding] = field(default_factory=list)
    warnings: list[Finding] = field(default_factory=list)
    checklist: list[ChecklistLine] = field(default_factory=list)
    claims: list[ClaimResult] = field(default_factory=list)
    hook: FrozenHook | None = None
    angle: Angle | None = None

    @property
    def passed(self) -> bool:
        return not self.blocks

    def add(self, findings: Sequence[Finding]) -> None:
        for finding in findings:
            (self.blocks if finding.blocks else self.warnings).append(finding)

    def block(self, rule: str, detail: str, where: str = "") -> None:
        self.blocks.append(Finding(rule, where, detail))


@dataclass
class Context:
    """What every Draft of one run is checked against."""

    product: str
    window: int
    kit: Kit
    rules: Rules | None
    rules_problem: str | None
    platforms: Mapping[str, Platform]
    code: Code
    paths: Mapping[str, str]  # kit role: its Mandu-relative path, for citations


def claim_pattern(claim: str) -> re.Pattern:
    """A named claim, such as "under 100 milliseconds", as text that carries it: its number with any spelling of
    its unit, or the words themselves when it has no number."""
    parts = []
    for number, unit in re.findall(r"(\d+(?:\.\d+)?)\s*-?\s*([a-z]+)", claim, re.IGNORECASE):
        spelled = next((spelling for written, spelling in UNITS if re.fullmatch(written, unit, re.IGNORECASE)), None)
        if spelled:
            parts.append(rf"(?<![\d.]){re.escape(number)}\s*-?\s*{spelled}(?!\w)")
    if not parts:
        parts.append(r"\s+".join(re.escape(word) for word in claim.split()))
    return re.compile("|".join(parts), re.IGNORECASE)


def checklist_status(draft: PostDraft, context: Context, angle: Angle | None) -> list[ChecklistLine]:
    """Each checklist item's status for this post: done, open but not gating it, or blocking it.

    An open item blocks a post when its blocking scope covers social posts (everything public, or social); an item
    about one named claim blocks only a post that carries the claim or whose Angle depends on it.
    """
    carried = "\n".join([copy.text for copy in draft.copies()] + [claim.text for claim in draft.claims])
    pair = context.kit.pairs.get(draft.fields.get("pair", ""))
    depends = "\n".join(filter(None, [angle.row if angle else "", pair.text if pair else ""]))
    lines = []
    for item in context.kit.checklist:
        if item.checked:
            lines.append(ChecklistLine(item, DONE, "checked"))
        elif not item.gates_social:
            scope = f"blocks {', '.join(item.scope)} only" if item.scope else "names no asset it blocks"
            lines.append(ChecklistLine(item, OPEN, scope))
        elif item.claim:
            pattern = claim_pattern(item.claim)
            if pattern.search(carried):
                lines.append(ChecklistLine(item, BLOCKS, f"the Draft carries the {item.claim!r} claim"))
            elif pattern.search(depends):
                lines.append(ChecklistLine(item, BLOCKS, f"Angle {draft.fields.get('angle')} depends on the claim"))
            else:
                lines.append(ChecklistLine(item, OPEN, f"blocks only assets that use the {item.claim!r} claim"))
        else:
            lines.append(ChecklistLine(item, BLOCKS, f"open, and it blocks {', '.join(item.scope or ())}"))
    return lines


def evaluate(
    draft: PostDraft, context: Context, reference: PostDraft | None = None, file_day: int | None = None
) -> Verdict:
    """Every deterministic check of one Draft; the Draft is offered for approval only when nothing blocks it.

    reference is the Draft of its A/B pair's other leg, when that leg is the one this Draft must match beyond the
    Hook; file_day is the day its file name gives, which its front matter must name too.
    """
    verdict = Verdict()
    kit = context.kit
    for role, problem in sorted(kit.problems.items()):
        verdict.block("kit", f"{context.paths.get(role, role)} could not be used: {problem}")
    if context.rules is None:
        verdict.block("brand-rules.json", f"could not be used: {context.rules_problem}")
    if draft.problems:
        for problem in draft.problems:
            verdict.block("format", problem)
        return verdict
    calendar = context.paths.get("calendar", "the calendar")
    if file_day is not None and draft.day != file_day:
        verdict.block("calendar", f"the Draft in the file for day {file_day} says day {draft.day}")
    day = kit.days.get(draft.day or 0)
    if draft.fields["product"] != context.product or draft.number("window") != context.window:
        verdict.block("calendar", f"the window being prepared is {context.product} window {context.window}")
    if day is None:
        verdict.block("calendar", f"day {draft.day} is not in {calendar}")
        return verdict
    expected = (day.angle, day.pair, day.leg)
    actual = (draft.fields["angle"], draft.fields.get("pair"), draft.fields.get("leg"))
    if day.angle is not None and actual != expected:
        leg = f" / {day.pair} leg {day.leg}" if day.pair else ""
        verdict.block("calendar", f"day {day.day} is {day.angle}{leg} in {calendar} line {day.line}")
    if day.angle is not None and day.angle not in kit.angles:
        verdict.block("angle-bank", f"Angle {day.angle} is not in {context.paths.get('angles', 'the Angle bank')}")
        return verdict
    verdict.hook, why = frozen_hook(day, kit)
    verdict.angle = kit.angles.get(draft.fields["angle"])
    if verdict.hook is None:
        verdict.block("frozen-hook", why)
    else:
        check_hook(draft, verdict.hook, context, verdict)
    opening = {norm(hook).casefold() for hook in recut_hooks(day, kit)}
    check_isolation(draft, kit, opening, verdict)
    check_beats(draft, verdict)
    check_platforms(draft, context, verdict)
    if reference is not None and verdict.hook is not None:
        check_pair(draft, reference, context, opening, verdict)
    if context.rules is not None:
        verdict.add(context.rules.check(draft.copies()))
        check_pain(verdict.angle, context, verdict)
    check_competitors(draft, kit, context, verdict)
    check_claims(draft, context.code, verdict)
    verdict.checklist = checklist_status(draft, context, verdict.angle)
    checklist = context.paths.get("checklist", "the pre-publication checklist")
    for line in verdict.checklist:
        if line.status == BLOCKS:
            verdict.block(f"{checklist} line {line.item.line}", f"{line.item.title}: {line.note}")
    return verdict


def check_hook(draft: PostDraft, hook: FrozenHook, context: Context, verdict: Verdict) -> None:
    where = f"{context.paths.get(hook.source, hook.source)} line {hook.line}"
    frozen = norm(hook.text)
    if norm(draft.hook) != frozen:
        verdict.block("frozen-hook", f"## Hook differs from the Hook frozen in {where}: {hook.text!r}")
    if draft.beats and norm(draft.beats[0].on_screen) != frozen:
        verdict.block("frozen-hook", "beat 1's on-screen text must be the frozen Hook, word for word")
    for platform, values in draft.platforms.items():
        facts = context.platforms.get(platform)
        if facts is None:
            continue
        body = values.get(facts.field("body").name, "")
        if norm(body.splitlines()[0] if body.strip() else "") != frozen:
            verdict.block(
                "frozen-hook", f"the {platform} {facts.field('body').name.lower()}'s first line must be the Hook"
            )
        title = facts.field("title")
        if title is not None and norm(values.get(title.name, "")) != frozen:
            verdict.block("frozen-hook", f"the {platform} {title.name.lower()} must be the Hook")


def check_isolation(draft: PostDraft, kit: Kit, opening: Collection[str], verdict: Verdict) -> None:
    """A Hook belongs to one Angle and one leg, so no other Hook appears anywhere in a Draft; only a later beat of a
    re-cut pair's leg may show the pair's other Hook, one of opening, which the re-cut moves out of the first beat."""
    own = norm(draft.hook).casefold()
    angle = draft.fields.get("angle")
    reported = set()
    for copy in draft.copies():
        text = norm(copy.text).casefold()
        video_after_hook = copy.field.startswith("beat ") and not copy.field.startswith("beat 1 ")
        for hook, owner in all_hooks(kit):
            folded = norm(hook).casefold()
            if folded == own or folded not in text or (folded in opening and video_after_hook):
                continue
            if (hook, copy.field) in reported:
                continue
            reported.add((hook, copy.field))
            whose = "another leg of this Angle" if owner == angle else f"Angle {owner}"
            verdict.block("hook-isolation", f"carries the Hook of {whose}: {hook!r}", copy.field)


def check_beats(draft: PostDraft, verdict: Verdict) -> None:
    if not draft.beats:
        return
    hook = draft.beats[0]
    if not none(hook.spoken) and norm(hook.spoken).casefold() == norm(hook.on_screen).casefold():
        verdict.warnings.append(
            Finding(
                "hook-channels", "beat 1", "the spoken line repeats the on-screen text; they work best apart", False
            )
        )
    if none(hook.visual):
        verdict.block("format", "the hook beat needs a visual action")


def check_platforms(draft: PostDraft, context: Context, verdict: Verdict) -> None:
    """Both test platforms, each with its configured fields within its limits, carrying identical content."""
    wanted = list(context.kit.platforms)
    if sorted(draft.platforms) != sorted(wanted):
        verdict.block("platforms", f"the Draft needs one section per test platform: {', '.join(wanted)}")
    shared: dict[str, dict[str, str]] = {}
    for platform, values in draft.platforms.items():
        facts = context.platforms.get(platform)
        if facts is None:
            verdict.block("platforms", f"config/platforms.json has no facts for {platform}")
            continue
        names = [limit.name for limit in facts.fields]
        if sorted(values) != sorted(names):
            verdict.block("format", f"## {platform} needs exactly: {', '.join('### ' + name for name in names)}")
            continue
        for name in names:
            if not values[name].strip():
                verdict.block("format", f"## {platform} ### {name} is empty (write none for no hashtags)")
        verdict.add(check_platform(facts, values))
        shared[platform] = {
            "text": norm(values[facts.field("body").name]),
            "hashtags": " ".join(hashtags(values[facts.field("hashtags").name])),
            "alt text": norm(values.get("Alt text", "")),
        }
    for key in ("text", "hashtags", "alt text"):
        if len({values[key] for values in shared.values()}) > 1:
            verdict.block(
                "identical-content", f"the {key} differs between {', '.join(shared)}; both carry identical content"
            )


def beyond_hook(draft: PostDraft, context: Context, opening: Collection[str]) -> PostDraft:
    """The Draft with its Hook taken out, leaving what an A/B leg shares with its other leg: no hook beat, no title,
    and no first line of each platform's text. In a re-cut pair a later beat that shows one of the pair's Hooks, one
    of opening, goes too, since it is part of the opening the two legs cut differently."""
    beats = [
        beat
        for beat in draft.beats[1:]
        if not any(hook in norm(text).casefold() for hook in opening for text in (beat.spoken, beat.on_screen))
    ]
    platforms = {}
    for platform, values in draft.platforms.items():
        facts = context.platforms.get(platform)
        platforms[platform] = {
            limit.name: "\n".join(values.get(limit.name, "").splitlines()[1 if limit.body else 0 :])
            for limit in (facts.fields if facts else ())
            if not limit.title
        }
    return replace(draft, hook="", beats=beats, platforms=platforms)


def check_pair(
    draft: PostDraft, reference: PostDraft, context: Context, opening: Collection[str], verdict: Verdict
) -> None:
    """An A/B leg differs from its reference leg only in the Hook, so every field outside the Hook matches: beat by
    beat in order, or, in a re-cut pair, as the same set of beats in any order. Text the reference no longer passes
    a brand rule with is never inherited or waived: this leg stays blocked, naming the rule, until the Founder
    resolves it."""
    mine, theirs = beyond_hook(draft, context, opening), beyond_hook(reference, context, opening)

    def differs(where: str) -> None:
        verdict.block(
            "pair-legs", f"differs from day {reference.day}'s leg beyond the Hook (`{reference.path}`)", where
        )

    def lines(text: str) -> list[str]:
        return [norm(line) for line in text.splitlines()]

    ours, others = (
        [[norm(getattr(beat, key)) for key in BEAT_LINES.values()] for beat in leg.beats] for leg in (mine, theirs)
    )
    if opening:
        if sorted(ours) != sorted(others):
            differs("beats after the re-cut opening")
    else:
        absent = [None] * len(BEAT_LINES)
        for number, (here, there) in enumerate(zip_longest(ours, others, fillvalue=absent), start=2):
            for label, said, expected in zip(BEAT_LINES, here, there):
                if said != expected:
                    differs(f"beat {number} {label.lower()}")
    for platform, values in theirs.platforms.items():
        for name, expected in values.items():
            if lines(mine.platforms.get(platform, {}).get(name, "")) != lines(expected):
                differs(f"{platform} {name.lower()}")
    failing = context.rules.check(theirs.copies()) if context.rules else []
    rules = sorted({finding.rule for finding in failing if finding.blocks and finding.field})
    if rules:
        verdict.block(
            "pair-legs",
            f"day {reference.day}'s leg, which this leg must match beyond the Hook, now fails {', '.join(rules)}, so"
            " the pair cannot both pass until the Founder resolves it by a package change or by re-cutting both legs",
        )


def check_pain(angle: Angle | None, context: Context, verdict: Verdict) -> None:
    prefix = context.rules.pain_prefix if context.rules else None
    if angle is None or not prefix:
        return
    if not any(url.startswith(prefix) for url in angle.pain_urls):
        verdict.block("pain_source_url_must_start_with", f"Angle {angle.id}'s sourced pain has no {prefix} source")


def check_competitors(draft: PostDraft, kit: Kit, context: Context, verdict: Verdict) -> None:
    """No field names a competitor, a beat's visual action included. A name is matched as the research writes it,
    case kept, since some names are common words; the Founder reads every post."""
    research = context.paths.get("competitors", "the research")
    visuals = [Copy(f"beat {beat.number} visual action", beat.visual) for beat in draft.beats]
    for copy in draft.copies() + visuals:
        tags = copy.field.endswith(" hashtags")
        for competitor in kit.competitors:
            if tags:
                squashed = re.sub(r"\W", "", competitor.name).casefold()
                hit = any(re.sub(r"\W", "", tag).casefold() == squashed for tag in hashtags(copy.text))
            else:
                hit = re.search(rf"(?<![\w]){re.escape(competitor.name)}(?![\w])", copy.text) is not None
            if hit:
                verdict.block(
                    "competitor-name",
                    f"names {competitor.name}, a competitor in `{research}{competitor.source}` line {competitor.line}",
                    copy.field,
                )


def check_claims(draft: PostDraft, code: Code, verdict: Verdict) -> None:
    if not draft.claims:
        verdict.block("claims", "a post Draft shows each behavioral claim it makes with the code that supports it")
    for claim in draft.claims:
        problem = code.verify(claim.location, claim.excerpt)
        verdict.claims.append(ClaimResult(claim, problem))
        if problem:
            verdict.block("claim-location", f"{claim.text!r}: {problem}")
