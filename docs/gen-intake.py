"""gen-intake - writes docs/INTAKE.md to stdout: the intake's stage table, generated from intake/STAGES.toml and intake/POLICY.toml (plan 1136).
Invariant: docs/INTAKE.md is this output byte for byte and is never edited by hand; `bin/cc intake explain` prints the same text.
Usage: python docs/gen-intake.py > docs/INTAKE.md"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "cc")]
import intake  # after the path line: cc/ holds the modules
import intake_say

sys.stdout.write(intake_say.explain(intake.tables(ROOT)))
