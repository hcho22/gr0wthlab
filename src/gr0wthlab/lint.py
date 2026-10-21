"""The Draft lint: the Product's brand-rules.json, read from Mandu every run as the one rule source, applied to every
field of copy, plus the platform facts in config/platforms.json.

brand-rules.json began as a lint of the Hook alone; each of its checks now runs on every field a viewer reads
(Hooks, spoken lines, on-screen text, captions, titles, hashtags, and alt text), except the Hook's word cap, which is
about the Hook itself. The newer rule types (stock phrases, capped words, long sentences, invented proof, fake
scarcity, and loss framing) run with whatever lists brand-rules.json holds; one it does not hold yet is reported as
pending, never filled in from anywhere else. A message to a creator is also read for the sponsorship asks the file
lists, which no post is. A key gr0wthlab does not know blocks every Draft until a reviewed change teaches it,
so no rule in Mandu is ever skipped silently. A filming note, such as a beat's visual action, is no copy: it may
describe real screens and numbers, so only the social-proof rule reads it.

A listed word or phrase matches as whole words, whatever sets its words apart in the rule or in the text (spaces,
hyphens, dashes, or underscores). A hashtag runs words together, so there it matches anywhere inside the tag, which
is stricter: a false hit costs another hashtag, and a miss puts banned language in a public post. An allowed
phrase is blanked in a hashtag only when it is the whole tag, so a longer tag is always checked in full.

A post Draft's frozen Hooks are planned test text, so brand-rules.json may exempt them from the Hook's word cap and
its banned words (frozen_hooks_exempt_from). The post Draft checks alone name the frozen Hooks each field may show
(Copy.frozen): the cap is then skipped for a Hook that is one of them word for word, and a banned word is not counted
inside their own words, a whole Hook or one of its sentences, wherever the field repeats them. Every other word in the
same field, and every other rule, is read as before, and no other text is ever exempt.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

APPLIED = "applied"
PENDING = "pending"
NOT_APPLICABLE = "not applicable"
DOCUMENTATION = ("comment", "notes")
EMOJI_ABOVE = 0x2100  # the package's own lint treats any character above U+2100 as a non-text symbol
NUMBER = r"\d(?:[\d,.]*\d)?\s*(?:k|m|million|thousand)?\+?"
SEPARATOR = r"[\s_\-\u2010-\u2015]+"  # what sets words apart: spaces, hyphens, dashes, and underscores
LETTER = r"[^\W_]"  # a letter or digit, so a word ends at an underscore as at any other separator
BEFORE, AFTER = f"(?<!{LETTER})", f"(?!{LETTER})"
QUOTES = str.maketrans({"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"'})
NEED_MARKER = re.compile(r"\[NEED:[^\]]*\]", re.IGNORECASE)

# What each key of brand-rules.json makes the lint do. The F1 rule types are listed with the keys they read.
KNOWN_RULES = {
    "hook_max_words": "the Hook has at most this many words",
    "hook_must_not_be_question": "no copy asks a question",
    "banned_words_in_hook": "no copy uses a banned word",
    "banned_social_proof_in_hook": "no copy uses social-proof language",
    "banned_characters_anywhere": "no copy uses a banned character",
    "no_emoji_in_hook": "no copy uses an emoji or other non-text symbol",
    "no_all_caps_words_in_hook": "no copy has an all-caps word outside all_caps_allowlist",
    "all_caps_allowlist": "all-caps words the all-caps rule allows",
    "pain_source_url_must_start_with": "the Angle's sourced pain links its source with this prefix",
    "required_sections": "creative-brief sections",
    "required_disclosure": "the simulated-screen disclosure",
    "stock_phrases": "no copy uses a stock phrase",
    "capped_words": "capped words, counted per paragraph",
    "capped_words_per_paragraph": "how many capped words one paragraph may hold",
    "long_sentence_words": "a sentence with more words is flagged",
    "long_sentence_commas": "a sentence with more commas is flagged",
    "invented_proof_terms": "no number or quantity of people, reviews, or results that does not exist",
    "invented_proof_quantities": "quantity words the invented-proof rule reads before a term, such as thousands of",
    "fake_scarcity": "no scarcity or urgency phrase",
    "lint_allow_phrases": "phrases no word or phrase rule counts",
    "loss_framing": "no copy uses a loss-framed phrase",
    "sponsorship_asks": "no message to a creator asks for a sponsorship or a paid placement",
    "frozen_hooks_exempt_from": "a post's frozen Hooks, in their own words, are exempt from these Hook rules",
}
# The rules frozen_hooks_exempt_from may name: the Hook's word cap and its banned words, and no other.
FROZEN_EXEMPTABLE = ("hook_max_words", "banned_words_in_hook")
EXEMPT = "frozen test Hook, exempt by brand-rules.json frozen_hooks_exempt_from: "  # opens an exemption's detail
# The rule types F1 added, each with the keys it needs before it runs.
NEW_RULE_TYPES = {
    "stock phrases": ("stock_phrases",),
    "capped words per paragraph": ("capped_words", "capped_words_per_paragraph"),
    "long sentences (warning)": ("long_sentence_words", "long_sentence_commas"),
    "invented proof": ("invented_proof_terms", "invented_proof_quantities"),
    "fake scarcity": ("fake_scarcity",),
    "allowed phrases": ("lint_allow_phrases",),
}
# The rule types US-ME14 added, each with the key it needs: loss framing is read in every field of copy, like the F1
# types, and sponsorship asks only in a message to a creator.
LOSS_FRAMING = {"loss framing": ("loss_framing",)}
CREATOR_RULE_TYPES = {"sponsorship asks": ("sponsorship_asks",)}
NOT_FOR_POSTS = {
    "required_sections": "the layout of the dry-run creative briefs; a post Draft has its own format",
    "required_disclosure": "screens shown as simulated; the kit's posts are real-device recordings",
    "sponsorship_asks": "asks a message to a creator may not make; a post is not read for them",
}


class RulesError(ValueError):
    """brand-rules.json cannot be used, so no Draft can pass the lint."""


@dataclass(frozen=True)
class Copy:
    """One field of a post, named as the Founder sees it; a description, such as alt text, describes the video
    rather than speaking to the viewer, so the sentence-length warnings skip it, and a note, such as a beat's visual
    action, is a filming note no viewer reads, so only the social-proof rule reads it. frozen holds the frozen Hooks
    the field may show, whose own words are exempt from the Hook rules frozen_hooks_exempt_from names; only the post
    Draft checks set it."""

    field: str
    text: str
    hook: bool = False
    description: bool = False
    note: bool = False
    frozen: tuple[str, ...] = ()


@dataclass(frozen=True)
class Finding:
    rule: str
    field: str
    detail: str
    blocks: bool = True

    def line(self) -> str:
        return f"{self.rule}: {self.detail}" + (f" ({self.field})" if self.field else "")


@dataclass(frozen=True)
class RuleStatus:
    rule: str
    status: str
    detail: str


def plain(text: str) -> str:
    """Typographic quotes made plain, so a word reads the same however its apostrophe was typed."""
    return text.translate(QUOTES)


def phrase(term: str, tag: bool = False) -> str:
    """A term's words as a pattern, quotes plain and {n} any number; any separator sets them apart, in the term and
    in the text alike. tag is the term as a hashtag writes it: each word down to its letters and digits, run
    together or joined by underscores."""
    words = [word for word in re.split(SEPARATOR, plain(term)) if word]
    if tag:
        words = [word if word == "{n}" else re.sub(r"\W", "", word) for word in words]
    return ("_*" if tag else SEPARATOR).join(NUMBER if word == "{n}" else re.escape(word) for word in words)


def words_pattern(term: str, plural: bool = True) -> re.Pattern:
    """A term in any case: as whole words, with a plural ending when plural is set, or anywhere inside a hashtag."""
    ending = "(?:s|es)?" if plural else ""
    return re.compile(rf"{BEFORE}{phrase(term)}{ending}{AFTER}|#\w*?{phrase(term, tag=True)}", re.IGNORECASE)


def allowed_pattern(term: str) -> re.Pattern:
    """An allowed phrase in any case: as whole words outside every hashtag, or as one whole hashtag, so blanking it
    never takes a part out of a longer hashtag."""
    return re.compile(rf"(?<![\w#]){phrase(term)}{AFTER}|(?<=#){phrase(term, tag=True)}(?!\w)", re.IGNORECASE)


def string_list(data: Mapping, key: str, words: bool = True) -> tuple[str, ...]:
    """A list of brand-rules.json; in a list of words, every entry holds a letter or digit, so it has a word to
    match."""
    value = data.get(key)
    holds = re.compile(LETTER if words else r"\S")
    if not isinstance(value, list) or not all(isinstance(item, str) and holds.search(item) for item in value):
        raise RulesError(f"brand-rules.json {key} must be a list of words or phrases")
    return tuple(item.strip() for item in value)


def whole_number(data: Mapping, key: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RulesError(f"brand-rules.json {key} must be a whole number")
    return value


def paragraphs(text: str) -> list[str]:
    return [block for block in re.split(r"\n\s*\n", text) if block.strip()]


def sentences(text: str) -> list[str]:
    found = []
    for block in paragraphs(text):
        found += [part for part in re.split(r"(?<=[.!?])\s+|\n", block) if part.strip()]
    return found


def snippet(text: str, limit: int = 60) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


class Rules:
    """brand-rules.json, validated; every key is either applied, not applicable to post Drafts, or documentation."""

    def __init__(self, data: Mapping):
        if not isinstance(data, Mapping):
            raise RulesError("brand-rules.json must hold a JSON object")
        self.data = data
        self.unknown = sorted(key for key in data if key not in KNOWN_RULES and key not in DOCUMENTATION)
        self.lists: dict[str, tuple[str, ...]] = {}
        self.numbers: dict[str, int] = {}
        for key in (
            "banned_words_in_hook",
            "banned_social_proof_in_hook",
            "banned_characters_anywhere",
            "all_caps_allowlist",
            "stock_phrases",
            "capped_words",
            "invented_proof_terms",
            "invented_proof_quantities",
            "fake_scarcity",
            "lint_allow_phrases",
            "loss_framing",
            "sponsorship_asks",
        ):
            if key in data:
                self.lists[key] = string_list(data, key, words=key != "banned_characters_anywhere")
        for key in ("hook_max_words", "capped_words_per_paragraph", "long_sentence_words", "long_sentence_commas"):
            if key in data:
                self.numbers[key] = whole_number(data, key)
        for key in ("hook_must_not_be_question", "no_emoji_in_hook", "no_all_caps_words_in_hook"):
            if key in data and not isinstance(data[key], bool):
                raise RulesError(f"brand-rules.json {key} must be true or false")
        prefix = data.get("pain_source_url_must_start_with")
        if prefix is not None and not (isinstance(prefix, str) and prefix):
            raise RulesError("brand-rules.json pain_source_url_must_start_with must be text")
        self.pain_prefix: str | None = prefix
        exempt = data.get("frozen_hooks_exempt_from", [])
        if not isinstance(exempt, list) or not all(rule in FROZEN_EXEMPTABLE for rule in exempt):
            raise RulesError(
                "brand-rules.json frozen_hooks_exempt_from must be a list naming only " + " or ".join(FROZEN_EXEMPTABLE)
            )
        self.frozen_exempt = frozenset(exempt)
        self.allow = [allowed_pattern(term) for term in self.lists.get("lint_allow_phrases", ())]

    def has(self, *keys: str) -> bool:
        return all(key in self.data for key in keys)

    def statuses(self) -> list[RuleStatus]:
        """How each rule in brand-rules.json, and each rule type that waits for keys it does not hold yet, applies."""
        rows = []
        for key in self.data:
            if key in DOCUMENTATION:
                continue
            if key in self.unknown:
                rows.append(
                    RuleStatus(key, "unknown", "gr0wthlab cannot check this rule yet, so it blocks every Draft")
                )
            elif key in NOT_FOR_POSTS:
                rows.append(RuleStatus(key, NOT_APPLICABLE, NOT_FOR_POSTS[key]))
            elif key == "frozen_hooks_exempt_from":
                rows.append(RuleStatus(key, APPLIED, f"{KNOWN_RULES[key]}: {', '.join(self.exempt_rules()) or 'none'}"))
            else:
                rows.append(RuleStatus(key, APPLIED, KNOWN_RULES[key]))
        for name, keys in {**NEW_RULE_TYPES, **LOSS_FRAMING}.items():
            missing = [key for key in keys if key not in self.data]
            if missing:
                rows.append(RuleStatus(name, PENDING, "brand-rules.json has no " + ", ".join(missing) + " yet"))
        return rows

    def exempt_rules(self) -> list[str]:
        """The Hook rules a post's frozen Hooks are exempt from, in the order the lint knows them."""
        return [rule for rule in FROZEN_EXEMPTABLE if rule in self.frozen_exempt]

    def pending(self) -> list[str]:
        return [row.rule for row in self.statuses() if row.status == PENDING]

    def creator_pending(self) -> list[str]:
        """The rule types a message to a creator is read for whose lists brand-rules.json does not hold yet."""
        return [name for name, keys in CREATOR_RULE_TYPES.items() if not self.has(*keys)]

    def sponsorship(self, copy: Copy) -> list[Finding]:
        """A message to a creator asks for nothing paid: no phrase brand-rules.json lists as a sponsorship ask."""
        text = self.masked(plain(copy.text))
        return [
            Finding("sponsorship_asks", copy.field, f"sponsorship ask {term!r}")
            for term in self.lists.get("sponsorship_asks", ())
            if words_pattern(term).search(text)
        ]

    def masked(self, text: str) -> str:
        """The text with every allowed phrase blanked out, so no word or phrase rule counts inside one."""
        for pattern in self.allow:
            text = pattern.sub(lambda match: " " * len(match.group(0)), text)
        return text

    def check(self, copies: Sequence[Copy]) -> list[Finding]:
        """Every rule on every field. The own words of the frozen Hooks a field may show (Copy.frozen) are exempt
        from the rules frozen_hooks_exempt_from names; nothing else is ever exempt."""
        findings = [Finding(key, "", "gr0wthlab cannot check this brand rule yet") for key in self.unknown]
        for copy in copies:
            if copy.text.strip():
                findings += self.check_one(copy)
        return findings

    def exemptions(self, copies: Sequence[Copy]) -> list[Finding]:
        """What the frozen Hooks' exemption let pass: each finding of an exempt rule that the same fields would carry
        without it, so a report can say where it applied. None of them blocks."""
        found = []
        for copy in copies:
            if copy.text.strip():
                kept = {(finding.rule, finding.detail) for finding in self.check_one(copy)}
                found += [
                    Finding(finding.rule, finding.field, EXEMPT + finding.detail, False)
                    for finding in self.check_one(replace(copy, frozen=()))
                    if finding.rule in self.frozen_exempt and (finding.rule, finding.detail) not in kept
                ]
        return found

    def unfrozen(self, text: str, frozen: Sequence[str]) -> str:
        """The text with the frozen Hooks' own words blanked out, as written (case kept): each whole Hook, and each
        of its sentences, wherever the text repeats one as whole words."""
        for part in [part for hook in frozen for part in (hook, *sentences(hook))]:
            words = plain(part).split()
            if words:
                pattern = re.compile(BEFORE + r"\s+".join(re.escape(word) for word in words) + AFTER)
                text = pattern.sub(lambda match: " " * len(match.group(0)), text)
        return text

    def check_one(self, copy: Copy) -> list[Finding]:
        found: list[Finding] = []
        text = copy.text
        words_text = self.masked(plain(text))
        frozen = () if copy.note else tuple(hook for hook in copy.frozen if hook.strip())
        if frozen and "banned_words_in_hook" in self.frozen_exempt:
            # The frozen words go before the allowed phrases, so blanking an allowed phrase never hides one of them.
            banned_text = self.masked(self.unfrozen(plain(text), frozen))
        else:
            banned_text = words_text

        def block(rule: str, detail: str) -> None:
            found.append(Finding(rule, copy.field, detail))

        def banned(key: str, label: str, among: str = words_text) -> None:
            for term in self.lists.get(key, ()):
                if words_pattern(term).search(among):
                    block(key, f"{label} {term!r}")

        if copy.note:
            banned("banned_social_proof_in_hook", "social proof")
            return found
        verbatim = any(plain(text).split() == plain(hook).split() for hook in frozen)
        exempt_cap = verbatim and "hook_max_words" in self.frozen_exempt
        if copy.hook and "hook_max_words" in self.numbers and not exempt_cap:
            count = len(text.split())
            if count > self.numbers["hook_max_words"]:
                block("hook_max_words", f"the Hook has {count} words; at most {self.numbers['hook_max_words']}")
        if self.data.get("hook_must_not_be_question") and "?" in text:
            block("hook_must_not_be_question", f"asks a question: {snippet(text)!r}")
        banned("banned_words_in_hook", "banned word", banned_text)
        banned("banned_social_proof_in_hook", "social proof")
        for character in self.lists.get("banned_characters_anywhere", ()):
            if character in text:
                block("banned_characters_anywhere", f"banned character {character!r}")
        if self.data.get("no_emoji_in_hook"):
            symbols = sorted({character for character in text if ord(character) > EMOJI_ABOVE})
            if symbols:
                block("no_emoji_in_hook", "non-text symbol " + ", ".join(repr(symbol) for symbol in symbols))
        if self.data.get("no_all_caps_words_in_hook"):
            allowed = set(self.lists.get("all_caps_allowlist", ()))
            for word in text.split():
                bare = word.strip(".,!:;\"'()#?")
                if len(bare) > 1 and bare.isupper() and bare not in allowed:
                    block("no_all_caps_words_in_hook", f"all-caps word {bare!r}")
        for term in self.lists.get("stock_phrases", ()):
            if words_pattern(term, plural=False).search(words_text):
                block("stock_phrases", f"stock phrase {term!r}")
        if self.has("capped_words", "capped_words_per_paragraph"):
            cap = self.numbers["capped_words_per_paragraph"]
            for paragraph in paragraphs(words_text):
                hits = [term for term in self.lists["capped_words"] for _ in words_pattern(term).finditer(paragraph)]
                if len(hits) > cap:
                    block(
                        "capped_words", f"{len(hits)} capped words in one paragraph ({', '.join(hits)}); at most {cap}"
                    )
        for key, measure, unit in (
            ("long_sentence_words", lambda sentence: len(sentence.split()), "words"),
            ("long_sentence_commas", lambda sentence: sentence.count(","), "commas"),
        ):
            if key in self.numbers and not copy.description:
                for sentence in sentences(text):
                    if measure(sentence) > self.numbers[key]:
                        found.append(
                            Finding(
                                key,
                                copy.field,
                                f"{measure(sentence)} {unit}, over {self.numbers[key]}: {snippet(sentence)!r}",
                                blocks=False,
                            )
                        )
        if "invented_proof_terms" in self.lists:
            found += self.invented_proof(copy, words_text)
        for term in self.lists.get("fake_scarcity", ()):
            if words_pattern(term, plural=False).search(words_text):
                block("fake_scarcity", f"scarcity or urgency {term!r}")
        for term in self.lists.get("loss_framing", ()):
            if words_pattern(term, plural=False).search(words_text):
                block("loss_framing", f"loss-framed phrase {term!r}")
        if NEED_MARKER.search(text):
            block(
                "need-marker", f"still asks for proof: {NEED_MARKER.search(text).group(0)}; a Draft never fills it in"
            )
        return found

    def invented_proof(self, copy: Copy, text: str) -> list[Finding]:
        """Numbers and quantities of people, reviews, or results: the product has none, so none may be implied. An
        amount counts before a term as words, with up to two words between them, and anywhere before a term inside
        one hashtag."""
        found = []
        terms = self.lists["invented_proof_terms"]
        quantities = self.lists.get("invented_proof_quantities", ())
        if terms:
            term, tag_term = ("|".join(phrase(word, tag) for word in terms) for tag in (False, True))
            amount, tag_amount = (
                "|".join([NUMBER] + [phrase(word, tag) for word in quantities]) for tag in (False, True)
            )
            near = re.compile(
                rf"{BEFORE}(?:{amount}){SEPARATOR}(?:{LETTER}+{SEPARATOR}){{0,2}}(?:{term})(?:s|es)?{AFTER}"
                rf"|#\w*?(?:{tag_amount})\w*?(?:{tag_term})\w*",
                re.IGNORECASE,
            )
            for match in near.finditer(text):
                found.append(Finding("invented_proof_terms", copy.field, f"unsourced proof {match.group(0)!r}"))
        for pattern, what in (
            (r"\d+(?:\.\d+)?\s*(?:%|percent\b)", "percentage"),
            (r"(?<!\w)\d+(?:\.\d+)?x(?!\w)", "multiplier"),
        ):
            for match in re.finditer(pattern, text, re.IGNORECASE):
                found.append(Finding("invented_proof_terms", copy.field, f"unsourced {what} {match.group(0)!r}"))
        return found


# Platform facts.


@dataclass(frozen=True)
class FieldLimit:
    name: str
    max_chars: int | None = None
    visible_chars: int | None = None
    body: bool = False
    title: bool = False
    hashtags: bool = False


@dataclass(frozen=True)
class Platform:
    name: str
    fields: tuple[FieldLimit, ...]
    max_hashtags: int | None
    hashtags_void_above: int | None

    def field(self, flag: str) -> FieldLimit | None:
        return next((limit for limit in self.fields if getattr(limit, flag)), None)


class PlatformError(ValueError):
    """config/platforms.json does not describe a platform the Drafts need."""


def load_platforms(data: Mapping) -> dict[str, Platform]:
    platforms = {}
    for name, facts in (data.get("platforms") or {}).items():
        fields = []
        for field_name, limit in (facts.get("fields") or {}).items():
            fields.append(
                FieldLimit(
                    field_name,
                    limit.get("max_chars"),
                    limit.get("visible_chars"),
                    bool(limit.get("body")),
                    bool(limit.get("title")),
                    bool(limit.get("hashtags")),
                )
            )
        platform = Platform(name, tuple(fields), facts.get("max_hashtags"), facts.get("hashtags_void_above"))
        if sum(limit.body for limit in fields) != 1 or sum(limit.hashtags for limit in fields) != 1:
            raise PlatformError(f"config/platforms.json {name} needs exactly one body field and one hashtags field")
        platforms[name] = platform
    if not platforms:
        raise PlatformError("config/platforms.json names no platforms")
    return platforms


def hashtags(text: str) -> list[str]:
    return [] if text.strip().casefold() in ("", "none") else text.split()


def check_platform(platform: Platform, values: Mapping[str, str]) -> list[Finding]:
    """A platform's character and hashtag limits on one Draft's fields; hashtags count against the body's limit."""
    found = []
    tags = hashtags(values.get(platform.field("hashtags").name, ""))
    source = "config/platforms.json"
    for tag in tags:
        if not re.fullmatch(r"#\w+", tag):
            found.append(Finding("hashtags", f"{platform.name} hashtags", f"{tag!r} is not one #word"))
    if platform.max_hashtags is not None and len(tags) > platform.max_hashtags:
        found.append(
            Finding(
                f"{source} {platform.name} max_hashtags",
                f"{platform.name} hashtags",
                f"{len(tags)} hashtags; {platform.name} allows {platform.max_hashtags}",
            )
        )
    if platform.hashtags_void_above is not None and len(tags) > platform.hashtags_void_above:
        found.append(
            Finding(
                f"{source} {platform.name} hashtags_void_above",
                f"{platform.name} hashtags",
                f"{len(tags)} hashtags; more than {platform.hashtags_void_above} makes {platform.name} ignore them all",
            )
        )
    for limit in platform.fields:
        if limit.hashtags:
            continue
        text = values.get(limit.name, "")
        length = len(text) + (len(" ".join(tags)) + 1 if limit.body and tags else 0)
        where = f"{platform.name} {limit.name.lower()}"
        if limit.body and re.search(r"(?<!\w)#\w", text):
            found.append(Finding("hashtags", where, "hashtags belong in the Hashtags field, not in the text"))
        if limit.max_chars is not None and length > limit.max_chars:
            counted = " with its hashtags" if limit.body and tags else ""
            found.append(
                Finding(
                    f"{source} {platform.name} {limit.name} max_chars",
                    where,
                    f"{length} characters{counted}; {platform.name} allows {limit.max_chars}",
                )
            )
        first = text.splitlines()[0] if text.strip() else ""
        if limit.visible_chars is not None and len(first) > limit.visible_chars:
            found.append(
                Finding(
                    f"{source} {platform.name} {limit.name} visible_chars",
                    where,
                    f"its first line is {len(first)} characters; about {limit.visible_chars} show before it is cut",
                    blocks=False,
                )
            )
    return found
