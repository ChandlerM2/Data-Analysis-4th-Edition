"""Session clock for the study repo. Study happens in two windows a day, each with a time budget:

    day      08:00 to 18:15   start by 16:30: a warm-up of up to 15 minutes, then 90 of study
    closed   18:15 to 19:00   no warm-ups, reps, or new material
    evening  19:00 to 23:00   up to 60 minutes in total
    weekend  Fri 17:00 to Sun 12:00   one window, holding whatever is left of the day's 240

Over all of them sits one cap: 240 minutes a study day, counting every window and the warm-up with
them, because all of it is time worked. On an ordinary weekday the cap never binds, since 105 and
60 come to 165. It does the work on the days the weekend touches, where one pot is shared: spend
105 in Friday's day window and the weekend stretch that opens at 17:00 has 135 left, and a Sunday
morning inside the weekend leaves that much less for Sunday afternoon.

The weekend period outranks the weekday windows while it runs, so inside it there are no sub-windows
and no last start. It is also the only window that crosses midnight, so its rows can carry times
from more than one calendar day, and every window stops counting at the end of the study day it is
keyed to, because minutes are counted one study day at a time.

The day window has a last start time, so a session not begun by 16:30 is spent for the day instead
of starting a stub too short to hold the whole stretch: that block is reading and learning time and
needs its full run. The evening window has no last start, because its job is the opposite. Starting
at 22:40 leaves 20 minutes, and that shrinking number is the nudge to begin early. Either way the
closing time outranks the budget, so minutes left are always the smaller of the two, and the last
start is set so a session begun right at the cutoff still fits the full budget.

The study day resets at 04:00. Wrap-up starts 15 minutes before a budget runs out. The times and
budgets live under "clock" in PRACTICE/settings.json, and "enabled": false there turns the limits
off without touching this file, so the change is one line to undo.

Every clock event is a row in PRACTICE/time.csv, stamped with this computer's clock, and the
minutes used are always worked out from those rows. So the budget doesn't depend on anyone
remembering when the session started, and the CSV doubles as a record of how long sessions run.

Each learner message is proof they were still at the desk, so the prompt hook drops a "seen" row
when the last one is more than stamp_every_minutes old. A session that was closed properly counts
in full, gaps and all. One nobody closed counts only to the last of those marks, plus
idle_grace_minutes if any is allowed, because the last message is the last moment anyone can say
the learner was there. A gap longer than away_after_minutes means they left: the next message
times the session out, closing the old segment back at that mark and locking practice until a new
session begins. That check runs on every message, so the timeout does not depend on a watcher
being alive to notice.

    status       where the clock stands now
    start        open a timed segment (the prompt hook does this on the first message in a window)
    warmup-done  the day window warm-up is over: start the 90-minute study budget
    end          close the open segment when the learner stops early or steps away
    charge       add minutes the learner studied while the clock was stopped (--minutes N)
    report       minutes used per window for the last 14 days
    idle          minutes since the learner's last message, or -1 when nothing is open
    sweep         close any segment left open, back at its last message
    maintenance  this session is repair work, not study, so stop counting its minutes (--off ends it)
    session-start SessionStart hook: sweep, then record that a new session began
    hook-prompt  UserPromptSubmit hook: start the clock when needed and print where it stands

Run from the repo root:
    uv run --no-project python PRACTICE/tools/clock.py <command>

`--now YYYY-MM-DDTHH:MM` works only when PRACTICE_ALLOW_NOW is 1, for tests and simulations.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

PRACTICE_DIR = Path(__file__).resolve().parents[1]
TIME_FILE = PRACTICE_DIR / "time.csv"
SETTINGS_FILE = PRACTICE_DIR / "settings.json"
COLUMNS = ["study_day", "window", "event", "time", "minutes"]
CLOCK_KEYS = ("day_opens", "day_last_start", "day_closes", "evening_opens", "evening_closes",
              "warmup_max_minutes", "day_study_minutes", "evening_minutes", "wrap_up_minutes",
              "daily_minutes", "idle_grace_minutes", "stamp_every_minutes", "away_after_minutes",
              "check_in_after_minutes")
WINDOWS = ("day", "evening", "weekend")
# Rows that prove the learner was at the desk at that minute. An end or a time-up closes instead.
MARKS = ("start", "seen", "charge", "warmup-done")
# A segment the learner walked away from is closed with "timeout" rather than "end", because that
# closing locks practice until a new session begins, and "end" is an ordinary stop.
CLOSERS = ("end", "time-up", "timeout")
# The window times have to run in this order for a day to make sense, and load_config checks it.
ORDERED_TIMES = ("day_opens", "day_last_start", "day_closes", "evening_opens", "evening_closes")
WEEKEND_KEYS = ("opens_day", "opens", "closes_day", "closes")
WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5,
            "sunday": 6}


@dataclass
class Clock:
    """Where one window's budget stands at a moment."""
    window: str | None        # "day", "evening", or None when closed
    study_day: date
    state: str                # closed, missed-start, not-started, warm-up, running, paused, wrap-up, time-up
    used: float               # minutes counted against this window's budget
    limit: float              # minutes the budget allows
    hard_end: datetime | None  # the window's closing time, which also ends the budget
    next_open: str            # when the next window opens, for the learner


def load_config(path: Path = SETTINGS_FILE) -> dict:
    settings = json.loads(path.read_text(encoding="utf-8"))
    config = settings.get("clock")
    if not isinstance(config, dict) or any(key not in config for key in CLOCK_KEYS):
        raise SystemExit(f"settings.json needs a clock section with {', '.join(CLOCK_KEYS)}")
    config["day_starts_hour"] = settings["day_starts_hour"]
    config.setdefault("enabled", True)
    # Every window is read as plain clock times inside one calendar day, so times out of order would
    # quietly open the wrong window or none at all. Catching it here names the setting to fix.
    times = [config[key] for key in ORDERED_TIMES]
    if sorted(times) != times:
        raise SystemExit("settings.json clock times must run in order: " + ", ".join(ORDERED_TIMES))
    weekend = config.get("weekend")
    if weekend is not None:
        if not isinstance(weekend, dict) or any(key not in weekend for key in WEEKEND_KEYS):
            raise SystemExit("settings.json clock.weekend needs " + ", ".join(WEEKEND_KEYS))
        for key in ("opens_day", "closes_day"):
            if str(weekend[key]).lower() not in WEEKDAYS:
                raise SystemExit(f"settings.json clock.weekend {key} must be a weekday name")
        weekend.setdefault("enabled", True)
    return config


def hhmm(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time()


def local(moment: datetime) -> datetime:
    """The same moment with this computer's UTC offset attached, if it has none. Every comparison
    and every duration in this file runs on these, so the hour that repeats when the clocks go back
    is counted once rather than twice, and the hour that goes missing in spring isn't billed."""
    return moment if moment.tzinfo else moment.astimezone()


def at_time(day: date, when: time) -> datetime:
    """A wall-clock time on a study day, as a real moment on this computer."""
    return local(datetime.combine(day, when))


def study_day(moment: datetime, config: dict) -> date:
    return (moment - timedelta(hours=config["day_starts_hour"])).date()


def weekend_span(moment: datetime, config: dict) -> tuple[datetime, datetime] | None:
    """The weekend period this moment sits inside, as (start, end), or None when it sits outside
    one. Unlike the weekday windows this period is named by two weekdays rather than two clock
    times, because it runs across midnight from one day of the week to another."""
    weekend = config.get("weekend")
    if not weekend or not weekend.get("enabled", True):
        return None
    moment = local(moment)
    opens_day = WEEKDAYS[str(weekend["opens_day"]).lower()]
    closes_day = WEEKDAYS[str(weekend["closes_day"]).lower()]
    start = at_time(moment.date() - timedelta(days=(moment.weekday() - opens_day) % 7),
                    hhmm(weekend["opens"]))
    if start > moment:
        start -= timedelta(days=7)
    end = at_time(start.date() + timedelta(days=(closes_day - opens_day) % 7), hhmm(weekend["closes"]))
    if end <= start:
        end += timedelta(days=7)
    return (start, end) if start <= moment < end else None


def weekend_span_for_day(day: date, config: dict) -> tuple[datetime, datetime] | None:
    """The weekend period a study day's rows belong to. A study day runs from 04:00 to 04:00 and
    the period crosses midnight, so which hour of the day lands inside it depends on where the day
    sits: late for the day the period opens, midday for a day it covers whole, early for the
    morning it closes."""
    for hour in (23, 12, 5):
        span = weekend_span(at_time(day, time(hour)), config)
        if span:
            return span
    return None


def next_weekend_start(moment: datetime, config: dict) -> datetime | None:
    """When the next weekend period opens, or None when none is configured."""
    weekend = config.get("weekend")
    if not weekend or not weekend.get("enabled", True):
        return None
    moment = local(moment)
    opens_day = WEEKDAYS[str(weekend["opens_day"]).lower()]
    start = at_time(moment.date() + timedelta(days=(opens_day - moment.weekday()) % 7),
                    hhmm(weekend["opens"]))
    return start if start > moment else start + timedelta(days=7)


def window_at(moment: datetime, config: dict) -> tuple[str | None, datetime | None]:
    """The window these times put this moment in, and when that window closes. The day window's last
    start is not applied here, because a session already under way runs to the closing time: only
    clock_at, which reads the rows, can tell a missed start from a session still going."""
    moment = local(moment)
    span = weekend_span(moment, config)
    if span:
        return "weekend", span[1]
    now = moment.time()
    day = moment.date()
    for window in ("day", "evening"):
        if hhmm(config[f"{window}_opens"]) <= now < hhmm(config[f"{window}_closes"]):
            end = at_time(day, hhmm(config[f"{window}_closes"]))
            # A weekend period opening inside a weekday window ends it early, so the closing time
            # the learner is shown is the moment the budget really stops applying.
            start = next_weekend_start(moment, config)
            return window, min(end, start) if start else end
    return None, None


def read_rows(path: Path = TIME_FILE) -> list[dict]:
    """Rows from time.csv, skipping any that don't parse, so one damaged line (a bad merge, a hand
    edit) can't stop every prompt. The skipped rows stay in the file for anyone checking it."""
    if not path.exists():
        return []
    rows = []
    with path.open(newline="", encoding="utf-8") as handle:
        # Name the columns here rather than trusting the file's header line, so a file started before
        # the minutes column existed still reads its charge rows. The header itself fails the date check.
        for row in csv.DictReader(handle, fieldnames=COLUMNS):
            try:
                date.fromisoformat(row["study_day"])
                datetime.fromisoformat(row["time"])
            except (KeyError, TypeError, ValueError):
                continue
            if row.get("event") == "charge":
                try:
                    if int(row.get("minutes") or "") <= 0:
                        continue
                except ValueError:
                    continue
            if row.get("event") in ("session", "maintenance-on", "maintenance-off") or (
                    row.get("window") in WINDOWS and row.get("event") in MARKS + CLOSERS):
                rows.append(row)
    return rows


def write_row(row: dict, path: Path = TIME_FILE) -> None:
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        if new:
            writer.writeheader()
        writer.writerow(row)


def window_end(day: date, window: str, config: dict) -> datetime:
    """When this window stops counting minutes against this study day. Every window is capped by the
    end of the study day it is keyed to, because usage counts rows one study day at a time: a
    weekend period runs on past 04:00 into the next study day, which meters itself, so letting one
    day's unclosed segment run to the period's close would count the same hours on two rows.
    A weekday window is capped again by a weekend period opening inside it, because from that
    moment the weekend window is the one counting."""
    day_end = at_time(day + timedelta(days=1), time(config["day_starts_hour"]))
    if window == "weekend":
        span = weekend_span_for_day(day, config)
        return min(span[1], day_end) if span else day_end
    end = at_time(day, hhmm(config[f"{window}_closes"]))
    weekend = config.get("weekend")
    if weekend and weekend.get("enabled", True) and day.weekday() == WEEKDAYS[str(weekend["opens_day"]).lower()]:
        end = min(end, at_time(day, hhmm(weekend["opens"])))
    return min(end, day_end)


def usage(rows: list[dict], day: date, window: str, now: datetime, config: dict) -> tuple[float, bool, float | None]:
    """Minutes used in this window, whether a segment is open, and the minute mark when the
    warm-up was marked done (None if it wasn't). A segment left open counts only until the window
    closes, so a session nobody ended can't swallow the rest of the day."""
    now = min(local(now), window_end(day, window, config))
    used, open_start, warmup_mark, seen_at = 0.0, None, None, None
    for row in rows:
        if row["study_day"] != day.isoformat() or row["window"] != window:
            continue
        at = local(datetime.fromisoformat(row["time"]))
        if row["event"] in MARKS:
            seen_at = at
        if row["event"] == "start" and open_start is None:
            open_start = at
        elif row["event"] in CLOSERS and open_start is not None:
            used += max(0.0, (at - open_start).total_seconds() / 60)
            open_start = None
        elif row["event"] == "charge":
            used += int(row["minutes"])
        elif row["event"] == "warmup-done" and warmup_mark is None:
            warmup_mark = used + ((at - open_start).total_seconds() / 60 if open_start else 0)
    if open_start is not None:
        # Nobody closed this one, so it runs to the last sign of life plus the grace, never past now.
        grace = timedelta(minutes=config["idle_grace_minutes"])
        used += max(0.0, (min(now, (seen_at or open_start) + grace) - open_start).total_seconds() / 60)
    return used, open_start is not None, warmup_mark


def day_used(rows: list[dict], day: date, now: datetime, config: dict) -> float:
    """Minutes counted against this study day across every window. The daily cap is read from this
    rather than from one window, because a Friday or a Sunday splits its day between two windows and
    the learner asked for one budget over the whole day."""
    return sum(usage(rows, day, window, now, config)[0] for window in WINDOWS)


def maintenance_on(rows: list[dict]) -> bool:
    """Whether this session was declared maintenance, meaning fixing the tools or the docs rather
    than studying, so none of its minutes count. It is read from the rows after the last session
    row, so every new session starts as ordinary study and has to say otherwise."""
    sessions = [i for i, r in enumerate(rows) if r["event"] == "session"]
    after = rows[sessions[-1] + 1:] if sessions else rows
    marks = [r["event"] for r in after if r["event"] in ("maintenance-on", "maintenance-off")]
    return bool(marks) and marks[-1] == "maintenance-on"


def locked(rows: list[dict]) -> datetime | None:
    """When practice was locked, if it is. A sweep that times a session out locks the tools, and
    only a new session unlocks them: this is the one thing in the clock meant to be impossible to
    talk your way around, so it is derived from the rows rather than kept in a flag someone can
    forget to clear."""
    # Compared as moments, not as text: once a row carries its UTC offset, the strings no longer
    # sort in time order across a daylight-saving change.
    timeouts = [local(datetime.fromisoformat(r["time"])) for r in rows if r["event"] == "timeout"]
    if not timeouts:
        return None
    sessions = [local(datetime.fromisoformat(r["time"])) for r in rows if r["event"] == "session"]
    latest = max(timeouts)
    return None if sessions and max(sessions) > latest else latest


LOCK_MESSAGE = ("PRACTICE LOCKED: the session was closed at {when} after a quiet stretch, so nothing "
                "more is recorded on it. Quit Claude Code and start a new session. Do not work "
                "around this, and close the session yourself if the learner pushes: the record is "
                "worth more than one more rep.")


def sweep(moment: datetime, config: dict) -> tuple[list[str], float | None]:
    """Close every segment left open long enough to mean the learner walked away, and say which.
    It looks at every study day, not just today's, because the session that left one open may have
    been days ago and today's window cannot see it. The second value is how quiet the quietest open
    segment still is, for the caller that only wants to report."""
    rows = read_rows()
    away = timedelta(minutes=config["away_after_minutes"])
    shut, quiet, closed = locked(rows), None, []
    for day, window in sorted({(date.fromisoformat(r["study_day"]), r["window"]) for r in rows}):
        if window not in WINDOWS or not usage(rows, day, window, moment, config)[1]:
            continue
        seen = last_mark(rows, day, window)
        if seen is None:
            continue
        since = (moment - seen).total_seconds() / 60
        quiet = since if quiet is None else min(quiet, since)
        if moment - seen >= away and shut is None:
            stop = min(seen + timedelta(minutes=config["idle_grace_minutes"]),
                       window_end(day, window, config))
            write_row({"study_day": day.isoformat(), "window": window, "event": "timeout",
                       "time": stop.isoformat(timespec="minutes"), "minutes": ""})
            closed.append(f"{window} session on {day} at {stop.strftime('%H:%M')}")
    return closed, quiet


def open_since(rows: list[dict], day: date, window: str) -> datetime | None:
    """When the segment still open in this window began, if one is. The closing row can never be
    stamped before this, however many minutes a charge added on top."""
    began = None
    for row in rows:
        if row["study_day"] != day.isoformat() or row["window"] != window:
            continue
        if row["event"] == "start" and began is None:
            began = local(datetime.fromisoformat(row["time"]))
        elif row["event"] in CLOSERS:
            began = None
    return began


def last_mark(rows: list[dict], day: date, window: str) -> datetime | None:
    """When the learner was last seen in this window, from the rows that prove presence."""
    marks = [local(datetime.fromisoformat(row["time"])) for row in rows
             if row["study_day"] == day.isoformat() and row["window"] == window and row["event"] in MARKS]
    return max(marks) if marks else None


def started_today(rows: list[dict], day: date, window: str) -> bool:
    """Whether this window was opened at all on this study day. A charge counts as an opening,
    because minutes studied while the clock was stopped are still a session that began."""
    return any(row["study_day"] == day.isoformat() and row["window"] == window
               and row["event"] in ("start", "charge") for row in rows)


def next_open_text(moment: datetime, config: dict, pot_spent: bool = False) -> str:
    moment = local(moment)
    hour = config["day_starts_hour"]
    if pot_spent:
        # The windows take turns, but the day's minutes do not come back until the study day does.
        roll = at_time(moment.date(), time(hour))
        if roll <= moment:
            roll += timedelta(days=1)
        if weekend_span(roll, config):
            return f"{hour:02d}:00, when the study day rolls over"
        return f"{config['day_opens']}" + (" tomorrow" if roll.date() != moment.date() else "")
    now = moment.time()
    if now < hhmm(config["day_opens"]):
        opens, text = at_time(moment.date(), hhmm(config["day_opens"])), config["day_opens"]
    elif now < hhmm(config["evening_opens"]):
        opens = at_time(moment.date(), hhmm(config["evening_opens"]))
        text = f"{config['evening_opens']} tonight"
    else:
        opens = at_time(moment.date() + timedelta(days=1), hhmm(config["day_opens"]))
        text = f"{config['day_opens']} tomorrow"
    # A weekend that opens before the next weekday window is the real answer, so say that instead.
    start = next_weekend_start(moment, config)
    if start is not None and start < opens:
        when = "today" if start.date() == moment.date() else start.strftime("%A")
        return f"{config['weekend']['opens']} {when}"
    return text


def clock_at(moment: datetime, config: dict, rows: list[dict] | None = None) -> Clock:
    moment = local(moment)
    rows = read_rows() if rows is None else rows
    day = study_day(moment, config)
    if not config["enabled"]:
        return Clock(None, day, "off", 0, 0, None, "")
    window, hard_end = window_at(moment, config)
    if window is None:
        return Clock(None, day, "closed", 0, 0, None, next_open_text(moment, config))
    if (window == "day" and moment.time() >= hhmm(config["day_last_start"])
            and not started_today(rows, day, window)):
        # Past the last start with nothing begun: the day window is spent rather than merely late,
        # so the answer is the same all afternoon instead of offering a session too short to use.
        return Clock(None, day, "missed-start", 0, 0, None, next_open_text(moment, config))
    used, is_open, warmup_mark = usage(rows, day, window, moment, config)
    wrap = config["wrap_up_minutes"]
    if window == "day":
        warmup_max = config["warmup_max_minutes"]
        warmup_used = warmup_mark if warmup_mark is not None else min(used, warmup_max)
        in_warmup = warmup_mark is None and used < warmup_max
        limit = warmup_used + config["day_study_minutes"]
    elif window == "weekend":
        # The weekend has no window budget of its own: the day's cap below is its only limit, and
        # its warm-up is not metered separately, because every minute counts the same here.
        in_warmup = False
        limit = float("inf")
    else:
        in_warmup = False
        limit = config["evening_minutes"]
    # The day's cap is shared, so what the other windows already spent comes off this one's budget.
    spent_today = day_used(rows, day, moment, config)
    limit = min(limit, config["daily_minutes"] - (spent_today - used))
    minutes_to_close = (hard_end - moment).total_seconds() / 60
    left = min(limit - used, minutes_to_close)
    if left <= 0:
        state = "time-up"
    elif used == 0 and not is_open:
        state = "not-started"
    elif not is_open:
        state = "paused"
    elif in_warmup and left > wrap:
        state = "warm-up"
    elif left <= wrap:
        state = "wrap-up"
    else:
        state = "running"
    return Clock(window, day, state, used, limit, hard_end,
                 next_open_text(moment, config, spent_today >= config["daily_minutes"]))


def describe(clock: Clock, moment: datetime, config: dict) -> str:
    moment = local(moment)
    if clock.state == "off":
        return "CLOCK: off. The learner turned study limits off in settings.json; sessions end when they stop."
    if clock.state == "missed-start":
        return (f"CLOCK: closed. The day window had to start by {config['day_last_start']} and didn't, so it's "
                f"spent for today; the next opens at {clock.next_open}. No warm-ups, reps, or new material now; "
                "quick logistics are fine.")
    if clock.state == "closed":
        weekend = config.get("weekend")
        free = (f" Weekends run {weekend['opens_day']} {weekend['opens']} to {weekend['closes_day']} "
                f"{weekend['closes']} on the same {config['daily_minutes']} minutes a study day."
                if weekend and weekend.get("enabled", True) else "")
        return (f"CLOCK: closed. Study windows are {config['day_opens']}-{config['day_closes']} (start by "
                f"{config['day_last_start']}) and {config['evening_opens']}-{config['evening_closes']}; the next "
                f"opens at {clock.next_open}.{free} No warm-ups, reps, or new material now; quick logistics are fine.")
    left = max(0, min(clock.limit - clock.used, (clock.hard_end - moment).total_seconds() / 60))
    # The weekend runs across days, so its closing time needs the day name to mean anything.
    closes = clock.hard_end.strftime("%a %H:%M" if clock.window == "weekend" else "%H:%M")
    budget = (f"{clock.window} window, {round(clock.used)} min used, {round(left)} min left "
              f"(closes by {closes})")
    if clock.state == "time-up":
        return (f"CLOCK: time's up in the {clock.window} window. Stop: no new material or reps. Finish any "
                f"recording, tell the learner the next window opens at {clock.next_open}, and end the session.")
    if clock.state == "wrap-up":
        return f"CLOCK: {budget}. Start wrapping up now: finish the current step, recap, then run the closing steps."
    if clock.state == "warm-up":
        return (f"CLOCK: {budget}. Warm-up in progress (up to {config['warmup_max_minutes']} min); run "
                "`clock.py warmup-done` after the last warm-up rep to start the study time.")
    return f"CLOCK: {budget}."


def from_the_harness() -> bool:
    """Whether this prompt came from the harness rather than the learner. A finished background
    task re-enters the session exactly the way a message does, hook and all, so without this the
    record grows while nobody is at the desk: presence has to mean the learner typed something."""
    try:
        if sys.stdin is None or sys.stdin.isatty():
            return False
        payload = json.loads(sys.stdin.read() or "{}")
    except (ValueError, OSError, AttributeError):
        return False
    prompt = str(payload.get("prompt", ""))
    return any(mark in prompt for mark in
               ("<task-notification>", "[SYSTEM NOTIFICATION", "<system-reminder>"))


def now_from(args) -> datetime:
    if args.now is not None:
        if os.environ.get("PRACTICE_ALLOW_NOW") != "1":
            raise SystemExit("--now only works in tests (PRACTICE_ALLOW_NOW=1).")
        return local(datetime.fromisoformat(args.now))
    return local(datetime.now().replace(microsecond=0))


def row(clock: Clock, event: str, moment: datetime, minutes: int | None = None) -> dict:
    return {"study_day": clock.study_day.isoformat(), "window": clock.window, "event": event,
            "time": moment.isoformat(timespec="minutes"), "minutes": "" if minutes is None else minutes}


def report(config: dict, moment: datetime) -> str:
    moment = local(moment)
    rows = read_rows()
    days = sorted({r["study_day"] for r in rows})[-14:]
    lines = [f"study_day   warm-up  day study  evening  weekend    total (of {config['daily_minutes']})"]
    for day_text in days:
        day = date.fromisoformat(day_text)
        day_used, _, mark = usage(rows, day, "day", moment, config)
        evening, _, _ = usage(rows, day, "evening", moment, config)
        weekend, _, _ = usage(rows, day, "weekend", moment, config)
        warm = mark if mark is not None else min(day_used, config["warmup_max_minutes"])
        lines.append(f"{day_text}  {round(warm):>7}  {round(max(0, day_used - warm)):>9}  "
                     f"{round(evening):>7}  {round(weekend):>7}  {round(day_used + evening + weekend):>7}")
    return "\n".join(lines) if days else "No sessions timed yet."


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Session clock for PRACTICE/time.csv.")
    parser.add_argument("command", choices=("status", "start", "warmup-done", "end", "charge", "report",
                                            "idle", "sweep", "maintenance", "session-start", "hook-prompt"))
    parser.add_argument("--now", help="act as if it were this time (tests only)")
    parser.add_argument("--minutes", type=int, help="for charge: minutes studied while the clock was stopped")
    parser.add_argument("--off", action="store_true", help="for maintenance: go back to counting study time")
    args = parser.parse_args(argv)
    config = load_config()
    moment = now_from(args)
    clock = clock_at(moment, config)

    if args.command == "report":
        print(report(config, moment))
        return 0
    if clock.state == "off":
        # A session still gets recorded with the limits off, so that a timeout plus the documented
        # one-line escape hatch can't leave the learner locked out of their own log for good.
        if args.command == "session-start":
            write_row({"study_day": clock.study_day.isoformat(), "window": "-", "event": "session",
                       "time": moment.isoformat(timespec="minutes"), "minutes": ""})
        print(describe(clock, moment, config))
        return 0
    if args.command == "session-start":
        # A new session clears the lock, and clears it only after any stale segment is closed.
        # It says nothing unless it closed something, because this runs on every session opening.
        closed, _ = sweep(moment, config)
        if closed:
            print("Closed the " + ", and the ".join(closed) + ", back at the last message.")
        write_row({"study_day": clock.study_day.isoformat(), "window": clock.window or "-",
                   "event": "session", "time": moment.isoformat(timespec="minutes"), "minutes": ""})
        return 0
    if args.command in ("idle", "sweep"):
        if args.command == "idle":
            rows = read_rows()
            pairs = [(clock.study_day, clock.window)] if clock.window else []
            quiet = None
            for day, window in pairs:
                if not usage(rows, day, window, moment, config)[1]:
                    continue
                seen = last_mark(rows, day, window)
                if seen is not None:
                    quiet = (moment - seen).total_seconds() / 60
            print(-1 if quiet is None else round(quiet))
            return 0
        closed, quiet = sweep(moment, config)
        if closed:
            print("Closed the " + ", and the ".join(closed) + ", back at the last message.")
        elif quiet is None:
            print("Nothing open to close.")
        else:
            print(f"Still active: {round(quiet)} min since the last message.")
        return 0

    if args.command == "maintenance":
        rows = read_rows()
        if args.off:
            write_row({"study_day": clock.study_day.isoformat(), "window": "-", "event": "maintenance-off",
                       "time": moment.isoformat(timespec="minutes"), "minutes": ""})
            print("Maintenance over; the clock counts study time again.")
            return 0
        if not maintenance_on(rows):
            # Close what is open first, so the minutes already spent studying stay counted and only
            # the repair work that follows goes unmetered.
            if clock.window and clock.state in ("warm-up", "running", "wrap-up"):
                write_row(row(clock, "end", moment))
            write_row({"study_day": clock.study_day.isoformat(), "window": "-", "event": "maintenance-on",
                       "time": moment.isoformat(timespec="minutes"), "minutes": ""})
        print("Maintenance session: no minutes are counted until it ends or a new session starts.")
        return 0
    if maintenance_on(read_rows()) and args.command in ("start", "warmup-done", "charge", "hook-prompt"):
        print("CLOCK: maintenance session, minutes not counted.")
        return 0
    if args.command == "hook-prompt" and from_the_harness():
        # Not the learner: report where the clock stands, but leave no mark and open nothing.
        print(describe(clock, moment, config))
        return 0
    if args.command in ("start", "hook-prompt") and clock.window:
        # This is what makes the timeout deterministic: it runs on every single message, so a
        # message arriving after a long quiet stretch times the session out here whether or not a
        # watcher is alive. It sweeps every open segment, not only one in the window the message
        # landed in, because an absence long enough to matter usually crosses a window or the 04:00
        # rollover, and the segment left open then belongs to a pair this moment cannot see.
        if sweep(moment, config)[0]:
            clock = clock_at(moment, config)
    shut = locked(read_rows())
    if shut is not None and args.command in ("start", "warmup-done", "charge", "hook-prompt"):
        # Nothing is recorded on a session that timed out, so a message cannot quietly resume it.
        print(LOCK_MESSAGE.format(when=shut.strftime("%H:%M")))
        return 0
    if args.command in ("start", "hook-prompt") and clock.state in ("not-started", "paused"):
        write_row(row(clock, "start", moment))
        clock = clock_at(moment, config)
    elif args.command == "hook-prompt" and clock.window and clock.state in ("warm-up", "running", "wrap-up"):
        # This message is proof of presence; one mark every few minutes is enough to bound the tail.
        seen = last_mark(read_rows(), clock.study_day, clock.window)
        if seen is None or moment - seen >= timedelta(minutes=config["stamp_every_minutes"]):
            write_row(row(clock, "seen", moment))
            clock = clock_at(moment, config)
    elif args.command == "start" and clock.state in ("closed", "missed-start"):
        print(describe(clock, moment, config))
        return 1
    if clock.state == "time-up":
        # Close an open segment at the moment the budget ran out, so the CSV shows real minutes.
        # The minutes stop at the last sign of life plus the grace, so the closing row counts back
        # from there rather than from now, which may be long after the learner left.
        rows = read_rows()
        used, is_open, _ = usage(rows, clock.study_day, clock.window, moment, config)
        if is_open:
            seen = last_mark(rows, clock.study_day, clock.window) or moment
            counted_to = min(moment, seen + timedelta(minutes=config["idle_grace_minutes"]))
            began = open_since(rows, clock.study_day, clock.window) or counted_to
            overrun = max(0.0, used - clock.limit)
            # Charged minutes can be larger than the segment itself, so the count-back is floored
            # at the start: a closing row before its own opening row would be a lie about when.
            stop_at = min(max(counted_to - timedelta(minutes=overrun), began), clock.hard_end)
            write_row(row(clock, "time-up", stop_at.replace(second=0)))
    if args.command == "warmup-done":
        # Recorded in any window, because it is what says the day's warm-up happened. Only the day
        # window meters it separately; elsewhere it sits inside the day's one budget.
        if any(r["event"] == "warmup-done" and r["study_day"] == clock.study_day.isoformat()
               for r in read_rows()):
            print("The warm-up is already marked done today.")
            return 1
        write_row(row(clock, "warmup-done", moment))
        clock = clock_at(moment, config)
    if args.command == "charge":
        # Study done while the clock was stopped still counts, because the limit is on study time,
        # not on time the clock happened to be running.
        if clock.window is None or not args.minutes or args.minutes <= 0:
            print("charge needs an open window and --minutes above 0.")
            return 1
        write_row(row(clock, "charge", moment, args.minutes))
        clock = clock_at(moment, config)
    if args.command == "end":
        # The SessionEnd hook fires this when Claude Code quits, which can be hours after the last
        # message, so it closes at the last mark like every other path. A gap long enough to mean
        # the learner left closes as a timeout, which locks, rather than as an ordinary end.
        rows = read_rows()
        _, is_open, _ = (usage(rows, clock.study_day, clock.window, moment, config) if clock.window else (0, False, None))
        if clock.window and is_open:
            seen = last_mark(rows, clock.study_day, clock.window) or moment
            if moment - seen >= timedelta(minutes=config["away_after_minutes"]):
                # Nobody was here: close back at the last message, and lock, as a timeout does.
                write_row(row(clock, "timeout", min(moment, seen + timedelta(minutes=config["idle_grace_minutes"]))))
            else:
                # A goodbye said while the learner is still at the desk closes where they said it.
                write_row(row(clock, "end", moment))
            clock = clock_at(moment, config)
    print(describe(clock, moment, config))
    return 0


if __name__ == "__main__":
    sys.exit(main())
