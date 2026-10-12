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

from gr0wthlab import cycle, report, work
from gr0wthlab.report import RunState
from tests import fakes
from tests.test_cycle import CycleTestCase

SHOWN = 40000
FILES_RULE = "counting a file as read when at least half of its lines came back in output the model was shown"


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

    def test_every_count_says_what_it_counts(self):
        counted = work.Work(
            files_listed=24, files_not_read=("gtm/a.md", "gtm/b.md"), claims=10, claims_cited=8, proposals=4
        )
        self.assertEqual(
            work.count_lines(counted),
            [
                f"Package files read: 22 of the 24 the brief listed, {FILES_RULE}. Not read: `gtm/a.md`, `gtm/b.md`.",
                "Draft claims: 10 listed; 8 name a code location and 2 name none.",
                "Proposals queued: 4 package-change proposals the agent wrote.",
            ],
        )
        self.assertEqual(
            work.summary(counted),
            "22 of 24 package files read, 8 of 10 Draft claims with a code location, 4 proposals queued",
        )
        self.assertEqual(
            counted.as_json(),
            {
                "package_files_listed": 24,
                "package_files_read": 22,
                "package_files_not_read": ["gtm/a.md", "gtm/b.md"],
                "claims_with_code_location": 8,
                "claims_without_code_location": 2,
                "proposals_queued": 4,
            },
        )

    def test_many_unread_files_are_counted_and_not_named(self):
        unread = tuple(f"gtm/{number}.md" for number in range(work.NAMED_AT_MOST + 1))
        lines = work.count_lines(work.Work(files_listed=24, files_not_read=unread))
        self.assertEqual(lines[0], f"Package files read: 17 of the 24 the brief listed, {FILES_RULE}.")

    def test_a_run_with_no_stream_or_no_claim_says_so(self):
        counted = work.Work(files_listed=24)
        self.assertEqual(
            work.count_lines(counted),
            [
                "Package files read: not counted; the agent left no record of a session to count from.",
                "Draft claims: none listed.",
                "Proposals queued: 0 package-change proposals the agent wrote.",
            ],
        )
        self.assertIsNone(counted.as_json()["package_files_read"])
        self.assertIsNone(counted.as_json()["package_files_not_read"])
        self.assertEqual(work.summary(counted), "0 proposals queued")

    def test_the_report_names_the_launcher_s_counts_and_the_agent_s_word_apart(self):
        counted = work.Work(files_listed=24, files_not_read=("a",) * 18, proposals=1)
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
                "- Draft claims: none listed.",
                "- Proposals queued: 1 package-change proposal the agent wrote.",
            ],
        )
        self.assertNotIn("Review:", launcher)
        self.assertEqual(agent.strip(), '- "Review: complete"')
        self.assertIn(
            "- The agent's work, as the launcher counted it: 6 of 24 package files read, 1 proposal queued, in 8 min"
            ' 21 s of agent time. The agent\'s own word: "Review: complete".',
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
        return json.loads(next(self.logs.glob("*-on-demand-*.json")).read_text(encoding="utf-8"))["work"]

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
                "- Draft claims: 7 listed; 7 name a code location and 0 name none.",
                "- Proposals queued: 1 package-change proposal the agent wrote.",
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
            "- The agent's work, as the launcher counted it: 2 of 14 package files read, 1 proposal queued, in ", text
        )
        self.assertIn('The agent\'s own word: "Review: complete".', text)
        self.assertEqual(
            self.counts()[1:],
            [
                f"- Package files read: 2 of the 14 the brief listed, {FILES_RULE}.",
                "- Draft claims: none listed.",
                "- Proposals queued: 1 package-change proposal the agent wrote.",
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
        self.assertIn("- Draft claims: 7 listed; 0 name a code location and 7 name none.", self.counts())
        self.assertIn("0 of 7 Draft claims with a code location", self.report().split("## Sources")[0])
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

    @unittest.skipIf(os.geteuid() == 0, "root can search any folder")
    def test_a_draft_folder_closed_before_the_agent_starts_does_not_stop_the_run(self):
        # No count reads workspace/ before the agent starts: a folder left closed is restored once the agent has
        # ended, as it was before the counts existed, and the run reports.
        folder = (self.workspace() / fakes.draft_path(1)).parent
        folder.mkdir(parents=True)
        folder.chmod(0)
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        self.assertIn("was left without its owner's read and write access, so the launcher restored it", self.report())
        self.assertEqual(self.record()["proposals_queued"], 0)

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
