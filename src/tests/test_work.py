"""What the launcher counts of the agent's session, from synthetic event streams in Codex's format, and how the run
report sets those counts beside the agent's own word."""

from __future__ import annotations

import json
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

    def session(self, *lines: str, checkout: Path | None = None) -> work.Session:
        return work.read_session(fakes.write_events(self.events, *lines), SHOWN, checkout)

    def test_a_session_is_its_finished_commands_and_edits_whatever_else_the_stream_holds(self):
        started = json.dumps({"type": "item.started", "item": {"type": "command_execution", "command": "cat a"}})
        message = json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "Reading."}})
        session = self.session(
            started,
            fakes.command_event("cat brief.md", "the brief\n"),
            message,
            fakes.command_event("rg -n missing package", "", exit_code=1),
            fakes.command_event("git -C /code/RepToday show abc:App/Ready.swift", "struct Ready {}\n"),
            fakes.command_event("/usr/bin/python3 /repo/src/bin/gr0wthlab check-drafts --run R", "day 1: blocked\n", 1),
            fakes.command_event("/usr/bin/python3 '/repo/src/bin/gr0wthlab' check-incoming", "no items\n"),
            fakes.command_event('A=/m /usr/bin/python3 "/repo/src/bin/gr0wthlab" check-beta-drafts --run R', "", 1),
            fakes.command_event("cat /repo/src/bin/gr0wthlab; rg check-drafts /repo/docs", "the entry point\n"),
            fakes.edit_event("/repo/workspace/drafts/posts/window-1/day-01.md"),
            json.dumps({"type": "turn.completed", "usage": {"output_tokens": 9}}),
            '{"type": "item.completed", "item": {"type": "command_execution", "comm',
            checkout=Path("/code/RepToday"),
        )
        self.assertEqual((session.commands, session.edits, session.cut), (7, 1, 0))
        self.assertEqual((session.code_reads, session.checks), (1, 3))
        self.assertIn("struct Ready {}", session.shown)

    def test_no_stream_is_no_session_and_an_empty_one_is_a_session_that_did_nothing(self):
        self.assertIsNone(work.read_session(self.root / "absent.jsonl", SHOWN))
        self.assertEqual(self.session(), work.Session())

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
        session = self.session(fakes.command_event("seq 1 4000", output), fakes.command_event("true", output[:SHOWN]))
        self.assertEqual((session.commands, session.cut), (2, 1))

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
        self.assertEqual(session.cut, 1)
        compared, missing = work.files_read(session, self.files)
        self.assertEqual((compared, missing), (5, ["package/charlie.md", "package/delta.md", "package/echo.md"]))

    def test_a_file_that_cannot_be_told_apart_is_left_out_of_the_count(self):
        (self.root / "package" / "empty.md").write_text("\n\n", encoding="utf-8")
        files = dict(self.files, **{"package/empty.md": self.root / "package" / "empty.md"})
        files["package/gone.md"] = self.root / "package" / "gone.md"
        session = self.session(fakes.read_event(*self.files.values()))
        self.assertEqual(work.files_read(session, files), (5, []))

    def test_a_short_file_is_told_by_every_line_it_has(self):
        path = self.root / "package" / "rules.json"
        path.write_text('{\n  "max": 12,\n  "ban": ["grind"]\n}\n', encoding="utf-8")
        files = {"package/rules.json": path}
        self.assertEqual(work.files_read(self.session(fakes.read_event(path)), files), (1, []))
        self.assertEqual(
            work.files_read(self.session(fakes.command_event("true", "{\n")), files), (1, ["package/rules.json"])
        )


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
            work.Session(commands=70, cut=12, code_reads=18, checks=6, edits=9),
            files_listed=24,
            files_not_read=("gtm/a.md", "gtm/b.md"),
            days_due=7,
            drafts_present=7,
            drafts_written=6,
            claims=10,
            claims_cited=8,
            claims_found=7,
            queued=5,
            proposals=4,
            set_aside=1,
            shown_chars=SHOWN,
        )
        self.assertEqual(
            work.count_lines(counted),
            [
                "Commands run: 70; 18 of them read the Product's code, 6 ran one of the launcher's checks, and 12"
                " returned more than the 40,000 characters Codex shows the model of one command's output, so the middle"
                " of that output was cut.",
                "Package files read: 22 of the 24 the brief listed, counting a file as read when at least half of its"
                " lines came back in output the model was shown. Not read: `gtm/a.md`, `gtm/b.md`.",
                "File edits: 9.",
                "Post Drafts: 7 of the 7 days due have a Draft; 6 written or changed this run.",
                "Draft claims: 10 listed; 8 name a code location, where the launcher found the quoted code for 7; 2"
                " name none.",
                "Review Queue items the agent wrote: 5 queued, 4 package-change proposals among them; 1 set aside.",
            ],
        )
        self.assertEqual(
            work.summary(counted),
            "70 commands, 22 of 24 package files read, 6 of 7 due Drafts written, 8 of 10 Draft claims with a code"
            " location, 4 proposals queued",
        )
        record = counted.as_json()
        self.assertEqual((record["claims_with_code_location"], record["claims_without_code_location"]), (8, 2))
        self.assertEqual((record["package_files_read"], record["package_files_listed"]), (22, 24))

    def test_many_unread_files_are_counted_and_not_named(self):
        unread = tuple(f"gtm/{number}.md" for number in range(work.NAMED_AT_MOST + 1))
        lines = work.count_lines(work.Work(work.Session(commands=8), files_listed=24, files_not_read=unread))
        self.assertTrue(lines[1].startswith("Package files read: 17 of the 24 the brief listed"), lines[1])
        self.assertNotIn("Not read", lines[1])

    def test_a_run_with_no_stream_or_no_day_due_says_so(self):
        lines = work.count_lines(work.Work(None, files_listed=24))
        self.assertEqual(lines[0], "Commands run: none recorded; the agent left no record of a session to count from.")
        self.assertNotIn("Package files read", " ".join(lines))
        self.assertIn("Post Drafts: no calendar day was due.", lines)
        self.assertIsNone(work.Work(None, files_listed=24).as_json()["package_files_read"])
        self.assertEqual(work.summary(work.Work(None)), "0 proposals queued")

    def test_the_report_names_the_launcher_s_counts_and_the_agent_s_word_apart(self):
        counted = work.Work(work.Session(commands=8, edits=1), files_listed=24, files_not_read=("a",) * 18)
        text = report.render_report(self.state(counted))
        section = text.split("## Agent's work\n", 1)[1].split("\n## Agent\n", 1)[0]
        launcher, agent = section.split("The agent's own word, which the launcher does not check:")
        self.assertIn("Counted by the launcher from Codex's record of the session", launcher)
        self.assertIn("None of these comes from what the agent says of itself", launcher)
        self.assertIn(
            "- Agent time: 8 min 21 s of its 30 min limit, with `gpt-6-luna` at `high` reasoning effort.", launcher
        )
        self.assertIn("- Commands run: 8;", launcher)
        self.assertIn("- Package files read: 6 of the 24 the brief listed", launcher)
        self.assertNotIn("Review:", launcher)
        self.assertEqual(agent.strip(), '- "Review: complete"')
        self.assertIn(
            "- The agent's work, as the launcher counted it: 8 commands, 6 of 24 package files read, 0 proposals"
            ' queued, in 8 min 21 s of agent time. The agent\'s own word: "Review: complete".',
            text.split("## Sources")[0],
        )

    def test_the_agent_s_word_is_quoted_as_it_ended_or_named_as_missing(self):
        incomplete = self.state(work.Work(work.Session()), "Stopped.\n\nReview: incomplete: pass 2, out of time.\n")
        self.assertEqual(report.review_word(incomplete), '"Review: incomplete: pass 2, out of time."')
        other = self.state(work.Work(work.Session()), "All done here, nothing else to add " + "x" * 400)
        self.assertRegex(
            report.review_word(other),
            r'^its summary ends with neither `Review: complete` nor `Review: incomplete`, but with "All.*x\.\.\."$',
        )
        self.assertLess(len(report.review_word(other)), 400)
        self.assertEqual(
            report.review_word(self.state(work.Work(work.Session()), "")), "none; the agent left no summary"
        )

    def test_a_run_whose_agent_never_started_counts_nothing(self):
        state = self.state(None, "")
        state.agent = {"exit_code": 2, "agent_started": False, "error": "codex executable not found"}
        text = report.render_report(state)
        self.assertIn("## Agent's work\n\nThe launcher counted nothing: the agent did not start", text)
        self.assertNotIn("as the launcher counted it", text)

    def test_reasoning_tokens_are_shown_as_part_of_the_output_tokens_the_cost_prices(self):
        usage = {"input_tokens": 1000000, "cached_input_tokens": 900000, "output_tokens": 40000}
        usage["reasoning_output_tokens"] = 18000
        prices = {"input": 0.1, "cached_input": 0.01, "cache_write_input": 0.125, "output": 0.5}
        state = self.state(work.Work(work.Session()))
        state.usage, state.cost = usage, report.cost(usage, prices)
        # 100,000 fresh input, 900,000 cached, and all 40,000 output tokens, reasoning among them.
        self.assertAlmostEqual(state.cost, (100000 * 0.1 + 900000 * 0.01 + 40000 * 0.5) / 1_000_000)
        self.assertEqual(
            report.cost_line(state),
            "Approximate cost: about $0.039 at API prices, for 1,000,000 input tokens (900,000 cached) and 40,000"
            " output tokens (18,000 of them reasoning).",
        )
        with tempfile.TemporaryDirectory() as directory:
            turn = json.dumps({"type": "turn.completed", "usage": usage})
            events = Path(directory) / "events.jsonl"
            events.write_text(f"{turn}\n{turn}\n", encoding="utf-8")
            self.assertEqual(report.token_usage(events)["reasoning_output_tokens"], 36000)
            self.assertEqual(report.token_usage(events)["output_tokens"], 80000)


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

    def agents_work(self) -> str:
        return self.report().split("## Agent's work\n", 1)[1].split("\n## Agent\n", 1)[0]

    def test_a_thorough_session_s_counts_match_what_it_did(self):
        code_show = f"git -C {self.code} show HEAD:Engine/ConsistencyScore.swift"
        events = [fakes.read_event(path) for path in self.package]
        events += [fakes.command_event(code_show, "value = max(floorValue, value - missPenalty)\n")] * 3
        events += [fakes.edit_event(*self.drafts), fakes.edit_event("incoming/name-status-stale.md")]
        events.append(
            fakes.command_event(f"/usr/bin/python3 {self.repo}/src/bin/gr0wthlab check-drafts --run R", "", 1)
        )
        writes = {fakes.draft_path(day): fakes.draft(day) for day in range(1, 8)}
        writes["review-queue/incoming/name-status-stale.md"] = fakes.PROPOSAL
        fakes.behave(self.codex_dir, {"write": writes, "events": events})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        counted = self.record()
        self.assertEqual(len(self.package), 14)
        self.assertEqual((counted["commands"], counted["file_edits"]), (18, 2))
        self.assertEqual((counted["commands_reading_product_code"], counted["commands_running_checks"]), (3, 1))
        self.assertEqual((counted["package_files_read"], counted["package_files_listed"]), (14, 14))
        self.assertEqual(counted["package_files_not_read"], [])
        self.assertEqual((counted["draft_days_due"], counted["drafts_present"], counted["drafts_written"]), (7, 7, 7))
        self.assertEqual((counted["claims"], counted["claims_with_code_location"]), (7, 7))
        self.assertEqual((counted["claims_found_at_location"], counted["claims_without_code_location"]), (7, 0))
        self.assertEqual((counted["items_queued"], counted["proposals_queued"], counted["items_set_aside"]), (1, 1, 0))
        section = self.agents_work()
        self.assertIn(
            "- Commands run: 18; 3 of them read the Product's code, 1 ran one of the launcher's checks", section
        )
        self.assertIn("- Package files read: 14 of the 14 the brief listed", section)
        self.assertIn("- Post Drafts: 7 of the 7 days due have a Draft; 7 written or changed this run.", section)
        self.assertIn(
            "- Draft claims: 7 listed; 7 name a code location, where the launcher found the quoted code for 7", section
        )
        self.assertIn("- Review Queue items the agent wrote: 1 queued, 1 package-change proposal among them", section)

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
        self.assertEqual((counted["commands"], counted["commands_output_cut"]), (3, 1))
        self.assertEqual((counted["package_files_read"], counted["package_files_listed"]), (2, 14))
        self.assertEqual(len(counted["package_files_not_read"]), 12)
        self.assertEqual((counted["drafts_present"], counted["drafts_written"], counted["claims"]), (0, 0, 0))
        text = self.report()
        self.assertIn(
            "- The agent's work, as the launcher counted it: 3 commands, 2 of 14 package files read, 0 of 7 due Drafts"
            " written, 1 proposal queued, in ",
            text,
        )
        self.assertIn('The agent\'s own word: "Review: complete".', text)
        section = self.agents_work()
        self.assertIn("1 returned more than the 40,000 characters Codex shows the model", section)
        self.assertIn("- Package files read: 2 of the 14 the brief listed", section)
        self.assertIn("- Post Drafts: 0 of the 7 days due have a Draft; 0 written or changed this run.", section)
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
        self.assertEqual((counted["claims"], counted["claims_with_code_location"]), (7, 0))
        self.assertEqual((counted["claims_without_code_location"], counted["claims_found_at_location"]), (7, 0))
        self.assertEqual((counted["commands"], counted["commands_reading_product_code"]), (0, 0))
        section = self.agents_work()
        self.assertIn(
            "- Draft claims: 7 listed; 0 name a code location, where the launcher found the quoted code for 0; 7 name"
            " none.",
            section,
        )
        self.assertIn("0 of 7 Draft claims with a code location", self.report().split("## Sources")[0])
        # The Draft check blocks them as it did before the counts existed, each naming its claim.
        self.assertIn("| Post Drafts | complete | 7 days: 7 blocked |", self.report())
        self.assertEqual(self.report().count("claim-unsupported:"), 7)

    def test_a_cited_location_that_does_not_hold_the_quote_is_not_counted_as_found(self):
        writes = {fakes.draft_path(day): fakes.draft(day) for day in range(1, 8)}
        writes[fakes.draft_path(2)] = writes[fakes.draft_path(2)].replace(
            "ConsistencyScore.swift:6-7", "Nowhere.swift:1"
        )
        fakes.behave(self.codex_dir, {"write": writes})
        code, out = self.run_cycle()
        self.assertEqual(code, 0, out)
        counted = self.record()
        self.assertEqual((counted["claims"], counted["claims_with_code_location"]), (7, 7))
        self.assertEqual(counted["claims_found_at_location"], 6)

    def test_a_draft_left_from_an_earlier_run_is_present_and_not_written_again(self):
        writes = {fakes.draft_path(day): fakes.draft(day) for day in range(1, 8)}
        fakes.behave(self.codex_dir, {"write": writes})
        self.assertEqual(self.run_cycle()[0], 0)
        changed = fakes.draft(3, caption="The score dipped after a skipped day and kept its history.")
        fakes.behave(self.codex_dir, {"write": {fakes.draft_path(3): changed}})
        self.assertEqual(self.run_cycle()[0], 0)
        counted = json.loads(sorted(self.logs.glob("*-on-demand-*.json"))[-1].read_text(encoding="utf-8"))["work"]
        self.assertEqual((counted["draft_days_due"], counted["drafts_present"], counted["drafts_written"]), (7, 7, 1))

    def test_a_timed_out_agent_s_partial_stream_is_still_counted(self):
        fakes.set_run(self.repo, "agent", {"time_limit_seconds": 2})
        events = [fakes.read_event(path) for path in self.package[:3]]
        fakes.behave(self.codex_dir, {"hang": True, "events": events})
        try:
            code, out = self.run_cycle()
        finally:
            fakes.stop_leftovers(self.codex_dir)
        self.assertEqual(code, cycle.EXIT_STOPPED, out)
        counted = self.record()
        self.assertEqual((counted["commands"], counted["package_files_read"]), (3, 3))
        self.assertIn("The agent's own word: none; the agent left no summary.", self.report())

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
