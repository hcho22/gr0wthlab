"""The LaunchAgent starts scheduled runs through the same entry point and launcher as on-demand runs."""

import plistlib
import unittest
from pathlib import Path

from gr0wthlab import schedule
from gr0wthlab.schedule import ScheduleError


class CalendarTest(unittest.TestCase):
    def test_weekly(self):
        self.assertEqual(schedule.weekly("Monday", "07:30"), {"Weekday": 1, "Hour": 7, "Minute": 30})
        self.assertEqual(schedule.weekly("sunday", "0:05"), {"Weekday": 0, "Hour": 0, "Minute": 5})
        for day, time in (("someday", "07:30"), ("monday", "24:00"), ("monday", "7:3"), ("monday", "noon")):
            with self.subTest(day=day, time=time), self.assertRaises(ScheduleError):
                schedule.weekly(day, time)

    def test_once(self):
        self.assertEqual(schedule.once("2026-10-08T18:26"), {"Month": 10, "Day": 8, "Hour": 18, "Minute": 26})
        with self.assertRaises(ScheduleError):
            schedule.once("2026-10-08 18:26")


class LaunchAgentTest(unittest.TestCase):
    def render(self, label="gr0wthlab.weekly-run", overrides=None):
        return plistlib.loads(
            schedule.launch_agent(
                label,
                Path("/srv/gr0wthlab/src/bin/gr0wthlab"),
                Path("/srv/gr0wthlab"),
                Path("/srv/gr0wthlab/src/instructions/weekly-run.md"),
                schedule.weekly("monday", "07:30"),
                overrides or {"GR0WTHLAB_CODEX_BIN": "/opt/codex", "OPENAI_API_KEY": "secret"},
                Path("/logs"),
            )
        )

    def test_runs_the_launcher_entry_point_as_a_scheduled_run(self):
        agent = self.render()
        self.assertEqual(
            agent["ProgramArguments"],
            [
                "/srv/gr0wthlab/src/bin/gr0wthlab",
                "run",
                "--trigger",
                "scheduled",
                "--instruction",
                "/srv/gr0wthlab/src/instructions/weekly-run.md",
            ],
        )
        self.assertEqual(agent["StartCalendarInterval"], {"Weekday": 1, "Hour": 7, "Minute": 30})
        self.assertEqual(agent["WorkingDirectory"], "/srv/gr0wthlab")
        self.assertFalse(agent["RunAtLoad"])
        self.assertEqual(agent["StandardOutPath"], "/logs/gr0wthlab.weekly-run.out.log")

    def test_passes_only_launcher_overrides(self):
        environment = self.render()["EnvironmentVariables"]
        self.assertEqual(environment, {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "GR0WTHLAB_CODEX_BIN": "/opt/codex"})

    def test_rejects_an_unsafe_label(self):
        for label in ("", "../evil", "a b", "-x"):
            with self.subTest(label=label), self.assertRaises(ScheduleError):
                self.render(label=label)


if __name__ == "__main__":
    unittest.main()
