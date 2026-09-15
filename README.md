# Data-Analysis-4th-Edition
My Analysis and ML journey using Avinash Navlani and Cornellius Yudha ijaya's book. 

## Setup on a new machine

This repo works the same on Windows, macOS, and Linux. Install [uv](https://docs.astral.sh/uv/),
clone the repo, and from its root run:

```
uv sync
uv run jupyter lab
```

`uv sync` reads `uv.lock` and builds `.venv` with the exact package versions recorded there.
`uv run jupyter lab` opens JupyterLab using that environment.

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
