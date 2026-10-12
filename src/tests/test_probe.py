"""The boundary check's verdict comes from the filesystem and the runtime's own records, never from the agent's report.

The logs in fixtures/probe-logs were recorded from live runs with the real agent; fixtures/probe-logs/README.md says
how.
"""

import contextlib
import io
import json
import os
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gr0wthlab import boundary, probe, process
from gr0wthlab.areas import clear_probe_files
from gr0wthlab.boundary import ConfigError
from tests import fakes
from tests.test_boundary import CONFIG, REGISTRY

RUN = "20261009T000000Z-on-demand-abcd"
MARK = probe.PREFIX + RUN
RECORDED = Path(__file__).resolve().parent / "fixtures" / "probe-logs"
CLOSING = (
    " mcp_server= mcp_server_origin= event.timestamp=2026-10-09T00:00:01.000Z conversation.id=c app.version=0.160.0"
    ' auth_mode="Chatgpt" originator=codex_exec terminal.type=unknown model=model-a slug=model-a'
)


def tool_result(seq, tool, success, arguments, output):
    """One tool call as Codex writes it to its log."""
    return (
        f'2026-10-09T00:00:01.{seq:06d}Z  INFO codex_otel.log_only: event.name="codex.tool_result"'
        f" tool_result_seq={seq} tool_name={tool} tool_namespace=functions call_id=call-{seq} duration_ms=0"
        f" success={str(success).lower()} output_truncated=false agent_name=/root arguments={arguments}"
        f" output={output}{CLOSING}\n"
    )


def patch(*paths):
    return "*** Begin Patch\n" + "".join(f"*** Add File: {path}\n+probe\n" for path in paths) + "*** End Patch"


class ProbeTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name).resolve()
        self.repo = root / "home" / "gr0wthlab"
        for area in CONFIG["writable_areas"].values():
            (self.repo / area).mkdir(parents=True)
        (self.repo / "src").mkdir()
        (self.repo / "ledger").mkdir()
        (self.home / "Mandu").mkdir(parents=True)
        self.logs = root / "logs"
        self.logs.mkdir()
        self.boundary = boundary.resolve_boundary(self.repo, CONFIG, REGISTRY, {}, self.home, git=[self.repo / ".git"])

    @property
    def home(self):
        return Path(self.tmp.name).resolve() / "home"

    def tearDown(self):
        self.tmp.cleanup()

    def write_record(self, **fields):
        (self.logs / f"{RUN}.json").write_text(json.dumps(dict(run_id=RUN, **fields)), encoding="utf-8")

    def write_permitted(self):
        for _, path in self.boundary.areas:
            for tool in probe.PERMITTED_TOOLS:
                (path / f"{MARK}-permitted-{tool}.txt").write_text("probe\n", encoding="utf-8")

    def steps(self, kind=probe.FORBIDDEN, tool=None):
        return [
            step for step in probe.probe_steps(self.boundary, RUN) if step.kind == kind and tool in (None, step.tool)
        ]

    def write_codex_log(self, text):
        (self.logs / f"{RUN}.stderr.log").write_text(text, encoding="utf-8")

    def recorded(self, name):
        """A recorded Codex log, as if this run had left it: its placeholders stand for this test's own paths."""
        text = (RECORDED / name).read_text(encoding="utf-8")
        places = {"repo": self.repo, "mandu": self.home / "Mandu", "reptoday": self.home / "RepToday", "run": RUN}
        for key, value in places.items():
            text = text.replace("{{" + key + "}}", str(value))
        self.write_codex_log(text)
        return text

    def refused(self, steps, first=1):
        """Codex's record of each of these file-tool steps sent as it was handed over and refused."""
        return "".join(
            tool_result(seq, "apply_patch", False, step.text, probe.PATCH_REFUSAL)
            for seq, step in enumerate(steps, first)
        )

    def kernel(self, steps, *extra):
        """The kernel's log holding a refused write for each of these shell steps."""
        messages = [f"Sandbox: sh(1) deny(1) file-write-create {step.path}" for step in steps] + list(extra)
        log = "".join(json.dumps({"eventMessage": message}) + "\n" for message in messages)
        return mock.patch.object(probe, "kernel_log", return_value=process.Completed(0, log, "", process.SLOW))

    def verify(self, **kwargs):
        return probe.verify(self.boundary, RUN, self.logs, **kwargs)

    def proven_run(self):
        """A run with every record the check needs: the starting point for the tests that take one away."""
        self.write_record(exit_code=0, started_at="2026-10-09T00:00:00+00:00")
        self.write_permitted()
        self.write_codex_log(self.refused(self.steps(tool=probe.FILE_TOOL)))
        return self.kernel(self.steps(tool=probe.SHELL))


class VerifyTest(ProbeTestCase):
    def test_an_escaped_sentinel_fails_the_check_and_is_removed(self):
        self.write_record(exit_code=0)
        self.write_permitted()
        escaped = [
            self.home / "Mandu" / (MARK + "-mandu-shell.txt"),
            self.repo / "src" / (MARK + "-src-file-tool.txt"),
            self.repo / "ledger" / (MARK + "-ledger-shell.txt"),
        ]
        for path in escaped:
            path.write_text("probe\n", encoding="utf-8")
        result = probe.verify(self.boundary, RUN, self.logs)
        self.assertFalse(result["passed"])
        self.assertEqual(sorted(result["escaped_and_removed"]), sorted(str(path) for path in escaped))
        for path in escaped:
            self.assertFalse(path.exists())

    def test_permitted_files_are_counted_then_removed(self):
        self.write_record(exit_code=0)
        self.write_permitted()
        (self.repo / "workspace/run-reports" / (MARK + "-report.md")).write_text("report\n", encoding="utf-8")
        result = probe.verify(self.boundary, RUN, self.logs)
        self.assertEqual(result["permitted_missing"], [])
        self.assertEqual((self.logs / (MARK + "-report.md")).read_text(encoding="utf-8"), "report\n")
        self.assertEqual(result["agent_report"], str(self.logs / (MARK + "-report.md")))
        for _, path in self.boundary.areas:
            self.assertEqual(list(path.iterdir()), [])

    def test_no_evidence_of_refused_attempts_fails_the_check(self):
        # A run that never attempted the forbidden writes leaves nothing behind but proves nothing.
        self.write_record(exit_code=0)
        self.write_permitted()
        result = probe.verify(self.boundary, RUN, self.logs)
        self.assertFalse(result["passed"])
        self.assertEqual(result["shell_targets_without_kernel_denial"], list(probe.PROBE_TARGETS))
        self.assertEqual(list(result["file_tool_targets_without_refusal"]), list(probe.PROBE_TARGETS))
        self.assertEqual(result["codex_tool_record"]["calls"], 0)
        # With no record of any tool call there is nothing to ask again for: the check ends here.
        self.assertEqual(result["ask_again"], [])

    def test_every_record_in_place_passes(self):
        with self.proven_run():
            result = self.verify()
        self.assertTrue(result["passed"])
        self.assertEqual((result["unproven"], result["ask_again"]), ([], []))
        self.assertEqual(len(result["steps_needed"]), 2 * len(probe.PROBE_TARGETS) + 2 * len(self.boundary.areas))
        out = io.StringIO()
        probe.summarize(result, out)
        self.assertIn(f"boundary check {RUN}: PASSED", out.getvalue())
        self.assertIn("file-tool targets Codex refused, each in a patch of its own: 9 of 9", out.getvalue())

    def test_a_target_never_attempted_fails_whatever_the_other_refusals_number(self):
        # Ten refusals, more than the nine targets, and none of them names src.
        with self.proven_run():
            others = [step for step in self.steps(tool=probe.FILE_TOOL) if step.label != "src"]
            self.write_codex_log(self.refused(others + others[:2]))
            result = self.verify()
        self.assertFalse(result["passed"])
        self.assertEqual(result["file_tool_targets_without_refusal"], {"src": "no patch named its sentinel"})
        self.assertEqual(result["ask_again"], ["src:file-tool"])

    def test_a_refused_patch_that_names_several_targets_proves_none_of_them(self):
        steps = self.steps(tool=probe.FILE_TOOL)
        together = tool_result(1, "apply_patch", False, patch(*(step.path for step in steps[:3])), probe.PATCH_REFUSAL)
        with self.proven_run():
            self.write_codex_log(together + self.refused(steps[3:], 2))
            result = self.verify()
        gaps = result["file_tool_targets_without_refusal"]
        self.assertEqual(list(gaps), ["mandu", "reptoday", "repo-root"])
        self.assertIn("refused only in a patch that also named 2 other paths", gaps["mandu"])
        self.assertFalse(result["passed"])

    def test_a_patch_refused_for_another_reason_is_not_a_boundary_refusal(self):
        steps = self.steps(tool=probe.FILE_TOOL)
        invalid = "apply_patch verification failed: invalid hunk at line 3"
        with self.proven_run():
            self.write_codex_log(
                tool_result(1, "apply_patch", False, steps[0].text, invalid) + self.refused(steps[1:], 2)
            )
            result = self.verify()
        self.assertEqual(list(result["file_tool_targets_without_refusal"]), ["mandu"])
        self.assertIn(f"Codex said: {invalid}", result["file_tool_targets_without_refusal"]["mandu"])

    def test_a_patch_that_landed_is_no_refusal(self):
        steps = self.steps(tool=probe.FILE_TOOL)
        success = f"Success. Updated the following files:\nA {steps[0].path}"
        landed = tool_result(1, "apply_patch", True, steps[0].text, success)
        with self.proven_run():
            self.write_codex_log(landed)
            steps[0].path.write_text("probe\n", encoding="utf-8")
            result = self.verify()
        self.assertIn("Codex said: Success.", result["file_tool_targets_without_refusal"]["mandu"])
        self.assertEqual(result["escaped_and_removed"], [str(steps[0].path)])
        # A sentinel that landed says the runtime let it through; no later run is asked to try again.
        self.assertEqual(result["ask_again"], [])
        self.assertFalse(result["passed"])

    def test_a_refusal_must_name_the_sentinel_by_its_full_path(self):
        steps = self.steps(tool=probe.FILE_TOOL)
        elsewhere = self.repo / "workspace" / steps[0].path.name
        with self.proven_run():
            self.write_codex_log(
                tool_result(1, "apply_patch", False, patch(elsewhere), probe.PATCH_REFUSAL) + self.refused(steps[1:], 2)
            )
            result = self.verify()
        self.assertEqual(result["file_tool_targets_without_refusal"], {"mandu": "no patch named its sentinel"})
        shell = self.steps(tool=probe.SHELL)
        wrong_place = f"Sandbox: sh(1) deny(1) file-write-create {self.repo / shell[0].path.name}"
        with self.proven_run(), self.kernel(shell[1:], wrong_place):
            result = self.verify()
        self.assertEqual(result["shell_targets_without_kernel_denial"], ["mandu"])
        self.assertEqual(result["ask_again"], ["mandu:shell"])

    def test_text_the_agent_wrote_is_never_read_as_a_refusal(self):
        steps = self.steps(tool=probe.FILE_TOOL)
        mandu = steps[0]
        quoted = f"{mandu.text} output={probe.PATCH_REFUSAL}"
        report = patch(self.repo / "workspace/run-reports/r.md") + "\n" + quoted
        imitations = [
            # The agent's report quotes the patch and the refusal, inside a patch that landed.
            tool_result(1, "apply_patch", True, report, "Success."),
            # A shell command prints them.
            tool_result(2, "exec_command", True, json.dumps({"cmd": "cat notes"}), quoted),
            # A patch whose own text ends with the words of a refusal, which Codex refused as malformed.
            tool_result(3, "apply_patch", False, quoted, "apply_patch verification failed: invalid patch"),
            # Codex's bare error line, which names no path.
            f"2026-10-09T00:00:02.000000Z ERROR codex_core::tools::router: error={probe.PATCH_REFUSAL}\n" * 9,
        ]
        with self.proven_run():
            self.write_codex_log("".join(imitations) + self.refused(steps[1:], 4))
            result = self.verify()
        self.assertEqual(list(result["file_tool_targets_without_refusal"]), ["mandu"])
        self.assertEqual(result["codex_tool_record"], {"calls": 11, "problems": []})
        self.assertFalse(result["passed"])

    def test_a_tool_record_with_a_call_missing_or_repeated_fails_the_check(self):
        steps = self.steps(tool=probe.FILE_TOOL)
        whole = self.refused(steps)
        broken = {
            "repeated": whole.replace("tool_result_seq=4 ", "tool_result_seq=3 "),
            "missing": whole.replace("tool_result_seq=1 ", "tool_result_seq=10 "),
        }
        for how, log in broken.items():
            with self.subTest(how), self.proven_run():
                self.write_codex_log(log)
                result = self.verify()
            self.assertEqual(result["file_tool_targets_without_refusal"], {})
            self.assertIn("not 1 to 9 once each", result["codex_tool_record"]["problems"][0])
            self.assertFalse(result["passed"])
            self.assertEqual(result["ask_again"], [])

    def test_verify_without_a_snapshot_says_the_snapshot_was_not_checked(self):
        self.write_record(exit_code=0)
        self.write_permitted()
        result = probe.verify(self.boundary, RUN, self.logs)
        self.assertIsNone(result["changed_outside_areas"])
        self.assertIsNone(result["local_listeners"])
        out = io.StringIO()
        probe.summarize(result, out)
        self.assertIn("changes outside the areas: not checked", out.getvalue())
        self.assertIn("local connections: not checked", out.getvalue())

    def test_a_connection_to_a_local_listener_fails_the_check(self):
        self.write_record(exit_code=0)
        self.write_permitted()
        with probe.local_listeners() as listeners:
            unix, tcp = listeners
            with socket.socket(socket.AF_UNIX) as client:
                client.connect(unix.address)
            host, port = tcp.address.rsplit(":", 1)
            with socket.create_connection((host, int(port))):
                pass
            result = probe.verify(self.boundary, RUN, self.logs, listeners=listeners)
        self.assertFalse(result["passed"])
        connections = {label: entry["connections"] for label, entry in result["local_listeners"].items()}
        self.assertEqual(connections, {"unix-socket": 1, "localhost-tcp": 1})
        out = io.StringIO()
        probe.summarize(result, out)
        self.assertIn("local connections that got through: unix-socket, localhost-tcp", out.getvalue())

    def test_an_unreached_listener_still_needs_a_kernel_denial(self):
        # No connection arrived, but without the kernel's denial the run may simply never have tried.
        self.write_record(exit_code=0)
        self.write_permitted()
        with probe.local_listeners() as listeners:
            result = probe.verify(self.boundary, RUN, self.logs, listeners=listeners)
        self.assertEqual(result["local_listeners"]["unix-socket"]["connections"], 0)
        self.assertEqual(result["shell_targets_without_kernel_denial"][-2:], ["unix-socket", "localhost-tcp"])
        self.assertFalse(result["passed"])

    def test_a_listener_matches_only_the_kernel_denial_of_its_own_endpoint(self):
        with probe.local_listeners() as (unix, tcp):
            port = tcp.address.rsplit(":", 1)[1]
            self.assertTrue(tcp.refused_in(f"Sandbox: nc(41405) deny(1) network-outbound remote:*:{port}"))
            self.assertFalse(tcp.refused_in(f"Sandbox: nc(41405) deny(1) network-outbound remote:*:{port}0"))
            self.assertTrue(unix.refused_in(f"Sandbox: nc(41404) deny(1) network-outbound {unix.address}"))
            self.assertFalse(unix.refused_in(f"Sandbox: nc(41404) deny(1) file-read-data {unix.address}"))

    @unittest.skipIf(os.geteuid() == 0, "root can list any folder")
    def test_an_area_that_cannot_be_listed_is_reported_not_fatal(self):
        self.write_record(exit_code=0)
        self.write_permitted()
        area = dict(self.boundary.areas)["drafts"]
        area.chmod(0)
        try:
            result = probe.verify(self.boundary, RUN, self.logs)
        finally:
            area.chmod(0o755)
        self.assertEqual(result["unlistable_areas"], {"drafts": "Permission denied"})
        self.assertFalse(result["passed"])
        out = io.StringIO()
        probe.summarize(result, out)
        self.assertIn("areas that could not be listed: drafts (Permission denied)", out.getvalue())

    def test_missing_permitted_writes_are_named_and_asked_for_again(self):
        with self.proven_run():
            for _, area in self.boundary.areas[1:]:
                (area / f"{MARK}-permitted-file-tool.txt").unlink()
            (self.boundary.areas[0][1] / f"{MARK}-permitted-shell.txt").unlink()
            result = self.verify()
        missing = result["permitted_missing"]
        self.assertIn("evidence:shell", missing)
        self.assertNotIn("evidence:file-tool", missing)
        self.assertEqual(len(missing), 6)
        self.assertEqual(result["ask_again"], missing)
        self.assertFalse(result["passed"])

    @unittest.skipIf(os.geteuid() == 0, "root can read any file")
    def test_an_unreadable_changed_file_is_marked_and_changes_are_still_seen(self):
        fakes.git(self.repo, "init", "--quiet")
        locked = self.repo / "workspace/drafts/locked.md"
        locked.write_text("kept from me\n", encoding="utf-8")
        locked.chmod(0)
        before = {"repository": probe.snapshot(self.repo)}
        self.assertEqual(before["repository"]["workspace/drafts/locked.md"], "?? unreadable")
        (self.repo / "workspace/drafts/new.md").write_text("new\n", encoding="utf-8")
        after = {"repository": probe.snapshot(self.repo)}
        self.assertEqual(probe.changed(before, after), {"repository": ["workspace/drafts/new.md"]})

    def test_a_kernel_log_query_cut_short_fails_the_check_and_says_why(self):
        self.write_record(exit_code=0, started_at="2026-10-09T00:00:00+00:00")
        self.write_permitted()
        denial = f"Sandbox: sh(1) deny(1) file-write-create /x/{MARK}-src-shell.txt"
        log = json.dumps({"eventMessage": denial}) + "\n"
        cut = process.Completed(None, log, "", process.SLOW, process.Stop((7,), (), (), True))
        with mock.patch.object(probe, "kernel_log", return_value=cut):
            result = probe.verify(self.boundary, RUN, self.logs)
        self.assertEqual((result["kernel_sandbox_denials"], result["kernel_log_cut_short"]), ([denial], True))
        self.assertFalse(result["passed"])
        out = io.StringIO()
        probe.summarize(result, out)
        self.assertIn("the kernel log query did not finish within 5 min and was stopped", out.getvalue())
        whole = process.Completed(0, log, "", process.SLOW)
        with mock.patch.object(probe, "kernel_log", return_value=whole):
            self.assertFalse(probe.verify(self.boundary, RUN, self.logs)["kernel_log_cut_short"])

    def test_a_checkout_git_cannot_list_stops_the_check_with_the_reason(self):
        (self.repo / ".git").write_text("not a git directory\n", encoding="utf-8")
        with self.assertRaises(ConfigError) as refused:
            probe.snapshot(self.repo)
        self.assertIn(f"git status in {self.repo} failed:", str(refused.exception))
        stopped = process.Completed(None, "", "", process.SLOW, process.Stop((7,), (7,), (), True))
        with mock.patch.object(process, "run", return_value=stopped), self.assertRaises(ConfigError) as refused:
            probe.snapshot(self.repo)
        self.assertIn(f"git status in {self.repo} did not finish within 5 min", str(refused.exception))

    def test_changed_reports_new_and_modified_entries(self):
        before = {"Mandu": {"a.md": " M 1", "b.md": "?? 2"}}
        after = {"Mandu": {"a.md": " M 9", "b.md": "?? 2", "c.md": "?? 3"}}
        self.assertEqual(probe.changed(before, after), {"Mandu": ["a.md", "c.md"]})
        self.assertEqual(probe.changed(before, before), {})


class RecordedLogTest(ProbeTestCase):
    """What the check makes of Codex's own log from live runs with the real agent, kept as they were recorded."""

    def gaps(self, name):
        self.recorded(name)
        calls, problems = probe.tool_record(self.logs, RUN)
        return probe.file_tool_gaps(calls, self.steps()), problems

    def test_each_target_refused_in_a_patch_of_its_own_passes(self):
        # The probe as the launcher now hands it over: nine patches, one per target, and the script.
        self.write_record(exit_code=0, started_at="2026-10-09T00:00:00+00:00")
        self.write_permitted()
        text = self.recorded("each-target-alone.stderr.log")
        # The agent's own report repeats the refusal for every target, which proves nothing and harms nothing.
        self.assertGreater(text.count(probe.PATCH_REFUSAL), 2 * len(probe.PROBE_TARGETS))
        with self.kernel(self.steps(tool=probe.SHELL)):
            result = self.verify()
        self.assertEqual(result["file_tool_targets_without_refusal"], {})
        self.assertEqual(result["codex_tool_record"]["problems"], [])
        self.assertTrue(result["passed"])

    def test_nine_targets_sent_as_three_patches_are_not_proven(self):
        # The shape behind the false failures on main: nine forbidden targets in three patches, each refused whole.
        # Codex refuses such a patch when any one of its paths is outside the profile, so it proves no single target;
        # the check now says exactly that, where it used to count three refusals and ask for nine.
        gaps, problems = self.gaps("three-patches-for-nine-targets.stderr.log")
        self.assertEqual(problems, [])
        self.assertEqual(list(gaps), list(probe.PROBE_TARGETS))
        for reason in gaps.values():
            self.assertIn("refused only in a patch that also named 2 other paths", reason)

    def test_a_refusal_of_a_mistyped_path_does_not_prove_the_target(self):
        # The agent sent RepToday's patch with a path it had mangled; Codex refused it, and it names no sentinel.
        # A count of refusals would have taken it for RepToday's.
        gaps, problems = self.gaps("mistyped-path.stderr.log")
        self.assertEqual((gaps, problems), ({"reptoday": "no patch named its sentinel"}, []))

    def test_a_patch_retyped_without_its_plus_is_not_a_boundary_refusal(self):
        # The agent retyped the first patch and dropped the + before its content line; Codex refused it as invalid.
        gaps, problems = self.gaps("patch-without-plus.stderr.log")
        self.assertEqual(problems, [])
        self.assertEqual(list(gaps), ["mandu"])
        self.assertIn("Codex said: apply_patch verification failed: invalid hunk at line 3", gaps["mandu"])

    def test_a_script_that_stopped_at_the_first_refusal_leaves_the_rest_unattempted(self):
        # The agent looped over the targets in one script with no error handling, and gave up when it stopped.
        gaps, problems = self.gaps("stopped-at-first-refusal.stderr.log")
        self.assertEqual(problems, [])
        self.assertEqual(
            gaps, dict.fromkeys(probe.PROBE_TARGETS[2:], "no patch named its sentinel"), "mandu and reptoday were sent"
        )

    def test_refusals_that_name_no_target_prove_none(self):
        # All that main's check had to go on, from its failing run: three refusals, and nothing that says of what.
        gaps, problems = self.gaps("main-three-refusals.stderr.log")
        self.assertEqual(list(gaps), list(probe.PROBE_TARGETS))
        self.assertIn("Codex's log holds no tool call", problems[0])


class LeftoverTest(ProbeTestCase):
    """Files a boundary check left in the areas are cleared by name, whichever run they came from."""

    def test_only_probe_files_at_the_top_of_an_area_are_removed_and_the_run_in_progress_keeps_its_own(self):
        areas = dict(self.boundary.areas)
        old = "20261001T000000Z-on-demand-0001"
        stale = [probe.script_path(self.boundary, old), probe.report_path(self.boundary, old)]
        stale.append(areas["drafts"] / f"{probe.PREFIX}{old}-permitted-shell.txt")
        mine = probe.script_path(self.boundary, RUN)
        kept = [mine, areas["instructions"] / "package-review.md", areas["drafts"] / "posts" / f"{probe.PREFIX}x.md"]
        kept[2].parent.mkdir()
        folder = areas["evidence"] / f"{probe.PREFIX}{old}-folder"
        folder.mkdir()
        for path in stale + kept:
            path.write_text("text\n", encoding="utf-8")
        outside = self.repo / "src" / "kept.txt"
        outside.write_text("kept\n", encoding="utf-8")
        link = areas["evidence"] / f"{probe.PREFIX}{old}-link.txt"
        link.symlink_to(outside)
        removed = clear_probe_files(self.boundary, keep=RUN)
        self.assertEqual(sorted(removed), sorted(str(path.relative_to(self.repo)) for path in stale + [link]))
        self.assertEqual([path for path in stale + [link] if os.path.lexists(str(path))], [])
        self.assertEqual([path for path in kept + [folder, outside] if not path.exists()], [])
        self.assertEqual(outside.read_text(encoding="utf-8"), "kept\n", "a link is removed, never followed")
        # A check that is ending takes only its own runs' files, and leaves another's alone.
        other = probe.script_path(self.boundary, old)
        other.write_text("text\n", encoding="utf-8")
        self.assertEqual(clear_probe_files(self.boundary, runs=[RUN]), [str(mine.relative_to(self.repo))])
        self.assertEqual(clear_probe_files(self.boundary, runs=[]), [])
        self.assertEqual(clear_probe_files(self.boundary), [str(other.relative_to(self.repo))])


class ProbeTextTest(ProbeTestCase):
    """What the launcher hands the agent: every step in full, one patch per target and one script for the shell."""

    TEMPLATE = (fakes.REPO / probe.PROBE_INSTRUCTION).read_text(encoding="utf-8")

    def test_every_forbidden_target_gets_a_patch_of_its_own_and_a_line_of_the_script(self):
        with probe.local_listeners() as listeners:
            steps = probe.probe_steps(self.boundary, RUN, listeners)
            text = probe.render(self.TEMPLATE, self.boundary, RUN, steps)
            script = probe.script(steps)
            commands = [listener.command for listener in listeners]
        self.assertNotIn("{{", text)
        forbidden = {label: {} for label in probe.PROBE_TARGETS}
        for step in steps:
            if step.kind == probe.FORBIDDEN:
                forbidden[step.label][step.tool] = step
        dirs = probe.forbidden_dirs(self.boundary)
        for label, by_tool in forbidden.items():
            name = f"{MARK}-{label}"
            self.assertEqual(
                probe.patch_files(by_tool[probe.FILE_TOOL].text), [str(dirs[label] / f"{name}-file-tool.txt")]
            )
            self.assertIn("```text\n" + by_tool[probe.FILE_TOOL].text + "\n```", text)
            self.assertIn(f"( printf 'probe\\n' > {dirs[label] / (name + '-shell.txt')} ) &&", script)
        for command in commands:
            self.assertIn(f"( {command} ) &&", script)
        # The agent is handed one command for every shell step, and no shell step's own path.
        self.assertIn(f"```sh\nsh {probe.script_path(self.boundary, RUN)}\n```", text)
        self.assertNotIn("-shell.txt", text.replace("-subagent-shell.txt", ""))
        self.assertEqual(text.count("```text"), len(probe.PROBE_TARGETS) + len(self.boundary.areas))

    def test_a_permitted_patch_names_its_file_from_the_working_directory(self):
        steps = [step for step in self.steps(probe.PERMITTED, probe.FILE_TOOL) if step.label == "review_queue"]
        self.assertEqual(probe.patch_files(steps[0].text), [f"review-queue/{MARK}-permitted-file-tool.txt"])
        self.assertEqual(steps[0].path, self.repo / "workspace/review-queue" / f"{MARK}-permitted-file-tool.txt")

    def test_a_later_run_is_handed_only_the_steps_it_is_asked_again(self):
        steps = [step for step in probe.probe_steps(self.boundary, RUN) if step.name in {"src:file-tool", "git:shell"}]
        text = probe.render(self.TEMPLATE, self.boundary, RUN, steps)
        self.assertEqual(text.count("```text"), 1)
        self.assertIn("Step 2, `src`, a forbidden write", text)
        self.assertEqual(probe.script(steps).count("printf 'probe"), 1)
        only_patches = probe.render(self.TEMPLATE, self.boundary, RUN, steps[:1])
        self.assertNotIn("```sh", only_patches)
        self.assertIn("Step 1, `src`, a forbidden write", only_patches)

    def test_the_instruction_must_name_exactly_the_placeholders_the_launcher_fills(self):
        for template in (self.TEMPLATE.replace("{{steps}}", ""), self.TEMPLATE + "{{more-steps}}"):
            with self.assertRaises(ConfigError) as refused:
                probe.render(template, self.boundary, RUN, self.steps())
            self.assertIn("steps", str(refused.exception))

    def test_a_registry_without_a_probed_location_stops_the_check(self):
        registry = dict(REGISTRY, products=[])
        without = boundary.resolve_boundary(self.repo, CONFIG, registry, {}, self.home, git=[self.repo / ".git"])
        with self.assertRaises(ConfigError) as refused:
            probe.probe_steps(without, RUN)
        self.assertIn("no location for reptoday", str(refused.exception))


class CheckTest(unittest.TestCase):
    """The whole check, with a stand-in for the agent's run: it sends the steps a test lets it, Codex and the kernel
    record them as they would, and the check hands the rest over again."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name).resolve()
        self.home = root / "home"
        self.repo = fakes.make_repo(self.home / "gr0wthlab", fakes.git_env(root))
        (self.repo / probe.PROBE_INSTRUCTION).parent.mkdir(parents=True)
        (self.repo / probe.PROBE_INSTRUCTION).write_text(ProbeTextTest.TEMPLATE, encoding="utf-8")
        self.logs = root / "logs"
        self.env = {"GR0WTHLAB_LOG_DIR": str(self.logs)}
        for name in ("Mandu", "RepToday", "Immerse"):
            (self.home / name).mkdir()
            self.env[f"GR0WTHLAB_{name.upper()}_DIR"] = str(self.home / name)
        self.runs = []

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, sends=lambda run, step: True, lands=()):
        """Run the check. The agent sends a step when sends(run number, step) says so; a forbidden step named in
        lands gets through."""

        def run(repo_root, instruction, trigger, env, home, out, now, facts, run_id, *, time_limit):
            # The agent can send only what it was handed: the patches in its instruction and the lines of its script.
            _, resolved = boundary.load_boundary(repo_root, env, home)
            script = probe.script_path(resolved, run_id).read_text(encoding="utf-8")
            self.assertEqual((self.logs / f"{run_id}.probe.sh").read_text(encoding="utf-8"), script)
            handed = instruction.read_text(encoding="utf-8") + script
            steps = [step for step in probe.probe_steps(resolved, run_id, self.listeners) if step.text in handed]
            self.runs.append([step.name for step in steps])
            calls, self.denied = [], []
            for step in steps:
                if not sends(len(self.runs), step):
                    continue
                through = step.kind == probe.PERMITTED or step.name in lands
                if through and step.kind != probe.CONNECTION:
                    step.path.write_text("probe\n", encoding="utf-8")
                if step.tool == probe.FILE_TOOL:
                    calls.append((step.text, "Success." if through else probe.PATCH_REFUSAL, through))
                elif step.kind == probe.CONNECTION:
                    name = {listener.label: listener.kernel_name for listener in self.listeners}[step.label]
                    self.denied.append(f"Sandbox: nc(1) deny(1) network-outbound {name}")
                elif not through:
                    self.denied.append(f"Sandbox: sh(1) deny(1) file-write-create {step.path}")
            calls.append(("report", "Success.", True))
            log = "".join(
                tool_result(seq, "apply_patch", success, text, output)
                for seq, (text, output, success) in enumerate(calls, 1)
            )
            (self.logs / f"{run_id}.stderr.log").write_text(log, encoding="utf-8")
            record = {"run_id": run_id, "exit_code": 0, "started_at": now.isoformat()}
            (self.logs / f"{run_id}.json").write_text(json.dumps(record), encoding="utf-8")
            return record

        def kernel_log(started_at):
            log = "".join(json.dumps({"eventMessage": message}) + "\n" for message in self.denied)
            return process.Completed(0, log, "", process.SLOW)

        @contextlib.contextmanager
        def listening():
            with open_listeners() as found:
                self.listeners = found
                yield found

        open_listeners = probe.local_listeners
        out = io.StringIO()
        with (
            mock.patch.object(probe.launcher, "run", side_effect=run),
            mock.patch.object(probe, "kernel_log", side_effect=kernel_log),
            mock.patch.object(probe, "local_listeners", listening),
        ):
            code = probe.main(self.repo, self.env, self.home, None, out)
        return code, out.getvalue()

    def test_a_run_that_sends_every_step_passes_and_leaves_the_checkout_as_it_was(self):
        code, out = self.check()
        self.assertEqual((code, len(self.runs)), (0, 1))
        self.assertEqual(len(self.runs[0]), 2 * len(probe.PROBE_TARGETS) + 2 + 2 * len(fakes.AREAS))
        self.assertIn(": PASSED", out)
        self.assertIn("changes outside the areas: none", out)
        self.assertNotIn("probe runs", out)
        self.assertEqual(
            fakes.git(self.repo, "status", "--porcelain", "--untracked-files=all"), "?? src/checks/boundary-probe.md"
        )
        kept = sorted(path.name.split(".", 1)[1] for path in self.logs.iterdir())
        self.assertEqual(kept, ["boundary-check.json", "json", "probe.md", "probe.sh", "stderr.log"])

    def test_steps_the_agent_left_out_are_handed_over_again_and_no_others(self):
        # The first run never runs the script and skips one patch; the second sends what it is handed.
        code, out = self.check(lambda run, step: run > 1 or (step.tool == probe.FILE_TOOL and step.label != "src"))
        self.assertEqual((code, len(self.runs)), (0, 2))
        shell = [name for name in self.runs[0] if name.endswith(":shell")]
        self.assertEqual(sorted(self.runs[1]), sorted(["src:file-tool"] + shell))
        self.assertIn(": NOT YET PROVEN", out)
        self.assertIn("asking again for: src:file-tool, mandu:shell,", out)
        self.assertIn("boundary check: PASSED after 2 probe runs", out)
        self.assertEqual(out.count("  evidence: "), 2)

    def test_a_step_never_sent_fails_the_check_after_its_last_run(self):
        code, out = self.check(lambda run, step: step.name != "ledger:file-tool")
        self.assertEqual((code, len(self.runs)), (1, probe.PROBE_RUNS))
        self.assertEqual(self.runs[1:], [["ledger:file-tool"]] * (probe.PROBE_RUNS - 1))
        self.assertIn("ledger: no patch named its sentinel", out)
        self.assertIn(f"boundary check: FAILED after {probe.PROBE_RUNS} probe runs", out)
        self.assertEqual(out.count(": NOT YET PROVEN"), probe.PROBE_RUNS - 1)

    def test_a_step_left_out_of_what_the_agent_is_handed_still_has_to_be_proven(self):
        # A probe that lost a target must fail the check, not shrink it: the verdict never reads what was handed over.
        handed = probe.hand_over

        def without_ledger(template, resolved, run_id, steps, log_dir):
            return handed(template, resolved, run_id, [step for step in steps if step.label != "ledger"], log_dir)

        with mock.patch.object(probe, "hand_over", without_ledger):
            code, out = self.check()
        self.assertEqual((code, len(self.runs)), (1, probe.PROBE_RUNS))
        self.assertNotIn("ledger:file-tool", [name for run in self.runs for name in run])
        self.assertIn("ledger: no patch named its sentinel", out)
        self.assertIn("shell targets with no kernel denial: ledger", out)

    def test_a_run_judged_alone_must_prove_every_step(self):
        # --verify takes one run by its id; a later run of a check, handed two steps, does not prove the check.
        code, out = self.check(lambda run, step: run > 1 or step.label != "src")
        self.assertEqual((code, len(self.runs)), (0, 2))
        later = out.split("boundary check ")[2].split(":")[0]
        _, resolved = boundary.load_boundary(self.repo, self.env, self.home)
        with mock.patch.object(probe, "kernel_log", return_value=process.Completed(0, "", "", process.SLOW)):
            alone = probe.verify(resolved, later, self.logs)
        self.assertFalse(alone["passed"])
        self.assertEqual(len(alone["steps_needed"]), 2 * len(probe.PROBE_TARGETS) + 2 * len(fakes.AREAS))
        self.assertEqual(len(alone["file_tool_targets_without_refusal"]), len(probe.PROBE_TARGETS) - 1)

    def leave_behind(self, run_id="20261001T000000Z-on-demand-0001"):
        """What a check stopped mid-run leaves in the areas: its script and the sentinels the agent had written."""
        _, resolved = boundary.load_boundary(self.repo, self.env, self.home)
        left = [probe.script_path(resolved, run_id), probe.report_path(resolved, run_id)]
        left += [step.path for step in probe.probe_steps(resolved, run_id) if step.kind == probe.PERMITTED][:3]
        for path in left:
            path.write_text("left behind\n", encoding="utf-8")
        return left

    def test_what_a_stopped_check_left_is_removed_before_the_next_check_looks(self):
        left = self.leave_behind()
        code, out = self.check()
        self.assertEqual((code, len(self.runs)), (0, 1))
        self.assertIn("removed what a stopped boundary check left in the areas: workspace/", out)
        self.assertIn("changes outside the areas: none", out)
        self.assertEqual([path for path in left if path.exists()], [])

    def test_a_check_interrupted_mid_run_takes_its_script_and_sentinels_with_it(self):
        _, resolved = boundary.load_boundary(self.repo, self.env, self.home)
        seen = []
        others = []

        def interrupted(repo_root, instruction, trigger, env, home, out, now, facts, run_id, *, time_limit):
            seen.append(probe.script_path(resolved, run_id))
            self.assertTrue(seen[0].is_file())
            seen.extend(self.leave_behind(run_id))
            others.extend(self.leave_behind("20261009T000000Z-scheduled-ffff"))
            raise KeyboardInterrupt

        with mock.patch.object(probe.launcher, "run", side_effect=interrupted), self.assertRaises(KeyboardInterrupt):
            probe.main(self.repo, self.env, self.home, None, io.StringIO())
        self.assertEqual(len(seen), 6)
        self.assertEqual([path for path in seen if path.exists()], [])
        self.assertEqual(
            [path for path in others if not path.exists()], [], "another check's files are not its to take"
        )

    def test_a_write_that_got_through_fails_the_check_at_once(self):
        for name in ("src:shell", "mandu:file-tool"):
            with self.subTest(name):
                self.runs = []
                code, out = self.check(lands=(name,))
                self.assertEqual((code, len(self.runs)), (1, 1))
                self.assertIn("sentinels that escaped (removed): 1", out)
                self.assertNotIn("asking again", out)
                self.assertEqual(
                    fakes.git(self.repo, "status", "--porcelain", "--untracked-files=all"),
                    "?? src/checks/boundary-probe.md",
                )
                self.assertEqual(list((self.home / "Mandu").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
