"""The run report's facts: when a scheduled run was due, whether it was late, and what it cost."""

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from gr0wthlab import exchange, package, report
from gr0wthlab.queue import SetAside
from gr0wthlab.report import RunState, SourceLine


def local(*args):
    """A time on the Mac's wall clock, as an aware datetime."""
    return datetime(*args).astimezone()


class DueTimeTest(unittest.TestCase):
    def test_weekly_due_time_is_the_latest_at_or_before_the_start(self):
        sunday = local(2026, 10, 11, 16, 5)
        self.assertEqual(report.due_time(sunday, ("sunday", "16:00")), datetime(2026, 10, 11, 16, 0))
        self.assertEqual(report.due_time(local(2026, 10, 11, 15, 59), ("sunday", "16:00")), datetime(2026, 10, 4, 16))
        self.assertEqual(report.due_time(local(2026, 10, 13, 9, 0), ("sunday", "16:00")), datetime(2026, 10, 11, 16))
        self.assertEqual(
            report.due_time(sunday, ("sunday", "16:00"), "2026-10-11T15:30"), datetime(2026, 10, 11, 15, 30)
        )

    def test_late_beyond_the_allowance(self):
        state = RunState("R", "scheduled", local(2026, 10, 11, 16, 14), "i.md", due=datetime(2026, 10, 11, 16))
        self.assertFalse(state.late)
        self.assertIn("started on time", report.start_line(state))
        state.started = local(2026, 10, 12, 8, 30)
        self.assertTrue(state.late)
        self.assertIn("16 h 30 min after its time", report.start_line(state))
        self.assertIn("asleep or off", report.start_line(state))
        state.started = local(2026, 10, 15, 8, 30)
        self.assertIn("3 d 16 h 30 min", report.start_line(state))

    def test_on_demand_runs_are_never_late(self):
        state = RunState("R", "on-demand", local(2026, 10, 12, 8, 30), "i.md")
        self.assertFalse(state.late)
        self.assertTrue(report.start_line(state).startswith("On demand, started Monday 2026-10-12 08:30"))


class CostTest(unittest.TestCase):
    def test_usage_is_summed_over_every_turn(self):
        with tempfile.TemporaryDirectory() as directory:
            events = Path(directory) / "events.jsonl"
            turn = {"input_tokens": 100, "cached_input_tokens": 60, "cache_write_input_tokens": 10, "output_tokens": 7}
            events.write_text(
                "\n".join(
                    [
                        json.dumps({"type": "thread.started"}),
                        json.dumps({"type": "turn.completed", "usage": turn}),
                        "not json",
                        json.dumps({"type": "turn.completed", "usage": dict(turn, output_tokens=3)}),
                    ]
                ),
                encoding="utf-8",
            )
            usage = report.token_usage(events)
            self.assertEqual(usage["input_tokens"], 200)
            self.assertEqual(usage["output_tokens"], 10)
            self.assertIsNone(report.token_usage(Path(directory) / "absent.jsonl"))
            events.write_text(json.dumps({"type": "turn.started"}), encoding="utf-8")
            self.assertIsNone(report.token_usage(events))

    def test_cost_prices_fresh_cached_written_and_output_tokens(self):
        prices = {"input": 0.1, "cached_input": 0.01, "cache_write_input": 0.125, "output": 0.5}
        usage = {
            "input_tokens": 1_000_000,
            "cached_input_tokens": 600_000,
            "cache_write_input_tokens": 100_000,
            "output_tokens": 20_000,
        }
        expected = 0.3 * 0.1 + 0.6 * 0.01 + 0.1 * 0.125 + 0.02 * 0.5
        self.assertAlmostEqual(report.cost(usage, prices), expected)

    def test_the_report_says_when_the_cost_is_unknown(self):
        state = RunState("R", "on-demand", local(2026, 10, 11, 16), "i.md")
        self.assertIn("unknown", report.cost_line(state))


class NoticeTest(unittest.TestCase):
    def state(self):
        state = RunState("R", "on-demand", local(2026, 10, 11, 16), "i.md")
        state.agent = {"agent_started": True, "exit_code": 0}
        state.review = report.REVIEW_COMPLETE
        return state

    def test_a_clean_run_has_no_notice(self):
        self.assertIsNone(report.problems_notice(self.state(), "run-reports/R.md"))

    def test_a_review_the_agent_did_not_finish_is_a_problem(self):
        state = self.state()
        state.review = "Review: incomplete: the rules pass is unfinished."
        title, body, _, _ = report.problems_notice(state, "run-reports/R.md")
        self.assertEqual(title, "Notice: the package review was not finished on 2026-10-11")
        self.assertTrue(
            body.startswith(
                "The Marketing Engineer did not finish reviewing the Go-To-Market Package (the rules pass is"
                " unfinished), so a contradiction"
            ),
            body,
        )

    def test_a_review_the_agent_never_confirmed_finishing_says_only_that(self):
        state = self.state()
        state.review = "I traced every outcome."
        title, body, _, _ = report.problems_notice(state, "run-reports/R.md")
        self.assertEqual(title, "Notice: the package review was not confirmed finished on 2026-10-11")
        self.assertTrue(body.startswith("The Marketing Engineer did not confirm that it finished every pass"), body)
        self.assertNotIn("Review: complete", body)

    def test_a_failed_source_names_what_it_leaves_incomplete(self):
        state = self.state()
        state.sources.append(
            SourceLine("RepToday package: `a.md`", package.FAILED, "missing.", ("Package review", "Post Drafts"))
        )
        title, body, touches, evidence = report.problems_notice(state, "run-reports/R.md")
        self.assertEqual(title, "Notice: 1 source could not be read on 2026-10-11")
        self.assertIn("- RepToday package: `a.md`: missing. Incomplete: Package review, Post Drafts.", body)
        self.assertIn("`run-reports/R.md`", evidence)

    def test_an_agent_that_never_started_is_a_problem(self):
        state = self.state()
        state.agent = {"agent_started": False, "exit_code": 3, "error": None}
        state.problems.append("the ledger could not be read")
        title, body, _, _ = report.problems_notice(state, "run-reports/R.md")
        self.assertEqual(title, "Notice: the run on 2026-10-11 had 2 problems")
        self.assertIn("The agent did not start", body)

    def test_a_notice_about_several_kinds_of_problem_counts_every_problem(self):
        state = self.state()
        state.review = "Review: incomplete: the rules pass is unfinished"
        for name in ("a.md", "b.md", "c.json"):
            state.sources.append(SourceLine(f"RepToday package: `{name}`", package.FAILED, "missing.", ()))
        title, _, _, _ = report.problems_notice(state, "run-reports/R.md")
        self.assertEqual(title, "Notice: the run on 2026-10-11 had 4 problems")

    def test_a_notice_stays_a_valid_item_however_many_problems_it_lists(self):
        state = self.state()
        state.problems = [f"problem {number}: " + "x" * 100 for number in range(500)]
        state.set_aside = [SetAside("odd\n# name.md", "", ("name it <slug>.md",))]
        title, body, touches, evidence = report.problems_notice(state, "run-reports/R.md")
        self.assertIn("- And more: the run report lists every problem.", body)
        self.assertIn("- `odd # name.md`: name it <slug>.md", body)
        fields = {"exchange": str(exchange.EXCHANGE_VERSION), "id": "20261011-notice-run-problems", "kind": "notice"}
        text = exchange.render_item(fields, title, body, touches, evidence)
        self.assertEqual(exchange.check_item(text, [], published=True).problems, [])

    def test_the_report_lists_every_source_and_output(self):
        state = self.state()
        state.sources = [SourceLine("YouTube results", report.SKIPPED, "not connected until US-ME11")]
        state.outputs = [["Weekly Read memo", report.NOT_BUILT, "US-ME12"]]
        text = report.render_report(state)
        self.assertIn("| YouTube results | skipped | not connected until US-ME11 |", text)
        self.assertIn("| Weekly Read memo | not built yet | US-ME12 |", text)
        self.assertIn("1 skipped", text)
        self.assertTrue(text.startswith("# Run report: R\n\n## Summary\n"))


class NextDueTest(unittest.TestCase):
    def test_the_next_weekly_time_after_a_run_with_its_offset(self):
        weekly = ("sunday", "16:00")
        for finished, due in (
            (local(2026, 10, 11, 16, 40), local(2026, 10, 18, 16)),
            (local(2026, 10, 11, 15, 0), local(2026, 10, 11, 16)),
            (local(2026, 10, 14, 9, 0), local(2026, 10, 18, 16)),
            (local(2026, 10, 30, 16, 40), local(2026, 11, 1, 16)),
        ):
            with self.subTest(finished=finished):
                next_run = report.next_due(finished, weekly)
                self.assertIsNotNone(next_run.utcoffset())
                self.assertEqual(next_run, due)
                self.assertEqual(report.wall_clock(next_run), datetime(due.year, due.month, due.day, 16, 0))


class DurationTest(unittest.TestCase):
    def test_duration(self):
        self.assertEqual(report.duration(timedelta(minutes=5)), "5 min")
        self.assertEqual(report.duration(timedelta(hours=2, minutes=1)), "2 h 1 min")


if __name__ == "__main__":
    unittest.main()
