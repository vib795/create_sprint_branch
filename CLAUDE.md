# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A template that gets **copied into every repo the team owns**. It cuts sprint
branches on a configurable cadence and walks each sprint through a
branch-per-environment promotion chain as reviewable pull requests:

```
base (develop) → Sprint_<slug> → env/dit → env/sit → env/uat → release/<slug>
```

Because it is copied rather than referenced, changes here reach other repos only
when someone re-runs `tools/install.sh` against them. Treat every edit to the
payload as something N repos will eventually need, and keep `VERSION` bumped so
`--check` can detect drift.

**This repo never runs the automation on itself.** The copyable payload lives
under `template/`, and `.github/workflows/` holds only `ci.yml`. That separation
is deliberate: a scheduled workflow here would cut sprint branches on the
template repo. Never add a `schedule:` trigger to `.github/workflows/`; new
scheduled workflows belong in `template/workflows/`, and `tools/install.sh`
needs a matching `source:destination` entry in its `PAYLOAD` array or the file
silently never reaches any repo.

| Path here | Installed as |
|---|---|
| `template/sprint.yml` | `.github/sprint.yml` |
| `template/workflows/*.yml` | `.github/workflows/*.yml` |
| `scripts/sprint/`, `tests/` | same paths |
| `.github/workflows/ci.yml` | never copied |

## Commands

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
export PYTHONPATH=scripts          # the workflows set this too

# This repo has no .github/sprint.yml; name the template config explicitly.
python -m sprint --config template/sprint.yml validate
python -m sprint --config template/sprint.yml status --date 2026-08-27

# In an installed repo the default path (.github/sprint.yml) is found automatically.
python -m sprint status                    # where today falls in the cycle
python -m sprint promotion --hop dit       # plan a hop: dit | sit | uat | release

pytest tests -q                            # whole suite (fast, no network, no git)
pytest tests -q -k quarter                 # single concern
pytest tests/test_cadence.py::test_moving_the_anchor_moves_the_start_weekday
```

Rolling out to other repos:

```bash
./tools/install.sh /path/to/repo           # install or update the payload
./tools/install.sh --check /path/to/repo   # report drift, change nothing
```

## Architecture

**The split that matters: Python owns date arithmetic and naming; the workflows
own git and GitHub.** Python never shells out to git and never calls the API;
the workflows never compute a date. This is what makes the cadence testable
without a runner, and it is the line to preserve when adding features.

`scripts/sprint/` is a package, not a script:

| Module | Responsibility |
|---|---|
| `config.py` | Parse and validate `.github/sprint.yml`. Fails loudly with actionable messages. |
| `cadence.py` | Sprint arithmetic. Pure — the caller passes the day in. |
| `naming.py` | Branch name construction. |
| `__main__.py` | CLI. Emits JSON to stdout and the same fields to `$GITHUB_OUTPUT`. |

Workflows consume step outputs from `python -m sprint status` / `promotion`.
Adding a field the workflows need means adding it to `_status_fields` or
`cmd_promotion` in `__main__.py` — the workflows have no other source of truth.

### Cadence model

Every sprint is `anchor + k * length_days`. Two config values describe the whole
schedule: the **anchor** (any date a sprint started — its weekday becomes the
start weekday) and **length_days** (which fixes the end date). There is no
separate "start day" setting; `cadence.start_weekday` in the YAML is an optional
cross-check that errors if it disagrees with the anchor.

`sprint_for()` uses floor division, so dates before the anchor extrapolate
backwards rather than raising — useful for back-filling and tests.

### Sprint numbering

Two modes, and they differ in a way worth knowing before changing either:

- `quarter` — numbering resets each quarter. `_number_in_quarter` counts **actual
  sprint start dates** falling in the sprint's quarter, rather than dividing
  elapsed days by the length. This is deliberate: the original implementation
  divided, which broke for sprints straddling a quarter boundary and clamped
  them to `S1`.
- `continuous` — counts from the anchor, never resets, and omits `Q<n>` from the
  branch name.

**Branch names are a compatibility surface.** The `quarter` mode reproduces the
format of the 50 sprint branches this repo's predecessor already created
(`Sprint_Q3_S5_082726_090926`). That was verified by regenerating all 50 names
from their start dates and diffing — do the same before changing `naming.py`:

```bash
git branch -r --format='%(refname:short)' | sed 's|^origin/||' | grep '^Sprint_'
```

### Promotion model

Only sprint → DIT is automatic, on the sprint's last day. Every later hop is a
manual `workflow_dispatch`, because the gate *is* a person confirming the
environment was verified. Don't "helpfully" automate those hops.

A release is a **branch cut from UAT**, not a merge — hence `is_cut` in the
promotion plan, and no PR title or body for that hop.

All promotion steps are idempotent and exit 0 on: branch already exists, PR
already open, or head has no commits the base lacks. Preserve that; these
workflows run daily.

### Back-merge

`sprint-backmerge.yml` exists because branch-per-environment silently loses
downstream fixes: a hotfix on `env/uat` or a release branch never reaches
`base`, so the next sprint is cut without it. It runs on a schedule and diffs
config-derived branch names, deliberately **not** on a `push:` trigger — a push
trigger would need branch names hardcoded in YAML, which would break for any
team that renames them in `sprint.yml`.

Any new workflow should follow the same rule: read branch names from the CLI, do
not hardcode them in triggers.

## Gotchas

- **`PYTHONPATH=scripts` is required** for `python -m sprint`. Workflows set it
  at job level; `tests/conftest.py` mirrors it.
- **Never interpolate `${{ inputs.* }}` directly into a `run:` block.** Pass it
  through `env:` and quote it in shell. The existing workflows all do this.
- **`GITHUB_TOKEN`-opened PRs do not trigger other workflows**, so promotion PRs
  would have no status checks to gate on. Workflows use
  `secrets.SPRINT_TOKEN || secrets.GITHUB_TOKEN`.
- **`gh pr create --label` fails outright on an unknown label**, which is why
  each label is created with `|| true` first.
- Config changes need a matching case in the `test_invalid_config_fails_loudly`
  parametrisation — validation is the only thing standing between a typo and
  branches cut on the wrong day.
- The old `scripts/calculate_sprint_details.py`, its workflow, and `test.env`
  were removed at the rewrite. If you need the previous behaviour, it is at
  commit `2415a3d`, not on disk.
