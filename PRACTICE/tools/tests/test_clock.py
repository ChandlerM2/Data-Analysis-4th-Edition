"""Checks study windows, the day window's last start, warm-up, wrap-up, time-up, pauses, charges,
and the clock switch. Every date here is a Monday to Thursday, because the weekend period
(Friday 17:00 to Sunday 12:00) replaces the weekday windows while it runs and test_weekend.py
covers it.

Each check runs the tools as subprocesses on a copy in a temporary folder, so the real log and
time.csv are never touched. Run all suites with `uv run --no-project python PRACTICE/tools/tests/run.py`.
"""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
root = Path(tempfile.mkdtemp())
shutil.copytree(REPO / "PRACTICE" / "tools", root / "PRACTICE" / "tools")
shutil.copy(REPO / "PRACTICE" / "settings.json", root / "PRACTICE" / "settings.json")
C = root / "PRACTICE" / "tools" / "clock.py"
ENV = {**os.environ, "PRACTICE_ALLOW_NOW": "1"}
fails = 0


def run(cmd, now, env=ENV):
    r = subprocess.run([sys.executable, str(C), cmd, "--now", now], capture_output=True, stdin=subprocess.DEVNULL, text=True, encoding="utf-8", env=env)
    return r.returncode, (r.stdout + r.stderr).strip()


def check(name, cond, out=""):
    global fails
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"\n   -> {out}"))
    fails += 0 if cond else 1


def work(start: str, end: str, step: int = 20, runner=None):
    """Simulate a learner who is present: one message every `step` minutes from start to end.
    Each message is a mark in time.csv, which is what keeps an open segment counting."""
    from datetime import datetime as _dt, timedelta as _td
    at, stop = _dt.fromisoformat(start), _dt.fromisoformat(end)
    out = ""
    while at <= stop:
        out = (runner or run)("hook-prompt", at.strftime("%Y-%m-%dT%H:%M"))[1]
        at += _td(minutes=step)
    return out


c, o = run("hook-prompt", "2026-09-21T18:30"); check("the gap before evening is closed, next window tonight", "closed" in o and "19:00 tonight" in o, o)
check("closed prompt writes nothing", not (root / "PRACTICE" / "time.csv").exists())
c, o = run("hook-prompt", "2026-09-21T08:00"); check("first day prompt starts the clock in warm-up", "Warm-up in progress" in o, o)
c, o = run("hook-prompt", "2026-09-21T08:08"); check("still warm-up at 8 min", "Warm-up in progress" in o, o)
c, o = run("warmup-done", "2026-09-21T08:10"); check("warm-up done at 10 min starts study budget", "10 min used, 90 min left" in o, o)
c, o = run("warmup-done", "2026-09-21T08:11"); check("warm-up can't be marked twice", c == 1, o)
work("2026-09-21T08:15", "2026-09-21T08:55")
c, o = run("hook-prompt", "2026-09-21T09:00"); check("running at 09:00: 10 warm-up + 50 study", "60 min used, 40 min left" in o and "wrap" not in o.lower(), o)
c, o = run("end", "2026-09-21T09:05"); check("end closes the segment", "65 min used" in o, o)
c, o = run("hook-prompt", "2026-09-21T09:20"); check("coming back resumes without counting the gap", "65 min used" in o, o)
work("2026-09-21T09:25", "2026-09-21T09:45", 10)
c, o = run("hook-prompt", "2026-09-21T09:47"); check("wrap-up at 09:47 (8 min of budget left)", "Start wrapping up" in o, o)
c, o = run("hook-prompt", "2026-09-21T09:59"); check("budget used up by 09:59", "time's up" in o, o)
c, o = run("hook-prompt", "2026-09-21T18:15"); check("18:15 closes the day window", "closed" in o, o)

# evening: 60 minutes, wrap at 45, time-up at 60
run("session-start", "2026-09-21T19:59")
c, o = run("hook-prompt", "2026-09-21T20:00"); check("evening starts", "evening window, 0 min used, 60 min left" in o, o)
work("2026-09-21T20:10", "2026-09-21T20:40")
c, o = run("hook-prompt", "2026-09-21T20:46"); check("evening wrap-up at 46 min", "Start wrapping up" in o, o)
c, o = run("hook-prompt", "2026-09-21T21:10"); check("evening time-up after 60 min", "time's up" in o, o)
c, o = run("hook-prompt", "2026-09-21T22:30"); check("stays time-up later that night, no restart", "time's up" in o, o)
c, o = run("hook-prompt", "2026-09-21T23:00"); check("23:00 closes the evening window", "closed" in o, o)
rows = (root / "PRACTICE" / "time.csv").read_text().splitlines()
check("time-up row stamped at the 60-minute mark", any("time-up,2026-09-21T21:00" in r for r in rows), "\n".join(rows))

# the day window with no warmup-done: warm-up counts as 15 minutes, study 90 after
run("session-start", "2026-09-22T08:29")
c, o = run("hook-prompt", "2026-09-22T08:30"); check("a new study day opens a fresh day window", "day window, 0 min used" in o, o)
work("2026-09-22T08:35", "2026-09-22T08:55", 10)
c, o = run("hook-prompt", "2026-09-22T09:00"); check("after 15 min without warmup-done, study time runs", "Warm-up" not in o and "30 min used, 75 min left" in o, o)
work("2026-09-22T09:10", "2026-09-22T09:50")
c, o = run("hook-prompt", "2026-09-22T10:00"); check("day wrap-up at 90 of 105", "Start wrapping up" in o, o)
run("hook-prompt", "2026-09-22T10:15")
c, o = run("status", "2026-09-22T10:20"); check("day time-up at 105 (15 warm-up + 90)", "time's up" in o, o)

# a session nobody ended counts only until the window closes
run("session-start", "2026-09-23T19:29")
c, o = run("hook-prompt", "2026-09-23T19:30")
c, o = run("report", "2026-09-24T12:00"); check("report lists days", "2026-09-23" in o and "2026-09-21" in o, o)
c, o = run("hook-prompt", "2026-09-23T19:30")
c, o = run("hook-prompt", "2026-09-23T19:40")
before = (root / "PRACTICE" / "time.csv").read_text(encoding="utf-8")
c, o = run("status", "2026-09-23T19:45")
check("status reads the rows without writing one", "10 min used" in o
      and (root / "PRACTICE" / "time.csv").read_text(encoding="utf-8") == before, o)
c, o = run("start", "2026-09-24T18:30"); check("start refused while closed", c == 1 and "closed" in o, o)

# the day window's last start: miss it and the window is spent, whatever time of day it is
run("session-start", "2026-09-28T16:28")
c, o = run("status", "2026-09-28T16:29"); check("16:29 can still open the day window", "day window, 0 min used" in o, o)
c, o = run("status", "2026-09-28T16:30"); check("no start by 16:30 spends the day window", "had to start by 16:30" in o and "19:00 tonight" in o, o)
c, o = run("start", "2026-09-28T17:00"); check("start refused after the last start", c == 1 and "had to start by" in o, o)
c, o = run("hook-prompt", "2026-09-28T17:00"); check("the hook explains the missed start", c == 0 and "had to start by" in o, o)
check("a missed day start writes no row", "2026-09-28,day,start" not in (root / "PRACTICE" / "time.csv").read_text())
c, o = run("status", "2026-09-21T06:00", env={k: v for k, v in os.environ.items() if k != "PRACTICE_ALLOW_NOW"})
check("--now refused outside tests", c != 0 and "only works in tests" in o, o)
r2 = Path(tempfile.mkdtemp())
shutil.copytree(REPO / "PRACTICE" / "tools", r2 / "PRACTICE" / "tools")
shutil.copy(REPO / "PRACTICE" / "settings.json", r2 / "PRACTICE" / "settings.json")
C = r2 / "PRACTICE" / "tools" / "clock.py"
run("hook-prompt", "2026-09-29T20:00")
run("end", "2026-09-29T20:10")
c, o = subprocess.run([sys.executable, str(C), "charge", "--minutes", "30", "--now", "2026-09-29T20:45"], capture_output=True, stdin=subprocess.DEVNULL, text=True, encoding="utf-8", env=ENV).returncode, ""
c, o = run("status", "2026-09-29T20:45"); check("charged minutes count against the window", "40 min used, 20 min left" in o, o)
c2 = subprocess.run([sys.executable, str(C), "charge", "--minutes", "-5", "--now", "2026-09-29T20:46"], capture_output=True, stdin=subprocess.DEVNULL, text=True, encoding="utf-8", env=ENV).returncode
check("negative charge refused", c2 == 1)
r3 = Path(tempfile.mkdtemp())
shutil.copytree(REPO / "PRACTICE" / "tools", r3 / "PRACTICE" / "tools")
shutil.copy(REPO / "PRACTICE" / "settings.json", r3 / "PRACTICE" / "settings.json")
(r3 / "PRACTICE" / "time.csv").write_text(
    "study_day,window,event,time\n2026-09-29,evening,start,2026-09-29T20:00\n2026-09-29,evening,end,2026-09-29T20:10\n",
    encoding="utf-8")
C = r3 / "PRACTICE" / "tools" / "clock.py"
subprocess.run([sys.executable, str(C), "charge", "--minutes", "30", "--now", "2026-09-29T20:45"], capture_output=True, stdin=subprocess.DEVNULL, text=True, encoding="utf-8", env=ENV)
c, o = run("status", "2026-09-29T20:46"); check("charge counts in a time.csv started with the older 4-column header", "40 min used" in o, o)
r4 = Path(tempfile.mkdtemp())
shutil.copytree(REPO / "PRACTICE" / "tools", r4 / "PRACTICE" / "tools")
cfg = json.loads((REPO / "PRACTICE" / "settings.json").read_text(encoding="utf-8")); cfg["clock"]["enabled"] = False
(r4 / "PRACTICE" / "settings.json").write_text(json.dumps(cfg), encoding="utf-8")
C = r4 / "PRACTICE" / "tools" / "clock.py"
c, o = run("hook-prompt", "2026-09-29T12:00"); check("clock off: hook says off and writes nothing", "CLOCK: off" in o and not (r4 / "PRACTICE" / "time.csv").exists(), o)
for cmd in ("start", "warmup-done", "end", "status"):
    c, o = run(cmd, "2026-09-29T06:00"); check(f"clock off: {cmd} says off, exits 0", c == 0 and "CLOCK: off" in o, o)
r = subprocess.run([sys.executable, str(r4 / "PRACTICE" / "tools" / "harness.py"), "status", "--now", "2026-09-29T12:00"],
                   capture_output=True, stdin=subprocess.DEVNULL, text=True, encoding="utf-8", env=ENV)
check("clock off: harness status shows it", "CLOCK: off" in r.stdout and "closed" not in r.stdout, r.stdout + r.stderr)
check("clock off: nothing written after every command", not (r4 / "PRACTICE" / "time.csv").exists())

# maintenance: repair work is not study time
r5 = Path(tempfile.mkdtemp())
shutil.copytree(REPO / "PRACTICE" / "tools", r5 / "PRACTICE" / "tools")
shutil.copy(REPO / "PRACTICE" / "settings.json", r5 / "PRACTICE" / "settings.json")
C = r5 / "PRACTICE" / "tools" / "clock.py"
run("session-start", "2026-09-30T09:00")
run("hook-prompt", "2026-09-30T09:00")
run("hook-prompt", "2026-09-30T09:20")
c, o = run("maintenance", "2026-09-30T09:30")
check("maintenance closes the open segment and says so", c == 0 and "no minutes are counted" in o, o)
c, o = run("hook-prompt", "2026-09-30T10:30")
check("an hour of repair work records nothing", "maintenance session, minutes not counted" in o, o)
c, o = run("status", "2026-09-30T10:31")
check("the minutes studied before maintenance are still counted", "30 min used" in o, o)
c, o = run("maintenance", "2026-09-30T10:40")
c, o = run("hook-prompt", "2026-09-30T10:41")
check("declaring maintenance twice changes nothing", "maintenance session" in o, o)
def run_off(now):
    r = subprocess.run([sys.executable, str(C), "maintenance", "--off", "--now", now],
                       capture_output=True, stdin=subprocess.DEVNULL, text=True, encoding="utf-8", env=ENV)
    return r.returncode, (r.stdout + r.stderr).strip()


c, o = run_off("2026-09-30T10:45")
check("maintenance ends on request", c == 0 and "counts study time again" in o, o)
c, o = run("hook-prompt", "2026-09-30T10:46")
check("the clock counts again once maintenance is over", "CLOCK: day window" in o, o)
run("session-start", "2026-09-30T11:00")
c, o = run("hook-prompt", "2026-09-30T11:01")
check("a new session starts as ordinary study, not maintenance", "CLOCK: day window" in o, o)

print("FAILURES:", fails)
sys.exit(1 if fails else 0)
