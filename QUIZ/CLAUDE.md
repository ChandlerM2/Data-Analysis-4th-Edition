# QUIZ: practice sessions

The focus is the learner's learning. You handle the logistics (tracking what they have
finished, what is due) and write new problems so they can practice. The learner never runs the
tooling. The teaching rules in `.claude/CLAUDE.md` and `.claude/rules/explaining.md` still
apply. The repo moves between Windows, macOS, and Linux, so paths use forward slashes.

## Files

- `QUIZ/chapters.json`: the book's chapters, and under each one the sections the learner has
  told you they finished, with `date_added`, `date_last_practiced`, `times_practiced`,
  `last_result` (`correct` or `wrong`), and `box` (1 to 5).
- `QUIZ/YYYY-MM-DD.ipynb`: one notebook per practice session. The permanent record of the
  problems, every attempt, and every review.
- `QUIZ/tools/quiz.py`: background bookkeeping, run as
  `uv run --no-project python QUIZ/tools/quiz.py <command>`. `review` picks sections for an
  "across everything" session. `record --chapter N --section "Name" --result correct|wrong`
  saves a result. `validate` checks the file's format. A hook in `.claude/settings.json`
  checks `chapters.json` after every Edit or Write you make to it.

## Signals

Act on what the learner's message clearly means. If a message could start more than one flow,
ask which one.

| The learner says something like | You do |
|---|---|
| "finished <section>", "done with <section>", "finished chapter N", "stopped at <section>", "up to <section>" | Everything in `book/outline.txt` before the point they name is finished ("finished" and "done with" include the named heading and everything under it). Compute the difference: every heading up to that point that `chapters.json` lacks, at every level (main sections, subsections, nested subsections), and add each with today's date and the book's exact name, in outline order. Never track Technical requirements, Summary, References, Further reading, Join our community on Discord, or the outline's "Chapter 18" (Packt's benefits page). Confirm in one line that names what you added. |
| "quiz what I just did" + section names | Start a **what I just did** session on those sections. If they name none, ask which. |
| "quiz everything", "review", "mix it up" | Start an **across everything** session: run `review` and use the sections it picks. |
| "quiz" or "practice" with no mode | Ask: what you just did, or across everything? |
| "check 2.0", "done with problem 2" | Review that attempt. |
| "wrap up", "done for today" | Record the session (below). |

## Building a session notebook

1. Read the book's text for each section first. The book is the full scope of what the
   learner is studying; their notes and code show what they took from it, not everything it
   covered. Find the pages in `book/outline.txt` (from the section's `[pN]` up to the next
   heading's page) and extract them from the PDF in `book/` with
   `uv run --no-project --with pypdf python`. If the PDF isn't on this machine, use the Packt
   repo's notebook for that chapter. Then read the learner's work: their notebooks in
   `ChapterN - Topic/` and their `chapterN.md` notes.
2. If a section is coming back after a `wrong`, open the notebook from its
   `date_last_practiced` and read the WRONG reviews. Write the new problem to test that same
   idea again from a different angle.
3. Write 3 to 5 problems totaling 30 to 45 minutes, each with a time estimate. Most are tasks
   someone could be handed at work, stated as a goal and constraints, never naming the
   function or method. Mix in conceptual questions. Set each problem in one of the target
   jobsets from `.claude/CLAUDE.md` (analytics engineering across a whole company, AI
   engineering for go-to-market teams) and rotate across both and across departments. Use
   made-up values, never real company data.
   You may go beyond what the learner captured: combine the picked sections with each other
   or with earlier sections they have finished, push the difficulty past the book's examples,
   and ask about important topics the book covers that their notes or code skipped.
4. Data: use data that already exists, a setup code cell that generates it with a fixed seed,
   or a public URL or API. Add a file in `QUIZ/` only when none of those work.
5. Pre-verify before the learner sees it: run any setup cell and solve each problem yourself
   in the scratchpad. The solution never goes in the notebook.
6. Notebook layout: a title cell (`# Quiz YYYY-MM-DD`, the mode, the sections, the time
   estimate). Then for each problem N, a markdown cell `## Problem N: <title>` with the
   section, type (coding or conceptual), time estimate, and task; a setup cell only if data is
   generated; and an empty attempt cell labeled `N.0` (a code cell `# N.0`, or a markdown cell
   `**N.0**` for a conceptual answer). The learner explains their reasoning in comments.

## Reviewing an attempt

- Insert a markdown cell directly below the attempt titled `### N.0 CORRECT` or
  `### N.0 WRONG`.
- Grade the explanation as well as the code. Right code with a wrong explanation is WRONG,
  because it means the mental model is wrong.
- WRONG: show exactly where the learner went wrong (quote the line or the comment), explain
  the right mental model and why their version breaks, then leave an empty `N.1` cell below
  for the next try. The learner writes the fix. Never edit an earlier attempt or review.
- CORRECT: say what their reasoning got right, and add anything that deepens the concept.
- Talk the review through in chat as well.

## Recording a session

For each section practiced: `wrong` if any attempt on its problems was WRONG, otherwise
`correct`. Run `record` once per section. `correct` moves it up one box; `wrong` sends it to
box 1 so it comes back the next day. Days until due by box: 1, 3, 7, 14, 30. Tell the learner
which sections are coming back and when.
