"""Branch naming.

Two modes. With no `naming.sprint_template` in the config, the historical format
is produced, so a repo that has been cutting branches for years keeps generating
identical names:

    Sprint_Q3_S5_082726_090926     quarter numbering
    Sprint_S12_082726_090926       continuous numbering
    release/Q3_S5_082726_090926

With a template, the name is entirely yours. Teams put their board code in it so
a branch is recognisable at a glance rather than looking randomly generated:

    naming:
      project_code: PROTS
      end_boundary: exclusive
      sprint_template: "Q{quarter}_S{number}_{year}_{code}_{start:%m%d}-{end:%m%d}"

    -> Q3_S4_2026_PROTS_0813-0827

Git refuses several characters in a ref name, and a template makes it easy to
produce one by accident, so every rendered name is checked before it is returned.
"""

from __future__ import annotations

import datetime as dt
import string

from .cadence import Sprint
from .config import ConfigError, SprintConfig

_DATE_FORMAT = "%m%d%y"

# git check-ref-format: no whitespace, no ~ ^ : ? * [ \, no control characters.
_ILLEGAL_REF_CHARS = set(" ~^:?*[\\\x7f") | {chr(code) for code in range(32)}


def _validate_ref(name: str, where: str) -> str:
    """Reject anything git would not accept as a branch name."""
    if not name:
        raise ConfigError(f"{where}: rendered an empty branch name")

    bad = sorted({ch for ch in name if ch in _ILLEGAL_REF_CHARS})
    if bad:
        shown = ", ".join("space" if ch == " " else repr(ch) for ch in bad)
        raise ConfigError(
            f"{where}: {name!r} is not a valid git branch name -- it contains {shown}. "
            "Use underscores or hyphens instead."
        )
    for condition, reason in (
        (".." in name, "contains '..'"),
        ("//" in name, "contains '//'"),
        (name.startswith("/") or name.endswith("/"), "starts or ends with '/'"),
        (name.startswith(".") or name.endswith("."), "starts or ends with '.'"),
        (name.endswith(".lock"), "ends with '.lock'"),
        (name.startswith("-"), "starts with '-'"),
    ):
        if condition:
            raise ConfigError(f"{where}: {name!r} is not a valid git branch name -- it {reason}")
    return name


def _end_date(config: SprintConfig, sprint: Sprint) -> dt.date:
    """The end date as the team writes it.

    `inclusive` is the sprint's own last day. `exclusive` is the next sprint's
    start, which is how a range like 8/13-8/27 is usually written -- the boundary
    is shared, not a day of this sprint.
    """
    if config.naming.end_boundary == "exclusive":
        return sprint.start + dt.timedelta(days=config.cadence.length_days)
    return sprint.end


def _fields(config: SprintConfig, sprint: Sprint) -> dict[str, object]:
    return {
        "quarter": sprint.quarter,
        "number": sprint.number,
        "year": sprint.start.year,
        "code": config.naming.project_code,
        "index": sprint.index,
        "start": sprint.start,
        "end": _end_date(config, sprint),
    }


def _render(template: str, fields: dict[str, object], where: str) -> str:
    try:
        return string.Formatter().vformat(template, (), fields)
    except KeyError as exc:
        raise ConfigError(f"{where}: unknown field {exc} in {template!r}") from exc
    except (ValueError, IndexError) as exc:
        raise ConfigError(f"{where}: malformed template {template!r}: {exc}") from exc


def sprint_slug(config: SprintConfig, sprint: Sprint) -> str:
    """The identifying part of the historical name, without the prefix."""
    start = sprint.start.strftime(_DATE_FORMAT)
    end = _end_date(config, sprint).strftime(_DATE_FORMAT)
    if config.cadence.numbering == "continuous":
        return f"S{sprint.number}_{start}_{end}"
    return f"Q{sprint.quarter}_S{sprint.number}_{start}_{end}"


def sprint_branch(config: SprintConfig, sprint: Sprint) -> str:
    template = config.naming.sprint_template
    if template:
        name = _render(template, _fields(config, sprint), "naming.sprint_template")
        return _validate_ref(name, "naming.sprint_template")
    return f"{config.branches.sprint_prefix}_{sprint_slug(config, sprint)}"


def release_branch(config: SprintConfig, sprint: Sprint) -> str:
    template = config.naming.release_template
    if template:
        fields = _fields(config, sprint)
        fields["sprint"] = sprint_branch(config, sprint)
        name = _render(template, fields, "naming.release_template")
        return _validate_ref(name, "naming.release_template")

    if config.naming.sprint_template:
        # A custom sprint name with no release template: keep them corresponding
        # by prefixing the sprint's own name.
        prefix = config.branches.release_prefix
        separator = "" if prefix.endswith("/") else "_"
        return f"{prefix}{separator}{sprint_branch(config, sprint)}"

    prefix = config.branches.release_prefix
    separator = "" if prefix.endswith("/") else "_"
    return f"{prefix}{separator}{sprint_slug(config, sprint)}"
