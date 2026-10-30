# Upgrading from 4.9 to 5.7.4 (ChatGPT / Codex)

## Your project folder needs no migration

5.7.4 reads a 4.9 `project-state/` folder exactly as it is. There is no
migration step, no script to run, and nothing to convert first.

This was tested on 2026-10-30. The real 5.7.4 plugin was pointed at a dated
4.9 project folder, then used for reads, validation, a morning briefing,
a new decision, a new risk and a weekly report. It did not rewrite, rename or
reformat anything when it opened the folder. Reads changed nothing. Each write
touched only the file being written, one appended log line and, for some
kinds, the counters in `state.json`. Not one line of the 4.9 activity log was
changed or removed.

So, if an assistant tells you the upgrade needs a "migration" that rewrites
your records, it doesn't. **Decline it.** If your project folder is in git, `git
status` should show no changes until you ask for real work.

## How to upgrade

1. Back up your project folder (or commit it, if it is in git).
2. Replace the installed plugin folder with the 5.7.4 `project-state` folder
   from this repo or from `project-state-5.7.4.zip`.
3. Reinstall from your existing marketplace entry (the installation guide,
   section 3), then start a **new** task and check the installed version is
   5.7.4.
4. Set the email your records are signed with, if you haven't (see below).
5. In your project folder, ask: "Use project-state to validate this project's
   stored records. Report what you find; do not fix anything yet."

## What 5.7.4 will point out about a 4.9 folder

Validation reports these as **warnings**. They don't stop anything working.
Fix them only if and when you choose to:

- `state.json` counters that lag the files on disk (for example, 45 milestones
  counted, 47 present).
- Older `kind` spellings: `kind: change` (now `change-log`) and
  `kind: sc_meeting` (now `sc-meeting`).
- Records whose author is a skill name (`project-kanban`,
  `project-document-curator`) instead of a person's email. From 5.0 every
  record names the person responsible.
- Decisions marked as material changes with no change order linked.
- SR&ED settings that were never confirmed, such as `fiscal_year_end` and
  `claimant_bn`, if the SR&ED capability is on.

## What changes for you

**Writes are checked and signed (Codex with Node 20.10+).** The plugin now
ships a local server. Codex starts it and the skills write through it: each
change is checked against the record types, refused if the file changed since
it was read, stamped and logged. Without Node, or in a hosted ChatGPT chat, the
skills write the files directly, as 4.9 did. The README's "How skills write"
section has the detail.

**Records carry your email.** Set `PROJECT_STATE_ACTOR` or
`git config --global user.email` to your real address. In this build, if
neither is set, the server answers questions but refuses to write, rather than
signing records with your computer's login name.

**New in 4.10–5.7** (the full history is `project-state/CHANGELOG.md`):

- Project types on three axes, with ten work packs, a `sponsor-internal`
  default, chosen during onboarding.
- New capabilities: competitive **intel**, **portfolio** (a project whose
  subject is a set of member projects; it reads them and never writes into
  them) and **research** (mandates, findings and briefs).
- SR&ED: evidence confirmation and rejection, cost roll-ups, record revisions
  that keep history, and an executable validator
  (`capabilities/sred/validator/scripts/check.py`, needs Python 3 + PyYAML).
- Harvesting a local git clone, without fetching or writing.
- The daily tick catches up a period it missed, and logs a quiet tick, so
  "nothing was due" can be told apart from "it didn't run".

## Known issues in 5.7.4

Two server defects were found by the same test. Both affect Codex, where the
server runs. Neither touches your data until you hit them:

- **Editing `manifest.yaml` through the server can drop the `project:`
  block.** A patch to a nested field replaces the whole block (name, one-liner,
  packs). Until it is fixed, check `manifest.yaml` after any change to it, and
  restore the block from your backup or git if it went missing.
- **One missing document breaks the Documents view.** If
  `documents/index.yaml` lists a file that no longer exists, the whole
  documents screen fails. Remove or correct that entry.

## What does not carry over from Claude Code

Subagents, slash commands, Claude artifacts, claude.ai routines and Claude
Desktop scheduled tasks, and the cloud connector. The README's "What cannot be
carried over" table says what to do instead.
