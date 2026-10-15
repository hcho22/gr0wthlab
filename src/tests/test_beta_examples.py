"""The Beta Cohort recruiting example set (F5): every deterministic assertion in src/examples/beta-recruiting/evals.json
holds."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from gr0wthlab import beta, beta_drafts, lint, package
from tests import fakes

EXAMPLES = fakes.BETA_EXAMPLES
# The checks only a re-run can hold, since they read what a whole run queued or refused, not one candidate: a
# "queued" that names an item kind is one of them, while a Listening proposal's own "queued" names none.
RUN_ONLY = {"nothing_queued", "nothing_set_aside", "nothing_refused", "nothing_discarded"}


def run_only(assertion):
    return assertion["check"] in RUN_ONLY or (assertion["check"] == "queued" and "item" in assertion)


ADDRESS_PARTS = ("@", "example.com", "founder@")


class BetaExampleSetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((EXAMPLES / "evals.json").read_text(encoding="utf-8"))
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(os.path.realpath(cls.tmp.name))
        # A scenario with the gate recorded gives the context every Draft example is checked against.
        scenario = json.loads((EXAMPLES / "files/scenarios/first-batch.json").read_text(encoding="utf-8"))
        cls.plan, _, _ = fakes.beta_plan(cls.root / "context", scenario, fakes.waitlist_view())

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_set_has_the_evals_json_shape_and_covers_every_case_the_story_names(self):
        self.assertEqual(self.data["skill_name"], "beta-recruiting")
        ids = [example["id"] for example in self.data["evals"]]
        self.assertEqual(ids, list(range(1, len(ids) + 1)))
        self.assertGreaterEqual(len(ids), 10)
        checks = set()
        for example in self.data["evals"]:
            keys = ["assertions", "expected_output", "files", "id", "prompt"] + (["run"] if "run" in example else [])
            self.assertEqual(sorted(example), keys)
            self.assertTrue(example["files"] or "run" in example, example["id"])
            self.assertTrue(all((EXAMPLES / name).is_file() for name in example["files"]), example["id"])
            kinds = {assertion["kind"] for assertion in example["assertions"]}
            self.assertLessEqual(kinds, {"deterministic", "judged"})
            self.assertIn("deterministic", kinds)
            checks |= {
                (assertion["check"], assertion.get("rule", ""))
                for assertion in example["assertions"]
                if "check" in assertion
            }
        for case in (
            ("nothing_before_approval", ""),  # a run before the approval
            ("blocked_by", "no-address"),  # an address in a Draft
            ("blocked_by", "unbacked-number"),  # an invented spot count
            ("gap", ""),  # a pool too small to reach 20
            ("never_offered", ""),  # an entry already invited
            ("not_reported", ""),  # a count the Founder did not report
            ("blocked_by", "fake_scarcity"),
        ):
            self.assertIn(case, checks)

    def test_the_brand_rules_and_the_view_are_the_shared_synthetic_fixtures(self):
        rules = (EXAMPLES / self.data["brand_rules"]).resolve()
        self.assertEqual(rules, (fakes.EXAMPLES / "files/mandu" / self.plan.rules.brand_rules).resolve())
        self.assertIn("fake_scarcity", lint.Rules(json.loads(rules.read_text(encoding="utf-8"))).lists)
        view = json.loads((EXAMPLES / "files/waitlist-view.json").read_text(encoding="utf-8"))
        self.assertEqual(view, fakes.waitlist_view())
        for path in (EXAMPLES / "files").rglob("*"):
            if path.is_file() and "invitation-address" not in path.name:
                self.assertNotIn("@", path.read_text(encoding="utf-8"), path)

    def test_every_deterministic_assertion_holds_of_each_candidate_and_scenario(self):
        """An example the agent re-runs with no candidate holds in its own lab instead (test_example_runs.py), as do
        the re-run checks of what a whole run queued."""
        for example in self.data["evals"]:
            if not example["files"]:
                continue
            first = example["files"][0]
            subject = self.scenario(example) if first.startswith("files/scenarios/") else self.draft(first)
            for assertion in example["assertions"]:
                if assertion["kind"] != "deterministic" or run_only(assertion):
                    continue
                with self.subTest(example=example["id"], check=assertion["check"], rule=assertion.get("rule")):
                    self.assertTrue(self.holds(assertion, *subject), subject)

    def draft(self, name):
        text = (EXAMPLES / name).read_text(encoding="utf-8")
        draft = beta_drafts.parse(text, name)
        purpose = beta_drafts.WAITLIST_ASK if "waitlist-ask" in name else beta_drafts.INVITATION
        return beta_drafts.evaluate(draft, self.plan.context, purpose), None, None

    def scenario(self, example):
        scenario = json.loads((EXAMPLES / example["files"][0]).read_text(encoding="utf-8"))
        view = json.loads((EXAMPLES / scenario["view"]).read_text(encoding="utf-8"))
        plan, store, _ = fakes.beta_plan(self.root / f"example-{example['id']}", scenario, view)
        return None, plan, store

    def holds(self, assertion, verdict, plan, store):
        check = assertion["check"]
        if check == "passes":
            return verdict.passed
        if check == "blocked_by":
            return any(finding.rule.startswith(assertion["rule"]) for finding in verdict.blocks)
        if check == "not_blocked_by":
            return not any(finding.rule.startswith(assertion["rule"]) for finding in verdict.blocks)
        if check == "no_address_in_findings":
            told = json.dumps([finding.__dict__ for finding in verdict.blocks + verdict.warnings])
            return not any(part in told for part in ADDRESS_PARTS)
        if check == "nothing_before_approval":
            return self.nothing(plan, store)
        if check == "batch":
            batch = plan.batch
            return (batch.action, batch.entries, batch.good_fit) == (
                assertion["action"],
                assertion["entries"],
                assertion["good_fit"],
            )
        if check == "gap":
            return plan.gap == assertion["size"] and f"{assertion['size']} short of" in beta.gap_line(plan)
        if check == "asks_for":
            return [due.purpose for due in plan.drafts] == assertion["drafts"]
        if check == "never_offered":
            return not set(assertion["entries"]) & set(plan.batch.entries)
        if check == "not_reported":
            return self.not_reported(assertion["counts"], plan, store)
        if check == "reported":
            return plan.counts.stated[assertion["count"]][0] == assertion["value"]
        if check == "recruiting_ended":
            return plan.batch.ended and plan.gap is None and not plan.drafts
        raise AssertionError(f"unknown check {check}")

    def nothing(self, plan, store):
        """Before the gate: no entry chosen, no Draft asked for, nothing written, and nothing for the agent or the
        report beyond the approval listed as not recorded."""
        rows = beta.source_lines(plan)
        return (
            not plan.active
            and plan.batch is None
            and not plan.drafts
            and not plan.held
            and plan.context is None
            and beta.brief_lines(plan, Path("/repo")) == []
            and beta.report_lines(plan, None) == []
            and beta.summary(plan, None) == ""
            and not any(store.root.rglob("*"))
            and rows[0][:2] == (beta.GATE_SOURCE, beta.SKIPPED)
            and rows[0][2].startswith("not recorded")
        )

    def not_reported(self, counts, plan, store):
        """A count the Founder left out is null and named as not reported, in the Evidence and in the Founder's
        line, and is never a zero."""
        (kept,) = (store.root / "evidence" / beta.EVIDENCE / "reports").glob("*.json")
        record = json.loads(kept.read_text(encoding="utf-8"))
        standing = plan.counts.as_json()
        return all(
            record[key] is None
            and key in record["not_reported"]
            and standing[key] is None
            and key in standing["not_reported"]
            and f"{beta.COUNT_LABELS[key]} not reported" in plan.counts.line()
            and key not in plan.counts.stated
            for key in counts
        )

    def test_a_synthetic_package_file_is_a_citable_source(self):
        cited = {citation.path for name in ("invitation-clean", "waitlist-ask-clean") for citation in self.cites(name)}
        self.assertEqual(len(cited), 4)
        for path in cited:
            self.assertTrue(any(source.covers(path) for source in self.plan.rules.citable), path)
            self.assertEqual(package.file_type(self.plan.context.mandu / path), 0o100000)

    def cites(self, name):
        return beta_drafts.parse(fakes.beta_draft(name), name).citations


if __name__ == "__main__":
    unittest.main()
