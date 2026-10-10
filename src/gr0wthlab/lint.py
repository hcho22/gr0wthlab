"""The Draft lint: the Product's brand-rules.json, read from Mandu every run as the one rule source, applied to every
field of copy, plus the platform facts in config/platforms.json.

brand-rules.json began as a lint of the Hook alone; each of its checks now runs on every field a viewer reads
(Hooks, spoken lines, on-screen text, captions, titles, hashtags, and alt text), except the Hook's word cap, which is
about the Hook itself. The newer rule types (stock phrases, capped words, long sentences, invented proof, and fake
scarcity) run with whatever lists brand-rules.json holds; one it does not hold yet is reported as pending, never
filled in from anywhere else. A key gr0wthlab does not know blocks every Draft until a reviewed change teaches it,
so no rule in Mandu is ever skipped silently.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

APPLIED = "applied"
PENDING = "pending"
NOT_APPLICABLE = "not applicable"
DOCUMENTATION = ("comment", "notes")
EMOJI_ABOVE = 0x2100  # the package's own lint treats any character above U+2100 as a non-text symbol
NUMBER = r"\d[\d,.]*\s*(?:k|m|million|thousand)?\+?"
QUANTIFIER = r"(?:thousands|millions|hundreds|dozens|countless)\s+of"
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
    "fake_scarcity": "no scarcity or urgency phrase",
    "lint_allow_phrases": "phrases no word or phrase rule counts",
}
# The rule types F1 added, each with the keys it needs before it runs.
NEW_RULE_TYPES = {
    "stock phrases": ("stock_phrases",),
    "capped words per paragraph": ("capped_words", "capped_words_per_paragraph"),
    "long sentences (warning)": ("long_sentence_words", "long_sentence_commas"),
    "invented proof": ("invented_proof_terms",),
    "fake scarcity": ("fake_scarcity",),
    "allowed phrases": ("lint_allow_phrases",),
}
NOT_FOR_POSTS = {
    "required_sections": "the layout of the dry-run creative briefs; a post Draft has its own format",
    "required_disclosure": "screens shown as simulated; the kit's posts are real-device recordings",
}


class RulesError(ValueError):
    """brand-rules.json cannot be used, so no Draft can pass the lint."""


@dataclass(frozen=True)
class Copy:
    """One field a viewer reads, named as the Founder sees it; a description, such as alt text, describes the video
    rather than speaking to the viewer, so the sentence-length warnings skip it."""

    field: str
    text: str
    hook: bool = False
    description: bool = False


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


def words_pattern(term: str, plural: bool = True) -> re.Pattern:
    """A term as whole words, any case, spacing free, with a plural ending when plural is set; {n} is any number."""
    parts = [NUMBER if word == "{n}" else re.escape(word) for word in term.split()]
    ending = "(?:s|es)?" if plural else ""
    return re.compile(r"(?<!\w)" + r"\s+".join(parts) + ending + r"(?!\w)", re.IGNORECASE)


def string_list(data: Mapping, key: str) -> tuple[str, ...]:
    value = data.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
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
            "fake_scarcity",
            "lint_allow_phrases",
        ):
            if key in data:
                self.lists[key] = string_list(data, key)
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
        self.allow = [words_pattern(term, plural=False) for term in self.lists.get("lint_allow_phrases", ())]

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
            else:
                rows.append(RuleStatus(key, APPLIED, KNOWN_RULES[key]))
        for name, keys in NEW_RULE_TYPES.items():
            missing = [key for key in keys if key not in self.data]
            if missing:
                rows.append(RuleStatus(name, PENDING, "brand-rules.json has no " + ", ".join(missing) + " yet"))
        return rows

    def pending(self) -> list[str]:
        return [row.rule for row in self.statuses() if row.status == PENDING]

    def masked(self, text: str) -> str:
        """The text with every allowed phrase blanked out, so no word or phrase rule counts inside one."""
        for pattern in self.allow:
            text = pattern.sub(lambda match: " " * len(match.group(0)), text)
        return text

    def check(self, copies: Sequence[Copy]) -> list[Finding]:
        findings = [Finding(key, "", "gr0wthlab cannot check this brand rule yet") for key in self.unknown]
        for copy in copies:
            if copy.text.strip():
                findings += self.check_one(copy)
        return findings

    def check_one(self, copy: Copy) -> list[Finding]:
        found: list[Finding] = []
        text = copy.text
        words_text = self.masked(text)

        def block(rule: str, detail: str) -> None:
            found.append(Finding(rule, copy.field, detail))

        if copy.hook and "hook_max_words" in self.numbers:
            count = len(text.split())
            if count > self.numbers["hook_max_words"]:
                block("hook_max_words", f"the Hook has {count} words; at most {self.numbers['hook_max_words']}")
        if self.data.get("hook_must_not_be_question") and "?" in text:
            block("hook_must_not_be_question", f"asks a question: {snippet(text)!r}")
        for key, label in (("banned_words_in_hook", "banned word"), ("banned_social_proof_in_hook", "social proof")):
            for term in self.lists.get(key, ()):
                if words_pattern(term).search(words_text):
                    block(key, f"{label} {term!r}")
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
                hits = [term for term in self.lists["capped_words"] if words_pattern(term).search(paragraph)]
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
        if NEED_MARKER.search(text):
            block(
                "need-marker", f"still asks for proof: {NEED_MARKER.search(text).group(0)}; a Draft never fills it in"
            )
        return found

    def invented_proof(self, copy: Copy, text: str) -> list[Finding]:
        """Numbers and quantities of people, reviews, or results: the product has none, so none may be implied."""
        found = []
        terms = "|".join(re.escape(term) for term in self.lists["invented_proof_terms"])
        if terms:
            near = re.compile(
                rf"(?<!\w)(?:{NUMBER}|{QUANTIFIER})\s+(?:\w+\s+){{0,2}}(?:{terms})(?:s|es)?(?!\w)", re.IGNORECASE
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
