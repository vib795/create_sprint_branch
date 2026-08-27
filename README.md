# Sprint Branch Automation

Cuts sprint branches on your team's cadence and walks each sprint through
DIT, SIT, UAT and release as a chain of reviewable pull requests.

Designed to be copied into every repo you own. Each repo keeps its own
`.github/sprint.yml`, so teams on different cadences share the same tooling.

## The pipeline

```
 base (develop) ──cut on sprint start──> Sprint_Q3_S5_082726_090926
                                              │  feature PRs land here all sprint
                                              │
                                              │  last day of sprint: PR opens automatically
                                              ▼
                                          env/dit ──verify──▶ env/sit ──verify──▶ env/uat
                                              │                                       │
                                              │                                       │ cut
                                              ▼                                       ▼
                                    back-merge PR to base            release/Q3_S5_082726_090926
```

Feature branches are pull-requested into the **sprint branch**, not into the base
branch. Everything merged during the sprint ships together.

Only the first hop is automatic. `env/dit → env/sit → env/uat` each wait for a
person to confirm the environment is actually verified, then merge the pull
request the workflow opened.

## Installing in a repository

```bash
git clone https://github.com/vib795/create_sprint_branch.git
cd create_sprint_branch
./tools/install.sh /path/to/your/repo
```

Then in that repo:

1. Edit `.github/sprint.yml` — set the cadence anchor and your branch names.
2. Confirm it reads the way you expect:
   ```bash
   PYTHONPATH=scripts python -m sprint validate
   ```
3. Add a `SPRINT_TOKEN` repository secret (see [Tokens](#tokens)).
4. Commit, then run **Sprint - cut branch** manually with *force* to check it end to end.

To roll a fix out later, re-run `install.sh` against each repo. `--check` reports
which repos have drifted without changing anything:

```bash
./tools/install.sh --check /path/to/your/repo
```

## Setting your sprint cadence

Sprint boundaries come from two values. The anchor is any date one of your
sprints started; its weekday becomes the day every sprint starts. The length
sets the end date.

```yaml
cadence:
  anchor: 2026-01-05      # a Monday -> sprints start on Mondays
  length_days: 14         # ends Sunday, 13 days later
  start_weekday: monday   # optional cross-check against the anchor
  timezone: America/Chicago
  numbering: quarter
```

Some cadences and what they produce:

| Goal | `anchor` | `length_days` | First sprint |
|---|---|---|---|
| Thursday fortnights | `2024-06-06` (Thu) | `14` | Thu 6 Jun – Wed 19 Jun |
| Monday fortnights | `2026-01-05` (Mon) | `14` | Mon 5 Jan – Sun 18 Jan |
| Monday weeks | `2026-01-05` (Mon) | `7` | Mon 5 Jan – Sun 11 Jan |
| Wednesday three-week | `2026-01-07` (Wed) | `21` | Wed 7 Jan – Tue 27 Jan |

`start_weekday` is optional and purely a guard: if it disagrees with the anchor,
the config is rejected with an explanation rather than quietly cutting branches
on the wrong day.

`timezone` decides which calendar day a boundary lands on, so a team in Chicago
gets its sprint branch on the Monday it recognises, not on UTC's.

### Branch names

`numbering: quarter` reproduces the established format, resetting the sprint
number each quarter:

```
Sprint_Q3_S5_082726_090926     release/Q3_S5_082726_090926
```

`numbering: continuous` counts from the anchor and never resets:

```
Sprint_S59_082726_090926       release/S59_082726_090926
```

## Workflows

| Workflow | Trigger | What it does |
|---|---|---|
| **Sprint - cut branch** | daily, or manual | On a sprint start day, cuts the sprint branch from `branches.base`. Otherwise exits. |
| **Sprint - promote** | daily, or manual | On a sprint end day, opens the sprint → DIT pull request. Manually, runs any hop: `dit`, `sit`, `uat`, `release`. |
| **Sprint - back-merge to base** | daily, or manual | Opens a pull request whenever UAT or a release branch is ahead of the base branch. |
| **Sprint - validate config** | pull requests | Validates `sprint.yml` and runs the cadence tests. |

All three scheduled workflows self-gate, so most days they run and do nothing.

Promotions are idempotent: an existing branch, an already-open pull request, or
a head branch with nothing the base is missing are all reported and skipped, not
duplicated or failed.

On first use in a repo, an environment branch that does not yet exist is seeded
from the base branch so the first promotion has somewhere to land.

## Why back-merge matters

Branch-per-environment drifts. A hotfix applied to `env/uat` or to a release
branch exists only there — the next sprint is cut from a base branch that lacks
it, and the fix disappears from production.

The back-merge workflow is the mitigation, and it is on by default. Merge those
pull requests promptly; skipping them is how this model fails quietly. Set
`promotion.backmerge_to_base: false` only if you have another mechanism.

## Tokens

Pull requests opened with the default `GITHUB_TOKEN` do **not** trigger other
workflows. A promotion pull request would sit with no status checks, which
defeats gating a promotion on checks passing.

Create a fine-grained personal access token with `contents: read/write` and
`pull requests: read/write` on the repos you are rolling this out to, and store
it as a repository (or organisation) secret named `SPRINT_TOKEN`. The workflows
fall back to `GITHUB_TOKEN` when it is absent, which is fine for a first trial
run but not for enforced gating.

## Local use

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
export PYTHONPATH=scripts

python -m sprint validate                       # resolved cadence for this repo
python -m sprint status                         # where today falls
python -m sprint status --date 2026-08-27       # any date, no clock patching
python -m sprint promotion --hop dit            # what the next promotion would open
pytest tests -q
```

## Repository protection

This automation assumes, but does not configure, branch protection. Protect
`base`, `env/dit`, `env/sit`, `env/uat` and `release/*` so the only route
between environments is a reviewed pull request — otherwise the gates are
convention rather than enforcement.

## Contributing

Changes to cadence or naming need a test in `tests/test_cadence.py`. The suite
runs without a runner, a subprocess, or a patched clock — pass the date in.

## License

MIT.
