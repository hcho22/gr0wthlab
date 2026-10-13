"""Beta Cohort recruiting outside a whole run: the records the Founder makes, the order invitations go out in, the
checks of a recruiting Draft, the run's one decision about the batch, and the run state."""

import dataclasses
import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path

from gr0wthlab import beta, beta_drafts, exchange, settings, state, waitlist
from gr0wthlab.boundary import ConfigError
from gr0wthlab.queue import Ledger
from tests import fakes

REGISTRY = json.loads((fakes.REPO / "config" / "products.json").read_text(encoding="utf-8"))
SCENARIO = {"run_started": "2026-10-11T23:00:00+00:00", "beta_build": fakes.BETA_BUILD}


def batch(number, status, candidates, on="2026-10-04", **more):
    return {
        "id": f"{on.replace('-', '')}-beta-invitation-batch-{number:02d}",
        "status": status,
        "batch": number,
        "candidates": candidates,
        "published_at": f"{on}T23:10:00+00:00",
        **more,
    }


class TempCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(os.path.realpath(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def plan(self, view=None, **scenario):
        view = fakes.waitlist_view() if view is None else view
        return fakes.beta_plan(self.root / f"run-{len(list(self.root.iterdir()))}", dict(SCENARIO, **scenario), view)


class RecordsTest(unittest.TestCase):
    def test_a_beta_build_record_is_an_approval_only_in_its_format(self):
        record, problems = exchange.parse_beta_build("RepToday", fakes.BETA_BUILD)
        self.assertEqual(problems, [])
        self.assertEqual((record.approved_on, record.recruiting, record.build), ("2026-10-09", "open", "1.0 (42)"))
        for change, problem in (
            ({"exchange": 3}, "exchange must be 4 or later"),
            ({"exchange": exchange.EXCHANGE_VERSION + 1}, "newer than gr0wthlab can read"),
            ({"product": "Immerse"}, "product must equal the file name"),
            ({"approved_on": "soon"}, "approved_on must be the YYYY-MM-DD date"),
            ({"approved_on": "2026-10-12"}, "approved_on is after the day the record was made"),
            ({"recorded_at": "2026-10-10T19:40:00"}, "recorded_at must be an ISO 8601 time with its UTC offset"),
            ({"recruiting": "paused"}, "recruiting must be 'open' or 'stopped'"),
            ({"recruiting": "stopped"}, "a stop needs stopped_on"),
            ({"stopped_on": "2026-10-10"}, "stopped_on belongs only to a record whose recruiting is stopped"),
            ({"recruiting": "stopped", "stopped_on": "2026-10-01"}, "stopped_on is before approved_on"),
            ({"build": "one\ntwo"}, "build must be one line of text"),
        ):
            record, problems = exchange.parse_beta_build("RepToday", dict(fakes.BETA_BUILD, **change))
            self.assertIsNone(record, change)
            self.assertIn(problem, " | ".join(problems))
        stopped = dict(fakes.BETA_BUILD, recruiting="stopped", stopped_on="2026-10-10")
        self.assertEqual(exchange.parse_beta_build("RepToday", stopped)[0].stopped_on, "2026-10-10")
        self.assertEqual(exchange.parse_beta_build("RepToday", [])[1], ["the record must be a JSON object"])

    def test_a_report_keeps_a_count_the_founder_left_out_as_not_reported(self):
        report, problems = exchange.parse_beta_report(
            "RepToday-2026-10-18", fakes.beta_report("2026-10-18", invitations_sent=8, accepted=0, sessions_booked=None)
        )
        self.assertEqual(problems, [])
        self.assertEqual(report.counts, {"invitations_sent": 8, "accepted": 0, "sessions_booked": None})
        left_out, _ = exchange.parse_beta_report("RepToday-2026-10-18", fakes.beta_report("2026-10-18", accepted=3))
        self.assertEqual(left_out.counts, {"invitations_sent": None, "accepted": 3, "sessions_booked": None})
        for stem, record, problem in (
            ("RepToday-2026-10-17", fakes.beta_report("2026-10-18", accepted=3), "must be <product>-<date>"),
            ("RepToday-2026-10-18", fakes.beta_report("2026-10-18"), "the record reports none of"),
            ("RepToday-2026-10-18", fakes.beta_report("2026-10-18", accepted=-1), "accepted must be a whole number"),
            ("RepToday-2026-10-18", fakes.beta_report("2026-10-18", accepted=True), "accepted must be a whole number"),
            ("RepToday-2026-10-18", fakes.beta_report("2026-10-18", accepted="4"), "accepted must be a whole number"),
            ("RepToday-2026-10-18", dict(fakes.beta_report("2026-10-18", accepted=4), exchange=3), "4 or later"),
        ):
            parsed, problems = exchange.parse_beta_report(stem, record)
            self.assertIsNone(parsed, record)
            self.assertIn(problem, " | ".join(problems))

    def test_a_record_holding_an_address_is_refused_whole_and_never_repeated(self):
        record = dict(fakes.BETA_BUILD, build=f"sent from {fakes.ADDRESS}")
        data = json.dumps(record).encode("utf-8")
        gate = beta.read_gate(
            "RepToday", [("RepToday.json", Path("founder/beta-builds/RepToday.json"), data)], [], None
        )
        self.assertEqual(gate.status, beta.UNUSABLE)
        self.assertFalse(gate.recorded)
        self.assertIn("looks like an email address", gate.detail)
        self.assertNotIn("jane", gate.detail)
        report = dict(fakes.beta_report("2026-10-18", accepted=3), note=f"ask {fakes.ADDRESS}")
        raw = [("RepToday-2026-10-18.json", Path("/m/r.json"), json.dumps(report).encode("utf-8"))]
        usable, problems = beta.read_reports("RepToday", raw)
        self.assertEqual(usable, [])
        self.assertEqual(len(problems), 1)
        self.assertNotIn("jane", problems[0])

    def test_a_report_whose_file_name_looks_like_an_address_is_refused_whole_and_its_name_never_repeated(self):
        name = f"RepToday-{fakes.ADDRESS}.json"
        data = json.dumps(fakes.beta_report("2026-10-18", accepted=3)).encode("utf-8")
        usable, problems = beta.read_reports("RepToday", [(name, Path("/m") / name, data)])
        self.assertEqual(usable, [])
        self.assertEqual(
            problems,
            [
                "a file in `founder/beta-reports/` whose name is not repeated here: it holds something that looks like"
                " an email address, so nothing in it was read or kept"
            ],
        )
        misnamed = "RepToday-2026-10-17.json"
        _, problems = beta.read_reports("RepToday", [(misnamed, Path("/m") / misnamed, data)])
        self.assertIn(
            "`founder/beta-reports/RepToday-2026-10-17.json`: the file name 'RepToday-2026-10-17'", problems[0]
        )

    def test_only_a_valid_record_named_for_the_product_opens_the_gate(self):
        missing = beta.read_gate("RepToday", [], [], None)
        self.assertEqual((missing.status, missing.recorded), (beta.NOT_RECORDED, False))
        self.assertIn("not recorded: the Founder has recorded no approved Beta Build for RepToday", missing.detail)
        other = [("reptoday.json", Path("/m/reptoday.json"), json.dumps(fakes.BETA_BUILD).encode())]
        stray = [("RepToday.txt", "only <name>.json record files belong here")]
        misnamed = beta.read_gate("RepToday", other, stray, None)
        self.assertEqual((misnamed.status, misnamed.recorded), (beta.NOT_RECORDED, False))
        self.assertIn(
            "; `founder/beta-builds/` holds `RepToday.txt`, `reptoday.json`, and only `RepToday.json` is",
            misnamed.detail,
        )
        hidden = beta.read_gate("RepToday", [(f"{fakes.ADDRESS}.json", Path("/m/x.json"), b"{}")], [], None)
        self.assertIn("`founder/beta-builds/` holds 1 whose name is not repeated here", hidden.detail)
        self.assertNotIn("jane", hidden.detail)
        unreadable_file = beta.read_gate("RepToday", [], [("RepToday.json", "Permission denied")], None)
        self.assertEqual(unreadable_file.status, beta.UNUSABLE)
        self.assertIn(
            "`founder/beta-builds/RepToday.json` could not be used (Permission denied)", unreadable_file.detail
        )
        unreadable = beta.read_gate("RepToday", [], [], "Permission denied")
        self.assertEqual((unreadable.status, unreadable.recorded), (beta.UNUSABLE, False))
        broken = beta.read_gate("RepToday", [("RepToday.json", Path("/m/RepToday.json"), b"{not json")], [], None)
        self.assertEqual((broken.status, broken.recorded), (beta.UNUSABLE, False))
        self.assertIn("it is not JSON (line 1)", broken.detail)
        good = [("RepToday.json", Path("/m/RepToday.json"), json.dumps(fakes.BETA_BUILD).encode())]
        gate = beta.read_gate("RepToday", good, [], None)
        self.assertEqual((gate.status, gate.recorded, gate.stopped), ("open", True, False))
        self.assertEqual(
            gate.detail,
            "approved on 2026-10-09, build 1.0 (42), recorded 2026-10-10T19:40:00-07:00; recruiting is open",
        )

    def test_the_latest_report_states_each_count_or_leaves_it_not_reported(self):
        reports = [
            exchange.parse_beta_report(f"RepToday-{day}", fakes.beta_report(day, **counts))[0]
            for day, counts in (
                ("2026-10-18", {"invitations_sent": 8, "accepted": 3}),
                ("2026-10-25", {"invitations_sent": 16, "sessions_booked": 2}),
            )
        ]
        counts = beta.standing(reports)
        self.assertEqual(counts.accepted, 3)
        self.assertEqual(
            counts.line(),
            "as reported on 2026-10-25: invitations sent 16, accepted not reported (last reported: 3 on 2026-10-18),"
            " sessions booked 2",
        )
        self.assertEqual(counts.as_json()["not_reported"], ["accepted"])
        self.assertIsNone(counts.as_json()["accepted"])
        empty = beta.standing([])
        self.assertIsNone(empty.accepted)
        self.assertEqual(
            empty.line(),
            "none reported yet: invitations sent not reported, accepted not reported, sessions booked not reported",
        )
        self.assertEqual(empty.as_json()["not_reported"], list(exchange.BETA_COUNTS))


class InvitationOrderTest(unittest.TestCase):
    RULES = settings.Waitlist("RepToday", None, ("tiktok", "network"), ("lost", "regular"), ("lost",), 50)

    def entry(self, name, fit, opted_in, day, source="tiktok"):
        return waitlist.Entry(name, source, fit, opted_in, date.fromisoformat(day))

    def test_good_fit_opt_ins_first_then_sign_up_date_then_the_view_s_own_order(self):
        entries = [
            self.entry("late-good", "lost", True, "2026-10-09"),
            self.entry("never-asked", "lost", False, "2026-10-01"),
            self.entry("other-early", "regular", True, "2026-10-01"),
            self.entry("tie-first", "lost", True, "2026-10-05", "network"),
            self.entry("tie-second", "lost", True, "2026-10-05"),
            self.entry("no-answer", "unknown", True, "2026-10-02"),
        ]
        order = waitlist.invitation_order(entries, self.RULES)
        self.assertEqual(
            [(candidate.entry, candidate.good_fit) for candidate in order],
            [
                ("tie-first", True),
                ("tie-second", True),
                ("late-good", True),
                ("other-early", False),
                ("no-answer", False),
            ],
        )

    def test_the_source_never_moves_anyone(self):
        for sources in (("tiktok", "network"), ("network", "tiktok")):
            entries = [
                self.entry("a", "lost", True, "2026-10-05", sources[0]),
                self.entry("b", "lost", True, "2026-10-05", sources[1]),
            ]
            self.assertEqual([c.entry for c in waitlist.invitation_order(entries, self.RULES)], ["a", "b"])

    def test_a_candidate_carries_nothing_but_its_identifier_and_its_fit(self):
        self.assertEqual([field.name for field in dataclasses.fields(waitlist.Candidate)], ["entry", "good_fit"])


class ConfigTest(unittest.TestCase):
    def rules(self, change=None, batch_size=None):
        """The rules from the committed configuration, or with another batch size."""
        registry = json.loads(json.dumps(REGISTRY))
        product = registry["products"][0]
        if change:
            change(product)
        config = settings.load(fakes.REPO, {}, Path("/Users/founder"))
        if batch_size is not None:
            config = dataclasses.replace(config, beta_batch_size=batch_size)
        return beta.rules(registry, config)

    def test_the_committed_configuration(self):
        rules = self.rules()
        self.assertEqual((rules.product, rules.minimum, rules.maximum, rules.batch_size), ("RepToday", 20, 50, 20))
        self.assertEqual(rules.k8, "projects/RepToday/gtm/07-thesis/")
        self.assertEqual(
            sorted(source.path for source in rules.citable),
            [
                "projects/RepToday/gtm/02-brand/brand-guidelines.md",
                "projects/RepToday/gtm/06-channels/",
                "projects/RepToday/gtm/07-thesis/",
                "projects/RepToday/gtm/09-extras/marketing-agent/brand-rules.json",
            ],
        )
        run = json.loads((fakes.REPO / "config" / "run.json").read_text(encoding="utf-8"))
        self.assertTrue(run["outputs"]["beta-recruiting"]["built"])
        self.assertNotIn("Beta Build approval", [source["name"] for source in run["sources_not_connected"]])

    def test_a_registry_that_names_it_wrongly_stops_the_run(self):
        def without(key):
            return lambda product: product["beta_recruiting"].pop(key)

        def cohort(minimum, maximum):
            return lambda product: product["beta_recruiting"].update(cohort={"minimum": minimum, "maximum": maximum})

        for change in (
            without("k8"),
            without("brand_rules"),
            without("cohort"),
            cohort(30, 20),
            cohort(0, 20),
            cohort(True, 20),
            lambda product: product["beta_recruiting"].update(k8="projects/RepToday/gtm/01-research/"),
            lambda product: product["beta_recruiting"].update(brand_rules="projects/RepToday/gtm/x.json"),
            lambda product: product.pop("waitlist"),
        ):
            with self.assertRaises(ConfigError):
                self.rules(change)
        with self.assertRaises(ConfigError):
            self.rules(batch_size=51)
        self.assertIsNone(self.rules(lambda product: product.pop("beta_recruiting")))

    def test_the_batch_size_is_a_whole_number_from_1(self):
        self.assertEqual(settings.load_batch_size({"batch_size": 5}), 5)
        for value in (0, -1, True, "10", None, 2.5):
            with self.assertRaises(ConfigError):
                settings.load_batch_size({"batch_size": value})


class DraftTest(TempCase):
    def setUp(self):
        super().setUp()
        self.context = self.plan()[0].context

    def verdict(self, old="", new="", name="invitation-clean", purpose=beta_drafts.INVITATION):
        draft = beta_drafts.parse(fakes.beta_draft(name, old, new), "drafts/beta-recruiting/RepToday/invitation.md")
        return draft, beta_drafts.evaluate(draft, self.context, purpose)

    def rules(self, verdict):
        return sorted({finding.rule for finding in verdict.blocks})

    def test_the_clean_invitation_passes_and_its_citations_are_read(self):
        draft, verdict = self.verdict()
        self.assertEqual(self.rules(verdict), [])
        self.assertEqual(draft.subject, "Your Rep Today beta invitation")
        self.assertEqual([citation.line for citation in draft.citations], [12, 7])
        self.assertTrue(draft.message.startswith("You asked to try Rep Today"))

    def test_an_address_anywhere_in_the_file_blocks_it_and_no_finding_quotes_the_draft(self):
        for old, new in (
            ("Reply to this message", f"Write to {fakes.ADDRESS}"),
            ("# Beta invitation", f"# For {fakes.ADDRESS}"),
            ("Your Rep Today beta invitation", "Reply to beta@reptoday.app"),
            ('- Quote: "record', f'- Quote: "{fakes.ADDRESS} record'),
            ("draft: message", f"draft: message\nto: {fakes.ADDRESS}"),
        ):
            draft, verdict = self.verdict(old, new)
            self.assertTrue(draft.holds_address, new)
            self.assertEqual(self.rules(verdict), ["no-address"])
            told = json.dumps([finding.__dict__ for finding in verdict.blocks])
            for part in ("jane", "example.com", "reptoday.app", "@"):
                self.assertNotIn(part, told)
            self.assertEqual((draft.subject, draft.message, draft.citations), ("", "", []))

    def test_a_link_of_any_kind_blocks_it(self):
        for link in (
            "https://testflight.apple.com/join/abc",
            "testflight.apple.com/join/abc",
            "www.reptoday.app",
            "reptoday.app",
            "Reptoday.App/network",
        ):
            _, verdict = self.verdict("Reply to this message", f"Open {link} and reply to this message")
            self.assertIn("no-link", self.rules(verdict), link)
        for plain in ("e.g. tonight", "i.e. once", "at 7 p.m. or so", "the U.S. build"):
            _, verdict = self.verdict("Reply to this message", f"Reply to this message, {plain},")
            self.assertNotIn("no-link", self.rules(verdict), plain)

    def test_every_figure_must_be_in_a_cited_line_whether_in_digits_or_as_a_word(self):
        for sentence in (
            "Only 20 places are open.",
            "There are twenty places.",
            "We are asking 1,000 people.",
            "It closes in 3 days.",
            "A dozen places remain.",
        ):
            _, verdict = self.verdict("Nothing is asked of you beforehand.", sentence)
            self.assertIn("unbacked-number", self.rules(verdict), sentence)
        _, verdict = self.verdict("a 30-minute video call", "a thirty-minute video call")
        self.assertEqual(self.rules(verdict), [])
        _, verdict = self.verdict("a 30-minute video call", "a 45-minute video call")
        self.assertEqual(self.rules(verdict), ["unbacked-number"])
        self.assertEqual(beta_drafts.numbers("Only 1,000 or twenty-five, not one."), ["1000", "20", "5"])

    def test_an_invitation_explains_the_recorded_session_and_cites_k8(self):
        _, verdict = self.verdict(name="invitation-not-recorded")
        self.assertEqual(self.rules(verdict), ["session-recorded"])
        _, verdict = self.verdict(name="invitation-no-length")
        self.assertEqual(self.rules(verdict), ["session-length"])
        _, verdict = self.verdict(name="invitation-no-k8")
        self.assertEqual(self.rules(verdict), ["k8-citation"])
        _, verdict = self.verdict(name="waitlist-ask-clean", purpose=beta_drafts.WAITLIST_ASK)
        self.assertEqual(self.rules(verdict), [])

    def test_a_citation_is_checked_against_the_line_in_mandu(self):
        for old, new, problem in (
            ("line 12", "line 11", "does not hold the quote"),
            ("line 12", "line 400", "has no line 400"),
            ("07-thesis/investment-thesis.md", "07-thesis/missing.md", "is not a file in Mandu"),
            ("projects/RepToday/gtm/07-thesis/investment-thesis.md", "../../etc/passwd", "is not a path inside Mandu"),
            ("projects/RepToday/gtm/07-thesis/investment-thesis.md", "/etc/passwd", "is not a path inside Mandu"),
            (
                "gtm/07-thesis/investment-thesis.md",
                "gtm/05-social-pmf/angles.md",
                "is not a package file this workflow reads",
            ),
            (
                '"record moderated first-run sessions before any public launch"',
                '"record moderated"',
                "must be 4 words or more",
            ),
        ):
            _, verdict = self.verdict(old, new)
            self.assertIn("source-quote", self.rules(verdict), new)
            self.assertIn(problem, " | ".join(finding.detail for finding in verdict.blocks))

    def test_the_format_is_checked_before_anything_else(self):
        for old, new, problem in (
            ("draft: message", "draft: post", "front matter needs draft: message"),
            ("purpose: beta-invitation", "purpose: newsletter", "front matter needs purpose"),
            ("## Subject", "## Title", "the Draft holds exactly these sections"),
            ("Your Rep Today beta invitation", "Your invitation\nand more", "## Subject holds the subject on one line"),
            ("# Beta invitation\n", "", "exactly one # title line"),
            (
                "  File: `projects/RepToday/gtm/06-channels/channel-plan.md` line 7",
                "  File: somewhere",
                "each source is",
            ),
        ):
            _, verdict = self.verdict(old, new)
            self.assertEqual(self.rules(verdict), ["format"], new)
            self.assertIn(problem, " | ".join(finding.detail for finding in verdict.blocks))
        _, verdict = self.verdict("purpose: beta-invitation", "purpose: waitlist-ask")
        self.assertIn("so its front matter says purpose: beta-invitation", verdict.blocks[0].detail)
        _, verdict = self.verdict("product: RepToday", "product: Immerse")
        self.assertIn("the Product recruiting its Beta Cohort is RepToday", verdict.blocks[0].detail)

    def test_the_brand_lint_reads_the_subject_and_the_message_from_mandu_s_rules_alone(self):
        _, verdict = self.verdict("Your Rep Today beta invitation", "Will you try Rep Today")
        self.assertEqual(self.rules(verdict), [])
        _, verdict = self.verdict("Your Rep Today beta invitation", "Will you try Rep Today?")
        self.assertEqual([(f.rule, f.field) for f in verdict.blocks], [("hook_must_not_be_question", "subject")])
        _, verdict = self.verdict(name="invitation-fake-scarcity")
        self.assertEqual(self.rules(verdict), ["fake_scarcity"])
        context = dataclasses.replace(self.context, rules=None, rules_problem="No such file or directory")
        draft = beta_drafts.parse(fakes.beta_draft(), "invitation.md")
        verdict = beta_drafts.evaluate(draft, context, beta_drafts.INVITATION)
        self.assertEqual(self.rules(verdict), ["brand-rules.json"])


class DecideTest(TempCase):
    def test_nothing_exists_before_the_gate(self):
        plan, store, _ = self.plan(beta_build=None)
        self.assertFalse(plan.active)
        self.assertIsNone(plan.batch)
        self.assertEqual((plan.drafts, plan.held, plan.pool, plan.gap), ([], {}, 0, None))
        self.assertEqual(list(store.root.rglob("*")), [])
        self.assertEqual(beta.brief_lines(plan, Path("/repo")), [])
        rows = beta.source_lines(plan)
        self.assertEqual([row[:2] for row in rows], [(beta.GATE_SOURCE, "skipped"), (beta.REPORT_SOURCE, "skipped")])
        self.assertEqual(rows[1][2], "not read: Beta Cohort recruiting has not started")

    def test_the_first_batch_takes_the_next_entries_in_order_up_to_the_batch_size(self):
        plan, _, _ = self.plan(batch_size=3)
        self.assertEqual((plan.batch.action, plan.batch.number), (beta.NEW, 1))
        self.assertEqual(plan.batch.entries, fakes.GOOD_FIT_OPT_INS[:3])
        self.assertEqual((plan.pool, plan.gap), (8, 12))
        self.assertEqual([due.purpose for due in plan.drafts], ["beta-invitation", "waitlist-ask"])
        self.assertIn("8 sign-ups asked for a beta invitation in all", beta.gap_line(plan))

    def test_an_approved_entry_is_never_offered_again_and_a_rejected_one_is_free(self):
        first = fakes.GOOD_FIT_OPT_INS[:2]
        plan, _, _ = self.plan(batch_size=2, batches=[batch(1, "approved", first)])
        self.assertEqual((plan.batch.number, plan.batch.entries), (2, fakes.GOOD_FIT_OPT_INS[2:4]))
        self.assertEqual(beta.invited(plan.held), sorted(first))
        plan, _, _ = self.plan(batch_size=2, batches=[batch(1, "rejected", first)])
        self.assertEqual((plan.batch.number, plan.batch.entries), (1, first))
        withdrawn = batch(1, "superseded", first, withdrawn=True)
        plan, _, _ = self.plan(batch_size=2, batches=[withdrawn])
        self.assertEqual((plan.batch.number, plan.batch.entries), (1, first))
        decided_late = batch(1, "superseded", first, decided="approved")
        plan, _, _ = self.plan(batch_size=2, batches=[decided_late])
        self.assertEqual((plan.batch.number, plan.batch.entries), (2, fakes.GOOD_FIT_OPT_INS[2:4]))

    def test_one_batch_is_open_at_a_time(self):
        first = fakes.GOOD_FIT_OPT_INS[:2]
        plan, _, _ = self.plan(batch_size=2, batches=[batch(1, "open", first)])
        self.assertEqual((plan.batch.action, plan.batch.number, plan.batch.entries), (beta.KEEP, 1, first))
        self.assertEqual(plan.pool, 6)

    def test_an_entry_that_left_the_waitlist_or_its_opt_in_leaves_the_open_batch(self):
        gone = batch(1, "open", ["Qm7tLx2a", "Gone0000"])
        plan, _, _ = self.plan(batch_size=2, batches=[gone])
        self.assertEqual((plan.batch.action, plan.batch.entries), (beta.REBUILD, ["Qm7tLx2a", "Ka0zMn2p"]))
        opted_out = [
            entry if entry[0] != "Ka0zMn2p" else (*entry[:3], False, entry[4]) for entry in fakes.WAITLIST_ENTRIES
        ]
        plan, _, _ = self.plan(
            fakes.waitlist_view(entries=opted_out), batch_size=2, batches=[batch(1, "open", ["Qm7tLx2a", "Ka0zMn2p"])]
        )
        self.assertEqual((plan.batch.action, plan.batch.entries), (beta.REBUILD, ["Qm7tLx2a", "Xf9mKa3i"]))
        nobody = fakes.waitlist_view(entries=[entry for entry in fakes.WAITLIST_ENTRIES if not entry[3]])
        plan, _, _ = self.plan(nobody, batch_size=2, batches=[batch(1, "open", ["Qm7tLx2a", "Ka0zMn2p"])])
        self.assertEqual((plan.batch.action, plan.batch.stale, plan.batch.ended), (beta.NONE, True, False))

    def test_an_offered_entry_that_left_no_longer_counts_toward_the_cohort_and_an_invited_one_still_does(self):
        opted_out = fakes.waitlist_view(
            entries=[e if e[0] != "Ka0zMn2p" else (*e[:3], False, e[4]) for e in fakes.WAITLIST_ENTRIES]
        )
        plan, _, _ = self.plan(opted_out, batch_size=2, batches=[batch(1, "open", ["Qm7tLx2a", "Ka0zMn2p"])])
        self.assertEqual(plan.gap, 13)
        self.assertIn("7 sign-ups asked for a beta invitation in all", beta.gap_line(plan))
        plan, _, _ = self.plan(batch_size=2, batches=[batch(1, "open", ["Qm7tLx2a", "Gone0000"])])
        self.assertEqual(plan.gap, 12)
        plan, _, _ = self.plan(opted_out, batch_size=2, batches=[batch(1, "approved", ["Qm7tLx2a", "Ka0zMn2p"])])
        self.assertEqual(plan.gap, 12)
        nobody = fakes.waitlist_view(entries=[entry for entry in fakes.WAITLIST_ENTRIES if not entry[3]])
        plan, _, _ = self.plan(nobody, batch_size=2, batches=[batch(1, "open", ["Qm7tLx2a", "Ka0zMn2p"])])
        self.assertEqual(plan.gap, 20)

    def test_an_open_item_that_cannot_stand_is_not_recorded_as_standing_for_check_beta_drafts(self):
        def recorded(plan):
            return {due["purpose"]: due["open"] for due in beta.plan_record(plan, _Areas(self.root))["drafts"]}

        first = batch(1, "open", fakes.GOOD_FIT_OPT_INS[:2])
        ask = batch(9, "open", [], beta="waitlist-ask", gap=12)
        plan, _, _ = self.plan(batch_size=2, batches=[first, ask])
        standing = {"draft_sha256": "0" * 64}
        self.assertEqual(
            recorded(plan),
            {"beta-invitation": dict(standing, id=first["id"]), "waitlist-ask": dict(standing, id=ask["id"])},
        )
        gone = batch(1, "open", ["Qm7tLx2a", "Gone0000"])
        plan, _, _ = self.plan(batch_size=2, batches=[gone, dict(ask, gap=10)])
        self.assertEqual(recorded(plan), {"beta-invitation": None, "waitlist-ask": None})

    def test_recruiting_ends_at_the_founder_s_stop_or_once_the_cohort_reaches_its_maximum(self):
        stopped = dict(fakes.BETA_BUILD, recruiting="stopped", stopped_on="2026-10-10")
        plan, _, _ = self.plan(beta_build=stopped, batches=[batch(1, "open", ["Qm7tLx2a"])])
        self.assertEqual((plan.batch.action, plan.batch.ended), (beta.NONE, True))
        self.assertEqual(plan.batch.why, "the Founder stopped recruiting on 2026-10-10")
        self.assertEqual((plan.drafts, plan.gap), ([], None))
        full = [fakes.beta_report("2026-10-04", accepted=50)]
        plan, _, _ = self.plan(reports=full)
        self.assertTrue(plan.batch.ended)
        self.assertIn("the Beta Cohort reached 50 people: 50 accepted", plan.batch.why)
        within = [fakes.beta_report("2026-10-04", accepted=20)]
        plan, _, _ = self.plan(reports=within)
        self.assertEqual((plan.batch.action, plan.gap), (beta.NEW, 0))
        self.assertIn("which is within it. Recruiting goes on until it reaches 50", beta.cohort_line(plan))

    def test_the_room_left_in_the_cohort_caps_the_batch(self):
        many = [(f"Entry{n:03d}", "tiktok", "lost-the-routine", True, "2026-10-05") for n in range(70)]
        view = fakes.waitlist_view(entries=many)
        plan, _, _ = self.plan(view, reports=[fakes.beta_report("2026-10-04", accepted=46)])
        self.assertEqual(len(plan.batch.entries), 4)
        self.assertEqual(plan.gap, 0)

    def test_an_unreported_cohort_is_never_counted_as_empty(self):
        """Fifty entries approved and no count of who accepted: the cohort may be full, so no batch is offered."""
        many = [(f"Entry{n:03d}", "tiktok", "lost-the-routine", True, "2026-10-05") for n in range(70)]
        view = fakes.waitlist_view(entries=many)
        approved = [batch(n + 1, "approved", [entry[0] for entry in many[n * 10 : n * 10 + 10]]) for n in range(5)]
        plan, _, _ = self.plan(view, batches=approved)
        self.assertEqual(plan.batch.action, beta.NONE)
        self.assertIn(
            "the Founder has not reported how many accepted, so the cohort may already hold 50", plan.batch.why
        )
        self.assertFalse(plan.batch.ended)
        plan, _, _ = self.plan(view, batches=approved[:4])
        self.assertEqual((plan.batch.action, plan.batch.number, len(plan.batch.entries)), (beta.NEW, 5, 10))
        plan, _, _ = self.plan(view, batches=approved, reports=[fakes.beta_report("2026-10-04", accepted=12)])
        self.assertEqual((plan.batch.action, len(plan.batch.entries)), (beta.NEW, 20))

    def test_no_entry_is_chosen_without_a_usable_view(self):
        plan, _, _ = self.plan({"view": 1})
        self.assertEqual((plan.batch.action, plan.gap, plan.drafts), (beta.NONE, None, []))
        self.assertIn("could not be used this run", plan.batch.why)
        plan, _, _ = self.plan(fakes.address_variant(), batches=[batch(1, "open", ["Qm7tLx2a"])])
        self.assertEqual((plan.batch.action, plan.batch.stale, plan.batch.open["batch"]), (beta.NONE, False, 1))

    def test_everyone_offered_leaves_no_batch(self):
        everyone = fakes.GOOD_FIT_OPT_INS + fakes.OTHER_OPT_INS
        plan, _, _ = self.plan(batches=[batch(1, "approved", everyone)])
        self.assertEqual(plan.batch.action, beta.NONE)
        self.assertEqual(plan.batch.why, "every sign-up that asked for a beta invitation has been offered one")
        self.assertEqual((plan.gap, [due.purpose for due in plan.drafts]), (12, ["waitlist-ask"]))


class StateTest(TempCase):
    def test_the_review_queue_is_the_record_and_the_state_a_copy(self):
        first = fakes.GOOD_FIT_OPT_INS[:2]
        ledger = Ledger(
            [fakes.batch_entry(batch(1, "approved", first)), fakes.batch_entry(batch(2, "open", ["Xf9mKa3i"]))]
        )
        held, notes = beta.held_entries(state.BetaRecruitingState(), ledger.entries, "RepToday")
        self.assertEqual(notes, [])
        self.assertEqual(
            {key: value["status"] for key, value in held.items()},
            {"Qm7tLx2a": "invited", "Ka0zMn2p": "invited", "Xf9mKa3i": "offered"},
        )
        saved = state.BetaRecruitingState.from_json(state.BetaRecruitingState(held, "a" * 64).as_json())
        self.assertEqual((saved.entries, saved.build), (held, "a" * 64))

    def test_the_review_queue_alone_says_who_is_invited_and_the_state_s_disagreement_is_noted(self):
        item = "20261004-beta-invitation-batch-01"
        previous = state.BetaRecruitingState({"Qm7tLx2a": {"status": "invited", "item": item}})
        approved = Ledger([fakes.batch_entry(batch(1, "approved", ["Qm7tLx2a"]))])
        held, notes = beta.held_entries(previous, approved.entries, "RepToday")
        self.assertEqual((held, notes), ({"Qm7tLx2a": {"status": "invited", "item": item}}, []))
        rejected = Ledger([fakes.batch_entry(batch(1, "rejected", ["Qm7tLx2a"]))])
        held, notes = beta.held_entries(previous, rejected.entries, "RepToday")
        self.assertEqual(held, {})
        self.assertEqual(
            notes, [f"state had `Qm7tLx2a` invited under `{item}`; the Review Queue has that item rejected"]
        )
        held, notes = beta.held_entries(previous, {}, "RepToday")
        self.assertEqual(held, {})
        self.assertEqual(
            notes, [f"state had `Qm7tLx2a` invited under `{item}`; the Review Queue does not hold that item"]
        )
        offered = state.BetaRecruitingState({"Qm7tLx2a": {"status": "offered", "item": item}})
        self.assertEqual(beta.held_entries(offered, {}, "RepToday"), ({}, []))

    def test_the_state_holds_identifiers_and_hashes_only(self):
        for data in (
            {"entries": {"jane@example.com": {"status": "invited", "item": "20261004-a"}}},
            {"entries": {"amFuZUBleGFtcGxlLmNvbQ": {"status": "invited", "item": "20261004-a"}}},
            {"entries": {"Qm7tLx2a": {"status": "maybe", "item": "20261004-a"}}},
            {"entries": {"Qm7tLx2a": {"status": "invited", "item": "nope"}}},
            {"entries": {"Qm7tLx2a": "invited"}},
            {"build": "not a hash"},
        ):
            with self.assertRaises(state.StateError):
                state.BetaRecruitingState.from_json(data)
        self.assertTrue(state.BetaRecruitingState().unused)
        self.assertFalse(state.BetaRecruitingState(build="a" * 64).unused)


class StandingTest(unittest.TestCase):
    def standing(self, *queued):
        entries = Ledger([fakes.batch_entry(entry) for entry in queued]).entries
        return beta.draft_standing(beta.draft_plan(beta_drafts.INVITATION, Path("/w"), entries, "RepToday"))

    def test_the_agent_is_told_the_founder_s_latest_decision_not_an_earlier_one(self):
        rejected = batch(1, "rejected", ["Qm7tLx2a"], reason="Too formal.")
        approved = batch(1, "approved", ["Qm7tLx2a"], on="2026-10-11", note="Good.")
        later = batch(2, "rejected", ["Ka0zMn2p"], on="2026-10-18", reason="Not this week.")
        self.assertEqual(self.standing(), "nothing yet")
        self.assertEqual(self.standing(rejected), f"rejected as `{rejected['id']}`: Too formal.")
        self.assertEqual(
            self.standing(rejected, approved),
            f"approved as `{approved['id']}`; rewrite the Draft only if there is a reason to. Note: Good.",
        )
        self.assertEqual(self.standing(rejected, approved, later), f"rejected as `{later['id']}`: Not this week.")
        waiting = batch(2, "open", ["Ka0zMn2p"], on="2026-10-18")
        self.assertIn(f"open as `{waiting['id']}`", self.standing(rejected, approved, waiting))


class ItemTest(TempCase):
    def item(self, name="invitation-clean", purpose=beta_drafts.INVITATION, **scenario):
        plan, _, _ = self.plan(**scenario)
        draft = beta_drafts.parse(
            fakes.beta_draft(name), f"drafts/beta-recruiting/RepToday/{beta.DRAFT_FILES[purpose]}"
        )
        verdict, item = beta.check_draft(plan, plan.due(purpose), draft, ["RepToday", "Immerse"])
        self.assertEqual(verdict.blocks, [])
        return plan, item

    def test_the_invitation_item_carries_the_batch_the_rule_and_no_address_or_link(self):
        plan, item = self.item(batch_size=6)
        self.assertEqual(item.ask, "Approve Beta Cohort invitation, batch 1: 6 Waitlist entries")
        self.assertEqual(item.fields, {"kind": "message", "product": "RepToday"})
        text = exchange.render_item(
            dict(item.fields, exchange="4", id="20261011-x"), item.ask, item.body, item.touches, item.evidence
        )
        self.assertEqual(exchange.check_item(text, ["RepToday", "Immerse"], published=True).problems, [])
        for line in (
            "- Good Fit, asked for a beta invitation (5): `Qm7tLx2a`, `Ka0zMn2p`, `Xf9mKa3i`, `Jd2wGs6u`, `Lr6jFq5s`",
            "- Asked for a beta invitation, with another Fit answer or none (1): `Ne5qTb1o`",
            f"{waitlist.SELECTION_RULE} No entry is offered twice.",
            "You resolve each entry identifier to its address on your side and send; gr0wthlab holds no address and"
            " sends nothing.",
            "by a TestFlight public link or by individual email invitation: add what your route needs when you send.",
            "> That first look is a 30-minute video call.",
            "**Where recruiting stood when run `20261011T230000Z-on-demand-0000` queued this item**",
            "- The Founder's counts, none reported yet: invitations sent not reported, accepted not reported, sessions"
            " booked not reported.",
            "- The pool is too small to reach 20: 8 sign-ups asked for a beta invitation in all, so even if every one"
            " accepted, the Beta Cohort would be 12 short of 20.",
            '- "record moderated first-run sessions before any public launch":'
            " `projects/RepToday/gtm/07-thesis/investment-thesis.md` line 12",
            "A count you leave out is recorded as not reported, never as zero.",
        ):
            self.assertIn(line, text)
        self.assertFalse(waitlist.looks_like_address(text))
        self.assertIsNone(beta_drafts.LINK.search(item.body.split("**Candidates")[0].split("**Subject**")[1]))
        for kept in ("tiktok", "youtube", "reddit", "network", "lost-the-routine", "2026-09-29"):
            self.assertNotIn(kept, text)

    def test_the_waitlist_ask_item_states_the_gap(self):
        _, item = self.item("waitlist-ask-clean", beta_drafts.WAITLIST_ASK)
        self.assertEqual(item.ask, "Approve Waitlist ask: the pool is 12 short of a 20-person Beta Cohort")
        self.assertIn("so even if every one accepted, the Beta Cohort would be 12 short of 20.", item.body)
        self.assertIn("it carries no link and no address, so add the Waitlist link for the channel you use", item.body)
        self.assertNotIn("Qm7tLx2a", item.body)

    def test_what_the_agent_is_told_names_no_entry(self):
        plan, _, _ = self.plan()
        told = "\n".join(beta.brief_lines(plan, Path("/repo")))
        self.assertIn("## Beta Cohort recruiting", told)
        self.assertIn("check-beta-drafts --run 20261011T230000Z-on-demand-0000", told)
        record = json.dumps(beta.plan_record(plan, _Areas(self.root)))
        for entry in fakes.WAITLIST_ENTRIES:
            self.assertNotIn(entry[0], told + record)
        for kept in ("tiktok", "lost-the-routine", "12 short", " 8 "):
            self.assertNotIn(kept, told + record)


class _Areas:
    """Stands in for Areas where only a workspace-relative path is needed."""

    def __init__(self, root):
        self.root = root

    def relative(self, path):
        return "/".join(Path(path).parts[-4:])


if __name__ == "__main__":
    unittest.main()
