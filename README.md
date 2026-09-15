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
| 5 | Optional: add the book PDF (see `book/README.md`), and copy `.claude/skills/setup/files/writing-for-future-readers.md` into `~/.claude/rules/`. | The PDF lets quizzes draw on the book's own pages, and the writing guide shapes how Claude writes docs and code comments on this computer. |

To check a setup at any time, run
`uv run --no-project python .claude/skills/setup/scripts/check_setup.py`.

## QUIZ: practicing what I've read

Reading a chapter doesn't mean a person knows the material, so the `QUIZ/` folder holds an agentic powered practice routine. Basicly, Claude (or your AI of choice) keeps track of the logistics and writes new problems so I can practice.

In a claude code session you can mention: 

1. **While you read,** tell Claude when you finish a section or sections. The section will then be added into a JSON file under its chapter
   in `QUIZ/chapters.json` with the date.

2. If a user says, **"Quiz what I just did in section x"** a session on those sections will start. Claude
   reads my notebooks, notes, and the book, if available, for those sections then builds a Juypter notebook in the following format: `QUIZ/YYYY-MM-DD.ipynb`.

3. If a user says, **"Quiz everything"** a session will start pulling in problems from everything finished so far in the book, limited to 3 - 5 problems. Leitner boxes decide which sections need to be worked on. For example, each section sits in a box from 1 to 5, a correct session moves it up a box so it returns less often (after 1, 3, 7, 14, then 30 days), and a wrong one sends it back to box 1 for the next day.

As mentioned, a session is 3 to 5 problems in a juypter notebook and should only last about 30 to 45 minutes. The questions are framed as if an individual was handed the task at work, described by what needs to happen (the business problem), thefore making judgement and function approach part of the problem. Some are conceptual questions from my notes.

To answer your questions claude will create a Markdown file with "Problem N" on the question and N.0 on your first
     code cell. So for instance number two would be `Problem 2` and in the code block `2.0`. In the code block you are to code the soultion and explain the reasoning/judgement via comments within the code block. Claude reviews it and write in a markdown cell below the code block. Claude will title it CORRECT or WRONG.


**Some Rules & Bookkeeping:**

- The Right code with a wrong explanation is WRONG, because it means your mental model/judgement layer is off balance given the problem. Syntax is okay to learn but the main thing we are working here is judgement in the form of repeated work. The syntax just adds a layer on top for difficulty.

A WRONG review shows where the user went wrong and explains the right idea. A new code block is created and the user trys again in a new cell, `N.1`, so every iteration stays visible. When a section comes back in future session, its new problem will test the same area the user failed on.

The rules Claude follows are in `QUIZ/CLAUDE.md`. `QUIZ/tools/quiz.py` and a hook in
`.claude/settings.json` do the bookkeeping in the background.
