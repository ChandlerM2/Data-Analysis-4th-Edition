"""Runs every test suite for the practice tools and exits non-zero if any check fails.

Run it after any change to harness.py or clock.py, before the change is committed, because the log
replays through this code on every session and a silent bug reschedules or mispays every rep.
"""
import subprocess
import sys
from pathlib import Path

failed = []
for suite in sorted(Path(__file__).parent.glob("test_*.py")):
    result = subprocess.run([sys.executable, str(suite)], capture_output=True, text=True, encoding="utf-8")
    print(f"{suite.name}: {'ok' if result.returncode == 0 else 'FAILED'}")
    if result.returncode != 0:
        failed.append(suite.name)
        problems = [line for line in result.stdout.splitlines() if not line.startswith("PASS ")]
        print("\n".join(problems), result.stderr, sep="\n")
sys.exit(1 if failed else 0)
