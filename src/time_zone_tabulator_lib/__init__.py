"""Time Zone Tabulator: find time zones matching a UTC offset and DST status.

Exports:
    TimeZoneInfo: Immutable record describing one zone at a moment in time.
    Tabulator: Entry point for querying zones by offset and DST status.
    known_zones: Tuple of IANA zone names the tabulator knows about.
"""

from .core import TimeZoneInfo, Tabulator, known_zones

__all__ = ["TimeZoneInfo", "Tabulator", "known_zones"]
