"""The production clone's git steps, against a throwaway bare remote: fast-forward before, records only after."""

import os
import tempfile
import unittest
from pathlib import Path

from gr0wthlab import records
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

    def save(self):
        return records.save(self.clone, "origin", "main", "RUN1", self.env, MAX)

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
        self.assertIn("ran the current code", result.detail)

    def test_leftover_outputs_are_committed_and_unpushed_records_replayed_onto_new_code(self):
        self.write("workspace/run-reports/old.md")
        self.land_upstream("src/new.py", "x = 1\n")
        result = self.prepare()
        self.assertEqual(result.status, records.UPDATED, result.detail)
        self.assertEqual(result.unpushed, 1)
        self.assertTrue((self.clone / "src/new.py").is_file())
        log = self.git(self.clone, "log", "--format=%s", "-2").splitlines()
        self.assertEqual(log[0], "chore(records): outputs left by a run before 20261011T230000Z")
        self.assertEqual(self.git(self.clone, "rev-parse", "HEAD~1"), self.git(self.remote, "rev-parse", "main"))

    def test_conflicting_records_leave_main_alone(self):
        self.write("workspace/instructions/guide.md", "local refinement\n")
        self.git(self.clone, "add", "--all")
        self.git(self.clone, "commit", "--quiet", "-m", "records")
        before = self.git(self.clone, "rev-parse", "HEAD")
        self.land_upstream("workspace/instructions/guide.md", "reviewed rewrite\n")
        result = self.prepare()
        self.assertEqual((result.status, result.ok_to_run), (records.NOT_REPLAYED, True))
        self.assertEqual(self.git(self.clone, "rev-parse", "HEAD"), before)
        self.assertEqual(self.git(self.clone, "status", "--porcelain"), "")


class SaveTest(RecordsTestCase):
    def test_commits_and_pushes_only_workspace_and_ledger(self):
        self.write("ledger/review-queue/queue.json", "{}\n")
        self.write("workspace/drafts/day-3.md", "a Draft\n")
        result = self.save()
        self.assertEqual(result.status, records.PUSHED, result.detail)
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

    @unittest.skipIf(os.geteuid() == 0, "root can read any file")
    def test_an_unreadable_record_is_left_out_and_never_stops_the_next_run(self):
        self.write("workspace/drafts/locked.md").chmod(0)
        self.write("workspace/drafts/ok.md")
        result = self.save()
        self.assertEqual(result.status, records.PUSHED, result.detail)
        self.assertEqual(self.remote_files(), ["workspace/drafts/ok.md"])
        self.assertIn("workspace/drafts/locked.md (could not be read)", result.excluded)
        result = self.prepare()
        self.assertTrue(result.ok_to_run, result.detail)
        self.assertIn("workspace/drafts/locked.md (could not be read)", result.excluded)

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
    def test_an_unreadable_committed_file_is_set_aside_so_the_replay_after_a_failed_push_goes_through(self):
        self.commit_upstream_and_update("workspace/instructions/guide.md", "committed\n")
        self.write("workspace/instructions/guide.md", "edited\n").chmod(0)
        self.write("workspace/drafts/new.md").chmod(0)
        self.write("workspace/run-reports/r.md")
        self.land_upstream("src/new.py", "x = 1\n")
        folder = self.clone / "ledger/review-queue/set-aside/RUN1"
        lines = records.set_aside_unreadable(self.clone, self.env, folder, "workspace/review-queue/incoming")
        self.assertEqual(
            lines,
            [
                "`workspace/drafts/new.md` could not be read, so it was left uncommitted",
                "`workspace/instructions/guide.md` could not be read, so it was set aside as"
                " `ledger/review-queue/set-aside/RUN1/workspace--instructions--guide.md` and its committed version"
                " put back",
            ],
        )
        self.assertEqual((self.clone / "workspace/instructions/guide.md").read_text(), "committed\n")
        self.assertTrue(os.path.lexists(str(folder / "workspace--instructions--guide.md")))
        result = self.save()
        self.assertEqual(result.status, records.PUSHED, result.detail)
        self.assertIn("had moved; replayed", result.detail)
        self.assertEqual(self.remote_files(), ["workspace/run-reports/r.md"])

    def test_a_moved_remote_is_replayed_and_pushed_once_never_forced(self):
        self.land_upstream("src/new.py", "x = 1\n")
        self.write("workspace/run-reports/r.md")
        result = self.save()
        self.assertEqual(result.status, records.PUSHED, result.detail)
        self.assertIn("had moved; replayed", result.detail)
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
        self.assertEqual(self.prepare().unpushed, 1)
        self.assertEqual(self.save().status, records.PUSHED)


if __name__ == "__main__":
    unittest.main()
