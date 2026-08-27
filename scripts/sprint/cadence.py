"""Sprint date arithmetic.

Every sprint is `anchor + k * length_days` for some integer k, so the cadence is
fully described by two config values: the anchor date (which fixes the start
weekday) and the sprint length (which fixes the end date). Nothing here reads
the clock -- callers pass the day in -- so any cadence can be tested directly.
"""

from __future__ import annotations

import dataclasses
import datetime as dt

from .config import SprintConfig


@dataclasses.dataclass(frozen=True)
class Sprint:
    index: int  # sprints elapsed since the anchor; 0 is the anchor sprint itself
    start: dt.date
    end: dt.date
    quarter: int
    number: int  # sprint number as displayed, per config.cadence.numbering

    @property
    def length_days(self) -> int:
        return (self.end - self.start).days + 1

    def contains(self, day: dt.date) -> bool:
        return self.start <= day <= self.end


def today_in(config: SprintConfig) -> dt.date:
    """The current date in the team's configured timezone, not the runner's."""
    return dt.datetime.now(config.cadence.timezone).date()


def _quarter_of(day: dt.date) -> int:
    return (day.month - 1) // 3 + 1


def _quarter_start(day: dt.date) -> dt.date:
    return dt.date(day.year, 3 * (_quarter_of(day) - 1) + 1, 1)


def _ceil_div(numerator: int, denominator: int) -> int:
    return -(-numerator // denominator)


def _number_in_quarter(config: SprintConfig, index: int, start: dt.date) -> int:
    """Position of this sprint among the sprints starting in its own quarter.

    Counts actual sprint start dates rather than dividing elapsed days, so it
    stays correct when a sprint straddles a quarter boundary -- the case the
    original implementation got wrong and clamped to 1.
    """
    cadence = config.cadence
    quarter_start = _quarter_start(start)
    offset = (quarter_start - cadence.anchor).days
    first_index_in_quarter = max(0, _ceil_div(offset, cadence.length_days))
    return max(1, index - first_index_in_quarter + 1)


def sprint_for(config: SprintConfig, day: dt.date) -> Sprint:
    """The sprint containing `day`."""
    cadence = config.cadence
    elapsed = (day - cadence.anchor).days
    # Floor division, so days before the anchor extrapolate backwards cleanly
    # rather than raising -- useful when back-filling or testing.
    index = elapsed // cadence.length_days
    start = cadence.anchor + dt.timedelta(days=index * cadence.length_days)
    end = start + dt.timedelta(days=cadence.length_days - 1)

    if cadence.numbering == "continuous":
        number = max(1, index + 1)
    else:
        number = _number_in_quarter(config, index, start)

    return Sprint(index=index, start=start, end=end, quarter=_quarter_of(start), number=number)


def is_sprint_start(config: SprintConfig, day: dt.date) -> bool:
    return sprint_for(config, day).start == day


def is_sprint_end(config: SprintConfig, day: dt.date) -> bool:
    return sprint_for(config, day).end == day
