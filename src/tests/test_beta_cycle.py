"""Whole runs of Beta Cohort recruiting with a fake Codex: US-ME15's Validation Test, and what follows it week by
week, on the seeded anonymous view and a throwaway Mandu."""

import io
import json
import os
from datetime import timedelta
from unittest import mock

from gr0wthlab import beta, cli, cycle, exchange, waitlist
from tests import fakes
from tests.test_cycle import CycleTestCase

WEEK = timedelta(days=7)
PRODUCTS = ["RepToday", "Immerse"]


class BetaCycleTestCase(CycleTestCase):
    def setUp(self):
        super().setUp()
        fakes.beta_mandu(self.mandu)
        self.view = self.root / "RepToday-exports" / "waitlist-view.json"
        self.env["GR0WTHLAB_WAITLIST_VIEW"] = str(self.view)
        fakes.write_view(self.view, fakes.waitlist_view())
        self.exchange.mkdir()
        self.week = 0

    def approve_build(self, **changes):
        return fakes.write_record(self.exchange / beta.BUILDS, "RepToday.json", dict(fakes.BETA_BUILD, **changes))

    def report_counts(self, day, **counts):
        record = fakes.beta_report(day, **counts)
        return fakes.write_record(self.exchange / beta.REPORTS, f"RepToday-{day}.json", record)

    def write(self, **drafts):
        """What the agent writes this run: invitation and ask are Draft texts."""
        paths = {"invitation": fakes.INVITATION, "ask": fakes.WAITLIST_ASK}
        fakes.behave(self.codex_dir, {"write": {paths[key]: text for key, text in drafts.items()}})

    def next_week(self):
        """The following Sunday's run, with a view generated an hour before it."""
        self.week += 1
        at = fakes.SUNDAY_RUN + self.week * WEEK
        view = json.loads(self.view.read_text(encoding="utf-8"))
        view["generated_at"] = (at - timedelta(hours=1)).isoformat()
        fakes.write_view(self.view, view)
        code, out = self.run_cycle(at=at)
        self.assertEqual(code, 0, out)

    def messages(self, status="open"):
        return [entry for entry in self.queue()[status] if entry["kind"] == "message"]

    def invitation(self):
        return next(entry for entry in self.messages() if entry["beta"] == "beta-invitation")

    def evidence(self):
        records = sorted((self.ledger() / "evidence/beta-recruiting").glob("*.json"))
        return json.loads(records[-1].read_text(encoding="utf-8")) if records else None

    def recruiting_state(self):
        path = self.ledger() / "run-reports/state/beta-recruiting.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def assert_no_address_anywhere(self, *parts):
        """Every output of every run so far: the records, the agent's areas, the logs, and what the agent was told."""
        for place in (self.ledger(), self.workspace(), self.logs, self.codex_dir):
            for path in place.rglob("*"):
                if path.is_file() and path.name != "behavior.json":
                    data = path.read_bytes()
                    for part in (fakes.ADDRESS, "jane", "example.com", *parts):
                        self.assertNotIn(part.encode(), data, path)
                    if path.suffix in (".md", ".json") and place != self.codex_dir:
                        self.assertFalse(waitlist.looks_like_address(data.decode("utf-8")), path)


class ValidationTest(BetaCycleTestCase):
    """US-ME15's Validation Test: a run before the approval, then the approval, then a run."""

    def test_nothing_happens_before_the_approval_then_a_batch_and_an_invitation_without_addresses(self):
        # Step 1: before the approval. Even Drafts the agent wrote unasked are never read.
        self.write(invitation=fakes.beta_draft(), ask=fakes.beta_draft("waitlist-ask-clean"))
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        ledger = self.ledger()
        self.assertFalse((ledger / "evidence/beta-recruiting").exists())
        self.assertIsNone(self.recruiting_state())
        self.assertEqual(list((ledger / "run-reports").glob("*.beta-plan.json")), [])
        self.assertEqual(self.messages(), [])
        brief = self.brief()
        prompt = (self.codex_dir / "prompt.txt").read_text(encoding="utf-8")
        self.assertNotIn("Beta", brief)
        self.assertNotIn("recruiting", brief)
        # The fixed task definition names the pass; nothing this run added to the prompt does.
        self.assertNotIn("check-beta-drafts --run", prompt)
        self.assertNotIn("beta-plan", prompt)
        report = self.report()
        for line in (
            "| Beta Build approval in Mandu | skipped | not recorded: the Founder has recorded no approved Beta Build"
            " for RepToday in Mandu, so Beta Cohort recruiting has not started |",
            "| Beta Cohort reports in Mandu | skipped | not read: Beta Cohort recruiting has not started |",
            "| Beta Cohort recruiting | skipped | the Founder has recorded no approved Beta Build in Mandu |",
            "- beta-recruiting: checked=0 acted=0 note=not started: no Beta Build approval is recorded in Mandu",
        ):
            self.assertIn(line, report)
        self.assertNotIn("## Beta Cohort recruiting", report)
        self.assertNotIn("Beta Cohort recruiting:", report.split("## Sources")[0])
        self.assertEqual(self.queue()["open"], [])

        # Step 2: the Founder records the approval, and the next run recruits.
        self.approve_build()
        self.next_week()
        invitation, ask = self.messages()
        self.assertEqual(invitation["ask"], "Approve Beta Cohort invitation, batch 1: 8 Waitlist entries")
        self.assertEqual(invitation["candidates"], fakes.GOOD_FIT_OPT_INS + fakes.OTHER_OPT_INS)
        self.assertEqual((invitation["beta"], invitation["batch"]), ("beta-invitation", 1))
        self.assertEqual(ask["ask"], "Approve Waitlist ask: the pool is 12 short of a 20-person Beta Cohort")
        text = (ledger / invitation["file"]).read_text(encoding="utf-8")
        self.assertEqual(exchange.check_item(text, PRODUCTS, published=True).problems, [])
        self.assertIn("- Good Fit, asked for a beta invitation (5): `Qm7tLx2a`, `Ka0zMn2p`, `Xf9mKa3i`,", text)
        self.assertIn("- Asked for a beta invitation, with another Fit answer or none (3): `Ne5qTb1o`,", text)
        self.assertIn("> That first look is a 30-minute video call.", text)
        for never in ("Vb3kPz9w", "Ug4vWc7y", "Ps1hDe8t", "Yt3bHv9r"):  # the sign-ups that did not ask
            self.assertNotIn(never, text)

        record = self.evidence()
        self.assertEqual(record["batch"]["candidates"], invitation["candidates"])
        self.assertEqual((record["batch"]["action"], record["batch"]["good_fit"]), ("new", 5))
        self.assertEqual(record["beta_build"]["approved_on"], "2026-10-09")
        self.assertEqual(record["beta_build"]["source"]["path"], str(self.exchange / "beta-builds/RepToday.json"))
        self.assertEqual(record["founder_counts"]["not_reported"], list(exchange.BETA_COUNTS))
        self.assertEqual(record["pool"], {"not_offered_yet": 0, "gap": 12})
        self.assertEqual((record["invited"], sorted(record["offered"])), ([], sorted(invitation["candidates"])))
        self.assertEqual(record["selection_rule"], waitlist.SELECTION_RULE)
        self.assertEqual([draft["status"] for draft in record["drafts"]], ["queued", "queued"])
        saved = self.recruiting_state()
        self.assertEqual(sorted(saved["entries"]), sorted(invitation["candidates"]))
        self.assertEqual({entry["status"] for entry in saved["entries"].values()}, {"offered"})

        report = self.report()
        for line in (
            "| Beta Build approval in Mandu | changed | approved on 2026-10-09, build 1.0 (42), recorded"
            " 2026-10-10T19:40:00-07:00; recruiting is open |",
            "| Beta Cohort reports in Mandu | read | 0 records, 0 new |",
            f"- Beta Cohort recruiting: batch 1 queued as `{invitation['id']}`: 8 entries (5 good Fit, 3 with another"
            " Fit answer or none); the pool is too small to reach 20: 8 sign-ups asked for a beta invitation in all,"
            " so even if every one accepted, the Beta Cohort would be 12 short of 20.",
            "- The Founder's counts, none reported yet: invitations sent not reported, accepted not reported, sessions"
            " booked not reported.",
            f"| Beta invitation | queued | `{invitation['id']}` |",
            f"| Waitlist ask | queued | `{ask['id']}` |",
        ):
            self.assertIn(line, report)
        self.assertIn("| Beta Cohort recruiting | complete | batch 1 queued as", report)
        self.assertRegex(report, r"- beta-recruiting: checked=8 acted=2 note=batch 1 queued as .*12 short of 20")

        # What the agent was told names nobody, and no address is anywhere in any output.
        brief = self.brief()
        self.assertIn("## Beta Cohort recruiting", brief)
        self.assertIn(
            f"| Beta invitation (`purpose: beta-invitation`) | `{self.workspace() / fakes.INVITATION}`", brief
        )
        prompt = (self.codex_dir / "prompt.txt").read_text(encoding="utf-8")
        plan = next((ledger / "run-reports").glob("*.beta-plan.json")).read_text(encoding="utf-8")
        for entry in fakes.WAITLIST_ENTRIES:
            self.assertNotIn(entry[0], brief.split("## Waitlist")[0] + brief.split("## Beta Cohort recruiting")[1])
            self.assertNotIn(entry[0], prompt + plan)
        self.assertNotIn(str(self.view), brief + prompt)
        self.assert_no_address_anywhere()

    def test_a_record_that_does_not_follow_its_format_is_not_an_approval(self):
        self.write(invitation=fakes.beta_draft())
        fakes.write_record(self.exchange / beta.BUILDS, "RepToday.json", dict(fakes.BETA_BUILD, recruiting="yes"))
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        report = self.report()
        self.assertIn(
            "| Beta Build approval in Mandu | failed | `beta-builds/RepToday.json` could not be used (recruiting must"
            " be 'open' or 'stopped'), so nothing shows an approval and recruiting has not started. |",
            report,
        )
        self.assertIn(
            "| Beta Cohort recruiting | incomplete | Beta Build approval in Mandu could not be read |", report
        )
        self.assertIn("note=not started: the Beta Build record in Mandu could not be used", report)
        self.assertFalse((self.ledger() / "evidence/beta-recruiting").exists())
        self.assertIsNone(self.recruiting_state())
        (notice,) = self.queue()["open"]
        self.assertEqual(notice["kind"], "notice")
        self.assertNotIn("Beta", self.brief())

    def test_a_record_holding_an_address_opens_nothing_and_is_never_repeated(self):
        self.write(invitation=fakes.beta_draft())
        self.approve_build(build=f"1.0, ask {fakes.ADDRESS}")
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        self.assertIn(
            "| Beta Build approval in Mandu | failed | `beta-builds/RepToday.json` could not be used (it holds"
            " something that looks like an email address",
            self.report(),
        )
        self.assertEqual(self.messages(), [])
        self.assert_no_address_anywhere()

    def test_an_approval_for_another_product_or_a_stray_file_opens_nothing(self):
        fakes.write_record(self.exchange / beta.BUILDS, "Immerse.json", dict(fakes.BETA_BUILD, product="Immerse"))
        fakes.write_record(self.exchange / beta.BUILDS, "RepToday.txt", json.dumps(fakes.BETA_BUILD))
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        self.assertIn(
            "| Beta Build approval in Mandu | skipped | not recorded: the Founder has recorded no approved Beta Build"
            " for RepToday in Mandu, so Beta Cohort recruiting has not started; `beta-builds/` holds `Immerse.json`,"
            " `RepToday.txt`, and only `RepToday.json` is RepToday's record |",
            self.report(),
        )
        self.assertFalse((self.ledger() / "evidence/beta-recruiting").exists())


class DraftChecksTest(BetaCycleTestCase):
    def setUp(self):
        super().setUp()
        self.approve_build()

    def test_an_address_in_a_draft_blocks_it_removes_the_file_and_reaches_no_record(self):
        self.write(invitation=fakes.beta_draft("invitation-address"), ask=fakes.beta_draft("waitlist-ask-clean"))
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        self.assertFalse((self.workspace() / fakes.INVITATION).exists())
        (ask,) = self.messages()
        self.assertEqual(ask["beta"], "waitlist-ask")
        report = self.report()
        self.assertIn(
            "| Beta invitation | blocked | 1 failing check, listed below; the Draft file was removed, since it held"
            " what looks like an email address |",
            report,
        )
        self.assertIn("- no-address: holds something that looks like an email address;", report)
        (notice,) = [entry for entry in self.queue()["open"] if entry["kind"] == "notice"]
        text = (self.ledger() / notice["file"]).read_text(encoding="utf-8")
        self.assertIn(
            f"- The Beta invitation Draft (`{fakes.INVITATION}`) was not offered: no-address:",
            text,
        )
        self.assertIn("- The launcher removed that Draft file, so nothing it held is kept or repeated here.", text)
        record = self.evidence()
        self.assertEqual((record["drafts"][0]["status"], record["drafts"][0]["removed"]), ("blocked", True))
        self.assertEqual(self.recruiting_state()["entries"], {})
        self.assert_no_address_anywhere("founder@")

    def test_an_invented_spot_count_blocks_it_naming_the_rule(self):
        self.write(invitation=fakes.beta_draft("invitation-spot-count"))
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.messages(), [])
        report = self.report()
        self.assertIn("- unbacked-number: states the figure 12, which no package line the Draft cites holds;", report)
        self.assertIn("- fake_scarcity: scarcity or urgency 'only {n} left' (message)", report)
        self.assertIn("- The Waitlist ask has no Draft, so it was not offered this run.", self.notice_text())
        self.assertIn("| Beta Cohort recruiting | incomplete | no Waitlist ask Draft |", report)
        self.assertTrue((self.workspace() / fakes.INVITATION).exists())

    def notice_text(self):
        (notice,) = [entry for entry in self.queue()["open"] if entry["kind"] == "notice"]
        return (self.ledger() / notice["file"]).read_text(encoding="utf-8")

    def test_a_draft_that_stops_passing_withdraws_its_open_invitation_and_frees_its_entries(self):
        self.write(invitation=fakes.beta_draft(), ask=fakes.beta_draft("waitlist-ask-clean"))
        self.next_week()
        invitation = self.invitation()
        self.write(invitation=fakes.beta_draft("invitation-link"))
        self.next_week()
        self.assertEqual([entry["beta"] for entry in self.messages()], ["waitlist-ask"])
        closed = {entry["id"]: entry for entry in self.queue()["closed"]}[invitation["id"]]
        self.assertTrue(closed["withdrawn"])
        self.assertIn(f"- The open `{invitation['id']}` is withdrawn, since it no longer stands.", self.notice_text())
        self.assertEqual(self.recruiting_state()["entries"], {})
        self.write(invitation=fakes.beta_draft())
        self.next_week()
        again = self.invitation()
        self.assertEqual((again["batch"], again["candidates"]), (1, invitation["candidates"]))

    def test_check_beta_drafts_gives_the_agent_the_launcher_s_verdict(self):
        self.write(invitation=fakes.beta_draft("invitation-spot-count"), ask=fakes.beta_draft("waitlist-ask-clean"))
        launch, seen = cycle.launcher.run, []

        def agent(*args, **kwargs):
            result = launch(*args, **kwargs)
            out = io.StringIO()
            with (
                mock.patch.object(cli, "REPO_ROOT", self.repo),
                mock.patch.object(cli, "LEDGER_DIR", self.repo / "ledger"),
                mock.patch.dict(os.environ, self.env),
            ):
                seen.append((cli.check_beta_drafts(kwargs["run_id"], out), out.getvalue()))
            return result

        with mock.patch.object(cycle.launcher, "run", agent):
            code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        code, text = seen[0]
        self.assertEqual(code, 1, text)
        self.assertIn("BLOCKED Beta invitation: drafts/beta-recruiting/RepToday/invitation.md", text)
        self.assertIn("  - unbacked-number: states the figure 12,", text)
        self.assertIn("OK Waitlist ask: drafts/beta-recruiting/RepToday/waitlist-ask.md", text)
        self.assertIn("2 Drafts due, 1 with problems", text)
        for entry in fakes.WAITLIST_ENTRIES:
            self.assertNotIn(entry[0], text)

    def test_check_beta_drafts_checks_nothing_without_the_run_s_recorded_plan(self):
        out = io.StringIO()
        with (
            mock.patch.object(cli, "REPO_ROOT", self.repo),
            mock.patch.object(cli, "LEDGER_DIR", self.repo / "ledger"),
            mock.patch.dict(os.environ, self.env),
        ):
            code = cli.check_beta_drafts("20261011T230001Z-on-demand-none", out)
        self.assertEqual(code, 1)
        self.assertIn("could not be read", out.getvalue())
        self.assertIn("so no Draft was checked", out.getvalue())


class WeekByWeekTest(BetaCycleTestCase):
    def setUp(self):
        super().setUp()
        self.approve_build()
        fakes.set_run(self.repo, "beta_recruiting", {"batch_size": 2})
        self.write(invitation=fakes.beta_draft(), ask=fakes.beta_draft("waitlist-ask-clean"))

    def test_nobody_is_invited_twice_and_the_next_batch_waits_for_the_founder_s_decision(self):
        self.next_week()
        first = self.invitation()
        self.assertEqual(first["candidates"], ["Qm7tLx2a", "Ka0zMn2p"])
        self.next_week()  # undecided: the same batch stands, and no second one is offered beside it
        self.assertEqual(self.invitation()["id"], first["id"])
        self.assertIn(f"| Beta invitation | kept | `{first['id']}`; its Draft is unchanged and passes |", self.report())
        self.decide(first["id"], "approve")
        self.next_week()
        second = self.invitation()
        self.assertEqual((second["batch"], second["candidates"]), (2, ["Xf9mKa3i", "Jd2wGs6u"]))
        saved = self.recruiting_state()["entries"]
        self.assertEqual(
            {key: value["status"] for key, value in saved.items()},
            {"Qm7tLx2a": "invited", "Ka0zMn2p": "invited", "Xf9mKa3i": "offered", "Jd2wGs6u": "offered"},
        )
        self.assertIn(
            "- Approved for invitation before this batch: 2 entries.", (self.ledger() / second["file"]).read_text()
        )
        self.assertIn(
            "2 entries approved for invitation, 2 offered and waiting for the Founder's decision, 4 sign-ups",
            self.report(),
        )
        self.decide(second["id"], "approve")
        for _ in range(2):
            self.next_week()
            self.decide(self.invitation()["id"], "approve")
        offered = [
            identifier
            for entry in self.queue()["closed"] + self.queue()["open"]
            for identifier in entry.get("candidates", [])
        ]
        self.assertEqual(sorted(offered), sorted(fakes.GOOD_FIT_OPT_INS + fakes.OTHER_OPT_INS))
        self.assertEqual(len(offered), len(set(offered)))
        self.next_week()
        self.assertIn("no batch: every sign-up that asked for a beta invitation has been offered one", self.report())

    def test_a_rejected_draft_is_not_asked_again_until_it_changes(self):
        self.next_week()
        first = self.invitation()
        self.decide(first["id"], "reject", reason="Too formal for people who asked to hear from me.")
        self.next_week()
        self.assertEqual([entry["beta"] for entry in self.messages()], ["waitlist-ask"])
        self.assertIn(
            f"| Beta invitation | not queued again | `{first['id']}`; the Founder rejected this Draft", self.report()
        )
        self.assertIn(f"rejected as `{first['id']}`: Too formal for people who asked to hear from me.", self.brief())
        self.assertEqual(self.recruiting_state()["entries"], {})
        self.write(invitation=fakes.beta_draft(old="and the beta is ready.", new="and it is ready for you."))
        self.next_week()
        again = self.invitation()
        self.assertEqual((again["batch"], again["candidates"]), (1, first["candidates"]))

    def test_a_changed_draft_replaces_the_open_invitation_with_the_same_entries(self):
        self.next_week()
        first = self.invitation()
        self.write(invitation=fakes.beta_draft(old="and the beta is ready.", new="and it is ready for you."))
        self.next_week()
        second = self.invitation()
        self.assertEqual((second["supersedes"], second["candidates"]), (first["id"], first["candidates"]))
        self.assertEqual(len([entry for entry in self.messages() if entry["beta"] == "beta-invitation"]), 1)
        self.assertIn(f"| Beta invitation | queued | `{second['id']}`; replaces `{first['id']}` |", self.report())

    def test_an_entry_that_leaves_the_waitlist_leaves_the_open_batch(self):
        self.next_week()
        first = self.invitation()
        fakes.write_view(
            self.view, fakes.waitlist_view(entries=[e for e in fakes.WAITLIST_ENTRIES if e[0] != "Ka0zMn2p"])
        )
        self.next_week()
        second = self.invitation()
        self.assertEqual((second["supersedes"], second["candidates"]), (first["id"], ["Qm7tLx2a", "Xf9mKa3i"]))
        self.assertNotIn("Ka0zMn2p", (self.ledger() / second["file"]).read_text(encoding="utf-8"))
        self.assertNotIn("Ka0zMn2p", self.recruiting_state()["entries"])

    def test_only_the_counts_the_founder_reports_are_kept_and_a_missing_one_is_not_reported(self):
        self.next_week()
        first = self.invitation()
        self.decide(first["id"], "approve")
        day = "2026-10-24"
        record = self.report_counts(day, invitations_sent=2, accepted=1)
        text = record.read_text(encoding="utf-8")
        record.write_text(text[:-1] + ', "who": "the two from the first batch"}', encoding="utf-8")
        self.next_week()
        kept = json.loads((self.ledger() / f"evidence/beta-recruiting/reports/RepToday-{day}.json").read_text())
        self.assertEqual(
            {key: kept[key] for key in ("invitations_sent", "accepted", "sessions_booked", "not_reported")},
            {"invitations_sent": 2, "accepted": 1, "sessions_booked": None, "not_reported": ["sessions_booked"]},
        )
        self.assertEqual(
            sorted(kept),
            sorted(
                [
                    "accepted",
                    "date",
                    "format",
                    "invitations_sent",
                    "not_reported",
                    "note",
                    "product",
                    "recorded_at",
                    "sessions_booked",
                    "source",
                    "taken_in_at",
                    "taken_in_by_run",
                ]
            ),
        )
        self.assertEqual(kept["source"]["path"], str(record))
        report = self.report()
        self.assertIn("| Beta Cohort reports in Mandu | changed | 1 record, 1 new |", report)
        self.assertIn(
            f"- The Founder's counts, as reported on {day}: invitations sent 2, accepted 1, sessions booked not"
            " reported.",
            report,
        )
        self.assertIn(
            f"- The Beta Cohort is 20 to 50 people: 1 accepted, as reported on {day}, 19 short of 20.", report
        )
        self.assertNotIn("sessions booked 0", report)
        self.assertEqual(self.evidence()["founder_counts"]["sessions_booked"], None)
        self.next_week()
        self.assertIn("| Beta Cohort reports in Mandu | read | 1 record, 0 new |", self.report())

    def test_a_report_that_cannot_be_used_fails_its_source_and_changes_no_count(self):
        self.next_week()
        self.report_counts("2026-10-24", accepted=1)
        fakes.write_record(self.exchange / beta.REPORTS, "RepToday-2026-10-31.json", f'{{"note": "{fakes.ADDRESS}"}}')
        self.next_week()
        report = self.report()
        self.assertIn(
            "| Beta Cohort reports in Mandu | failed | 2 records, 1 new; 1 could not be used:"
            " `beta-reports/RepToday-2026-10-31.json`: it holds something that looks like an email address",
            report,
        )
        self.assertIn("as reported on 2026-10-24: invitations sent not reported, accepted 1,", report)
        self.assertIn("| Beta Cohort recruiting | incomplete | Beta Cohort reports in Mandu could not be read", report)
        self.assert_no_address_anywhere()

    def test_the_founder_s_stop_ends_recruiting_and_withdraws_the_open_invitation(self):
        self.next_week()
        first, ask = self.invitation(), self.messages()[1]
        self.approve_build(recruiting="stopped", stopped_on="2026-10-20", recorded_at="2026-10-20T19:40:00-07:00")
        self.next_week()
        self.assertEqual(self.messages(), [])
        closed = {entry["id"]: entry for entry in self.queue()["closed"]}
        (notice,) = [entry for entry in self.queue()["open"] if entry["kind"] == "notice"]
        for item in (first, ask):
            self.assertEqual(
                (closed[item["id"]]["withdrawn"], closed[item["id"]]["superseded_by"]), (True, notice["id"])
            )
        text = (self.ledger() / notice["file"]).read_text(encoding="utf-8")
        self.assertIn(
            f"- The open `{first['id']}` is withdrawn: the Founder stopped recruiting on 2026-10-20. Its entries were"
            " not invited.",
            text,
        )
        self.assertIn(f"- The open `{ask['id']}` is withdrawn: the Founder stopped recruiting on 2026-10-20.\n", text)
        report = self.report()
        self.assertIn("- Beta Cohort recruiting: no batch: the Founder stopped recruiting on 2026-10-20.", report)
        self.assertIn("the Founder stopped recruiting on 2026-10-20 |", report.split("## Package changes")[0])
        self.assertNotIn("## Beta Cohort recruiting", self.brief())
        self.assertEqual(self.recruiting_state()["entries"], {})
        self.next_week()
        self.assertEqual(self.messages(), [])
        self.assertEqual([entry["id"] for entry in self.queue()["open"]], [notice["id"]])

    def test_recruiting_ends_once_the_founder_reports_the_cohort_full(self):
        self.next_week()
        self.decide(self.invitation()["id"], "approve")
        self.report_counts("2026-10-24", invitations_sent=60, accepted=50, sessions_booked=30)
        self.next_week()
        self.assertEqual([entry for entry in self.messages() if entry["beta"] == "beta-invitation"], [])
        self.assertIn(
            "no batch: the Beta Cohort reached 50 people: 50 accepted, as the Founder reported on 2026-10-24",
            self.report(),
        )

    def test_a_view_that_cannot_be_used_chooses_nobody_and_keeps_the_open_invitation(self):
        self.next_week()
        first = self.invitation()
        self.view.write_text("{not json", encoding="utf-8")
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + 2 * WEEK)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.invitation()["id"], first["id"])
        self.assertIn(
            "| Beta invitation | kept | `"
            + first["id"]
            + "`; the Waitlist's anonymous view could not be used this run",
            self.report(),
        )
        self.assertIn(
            "| Beta Cohort recruiting | incomplete | Waitlist anonymous view could not be read |", self.report()
        )

    def test_brand_rules_that_cannot_be_read_block_a_new_draft_and_keep_an_open_one(self):
        rules = self.mandu / "projects/RepToday/gtm/09-extras/marketing-agent/brand-rules.json"
        text = rules.read_text(encoding="utf-8")
        rules.write_text("{not json", encoding="utf-8")
        self.next_week()
        self.assertEqual(self.messages(), [])
        self.assertIn("- brand-rules.json: could not be used:", self.report())
        rules.write_text(text, encoding="utf-8")
        self.next_week()
        first = self.invitation()
        rules.write_text("{not json", encoding="utf-8")
        self.next_week()
        self.assertEqual(self.invitation()["id"], first["id"])
        self.assertIn(
            "not checked again, since brand-rules.json could not be used; the open item stands", self.report()
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
