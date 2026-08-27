#!/usr/bin/env bash
#
# Install (or update) sprint automation in another repository.
#
#   tools/install.sh /path/to/repo            copy the payload in
#   tools/install.sh --check /path/to/repo    report drift, change nothing
#
# The payload lives under template/ so that this repo never runs the automation
# on itself. Source and destination paths differ, which is what the mapping
# below encodes: template/workflows/*.yml lands in .github/workflows/, and
# template/sprint.yml becomes the target repo's .github/sprint.yml.
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(cat "$SOURCE_DIR/VERSION")"
CHECK_ONLY=false

# source-relative-path:destination-relative-path
PAYLOAD=(
  "template/workflows/sprint-cut.yml:.github/workflows/sprint-cut.yml"
  "template/workflows/sprint-promote.yml:.github/workflows/sprint-promote.yml"
  "template/workflows/sprint-backmerge.yml:.github/workflows/sprint-backmerge.yml"
  "template/workflows/sprint-validate.yml:.github/workflows/sprint-validate.yml"
  "scripts/sprint/__init__.py:scripts/sprint/__init__.py"
  "scripts/sprint/__main__.py:scripts/sprint/__main__.py"
  "scripts/sprint/cadence.py:scripts/sprint/cadence.py"
  "scripts/sprint/config.py:scripts/sprint/config.py"
  "scripts/sprint/naming.py:scripts/sprint/naming.py"
  "tests/conftest.py:tests/conftest.py"
  "tests/test_cadence.py:tests/test_cadence.py"
)

CONFIG_SOURCE="template/sprint.yml"
CONFIG_DEST=".github/sprint.yml"

usage() {
  sed -n '3,7p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
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
  echo "template version:  $VERSION"
  echo "installed version: $installed"
  drift=0
  for entry in "${PAYLOAD[@]}"; do
    src="${entry%%:*}"
    dest="${entry##*:}"
    if [ ! -f "$TARGET/$dest" ]; then
      echo "  MISSING  $dest"
      drift=$((drift + 1))
    elif ! cmp -s "$SOURCE_DIR/$src" "$TARGET/$dest"; then
      echo "  DIFFERS  $dest"
      drift=$((drift + 1))
    fi
  done
  if [ -f "$TARGET/$CONFIG_DEST" ]; then
    echo "  config   $CONFIG_DEST present (never overwritten by this script)"
  else
    echo "  MISSING  $CONFIG_DEST"
    drift=$((drift + 1))
  fi
  if [ "$drift" -eq 0 ]; then
    echo "up to date"
  else
    echo "$drift file(s) need attention - rerun without --check"
  fi
  exit 0
fi

echo "Installing sprint-automation $VERSION into $TARGET"

for entry in "${PAYLOAD[@]}"; do
  src="${entry%%:*}"
  dest="${entry##*:}"
  mkdir -p "$TARGET/$(dirname "$dest")"
  cp "$SOURCE_DIR/$src" "$TARGET/$dest"
  echo "  wrote    $dest"
done

# The config carries per-team cadence, so an existing one is never clobbered.
if [ -f "$TARGET/$CONFIG_DEST" ]; then
  echo "  kept     $CONFIG_DEST (existing config left untouched)"
else
  mkdir -p "$TARGET/$(dirname "$CONFIG_DEST")"
  cp "$SOURCE_DIR/$CONFIG_SOURCE" "$TARGET/$CONFIG_DEST"
  echo "  wrote    $CONFIG_DEST  <-- set your cadence anchor and branch names"
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
