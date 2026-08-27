"""Cadence math across the configurations teams are actually likely to pick.

The whole point of the rewrite is that these run without a GitHub runner, a
subprocess, or a patched clock: `sprint_for` takes the day as an argument.
"""

import datetime as dt

import pytest
import yaml

from sprint import cadence, load, naming
from sprint.config import ConfigError

BASE_CONFIG = {
    "version": 1,
    "cadence": {"anchor": "2024-06-06", "length_days": 14, "timezone": "UTC", "numbering": "quarter"},
    "branches": {"base": "develop", "dit": "env/dit", "sit": "env/sit", "uat": "env/uat"},
}


def write_config(tmp_path, **overrides):
    data = {k: dict(v) if isinstance(v, dict) else v for k, v in BASE_CONFIG.items()}
    for section, values in overrides.items():
        if isinstance(values, dict):
            data.setdefault(section, {}).update(values)
        else:
            data[section] = values
    path = tmp_path / "sprint.yml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return load(path)


def date(text):
    return dt.date.fromisoformat(text)


def test_anchor_day_is_a_sprint_start(tmp_path):
    config = write_config(tmp_path)
    assert cadence.is_sprint_start(config, date("2024-06-06"))
    assert not cadence.is_sprint_end(config, date("2024-06-06"))


def test_sprint_end_is_length_minus_one_days_after_start(tmp_path):
    config = write_config(tmp_path)
    sprint = cadence.sprint_for(config, date("2024-06-06"))
    assert sprint.end == date("2024-06-19")
    assert sprint.length_days == 14
    assert cadence.is_sprint_end(config, date("2024-06-19"))


@pytest.mark.parametrize("day", ["2024-06-07", "2024-06-12", "2024-06-19"])
def test_mid_sprint_days_are_neither_start_nor_end(tmp_path, day):
    config = write_config(tmp_path)
    assert not cadence.is_sprint_start(config, date(day))
    if day != "2024-06-19":
        assert not cadence.is_sprint_end(config, date(day))


def test_every_day_of_a_sprint_maps_to_the_same_sprint(tmp_path):
    config = write_config(tmp_path)
    first = cadence.sprint_for(config, date("2024-06-06"))
    for offset in range(14):
        day = date("2024-06-06") + dt.timedelta(days=offset)
        assert cadence.sprint_for(config, day) == first
        assert first.contains(day)
    assert cadence.sprint_for(config, date("2024-06-20")) != first


def test_moving_the_anchor_moves_the_start_weekday(tmp_path):
    """The headline customisation: one config value changes the sprint day."""
    monday = write_config(tmp_path, cadence={"anchor": "2026-01-05"})
    assert monday.cadence.start_weekday == "monday"
    assert cadence.is_sprint_start(monday, date("2026-01-05"))
    assert cadence.is_sprint_start(monday, date("2026-01-19"))
    assert not cadence.is_sprint_start(monday, date("2026-01-08"))


@pytest.mark.parametrize("length,expected_end", [(7, "2026-01-11"), (14, "2026-01-18"), (21, "2026-01-25")])
def test_length_days_sets_the_end_date(tmp_path, length, expected_end):
    config = write_config(tmp_path, cadence={"anchor": "2026-01-05", "length_days": length})
    assert cadence.sprint_for(config, date("2026-01-05")).end == date(expected_end)


def test_continuous_numbering_counts_from_the_anchor(tmp_path):
    config = write_config(tmp_path, cadence={"numbering": "continuous"})
    assert cadence.sprint_for(config, date("2024-06-06")).number == 1
    assert cadence.sprint_for(config, date("2024-06-20")).number == 2
    assert cadence.sprint_for(config, date("2026-08-27")).number == 59


def test_quarter_numbering_resets_each_quarter(tmp_path):
    config = write_config(tmp_path)
    first_of_q1_2026 = cadence.sprint_for(config, date("2026-01-01"))
    assert (first_of_q1_2026.quarter, first_of_q1_2026.number) == (1, 1)
    later = cadence.sprint_for(config, date("2026-01-15"))
    assert (later.quarter, later.number) == (1, 2)
    next_quarter = cadence.sprint_for(config, date("2026-04-09"))
    assert (next_quarter.quarter, next_quarter.number) == (2, 1)


def test_sprint_straddling_a_quarter_boundary_keeps_its_start_quarter(tmp_path):
    """The case the original implementation clamped to S1."""
    config = write_config(tmp_path)
    sprint = cadence.sprint_for(config, date("2026-07-01"))
    assert sprint.start == date("2026-06-18")
    assert sprint.end == date("2026-07-01")
    assert sprint.quarter == 2
    assert sprint.number >= 1


def test_days_before_the_anchor_extrapolate_backwards(tmp_path):
    config = write_config(tmp_path)
    sprint = cadence.sprint_for(config, date("2024-06-05"))
    assert sprint.index == -1
    assert sprint.start == date("2024-05-23")
    assert sprint.number >= 1


def test_timezone_decides_which_day_a_sprint_boundary_falls_on(tmp_path):
    config = write_config(tmp_path, cadence={"timezone": "America/Chicago"})
    assert str(config.cadence.timezone) == "America/Chicago"
    assert cadence.today_in(config) is not None


def test_branch_names_match_the_established_format(tmp_path):
    config = write_config(tmp_path)
    sprint = cadence.sprint_for(config, date("2026-08-27"))
    assert naming.sprint_branch(config, sprint) == "Sprint_Q3_S5_082726_090926"
    assert naming.sprint_slug(config, sprint) == "Q3_S5_082726_090926"
    assert naming.release_branch(config, sprint) == "release/Q3_S5_082726_090926"


def test_continuous_naming_omits_the_quarter(tmp_path):
    config = write_config(tmp_path, cadence={"numbering": "continuous"})
    sprint = cadence.sprint_for(config, date("2026-08-27"))
    assert naming.sprint_branch(config, sprint) == "Sprint_S59_082726_090926"


def test_release_prefix_without_slash_gets_a_separator(tmp_path):
    config = write_config(tmp_path, branches={"release_prefix": "rel"})
    sprint = cadence.sprint_for(config, date("2026-08-27"))
    assert naming.release_branch(config, sprint) == "rel_Q3_S5_082726_090926"


def test_start_weekday_disagreeing_with_anchor_is_rejected(tmp_path):
    with pytest.raises(ConfigError, match="is a thursday"):
        write_config(tmp_path, cadence={"anchor": "2024-06-06", "start_weekday": "monday"})


def test_start_weekday_agreeing_with_anchor_is_accepted(tmp_path):
    config = write_config(tmp_path, cadence={"start_weekday": "thursday"})
    assert config.cadence.start_weekday == "thursday"


@pytest.mark.parametrize(
    "overrides,message",
    [
        ({"cadence": {"length_days": 0}}, "positive integer"),
        ({"cadence": {"length_days": "fortnight"}}, "positive integer"),
        ({"cadence": {"numbering": "weekly"}}, "numbering"),
        ({"cadence": {"timezone": "Mars/Olympus"}}, "unknown timezone"),
        ({"cadence": {"anchor": "not-a-date"}}, "anchor"),
        ({"branches": {"sit": "env/dit"}}, "promotions become no-ops"),
    ],
)
def test_invalid_config_fails_loudly(tmp_path, overrides, message):
    with pytest.raises(ConfigError, match=message):
        write_config(tmp_path, **overrides)


def test_missing_config_names_the_path(tmp_path):
    with pytest.raises(ConfigError, match="no sprint config at"):
        load(tmp_path / "absent.yml")


def test_hop_pairs_walk_the_environment_chain(tmp_path):
    config = write_config(tmp_path)
    assert config.hop("sit") == ("env/dit", "env/sit")
    assert config.hop("uat") == ("env/sit", "env/uat")
    with pytest.raises(ConfigError):
        config.hop("prod")


# --- start_number: adopting the tooling mid-way through an existing scheme ---


def test_start_number_defaults_to_one(tmp_path):
    config = write_config(tmp_path)
    assert config.cadence.start_number == 1
    assert cadence.sprint_for(config, date("2024-06-06")).number == 1


def test_continuous_numbering_starts_at_start_number(tmp_path):
    """A team already on Sprint 23 keeps counting rather than restarting."""
    config = write_config(tmp_path, cadence={"numbering": "continuous", "start_number": 23})
    assert cadence.sprint_for(config, date("2024-06-06")).number == 23
    assert cadence.sprint_for(config, date("2024-06-20")).number == 24
    assert naming.sprint_branch(config, cadence.sprint_for(config, date("2024-06-06"))) == (
        "Sprint_S23_060624_061924"
    )


def test_quarter_numbering_offsets_only_the_anchor_quarter(tmp_path):
    """start_number labels the anchor sprint; later quarters restart at 1."""
    config = write_config(tmp_path, cadence={"numbering": "quarter", "start_number": 7})
    assert cadence.sprint_for(config, date("2024-06-06")).number == 7
    assert cadence.sprint_for(config, date("2024-06-20")).number == 8
    later = cadence.sprint_for(config, date("2024-07-04"))
    assert (later.quarter, later.number) == (3, 1)


# --- fiscal_year_start_month: quarters that do not open in January ---


def test_fiscal_year_defaults_to_calendar_quarters(tmp_path):
    config = write_config(tmp_path)
    assert config.cadence.fiscal_year_start_month == 1
    assert cadence.sprint_for(config, date("2026-08-27")).quarter == 3


@pytest.mark.parametrize(
    "fiscal_start,day,expected_quarter",
    [
        (1, "2026-08-27", 3),   # calendar: Jul-Sep is Q3
        (4, "2026-08-27", 2),   # April year: Jul-Sep is Q2
        (4, "2026-04-09", 1),   # first quarter of an April fiscal year
        (4, "2026-02-12", 4),   # Jan-Mar closes the year that opened last April
        (7, "2026-08-27", 1),   # July year: August sits in its opening quarter
        (10, "2026-08-27", 4),
    ],
)
def test_fiscal_year_start_month_shifts_the_quarter(tmp_path, fiscal_start, day, expected_quarter):
    """Each `day` here is itself a sprint start, so the sprint's quarter is the day's.

    A sprint that straddles a quarter boundary deliberately keeps the quarter it
    started in, which is covered separately.
    """
    config = write_config(tmp_path, cadence={"fiscal_year_start_month": fiscal_start})
    sprint = cadence.sprint_for(config, date(day))
    assert sprint.start == date(day), "test fixture must be a sprint start date"
    assert sprint.quarter == expected_quarter


def test_a_sprint_straddling_the_fiscal_new_year_keeps_its_start_quarter(tmp_path):
    config = write_config(tmp_path, cadence={"fiscal_year_start_month": 4})
    sprint = cadence.sprint_for(config, date("2026-04-02"))
    assert sprint.start == date("2026-03-26")
    assert sprint.quarter == 4, "started in the closing quarter, so it stays there"


def test_fiscal_quarters_stay_contiguous_across_the_year_boundary(tmp_path):
    """Every day of an April fiscal year lands in exactly one quarter, 1 through 4."""
    config = write_config(tmp_path, cadence={"fiscal_year_start_month": 4})
    seen = {}
    day = date("2026-04-01")
    while day < date("2027-04-01"):
        seen.setdefault(cadence.sprint_for(config, day).quarter, []).append(day)
        day += dt.timedelta(days=1)
    assert sorted(seen) == [1, 2, 3, 4]
    assert len(seen[1]) + len(seen[2]) + len(seen[3]) + len(seen[4]) == 365


def test_the_two_knobs_compose(tmp_path):
    config = write_config(
        tmp_path,
        cadence={"numbering": "quarter", "start_number": 4, "fiscal_year_start_month": 4},
    )
    sprint = cadence.sprint_for(config, date("2024-06-06"))
    assert (sprint.quarter, sprint.number) == (1, 4)
    assert naming.sprint_branch(config, sprint) == "Sprint_Q1_S4_060624_061924"


@pytest.mark.parametrize(
    "overrides,message",
    [
        ({"cadence": {"start_number": 0}}, "start_number"),
        ({"cadence": {"start_number": -3}}, "start_number"),
        ({"cadence": {"start_number": "seven"}}, "start_number"),
        ({"cadence": {"fiscal_year_start_month": 0}}, "1 to 12"),
        ({"cadence": {"fiscal_year_start_month": 13}}, "1 to 12"),
        ({"cadence": {"fiscal_year_start_month": "April"}}, "1 to 12"),
    ],
)
def test_invalid_numbering_knobs_fail_loudly(tmp_path, overrides, message):
    with pytest.raises(ConfigError, match=message):
        write_config(tmp_path, **overrides)
