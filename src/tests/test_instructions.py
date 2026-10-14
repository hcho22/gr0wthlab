"""US-ME16 and FR-14: an execution reason may change the agent's Instructions only through the workflow's example set,
a kept change is shown to the Founder as a notice that can undo it, and a strategy reason never changes them.

The whole runs use the stand-in agent (fakes.install_codex) for every session, the examples' own included: each
example runs in a lab of its own, through the same cycle, and the stand-in writes there what a test tells the
post-Draft session to write, or, where the Instructions under test hold a marker, what the test says an agent that
follows them would write (fakes: when_instructions).
"""

import json
import os
import shutil
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest import mock

from gr0wthlab import boundary, codex, examples, instructions, launcher, learning, probe, settings
from gr0wthlab.areas import Store
from gr0wthlab.boundary import ConfigError
from gr0wthlab.queue import Ledger
from tests import fakes
from tests.test_boundary import CONFIG, REGISTRY
from tests.test_work_cycle import WorkCycleTestCase

WEEK = timedelta(days=7)
DAY_1, DAY_3 = "20261011-post-w1-day-01", "20261011-post-w1-day-03"
LONG = "The captions run too long to read in the first seconds."
WRONG_PERSON = "This speaks to gym regulars, not to people who lost the routine."
ADDED = "- Keep each caption line under twelve words: the Founder reads the first seconds only."
WORSE = "- Name the app's ranking among fitness apps in every caption."
# The post-Draft example set, cut to two of its re-run examples for these runs: day 3 and day 1, each one Draft.
KEPT_EXAMPLES = (1, 2)


def reason(item, words, code="", workflow="post-drafts", decided_at="2026-10-11T19:42:00-07:00", answer=None):
    return learning.Reason(item, workflow, words, decided_at, code, "why", "run", instructions=answer or {})


class CheckTest(WorkCycleTestCase):
    """What the launcher refuses of a proposed change, before any example is run."""

    def setUp(self):
        super().setUp()
        self.in_force = (fakes.REPO / "ledger/instructions/post-drafts.md").read_text(encoding="utf-8")
        self.found = [reason(DAY_1, LONG, "length"), reason(DAY_3, WRONG_PERSON, "fit")]
        self.offer = instructions.Offer("post-drafts", (DAY_1,))

    def proposal(self, text=None, reasons=DAY_1, summary="Shorter caption lines.", workflow="post-drafts"):
        body = self.in_force + ADDED + "\n" if text is None else text
        source = f"---\nworkflow: {workflow}\nreasons: {reasons}\nsummary: {summary}\n---\n\n{body}"
        return instructions.parse(source, f"{workflow}.md")

    def problems(self, proposal, package=None, chosen="offer"):
        chosen = self.offer if chosen == "offer" else chosen
        return instructions.check(proposal, chosen, "why", self.found, self.in_force, package or {})

    def test_a_change_from_an_execution_reason_offered_this_run_passes(self):
        proposal, problems = self.proposal()
        self.assertEqual(problems, [])
        self.assertEqual(proposal.reasons, (DAY_1,))
        self.assertEqual(proposal.text, self.in_force + ADDED + "\n")
        self.assertEqual(self.problems(proposal), [])

    def test_a_strategy_reason_can_never_be_cited(self):
        offer = instructions.Offer("post-drafts", (DAY_1, DAY_3))
        proposal, _ = self.proposal(reasons=f"{DAY_1}, {DAY_3}")
        self.assertEqual(
            self.problems(proposal, chosen=offer),
            [f"`{DAY_3}` is coded `fit`, a strategy code, which never changes Instructions"],
        )

    def test_a_reason_not_offered_this_run_or_with_no_code_is_refused(self):
        self.found.append(reason("20261011-post-w1-day-04", "Too wordy.", ""))
        offer = instructions.Offer("post-drafts", (DAY_1, "20261011-post-w1-day-04"))
        proposal, _ = self.proposal(reasons="20261011-post-w1-day-04, 20261011-unknown")
        self.assertEqual(
            self.problems(proposal, chosen=offer),
            [
                "`20261011-post-w1-day-04` has no accepted execution code",
                "`20261011-unknown` is no rejection reason this run offers for a change",
            ],
        )

    def test_only_the_offered_workflow_may_change_and_only_when_one_is_offered(self):
        proposal, _ = self.proposal(text="# Outreach\n", workflow="outreach")
        self.assertEqual(self.problems(proposal), ["this run offers a change to the Post Drafts Instructions only"])
        proposal, _ = self.proposal()
        self.assertEqual(self.problems(proposal, chosen=None), ["this run offers no change to any Instructions: why"])
        proposal, _ = self.proposal(workflow="learning")
        self.assertIn("`workflow:` must name one workflow whose Instructions may change", self.problems(proposal)[0])

    def test_the_text_must_change_keep_its_comment_lines_and_stay_within_its_limits(self):
        same, _ = self.proposal(text=self.in_force)
        self.assertEqual(self.problems(same), ["the proposed text is the text in force"])
        spaced, _ = self.proposal(text="\n\n" + self.in_force.replace(".\n", ".  \n") + "\n\n")
        self.assertEqual(self.problems(spaced), ["the proposed text is the text in force"], "spacing is no change")
        first = self.in_force.splitlines()[0]
        self.assertTrue(first.startswith("<!--"), "the post-Draft Instructions open with their attribution")
        stripped, _ = self.proposal(text=self.in_force.replace(first + "\n", "") + ADDED + "\n")
        self.assertIn("keep every comment line of the text in force as it is", self.problems(stripped)[0])
        long, _ = self.proposal(text=self.in_force + "x" * instructions.MAX_TEXT)
        self.assertIn("characters; at most 32000", self.problems(long)[0])
        address, _ = self.proposal(text=self.in_force + "- Write to jane.doe@example.com first.\n")
        self.assertEqual(self.problems(address), ["it holds something that looks like an email address"])
        summary, _ = self.proposal(summary="x" * 301)
        self.assertEqual(self.problems(summary), ["`summary:` must be one line of at most 300 characters"])

    def test_a_change_that_copies_package_text_is_refused(self):
        angles = "projects/RepToday/gtm/05-social-pmf/angles.md"
        package = instructions.package_lines(fakes.EXAMPLES / "files/mandu", [angles])
        self.assertEqual(package["airplane mode proves on-device building"], angles, "a table cell is a passage")
        copied, _ = self.proposal(text=self.in_force + "- Remember: airplane mode proves on-device building.\n")
        self.assertEqual(
            self.problems(copied, package),
            [
                f"a line it adds holds text of the Go-To-Market Package file `{angles}`:"
                " '- Remember: airplane mode proves on-device building.'"
            ],
        )
        own, _ = self.proposal()
        self.assertEqual(self.problems(own, package), [], "a line of the agent's own passes")

    def test_a_file_without_its_front_matter_is_no_proposal(self):
        self.assertEqual(
            instructions.parse("Shorter captions.\n", "post-drafts.md"),
            (None, ["the file must start with front matter between --- lines"]),
        )
        proposal, problems = instructions.parse("---\nworkflow: post-drafts\n---\n\ntext\n", "post-drafts.md")
        self.assertIsNone(proposal)
        self.assertEqual(problems, ["the front matter needs `reasons:`, `summary:`"])


class OfferTest(WorkCycleTestCase):
    def setUp(self):
        super().setUp()
        self.store = Store(self.ledger())
        shutil.copytree(str(fakes.REPO / "src/examples/post-drafts"), str(self.repo / "src/examples/post-drafts"))

    def offer(self, found, ledger=None):
        return instructions.offer(found, ledger or Ledger(), self.store, self.repo)

    def test_the_oldest_waiting_reason_s_workflow_goes_first_with_all_its_waiting_reasons(self):
        found = [
            reason("20261012-b", "Too long.", "length", decided_at="2026-10-12T10:00:00-07:00"),
            reason("20261011-a", "Wrong person.", "fit", decided_at="2026-10-11T10:00:00-07:00"),
            reason("20261011-c", "Stiff.", "", decided_at="2026-10-11T11:00:00-07:00"),
            reason("20261011-d", "Answered.", "tone", answer={"outcome": "kept"}),
            reason("20261010-e", "A Dispatch.", "tone", workflow="dispatch-requests"),
        ]
        chosen, why = self.offer(found)
        self.assertEqual((chosen, why), (instructions.Offer("post-drafts", ("20261011-c", "20261012-b")), ""))
        self.assertEqual([r.item for r in chosen.coded(found)], ["20261012-b"])

    def test_nothing_is_offered_while_the_last_change_s_notice_waits_or_no_example_set_can_gate_it(self):
        ledger = Ledger()
        ledger.entries["20261011-instructions-post-drafts"] = {
            "id": "20261011-instructions-post-drafts",
            "kind": "notice",
            "status": "open",
            "instructions": "post-drafts",
        }
        found = [reason(DAY_1, LONG, "length"), reason("20261011-x", "Long.", "length", workflow="outreach")]
        chosen, why = self.offer(found, ledger)
        self.assertIsNone(chosen)
        self.assertIn(
            "the Post Drafts Instructions wait on the notice `20261011-instructions-post-drafts` of their last change",
            why,
        )
        self.assertIn("no example set can gate a change to the Outreach Instructions", why)
        self.assertEqual(self.offer([]), (None, "no rejection reason may lead to one"))


class LoopTest(WorkCycleTestCase):
    """Whole runs: two posts rejected at a sitting, one for its execution, one for its strategy, then the run that
    learns from both, as US-ME16's Validation Test sets it up."""

    def setUp(self):
        super().setUp()
        folder = self.repo / "src/examples/post-drafts"
        shutil.copytree(str(fakes.REPO / "src/examples/post-drafts"), str(folder))
        data = json.loads((folder / "evals.json").read_text(encoding="utf-8"))
        data["evals"] = [example for example in data["evals"] if example["id"] in KEPT_EXAMPLES]
        (folder / "evals.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
        self.in_force = (self.ledger() / "instructions/post-drafts.md").read_text(encoding="utf-8")
        self.drafts = {fakes.draft_path(day): fakes.draft(day) for day in (1, 3)}
        # The first run drafts days 1 and 3 of the first batch; the Founder rejects both at the sitting.
        fakes.set_window(self.repo, {"number": 1, "first_sitting": None, "slot": None})
        fakes.keep_days(self.mandu, 1, 3)
        fakes.behave(self.codex_dir, {"sessions": {"post-drafts": {"write": self.drafts}}})
        self.go()
        self.assertEqual([entry["id"] for entry in self.items("post")], [DAY_1, DAY_3])
        self.decide(DAY_1, "reject", reason=LONG)
        self.decide(DAY_3, "reject", reason=WRONG_PERSON)
        fakes.set_window(self.repo, fakes.QUIET_WINDOW)

    def code_file(self, item, code, why="The Founder's words are about this."):
        return {f"evidence/learning/{item}.md": f"---\nitem: {item}\ncode: {code}\n---\n\n{why}\n"}

    def proposal(self, text, reasons=DAY_1, summary="Keep caption lines short, as the Founder rejected long ones."):
        return f"---\nworkflow: post-drafts\nreasons: {reasons}\nsummary: {summary}\n---\n\n{text}"

    def learning_writes(self, proposed=None, reasons=DAY_1):
        """What the rejection reasons' session writes: both codes, and the proposed Instructions text if any."""
        writes = dict(self.code_file(DAY_1, "length"), **self.code_file(DAY_3, "fit"))
        if proposed is not None:
            writes["instructions/post-drafts.md"] = self.proposal(proposed, reasons)
        return writes

    def answer(self):
        """The package-change proposal that answers the strategy reason. The stand-in has an item in incoming/
        written by the run's first session, whichever session the real agent writes it in."""
        cited = f"- The Founder's reason: `evidence/decisions/{DAY_3}.json`\n- Cleared and reserved:"
        text = fakes.proposal(title="say who the post speaks to").replace("- Cleared and reserved:", cited)
        return {"review-queue/incoming/fit-answer.md": text}

    def learn(self, proposed=None, reasons=DAY_1, worse_drafts=None, weeks=1):
        """The run after the sitting: the rejection reasons' session codes both reasons, answers the strategy one
        with a package-change proposal, and proposes the given Instructions text; in every example's lab, the
        post-Draft session writes the clean Drafts, or worse_drafts where the Instructions under test hold WORSE."""
        behavior = {
            "write": self.answer(),
            "sessions": {
                "learning": {"write": self.learning_writes(proposed, reasons)},
                "post-drafts": {"write": self.drafts},
            },
        }
        if worse_drafts is not None:
            behavior["when_instructions"] = {WORSE: {"write": worse_drafts}}
        fakes.behave(self.codex_dir, behavior)
        return self.go(weeks=weeks)

    def instructions_text(self):
        return (self.ledger() / "instructions/post-drafts.md").read_text(encoding="utf-8")

    def change_records(self):
        return sorted((self.ledger() / "evidence/instructions").glob("*.json"))

    def test_an_execution_reason_changes_the_instructions_through_a_passing_example_set_with_a_notice(self):
        proposed = self.in_force + ADDED + "\n"
        report = self.learn(proposed)

        # One Instructions change, written by the launcher once its example set passed.
        self.assertEqual(self.instructions_text(), proposed)
        records = self.change_records()
        self.assertEqual([path.name for path in records], ["20261018-post-drafts.json"])
        change = json.loads(records[0].read_text(encoding="utf-8"))
        self.assertEqual((change["outcome"], change["workflow"]), ("kept", "post-drafts"))
        self.assertEqual([entry["item"] for entry in change["reasons"]], [DAY_1], "the strategy reason is not cited")
        self.assertEqual(change["reasons"][0]["reason"], LONG)
        self.assertEqual(change["reasons"][0]["code"], "length")
        self.assertEqual(
            change["changed_lines"], [{"change": "added", "line": len(self.in_force.splitlines()) + 1, "text": ADDED}]
        )
        gate = change["gate"]
        self.assertEqual([example["id"] for example in gate["examples"]], list(KEPT_EXAMPLES))
        for example in gate["examples"]:
            for side in ("in_force", "proposed"):
                self.assertEqual(example[side]["status"], examples.RAN)
                self.assertTrue(example[side]["checks"])
                self.assertTrue(all(check["held"] for check in example[side]["checks"]), example)
        self.assertEqual(gate["sessions"], 4, "each example once on each side")
        before = self.ledger() / change["before"]["path"]
        self.assertEqual(before.read_text(encoding="utf-8"), self.in_force)

        # The notice for the next sitting, with the reason, its code, the change, and the example results.
        notice = next(entry for entry in self.items("notice") if entry.get("instructions") == "post-drafts")
        self.assertEqual(notice["change"], "20261018-post-drafts")
        self.assertEqual(change["notice"], notice["id"])
        text = self.item_text(notice["id"])
        self.assertIn("# Notice: the Post Drafts Instructions changed", text)
        self.assertIn(f'- Your reason for rejecting `{DAY_1}`: "{LONG}"', text)
        self.assertIn("The agent coded it `length`, an execution code:", text)
        self.assertIn("Keep caption lines short, as the Founder rejected long ones.", text)
        self.assertIn(f"- Line {len(self.in_force.splitlines()) + 1}, added: {ADDED}", text)
        self.assertIn("| 1: Prepare the Draft for day 3", text)
        self.assertIn("| 4 of 4 checks held | 4 of 4 checks held |", text)
        self.assertIn("Not judged by anything, by the launcher or a model; yours to judge, if you want to:", text)
        self.assertIn("- Example 1: The captions read as calm and plain, in the brand's voice, with no hype.", text)
        self.assertIn("`evidence/instructions/20261018-post-drafts.json`", text)

        # Each rejection reason is kept as Evidence linked to its item, both ways.
        for item, words in ((DAY_1, LONG), (DAY_3, WRONG_PERSON)):
            kept = self.read(f"evidence/decisions/{item}.json")
            self.assertEqual((kept["item"], kept["reason"]), (item, words))
            self.assertEqual(kept["item_file"], f"review-queue/items/{item}.md")
            self.assertEqual(self.entry(item)["evidence"], f"evidence/decisions/{item}.json")

        # The strategy reason became a package-change proposal and never an Instructions change.
        self.assertEqual(len(self.items("package-change-proposal")), 1)
        strategy = self.read(f"evidence/decisions/{DAY_3}.json")
        self.assertEqual(strategy["code"]["code"], "fit")
        self.assertNotIn("instructions", strategy)
        execution = self.read(f"evidence/decisions/{DAY_1}.json")
        self.assertEqual(execution["instructions"]["outcome"], "kept")
        self.assertEqual(execution["instructions"]["change"], "20261018-post-drafts")

        learned = self.section("Instructions")
        offered = "- Offered: a change to the Post Drafts Instructions, from its workflow's reasons coded as execution:"
        self.assertIn(f"{offered} `{DAY_1}`.", learned)
        self.assertIn(
            f"- Change `20261018-post-drafts` to the Post Drafts Instructions, from `{DAY_1}`: kept:", learned
        )
        self.assertIn(f"The notice `{notice['id']}` shows it at the next sitting.", learned)
        self.assertIn(
            "| Instructions changes | complete | change `20261018-post-drafts` to the Post Drafts Instructions kept |",
            report,
        )
        self.assertIn(
            "Beside these, the Instructions change's example set: The example set took 4 agent sessions", report
        )
        self.assertIn(
            "- Instructions: change `20261018-post-drafts` to the Post Drafts Instructions kept: no example of 2"
            " examples did worse.",
            self.section("Summary"),
        )

        # The brief told the session which reasons may change which Instructions.
        brief = self.brief(session="learning")
        self.assertIn("## Instructions change", brief)
        self.assertIn(f'- `{DAY_1}` (not coded yet): "{LONG}"', brief)
        self.assertIn(f'- `{DAY_3}` (not coded yet): "{WRONG_PERSON}"', brief)

    def test_a_change_that_makes_an_example_worse_is_not_kept_and_the_instructions_stay_exactly_as_they_were(self):
        before = (self.ledger() / "instructions/post-drafts.md").read_bytes()
        worse = {
            path: text.replace("This is the history view", "Crush it: this is the history view")
            for path, text in self.drafts.items()
        }
        report = self.learn(self.in_force + WORSE + "\n", worse_drafts=worse)

        self.assertEqual((self.ledger() / "instructions/post-drafts.md").read_bytes(), before)
        change = json.loads(self.change_records()[0].read_text(encoding="utf-8"))
        self.assertEqual(change["outcome"], "not kept")
        self.assertIn(
            "example 1 got worse: `passes` held with the Instructions in force and failed with the change, and did so"
            " again when the example was run again",
            change["why"],
        )
        self.assertEqual(change["gate"]["not_run"], [2], "the gate stops at the first example that is worse")
        self.assertEqual(change["gate"]["sessions"], 4, "example 1 on both sides, and again on both sides")
        self.assertIsNotNone(change["gate"]["examples"][0]["run_again"])
        self.assertIsNone(change["notice"])
        self.assertEqual([entry for entry in self.items("notice") if entry.get("instructions")], [])
        not_again = "The Instructions are as they were; the reasons it cites are not offered again."
        self.assertIn(not_again, self.section("Instructions"))
        self.assertEqual(self.read(f"evidence/decisions/{DAY_1}.json")["instructions"]["outcome"], "not kept")
        row = "| Instructions changes | complete | change `20261018-post-drafts` to the Post Drafts Instructions not"
        self.assertIn(row + " kept |", report)

    def test_a_change_that_cites_a_strategy_reason_is_refused_and_runs_no_example(self):
        report = self.learn(self.in_force + ADDED + "\n", reasons=f"{DAY_1}, {DAY_3}")
        self.assertEqual(self.instructions_text(), self.in_force)
        self.assertEqual(self.change_records(), [])
        self.assertIn(
            f"- Proposed change refused: `post-drafts.md`: `{DAY_3}` is coded `fit`, a strategy code, which never"
            " changes Instructions.",
            self.section("Instructions"),
        )
        self.assertFalse((self.workspace() / "instructions/post-drafts.md").exists(), "removed once read")
        self.assertIn("| Instructions changes | incomplete | the proposed change `post-drafts.md` was refused", report)
        self.assertIn("The proposed change `post-drafts.md` was refused", self.notices())
        self.assertNotIn("instructions", self.read(f"evidence/decisions/{DAY_1}.json"), "offered again")

    def test_rejecting_the_notice_undoes_the_change_at_the_next_run_and_nothing_else_changes_meanwhile(self):
        proposed = self.in_force + ADDED + "\n"
        self.learn(proposed)
        notice = next(entry["id"] for entry in self.items("notice") if entry.get("instructions"))

        # A run while the notice is undecided changes nothing about it.
        fakes.behave(self.codex_dir, {})
        self.go(weeks=2)
        self.assertEqual(self.instructions_text(), proposed)
        self.assertIn(notice, [entry["id"] for entry in self.items("notice")])

        self.decide(notice, "reject", reason="I prefer the captions as they were.")
        fakes.behave(self.codex_dir, {})
        self.go(weeks=3)
        self.assertEqual(self.instructions_text(), self.in_force, "put back as it was before the change")
        change = json.loads(self.change_records()[0].read_text(encoding="utf-8"))
        self.assertEqual(change["undone"]["reason"], "I prefer the captions as they were.")
        self.assertEqual(change["decided"]["decision"], "reject")
        self.assertIn(
            "- The Post Drafts Instructions were put back as they were before change `20261018-post-drafts`, since the"
            f' Founder rejected its notice `{notice}`: "I prefer the captions as they were."',
            self.section("Instructions"),
        )
        # The Founder's reason for rejecting the notice is kept and coded like any other, under the workflow changed.
        kept = self.read(f"evidence/decisions/{notice}.json")
        self.assertEqual(kept["reason"], "I prefer the captions as they were.")
        reasons, _ = learning.reasons(Store(self.ledger()), Ledger.load(self.ledger() / "review-queue/queue.json"))
        self.assertEqual(next(r.workflow for r in reasons if r.item == notice), "post-drafts")

    def test_a_change_whose_examples_cannot_be_compared_is_not_kept_and_its_reasons_are_offered_again(self):
        fakes.set_run(self.repo, "learning", {"gate_time_limit_seconds": 0.001, "example_time_limit_seconds": 0.001})
        report = self.learn(self.in_force + ADDED + "\n")
        self.assertEqual(self.instructions_text(), self.in_force)
        change = json.loads(self.change_records()[0].read_text(encoding="utf-8"))
        self.assertEqual(change["outcome"], "not compared")
        self.assertIn("example 1 could not be compared", change["why"])
        self.assertNotIn("instructions", self.read(f"evidence/decisions/{DAY_1}.json"), "offered again")
        self.assertIn("the reasons it cites are offered again at the next run", self.section("Instructions"))
        self.assertIn(
            "| Instructions changes | incomplete | change `20261018-post-drafts` could not be judged:", report
        )

    def test_another_session_cannot_leave_a_proposed_change(self):
        self.learn()
        self.assertEqual(self.read(f"evidence/decisions/{DAY_1}.json")["instructions"]["outcome"], "none proposed")
        # With no rejection reason waiting, the rejection reasons' session has nothing due, so the run's first
        # session, the package review, is the one that writes what the stand-in is told to.
        fakes.behave(
            self.codex_dir, {"write": {"instructions/post-drafts.md": self.proposal(self.in_force + ADDED + "\n")}}
        )
        self.go(weeks=2)
        self.assertEqual(self.instructions_text(), self.in_force)
        self.assertEqual(self.change_records(), [])
        self.assertIn(
            "after the Package review session: `instructions/post-drafts.md` was added during the run and removed",
            self.section("Learning"),
        )

    def test_check_work_tells_the_session_what_the_launcher_will_say_of_its_proposal(self):
        proposed = self.in_force + ADDED + "\n"
        behavior = {
            "write": self.answer(),
            "sessions": {
                "learning": {"write": self.learning_writes(proposed, f"{DAY_1}, {DAY_3}")},
                "post-drafts": {"write": self.drafts},
            },
        }
        fakes.behave(self.codex_dir, behavior)
        seen = dict((session, (code, out)) for session, code, out in self.go_with_checks(weeks=1, part=True))
        code, out = seen["learning"]
        self.assertEqual(code, 1)
        self.assertIn(
            f"PROBLEM Instructions change post-drafts.md\n  - `{DAY_3}` is coded `fit`, a strategy code, which never"
            " changes Instructions",
            out,
        )
        self.assertTrue((self.workspace() / "evidence/learning").is_dir(), "the check wrote and removed nothing")

    def test_a_proposal_an_earlier_run_left_is_removed_before_the_first_session(self):
        stale = self.workspace() / "instructions/post-drafts.md"
        stale.write_text(self.proposal(self.in_force + ADDED + "\n"), encoding="utf-8")
        fakes.behave(self.codex_dir, {"sessions": {"learning": {"write": self.learning_writes()}}})
        self.go(weeks=1)
        self.assertEqual(self.instructions_text(), self.in_force)
        self.assertIn(
            "`instructions/post-drafts.md`, a proposed Instructions change an earlier run left, was removed before"
            " the first session",
            self.report(),
        )


class RepeatTest(unittest.TestCase):
    """An agent's output varies from one session to the next, so an example that did worse with a change is run again
    on both sides, and is worse only when the same assertion does worse again."""

    SET = examples.ExampleSet(
        "post-drafts",
        Path("."),
        {},
        tuple(
            examples.Example(number, f"Example {number}.", "", ({"kind": "deterministic", "check": name},), {})
            for number, name in ((1, "passes"), (2, "hook_frozen"))
        ),
    )

    def gate(self, script):
        """The gate over two examples, each run returning the checks the script gives, in the order they run: a
        list of booleans by check, one Run per call; None for a run that did not run to its end."""
        calls = []

        def run_example(repo_root, example_set, example, side, text, root, env, home, log_dir, limit):
            calls.append((example.id, side))
            held = script.pop(0)
            if held is None:
                return examples.Run(side, "not run", "its session did not run to its end", seconds=1.0)
            checks = [examples.Check(assertion, held) for assertion in example.checks]
            return examples.Run(side, examples.RAN, checks=checks, seconds=10.0, cost=0.01, lab_run="r", started=True)

        with (
            mock.patch.object(examples, "load", return_value=self.SET),
            mock.patch.object(examples, "run_example", run_example),
        ):
            found = examples.gate(
                Path("."), "post-drafts", "a\n", "b\n", "c", {}, Path("."), Path("."), 100, 50, Path(".")
            )
        return found, calls

    def test_a_flip_that_does_not_repeat_keeps_the_change(self):
        found, calls = self.gate([True, False, True, True, True, True])
        self.assertEqual(found.outcome, examples.KEPT, found.why)
        self.assertEqual(
            calls,
            [(1, "in force"), (1, "proposed"), (1, "in force"), (1, "proposed"), (2, "in force"), (2, "proposed")],
        )
        lines = "\n".join(examples.result_lines(found))
        self.assertIn(
            "- Example 1: `passes` did worse with the change once; run again on both sides, it did not, so the"
            " example is not worse.",
            lines,
        )
        self.assertEqual(found.sessions, 6)

    def test_a_flip_that_repeats_keeps_the_change_out_and_stops_the_gate(self):
        found, calls = self.gate([True, False, True, False])
        self.assertEqual(found.outcome, examples.NOT_KEPT)
        self.assertIn("did so again when the example was run again", found.why)
        self.assertEqual([example.id for example in found.not_run], [2])
        self.assertEqual(len(calls), 4)

    def test_a_repeat_that_does_not_run_to_its_end_leaves_the_change_not_compared(self):
        found, _ = self.gate([True, False, True, None])
        self.assertEqual(found.outcome, examples.NOT_COMPARED)
        self.assertIn("example 1 could not be compared: run again, with the change", found.why)

    def test_a_repeat_the_bound_leaves_no_time_for_is_not_compared(self):
        tight, calls = self.gate_with_bound([True, False, True, True], 20)
        self.assertEqual(tight.outcome, examples.NOT_COMPARED)
        self.assertIn("bound of 20 seconds of agent time was used up", tight.why)
        self.assertEqual(len(calls), 2, "nothing was started past the bound")

    def gate_with_bound(self, script, bound):
        calls = []

        def run_example(repo_root, example_set, example, side, text, root, env, home, log_dir, limit):
            calls.append((example.id, side))
            checks = [examples.Check(assertion, script.pop(0)) for assertion in example.checks]
            return examples.Run(side, examples.RAN, checks=checks, seconds=10.0, lab_run="r", started=True)

        with (
            mock.patch.object(examples, "load", return_value=self.SET),
            mock.patch.object(examples, "run_example", run_example),
        ):
            found = examples.gate(
                Path("."), "post-drafts", "a\n", "b\n", "c", {}, Path("."), Path("."), bound, 50, Path(".")
            )
        return found, calls

    def test_an_assertion_is_named_in_plain_words(self):
        """The notice names an assertion to the Founder, so it reads as words and never as a list's code."""
        queued = {"kind": "deterministic", "check": "queued", "item": "package-change-proposal", "count": 1}
        self.assertEqual(
            examples.describe({**queued, "cites": ["a.md", "b.md"], "at_least": True}),
            "queued: at least 1 package-change-proposal citing a.md and b.md",
        )
        self.assertEqual(examples.describe(queued), "queued: 1 package-change-proposal")
        self.assertEqual(
            examples.describe({"kind": "deterministic", "check": "cites_angle", "angle": "P06", "day": 6}),
            "cites angle: angle P06, day 6",
        )
        nothing = {"kind": "deterministic", "check": "nothing_set_aside"}
        self.assertEqual(examples.describe(nothing), "nothing set aside")


class KeptOutOfReachTest(unittest.TestCase):
    """The Instructions in force and the example sets: the sandbox reads both and writes neither, and each is a
    forbidden target of its own of the preflight before every session and of the boundary check."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(os.path.realpath(self.tmp.name)) / "home"
        self.repo = self.home / "gr0wthlab"
        for area in CONFIG["writable_areas"].values():
            (self.repo / area).mkdir(parents=True)
        for folder in ("src/examples", "config/guardrails", "ledger/instructions"):
            (self.repo / folder).mkdir(parents=True)
        fakes.make_founder(self.repo / "ledger")
        (self.home / "Mandu").mkdir()
        self.boundary = boundary.resolve_boundary(self.repo, CONFIG, REGISTRY, {}, self.home, git=[self.repo / ".git"])
        self.kept = (
            ("instructions-in-force", self.repo / "ledger" / "instructions"),
            ("example-sets", self.repo / "src" / "examples"),
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_the_boundary_names_both_folders_and_no_grant_lets_the_sandbox_write_either(self):
        self.assertEqual(self.boundary.kept_dirs, self.kept)
        policy = boundary.filesystem_policy(self.boundary)
        writable = [path for path, access in policy.items() if access == "write"]
        self.assertEqual(sorted(writable), sorted(str(path) for path in self.boundary.area_paths))
        for _, path in self.kept:
            self.assertNotIn(str(path), policy)
            self.assertFalse(any(boundary.is_within(path, Path(granted)) for granted in writable))

    def test_every_session_s_preflight_tries_both_and_must_be_refused(self):
        environment = {"HOME": str(self.home), "TMPDIR": str(self.home), "CODEX_HOME": str(self.home)}
        allowed, forbidden = codex.preflight_targets(self.boundary, environment)
        tried = "".join(f"WROTE {path}\n" for path in allowed)
        refused = "".join(f"REFUSED {path}\n" for path in forbidden)
        for label, path in self.kept:
            with self.subTest(label=label):
                self.assertIn(path, forbidden)
                written = codex.evaluate_preflight(
                    tried + refused.replace(f"REFUSED {path}\n", f"WROTE {path}\n"), "n", allowed, forbidden
                )
                self.assertEqual(written.breaches, (path / "n",))
                skipped = codex.evaluate_preflight(
                    tried + refused.replace(f"REFUSED {path}\n", ""), "n", allowed, forbidden
                )
                self.assertEqual(skipped.failures, (f"{path} must be refused but was not probed",))

    def test_the_boundary_check_has_a_target_for_each_with_one_step_per_tool(self):
        dirs = probe.forbidden_dirs(self.boundary)
        steps = probe.probe_steps(self.boundary, "RUN")
        for label, path in self.kept:
            self.assertIn(label, probe.PROBE_TARGETS)
            self.assertEqual(dirs[label], path)
            mine = [step for step in steps if step.label == label]
            self.assertEqual(
                [(step.kind, step.tool) for step in mine], [("forbidden", "file-tool"), ("forbidden", "shell")]
            )
            for step in mine:
                self.assertEqual(step.path.parent, path, "the sentinel is named directly in the folder")
            self.assertNotIn(label, dict(self.boundary.areas), "no writable area shares the label")

    def test_a_folder_missing_or_a_link_stops_a_run_a_check_and_a_preflight(self):
        codex_bin = fakes.install_codex(self.home / "codex-bin")
        env = {"GR0WTHLAB_CODEX_BIN": str(codex_bin)}
        for label, path in self.kept:
            with self.subTest(label=label):
                shutil.rmtree(str(path))
                with mock.patch.object(launcher, "load_boundary", return_value=(CONFIG, self.boundary)):
                    with self.assertRaises(ConfigError) as raised:
                        launcher.Resolved(self.repo, env, self.home, Path("m.md"))
                self.assertIn(f"{path} must be a real folder", str(raised.exception))
                path.symlink_to(self.repo / "workspace" / "instructions")
                with self.assertRaises(ConfigError):
                    boundary.check_kept_dirs(self.repo)
                path.unlink()
                path.mkdir()
                boundary.check_kept_dirs(self.repo)


class SettingsTest(WorkCycleTestCase):
    def test_the_gate_s_bound_is_at_least_one_example_s_limit(self):
        fakes.set_run(self.repo, "learning", {"gate_time_limit_seconds": 60, "example_time_limit_seconds": 600})
        with self.assertRaises(settings.ConfigError):
            settings.load(self.repo, self.env, self.home)
        fakes.set_run(self.repo, "learning", {"gate_time_limit_seconds": 3600, "example_time_limit_seconds": 600})
        learned = settings.load(self.repo, self.env, self.home).learning
        self.assertEqual((learned.gate_time_limit, learned.example_time_limit), (3600.0, 600.0))


if __name__ == "__main__":
    unittest.main()
