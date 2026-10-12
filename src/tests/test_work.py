"""What the launcher counts of the agent's session, from synthetic event streams in Codex's format, and how the run
report sets those counts beside the agent's own word."""

from __future__ import annotations

import json
import os
import re
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from gr0wthlab import cycle, drafts, report, work
from gr0wthlab.report import RunState
from tests import fakes
from tests.test_cycle import CycleTestCase

SHOWN = 40000
FILES_RULE = "counting a file as read when at least half of its lines came back in output the model was shown"
NONE_WRITTEN = (
    "Draft claims: this session wrote or changed none of the 7 Drafts due, so it has no Draft claims to count"
)
ALL_WRITTEN = "Draft claims in the 7 of 7 due Drafts this session wrote or changed"
UNCOUNTED = (
    "Draft claims: not counted; the launcher problems say why",
    "Proposals this session wrote: not counted; the launcher problems say why",
)
UNCOUNTED_WHY = "the Draft claims and the proposals could not be counted"


def page(name: str, lines: int = 60) -> str:
    """A package file's text: numbered lines no other file holds."""
    return "".join(f"{name} line {number:03d} says something particular to it\n" for number in range(1, lines + 1))


class SessionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.events = self.root / "run.events.jsonl"
        self.files = {}
        for name in ("alpha", "bravo", "charlie", "delta", "echo"):
            path = self.root / "package" / f"{name}.md"
            path.parent.mkdir(exist_ok=True)
            path.write_text(page(name), encoding="utf-8")
            self.files[f"package/{name}.md"] = path

    def tearDown(self):
        self.tmp.cleanup()

    def session(self, *lines: str) -> list[work.Command]:
        return work.read_session(fakes.write_events(self.events, *lines), SHOWN)

    def test_a_session_is_its_finished_commands_whatever_else_the_stream_holds(self):
        started = json.dumps({"type": "item.started", "item": {"type": "command_execution", "command": "cat a"}})
        message = json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "Reading."}})
        session = self.session(
            started,
            fakes.command_event("cat brief.md", "the brief\n"),
            message,
            fakes.command_event("rg -n missing package", "", exit_code=1),
            fakes.edit_event("/repo/workspace/drafts/posts/window-1/day-01.md"),
            json.dumps({"type": "turn.completed", "usage": {"output_tokens": 9}}),
            '{"type": "item.completed", "item": {"type": "command_execution", "comm',
        )
        self.assertEqual(
            session,
            [
                work.Command("/bin/zsh -lc 'cat brief.md'", "the brief\n"),
                work.Command("/bin/zsh -lc 'rg -n missing package'", ""),
            ],
        )

    def test_no_stream_is_no_session_and_an_empty_one_is_a_session_that_did_nothing(self):
        self.assertIsNone(work.read_session(self.root / "absent.jsonl", SHOWN))
        self.assertEqual(self.session(), [])
        self.assertEqual(work.files_read(self.session(), self.files), (5, list(self.files)))

    def test_a_large_output_is_shown_as_its_first_and_last_halves_of_the_limit(self):
        # As measured with Codex CLI 0.160.0: of 4,000 lines of 45 characters, the model was shown lines 1 to 445 and
        # 3,557 to 4,000, each side 20,000 characters, with a note that the rest was cut.
        output = "".join(f"L{number:06d} abcdefghijklmnopqrstuvwxyz0123456789\n" for number in range(1, 4001))
        self.assertEqual(len(output), 180000)
        shown = work.shown_part(output, SHOWN)
        self.assertIn("L000444 ", shown)
        self.assertNotIn("L000446 ", shown)
        self.assertNotIn("L003555 ", shown)
        self.assertIn("L003557 ", shown)
        self.assertIn("L004000 ", shown)
        self.assertEqual(work.shown_part(output[:SHOWN], SHOWN), output[:SHOWN])
        cut, whole = self.session(
            fakes.command_event("seq 1 4000", output), fakes.command_event("true", output[:SHOWN])
        )
        self.assertEqual((cut.shown, whole.shown), (shown, output[:SHOWN]))

    def test_a_file_is_read_when_at_least_half_of_its_lines_came_back_shown(self):
        alpha, bravo, charlie, delta, echo = (path.read_text(encoding="utf-8") for path in self.files.values())
        numbered = "".join(f"{number:6d}\t{line}\n" for number, line in enumerate(delta.splitlines(), start=1))
        found = "".join(f"package/echo.md:{number}:{line}\n" for number, line in enumerate(echo.splitlines()[:3], 1))
        session = self.session(
            fakes.command_event("cat package/alpha.md", alpha),
            # One search hit is not the file.
            fakes.command_event("rg -n particular package/bravo.md", "package/bravo.md:7:" + bravo.splitlines()[6]),
            # Two readings of delta, with line numbers, together hold it all.
            fakes.command_event("nl -ba package/delta.md | sed -n 1,30p", numbered[: len(numbered) // 2]),
            fakes.command_event("nl -ba package/delta.md | sed -n 31,60p", numbered[len(numbered) // 2 :]),
            fakes.command_event("rg -n particular package/echo.md", found),
        )
        self.assertEqual(
            work.files_read(session, self.files), (5, ["package/bravo.md", "package/charlie.md", "package/echo.md"])
        )

    def test_a_file_named_in_a_command_whose_output_was_cut_past_it_is_not_read(self):
        # One command prints every file, far more than the model is shown: only the files at its two ends came back.
        middle = page("filler", 2000)
        bulk = (
            self.files["package/alpha.md"].read_text(encoding="utf-8")
            + self.files["package/bravo.md"].read_text(encoding="utf-8")
            + middle
            + self.files["package/charlie.md"].read_text(encoding="utf-8")
            + self.files["package/delta.md"].read_text(encoding="utf-8")
        )
        command = "cat " + " ".join(str(path) for path in self.files.values())
        session = self.session(fakes.command_event(command, bulk + page("echo", 2000)))
        compared, missing = work.files_read(session, self.files)
        self.assertEqual((compared, missing), (5, ["package/charlie.md", "package/delta.md", "package/echo.md"]))

    def test_a_file_that_cannot_be_told_apart_is_left_out_of_the_count(self):
        (self.root / "package" / "empty.md").write_text("\n\n", encoding="utf-8")
        files = dict(self.files, **{"package/empty.md": self.root / "package" / "empty.md"})
        files["package/gone.md"] = self.root / "package" / "gone.md"
        session = self.session(fakes.read_event(*self.files.values()))
        self.assertEqual(work.files_read(session, files), (5, []))

    def test_a_file_of_short_lines_is_read_only_when_a_command_that_names_it_was_shown_it_whole(self):
        path = self.root / "package" / "rules.json"
        text = '{\n"banned": [\n"grind",\n"hustle"\n]\n}\n'
        path.write_text(text, encoding="utf-8")
        files = {"package/rules.json": path}
        filler = page("filler", 2000)
        among = "cat package/alpha.md package/rules.json package/bravo.md"
        sessions = (
            # Its braces and brackets are in any JSON a command prints.
            ("the JSON of another command", "gr0wthlab check-drafts --run R", '{\n"problems": [\n]\n}\n', False),
            ("its text from a command that does not name it", "cat package/*.json", text, False),
            ("named, and cut before it was shown", among, filler + text + filler, False),
            ("named, and shown in part", "head -3 package/rules.json", '{\n"banned": [\n"grind",\n', False),
            ("named, and shown whole", f"cat {path}", text, True),
            ("named, and shown whole among others", among, page("alpha") + text + page("bravo"), True),
        )
        for label, command, output, read in sessions:
            with self.subTest(label):
                session = self.session(fakes.command_event(command, output))
                self.assertEqual(work.files_read(session, files), (1, [] if read else ["package/rules.json"]))


class CountLinesTest(unittest.TestCase):
    def state(self, counted: work.Work | None, summary: str = "Looked around.\n\nReview: complete\n") -> RunState:
        state = RunState("R", "on-demand", datetime(2026, 10, 11, 23, tzinfo=timezone.utc), "i.md")
        state.agent = {
            "exit_code": 0,
            "agent_started": True,
            "agent_seconds": 501.2,
            "time_limit_seconds": 1800.0,
            "model": "gpt-6-luna",
            "reasoning_effort": "high",
        }
        state.agent_summary = summary
        state.review = (summary.strip().splitlines() or [""])[-1].strip()
        state.work = counted
        return state

    def claims(self, before: dict, after: dict) -> work.Claims:
        """The claims of the Drafts a session wrote or changed, between two standings of the Drafts due."""
        return work.written(work.Standing(before, {}), work.Standing(after, {})).claims

    def test_every_count_says_what_it_counts(self):
        claims = work.Claims(due=7, written=3, listed=8, cited=7)
        counted = work.Work(
            files_listed=24, files_not_read=("gtm/a.md", "gtm/b.md"), claims=claims, proposals=work.Proposals(4)
        )
        self.assertEqual(
            work.count_lines(counted),
            [
                f"Package files read: 22 of the 24 the brief listed, {FILES_RULE}. Not read: `gtm/a.md`, `gtm/b.md`.",
                "Draft claims in the 3 of 7 due Drafts this session wrote or changed: 8 listed, 7 name a code location"
                " and 1 names none.",
                "Proposals this session wrote: 4 queued.",
            ],
        )
        self.assertEqual(
            work.summary(counted),
            "22 of 24 package files read, 7 of 8 Draft claims with a code location in the 3 of 7 due Drafts this"
            " session wrote or changed, 4 proposals this session wrote queued",
        )
        self.assertEqual(
            counted.as_json(),
            {
                "package_files_listed": 24,
                "package_files_read": 22,
                "package_files_not_read": ["gtm/a.md", "gtm/b.md"],
                "claims_with_code_location": 7,
                "claims_without_code_location": 1,
                "proposals_queued": 4,
            },
        )

    def test_the_draft_claims_line_says_which_drafts_it_is_of_or_why_there_is_no_count(self):
        lines = {
            work.Claims(due=1, written=1, listed=1, cited=1): (
                "Draft claims in the 1 of 1 due Draft this session wrote or changed: 1 listed, 1 names a code location"
                " and 0 name none.",
                "1 of 1 Draft claim with a code location in the 1 of 1 due Draft this session wrote or changed, ",
            ),
            work.Claims(due=7): (
                "Draft claims: this session wrote or changed none of the 7 Drafts due, so it has no Draft claims to"
                " count.",
                "none of the 7 Drafts due written or changed, ",
            ),
            work.Claims(): ("Draft claims: none to count; no post Draft was due.", ""),
            None: ("Draft claims: not counted; the launcher problems say why.", "Draft claims not counted, "),
        }
        for claims, (line, summary) in lines.items():
            with self.subTest(claims=claims):
                counted = work.Work(claims=claims, proposals=work.Proposals())
                self.assertEqual(work.count_lines(counted)[1], line)
                self.assertEqual(work.summary(counted), f"{summary}0 proposals this session wrote queued")
        uncounted = work.Work(claims=None).as_json()
        self.assertEqual(
            (uncounted["claims_with_code_location"], uncounted["claims_without_code_location"]), (None,) * 2
        )

    def test_the_proposals_line_counts_this_session_s_and_names_an_earlier_run_s_apart(self):
        lines = {
            work.Proposals(written=2): (
                "Proposals this session wrote: 2 queued.",
                "2 proposals this session wrote queued",
            ),
            work.Proposals(left=5): (
                "Proposals this session wrote: 0 queued; 5 more queued in this run were left by an earlier run.",
                "0 proposals this session wrote queued",
            ),
            work.Proposals(written=1, left=1): (
                "Proposals this session wrote: 1 queued; 1 more queued in this run was left by an earlier run.",
                "1 proposal this session wrote queued",
            ),
            None: (
                "Proposals this session wrote: not counted; the launcher problems say why.",
                "proposals not counted",
            ),
        }
        for proposals, (line, summary) in lines.items():
            with self.subTest(proposals=proposals):
                counted = work.Work(claims=work.Claims(), proposals=proposals)
                self.assertEqual(work.count_lines(counted)[2], line)
                self.assertEqual(work.summary(counted), summary)
        self.assertEqual(work.Work(proposals=work.Proposals(written=1, left=5)).as_json()["proposals_queued"], 1)
        self.assertIsNone(work.Work(proposals=None).as_json()["proposals_queued"])

    def test_a_proposal_an_earlier_run_left_is_not_this_session_s(self):
        before = work.Standing({}, {"left.md": "a", "rewritten.md": "b", "set-aside.md": "c"})
        after = work.Standing({}, {"left.md": "a", "rewritten.md": "B", "set-aside.md": "c", "new.md": "d"})
        proposals = work.written(before, after).proposals
        self.assertEqual(proposals, {"left.md": False, "rewritten.md": True, "set-aside.md": False, "new.md": True})
        queued = ["left.md", "rewritten.md", "new.md", "a-notice.md"]
        self.assertEqual(work.count_proposals(proposals, queued), work.Proposals(written=2, left=1))
        self.assertEqual(work.count_proposals(proposals, []), work.Proposals())

    def test_a_draft_an_earlier_run_left_is_not_this_session_s(self):
        earlier = {day: drafts.parse(fakes.draft(day), fakes.draft_path(day)) for day in (1, 2, 3)}
        changed = drafts.parse(fakes.draft(2, caption="The score dipped and kept its history."), fakes.draft_path(2))
        new = drafts.parse(fakes.draft(4), fakes.draft_path(4))
        before = {**earlier, 4: None, 5: None}
        after = {1: earlier[1], 2: changed, 3: None, 4: new, 5: None}
        self.assertEqual(self.claims(before, after), work.Claims(due=5, written=2, listed=2, cited=2))
        self.assertEqual(self.claims(before, before), work.Claims(due=5))
        self.assertEqual(self.claims({}, {}), work.Claims())

    def test_a_claim_item_the_launcher_cannot_read_names_no_code_location(self):
        # After the clean Draft's one claim: an item with no Shows line, one with no Code line, and one naming none.
        text = fakes.draft(3) + (
            "- Claim: The streak never resets.\n  Code: `Engine/ConsistencyScore.swift:6-7`\n"
            "- Claim: A rest day counts.\n  Shows: `restDays`\n"
            "- Claim: It reminds you at night.\n  Code: none\n  Shows: none\n"
        )
        draft = drafts.parse(text, fakes.draft_path(3))
        self.assertEqual((len(draft.claims), draft.unread_claims), (2, 2))
        claims = self.claims({3: None}, {3: draft})
        self.assertEqual(claims, work.Claims(due=1, written=1, listed=4, cited=1))
        self.assertEqual(claims.cited + claims.uncited, claims.listed)
        self.assertEqual(
            work.count_lines(work.Work(claims=claims))[1],
            "Draft claims in the 1 of 1 due Draft this session wrote or changed: 4 listed, 1 names a code location and"
            " 3 name none.",
        )

    def test_many_unread_files_are_counted_and_not_named(self):
        unread = tuple(f"gtm/{number}.md" for number in range(work.NAMED_AT_MOST + 1))
        lines = work.count_lines(work.Work(files_listed=24, files_not_read=unread))
        self.assertEqual(lines[0], f"Package files read: 17 of the 24 the brief listed, {FILES_RULE}.")

    def test_a_run_with_no_stream_says_so(self):
        counted = work.Work(files_listed=24, claims=work.Claims(), proposals=work.Proposals())
        self.assertEqual(
            work.count_lines(counted),
            [
                "Package files read: not counted; the agent left no record of a session to count from.",
                "Draft claims: none to count; no post Draft was due.",
                "Proposals this session wrote: 0 queued.",
            ],
        )
        self.assertIsNone(counted.as_json()["package_files_read"])
        self.assertIsNone(counted.as_json()["package_files_not_read"])
        self.assertEqual(work.summary(counted), "0 proposals this session wrote queued")

    def test_the_report_names_the_launcher_s_counts_and_the_agent_s_word_apart(self):
        counted = work.Work(
            files_listed=24, files_not_read=("a",) * 18, claims=work.Claims(due=7), proposals=work.Proposals(1)
        )
        text = report.render_report(self.state(counted))
        section = text.split("## Agent's work\n", 1)[1].split("\n## Agent\n", 1)[0]
        launcher, agent = section.split("The agent's own word, which the launcher does not check:")
        self.assertIn("Counted by the launcher from Codex's record of the session", launcher)
        self.assertIn("None of these comes from what the agent says of itself", launcher)
        self.assertEqual(
            [line for line in launcher.splitlines() if line.startswith("- ")],
            [
                "- Agent time: 8 min 21 s of its 30 min limit, with `gpt-6-luna` at `high` reasoning effort.",
                f"- Package files read: 6 of the 24 the brief listed, {FILES_RULE}.",
                f"- {NONE_WRITTEN}.",
                "- Proposals this session wrote: 1 queued.",
            ],
        )
        self.assertNotIn("Review:", launcher)
        self.assertEqual(agent.strip(), '- "Review: complete"')
        self.assertIn(
            "- The agent's work, as the launcher counted it: 6 of 24 package files read, none of the 7 Drafts due"
            " written or changed, 1 proposal this session wrote queued, in 8 min 21 s of agent time. The agent's own"
            ' word: "Review: complete".',
            text.split("## Sources")[0],
        )

    def test_the_agent_s_word_is_quoted_as_it_ended_or_named_as_missing(self):
        incomplete = self.state(work.Work(), "Stopped.\n\nReview: incomplete: pass 2, out of time.\n")
        self.assertEqual(report.review_word(incomplete), '"Review: incomplete: pass 2, out of time."')
        ticked = self.state(work.Work(), "Reviewed it all.\n\n`Review: complete`\n")
        self.assertEqual(
            report.review_word(ticked),
            'its last line, "`Review: complete`", is neither of the closing lines the launcher accepts, the plain text'
            " `Review: complete` or `Review: incomplete: ...`",
        )
        self.assertEqual(ticked.review_gap(), "the agent did not confirm that it finished every pass")
        other = self.state(work.Work(), "All done here, nothing else to add " + "x" * 400)
        self.assertRegex(report.review_word(other), r'^its last line, "All done.*x\.\.\.", is neither of the closing')
        self.assertLess(len(report.review_word(other)), 450)
        self.assertEqual(report.review_word(self.state(work.Work(), "")), "none; the agent left no summary")

    def test_a_run_whose_agent_never_started_counts_nothing(self):
        state = self.state(None, "")
        state.agent = {"exit_code": 2, "agent_started": False, "error": "codex executable not found"}
        text = report.render_report(state)
        self.assertIn("## Agent's work\n\nThe launcher counted nothing: the agent did not start", text)
        self.assertNotIn("as the launcher counted it", text)


def uncited(text: str) -> str:
    """A Draft whose every claim names no code."""
    text = re.sub(r"(?m)^  Code: .*$", "  Code: none", text)
    return re.sub(r"(?m)^  Shows: .*$", "  Shows: none", text)


class RunCountsTest(CycleTestCase):
    def setUp(self):
        super().setUp()
        fakes.set_window(self.repo, {"first_sitting": None, "slot": None})
        self.package = fakes.package_files(self.mandu)
        self.drafts = [str(self.workspace() / fakes.draft_path(day)) for day in range(1, 8)]

    def record(self) -> dict:
        """The latest run's counts in its log record."""
        return json.loads(sorted(self.logs.glob("*-on-demand-*.json"))[-1].read_text(encoding="utf-8"))["work"]

    def counts(self) -> list[str]:
        """The launcher's counts in the run report's Agent's work section, one to a line."""
        section = self.report().split("## Agent's work\n", 1)[1].split("\n## Agent\n", 1)[0]
        launcher = section.split("The agent's own word, which the launcher does not check:")[0]
        return [line for line in launcher.splitlines() if line.startswith("- ")]

    def test_a_thorough_session_s_counts_match_what_it_did(self):
        events = [fakes.read_event(path) for path in self.package]
        events += [fakes.edit_event(*self.drafts), fakes.edit_event("incoming/name-status-stale.md")]
        events.append(
            fakes.command_event(f"/usr/bin/python3 {self.repo}/src/bin/gr0wthlab check-drafts --run R", "", 1)
        )
        writes = {fakes.draft_path(day): fakes.draft(day) for day in range(1, 8)}
        writes["review-queue/incoming/name-status-stale.md"] = fakes.PROPOSAL
        fakes.behave(self.codex_dir, {"write": writes, "events": events})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        self.assertEqual(len(self.package), 14)
        self.assertEqual(
            self.record(),
            {
                "package_files_listed": 14,
                "package_files_read": 14,
                "package_files_not_read": [],
                "claims_with_code_location": 7,
                "claims_without_code_location": 0,
                "proposals_queued": 1,
            },
        )
        time, *counts = self.counts()
        self.assertRegex(
            time, r"^- Agent time: \d+ s of its 30 min limit, with `[\w.-]+` at `high` reasoning effort\.$"
        )
        self.assertEqual(
            counts,
            [
                f"- Package files read: 14 of the 14 the brief listed, {FILES_RULE}.",
                f"- {ALL_WRITTEN}: 7 listed, 7 name a code location and 0 name none.",
                "- Proposals this session wrote: 1 queued.",
            ],
        )

    def test_a_session_that_opens_few_files_and_says_it_finished_is_shown_for_what_it_did(self):
        # The shallow session of the investigation: one command prints every package file, most of it cut before the
        # model sees it, two files are read on their own, and the summary still ends `Review: complete`.
        bulk = "".join(path.read_text(encoding="utf-8") for path in self.package)
        opened = self.package[:2]
        events = [
            fakes.command_event(
                "cat " + " ".join(str(path) for path in self.package), "x" * 30000 + bulk + "y" * 30000
            ),
            *[fakes.read_event(path) for path in opened],
            fakes.edit_event("incoming/name-status-stale.md"),
        ]
        writes = {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}
        fakes.behave(self.codex_dir, {"write": writes, "events": events})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        counted = self.record()
        self.assertEqual((counted["package_files_read"], counted["package_files_listed"]), (2, 14))
        self.assertEqual(len(counted["package_files_not_read"]), 12)
        self.assertEqual((counted["claims_with_code_location"], counted["claims_without_code_location"]), (0, 0))
        text = self.report()
        self.assertIn(
            "- The agent's work, as the launcher counted it: 2 of 14 package files read, none of the 7 Drafts due"
            " written or changed, 1 proposal this session wrote queued, in ",
            text,
        )
        self.assertIn('The agent\'s own word: "Review: complete".', text)
        self.assertEqual(
            self.counts()[1:],
            [
                f"- Package files read: 2 of the 14 the brief listed, {FILES_RULE}.",
                f"- {NONE_WRITTEN}.",
                "- Proposals this session wrote: 1 queued.",
            ],
        )
        # The counts gate nothing: the review row stands on the agent's word as before, and the proposal is queued.
        self.assertIn(f"| Package review (contradictions) | complete | {cycle.REVIEW_SAID_COMPLETE} |", text)
        self.assertIn("20261011-name-status-stale", [entry["id"] for entry in self.queue()["open"]])
        notice = next(entry for entry in self.queue()["open"] if entry["kind"] == "notice")
        self.assertNotIn("package files", (self.ledger() / notice["file"]).read_text(encoding="utf-8"))

    def test_claims_that_all_lack_code_are_counted_as_naming_none(self):
        writes = {fakes.draft_path(day): uncited(fakes.draft(day)) for day in range(1, 8)}
        fakes.behave(self.codex_dir, {"write": writes, "events": [fakes.edit_event(*self.drafts)]})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        counted = self.record()
        self.assertEqual((counted["claims_with_code_location"], counted["claims_without_code_location"]), (0, 7))
        self.assertIn(f"- {ALL_WRITTEN}: 7 listed, 0 name a code location and 7 name none.", self.counts())
        self.assertIn(
            "0 of 7 Draft claims with a code location in the 7 of 7 due Drafts this session wrote or changed",
            self.report().split("## Sources")[0],
        )
        # The Draft check blocks them as it did before the counts existed, each naming its claim.
        self.assertIn("| Post Drafts | complete | 7 days: 7 blocked |", self.report())
        self.assertEqual(self.report().count("claim-unsupported:"), 7)

    def test_a_timed_out_agent_s_partial_stream_is_still_counted(self):
        fakes.set_run(self.repo, "agent", {"time_limit_seconds": 2})
        events = [fakes.read_event(path) for path in self.package[:3]]
        fakes.behave(self.codex_dir, {"hang": True, "events": events})
        try:
            code, out = self.run_cycle()
        finally:
            fakes.stop_leftovers(self.codex_dir)
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        self.assertEqual(self.record()["package_files_read"], 3)
        self.assertIn("The agent's own word: none; the agent left no summary.", self.report())

    def test_a_second_run_that_writes_nothing_has_no_draft_claims_to_count(self):
        writes = {fakes.draft_path(day): fakes.draft(day) for day in range(1, 8)}
        fakes.behave(self.codex_dir, {"write": writes})
        self.assertEqual(self.run_cycle()[0], 0)
        self.assertIn(f"- {ALL_WRITTEN}: 7 listed, 7 name a code location and 0 name none.", self.counts())
        # The second session opens three files, writes nothing, and says it finished.
        fakes.behave(self.codex_dir, {"events": [fakes.read_event(path) for path in self.package[:3]]})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        counted = self.record()
        self.assertEqual((counted["claims_with_code_location"], counted["claims_without_code_location"]), (0, 0))
        self.assertIn(f"- {NONE_WRITTEN}.", self.counts())
        text = self.report()
        self.assertIn(
            "- The agent's work, as the launcher counted it: 3 of 14 package files read, none of the 7 Drafts due"
            " written or changed, 0 proposals this session wrote queued, in ",
            text,
        )
        self.assertIn('The agent\'s own word: "Review: complete".', text)
        self.assertNotIn("Draft claims with a code location", text)

    def test_a_second_run_that_changes_one_draft_counts_that_one_only(self):
        writes = {fakes.draft_path(day): fakes.draft(day) for day in range(1, 8)}
        fakes.behave(self.codex_dir, {"write": writes})
        self.assertEqual(self.run_cycle()[0], 0)
        changed = uncited(fakes.draft(3, caption="The score dipped after a skipped day and kept its history."))
        fakes.behave(self.codex_dir, {"write": {fakes.draft_path(3): changed}})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        counted = self.record()
        self.assertEqual((counted["claims_with_code_location"], counted["claims_without_code_location"]), (0, 1))
        self.assertIn(
            "- Draft claims in the 1 of 7 due Drafts this session wrote or changed: 1 listed, 0 name a code location"
            " and 1 names none.",
            self.counts(),
        )

    @unittest.skipIf(os.geteuid() == 0, "root can search any folder")
    def test_a_draft_folder_closed_before_the_agent_starts_leaves_the_claims_uncounted_and_the_run_going(self):
        # An earlier run's Draft sits in a folder the launcher cannot search before the agent starts. Nothing says
        # whether this session wrote it, so its claims are not counted, nor are the proposals, which are told apart
        # by the same reading, and the run goes on as it would have: the agent runs, the folder is restored once it
        # has ended, and the Draft there is checked.
        earlier = self.workspace() / fakes.draft_path(1)
        earlier.parent.mkdir(parents=True)
        earlier.write_text(fakes.draft(1), encoding="utf-8")
        earlier.parent.chmod(0)
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.counts()[2:], [f"- {line}." for line in UNCOUNTED])
        text = self.report()
        problems = text.partition("\n## Launcher problems\n")[2]
        self.assertRegex(problems, rf"- {UNCOUNTED_WHY} \(\[Errno 13\] Permission denied: '[^']*day-01\.md'\)")
        self.assertIn("was left without its owner's read and write access, so the launcher restored it", problems)
        self.assertIn("Draft claims not counted, proposals not counted, in ", text.split("## Sources")[0])
        counted = self.record()
        self.assertEqual((counted["claims_with_code_location"], counted["claims_without_code_location"]), (None,) * 2)
        self.assertEqual((counted["package_files_listed"], counted["proposals_queued"]), (14, None))
        self.assertIn("20261011-name-status-stale", [entry["id"] for entry in self.queue()["open"]])
        self.assertEqual(earlier.read_text(encoding="utf-8"), fakes.draft(1))

    def leave_proposals(self, count: int = 5) -> None:
        """A first run that cannot read the Review Queue, so the proposals its session wrote stay in incoming/; the
        queue file is then repaired."""
        queue = self.ledger() / "review-queue/queue.json"
        queue.parent.mkdir(parents=True)
        queue.write_text("{", encoding="utf-8")
        writes = {
            f"review-queue/incoming/stale-{number}.md": fakes.proposal(title=f"record fact {number} as cleared")
            for number in range(1, count + 1)
        }
        fakes.behave(self.codex_dir, {"write": writes})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        self.assertIn("- Proposals this session wrote: 0 queued.", self.counts())
        self.assertEqual(len(list((self.workspace() / "review-queue/incoming").iterdir())), count)
        queue.unlink()

    def queued_from(self, slug: str) -> list[str]:
        return [entry["id"] for entry in self.queue()["open"] if f"-{slug}" in entry["id"]]

    def test_proposals_an_earlier_run_left_are_queued_and_not_counted_as_this_session_s(self):
        self.leave_proposals()
        # The second session opens three files, writes nothing, and says it finished.
        fakes.behave(self.codex_dir, {"events": [fakes.read_event(path) for path in self.package[:3]]})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        self.assertEqual(len(self.queued_from("stale-")), 5)
        self.assertIn(
            "- Proposals this session wrote: 0 queued; 5 more queued in this run were left by an earlier run.",
            self.counts(),
        )
        text = self.report()
        self.assertIn(
            "- The agent's work, as the launcher counted it: 3 of 14 package files read, none of the 7 Drafts due"
            " written or changed, 0 proposals this session wrote queued, in ",
            text,
        )
        self.assertIn('The agent\'s own word: "Review: complete".', text)
        self.assertEqual(self.record()["proposals_queued"], 0)

    def test_a_second_run_that_adds_one_proposal_beside_leftovers_counts_that_one(self):
        self.leave_proposals()
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        self.assertEqual((len(self.queued_from("stale-")), len(self.queued_from("name-status-stale"))), (5, 1))
        self.assertIn(
            "- Proposals this session wrote: 1 queued; 5 more queued in this run were left by an earlier run.",
            self.counts(),
        )
        self.assertIn("1 proposal this session wrote queued, in ", self.report().split("## Sources")[0])
        self.assertEqual(self.record()["proposals_queued"], 1)

    @unittest.skipIf(os.geteuid() == 0, "root can list any folder")
    def test_an_incoming_folder_unreadable_before_the_agent_starts_leaves_the_proposals_uncounted_and_the_run_going(
        self,
    ):
        # An earlier run's proposal sits in an incoming/ the launcher cannot list before the agent starts. Nothing
        # says whether this session wrote it, so the proposals are not counted, and the run goes on as it would
        # have: the agent runs, the folder is restored once it has ended, and everything in it is queued.
        incoming = self.workspace() / "review-queue/incoming"
        incoming.mkdir()
        (incoming / "left-behind.md").write_text(fakes.proposal(title="record the launch date"), encoding="utf-8")
        incoming.chmod(0o300)
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.counts()[2:], [f"- {line}." for line in UNCOUNTED])
        text = self.report()
        problems = text.partition("\n## Launcher problems\n")[2]
        self.assertRegex(problems, rf"- {UNCOUNTED_WHY} \(\[Errno 13\] Permission denied: '[^']*incoming'\)")
        self.assertIn(
            "- `workspace/review-queue/incoming` was left without its owner's read and write access, so the launcher"
            " restored it",
            problems,
        )
        self.assertIn("Draft claims not counted, proposals not counted, in ", text.split("## Sources")[0])
        counted = self.record()
        self.assertEqual((counted["package_files_listed"], counted["proposals_queued"]), (14, None))
        self.assertEqual((len(self.queued_from("left-behind")), len(self.queued_from("name-status-stale"))), (1, 1))

    def test_a_count_that_cannot_be_made_is_a_launcher_problem_and_the_run_goes_on(self):
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})

        def fail(*args, **kwargs):
            raise OSError("the event stream went away")

        original, work.measure = work.measure, fail
        try:
            code, out = self.run_cycle()
        finally:
            work.measure = original
        self.assertEqual(code, 0, out)
        text = self.report()
        self.assertIn("- the agent's work could not be counted (the event stream went away)", text)
        self.assertIn("The launcher counted nothing", text)
        self.assertIn("20261011-name-status-stale", [entry["id"] for entry in self.queue()["open"]])


if __name__ == "__main__":
    unittest.main()
