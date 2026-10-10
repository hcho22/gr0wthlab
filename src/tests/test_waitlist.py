"""The Waitlist's anonymous view: the address check before anything else, the view's format, and the counts."""

import base64
import json
import os
import random
import string
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from gr0wthlab import settings, waitlist
from tests import fakes

REPO = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 10, 11, 23, 0, tzinfo=timezone.utc)
RULES = settings.Waitlist(
    "RepToday",
    None,
    ("tiktok", "youtube", "reddit", "network"),
    ("lost-the-routine", "exercises-regularly", "never-had-a-routine"),
    ("lost-the-routine",),
    50,
)
# One read in another process, which the test stops if the read takes too long; it prints the read's status.
READ_ONCE = """
import sys
from dataclasses import replace
from pathlib import Path

from gr0wthlab import waitlist
from tests.test_waitlist import NOW, RULES

print(waitlist.read(replace(RULES, view=Path(sys.argv[1])), NOW).status)
"""


def strings(value):
    """Every string in a JSON value, keys included."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, inner in value.items():
            yield key
            yield from strings(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from strings(inner)


class AddressCheckTest(unittest.TestCase):
    def test_an_address_anywhere_in_a_text_looks_like_one(self):
        for text in (
            fakes.ADDRESS,
            "Jane.Doe+waitlist@mail.example.co.uk",
            "jane@localhost",
            "write to jane@example.com please",
            json.dumps(fakes.address_variant()),
        ):
            with self.subTest(text=text):
                self.assertTrue(waitlist.looks_like_address(text))

    def test_the_view_s_own_values_do_not(self):
        for value in (
            "tiktok",
            "lost-the-routine",
            "2026-10-05",
            "2026-10-11T22:00:00+00:00",
            "Qm7tLx2a",
            "@reptoday",
            "reptoday@",
            "a @ b",
            json.dumps(fakes.waitlist_view()),
        ):
            with self.subTest(value=value):
                self.assertFalse(waitlist.looks_like_address(value))

    def test_random_identifiers_never_pass_for_an_address(self):
        alphabet = string.ascii_letters + string.digits + "-_"
        generator = random.Random(20261011)
        for _ in range(5000):
            identifier = "".join(generator.choice(alphabet) for _ in range(generator.randint(8, 64)))
            self.assertFalse(waitlist.looks_like_address(identifier), identifier)
            self.assertFalse(waitlist.encodes_address(identifier), identifier)


class ReadTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(os.path.realpath(self.tmp.name)) / "view" / "waitlist-view.json"
        self.rules = replace(RULES, view=self.path)
        fakes.mac_time_zone(self)

    def tearDown(self):
        if self.path.is_file():
            self.path.chmod(0o644)
        self.tmp.cleanup()

    def read(self, view=None, raw=None, rules=None, now=NOW):
        if raw is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_bytes(raw)
        elif view is not None:
            fakes.write_view(self.path, view)
        return waitlist.read(rules or self.rules, now)


class CountsTest(ReadTestCase):
    def test_the_twelve_entry_seed(self):
        reading = self.read(fakes.waitlist_view())
        self.assertEqual(reading.status, waitlist.READ, reading.detail)
        self.assertEqual(
            reading.detail, "generated 2026-10-11T22:00:00+00:00: sign-ups 12, good-Fit opt-ins 5 of about 50"
        )
        self.assertEqual(reading.entries, tuple(sorted(entry[0] for entry in fakes.WAITLIST_ENTRIES)))
        overall = reading.cumulative
        self.assertEqual([overall[key] for key in waitlist.COUNTS], [12, 6, 8, 5])
        self.assertEqual(
            {tag: [row[key] for key in waitlist.COUNTS] for tag, row in overall["by_source"].items()},
            {
                "tiktok": [4, 3, 3, 2],
                "youtube": [3, 1, 2, 1],
                "reddit": [2, 1, 1, 1],
                "network": [2, 1, 1, 1],
                "unknown": [1, 0, 1, 0],
            },
        )
        self.assertEqual(
            overall["by_fit"],
            {
                "lost-the-routine": {"sign_ups": 6, "opted_in": 5},
                "exercises-regularly": {"sign_ups": 2, "opted_in": 1},
                "never-had-a-routine": {"sign_ups": 2, "opted_in": 1},
                "unknown": {"sign_ups": 2, "opted_in": 1},
            },
        )
        self.assertEqual(
            [(week["week_of"], [week[key] for key in waitlist.COUNTS]) for week in reading.weeks],
            [("2026-09-28", [5, 3, 3, 2]), ("2026-10-05", [7, 3, 5, 3])],
        )
        self.assertEqual(reading.this_week["by_source"]["tiktok"]["sign_ups"], 2)
        self.assertEqual(reading.this_week["by_fit"]["unknown"]["sign_ups"], 2)
        self.assertEqual(reading.good_fit_opt_ins, 5)

    def test_a_sign_up_with_no_fit_answer_is_unknown_never_not_a_fit(self):
        entries = [("Qm7tLx2a", "tiktok", None, True, "2026-10-06")]
        reading = self.read(fakes.waitlist_view(entries=entries))
        self.assertEqual(reading.cumulative["by_fit"]["unknown"], {"sign_ups": 1, "opted_in": 1})
        self.assertEqual(reading.cumulative["good_fit"], 0)
        self.assertNotIn("not a fit", json.dumps(waitlist.evidence(reading, "RUN", NOW)))

    def test_good_fit_follows_the_configuration(self):
        rules = replace(self.rules, good_fit=("lost-the-routine", "never-had-a-routine"))
        reading = self.read(fakes.waitlist_view(), rules=rules)
        self.assertEqual((reading.cumulative["good_fit"], reading.good_fit_opt_ins), (8, 6))

    def test_every_week_is_listed_even_an_empty_one(self):
        entries = [("Qm7tLx2a", "tiktok", None, True, "2026-09-22"), ("Vb3kPz9w", "reddit", None, False, "2026-10-09")]
        weeks = self.read(fakes.waitlist_view(entries=entries)).weeks
        self.assertEqual(
            [(week["week_of"], week["sign_ups"]) for week in weeks],
            [
                ("2026-09-21", 1),
                ("2026-09-28", 0),
                ("2026-10-05", 1),
            ],
        )

    def test_an_empty_view_counts_zero_this_week(self):
        reading = self.read(fakes.waitlist_view(entries=[]))
        self.assertEqual(reading.status, waitlist.READ)
        self.assertEqual([(week["week_of"], week["sign_ups"]) for week in reading.weeks], [("2026-10-05", 0)])
        self.assertEqual(reading.cumulative["sign_ups"], 0)

    def test_the_run_s_week_ends_at_the_sunday_sitting_on_the_mac_s_clock(self):
        """In winter the Sunday 16:00 run starts at 00:00 UTC on Monday, and it still reports the week then ending."""
        entries = [(f"Entry{n:02d}", "tiktok", "lost-the-routine", True, f"2026-11-0{2 + n % 7}") for n in range(30)]
        sunday_run = datetime(2026, 11, 9, 0, 0, tzinfo=timezone.utc)
        for generated in ("2026-11-08T23:55:00+00:00", "2026-11-09T00:00:05+00:00"):
            with self.subTest(generated=generated):
                reading = self.read(fakes.waitlist_view(generated, entries), now=sunday_run)
                week = reading.this_week
                self.assertEqual((week["week_of"], week["sign_ups"]), ("2026-11-02", 30))
                self.assertEqual([week["week_of"] for week in reading.weeks], ["2026-11-02"])

    def test_a_sign_up_dated_after_the_run_s_week_adds_a_week_and_never_moves_the_run_s(self):
        """Late on a Sunday evening on the Mac a sign-up's UTC date is already Monday's."""
        entries = [("Qm7tLx2a", "tiktok", None, True, "2026-11-06"), ("Vb3kPz9w", "reddit", None, False, "2026-11-09")]
        sunday_evening = datetime(2026, 11, 9, 3, 0, tzinfo=timezone.utc)
        reading = self.read(fakes.waitlist_view("2026-11-09T02:55:00+00:00", entries), now=sunday_evening)
        self.assertEqual(
            [(week["week_of"], week["sign_ups"]) for week in reading.weeks], [("2026-11-02", 1), ("2026-11-09", 1)]
        )
        self.assertEqual((reading.this_week["week_of"], reading.cumulative["sign_ups"]), ("2026-11-02", 2))

    def test_a_view_of_any_age_is_read_and_its_age_kept(self):
        old = self.read(fakes.waitlist_view(), now=NOW + timedelta(days=3))
        self.assertEqual((old.status, old.age), (waitlist.READ, timedelta(days=3, hours=1)))
        self.assertEqual((old.this_week["week_of"], old.this_week["sign_ups"]), ("2026-10-12", 0))
        self.assertEqual(waitlist.evidence(old, "RUN", NOW)["source"]["generated_at"], "2026-10-11T22:00:00+00:00")
        ahead = self.read(fakes.waitlist_view("2026-10-13T22:00:00+00:00"))
        self.assertEqual((ahead.status, ahead.age), (waitlist.READ, -timedelta(days=1, hours=23)))

    def test_evidence_holds_entry_identifiers_and_counts_only(self):
        reading = self.read(fakes.waitlist_view())
        record = waitlist.evidence(reading, "20261011T230000Z-on-demand-abcd", NOW)
        self.assertEqual(
            sorted(record),
            sorted(
                [
                    "format",
                    "run",
                    "product",
                    "read_at",
                    "source",
                    "good_fit",
                    "beta_cohort_bar",
                    "progress",
                    "entries",
                    "weeks",
                    "cumulative",
                    "note",
                ]
            ),
        )
        self.assertEqual(record["source"]["view"], str(self.path))
        self.assertEqual(record["progress"], {"good_fit_opt_ins": 5, "bar": 50})
        values = set(strings([record[key] for key in ("entries", "weeks", "cumulative", "good_fit")]))
        allowed = {entry[0] for entry in fakes.WAITLIST_ENTRIES}
        allowed |= set(RULES.source_tags + RULES.fit_answers) | {"unknown", "week_of", "by_source", "by_fit"}
        allowed |= set(waitlist.COUNTS) | {"2026-09-28", "2026-10-05"}
        self.assertLessEqual(values, allowed)


class NoViewTest(ReadTestCase):
    def test_no_configured_location_is_skipped_because_the_build_has_not_landed(self):
        reading = waitlist.read(RULES, NOW)
        self.assertEqual(reading.status, waitlist.SKIPPED)
        self.assertEqual(
            reading.detail,
            "RepToday's Waitlist build has not landed, so no view location is configured yet (US-ME05)",
        )
        self.assertEqual(waitlist.read(None, NOW).status, waitlist.SKIPPED)

    def test_a_configured_view_that_is_missing_or_a_folder_fails(self):
        self.assertEqual(self.read().detail, f"`{self.path}` is configured but does not exist.")
        self.path.mkdir(parents=True)
        self.assertEqual(self.read().detail, f"`{self.path}` is a folder, not the view's file.")
        self.path.rmdir()

    @unittest.skipIf(os.geteuid() == 0, "root can read any file")
    def test_an_unreadable_view_fails_with_the_reason(self):
        fakes.write_view(self.path, fakes.waitlist_view()).chmod(0o000)
        reading = self.read()
        self.assertEqual(
            (reading.status, reading.detail), (waitlist.FAILED, f"`{self.path}` could not be read: Permission denied.")
        )


class FormatTest(ReadTestCase):
    def failure(self, view=None, raw=None):
        reading = self.read(view, raw)
        self.assertEqual(reading.status, waitlist.FAILED, reading.detail)
        return reading.detail

    def test_files_that_are_not_a_view(self):
        self.assertIn("is not valid JSON (line 1)", self.failure(raw=b"{not json"))
        self.assertIn("is not UTF-8 text", self.failure(raw=b'{"view": "\xff"}'))
        self.assertIn("the file is not a JSON object", self.failure(raw=b"[]"))
        # Closed, so its depth is the file's only fault on an interpreter whose parser reads this deep.
        deep = b"[" * 100_000 + b"]" * 100_000
        self.assertIn("is nested too deeply to be the view", self.failure(raw=deep))
        with mock.patch.object(waitlist, "MAX_VIEW_BYTES", 10):
            self.assertIn("is larger than", self.failure(fakes.waitlist_view()))

    def test_every_departure_from_the_format_is_named(self):
        def view_with(**changes):
            view = fakes.waitlist_view()
            view["entries"][0].update(changes)
            return view

        cases = {
            "entry 1: entry must be 1 to 64 letters, digits, - or _": view_with(entry="has space"),
            "entry 1: source is not one of tiktok, youtube, reddit, network, unknown": view_with(source="instagram"),
            "entry 1: fit is not one of": view_with(fit="not-a-fit"),
            "entry 1: beta_opt_in must be true or false": view_with(beta_opt_in="yes"),
            "entry 1: signed_up_on must be a YYYY-MM-DD date": view_with(signed_up_on="09/29/2026"),
            "entry 1: signed_up_on is after the day the view was generated": view_with(signed_up_on="2026-10-12"),
            "entry 1 must hold exactly entry, source, fit, beta_opt_in, signed_up_on": view_with(name="Jane"),
            "entry 2: entry repeats an earlier entry's identifier": view_with(entry="Vb3kPz9w"),
        }
        for expected, view in cases.items():
            with self.subTest(expected=expected):
                self.assertIn(expected, self.failure(view))
        self.assertIn(
            "the file must hold exactly view, generated_at, entries", self.failure(dict(fakes.waitlist_view(), extra=1))
        )
        self.assertIn("generated_at must be an ISO 8601 time", self.failure(fakes.waitlist_view("2026-10-11 22:00")))
        self.assertIn("view must be 1", self.failure(dict(fakes.waitlist_view(), view=True)))
        self.assertIn("entries must be a list", self.failure(dict(fakes.waitlist_view(), entries={})))

    def test_a_failure_never_repeats_what_the_view_holds(self):
        view = fakes.waitlist_view()
        view["entries"][0].update(source="Jane Doe", fit="Jane's answer")
        detail = self.failure(view)
        self.assertNotIn("Jane", detail)

    def test_a_newer_format_is_never_guessed_at(self):
        self.assertIn(
            "view format 2 is newer than gr0wthlab reads (up to 1)", self.failure(dict(fakes.waitlist_view(), view=2))
        )


class BreachTest(ReadTestCase):
    def refused(self, view=None, raw=None):
        reading = self.read(view, raw)
        self.assertEqual(reading.status, waitlist.REFUSED, reading.detail)
        shown = reading.detail + "".join(reading.places)
        for part in ("@", "jane", "example"):
            self.assertNotIn(part, shown)
        self.assertEqual((reading.entries, reading.weeks, reading.cumulative, reading.sha256), ((), [], {}, None))
        return reading

    def test_the_address_bearing_variant_is_refused_whole(self):
        reading = self.refused(fakes.address_variant())
        self.assertEqual(reading.places, ("entry 3, a field outside the format",))
        self.assertIn("the whole read was discarded and nothing from it was kept", reading.detail)

    def test_an_address_in_any_value_or_name_is_refused(self):
        def view_with(**changes):
            view = fakes.waitlist_view()
            view["entries"][4].update(changes)
            return view

        self.assertEqual(self.refused(view_with(source=fakes.ADDRESS)).places, ("entry 5, `source`",))
        self.assertEqual(self.refused(view_with(entry=fakes.ADDRESS)).places, ("entry 5, `entry`",))
        self.assertEqual(self.refused(view_with(fit=fakes.ADDRESS.upper())).places, ("entry 5, `fit`",))
        keyed = fakes.waitlist_view()
        keyed["entries"][0][fakes.ADDRESS] = True
        self.assertIn("entry 1, a field name", self.refused(keyed).places)
        self.assertEqual(
            self.refused(dict(fakes.waitlist_view(), generated_at=fakes.ADDRESS)).places,
            ("the top of the file, `generated_at`",),
        )

    def test_an_entry_identifier_that_encodes_an_address_is_refused(self):
        address = fakes.ADDRESS.encode()
        for identifier in (
            "jane%40example.com",
            base64.b64encode(address).decode(),
            base64.urlsafe_b64encode(address).decode().rstrip("="),
            address.hex(),
            address.hex().upper(),
        ):
            with self.subTest(identifier=identifier):
                view = fakes.waitlist_view()
                view["entries"][4]["entry"] = identifier
                self.assertEqual(self.refused(view).places, ("entry 5, `entry`",))

    def test_only_the_entry_identifier_is_decoded(self):
        """Every other value must be one the format lists, so an encoded one fails the format and is kept nowhere."""
        view = fakes.waitlist_view()
        view["entries"][4]["source"] = base64.b64encode(fakes.ADDRESS.encode()).decode()
        reading = self.read(view)
        self.assertEqual((reading.status, reading.entries), (waitlist.FAILED, ()))
        self.assertIn("entry 5: source is not one of", reading.detail)

    def test_an_address_the_parsed_view_would_hide_is_still_found(self):
        hidden = b'{"view": 1, "generated_at": "2026-10-11T22:00:00+00:00", "entries": [], "entries": []'
        reading = self.refused(raw=hidden + b', "x": "jane\\u0040example.com"}')
        self.assertTrue(reading.places)
        unparseable = self.refused(raw=b"not json at all, jane.doe@example.com")
        self.assertEqual(unparseable.places, ("the file's text, outside any value the format names",))
        duplicate = b'{"view": 1, "generated_at": "jane@example.com", "generated_at": "2026-10-11T22:00:00+00:00",'
        self.refused(raw=duplicate + b' "entries": []}')

    def test_an_address_in_a_file_too_large_to_read_is_still_refused(self):
        with mock.patch.object(waitlist, "MAX_VIEW_BYTES", 40):
            self.refused(raw=b"jane.doe@example.com" + b" " * 100)


class SpeedTest(ReadTestCase):
    """The address check runs over the whole file before its size or format can fail the read, so it takes time in
    proportion to the file: a check that slowed with the square of a run of characters would hold the run, and its
    lock, for hours."""

    def status_in_time(self, raw):
        self.path.parent.mkdir(parents=True)
        self.path.write_bytes(raw)
        done = subprocess.run(
            [sys.executable, "-c", READ_ONCE, str(self.path)],
            cwd=str(REPO / "src"),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout.strip()

    def test_a_multi_megabyte_run_with_no_delimiter_is_checked_quickly(self):
        self.assertEqual(self.status_in_time(b"a" * 4_000_000), waitlist.FAILED)

    def test_a_multi_megabyte_entry_identifier_is_checked_quickly(self):
        view = fakes.waitlist_view()
        view["entries"][0]["entry"] = base64.b64encode(b"a" * 3_000_000).decode()
        self.assertEqual(self.status_in_time(json.dumps(view).encode()), waitlist.FAILED)


if __name__ == "__main__":
    unittest.main()
