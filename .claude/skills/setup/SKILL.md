---
name: setup
description: Set up this computer for the Data-Analysis-4th-Edition repo, or check an existing setup. Use when the learner says "set me up", "set up this computer", or "setup", or has just cloned the repo on a new machine.
---

# Set up this computer

Setup is logistics, not practice, so run every command yourself instead of asking the learner
to type them. The steps are safe on a computer in any state: a fresh clone, a clone that still
has history GitHub no longer has, or a finished setup, where the check reports nothing to fix.

Ask before two kinds of action, because both can't be undone from here: deleting anything
(uncommitted changes, local commits, branches) and overwriting a file that differs from the
repo's copy. Everything else, run without asking.

## 1. Make sure uv exists

The check script runs through uv, so run `uv --version` first. If uv is missing, install it
with Astral's official installer:

- Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
- macOS and Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`

The installer adds uv to PATH for new shells only. If `uv --version` still fails, call uv by the
full path the installer printed.

## 2. Run the check

From the repo root:

```
uv run --no-project python .claude/skills/setup/scripts/check_setup.py
```

Each line is `[ok]` (nothing to do), `[fix]` (yours to fix), or `[info]` (the learner's to
handle). The script prints checks in the order to fix them.

## 3. Fix each `[fix]` line, top to bottom

- **git email:** `git config --global user.email <address>`. When the line suggests the address
  on GitHub's newest commit, confirm with the learner that it's theirs before setting it,
  because every commit from this computer will carry it.
- **git history, no shared commits with GitHub:** GitHub's history was replaced and this clone
  still holds the old one. Show the learner the uncommitted changes (`git status`) and the
  local-only commits the line lists, and ask whether any are work to keep. Copy anything they
  keep outside the repo, then run `git reset --hard origin/main`. Never run `git pull` in this
  state: it can merge the old history back in, and a later push would put it on GitHub again.
- **git history, behind GitHub:** `git pull --ff-only`.
- **branch holding old history:** show the learner what the line lists, and after they confirm,
  `git branch -D <branch>`. Never push these branches, for the same reason as above.
- **environment:** `uv sync`. It installs the Python version in `.python-version` if needed and
  builds `.venv` from `uv.lock`. When it creates or rebuilds `.venv`, tell the learner in the
  report to run **Developer: Reload Window** in VS Code before choosing a kernel, because the
  Python and Jupyter extensions keep the environment list they built before `.venv` existed, and
  the kernel picker shows `.venv` for an instant and then drops it until the window reloads.
- **practice history:** this computer has never run the repo before, and `PRACTICE/log.jsonl` and
  `PRACTICE/time.csv` already hold practice. Both are tracked, so a clone carries the skills,
  balance, and sessions of whoever committed them. Ask in one line, naming the counts and the
  address the check gives: "PRACTICE has 26 log events (9 skills) and 2 sessions from <address>.
  Yours from another computer, or are you starting your own?"
  - **Theirs:** leave both files alone. The harness replays the log for every layer and due day,
    and a warm-up done on one computer is meant to count on the other once it pushes and this one
    pulls.
  - **Starting their own:** `git rm PRACTICE/log.jsonl PRACTICE/time.csv`. Both are tracked on
    purpose; the harness reads a missing log as no practice yet, and each file is recreated on
    first use, so they begin at zero skills and a zero balance with nothing inherited. Say that
    this removes nothing from the repo's history: the original record stays in git and on GitHub,
    so they can still read every skill and session it holds.
  - **Keeping it to work through:** also fine, and no command is needed. Someone who cloned this to
    run the existing skills and reps rather than build their own record keeps both files, and their
    reps append to that history. Say once that their own timings will sit alongside the original
    learner's, because the log is one record and does not separate people.

  Either way the question is asked once, since `uv sync` settles it for this computer.
- **writing guide, not installed:** copy `.claude/skills/setup/files/writing-for-future-readers.md`
  to `~/.claude/rules/`, creating the folder if needed. Claude Code loads that folder in every
  project on the computer.
- **writing guide, differs:** show the learner the differences and ask which copy wins, since
  either side may hold edits. When the home copy wins, copy it into the repo too, so the next
  computer gets the same guide.
- **VS Code:** `code --install-extension <id>` for each missing extension.
- **uv:** go back to step 1.

## 4. Check again and report

Rerun the check until no `[fix]` lines remain. Then tell the learner what changed, and list each
`[info]` line as something left for them, such as adding the book PDF or installing Java before
the PySpark chapter. If a fix fails, stop, show the error, and say which lines are still open.
