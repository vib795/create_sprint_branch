# Sprint Branch Automation

Cuts sprint branches on your team's cadence and walks each sprint through
DIT, SIT and UAT as a chain of reviewable pull requests. Cutting a release is a
separate, ad-hoc step for whenever you actually ship.

Designed to be copied into every repo you own. Each repo keeps its own
`.github/sprint.yml`, so teams on different cadences share the same tooling.

**This repo holds the logic; it does not run the automation on itself.** The
copyable payload lives under `template/`, so nothing here is scheduled and no
sprint branch is ever cut on this repo.

```
template/sprint.yml         -> installed as .github/sprint.yml
template/sprint.ps1         -> installed as sprint.ps1, the Windows CLI wrapper
template/workflows/*.yml    -> installed into .github/workflows/
scripts/sprint/             -> copied as-is
tests/                      -> copied as-is
tools/install.sh            -> the rollout tool, macOS and Linux
tools/install.ps1           -> the rollout tool, Windows
tools/payload.manifest      -> the file list both installers read
.github/workflows/ci.yml    -> this repo's own CI, never copied
```

## The pipeline

```
 base (develop) ──cut on sprint start──> Sprint_Q3_S5_082726_090926
                                              │  feature PRs land here all sprint
                                              │
                                              │  last day of sprint: PR opens automatically
                                              ▼
                                          env/dit ──verify──▶ env/sit ──verify──▶ env/uat
                                              │                                       │
                                              │                                       │ ad-hoc, only when
                                              ▼                                       ▼ you actually ship
                                    back-merge PR to base            release/Q3_S5_082726_090926
```

Feature branches are pull-requested into the **sprint branch**, not into the base
branch. Everything merged during the sprint ships together.

Only the first hop is automatic. `env/dit → env/sit → env/uat` each wait for a
person to confirm the environment is actually verified, then merge the pull
request the workflow opened.

**Releases are ad-hoc.** Nothing cuts one on a schedule — the daily run only ever
opens the sprint → DIT pull request. Most sprints end at UAT. When you do ship,
run the promote workflow with `hop: release`, or cut the branch by hand; both
give the same result.

## Installing in a repository

There are two installers and they are interchangeable. Both read
`tools/payload.manifest`, so a repo installed from Windows is byte-for-byte the
same as one installed from macOS — and either one can `--check` the other's work.

**macOS and Linux**

```bash
git clone https://github.com/vib795/create_sprint_branch.git
cd create_sprint_branch
./tools/install.sh /path/to/your/repo
```

**Windows** (PowerShell, including Windows PowerShell 5.1 on a locked-down VDI)

```powershell
git clone https://github.com/vib795/create_sprint_branch.git
cd create_sprint_branch
.\tools\install.ps1 C:\path\to\your\repo
```

Then in that repo:

1. Edit `.github/sprint.yml` — set the cadence anchor and your branch names.
2. Confirm it reads the way you expect:
   ```powershell
   .\sprint.ps1 validate                            # Windows
   ```
   ```bash
   PYTHONPATH=scripts python -m sprint validate     # macOS / Linux
   ```

   On Windows use the installed `sprint.ps1` wrapper rather than translating the
   bash line. `PYTHONPATH=scripts python …` is bash-only syntax — PowerShell
   reads `PYTHONPATH=scripts` as a command name and fails with *"is not
   recognized as a name of a cmdlet"*. `python -m .\scripts\sprint\` fails too:
   `-m` takes a module name, not a path. The wrapper sets `PYTHONPATH` itself,
   runs from the repo root so `.github/sprint.yml` resolves, prefers your
   activated venv, and forwards every argument through:

   ```powershell
   .\sprint.ps1 status
   .\sprint.ps1 status --date 2026-09-10
   .\sprint.ps1 promotion --hop dit
   ```
3. Add a `SPRINT_TOKEN` repository secret (see [Tokens](#tokens)).
4. Commit, then run **Sprint - cut branch** manually with *force* to check it end to end.

To roll a fix out later, re-run the installer against each repo. Check mode
reports which repos have drifted without changing anything:

```bash
./tools/install.sh --check /path/to/your/repo         # bash
```
```powershell
.\tools\install.ps1 -Check C:\path\to\your\repo       # PowerShell (--check also works)
```

### If the installer does nothing on Windows

`./tools/install.sh` cannot run in PowerShell — PowerShell hands `.sh` files to
the Windows file association, which usually means a window flashes open and
shuts, or nothing visible happens at all. Use `install.ps1` instead; it needs
no Git Bash, no WSL and no Python to do the copying.

Two other things bite on a corporate VDI:

- **Execution policy.** If PowerShell refuses to run the script, start it as
  `powershell -ExecutionPolicy Bypass -File .\tools\install.ps1 C:\path\to\repo`.
  If you downloaded a ZIP rather than cloning, Windows also marks the files as
  web content — clear that with `Unblock-File .\tools\install.ps1` first.
- **Line endings.** Git for Windows rewrites files to CRLF by default, which is
  what makes `install.sh` fail with `bad interpreter: /usr/bin/env bash^M` even
  in Git Bash. This repo ships a `.gitattributes` that pins everything to LF, so
  a fresh clone is already correct; an older clone is fixed with
  `git rm --cached -r . && git reset --hard`.

## Setting your sprint cadence

Sprint boundaries come from two values. The anchor is any date one of your
sprints started; its weekday becomes the day every sprint starts. The length
sets the end date.

```yaml
cadence:
  anchor: 2024-06-06        # a Thursday -> sprints start on Thursdays
  length_days: 14           # ends Wednesday, 13 days later
  start_weekday: thursday   # optional cross-check against the anchor
  timezone: America/Chicago
  numbering: quarter
```

That anchor is what produces the branch names shown below: 812 days from
`2024-06-06` to 2026-08-27 divides exactly by 14, so that Thursday starts a
sprint ending 2026-09-09. Move the anchor to a Monday and every boundary moves
with it — the dates in the name change too.

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

### Adopting part-way through an existing scheme

Nobody wants their sprint counter reset to 1 because they installed a tool.
`start_number` says what to call the sprint that starts on the anchor:

```yaml
cadence:
  numbering: continuous
  start_number: 23        # anchor sprint is S23, then S24, S25, ...
```

Under `numbering: quarter` it labels the anchor's own quarter and later quarters
restart at 1 as usual — otherwise every quarter forever would open at
`start_number`.

#### Worked example: you are on Sprint 23

Your team runs Monday fortnights and just finished Sprint 23. The next one
starts Monday 7 September 2026 and should be called Sprint 24. Set the anchor to
that date and name it:

```yaml
cadence:
  anchor: 2026-09-07        # the next sprint's start date, a Monday
  length_days: 14
  numbering: continuous
  start_number: 24          # ...and it is Sprint 24
```

```
2026-09-07   Sprint_S24_090726_092026
2026-09-21   Sprint_S25_092126_100426
2026-10-05   Sprint_S26_100526_101826
```

The same idea in `quarter` mode, where the next sprint should be Q3 S7:

```yaml
cadence:
  anchor: 2026-09-10        # a Thursday
  length_days: 14
  numbering: quarter
  start_number: 7
```

```
2026-09-10   Sprint_Q3_S7_091026_092326
2026-09-24   Sprint_Q3_S8_092426_100726
2026-10-08   Sprint_Q4_S1_100826_102126   <- new quarter, back to S1
```

Point the anchor at the sprint you are naming. It does not have to be the first
sprint you ever ran — any date on the cycle works, and past dates extrapolate
backwards from it.

### Quarters that do not open in January

`fiscal_year_start_month` is the month Q1 counts from. The default of `1` gives
ordinary calendar quarters. A firm whose financial year opens in April sets `4`,
and then July — calendar Q3 — is reported as Q2:

```yaml
cadence:
  fiscal_year_start_month: 4
```

Both knobs are set once and stay correct indefinitely. A sprint that straddles a
quarter boundary keeps the quarter it started in.

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

## Branch names your team recognises

By default the historical format is produced. Add a `naming` section and the
name is entirely yours — teams put their board code in it so a branch is
recognisable at a glance rather than looking generated:

```yaml
naming:
  project_code: PROTS         # each team sets its own
  end_boundary: exclusive     # 8/13-8/27 shares its boundary with the next sprint
  sprint_template: "Q{quarter}_S{number}_{year}_{code}_{start:%m%d}-{end:%m%d}"
  release_template: "release/{sprint}"
```

```
2026-08-13   Q3_S4_2026_PROTS_0813-0827   release/Q3_S4_2026_PROTS_0813-0827
2026-08-27   Q3_S5_2026_PROTS_0827-0910   release/Q3_S5_2026_PROTS_0827-0910
2026-10-08   Q4_S1_2026_PROTS_1008-1022   release/Q4_S1_2026_PROTS_1008-1022
```

Fields: `quarter`, `number`, `year`, `code`, `index`, `start`, `end`. Dates take
strftime, so `{start:%m%d}` gives `0813` and `{start:%Y-%m-%d}` gives
`2026-08-13`. `release_template` also gets `{sprint}`, the sprint branch just
built.

**`end_boundary` changes the date, not just its rendering.** `inclusive` ends on
the sprint's own last day (`8/26`); `exclusive` ends on the next sprint's start
(`8/27`), which is how most teams write a range.

Every rendered name is checked against git's ref rules before it is used, so a
template producing a space or `..` is rejected with an explanation rather than
pushed. A single `/` is allowed — `env/dit` and `release/` depend on it — but it
nests the branch, which is worth knowing before putting `8/13` in a template.

Omit the `naming` section entirely and nothing changes: existing repos keep
cutting `Sprint_Q3_S5_082726_090926`.

## Running on self-hosted runners

The workflows default to `self-hosted`, since many organisations do not permit
GitHub-hosted cloud runners:

```yaml
runs-on: ${{ vars.SPRINT_RUNNER || 'self-hosted' }}
```

Set a repository or organisation variable `SPRINT_RUNNER` to override it —
`ubuntu-latest` for a repo that may use cloud runners, or a specific label like
`sprint-linux` to pin a runner pool. No file edits, so every repo keeps an
identical payload.

Each workflow runs a preflight that names anything missing instead of failing
obscurely later. Your runners need:

| Requirement | Used by |
|---|---|
| `git` | every workflow |
| Python 3.9+ with `PyYAML` | every workflow |
| `gh` (GitHub CLI), authenticated via `GH_TOKEN` | promote, back-merge |

`actions/setup-python` is marked `continue-on-error`, and `pip install` falls
back to whatever is already on the runner — so a runner with no route to PyPI or
the action toolchain still works, provided Python and PyYAML are pre-installed.

## Workflows

| Workflow | Trigger | What it does |
|---|---|---|
| **Sprint - cut branch** | daily, or manual | On a sprint start day, cuts the sprint branch from `branches.base`. Otherwise exits. |
| **Sprint - promote** | daily, or manual | On a sprint end day, opens the sprint → DIT pull request — the *only* thing the schedule ever does. Manually, runs any hop: `dit`, `sit`, `uat`, `release`. |
| **Sprint - back-merge to base** | daily, or manual | Opens a pull request whenever UAT or a release branch is ahead of the base branch. |
| **Sprint - validate config** | pull requests | Validates `sprint.yml` and runs the cadence tests. |

These live in `template/workflows/` here and are installed into
`.github/workflows/` in each target repo. All three scheduled workflows
self-gate, so most days they run and do nothing.

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

# In this repo the config lives at template/sprint.yml, so name it explicitly:
python -m sprint --config template/sprint.yml validate
python -m sprint --config template/sprint.yml status --date 2026-08-27

# In a repo where the payload is installed, the default path just works:
python -m sprint validate                       # resolved cadence for that repo
python -m sprint status                         # where today falls
python -m sprint promotion --hop dit            # what the next promotion would open

pytest tests -q
```

## Repository protection

This automation assumes, but does not configure, branch protection. Protect
`base`, `env/dit`, `env/sit`, `env/uat` and `release/*` so the only route
between environments is a reviewed pull request — otherwise the gates are
convention rather than enforcement.

## Team handbook

A task-oriented guide for people adopting this — installing, setting a cadence,
promoting through environments, and the failures worth recognising — lives at
[`docs/sprint-pipeline-handbook.html`](docs/sprint-pipeline-handbook.html).
It is published as a shareable page; edit the file and republish so the page and
this repo never disagree.

## Contributing

Changes to cadence or naming need a test in `tests/test_cadence.py`. The suite
runs without a runner, a subprocess, or a patched clock — pass the date in.

## License

MIT.
