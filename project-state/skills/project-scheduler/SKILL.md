---
name: project-scheduler
description: "Change when things happen, or make them run on their own — 'move the weekly report to Fridays', 'what's scheduled', 'make the tick run automatically', 'is anything firing'. Edits automation/tasks.yaml; installs a host only on a yes."
metadata:
  map:
    tier: P2
    stage: control
    requires: [memory, python, local-fs]
    inputs: [operator]
    reads: [reporting-matrix, automation-tasks, automation-hosts, state, milestones, log]
    writes: [automation-tasks, automation-hosts]
    delivers: [chat]
---

# project-scheduler

> **When to use — full trigger description.** The frontmatter carries a short, trigger-first
> description so all of the suite's skills fit Claude Code's skill-listing budget (see
> docs/SKILL-SPEC.md, *Description budget*). The complete version, kept here:
>
> Talk the project's cadence into place. Conversational read and write over automation/tasks.yaml — the canonical cadence registry — using the same op vocabulary and proposed-ghost-card discipline as the kanban calendar's chat surface, but without needing the app running. Use when the user says 'schedule the weekly status report', 'move the SR&ED digest to Tuesday', 'pause the Monday tracker email', 'what's scheduled', 'what fires this week', 'set up the cadence for this project', 'add milestone check-ins for M03', 'stop that recurring report', 'run the weekly report now', or any request to read or change WHEN something runs. Also sets up the HOST that makes the tick fire on its own when nothing else does (a plugin-only install ships none): 'make it run on its own', 'schedule the tick', 'nothing ran overnight', 'is anything firing for this project', 'set up a Desktop task / cron / launchd for the tick'. Proposes the exact Desktop task, routine, plist, crontab line or Task Scheduler registration and installs nothing without an explicit yes. Creates land as status:proposed ghost tasks awaiting acceptance — never live on first write. Does NOT compile from the matrix (that is project-automator), does NOT dispatch generators (that is project-orchestrator tick), and never edits reporting-matrix.yaml. All writes route through project-state. Trigger: /project-scheduler

## Purpose

The reporting matrix says *what* runs. `automation/tasks.yaml` says *when*. This skill is
how a person changes the *when* by talking, instead of editing YAML or dragging cards in
the kanban calendar.

It is the third door onto one registry:

| Door | Who uses it | Where |
|---|---|---|
| `project-automator` | compiles matrix → registry | batch |
| kanban calendar + its chat | operator, visually | the app, port 3355 |
| **`project-scheduler`** | operator, conversationally | **anywhere — Claude Desktop, CLI** |

All three write the same file under the same rules. This skill exists because the other
two need the app running, and the scheduling hosts that actually fire (see
`docs/AUTOMATION-HOSTS.md`) mostly do not have it.

> **This skill decides and persists. It does not fire.** Dispatching due work is
> `project-orchestrator tick`. Compiling the matrix is `project-automator`. Keep the
> jobs separate — one skill, one coherent job. The one exception to "it does not fire" is
> not an exception: `host` (below) sets up the alarm clock that calls the tick, records that
> it did, and checks it is still ringing. It never runs the tick itself.

---

## Invocation

```
/project-scheduler                          → read: what's scheduled, what fires next 7 days
/project-scheduler status                   → registry health: orphans, proposed, disabled, stale once-tasks
/project-scheduler <anything in words>      → interpret, emit ops, persist
/project-scheduler host                     → is a host installed for tick, and when did tick last run
/project-scheduler host setup               → propose a host for this project; install it only on a yes
/project-scheduler host remove              → propose removing the recorded host; remove only on a yes
```

There is no op syntax for the user to learn. They speak; this skill resolves.

---

## Step 0 — Locate and load state

1. Walk up from cwd to find `project-state/manifest.yaml`. **Fail fast if not found** —
   a scheduling change written into the wrong project is worse than no change.
2. Read `project-state/automation/tasks.yaml` → `tasks[]`. If absent, say so and route to
   `/project-automator generate` rather than creating one from nothing.
3. Read `project-state/reporting-matrix.yaml` → `entries[]` (targets and the authoritative
   `enabled` flag for matrix tasks).
4. Read `project-state/state.json` → phase, pointers, `sprint_calendar`.
5. Read `milestones/` for ids and due dates (milestone-scoped check-ins need both).
6. Timezone from `manifest.yaml:automation.timezone`. **REFUSE if absent** — report the
   missing key and stop. Never default to UTC or read the host clock.

---

## The op vocabulary

Every change is one of eight ops. This is the same vocabulary the kanban chat emits, so a
cadence talked into place here reads identically to one dragged into place there.

| Op | Shape | Applies |
|---|---|---|
| `create` | `{target: {kind: matrix\|action\|adhoc, ref}, cadence, title?, prompt?, scope?}` | **as proposal** |
| `reschedule` | `{id, cadence}` | immediately |
| `enable` / `disable` | `{id}` | immediately |
| `accept` | `{id}` | immediately |
| `remove` | `{id}` | immediately, proposed/adhoc only |
| `run` | `{id}` | immediately (one firing) |
| `apply-preset` | `{preset, day?, hour?, milestone?, due?}` | **as proposals** |

### Cadence shape

```yaml
kind: daily | weekly | bi-weekly | monthly | quarterly | annual | sprint-aligned | once | deadline
day:    <weekday>        # weekly, bi-weekly
hour:   0-23             # all time-fired kinds
minute: 0 | 30
dom:    1-28             # monthly, quarterly, annual
month:  1-12             # annual
start:  YYYY-MM-DD       # once
due / lead_days / hard / escalation   # deadline
```

`sprint-aligned` fires on each sprint's last day and stays **dormant** until
`state.json:sprint_calendar` is set — say so plainly when it is null rather than writing a
task that silently never fires.

### Presets

`daily-ops` · `weekly-core` · `funder` · `agile-default` · `milestone-checkins`

Presets are additive and idempotent. `milestone-checkins` takes `milestone` and `due`.

---

## The rules that keep this safe

1. **Creates are proposals.** Every `create` and `apply-preset` is written with
   `status: proposed` and `enabled: false`. The tick skips both, so a proposal cannot fire.
   Acceptance is a separate, deliberate act — `accept`, or the calendar's Accept button.
   Say "proposed, not live" in the reply every time.
2. **Never invent an id.** Targets must resolve to something already on file: a
   `tasks[].id`, a `reporting-matrix.yaml` entry id, a known skill action, a preset id, or
   a milestone id. If the user asks for a report nothing covers, create an **adhoc** task
   with an explicit `title` and `prompt`, and say it is ad-hoc, not a matrix entry.
3. **Never write `reporting-matrix.yaml`.** This skill owns *when*, not *what*. For matrix
   tasks the matrix's own `enabled` flag is authoritative — disabling a matrix entry is a
   matrix edit, and belongs to `project-state` or the matrix editor.
4. **Never dispatch, never send.** `run` queues one firing through the normal job path; the
   generator still drafts into `outbox/queue/`. Nothing reaches a human recipient from here.
5. **Milestone scoping.** Check-ins for a milestone carry
   `scope: {milestone: <id>, until: due}` so they retire when it completes. Prefer the
   `milestone-checkins` preset, passing `due` from the milestone file.
6. **Preserve operator intent.** Existing cadences are the operator's. Re-running this
   skill must never silently reset a task someone rescheduled — that is exactly the
   guarantee `project-automator update` makes, and this skill honours it too.
7. **Route writes through `project-state`.** Take the advisory lockfile on
   `automation/tasks.yaml` (300 s TTL), write, release, and append one
   `scheduler.<op>` event per applied op to `logs/activity.ndjson` (append-only).

---

## How a turn works

1. **Read the registry** and build the current picture: time-fired tasks, event-driven
   tasks, proposals awaiting acceptance, disabled tasks, and what fires in the next 7 days.
2. **Resolve the request against what exists.** "The Monday email" → `auto-monday-tracker-email`.
   Ambiguous? Ask once, with the candidates named. Never guess between two tasks.
3. **Emit the ops** — plainly, in the reply, so the user sees exactly what will change.
4. **Persist** through `project-state`, under the lock.
5. **Report** what applied, what is proposed and still needs acceptance, and when each
   thing next fires. Name the weekday and date, not just the cadence kind — "Monday
   2026-09-28" beats "weekly".

---

## Reading the schedule

A read should answer three questions without being asked:

- **What fires next, and when** — next 7 days, by date.
- **What is waiting on you** — proposals unaccepted, and anything disabled that the matrix
  still expects.
- **What is declared but dead** — `sprint-aligned` tasks with no sprint calendar, `once`
  tasks whose `start` has passed, matrix entries with no compiled task, tasks whose target
  no longer resolves. A cadence that cannot fire should never look healthy.

---

## Making it run on its own — `host`

A registry with no host produces nothing, silently (`docs/AUTOMATION-HOSTS.md`). The kanban app,
Atomic 47's fan-out Desktop tasks and the cloud scheduler are all hosts, but **a plugin-only install
has none of them**: unless something below is installed, `project-orchestrator tick` — the due
reports and the SR&ED deadline escalations — runs only when someone runs it by hand. `host` closes
that gap for one project. It follows the shape of `project-harvest-setup`: inventory first, propose
the exact thing, install nothing until the person says yes.

The artifacts come from `scripts/tick_host.py` in this skill's folder (standard library only), so
every host says the same tick prompt and none of them carries a cadence — the cadence stays in
`automation/tasks.yaml`. **Never compose a plist, crontab line, task prompt or PowerShell
registration by hand**; render it.

```
python3 <this skill>/scripts/tick_host.py check  --project-dir <folder> [--json]
python3 <this skill>/scripts/tick_host.py render --kind <kind> --project-dir <folder> [--time HH:MM] [--days daily|weekdays] [--json]
```

`<folder>` is the folder that holds `project-state/` (or `.project-state/`). `check` exits 0 when a
host is recorded, can be seen on this machine, and tick has logged a run recently enough; 1 otherwise.

### `host` (status) — "is anything firing for this project"

Read-only. Run `check` and report, in three lines at most: which host is recorded (kind, name, when it
fires) and whether this machine can see it installed (`installed` / `missing` / `unverifiable` — a
routine, or a host recorded on another machine); when tick last ran and by which host, and when it
last dispatched something; the problem and its fix. Also look for hosts that serve this project
without being recorded here, and say so rather than proposing a second one:

- the kanban app with its scheduler enabled, or its managed crontab block (`crontab -l` shows a
  `/api/cron/tick` line);
- Atomic 47's fan-out tasks (`project-state-nightly-tick` in the Desktop scheduled-task list) —
  `project-fanout` owns those;
- a project whose home is the cloud (`project_list` says `home: server`): the cloud scheduler ticks it.

`verdict: no-host` with tick runs in the log means someone has been running it by hand. Say that
plainly — it is the situation issue #109 describes.

### `host setup` — "make it run on its own"

1. **Status first** (above). An existing host that is healthy → stop and say so; one recorded but
   `missing` → offer to reinstall that one, not a different one.
2. **Preconditions.** `automation/tasks.yaml` exists (else route to `/project-automator generate`)
   and has accepted, enabled tasks — a host over an empty registry fires a quiet tick forever. The
   project is not served by the cloud scheduler.
3. **Pick the host by fit**, and say why in one line. Offer the first that fits; name the others.

   | # | Host | Fits when | Kind |
   |---|---|---|---|
   | 1 | Claude Desktop scheduled task | the person uses Claude Desktop on the machine holding the folder | `desktop` |
   | 2 | claude.ai routine | the project is reachable from the cloud (a git repository the routine can clone and push to) and the plugin installs in the routine's environment | `routine` |
   | 3 | OS scheduler running Claude Code headless | no Desktop app, or the person wants it to run with the app closed | `launchd` (macOS), `cron` (Linux), `task-scheduler` (Windows) |

   A routine cannot see a local folder. For a project that lives only on disk it does not fit; do
   not offer it as if it did.
4. **Agree the time.** Default 07:15 machine-local, every day (deadline escalations do not wait for
   Monday). A host fires once a day; *what* is due is the registry's business. Run `render` with the
   agreed `--kind`, `--time` and `--days`.
5. **Show exactly what will be installed** — the rendered artifact verbatim (the Desktop task's
   arguments, the routine's prompt, the plist and its path, the crontab line, the PowerShell lines),
   where it goes, how to remove it, what it costs (each run is a Claude session against the person's
   plan; the OS hosts cap it with `--max-budget-usd 2`), and what happens to a missed run (below).
   Then ask one yes/no question. **No yes, no install.**
6. **Install, on yes only:**
   - `desktop` → `create_scheduled_task` with the rendered arguments; then offer `run_scheduled_task`
     once and ask the person to approve any permission prompt it raises (approvals are kept per task;
     an unanswered prompt parks the run indefinitely).
   - `routine` → the `schedule` skill, switched off; one test run; switch it on only when the run log
     shows a tick result and the person agrees. Its prompt pushes to the repository — say so, because
     that is write access.
   - `launchd` / `cron` / `task-scheduler` → write the plist or show the lines, and run the rendered
     install commands **only if the person asked you to**; otherwise hand them over to run. The
     headless command runs in `--permission-mode dontAsk` with a fixed allow list, so it is denied
     rather than parked on anything outside it, and the allow list holds no connector that sends.
7. **Record it** through `project-state`: add the rendered `record` (with `installed_at` from
   `date -u +%Y-%m-%dT%H:%M:%SZ` and `installed_by`) to `automation/hosts.json` (kind
   `automation-hosts`) under the lock, replacing an entry with the same `id`; append
   `scheduler.host_installed` to the activity log with `kind`, `name` and `cron`.
8. **Prove it.** Fire it once (step 6's first run), then `check`: the verdict should read `ok` with a
   fresh `last tick` by the new host. If tick did not log, read the host's log file and report what it
   says. Do not call the setup done on the strength of the install alone.

### `host remove`

Show the recorded host and its rendered removal, ask, and on yes remove it; set the record's `status:
removed` (keep the entry — it is history) and append `scheduler.host_removed`.

### What happens to a missed run

| Host | Machine asleep or app closed at the time |
|---|---|
| Desktop task | runs when Claude Desktop next opens (jittered by several minutes) |
| launchd | asleep → runs on wake, missed intervals coalesced into one; powered off → skipped |
| cron | skipped; the next firing is the next one (a systemd user timer with `Persistent=true` catches up) |
| Task Scheduler | `StartWhenAvailable` runs it as soon as the machine is back |
| routine | the cloud does not sleep; it does not depend on this machine at all |

A late or caught-up tick is safe: dueness is "has this task's current period been run", so the
first tick of a period dispatches once and any later tick in the same period finds the
`orchestrator.tick` entry for that task and period and dispatches nothing (`project-orchestrator`,
*tick*, steps 2 and 6). A tick only ever queues drafts — nothing is sent — so the worst case of two
hosts racing in the same minute is a duplicate draft for a person to discard, never a duplicate send.
A period that passed entirely while nothing ran is not back-filled period by period: the next tick
sees the task due in the *current* period and runs it once.

---

## What this skill does NOT do

- Does not compile the matrix into the registry — `project-automator`
- Does not decide what is due today or dispatch generators — `project-orchestrator tick`
- Does not create or edit reporting-matrix entries
- Does not register a host on its own initiative. `host setup` proposes one and installs it only after
  the person says yes to the exact artifact shown; every other path through this skill only fills the
  registry the hosts read
- Does not set up Atomic 47's own fan-out tasks over a workspace registry — that is `project-fanout`.
  `host` is one project, one host, on the person's own machine or account
- Does not send, post, or publish anything
