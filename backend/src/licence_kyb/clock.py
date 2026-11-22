"""An injectable clock. Rules and routing never read the system time directly.

"Today" is the date in the UAE: a licence expires at the end of its day there, and from
20:00 UTC the UTC date is still the day before (an expired licence would read as valid).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Protocol

UAE = timezone(timedelta(hours=4), "GST")
"""Gulf Standard Time: UTC+4 all year (the UAE has no daylight saving time)."""


class Clock(Protocol):
    def now(self) -> datetime: ...

    def today(self) -> date: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)

    def today(self) -> date:
        return self.now().astimezone(UAE).date()


@dataclass(frozen=True)
class FixedClock:
    """Used by every test that involves dates (test-cases.md: today is 2026-06-01)."""

    at: datetime = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self.at

    def today(self) -> date:
        return self.at.astimezone(UAE).date()
