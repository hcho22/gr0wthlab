"""Message Drafts: what counts as a link, the Source link's one origin, and the checks the example sets do not reach."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from gr0wthlab import exchange, learning, lint, messages, outreach, proposals
from gr0wthlab.boundary import ConfigError
from tests import fakes

PRODUCTS = ["RepToday", "Immerse"]


class LinksTest(unittest.TestCase):
    def test_anything_a_reader_could_follow_is_a_link(self):
        for text, found in (
            ("See https://example.com/a?b=1.", ["https://example.com/a?b=1"]),
            ("See http://example.com", ["http://example.com"]),
            ("Go to www.example.com now", ["www.example.com"]),
            ("It is at reptoday.app/network.", ["reptoday.app/network"]),
            ("RepToday.App is the site", ["RepToday.App"]),
            ("a [label](target) here", ["a Markdown link"]),
            ("sub.domain.example.co.uk/path, then more", ["sub.domain.example.co.uk/path"]),
        ):
            with self.subTest(text=text):
                self.assertEqual(messages.links(text), found)

    def test_ordinary_prose_holds_no_link(self):
        for text in (
            "I trained at 6.30am, e.g. before work, i.e. early.",
            "It costs 3.5 hours a week. Then nothing.",
            "The U.S. edition is v1.2 now... wait and see.",
            "Mail is never written here",
            "One short session, ready before I could talk myself out of it.",
        ):
            with self.subTest(text=text):
                self.assertEqual(messages.links(text), [])

    def test_the_same_link_with_or_without_its_scheme(self):
        self.assertTrue(messages.same_link("https://RepToday.app/network/", "reptoday.app/network"))
        self.assertFalse(messages.same_link("reptoday.app", "reptoday.app/network"))
        self.assertFalse(messages.same_link("reptoday.app/networks", "reptoday.app/network"))

    def test_a_site_spelled_out_is_caught_and_the_product_s_name_is_not(self):
        pattern = messages.site_pattern("reptoday.app")
        for text in ("reptoday dot app", "RepToday (dot) app", "reptoday . app", "reptoday[dot]app"):
            self.assertIsNotNone(pattern.search(text), text)
        for text in ("the RepToday app", "Rep Today, an app", "reptoday"):
            self.assertIsNone(pattern.search(text), text)
        self.assertIsNone(messages.site_pattern(""))

    def test_a_mention_reddit_would_link(self):
        self.assertEqual(
            messages.MENTION.findall("see r/fitness30plus and u/someone, or your/their and/or"),
            ["r/fitness30plus", "u/someone"],
        )


class SourceLinkTest(unittest.TestCase):
    def test_each_source_s_link_comes_only_from_the_reviewed_dispatch_request(self):
        registry = json.loads((fakes.REPO / "config" / "products.json").read_text(encoding="utf-8"))
        tags = next(p for p in registry["products"] if p["name"] == "RepToday")["waitlist"]["source_tags"]
        links = messages.source_links(fakes.REPO, PRODUCTS, tags)
        self.assertEqual(
            links,
            {
                tag: (f"reptoday.app/{tag}", "src/dispatches/reptoday-waitlist.md")
                for tag in ("tiktok", "youtube", "reddit", "network")
            },
        )
        self.assertEqual(links["network"][0], fakes.SOURCE_LINK)
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(messages.source_links(Path(folder), PRODUCTS, tags), {}, "no request, so no link at all")


class DraftFormatTest(unittest.TestCase):
    def test_a_draft_that_does_not_follow_the_format_says_how(self):
        clean = fakes.message("creator", "slow-strength", fakes.CREATOR_BODY)
        self.assertEqual(messages.parse(clean, "x.md").problems, [])
        for text, problem in (
            ("no front matter", "the file must start with front matter"),
            (clean.replace("purpose: creator", "purpose: dm"), "purpose must be one of"),
            (clean.replace("draft: message", "draft: post"), "front matter needs draft: message"),
            (clean.replace("angle: P03\n", ""), "front matter needs angle"),
            (clean.replace("## Notes", "## Thoughts"), "the sections must be exactly: ## Message, ## Notes, ## Claims"),
            (clean.replace("# A short hello", "A short hello"), "the Draft needs exactly one # title line"),
            (clean.replace("offer: early-access", "offer: early-access\nto: someone"), "is not one of"),
        ):
            with self.subTest(problem=problem):
                self.assertTrue(any(problem in found for found in messages.parse(text, "x.md").problems))
        ask = messages.parse(fakes.message("network-ask", "network", fakes.NETWORK_BODY), "x.md")
        self.assertEqual(ask.problems, [])
        self.assertEqual([(copy.field, copy.text) for copy in ask.sent()], [("message", fakes.NETWORK_BODY)])

    def test_a_queue_entry_names_its_message_and_a_slug_fits(self):
        target = messages.Target(messages.FOLLOW_UP, "a-very-long-creator-key-that-goes-on-and-on-and-on-and-on", "X")
        self.assertLessEqual(len(messages.slug(target)), 60)
        self.assertRegex(messages.slug(target), exchange.SLUG_PATTERN.pattern)
        self.assertEqual(messages.slug(messages.Target(messages.NETWORK, "network", "x")), "message-network-ask")
        self.assertEqual(messages.marker(target)["purpose"], "creator-follow-up")


class OutreachSettingsTest(unittest.TestCase):
    def test_the_committed_settings_and_the_package_file_they_point_at(self):
        config = json.loads((fakes.REPO / "config" / "run.json").read_text(encoding="utf-8"))
        loaded = outreach.settings(config)
        self.assertEqual((loaded.network_source, loaded.wait_days), ("network", 7))
        self.assertEqual(
            [(creator.key, creator.name) for creator in loaded.creators],
            [
                ("gmb-fitness", "GMB Fitness"),
                ("hybrid-calisthenics", "Hybrid Calisthenics"),
                ("the-bioneer", "The Bioneer"),
            ],
        )
        registry = json.loads((fakes.REPO / "config" / "products.json").read_text(encoding="utf-8"))
        self.assertEqual(
            outreach.package_role(registry), ("RepToday", "projects/RepToday/gtm/06-channels/channel-plan.md")
        )
        for output in ("listening", "outreach-drafts", "rejection-codes"):
            self.assertTrue(config["outputs"][output]["built"])
        self.assertNotIn("Listening sources", [source["name"] for source in config["sources_not_connected"]])

    def test_settings_that_are_not_what_they_say_stop_the_run(self):
        good = {"network_ask_source": None, "follow_up_wait_days": 7, "creators": fakes.creators()}
        self.assertIsNone(outreach.settings({"outreach": good}).network_source)
        self.assertEqual(outreach.settings({"outreach": dict(good, creators=[])}).creators, ())
        for change in (
            {"follow_up_wait_days": 0},
            {"follow_up_wait_days": True},
            {"network_ask_source": 3},
            {"creators": None},
            {"creators": [{"key": "A B", "name": "A"}]},
            {"creators": [{"key": "a"}]},
            {"creators": ["a"]},
            {"creators": fakes.creators() + fakes.creators()[:1]},
        ):
            with self.subTest(change=change), self.assertRaises(ConfigError):
                outreach.settings({"outreach": dict(good, **change)})
        with self.assertRaises(ConfigError):
            outreach.settings({})
        with self.assertRaises(ConfigError):
            outreach.package_role(
                {
                    "products": [
                        {
                            "name": "X",
                            "status": "active",
                            "go_to_market_package": {"outreach": {"channel_plan": "a.md"}},
                        }
                    ]
                }
            )


class OutreachRecordTest(unittest.TestCase):
    def parse(self, **changes):
        record = {"exchange": exchange.EXCHANGE_VERSION, "item": "20261011-message-creator-x", "sent_on": "2026-10-12"}
        record.update(changes)
        return exchange.parse_outreach("20261011-message-creator-x", record)

    def test_a_record_of_what_was_sent_and_answered(self):
        record, problems = self.parse(replied_on="2026-10-14", follow_up_wait_days=21, note="Replied by email.")
        self.assertEqual(problems, [])
        self.assertEqual((record.sent_on, record.replied_on, record.wait_days), ("2026-10-12", "2026-10-14", 21))
        self.assertEqual(self.parse()[0].replied_on, None)
        self.assertEqual(self.parse(exchange=3)[1], [], "an earlier version's record reads as it is")

    def test_a_record_that_does_not_follow_the_format_is_not_used(self):
        for change, problem in (
            ({"item": "other"}, "item must equal the file name"),
            ({"sent_on": "yesterday"}, "sent_on must be the YYYY-MM-DD date"),
            ({"replied_on": "2026-10-01"}, "replied_on cannot come before sent_on"),
            ({"replied_on": True}, "replied_on must be null or"),
            ({"follow_up_wait_days": 0}, "follow_up_wait_days must be null or a whole number"),
            ({"follow_up_wait_days": 365}, "follow_up_wait_days must be null or a whole number"),
            ({"exchange": exchange.EXCHANGE_VERSION + 1}, "is newer than gr0wthlab can read"),
            ({"note": "two\nlines"}, "note must be one line"),
        ):
            with self.subTest(change=change):
                record, problems = self.parse(**change)
                self.assertIsNone(record)
                self.assertTrue(any(problem in found for found in problems), problems)
        self.assertEqual(exchange.parse_outreach("x", [])[1], ["the record must be a JSON object"])


class OutreachListsProposalTest(unittest.TestCase):
    SOURCE = fakes.REPO / outreach.RULES_PROPOSAL

    def test_it_is_a_valid_proposal_that_adds_exactly_the_two_lists_the_lint_reads(self):
        check = exchange.check_item(proposals.item_text(self.SOURCE.read_text(encoding="utf-8")), PRODUCTS)
        self.assertEqual(check.problems, [])
        self.assertEqual(check.item.kind, "package-change-proposal")
        keys = proposals.proposed_keys(check.item.body)
        wanted = {key for needed in {**lint.LOSS_FRAMING, **lint.CREATOR_RULE_TYPES}.values() for key in needed}
        self.assertEqual(set(keys), wanted)
        block = json.loads(check.item.body.split("```json\n")[1].split("\n```")[0])
        rules = lint.Rules(block)
        self.assertEqual(rules.creator_pending(), [])
        hits = rules.check([lint.Copy("message", "Don’t break your streak, you’ll regret it.")])
        self.assertEqual(sorted({finding.rule for finding in hits}), ["loss_framing"])
        self.assertEqual(
            [f.rule for f in rules.sponsorship(lint.Copy("message", "Send me your rate card."))], ["sponsorship_asks"]
        )
        self.assertEqual(
            rules.sponsorship(lint.Copy("message", "Early access is yours, with nothing asked in return.")), []
        )

    def test_without_the_lists_from_mandu_the_lint_knows_none_of_their_phrases(self):
        bare = lint.Rules({})
        self.assertEqual(bare.check([lint.Copy("message", "Don’t break your streak, you’ll regret it.")]), [])
        self.assertEqual(bare.sponsorship(lint.Copy("message", "Send me your rate card.")), [])
        self.assertEqual(bare.pending()[-1:] + bare.creator_pending(), ["loss framing", "sponsorship asks"])

    def test_a_post_is_not_read_for_sponsorship_asks_and_says_so(self):
        rules = lint.Rules({"sponsorship_asks": ["sponsor"], "loss_framing": ["falling behind"]})
        statuses = {row.rule: row.status for row in rules.statuses()}
        self.assertEqual((statuses["sponsorship_asks"], statuses["loss_framing"]), (lint.NOT_APPLICABLE, lint.APPLIED))
        self.assertEqual(rules.check([lint.Copy("TikTok caption", "A sponsor would be nice.")]), [])
        self.assertEqual(
            [f.rule for f in rules.check([lint.Copy("TikTok caption", "You are falling behind.")])], ["loss_framing"]
        )
        self.assertEqual(lint.Rules({}).creator_pending(), ["sponsorship asks"])


class CodesTest(unittest.TestCase):
    def test_the_split_between_execution_and_strategy_is_fixed_in_code(self):
        self.assertEqual(learning.EXECUTION, ("tone", "length", "factual-slip", "format"))
        self.assertEqual(learning.STRATEGY, ("fit", "angle", "claim", "positioning"))
        self.assertFalse(set(learning.EXECUTION) & set(learning.STRATEGY))
        for code in learning.EXECUTION:
            self.assertEqual((learning.kind(code), learning.route(code)), ("execution", learning.TO_INSTRUCTIONS))
            self.assertTrue(learning.may_refine_instructions(code))
        for code in learning.STRATEGY:
            self.assertEqual((learning.kind(code), learning.route(code)), ("strategy", learning.TO_PROPOSAL))
            self.assertFalse(learning.may_refine_instructions(code), "a strategy reason can never refine Instructions")
        self.assertFalse(learning.may_refine_instructions("anything-else"))
        with self.assertRaises(ValueError):
            learning.route("vibes")
        self.assertEqual(set(learning.MEANING), set(learning.CODES))

    def test_counts_read_as_n_of_m_never_as_a_percentage(self):
        self.assertEqual(learning.of(3, 7), "3 of 7")
        reasons = [
            learning.Reason(f"i{n}", "post-drafts", "words", "2026-10-11", code)
            for n, code in enumerate(["tone"] * 3 + ["claim", "", "", ""])
        ]
        self.assertEqual(
            learning.count_lines(reasons),
            ["post-drafts: 7 rejections, 4 of 7 coded (claim 1 of 7, tone 3 of 7); execution 3 of 7, strategy 1 of 7"],
        )
        record = json.dumps(learning.ledger_record(reasons, "run", fakes.SUNDAY_RUN))
        self.assertNotIn("%", record)
        self.assertIn("never as a percentage", record)

    def test_an_item_s_workflow_comes_from_its_queue_entry(self):
        for entry, workflow in (
            ({"kind": "post"}, "post-drafts"),
            ({"kind": "message", "message": {"purpose": "reply"}}, "listening"),
            ({"kind": "message", "message": {"purpose": "creator"}}, "outreach"),
            ({"kind": "package-change-proposal", "listening": {"proposal": "angle"}}, "listening"),
            ({"kind": "package-change-proposal"}, "package-review"),
            ({"kind": "dispatch-request"}, "dispatch-requests"),
            ({"kind": "notice"}, "review-queue"),
        ):
            self.assertEqual(learning.workflow_of(entry), workflow)


class InstructionsGuardTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(os.path.realpath(self.tmp.name))
        self.areas = fakes.workspace_areas(self.root / "repo")
        self.folder = self.root / "repo" / "workspace" / "instructions"
        (self.folder / "listening.md").write_text("Quote, never paraphrase.\n", encoding="utf-8")
        (self.folder / "sub").mkdir()
        (self.folder / "sub" / "notes.md").write_text("Notes.\n", encoding="utf-8")
        self.before = learning.remember(self.areas)

    def tearDown(self):
        self.tmp.cleanup()

    def test_nothing_changed_means_nothing_is_touched(self):
        self.assertEqual(sorted(self.before.files), ["instructions/listening.md", "instructions/sub/notes.md"])
        self.assertEqual(learning.put_back(self.before, self.areas), [])

    def test_every_change_is_undone_and_named(self):
        (self.folder / "listening.md").write_text("Paraphrase freely.\n", encoding="utf-8")
        (self.folder / "sub" / "notes.md").unlink()
        (self.folder / "sub").rmdir()
        (self.folder / "new" / "deep").mkdir(parents=True)
        (self.folder / "new" / "deep" / "added.md").write_text("Added.\n", encoding="utf-8")
        lines = learning.put_back(self.before, self.areas)
        self.assertEqual(
            lines,
            [
                "`instructions/new/deep/added.md` was added during the run and removed",
                "`instructions/listening.md` was changed during the run and put back as it was",
                "`instructions/sub/notes.md` was removed during the run and put back as it was",
            ],
        )
        self.assertEqual((self.folder / "listening.md").read_text(encoding="utf-8"), "Quote, never paraphrase.\n")
        self.assertEqual((self.folder / "sub" / "notes.md").read_text(encoding="utf-8"), "Notes.\n")
        self.assertFalse((self.folder / "new").exists())
        self.assertEqual(learning.put_back(self.before, self.areas), [])

    def test_a_link_left_in_place_of_a_file_is_never_written_through(self):
        outside = self.root / "outside.md"
        outside.write_text("Mandu's own file.\n", encoding="utf-8")
        (self.folder / "listening.md").unlink()
        (self.folder / "listening.md").symlink_to(outside)
        lines = learning.put_back(self.before, self.areas)
        self.assertEqual(lines, ["`instructions/listening.md` was changed during the run and put back as it was"])
        self.assertFalse((self.folder / "listening.md").is_symlink())
        self.assertEqual((self.folder / "listening.md").read_text(encoding="utf-8"), "Quote, never paraphrase.\n")
        self.assertEqual(outside.read_text(encoding="utf-8"), "Mandu's own file.\n")

    def test_a_folder_replaced_by_a_link_is_made_real_again_before_anything_is_written(self):
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        (self.folder / "sub" / "notes.md").unlink()
        (self.folder / "sub").rmdir()
        (self.folder / "sub").symlink_to(elsewhere)
        learning.put_back(self.before, self.areas)
        self.assertFalse((self.folder / "sub").is_symlink())
        self.assertEqual((self.folder / "sub" / "notes.md").read_text(encoding="utf-8"), "Notes.\n")
        self.assertEqual(list(elsewhere.iterdir()), [], "nothing was written through the link")


if __name__ == "__main__":
    unittest.main()
