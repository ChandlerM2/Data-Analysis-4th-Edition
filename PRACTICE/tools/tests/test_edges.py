"""Checks boundary times, bad input, clawbacks, tickets, and two computers merging one log.

Each check runs the tools as subprocesses on a copy in a temporary folder, so the real log and
time.csv are never touched. Run all suites with `uv run --no-project python PRACTICE/tools/tests/run.py`.
"""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ENV = {**os.environ, "PRACTICE_ALLOW_NOW": "1"}
fails = 0


def fresh():
    root = Path(tempfile.mkdtemp())
    shutil.copytree(REPO / "PRACTICE" / "tools", root / "PRACTICE" / "tools")
    shutil.copy(REPO / "PRACTICE" / "settings.json", root / "PRACTICE" / "settings.json")
    return root


def run(root, tool, *args, stdin=None):
    r = subprocess.run([sys.executable, str(root / "PRACTICE" / "tools" / tool), *args], capture_output=True,
                       text=True, encoding="utf-8", env=ENV, input=stdin)
    return r.returncode, (r.stdout + r.stderr).strip()


def check(name, cond, out=""):
    global fails
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"\n   -> {out}"))
    fails += 0 if cond else 1


H, C = "harness.py", "clock.py"

# --- harness edges
r = fresh()
run(r, H, "add-skill", "--now", "2026-09-18T09:00", "--id", "kdd", "--text", "KDD är en loop 🔁", "--kind", "concept", "--importance", "core", "--chapter", "1", "--pages", "32-33", "--source", "learner-notes")
c, o = run(r, H, "skills", "--now", "2026-09-18T09:01"); check("unicode skill text round-trips", "🔁" in o, o)
c, o = run(r, H, "rep", "--now", "2026-09-19T08:00", "--rep", "a#1", "--skill", "kdd", "--format", "explain", "--result", "wrong", "--help-level", "0", "--no-attempt")
c, o = run(r, H, "fix", "--now", "2026-09-19T08:02", "--rep", "a#1"); check("fix refused after a no-attempt", c == 1 and "no attempt" in o, o)
c, o = run(r, H, "set-rewards", "--now", "2026-09-19T08:03", "--budget", "0", "--item", "x=5"); check("zero budget refused", c == 1, o)
c, o = run(r, H, "set-rewards", "--now", "2026-09-19T08:03", "--budget", "40", "--item", "x=-5"); check("negative price refused", c == 1, o)
c, o = run(r, H, "set-rewards", "--now", "2026-09-19T08:03", "--budget", "40", "--item", "=5"); check("empty item name refused", c == 1, o)
c, o = run(r, H, "rep", "--now", "2026-09-19T08:04", "--rep", "a#2", "--skill", "nope", "--format", "explain", "--result", "correct", "--help-level", "0"); check("unknown skill refused cleanly", c == 1 and "No skill" in o, o)

# clean bonus clawback on a two-skill rep at L4
r = fresh()
for sid in ("s-one", "s-two"):
    run(r, H, "add-skill", "--now", "2026-09-10T09:00", "--id", sid, "--text", sid, "--kind", "concept", "--importance", "core", "--chapter", "1", "--pages", "1", "--source", "book", "--force")
for d, rid in (("2026-09-11", "w1"),):
    for sid in ("s-one", "s-two"):
        run(r, H, "rep", "--now", d + "T08:00", "--rep", rid, "--skill", sid, "--format", "explain", "--result", "correct", "--help-level", "0")
c, o1 = run(r, H, "rep", "--now", "2026-09-14T08:00", "--rep", "w2", "--skill", "s-one", "--format", "explain", "--result", "correct", "--help-level", "0")
c, o2 = run(r, H, "rep", "--now", "2026-09-14T08:00", "--rep", "w2", "--skill", "s-two", "--format", "explain", "--result", "wrong", "--help-level", "0")
check("clean bonus paid then clawed back when the second skill misses", "+25" in o1 and "Coins: -10" in o2, o1 + " | " + o2)

# abandoned ticket doesn't block the next
r = fresh()
for i in range(5):
    run(r, H, "add-skill", "--now", "2026-09-10T09:00", "--id", f"t-{i}", "--text", "x", "--kind", "concept", "--importance", "core", "--chapter", "1", "--pages", "1", "--source", "book", "--force")
c, o = run(r, H, "status", "--now", "2026-09-11T06:00"); check("ticket available with 5 skills at L3", "weekly ticket is available" in o, o)
run(r, H, "ticket", "--now", "2026-09-11T06:30", "--id", "t1", "--result", "abandoned")
c, o = run(r, H, "status", "--now", "2026-09-12T06:00"); check("abandoned ticket comes back the next day", "weekly ticket is available" in o, o)
run(r, H, "ticket", "--now", "2026-09-12T06:30", "--id", "t2", "--result", "done")
c, o = run(r, H, "status", "--now", "2026-09-13T06:00"); check("finished ticket waits a week", "weekly ticket" not in o, o)

# --- clock edges
r = fresh()
for t, want in (("2026-09-18T03:59", "evening"), ("2026-09-18T04:00", "morning"), ("2026-09-18T07:59", "morning"),
                ("2026-09-18T08:00", "closed"), ("2026-09-18T18:59", "closed"), ("2026-09-18T19:00", "evening"),
                ("2026-09-19T00:00", "evening")):
    c, o = run(r, C, "status", "--now", t)
    check(f"clock at {t[11:]} is {want}", (want in o) if want != "closed" else ("closed" in o), o)
(r / "PRACTICE" / "time.csv").write_text("study_day,window,event,time\ngarbage row\n2026-09-18,evening,start,not-a-time\n", encoding="utf-8")
c, o = run(r, C, "hook-prompt", "--now", "2026-09-18T20:00"); check("corrupt time.csv rows are skipped and the hook still answers", c == 0 and "CLOCK:" in o, o)
c, o = run(r, H, "status", "--now", "2026-09-18T20:00"); check("harness status survives a corrupt time.csv", c == 0, o)

# --- two computers, union merge
base = Path(tempfile.mkdtemp())
def git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True)
origin = base / "origin.git"; git(base, "init", "--bare", str(origin))
a = base / "a"; git(base, "clone", str(origin), str(a))
shutil.copytree(REPO / "PRACTICE" / "tools", a / "PRACTICE" / "tools")
shutil.copy(REPO / "PRACTICE" / "settings.json", a / "PRACTICE" / "settings.json")
shutil.copy(REPO / ".gitattributes", a / ".gitattributes")
run(a, H, "add-skill", "--now", "2026-09-10T09:00", "--id", "kk", "--text", "k", "--kind", "concept", "--importance", "core", "--chapter", "1", "--pages", "1", "--source", "book")
for cmd in (("config", "user.email", "t@t"), ("config", "user.name", "t"), ("add", "."), ("commit", "-m", "seed"), ("push", "origin", "HEAD:main")):
    git(a, *cmd)
b = base / "b"; git(base, "clone", "-b", "main", str(origin), str(b))
git(b, "config", "user.email", "t@t"); git(b, "config", "user.name", "t")
run(a, H, "rep", "--now", "2026-09-11T08:00", "--rep", "laptop#1", "--skill", "kk", "--format", "explain", "--result", "correct", "--help-level", "0")
run(b, H, "tip", "--now", "2026-09-11T07:00", "--text", "desktop tip")
git(a, "commit", "-am", "laptop"); git(a, "push", "origin", "HEAD:main")
git(b, "commit", "-am", "desktop")
pull = git(b, "pull", "--no-rebase", "origin", "main")
c, o = run(b, H, "validate", "--now", "2026-09-11T09:00")
check("union merge of two computers' logs replays cleanly", "CONFLICT" not in pull.stdout + pull.stderr and c == 0 and "1 counted reps" in o, pull.stdout + pull.stderr + o)
print("FAILURES:", fails)
sys.exit(1 if fails else 0)
