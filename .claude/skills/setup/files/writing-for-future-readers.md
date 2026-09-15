# Writing for future readers

Use this whenever you write or edit text that a future reader acts on: CLAUDE.md files,
`.claude/rules/`, skills, agent definitions, READMEs, and comments and docstrings in code. The
reader arrives without today's conversation, so the text has to carry what they need to act
well, including in cases it doesn't name.

## Write each rule as an instruction plus its reason

State what to do, then give the reason when it would help the reader handle a case the rule
doesn't list. A bare command gets followed to the letter; a command with its purpose can be
adapted to a case nobody planned for. The military calls this commander's intent, and
Anthropic's prompting guide calls it adding context or motivation.

> Bare: "NEVER use ellipses."
> With its reason: "Your response will be read aloud by a text-to-speech engine, so never use
> ellipses since the text-to-speech engine will not know how to pronounce them."

A reader of the second version also avoids other symbols a voice can't pronounce, without
needing a list of them.

## Test every sentence

Ask: if the reader hits a case this text doesn't cover, would this sentence change what they
do?

- Keep it if yes. Reasons, goals, and the consequences of breaking a rule usually pass.
- Cut sentences that retell how a decision was made, such as "it was chosen" or "we switched
  to this in March." The instruction already shows the decision, and the story goes stale.
- Cut background that no instruction depends on. A fact about a person, a machine, or a setup
  belongs in the text only as the reason behind an instruction.

## Describe the present, not the history

Write about what exists now. Leave out what used to exist and how the text or code got here,
because the reader can't see the old version and the story turns false the next time things
change. Git history and commit messages record changes; the file records the current state.

- In instruction files, fold a new rule into the section it belongs to and merge near
  duplicates. Don't append dated change notes.
- In code comments and docstrings, say what the code does and why, when the why isn't visible
  from the code itself: a business rule, a workaround for a library bug, a limit set by another
  system. Don't write comments like "used to call the old API", "removed the retry loop", or
  "no longer needed", and don't mention functions, files, tables, or columns that aren't in the
  codebase anymore. Put that history in the commit message.

Records whose job is history are the exception: commit messages, changelogs, decision logs,
retros, and memory entries that track dated project status.

## Keep the plain-language rules

The writing rules in `~/.claude/CLAUDE.md` apply here too: no em dashes, no intensifiers,
ordinary words first, and technical terms defined the first time they appear.

Source: Anthropic, "Prompting best practices", section "Add context to improve performance":
https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
