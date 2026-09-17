"""Check whether this computer is set up for the repo. The setup skill runs this; the learner never has to.

Each check prints one line:

    [ok]    nothing to do
    [fix]   the setup skill fixes this; the line says how
    [info]  the learner has to handle this; the line says what to do

Run from the repo root:
    uv run --no-project python .claude/skills/setup/scripts/check_setup.py

Exits 0 when nothing needs fixing and 1 otherwise. Standard library only, so it runs before the
project environment exists, the same way on Windows, macOS, and Linux.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
GUIDE_NAME = "writing-for-future-readers.md"
GUIDE_SOURCE = Path(__file__).resolve().parents[1] / "files" / GUIDE_NAME
GUIDE_TARGET = Path.home() / ".claude" / "rules" / GUIDE_NAME
BOOK_PDF = REPO / "book" / "Python Data Analysis - Fourth Edition.pdf"
VSCODE_EXTENSIONS = ("ms-python.python", "ms-toolsai.jupyter", "astral-sh.ty")
NOREPLY_SUFFIX = "@users.noreply.github.com"

Report = list[tuple[str, str, str]]


def run(*args: str, timeout: int = 60) -> subprocess.CompletedProcess[str] | None:
    """Run a command in the repo root. None means the program isn't installed or didn't finish."""
    program = shutil.which(args[0])
    if program is None:
        return None
    try:
        # The full path from shutil.which lets Windows run .cmd launchers such as VS Code's `code`.
        return subprocess.run(
            [program, *args[1:]], cwd=REPO, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def succeeded(result: subprocess.CompletedProcess[str] | None) -> bool:
    return result is not None and result.returncode == 0


def check_uv(report: Report) -> None:
    result = run("uv", "--version")
    if succeeded(result):
        report.append(("ok", "uv", result.stdout.strip()))
    else:
        report.append(("fix", "uv", "uv is not installed. Install it with Astral's installer for this OS."))


def check_git_email(report: Report) -> None:
    result = run("git", "config", "user.email")
    email = result.stdout.strip() if succeeded(result) else ""
    if email.lower().endswith(NOREPLY_SUFFIX):
        report.append(("ok", "git email", email))
        return
    newest = run("git", "log", "-1", "--format=%ae", "origin/main")
    suggestion = newest.stdout.strip() if succeeded(newest) else ""
    if suggestion.lower().endswith(NOREPLY_SUFFIX):
        hint = f"GitHub's newest commit uses {suggestion}; confirm it is the learner's before using it."
    else:
        hint = "The learner's address is on GitHub's Emails settings page."
    report.append(("fix", "git email",
                   f"Commits would use {email or 'no email'}, not a GitHub no-reply address. "
                   f"Set it with `git config --global user.email <address>`. {hint}"))


def local_only_summary(ref: str) -> str:
    """Describe commits on `ref` that GitHub's main doesn't have, so the learner can judge them."""
    log = run("git", "log", "--format=%h %ad %s", "--date=short", ref, "--not", "origin/main")
    commits = log.stdout.strip().splitlines() if succeeded(log) else []
    if not commits:
        return "no local-only commits"
    return f"{len(commits)} local-only commits, newest: {commits[0]}"


def check_git_history(report: Report) -> None:
    if shutil.which("git") is None:
        report.append(("info", "git history", "Git is not installed. Install Git, then rerun setup."))
        return
    fetch = run("git", "fetch", "origin", "--quiet", timeout=180)
    if not succeeded(fetch):
        error = fetch.stderr.strip().splitlines()[0] if fetch and fetch.stderr.strip() else "no response"
        report.append(("info", "git history", f"`git fetch origin` failed ({error}), so this check was skipped."))
        return
    status = run("git", "status", "--porcelain")
    changes = len(status.stdout.splitlines()) if succeeded(status) else 0
    head = run("git", "rev-parse", "HEAD")
    remote = run("git", "rev-parse", "origin/main")
    if not (succeeded(head) and succeeded(remote)):
        report.append(("info", "git history", "This clone has no commits or no origin/main. Clone the repo from GitHub again."))
        return

    if head.stdout.strip() == remote.stdout.strip():
        report.append(("ok", "git history", "matches GitHub's main"))
    elif not succeeded(run("git", "merge-base", "HEAD", "origin/main")):
        # No shared commit means GitHub's history was replaced and this clone still has the old one.
        report.append(("fix", "git history",
                       f"This clone shares no commits with GitHub's main, so GitHub's history was replaced. "
                       f"Before `git reset --hard origin/main`, review {changes} uncommitted changes and "
                       f"{local_only_summary('HEAD')}. Never `git pull` here."))
    elif succeeded(run("git", "merge-base", "--is-ancestor", "HEAD", "origin/main")):
        report.append(("fix", "git history", "Behind GitHub's main. Update with `git pull --ff-only`."))
    elif succeeded(run("git", "merge-base", "--is-ancestor", "origin/main", "HEAD")):
        report.append(("info", "git history", f"Ahead of GitHub's main: {local_only_summary('HEAD')} not pushed yet."))
    else:
        report.append(("info", "git history", "Local and GitHub history have split. Sort this out before setup changes it."))

    branches = run("git", "for-each-ref", "--format=%(refname:short)", "refs/heads")
    current = run("git", "branch", "--show-current").stdout.strip()
    for branch in branches.stdout.split() if succeeded(branches) else []:
        if branch != current and not succeeded(run("git", "merge-base", branch, "origin/main")):
            report.append(("fix", f"branch {branch}",
                           f"Holds history GitHub no longer has ({local_only_summary(branch)}). "
                           f"Delete with `git branch -D {branch}` after the learner confirms; never push it."))


def venv_python() -> Path:
    # uv puts the interpreter in Scripts on Windows and in bin everywhere else.
    return REPO / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def check_environment(report: Report) -> None:
    pinned = (REPO / ".python-version").read_text(encoding="utf-8").strip()
    if not venv_python().exists():
        report.append(("fix", "environment", f".venv is missing. Run `uv sync`, which also installs Python {pinned}."))
        return
    if not succeeded(run("uv", "sync", "--check")):
        report.append(("fix", "environment", ".venv doesn't match uv.lock. Run `uv sync`."))
        return
    probe = subprocess.run(
        [str(venv_python()), "-c", "import platform, numpy, pandas; print(platform.python_version())"],
        cwd=REPO, capture_output=True, text=True,
    )
    version = probe.stdout.strip()
    if probe.returncode != 0:
        report.append(("fix", "environment", "NumPy or pandas won't import from .venv. Run `uv sync`."))
    elif version != pinned and not version.startswith(pinned + "."):
        report.append(("fix", "environment", f".venv runs Python {version}, but .python-version pins {pinned}. Run `uv sync`."))
    else:
        report.append(("ok", "environment", f"Python {version}, packages match uv.lock, NumPy and pandas import"))


def check_practice_tools(report: Report) -> None:
    result = run("uv", "run", "--no-project", "python", "PRACTICE/tools/harness.py", "validate")
    if succeeded(result):
        report.append(("ok", "practice tools", result.stdout.strip()))
    else:
        report.append(("info", "practice tools", "PRACTICE/tools/harness.py validate failed. Ask Claude to look at PRACTICE/log.jsonl."))


def check_writing_guide(report: Report) -> None:
    if not GUIDE_TARGET.exists():
        report.append(("fix", "writing guide", f"Not installed. Copy the repo copy to {GUIDE_TARGET}."))
        return
    # Git can switch line endings on Windows, so compare text with line endings evened out.
    home = GUIDE_TARGET.read_text(encoding="utf-8").replace("\r\n", "\n")
    repo = GUIDE_SOURCE.read_text(encoding="utf-8").replace("\r\n", "\n")
    if home == repo:
        report.append(("ok", "writing guide", str(GUIDE_TARGET)))
    else:
        report.append(("fix", "writing guide",
                       f"{GUIDE_TARGET} differs from the repo copy. Show the learner the differences and ask which copy wins."))


def check_vscode(report: Report) -> None:
    if shutil.which("code") is None:
        report.append(("info", "VS Code",
                       "The `code` command isn't on PATH. Install VS Code (on macOS, also run "
                       "'Shell Command: Install code command in PATH'), then rerun setup."))
        return
    result = run("code", "--list-extensions")
    if not succeeded(result):
        report.append(("info", "VS Code", "The `code` command failed. If VS Code is mid-update, restart it, then rerun setup."))
        return
    installed = {line.strip().lower() for line in result.stdout.splitlines()}
    missing = [ext for ext in VSCODE_EXTENSIONS if ext not in installed]
    if missing:
        report.append(("fix", "VS Code", f"Missing extensions: {', '.join(missing)}. Install each with `code --install-extension <id>`."))
    else:
        report.append(("ok", "VS Code", f"extensions installed: {', '.join(VSCODE_EXTENSIONS)}"))


def check_book(report: Report) -> None:
    if BOOK_PDF.exists():
        report.append(("ok", "book PDF", "present"))
    else:
        report.append(("info", "book PDF", "Not on this computer. Optional; book/README.md explains how to add it."))


def check_java(report: Report) -> None:
    result = run("java", "-version")
    # Java prints its version to stderr, as `version "17.0.8"` or the older `version "1.8.0_392"`.
    match = re.search(r'version "(\d+)(?:\.(\d+))?', (result.stderr + result.stdout) if result else "")
    major = 0
    if match:
        major = int(match.group(2) or 0) if match.group(1) == "1" else int(match.group(1))
    if major >= 17 and os.environ.get("JAVA_HOME"):
        report.append(("ok", "Java", f"Java {major}, JAVA_HOME set"))
    else:
        found = f"Java {major}" if major else "no Java"
        report.append(("info", "Java", f"Found {found}. Not needed until the PySpark chapter, which needs Java 17+ and JAVA_HOME."))


def main() -> int:
    report: Report = []
    # History comes before the environment because resetting to GitHub can change uv.lock.
    for check in (check_uv, check_git_email, check_git_history, check_environment, check_practice_tools,
                  check_writing_guide, check_vscode, check_book, check_java):
        check(report)

    width = max(len(name) for _, name, _ in report)
    for status, name, message in report:
        print(f"{'[' + status + ']':<7}{name:<{width}}  {message}")
    counts = {status: sum(1 for s, _, _ in report if s == status) for status in ("fix", "info", "ok")}
    print(f"\n{counts['fix']} to fix, {counts['info']} for the learner, {counts['ok']} ok")
    return 1 if counts["fix"] else 0


if __name__ == "__main__":
    sys.exit(main())
