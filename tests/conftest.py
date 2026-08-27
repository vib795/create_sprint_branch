import sys
from pathlib import Path

# The workflows run with PYTHONPATH=scripts; mirror that for tests.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
