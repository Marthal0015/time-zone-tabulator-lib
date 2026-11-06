import unittest
from datetime import datetime, timedelta, timezone

from time_zone_tabulator_lib import TimeZoneInfo, Tabulator, known_zones


# A fixed instant chosen to be unambiguous for the zones in known_zones.
# 2024-01-15 12:00 UTC is northern-hemisphere winter and southern-hemisphere
# summer, so it exercises both DST states without depending on wall-clock time.
WINTER_UTC = datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)

# 2024-07-15 12:00 UTC flips the hemispheres.
SUMMER_UTC = datetime(2024, 7, 15, 12, 0, tzinfo=timezone.utc)


class FakeClock:
    """Deterministic clock for tests that do not pass ``at`` explicitly."""

    def __init__(self, fixed: datetime) -> None:
        self._fixed = fixed

    def __call__(self) -> datetime:
        return self._fixed


class TestKnownZones(unittest.TestCase):
    def test_known_zones_is_non_empty_tuple_of_strings(self):
        self.assertIsInstance(known_zones, tuple)
        self.assertGreater(len(known_zones), 0)
        for name in known_zones:
            self.assertIsInstance(name, str)

    def test_utc_is_present(self):
        self.assertIn("UTC", known_zones)


class TestTabulatorBasics(unittest.TestCase):
    def test_utc_offset_zero_and_no_dst_matches_utc_zone(self):
        tab = Tabulator()
        matches = tab.tabulate(0, False, at=WINTER_UTC)
        names = [m.name for m in matches]
        self.assertIn("UTC", names)
        for m in matches:
            self.assertEqual(m.utc_offset_seconds, 0)
            self.assertFalse(m.dst_active)

    def test_results_are_sorted_by_name(self):
        tab = Tabulator()
        matches = tab.tabulate(0, False, at=WINTER_UTC)
        names = [m.name for m in matches]
        self.assertEqual(names, sorted(names))

    def test_returns_tuple_of_timezoneinfo(self):
        tab = Tabulator()
        matches = tab.tabulate(0, False, at=WINTER_UTC)
        self.assertIsInstance(matches, tuple)
        for m in matches:
            self.assertIsInstance(m, TimeZoneInfo)

    def test_no_match_returns_empty_tuple(self):
        tab = Tabulator()
        # +12:34:56 is not a real offset in the known list.
        matches = tab.tabulate(12 * 3600 + 34 * 60 + 56, False, at=WINTER_UTC)
        self.assertEqual(matches, ())

    def test_naive_datetime_is_rejected(self):
        tab = Tabulator()
        with self.assertRaises(ValueError):
            tab.tabulate(0, False, at=datetime(2024, 1, 15, 12, 0))


class TestDstFiltering(unittest.TestCase):
    def test_northern_hemisphere_dst_flips_between_seasons(self):
        tab = Tabulator()
        winter = tab.tabulate(-5 * 3600, False, at=WINTER_UTC)
        summer = tab.tabulate(-4 * 3600, True, at=SUMMER_UTC)
        self.assertIn("America/New_York", [m.name for m in winter])
        self.assertIn("America/New_York", [m.name for m in summer])

    def test_dst_flag_is_respected(self):
        tab = Tabulator()
        # In January, New York is on EST (-5) and not on DST.
        matches = tab.tabulate(-5 * 3600, True, at=WINTER_UTC)
        self.assertNotIn("America/New_York", [m.name for m in matches])

    def test_southern_hemisphere_dst_in_january(self):
        tab = Tabulator()
        # Sydney in January is AEDT (+11) and on DST.
        matches = tab.tabulate(11 * 3600, True, at=WINTER_UTC)
        self.assertIn("Australia/Sydney", [m.name for m in matches])

    def test_southern_hemisphere_no_dst_in_july(self):
        tab = Tabulator()
        # Sydney in July is AEST (+10) and not on DST.
        matches = tab.tabulate(10 * 3600, False, at=SUMMER_UTC)
        self.assertIn("Australia/Sydney", [m.name for m in matches])


class TestFractionalOffsets(unittest.TestCase):
    def test_india_is_half_hour_offset(self):
        tab = Tabulator()
        matches = tab.tabulate(5 * 3600 + 30 * 60, False, at=WINTER_UTC)
        names = [m.name for m in matches]
        self.assertIn("Asia/Kolkata", names)
        for m in matches:
            self.assertEqual(m.utc_offset_seconds, 19800)
            self.assertFalse(m.dst_active)

    def test_utc_offset_hours_property(self):
        tab = Tabulator()
        matches = tab.tabulate(5 * 3600 + 30 * 60, False, at=WINTER_UTC)
        kolkata = next(m for m in matches if m.name == "Asia/Kolkata")
        self.assertAlmostEqual(kolkata.utc_offset_hours, 5.5, places=6)


class TestClockInjection(unittest.TestCase):
    def test_default_clock_is_used_when_at_is_omitted(self):
        tab = Tabulator(now=FakeClock(WINTER_UTC))
        matches = tab.tabulate(-5 * 3600, False)
        self.assertIn("America/New_York", [m.name for m in matches])

    def test_default_clock_ignored_when_at_is_given(self):
        tab = Tabulator(now=FakeClock(SUMMER_UTC))
        matches = tab.tabulate(-5 * 3600, False, at=WINTER_UTC)
        self.assertIn("America/New_York", [m.name for m in matches])


class TestCustomZoneList(unittest.TestCase):
    def test_custom_zones_restrict_results(self):
        tab = Tabulator(zones=["UTC", "Europe/London"])
        matches = tab.tabulate(0, False, at=WINTER_UTC)
        names = [m.name for m in matches]
        self.assertEqual(names, ["Europe/London", "UTC"])

    def test_all_infos_returns_every_zone(self):
        tab = Tabulator(zones=["UTC", "Asia/Tokyo"])
        infos = tab.all_infos(at=WINTER_UTC)
        self.assertEqual([i.name for i in infos], ["Asia/Tokyo", "UTC"])
        tokyo = next(i for i in infos if i.name == "Asia/Tokyo")
        self.assertEqual(tokyo.utc_offset_seconds, 9 * 3600)
        self.assertFalse(tokyo.dst_active)
        self.assertEqual(tokyo.abbreviation, "JST")


class TestAbbreviation(unittest.TestCase):
    def test_abbreviation_is_reported(self):
        tab = Tabulator(zones=["Europe/Paris"])
        infos = tab.all_infos(at=WINTER_UTC)
        self.assertEqual(infos[0].abbreviation, "CET")

    def test_abbreviation_changes_with_dst(self):
        tab = Tabulator(zones=["Europe/Paris"])
        infos = tab.all_infos(at=SUMMER_UTC)
        self.assertEqual(infos[0].abbreviation, "CEST")
        self.assertTrue(infos[0].dst_active)


class TestEdgeCases(unittest.TestCase):
    def test_empty_zone_list_yields_no_matches(self):
        tab = Tabulator(zones=[])
        self.assertEqual(tab.tabulate(0, False, at=WINTER_UTC), ())
        self.assertEqual(tab.all_infos(at=WINTER_UTC), ())

    def test_at_with_non_utc_tzinfo_still_works(self):
        # Passing a datetime already in a non-UTC zone must not change the
        # answer, because the zone conversion happens inside the tabulator.
        tab = Tabulator()
        paris = timezone(timedelta(hours=1))
        at_paris = WINTER_UTC.astimezone(paris)
        matches = tab.tabulate(0, False, at=at_paris)
        self.assertIn("UTC", [m.name for m in matches])

    def test_negative_offset_matches_western_zones(self):
        tab = Tabulator()
        matches = tab.tabulate(-8 * 3600, False, at=WINTER_UTC)
        self.assertIn("America/Los_Angeles", [m.name for m in matches])


if __name__ == "__main__":
    unittest.main()
