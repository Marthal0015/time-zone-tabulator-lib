# time-zone-tabulator-lib

Find IANA time zones that match a given UTC offset and current DST status at a chosen instant.

```python
from datetime import datetime, timezone
from time_zone_tabulator_lib import Tabulator

tab = Tabulator()
at = datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)

# Zones at UTC-5 that are NOT observing DST in mid-January.
for info in tab.tabulate(-5 * 3600, False, at=at):
    print(info.name, info.abbreviation, info.utc_offset_hours)
# America/New_York EST -5.0

# Every zone the tabulator knows about, with its state at that instant.
for info in tab.all_infos(at=at):
    print(info.name, info.utc_offset_seconds, info.dst_active)
```

## Why this exists

Given an offset and a DST flag, you usually want the zone name — not the other way around. The standard library gives you `ZoneInfo(name).utcoffset()`, but there is no inverse: no `zone_for_offset(-5, dst=False)`. This library provides that inverse over a fixed, documented set of zones.

The trade-off is coverage for determinism. Scanning the tz database directory is platform dependent (the path differs on Linux, macOS, and Windows) and the set of zones changes between tzdata releases, which makes tests flaky. Instead, `known_zones` is a fixed tuple of thirteen widely available IANA zones. If you need a zone outside that list, pass your own iterable to `Tabulator(zones=...)`; the matching logic is unchanged.

## The awkward edge

The offset you ask for is evaluated at a specific instant, because DST status is not a property of a zone — it is a property of a zone *at a time*. `Tabulator.tabulate` therefore takes an `at` datetime. If you omit it, the tabulator calls the clock you supplied at construction (default: `datetime.now(timezone.utc)`), which is fine for interactive use but non-deterministic for tests. Pass `at=` explicitly, or inject a fake clock with `Tabulator(now=...)`, whenever the answer must be reproducible.

Naive datetimes are rejected with `ValueError`: an offset query without a reference instant is ambiguous across DST boundaries.

## API

- `TimeZoneInfo` — frozen dataclass with `name`, `utc_offset_seconds`, `dst_active`, `abbreviation`, and the derived property `utc_offset_hours`.
- `Tabulator(zones=None, now=None)` — builds a tabulator. `zones` defaults to `known_zones`; `now` defaults to `datetime.now(timezone.utc)`.
  - `tabulate(offset_seconds, dst_active, at=None) -> tuple[TimeZoneInfo, ...]` — matching zones, sorted by name.
  - `all_infos(at=None) -> tuple[TimeZoneInfo, ...]` — every known zone's state, sorted by name.
- `known_zones` — tuple of IANA zone names considered by default.
- `TimezoneDataUnavailableError` — raised when the host has no tzdata for a requested zone.
