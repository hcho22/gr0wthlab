"""The production clone's git steps, against a throwaway bare remote: fast-forward before, records only after."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gr0wthlab import records, visibility
from tests import fakes

MAX = 1000


class RecordsTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(os.path.realpath(self.tmp.name))
        self.env = fakes.git_env(self.root)
        self.remote = self.root / "remote.git"
        fakes.git(self.root, "init", "--quiet", "--bare", str(self.remote), env=self.env)
        self.upstream = fakes.make_repo(self.root / "upstream", self.env)
        fakes.git(self.upstream, "remote", "add", "origin", str(self.remote), env=self.env)
        fakes.git(self.upstream, "push", "--quiet", "origin", "main", env=self.env)
        self.clone = self.root / "clone"
        fakes.git(self.root, "clone", "--quiet", str(self.remote), str(self.clone), env=self.env)

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, repo, *args):
        return fakes.git(repo, *args, env=self.env)

    def land_upstream(self, relative, text, message="reviewed change"):
        path = self.upstream / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        self.git(self.upstream, "add", "--all")
        self.git(self.upstream, "commit", "--quiet", "-m", message)
        self.git(self.upstream, "push", "--quiet", "origin", "main")

    def write(self, relative, text="record\n"):
        path = self.clone / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def prepare(self):
        return records.prepare(self.clone, "origin", "main", "20261011T230000Z", self.env, MAX)

    def save(self, answer=visibility.PRIVATE):
        github = fakes.GitHub(answer)
        return records.save(self.clone, "origin", "main", "RUN1", self.env, MAX, github(self.clone, "origin", {}))

    def remote_files(self, revision="main"):
        return self.git(self.remote, "show", "--name-only", "--format=", revision).split()


class PrepareTest(RecordsTestCase):
    def test_current_clone(self):
        result = self.prepare()
        self.assertEqual((result.status, result.ok_to_run, result.code_changed), (records.CURRENT, True, False))

    def test_fast_forwards_to_reviewed_code(self):
        self.land_upstream("src/new.py", "x = 1\n")
        result = self.prepare()
        self.assertEqual(result.status, records.UPDATED)
        self.assertTrue(result.code_changed)
        self.assertTrue((self.clone / "src/new.py").is_file())
        self.assertEqual(self.git(self.clone, "rev-parse", "HEAD"), self.git(self.remote, "rev-parse", "main"))

    def test_refuses_another_branch_or_detached_head(self):
        self.git(self.clone, "checkout", "--quiet", "-b", "feature")
        result = self.prepare()
        self.assertEqual((result.status, result.ok_to_run), (records.REFUSED, False))
        self.assertIn("on feature, not main", result.detail)
        self.git(self.clone, "checkout", "--quiet", "--detach", "main")
        self.assertIn("detached HEAD", self.prepare().detail)

    def test_refuses_changes_outside_workspace(self):
        for relative in ("config/run.json", "src/untracked.py"):
            with self.subTest(relative=relative):
                path = self.write(relative, "{}\n")
                result = self.prepare()
                self.assertEqual((result.status, result.ok_to_run), (records.REFUSED, False))
                self.assertIn(relative, result.detail)
                self.git(self.clone, "checkout", "--quiet", "--", ".")
                if path.exists() and relative.startswith("src/"):
                    path.unlink()

    def test_refuses_local_code_commits(self):
        self.write("src/hack.py", "x = 2\n")
        self.git(self.clone, "add", "--all")
        self.git(self.clone, "commit", "--quiet", "-m", "local hack")
        result = self.prepare()
        self.assertEqual((result.status, result.ok_to_run), (records.REFUSED, False))
        self.assertIn("outside workspace/", result.detail)

    def test_offline_runs_the_current_code_and_says_so(self):
        self.git(self.clone, "remote", "set-url", "origin", str(self.root / "missing.git"))
        result = self.prepare()
        self.assertEqual((result.status, result.ok_to_run, result.code_changed), (records.OFFLINE, True, False))
        self.assertIn("does not appear to be a git repository", result.detail)
        self.assertIn("ran the current code", result.detail)

    @unittest.skipIf(os.geteuid() == 0, "root can read any file")
    def test_access_removed_in_the_workspace_is_restored_before_new_code_is_fast_forwarded(self):
        self.land_upstream("workspace/instructions/README.md", "# instructions, reviewed\n")
        (self.clone / "workspace/drafts/README.md").chmod(0)
        (self.clone / "workspace/instructions").chmod(0)
        result = self.prepare()
        self.assertEqual(result.status, records.UPDATED, result.detail)
        restored = "was left without its owner's read and write access, so the launcher restored it"
        self.assertEqual(
            result.repaired,
            [f"`workspace/instructions` {restored}", f"`workspace/drafts/README.md` {restored}"],
        )
        self.assertEqual((self.clone / "workspace/instructions/README.md").read_text(), "# instructions, reviewed\n")

    def test_leftover_outputs_are_committed_and_unpushed_records_replayed_onto_new_code(self):
        self.write("workspace/run-reports/old.md")
        self.land_upstream("src/new.py", "x = 1\n")
        result = self.prepare()
        self.assertEqual(result.status, records.UPDATED, result.detail)
        self.assertEqual(result.unpushed, 1)
        self.assertIn("with 1 unpushed records commit on top", result.detail)
        self.assertTrue((self.clone / "src/new.py").is_file())
        log = self.git(self.clone, "log", "--format=%s", "-2").splitlines()
        self.assertEqual(log[0], "chore(records): records left before the run of 20261011T230000Z")
        self.assertEqual(self.git(self.clone, "rev-parse", "HEAD~1"), self.git(self.remote, "rev-parse", "main"))

    def test_conflicting_records_leave_main_alone(self):
        self.write("workspace/instructions/guide.md", "local refinement\n")
        self.git(self.clone, "add", "--all")
        self.git(self.clone, "commit", "--quiet", "-m", "records")
        before = self.git(self.clone, "rev-parse", "HEAD")
        self.land_upstream("workspace/instructions/guide.md", "reviewed rewrite\n")
        result = self.prepare()
        self.assertEqual((result.status, result.ok_to_run), (records.NOT_REPLAYED, True))
        self.assertIn("1 unpushed records commit could not be replayed onto origin/main", result.detail)
        self.assertEqual(self.git(self.clone, "rev-parse", "HEAD"), before)
        self.assertEqual(self.git(self.clone, "status", "--porcelain"), "")


class SaveTest(RecordsTestCase):
    def test_commits_and_pushes_only_workspace_and_ledger(self):
        self.write("ledger/review-queue/queue.json", "{}\n")
        self.write("workspace/drafts/day-3.md", "a Draft\n")
        result = self.save()
        self.assertEqual(result.status, records.PUSHED, result.detail)
        self.assertEqual(result.detail, "pushed 1 records commit to origin/main")
        self.assertEqual(sorted(self.remote_files()), ["ledger/review-queue/queue.json", "workspace/drafts/day-3.md"])
        message = self.git(self.remote, "log", "--format=%s", "-1", "main")
        self.assertEqual(message, "chore(records): outputs of run RUN1")

    def test_nothing_to_save(self):
        self.assertEqual(self.save().status, records.NOTHING)

    def test_a_readme_change_is_never_committed_and_is_put_back(self):
        self.write("workspace/drafts/README.md", "rewritten\n")
        (self.clone / "ledger/README.md").unlink()
        self.write("workspace/drafts/day-3.md", "a Draft\n")
        result = self.save()
        self.assertEqual(result.status, records.PUSHED, result.detail)
        self.assertEqual(self.remote_files(), ["workspace/drafts/day-3.md"])
        self.assertEqual((self.clone / "workspace/drafts/README.md").read_text(), "# drafts\n")
        self.assertEqual((self.clone / "ledger/README.md").read_text(), "# ledger\n")
        self.assertEqual(self.git(self.clone, "status", "--porcelain"), "")

    def test_never_commits_a_change_outside_workspace(self):
        self.write("workspace/run-reports/r.md")
        self.write("src/stray.py", "x = 1\n")
        result = self.save()
        self.assertEqual(result.status, records.PUSHED)
        self.assertEqual(self.remote_files(), ["workspace/run-reports/r.md"])
        self.assertEqual(result.outside_records, ["src/stray.py"])

    def test_refuses_when_a_path_outside_workspace_is_staged(self):
        self.write("workspace/run-reports/r.md")
        self.write("config/run.json", "{}\n")
        self.git(self.clone, "add", "config/run.json")
        before = self.git(self.remote, "rev-parse", "main")
        result = self.save()
        self.assertEqual(result.status, records.NOT_PUSHED)
        self.assertIn("refusing to commit paths outside workspace/ and ledger/: config/run.json", result.detail)
        self.assertEqual(self.git(self.remote, "rev-parse", "main"), before)
        self.assertEqual(self.git(self.clone, "diff", "--cached", "--name-only"), "config/run.json")

    def test_excludes_links_git_control_files_and_oversized_files(self):
        secret = self.root / "secret.txt"
        secret.write_text("credential\n")
        os.symlink(str(secret), str(self.clone / "workspace/drafts/link.md"))
        os.link(str(secret), str(self.clone / "workspace/drafts/hard.md"))
        self.write("workspace/drafts/.gitattributes", "* filter=x\n")
        self.write("workspace/drafts/big.md", "x" * (MAX + 1))
        self.write("workspace/drafts/ok.md")
        result = self.save()
        self.assertEqual(result.status, records.PUSHED)
        self.assertEqual(self.remote_files(), ["workspace/drafts/ok.md"])
        excluded = " ".join(result.excluded)
        for name in ("link.md", "hard.md", ".gitattributes", "big.md"):
            self.assertIn(name, excluded)

    def test_a_finished_asset_is_never_committed_though_its_record_is(self):
        asset = "ledger/assets/window-1/day-01-0a1b2c3d4e5f.mp4"
        record = "ledger/evidence/filming/assets/window-1-day-01-0a1b2c3d4e5f.json"
        self.write(asset, "video")
        self.write(record, "{}\n")
        result = self.save()
        self.assertEqual(result.status, records.PUSHED, result.detail)
        self.assertEqual(self.remote_files(), [record])
        self.assertEqual(result.excluded, [])
        self.assertTrue((self.clone / asset).is_file())
        # Were the ignore rule ever lost, the records step itself still leaves a finished asset out.
        (self.clone / ".gitignore").write_text("__pycache__/\n")
        self.write("ledger/run-reports/later.md")
        result = self.save()
        self.assertEqual(result.status, records.PUSHED, result.detail)
        self.assertEqual(self.remote_files(), ["ledger/run-reports/later.md"])
        self.assertEqual(result.excluded, [f"{asset} (a finished asset, which never enters git)"])

    def test_the_founders_records_are_saved_with_the_launchers_and_one_holding_an_address_never_is(self):
        """What the Founder recorded at a sitting is committed by the next records step, before the run or after it.
        A record changed by hand to hold an address stays out of git, and its name is not repeated if it is one."""
        decision = '{"exchange": 7, "item": "20261011-x", "decision": "approve"}\n'
        self.write("ledger/founder/decisions/20261011-x.json", decision)
        self.write("ledger/founder/outreach/20261011-y.json", f'{{"note": "write to {fakes.ADDRESS}"}}\n')
        self.write(f"ledger/founder/sittings/{fakes.ADDRESS}.json", "{}\n")
        result = self.prepare()
        self.assertEqual(result.status, records.CURRENT, result.detail)
        self.assertIn(
            "records left before this run, an earlier run's or a sitting's, were committed first", result.detail
        )
        self.assertEqual(
            self.git(self.clone, "show", "--name-only", "--format=").split(),
            ["ledger/founder/decisions/20261011-x.json"],
        )
        held = "one of the Founder's records that holds what looks like an email address, which never enters git"
        self.assertEqual(
            sorted(result.excluded),
            [f"a file whose name is not repeated here ({held})", f"ledger/founder/outreach/20261011-y.json ({held})"],
        )
        saved = self.save()
        self.assertEqual(saved.status, records.PUSHED, saved.detail)
        self.assertEqual(sorted(saved.excluded), sorted(result.excluded))
        self.assertEqual(self.remote_files(), ["ledger/founder/decisions/20261011-x.json"])
        history = self.git(self.remote, "log", "--all", "-p", "--format=%s")
        self.assertNotIn(fakes.ADDRESS, history)
        self.assertNotIn("example.com", history)

    @unittest.skipIf(os.geteuid() == 0, "root can read any file")
    def test_an_unreadable_record_is_left_out_then_restored_before_the_next_run(self):
        self.write("workspace/drafts/locked.md").chmod(0)
        self.write("workspace/drafts/ok.md")
        result = self.save()
        self.assertEqual(result.status, records.PUSHED, result.detail)
        self.assertEqual(self.remote_files(), ["workspace/drafts/ok.md"])
        self.assertIn("workspace/drafts/locked.md (could not be read)", result.excluded)
        result = self.prepare()
        self.assertTrue(result.ok_to_run, result.detail)
        restored = "was left without its owner's read and write access, so the launcher restored it"
        self.assertEqual(result.repaired, [f"`workspace/drafts/locked.md` {restored}"])
        self.assertEqual(result.excluded, [])
        self.assertEqual(self.git(self.clone, "status", "--porcelain"), "")

    @unittest.skipIf(os.geteuid() == 0, "root can read any file")
    def test_an_unreadable_file_among_the_founders_records_named_like_an_address_is_left_out_unnamed(self):
        self.write(f"ledger/founder/sittings/{fakes.ADDRESS}.json", "{}\n").chmod(0)
        self.write("ledger/founder/decisions/locked.json", "{}\n").chmod(0)
        self.write("workspace/drafts/ok.md")
        result = self.save()
        self.assertEqual(result.status, records.PUSHED, result.detail)
        self.assertEqual(self.remote_files(), ["workspace/drafts/ok.md"])
        self.assertEqual(
            sorted(result.excluded),
            [
                "a file whose name is not repeated here (could not be read)",
                "ledger/founder/decisions/locked.json (could not be read)",
            ],
        )

    def commit_upstream_and_update(self, relative, text):
        self.land_upstream(relative, text)
        result = self.prepare()
        self.assertEqual(result.status, records.UPDATED, result.detail)

    @unittest.skipIf(os.geteuid() == 0, "root can read any file")
    def test_an_unread_edit_to_a_committed_file_stops_the_replay_and_says_why(self):
        self.commit_upstream_and_update("workspace/instructions/guide.md", "committed\n")
        self.write("workspace/instructions/guide.md", "edited\n").chmod(0)
        self.write("workspace/run-reports/r.md")
        self.land_upstream("src/new.py", "x = 1\n")
        result = self.save()
        self.assertEqual(result.status, records.NOT_PUSHED)
        self.assertIn("could not be replayed (error: cannot rebase: You have unstaged changes.)", result.detail)

    @unittest.skipIf(os.geteuid() == 0, "root can read any file")
    def test_restored_access_lets_the_replay_after_a_failed_push_go_through(self):
        self.commit_upstream_and_update("workspace/instructions/guide.md", "committed\n")
        self.write("workspace/instructions/guide.md", "edited\n").chmod(0)
        self.write("workspace/run-reports/r.md")
        self.land_upstream("src/new.py", "x = 1\n")
        restored = "was left without its owner's read and write access, so the launcher restored it"
        self.assertEqual(records.restore_access(self.clone), [f"`workspace/instructions/guide.md` {restored}"])
        result = self.save()
        self.assertEqual(result.status, records.PUSHED, result.detail)
        self.assertIn("had moved; replayed", result.detail)
        self.assertEqual(self.remote_files(), ["workspace/instructions/guide.md", "workspace/run-reports/r.md"])

    def test_a_moved_remote_is_replayed_and_pushed_once_never_forced(self):
        self.land_upstream("src/new.py", "x = 1\n")
        self.write("workspace/run-reports/r.md")
        result = self.save()
        self.assertEqual(result.status, records.PUSHED, result.detail)
        self.assertEqual(result.detail, "origin/main had moved; replayed and pushed 1 records commit")
        self.assertEqual(self.remote_files(), ["workspace/run-reports/r.md"])
        self.assertEqual(self.remote_files("main~1"), ["src/new.py"])

    def test_a_rewritten_remote_is_never_overwritten(self):
        self.land_upstream("workspace/run-reports/r.md", "upstream\n")
        self.write("workspace/run-reports/r.md", "local\n")
        before = self.git(self.remote, "rev-parse", "main")
        result = self.save()
        self.assertEqual(result.status, records.NOT_PUSHED)
        self.assertIn("could not be replayed", result.detail)
        self.assertEqual(self.git(self.remote, "rev-parse", "main"), before)
        self.assertEqual(self.git(self.clone, "status", "--porcelain"), "")

    def test_an_unreachable_remote_keeps_the_commit_for_the_next_run(self):
        self.write("workspace/run-reports/r.md")
        self.git(self.clone, "remote", "set-url", "origin", str(self.root / "missing.git"))
        result = self.save()
        self.assertEqual(result.status, records.NOT_PUSHED)
        self.assertIsNotNone(result.commit)
        self.git(self.clone, "remote", "set-url", "origin", str(self.remote))
        prepared = self.prepare()
        self.assertEqual(prepared.unpushed, 1)
        self.assertIn("this run pushes 1 unpushed records commit", prepared.detail)
        self.assertEqual(self.save().status, records.PUSHED)


class VisibilityTest(RecordsTestCase):
    """The records step pushes only on GitHub's plain word, asked again once the run's work was done, that the
    repository is private; anything else keeps the commits local, as a failed push does."""

    def assert_kept_local(self, result, before):
        self.assertEqual(result.status, records.WITHHELD, result.detail)
        self.assertIsNotNone(result.commit)
        self.assertEqual(self.git(self.remote, "rev-parse", "main"), before, "nothing was pushed")
        self.assertEqual(self.git(self.clone, "rev-parse", "HEAD"), result.commit)
        self.assertEqual(self.git(self.clone, "status", "--porcelain"), "")

    def test_a_public_repository_is_never_pushed_to(self):
        self.write("workspace/run-reports/r.md")
        before = self.git(self.remote, "rev-parse", "main")
        with mock.patch.object(records, "push", wraps=records.push) as pushed:
            result = self.save(visibility.PUBLIC)
        self.assert_kept_local(result, before)
        self.assertEqual(pushed.call_count, 0)
        self.assertEqual(
            result.detail,
            "not pushed: the GitHub repository `example/gr0wthlab` is public: a real run would publish its Drafts, its"
            " Evidence, and the Founder's records there, so the repository must be made private first; the commits"
            " stay local for the next run",
        )

    def test_an_answer_that_is_not_private_keeps_the_commits_local_with_the_reason(self):
        self.write("workspace/run-reports/r.md")
        before = self.git(self.remote, "rev-parse", "main")
        result = self.save(visibility.UNCONFIRMED)
        self.assert_kept_local(result, before)
        self.assertIn(
            "not pushed: could not confirm that the GitHub repository is private (gh api exited with 1: error"
            " connecting to api.github.com)",
            result.detail,
        )

    def test_a_moved_remote_is_not_pushed_to_either(self):
        self.land_upstream("src/new.py", "x = 1\n")
        self.write("workspace/run-reports/r.md")
        before = self.git(self.remote, "rev-parse", "main")
        with mock.patch.object(records, "push", wraps=records.push) as pushed:
            result = self.save(visibility.UNCONFIRMED)
        self.assert_kept_local(result, before)
        self.assertEqual(pushed.call_count, 0)

    def test_nothing_to_save_is_said_whatever_github_answered(self):
        self.assertEqual(self.save(visibility.PUBLIC).status, records.NOTHING)

    def test_commits_kept_from_a_public_repository_are_pushed_once_it_is_private(self):
        self.write("workspace/run-reports/r.md")
        self.save(visibility.PUBLIC)
        prepared = self.prepare()
        self.assertIn("this run pushes 1 unpushed records commit", prepared.detail)
        result = self.save()
        self.assertEqual(result.status, records.PUSHED, result.detail)
        self.assertEqual(self.remote_files(), ["workspace/run-reports/r.md"])


class BackgroundTest(RecordsTestCase):
    def test_no_git_command_of_a_test_starts_maintenance(self):
        """git starts its maintenance detached, so it outlives the command that started it and would still be writing
        in a repository while tearDown removes it. git's own trace names every command that ran here: the fixture's,
        the launcher's, and the ones the remote ran to receive a push."""
        trace = self.root / "trace.json"
        self.env["GIT_TRACE2_EVENT"] = str(trace)
        self.land_upstream("src/reviewed.py", "reviewed = True\n")
        self.assertEqual(self.prepare().status, records.UPDATED)
        self.write("workspace/drafts/note.md")
        self.assertEqual(self.save().status, records.PUSHED)
        events = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
        ran = {event["name"] for event in events if event["event"] == "cmd_name"}
        self.assertLessEqual({"commit", "fetch", "merge", "push", "receive-pack"}, ran, "the trace saw each command")
        self.assertEqual(ran & {"maintenance", "gc"}, set())


class GitLimitTest(RecordsTestCase):
    def tearDown(self):
        fakes.stop_leftovers(self.root)
        super().tearDown()

    def test_git_still_running_at_its_limit_is_stopped_with_what_it_started(self):
        """A fetch or a push waits on a helper git starts for the network, which must not outlive the limit."""
        stalled = self.root / "bin" / "git"
        stalled.parent.mkdir()
        stalled.write_text(f'#!/bin/sh\n/bin/sleep 600 &\necho $! > "{self.root}/pids.txt"\nwait\n')
        stalled.chmod(0o755)
        git = records.Git(self.clone, dict(self.env, PATH=f"{stalled.parent}{os.pathsep}{self.env['PATH']}"))
        with self.assertRaises(records.GitError) as stopped:
            git.run("push", "--quiet", "origin", "main", timeout=2)
        self.assertEqual(str(stopped.exception), "git push --quiet origin main failed: timed out after 2s")
        self.assertTrue(fakes.all_gone(fakes.agent_pids(self.root)))


if __name__ == "__main__":
    unittest.main()
