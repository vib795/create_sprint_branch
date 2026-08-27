#!/usr/bin/env python3
"""Run the sprint CLI from the repo root, with no PYTHONPATH to set.

    python sprint.py validate
    python sprint.py status --date 2026-09-10
    python sprint.py promotion --hop dit

This is plain Python rather than a shell wrapper on purpose. `python -m sprint`
needs scripts/ on PYTHONPATH, and the bash idiom that sets it inline is not
valid PowerShell -- but a .ps1 wrapper is refused outright on a locked-down
Windows image, where the execution policy rejects any script that is not
digitally signed. Nothing here is subject to that policy, and the same command
works identically on Windows, macOS and Linux.
"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(ROOT, "scripts")

if not os.path.isdir(os.path.join(SCRIPTS, "sprint")):
    sys.stderr.write("error: no sprint package at %s\n" % os.path.join(SCRIPTS, "sprint"))
    sys.stderr.write("       rerun the installer against this repo\n")
    raise SystemExit(1)

# Ahead of the repo root, which is sys.path[0] when this file is run directly,
# so `sprint` resolves to the package under scripts/ and never to this wrapper.
sys.path.insert(0, SCRIPTS)

# The CLI looks for .github/sprint.yml relative to the working directory;
# anchoring to the repo root lets this be run from any subdirectory.
os.chdir(ROOT)

from sprint.__main__ import main  # noqa: E402  (needs the sys.path line above)

if __name__ == "__main__":
    raise SystemExit(main())
