# Data-Analysis-4th-Edition
My Analysis and ML journey using Avinash Navlani and Cornellius Yudha ijaya's book. 

## Setup on a new machine

This repo works the same on Windows, macOS, and Linux. Set it up with Claude Code, or by hand.

### With Claude Code

| Step | Do this | What it does |
|---|---|---|
| 1 | Install [Git](https://git-scm.com/downloads) and [Claude Code](https://code.claude.com/docs/en/setup). | Git copies the repo to this computer, and Claude Code runs the setup. |
| 2 | `git clone https://github.com/ChandlerM2/Data-Analysis-4th-Edition.git` | Downloads the repo into a `Data-Analysis-4th-Edition` folder. |
| 3 | `cd Data-Analysis-4th-Edition`, then `claude` | Starts Claude Code inside the repo folder. |
| 4 | Say **"set me up"**, or run `/setup`. | Claude runs the setup skill in `.claude/skills/setup/`. It checks the computer, fixes what it can ([uv](https://docs.astral.sh/uv/), Python, packages, the Git author email, VS Code extensions, and the writing guide in `~/.claude/rules/`), asks before deleting anything, and lists what's left for you, like adding the book PDF. |

Running the skill again on a computer that's already set up changes nothing, so it's also the
way to update an older clone.

### By hand

| Step | Do this | What it does |
|---|---|---|
| 1 | Install [uv](https://docs.astral.sh/uv/) and clone the repo. | uv installs Python and the project's packages. |
| 2 | `uv sync`, from the repo root | Reads `uv.lock`, installs the pinned Python if it's missing, and builds `.venv` with the exact package versions recorded there. |
| 3 | `git config --global user.email "<your no-reply address>"` | Commits carry your GitHub no-reply address, listed on GitHub's Emails settings page, so your personal email stays out of public commits. |
| 4 | In VS Code, install the Python, Jupyter, and ty extensions, open a notebook, and pick the `.venv` kernel. | Notebooks run in the project environment. To use JupyterLab instead, run `uv run jupyter lab`. |
| 5 | Optional: add the book PDF (see `book/README.md`), and copy `.claude/skills/setup/files/writing-for-future-readers.md` into `~/.claude/rules/`. | The PDF lets practice reps draw on the book's own pages, and the writing guide shapes how Claude writes docs and code comments on this computer. |

To check a setup at any time, run
`uv run --no-project python .claude/skills/setup/scripts/check_setup.py`.

## PRACTICE: the teaching harness

Reading a chapter builds understanding, but not the ability to do the work. `PRACTICE/` holds a
harness that Claude Code runs every session so practice happens without planning it.

- **Warm-up (5 to 10 minutes).** Every session opens with a few small reps, one at a time:
  predict what a cell prints, pick the right function for a job, find a bug, reorder shuffled
  lines, or break a request into steps. Answers are a letter, a line, or a short cell.
- **Study.** Read and type the book's code. Before running a new cell, predict what it prints.
  When an idea takes a while to click, Claude works it with a worked example and a puzzle.
  When you stop, Claude records where, the first step for next time, and the one idea you'd most
  regret forgetting.
- **Weekly ticket (about 30 minutes).** A manager at a made-up company sends a voice memo with a
  job request that mixes several ideas. Plan it in three steps, then build it with docs open.

**Study hours are fixed.** Mornings from 04:00 to 08:00 get the warm-up plus 90 minutes of study.
08:00 to 19:00 is closed. Evenings from 19:00 get one hour. A hook checks the clock on every
message, Claude starts wrapping up 15 minutes before time runs out, and `PRACTICE/time.csv` records
the minutes. The windows and budgets are in `PRACTICE/settings.json`, where `"enabled": false`
under `clock` turns the limits off and `true` turns them back on.

Each tracked idea (a skill) climbs seven layers. Help fades from a worked example to working alone,
and the wait before the next rep grows from a day to a month. A wrong answer drops it back a layer
so help returns. Coins for showing up, practicing what's due, and fixing mistakes go toward rewards
you price in dollars, capped at a monthly budget you set.

Say **"warm up"** to start, **"done"** to close a study session, **"dispute 3"** to have a graded
rep rechecked, and **"I already know this one"** to test out of a skill. The rules Claude follows
are in `PRACTICE/CLAUDE.md`. `PRACTICE/log.jsonl` is the record, written only by
`PRACTICE/tools/harness.py`, and `PRACTICE/tips.md` collects the rules of thumb from past sessions.
After changing a tool, run `uv run --no-project python PRACTICE/tools/tests/run.py`.
