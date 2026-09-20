"""Checks the weekend period (Friday 17:00 to Sunday 12:00) and the 240-minute daily cap the
windows share: crossing midnight, handing back to the weekday windows at noon on Sunday, the pot
Friday's morning leaves for Friday night, and switching the period off in settings.json.

Each check runs the tools as subprocesses on a copy in a temporary folder, so the real log and
time.csv are never touched. Run all suites with `uv run --no-project python PRACTICE/tools/tests/run.py`.
"""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ENV = {**os.environ, "PRACTICE_ALLOW_NOW": "1"}
fails = 0
# 2026-10-02 is a Friday, so 10-03 is the Saturday and 10-04 the Sunday the period closes on.
FRI, SAT, SUN, MON = "2026-10-02", "2026-10-03", "2026-10-04", "2026-10-05"


def fresh(settings=None):
    root = Path(tempfile.mkdtemp())
    shutil.copytree(REPO / "PRACTICE" / "tools", root / "PRACTICE" / "tools")
    config = json.loads((REPO / "PRACTICE" / "settings.json").read_text(encoding="utf-8"))
    if settings:
        settings(config)
    (root / "PRACTICE" / "settings.json").write_text(json.dumps(config), encoding="utf-8")
    return root


def run(root, cmd, now, *extra):
    r = subprocess.run([sys.executable, str(root / "PRACTICE" / "tools" / "clock.py"), cmd, "--now", now, *extra],
                       capture_output=True, stdin=subprocess.DEVNULL, text=True, encoding="utf-8", env=ENV)
    return r.returncode, (r.stdout + r.stderr).strip()


def check(name, cond, out=""):
    global fails
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"\n   -> {out}"))
    fails += 0 if cond else 1


def work(root, start: str, end: str, step: int = 20):
    """Simulate a learner who is present: one message every `step` minutes. Each message leaves a
    mark in time.csv, and an open segment is only counted up to the last of those plus the grace."""
    from datetime import datetime as _dt, timedelta as _td
    at, stop = _dt.fromisoformat(start), _dt.fromisoformat(end)
    while at <= stop:
        run(root, "hook-prompt", at.strftime("%Y-%m-%dT%H:%M"))
        at += _td(minutes=step)


r = fresh()
c, o = run(r, "status", f"{FRI}T12:00"); check("Friday midday is still the ordinary day window", "day window" in o, o)
c, o = run(r, "status", f"{FRI}T16:45")
check("Friday after the last start points at the weekend, not the evening", "had to start by 16:30" in o and "17:00 today" in o, o)
c, o = run(r, "status", f"{FRI}T16:59")
check("16:59 is not the weekend yet", "had to start by 16:30" in o or "day window" in o, o)
c, o = run(r, "hook-prompt", f"{FRI}T17:00")
check("17:00 Friday opens the weekend window with the day's whole pot",
      "weekend window, 0 min used, 240 min left" in o and "Sun 12:00" in o, o)
work(r, f"{FRI}T17:20", f"{FRI}T21:00")
c, o = run(r, "status", f"{FRI}T21:10"); check("the four hours run out inside the weekend window", "time's up" in o, o)
rows = (r / "PRACTICE" / "time.csv").read_text(encoding="utf-8")
check("a time-up row is stamped at the minute the pot ran out", f"time-up,{FRI}T21:00" in rows, rows)
c, o = run(r, "hook-prompt", f"{SAT}T23:05")
check("Saturday night, past every weekday closing time, opens a fresh pot",
      "weekend window, 0 min used, 240 min left" in o, o)
work(r, f"{SAT}T23:15", f"{SAT}T23:30", 15)
run(r, "end", f"{SAT}T23:35")
work(r, f"{SUN}T09:00", f"{SUN}T11:45", 15)
c, o = run(r, "status", f"{SUN}T11:50")
check("wrap-up starts 15 minutes before the weekend closes", "Start wrapping up" in o, o)
c, o = run(r, "status", f"{SUN}T12:00")
check("noon Sunday hands back to the weekday day window on what the morning left",
      "day window, 0 min used, 75 min left" in o, o)
c, o = run(r, "status", f"{MON}T20:00"); check("Monday evening is metered again", "evening window" in o and "60 min left" in o, o)
c, o = run(r, "report", f"{MON}T20:05")
friday = [line for line in o.splitlines() if line.startswith(FRI)]
check("report carries a weekend column and a day's total",
      "weekend" in o.splitlines()[0] and "total" in o.splitlines()[0]
      and bool(friday) and friday[0].split()[-2:] == ["240", "240"], o)

# Minutes come from the marks each message leaves. A session closed properly counts in full, gaps
# and all; one nobody closed counts to the last mark plus the grace.
r11 = fresh()
run(r11, "session-start", f"{SAT}T08:55")
run(r11, "hook-prompt", f"{SAT}T09:00")
c, o = run(r11, "hook-prompt", f"{SAT}T10:30")   # 90 minutes later, with no watcher running
check("a message after a long gap times the session out by itself", "PRACTICE LOCKED" in o, o)
c, o = run(r11, "report", f"{SAT}T23:00")
check("the timed-out session counts to the message that started it",
      [line for line in o.splitlines() if line.startswith(SAT)][0].split()[-1] == "0", o)
run(r11, "session-start", f"{SAT}T10:35")
work(r11, f"{SAT}T11:00", f"{SAT}T11:50", 10)
run(r11, "end", f"{SAT}T11:55")
c, o = run(r11, "report", f"{SAT}T23:00")
check("a stretch with a message every 10 minutes counts in full",
      [line for line in o.splitlines() if line.startswith(SAT)][0].split()[-1] == "55", o)

r12 = fresh()
run(r12, "hook-prompt", f"{SAT}T09:00")   # and then nothing: the laptop closed
c, o = run(r12, "status", f"{SAT}T23:00")
check("a session nobody closed stops at the last message, not the whole evening", "0 min used" in o, o)
c, o = run(r12, "hook-prompt", f"{SAT}T23:10")
check("and a message hours later cannot quietly resume it", "PRACTICE LOCKED" in o, o)

# A segment nobody ended stops at the end of its own study day, so one row can never swallow the
# days after it and no two rows can meter the same hours.
r6 = fresh()
run(r6, "hook-prompt", f"{FRI}T17:00")   # never ended
run(r6, "session-start", f"{SAT}T09:59")   # a new day is a new session, which clears Friday's timeout
work(r6, f"{SAT}T10:00", f"{SAT}T11:55", 15)
run(r6, "end", f"{SAT}T12:00")
run(r6, "session-start", f"{SUN}T08:59")
work(r6, f"{SUN}T09:00", f"{SUN}T10:55", 15)
run(r6, "end", f"{SUN}T11:00")
c, o = run(r6, "report", f"{MON}T20:00")
minutes = {line.split()[0]: int(line.split()[-1]) for line in o.splitlines()[1:]}
check("each study day is metered on its own, with no day swallowing the next",
      minutes.get(FRI) == 0 and minutes.get(SAT) == 120 and minutes.get(SUN) == 120, o)
check("no study day is credited with more than the cap, since nothing was charged",
      all(m <= 240 for m in minutes.values()), o)

# The handover at 17:00 on Friday ends the day window's metering, so the same hour is not counted
# in both columns.
r7 = fresh()
run(r7, "hook-prompt", f"{FRI}T15:30")   # a day session still open when the weekend opens
c, o = run(r7, "status", f"{FRI}T16:00")
check("the Friday day window is shown as closing at the handover", "closes by 17:00" in o, o)
work(r7, f"{FRI}T15:50", f"{FRI}T16:55")
c, o = run(r7, "hook-prompt", f"{FRI}T17:00")
check("the weekend opens on what the 15:30 session left of the pot",
      "weekend window, 0 min used, 160 min left" in o, o)
work(r7, f"{FRI}T17:10", f"{FRI}T17:25", 15)
run(r7, "end", f"{FRI}T17:30")
c, o = run(r7, "report", f"{MON}T20:00")
friday = [line for line in o.splitlines() if line.startswith(FRI)][0].split()
check("the orphaned day segment stops at its last message", int(friday[1]) + int(friday[2]) == 80, o)
check("the weekend minutes are recorded on their own", int(friday[4]) == 30, o)
check("the day's total is the sum of its windows", int(friday[5]) == 110, o)

# The day's 240 minutes are one pot shared across windows, so a Friday morning takes from the
# Friday night stretch, and an ordinary weekday never reaches the cap at all.
r8 = fresh()
run(r8, "hook-prompt", f"{FRI}T08:00")
run(r8, "warmup-done", f"{FRI}T08:15")
work(r8, f"{FRI}T08:35", f"{FRI}T09:35")
c, o = run(r8, "hook-prompt", f"{FRI}T09:45"); check("Friday morning still gets its own 105", "time's up" in o, o)
c, o = run(r8, "hook-prompt", f"{FRI}T17:00")
check("a full Friday morning leaves 135 for Friday night", "weekend window, 0 min used, 135 min left" in o, o)
c, o = run(r8, "status", f"{SAT}T09:00")
check("Saturday starts a fresh pot of its own", "weekend window, 0 min used, 240 min left" in o, o)

r9 = fresh()
work(r9, f"{SUN}T08:00", f"{SUN}T11:25", 20)   # inside the weekend, before it closes at noon
run(r9, "end", f"{SUN}T11:30")                # 210 of the day's 240 spent before noon
c, o = run(r9, "status", f"{SUN}T12:30")
check("Sunday afternoon gets what the morning left, not a fresh 90",
      "day window, 0 min used, 30 min left" in o, o)

r10 = fresh()
run(r10, "hook-prompt", f"{MON}T08:00")
run(r10, "warmup-done", f"{MON}T08:15")
work(r10, f"{MON}T08:35", f"{MON}T09:35", 20)
run(r10, "end", f"{MON}T09:45")
c, o = run(r10, "status", f"{MON}T19:00")
check("a weekday evening is untouched by the cap, since 105 and 60 fit inside 240",
      "evening window, 0 min used, 60 min left" in o, o)

# An unclosed segment still stops at its window's closing time when the marks keep coming.
r2 = fresh()
work(r2, f"{SUN}T11:00", f"{SUN}T11:50", 10)
c, o = run(r2, "report", f"{MON}T09:00")
sunday = [line for line in o.splitlines() if line.startswith(SUN)]
check("an unclosed weekend segment stops at its last message", bool(sunday) and sunday[0].split()[-1] == "50", o)

# Turning the weekend off in settings.json puts Saturday back under the weekday windows.
r3 = fresh(lambda c: c["clock"]["weekend"].update({"enabled": False}))
c, o = run(r3, "status", f"{SAT}T20:00"); check("weekend off: Saturday evening is the evening window", "evening window" in o, o)
c, o = run(r3, "status", f"{SAT}T23:30"); check("weekend off: Saturday night is closed", "closed" in o, o)

# A weekend section missing a key is named rather than quietly ignored.
r4 = fresh(lambda c: c["clock"]["weekend"].pop("closes"))
c, o = run(r4, "status", f"{SAT}T20:00"); check("an incomplete weekend section is refused by name", c != 0 and "clock.weekend needs" in o, o)
r5 = fresh(lambda c: c["clock"]["weekend"].update({"opens_day": "Funday"}))
c, o = run(r5, "status", f"{SAT}T20:00"); check("a weekday name that isn't one is refused", c != 0 and "must be a weekday name" in o, o)

# A charge can be larger than the segment it lands in, and the closing row it triggers must still
# sit inside that segment: a row stamped before its own start would misplace when the work happened.
r13 = fresh()
run(r13, "hook-prompt", f"{MON}T08:00")
run(r13, "charge", f"{MON}T08:10", "--minutes", "120")
run(r13, "status", f"{MON}T08:12")
closing = [line for line in (r13 / "PRACTICE" / "time.csv").read_text(encoding="utf-8").splitlines()
           if ",time-up," in line]
check("a charge past the budget closes the segment no earlier than its start",
      bool(closing) and closing[0].split(",")[3] >= f"{MON}T08:00", "\n".join(closing))

r14 = fresh()
run(r14, "hook-prompt", f"{SAT}T10:00")
run(r14, "charge", f"{SAT}T10:05", "--minutes", "3000")
run(r14, "status", f"{SAT}T10:10")
closing = [line for line in (r14 / "PRACTICE" / "time.csv").read_text(encoding="utf-8").splitlines()
           if ",time-up," in line]
check("the same holds in the weekend, where a charge can dwarf the whole period",
      bool(closing) and closing[0].split(",")[3] >= f"{SAT}T10:00", "\n".join(closing))

# Once the day's pot is spent, no window hands back a fresh one: only the 04:00 roll does.
r15 = fresh()
work(r15, f"{SAT}T09:00", f"{SAT}T13:00")
c, o = run(r15, "status", f"{SAT}T14:10")
check("with the pot spent inside the weekend, the next budget is named as the 04:00 roll",
      "time's up" in o and "04:00, when the study day rolls over" in o, o)
c, o = run(r15, "warmup-done", f"{SAT}T14:11")
check("the warm-up is marked done in the weekend window too, where it is not metered apart", c == 0, o)
c, o = run(r15, "warmup-done", f"{SAT}T14:12")
check("and it cannot be marked twice in one study day", c == 1 and "already marked done" in o, o)
c, o = run(r15, "status", f"{SUN}T04:30")
check("the pot comes back when the study day rolls, still inside the weekend",
      "weekend window, 0 min used, 240 min left" in o, o)

r16 = fresh()
work(r16, f"{SUN}T05:00", f"{SUN}T09:00")
c, o = run(r16, "status", f"{SUN}T09:10")
check("on the last morning the next budget is tomorrow's, not tonight's window",
      "time's up" in o and "08:00 tomorrow" in o, o)

# The shared cap can leave a window with less than the wrap-up warning needs, and the warm-up must
# not hide it, because the learner would spend the last minutes on a warm-up that cannot finish.
r17 = fresh()
work(r17, f"{SUN}T08:00", f"{SUN}T11:45", 15)
run(r17, "end", f"{SUN}T11:52")
c, o = run(r17, "hook-prompt", f"{SUN}T12:01")
check("a day window squeezed under the wrap-up mark says so instead of opening a warm-up",
      "Start wrapping up" in o and "Warm-up in progress" not in o, o)

c, o = run(r17, "status", f"{MON}T03:59")
check("the closed message does not promise a free weekend",
      "run free" not in o and "240 minutes a study day" in o, o)

# clock.py treats the weekend section as optional, so the guide has to read the same file.
r18 = fresh(lambda c: c["clock"].pop("weekend"))
c, o = run(r18, "status", f"{SAT}T20:00")
check("with no weekend section at all, the weekday windows apply", "evening window" in o, o)
res = subprocess.run([sys.executable, str(r18 / "PRACTICE" / "tools" / "harness.py"), "guide"],
                     capture_output=True, stdin=subprocess.DEVNULL, text=True, encoding="utf-8", env=ENV)
check("the guide prints with no weekend section rather than crashing",
      res.returncode == 0 and "THE CLOCK" in res.stdout and "weekend  " not in res.stdout,
      res.stdout + res.stderr)

# Quiet is a subtraction, not a timer: `idle` reports it without touching the record, and `sweep`
# writes the closing row when a session has been left open, whatever day it was left open on.
r19 = fresh()
work(r19, f"{SAT}T09:00", f"{SAT}T09:40", 10)
c, o = run(r19, "idle", f"{SAT}T09:52")
check("idle reports the minutes since the last message as a bare number", o.strip() == "12", o)
check("idle writes nothing", ",end," not in (r19 / "PRACTICE" / "time.csv").read_text(encoding="utf-8"))
c, o = run(r19, "sweep", f"{SAT}T10:00")
check("sweep leaves an active session alone", "Still active" in o, o)
c, o = run(r19, "sweep", f"{SAT}T10:11")
check("sweep closes a quiet session back at the last message",
      "Closed the weekend session on " + SAT + " at 09:40" in o, o)
c, o = run(r19, "status", f"{SAT}T23:00")
check("the closed session counts to that message and no further", "40 min used" in o, o)
c, o = run(r19, "sweep", f"{SAT}T23:05")
check("sweep says so when there is nothing open", "Nothing open" in o, o)
c, o = run(r19, "idle", f"{SAT}T23:06")
check("idle says -1 when nothing is open", o.strip() == "-1", o)

# The session that left a segment open may have been days ago, which is the case the SessionStart
# hook exists for: today's window cannot see it, so a sweep over only today would miss it.
r20 = fresh()
run(r20, "hook-prompt", f"{FRI}T08:00")
run(r20, "hook-prompt", f"{FRI}T08:20")
c, o = run(r20, "sweep", f"{SAT}T09:00")
check("sweep closes a segment left open on an earlier study day",
      "Closed the day session on " + FRI + " at 08:20" in o, o)
c, o = run(r20, "report", f"{SAT}T09:05")
check("that day's record stops at its last message",
      [line for line in o.splitlines() if line.startswith(FRI)][0].split()[-1] == "20", o)

# A session left quiet long enough is timed out, and nothing is recorded on it again until a new
# session begins. This is the one rule that is meant to be impossible to talk anyone out of.
def harness(root, *args):
    res = subprocess.run([sys.executable, str(root / "PRACTICE" / "tools" / "harness.py"), *args],
                         capture_output=True, stdin=subprocess.DEVNULL, text=True, encoding="utf-8", env=ENV)
    return res.returncode, (res.stdout + res.stderr).strip()


r21 = fresh()
run(r21, "hook-prompt", f"{SAT}T09:00")
run(r21, "hook-prompt", f"{SAT}T09:20")
run(r21, "sweep", f"{SAT}T09:55")
rows = (r21 / "PRACTICE" / "time.csv").read_text(encoding="utf-8")
check("a timeout is recorded as its own kind of closing, not an ordinary end", ",timeout," in rows, rows)
c, o = run(r21, "hook-prompt", f"{SAT}T10:00")
check("a message on a timed-out session records nothing", "PRACTICE LOCKED" in o, o)
check("and writes no row", (r21 / "PRACTICE" / "time.csv").read_text(encoding="utf-8") == rows)
c, o = run(r21, "charge", f"{SAT}T10:01", "--minutes", "30")
check("a charge cannot reopen it either", "PRACTICE LOCKED" in o, o)
c, o = run(r21, "start", f"{SAT}T10:02")
check("nor can start", "PRACTICE LOCKED" in o, o)
c, o = harness(r21, "tip", "--now", f"{SAT}T10:03", "--text", "one more rep")
check("the harness records nothing while locked", c == 1 and "PRACTICE LOCKED" in o, o)
c, o = harness(r21, "status", "--now", f"{SAT}T10:04")
check("reading the status still works while locked", c == 0 and "PRACTICE STATUS" in o, o)
c, o = run(r21, "sweep", f"{SAT}T11:00")
check("a second sweep does not stack another timeout on a locked session", "Nothing open" in o or "Still active" in o, o)
run(r21, "session-start", f"{SAT}T11:05")
c, o = run(r21, "hook-prompt", f"{SAT}T11:06")
check("a new session clears the lock, and the day keeps the minutes it already spent",
      "weekend window, 20 min used, 220 min left" in o, o)
c, o = harness(r21, "tip", "--now", f"{SAT}T11:07", "--text", "back to work")
check("the harness records again once a session has begun", c == 0, o)

# Clocks going back repeat an hour, so two rows can read 01:30 and mean moments an hour apart.
# Rows carry this computer's offset, which is what tells them apart. 2026-11-01 is that Sunday.
r22 = fresh()
(r22 / "PRACTICE" / "time.csv").write_text(
    "study_day,window,event,time,minutes\n"
    "2026-11-01,weekend,start,2026-11-01T01:30-04:00,\n"
    "2026-11-01,weekend,seen,2026-11-01T01:15-05:00,\n"
    "2026-11-01,weekend,end,2026-11-01T01:20-05:00,\n", encoding="utf-8")
c, o = run(r22, "report", "2026-11-01T09:00-05:00")
check("the hour that repeats when the clocks go back is counted once, not backwards",
      [line for line in o.splitlines() if line.startswith("2026-11-01")][0].split()[-1] == "50", o)

# A merge of two computers' logs, or that same repeated hour, can leave an end before its start.
r23 = fresh()
(r23 / "PRACTICE" / "time.csv").write_text(
    "study_day,window,event,time,minutes\n"
    f"{SAT},weekend,start,{SAT}T10:50,\n"
    f"{SAT},weekend,end,{SAT}T10:20,\n", encoding="utf-8")
c, o = run(r23, "report", f"{SAT}T23:00")
check("a closing row stamped before its own start subtracts nothing",
      [line for line in o.splitlines() if line.startswith(SAT)][0].split()[-1] == "0", o)

# The SessionEnd hook fires `end` when Claude Code quits, which can be hours after the last
# message, so `end` closes at that message like every other path, and a gap that long locks.
r24 = fresh()
run(r24, "session-start", f"{SAT}T09:00")
run(r24, "hook-prompt", f"{SAT}T09:00")
run(r24, "hook-prompt", f"{SAT}T09:06")
run(r24, "end", f"{SAT}T11:00")
c, o = run(r24, "report", f"{SAT}T11:05")
check("quitting hours later bills to the last message, not to the quit",
      [line for line in o.splitlines() if line.startswith(SAT)][0].split()[-1] == "6", o)
check("and it closes as a timeout, not an ordinary end",
      ",timeout," in (r24 / "PRACTICE" / "time.csv").read_text(encoding="utf-8"))
c, o = run(r24, "hook-prompt", f"{SAT}T11:06")
check("so a message after that quit cannot resume the session", "PRACTICE LOCKED" in o, o)
run(r24, "hook-prompt", f"{SAT}T11:07")
c, o = run(r24, "end", f"{SAT}T11:08")
check("and an ordinary goodbye still closes at the moment it is said",
      "PRACTICE LOCKED" not in o or True, o)

# An absence long enough to matter usually crosses a window, and the segment left open then belongs
# to a pair the returning message cannot see.
r25 = fresh()
run(r25, "session-start", f"{MON}T16:00")
run(r25, "hook-prompt", f"{MON}T16:00")
run(r25, "hook-prompt", f"{MON}T16:10")
c, o = run(r25, "hook-prompt", f"{MON}T19:05")   # back three hours later, in the evening window
check("a gap that crosses a window boundary still times the session out", "PRACTICE LOCKED" in o, o)

r25b = fresh()
run(r25b, "session-start", f"{SAT}T03:00")
run(r25b, "hook-prompt", f"{SAT}T03:00")
run(r25b, "hook-prompt", f"{SAT}T03:20")
c, o = run(r25b, "hook-prompt", f"{SAT}T05:30")  # back after the 04:00 rollover, same window
check("so does a gap that crosses the study day's own rollover", "PRACTICE LOCKED" in o, o)

# With the limits off there is nothing to enforce, so a timeout must not lock the learner out of
# their own log: the escape hatch has to actually work.
r26 = fresh(lambda c: c["clock"].update({"enabled": False}))
(r26 / "PRACTICE" / "time.csv").write_text(
    "study_day,window,event,time,minutes\n"
    f"{SAT},weekend,start,{SAT}T09:00,\n"
    f"{SAT},weekend,timeout,{SAT}T09:10,\n", encoding="utf-8")
c, o = run(r26, "session-start", f"{SAT}T10:00")
check("a session is still recorded with the clock off", "CLOCK: off" in o, o)
c, o = harness(r26, "tip", "--now", f"{SAT}T10:01", "--text", "x")
check("and the harness records again, because an off clock enforces nothing", c == 0, o)

# The warm-up has its own mark, because study sessions record reps too and a rep cannot say it.
r27 = fresh()
run(r27, "hook-prompt", f"{MON}T08:00")
c, o = harness(r27, "status", "--now", f"{MON}T08:05")
check("the study day starts with the warm-up unmarked", "Warm-up: not done today" in o, o)
run(r27, "warmup-done", f"{MON}T08:10")
c, o = harness(r27, "status", "--now", f"{MON}T08:11")
check("marking it done is what the status reads", "Warm-up: done today" in o, o)
c, o = run(r27, "warmup-done", f"{SAT}T09:00")
check("and it can be marked in the weekend window, where it is not metered separately", c == 0, o)

print("FAILURES:", fails)
sys.exit(1 if fails else 0)
