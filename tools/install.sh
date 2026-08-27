#!/usr/bin/env bash
#
# Install (or update) sprint automation in another repository.
#
#   tools/install.sh /path/to/repo            copy the payload in
#   tools/install.sh --check /path/to/repo    report drift, change nothing
#
# You chose copy-per-repo over a shared reusable workflow, so this exists to
# make the rollout and every later fix one command per repo instead of a
# hand-edit per repo. The version stamp is what makes drift detectable.
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(cat "$SOURCE_DIR/VERSION")"
CHECK_ONLY=false

PAYLOAD=(
  ".github/workflows/sprint-cut.yml"
  ".github/workflows/sprint-promote.yml"
  ".github/workflows/sprint-backmerge.yml"
  ".github/workflows/sprint-validate.yml"
  "scripts/sprint/__init__.py"
  "scripts/sprint/__main__.py"
  "scripts/sprint/cadence.py"
  "scripts/sprint/config.py"
  "scripts/sprint/naming.py"
  "tests/conftest.py"
  "tests/test_cadence.py"
)

usage() {
  sed -n '3,9p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

while [ $# -gt 0 ]; do
  case "$1" in
    --check) CHECK_ONLY=true; shift ;;
    -h|--help) usage 0 ;;
    -*) echo "unknown option: $1" >&2; usage 1 ;;
    *) TARGET="$1"; shift ;;
  esac
done

if [ -z "${TARGET:-}" ]; then
  echo "error: no target repository given" >&2
  usage 1
fi
if [ ! -d "$TARGET/.git" ]; then
  echo "error: $TARGET is not a git repository" >&2
  exit 1
fi
TARGET="$(cd "$TARGET" && pwd)"
if [ "$TARGET" = "$SOURCE_DIR" ]; then
  echo "error: target is the sprint-automation repo itself" >&2
  exit 1
fi

STAMP="$TARGET/.github/.sprint-automation-version"

if [ "$CHECK_ONLY" = true ]; then
  installed="none"
  [ -f "$STAMP" ] && installed="$(cat "$STAMP")"
  echo "template version: $VERSION"
  echo "installed version: $installed"
  drift=0
  for file in "${PAYLOAD[@]}"; do
    if [ ! -f "$TARGET/$file" ]; then
      echo "  MISSING  $file"
      drift=$((drift + 1))
    elif ! cmp -s "$SOURCE_DIR/$file" "$TARGET/$file"; then
      echo "  DIFFERS  $file"
      drift=$((drift + 1))
    fi
  done
  if [ -f "$TARGET/.github/sprint.yml" ]; then
    echo "  config   .github/sprint.yml present (never overwritten by this script)"
  else
    echo "  MISSING  .github/sprint.yml"
    drift=$((drift + 1))
  fi
  [ "$drift" -eq 0 ] && echo "up to date" || echo "$drift file(s) need attention - rerun without --check"
  exit 0
fi

echo "Installing sprint-automation $VERSION into $TARGET"

for file in "${PAYLOAD[@]}"; do
  mkdir -p "$TARGET/$(dirname "$file")"
  cp "$SOURCE_DIR/$file" "$TARGET/$file"
  echo "  wrote    $file"
done

# The config carries per-team cadence, so an existing one is never clobbered.
if [ -f "$TARGET/.github/sprint.yml" ]; then
  echo "  kept     .github/sprint.yml (existing config left untouched)"
else
  cp "$SOURCE_DIR/.github/sprint.yml" "$TARGET/.github/sprint.yml"
  echo "  wrote    .github/sprint.yml  <-- set your cadence anchor and branch names"
fi

# Merge the runtime dependency rather than replacing a requirements file that
# may already describe the target project.
for req in requirements.txt requirements-dev.txt; do
  if [ ! -f "$TARGET/$req" ]; then
    cp "$SOURCE_DIR/$req" "$TARGET/$req"
    echo "  wrote    $req"
  elif ! grep -qi '^[[:space:]]*pyyaml' "$TARGET/$req"; then
    if [ "$req" = "requirements.txt" ]; then
      printf 'PyYAML>=6.0\n' >> "$TARGET/$req"
      echo "  appended PyYAML>=6.0 to $req"
    fi
  else
    echo "  kept     $req (PyYAML already present)"
  fi
done

echo "$VERSION" > "$STAMP"

cat <<EOF

Installed. Next, in $TARGET:

  1. Edit .github/sprint.yml   - set cadence.anchor to a date your sprint
                                 started, and branches.base to develop or
                                 whatever you cut sprints from.
  2. Confirm the cadence:      PYTHONPATH=scripts python -m sprint validate
  3. Add a SPRINT_TOKEN secret so promotion pull requests run their checks.
  4. Commit, then run the "Sprint - cut branch" workflow manually to verify.
EOF
