"""Practice bookkeeping for the Data-Analysis-4th-Edition study repo. Claude runs it; the learner
never has to.

PRACTICE/log.jsonl is the only record. Every command replays it from the top to work out each
skill's layer and due day, the coins, the week's practice days, the reading position, and the
open why-questions, so the state can't drift from the history. A wrong entry gets corrected with
an `amend` event, never by editing a line, and a hook blocks Claude's Edit and Write tools on the
log.

    status              what the next session opens with (the SessionStart hook prints this)
    due                 work due now: skills needing a worked example, then scheduled reps
    skills              every skill with its layer, due day, and last rep
    add-skill           add a skill drafted from pages the learner read
    skill-edit          reword or re-rate a skill, or drop one added by mistake the same day
    rep                 record one skill's result on one rep (--test-out to retire a known skill)
    fix                 record that the learner fixed a wrong rep and explained the bug
    amend               change a recorded result after a dispute
    pages               record where the learner stopped reading and the first step for next time
    question            log a why-question, or a rule change to confirm next session (--rule); --close N
    ticket              record a finished or abandoned weekly ticket
    tip                 record a tip that was given, and rebuild PRACTICE/tips.md
    set-rewards         set the learner's monthly budget and dollar-priced menu, from now on
    redeem              spend coins on an item from the menu
    target              time target in seconds for a timed rep
    validate            check the log and settings
    hook-session-start  SessionStart hook entry point
    hook-guard          PreToolUse hook entry point

Run from the repo root:
    uv run --no-project python PRACTICE/tools/harness.py <command> [options]

Standard library only, so it runs the same on Windows, macOS, and Linux with nothing to install.
`--now YYYY-MM-DDTHH:MM` acts as if it were that time. It works only when the environment variable
PRACTICE_ALLOW_NOW is 1, because in a real session a chosen time would let results be backdated.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

PRACTICE_DIR = Path(__file__).resolve().parents[1]
LOG_FILE = PRACTICE_DIR / "log.jsonl"
SETTINGS_FILE = PRACTICE_DIR / "settings.json"
TIPS_FILE = PRACTICE_DIR / "tips.md"

# Days a skill waits at a layer before it is due, counted from the rep that moved it there.
# Layers 1 and 2 are worked in the study session itself, so they are due right away.
WAIT_DAYS = {3: 1, 4: 3, 5: 7, 6: 14, 7: 30}
TOP_LAYER = 7
# The first layer the learner works alone. A wrong answer above it drops the skill here.
ALONE_LAYER = 4
# Multiplier on the learner's own typing and reading time for a timed rep at each layer.
TIME_SCALE = {4: 2.0, 5: 1.5, 6: 1.25, 7: 1.25}

# Coin rates live in code, not settings, so changing them is a visible code change that applies
# from the commit on, and no one can raise them to repay old reps. The learner controls the money
# through the budget and menu instead (`set-rewards`).
COINS_PER_DOLLAR = 10
DAILY_CAP = 60
PAY = {"warmup_start": 5, "scheduled_rep": 10, "clean_bonus": 10, "study_catch": 10, "fix": 10, "ticket": 40}

KINDS = ("code", "concept")
IMPORTANCE = ("core", "useful")
RESULTS = ("correct", "wrong")
# 0: no help. 1: Claude asked a guiding question or gave a hint. 2: Claude gave the answer or code.
HELP_LEVELS = (0, 1, 2)
FORMATS = ("worked", "parsons", "fill", "predict", "tool-pick", "bug-hunt", "contrast", "modify",
           "decompose", "explain", "ticket")
SKILL_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,60}$")
EVENT_FIELDS = {
    "skill": {"id", "text", "kind", "importance", "chapter", "pages", "source"},
    "skill-edit": {"id"},
    "rep": {"rep", "skill", "format", "result", "help"},
    "fix": {"rep"},
    "amend": {"rep", "skill", "result", "reason"},
    "pages": {"chapter", "page"},
    "question": set(),
    "ticket": {"id", "result"},
    "tip": {"text"},
    "rewards": {"budget_dollars", "menu"},
    "redeem": {"item", "coins"},
}
SETTINGS_KEYS = ("coding_chars_per_minute", "reading_words_per_minute", "day_starts_hour",
                 "weekly_practice_days", "new_skill_backlog_limit", "max_new_skills_per_day")


class LogError(Exception):
    """The log or settings can't be used as written."""


# ----------------------------------------------------------------------------- time


def parse_time(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value).replace(tzinfo=None)
    except (TypeError, ValueError):
        raise LogError(f"{value!r} is not an ISO date-time such as 2026-09-18T08:05")


def stamp(moment: datetime) -> str:
    return moment.replace(microsecond=0, tzinfo=None).isoformat(timespec="minutes")


def study_day(moment: datetime, day_starts_hour: int) -> date:
    """A session at 00:30 still belongs to the previous day, so a late night isn't a new morning."""
    return (moment - timedelta(hours=day_starts_hour)).date()


# ----------------------------------------------------------------------------- files


def load_settings(path: Path) -> dict:
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise LogError(f"{path} does not exist")
    except json.JSONDecodeError as exc:
        raise LogError(f"{path.name} is not valid JSON: {exc.msg} at line {exc.lineno}")
    missing = [key for key in SETTINGS_KEYS if key not in settings]
    if missing:
        raise LogError(f"{path.name} is missing {', '.join(missing)}")
    return settings


def load_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    events = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise LogError(f"log line {number} is not valid JSON: {exc.msg}")
        if not isinstance(event, dict) or event.get("type") not in EVENT_FIELDS:
            raise LogError(f"log line {number} has no known type")
        missing = sorted(EVENT_FIELDS[event["type"]] - set(event)) + ([] if "at" in event else ["at"])
        if missing:
            raise LogError(f"log line {number} ({event['type']}) is missing {', '.join(missing)}")
        event["_line"] = number
        event["_at"] = parse_time(event["at"])
        events.append(event)
    # Two computers with clocks a little apart, or a merge of two computers' logs, can leave lines
    # slightly out of time order. Replaying in time order gives the same result either way.
    events.sort(key=lambda e: (e["_at"], e["_line"]))
    return events


def append_event(path: Path, event: dict) -> None:
    # newline="\n" keeps the file identical on Windows, macOS, and Linux.
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


# ----------------------------------------------------------------------------- replay


@dataclass
class Skill:
    id: str
    text: str
    kind: str
    importance: str
    chapter: int
    pages: list
    source: str
    added: datetime
    layer: int
    anchor: datetime
    retired: str | None = None  # "mastered", "tested out", or "dropped"
    reps: int = 0
    history: list = field(default_factory=list)
    test_out_days: set = field(default_factory=set)

    def due_day(self, day_starts_hour: int) -> date | None:
        if self.retired:
            return None
        start = study_day(self.anchor, day_starts_hour)
        return start if self.layer < 3 else start + timedelta(days=WAIT_DAYS[self.layer])


@dataclass
class State:
    skills: dict = field(default_factory=dict)
    reading: dict | None = None
    last_activity: datetime | None = None
    coins_by_day: dict = field(default_factory=lambda: defaultdict(int))
    coins_by_month: dict = field(default_factory=lambda: defaultdict(int))
    redeemed: int = 0
    budget_dollars: int | None = None
    menu: list = field(default_factory=list)
    pending_rewards: tuple | None = None  # (study day it takes effect, event)
    practice_days: set = field(default_factory=set)
    tickets: list = field(default_factory=list)
    tips: list = field(default_factory=list)
    questions: list = field(default_factory=list)  # [text, asked stamp, open, kind]
    reps_seen: set = field(default_factory=set)
    fixed: set = field(default_factory=set)

    @property
    def earned(self) -> int:
        return sum(self.coins_by_day.values())

    @property
    def balance(self) -> int:
        return self.earned - self.redeemed


def settle_rewards(state: State, day: date) -> None:
    """Apply a budget and menu change once its study day has arrived."""
    if state.pending_rewards and day >= state.pending_rewards[0]:
        state.budget_dollars = state.pending_rewards[1]["budget_dollars"]
        state.menu = state.pending_rewards[1]["menu"]
        state.pending_rewards = None


def effective_result(result: str, help_level: int, layer: int) -> tuple[str, str | None]:
    """Help turns a correct answer wrong once the layer is past where that help belongs."""
    if result == "correct" and layer >= ALONE_LAYER and help_level >= 1:
        return "wrong", "help at layer 4 or above counts as wrong"
    if result == "correct" and layer == 3 and help_level >= 2:
        return "wrong", "Claude gave the answer, so layer 3 counts it wrong"
    return result, None


def next_layer(layer: int, result: str) -> tuple[int, bool]:
    """Return (layer, mastered). Correct climbs one layer, and correct at the top masters the
    skill. Wrong at layers 1 and 2 stays, because those layers are still building the idea. Wrong
    at 3 or 4 drops one layer. Wrong above 4 drops to 4, then one layer per further wrong."""
    if result == "correct":
        return (layer, True) if layer == TOP_LAYER else (layer + 1, False)
    if layer <= 2:
        return layer, False
    if layer > ALONE_LAYER:
        return ALONE_LAYER, False
    return layer - 1, False


def replay(events: list[dict], settings: dict) -> State:
    state = State()
    hour = settings["day_starts_hour"]
    amendments = {(e["rep"], e["skill"]): e for e in events if e["type"] == "amend"}
    rep_outcomes = defaultdict(list)  # rep id -> [(layer, result, help, seconds, target)] for counted skills
    bonus_paid = {}  # rep id -> day the clean bonus was paid
    no_attempt_reps = set()
    warmup_days, study_days = set(), set()

    def pay(day: date, amount: int, daily_cap: bool = True) -> None:
        """Pay up to the daily cap and, once a budget is set, the monthly budget in effect today.
        A budget change can't repay or claw back earlier months."""
        room = DAILY_CAP - state.coins_by_day[day] if daily_cap else amount
        month = (day.year, day.month)
        if state.budget_dollars is not None:
            room = min(room, state.budget_dollars * COINS_PER_DOLLAR - state.coins_by_month[month])
        paid = max(0, min(amount, room))
        state.coins_by_day[day] += paid
        state.coins_by_month[month] += paid

    def claw_back(day: date, amount: int) -> None:
        state.coins_by_day[day] -= amount
        state.coins_by_month[(day.year, day.month)] -= amount

    for event in events:
        at, kind = event["_at"], event["type"]
        day = study_day(at, hour)
        where = f"log line {event['_line']}"
        settle_rewards(state, day)

        if kind == "skill":
            if not SKILL_ID.match(event["id"]) or event["id"] in state.skills:
                raise LogError(f"{where}: skill id {event['id']!r} is malformed or already used")
            if event["kind"] not in KINDS or event["importance"] not in IMPORTANCE:
                raise LogError(f"{where}: kind must be one of {KINDS} and importance one of {IMPORTANCE}")
            start = 1 if event["kind"] == "code" else 3
            state.skills[event["id"]] = Skill(event["id"], event["text"], event["kind"], event["importance"],
                                              event["chapter"], event["pages"], event["source"], at, start, at)
            state.last_activity = at

        elif kind == "skill-edit":
            skill = state.skills.get(event["id"])
            if skill is None:
                raise LogError(f"{where}: unknown skill {event['id']!r}")
            skill.text = event.get("text", skill.text)
            skill.importance = event.get("importance", skill.importance)
            if event.get("drop"):
                if study_day(skill.added, hour) != day:
                    raise LogError(f"{where}: {skill.id} can only be dropped on the day it was added; "
                                   "a skill the learner already knows retires through a test-out rep")
                skill.retired = "dropped"

        elif kind == "rep":
            skill = state.skills.get(event["skill"])
            if skill is None:
                raise LogError(f"{where}: unknown skill {event['skill']!r}")
            key = (event["rep"], event["skill"])
            if key in state.reps_seen:
                raise LogError(f"{where}: rep {event['rep']} already has a result for {event['skill']}")
            state.reps_seen.add(key)
            if event["result"] not in RESULTS or event["help"] not in HELP_LEVELS or event["format"] not in FORMATS:
                raise LogError(f"{where}: result, help, or format is not an allowed value")
            state.last_activity = at
            amended = amendments.get(key)
            result = amended["result"] if amended else event["result"]
            if skill.retired:
                skill.history.append((stamp(at), event["rep"], f"extra ({skill.retired})"))
                continue
            if event.get("test_out"):
                # Passing alone retires the skill; missing leaves it exactly where it was, because
                # the learner asked to skip ahead and only the skip is being tested. Pays nothing.
                # One try a day, so a skill can't be retired by retrying until a guess lands.
                if day in skill.test_out_days:
                    raise LogError(f"{where}: {skill.id} already had a test-out on {day}; the next try is tomorrow")
                skill.test_out_days.add(day)
                passed = result == "correct" and event["help"] == 0
                if passed:
                    skill.retired = "tested out"
                skill.history.append((stamp(at), event["rep"], f"test-out {'passed, retired' if passed else 'missed, unchanged'}"))
                state.practice_days.add(day)
                continue
            due = skill.due_day(hour)
            if skill.layer >= 3 and due is not None and day < due:
                skill.history.append((stamp(at), event["rep"], f"extra (due {due})"))
                continue
            layer_before = skill.layer
            result, _ = effective_result(result, event["help"], layer_before)
            # "idk", a blank, or a guess with no reasoning still counts as wrong for the schedule,
            # but pays nothing, so due reps can't be farmed for coins without trying them.
            attempted = not event.get("no_attempt")
            if not attempted:
                result = "wrong"
                no_attempt_reps.add(event["rep"])
            skill.layer, mastered = next_layer(layer_before, result)
            if mastered:
                skill.retired = "mastered"
            skill.anchor = at
            skill.reps += 1
            skill.history.append((stamp(at), event["rep"], f"{event['format']} L{layer_before} {result} -> L{skill.layer}"
                                  + (" mastered" if mastered else "")))
            state.practice_days.add(day)
            earlier = list(rep_outcomes[event["rep"]])
            outcome = (layer_before, result, event["help"], event.get("seconds"), event.get("target_seconds"))
            rep_outcomes[event["rep"]].append(outcome)
            if not attempted:
                pass
            elif layer_before >= 3:
                if day not in warmup_days:
                    warmup_days.add(day)
                    pay(day, PAY["warmup_start"])
                if not any(layer >= 3 for layer, *_ in earlier):
                    pay(day, PAY["scheduled_rep"])
            elif day not in study_days:
                study_days.add(day)
                pay(day, PAY["study_catch"])
            # Bonus for a clean, on-time rep at layer 4 and up, once per rep. A rep covering two
            # skills pays it only when every alone skill in it is clean.
            if layer_before >= ALONE_LAYER and attempted:
                clean = (result == "correct" and event["help"] == 0
                         and (outcome[4] is None or (outcome[3] or 0) <= outcome[4]))
                alone_earlier = [o for o in earlier if o[0] >= ALONE_LAYER]
                if clean and not alone_earlier:
                    before = state.coins_by_day[day]
                    pay(day, PAY["clean_bonus"])
                    bonus_paid[event["rep"]] = (day, state.coins_by_day[day] - before)
                elif not clean and event["rep"] in bonus_paid:
                    paid_day, amount = bonus_paid.pop(event["rep"])
                    claw_back(paid_day, amount)

        elif kind == "fix":
            outcomes = rep_outcomes.get(event["rep"])
            if not outcomes or not any(result == "wrong" for _, result, *_ in outcomes):
                raise LogError(f"{where}: rep {event['rep']} has no counted wrong result to fix")
            if event["rep"] in no_attempt_reps:
                raise LogError(f"{where}: rep {event['rep']} had no attempt, so there's no bug to fix")
            if event["rep"] in state.fixed:
                raise LogError(f"{where}: rep {event['rep']} was already fixed")
            state.fixed.add(event["rep"])
            pay(day, PAY["fix"])

        elif kind == "amend":
            if (event["rep"], event["skill"]) not in state.reps_seen:
                raise LogError(f"{where}: amend names a rep and skill that aren't recorded yet")

        elif kind == "pages":
            state.reading = {"chapter": event["chapter"], "page": event["page"], "heading": event.get("heading", ""),
                             "next": event.get("next", ""), "at": at}

        elif kind == "question":
            if "close" in event:
                index = event["close"] - 1
                if not 0 <= index < len(state.questions) or not state.questions[index][2]:
                    raise LogError(f"{where}: no open question number {event['close']}")
                state.questions[index][2] = False
            elif "text" in event:
                state.questions.append([event["text"], stamp(at), True, event.get("kind", "why")])
            else:
                raise LogError(f"{where}: a question needs text or close")

        elif kind == "ticket":
            if event["result"] not in ("done", "abandoned"):
                raise LogError(f"{where}: ticket result must be done or abandoned")
            if any(t["id"] == event["id"] for t in state.tickets):
                raise LogError(f"{where}: ticket {event['id']} is already recorded")
            state.tickets.append({"id": event["id"], "result": event["result"], "at": at})
            if event["result"] == "done":
                # A ticket is once a week, so it sits outside the daily cap: a full warm-up the
                # same morning shouldn't make the week's biggest piece of work pay nothing.
                pay(day, PAY["ticket"], daily_cap=False)

        elif kind == "tip":
            state.tips.append((stamp(at), event["text"]))

        elif kind == "rewards":
            # The first budget and menu apply at once. Later changes start the next study day, so a
            # price can't be dropped, redeemed, and put back in one sitting.
            if state.budget_dollars is None:
                state.budget_dollars = event["budget_dollars"]
                state.menu = event["menu"]
            else:
                state.pending_rewards = (day + timedelta(days=1), event)

        elif kind == "redeem":
            if event["coins"] > state.balance:
                raise LogError(f"{where}: redeeming {event['coins']} coins overdraws the balance of {state.balance}")
            state.redeemed += event["coins"]

    return state


# ----------------------------------------------------------------------------- views


def due_lists(state: State, settings: dict, today: date) -> tuple[list[Skill], list[Skill]]:
    """Skills still needing a worked example (layers 1 and 2), and scheduled reps (layer 3 up)
    ordered most overdue relative to their wait first, core before useful."""
    hour = settings["day_starts_hour"]
    building, scheduled = [], []
    for skill in state.skills.values():
        due = skill.due_day(hour)
        if due is None or due > today:
            continue
        (building if skill.layer < 3 else scheduled).append(skill)

    def lateness(skill: Skill) -> float:
        return (today - study_day(skill.anchor, hour)).days / WAIT_DAYS[skill.layer]

    scheduled.sort(key=lambda s: (-lateness(s), s.importance != "core", s.added))
    building.sort(key=lambda s: (s.importance != "core", s.added))
    return building, scheduled


def week_days(state: State, today: date) -> int:
    monday = today - timedelta(days=today.weekday())
    return sum(1 for day in state.practice_days if monday <= day <= today)


def week_streak(state: State, settings: dict, today: date) -> int:
    """Consecutive finished weeks that met the practice-day goal. The current week never breaks it."""
    monday = today - timedelta(days=today.weekday())
    streak = 0
    while True:
        monday -= timedelta(days=7)
        if sum(1 for day in state.practice_days if monday <= day < monday + timedelta(days=7)) < settings["weekly_practice_days"]:
            return streak
        streak += 1


def ticket_ready(state: State, today: date, hour: int) -> bool:
    # Only a finished ticket starts the week's wait, so one cut short by the clock comes back soon.
    last = max((study_day(t["at"], hour) for t in state.tickets if t["result"] == "done"), default=None)
    eligible = sum(1 for s in state.skills.values() if not s.retired and s.layer >= 3)
    return eligible >= 5 and (last is None or (today - last).days >= 7)


def git_note() -> str | None:
    try:
        subprocess.run(["git", "fetch", "--quiet", "origin"], cwd=PRACTICE_DIR.parent, timeout=6, capture_output=True)
        out = subprocess.run(["git", "rev-list", "--left-right", "--count", "HEAD...@{upstream}"],
                             cwd=PRACTICE_DIR.parent, timeout=6, capture_output=True, text=True)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    ahead, behind = (int(n) for n in out.stdout.split())
    if behind:
        return f"This computer is {behind} commit(s) behind GitHub: ask the learner to pull first, or the log splits."
    if ahead:
        return f"{ahead} local commit(s) aren't on GitHub yet."
    return None


def last_clock_day(today: date) -> date | None:
    """The latest study day before today that the session clock timed."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import clock
        days = [date.fromisoformat(row["study_day"]) for row in clock.read_rows() if row["event"] == "start"]
    except Exception:  # a missing or broken time.csv just means no timed sessions to count
        return None
    earlier = [day for day in days if day < today]
    return max(earlier, default=None)


def same_window(earlier: datetime, now: datetime, hour: int) -> bool:
    """Whether two moments fall in the same study window of the same study day."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import clock
        config = clock.load_config()
    except (Exception, SystemExit):
        return study_day(earlier, hour) == study_day(now, hour)
    return (study_day(earlier, hour) == study_day(now, hour)
            and clock.window_at(earlier, config)[0] == clock.window_at(now, config)[0])


def clock_line(now: datetime) -> str:
    """The session clock's view of this moment, from clock.py next to this file."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import clock
        config = clock.load_config()
        return clock.describe(clock.clock_at(now, config), now, config)
    except (Exception, SystemExit) as exc:  # a broken clock must not block the session status
        return f"CLOCK: unavailable ({exc})"


def status_text(state: State, settings: dict, now: datetime, check_git: bool) -> str:
    hour = settings["day_starts_hour"]
    today = study_day(now, hour)
    building, scheduled = due_lists(state, settings, today)
    lines = [f"PRACTICE STATUS {stamp(now)} (study day {today})"]
    r = state.reading
    if r:
        lines.append(f"Reading: stopped at p{r['page']}, chapter {r['chapter']}"
                     + (f" ({r['heading']})" if r["heading"] else "") + f", on {study_day(r['at'], hour)}.")
        if r["next"]:
            lines.append(f"First step planned for this session: {r['next']}")
    else:
        lines.append("Reading: no position recorded yet.")
    # A session that only studied logs nothing to this file, so the clock's rows count as activity too.
    logged_day = study_day(state.last_activity, hour) if state.last_activity else None
    last_day = max(filter(None, [logged_day if logged_day and logged_day < today else None,
                                 last_clock_day(today)]), default=None)
    if last_day and (r is None or study_day(r["at"], hour) < last_day):
        lines.append(f"The session on {last_day} ended without a reading position: ask where they stopped before study.")
    lines.append(f"Due: {len(scheduled)} scheduled rep(s), {len(building)} skill(s) still being built (layers 1 and 2).")
    for skill in scheduled[:6]:
        lines.append(f"  L{skill.layer} {skill.id} [{skill.kind}, {skill.importance}]: {skill.text}")
    for skill in building[:3]:
        work = "worked example" if skill.layer == 1 else "parsons or fill"
        lines.append(f"  L{skill.layer} {skill.id} [{work}]: {skill.text}")
    if len(scheduled) > settings["new_skill_backlog_limit"]:
        lines.append(f"Backlog {len(scheduled)} is over {settings['new_skill_backlog_limit']}: add no new skills until it drops.")
    open_questions = [(n, q) for n, q in enumerate(state.questions, start=1) if q[2]]
    # A rule change is asked about at the next session, never the one it was requested in, so one
    # logged in the window that is still open waits.
    rules = [(n, q) for n, q in open_questions if q[3] == "rule" and not same_window(parse_time(q[1]), now, hour)]
    whys = [(n, q) for n, q in open_questions if q[3] == "why"]
    for n, q in rules:
        lines.append(f"Rule change waiting for confirmation (ask once at this opening, apply only on a yes, "
                     f"then close #{n}): {q[0]}")
    if whys:
        lines.append("Open why-questions (turn one into a warm-up rep, then close it): "
                     + "; ".join(f"#{n} {q[0]}" for n, q in whys[:3]))
    lines.append(f"Week: {week_days(state, today)} of {settings['weekly_practice_days']} practice days; "
                 f"{week_streak(state, settings, today)} week streak.")
    month = state.coins_by_month[(today.year, today.month)]
    if state.budget_dollars is None:
        lines.append(f"Coins: balance {state.balance}. No budget or menu yet: set them at the first warm-up summary.")
    else:
        lines.append(f"Coins: {month} of {state.budget_dollars * COINS_PER_DOLLAR} earned this month, balance {state.balance}.")
    if ticket_ready(state, today, hour):
        lines.append("A weekly ticket is available after the warm-up.")
    lines.append(clock_line(now))
    if check_git:
        note = git_note()
        if note:
            lines.append(note)
    lines.append("Read PRACTICE/CLAUDE.md, then open the session with the warm-up.")
    return "\n".join(lines)


# ----------------------------------------------------------------------------- commands


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--now", type=parse_time, default=None, help="act as if it were this time (tests only)")
    parser = argparse.ArgumentParser(description="Practice bookkeeping for PRACTICE/log.jsonl.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "due", "skills", "validate", "hook-session-start"):
        sub.add_parser(name, parents=[common])
    p = sub.add_parser("add-skill", parents=[common])
    p.add_argument("--id", required=True)
    p.add_argument("--text", required=True)
    p.add_argument("--kind", choices=KINDS, required=True)
    p.add_argument("--importance", choices=IMPORTANCE, required=True)
    p.add_argument("--chapter", type=int, required=True)
    p.add_argument("--pages", required=True, help="first-last, such as 67-70")
    p.add_argument("--source", required=True, choices=("book", "packt-notebook", "learner-notes"))
    p.add_argument("--force", action="store_true", help="add a core idea past the daily or backlog limit")
    p = sub.add_parser("skill-edit", parents=[common])
    p.add_argument("--id", required=True)
    p.add_argument("--text")
    p.add_argument("--importance", choices=IMPORTANCE)
    p.add_argument("--drop", action="store_true", help="remove a skill added by mistake, the same day only")
    p = sub.add_parser("rep", parents=[common])
    p.add_argument("--rep", required=True, help="session stamp and item number, such as 2026-09-18-0805#2")
    p.add_argument("--skill", required=True)
    p.add_argument("--format", choices=FORMATS, required=True)
    p.add_argument("--result", choices=RESULTS, required=True)
    p.add_argument("--help-level", type=int, choices=HELP_LEVELS, required=True)
    p.add_argument("--seconds", type=int)
    p.add_argument("--target-seconds", type=int)
    p.add_argument("--test-out", action="store_true", help="the learner says they know it: pass alone to retire it")
    p.add_argument("--no-attempt", action="store_true", help="idk, blank, or a guess with no reasoning: wrong, pays nothing")
    p = sub.add_parser("fix", parents=[common])
    p.add_argument("--rep", required=True)
    p = sub.add_parser("amend", parents=[common])
    p.add_argument("--rep", required=True)
    p.add_argument("--skill", required=True)
    p.add_argument("--result", choices=RESULTS, required=True)
    p.add_argument("--reason", required=True)
    p = sub.add_parser("pages", parents=[common])
    p.add_argument("--chapter", type=int, required=True)
    p.add_argument("--page", type=int, required=True)
    p.add_argument("--heading", default="")
    p.add_argument("--next", default="", help="one line: the first thing to do next session")
    p = sub.add_parser("question", parents=[common])
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--text")
    group.add_argument("--close", type=int, help="number shown in status")
    p.add_argument("--rule", action="store_true", help="a request to loosen a limit, confirmed at the next session")
    p = sub.add_parser("ticket", parents=[common])
    p.add_argument("--id", required=True)
    p.add_argument("--result", choices=("done", "abandoned"), required=True)
    p = sub.add_parser("tip", parents=[common])
    p.add_argument("--text", required=True)
    p = sub.add_parser("set-rewards", parents=[common])
    p.add_argument("--budget", type=int, required=True, help="whole dollars a month")
    p.add_argument("--item", action="append", required=True, help='"name=dollars", such as "takeout=20"')
    p = sub.add_parser("redeem", parents=[common])
    p.add_argument("--item", required=True)
    p = sub.add_parser("target", parents=[common])
    p.add_argument("--chars", type=int, required=True, help="characters in Claude's own solution, comments included")
    p.add_argument("--words", type=int, required=True, help="words the learner reads in the task")
    p.add_argument("--layer", type=int, choices=sorted(TIME_SCALE), required=True)
    sub.add_parser("hook-guard")
    return parser


def main(argv: list[str] | None = None) -> int:
    # Windows consoles default to a legacy code page; book headings hold curly quotes.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    if args.command == "hook-guard":
        return hook_guard()
    if args.now is not None and os.environ.get("PRACTICE_ALLOW_NOW") != "1":
        print("--now only works in tests (PRACTICE_ALLOW_NOW=1). Record at the real time.")
        return 1
    now = args.now or datetime.now()

    try:
        settings = load_settings(SETTINGS_FILE)
        if args.command == "target":
            seconds = (args.chars / settings["coding_chars_per_minute"] + args.words / settings["reading_words_per_minute"]) * 60
            print(round(seconds * TIME_SCALE[args.layer]))
            return 0
        events = load_events(LOG_FILE)
        state = replay(events, settings)
    except LogError as exc:
        print(f"PRACTICE log problem, nothing was done: {exc}")
        return 0 if args.command == "hook-session-start" else 1

    hour = settings["day_starts_hour"]
    today = study_day(now, hour)
    settle_rewards(state, today)
    if args.command in ("hook-session-start", "status"):
        print(status_text(state, settings, now, check_git=args.command == "hook-session-start"))
        return 0
    if args.command == "validate":
        ahead = [e["_line"] for e in events if e["_at"] > now + timedelta(days=1)]
        if ahead:
            print(f"Warning: log line(s) {ahead} are dated more than a day ahead of this computer's clock.")
        print(f"OK: {len(state.skills)} skills, {sum(s.reps for s in state.skills.values())} counted reps, "
              f"balance {state.balance} coins.")
        return 0
    if args.command in ("due", "skills"):
        building, scheduled = due_lists(state, settings, today)
        rows = building + scheduled if args.command == "due" else list(state.skills.values())
        if not rows:
            print("Nothing due." if args.command == "due" else "No skills yet.")
        for s in rows:
            when = s.retired or f"due {s.due_day(hour)}"
            last = f" | last: {s.history[-1][2]}" if s.history else ""
            print(f"L{s.layer} | {when:<14} | {s.kind:<7} | {s.importance:<6} | ch{s.chapter} p{s.pages} | {s.id}: {s.text}{last}")
        return 0

    event = build_event(args, state, settings, now, today)
    if event is None:
        return 1
    latest = max((e["_at"] for e in events), default=None)
    if latest and now < latest - timedelta(days=1):
        print(f"Not recorded: {stamp(now)} is more than a day before the latest log entry ({stamp(latest)}).")
        return 1
    # Replay with the new event before writing, so a bad event never reaches the file.
    try:
        trial = sorted(events + [dict(event, _line=len(events) + 1, _at=now)], key=lambda e: (e["_at"], e["_line"]))
        new_state = replay(trial, settings)
    except LogError as exc:
        print(f"Not recorded: {exc}")
        return 1
    append_event(LOG_FILE, event)
    report(event, state, new_state, settings)
    return 0


def build_event(args, state: State, settings: dict, now: datetime, today: date) -> dict | None:
    hour = settings["day_starts_hour"]
    event = {"type": args.command, "at": stamp(now)}
    if args.command == "add-skill":
        backlog = len(due_lists(state, settings, today)[1])
        added_today = sum(1 for s in state.skills.values() if study_day(s.added, hour) == today)
        if not args.force and backlog > settings["new_skill_backlog_limit"]:
            print(f"Not added: {backlog} scheduled reps are due, over the limit of {settings['new_skill_backlog_limit']}. "
                  "Pass --force only for a core idea.")
            return None
        if not args.force and added_today >= settings["max_new_skills_per_day"]:
            print(f"Not added: {added_today} skills were already added today, the daily limit, because warm-ups "
                  "can only keep up with about one new skill a reading day.")
            return None
        first, _, last = args.pages.partition("-")
        event.update(type="skill", id=args.id, text=args.text, kind=args.kind, importance=args.importance,
                     chapter=args.chapter, pages=[int(first), int(last or first)], source=args.source)
    elif args.command == "skill-edit":
        event.update(id=args.id)
        for name in ("text", "importance"):
            if getattr(args, name):
                event[name] = getattr(args, name)
        if args.drop:
            event["drop"] = True
    elif args.command == "rep":
        skill = state.skills.get(args.skill)
        if skill is None:
            print(f"No skill {args.skill!r}. Run `skills` to see the ids.")
            return None
        event.update(rep=args.rep, skill=args.skill, format=args.format, result=args.result, help=args.help_level)
        for name in ("seconds", "target_seconds"):
            if getattr(args, name) is not None:
                event[name] = getattr(args, name)
        if args.no_attempt:
            event["no_attempt"] = True
        if args.test_out:
            event["test_out"] = True
        else:
            _, reason = effective_result(args.result, args.help_level, skill.layer)
            if reason:
                print(f"Recording as wrong: {reason}.")
    elif args.command == "fix":
        event.update(rep=args.rep)
    elif args.command == "amend":
        event.update(rep=args.rep, skill=args.skill, result=args.result, reason=args.reason)
    elif args.command == "pages":
        event.update(chapter=args.chapter, page=args.page, heading=args.heading, next=args.next)
    elif args.command == "question":
        event.update({"text": args.text, "kind": "rule" if args.rule else "why"} if args.text else {"close": args.close})
    elif args.command == "ticket":
        event.update(id=args.id, result=args.result)
    elif args.command == "tip":
        event.update(text=args.text)
    elif args.command == "set-rewards":
        menu = []
        for raw in args.item:
            name, _, dollars = raw.rpartition("=")
            if not name.strip() or not dollars.strip().isdigit() or int(dollars) <= 0:
                print(f"Menu item {raw!r} needs the form name=whole dollars, such as takeout=20.")
                return None
            menu.append({"item": name.strip(), "dollars": int(dollars)})
        if args.budget <= 0:
            print("The budget has to be a positive whole number of dollars.")
            return None
        event.update(type="rewards", budget_dollars=args.budget, menu=menu)
    elif args.command == "redeem":
        match = next((m for m in state.menu if m["item"].casefold() == args.item.casefold()), None)
        if match is None:
            names = ", ".join(m["item"] for m in state.menu) or "nothing yet"
            print(f"{args.item!r} is not on the menu ({names}).")
            return None
        event.update(item=match["item"], coins=match["dollars"] * COINS_PER_DOLLAR)
    return event


def report(event: dict, before: State, after: State, settings: dict) -> None:
    hour = settings["day_starts_hour"]
    kind = event["type"]
    if kind == "rep":
        skill = after.skills[event["skill"]]
        due = skill.due_day(hour)
        print(f"{skill.id}: {skill.history[-1][2]}" + (f", due {due}" if due else "") + ".")
    elif kind == "tip":
        lines = ["# Tips and tricks", "", "Rules of thumb from practice sessions, newest last.", ""]
        lines += [f"- {text} ({when[:10]})" for when, text in after.tips]
        TIPS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        print(f"Tip recorded; {TIPS_FILE.name} holds {len(after.tips)}.")
    elif kind == "rewards":
        items = ", ".join(f"{m['item']} {m['dollars'] * COINS_PER_DOLLAR} coins" for m in event["menu"])
        when = "from tomorrow's study day" if before.budget_dollars is not None else "from now on"
        print(f"Budget ${event['budget_dollars']} a month {when}; menu: {items}.")
    elif kind == "redeem":
        print(f"Redeemed {event['item']} for {event['coins']} coins: the learner spends ${event['coins'] // COINS_PER_DOLLAR} of real money on it.")
    else:
        print(f"Recorded {kind}.")
    gained = after.earned - before.earned
    if gained or kind == "redeem":
        print(f"Coins: {gained:+d}, balance {after.balance}.")


def hook_guard() -> int:
    """PreToolUse hook: block Edit and Write on the log, so every change goes through harness.py
    and gets checked by a replay first."""
    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return 0
    path = str((payload.get("tool_input") or {}).get("file_path", "")).replace("\\", "/").casefold()
    if path.endswith("practice/log.jsonl"):
        print("PRACTICE/log.jsonl is written only by harness.py, which checks each event by replaying "
              "the log. Use a harness.py command; fix mistakes with `amend`.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
