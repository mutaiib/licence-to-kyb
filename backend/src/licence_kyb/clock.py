"""An injectable clock. Rules and routing never read the system time directly."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...

    def today(self) -> date: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)

    def today(self) -> date:
        return self.now().date()


@dataclass(frozen=True)
class FixedClock:
    """Used by every test that involves dates (test-cases.md: today is 2026-06-01)."""

    at: datetime = datetime(2026, 6, 1, 9, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self.at

    def today(self) -> date:
        return self.at.date()
