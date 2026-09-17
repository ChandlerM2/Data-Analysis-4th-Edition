"""Session clock for the study repo. Study happens in two windows a day, each with a time budget:

    day      08:00 to 18:15   start by 16:30: a warm-up of up to 15 minutes, then 90 of study
    closed   18:15 to 19:00   no warm-ups, reps, or new material
    evening  19:00 to 23:00   up to 60 minutes in total

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

    status       where the clock stands now
    start        open a timed segment (the prompt hook does this on the first message in a window)
    warmup-done  the day window warm-up is over: start the 90-minute study budget
    end          close the open segment when the learner stops early or steps away
    charge       add minutes the learner studied while the clock was stopped (--minutes N)
    report       minutes used per window for the last 14 days
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
from datetime import date, datetime, timedelta
from pathlib import Path

PRACTICE_DIR = Path(__file__).resolve().parents[1]
TIME_FILE = PRACTICE_DIR / "time.csv"
SETTINGS_FILE = PRACTICE_DIR / "settings.json"
COLUMNS = ["study_day", "window", "event", "time", "minutes"]
CLOCK_KEYS = ("day_opens", "day_last_start", "day_closes", "evening_opens", "evening_closes",
              "warmup_max_minutes", "day_study_minutes", "evening_minutes", "wrap_up_minutes")
# The window times have to run in this order for a day to make sense, and load_config checks it.
ORDERED_TIMES = ("day_opens", "day_last_start", "day_closes", "evening_opens", "evening_closes")


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
    return config


def hhmm(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time()


def study_day(moment: datetime, config: dict) -> date:
    return (moment - timedelta(hours=config["day_starts_hour"])).date()


def window_at(moment: datetime, config: dict) -> tuple[str | None, datetime | None]:
    """The window these times put this moment in, and when that window closes. The day window's last
    start is not applied here, because a session already under way runs to the closing time: only
    clock_at, which reads the rows, can tell a missed start from a session still going."""
    now = moment.time()
    day = moment.date()
    for window in ("day", "evening"):
        if hhmm(config[f"{window}_opens"]) <= now < hhmm(config[f"{window}_closes"]):
            return window, datetime.combine(day, hhmm(config[f"{window}_closes"]))
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
            if row.get("window") in ("day", "evening") and row.get("event") in ("start", "end", "time-up", "warmup-done", "charge"):
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
    """When this window shuts on this study day. No window crosses midnight, so a study day's date
    is the calendar date of every session the clock times."""
    return datetime.combine(day, hhmm(config[f"{window}_closes"]))


def usage(rows: list[dict], day: date, window: str, now: datetime, config: dict) -> tuple[float, bool, float | None]:
    """Minutes used in this window, whether a segment is open, and the minute mark when the
    warm-up was marked done (None if it wasn't). A segment left open counts only until the window
    closes, so a session nobody ended can't swallow the rest of the day."""
    now = min(now, window_end(day, window, config))
    used, open_start, warmup_mark = 0.0, None, None
    for row in rows:
        if row["study_day"] != day.isoformat() or row["window"] != window:
            continue
        at = datetime.fromisoformat(row["time"])
        if row["event"] == "start" and open_start is None:
            open_start = at
        elif row["event"] in ("end", "time-up") and open_start is not None:
            used += (at - open_start).total_seconds() / 60
            open_start = None
        elif row["event"] == "charge":
            used += int(row["minutes"])
        elif row["event"] == "warmup-done" and warmup_mark is None:
            warmup_mark = used + ((at - open_start).total_seconds() / 60 if open_start else 0)
    if open_start is not None:
        used += max(0.0, (now - open_start).total_seconds() / 60)
    return used, open_start is not None, warmup_mark


def started_today(rows: list[dict], day: date, window: str) -> bool:
    """Whether this window was opened at all on this study day. A charge counts as an opening,
    because minutes studied while the clock was stopped are still a session that began."""
    return any(row["study_day"] == day.isoformat() and row["window"] == window
               and row["event"] in ("start", "charge") for row in rows)


def next_open_text(moment: datetime, config: dict) -> str:
    now = moment.time()
    if now < hhmm(config["day_opens"]):
        return config["day_opens"]
    if now < hhmm(config["evening_opens"]):
        return f"{config['evening_opens']} tonight"
    return f"{config['day_opens']} tomorrow"


def clock_at(moment: datetime, config: dict, rows: list[dict] | None = None) -> Clock:
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
    else:
        in_warmup = False
        limit = config["evening_minutes"]
    minutes_to_close = (hard_end - moment).total_seconds() / 60
    left = min(limit - used, minutes_to_close)
    if left <= 0:
        state = "time-up"
    elif used == 0 and not is_open:
        state = "not-started"
    elif not is_open:
        state = "paused"
    elif in_warmup:
        state = "warm-up"
    elif left <= wrap:
        state = "wrap-up"
    else:
        state = "running"
    return Clock(window, day, state, used, limit, hard_end, next_open_text(moment, config))


def describe(clock: Clock, moment: datetime, config: dict) -> str:
    if clock.state == "off":
        return "CLOCK: off. The learner turned study limits off in settings.json; sessions end when they stop."
    if clock.state == "missed-start":
        return (f"CLOCK: closed. The day window had to start by {config['day_last_start']} and didn't, so it's "
                f"spent for today; the next opens at {clock.next_open}. No warm-ups, reps, or new material now; "
                "quick logistics are fine.")
    if clock.state == "closed":
        return (f"CLOCK: closed. Study windows are {config['day_opens']}-{config['day_closes']} (start by "
                f"{config['day_last_start']}) and {config['evening_opens']}-{config['evening_closes']}; the next "
                f"opens at {clock.next_open}. No warm-ups, reps, or new material now; quick logistics are fine.")
    left = max(0, min(clock.limit - clock.used, (clock.hard_end - moment).total_seconds() / 60))
    budget = (f"{clock.window} window, {round(clock.used)} min used, {round(left)} min left "
              f"(closes by {clock.hard_end.strftime('%H:%M')})")
    if clock.state == "time-up":
        return (f"CLOCK: time's up in the {clock.window} window. Stop: no new material or reps. Finish any "
                f"recording, tell the learner the next window opens at {clock.next_open}, and end the session.")
    if clock.state == "wrap-up":
        return f"CLOCK: {budget}. Start wrapping up now: finish the current step, recap, then run the closing steps."
    if clock.state == "warm-up":
        return (f"CLOCK: {budget}. Warm-up in progress (up to {config['warmup_max_minutes']} min); run "
                "`clock.py warmup-done` after the last warm-up rep to start the study time.")
    return f"CLOCK: {budget}."


def now_from(args) -> datetime:
    if args.now is not None:
        if os.environ.get("PRACTICE_ALLOW_NOW") != "1":
            raise SystemExit("--now only works in tests (PRACTICE_ALLOW_NOW=1).")
        return datetime.fromisoformat(args.now)
    return datetime.now().replace(microsecond=0)


def row(clock: Clock, event: str, moment: datetime, minutes: int | None = None) -> dict:
    return {"study_day": clock.study_day.isoformat(), "window": clock.window, "event": event,
            "time": moment.isoformat(timespec="minutes"), "minutes": "" if minutes is None else minutes}


def report(config: dict, moment: datetime) -> str:
    rows = read_rows()
    days = sorted({r["study_day"] for r in rows})[-14:]
    lines = ["study_day   warm-up  day study  evening"]
    for day_text in days:
        day = date.fromisoformat(day_text)
        day_used, _, mark = usage(rows, day, "day", moment, config)
        evening, _, _ = usage(rows, day, "evening", moment, config)
        warm = mark if mark is not None else min(day_used, config["warmup_max_minutes"])
        lines.append(f"{day_text}  {round(warm):>7}  {round(max(0, day_used - warm)):>9}  {round(evening):>7}")
    return "\n".join(lines) if days else "No sessions timed yet."


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Session clock for PRACTICE/time.csv.")
    parser.add_argument("command", choices=("status", "start", "warmup-done", "end", "charge", "report", "hook-prompt"))
    parser.add_argument("--now", help="act as if it were this time (tests only)")
    parser.add_argument("--minutes", type=int, help="for charge: minutes studied while the clock was stopped")
    args = parser.parse_args(argv)
    config = load_config()
    moment = now_from(args)
    clock = clock_at(moment, config)

    if args.command == "report":
        print(report(config, moment))
        return 0
    if clock.state == "off":
        print(describe(clock, moment, config))
        return 0
    if args.command in ("start", "hook-prompt") and clock.state in ("not-started", "paused"):
        write_row(row(clock, "start", moment))
        clock = clock_at(moment, config)
    elif args.command == "start" and clock.state in ("closed", "missed-start"):
        print(describe(clock, moment, config))
        return 1
    if clock.state == "time-up":
        # Close an open segment at the moment the budget ran out, so the CSV shows real minutes.
        used, is_open, _ = usage(read_rows(), clock.study_day, clock.window, moment, config)
        if is_open:
            overrun = max(0.0, used - clock.limit)
            stop_at = min(moment - timedelta(minutes=overrun), clock.hard_end)
            write_row(row(clock, "time-up", stop_at.replace(second=0)))
    if args.command == "warmup-done":
        if clock.window != "day":
            print("Only the day window has a separate warm-up.")
            return 1
        if any(r["event"] == "warmup-done" and r["study_day"] == clock.study_day.isoformat() and r["window"] == "day"
               for r in read_rows()):
            print("The warm-up is already marked done for today's day window.")
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
        _, is_open, _ = (usage(read_rows(), clock.study_day, clock.window, moment, config) if clock.window else (0, False, None))
        if clock.window and is_open:
            write_row(row(clock, "end", moment))
            clock = clock_at(moment, config)
    print(describe(clock, moment, config))
    return 0


if __name__ == "__main__":
    sys.exit(main())
