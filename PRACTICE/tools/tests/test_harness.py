"""Checks layers, scheduling, money, sections, skill limits, questions, and the log guard.

Each check runs the tools as subprocesses on a copy in a temporary folder, so the real log and
time.csv are never touched. Run all suites with `uv run --no-project python PRACTICE/tools/tests/run.py`.
"""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
root = Path(tempfile.mkdtemp())
shutil.copytree(REPO / "PRACTICE" / "tools", root / "PRACTICE" / "tools")
shutil.copy(REPO / "PRACTICE" / "settings.json", root / "PRACTICE" / "settings.json")
H = root / "PRACTICE" / "tools" / "harness.py"
ENV = {**os.environ, "PRACTICE_ALLOW_NOW": "1"}
fails = 0


def run(*args, stdin=None, env=ENV):
    r = subprocess.run([sys.executable, str(H), *args], capture_output=True, text=True, input=stdin or "", encoding="utf-8", env=env)
    return r.returncode, (r.stdout + r.stderr).strip()


def check(name, cond, out=""):
    global fails
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"\n   -> {out}"))
    fails += 0 if cond else 1


def rep(now, rep_id, skill, result, help=0, fmt="predict", extra=()):
    return run("rep", "--now", now, "--rep", rep_id, "--skill", skill, "--format", fmt, "--result", result,
               "--help-level", str(help), *extra)


def add(now, sid, kind, imp="core", ch="2", pages="67-70", source="book", force=False):
    return run("add-skill", "--now", now, "--id", sid, "--text", f"text for {sid}", "--kind", kind,
               "--importance", imp, "--chapter", ch, "--pages", pages, "--source", source, *(["--force"] if force else []))


def money_of(out):
    for line in out.splitlines():
        if line.startswith("Money:"):
            return line
    return ""


# guard on --now
c, o = run("status", "--now", "2026-09-18T09:00", env={k: v for k, v in os.environ.items() if k != "PRACTICE_ALLOW_NOW"})
check("--now refused outside tests", c == 1 and "only works in tests" in o, o)
c, o = run("validate"); check("empty log validates", c == 0 and "0 skills" in o, o)
c, o = run("status", "--now", "2026-09-18T08:00"); check("status opens with an empty balance", "Money: $0.00 earned this month, balance $0.00." in o, o)

# layers and extras
c, o = add("2026-09-18T09:00", "np-like-dtype", "code"); check("add code skill", c == 0, o)
c, o = rep("2026-09-18T09:10", "s1#1", "np-like-dtype", "correct", 2, "worked"); check("L1 correct -> L2, study catch $4", "worked L1 correct -> L2" in o and "+$4.00" in o, o)
c, o = rep("2026-09-18T09:20", "s1#2", "np-like-dtype", "wrong", 1, "parsons"); check("L2 wrong stays", "L2 wrong -> L2" in o, o)
c, o = rep("2026-09-18T09:25", "s1#3", "np-like-dtype", "correct", 1, "parsons"); check("a second rep at L2 is old ground, so it pays the repeat rate", "L2 correct -> L3, due 2026-09-19" in o and "Money: +$0.25" in o, o)
c, o = rep("2026-09-18T09:30", "s1#4", "np-like-dtype", "correct"); check("same-day L3 rep is extra", "extra (due 2026-09-19)" in o, o)
c, o = rep("2026-09-18T09:30", "s1#4", "np-like-dtype", "correct"); check("duplicate rep+skill refused", c == 1 and "already has a result" in o, o)
c, o = rep("2026-09-19T01:30", "s2#1", "np-like-dtype", "correct"); check("01:30 belongs to the previous study day", "extra" in o, o)
c, o = rep("2026-09-19T08:00", "s3#1", "np-like-dtype", "correct", 1); check("new layer with a hint pays the warm-up and the rep, no bonus", "L3 correct -> L4, due 2026-09-22" in o and "Money: +$2.00" in o, o)
c, o = rep("2026-09-22T08:00", "s4#1", "np-like-dtype", "correct", 1); check("L4 help turns correct into wrong", "Recording as wrong" in o and "L4 wrong -> L3" in o, o)
c, o = run("fix", "--now", "2026-09-22T08:05", "--rep", "s4#1"); check("fix pays $1", c == 0 and "+$1.00" in o, o)
c, o = run("fix", "--now", "2026-09-22T08:06", "--rep", "s4#1"); check("second fix refused", c == 1, o)
c, o = run("amend", "--now", "2026-09-22T08:10", "--rep", "s4#1", "--skill", "np-like-dtype", "--result", "correct", "--reason", "dispute")
c, o = run("skills", "--now", "2026-09-22T08:11"); check("amend can't beat the help rule", "L3 |" in o, o)
c, o = rep("2026-09-23T08:00", "s5#1", "np-like-dtype", "correct"); check("L3 -> L4", "L3 correct -> L4" in o, o)
c, o = rep("2026-09-26T08:00", "s6#1", "np-like-dtype", "correct", extra=("--seconds", "100", "--target-seconds", "90")); check("winning back the best layer pays full plus a dollar, and over the target still earns no clean bonus",
      "L4 correct -> L5" in o and "Money: +$3.00" in o, o)
c, o = rep("2026-10-03T08:00", "s7#1", "np-like-dtype", "correct"); check("inside the target at a new layer: clean bonus", "L5 correct -> L6" in o and "Money: +$4.00" in o, o)
c, o = rep("2026-10-17T08:00", "s8#1", "np-like-dtype", "wrong"); check("wrong at L6 -> L4", "L6 wrong -> L4" in o, o)
c, o = rep("2026-10-20T08:00", "s9#1", "np-like-dtype", "wrong"); check("wrong at L4 -> L3", "L4 wrong -> L3" in o, o)
for d, r in [("2026-10-21", "a"), ("2026-10-24", "b"), ("2026-10-31", "c"), ("2026-11-14", "d")]:
    rep(d + "T08:00", "c" + r, "np-like-dtype", "correct")
c, o = rep("2026-12-14T08:00", "top", "np-like-dtype", "correct"); check("correct at L7 masters", "mastered" in o, o)

# money: sections, the evening double, the repeat rate, and free-form spending
c, o = run("section", "--now", "2026-12-14T08:30", "--heading", "Selecting array elements")
check("a section worked through pays $1", c == 0 and "Money: +$1.00" in o, o)
c, o = run("section", "--now", "2026-12-14T08:31", "--heading", "selecting array elements")
check("the same section is refused however it is capitalised", c == 1 and "already recorded" in o, o)
add("2026-12-14T09:00", "crisp-dm", "concept", ch="1", pages="7-9", source="learner-notes")
add("2026-12-14T09:01", "kdd", "concept", imp="useful", ch="1", pages="5-6", source="learner-notes")
c, o = run("due", "--now", "2026-12-14T10:00"); check("concept skill not due the day it is added", "Nothing due" in o, o)
c, p1 = rep("2026-12-15T08:00", "m1#1", "crisp-dm", "correct", 0, "explain")
c, o = rep("2026-12-15T08:00", "m1#1", "kdd", "correct", 0, "explain")
check("a rep covering two skills pays the day's warm-up and rep once",
      money_of(p1).startswith("Money: +$2.00") and money_of(o) == "", p1 + " | " + o)

# 2026-12-16 is a Wednesday, so 20:00 is the evening window and every rate doubles there.
add("2026-12-15T09:00", "ev-skill", "concept", ch="1", pages="5-6", source="learner-notes")
c, o = rep("2026-12-16T20:00", "ev#1", "ev-skill", "correct", 0, "explain")
check("the evening window pays double", "Money: +$4.00" in o, o)
c, o = run("section", "--now", "2026-12-16T20:30", "--heading", "Splitting arrays")
check("a section in the evening pays double too", "Money: +$2.00" in o, o)

c, o = rep("2026-12-18T08:00", "rp#1", "kdd", "wrong", 0, "explain")
check("a first rep at a new layer pays for the attempt even when it is wrong",
      "L4 wrong -> L3" in o and "Money: +$2.00" in o, o)
c, o = rep("2026-12-19T08:00", "rp#2", "kdd", "correct", 0, "explain")
check("a rep below the best layer pays only the repeat rate", "L3 correct -> L4" in o and "Money: +$0.25" in o, o)

c, o = run("ticket", "--now", "2026-12-19T09:00", "--id", "wk1", "--result", "done")
check("a finished ticket pays $20", c == 0 and "+$20.00" in o, o)
c, o = run("status", "--now", "2026-12-19T09:30")
check("status shows the month and the balance in dollars", "Money: $" in o and "balance $" in o, o)
c, o = run("redeem", "--now", "2026-12-19T09:40", "--item", "ammo", "--dollars", "42.50")
check("spending is recorded as what it went on", c == 0 and "Spent $42.50 on ammo" in o, o)
c, o = run("redeem", "--now", "2026-12-19T09:41", "--item", "gas", "--dollars", "-5")
check("negative spending refused", c == 1, o)
c, o = run("redeem", "--now", "2026-12-19T09:42", "--item", "books", "--dollars", "500")
check("spending past the balance is allowed and shows a negative balance", c == 0 and "balance -$" in o, o)

# test-out and drop
add("2026-12-19T10:00", "env-uv-sync", "concept", imp="useful", ch="1", pages="43-45", source="learner-notes", force=True)
c, o = run("skill-edit", "--now", "2026-12-20T10:00", "--id", "env-uv-sync", "--drop"); check("drop refused after the day added", c == 1 and "test-out" in o, o)
c, o = rep("2026-12-20T10:05", "t1#1", "env-uv-sync", "correct", 1, "explain", extra=("--test-out",)); check("test-out with help doesn't retire", "missed, unchanged" in o, o)
c, o = rep("2026-12-20T10:10", "t1#2", "env-uv-sync", "correct", 0, "explain", extra=("--test-out",)); check("second test-out the same day refused", c == 1 and "next try is tomorrow" in o, o)
c, o = rep("2026-12-21T10:10", "t1#3", "env-uv-sync", "correct", 0, "explain", extra=("--test-out",)); check("clean test-out next day retires", "passed, retired" in o and "Money" not in o, o)
add("2026-12-21T10:20", "oops", "concept", imp="useful", ch="1", pages="1", source="book")
c, o = run("skill-edit", "--now", "2026-12-21T10:21", "--id", "oops", "--drop"); check("same-day drop allowed", c == 0, o)

# page ranges are corrected through skill-edit, because a skill logged with the wrong numbering
# has to be fixed without touching the log by hand
add("2026-12-21T10:30", "np-printed-pages", "code", ch="2", pages="67-70")
c, o = run("skill-edit", "--now", "2026-12-21T10:31", "--id", "np-printed-pages", "--pages", "40-43"); check("skill-edit accepts a new page range", c == 0, o)
c, o = run("skills", "--now", "2026-12-21T10:32")
line = next((l for l in o.splitlines() if "np-printed-pages" in l), "")
check("the corrected page range replaces the old one", "p[40, 43]" in line and "67" not in line, line or o)
c, o = run("skill-edit", "--now", "2026-12-21T10:33", "--id", "np-printed-pages", "--pages", "45"); check("a single page works too", c == 0, o)
c, o = run("skills", "--now", "2026-12-21T10:34")
line = next((l for l in o.splitlines() if "np-printed-pages" in l), "")
check("one page reads as a range of itself", "p[45, 45]" in line, line or o)

# pages, next step, missing position, questions
c, o = run("status", "--now", "2026-12-21T11:00"); check("no flag for the session still running today", "ended without a reading position" not in o, o)
c, o = run("status", "--now", "2026-12-22T06:00"); check("status flags yesterday's session with no reading position", "ended without a reading position" in o, o)
c, o = run("pages", "--now", "2026-12-22T06:10", "--chapter", "2", "--page", "76", "--heading", "Data type character codes", "--next", "type the character code table on p76")
c, o = run("status", "--now", "2026-12-23T06:00"); check("status shows the planned first step and no flag", "First step planned" in o and "ended without" not in o, o)
c, o = run("question", "--now", "2026-12-23T06:01", "--text", "why does full_like keep the int dtype?")
c, o = run("status", "--now", "2026-12-23T06:02"); check("open question shows", "#1 why does full_like" in o, o)
c, o = run("question", "--now", "2026-12-23T06:03", "--close", "1")
c, o = run("status", "--now", "2026-12-23T06:04"); check("closed question hidden", "why-questions" not in o, o)
c, o = run("question", "--now", "2026-12-23T06:05", "--close", "1"); check("closing twice refused", c == 1, o)

# time, limits, backdating, guard, corruption
c, o = run("tip", "--now", "2026-12-01T09:00", "--text", "late"); check("event backdated over a day refused", c == 1 and "more than a day before" in o, o)
c, o = run("tip", "--now", "2026-12-23T05:30", "--text", "clock skew"); check("event an hour before latest accepted", c == 0, o)
c, o = add("2026-12-24T09:10", "limit-a", "concept", imp="useful", ch="3", pages="90"); check("1st skill of the day", c == 0, o)
c, o = add("2026-12-24T09:11", "limit-b", "concept", imp="useful", ch="3", pages="90"); check("2nd skill of the day", c == 0, o)
c, o = add("2026-12-24T09:12", "limit-c", "concept", imp="useful", ch="3", pages="90"); check("3rd skill of the day refused", c == 1 and "daily limit" in o, o)
for i in range(10):
    add("2026-12-24T09:15", f"bulk-{i}", "concept", imp="useful", ch="3", pages="90", force=True)
c, o = add("2026-12-26T09:00", "one-more", "concept", imp="useful", ch="3", pages="91"); check("backlog over limit refuses new skill", c == 1 and "over the limit" in o, o)
c, o = run("hook-guard", stdin=json.dumps({"tool_input": {"file_path": "C:\\x\\PRACTICE\\log.jsonl"}})); check("guard blocks log edits", c == 2, o)
c, o = run("hook-guard", stdin=json.dumps({"tool_input": {"file_path": "C:\\x\\PRACTICE\\time.csv"}})); check("guard blocks clock record edits", c == 2 and "clock.py" in o, o)
c, o = run("hook-guard", stdin=json.dumps({"tool_input": {"file_path": "/home/x/practice/time.csv"}})); check("guard blocks the clock record on posix paths too", c == 2, o)
c, o = run("hook-guard", stdin=json.dumps({"tool_input": {"file_path": "C:\\x\\PRACTICE\\settings.json"}})); check("guard allows other files", c == 0, o)
c, o = run("target", "--chars", "150", "--words", "60", "--layer", "4"); check("target (150/30 + 60/120) min x2 = 660 s", o == "660", o)
c, o = run("validate", "--now", "2026-12-26T10:00"); check("log validates", c == 0, o)
with (root / "PRACTICE" / "log.jsonl").open("a", encoding="utf-8") as f:
    f.write("{bad json\n")
c, o = run("status"); check("corrupt log reported, command refused", c == 1 and "not valid JSON" in o, o)
c, o = run("hook-session-start"); check("session hook never fails the session", c == 0 and "log problem" in o, o)
# no-attempt pays nothing and counts wrong
root2 = Path(tempfile.mkdtemp())
shutil.copytree(REPO / "PRACTICE" / "tools", root2 / "PRACTICE" / "tools")
shutil.copy(REPO / "PRACTICE" / "settings.json", root2 / "PRACTICE" / "settings.json")
H = root2 / "PRACTICE" / "tools" / "harness.py"
add("2026-09-18T09:00", "kdd", "concept")
c, o = rep("2026-09-19T08:00", "n1#1", "kdd", "correct", 0, "explain", extra=("--no-attempt",))
check("no-attempt counts wrong and pays nothing", "L3 wrong -> L2" in o and "Money" not in o, o)
for i in range(6):
    add("2026-09-18T09:0" + str(i), f"cap-{i}", "concept", force=True)
for i in range(6):
    rep("2026-09-19T08:1" + str(i), f"cap#{i}", f"cap-{i}", "correct", 0, "explain")
c, o = run("ticket", "--now", "2026-09-19T08:40", "--id", "t-1", "--result", "done")
check("a ticket pays $20 however much the day already earned", "+$20.00" in o, o)
# a study-only session (clock rows, no log events) still flags a missing reading position
root3 = Path(tempfile.mkdtemp())
shutil.copytree(REPO / "PRACTICE" / "tools", root3 / "PRACTICE" / "tools")
shutil.copy(REPO / "PRACTICE" / "settings.json", root3 / "PRACTICE" / "settings.json")
H = root3 / "PRACTICE" / "tools" / "harness.py"
run("pages", "--now", "2026-09-24T20:15", "--chapter", "2", "--page", "82")
(root3 / "PRACTICE" / "time.csv").write_text("study_day,window,event,time\n2026-10-03,evening,start,2026-10-03T21:30\n", encoding="utf-8")
c, o = run("status", "--now", "2026-10-04T06:40")
check("study-only session flags missing reading position", "session on 2026-10-03 ended without a reading position" in o, o)
root4 = Path(tempfile.mkdtemp())
shutil.copytree(REPO / "PRACTICE" / "tools", root4 / "PRACTICE" / "tools")
shutil.copy(REPO / "PRACTICE" / "settings.json", root4 / "PRACTICE" / "settings.json")
H = root4 / "PRACTICE" / "tools" / "harness.py"
run("question", "--now", "2026-09-23T06:01", "--text", "Remove the clock entirely", "--rule")
run("question", "--now", "2026-09-23T06:02", "--text", "why U21 for int64?")
c, o = run("status", "--now", "2026-09-24T06:05")
check("rule request shown separately from why-questions", "Rule change waiting for confirmation" in o and "#1): Remove the clock" in o and "why-questions (turn one into a warm-up rep, then close it): #2" in o, o)
root5 = Path(tempfile.mkdtemp())
shutil.copytree(REPO / "PRACTICE" / "tools", root5 / "PRACTICE" / "tools")
shutil.copy(REPO / "PRACTICE" / "settings.json", root5 / "PRACTICE" / "settings.json")
H = root5 / "PRACTICE" / "tools" / "harness.py"
run("question", "--now", "2026-09-23T06:01", "--text", "Remove the clock", "--rule")
c, o = run("status", "--now", "2026-09-23T06:30"); check("rule request hidden in the window it was logged", "Rule change waiting" not in o, o)
c, o = run("status", "--now", "2026-09-23T19:30"); check("rule request shown at the evening session the same day", "Rule change waiting" in o, o)
c, o = run("guide", "--now", "2026-09-23T09:00")
check("guide prints the process with the settings' own numbers",
      c == 0 and "240 minutes a study day" in o and "Fri 17:00 to Sun 12:00" in o, o)
# README.md quotes this output for anyone reading the repo, so it has to still be the real output.
readme = (REPO / "README.md").read_text(encoding="utf-8")
check("README.md quotes the current guide output",
      o.strip() in readme,
      "Regenerate it: uv run --no-project python PRACTICE/tools/harness.py guide, then replace the\n"
      "guide block under 'The whole process, from the tool itself' in README.md.")
# the full drop-and-climb story, in its own log so the dates stay in order
root6 = Path(tempfile.mkdtemp())
shutil.copytree(REPO / "PRACTICE" / "tools", root6 / "PRACTICE" / "tools")
shutil.copy(REPO / "PRACTICE" / "settings.json", root6 / "PRACTICE" / "settings.json")
H = root6 / "PRACTICE" / "tools" / "harness.py"
add("2027-02-01T09:00", "climb", "concept", ch="1", pages="5-6", source="learner-notes")
c, o = rep("2027-02-02T08:00", "cl#1", "climb", "correct", 0, "explain")
check("first rep at L3 is new ground: warm-up and scheduled rep", "L3 correct -> L4" in o and "Money: +$2.00" in o, o)
c, o = rep("2027-02-05T08:00", "cl#2", "climb", "wrong", 0, "explain")
check("first rep at L4 is new ground and pays even though it is wrong", "L4 wrong -> L3" in o and "Money: +$2.00" in o, o)
c, o = rep("2027-02-06T08:00", "cl#3", "climb", "correct", 0, "explain")
check("the rep below the best layer pays only the repeat rate", "L3 correct -> L4" in o and "Money: +$0.25" in o, o)
c, o = rep("2027-02-09T08:00", "cl#4", "climb", "correct", 0, "explain")
check("winning the best layer back pays full, the clean bonus and the extra dollar",
      "L4 correct -> L5" in o and "Money: +$5.00" in o, o)
c, o = rep("2027-02-16T08:00", "cl#5", "climb", "correct", 0, "explain")
check("the layer above that is ordinary new ground again", "L5 correct -> L6" in o and "Money: +$4.00" in o, o)

print("FAILURES:", fails)
sys.exit(1 if fails else 0)
