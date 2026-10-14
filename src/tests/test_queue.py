"""The Review Queue ledger: stable identifiers, validation before queuing, decisions, carry-over, and order."""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from gr0wthlab import boundary, exchange, state
from gr0wthlab.areas import Areas, Store
from gr0wthlab.queue import APPROVED, OPEN, REJECTED, SUPERSEDED, Ledger, QueueError
from tests import fakes
from tests.test_boundary import CONFIG, REGISTRY

PRODUCTS = ["RepToday", "Immerse"]
NOW = datetime(2026, 10, 11, 23, 0, tzinfo=timezone.utc)


def decision(item, verdict="approve", reason=None, decided_at="2026-10-11T19:42:00-07:00"):
    return exchange.Decision(item, verdict, reason, None, decided_at, "2026-10-11")


class LedgerTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(os.path.realpath(self.tmp.name)) / "gr0wthlab"
        for area in CONFIG["writable_areas"].values():
            (self.repo / area).mkdir(parents=True)
        resolved = boundary.resolve_boundary(
            self.repo, CONFIG, REGISTRY, {}, self.repo.parent, git=[self.repo / ".git"]
        )
        self.areas = Areas(resolved)
        self.store = Store(resolved.ledger)
        self.incoming = self.repo / "workspace/review-queue/incoming"
        self.incoming.mkdir()
        self.ledger = Ledger()

    def tearDown(self):
        self.tmp.cleanup()

    def drop(self, name, text):
        path = self.incoming / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def take(self, run="RUN1", now=NOW):
        return self.ledger.take_incoming(self.areas, self.store, PRODUCTS, run, now)


class IncomingTest(LedgerTestCase):
    @unittest.skipIf(os.geteuid() == 0, "root can list any folder")
    def test_a_folder_that_cannot_be_listed_or_searched_is_reported_not_fatal(self):
        self.drop("item.md", fakes.PROPOSAL)
        self.drop("sub/inner/item.md", fakes.PROPOSAL)
        cases = {
            self.incoming: (0o300, "`review-queue/incoming` could not be read (Permission denied)"),
            self.incoming / "sub": (0o600, "`review-queue/incoming/sub/inner` could not be read (Permission denied)"),
        }
        for folder, (mode, problem) in cases.items():
            with self.subTest(folder=folder.name):
                self.areas.problems.clear()
                folder.chmod(mode)
                try:
                    self.take()
                finally:
                    folder.chmod(0o755)
                self.assertTrue(any(line.startswith(problem) for line in self.areas.problems), self.areas.problems)

    def test_a_valid_item_is_queued_under_a_stable_identifier(self):
        self.drop("name-status-stale.md", fakes.PROPOSAL)
        published, set_aside = self.take()
        self.assertEqual((published, set_aside), (["20261011-name-status-stale"], []))
        item = self.repo / "ledger/review-queue/items/20261011-name-status-stale.md"
        self.assertTrue(
            item.read_text(encoding="utf-8").startswith(
                f"---\nexchange: {exchange.EXCHANGE_VERSION}\nid: 20261011-name-status-stale\n"
            )
        )
        entry = self.ledger.entries["20261011-name-status-stale"]
        self.assertEqual(entry["status"], OPEN)
        self.assertEqual(entry["file"], "review-queue/items/20261011-name-status-stale.md")
        self.assertEqual(entry["product"], "RepToday")
        self.assertEqual(list(self.incoming.iterdir()), [])

    def test_a_repeated_slug_gets_a_new_identifier(self):
        self.drop("same.md", fakes.PROPOSAL)
        self.take()
        self.drop("same.md", fakes.PROPOSAL)
        published, _ = self.take("RUN2")
        self.assertEqual(published, ["20261011-same-2"])

    def test_malformed_files_are_set_aside_with_their_problems(self):
        self.drop("broken.md", fakes.PROPOSAL.replace("## Touches", "## Changes"))
        self.drop("Bad Name.md", fakes.PROPOSAL)
        self.drop("nested/deep.md", fakes.PROPOSAL)
        self.drop(".hidden.md", fakes.PROPOSAL)
        published, set_aside = self.take()
        self.assertEqual(published, [])
        names = {item.name: item for item in set_aside}
        self.assertEqual(set(names), {"broken.md", "Bad Name.md", "nested/deep.md", ".hidden.md"})
        self.assertTrue(any("sections must be exactly" in problem for problem in names["broken.md"].problems))
        self.assertEqual(list(self.incoming.iterdir()), [])
        record = json.loads((self.repo / "ledger/review-queue/set-aside/RUN1.json").read_text(encoding="utf-8"))
        self.assertEqual(
            record,
            {"run": "RUN1", "items": [{"name": item.name, "reasons": list(item.problems)} for item in set_aside]},
        )
        kept = sorted(path.name for path in (self.repo / "ledger/review-queue").rglob("*") if path.is_file())
        self.assertEqual(kept, ["RUN1.json"], "nothing of a set-aside file is kept but its record")

    def test_a_set_aside_file_leaves_its_name_and_reasons_and_none_of_its_words(self):
        """Every line of every file below carries the marker; no reason, record, or other file in the ledger does."""
        marker = "zqxstranger"

        seen = {}
        self.drop("first.md", fakes.PROPOSAL)
        self.ledger.take_incoming(self.areas, self.store, PRODUCTS, "RUN0", NOW, seen)
        files = fakes.refused_items(marker)
        # The same ask as the queued item, with the marker only where an item's fingerprint does not look.
        files["a-twin.md"] = fakes.PROPOSAL.replace("`projects/", f"`{marker}/")
        for name, text in files.items():
            self.drop(name, text)
        published, set_aside = self.ledger.take_incoming(self.areas, self.store, PRODUCTS, "RUN1", NOW, seen)
        self.assertEqual(published, [])
        self.assertEqual({item.name for item in set_aside}, set(files))
        for item in set_aside:
            with self.subTest(name=item.name):
                self.assertTrue(item.problems)
                self.assertNotIn(marker, " ".join(item.problems).casefold())
        reasons = {item.name: item.problems for item in set_aside}
        self.assertIn("line 3 of the front matter is not one of", reasons["a-line.md"][0])
        self.assertIn("exchange must be a version number", reasons["a-version.md"])
        self.assertIn("supersedes names no item in the Review Queue", reasons["a-repeat.md"][0])
        self.assertEqual(reasons["a-twin.md"], ("asks the same as 20261011-first, which is open",))
        self.assertIn("Evidence item 2 has no source (a URL or a `path`)", reasons["a-source.md"])
        self.assertIn(
            "sections must be exactly: ## Proposal, ## Touches, ## Evidence, ## Options; missing ## Touches,"
            " 1 other section",
            reasons["a-section.md"],
        )
        for path in (self.repo / "ledger").rglob("*"):
            if path.is_file():
                self.assertNotIn(marker, path.read_text(encoding="utf-8").casefold(), path)
        self.assertEqual(list(self.incoming.iterdir()), [])

    def test_a_set_aside_record_that_cannot_be_written_is_said_in_each_file_s_reasons(self):
        (self.repo / "ledger/review-queue").mkdir(parents=True)
        (self.repo / "ledger/review-queue/set-aside").write_text("not a folder\n", encoding="utf-8")
        self.drop("broken.md", fakes.PROPOSAL.replace("## Touches", "## Changes"))
        published, set_aside = self.take()
        self.assertEqual(published, [])
        (item,) = set_aside
        self.assertTrue(item.problems[0].startswith("sections must be exactly"))
        self.assertTrue(item.problems[-1].startswith("the set-aside record could not be written ("), item.problems)
        self.assertEqual(list(self.incoming.iterdir()), [], "the file is removed all the same, and copied nowhere")

    def test_links_are_never_followed(self):
        secret = self.repo.parent / "secret.md"
        secret.write_text(fakes.PROPOSAL, encoding="utf-8")
        os.symlink(str(secret), str(self.incoming / "linked.md"))
        os.link(str(secret), str(self.incoming / "hard.md"))
        published, set_aside = self.take()
        self.assertEqual(published, [])
        self.assertEqual({item.name for item in set_aside}, {"linked.md", "hard.md"})
        self.assertTrue(secret.is_file())
        self.assertFalse(any((self.repo / "ledger/review-queue/set-aside").rglob("*.md")))

    def test_an_item_that_asks_the_same_as_another_is_never_queued(self):
        self.drop("first.md", fakes.PROPOSAL)
        self.drop("second.md", fakes.PROPOSAL.replace("line 24", "line 25").replace("cleared", "  CLEARED "))
        seen = {}
        published, set_aside = self.ledger.take_incoming(self.areas, self.store, PRODUCTS, "RUN1", NOW, seen)
        self.assertEqual(published, ["20261011-first"])
        self.assertIn("asks the same as 20261011-first, which is open", set_aside[0].problems[0])
        self.ledger.take_decisions([decision("20261011-first", "reject", "No.")], "RUN2", NOW)
        self.drop("again.md", fakes.PROPOSAL)
        published, set_aside = self.ledger.take_incoming(self.areas, self.store, PRODUCTS, "RUN2", NOW, seen)
        self.assertEqual(published, [])
        self.assertIn("asks the same as 20261011-first, which is rejected", set_aside[0].problems[0])
        self.drop("reworded.md", fakes.proposal(title="record the name as searched and reserved"))
        published, _ = self.ledger.take_incoming(self.areas, self.store, PRODUCTS, "RUN2", NOW, seen)
        self.assertEqual(published, ["20261011-reworded"])

    def test_supersedes_withdraws_an_open_item_only(self):
        self.drop("first.md", fakes.PROPOSAL)
        self.take()
        self.drop("second.md", fakes.proposal(extra="supersedes: 20261011-first\n"))
        published, set_aside = self.take("RUN2")
        self.assertEqual((published, set_aside), (["20261011-second"], []))
        first = self.ledger.entries["20261011-first"]
        self.assertEqual((first["status"], first["superseded_by"]), (SUPERSEDED, "20261011-second"))
        self.drop("third.md", fakes.proposal(extra="supersedes: 20261011-first\n"))
        published, set_aside = self.take("RUN3")
        self.assertEqual(published, [])
        self.assertIn("not an open item", set_aside[0].problems[0])

    def test_supersedes_never_withdraws_an_open_item_whose_item_file_could_not_be_read(self):
        """The reason given states what the records show: the file could not be read, so the open item stands."""
        self.drop("first.md", fakes.PROPOSAL)
        self.take()
        self.drop("second.md", fakes.proposal(extra="supersedes: 20261011-first\n", title="record it another way"))
        self.drop("third.md", fakes.proposal(extra="supersedes: 20261011-first\n", title="record it a third way"))
        lost = {"20261011-first": "`review-queue/items/20261011-first.md`, its item file, could not be read"}
        published, set_aside = self.ledger.take_incoming(self.areas, self.store, PRODUCTS, "RUN2", NOW, {}, (), lost)
        self.assertEqual(published, [])
        reason = (
            "supersedes 20261011-first: `review-queue/items/20261011-first.md`, its item file, could not be read,"
            " so the open item stands and nothing replaces it in this run"
        )
        self.assertEqual(
            sorted((item.name, item.problems) for item in set_aside),
            [("second.md", (reason,)), ("third.md", (reason,))],
        )
        self.assertEqual(self.ledger.entries["20261011-first"]["status"], OPEN)
        self.assertEqual(
            [(kept.item, kept.unread) for kept in self.ledger.stood],
            [("20261011-first", (lost["20261011-first"],))],
            "the one open item stands once, however many items would have replaced it",
        )

    def test_an_item_with_the_kind_and_ask_of_a_queued_one_whose_item_file_could_not_be_read_is_never_queued(self):
        """Its fingerprint is then unknown, so nothing shows the item is not the ask the Founder decided."""
        self.drop("first.md", fakes.PROPOSAL)
        self.take()
        self.ledger.take_decisions([decision("20261011-first", "reject", "No.")], "RUN2", NOW)
        rejected = dict(self.ledger.entries["20261011-first"])
        lost = {"20261011-first": "`review-queue/items/20261011-first.md`, its item file, could not be read"}
        self.drop("again.md", fakes.PROPOSAL.replace("cleared\n", "  CLEARED \n").replace("stale caveat", "caveat"))
        self.drop("other.md", fakes.proposal(title="record it another way"))
        self.drop("notice.md", fakes.proposal("notice"))
        published, set_aside = self.ledger.take_incoming(self.areas, self.store, PRODUCTS, "RUN2", NOW, {}, (), lost)
        self.assertEqual(published, ["20261011-notice", "20261011-other"], "the ledger shows these ask something else")
        self.assertEqual(
            [(item.name, item.problems) for item in set_aside],
            [
                (
                    "again.md",
                    (
                        "has the kind and ask of 20261011-first, which is rejected: `review-queue/items/"
                        "20261011-first.md`, its item file, could not be read, so nothing shows this item asks"
                        " anything else",
                    ),
                )
            ],
        )
        self.assertEqual((self.ledger.unsettled, self.ledger.stood), ([lost["20261011-first"]], []))
        self.assertEqual(self.ledger.entries["20261011-first"], rejected)

    def test_an_item_the_launcher_filed_from_reviewed_text_is_never_superseded(self):
        request = exchange.check_item(fakes.proposal("dispatch-request"), PRODUCTS).item
        filed = self.ledger.publish(self.store, request, "waitlist", "RUN1", NOW, origin="dispatch/waitlist")
        self.drop("smaller.md", fakes.proposal("dispatch-request", f"supersedes: {filed}\n", "build less"))
        published, set_aside = self.take("RUN2")
        self.assertEqual(published, [])
        self.assertIn(f"supersedes {filed}, which the launcher filed from reviewed text", set_aside[0].problems[0])
        self.assertEqual(self.ledger.entries[filed]["status"], OPEN)


class DecisionsTest(LedgerTestCase):
    def setUp(self):
        super().setUp()
        for slug in ("a", "b", "c"):
            self.drop(f"{slug}.md", fakes.proposal(title=f"fix {slug}"))
        self.take()

    def test_each_decision_closes_its_item_once(self):
        outcomes = self.ledger.take_decisions(
            [decision("20261011-a"), decision("20261011-b", "reject", "No.")], "RUN2", NOW
        )
        self.assertEqual([outcome.status for outcome in outcomes], ["taken", "taken"])
        self.assertEqual(self.ledger.entries["20261011-a"]["status"], APPROVED)
        self.assertEqual(self.ledger.entries["20261011-b"]["status"], REJECTED)
        self.assertEqual([entry["id"] for entry in self.ledger.ordered()], ["20261011-c"])
        again = self.ledger.take_decisions([decision("20261011-a")], "RUN3", NOW)
        self.assertEqual(again[0].status, "already-taken")
        changed = self.ledger.take_decisions([decision("20261011-a", "reject", "Actually no.")], "RUN3", NOW)
        self.assertEqual(changed[0].status, "conflict")
        self.assertEqual(self.ledger.entries["20261011-a"]["status"], APPROVED)

    def test_unknown_items_and_decisions_on_superseded_items(self):
        self.drop("d.md", fakes.proposal(extra="supersedes: 20261011-c\n"))
        self.take("RUN2")
        self.drop("e.md", fakes.proposal(extra="supersedes: 20261011-d\n", title="fix e"))
        self.take("RUN3")
        outcomes = self.ledger.take_decisions(
            [decision("20261011-zzz"), decision("20261011-c", "reject", "No.")], "RUN4", NOW
        )
        self.assertEqual(
            {o.decision.item: o.status for o in outcomes},
            {"20261011-zzz": "unknown-item", "20261011-c": "taken"},
        )
        superseded = self.ledger.entries["20261011-c"]
        self.assertEqual((superseded["status"], superseded["decided"]), (SUPERSEDED, REJECTED))
        self.assertEqual([entry["id"] for entry in self.ledger.ordered()], ["20261011-a", "20261011-b", "20261011-e"])
        replaced = self.ledger.decided_replaced(self.ledger.entries["20261011-e"])
        self.assertEqual([entry["id"] for entry in replaced], ["20261011-c"])
        again = self.ledger.take_decisions([decision("20261011-c", "reject", "No.")], "RUN5", NOW)
        self.assertEqual(again[0].status, "already-taken")
        changed = self.ledger.take_decisions([decision("20261011-c")], "RUN5", NOW)
        self.assertEqual(changed[0].status, "conflict")
        self.assertEqual(superseded["decided"], REJECTED)


class OrderAndPersistenceTest(LedgerTestCase):
    def post(self, slug, day, slot=None, now=NOW):
        """A post as the launcher queues it from a Draft that passed."""
        fields = {"kind": "post", "product": "RepToday", "window": "1", "day": str(day)}
        if slot:
            fields["slot"] = slot
        item = exchange.Item(fields, f"Approve day {day} post: {slug}", "The Draft.", "- The post", "- `a/b.md` line 1")
        return self.ledger.publish(self.store, item, slug, "RUN1", now, {"draft": f"day-{day:02d}.md"})

    def message(self, slug, purpose="beta-invitation"):
        """A recruiting message as the launcher queues it from a Draft that passed."""
        fields = {"kind": "message", "product": "RepToday"}
        item = exchange.Item(fields, f"Approve {slug}", "The Draft.", "- The message", "- `a/b.md` line 1")
        extra = {"beta": purpose, "draft": f"drafts/beta-recruiting/RepToday/{slug}.md"}
        return self.ledger.publish(self.store, item, slug, "RUN1", NOW, extra)

    def test_posts_by_nearest_slot_then_by_day_then_each_kind_oldest_first(self):
        self.drop("notice.md", fakes.proposal("notice"))
        self.post("later-post", 6, "2026-10-16T19:00-07:00")
        self.drop("proposal.md", fakes.PROPOSAL)
        self.post("unslotted-day-2", 2)
        self.post("sooner-post", 5, "2026-10-15T02:00Z")
        self.post("unslotted-day-1", 1, now=NOW + timedelta(minutes=5))
        self.message("message")
        self.take()
        self.drop("old-request.md", fakes.proposal("dispatch-request"))
        self.take("RUN2", NOW + timedelta(days=7))
        # A Weekly Read decision, as the launcher queues it from a memo that passed its checks.
        fields = {"kind": "weekly-read-decision", "product": "RepToday", "window": "1", "read": "7"}
        item = exchange.Item(fields, "Weekly Read day 7: P01, keep", "The line.", "- P01", "- `a/b.md` line 1")
        self.ledger.publish(self.store, item, "decision", "RUN2", NOW + timedelta(days=7))
        order = [entry["id"][9:] for entry in self.ledger.ordered()]
        self.assertEqual(
            order,
            [
                "sooner-post",
                "later-post",
                "unslotted-day-1",
                "unslotted-day-2",
                "message",
                "decision",
                "old-request",
                "proposal",
                "notice",
            ],
        )
        entry = self.ledger.entries["20261011-later-post"]
        self.assertEqual((entry["window"], entry["day"], entry["draft"]), (1, 6, "day-06.md"))

    def test_a_post_or_a_message_is_never_taken_from_incoming(self):
        self.drop("day-3.md", fakes.proposal("post", "window: 1\nday: 3\n", title="day 3"))
        self.drop("network-ask.md", fakes.proposal("message", title="a note to my network"))
        published, set_aside = self.take()
        self.assertEqual(published, [])
        problems = {item.name: item.problems for item in set_aside}
        self.assertIn(
            "a post is queued only from its Draft in drafts/posts/, after the launcher's checks; never write one here",
            problems["day-3.md"],
        )
        self.assertEqual(
            problems["network-ask.md"],
            (
                "a message is queued only from its Draft in drafts/messages/ or drafts/beta-recruiting/, after the"
                " launcher's checks; never write one here",
            ),
        )
        self.assertEqual(self.ledger.entries, {})
        self.drop("example-notice.md", fakes.proposal("notice"))
        self.drop("name-status-stale.md", fakes.PROPOSAL)
        published, set_aside = self.take("RUN2")
        self.assertEqual((len(published), set_aside), (2, []))

    BANK = "projects/RepToday/gtm/05-social-pmf/angles.md"
    PAIRS = "projects/RepToday/gtm/05-social-pmf/ab-pairs.md"
    KEPT = "evidence/listening/quotes/d-0123456789ab.json"

    def declared(self, title, new_angle, touches=None, evidence=""):
        """A package-change proposal with this ask and declaration, touching that package file, with that Evidence
        line before its own."""
        text = fakes.proposal(title=title, new_angle=new_angle)
        if touches:
            text = text.replace("- `projects/RepToday/gtm/02-brand/brand-guidelines.md`", f"- `{touches}`")
        return text.replace("- Cleared and reserved:", f"{evidence}\n- Cleared and reserved:".lstrip("\n"))

    def take_kept(self):
        """Take incoming/ in as a run whose ledger keeps one Listening quote."""
        return self.ledger.take_incoming(self.areas, self.store, PRODUCTS, "RUN1", NOW, None, {self.KEPT})

    def test_a_package_change_proposal_that_declares_nothing_is_set_aside(self):
        self.drop("fix.md", fakes.proposal(new_angle=None))
        published, set_aside = self.take_kept()
        self.assertEqual(published, [])
        self.assertIn(
            "a package-change proposal needs new_angle: yes when it adds or changes an Angle or Hook",
            set_aside[0].problems[0],
        )

    def test_a_declared_angle_or_hook_is_queued_only_when_its_evidence_names_a_kept_quote_exactly(self):
        title = "introduce Angle P07 for desk workers"
        for evidence in (
            "",
            "- Sourced pain: `evidence/listening/quotes/d-000000000000.json`",
            "- The Founder's reason: `evidence/decisions/20261011-fit-wording.json`",
            f"- Sourced pain: `notes/{self.KEPT}.txt`",
            f"- Sourced pain, in {self.KEPT}: `{self.BANK}` line 3",
        ):
            with self.subTest(evidence=evidence):
                self.drop("angle.md", self.declared(title, "yes", self.BANK, evidence))
                published, set_aside = self.take_kept()
                self.assertEqual(published, [])
                (problem,) = set_aside[0].problems
                self.assertIn(
                    "it declares new_angle: yes, and a proposal that adds or changes an Angle or Hook", problem
                )
                self.assertIn(
                    "any Hook, signal, or kill criterion included (FR-7), is queued only with sourced pain", problem
                )
                self.assertIn("no record its Evidence names is a Listening quote the launcher keeps", problem)
                self.assertIn("Name one exactly in an Evidence line, as `evidence/listening/quotes/", problem)
        self.drop("angle.md", self.declared(title, "yes", self.BANK, f"- Sourced pain: `{self.KEPT}`"))
        published, set_aside = self.take_kept()
        self.assertEqual((published, set_aside), (["20261011-angle"], []))
        entry = self.ledger.entries["20261011-angle"]
        self.assertEqual(entry["new_angle"], "yes")
        queued = (self.store.root / entry["file"]).read_text(encoding="utf-8")
        self.assertIn("\nnew_angle: yes\n---\n", queued, "the declaration is on the item the Founder reads")

    def test_a_proposal_that_declares_no_angle_or_hook_is_queued_whatever_it_touches_or_says(self):
        for title, touches in (
            ("add the Hook's missing kill criterion to day 4", self.PAIRS),
            ("mark the new Hook on day 9 as frozen", self.PAIRS),
            ("record the cleared name in the Angle bank's caveat", self.BANK),
            ("add the Hook freeze date to the calendar", None),
            ("add Angle P03's missing source link", self.BANK),
            ("add hook-word-cap note to the brand guidelines", None),
            ("introduce Angle P07 for desk workers", self.BANK),
        ):
            with self.subTest(title=title):
                self.drop("fix.md", self.declared(title, "no", touches))
                published, set_aside = self.take_kept()
                self.assertEqual((len(published), set_aside), (1, []))
                entry = self.ledger.entries[published[0]]
                self.assertEqual(entry["new_angle"], "no")
                queued = (self.store.root / entry["file"]).read_text(encoding="utf-8")
                self.assertIn("\nnew_angle: no\n---\n", queued, "the Founder reads what it declared")

    def test_no_item_the_agent_writes_supersedes_a_post(self):
        post = self.post("day-3", 3)
        self.drop("day-3-off.md", fakes.proposal("notice", f"supersedes: {post}\n", "day 3 is off"))
        published, set_aside = self.take("RUN2")
        self.assertEqual(published, [])
        self.assertEqual(
            set_aside[0].problems,
            (
                f"supersedes {post}, a post the launcher queued from its Draft; only a change to that Draft in"
                " drafts/posts/ replaces it",
            ),
        )
        self.assertEqual(self.ledger.entries[post]["status"], OPEN)

    def test_no_item_the_agent_writes_supersedes_a_recruiting_message(self):
        queued = [self.message("invitation"), self.message("waitlist-ask", "waitlist-ask")]
        for identifier in queued:
            text = fakes.proposal("notice", f"supersedes: {identifier}\n", f"{identifier} is off")
            self.drop(f"off-{identifier}.md", text)
        published, set_aside = self.take("RUN2")
        self.assertEqual(published, [])
        self.assertEqual(
            sorted(problem for item in set_aside for problem in item.problems),
            [
                f"supersedes {identifier}, a message the launcher queued from its Draft; only a change to that Draft in"
                " drafts/messages/ or drafts/beta-recruiting/ replaces it"
                for identifier in sorted(queued)
            ],
        )
        self.assertEqual([self.ledger.entries[identifier]["status"] for identifier in queued], [OPEN, OPEN])

    def test_an_item_carries_over_only_once_a_sitting_has_left_it_undecided(self):
        self.drop("first.md", fakes.PROPOSAL)
        [first] = self.take("20261011T230000Z-scheduled-aaaa")[0]
        self.drop("rerun.md", fakes.proposal(title="queued by a re-run before the sitting"))
        self.take("20261011T233000Z-on-demand-bbbb", NOW + timedelta(minutes=30))
        self.ledger.mark_carried_over({})
        self.assertEqual([entry["carried_over"] for entry in self.ledger.ordered()], [False, False])

        sitting = NOW.astimezone().date().isoformat()
        self.drop("after.md", fakes.proposal(title="queued after the sitting"))
        [after] = self.take("20261011T234500Z-on-demand-cccc", NOW + timedelta(minutes=45))[0]
        read_by = "20261011T234500Z-on-demand-cccc"
        self.ledger.mark_carried_over({"2026-10-01": read_by, sitting: read_by})
        entry = self.ledger.entries[first]
        self.assertEqual((entry["carried_over"], entry["carried_over_from"]), (True, sitting))
        entry = self.ledger.entries[after]
        self.assertEqual((entry["carried_over"], "carried_over_from" in entry), (False, False))

        self.ledger.take_decisions([decision(first)], "20261018T230000Z-scheduled-dddd", NOW)
        self.assertNotIn("carried_over_from", self.ledger.entries[first])

    def test_queue_json_round_trips(self):
        self.drop("old.md", fakes.PROPOSAL)
        self.take("RUN1")
        self.drop("new.md", fakes.PROPOSAL)
        self.take("RUN2", NOW + timedelta(days=7))
        self.ledger.take_decisions([decision("20261011-old")], "RUN2", NOW)
        self.drop("kept.md", fakes.PROPOSAL)
        self.take("RUN1")
        next_run = datetime(2026, 10, 18, 16, 0).astimezone()
        data = self.ledger.as_json("RUN2", NOW, "run-reports/RUN2.md", next_run)
        self.assertEqual(datetime.fromisoformat(data["next_run"]), next_run)
        self.assertEqual([entry["id"] for entry in data["open"]], ["20261011-kept", "20261018-new"])
        self.assertEqual([entry["id"] for entry in data["closed"]], ["20261011-old"])
        path = self.repo / "ledger/review-queue/queue.json"
        self.store.write_json(path, data)
        loaded = Ledger.load(path)
        self.assertEqual(sorted(loaded.entries), sorted(self.ledger.entries))
        self.assertEqual(loaded.entries["20261011-old"]["status"], APPROVED)

    def test_an_unreadable_ledger_is_not_overwritten(self):
        path = self.repo / "ledger/review-queue/queue.json"
        path.parent.mkdir(parents=True)
        path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(QueueError):
            Ledger.load(path)
        newer = {"exchange": exchange.EXCHANGE_VERSION + 1, "open": [], "closed": []}
        path.write_text(json.dumps(newer), encoding="utf-8")
        with self.assertRaises(QueueError):
            Ledger.load(path)

    def test_a_queue_and_its_items_still_read_after_a_version_bump(self):
        self.drop("first.md", fakes.PROPOSAL)
        [first] = self.take()[0]
        path = self.repo / "ledger/review-queue/queue.json"
        self.store.write_json(path, self.ledger.as_json("RUN1", NOW, "run-reports/RUN1.md", NOW))
        with mock.patch.object(exchange, "EXCHANGE_VERSION", exchange.EXCHANGE_VERSION + 1):
            loaded = Ledger.load(path)
            hashes, problems = state.item_hashes(
                self.repo / "ledger", loaded.entries, PRODUCTS, state.ReviewQueueState()
            )
        self.assertEqual(list(loaded.entries), [first])
        self.assertEqual((list(hashes), problems), ([first], []))
        self.assertEqual(len(Ledger.load(path.with_name("absent.json")).entries), 0)


if __name__ == "__main__":
    unittest.main()
