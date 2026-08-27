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


def _quarter_of(day: dt.date, fiscal_start_month: int = 1) -> int:
    """Which quarter `day` falls in, counting from the fiscal year's first month.

    With the default of January this is the plain calendar quarter. A firm whose
    year opens in April sets 4, and then July -- calendar Q3 -- reports as Q2.
    """
    return ((day.month - fiscal_start_month) % 12) // 3 + 1


def _quarter_start(day: dt.date, fiscal_start_month: int = 1) -> dt.date:
    """First day of the quarter containing `day`, on the same fiscal calendar."""
    quarter = _quarter_of(day, fiscal_start_month)
    # A date earlier in the calendar year than the fiscal opening month belongs
    # to the fiscal year that began in the previous calendar year.
    fiscal_year = day.year - 1 if day.month < fiscal_start_month else day.year
    month_index = (fiscal_start_month - 1) + 3 * (quarter - 1)
    return dt.date(fiscal_year + month_index // 12, month_index % 12 + 1, 1)


def _ceil_div(numerator: int, denominator: int) -> int:
    return -(-numerator // denominator)


def _number_in_quarter(config: SprintConfig, index: int, start: dt.date) -> int:
    """Position of this sprint among the sprints starting in its own quarter.

    Counts actual sprint start dates rather than dividing elapsed days, so it
    stays correct when a sprint straddles a quarter boundary -- the case the
    original implementation got wrong and clamped to 1.
    """
    cadence = config.cadence
    quarter_start = _quarter_start(start, cadence.fiscal_year_start_month)
    offset = (quarter_start - cadence.anchor).days
    first_index_in_quarter = max(0, _ceil_div(offset, cadence.length_days))
    number = index - first_index_in_quarter + 1

    # start_number labels the anchor's own sprint, so the offset applies only
    # inside the anchor's quarter. Later quarters restart at 1 as usual --
    # otherwise every quarter forever would open at start_number.
    if _quarter_start(cadence.anchor, cadence.fiscal_year_start_month) == quarter_start:
        number += cadence.start_number - 1

    return max(1, number)


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
        number = max(1, index + cadence.start_number)
    else:
        number = _number_in_quarter(config, index, start)

    return Sprint(
        index=index,
        start=start,
        end=end,
        quarter=_quarter_of(start, cadence.fiscal_year_start_month),
        number=number,
    )


def is_sprint_start(config: SprintConfig, day: dt.date) -> bool:
    return sprint_for(config, day).start == day


def is_sprint_end(config: SprintConfig, day: dt.date) -> bool:
    return sprint_for(config, day).end == day
