"""Branch naming.

The sprint branch format is preserved from the original automation so existing
branches stay consistent with new ones:

    Sprint_Q3_S5_082726_090926     quarter numbering
    Sprint_S12_082726_090926       continuous numbering

Release branches mirror the sprint they ship, minus the redundant prefix:

    release/Q3_S5_082726_090926
"""

from __future__ import annotations

from .cadence import Sprint
from .config import SprintConfig

_DATE_FORMAT = "%m%d%y"


def sprint_slug(config: SprintConfig, sprint: Sprint) -> str:
    """The identifying part of a sprint branch name, without the prefix."""
    start = sprint.start.strftime(_DATE_FORMAT)
    end = sprint.end.strftime(_DATE_FORMAT)
    if config.cadence.numbering == "continuous":
        return f"S{sprint.number}_{start}_{end}"
    return f"Q{sprint.quarter}_S{sprint.number}_{start}_{end}"


def sprint_branch(config: SprintConfig, sprint: Sprint) -> str:
    return f"{config.branches.sprint_prefix}_{sprint_slug(config, sprint)}"


def release_branch(config: SprintConfig, sprint: Sprint) -> str:
    prefix = config.branches.release_prefix
    separator = "" if prefix.endswith("/") else "_"
    return f"{prefix}{separator}{sprint_slug(config, sprint)}"
