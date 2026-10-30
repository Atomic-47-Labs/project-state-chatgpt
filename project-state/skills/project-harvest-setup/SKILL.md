---
name: project-harvest-setup
description: "Set up and manage who harvests what — 'set up my harvest', 'what's harvesting my projects', 'add Slack to my harvest', 'why didn't X harvest'. Cloud projects: lanes + your claude.ai routine; local: the Desktop nightly harvest."
metadata:
  map:
    tier: P2
    stage: control
    requires: [memory, python, git, local-fs]
    inputs: [operator]
    reads: [manifest, automation-tasks]
    calls: [project-fanout, project-harvester, project-state]
    delivers: [chat]
---

# project-harvest-setup

> **When to use — full trigger description.** The frontmatter carries a short, trigger-first
> description so all of the suite's skills fit Claude Code's skill-listing budget (see
> docs/SKILL-SPEC.md, *Description budget*). The complete version, kept here:
>
> Set up, inspect and change the harvests that feed a person's projects. Every project has one
> home, and the home decides its harvest: a **local** project is fed by the Claude Desktop task
> `project-state-nightly-harvest` fanning out over the workspace registry; a **cloud** project
> (home `server`) is fed by the person's own claude.ai routine over the lanes they opened. Trigger
> on 'set up my harvest', 'set up my harvest for <project>', 'connect my email to the project',
> 'harvest my calendar into <project> automatically', 'what's harvesting my projects', 'is <project>
> being harvested', 'add Slack to my harvest', 'stop harvesting into <project>', 'why didn't <project>
> harvest', an admin's request ('Jen asked you to connect your mail'), or the clocks changing.
> Takes an inventory first, proposes, and changes nothing until the person agrees. Does not harvest
> itself — `project-harvester` does — and does not operate the Desktop fan-out — `project-fanout`
> does. Trigger: /project-harvest-setup [status|setup [project]|change|why <project>]

The operator's guide this skill follows is `docs/HARVEST-GUIDE.md` in the tooling repo. Read it
when a person asks *why* something works the way it does.

---

## The rule

A project's **home** decides its harvest, and there is exactly one:

| Home (`project_list`) | Fed by | Written to |
|---|---|---|
| `local` | the local harvest: Desktop task `project-state-nightly-harvest` → `project-harvester` per project | the project's files |
| `server` | the cloud harvest: the person's routine `project-state harvest (<email>)` | the cloud project, via `deposit_inbox` |

Never cross them. A claude.ai routine cannot reach a local folder, and the cloud refuses deposits
into a mirror of a local project (`can_write: false`). The local fan-out already skips a project
whose manifest says `home: kind: server`. When someone asks for the crossing ("can't the routine
just feed project-state?"), explain this and offer what does work: a second Desktop schedule for
more frequent local harvests, or moving the project's home (a separate decision, never made here).

---

## Step 0 — Inventory (every mode starts here)

Read-only. Gather, then show one table.

1. **Cloud projects.** With the **Project State connector** (the cloud one, host
   `cloud.project-state.app` — not this plugin's local server): `project_list`. Keep each
   project's `home` and `access`. Then `harvest_lane` `list` → the person's lanes
   (`surfaces`, `surface_last`, `last_deposit_at`) and any open admin `requests`.
2. **Local projects.** Locate the tooling repo as `project-fanout` does (its Step 0:
   `~/.project-state/config.json` → `workspaceRoot` → `registry.json` → `toolingRepo`), then
   `python3 <toolingRepo>/scripts/automation-fanout.py list --phase harvest --json` → eligible
   projects and skipped ones with reasons, and
   `python3 <toolingRepo>/scripts/automation-fanout.py status --days 3 --json` → last results.
   No registry → say so and point to `/project-fanout registry`; carry on with the cloud half.
3. **The hosts.** The Desktop task: `python3 <toolingRepo>/scripts/check-desktop-tasks.py`
   (`ok` / `DRIFT` / `MISSING` for the harvest stub). The routine: `RemoteTrigger` `list`, find
   the one named `project-state harvest (<email>)` — the name `harvest_context` (`setup: true`)
   returns as `routine_name` — and `get` it (enabled, schedule, `mcp_connections`).
   `RemoteTrigger` exists only in Claude Code; without it, say the routine cannot be checked
   from here and point to https://claude.ai/code/routines.
4. **Scope.** `harvest_context` (no `setup`) for the cloud projects with lanes: per surface its
   `scope` and any `skip`.

Show:

```
| Project | Home | Fed by | Surfaces | Last harvest | Problems |
```

One row per project the person can feed. **Problems** is where the value is — name each in a few
words: a cloud project with no lane; a lane surface that comes back `skip`; a scope that looks
malformed (a channel reading `[object Object]`, an empty keyword list where the calendar has
many); a lane surface the routine has no connector for (`not_attached`, or a connector the person
has not connected); a local project skipped by the fan-out and why; an eligible local project with
no record in three nights; the Desktop task `MISSING`; the routine off or absent while lanes exist.

---

## Mode: status (default — "what's harvesting my projects", "is X being harvested")

Step 0, then the table, then at most three lines: what is healthy, what is broken and the fix for
each, what is merely quiet. Do not run anything. Offer the fix; do not make it.

## Mode: why <project> ("why didn't X harvest")

Step 0 for that one project, then walk `docs/HARVEST-GUIDE.md` §6 in order and stop at the first
cause found. Home first — looking at the wrong harvest is the commonest mistake. For a local
project, `/project-fanout` owns the details (`list`, `status`, `check`); call its reads rather than
re-deriving them. For a cloud project, read the routine's last run: `RemoteTrigger` `list_runs`,
then `get_run_log` for the newest, and read its `HARVEST-RESULT` block. A run log quotes the
person's mail: summarise it, never paste it.

---

## Mode: setup — cloud projects

Sets up the person's **own claude.ai routine**: hourly in their working hours, reading their
accounts with their own connectors, each limited to read-only tools, depositing into the cloud
projects they choose. Needs `RemoteTrigger` (Claude Code). Without it (claude.ai chat), point the
person to the Console's *Set up my harvest* page, or offer to harvest once now (`project-harvester`,
*Harvest once, now*). Everything the routine is made of — its prompt, which connectors to attach
with which tools, its schedule — comes from the server (`harvest_context` with `setup: true`).
**Never write the recipe or the tool list from memory, and never add a tool to a pin.**

The routine, lanes and bookmarks are the person's. Confirm the plan before any change, and change
only their own routine.

1. **Who and where** — from Step 0: projects whose home is `server` and whose access is `editor`
   (viewers cannot harvest). If they named a project, start there; if an admin asked, start from
   the request.
2. **Agree the lanes.** For each project, which surfaces feed it: `gmail`, `gcal`, `gdocs`, `jira`,
   `slack`, `github` (`outlook`, `outlook-calendar` once tested). Say plainly what that means:
   *"Your routine reads your Gmail for mail about acme-launch (keywords: …) and copies it into that
   project's inbox, where your team can see it."* A Google Doc or Jira issue that changes arrives
   again as a new revision, replacing the one still waiting. Show the scope from `harvest_context`;
   if a surface comes back `skip`, or its scope is malformed, say why and either leave it out or —
   only if the person wants — fix the manifest first through `project-state` (it is the team's,
   not this skill's).
3. **Open the lanes** with `harvest_lane` `open` (project, surfaces), one call per project. Surfaces
   replace the lane's list, so pass the whole list.
4. **Get the routine's parts:** `harvest_context` with `setup: true` and `tz` = the person's IANA
   time zone (`readlink /etc/localtime` on macOS is a strong hint; confirm it). It returns
   `routine_name`, `recipe`, `connectors` (each with `host` and `permitted_tools`), `not_attached`,
   `builtin_tools`, `model` and `schedule` (`cron`, `local`, any dropped hour).
5. **Find their connectors.** If Step 0 found the routine, reuse it. Otherwise `RemoteTrigger`
   `create` it switched off (`enabled: false`, `schedule.cron`, the `recipe` as its one user event,
   `session_context: {model, sources: <setup.sources>, allowed_tools: builtin_tools}`) **without**
   `mcp_connections`: the response lists every claude.ai connector the person has, with
   `connector_uuid`, `name` and `url`. Two things the API needs that the server does not hand you
   (both learned setting up the first routine, 2026-10-01):
   - **`job_config.ccr.environment_id` is required.** Take it from an existing routine of theirs
     (`get` → `job_config.ccr.environment_id`), or load the `schedule` skill, whose *Environments*
     list names the person's environments; use the default `anthropic_cloud` one. The event is
     `{data: {uuid: <fresh lowercase v4>, session_id: "", type: "user", parent_tool_use_id: null,
     message: {role: "user", content: <recipe>}}}`.
   - **A create without `mcp_connections` attaches every connector the person has, unpinned** — not
     none. The routine is off, so nothing can run, but step 6 is the very next call, before anything
     else; then `get` it and check `mcp_connections` lists only the pinned set.
6. **Attach only what the lanes need.** `RemoteTrigger` `update` with `mcp_connections` = for each
   entry of `connectors`, the person's connector whose `url` host equals its `host`, with
   `permitted_tools` exactly as given. Attach nothing else. GitHub is not a connector here: a GitHub lane's
   repositories come back as `sources`, attached to `session_context.sources` with read access, for commits only
   (`limited` says so; tell the person). Never give the routine push access. A needed connector missing → stop for
   that surface and send them to https://claude.ai/customize/connectors, then carry on. Name each
   `not_attached` surface and why. Always pass `allowed_tools: builtin_tools` — with none named a
   routine gets every built-in tool.
7. **Run it once:** `RemoteTrigger` `run`, wait about two minutes, then `list_runs` and
   `get_run_log` for the new session. Read its `HARVEST-RESULT` block and report what arrived per
   project and surface, and anything skipped. Summarise; never paste mail.
8. **Switch it on** only when the run succeeded and they agree: `update` with `enabled: true`. Tell
   them the schedule in their own time (`schedule.local`), runs per weekday, any dropped hour, that
   it counts against their Claude plan (about 30–60 s a run), that the runs move by an hour when
   their clocks change (set it up again then), and that they can pause or delete it at
   https://claude.ai/code/routines.
9. **Log nothing yourself** — `harvest_lane` recorded the lanes in the org's audit, and each
   deposit logs `harvest.deposited` in the project.

## Mode: setup — local projects

The local harvest already serves every eligible project on the machine; setting one up is making
it eligible and making sure the host fires.

1. **Surfaces.** The project's `manifest.yaml → surfaces` names what to watch. None → the fan-out
   skips it (*"manifest declares no surfaces"*). Propose the block (channel, Gmail keywords and
   contacts, Drive folder, repos — keys in `project-harvester`, *Manifest keys consumed*) and write
   it through `project-state` only after the person agrees.
   **Harvest a local clone.** When the code lives in a repository cloned on this machine — no
   GitHub connector, no `gh`, or a host that isn't GitHub — offer `surfaces.github.local_repos`
   (`[{path: "~/code/<repo>", name: <repo>, branch: ~}]`, with `github.enabled: true`). Check the
   path first, read-only: `python3 <project-harvester>/scripts/git_digest.py --repo <path> --since
   <7 days ago>` must exit 0 (exit 2 names the problem: not a clone's root, unknown branch, not a
   safe.directory). Say what it gives — commits digested per day, and tags in place of releases;
   no pull requests, issues or CI results — and that the harvest never fetches or pulls: new
   commits arrive once the person pulls. The clone must be on the machine that runs the nightly
   harvest. This is for local projects only; a cloud project's routine reads its own clone.
2. **Registry.** Not listed by `automation-fanout.py list` at all → `/project-fanout registry`.
   Paused or archived → `/project-fanout resume <id> harvest`, with their agreement.
3. **The Desktop task.** `MISSING` → create it from `hosts/desktop/project-state-nightly-harvest.md`
   with the scheduled-tasks tool (`create_scheduled_task`, the stub's `taskId` and `cron`, `prompt` =
   the body below its frontmatter), after confirming. `DRIFT` → `project-fanout check` owns the fix
   (the repo is the source, the task is the copy).
4. **Connectors.** The Desktop session must have the surface's connector; a missing one is skipped
   every night and its cursor never moves. Say which. Local clones need no connector, only
   `git` and `python3` on the machine.
5. **Prove it:** offer `/project-fanout run harvest <id>` — one project, exactly as the night would.

## Mode: change ("add Slack to my harvest", "stop harvesting into X")

Step 0 for the projects named. Cloud: `harvest_lane` `open` with the new full list, or `close`;
then repeat setup steps 4–7, because the routine covers every lane the person has and its
connectors may change with a lane. Local: the manifest's `surfaces` (through `project-state`) or
`/project-fanout pause|resume <id> harvest`. More frequent local harvests → a second schedule on
the Desktop task: edit the stub in `hosts/desktop/`, apply it, `/project-fanout check`.

**A different cadence** ("every two hours"): keep the hours `schedule.cron` covers and change only the step
(`0 15-23 * * 1-5` → `0 15-23/2 * * 1-5`), with `RemoteTrigger` `update`. Hourly is the floor. Re-apply the same step
when the clocks change.

**Clocks changed** (the person says so, or `harvest_context`'s `schedule.utc_offset_minutes` no
longer matches the routine's cron): repeat setup steps 4 and 6 with the new `schedule.cron`, keeping
the routine's id. The local harvest runs in local time and needs nothing.

**A project changed home.** Moved to the cloud → the local fan-out skips it from now on and nothing
feeds it until a lane opens: offer the cloud setup for it. Moved back → close its lane; the next
`/project-fanout registry` makes the local copy eligible.

---

## Rules

- **Inventory before advice, agreement before change.** Every write — a lane, a routine, a
  manifest, the registry, a Desktop task — is proposed and confirmed first.
- **Only the person's own.** Their lanes, their routine (named `project-state harvest (<email>)`).
  An admin's `ask` is a request, never an opened lane.
- **The server's recipe, the server's pins.** Never compose the routine's prompt, schedule or tool
  list; never widen a pin; never attach an unpinned connector (Microsoft 365 today), and never give a routine push access to a
  repository (GitHub is commits only, from a read-only clone).
- **Never cross homes** (see *The rule*). Never deposit into a mirror; never harvest into a local
  copy of a cloud project.
- **Mail stays summarised.** Run logs and deposits quote people's mail; report counts and subjects
  at most.
- **Hand off, don't duplicate.** Harvesting is `project-harvester`; the Desktop fan-out's status,
  re-runs, registry fields and drift check are `project-fanout`; manifest writes are `project-state`.
