"""What an approved Weekly Read decision changes in the package (weekly_changes.py): the one package-change proposal
an approved kill, change, resolved pair, or flex slot owes, filed at the next run with the exact edit, and nothing for
any other decision. Every package file here is the synthetic kit, and every number synthetic."""

import json
import re
import shutil
import unittest
from datetime import date, timedelta
from pathlib import Path

from gr0wthlab import exchange, kit, weekly_changes
from tests import fakes
from tests.test_cycle import CycleTestCase

KIT = fakes.EXAMPLES / "files" / "mandu"
GTM = "projects/RepToday/gtm/05-social-pmf"
ANGLES, PAIRS, CALENDAR, LOG = (
    f"{GTM}/angles.md",
    f"{GTM}/ab-pairs.md",
    f"{GTM}/cadence-14-day.md",
    f"{GTM}/creative-log.json",
)
EXAMPLES = fakes.REPO / "src" / "examples" / "weekly-read" / "files"
DAY_7_MEMO = (EXAMPLES / "memos" / "day-07-good.md").read_text(encoding="utf-8")
# The example set's day-14 numbers, read as the Founder gave them: P04 met its kill criterion at the day-14 read, as
# the day-7 read flagged it at risk, P07 is changed, AB-2 resolved with leg A leading, and AB-1 reposted.
DAY_14_MEMO = "\n".join(
    [
        "# Weekly Read, window 1, day 14",
        "",
        "## Angles",
        "",
        "- P01 (days 1 and 8): insufficient data. Day 8 is under the floor, so only day 1 is readable, too few posts"
        " to rank. What would settle it: a readable repost of day 8 in window 2. Decision: test",
        "- P02 (days 2 and 9): cleared its signal. Its 9 comments (n=1) and 6 comments (n=1) rank first and second of"
        " the 4 posts with comments given (n=4). Decision: keep",
        "- P03 (days 3 and 10): cleared its signal. Viewed rates of 81% (n=1) and 74% (n=1) held on both legs."
        " Decision: keep",
        "- P04 (days 4 and 11): met its kill criterion. None of the 5 comments given (n=2) named offline, at this read"
        " as at the day-7 read. Decision: kill",
        "- P05 (day 5): insufficient data. Its signal names no number the Founder gave. What would settle it: a number"
        " its signal can be read on. Decision: test",
        "- P06 (days 6 and 12): cleared its signal. Its 2 saves (n=1) and 4 saves (n=1) rank in the top half of the 4"
        " posts with saves given (n=4). Decision: keep",
        "- P07 (days 7 and 13): missed its signal. Its 1 save (n=1) on each post ranks in the bottom half of the 4"
        " posts with saves given (n=4). Decision: change",
        "",
        "## Pairs",
        "",
        "- AB-1 (days 1 and 8): repost. Day 8 is under the floor. What would settle it: both legs readable in window 2."
        " Decision: test",
        "- AB-2 (days 3 and 10): resolved, leg A leads. Leg A's viewed rate of 81% (n=1) leads leg B's 74% (n=1)."
        " Decision: keep",
        "",
        "## Product",
        "",
        "- None this read.",
        "",
    ]
)
# The new Angle the Weekly Read session writes for P07's change: P07's pain and source as they are, a Hook of its own.
NEW_ANGLE = (
    '| P08 | Five minutes, timed | Pain 6: "I only had ten minutes" - https://example.com/threads/107 | A timer that'
    ' stops at five makes the session feel whole | "Watch the timer stop at five." | 15s timer timelapse, the timer'
    " large on screen | TikTok | Watched-full rate in the top half | Bottom quartile watched-full on two reads |"
)
EDIT = re.compile(
    r"In `([^`]+)`, lines? \d+(?: to \d+)? (?:is|are) this text, which appears exactly once in the file:\n\n```\n"
    r"(.*?)\n```\n\nReplace it with this text:\n\n```\n(.*?)\n```",
    re.DOTALL,
)


def apply_exactly(item_text: str, mandu: Path) -> list[str]:
    """Apply a proposal's exact edits as Mandu does, with no judgment: each named text, found exactly once in its
    file, replaced by the text given. Returns the files changed."""
    proposal = item_text.split("## Proposal\n", 1)[1].split("\n## Touches\n", 1)[0]
    touched = []
    for path, old, new in EDIT.findall(proposal):
        target = mandu / path
        text = target.read_text(encoding="utf-8")
        assert text.count(old) == 1, (path, text.count(old))
        target.write_text(text.replace(old, new, 1), encoding="utf-8")
        touched.append(path)
    return touched


def owed(kind, key, **more):
    found = weekly_changes.Owed("20261018-weekly-read-14-x", kind, key, "Weekly Read day 14: ...", 1, 14, None)
    for name, value in more.items():
        setattr(found, name, value)
    return found


class EditTest(unittest.TestCase):
    """Each kind of edit, made on the synthetic kit: it replaces a text found exactly once, and applying it changes
    what the decision fixes and nothing else."""

    def text(self, path):
        return (KIT / path).read_text(encoding="utf-8")

    def test_a_kill_marks_its_angle_killed_in_the_creative_log_with_the_two_read_dates(self):
        text = self.text(LOG)
        edit, problem, already = weekly_changes.compose_kill(LOG, text, "P04", ("2026-10-11", "2026-10-18"))
        self.assertEqual((problem, already), ("", ""))
        self.assertTrue(edit.old.lstrip().startswith('"angle_id": "P04-offline",'), edit.old)
        self.assertTrue(edit.old.rstrip().endswith('"status": "draft",'), edit.old)
        self.assertEqual(text.count(edit.old), 1)
        self.assertEqual(text.split("\n")[edit.line - 1].strip(), '"angle_id": "P04-offline",')
        before, after = json.loads(text), json.loads(weekly_changes.apply(text, [edit]))
        record = after["angles"][3]
        self.assertEqual((record["status"], record["killed_on_reads"]), ("killed", ["2026-10-11", "2026-10-18"]))
        before["angles"][3].update(status="killed", killed_on_reads=["2026-10-11", "2026-10-18"])
        self.assertEqual(after, before, "nothing else in the log changes")

    def test_a_kill_needs_exactly_one_record_of_its_angle(self):
        text = self.text(LOG)
        _, problem, _ = weekly_changes.compose_kill(LOG, text, "P09", ("2026-10-11", "2026-10-18"))
        self.assertEqual(problem, f"`{LOG}` has 0 records whose angle_id is P09 or starts with P09-")
        data = json.loads(text)
        data["angles"].append(dict(data["angles"][3]))
        twice = json.dumps(data, indent=2) + "\n"
        _, problem, _ = weekly_changes.compose_kill(LOG, twice, "P04", ("2026-10-11", "2026-10-18"))
        self.assertEqual(problem, f"`{LOG}` has 2 records whose angle_id is P04 or starts with P04-")
        _, problem, _ = weekly_changes.compose_kill(LOG, "{not json", "P04", ("2026-10-11", "2026-10-18"))
        self.assertTrue(problem.startswith(f"`{LOG}` is not JSON ("), problem)

    def test_a_kill_the_log_already_holds_files_nothing(self):
        text = self.text(LOG)
        edit, _, _ = weekly_changes.compose_kill(LOG, text, "P04", ("2026-10-11", "2026-10-18"))
        done = weekly_changes.apply(text, [edit])
        again, problem, already = weekly_changes.compose_kill(LOG, done, "P04", ("2026-10-11", "2026-10-18"))
        self.assertEqual((again, problem), (None, ""))
        self.assertEqual(already, f"`{LOG}` already marks P04 killed on the reads of 2026-10-11 and 2026-10-18")

    def check(self, row, number="P08", old="P07"):
        bank_text, pairs_text = self.text(ANGLES), self.text(PAIRS)
        hooks = weekly_changes.known_hooks(kit.parse_angles(bank_text), kit.parse_pairs(pairs_text))
        return weekly_changes.check_row(row, bank_text, old, number, hooks)

    def test_a_change_adds_its_new_angle_after_the_bank_s_last_row(self):
        cells, problems = self.check(f"\n{NEW_ANGLE}\n")
        self.assertEqual(problems, [])
        text = self.text(ANGLES)
        edit, problem = weekly_changes.compose_change(ANGLES, text, cells)
        self.assertEqual(problem, "")
        self.assertEqual(text.count(edit.old), 1)
        self.assertEqual(edit.old, text.split("\n")[edit.line - 1], "the bank's last row, which appears once")
        after = kit.parse_angles(weekly_changes.apply(text, [edit]))
        self.assertEqual(list(after), ["P01", "P02", "P03", "P04", "P05", "P06", "P07", "P08"])
        self.assertEqual(after["P08"].hook, "Watch the timer stop at five.")
        self.assertEqual(after["P08"].pain, kit.parse_angles(text)["P07"].pain)
        self.assertEqual({key: after[key] for key in kit.parse_angles(text)}, kit.parse_angles(text))

    def test_a_new_angle_is_refused_unless_it_carries_the_changed_angle_s_pain_and_a_hook_of_its_own(self):
        bank = kit.parse_angles(self.text(ANGLES))
        cases = {
            NEW_ANGLE.replace("| P08 |", "| P09 |"): "its ID cell must be P08, the number the brief gives the new"
            " Angle",
            NEW_ANGLE.replace('"I only had ten minutes"', '"I had no time"'): "its pain and source cell must be P07's"
            " exactly as the Angle bank has it: the new Angle carries the same sourced pain",
            NEW_ANGLE.replace('"Watch the timer stop at five."', bank["P07"].hook_cell): "its Hook is one the Angle"
            " bank or the A/B pairs already hold; a Hook belongs to exactly one Angle, so the new Angle needs a Hook of"
            " its own",
            NEW_ANGLE.replace('"Watch the timer stop at five."', '"the session is on screen before you decide."'): "its"
            " Hook is one the Angle bank or the A/B pairs already hold; a Hook belongs to exactly one Angle, so the new"
            " Angle needs a Hook of its own",
            NEW_ANGLE.replace("| TikTok |", "| Instagram |"): "its Platform cell must name TikTok or YouTube Shorts,"
            " the platform whose numbers judge it",
            NEW_ANGLE.replace("| 15s timer", "| | 15s timer"): "the row has 10 cells; the Angle bank's header has 9",
            f"{NEW_ANGLE}\n{NEW_ANGLE}": "the file holds exactly one line: the new Angle's row of the Angle bank, from"
            " | to |",
            NEW_ANGLE.replace("A timer", "Write to someone@example.com: a timer"): "the row holds something that looks"
            " like an email address",
        }
        for row, problem in cases.items():
            with self.subTest(problem=problem):
                _, problems = self.check(row)
                self.assertIn(problem, problems)
                for problem_text in problems:
                    self.assertNotIn("timer", problem_text, "a reason never repeats what the file says")

    def test_a_resolved_pair_adds_one_line_at_the_end_of_its_section(self):
        text = self.text(PAIRS)
        found = owed(weekly_changes.PAIR, "AB-2", leads="A", read_date=date(2026, 10, 18))
        edit, problem, already = weekly_changes.compose_pair(PAIRS, text, found)
        self.assertEqual((problem, already), ("", ""))
        self.assertEqual(text.count(edit.old), 1)
        added = "- Resolved at the window 1 day-14 Weekly Read (2026-10-18): leg A's Hook leads."
        self.assertEqual(edit.new, f"{edit.old}\n{added}")
        before, after = kit.parse_pairs(text), kit.parse_pairs(weekly_changes.apply(text, [edit]))
        self.assertEqual(after["AB-1"], before["AB-1"])
        self.assertEqual(after["AB-2"].legs, before["AB-2"].legs)
        self.assertEqual(after["AB-2"].text.split("\n")[-1], added)
        done = weekly_changes.apply(text, [edit])
        self.assertEqual(
            weekly_changes.compose_pair(PAIRS, done, found)[2], f"`{PAIRS}` already says AB-2 resolved at that read"
        )

    def test_a_resolved_pair_before_another_moves_the_later_section_down_and_changes_nothing_in_it(self):
        text = self.text(PAIRS)
        found = owed(weekly_changes.PAIR, "AB-1", leads="B", read_date=date(2026, 10, 18))
        edit, problem, _ = weekly_changes.compose_pair(PAIRS, text, found)
        self.assertEqual(problem, "")
        before, after = kit.parse_pairs(text), kit.parse_pairs(weekly_changes.apply(text, [edit]))
        self.assertEqual(after["AB-2"].line, before["AB-2"].line + 1)
        self.assertEqual(after["AB-2"].text, before["AB-2"].text)
        self.assertIn(
            "- Resolved at the window 1 day-14 Weekly Read (2026-10-18): leg B's Hook leads.", after["AB-1"].text
        )

    def test_the_flex_slot_puts_its_angle_in_the_calendar_on_its_own_platform(self):
        text, bank = self.text(CALENDAR), kit.parse_angles(self.text(ANGLES))
        for earned, angle, platform in ((True, "P03", "YouTube Shorts"), (False, "P04", "YouTube Shorts")):
            with self.subTest(earned=earned):
                found = owed(weekly_changes.FLEX, "flex", angle="P03" if earned else "", earned=earned, read=7)
                edit, named, problem = weekly_changes.compose_flex(CALENDAR, text, found, bank, ANGLES)
                self.assertEqual((named, problem), (angle, ""))
                self.assertTrue(edit.old.startswith("| 14 | Flex slot |"), edit.old)
                self.assertEqual(text.count(edit.old), 1)
                day = kit.parse_calendar(weekly_changes.apply(text, [edit]))[14]
                self.assertEqual((day.angle, day.pair, day.primary), (angle, None, platform))
                words = "earned at" if earned else "not earned at"
                self.assertIn(f"| {angle} (flex slot: {words} the window 1 day-7 Weekly Read", edit.new)
        # Once the row names an Angle, the calendar has no flex slot left to fill.
        filled = weekly_changes.apply(text, [edit])
        _, _, problem = weekly_changes.compose_flex(CALENDAR, filled, found, bank, ANGLES)
        self.assertEqual(problem, f"`{CALENDAR}` has 0 rows whose Angle the calendar decides later, not one")

    def test_an_added_line_is_anchored_on_the_shortest_run_of_lines_that_appears_once_and_never_on_a_heading(self):
        text = "# Title\n\n## AB-1\n\n- same\n- same\n- last\n\n## AB-2\n\n- same\n- last\n"
        edit = weekly_changes.anchored("f.md", text, 6, ["- added"])
        self.assertEqual((edit.line, edit.old), (5, "- same\n- same\n- last"))
        self.assertIsNone(weekly_changes.anchored("f.md", "## AB-1\n- last\n## AB-2\n- last\n", 1, ["- x"]))
        self.assertEqual(
            weekly_changes.edit_problems("## a\nb\n", [weekly_changes.Edit("f.md", 1, "## a", "## b")]),
            ["the edit at line 1 of `f.md` holds a line that starts with #, which would end its proposal's section"],
        )

    def test_a_new_angle_s_number_follows_every_number_taken(self):
        self.assertEqual(weekly_changes.next_number(["P01", "P16"]), "P17")
        self.assertEqual(weekly_changes.next_number(["P01", "P07", "P09"]), "P10")
        self.assertEqual(weekly_changes.next_number([]), "P01")


class ApprovedDecisionRunTest(CycleTestCase):
    """Whole runs: the day-7 read, the day-14 read, and the Founder's decisions on their items at each sitting."""

    def setUp(self):
        super().setUp()
        self.day_7 = fakes.SUNDAY_RUN.astimezone().date()
        # The window's first sitting was a week before this run, so this run is day 7's; the calendar keeps the days
        # the read covers and the flex slot, so no post Draft is due until the flex slot is filled.
        fakes.set_window(self.repo, {"first_sitting": (self.day_7 - timedelta(days=7)).isoformat(), "slot": "19:00"})
        fakes.keep_days(self.mandu, 1, 2, 3, 4, 5, 14)

    def give(self, read, read_on):
        day_1 = self.day_7 - timedelta(days=6)
        for data in json.loads((EXAMPLES / "results" / f"day-{read:02d}.json").read_text(encoding="utf-8")):
            data.update(
                read_on=read_on.isoformat(),
                posted_on=(day_1 + timedelta(days=data["day"] - 1)).isoformat(),
                recorded_at=f"{read_on.isoformat()}T18:30:00-07:00",
            )
            name = exchange.result_stem(1, read, data["platform"], data["day"])
            fakes.write_record(self.exchange / "results", f"{name}.json", data)

    def items(self, kind):
        return {entry["ask"]: entry for entry in self.queue()["open"] if entry["kind"] == kind}

    def proposals(self):
        queue = self.queue()
        return [entry for entry in queue["open"] + queue["closed"] if entry["kind"] == "package-change-proposal"]

    def read_items(self):
        """The day-7 read's run, the flex slot approved, and the day-14 read's run; the day-14 items by line key."""
        self.give(7, self.day_7)
        fakes.behave(self.codex_dir, {"write": {"weekly-reads/window-1-read-07.md": DAY_7_MEMO}})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        flex = self.items("weekly-read-decision")["Weekly Read day 7: flex slot earned: test"]
        self.assertIn(
            "- Nothing yet: approving it has the next run file a package-change proposal with the exact edit that puts"
            f" P03 in the flex slot of the calendar, `{CALENDAR}`, for you to approve before Mandu changes the file.",
            (self.ledger() / flex["file"]).read_text(encoding="utf-8"),
        )
        self.decide(flex["id"], "approve")
        # A week later: the day-14 read, with every day of the calendar back.
        shutil.copy(str(KIT / CALENDAR), str(self.mandu / CALENDAR))
        day_14 = self.day_7 + timedelta(days=7)
        self.give(14, day_14)
        fakes.behave(self.codex_dir, {"write": {"weekly-reads/window-1-read-14.md": DAY_14_MEMO}})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=7))
        self.assertEqual(code, 0, out)
        return flex, {entry["line_key"]: entry for entry in self.items("weekly-read-decision").values()}

    def test_each_approved_decision_files_one_proposal_with_the_exact_edit_that_mandu_applies_as_written(self):
        flex, items = self.read_items()
        # The flex slot's approval was taken in by the day-14 read's run, which filed its proposal.
        (filed,) = self.proposals()
        self.assertEqual(filed["origin"], f"weekly-read/{flex['id']}")
        self.assertEqual(filed["weekly_change"], {"decision": flex["id"], "kind": "flex"})
        self.assertEqual(filed["ask"], "Approve package change: put P03 in the calendar's flex slot")
        text = (self.ledger() / filed["file"]).read_text(encoding="utf-8")
        self.assertEqual(exchange.check_item(text, ["RepToday"], published=True).problems, [])
        self.assertIn(f"## Touches\n\n- `{CALENDAR}`\n", text)
        self.assertIn(f"- Your approved decision: `evidence/decisions/{flex['id']}.json`", text)
        self.assertEqual(len(items), 9)
        self.assertIn(
            "Weekly Read day 14: AB-2, resolved, leg A leads: keep", [entry["ask"] for entry in items.values()]
        )
        # The Founder approves the kill, the change, the resolved pair, the repost, a keep, and a test.
        for key in ("P04", "P07", "AB-2", "AB-1", "P02", "P01"):
            self.decide(items[key]["id"], "approve")
        change = items["P07"]["id"]
        fakes.behave(self.codex_dir, {"write": {f"weekly-reads/changes/{change}.md": NEW_ANGLE + "\n"}})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=14))
        self.assertEqual(code, 0, out)
        # No Weekly Read is due a week after the day-14 read: the session ran for the new Angle alone.
        self.assertEqual(fakes.sessions_started(self.codex_dir), ["package-review", "weekly-read"])
        brief = self.brief(session="weekly-read")
        self.assertIn(
            "## Weekly Read\n\nNo memo is due this run: window 1's Weekly Reads are behind it. Write none.", brief
        )
        self.assertIn(f"Write the new Angle as P08 in `{self.workspace()}/weekly-reads/changes/{change}.md`.", brief)
        by_kind = {entry["weekly_change"]["kind"]: entry for entry in self.proposals() if entry["id"] != filed["id"]}
        self.assertEqual(sorted(by_kind), ["change", "kill", "pair"], "a keep, a test, and a repost file nothing")
        self.assertEqual(by_kind["kill"]["origin"], f"weekly-read/{items['P04']['id']}")
        self.assertEqual(by_kind["change"]["weekly_change"]["angle"], "P08")
        self.assertEqual(by_kind["change"]["new_angle"], "yes")
        self.assertEqual(by_kind["kill"]["new_angle"], "no")
        self.assertFalse((self.workspace() / "weekly-reads" / "changes" / f"{change}.md").exists())
        outputs = self.report().split("## Outputs\n\n")[1].split("\n\n")[0]
        self.assertIn(
            "| Weekly Read memo | complete | package-change proposals owed by approved decisions: 3 of 3 filed |",
            outputs,
        )
        # Mandu applies each as written: every text it names is in its file exactly once.
        for entry in [filed, *by_kind.values()]:
            text = (self.ledger() / entry["file"]).read_text(encoding="utf-8")
            touched = apply_exactly(text, self.mandu)
            self.assertEqual([f"- `{path}`" for path in touched], [text.split("## Touches\n\n")[1].split("\n")[0]])
        log = json.loads((self.mandu / LOG).read_text(encoding="utf-8"))
        killed = next(record for record in log["angles"] if record["angle_id"].startswith("P04-"))
        read_7, read_14 = self.day_7.isoformat(), (self.day_7 + timedelta(days=7)).isoformat()
        self.assertEqual((killed["status"], killed["killed_on_reads"]), ("killed", [read_7, read_14]))
        bank = kit.parse_angles((self.mandu / ANGLES).read_text(encoding="utf-8"))
        self.assertEqual(bank["P08"].hook, "Watch the timer stop at five.")
        self.assertEqual(bank["P07"].row, kit.parse_angles((KIT / ANGLES).read_text(encoding="utf-8"))["P07"].row)
        pairs = (self.mandu / PAIRS).read_text(encoding="utf-8")
        self.assertIn(f"- Resolved at the window 1 day-14 Weekly Read ({read_14}): leg A's Hook leads.", pairs)
        day = kit.parse_calendar((self.mandu / CALENDAR).read_text(encoding="utf-8"))[14]
        self.assertEqual((day.angle, day.primary), ("P03", "YouTube Shorts"))
        # Whatever the Founder decides of a proposal, no decision files a second one.
        self.decide(by_kind["kill"]["id"], "reject", reason="Not yet.")
        fakes.behave(self.codex_dir, {})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=14, hours=2))
        self.assertEqual(code, 0, out)
        self.assertEqual(len(self.proposals()), 4)
        self.assertNotIn("weekly-read", fakes.sessions_started(self.codex_dir))

    def test_a_rejected_decision_files_nothing(self):
        flex, items = self.read_items()
        for key in ("P04", "P07", "AB-2"):
            self.decide(items[key]["id"], "reject", reason="Not now.")
        fakes.behave(self.codex_dir, {})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=14))
        self.assertEqual(code, 0, out)
        self.assertEqual([entry["weekly_change"]["decision"] for entry in self.proposals()], [flex["id"]])
        self.assertNotIn("weekly-read", fakes.sessions_started(self.codex_dir))

    def test_a_change_whose_new_angle_is_not_filed_still_owes_it_and_says_why(self):
        _, items = self.read_items()
        self.decide(items["P07"]["id"], "approve")
        change = items["P07"]["id"]
        # The session writes nothing and ends with an error: the Weekly Read row says both, and the notice says why.
        fakes.behave(self.codex_dir, {"exit": 9})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=14))
        self.assertEqual(code, 9, out)
        outputs = self.report().split("## Outputs\n\n")[1].split("\n\n")[0]
        self.assertRegex(
            outputs,
            r"\| Weekly Read memo \| incomplete \| its session ended with exit code 9; no package-change proposal for"
            rf" the change of P07 \(`{change}`\): no new Angle was written for it at"
            rf" `weekly-reads/changes/{change}\.md` \|",
        )
        self.assertIn("the change of P07, `" + change + "`: no new Angle was written", self.notices())
        # The next run asks again, and a new Angle that fails its checks is removed with only its name and reasons.
        fakes.behave(self.codex_dir, {"write": {f"weekly-reads/changes/{change}.md": NEW_ANGLE.replace("P08", "P09")}})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=14, hours=2))
        self.assertEqual(code, 0, out)
        self.assertIn("weekly-read", fakes.sessions_started(self.codex_dir))
        self.assertFalse((self.workspace() / "weekly-reads" / "changes" / f"{change}.md").exists())
        report = self.report()
        self.assertIn(
            f"  - `weekly-reads/changes/{change}.md` was set aside, and removed: its ID cell must be P08, the number"
            " the brief gives the new Angle.",
            report,
        )
        self.assertNotIn("timer", report.split("## Weekly Read", 1)[1].split("\n## ", 1)[0])
        self.assertEqual([entry["weekly_change"]["kind"] for entry in self.proposals()], ["flex"])
        fakes.behave(self.codex_dir, {"write": {f"weekly-reads/changes/{change}.md": NEW_ANGLE}})
        code, out = self.run_cycle(at=fakes.SUNDAY_RUN + timedelta(days=14, hours=4))
        self.assertEqual(code, 0, out)
        self.assertEqual(sorted(entry["weekly_change"]["kind"] for entry in self.proposals()), ["change", "flex"])
