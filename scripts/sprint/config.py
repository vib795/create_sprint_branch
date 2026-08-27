"""Load and validate the per-repo sprint configuration (.github/sprint.yml).

Every value the automation needs is declared here, so a team adopting this
changes YAML rather than Python. Validation is deliberately strict and fails
with an actionable message: a bad cadence silently cutting branches on the
wrong day is far more expensive than a loud startup error.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

DEFAULT_CONFIG_PATH = Path(".github/sprint.yml")
NUMBERING_MODES = ("quarter", "continuous")
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


class ConfigError(ValueError):
    """Raised when sprint.yml is missing, malformed, or self-contradictory."""


@dataclasses.dataclass(frozen=True)
class Cadence:
    anchor: dt.date
    length_days: int
    timezone: ZoneInfo
    numbering: str
    start_number: int
    fiscal_year_start_month: int

    @property
    def start_weekday(self) -> str:
        """The weekday sprints start on. Derived from the anchor, never configured."""
        return WEEKDAYS[self.anchor.weekday()]


@dataclasses.dataclass(frozen=True)
class Branches:
    base: str
    dit: str
    sit: str
    uat: str
    sprint_prefix: str
    release_prefix: str


@dataclasses.dataclass(frozen=True)
class Promotion:
    auto_open_dit_pr: bool
    backmerge_to_base: bool
    reviewers: tuple[str, ...]
    labels: tuple[str, ...]
    draft: bool


@dataclasses.dataclass(frozen=True)
class SprintConfig:
    cadence: Cadence
    branches: Branches
    promotion: Promotion

    def hop(self, name: str) -> tuple[str, str]:
        """Return (head, base) for a promotion hop between environment branches."""
        b = self.branches
        hops = {"sit": (b.dit, b.sit), "uat": (b.sit, b.uat)}
        if name not in hops:
            raise ConfigError(f"unknown environment hop {name!r}; expected one of {sorted(hops)}")
        return hops[name]


def _require(mapping: dict, key: str, where: str) -> object:
    if key not in mapping:
        raise ConfigError(f"{where}: missing required key {key!r}")
    return mapping[key]


def _as_branch(value: object, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{where}: must be a non-empty string, got {value!r}")
    name = value.strip()
    if any(ch.isspace() for ch in name):
        raise ConfigError(f"{where}: branch names cannot contain whitespace, got {name!r}")
    if name.endswith("/") and not where.endswith("prefix"):
        raise ConfigError(f"{where}: branch names cannot end with '/', got {name!r}")
    return name


def _parse_anchor(value: object) -> dt.date:
    # PyYAML already turns an unquoted YYYY-MM-DD into a date object.
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value.strip())
        except ValueError as exc:
            raise ConfigError(f"cadence.anchor: {exc}") from exc
    raise ConfigError(f"cadence.anchor: expected a YYYY-MM-DD date, got {value!r}")


def _parse_cadence(raw: dict) -> Cadence:
    anchor = _parse_anchor(_require(raw, "anchor", "cadence"))

    length = _require(raw, "length_days", "cadence")
    if not isinstance(length, int) or isinstance(length, bool) or length < 1:
        raise ConfigError(f"cadence.length_days: expected a positive integer, got {length!r}")

    tz_name = raw.get("timezone", "UTC")
    try:
        tz = ZoneInfo(str(tz_name))
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ConfigError(f"cadence.timezone: unknown timezone {tz_name!r}") from exc

    numbering = str(raw.get("numbering", "quarter")).lower()
    if numbering not in NUMBERING_MODES:
        raise ConfigError(
            f"cadence.numbering: expected one of {list(NUMBERING_MODES)}, got {numbering!r}"
        )

    start_number = raw.get("start_number", 1)
    if not isinstance(start_number, int) or isinstance(start_number, bool) or start_number < 1:
        raise ConfigError(
            f"cadence.start_number: expected a positive integer, got {start_number!r}"
        )

    fiscal_start = raw.get("fiscal_year_start_month", 1)
    if (
        not isinstance(fiscal_start, int)
        or isinstance(fiscal_start, bool)
        or not 1 <= fiscal_start <= 12
    ):
        raise ConfigError(
            "cadence.fiscal_year_start_month: expected a month number from 1 to 12, "
            f"got {fiscal_start!r}"
        )

    cadence = Cadence(
        anchor=anchor,
        length_days=length,
        timezone=tz,
        numbering=numbering,
        start_number=start_number,
        fiscal_year_start_month=fiscal_start,
    )

    # start_weekday is optional and purely a cross-check: the anchor already
    # determines it. Declaring both and disagreeing means someone edited one
    # and forgot the other, which is exactly the mistake worth catching here.
    declared = raw.get("start_weekday")
    if declared is not None:
        declared_name = str(declared).strip().lower()
        if declared_name not in WEEKDAYS:
            raise ConfigError(
                f"cadence.start_weekday: expected a weekday name, got {declared!r}"
            )
        if declared_name != cadence.start_weekday:
            raise ConfigError(
                f"cadence.start_weekday says {declared_name!r} but cadence.anchor "
                f"({anchor.isoformat()}) is a {cadence.start_weekday}. "
                f"Move the anchor to the {declared_name} you want sprints to start on."
            )
    return cadence


def _parse_branches(raw: dict) -> Branches:
    branches = Branches(
        base=_as_branch(_require(raw, "base", "branches"), "branches.base"),
        dit=_as_branch(_require(raw, "dit", "branches"), "branches.dit"),
        sit=_as_branch(_require(raw, "sit", "branches"), "branches.sit"),
        uat=_as_branch(_require(raw, "uat", "branches"), "branches.uat"),
        sprint_prefix=_as_branch(raw.get("sprint_prefix", "Sprint"), "branches.sprint_prefix"),
        release_prefix=_as_branch(raw.get("release_prefix", "release/"), "branches.release_prefix"),
    )

    named = {
        "branches.base": branches.base,
        "branches.dit": branches.dit,
        "branches.sit": branches.sit,
        "branches.uat": branches.uat,
    }
    seen: dict[str, str] = {}
    for where, value in named.items():
        if value in seen:
            raise ConfigError(
                f"{where} and {seen[value]} are both {value!r}; "
                "each stage needs its own branch or promotions become no-ops"
            )
        seen[value] = where
    return branches


def _parse_promotion(raw: dict) -> Promotion:
    def flag(key: str, default: bool) -> bool:
        value = raw.get(key, default)
        if not isinstance(value, bool):
            raise ConfigError(f"promotion.{key}: expected true or false, got {value!r}")
        return value

    def string_list(key: str) -> tuple[str, ...]:
        value = raw.get(key, []) or []
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise ConfigError(f"promotion.{key}: expected a list of strings, got {value!r}")
        return tuple(v.strip() for v in value if v.strip())

    return Promotion(
        auto_open_dit_pr=flag("auto_open_dit_pr", True),
        backmerge_to_base=flag("backmerge_to_base", True),
        reviewers=string_list("reviewers"),
        labels=string_list("labels") or ("sprint-automation",),
        draft=flag("draft", False),
    )


def load(path: Path | str | None = None) -> SprintConfig:
    """Read and validate sprint.yml, raising ConfigError with an actionable message."""
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not config_path.is_file():
        raise ConfigError(
            f"no sprint config at {config_path}. Copy .github/sprint.yml from the "
            "sprint-automation template and set your cadence anchor."
        )

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"{config_path}: invalid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"{config_path}: expected a YAML mapping at the top level")

    version = raw.get("version", 1)
    if version != 1:
        raise ConfigError(f"{config_path}: unsupported config version {version!r}; this tooling reads version 1")

    for section in ("cadence", "branches"):
        if not isinstance(raw.get(section), dict):
            raise ConfigError(f"{config_path}: missing required {section!r} section")

    promotion_raw = raw.get("promotion") or {}
    if not isinstance(promotion_raw, dict):
        raise ConfigError(f"{config_path}: 'promotion' must be a mapping if present")

    return SprintConfig(
        cadence=_parse_cadence(raw["cadence"]),
        branches=_parse_branches(raw["branches"]),
        promotion=_parse_promotion(promotion_raw),
    )
