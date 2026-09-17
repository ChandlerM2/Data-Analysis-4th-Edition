"""Build a practice notebook from a short text spec, so every session notebook is valid JSON
without hand-writing notebook format.

    uv run --no-project python PRACTICE/tools/notebook.py SPEC.txt PRACTICE/sessions/2026-09-18-0805.ipynb

The spec is plain text split into cells by marker lines:

    %% md               a markdown cell
    %% code             a code cell
    %% parsons SEED     a code cell holding the lines below it in shuffled order
    %% audio FILE       a code cell that shows a player for FILE (path relative to the notebook)

Parsons lines are shuffled with the seed, so rebuilding the notebook gives the same order, and
the shuffle never returns the original order. Put any line that doesn't belong among the lines;
nothing marks it. Refuses to overwrite an existing notebook, because past attempts are the record.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

PARSONS_HEADER = ("# Put these lines in order: Alt+Up and Alt+Down move the line the cursor is on.\n"
                  "# One line doesn't belong. Delete it, then run the cell.\n")


def cell(kind: str, text: str) -> dict:
    lines = text.strip("\n").splitlines(keepends=True)
    base = {"cell_type": kind, "metadata": {}, "source": lines}
    if kind == "code":
        base.update(execution_count=None, outputs=[])
    return base


def shuffled(lines: list[str], seed: int) -> list[str]:
    if len(set(lines)) < 2:
        return lines
    rng = random.Random(seed)
    order = lines[:]
    while order == lines:
        rng.shuffle(order)
    return order


def build(spec: str) -> list[dict]:
    cells, kind, arg, body = [], None, None, []

    def flush() -> None:
        if kind is None:
            return
        text = "\n".join(body)
        if kind == "md":
            cells.append(cell("markdown", text))
        elif kind == "code":
            cells.append(cell("code", text))
        elif kind == "parsons":
            lines = [line for line in body if line.strip()]
            cells.append(cell("code", PARSONS_HEADER + "\n".join(shuffled(lines, int(arg)))))
        elif kind == "audio":
            cells.append(cell("code", f"from IPython.display import Audio\nAudio({arg!r})"))

    for line in spec.splitlines():
        if line.startswith("%% "):
            flush()
            parts = line[3:].split(maxsplit=1)
            kind, arg, body = parts[0], (parts[1].strip() if len(parts) > 1 else None), []
            if kind not in ("md", "code", "parsons", "audio"):
                raise SystemExit(f"Unknown cell marker: {line}")
            if kind in ("parsons", "audio") and not arg:
                raise SystemExit(f"{kind} needs an argument: {line}")
        else:
            body.append(line)
    flush()
    return cells


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 1
    spec_path, out_path = Path(argv[0]), Path(argv[1])
    if out_path.exists():
        print(f"{out_path} already exists. Pick a new name; past notebooks are never overwritten.")
        return 1
    notebook = {
        "cells": build(spec_path.read_text(encoding="utf-8")),
        "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                     "language_info": {"name": "python"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    for number, item in enumerate(notebook["cells"]):
        item["id"] = f"cell-{number}"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(notebook, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"Wrote {out_path} with {len(notebook['cells'])} cells.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
