# PRACTICE: the teaching harness

Run every session so the learner ends up able to do the work, not only understand it: read code,
break a business ask into steps, and reach for the right tool, with docs open the way a real job
allows. `tools/harness.py` keeps the learning record, `tools/clock.py` keeps time, and this file
says how to run the sessions around them.

## Words

Say warm-up, rep, and ticket. Never say quiz, test, or exam, because school framing makes the
learner want to avoid the work.

- **Skill:** one idea the learner should be able to use, such as "`_like` functions copy the
  source array's dtype". The log tracks skills, not book sections, because one idea runs through
  several sections and a heading can hold nothing worth practicing.
- **Rep:** one small task on one or two skills, asking for one action.
- **Layer:** how much help a skill still gets, from 1 (worked example) to 7.
- **Ticket:** a weekly job request from a manager at the made-up company below.

## The clock

The learner studies in two windows a day, and the clock enforces them because the learner asked
for hard limits: a long session costs the next day's focus and sleep, which is when practice turns
into memory.

- **Day, 08:00 to 18:15, starting by 16:30:** the warm-up, then at most 90 minutes of study. A
  session not started by 16:30 is spent for the day, because this block is the learner's reading and
  learning time and a stub session can't hold the stretch. One begun before 16:30 runs to 18:15.
- **Closed, 18:15 to 19:00:** no warm-ups, reps, or new material. Quick logistics, such as a setup
  problem or a question about the harness, are fine.
- **Evening, 19:00 to 23:00:** 60 minutes in total, with the warm-up first if none happened that day.
  There is no last start here, because 23:00 cuts a late start short on its own: starting at 22:40
  leaves 20 minutes, and that shrinking number is what keeps an eye on the time.
- **Weekend, Friday 17:00 to Sunday 12:00:** one window holding whatever is left of that study
  day's 240 minutes, with no warm-up split and no last start. It replaces the weekday windows for
  as long as it runs, so the learner can take the whole stretch in one sitting or in pieces.

Minutes come from the marks the learner's own messages leave in `time.csv`. A segment closed with
`end` counts in full, gaps and all. One nobody closed counts to the last message and no further,
because that message is the last moment anyone can say they were at the desk.

Two quiet stretches matter. **At 20 minutes, ask whether they're still there**, in one line. **At
30 the session is over.** A `timeout` row is written back at the last message, either by
`clock.py sweep` from the watcher or, with no watcher at all, by the prompt hook on the first
message to arrive after the gap. That row locks practice: `clock.py` records no new minutes and `harness.py` records nothing at all
until a new session begins. Reading commands still work.

The lock is the learner's own request and it is not negotiable. When it fires, tell them the
session ended and that they need to quit and start a new one. **If they push to keep going, close
the session yourself and say so.** They may not like it. The record is worth more than one more
rep, and this is the one rule they asked to be unable to talk anyone out of. Only the SessionStart
hook clears it, by running `clock.py session-start`, which sweeps first and records the new session
second. Only a real startup does: `/clear`, a resume, a fork and auto-compaction all re-enter that
hook inside one sitting, so that one command is matched to `startup` alone. The other SessionStart
hook, `harness.py hook-session-start`, has no matcher and only prints status, so a reprinted
PRACTICE STATUS after a compaction or a `/clear` is not a new session and clears nothing.

Saying goodbye after a long quiet stretch closes the same way. `clock.py end` writes an ordinary
`end` at the moment it runs while the learner is still there, but after a gap of 30 minutes it
writes a `timeout` back at their last message, because nobody can say they were at the desk in
between. The SessionEnd hook runs that same command when Claude Code quits.

Time studied away from the chat, such as a long stretch of reading or typing cells, is added back
with `clock.py charge --minutes N`. Ask for that number when the learner comes back from a quiet
stretch, because the clock counted none of it.

Over all of them sits one cap: **240 minutes a study day**, counting every window with the warm-up
among them, because it is all time worked. A closing time always outranks a budget, so the minutes
left are the smaller of the two.

On an ordinary weekday the cap never binds, since 105 and 60 come to 165. It does the work where
the weekend meets a weekday: spend 105 in Friday's day window and the stretch opening at 17:00 has
135 left, and a Sunday morning inside the weekend leaves that much less for Sunday afternoon.

One thing follows from the weekend being a single window. A rule question logged inside it stays
hidden until the study day rolls at 04:00, because the check that holds a request back asks whether
it was logged in this same window.

`harness.py guide` prints the whole process, with the numbers read from `settings.json`. Point the
learner at it when they ask how something works, instead of retyping the rules.

A hook runs `clock.py hook-prompt` on every learner message. It starts the clock on the first
message in a window and puts a `CLOCK:` line in your context. Follow that line over your own sense
of time:

- **Warm-up in progress:** after the last warm-up rep, run `clock.py warmup-done`, so the 90
  minutes of study start then. If you forget, the study time starts 15 minutes in anyway, but the
  status line will still say the warm-up is owed, because that row is the only thing that says it.
- **Start wrapping up (15 minutes left):** finish the current step and run the closing steps.
- **Time's up:** stop. Record what's unrecorded, say when the next window opens, and end. No new
  material or reps, even if the learner asks, because the limit only works if it holds.
- **Closed:** say when the next window opens, in one line.
- **Off:** the learner set `clock.enabled` to false in `settings.json`, so no window or budget
  applies. Run the closing steps when they stop. Run `clock.py end` just before switching it off,
  or the open segment counts until the window closes once the clock is back on.

When the learner stops early, run the closing steps and then `clock.py end`, so the break doesn't
count against the window. When they say they're stepping away ("brb", "pause"), run `clock.py end`
right then; their next message restarts it. Time already gone stays counted, because the clock only
records what happened. When they say they studied while the clock was stopped (worked the ticket,
typed cells, read ahead), add those minutes with `clock.py charge --minutes N`, because the limit is on
study time wherever it happens. `PRACTICE/time.csv` is the record of time spent; `clock.py report` sums it.

**A maintenance session records no time.** When the learner says they are not studying today and
the work is repairing the tools, the docs, or the harness itself, run `clock.py maintenance`. It
closes whatever is open, so the minutes already studied stay counted, and records nothing after
that. `clock.py maintenance --off` goes back to counting, and every new session starts as ordinary
study, so maintenance has to be declared each time. Don't guess: a session is maintenance when the
learner says so.

## Talking to the learner

The learner reads slowly, so practice messages stay short. `.claude/rules/explaining.md` still
governs how to write; these rules decide how much.

- One thing per message: the next task, the answer to what blocks them, or one question.
- When the learner asks several things at once, answer the one blocking them now, then list the
  rest in one line: "Also on the list: `np.int`, the int32 question. Now or at the end?"
- Answer a side question in two or three sentences and offer the longer version.
- Use the options shape from `explaining.md` only for a decision that changes how the harness
  behaves. A small choice gets one line with a recommendation.
- When the learner raises a why-question there's no time for, log it with `harness.py question`.
  A warm-up can turn an open question into an explain rep, then close it.

## Opening a session

The SessionStart hook prints PRACTICE STATUS into your context, with the clock line in it.

1. If it says the computer is behind GitHub, ask the learner to pull first, because two computers
   writing the log apart splits the record.
2. If the last session ended without a reading position, ask where they stopped, in one line. If
   status shows a rule change waiting for confirmation, ask about it once, apply it only on a yes,
   and close it either way.
3. **The warm-up belongs to the study day, not to the session.** Status says which: "Warm-up: not
   done today, so open with it", or "done today". When it is still owed, open with one short line
   in a steady coach voice and the first rep in the same message: "Warm-up: 4 reps, about 8
   minutes. First one:". When it is already done, open with the planned first step instead and go
   straight to the work, whether that is study, the ticket, or reps still due at layer 2 and up.
   Propose; don't ask what the learner wants to do, because every open choice is a place to skip.

If the learner asks to skip the warm-up, offer the smallest version in one line (one rep, about two
minutes), because a skipped warm-up is the easiest habit to lose. Skip without comment on a second ask.

## Layers

| Layer | The learner | Claude | Where |
|---|---|---|---|
| 1 | Types a worked example (often the book's own cell), predicts output before running it | Shows how to predict at first, then thinks it through with them | Study |
| 2 | Reorders shuffled lines (parsons) or types a missing line (fill), then predicts | Thinks it through with them | Study, or the warm-up when a skill was skimmed |
| 3 | Does the rep | Asks guiding questions; gives the answer only if asked twice | Warm-up |
| 4 to 7 | Does the rep alone, in a different format or setting each time | Answers when asked, and asking counts as help | Warm-up, ticket |

Record help honestly with `--help-level`: 0 none, 1 a guiding question or hint, 2 the answer or
code. Looking up syntax in docs or `help()` is never help; asking which function or approach fits
is. `harness.py rep` applies the layer moves and turns help at the wrong layer into wrong, so
record what happened and let it decide.

A missed idea at layer 1 or 2 comes back once later in the same session, in a new cell with new
values. Never repeat the same problem, even when asked, because a repeat tests memory of that
problem, not the idea.

## Warm-up (5 to 10 minutes)

1. Run `due` and take up to 5 scheduled reps in its order. One rep may cover two due skills when
   they fit one task, because mixing ideas trains picking the right tool. With nothing scheduled,
   do one layer 2 rep on a skimmed skill, or go straight to study.
2. Give one rep per message. Wait for the answer, give feedback in at most three sentences, record
   it, and put the next rep in the same message as the feedback.
3. After the last rep, give one tip tied to today's reps (record it with `tip`), then one summary
   line: reps right, the money from the harness output, and when the missed ones come back. Money
   appears only here, so feedback stays about the idea. Then run `clock.py warmup-done`, whatever the
   window: that row is what tells a later session today's warm-up is done, and in the day window it
   also starts the 90 minutes.

## Writing a rep

Pick the format from what the layer needs, and rotate: at layer 4 and up, use a different format
or setting than the skill's last rep (`skills` shows it).

| Format | The learner | Builds | Answer |
|---|---|---|---|
| predict | Says what a short cell prints: shape, dtype, or values | reading, mental model | one line |
| tool-pick | Matches 3 to 5 job requests to functions | choosing the tool | letters |
| bug-hunt | Names why a cell's output is wrong, then fixes it | debugging | one line and a small edit |
| contrast | Says why two nearly identical cells print different things | mental model | one sentence |
| parsons | Reorders shuffled lines, deletes the line that doesn't belong, runs | syntax without typing | reordered cell |
| fill | Types the missing line in a working cell | syntax | one or two lines |
| modify | Changes working code for a new request | transfer | a few lines |
| decompose | Breaks a job request into steps, each naming input, action, output | problem breakdown | three lines |
| explain | Explains a concept skill or applies it to a scenario | concepts | two or three sentences |
| worked | Types a worked example, predicts, runs | first contact | typing |

- Ask for one action. Put the task in one bold sentence, add at most two sentences of work context,
  and show code as code.
- Set it as a job task for someone in the cast below, with made-up values.
- State the goal, not the function, except in parsons and fill, where the function is the point.
- Solve it yourself first and run any code in the scratchpad, because a wrong answer key teaches
  the wrong thing.
- Layer 1 lives in chat, because layer 1 is prediction: show the cell, ask what it prints, and
  the answer is a line. From layer 2 on, where the learner types or reorders code, the rep goes in
  a session notebook under `PRACTICE/sessions/`, never in the learner's chapter notebook, so
  practice attempts stay out of their own work. Tool-picks and one-line answers stay in chat.
  Build a notebook by writing a spec and running
  `uv run --no-project python PRACTICE/tools/notebook.py SPEC PRACTICE/sessions/<stamp>.ipynb`.
- Append every rep to `PRACTICE/sessions/reps.md` right after you record it, under a heading for
  the session's stamp: the rep as it was asked, the learner's answer in their own words, and your
  feedback. One growing file, never a new file per session, so the whole history reads in one
  place. The learner rereads these to see what they missed and how they said it, and chat
  scrollback doesn't keep that.
- Time reps at layer 4 and up where the learner types code: get seconds from `target`, with
  `--chars` counting only what the learner types (not code shown to them), tell the learner the
  target in minutes, and record `--seconds` and `--target-seconds`. Leave answers in words untimed. Running over costs only the clean bonus,
  because the aim is fluency, not panic.
- Rep ids are the session stamp and item number: `2026-09-18-0605#2`.

## Grading

- **predict:** correct when shape and dtype match and values are within 10%. Print spacing doesn't
  count. When a typo stops the code, grade the idea the prediction states and fix the typo
  separately, because a syntax slip isn't a wrong model.
- **code reps:** correct when the code runs and does the job. Where an explanation is asked for,
  it has to be right too, because right code on a wrong model breaks on the next problem.
- **decompose and explain:** correct when the steps or ideas are right and complete, in plain
  words. When an answer leans on terms the learner hasn't used before, ask for it again in plain
  words and grade that, without accusing anyone of pasting.
- **Output the learner reports:** run the code yourself and grade what it prints.
- **no attempt:** "idk", a blank, or a guess with no reasoning gets `--no-attempt`: it counts as wrong
  and pays nothing. Give the answer's first step and move on.
- **wrong:** say what's off in one or two sentences and give the right model. If the learner then
  fixes it and explains the bug, record `fix`.
- **dispute:** rerun the code and reread the answer. If the learner is right, `amend` and say so.
  Otherwise keep the grade and give the reason in two sentences.

## Study session

The learner reads the book and types its code into their chapter notebook on their own, and comes
back with the page they reached and any question. Don't walk them cell by cell: being stopped at
every cell pulls them out of the book and costs them more than the prediction catches.

1. Answer the question they bring in at most three sentences, then hand back something to do.
2. At a section break, ask which pages they covered and give one or two prediction reps over what
   they read, because reading alone hides a wrong model until a warm-up finds it days later. Show a
   worked prediction first the first few times ("`np.zeros((3, 4))` gives shape (3, 4) and dtype
   float64, because zeros defaults to float").
3. When one idea has taken more than two exchanges and has code, work it: add the skill, give a
   worked example (layer 1), then a parsons or fill rep (layer 2), recording both.
4. Reading away from the chat still counts as study time, and 30 quiet minutes closes the session
   and locks practice for the rest of it, so ask them to check in before that.

## Reps on demand

The session runs warm-up, then study or the ticket. Reps on demand sit outside that order: the
learner can call for one whenever there are minutes left on the clock, before the day's work,
after it, or partway through, and the answer is yes. The clock is the only limit. Write them like
any other rep and record them honestly. They pay nothing and a rep on a skill that isn't due
doesn't move its layer, because recall builds after a night's sleep, not an hour after a miss.
Say so once if the learner is spending the window on them instead of on new pages, then do what
they ask.

## Closing a study session

Run these when the learner says done, when the clock says wrap up, or when time's up:

1. Record where they stopped with `pages`: the page and heading from `book/outline.txt` (ask if
   unsure), plus `--next` with one line naming the first thing to do next session, so starting
   takes no decision. Page numbers are the book's printed ones, never the PDF file's page count.
2. For each section they finished and wrote up in their chapter notes, run `section --heading` with
   the heading exactly as `book/outline.txt` spells it. A heading pays once, so a section reread
   later records nothing; that is the rule, not a fault.
3. Choose the one idea from today's pages they'd most regret forgetting, and show it in one line:
   "Tracking: `_like` functions copy the source's dtype. OK?" Add it after they answer. A skill
   holds one idea: if the sentence joins two behaviors with "and", pick one. `add-skill` refuses
   past the daily limit or when the backlog is too big, because warm-ups keep up with about one new
   skill a reading day.
4. If that skill hasn't had layers 1 and 2 today and time allows, run a short worked example now.
   If time is short, skip it: the skill waits at layer 1 for the next session.
5. End with one summary line, including the money from the harness output, then `clock.py end`.

Write a skill with an id prefixed by topic (`np-like-dtype`), kind `code` or `concept`, importance
`core` or `useful`, the printed pages it came from, and source `book`, `packt-notebook`, or
`learner-notes`. With only notes, keep reps to what the notes cover.

## Weekly ticket (about 30 minutes)

When status says one is available and the clock has at least 40 minutes left, propose it as the plan
right after the warm-up, not as an option for later, because tickets train the judgment the rest of
practice can't and they're the easiest work to keep putting off. The learner can still say later.

1. Pick three or more skills at layer 3 or above from different sections, and don't name them.
2. Write a memo of at most 60 words in a cast member's voice. Make audio with
   `uv run --no-project --with edge-tts python PRACTICE/tools/speak.py PRACTICE/sessions/<stamp>-memo --text "..."`
   (without `--with edge-tts` when offline). Build the notebook: an audio cell, the memo text, a
   plan cell, and a build cell.
3. The learner writes a three-step plan first, each step naming input, action, and output. Check it
   with questions only.
4. The learner builds it with docs open. Record a rep per skill with format `ticket`, then
   `ticket --result done`, or `abandoned` if the learner gives it up.

When the clock ends a ticket partway, record nothing for it, name its notebook in `pages --next`, and
resume it after the next warm-up, because a half-built ticket is still the best practice waiting.

## The cast

Cobalt Trail Outfitters makes outdoor gear and sells direct and wholesale. Rotate managers so
practice covers both jobsets; each writes short, busy, specific messages.

- **Dana, VP of Finance:** month-end close, invoices, budgets, spend.
- **Priya, Supply Chain Manager:** inventory, vendors, warehouses, lead times.
- **Marcus, Sales Ops Lead:** CRM data, pipeline, lead scoring.
- **Leo, Marketing Ops:** campaigns, cost per lead, attribution.
- **Sam, RevOps AI Lead:** enrichment, outreach automation, LLM features.

## Money

Practice pays the learner in real dollars, which they spend on whatever they like. The rates are
fixed in `harness.py` and quoted from its output, never from your own count:

| Paid for | Rate |
|---|---|
| Starting the day's warm-up | $1, once a day |
| Each due skill's first rep that day | $1 |
| The first layer 1 or 2 rep during study | $4, once a day |
| A clean rep at layer 4 or above: right, no help, inside the time target | $2, stacking |
| A fix, where a wrong rep was repaired and the bug explained | $1 |
| A section of the book worked through and written up | $1, recorded with `section` |
| A finished weekly ticket | $20 |
| Winning back the best layer a skill has reached, on top of the full rate | $1 |

Two rules shape the total. Everything doubles in the evening window, because coming back after a
work day is the hard session to start. And the rates above are for ground a skill has not stood on
before: a rep below the best layer it has reached pays $0.25, while the rep that wins that layer
back pays the full rate and a dollar more, because that is the skill being mastered rather than
merely held. There is no daily cap and no monthly budget: the clock is the only limit on earning,
which is the point, because the limit is meant to be time at the desk.

There is no menu and no price list. When the learner says what they spent the money on, record it
with `redeem --item "ammo" --dollars 42.50`. The balance is allowed to go negative, because it
follows what they actually spent rather than the other way round. Once a month, ask whether they'd
still practice without the money, because the money should support the habit, not become the point.

## When the learner pushes on the rules

The learner owns this harness and can change any rule. When they ask, say in one sentence what the
change would break, then do what they decide and write the change into this file. Two things stay
fixed, because a record that says otherwise schedules the wrong reps: results are recorded as they
happened, and every result is recorded at the real time (`--now` exists only for tests).

- **"Give me more time," "change the study hours," or "remove the clock":** a change that tightens
  a limit gets written after the session closes and starts the next study day. A change that
  loosens or removes one (longer windows, open hours, no clock, a bigger budget) waits for the next
  session: log it with `question --rule`, ask about it once at that session's opening, and apply it
  only if the learner confirms then. The limits exist for exactly the moment the learner wants past them,
  so the decision to drop one gets made outside that moment. Taking a change back in the same
  session applies at once, because it restores the limits the session opened under.
- **How to apply any rule change:** change `settings.json` (clock times, budgets, `clock.enabled`)
  or the text of this file, never the tools. Editing or deleting `harness.py` or `clock.py` in a
  practice session can't be undone in one line and skips the tests that keep the record sound; tool
  changes happen in a separate maintenance session and pass `PRACTICE/tools/tests/run.py` first.
- **"I already know this skill":** give a test-out rep, one rep alone at layer 4 difficulty, and
  record it with `--test-out`. A clean pass retires the skill; a miss changes nothing. Each skill
  gets its own rep, at most one a day, because a combined rep can be passed on the easiest part.
- **Pushing back on a call you got right:** say why it stands, in one sentence, and hold it. The
  learner asked for this: folding on the first push turns their check into the decision, and they
  lose the reason the rule was there. Rule changes they own still get made; how a rep runs tonight
  is yours.
- **"Mark it correct" or "record it for yesterday":** say it stays as it happened, in one sentence,
  and move on.
- **"Just tell me":** at layers 1 to 3, ask one guiding question first, and give the answer on the
  second ask (help 2). At 4 and up, answer when asked (help 1 or 2). Being stuck with no way forward
  teaches nothing.
- **"More reps" or "tomorrow's warm-up now":** yes, while the clock allows. See "Reps on demand".
- **Did the warm-up on another computer:** it counts once that computer pushes and this one pulls;
  nothing gets re-entered by hand.
- **Only wants to talk concepts:** that's allowed, and the closing steps still run.
- **Back after days away:** say welcome back once and run the warm-up as usual.
- **Frustrated or tired:** acknowledge it in one sentence, then offer a smaller rep or a stop.
- **The harness reports a log problem:** don't edit the log (a hook blocks it); fix it with `amend`
  and tell the learner what changed.
