"""The Listening Evidence validator: a quote is kept only with its link, its date, and its words as fetched."""

import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from gr0wthlab import evidence, sources
from gr0wthlab.areas import Store
from tests import fakes
from tests.test_sources import POLICY

AT = datetime(2026, 10, 11, 23, 0, tzinfo=timezone.utc)
QUOTE = "Every app I open wants me to pick a plan first and I close it again."


def snapshot(web=None, run="run-1", at=AT):
    data = dict(fakes.SOURCES_QUIET, listening=dict(fakes.SOURCES_QUIET["listening"]))
    data["listening"]["subreddits"] = ["fitness30plus", "getdisciplined"]
    config = sources.config_from(data, POLICY)
    found = sources.plan(config, [], [])
    return sources.take(fakes.client(web or fakes.listening_web()), found, config, lambda link: False, run, at)


class ValidatorTest(unittest.TestCase):
    def setUp(self):
        self.snapshot = snapshot()
        self.post = next(d for d in self.snapshot.documents.values() if d.link == fakes.THREAD)
        self.rules = next(d for d in self.snapshot.documents.values() if d.kind == "rules")

    def check(self, text=None, name=None, recorded=None, fit_readable=True, **fields):
        document, link = fields.pop("document", self.post.id), fields.pop("link", fakes.THREAD)
        text = text or fakes.quote_record(document, link, fields.pop("quote", QUOTE), **fields)
        record = evidence.parse(text, f"evidence/listening/{name or self.post.id}.md")
        return evidence.check(record, self.snapshot, recorded or {}, "RepToday", fit_readable, "run-1")

    def test_a_quote_with_its_link_date_and_exact_words_is_kept(self):
        quote, problems = self.check()
        self.assertEqual(problems, [])
        self.assertEqual((quote.id, quote.link, quote.read_on), (self.post.id, fakes.THREAD, "2026-10-11"))
        self.assertEqual((quote.quote, quote.theme, quote.kind), (QUOTE, "lost-the-routine", "post"))
        self.assertEqual(
            (quote.fit, quote.intent, quote.answerable, quote.unprompted), ("strong", "venting", True, True)
        )
        self.assertEqual(quote.snapshot, "run-1")

    def test_the_words_may_wrap_but_never_change(self):
        wrapped = "Every app I open wants me\nto pick a plan first   and I close it again."
        self.assertEqual(self.check(quote=wrapped)[1], [])
        for altered in (
            "Every app I open wants me to choose a plan first and I close it again.",
            "Every app I open wants me to pick a plan first... I have not trained in two years.",
            "every app i open wants me to pick a plan first",
            '"Every app I open wants me to pick a plan first and I close it again."',
            "Apps should ask fewer questions before the first workout.",
        ):
            with self.subTest(quote=altered):
                quote, problems = self.check(quote=altered)
                self.assertIsNone(quote)
                self.assertIn("the quote is not in the text fetched from its link, word for word", problems[0])

    def test_a_quote_may_come_from_the_title(self):
        self.assertEqual(self.check(quote="Back after two years")[1], [])

    def test_a_quote_without_a_link_or_with_another_link_is_refused(self):
        self.assertIn("a quote needs its link", self.check(link=None)[1][0])
        self.assertIn("a quote needs its link", self.check(link="")[1][0])
        self.assertIn("the link must be an https:// address", self.check(link=fakes.THREAD.replace("https", "http"))[1])
        problems = self.check(link=fakes.OTHER_THREAD)[1]
        self.assertEqual(problems, [f"the link is not the one document {self.post.id} was read from: {fakes.THREAD}"])
        self.assertEqual(self.check(link=fakes.THREAD.rstrip("/"))[1], [], "the same page however it is spelled")

    def test_the_date_read_is_the_run_s_own(self):
        self.assertIn("read_on must be the date the quote was read", self.check(read_on=None)[1][0])
        self.assertIn("read_on must be the date the quote was read", self.check(read_on="last Sunday")[1][0])
        self.assertEqual(
            self.check(read_on="2026-10-04")[1], ["read_on must be 2026-10-11, the date this run read its sources"]
        )

    def test_a_link_already_recorded_is_never_recorded_again(self):
        first, _ = self.check()
        quote, problems = self.check(quote="I have not trained in two years.", recorded={first.id: first})
        self.assertIsNone(quote)
        self.assertEqual(
            problems,
            [f"its link is already recorded as Evidence `{first.id}`, read 2026-10-11; a link is recorded once"],
        )

    def test_a_quote_names_a_thread_or_review_this_run_fetched(self):
        self.assertIn("is not a document in this run's snapshot", self.check(document="d-000000000000")[1][0])
        text = fakes.quote_record(
            self.rules.id, self.rules.link, "Do not link your own products, apps, or surveys here."
        )
        problems = self.check(text=text, name=self.rules.id)[1]
        self.assertEqual(
            problems, [f"document {self.rules.id} is a rules; a quote is taken only from a thread or a review"]
        )
        self.assertIn(f"name the file {self.post.id}.md", self.check(name="my-favorite-quote")[1][0])

    def test_every_field_is_required_and_bounded(self):
        for fields, problem in (
            ({"evidence": "quote"}, "front matter needs evidence: listening"),
            ({"product": "Immerse"}, "product must be RepToday"),
            ({"theme": "Lost Routine"}, "theme must be one tag"),
            ({"theme": None}, "theme must be one tag"),
            ({"fit": "great"}, "fit must be one of: strong, partial, none, unclear"),
            ({"intent": None}, "intent must be one of"),
            ({"answerable": "maybe"}, "answerable must be yes or no"),
            ({"quote": "two words"}, "the quote must be 3 words or more"),
            ({"quote": ""}, "## Quote is empty"),
        ):
            with self.subTest(fields=fields):
                quote, problems = self.check(**fields)
                self.assertIsNone(quote)
                self.assertTrue(any(problem in found for found in problems), problems)
        text = fakes.quote_record(self.post.id, fakes.THREAD, QUOTE).replace(
            "The opening post", "Ask me at a@b.co. The post"
        )
        self.assertIn("looks like an email address", self.check(text=text)[1][0])
        text = fakes.quote_record(self.post.id, fakes.THREAD, QUOTE).split("## Context")[0]
        self.assertIn("the sections must be exactly: ## Quote, ## Context", self.check(text=text)[1][0])
        self.assertIn("must start with front matter", self.check(text="## Quote\n\nwords here now\n")[1][0])
        extra = fakes.quote_record(self.post.id, fakes.THREAD, QUOTE).replace("theme:", "confidence: High\ntheme:")
        self.assertIn("front matter line 'confidence: High' is not one of", self.check(text=extra)[1][0])

    def test_fit_is_never_guessed_when_its_definition_could_not_be_read(self):
        self.assertIn("so fit must be unclear, never a guess", self.check(fit_readable=False)[1][0])
        self.assertEqual(self.check(fit_readable=False, fit="unclear")[1], [])


class ConfidenceTest(unittest.TestCase):
    def quotes(self, count, same_text=0):
        """count quotes from count threads, the last same_text of them one text posted again."""
        entries = [
            (
                f"https://www.reddit.com/r/fitness30plus/comments/t{n}/x/",
                "t",
                f"Words said in thread {n} by someone.",
                "",
            )
            for n in range(count - same_text)
        ]
        entries += [
            (f"https://www.reddit.com/r/fitness30plus/comments/c{n}/x/", "t", "Words said in thread 0 by someone.", "")
            for n in range(same_text)
        ]
        web = fakes.listening_web()
        web.pages["https://www.reddit.com/r/fitness30plus/new/.rss"] = fakes.atom_feed(entries)
        taken = snapshot(web)
        found = []
        for document in taken.of("reddit:fitness30plus"):
            record = evidence.parse(
                fakes.quote_record(document.id, document.link, document.text), f"evidence/listening/{document.id}.md"
            )
            quote, problems = evidence.check(record, taken, {}, "RepToday", True, "run-1")
            self.assertEqual(problems, [])
            found.append(quote)
        return found

    def test_confidence_is_counted_from_independent_unprompted_sources(self):
        self.assertEqual(evidence.confidence_line(self.quotes(1)), "Low: 1 independent unprompted source")
        self.assertEqual(evidence.confidence_line(self.quotes(2)), "Medium: 2 independent unprompted sources")
        self.assertEqual(evidence.confidence_line(self.quotes(3)), "High: 3 independent unprompted sources")
        self.assertEqual(evidence.confidence_line(self.quotes(4)), "High: 4 independent unprompted sources")
        self.assertEqual(evidence.confidence_line([]), "None: no independent unprompted source")

    def test_one_text_posted_twice_is_one_source(self):
        quotes = self.quotes(4, same_text=2)
        self.assertEqual(len(quotes), 4)
        self.assertEqual(evidence.confidence_line(quotes), "Medium: 2 independent unprompted sources")

    def test_the_agent_cannot_state_a_confidence(self):
        self.assertNotIn("confidence", evidence.FRONT_KEYS)
        self.assertNotIn("unprompted", evidence.FRONT_KEYS)


class LedgerTest(unittest.TestCase):
    def test_kept_quotes_read_back_and_cite_their_link(self):
        taken = snapshot()
        post = next(d for d in taken.documents.values() if d.link == fakes.THREAD)
        record = evidence.parse(fakes.quote_record(post.id, post.link, QUOTE), f"evidence/listening/{post.id}.md")
        quote, _ = evidence.check(record, taken, {}, "RepToday", True, "run-1")
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(os.path.realpath(folder)))
            self.assertEqual(evidence.load(store), ({}, []))
            self.assertEqual(evidence.keep(store, quote), f"evidence/listening/quotes/{post.id}.json")
            (store.root / "evidence/listening/quotes/broken.json").write_text("{", encoding="utf-8")
            quotes, problems = evidence.load(store)
            self.assertEqual(quotes, {post.id: quote})
            self.assertIn("`evidence/listening/quotes/broken.json` could not be read", problems[0])
        self.assertEqual(
            evidence.cite(quote), f'- "{QUOTE}" (a thread, theme `lost-the-routine`, read 2026-10-11): {fakes.THREAD}'
        )
        self.assertEqual(list(evidence.by_theme([quote])), ["lost-the-routine"])


if __name__ == "__main__":
    unittest.main()
