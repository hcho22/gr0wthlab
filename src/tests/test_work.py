"""What the launcher counts of an agent session, from synthetic event streams in Codex's format, and how the run
report sets each session's counts beside that session's own word, and then gives the run's totals."""

from __future__ import annotations

import json
import os
import re
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from gr0wthlab import cycle, drafts, report, sessions, work
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
    "Proposals this session wrote to incoming/: not counted; the launcher problems say why",
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
    def state(
        self,
        counted: work.Work | None,
        summary: str = "Looked around.\n\nSession: complete\n",
        key: str = "package-review",
    ) -> RunState:
        """A run whose one session, the package review's unless told otherwise, ended with that summary."""
        state = RunState("R", "on-demand", datetime(2026, 10, 11, 23, tzinfo=timezone.utc), "i.md")
        session = fakes.session(key, agent_seconds=501.2, model="gpt-6-luna", reasoning_effort="high")
        session.summary = summary
        session.closing = (summary.strip().splitlines() or [""])[-1].strip()
        session.work = counted
        state.sessions = [session]
        state.run_limit = 5400.0
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
                "Proposals this session wrote to incoming/: 4 queued.",
            ],
        )
        self.assertEqual(
            work.summary(counted),
            "22 of 24 package files read, 7 of 8 Draft claims with a code location in the 3 of 7 due Drafts this"
            " session wrote or changed, 4 proposals this session wrote to incoming/ queued",
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
                self.assertEqual(work.summary(counted), f"{summary}0 proposals this session wrote to incoming/ queued")
        uncounted = work.Work(claims=None).as_json()
        self.assertEqual(
            (uncounted["claims_with_code_location"], uncounted["claims_without_code_location"]), (None,) * 2
        )

    def test_the_proposals_line_counts_this_session_s_and_names_an_earlier_run_s_apart(self):
        lines = {
            work.Proposals(written=2): (
                "Proposals this session wrote to incoming/: 2 queued.",
                "2 proposals this session wrote to incoming/ queued",
            ),
            work.Proposals(left=5): (
                "Proposals this session wrote to incoming/: 0 queued; 5 more queued in this run were"
                " left by an earlier run.",
                "0 proposals this session wrote to incoming/ queued",
            ),
            work.Proposals(written=1, left=1): (
                "Proposals this session wrote to incoming/: 1 queued; 1 more queued in this run was"
                " left by an earlier run.",
                "1 proposal this session wrote to incoming/ queued",
            ),
            None: (
                "Proposals this session wrote to incoming/: not counted; the launcher problems say why.",
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
        # One session's count is of its own alone: what else was queued may be another session's of the same run.
        self.assertEqual(work.count_proposals(proposals, queued), work.Proposals(written=2))
        # Read from before a run's first session to after its last, the rest are what an earlier run left.
        self.assertEqual(work.count_proposals(proposals, queued, whole_run=True), work.Proposals(written=2, left=1))
        self.assertEqual(work.count_proposals(proposals, [], whole_run=True), work.Proposals())

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
                "Proposals this session wrote to incoming/: 0 queued.",
            ],
        )
        self.assertIsNone(counted.as_json()["package_files_read"])
        self.assertIsNone(counted.as_json()["package_files_not_read"])
        self.assertEqual(work.summary(counted), "0 proposals this session wrote to incoming/ queued")

    def test_a_count_a_session_was_not_asked_for_is_left_out_of_its_one_line_while_it_has_nothing_to_say(self):
        quiet = work.Work(files_listed=0, files_not_read=(), claims=work.Claims(due=7), proposals=work.Proposals())
        # The session that writes the Drafts and may write items says so when it wrote none of either.
        self.assertEqual(
            work.summary(quiet),
            "none of the 7 Drafts due written or changed, 0 proposals this session wrote to incoming/ queued",
        )
        # A session asked for neither, such as Filming's, has nothing to say of them, and a brief that listed no
        # package file leaves no file count.
        self.assertEqual(work.summary(quiet, drafts=False, items=False), "")
        self.assertEqual(
            work.count_lines(quiet)[0],
            "Package files read: none to count; this session's brief listed no package file.",
        )
        # What it did all the same is counted: a Draft it changed, a proposal it wrote.
        busy = work.Work(claims=work.Claims(due=7, written=1, listed=2, cited=1), proposals=work.Proposals(1))
        self.assertEqual(
            work.summary(busy, drafts=False, items=False),
            "1 of 2 Draft claims with a code location in the 1 of 7 due Drafts this session wrote or changed,"
            " 1 proposal this session wrote to incoming/ queued",
        )

    def test_the_run_s_totals_name_the_sessions_together_and_what_an_earlier_run_left(self):
        self.assertEqual(
            work.claim_line(work.Claims(due=7), whole_run=True),
            "Draft claims: the sessions of this run wrote or changed none of the 7 Drafts due, so they have no Draft"
            " claims to count",
        )
        self.assertEqual(
            work.claim_line(work.Claims(due=7, written=2, listed=3, cited=2), whole_run=True),
            "Draft claims in the 2 of 7 due Drafts the sessions of this run wrote or changed: 3 listed, 2 name a code"
            " location and 1 names none",
        )
        self.assertEqual(
            work.proposal_line(work.Proposals(written=3, left=5), whole_run=True),
            "Proposals the sessions of this run wrote to incoming/: 3 queued; 5 more queued in this run were left by"
            " an earlier run",
        )

    def test_the_report_names_the_launcher_s_counts_and_the_agent_s_word_apart(self):
        counted = work.Work(
            files_listed=24, files_not_read=("a",) * 18, claims=work.Claims(due=7), proposals=work.Proposals(1)
        )
        text = report.render_report(self.state(counted))
        section = text.split("## Sessions\n", 1)[1].split("\n## Agent\n", 1)[0]
        self.assertIn("none of it comes from what an agent says of itself", section)
        self.assertIn("The last column is each agent's own closing line, which the launcher does not check.", section)
        own = section.split("### Package review\n", 1)[1].split("\n### The run's totals\n", 1)[0]
        self.assertEqual(
            [line for line in own.splitlines() if line.startswith("- ")],
            [
                "- Ended by itself with exit code 0.",
                "- Agent time: 8 min 21 s of its 30 min limit, with `gpt-6-luna` at `high` reasoning effort.",
                "- Approximate cost: unknown.",
                f"- Package files read: 6 of the 24 the brief listed, {FILES_RULE}.",
                f"- {NONE_WRITTEN}.",
                "- Proposals this session wrote to incoming/: 1 queued.",
                '- The agent\'s own word, which the launcher does not check: "Session: complete"',
            ],
        )
        self.assertIn(
            '| Package review | ended by itself, exit code 0 | 8 min 21 s | 30 min | unknown | "Session: complete" |',
            section,
        )
        self.assertIn(
            "| All sessions | 1 ran of the 1 with work due | 8 min 21 s | 90 min for the run | - |  |", section
        )
        # The package review is not the session that writes the Drafts, so its one line says nothing of them.
        self.assertIn(
            "- The Package review session's work, as the launcher counted it: 6 of 24 package files read, 1 proposal"
            " this session wrote to incoming/ queued, in 8 min 21 s of agent time. Its agent's own word:"
            ' "Session: complete".',
            text.split("## Sources")[0],
        )

    def test_the_agent_s_word_is_quoted_as_it_ended_or_named_as_missing(self):
        def word(summary: str) -> str:
            return self.state(work.Work(), summary).sessions[0].word()

        self.assertEqual(
            word("Stopped.\n\nSession: incomplete: pass 2, out of time.\n"),
            '"Session: incomplete: pass 2, out of time."',
        )
        ticked = self.state(work.Work(), "Reviewed it all.\n\n`Session: complete`\n")
        self.assertEqual(
            ticked.sessions[0].word(),
            'its last line, "`Session: complete`", is neither of the closing lines the launcher accepts, the plain'
            " text `Session: complete` or `Session: incomplete: ...`",
        )
        self.assertEqual(ticked.review_gap(), "the agent did not confirm that it finished every pass")
        # The single session's closing line, which named one workflow's work, is no longer a confirmation.
        self.assertFalse(self.state(work.Work(), "Reviewed it all.\n\nReview: complete\n").sessions[0].confirmed)
        other = word("All done here, nothing else to add " + "x" * 400)
        self.assertRegex(other, r'^its last line, "All done.*x\.\.\.", is neither of the closing')
        self.assertLess(len(other), 450)
        self.assertEqual(word(""), "none; the agent left no summary")

    def test_only_the_package_review_s_row_reads_its_session_s_closing_line(self):
        unconfirmed = "Wrote four of five.\n\nSession: incomplete: one message is left.\n"
        self.assertEqual(
            self.state(work.Work(), unconfirmed, sessions.REVIEW).review_gap(),
            "the agent did not finish its review: one message is left",
        )
        outreach = self.state(work.Work(), unconfirmed, "outreach")
        self.assertEqual((outreach.review_gap(), outreach.agent_gap("outreach")), ("", ""))

    def test_a_run_whose_agent_never_started_counts_nothing(self):
        state = self.state(None, "")
        state.sessions[0].record = {"exit_code": 2, "agent_started": False, "error": "codex executable not found"}
        text = report.render_report(state)
        self.assertIn(
            "### Package review\n\n- Did not start: codex executable not found.\n- The launcher counted nothing: no"
            " agent ran.",
            text,
        )
        self.assertIn("| Package review | did not start: codex executable not found | - | 30 min | - | - |", text)
        self.assertNotIn("as the launcher counted it", text)
        self.assertIn("- Approximate cost: none; no agent session was started.", text)


def uncited(text: str) -> str:
    """A Draft whose every claim names no code."""
    text = re.sub(r"(?m)^  Code: .*$", "  Code: none", text)
    return re.sub(r"(?m)^  Shows: .*$", "  Shows: none", text)


class RunCountsTest(CycleTestCase):
    """Whole runs with the first batch's seven Drafts due, so each has two sessions: the package review's and the
    post Drafts'."""

    def setUp(self):
        super().setUp()
        fakes.set_window(self.repo, {"first_sitting": None, "slot": None})
        self.package = fakes.package_files(self.mandu)
        self.drafts = [str(self.workspace() / fakes.draft_path(day)) for day in range(1, 8)]

    def counted(self, session: str) -> dict:
        """One session's counts in the latest run's log record."""
        return self.run_record(session)["work"]

    def counts(self, session: str) -> list[str]:
        """The launcher's counts of one session in the run report's Sessions section, one to a line."""
        title = sessions.workflow(session).title
        own = self.report().split(f"### {title}\n", 1)[1].split("\n### ", 1)[0]
        return [
            line[2:] for line in own.splitlines() if line.startswith(("- Package files", "- Draft claims", "- Prop"))
        ]

    def totals(self) -> list[str]:
        section = self.report().split("### The run's totals\n", 1)[1].split("\n## ", 1)[0]
        return [line[2:] for line in section.splitlines() if line.startswith("- ")]

    def test_each_session_s_counts_are_of_that_session_alone_and_the_totals_are_the_run_s(self):
        review = [fakes.read_event(path) for path in self.package] + [fakes.edit_event("incoming/stale.md")]
        kit = [path for path in self.package if path.name in ("cadence-14-day.md", "angles.md", "ab-pairs.md")]
        drafting = [fakes.read_event(path) for path in kit] + [fakes.edit_event(*self.drafts)]
        writes = {fakes.draft_path(day): fakes.draft(day) for day in range(1, 8)}
        writes["review-queue/incoming/name-status-stale.md"] = fakes.PROPOSAL
        behavior = {
            "write": writes,
            "sessions": {"package-review": {"events": review}, "post-drafts": {"events": drafting}},
        }
        fakes.behave(self.codex_dir, behavior)
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        self.assertEqual(fakes.sessions_started(self.codex_dir), ["package-review", "post-drafts"])
        self.assertEqual(len(self.package), 16)
        # The package review's brief lists every package file, and its session read them all; the Drafts and the
        # proposal standing in incoming/ when it ended are counted to the session that wrote each.
        self.assertEqual(
            self.counted("package-review"),
            {
                "package_files_listed": 16,
                "package_files_read": 16,
                "package_files_not_read": [],
                "claims_with_code_location": 0,
                "claims_without_code_location": 0,
                "proposals_queued": 1,
            },
        )
        self.assertEqual(
            self.counts("package-review"),
            [
                f"Package files read: 16 of the 16 the brief listed, {FILES_RULE}.",
                f"{NONE_WRITTEN}.",
                "Proposals this session wrote to incoming/: 1 queued.",
            ],
        )
        # The post Drafts' brief lists only the package files the Product registry says post Drafts need.
        posts = self.counted("post-drafts")
        self.assertEqual((posts["claims_with_code_location"], posts["claims_without_code_location"]), (7, 0))
        self.assertEqual(posts["proposals_queued"], 0)
        self.assertLess(posts["package_files_listed"], 16)
        self.assertEqual(posts["package_files_read"], len(kit))
        self.assertIn(f"`{kit[0]}`", self.brief(session="post-drafts"))
        self.assertNotIn("07-thesis", self.brief(session="post-drafts"))
        self.assertEqual(
            self.counts("post-drafts")[1:],
            [
                f"{ALL_WRITTEN}: 7 listed, 7 name a code location and 0 name none.",
                "Proposals this session wrote to incoming/: 0 queued.",
            ],
        )
        time = next(
            line for line in self.report().splitlines() if line.startswith("- Agent time: ") and "limit," in line
        )
        self.assertRegex(
            time, r"^- Agent time: \d+ s of its 30 min limit, with `[\w.-]+` at `high` reasoning effort\.$"
        )
        totals = self.totals()
        self.assertEqual(
            totals[0],
            "Sessions: 2 ran of the 2 with work due; nothing was due for Filming, Beta Cohort recruiting, Listening,"
            " Outreach, Rejection reasons.",
        )
        self.assertRegex(totals[1], r"^Agent time: \d+ s of the 60 min that bounds all of a run's sessions together\.$")
        self.assertRegex(totals[2], r"^Approximate cost: about \$0\.01[67] at API prices, for 400,000 input tokens")
        self.assertTrue(totals[2].endswith(", over its 2 sessions."), totals[2])
        self.assertEqual(
            totals[3:],
            [
                "Draft claims in the 7 of 7 due Drafts the sessions of this run wrote or changed: 7 listed, 7 name a"
                " code location and 0 name none.",
                "Proposals the sessions of this run wrote to incoming/: 1 queued.",
            ],
        )

    def test_a_session_that_opens_few_files_and_says_it_finished_is_shown_for_what_it_did(self):
        # The shallow session of the investigation: one command prints every package file, most of it cut before the
        # model sees it, two files are read on their own, and the summary still ends `Session: complete`.
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
        fakes.behave(self.codex_dir, {"write": writes, "sessions": {"package-review": {"events": events}}})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        counted = self.counted("package-review")
        self.assertEqual((counted["package_files_read"], counted["package_files_listed"]), (2, 16))
        self.assertEqual(len(counted["package_files_not_read"]), 14)
        self.assertEqual((counted["claims_with_code_location"], counted["claims_without_code_location"]), (0, 0))
        text = self.report()
        self.assertIn(
            "- The Package review session's work, as the launcher counted it: 2 of 16 package files read, 1 proposal"
            " this session wrote to incoming/ queued, in ",
            text,
        )
        self.assertIn('Its agent\'s own word: "Session: complete".', text)
        self.assertEqual(
            self.counts("package-review"),
            [
                f"Package files read: 2 of the 16 the brief listed, {FILES_RULE}.",
                f"{NONE_WRITTEN}.",
                "Proposals this session wrote to incoming/: 1 queued.",
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
        counted = self.counted("post-drafts")
        self.assertEqual((counted["claims_with_code_location"], counted["claims_without_code_location"]), (0, 7))
        self.assertIn(f"{ALL_WRITTEN}: 7 listed, 0 name a code location and 7 name none.", self.counts("post-drafts"))
        self.assertIn(
            "0 of 7 Draft claims with a code location in the 7 of 7 due Drafts this session wrote or changed",
            self.report().split("## Sources")[0],
        )
        # The Draft check blocks them as it did before the counts existed, each naming its claim.
        self.assertIn("| Post Drafts | complete | 7 days: 7 blocked |", self.report())
        self.assertEqual(self.report().count("claim-unsupported:"), 7)

    def test_a_timed_out_session_s_partial_stream_is_still_counted(self):
        fakes.set_run(self.repo, "agent", {"time_limit_seconds": 2, "run_time_limit_seconds": 60})
        events = [fakes.read_event(path) for path in self.package[:3]]
        fakes.behave(self.codex_dir, {"sessions": {"package-review": {"hang": True, "events": events}}})
        try:
            code, out = self.run_cycle()
        finally:
            fakes.stop_leftovers(self.codex_dir)
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        self.assertEqual(self.counted("package-review")["package_files_read"], 3)
        self.assertIn("Its agent's own word: none; the agent left no summary.", self.report())

    def test_a_second_run_that_writes_nothing_has_no_draft_claims_to_count(self):
        writes = {fakes.draft_path(day): fakes.draft(day) for day in range(1, 8)}
        fakes.behave(self.codex_dir, {"write": writes})
        self.assertEqual(self.run_cycle()[0], 0)
        self.assertIn(f"{ALL_WRITTEN}: 7 listed, 7 name a code location and 0 name none.", self.counts("post-drafts"))
        # The second run's sessions open three files each, write nothing, and say they finished.
        fakes.behave(self.codex_dir, {"events": [fakes.read_event(path) for path in self.package[:3]]})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        counted = self.counted("post-drafts")
        self.assertEqual((counted["claims_with_code_location"], counted["claims_without_code_location"]), (0, 0))
        self.assertIn(f"{NONE_WRITTEN}.", self.counts("post-drafts"))
        text = self.report()
        self.assertIn(
            "- The Post Drafts session's work, as the launcher counted it: 3 of 11 package files read, none of the 7"
            " Drafts due written or changed, 0 proposals this session wrote to incoming/ queued, in ",
            text,
        )
        self.assertIn('Its agent\'s own word: "Session: complete".', text)
        self.assertNotIn("Draft claims with a code location", text)
        self.assertIn(
            "Draft claims: the sessions of this run wrote or changed none of the 7 Drafts due, so they have no Draft"
            " claims to count.",
            self.totals(),
        )

    def test_a_second_run_that_changes_one_draft_counts_that_one_only(self):
        writes = {fakes.draft_path(day): fakes.draft(day) for day in range(1, 8)}
        fakes.behave(self.codex_dir, {"write": writes})
        self.assertEqual(self.run_cycle()[0], 0)
        changed = uncited(fakes.draft(3, caption="The score dipped after a skipped day and kept its history."))
        fakes.behave(self.codex_dir, {"write": {fakes.draft_path(3): changed}})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        counted = self.counted("post-drafts")
        self.assertEqual((counted["claims_with_code_location"], counted["claims_without_code_location"]), (0, 1))
        self.assertIn(
            "Draft claims in the 1 of 7 due Drafts this session wrote or changed: 1 listed, 0 name a code location"
            " and 1 names none.",
            self.counts("post-drafts"),
        )

    def test_a_draft_another_session_changes_is_counted_as_that_session_s_too(self):
        # Every session has the same six areas, so a later one can change what an earlier one wrote before the
        # launcher has read it. The counts show it: each is of what that session wrote or changed, by fingerprint.
        fakes.set_run(self.repo, "outreach", {"creators": fakes.creators(fakes.KIT_CREATORS[:1])})
        changed = uncited(fakes.draft(3, caption="The score dipped after a skipped day and kept its history."))
        behavior = {
            "write": {fakes.draft_path(day): fakes.draft(day) for day in range(1, 8)},
            "sessions": {
                "outreach": {"write": {"drafts/messages/outreach/day-03-copy.md": "x", fakes.draft_path(3): changed}}
            },
        }
        fakes.behave(self.codex_dir, behavior)
        code, out = self.run_cycle()
        self.assertEqual(fakes.sessions_started(self.codex_dir), ["package-review", "post-drafts", "outreach"])
        self.assertEqual(self.counted("post-drafts")["claims_with_code_location"], 7)

    @unittest.skipIf(os.geteuid() == 0, "root can search any folder")
    def test_a_draft_folder_closed_before_a_session_starts_leaves_the_claims_uncounted_and_the_run_going(self):
        # An earlier run's Draft sits in a folder the launcher cannot search before the first session starts. Nothing
        # says whether that session wrote it, so its claims are not counted, nor are its proposals, which are told
        # apart by the same reading, and the run goes on as it would have: the session runs, the folder is restored
        # once it has ended, the next session's counts are made, and the Draft there is checked.
        earlier = self.workspace() / fakes.draft_path(1)
        earlier.parent.mkdir(parents=True)
        earlier.write_text(fakes.draft(1), encoding="utf-8")
        earlier.parent.chmod(0)
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.counts("package-review")[1:], [f"{line}." for line in UNCOUNTED])
        self.assertEqual(self.counts("post-drafts")[1], f"{NONE_WRITTEN}.")
        text = self.report()
        problems = text.partition("\n## Launcher problems\n")[2]
        self.assertRegex(problems, rf"- {UNCOUNTED_WHY} \(\[Errno 13\] Permission denied: '[^']*day-01\.md'\)")
        self.assertEqual(problems.count(UNCOUNTED_WHY), 1)
        self.assertIn("was left without its owner's read and write access, so the launcher restored it", problems)
        self.assertIn("Draft claims not counted, proposals not counted, in ", text.split("## Sources")[0])
        counted = self.counted("package-review")
        self.assertEqual((counted["claims_with_code_location"], counted["claims_without_code_location"]), (None,) * 2)
        self.assertEqual((counted["package_files_listed"], counted["proposals_queued"]), (16, None))
        # With no reading from before the run's first session, the run's totals are not counted either.
        self.assertIn("Draft claims: not counted; the launcher problems say why.", self.totals())
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
        self.assertIn("Proposals this session wrote to incoming/: 0 queued.", self.counts("package-review"))
        self.assertEqual(len(list((self.workspace() / "review-queue/incoming").iterdir())), count)
        queue.unlink()

    def queued_from(self, slug: str) -> list[str]:
        return [entry["id"] for entry in self.queue()["open"] if f"-{slug}" in entry["id"]]

    def test_proposals_an_earlier_run_left_are_queued_and_counted_as_no_session_s_of_this_run(self):
        self.leave_proposals()
        # The second run's sessions open three files each, write nothing, and say they finished.
        fakes.behave(self.codex_dir, {"events": [fakes.read_event(path) for path in self.package[:3]]})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        self.assertEqual(len(self.queued_from("stale-")), 5)
        for session in ("package-review", "post-drafts"):
            self.assertIn("Proposals this session wrote to incoming/: 0 queued.", self.counts(session))
            self.assertEqual(self.counted(session)["proposals_queued"], 0)
        self.assertIn(
            "Proposals the sessions of this run wrote to incoming/: 0 queued; 5 more queued in this run were left by"
            " an earlier run.",
            self.totals(),
        )
        # A later session's brief names what waits in incoming/, by file name alone.
        waiting = self.brief(session="post-drafts").split("## Items waiting in the incoming folder", 1)[1]
        self.assertIn("- `stale-1.md`: not taken in yet", waiting)
        self.assertNotIn("record fact 1 as cleared", waiting)

    def test_a_second_run_that_adds_one_proposal_beside_leftovers_counts_that_one(self):
        self.leave_proposals()
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        self.assertEqual((len(self.queued_from("stale-")), len(self.queued_from("name-status-stale"))), (5, 1))
        self.assertIn("Proposals this session wrote to incoming/: 1 queued.", self.counts("package-review"))
        self.assertIn(
            "Proposals the sessions of this run wrote to incoming/: 1 queued; 5 more queued in this run were left by"
            " an earlier run.",
            self.totals(),
        )
        self.assertIn("1 proposal this session wrote to incoming/ queued, in ", self.report().split("## Sources")[0])
        self.assertEqual(self.counted("package-review")["proposals_queued"], 1)
        # The post Drafts session, which comes after, sees the review's proposal waiting beside the leftovers.
        waiting = self.brief(session="post-drafts").split("## Items waiting in the incoming folder", 1)[1]
        self.assertIn("- `name-status-stale.md`: not taken in yet", waiting)
        self.assertNotIn("name-status-stale.md", self.brief(session="package-review"))

    @unittest.skipIf(os.geteuid() == 0, "root can list any folder")
    def test_an_incoming_folder_unreadable_before_a_session_starts_leaves_the_proposals_uncounted_and_the_run_going(
        self,
    ):
        # An earlier run's proposal sits in an incoming/ the launcher cannot list before the first session starts.
        # Nothing says whether that session wrote it, so its proposals are not counted, and the run goes on as it
        # would have: the session runs, the folder is restored once it has ended, and everything in it is queued.
        incoming = self.workspace() / "review-queue/incoming"
        incoming.mkdir()
        (incoming / "left-behind.md").write_text(fakes.proposal(title="record the launch date"), encoding="utf-8")
        incoming.chmod(0o300)
        fakes.behave(self.codex_dir, {"write": {"review-queue/incoming/name-status-stale.md": fakes.PROPOSAL}})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.counts("package-review")[1:], [f"{line}." for line in UNCOUNTED])
        text = self.report()
        problems = text.partition("\n## Launcher problems\n")[2]
        self.assertRegex(problems, rf"- {UNCOUNTED_WHY} \(\[Errno 13\] Permission denied: '[^']*incoming'\)")
        self.assertIn(
            "- `workspace/review-queue/incoming` was left without its owner's read and write access, so the launcher"
            " restored it",
            problems,
        )
        self.assertIn("Draft claims not counted, proposals not counted, in ", text.split("## Sources")[0])
        counted = self.counted("package-review")
        self.assertEqual((counted["package_files_listed"], counted["proposals_queued"]), (16, None))
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
        self.assertIn("- the Package review session's work could not be counted (the event stream went away)", text)
        self.assertIn("- the Post Drafts session's work could not be counted (the event stream went away)", text)
        self.assertIn("The launcher counted nothing", text)
        self.assertIn("20261011-name-status-stale", [entry["id"] for entry in self.queue()["open"]])


if __name__ == "__main__":
    unittest.main()
