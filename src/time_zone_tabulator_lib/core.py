"""Core implementation for time-zone-tabulator-lib.

Design decisions worth stating up front:

* We use the standard library's ``zoneinfo`` module.  It is the only way to
  get real DST rules without a third-party dependency.  On systems without a
  populated tzdata database ``zoneinfo.ZoneInfo`` raises ``ZoneInfoNotFoundError``;
  we surface that as ``TimezoneDataUnavailableError`` so callers can distinguish
  "no match" from "no data".

* The set of zones is a fixed tuple rather than a scan of the tz database
  directory.  Scanning is platform dependent (the directory location differs
  between Linux, macOS, and Windows) and would make tests non-deterministic on
  machines with different tzdata versions.  A fixed list keeps behaviour stable
  and testable.  ``known_zones`` documents exactly what is covered.

* ``now`` is injected as a callable returning a timezone-aware ``datetime``.
  This makes the DST lookup deterministic in tests without freezing the clock
  globally.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable, Tuple

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class TimezoneDataUnavailableError(RuntimeError):
    """Raised when the host has no usable tzdata for a requested zone."""


# A deliberately small, stable list.  Every entry is a well-known IANA zone
# that exists in essentially every tzdata release since 2018.  Keeping the
# list short makes the README's promise concrete and the tests deterministic.
known_zones: Tuple[str, ...] = (
    "UTC",
    "America/New_York",
    "America/Los_Angeles",
    "America/Sao_Paulo",
    "Europe/London",
    "Europe/Paris",
    "Europe/Moscow",
    "Africa/Cairo",
    "Asia/Kolkata",
    "Asia/Shanghai",
    "Asia/Tokyo",
    "Australia/Sydney",
    "Pacific/Auckland",
)


@dataclass(frozen=True)
class TimeZoneInfo:
    """A single zone's state at a specific instant.

    Attributes:
        name: IANA zone identifier, e.g. ``"Europe/Paris"``.
        utc_offset_seconds: Offset from UTC in seconds at ``at``.
        dst_active: True when the zone is observing daylight saving time.
        abbreviation: Short name reported by the zone, e.g. ``"CEST"``.
    """

    name: str
    utc_offset_seconds: int
    dst_active: bool
    abbreviation: str

    @property
    def utc_offset_hours(self) -> float:
        """Offset in hours.  Fractional for zones such as Asia/Kolkata."""
        return self.utc_offset_seconds / 3600.0


class Tabulator:
    """Finds zones matching a UTC offset and DST status at a given instant.

    Args:
        zones: Iterable of IANA zone names to consider.  Defaults to
            :data:`known_zones`.
        now: Callable returning a timezone-aware ``datetime``.  Defaults to
            ``datetime.now(timezone.utc)``.  Injecting a clock keeps DST
            queries deterministic in tests.
    """

    def __init__(
        self,
        zones: Iterable[str] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._zone_names: Tuple[str, ...] = tuple(zones) if zones is not None else known_zones
        if now is None:
            now = lambda: datetime.now(timezone.utc)
        self._now = now

    def _info_for(self, name: str, at: datetime) -> TimeZoneInfo:
        """Build a :class:`TimeZoneInfo` for one zone at ``at``.

        ``at`` must be timezone-aware.  The offset and DST flag are read from
        the zone's own rules, not from the caller's tzinfo.
        """
        try:
            zone = ZoneInfo(name)
        except ZoneInfoNotFoundError as exc:  # pragma: no cover - data dependent
            raise TimezoneDataUnavailableError(
                f"tzdata for zone {name!r} is not available on this host"
            ) from exc

        localized = at.astimezone(zone)
        offset = localized.utcoffset()
        if offset is None:  # pragma: no cover - defensive; aware datetimes always have one
            raise TimezoneDataUnavailableError(f"zone {name!r} returned no UTC offset")
        dst = localized.dst()
        return TimeZoneInfo(
            name=name,
            utc_offset_seconds=int(offset.total_seconds()),
            dst_active=bool(dst and dst.total_seconds() != 0),
            abbreviation=localized.tzname() or name,
        )

    def tabulate(self, offset_seconds: int, dst_active: bool, at: datetime | None = None) -> Tuple[TimeZoneInfo, ...]:
        """Return zones whose offset and DST status match.

        Args:
            offset_seconds: Desired offset from UTC in seconds.  Fractional
                hours (e.g. 19800 for +05:30) are supported.
            dst_active: Whether the zone must be observing DST.
            at: Instant to evaluate.  Defaults to the injected clock.  Must be
                timezone-aware; a naive datetime is rejected because "now"
                without a zone is ambiguous.

        Returns:
            Tuple of :class:`TimeZoneInfo`, ordered by zone name for stable
            output.
        """
        if at is None:
            at = self._now()
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("at must be a timezone-aware datetime")

        matches = [
            self._info_for(name, at)
            for name in self._zone_names
            if self._matches(self._info_for(name, at), offset_seconds, dst_active)
        ]
        matches.sort(key=lambda info: info.name)
        return tuple(matches)

    @staticmethod
    def _matches(info: TimeZoneInfo, offset_seconds: int, dst_active: bool) -> bool:
        return info.utc_offset_seconds == offset_seconds and info.dst_active == dst_active

    def all_infos(self, at: datetime | None = None) -> Tuple[TimeZoneInfo, ...]:
        """Return every known zone's state at ``at``, ordered by name.

        Useful for inspecting what the tabulator considers when matching.
        """
        if at is None:
            at = self._now()
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("at must be a timezone-aware datetime")
        infos = tuple(sorted((self._info_for(name, at) for name in self._zone_names), key=lambda i: i.name))
        return infos
