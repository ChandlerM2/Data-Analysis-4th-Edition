"""Background bookkeeping for QUIZ/chapters.json. Claude runs this; the learner never has to.

chapters.json lists the book's chapters and, under each, the sections the learner has told
Claude they finished, with dates and a Leitner box that decides when a section comes back.

    validate  check chapters.json is well-formed
    review    pick sections for an "across everything" session, most overdue first
    record    save how a section went: correct moves it up a box, wrong sends it to box 1
    hook      entry point for the Claude Code PostToolUse hook

Run from the repo root:
    uv run --no-project python QUIZ/tools/quiz.py <command> [options]

Standard library only, so nothing needs installing and it runs the same on Windows,
macOS, and Linux.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

CHAPTERS_FILE = Path(__file__).resolve().parents[1] / "chapters.json"

# Leitner boxes: days a section waits after practice before it is due again.
INTERVAL_DAYS = {1: 1, 2: 3, 3: 7, 4: 14, 5: 30}
RESULTS = ("correct", "wrong")
CHAPTER_FIELDS = ("chapter", "title", "sections")
SECTION_FIELDS = ("section", "date_added", "date_last_practiced", "times_practiced", "last_result", "box")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def normalize(text: str) -> str:
    return " ".join(text.split()).casefold()


def is_whole_number(value, minimum: int) -> bool:
    # bool is a subclass of int in Python, so True would otherwise pass as 1.
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def save(path: Path, data: dict) -> None:
    # newline="\n" keeps line endings identical on Windows, macOS, and Linux.
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def parse_date(value, label: str, errors: list[str]) -> date | None:
    if not isinstance(value, str) or not DATE_PATTERN.match(value):
        errors.append(f"{label}: {value!r} is not a YYYY-MM-DD date")
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.append(f"{label}: {value!r} is not a real calendar date")
        return None


def check_fields(obj, fields, where: str, errors: list[str]) -> bool:
    if not isinstance(obj, dict):
        errors.append(f"{where}: must be an object")
        return False
    unknown = sorted(set(obj) - set(fields))
    missing = [f for f in fields if f not in obj]
    if unknown:
        errors.append(f"{where}: unknown field(s) {', '.join(unknown)} (typo?)")
    if missing:
        errors.append(f"{where}: missing field(s) {', '.join(missing)}")
    return not missing


def validate(data, today: date) -> list[str]:
    """Return every formatting rule chapters.json breaks. Empty list means it is fine."""
    if not isinstance(data, dict) or not isinstance(data.get("chapters"), list):
        return ['top level must be an object holding a "chapters" list']
    errors: list[str] = []
    seen_chapters = set()
    for i, chapter in enumerate(data["chapters"]):
        where = f"chapters[{i}]"
        if not check_fields(chapter, CHAPTER_FIELDS, where, errors):
            continue
        number = chapter["chapter"]
        if not is_whole_number(number, 1):
            errors.append(f"{where}: chapter must be a whole number of 1 or more")
        elif number in seen_chapters:
            errors.append(f"{where}: chapter {number} is listed twice")
        seen_chapters.add(number)
        if not isinstance(chapter["title"], str) or not chapter["title"].strip():
            errors.append(f"{where}: title must be non-empty text")
        if not isinstance(chapter["sections"], list):
            errors.append(f"{where}: sections must be a list")
            continue

        seen_sections = set()
        for j, entry in enumerate(chapter["sections"]):
            spot = f"chapter {number} sections[{j}]"
            if not check_fields(entry, SECTION_FIELDS, spot, errors):
                continue
            name = entry["section"]
            if not isinstance(name, str) or not name.strip():
                errors.append(f"{spot}: section must be non-empty text")
            else:
                spot = f"chapter {number} {name!r}"
                if normalize(name) in seen_sections:
                    errors.append(f"{spot}: listed twice in this chapter")
                seen_sections.add(normalize(name))

            added = parse_date(entry["date_added"], f"{spot}: date_added", errors)
            if added and added > today:
                errors.append(f"{spot}: date_added {added} is in the future")
            times, last, result, box = (entry["times_practiced"], entry["date_last_practiced"],
                                        entry["last_result"], entry["box"])
            if isinstance(box, bool) or box not in INTERVAL_DAYS:
                errors.append(f"{spot}: box must be one of {sorted(INTERVAL_DAYS)}")
            if not is_whole_number(times, 0):
                errors.append(f"{spot}: times_practiced must be a whole number of 0 or more")
            elif times == 0:
                if last is not None or result is not None or box != 1:
                    errors.append(f"{spot}: never practiced, so date_last_practiced and last_result "
                                  "must be null and box must be 1")
            else:
                practiced = parse_date(last, f"{spot}: date_last_practiced", errors)
                if practiced and added and practiced < added:
                    errors.append(f"{spot}: practiced {practiced} before it was added {added}")
                if practiced and practiced > today:
                    errors.append(f"{spot}: date_last_practiced {practiced} is in the future")
                if result not in RESULTS:
                    errors.append(f"{spot}: last_result must be {' or '.join(RESULTS)}")
    return errors


def load_checked(path: Path, today: date) -> tuple[dict | None, list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, [f"{path} does not exist"]
    except json.JSONDecodeError as exc:
        return None, [f"not valid JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}"]
    return data, validate(data, today)


def all_sections(data: dict):
    """Yield (chapter number, section entry) in file order, which is reading order."""
    for chapter in data["chapters"]:
        for entry in chapter["sections"]:
            yield chapter["chapter"], entry


def due_date(entry: dict) -> date:
    """A never-practiced section is due from the day it was added."""
    if entry["date_last_practiced"] is None:
        return date.fromisoformat(entry["date_added"])
    return date.fromisoformat(entry["date_last_practiced"]) + timedelta(days=INTERVAL_DAYS[entry["box"]])


def run_hook() -> int:
    """PostToolUse hook. Exit 0 = fine or not our file. Exit 2 = chapters.json is broken
    (stderr goes back to Claude). Exit 1 = input unreadable (non-blocking notice)."""
    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        print(f"quiz.py hook could not read its input ({exc}); chapters.json was not checked.", file=sys.stderr)
        return 1
    file_path = str((payload.get("tool_input") or {}).get("file_path", ""))
    if not file_path.replace("\\", "/").casefold().endswith("quiz/chapters.json"):
        return 0
    _, errors = load_checked(Path(file_path), date.today())
    if not errors:
        return 0
    print("QUIZ/chapters.json is malformed after this edit:", file=sys.stderr)
    for error in errors:
        print(f"  - {error}", file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--file", type=Path, default=CHAPTERS_FILE)
    common.add_argument("--as-of", type=date.fromisoformat, default=date.today(),
                        help="treat this YYYY-MM-DD date as today (for testing)")
    parser = argparse.ArgumentParser(description="Bookkeeping for QUIZ/chapters.json.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", parents=[common])
    review_cmd = commands.add_parser("review", parents=[common])
    review_cmd.add_argument("--count", type=int, default=5)
    record_cmd = commands.add_parser("record", parents=[common])
    record_cmd.add_argument("--chapter", type=int, required=True)
    record_cmd.add_argument("--section", required=True)
    record_cmd.add_argument("--result", choices=RESULTS, required=True)
    commands.add_parser("hook")
    args = parser.parse_args(argv)

    if args.command == "hook":
        return run_hook()

    data, errors = load_checked(args.file, args.as_of)
    if errors:
        print("chapters.json is malformed, so nothing was done:")
        for error in errors:
            print(f"  - {error}")
        return 1

    if args.command == "validate":
        count = sum(1 for _ in all_sections(data))
        print(f"OK: {len(data['chapters'])} chapters, {count} finished sections.")
        return 0

    if args.command == "review":
        # Stable sort: ties keep reading order.
        ranked = sorted(all_sections(data), key=lambda pair: (due_date(pair[1]), pair[1]["box"]))
        chosen = ranked[: args.count]
        print(f"review as of {args.as_of}: {len(chosen)} of {len(ranked)} sections")
        for number, entry in chosen:
            due = due_date(entry)
            status = ("never practiced" if entry["times_practiced"] == 0
                      else f"due {due}" if due <= args.as_of else f"early, due {due}")
            last = f"last {entry['last_result']} on {entry['date_last_practiced']}" if entry["last_result"] else ""
            print(f"  ch {number:>2} | box {entry['box']} | {status:<21} | {entry['section']}  {last}")
        return 0

    # record
    entry = next((e for n, e in all_sections(data)
                  if n == args.chapter and normalize(e["section"]) == normalize(args.section)), None)
    if entry is None:
        print(f"chapter {args.chapter} {args.section!r} is not in chapters.json.")
        return 1
    today = args.as_of.isoformat()
    if entry["date_last_practiced"] == today:
        print(f"chapter {args.chapter} {entry['section']!r} is already recorded for {today}. "
              "Record each section once per session.")
        return 1
    entry["times_practiced"] += 1
    entry["date_last_practiced"] = today
    entry["last_result"] = args.result
    entry["box"] = min(entry["box"] + 1, max(INTERVAL_DAYS)) if args.result == "correct" else 1
    save(args.file, data)
    print(f"Recorded chapter {args.chapter} {entry['section']!r}: {args.result}, now box {entry['box']}, "
          f"due {due_date(entry)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
