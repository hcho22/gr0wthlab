"""Every example the agent re-runs on an Instructions change (US-ME16, ADR 0003) can hold: its lab is built from its
set's fixtures, one weekly run there starts that workflow's session alone, and with a stand-in agent that writes a
good output for it, every one of its deterministic assertions holds on what the launcher took in.

A re-run whose example could never hold would make the gate blind: no change could make that example worse. So this
test runs each set's every re-run example with the stand-in (fakes.install_codex) writing what GOOD says a good run
writes there, and fails on any assertion that does not hold or any example GOOD says nothing of.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gr0wthlab import codebase, cycle, examples, posts
from gr0wthlab.queue import Ledger
from tests import fakes

POSTS = fakes.EXAMPLES
OUTREACH = fakes.REPO / "src/examples/outreach"
LISTENING = fakes.REPO / "src/examples/listening"
FILMING = fakes.FILMING


def text(folder: Path, name: str) -> str:
    return (folder / name).read_text(encoding="utf-8")


def answering(cites: str) -> str:
    """A package-change proposal whose Evidence cites the given package file."""
    return fakes.PROPOSAL.replace(
        "- Cleared and reserved: `projects/RepToday/02-marketing-launch-checklist_260807.md` line 24",
        f"- The rule the frozen Hook breaks: `projects/RepToday/gtm/{cites}` line 7",
    )


def creator(key: str, line: str = "If early access would be of use to you, it is yours") -> str:
    draft = text(OUTREACH, "files/drafts/creator.md").replace("to: slow-strength", f"to: {key}")
    return draft.replace("If early access would be of use to you, it is yours", line)


NETWORK = {fakes.message_path("network-ask"): text(OUTREACH, "files/drafts/network-ask.md")}
INVITATION = fakes.beta_draft()
ASK = fakes.beta_draft("waitlist-ask-clean")
RECRUITING = {fakes.INVITATION: INVITATION, fakes.WAITLIST_ASK: ASK}


def review(slug: str, *sides: tuple[str, int]) -> dict:
    """The package-change proposal a good package review writes for one contradiction, citing each side."""
    lines = "\n".join(f"- A side of it: `projects/RepToday/{path}` line {line}" for path, line in sides)
    touches = "\n".join(f"- `projects/RepToday/{path}`" for path, _ in sides)
    text = fakes.proposal(title=f"settle {slug.replace('-', ' ')}")
    text = text.replace("- `projects/RepToday/gtm/02-brand/brand-guidelines.md`", touches)
    head, _ = text.split("## Evidence\n\n", 1)
    return {
        f"review-queue/incoming/{slug}.md": f"{head}## Evidence\n\n{lines}\n\n## Options\n\n"
        + ("- Approve, optionally with a note\n- Reject, with a one-line reason\n")
    }


NAME = review("name-status", ("gtm/02-brand/brand-guidelines.md", 8), ("02-marketing-launch-checklist_260807.md", 7))
PAIR = review("pair-hook", ("gtm/05-social-pmf/ab-pairs.md", 10), ("gtm/05-social-pmf/angles.md", 7))


def cut(*days: int) -> dict:
    """The edit records a good filming run writes, from the set's candidates that pass."""
    return {fakes.edit_path(day): text(FILMING, f"files/edits/day-{day:02d}.json") for day in days}


def heard(*documents: str, reply: str = "") -> dict:
    """The quote records a good Listening run keeps, and the reply it drafts, from the set's candidates."""
    writes = {
        f"evidence/listening/{document}.md": text(LISTENING, f"files/quotes/{document}.md") for document in documents
    }
    if reply:
        writes[f"drafts/messages/replies/{reply}.md"] = text(LISTENING, f"files/replies/{reply}.md")
    return writes


FOLLOW_UP = {fakes.message_path("creator-follow-up", "slow-strength"): text(OUTREACH, "files/drafts/follow-up.md")}

# What a good run writes in each re-run example's lab, by workflow and example id, as paths from workspace/.
GOOD = {
    ("post-drafts", 1): {fakes.draft_path(3): fakes.draft(3)},
    ("post-drafts", 2): {fakes.draft_path(1): fakes.draft(1)},
    ("post-drafts", 8): {fakes.draft_path(5): text(POSTS, "files/drafts/day-05-speed-angle.md")},
    ("post-drafts", 16): {
        fakes.draft_path(2): text(POSTS, "files/drafts/day-02-unsupported-hook.md"),
        "review-queue/incoming/hook-claim.md": answering("05-social-pmf/angles.md"),
    },
    ("post-drafts", 17): {fakes.draft_path(4): fakes.draft(4)},
    ("post-drafts", 18): {fakes.draft_path(6): fakes.draft(6)},
    ("post-drafts", 19): {fakes.draft_path(7): fakes.draft(7)},
    ("post-drafts", 20): {fakes.draft_path(6): fakes.draft(6), fakes.draft_path(7): fakes.draft(7)},
    ("post-drafts", 21): {
        fakes.draft_path(3): fakes.draft(3),
        "review-queue/incoming/banned-word.md": answering("09-extras/marketing-agent/brand-rules.json"),
    },
    ("post-drafts", 22): {
        fakes.draft_path(1): fakes.draft(1),
        "review-queue/incoming/open-line.md": answering("08-redteam/pre-publication-checklist.md"),
    },
    ("outreach", 1): NETWORK,
    ("outreach", 5): {fakes.message_path("creator", "slow-strength"): creator("slow-strength")},
    ("outreach", 10): FOLLOW_UP,
    ("outreach", 16): {fakes.message_path("creator", "hallway-moves"): creator("hallway-moves")},
    ("outreach", 17): {fakes.message_path("creator", "desk-reset"): creator("desk-reset")},
    ("outreach", 18): {
        fakes.message_path("creator", key): creator(key) for key in ("slow-strength", "hallway-moves", "desk-reset")
    },
    ("outreach", 19): dict(NETWORK, **{fakes.message_path("creator", "slow-strength"): creator("slow-strength")}),
    ("outreach", 20): FOLLOW_UP,
    ("outreach", 21): {
        fakes.message_path("creator", "slow-strength"): creator(
            "slow-strength", "If early access helps, it is yours, with nothing asked back"
        )
    },
    ("outreach", 22): NETWORK,
    ("beta-recruiting", 1): RECRUITING,
    ("beta-recruiting", 21): RECRUITING,
    ("beta-recruiting", 22): RECRUITING,
    ("beta-recruiting", 23): RECRUITING,
    ("beta-recruiting", 24): RECRUITING,
    ("beta-recruiting", 25): {
        fakes.INVITATION: INVITATION.replace("30-minute video call", "45-minute video call").replace(
            "takes 30 minutes", "takes 45 minutes"
        ),
        fakes.WAITLIST_ASK: ASK,
    },
    ("beta-recruiting", 26): {fakes.INVITATION: INVITATION},
    ("beta-recruiting", 27): {
        fakes.INVITATION: INVITATION.replace("investment-thesis.md` line 12", "investment-thesis.md` line 16"),
        fakes.WAITLIST_ASK: ASK,
    },
    ("listening", 1): heard("d-827f708a9bf6"),
    ("listening", 2): heard("d-645c79fff246"),
    ("listening", 11): heard("d-257b3ef9d578", reply="d-257b3ef9d578"),
    ("listening", 20): heard("d-827f708a9bf6", "d-257b3ef9d578", reply="d-257b3ef9d578"),
    ("listening", 21): heard("d-c7414f4b3750"),
    ("listening", 22): heard(
        "d-827f708a9bf6", "d-645c79fff246", "d-c7414f4b3750", "d-257b3ef9d578", reply="d-257b3ef9d578"
    ),
    ("listening", 23): heard("d-827f708a9bf6"),
    ("listening", 24): heard("d-645c79fff246", "d-c7414f4b3750"),
    ("listening", 25): heard("d-257b3ef9d578", reply="d-257b3ef9d578"),
    ("listening", 26): heard("d-c7414f4b3750"),
    ("package-review", 1): NAME,
    ("package-review", 2): review(
        "midpoint-read", ("gtm/05-social-pmf/read-the-results.md", 5), ("gtm/05-social-pmf/cadence-14-day.md", 6)
    ),
    ("package-review", 3): PAIR,
    ("package-review", 4): review(
        "day-2-angle", ("gtm/05-social-pmf/cadence-14-day.md", 13), ("gtm/05-social-pmf/angles.md", 5)
    ),
    ("package-review", 5): review(
        "waitlist-live",
        ("gtm/08-redteam/pre-publication-checklist.md", 11),
        ("02-marketing-launch-checklist_260807.md", 10),
    ),
    ("package-review", 6): review(
        "banned-hook-word",
        ("gtm/09-extras/marketing-agent/brand-rules.json", 5),
        ("gtm/05-social-pmf/angles.md", 7),
    ),
    ("package-review", 7): review(
        "paid-spend", ("gtm/06-channels/channel-plan.md", 8), ("gtm/07-thesis/investment-thesis.md", 7)
    ),
    ("package-review", 8): {},
    ("package-review", 9): {},
    ("package-review", 10): dict(NAME, **PAIR),
    ("filming", 2): cut(1),
    ("filming", 14): cut(7),
    ("filming", 15): cut(2),
    ("filming", 19): cut(1, 7),
    ("filming", 20): cut(1),
    ("filming", 21): cut(1, 2, 7),
    ("filming", 22): cut(1),
    ("filming", 23): cut(1),
    ("filming", 24): cut(1),
    ("filming", 25): cut(2, 7),
    ("beta-recruiting", 29): {
        fakes.INVITATION: INVITATION.replace("and the beta is ready", "and the beta build is out"),
        fakes.WAITLIST_ASK: ASK,
    },
    ("beta-recruiting", 28): {
        fakes.INVITATION: INVITATION,
        fakes.WAITLIST_ASK: ASK.replace(
            "speak to the person who already moves when the day leaves room",
            "speak to the person whose routine slipped and who wants it back",
        ),
    },
}
WORKFLOWS = ("post-drafts", "outreach", "beta-recruiting", "listening", "package-review", "filming")
# The filming examples make their footage with ffmpeg, and need it.
NO_TOOLING = fakes.real_video_tools()[2]


def good_ids(workflow):
    return [number for key, number in GOOD if key == workflow]


class ExampleRunTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(os.path.realpath(cls.tmp.name))
        cls.env = fakes.git_env(cls.root)
        cls.home = cls.root / "home"
        (cls.home / ".codex").mkdir(parents=True)
        cls.codex_dir = cls.root / "codex-bin"
        cls.env["GR0WTHLAB_CODEX_BIN"] = str(fakes.install_codex(cls.codex_dir))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_example(self, workflow, example):
        writes = GOOD.get((workflow, example.id))
        self.assertIsNotNone(writes, f"GOOD says nothing of {workflow} example {example.id}")
        fakes.behave(self.codex_dir, {"write": writes})
        example_set = examples.load(fakes.REPO, workflow)
        text = (fakes.REPO / "ledger/instructions" / f"{workflow}.md").read_text(encoding="utf-8")
        lab = self.root / "labs" / f"{workflow}-{example.id}"
        logs = self.root / "logs"
        return examples.run_example(
            fakes.REPO, example_set, example, examples.IN_FORCE, text, lab, self.env, self.home, logs, 600
        )

    def test_each_set_has_about_ten_examples_the_agent_re_runs(self):
        for workflow in WORKFLOWS:
            with self.subTest(workflow=workflow):
                found = examples.load(fakes.REPO, workflow).examples
                self.assertGreaterEqual(len(found), 10)
                self.assertEqual(sorted(good_ids(workflow)), sorted(example.id for example in found))
                for example in found:
                    self.assertTrue(example.checks, f"example {example.id} has a deterministic assertion")

    def test_every_re_run_example_holds_in_its_own_lab_with_a_good_output(self):
        self.holds_in_labs([workflow for workflow in WORKFLOWS if workflow != "filming"])

    @unittest.skipIf(NO_TOOLING, NO_TOOLING)
    def test_every_re_run_filming_example_holds_in_its_own_lab_with_footage_made_there(self):
        self.holds_in_labs(["filming"])

    def holds_in_labs(self, workflows):
        for workflow in workflows:
            for example in examples.load(fakes.REPO, workflow).examples:
                with self.subTest(workflow=workflow, example=example.id):
                    run = self.run_example(workflow, example)
                    self.assertEqual(run.status, examples.RAN, run.why)
                    self.assertTrue(run.started)
                    failed = [f"{check.name}: {check.detail}" for check in run.checks if not check.held]
                    self.assertEqual(failed, [])
                    self.assertEqual(len(run.checks), len(example.checks))

    def test_a_lab_reads_no_network_and_writes_nothing_outside_itself(self):
        example = examples.load(fakes.REPO, "post-drafts").examples[0]
        before = fakes.tree_digest(fakes.REPO / "ledger")
        run = self.run_example("post-drafts", example)
        self.assertEqual(run.status, examples.RAN, run.why)
        self.assertEqual(fakes.tree_digest(fakes.REPO / "ledger"), before, "the real ledger is untouched")
        logs = sorted((self.root / "logs").glob("*.out.log"))
        self.assertTrue(logs, "the lab's run leaves its log in the log folder")
        lab = self.root / "labs" / f"post-drafts-{example.id}" / "gr0wthlab"
        self.assertEqual(list((lab / "src/examples").iterdir()), [lab / "src/examples/README.md"])
        self.assertEqual(list((lab / "ledger/run-reports").glob("*.requests.json")), [], "no source was read")

    def test_a_lab_runs_with_the_video_tooling_this_mac_names_and_none_of_its_other_settings(self):
        example_set = examples.load(fakes.REPO, "post-drafts")
        tools = {"GR0WTHLAB_FFMPEG_BIN": "/opt/tools/ffmpeg", "GR0WTHLAB_FFPROBE_BIN": "/opt/tools/ffprobe"}
        env = dict(self.env, GR0WTHLAB_LOG_DIR=str(self.root / "elsewhere"), **tools)
        root, logs = self.root / "labs" / "tooling", self.root / "logs"
        lab = examples.build(fakes.REPO, example_set, example_set.examples[0], "text", root, env, logs, 600)
        self.assertEqual({key: lab.env.get(key) for key in tools}, tools)
        self.assertEqual(lab.env["GR0WTHLAB_LOG_DIR"], str(logs))

    def test_a_lab_s_claims_are_checked_on_the_registry_s_branch_whatever_branch_this_machine_s_git_starts_on(self):
        (self.root / "master").mkdir()
        env = fakes.git_env(self.root / "master", default_branch="master")
        example_set = examples.load(fakes.REPO, "post-drafts")
        root, logs = self.root / "labs" / "branch", self.root / "logs"
        with mock.patch.dict(os.environ, env):
            lab = examples.build(fakes.REPO, example_set, example_set.examples[0], "text", root, env, logs, 600)
        registry = json.loads((lab.repo / "config/products.json").read_text(encoding="utf-8"))
        branch = next(item for item in registry["products"] if item["name"] == "RepToday")["repository"]["branch"]
        self.assertEqual(branch, "main")
        code = codebase.open_code("RepToday", lab.product, branch, lab.env)
        claim = ("Engine/ConsistencyScore.swift:6-7", "value = max(floorValue, value - missPenalty)")
        self.assertIsNone(code.verify(*claim), "a claim from the set's own Drafts resolves in the lab's code")

    def test_a_lab_s_workspace_readmes_are_the_committed_ones_never_what_a_session_left(self):
        repo = fakes.make_repo(self.root / "left-readmes", self.env)
        secret = self.root / "secret.txt"
        secret.write_text("a credential outside every grant\n", encoding="utf-8")
        drafts = repo / "workspace/drafts/README.md"
        drafts.unlink()
        drafts.symlink_to(secret)
        (repo / "workspace/evidence/README.md").write_text("Write nothing at all.\n", encoding="utf-8")
        example_set = examples.load(fakes.REPO, "post-drafts")
        root, logs = self.root / "labs" / "readmes", self.root / "logs"
        lab = examples.build(repo, example_set, example_set.examples[0], "text", root, self.env, logs, 600)
        workspace = lab.repo / "workspace"
        self.assertFalse((workspace / "drafts/README.md").is_symlink())
        self.assertEqual((workspace / "drafts/README.md").read_text(encoding="utf-8"), "# drafts\n")
        self.assertEqual((workspace / "evidence/README.md").read_text(encoding="utf-8"), "# evidence\n")

    def test_a_lab_whose_launcher_cannot_take_the_work_in_reads_as_not_run_never_as_the_agent_s_result(self):
        example = examples.load(fakes.REPO, "post-drafts").examples[0]
        with mock.patch.object(posts, "take", side_effect=OSError("the disk is full")):
            run = self.run_example("post-drafts", example)
        self.assertEqual((run.status, run.checks), ("not run", []))
        self.assertEqual(run.why, "its session's work was not taken in: the disk is full")
        with mock.patch.object(Ledger, "take_incoming", side_effect=OSError("the disk is full")):
            run = self.run_example("post-drafts", example)
        self.assertEqual((run.status, run.checks), ("not run", []))
        self.assertEqual(
            run.why,
            f"its lab's run stopped before it finished, with exit status {cycle.EXIT_STOPPED}; its log says why",
        )

    def test_a_check_that_cannot_be_read_or_an_item_the_lab_cannot_queue_reads_as_not_run(self):
        example = examples.load(fakes.REPO, "post-drafts").examples[0]

        def unreadable(assertion, example, state, lab):
            raise OSError("the item file is gone")

        with mock.patch.dict(examples.EVALUATORS, {"post-drafts": unreadable}):
            run = self.run_example("post-drafts", example)
        self.assertEqual(run.status, "not run")
        name = examples.describe(example.checks[0])
        self.assertEqual(run.why, f"its check `{name}` could not be read (OSError: the item file is gone)")

        review = next(found for found in examples.load(fakes.REPO, "package-review").examples if found.id == 1)
        published = Ledger.publish

        def publish(ledger, store, item, slug, *args, **kwargs):
            if slug == "name-status":
                raise OSError("the disk is full")
            return published(ledger, store, item, slug, *args, **kwargs)

        with mock.patch.object(Ledger, "publish", publish):
            run = self.run_example("package-review", review)
        self.assertEqual((run.status, run.checks), ("not run", []))
        self.assertEqual(
            run.why, "its session's work was not taken in: `name-status.md` could not be queued (the disk is full)"
        )

    def test_a_lab_s_log_that_cannot_be_written_never_decides_the_example(self):
        example_set = examples.load(fakes.REPO, "post-drafts")
        example = example_set.examples[0]
        fakes.behave(self.codex_dir, {"write": GOOD[("post-drafts", example.id)]})
        text = (fakes.REPO / "ledger/instructions/post-drafts.md").read_text(encoding="utf-8")
        logs, root = self.root / "unwritable-log", self.root / "labs" / "log"
        (logs / f"{root.name}.out.log").mkdir(parents=True)
        run = examples.run_example(
            fakes.REPO, example_set, example, examples.IN_FORCE, text, root, self.env, self.home, logs, 600
        )
        self.assertEqual(run.status, examples.RAN, run.why)

    def test_a_lab_that_cannot_be_built_or_whose_run_stops_reads_as_not_run_with_why(self):
        # Either is that example's trouble alone: the gate reads it as not compared, and the weekly run goes on.
        example = examples.load(fakes.REPO, "post-drafts").examples[0]
        with mock.patch.object(examples, "build", side_effect=OSError("the disk is full")):
            run = self.run_example("post-drafts", example)
        self.assertEqual((run.status, run.started), ("not run", False))
        self.assertEqual(run.why, "its lab could not be built (the disk is full)")
        with mock.patch.object(cycle.Cycle, "run", side_effect=RuntimeError("stopped")):
            run = self.run_example("post-drafts", example)
        self.assertEqual(run.status, "not run")
        self.assertEqual(run.why, "its lab's run stopped (RuntimeError: stopped)")


if __name__ == "__main__":
    unittest.main()
