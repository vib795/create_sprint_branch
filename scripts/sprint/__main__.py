"""Command line entry point used by the GitHub Actions workflows.

    python -m sprint validate
    python -m sprint status   [--date YYYY-MM-DD]
    python -m sprint promotion --hop {dit,sit,uat,release} [--sprint-date YYYY-MM-DD]

Each command prints JSON to stdout and, when GITHUB_OUTPUT is set, writes the
same fields as step outputs. Python owns the date arithmetic and naming; the
workflows own the git and GitHub operations. Keeping that line clean is what
makes the cadence testable without a runner.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

from . import cadence, naming
from .config import ConfigError, SprintConfig, load

HOPS = ("dit", "sit", "uat", "release")


def _write_github_output(fields: dict[str, object]) -> None:
    target = os.environ.get("GITHUB_OUTPUT")
    if not target:
        return
    with open(target, "a", encoding="utf-8") as handle:
        for key, value in fields.items():
            rendered = _render(value)
            if "\n" in rendered:
                # Heredoc form is the only way to pass multi-line step outputs.
                delimiter = f"__SPRINT_{key.upper()}__"
                handle.write(f"{key}<<{delimiter}\n{rendered}\n{delimiter}\n")
            else:
                handle.write(f"{key}={rendered}\n")


def _render(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _emit(fields: dict[str, object]) -> None:
    _write_github_output(fields)
    json.dump(fields, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


def _resolve_day(config: SprintConfig, override: str | None) -> dt.date:
    if not override:
        return cadence.today_in(config)
    try:
        return dt.date.fromisoformat(override.strip())
    except ValueError as exc:
        raise ConfigError(f"--date/--sprint-date: {exc}") from exc


def _status_fields(config: SprintConfig, day: dt.date) -> dict[str, object]:
    sprint = cadence.sprint_for(config, day)
    return {
        "today": day.isoformat(),
        "timezone": str(config.cadence.timezone),
        "is_sprint_start": sprint.start == day,
        "is_sprint_end": sprint.end == day,
        "sprint_branch": naming.sprint_branch(config, sprint),
        "sprint_slug": naming.sprint_slug(config, sprint),
        "release_branch": naming.release_branch(config, sprint),
        "sprint_start": sprint.start.isoformat(),
        "sprint_end": sprint.end.isoformat(),
        "sprint_index": sprint.index,
        "quarter": sprint.quarter,
        "number": sprint.number,
        "base_branch": config.branches.base,
        "dit_branch": config.branches.dit,
        "sit_branch": config.branches.sit,
        "uat_branch": config.branches.uat,
        "auto_open_dit_pr": config.promotion.auto_open_dit_pr,
        "backmerge_to_base": config.promotion.backmerge_to_base,
        "labels": ",".join(config.promotion.labels),
        "reviewers": ",".join(config.promotion.reviewers),
        "draft": config.promotion.draft,
    }


def _pr_body(config: SprintConfig, sprint, hop: str, head: str, base: str) -> str:
    return "\n".join(
        [
            f"Automated **{hop.upper()}** promotion for sprint `{naming.sprint_slug(config, sprint)}`.",
            "",
            f"- Sprint window: `{sprint.start.isoformat()}` to `{sprint.end.isoformat()}` "
            f"({sprint.length_days} days, {config.cadence.timezone})",
            f"- Promoting: `{head}` into `{base}`",
            "",
            "Merge once this environment is verified. The next hop is opened by "
            "running the *Sprint - promote* workflow.",
            "",
            "<sub>Opened by sprint-automation.</sub>",
        ]
    )


def cmd_validate(args: argparse.Namespace) -> int:
    config = load(args.config)
    day = cadence.today_in(config)
    sprint = cadence.sprint_for(config, day)
    _emit(
        {
            "valid": True,
            "start_weekday": config.cadence.start_weekday,
            "length_days": config.cadence.length_days,
            "numbering": config.cadence.numbering,
            "current_sprint": naming.sprint_branch(config, sprint),
            "sprint_start": sprint.start.isoformat(),
            "sprint_end": sprint.end.isoformat(),
        }
    )
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    config = load(args.config)
    _emit(_status_fields(config, _resolve_day(config, args.date)))
    return 0


def cmd_promotion(args: argparse.Namespace) -> int:
    config = load(args.config)
    day = _resolve_day(config, args.sprint_date)
    sprint = cadence.sprint_for(config, day)
    branches = config.branches

    if args.hop == "release":
        # A release is a cut from UAT, not a merge, so there is no PR to open.
        fields: dict[str, object] = {
            "hop": "release",
            "is_cut": True,
            "head": branches.uat,
            "base": "",
            "release_branch": naming.release_branch(config, sprint),
            "title": "",
            "body": "",
        }
    else:
        if args.hop == "dit":
            head, base = naming.sprint_branch(config, sprint), branches.dit
        else:
            head, base = config.hop(args.hop)
        fields = {
            "hop": args.hop,
            "is_cut": False,
            "head": head,
            "base": base,
            "release_branch": "",
            "title": f"{args.hop.upper()}: promote {head} to {base}",
            "body": _pr_body(config, sprint, args.hop, head, base),
        }

    fields.update(
        {
            "sprint_slug": naming.sprint_slug(config, sprint),
            "sprint_branch": naming.sprint_branch(config, sprint),
            "labels": ",".join(config.promotion.labels),
            "reviewers": ",".join(config.promotion.reviewers),
            "draft": config.promotion.draft,
        }
    )
    _emit(fields)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sprint", description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="path to sprint.yml (default: .github/sprint.yml)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="check sprint.yml and show the resolved cadence")
    validate.set_defaults(func=cmd_validate)

    status = subparsers.add_parser("status", help="report where today falls in the sprint cycle")
    status.add_argument("--date", help="evaluate a specific date (YYYY-MM-DD) instead of today")
    status.set_defaults(func=cmd_status)

    promotion = subparsers.add_parser("promotion", help="plan a promotion hop")
    promotion.add_argument("--hop", required=True, choices=HOPS)
    promotion.add_argument(
        "--sprint-date",
        help="a date inside the sprint being promoted (default: today)",
    )
    promotion.set_defaults(func=cmd_promotion)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as exc:
        print(f"sprint: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
