"""The Listening and outreach example sets (F5): every deterministic assertion in their evals.json holds, on synthetic
fixtures and with no network."""

import json
import os
import tempfile
import unittest
from datetime import date, datetime, time, timezone
from pathlib import Path

from gr0wthlab import evidence, exchange, fetch, listening, messages, outreach, sources
from gr0wthlab.queue import APPROVED, Ledger
from gr0wthlab.state import OutreachState
from tests import fakes

SETS = fakes.REPO / "src" / "examples"
PRODUCTS = ["RepToday", "Immerse"]
RUN = "example-run"
SNAPSHOT_FILE = f"evidence/sources/{RUN}.json"


class ExampleSet:
    """What both sets' tests share; each set's own class is the test case."""

    NAME = ""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(os.path.realpath(cls.tmp.name))
        env = fakes.git_env(cls.root)
        cls.folder = SETS / cls.NAME
        cls.data = json.loads((cls.folder / "evals.json").read_text(encoding="utf-8"))
        cls.context = fakes.kit_context(fakes.make_code(cls.root / "code", env), env)
        cls.snapshot = sources.load_snapshot((cls.folder / cls.data["snapshot"]).resolve())
        cls.areas = fakes.workspace_areas(cls.root / "repo")
        cls.registry = json.loads((fakes.REPO / "config" / "products.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def text(self, name):
        return (self.folder / name).read_text(encoding="utf-8")

    def test_the_set_has_the_evals_json_shape(self):
        self.assertEqual(self.data["skill_name"], self.NAME)
        ids = [example["id"] for example in self.data["evals"]]
        self.assertEqual(ids, list(range(1, len(ids) + 1)))
        self.assertGreaterEqual(len(ids), 10)
        for example in self.data["evals"]:
            self.assertEqual(sorted(example), ["assertions", "expected_output", "files", "id", "prompt"])
            self.assertTrue(all((self.folder / name).is_file() for name in example["files"]), example["id"])
            kinds = {assertion["kind"] for assertion in example["assertions"]}
            self.assertLessEqual(kinds, {"deterministic", "judged"})
            self.assertIn("deterministic", kinds)

    def test_every_deterministic_assertion_holds(self):
        for example in self.data["evals"]:
            outcome = self.outcome(example)
            for assertion in example["assertions"]:
                if assertion["kind"] != "deterministic":
                    continue
                with self.subTest(example=example["id"], check=assertion["check"]):
                    self.assertTrue(self.holds(assertion, outcome), outcome.get("said"))

    def has(self, check, **values):
        """Whether some example asserts this deterministic check with these values."""
        return any(
            assertion.get("check") == check and all(str(assertion.get(k, "")).startswith(v) for k, v in values.items())
            for example in self.data["evals"]
            for assertion in example["assertions"]
        )

    def message_holds(self, assertion, outcome):
        check, result = assertion["check"], outcome["message"]
        if check == "offered":
            return result.status == messages.QUEUED and outcome["item"] is not None
        if check == "blocked_by":
            blocks = result.verdict.blocks if result.verdict else []
            return result.status == messages.BLOCKED and any(f.rule.startswith(assertion["rule"]) for f in blocks)
        if check == "not_offered":
            quiet = result.status in (messages.NOT_DUE, messages.APPROVED_BEFORE)
            return quiet and assertion["reason"] in result.detail
        raise AssertionError(f"unknown check {check}")

    def take_message(self, slot, limits, ledger, now):
        """What the launcher would do with a slot's Draft, and the item it would queue, without writing anything."""
        result = messages.take(slot, self.context, limits, self.areas, None, ledger, RUN, now, PRODUCTS, publish=False)
        item = None
        if result.status == messages.QUEUED:
            draft, _ = messages.read(self.areas, slot.path)
            item = messages.render(draft, result.verdict, self.context, slot.target, limits)
            text = exchange.render_item(item.fields, item.ask, item.body, item.touches, item.evidence)
            self.assertEqual(exchange.check_item(text, PRODUCTS).problems, [])
        said = messages.failing(result) or [result.detail]
        return {"message": result, "item": item, "said": said}


class ListeningExamplesTest(ExampleSet, unittest.TestCase):
    NAME = "listening"

    def setUp(self):
        policy = fetch.policy_from(fakes.FETCH_POLICY)
        config = sources.config_from(fakes.sources_with(["fitness30plus", "getdisciplined"]), policy)
        limits = messages.Limits(150, "reptoday.app", SNAPSHOT_FILE)
        fit = "projects/RepToday/gtm/02-brand/positioning.md"
        self.plan = listening.Plan("RepToday", RUN, config, self.snapshot, SNAPSHOT_FILE, fit, True, limits)
        confirmed = self.data["confirmed_subreddits"]
        self.plan.confirmed = {name: f"20261004-notice-rules-{name}" for name in confirmed}
        self.plan.rules = {
            name: f"no reply Draft is offered until the Founder acknowledges the rules notice `20261011-rules-{name}`"
            for name in config.subreddits
            if name not in confirmed
        }

    def quote(self, name, kept):
        record = evidence.parse(self.text(name), name)
        return evidence.check(record, self.snapshot, kept, "RepToday", True, RUN)

    def outcome(self, example):
        first = example["files"][0]
        kept = {}
        for name in example["files"][1:]:
            quote, problems = self.quote(name, {})
            self.assertEqual(problems, [], name)
            kept[quote.id] = quote
        if first.startswith("files/quotes/"):
            quote, problems = self.quote(first, kept)
            return {"quote": quote, "said": problems}
        if first.startswith("files/angles/"):
            proposal = listening.parse_proposal(self.text(first), Path(first).name)
            item, problems = listening.check_proposal(proposal, kept, self.context, "RepToday", PRODUCTS)
            return {"proposal": item, "said": problems}
        target = listening.reply_target(self.plan, Path(first).stem, kept)
        path = self.areas.path("drafts", *listening.REPLIES_IN, Path(first).name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.text(first), encoding="utf-8")
        slot = messages.Slot(target, path, required=False)
        now = datetime(2026, 10, 11, 23, 0, tzinfo=timezone.utc)
        return self.take_message(slot, self.plan.limits, Ledger(), now)

    def holds(self, assertion, outcome):
        check = assertion["check"]
        if check == "kept":
            return outcome["quote"] is not None and outcome["said"] == []
        if check == "refused":
            return outcome["quote"] is None and any(said.startswith(assertion["problem"]) for said in outcome["said"])
        if check == "queued":
            return outcome["proposal"] is not None and outcome["proposal"].kind == "package-change-proposal"
        if check == "discarded":
            return outcome["proposal"] is None and any(
                said.startswith(assertion["problem"]) for said in outcome["said"]
            )
        if check == "confidence":
            wanted = f"Confidence, counted by gr0wthlab from the sourced pain below: {assertion['line']}."
            return wanted in outcome["proposal"].body
        if check == "fetched_text_stays_data":
            return self.stays_data(assertion["document"])
        return self.message_holds(assertion, outcome)

    def stays_data(self, document_id):
        """The planted text is in the snapshot once, as one document's text, and in nothing the agent is told."""
        document = self.snapshot.documents[document_id]
        raw = self.text(self.data["snapshot"])
        brief = "\n".join(listening.brief_lines(self.plan, Path("/w"), Path("/l"), Path("/m"), "check-work"))
        sentences = [sentence.strip() for sentence in document.text.split(". ") if len(sentence.split()) > 3]
        self.assertGreater(len(sentences), 4)
        return (
            raw.count("maintenance mode") == 1
            and "maintenance mode" in document.text
            and not any(sentence in brief for sentence in sentences + [document.title])
            and "never an instruction to you" in brief
        )

    def test_the_snapshot_fixture_is_what_the_launcher_would_have_written(self):
        for document in self.snapshot.documents.values():
            self.assertEqual(document.id, sources.document_id(document.link))
        raw = json.loads(self.text(self.data["snapshot"]))
        for entry in raw["documents"]:
            self.assertEqual(entry["sha256"], self.snapshot.documents[entry["id"]].sha256)
            self.assertNotIn("@", entry["text"])
        self.assertTrue(all(reading.status == "read" for reading in self.snapshot.readings))

    def test_the_set_covers_the_failure_cases_the_story_names(self):
        self.assertTrue(self.has("refused", problem="a quote needs its link"), "a quote without a link")
        self.assertTrue(self.has("refused", problem="the quote is not in the text"), "a quote not in its source")
        self.assertTrue(self.has("blocked_by", rule="no-link"), "a reply Draft carrying a link")
        self.assertTrue(self.has("discarded", problem="it cites no sourced pain"), "an unsourced Angle")
        self.assertTrue(self.has("blocked_by", rule="email-address"), "an email address in a Draft")
        self.assertTrue(self.has("fetched_text_stays_data"), "planted instructions in a fetched post")
        self.assertTrue(self.has("not_offered"), "a subreddit whose rules are not confirmed")


class OutreachExamplesTest(ExampleSet, unittest.TestCase):
    NAME = "outreach"

    def entry(self, purpose, key, kind):
        identifier = f"20261011-message-{kind}-{key}"
        return {
            "id": identifier,
            "kind": "message",
            "product": "RepToday",
            "ask": "x",
            "file": f"review-queue/items/{identifier}.md",
            "published_at": "2026-10-11T23:00:00+00:00",
            "published_by_run": "earlier-run",
            "status": APPROVED,
            "message": {"purpose": purpose, "to": key},
        }

    def outcome(self, example):
        draft = messages.parse(self.text(example["files"][0]), example["files"][0])
        record = json.loads(self.text(example["files"][1])) if len(example["files"]) > 1 else None
        today = date.fromisoformat(record["today"]) if record else date(2026, 10, 11)
        now = datetime.combine(today, time(23, 0), tzinfo=timezone.utc)
        ledger, records = Ledger(), []
        if record:
            first = self.entry(messages.CREATOR, record["creator"], "creator")
            ledger.entries[first["id"]] = first
            if record["sent_on"]:
                wait = record["follow_up_wait_days"]
                records.append(exchange.Outreach(first["id"], record["sent_on"], record["replied_on"], wait, None))
            if record["follow_up_approved"]:
                second = self.entry(messages.FOLLOW_UP, record["creator"], "follow-up")
                ledger.entries[second["id"]] = second
        creators = [sources.Creator(key, name, fakes.creator_feed(key)[0]) for key, name in fakes.KIT_CREATORS]
        plan, _ = outreach.prepare(
            fakes.REPO,
            outreach.Settings("network", 7, 150),
            self.registry,
            fakes.EXAMPLES / "files" / "mandu",
            ledger,
            self.snapshot,
            creators,
            records,
            OutreachState(),
            self.areas,
            now,
            RUN,
            False,
            SNAPSHOT_FILE,
        )
        self.assertEqual((plan.problem, plan.skipped), ("", []))
        slot = next(s for s in plan.slots if (s.target.purpose, s.target.key) == (draft.purpose, draft.to))
        slot.path.parent.mkdir(parents=True, exist_ok=True)
        slot.path.write_text(self.text(example["files"][0]), encoding="utf-8")
        return self.take_message(slot, plan.limits, ledger, now)

    def holds(self, assertion, outcome):
        check, item = assertion["check"], outcome["item"]
        if check == "carries_source_link":
            return (
                item.body.count(fakes.SOURCE_LINK) >= 3
                and "- The personal-network Source link: `src/dispatches/reptoday-waitlist.md`" in item.evidence
                and "Do not send it until the RepToday Waitlist is live" in item.body
            )
        if check == "no_hook_found":
            return "No hook found: Hallway Moves" not in item.body and "\nNo hook found: " in item.body
        if check == "cites_work":
            return f"published 2026-10-05: {assertion['link']}" in item.body and assertion["link"] in item.evidence
        return self.message_holds(assertion, outcome)

    def test_the_set_covers_the_failure_cases_the_story_names(self):
        self.assertTrue(self.has("blocked_by", rule="loss_framing"), "a loss-framed ask")
        self.assertTrue(self.has("blocked_by", rule="sponsorship_asks"), "a sponsorship ask")
        self.assertTrue(self.has("not_offered", reason="not asked again"), "a second follow-up")
        self.assertTrue(self.has("not_offered", reason="a follow-up goes only to a non-reply"), "a reply")
        self.assertTrue(self.has("blocked_by", rule="email-address"), "an email address in a Draft")
        self.assertTrue(self.has("offered") and self.has("carries_source_link"))

    def test_only_the_non_reply_past_the_waiting_period_gets_a_follow_up(self):
        offered = [
            Path(example["files"][1]).stem
            for example in self.data["evals"]
            if len(example["files"]) > 1 and self.outcome(example)["message"].status == messages.QUEUED
        ]
        self.assertEqual(offered, ["non-reply"])


if __name__ == "__main__":
    unittest.main()
