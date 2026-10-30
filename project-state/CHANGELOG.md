# Changelog

## v5.7.4 - 2026-10-27

A plugin-only project can run its daily tick on its own, SR&ED records can be checked by a script, and the harvester
reads a git clone on your own machine. These close the last gaps from a pilot partner's first SR&ED run.

### Added
- **A host for the daily tick in a plugin-only install** (#109). `project-scheduler host setup` installs what runs
  `project-orchestrator tick` for one project: a Claude Desktop scheduled task, a claude.ai routine (for a project the
  cloud can reach), or the operating system's scheduler running Claude Code headless (launchd on macOS, cron on Linux,
  Task Scheduler on Windows). It shows the exact artifact and installs nothing without a yes. Headless runs are limited
  to a fixed tool list with no mail or chat connector and a per-run budget cap. What was installed is recorded in
  `automation/hosts.json`, and `project-scheduler host` reports when tick last ran and from where.
- **An executable SR&ED validator** (#117), `capabilities/sred/validator/scripts/check.py`, shipped with the
  capability. It checks the spec's validator rules, the TU → EX → ADV links, the evidence log (back-fill flags,
  excerpts for tier-2 records, `corrects:` targets), cost worksheets, `state/sred.json`, inbox proposals, and the
  `revisions:` and `review_notes` shapes. Findings carry a severity and a rule id; `--json` for machines. Exit 0 with
  no failures, 1 on any failure, 2 on a usage or input error. `gap_analysis`, `quarterly_review` and the SR&ED
  reviewer run it. It needs PyYAML and writes nothing.
- **Harvesting a local git clone** (#118). `surfaces.github.local_repos: [{path, name, branch}]` harvests commits
  from a repository on disk, one digest per repository per day, with its own cursor (`git`) and dedup keys. A
  read-only helper (`skills/project-harvester/scripts/git_digest.py`) runs only `git log`-style reads and never
  fetches, pulls or writes. A clone has no pull requests, issues or CI results, so those are skipped; tags stand in
  for releases. Local commits join the SR&ED tier-1 sweep, referenced as `<name>@<sha>`.

### Changed
- **`project-orchestrator tick` catches up the current period.** A task is due once its moment in the current period
  has passed and the period has no recorded run, the same rule as the app's own scheduler. A tick that fires late —
  a laptop asleep on Monday — now produces Monday's weekly report on Tuesday instead of skipping the week. Periods that
  passed entirely with no tick are not back-filled.
- **Every tick writes an `orchestrator.tick` entry**, with the task, period, generator and host, and one
  `dispatched: false` entry when nothing was due, so a quiet tick can be told apart from no tick.

### Fixed
- **The SR&ED sample project** had an entry logged late without `backfilled: true` and a cluster proposal using
  record types outside the vocabulary; the validator found both.

## v5.7.3 - 2026-10-27

SR&ED evidence can be confirmed and costs rolled up, the SR&ED dashboard reads every record, and the plugin no
longer assumes its user is Atomic 47. Most of this came from a pilot partner's first run of the SR&ED capability.

### Added
- **SR&ED tracker operations that were referenced but never defined** (#107). `confirm_evidence` promotes a
  harvester proposal from `sred/inbox/` into the evidence log: the source's own date, its excerpt, `backfilled` when
  late, and for a correlation cluster one entry per record with `corroborated_by` cross-references. It stops when the
  evidence predates the TU or EX it is linked to. `reject_evidence` declines a proposal and logs why.
  `rollup_costs(fy)` writes only the cost worksheet's `rollup:` block and lists discrepancies; it never edits the
  lines a person entered. `claim_status(fy, status)` records claim transitions and opens a prior fiscal year for
  back-capture. `record_tu` is accepted as `record_uncertainty`'s short name.
- **Revising a recorded TU, EX or ADV** (#108). `update_record(id, changes, reason)` edits in place and keeps every
  revision, with the prior values, on the record's `revisions:` list; moving a TU's `identified_date` needs an
  explicit yes. New events `sred.tu.updated`, `sred.ex.updated`, `sred.adv.updated`, `sred.evidence.rejected` and
  `sred.costs.rolled-up`. Evidence-log entries are still never edited: a correction is a new entry with `corrects:`.
- **The plugin ships its changelog and an install check** (#119): `CHANGELOG.md` (scrubbed of client, grant and
  people names; the publish fails if one survives, `scripts/changelog-deny.yaml`) and `VERIFY.md`.
- **Customer-run servers** gain a server directory and licence; an expired licence locks the checkout and upload
  links (W-02, W-03).

### Changed
- **The SR&ED company profile ships blank** (#114). A claimant's Layer 1 (technology baseline, fields of science)
  now lives in its own project at `sred/company-criteria.yaml`, written by `sred-onboarding`; the shipped
  `innovation-criteria.yaml` is a template.
- **`project-admin` names no Vercel team and reads no CLI login file** (#115). The read-only viewer is an opt-in
  `viewer` block in `~/.project-state/config.json`; without it, create, pull and list need no Vercel.
- **Filing a data-risk feedback issue without the confirmation pause is opt-in** (#116):
  `feedback.data_risk_autofile`, default false.

### Fixed
- **The SR&ED dashboard silently dropped records** (#110). Its YAML reader stopped at a list written without
  indentation and lost every field after it. It now reads every shape the substrate writes, matches PyYAML across
  the repository's YAML, and turns a file it cannot read into a high finding instead of a blank row. The shipped
  sample dashboard was itself truncated by this and has been regenerated.
- **Clustered evidence proposals appear on the dashboard** (#111), as one card listing their records.
- **`review_notes` has a defined shape** (#112): a string, or `{date, by, finding, severity, status, resolution}`.
  Neither renders as `[object Object]`.
- **An empty SR&ED project no longer reads as all-clear** (#113): with nothing recorded it says so.
- `sync-release-tag` runs in `plugin.json`'s repository, not the caller's working directory.

Still open from the same pilot: unattended scheduling in a plugin-only install (#109), an executable SR&ED validator
(#117) and a local-git mode for the harvester (#118).

## v5.7.2 - 2026-10-16

CC4PS workload numbers are reserved across clones, and a release names its own version again.

### Changed
- **A CC4PS workload record is a numbered kind, `workload`** (#103). Creating `workloads/W-51.yaml` through the local
  server now reserves `refs/project-state/ids/workload/51` on origin first (the number without leading zeros, so
  `W-07.yaml` is `workload/7`), the same as every other numbered record, and a second clone's W-51 is refused with
  the next free number. The workload's mailbox, `workloads/W-NN-<slug>/` with its `spec.yaml`, `claim.yaml` and
  `report.yaml`, stays free-form content. CC4PS 0.2.67 and later already read these refs when choosing the next
  number. Workload records created before this release can be reserved once with
  `services/state-mcp/bin/reserve-existing-ids.mjs --write`. Documented in `docs/SCHEMA.md` ("Workload record").

### Fixed
- **Paths in the system map had backslashes when published from Windows.** 5.7.1 shipped every skill, capability and
  pack `path` in the bundled system map as `skills\grant-ingestor` and so on. `scripts/build-system-map.py` and
  `packages/substrate-core/build-registry.mjs` now write forward slashes on every platform.
- **A release named the previous version.** Both publishers built the local server before bumping `plugin.json` and
  regenerating the system map, so the 5.7.1 bundle embedded `plugin_version: "5.7.0"`. They now bump and regenerate
  first, then build the server.
- **The local server reports the plugin version it shipped in** as its MCP server version, instead of `0.1.0`, so you
  can tell which release an install runs without comparing hashes. The cloud server still reports `0.1.0`.

## v5.7.1 - 2026-10-16

Number reservation no longer crashes the local server on macOS and Linux.

### Fixed
- **The local server could crash while reserving a number on macOS and Linux** (5.7.0). Reserving a numbered record
  runs git with nothing to read on its input; when git exited before the server finished closing that input, the
  operating system raised `EPIPE` on it, nothing handled it, and the whole local Project State server exited mid-write
  (the session's tools then answer "Connection closed"). Windows never raised it, which is why 5.7.0's own tests
  passed on the machine it was published from; CI on Linux caught it. The error is now ignored where it is harmless,
  and `test/id-reserve.mjs` passes on Linux and Windows. The seeding tool, `reserve-existing-ids.mjs --write`, failed
  the same way and is fixed with it.
- **This repository's own checks are green again.** CC4PS workload files under `project-state/workloads/` are now a
  known kind of free-form content, so substrate-core's "every file has a kind" test passes for a facility that runs
  CC4PS workloads.
- **The local server's test harnesses run inside an unattended CC4PS flight**: `test/local.mjs` and
  `test/local-race.mjs` no longer hand `PROJECT_STATE_READ_ONLY` to their own scratch servers (Atomic-47-Labs/cc4ps#6).

## v5.7.0 - 2026-10-16

Numbered records get their number reserved on origin, so two clones of a project can no longer both create R-13.

### Changed
- **A new numbered record reserves its number on origin before it is created** (#101). The 5.6.9 write lock covers
  one folder, but a project kept in git and worked on by two people is two clones, so two folders: both could create
  `risks/R-13-<slug>.yaml`, and the clash showed only at push time, after both had quoted "R-13". Now, when the local
  server's `entity_put` creates a numbered record in a folder inside a git repository, it first pushes a ref
  `refs/project-state/ids/<kind>/<n>` to origin, without force, pointing at a commit only that clone can make. Git
  refuses a second clone's push of the same ref, so exactly one clone gets each number.
  - **Which records:** every kind whose file name carries a number rather than a date, read from the kind registry:
    milestones, risks (`R-07-` and `R07-` are one number), numbered decisions and lessons (`D07-`, `L07-`),
    increments, change orders, objectives, KPIs, feedback, intel, research, SR&ED. Date-named records, replaces and
    edits reserve nothing.
  - **Taken:** the create is refused, nothing is written, and the error names the next free number.
  - **Origin unreachable** (offline, no credentials, a 30-second timeout): the create is refused with git's reason.
    It never falls back to a local-only reservation. **This is the behaviour change**: on a project with a remote,
    creating a numbered record now needs that remote reachable and pushable.
  - **No remote:** a local ref. **Not in git:** nothing changes.
  - **Opt-out:** `PROJECT_STATE_RESERVE_IDS=off` in the server's environment, for a project with one writer. **Set it
    if you work offline, or with read-only access to the project's repository**: otherwise every new numbered
    record is refused until the server can push to origin.
  - **Cost:** about 2-3 seconds and one ~200-byte push per new numbered record; nothing for edits, reads or
    checkpoints. Clones do not fetch these refs, and they trigger no workflow.

  `services/state-mcp/README.md` ("Numbers across clones") and `docs/CONCURRENCY.md` (Principle 8) describe it;
  `test/id-reserve.mjs` (13 cases, bare repositories, no network) runs in CI from source and as the bundle. The
  approach generalises cc4ps's workload-number reservation (its D61). Built as workload W-01.

### Fixed
- **Capability glances and the portfolio collector run on Windows.** The local server started every Python builder as
  `python3`, which on Windows is usually the Microsoft Store placeholder: it prints an install prompt and runs
  nothing. It now runs `python` on Windows (`python3` elsewhere), or whatever `PROJECT_STATE_PYTHON` names, and starts
  each builder in Python's UTF-8 mode (`PYTHONUTF8=1`), so a builder that prints or writes "→" no longer dies on the
  cp1252 code page. The six date labels that used `strftime("%b %-d")`, which only glibc understands, are built from
  the month and the day instead (intel glance and competitive, tender glance, research timeline, portfolio glance).
- **`test/local.mjs` and `test/snapshot.mjs` pass on Windows**, so the plugin can be published from a Windows checkout.
  `local.mjs` sets `USERPROFILE` as well as `HOME` for the snapshot index, compares member paths with either
  separator, and checks the entitlement file's 0600 mode only where the file system has POSIX modes (67 of 67 pass).
  `snapshot.mjs` expects the folder name abbreviated against the recorder's home, not the person's: on Windows the
  temp folder sits under the person's home.

### Added
- **`services/state-mcp/bin/reserve-existing-ids.mjs`**: reserve the numbers a project already has, once, from a
  clone that holds them all. Without `--write` it lists what it would reserve; with `--write` it pushes them in one
  unforced push. It runs from a checkout of this repository; it is not in the plugin. Until a project is seeded, a
  clone that lacks a file can still re-create its number (risk R-22).

## v5.6.9 - 2026-10-14

Writes hold between processes, on disk and in the cloud. The chat at `/app` and `/mobile` arrives on the cloud.

### Fixed
- **Two local servers on one folder no longer clobber each other.** A pinned Cowork server and a Claude Code
  session on the same folder are two processes, and each used to serialize only its own writes. Under a race, both
  "created" the same file, both replaced it from one `base_sha256`, log lines were lost, and interleaved copies
  corrupted YAML and NDJSON. Now:
  - a local write takes the folder's write lock (`project-state/.state-mcp-write.lock`) from its private copy to its
    commit, so the two servers take turns;
  - every file a write touches is locked with `<file>.lock` before it is checked and copied. That is
    `docs/CONCURRENCY.md` Principle 3, the lock the kanban and skills take, so the local server now waits on them too;
  - a held lock refuses the write after a short wait, and a stale one (from a writer that crashed) is taken over;
  - the base is read before it is copied, so a file changed in between is refused at commit, not overwritten;
  - a log both sides only appended to keeps both.

  `test/local-race.mjs` races two servers on one folder, and CI runs it from source and as the bundle (#100).
- **The cloud's write guarantees hold in the database, not in one process.** Inside the MongoDB transaction, a
  create-only `entity_put` of an existing path is refused, and so is a change or delete from a stale `base_sha256`.
  Concurrent log appends both survive. A commit that interleaved with another no longer caches a copy that lacks the
  other's write. cc4ps reserves workload ids this way (Atomic-47-Labs/cc4ps#3). `test/write-race.mjs` races two
  servers on one replica set (#98, #99). Deployed 2026-10-14.
- **Sign-in at cloud.project-state.app works in real browsers.** Under `Referrer-Policy: no-referrer`, Chrome sends
  `Origin: null` on a page's own posts, and every sign-in was refused. One check (`fromThisSite`) now accepts the
  site's origin, or `null` only when `Sec-Fetch-Site` says same-origin (#91). Deployed 2026-10-04.
- **The kanban: phone sign-in for superadmins.** A superadmin with no org row now gets the sign-in email. The 6-digit
  code that the installed iOS app uses resolves the session as the email link does (#96).

### Added
- **The chat at `/app` and `/mobile`** on cloud.project-state.app (`docs/CHAT-SPEC.md`; #88–#95). It runs on Atomic
  47's key, with a per-org on-switch and monthly budget. You sign in by email link, pick a project and ask.
  - **Tools:** each turn runs with the person's own tools, with the same permissions, kind-registry checks and audit
    (`via: "chat"`). Viewers are offered no write tools.
  - **Writes:** never run on the model's say-so. Each becomes one proposal, applied only when the person presses
    Apply.
  - **Photos and files:** from the camera, a picker, drag or paste. Editors' files are filed in the project inbox.
  - **Hands-free voice:** the mic is a switch, speech in uses the browser, and replies are spoken sentence by
    sentence.
  - **Suggested next steps:** shown as buttons under the answer.
  - **Pictures and charts:** an agenda, a Gantt timeline, a risk heat map, goal meters, and charts the model asks
    for, all drawn by the page from data.

  Deployed 2026-10-04 and 2026-10-05.
- **The kanban: `PS_CHAT=off`** turns the kanban's own chat off per server (`/api/chat` answers 503, and `/chat` and
  `/m` open dashboards instead) (#96).
- **A pinned folder for Cowork.** The local server can be given its own server entry with `--root`, one per project,
  for sessions whose working directory is not the project (on Windows, Cowork starts in `C:\WINDOWS\system32`). See
  `services/state-mcp/README.md` (#97).

### Changed
- **The web Console at `/app` is parked.** Its sign-in now serves the chat.

## v5.6.8 - 2026-10-02

The cloud harvest routine reads GitHub commits.

### Added
- **GitHub commits in the cloud routine.** claude.ai's GitHub access is a repository attached to the run, not a
  connector with tools to pin. A GitHub lane now harvests **commits only**, from a read-only clone. Pull requests,
  releases and issues would need push access, which a harvest never gets. With `setup: true`, `harvest_context`
  returns:
  - `sources`: the repos of every GitHub lane, for the routine's `session_context.sources`;
  - `limited`: a note that GitHub is commits only;
  - a rule against push access.

  The recipe reads each clone with `git log` and deposits one item per commit. `project-harvest-setup` attaches the
  repos, and `docs/HARVEST-GUIDE.md` explains the limit. Deployed 2026-10-02.

### Changed
- **The Console's *Set up my harvest* page** lists the repositories a GitHub lane needs, with a Copy button. It no
  longer says the routine "needs no repository".
- **The routine recipe reads 12,000 characters of raw mail** for the `Message-ID`, up from 4,000. Mail with long
  headers, such as forwarded or ARC-signed mail, had pushed the line past 4,000. Deployed 2026-10-02.

## v5.6.7 - 2026-10-01

Who harvests what: a setup skill and an operator's guide for both kinds of harvest.

### Added
- **`project-harvest-setup`**: "set up my harvest", "what's harvesting my projects", "add Slack to my harvest",
  "why didn't X harvest". It takes an inventory across both homes first, then routes each project by its home:
  - a **cloud** project gets a lane and the person's own claude.ai routine;
  - a **local** project gets the manifest's `surfaces`, a registry entry and the Desktop nightly harvest.

  It changes nothing until the person agrees. The cloud setup steps move here from `project-harvester`, which goes
  back to doing the harvest itself and keeps "harvest once, now".
- **`docs/HARVEST-GUIDE.md`**, the operator's guide:
  - the rule: a project's home decides its harvest, and a claude.ai routine can never feed a local project;
  - the two harvests side by side;
  - setup, changes, cadence, and what happens when a project changes home;
  - a "why didn't X harvest" checklist and the known gaps.

### Fixed
- **A map of Slack channels no longer reads as `"[object Object]"`** in `harvest_context`. ai-compute's manifest maps
  its output channels (`surfaces.slack.channels`, all null), and the server read the map as one channel. It now
  takes a map's named values, and an all-null map is a proper skip. Deployed 2026-10-02.

### Changed
- The routines API notes that setting up the first routine through the skill turned up:
  - `job_config.ccr.environment_id` is required;
  - a routine created without `mcp_connections` gets **every** connector unpinned, so the skill narrows them in the
    very next call.
- The cloud server routes "set up my harvest" to the new skill (and to `project-harvester` for older plugins).
- 73 skills (41 core).

## v5.6.6 - 2026-10-01

Security fixes: the Wardley map and the research charts escape what they show.

### Fixed
- **The Wardley map escapes everything from the map file** (intel 1.2.3). The builder put map front matter into a
  `<style>` block, class names and markup without escaping. Anyone who could edit a map could plant CSS, links and
  forms in every viewer's Intel map: the Console, the local Competitive report and the kanban. Scripts were already
  blocked. Every value is escaped now, and values used in CSS selectors, ids and classes are cut down to letters,
  digits, `_` and `-`. A test plants a hostile map.
- **Research chart tooltips** escape every value from the project.

### Changed
- `test/privileges.mjs` fails if the server's code opens a database collection the app's Atlas role doesn't grant.

## v5.6.5 - 2026-10-01

Every org publishes its own Console.

### Added
- **"Publish our console"** in `/project-console` (decision `2026-10-01-surfaces-directory-and-console-front-door`,
  item 2). A page that reads a connector can't be made public, so each org needs its own copy. The plugin now ships
  the Console page and its manifest in `skills/project-console/pages/` (316 KB), and `make.mjs` there writes the 17
  single pages from it. An org admin publishes them into their own claude.ai account, and Claude registers them for
  the org with `admin_org` links and checks `whoami`. Run again, it republishes to the same URLs.
- The cloud server's "No Console is set" note tells an org admin about that step (deployed 2026-10-01).

### Changed
- A47L's 18 pages are republished from the org owner's account and registered for the org. The links in
  `artifacts/project-state-views/README.md` are the new ones.

## v5.6.4 - 2026-10-01

Every project opens where it lives: the Console for cloud work, the kanban or a snapshot for local work, one answer for both.

### Added
- **`/project-console`**, the front door (decision `2026-10-01-surfaces-directory-and-console-front-door`). "Open my
  console", "where's my dashboard", "open the admin", "show me Runs": it sees which servers are connected, places each
  project by its home (cloud, local, or a read-only mirror of a local one) and opens the Console, Admin or Runs page,
  the kanban, or a snapshot through `/project-artifacts`. Someone with both gets one table: where each project opens
  and where it is changed. Reads only; the one change it can make is an org admin setting the org's page links, after
  confirming.
- **The servers say where to open things.** The local server's `project_list` carries `surfaces`: the kanban and the
  snapshots this person published from this machine. The cloud server (deployed 2026-10-01) does the same in `whoami`
  and `project_list`: the connector, the web admin for admins, and each org's Claude pages, Admin and Runs to its
  admins only. An org admin sets the pages with `admin_org` action `"links"` (audited), and the invite email links the
  org's Console. A snapshot page never carries the person's other links.
- The marketplace description now counts 72 skills.

## v5.6.3 - 2026-10-01

Where value sits and who plays where, and every battlecard drawn the way it was designed.

### Added
- **The Wardley map, `intel-map`** (intel 1.2.2, `docs/INTEL-COMPARE-AND-MAP-SPEC.md` §2). What is on a map is
  declared in the manifest (a user, a need, the components and their dependencies); where each component sits on
  the evolution axis, and who plays where, is generated from cited claims every run. A placement is inferred when
  two or more of Wardley's characteristics (ubiquity, certainty, market, practice) are evidenced, a hypothesis when
  one or none is, and never verified. Every move since the last map is listed, logged and flagged in the digest.
  `scripts/wardley.py` checks and draws it, and exports OnlineWardleyMaps text; validator check 23.
- **A Battlecards tab and a Wardley map tab**, in the app and on the Console's Intel screen. Every battlecard is
  drawn in the design first made for the Northline sample: cover, health panel, positioning, when they win and when
  we win, differentiators with the three-part test, they say / we say, objections, avoid saying struck through, and
  the evidence ledger beside the card, each claim chip coloured by its freshness. The map tab draws each map with a
  player filter and the claims behind every placement.
- **Publishers:** `--point` counts from the last release tag; the mirror, private since 2026-10-01, is checked with
  your `gh` login instead of an anonymous request. The marketplace description now counts 71 skills.

## v5.6.2 - 2026-10-01

Every competitor and us, factor by factor, with the evidence and its strength on every cell.

### Added
- **The comparison matrix, `intel-compare`** (intel 1.2.1, `docs/INTEL-COMPARE-AND-MAP-SPEC.md`). One row per
  company, us first, and one column per declared dimension. Each cell is a short phrase, the claims behind it,
  its evidence state (evidenced, inferred, unknown, no claim, contested; stale marked) and, on a scored
  dimension, a score on that dimension's 1–5 rubric. An unknown or empty cell is never scored and never counts
  as zero. Totals per audience are always shown with the share of the weight the evidence covers, and a company
  is ranked only when that share reaches 60%. `scripts/compare.py` computes every number and refuses a matrix
  built on missing, superseded or one-sided evidence; validator check 22 recomputes it.
- **"How do they compare?"** on the Competitive report and the Console's Intel screen: the grid shaded by score,
  totals with their coverage, the companies not yet ranked and why.
- **Readable projections** (from 5.6.1's cloud release): the latest brief, every profile and every battlecard
  open in place on the Competitive report and in the Console.
- **`scripts/publish-plugin.sh --point`** (`-Point` on Windows): the next point release, read from
  `plugin.json`. Iterations now ship as point releases.

## v5.6.1 - 2026-10-01

### Fixed
- **The manifest is stamped in `meta`, not at the top level.** The local server's `entity_put` and `entity_patch`
  stamped every YAML file with a top-level `last_modified` / `last_modified_by`; the manifest keeps those in its
  `meta:` block, so each write left a second pair that disagreed with it. A file whose `meta` block carries the stamps
  is now stamped there, touching only those two lines, and a leftover top-level pair is removed on the next write. The
  cloud server had the same fault and was fixed on 2026-10-01 (#74).

## v5.6.0 - 2026-10-01

Each person's own Claude harvests their mail, calendar, documents and Jira into cloud projects; the cloud reads
nobody's accounts.

### Added
- **"Set up my harvest" in `project-harvester`** (M52 PH.5; decision `2026-09-30-person-side-harvest-no-provider-keys`).
  For a cloud project, the skill opens the person's harvest lanes and creates their own claude.ai routine through
  `RemoteTrigger`: hourly in their working hours, each connector limited to its read-only tools, the routine's prompt,
  pins and schedule all served by the cloud (`harvest_context` with `setup: true`), never written from memory. The
  routine deposits through `deposit_inbox`; Project State holds no Google or Microsoft key. It also harvests once on
  request in any chat. Plan: `docs/PERSON-SIDE-HARVEST-PLAN.md`.
- **Google Docs and Jira on that path.** A document or issue that changes arrives again as a new revision and replaces
  the one still waiting in the inbox. Drive is limited to four read tools and Atlassian to four of its 21 (comments
  through `executeRead`); a Jira comment restricted to a role, group or a service project's agents is never copied.

### Changed
- **The cloud says it does not harvest.** The cloud scheduler has no harvest phase; the Inputs screen of a cloud project
  names who feeds each source and how fresh it is, or "nobody yet", or "computer only" for scsiwyg, Confluence and
  Linear. The daily digest reports a person's stale harvest and the surfaces nobody feeds. Local projects and the
  kanban are unchanged: a project on a computer is still harvested there.

### Fixed
- **A routine's bookmark comes from the server's clock.** A routine has no clock of its own; when it found nothing it
  guessed the time, ahead of the server, and every empty bookmark was refused.

## v5.5.0 - 2026-09-30

Projects record the large binaries their tools download, so a clean install stops fetching them again.

### Added
- **A heavy-artifacts register, so clean installs stop re-downloading large binaries** (FB-001 from
  CanRentPro, issue #47). mongodb-memory-server's MongoDB binary, about 780 MB on Windows, was cached
  inside each app's `node_modules`, so every clean install downloaded it again, once per app: 718 s of
  the W-04 re-run's first check. Moving it to one git-ignored `.cache/` at the repository root took a
  clean `npm ci` to about 2 minutes. `manifest.yaml` now has a `caches:` list (artifact, tool, size,
  path, setting). `project-onboarding` Q1.10 and `project-scaffolder` Step 5 ask about it once, for code
  projects only, after scanning the package files for known tools. `project-state validate` reports a
  cache path that is not git-ignored or sits in `node_modules`. The scaffolder adds `.cache/` to
  `.gitignore` when anything is listed; it never edits the tool's own setting. Reference:
  `skills/project-state/references/heavy-artifacts.md`.
- **`templates/playbook-long-commands.md`**, a section to paste into a project's build playbook: the
  shared `.cache/` rule, the CI cache step, and the long-command pattern. The Cowork device bridge stops
  responding for the whole of any command over about 60 s, so anything expected to take over 45 s runs
  in a visible window that writes a log, and Cowork polls the log in short calls. Includes
  `run-visible` wrappers for PowerShell and macOS.

## v5.4.5 - 2026-09-30

SR&ED evidence, tender events and research logs can be written through the project-state server.

### Fixed
- **SR&ED evidence can be captured when the plugin's local server handles the project.** The server's
  only append tool wrote the activity log, and `entity_put` refuses every `.ndjson`. Skills must write
  through the server when it handles their project, so an evidence entry for `sred/evidence-log.ndjson`
  had no route at all, and neither did `tenders/events.ndjson` or a research log. `log_append` now also
  takes `path` and `entry`, appends that one line to any append-only log the kind registry knows, and
  signs it with `appended_by` and `appended_at`. The cloud server gets the same tool.

## v5.4.4 - 2026-09-29

A portfolio reads its members' large files; the in-app scheduler runs SR&ED's reports.

### Fixed
- **The portfolio collector reads large files through the server.** A member whose `documents/index.yaml` (or any file
  it reads) was over 60,000 characters was refused as malformed. `get_entity` now serves a large file in pieces
  (`offset`, `next_offset`), and the collector joins them. Found on the first real portfolio: `project-state` and
  a pilot facility both have documents indexes over 100 KB.
- **A risk scored in words no longer crashes a collect.** Members write `score: high`, `score: medium` or a stray
  value; the collector now reads a number, digits, likelihood × impact, or the word on the same 1–9 scale.
- **The in-app scheduler runs the sred capability's reports.** The kanban refused any matrix entry whose generator
  was not on its allow-list, and `project-sred-tracker` and `project-sred-reviewer` were not, so the weekly capture
  digest, quarterly review and T661 review never ran from the app (on an appliance, the only scheduler). Both are
  allowed now, and a test checks that every generator a shipped pack names is allowed or excluded on purpose.
- **Appliance jobs load the active skill profile.** `ks-app` starts its jobs with its own home folder, which had no
  link to the active skills, so every job it started ran with none. The appliance bootstrap now makes the link.

## v5.4.3 - 2026-09-29

A local portfolio reads its cloud members unattended; and the cloud scheduler's Runs page.

### Added
- **A portfolio on disk reads its cloud members unattended.** The collector takes a service token per org from
  `~/.config/project-state/mcp-tokens.json` (`{org: token}`, 0600, as `psctl token mint --into` writes it; a viewer
  token scoped to the portfolio's members) and the cloud's address by default, so the weekly collect of a local
  portfolio reads cloud members with nobody signed in. A token file others can read is refused. `build-registry.py`
  lists the cloud projects every token can see. (Portfolio capability.)

### Added (cloud tier; not in the plugin)
- **The Runs page**, in the Console under Admin (and as its own page): the cloud scheduler for an org's admins — each
  cloud project's last run per job, the run-now queue, recent runs with their digest lines, the scheduler's check-in and
  budget, and its tokens. Controls: turn phases on or off for the org, run now, stop a running worker, cancel a
  request, pause and resume a job, revoke a token (`scheduler_admin`, audited). The scheduler checks every two
  minutes.

### Fixed (cloud tier; not in the plugin)
- **A service token can no longer drop portfolio proposals.** `portfolio_promote` is offered only to people, and refused
  for a service token: a drop into a member needs a person who approved it, and the cloud scheduler's workers are
  unattended. Before, only the tick prompt kept them from it.
- **Confirmed actions work in the published Console.** The artifact viewer never shows `window.confirm` (it returns
  false), so every action that asked first did nothing there: disabling or removing a member, deleting inbox files,
  returning a project to the cloud, and the Runs controls. The pages now ask in their own dialog.

## v5.4.2 - 2026-09-29

A fix to the portfolio collector, and the cloud scheduler.

### Fixed
- **A portfolio's second weekly collect no longer crashes.** When a member was unchanged since its only snapshot,
  the collect kept an "unchanged" marker as the member's previous snapshot, and the weekly note read milestones from
  it (`KeyError: 'milestones'`), failing the whole collect. The note now says "unchanged since <date>" for that
  member. Found by the cloud scheduler's two-week test; regression check in `services/state-mcp/test/collector.mjs`.

### Changed
- The local server shares the cloud writer's refactored commit path (`services/state-mcp/src/writer.mjs`). No change
  in behaviour: `test/local.mjs` passes from source and against the bundle.

### Added (cloud tier, cloud.project-state.app; not in the plugin)
- **Service tokens.** Per-org `ksm_` identities for unattended work: scoped by access, projects and tools, revocable,
  never admin, their writes signed `<skill> (automated)`. `admin_token`, `psctl token` (decision
  `2026-09-28-service-tokens-and-cloud-scheduler`).
- **The cloud scheduler** (M49), live since 2026-09-29: a portfolio's weekly collect for projects whose home is the
  cloud, and harvest, tick and digest as headless workers once an org switches them on; runs in `ps_control.fanout`
  (`fanout_status`). `docs/CLOUD-SCHEDULER-PLAN.md`.
- **Collects no longer hold the server's write lock**; they commit at the end, rebased onto what changed meanwhile.

## v5.4.1 - 2026-09-29

A fix to the local server and the research rulings, which missed 5.4.0.

### Fixed
- **The local server no longer writes when it reads.** `view_wiki` and `view_wiki_page` reached the kanban
  library's lazy wiki index build, which wrote `wiki/.index/` and logged `wiki.graph.rebuilt` — even on a read-only
  server (`PROJECT_STATE_READ_ONLY`) and while `/project-artifacts` recorded a snapshot. A missing index is now built
  in memory for a read; only `wiki_save` persists it. The app is unchanged.

### Decided
- The research spec's open questions (§13) are ruled as built, and `source_relevance` is append-only after a mandate
  locks (decision `2026-09-28-research-open-questions-ruled`).

## v5.4.0 - 2026-09-28

Two capabilities grow up. **Research** arrives as the fifth capability plugin: questions held as mandates, evidence
graded and attacked before anything ships, and a Library of the studies and articles it produced (PR #53). **Intel
1.2** watches competitors on a schedule, learns from closed deals, and measures itself against the OCI evaluation
harness (PR #52). The plugin now carries 69 skills, 21 packs and 5 capabilities.

### Added — the research capability (0.1.0, `docs/RESEARCH-CAPABILITY-SPEC.md`)

Question-driven, evidence-graded research, held natively in a project — the fifth capability plugin.

- **Six record kinds:** mandates (the questions and the contract for answering them), steps, append-only findings graded
  on source tier, confidence, epistemic status and independence, challenges ruled by a person, longlist candidates, and
  change records. The state server enforces the append-only rules (a finding's claim never changes; only its status and
  lineage advance; a challenge is ruled, never rewritten).
- **Eleven skills and four fan-out subagents:** onboarding, mandate, ingest, step, deepweb, longlist, redteam, brief,
  walk, retro, ask; the fetcher, ingestor, comparer and scorer subagents are read-only and return JSON the parent merges.
  Research is the first capability to ship subagents: the build places them in the plugin's `agents/`.
- **Gates are computed:** `validator/scripts/check.py` (the whole validator, the lock checklist, the evidence gate);
  `scripts/walk.py` classifies every night's candidate action auto or gate, remembers what it tried against an
  unchanged project, fetches a page a challenge names before parking the ruling, and halts on an invalid project.
- **The views:** At a glance, Evidence, What changed, and a new Timeline report (each mandate's life, the evidence
  runway, the walk night by night), all from one model; and a **Research** tab in the Console and its own artifact page
  (`ps-research.html`) — an interactive dashboard, timeline and faceted evidence register.
- **The Library — what the research concluded:** each mandate's study (shipped, draft, blocked or living) and topic
  articles compiled across mandates (`research-brief article`), as a static report and a Console tab with a reader.
  Every citation is re-read against today's evidence: superseded, challenged, stale and provisional findings are
  flagged in the text and in an evidence ledger, and a document whose evidence has moved says so and reaches the digest.
- **The research-default pack:** the nightly walk, the weekly red-team sweep and delta, the glance after each walk.
- **Migration** from a standalone `.research-state` facility (`scripts/migrate_research_state.py`), proven on a
  scratch copy of a real one (82 findings, 13 challenges, 19 candidates).
- `scripts/test-research.py` in CI; `view_capability research` on the local and cloud servers.

### Added — intel 1.2: watch, learn, measure (`docs/INTEL-CI-SPEC.md` §14)

The intel capability reaches Open Competitive Intelligence v0.1 **L2 Connected**, and **L3 Operated** where
its evaluation harness passes.

- **`intel-monitor`** — the scheduled change monitor. A watch list (`intel/watch.yaml`) of sources per
  competitor, read through connector capabilities (`web.read`, `deals.read`, `documents.search`) with
  documented source-class defaults. Change is written as a claim delta: superseding claims and change events
  classed material / notable / noise, each with its owners and a recommended action; noise never reaches the
  digest. Weekly matrix entry `intel-weekly-monitor`; digest checks `intel.change-material`,
  `intel.monitor-overdue`, `intel.unwatched-competitor`.
- **`intel-winloss`** — closed deals into learning. A new kind, `intel-winloss` (`INT-W-NNN`), keeps the
  seller's reported reason and the buyer's evidenced reason in separate fields; the record is append-only
  except the buyer evidence that arrives later, and the shared validator refuses any rewrite of the seller's
  reason. Analyses state the sample behind every pattern, segment before generalising, flag reversals and
  report the seller/buyer divergence rate. The tender capability's won / lost offer it. Quarterly matrix entry
  `intel-quarterly-winloss`; digest checks `intel.winloss-unrecorded`, `intel.winloss-no-buyer`.
- **The evaluation harness (OCI §13).** A golden set generated with the fixture
  (`capabilities/intel/examples/fixture/golden.yaml`: 6 entities, 21 known facts, 5 unknown questions,
  4 historical deals); `scripts/eval_metrics.py` computes the six headline metrics over any project's
  projections; the fixture baseline passes every threshold (`eval-results.md`), and each metric fails on a
  copy doctored to break it. Six agent-run cases under `evals/` (`--tag intel`).
- **Migration from a standalone intel-state facility** (`scripts/migrate_intel_state.py`,
  `intel-onboarding migrate`): fixed ids, every old id rewritten, drifted field names mapped, nothing dropped
  (`legacy:`), re-run safe, the old tree untouched. Verified on a pilot facility (32 entities, 32 signals,
  7 mandates).
- The Competitive report and the Console's Intel view gain *Is the watch list being read?* and *What are closed
  deals teaching us?*; a Win-loss board and a *Watch and learn* setup stage in the app.
- `scripts/test-intel.py` runs in CI (Substrate workflow).

### Changed
- `intel-brief`, `intel-deal-coach`, `intel-battlecard`, `intel-ask` and `intel-ingest` read win-loss records
  and monitor runs, always with the sample; the harvester follows a documented per-category source ordering.
- The fixture's projections were corrected where the harness found real defects: a deal brief that cited one
  side of an open conflict, and uncited lines in a profile and a deal brief. Two stray files committed with the
  1.1 fixture (a kanban chat and a cost log) are gone, as the samples build already removed them.

## v5.3.0 - 2026-09-28

A project on this computer can now be shown as a Claude artifact. The page is a private, read-only snapshot, and
refreshing it republishes to the same link (PR #50, following snapshot mode in #49).

### Added

- **`/project-artifacts`: a project's screens as a private Claude artifact.** "Make me a snapshot of the project"
  records the Project State Console (Today, milestones, calendar, risks and decisions, goals, reporting, the
  capability glances, the wiki and the file drawer) filled with the project's own data. It reads through the local
  server, read-only, and publishes the page privately with the Artifact tool. "Refresh my snapshot" records again and
  republishes to the same URL. The page carries its data inside and declares no capabilities, so it opens where the
  `host:` bridge is refused. Snapshot URLs are kept per person in `~/.project-state/snapshots/index.json`, not in the
  project.
- **The plugin ships the recorder** beside the local server: `server/state-snapshot.mjs` and the page it fills,
  `server/artifacts/project-state.html`. `build-local.mjs --plugin` builds both and runs `test/snapshot.mjs` on the
  shipped files before `.mcp.json` is written.
- **A new surface, `artifact`,** in the system-map vocabulary.

### Changed

- `artifacts/project-state-views/snapshot.mjs` is now a thin wrapper over the recorder the plugin ships
  (`services/state-mcp/src/snapshot.mjs`). It records one folder, without the workspace registry.

## v5.2.0 - 2026-09-28

The team's plugin moves to version 5. Until now claude.ai's org copy stayed on the 4.11 content (5.0.1, then 5.1.1)
while the public marketplace carried v5. This release brings them back together (M51 CA.7, decision
`2026-09-28-org-plugin-v5-ca7`).

### Changed

- **The org copy gets v5**, the same build as the public marketplace:
  - **the local project-state server** for projects on disk: skills read and write through it, and every change is
    checked against the kind registry, refused on a disk conflict, and signed;
  - **the Project State connector** for cloud projects, unchanged;
  - everything since 5.0.0: several projects per local server, portfolio tools, capability entitlements, and
    capability glances that find their builders.
  Members without Node 20.10 or later, or where the server cannot start, keep working on the files as in 4.11.
- **The local server has its own instructions.** It used to send the cloud server's text, which says only projects
  whose home is "server" take writes; on a local project that could make Claude refuse writes the server accepts.
  It now describes itself, and says so when it runs read-only (`PROJECT_STATE_READ_ONLY`).
- **The publishers push one build to both repos**: the distribution repo (the org copy, by webhook) and the public
  mirror, the mirror as an ordinary commit on its own history. The two repos stopped sharing history on 2026-09-28,
  so `git push --mirror` is gone. The hold on the org copy is removed. `scripts/publish-marketplace-only.sh` remains
  for a release the org copy must not take.

### Fixed

- **The publishers could ship a stale file without saying so.** Both compared files by size and time
  (`rsync -a`, `robocopy /MIR`). In a fresh checkout, where the sources and `plugin/` share a timestamp, a
  one-character edit that kept the size was skipped. The 5.2.0 dry run built 15 packs with `compatible_core <5.0`
  although their sources said `<6.0`. Every copy now compares contents (`rsync --checksum`, `robocopy /IS /IT`).

### Staying on 4.11

Anyone who wants the 4.11 behaviour (files only, no local server) can keep it as a personal plugin: a kit built from
tag `v5.0.1`, labelled 4.11.0, with instructions. See `docs/PLUGIN-DISTRIBUTION.md`, "Staying on 4.11".

### Not in this release

- **Artifacts that read a local project.** Publishing an artifact that declares a `host:` server is refused from
  desktop-app Code sessions on this account, even with the local server connected. Artifacts reach cloud projects
  through the connector.

## v5.1.3 - 2026-09-28 (public mirror only)

### Fixed

- **The plugin uploads to claude.ai.** Its upload refused 5.1.2 twice over: the description was 835 characters (limit
  500), and `project-doc-suite-generator/SKILL.md` gave its `map:` key twice. The public build now takes a 424-character
  description from `.claude-plugin/plugin-description.txt` (`plugin/` on main stays held at 5.0.1), and the build fails
  on a description over 500 characters or a repeated SKILL.md frontmatter key.

## v5.1.2 - 2026-09-28 (public mirror only)

### Fixed

- **Capability glances in the plugin** (`view_capability` for SR&ED, intel, intel-competitive, tender) looked for their
  builders in a `vendor/` folder the plugin does not ship, and failed ("can't open file …/vendor/intel/views/…").
  The builder path was fixed when `capabilities.mjs` loaded, before `local.mjs` pointed it at the plugin's
  `capabilities/`; it is now found when a glance is asked for, starting with `capabilities/` beside `server/`. The
  shipped-file test now runs without the builder override the plugin never has, and checks the SR&ED and intel glances
  (60 checks); 5.1.0 fails it with the errors seen in the plugin.

## v5.1.0 - 2026-09-28 (marketplace only)

The v5 plugin again, on the public mirror only: claude.ai's org copy stays on the 4.11 content until M51 CA.7
(decision 2026-09-28-public-marketplace-v5-org-stays-4-11). The first publish went through the distribution repo,
which is the org copy's source (claude.ai webhook), so the org copy ran v5 from 15:06 to 18:49 UTC; **v5.1.1**,
the 4.11 content re-numbered, restored it there. The public mirror stays on 5.1.0.

### Fixed

- **`entity_put` with `data` on a `.json` path** wrote YAML and was refused; it writes canonical JSON (#37).
- **`entity_patch` on JSON files** (`state.json`) edits the named members in place instead of refusing (#39).
- **Numbered decisions, risks and lessons** (`decisions/D01-…`, `risks/R01-…`, `lessons/L01-….yaml`, as cc4ps
  names them) are the same kinds as the dated forms; `decided:` / `captured:` satisfy `date` (#41).

### Added

- **`PROJECT_STATE_READ_ONLY=1`** makes the local server offer only read tools (every tool not marked
  `readOnlyHint` is left unregistered), refuse writes in its store, and report `access: viewer` with the reason
  in `project_list`. For sessions that must not write because another is the project's single writer: cc4ps's
  executor sessions, where its decision D01 makes Cowork the only writer. cc4ps's autopilot launcher sets it.

### Changed

- **`plugin/` changes only in the release commit.** claude.ai syncs the org's copy of the plugin from
  `main`. In v5.0.0 the PR brought `plugin/.mcp.json` there an hour before the release commit brought the
  server it starts, and a desktop app that fetched in between failed with `Cannot find module
  …/server/state-mcp-local.mjs`. Now:
  - `.mcp.json` is written by the build, after the server has passed its end-to-end test;
  - `scripts/check-plugin-untouched.py`, run by `.github/workflows/plugin-guard.yml`, fails any pull
    request whose non-release commits touch `plugin/`;
  - see `docs/PLUGIN-DISTRIBUTION.md`.

## v5.0.0 - 2026-09-26

The major version is the transport: skills no longer have to write the project's files themselves.

### Added

- **The local project-state server.** The plugin now starts an MCP server, `project-state`, over the
  `project-state/` folder of the project you are working in. It has the same tools and views as the cloud
  server at cloud.project-state.app (47 of them: `project_list`, `get_entity`, `entity_put`,
  `entity_patch`, `log_append`, `milestone_update`, `view_today`, `due_between`, …). Every write:
  - runs through one writer and is checked against the kind registry (`packages/substrate-core`);
  - is refused if a file it touches changed on disk meanwhile;
  - is attributed and logged.
  Claude Code shows it as `plugin:project-state:project-state`.
  - **Who writes are signed as:** `$PROJECT_STATE_ACTOR`, else `git config user.email` (never a no-reply
    address), else the operating-system account. `project_list` says which.
  - **Where it looks:** `$PROJECT_STATE_DIR`, else the nearest `project-state/` or `.project-state/` above
    the session's directory. Started where there is none, it stays up, says so, and picks up a folder
    scaffolded later in the session.
  - **A folder whose project moved to the cloud** (`home: kind: server`, written by `ps-move`) is served
    read-only, naming where the project went.
  - **Needs Node 20.10 or later.** Without it the server does not start, and the skills work on the files
    exactly as in v4.
  - One 2 MB file, `server/state-mcp-local.mjs`, built from `services/state-mcp` by both publishers. Each
    publish runs the end-to-end test (21 checks) against the file that ships.
- **Skills choose their transport** (`project-state`, "Substrate binding"). When a project-state server is
  connected and lists the project, whether this local one or the Project State connector in claude.ai,
  reads and writes go through it; otherwise through the files. The daily loop names entities by kind and
  id, not by path:
  - `project-milestone-manager`, `project-status-reporter`, `project-orchestrator` and `project-inbox` are
    marked `binding: mcp-ready`;
  - each carries a "Which home" rule;
  - the build proves no substrate path is left in their bodies.
  Kinds and their paths are generated into `skills/project-state/references/kinds.md` from the registry.
- **`map.requires`** on every skill (memory, python, shell, git, local-fs, connector:<id>). The system map
  lists where each skill can run: 35 everywhere, 8 locally and on a runner, 11 locally only.

### Changed

- **`project-orchestrator`:**
  - an *urgent deadline* now means one someone outside the team holds you to: `fixed: true`, or a funder
    or customer group, as in the orchestration oracle. A due internal report, even one due today, is a
    pending report and ranks below a gate blocker;
  - a monthly report is not due before its lead-time window opens.
- **Pack `compatible_core` ranges** widened from `<5.0` to `<6.0` on the 16 packs that declared them. v5
  changes how skills reach the substrate, not the pack format.

### Fixed

- **Monthly reporting cadences are computed** (`day: 15`, `last-business-day`, `first-friday`,
  `second-tuesday`). They were listed as "not computable" wherever the server computed due dates. The
  rule now agrees with the orchestration oracle on every monthly cadence the packs ship.
- **`entity_patch` of a multi-line value** (a milestone's `technical_progress`) no longer rewrites the
  whole file: only that value's lines change, and comments and quoting stay.
- **The orchestration oracle** now treats a milestone the phase gate names as gate-blocking when it has
  missed its start, not only when it is overdue.

### Evals

- **Every write check is binding-agnostic.** It reads the files the run leaves behind, or matches
  tool-call inputs, so the daily loop scores the same over the local server and over files. Checks that
  matched the whole trace were vacuous: the trace carries the loaded SKILL.md.
- **`llm` graders ask one question each,** with the state they check against in the rubric; the
  orchestrator's order is a regex over the reply's numbered items. Measured with a replay suite; see
  `evals/README.md`, "Writing an `llm` grader".
- **The fixture has an operator** (Sam Okafor), who signs writes.

## v4.11.0 - 2026-09-24

### Added

- **Project types: work, accountability, rhythm** — onboarding stops assuming a software team or a
  funded consortium. It now asks three questions, each answered from the pack catalogue: *what is
  this project trying to make happen* (one `axis: work` pack → `project.kind`), *who needs to hear
  how it's going* (`axis: accountability` packs, with `sponsor-internal` pre-selected), and *how does
  the work move* (a phase preset). Spec `docs/PROJECT-TYPES-SPEC.md`; decision
  `2026-09-24-project-types-three-axes`. Ships as:
  - **Five packs** — `work-general`, `work-campaign`, `work-event`, `work-ops-cycle` and
    `sponsor-internal` (the missing "my manager or exec" accountability). `agile-default` is
    reclassified as the *Software product* work type and gains seeds.
  - **Three presets** — `stage-gate-default` (the generic ladder), `countdown-default` (planned back
    from `phases.anchor_date`), `cycle-default` (one increment per period).
  - **Seeds** — packs can ship draft milestones and risks, dated by expression (`anchor-120d`,
    `start+2w`, `50%`), plus KPI suggestions the Goals tab offers. `project-scaffolder seed-pack`
    queues them as outbox drafts and `adopt-seeds` writes them once approved, via the deterministic
    `skills/project-scaffolder/scripts/seed_pack.py`. The kanban runs it when it creates a project.
  - **Pack fields** — `pack.axis`, `picker` (listed / label / blurb / signals / preselected),
    `defaults.preset`, `asks`, `provides.seeds`. `check-pack-integrity.py` validates them and
    refuses `picker.listed: true` on a pack that ships no profile or seed —
    `open-source-community` is now unlisted until it does.
  - **Engine** — matrix entries may declare `active_phases` (the event's daily digest runs only in
    the final countdown), and a `deadline` with no `recur` fires once on its anchor ± `offset_days`.
  - **Front doors** — `project-onboarding` Chapter 1, `project-scaffolder` Step 1–2,
    `project-intake` §1b, the kanban home wizard, the full-setup form and the onboarding pack picker
    all read the catalogue from manifests. Re-orient offers a work type to facilities without one.
  - **Second wave** — `work-sales-pursuit`, `work-research`, `work-partnership`, `work-org-change`,
    `work-content`.
  - **Re-anchoring** — `seed_pack.py reanchor` (`project-milestone-manager reanchor()`) moves seeded
    milestones when the event/launch date slips, leaving hand-dated and completed ones alone; the
    kanban scheduler recomputes anchored deadlines from the current anchor on every tick.
  - **Review wording** — the kanban names the review-pack button after the meeting the project's
    review-meeting profile defines (*Draft Quarterly Business Review pack*, *Draft Steering Review
    pack*) instead of "Steering Committee" everywhere.
  - **Tests** — `scripts/test-project-types.py` (108 checks), two vitest suites (kanban total 227),
    ten generated eval cases `evals/onboarding-classifies-*`.

- **Fan-out automation hosts + `project-fanout`** — the three Claude Desktop scheduled
  routines (nightly harvest, nightly tick, morning digest) now serve every project on the
  machine by looping a workspace registry instead of hardcoding one working directory, so
  seven projects no longer mean twenty-one near-identical routines. `scripts/build-registry.py`
  surveys the disk and writes `registry.json` at the workspace root (the file the kanban's
  `readRegistry()` had always been waiting for); `scripts/automation-fanout.py` lists eligible
  projects per phase, renders `hosts/prompts/<phase>.md` for one project, and records results
  in an append-only fan-out log; `hosts/desktop/*.md` are the versioned routine stubs and
  `scripts/check-desktop-tasks.py` reports drift against what is installed. The morning digest
  is one consolidated read across all projects, ordered by severity, and it reads the fan-out
  log first so a project whose night phases did not run is a 🟡 line rather than a silence.
  The new `project-fanout` skill is the slash-command surface: status, eligibility, digest,
  single-project re-run, registry automation fields, drift check. Contract:
  `docs/AUTOMATION-HOSTS.md` §Fan-out.
- **Inline project education** — a teaching-concierge layer for audiences who carry real
  governance and accountability obligations without formal PM literacy (the motivating case is a
  First Nations band-management organization; the design generalizes to community-based
  organizations, first-time grantees, and founder teams). Not PM 101: the project's own state is
  the entire curriculum. Three surfaces: the **literacy briefing** ("how this project is
  functional and dysfunctional, in these specific ways, and one practical move per finding"),
  **inline why-lines** on artifacts the user already asked for (bounded, level-governed, fading
  as fluency grows), and **grounded explain** ("what is a risk register and why do we care —
  *here*"). Ships as:
  - `docs/INLINE-EDUCATION-SPEC.md` — design principles (teach from state, functional-first
    pairing, graduated withdrawal, strengthen-never-condescend, OCAP®-aware data-sovereignty
    teaching per risk R-21), surfaces, pattern library contract, data model, backend rail.
    §3.1 is the **plain-language contract**: at newcomer level every teaching moment is built
    from five plain questions in order — what was done, why it matters, what's next, why that,
    how to do it — spoken register, humanized numbers, names before codes. The first demo run
    read too steep for an uninitiated user; the contract exists so that failure mode is a spec
    violation, not a style choice.
  - `docs/VOICE-LAYER-SPEC.md` — the generalization: every sentence the system utters is a view,
    and the audience is a render parameter. One layer, three dials — register (newcomer contract,
    already shipped), lexicon (audience's words + framing anchor + per-audience forbidden
    vocabulary), and natural language (language packs with named steward, named reviewer, and
    community-verified status; uncovered strings fall back visibly, unreviewed free prose renders
    amber — review-not-author extended from facts to words, OCAP® extended from data to language,
    per R-21). Audience profiles live at `audiences/<id>.yaml` (`templates/audience-profile.yaml`),
    addressed by the reporting matrix's existing stakeholder groups; the education profile becomes
    a facet of the audience profile with a read-fallback migration. `project-orchestrator` gains a
    Voice section: the daily read renders in the default audience's voice — routing unchanged,
    words only. Strictly additive: no `audiences/` directory, no behavior change.
  - `skills/project-educator/` (P2) — `briefing` / `explain` / `pathway` / `profile`, plus the
    annotation policy host skills apply to their own drafts; pattern library in
    `references/dysfunction-patterns.md` (5 functional + 8 dysfunction patterns).
  - `templates/education-profile.yaml` — seeds `project-state/education/profile.yaml`
    (audience, level, annotations, governance-anchor framing, vocabulary map, muted topics);
    teaching moments log to `education/log.ndjson`. Both files route through `project-state`
    like every other write. Skill count: 42 → 43.

### Fixed

- Today, Blind spots and the Reporting matrix ran a generator-wide canned action for a specific
  report: any `project-funder-reporting` entry offered to draft a *quarterly claim*, any
  status-reporter entry drafted *weekly status*. Report rows now run their own matrix entry
  (`matrix:<entry-id>` through `/api/action`).
- Profile resolution (PACK-SPEC §6) is by axis — accountability, then work — not list position.
- `scripts/build-eval-cases.py` had drifted from the current `claude plugin eval` schema, so every
  case in `evals/` failed to load: `covers:` is not a prompt key (now folded into `tags`), an `llm`
  grader reads `focus` with its rubric in the body, `scaffold_script` is a path (fixtures are now
  `fixture.sh`), and the repo root does not resolve as a plugin (cases now target `../../plugin`).
- **Most of the suite was invisible to the model.** Claude Code shows skill descriptions under one
  shared listing budget; in a clean install about 22,000 characters of this suite's 46,400 were
  shown, alphabetically, and every later skill — `project-orchestrator`, `project-inbox`,
  `project-milestone-manager`, `project-phase-gate`, `project-status-reporter`, … — appeared as a
  bare name. "What should we do today?" therefore never reached the orchestrator (0 of 3 eval runs
  invoked it). All 56 descriptions are now ≤250 characters and trigger-first (10,675 in total); the
  full text moved into each skill body. `build-system-map.py` fails the build on a description over
  250 characters or a suite over 15,000. After the change all 55 listed skills carry a description
  and the orchestrator fires on every orchestration case.
- `project-orchestrator` could close its briefing by recommending routine work ahead of a deadline
  due today ("I'd go 3, 1, 4, 2"); any sequence now follows the ranking, with prerequisites folded into
  the higher item's next step.
- **Records named a skill as their author.** Nothing defined who `created_by` / `last_modified_by` /
  the log's `actor` is, so a dictated decision was stamped `created_by: project-state`, SR&ED
  templates shipped `created_by: "TODO"`, and `seed_pack.py` used its own name. `project-state` now
  defines it once (*Who the actor is*): deposit token → `$PROJECT_STATE_ACTOR` → the signed-in person →
  git `user.email` (never a no-reply address) → ask. The subject of a record goes in `decided_by` /
  `owner`; only runs no person started use `<skill> (automated)`. The kanban passes the requesting
  person to seeding. Verified by eval: the decision case now records a person as `created_by`.
- `project-milestone-manager` overwrote `technical_progress`; its own example showed a replacement.
  The narrative now accumulates as dated lines — found by the milestone eval, confirmed fixed.
- Four Harbour graders tested the wrong thing: "no entity writes" matched the fixture's own activity
  log, "sent nothing" matched the status-reporter skill's prose, the weekly report was judged
  against a frozen fixture with today's real date, and the decision rubric rejected a people id for
  the decider. All four now assert what they mean.
- The kanban's home wizard and full-setup form offered `sred-canada` — a capability's bundled pack —
  as a project pack, from hardcoded lists; both now read the catalogue and never show capability
  packs.
- New kanban projects were written with `current_phase: 01-planning` whatever the preset (not a
  phase of `agile-default`); the first phase of the chosen preset is now used.
- `project-scaffolder` Step 2 offered the grant ladder (LOI / Approval / Planning / Execution) as the
  starting phase for every project; it now lists the chosen preset's own phases. Its preset
  resolution step "the pack's default preset" can now fire — no pack used to declare one.
- `docs/PACK-SPEC.md` §6 still described a single `active_pack`; activation is the additive
  `project.packs_loaded` list and the section says so.
- Three pack manifests cited preset files by names that do not exist (`agile.yaml`, …).
- `project-phase-gate`'s description was 1,166 characters, over the 1,024 limit; now 993.

### Removed

- **`voice-forge` leaves this repo** and this marketplace. It now lives at
  `Atomic-47-Labs/voice-forge` (private) carrying its own marketplace, following the
  `assess-plugin` / `intel-state-plugin` / `forge-state-public` pattern. Nothing held it here: one
  incidental mention of the string "project-state" in the whole directory, no relative path reaching
  outside it, and no dependency in either direction with `demo-forge`. Install it with
  `/plugin marketplace add Atomic-47-Labs/voice-forge`. Decision:
  `2026-08-23-voice-forge-extracted-to-own-repo`.

  The move is worth reading for what it exposed rather than for what it moved. Three defects existed
  *only* because the plugin lived inside the repo it was narrating, so its relative paths happened to
  resolve — the skills' `node scripts/render.mjs`, an undocumented `player.js` copy step, and a key
  lookup that assumed one repo root. All three are fixed in the new repo's 0.2.0.

  A fourth was found by running `claude plugin validate` and has nothing to do with the move: **all
  four `SKILL.md` files had unparseable YAML frontmatter and had been loading with empty metadata
  since 0.1.0** — no name, no description, none of the trigger vocabulary. A colon-space inside a
  plain scalar (`Trigger "/voice-cast text: '…'"`) ends the scalar, YAML gives up on the block, and
  the loader falls back silently instead of erroring. Twelve days shipping, no signal in any output.
  `demo-forge` has the identical defect in both its skills; the 42 skills in `plugin/skills` are
  clean. **The lesson for the publish path: `claude plugin validate --strict` catches this in one
  second and is not currently run.**

## v4.10.1 - 2026-09-22

### Fixed

- **Every pack manifest now declares a truthful `compatible_core` and the full PACK-SPEC §3
  required set** — publisher pack mismatches 5 → 0, the first clean pack check the build has
  reported. `agile-default`, `board-investor`, `client-services`, `open-source-community` and
  `pic-pcais` declared `">=2.0,<3.0"`, asserting incompatibility with every core released since
  v3.0, and moved to `">=4.0,<5.0"`. This records what was already observably true (FB-014: they
  "load anyway", and have through two majors) and is explicitly **not** a tested compatibility
  claim — PACK-SPEC's "Testing a pack" checklist has not been run against any of them.
- **Missing required pack fields filled**: `tender-pursuit` had no `governing_documents`,
  `pic-pcais` and `grant-canada` no `maturity`, and the four starter packs no
  `governing_documents`. For packs encoding a practice rather than a funder's rulebook, that
  field names the convention and the phase preset assumed, not an invented external standard.
- **`intel-default` and `portfolio-default` conform to PACK-SPEC §3.** Both were authored with
  flat top-level keys instead of the nested `pack:` block, which is what had hidden their missing
  required fields.

### Documentation

- `docs/CAPABILITY-PLUGINS.md` **§9 Distribution** — the contract was previously answerable only
  from publisher source comments: one repo, one plugin, one install; how
  `build-capability-payload.py` splits a capability between the flat `plugin/skills/` the loader
  reads and `plugin/capabilities/<id>/` used at enable time; that undeclared files do not ship;
  why the payload declaration replaced symlinks; that installed ≠ active; and that one plugin
  means one version, so a single capability cannot be released on its own.
- FB-014 updated: the declaration half is closed, enforcement is not. Because every declaration
  is now truthful, implementing the pack check would no longer break the catalogue — a real
  option rather than a footgun. That decision remains open.

## v4.10.0 - 2026-09-22

### Added

- **`project-scheduler`** — conversational read/write over `automation/tasks.yaml`, using the
  same eight-op vocabulary and proposed-ghost-card discipline as the kanban calendar's chat
  surface, without needing the app running. Writes route through `project-state`; it never edits
  `reporting-matrix.yaml` and never dispatches.
- **`docs/AUTOMATION-HOSTS.md`** — the four scheduling hosts, the rule that a host must never
  carry a cadence (or the registry has a rival), the parked-run failure mode for unattended runs,
  and a diagnosis checklist for a facility that has gone silent.
- **The `intel` capability's 7 skills and `portfolio`'s 3 are published for the first time.**
  Both capabilities existed in source and shipped nothing: their skills had never reached
  `plugin/skills/`, so their handlers were not invokable.

### Fixed

- **Capability `examples/` fixtures no longer ship** (FB-019). 218 undeclared files across the
  four capabilities reached `plugin/` through the wholesale `capabilities/` mirror, and
  `portfolio`'s broke the publish outright: its harvest cursors are named
  `{email}--{surface}.yaml` and the bad-char guard rejects `@`. The exclude is scoped to the
  capabilities mirror in both publishers — a blanket one would have deleted
  `skills/project-onepager/examples`, which is declared payload (FB-007's failure mode).
- Six orphans removed from `plugin/` (`capabilities/tender-intelligence/surfaces.yaml`,
  `templates/tender/*`), each superseded by a file under `capabilities/tender/`.

### Note

4.9.0 was published twice; the second publish carried 11 new skills under an unchanged version,
so every client compared 4.9.0 to 4.9.0 and fetched nothing while the plugin card read "current".
**Always pass `--version` when contents change** — now the closing item of §9's publishing
checklist.


## v4.9.0 - 2026-08-21

Closes the entire open feedback register — FB-001 through FB-013 — and files two new records found
along the way. Twelve owner rulings, all recorded before implementation.

The branch is about one defect wearing seven costumes, and naming it is more useful than listing the
fixes: **a capability the product ships, documented, with nothing that makes it reachable.** Five phase
presets and no writer for `phases.preset`. `automation.timezone` marked REQUIRED, shipped as `~`, and
never mentioned by the component named on the record. A capability `payload:` block that nothing read.
`classified_by` written by two skills and defined in no schema. A feedback lifecycle with five states,
three never used, and no verb that advances any of them.

### Added

- **`set_preset(name)` on `project-phase-gate`** (FB-003) — the missing writer for `phases.preset`,
  open ten weeks *while being quoted as a cautionary precedent inside the work that kept not fixing
  it*. Three behaviours: writes freely before any phase starts; on a continuous facility routes
  through `close_increment` so the outgoing pass is frozen rather than discarded; on a terminal
  facility with phase history it refuses and explains.

- **Timezone collected at birth** (FB-002) — onboarding asks, scaffolder writes, and
  `project-automator` **refuses and names the missing key** rather than defaulting or reading the host
  clock. A 23:00–05:00 quiet window silently read as UTC fires at 4pm in Vancouver.

- **Four new shared publisher scripts**, bringing the total to six. `build-capability-payload.py`,
  `check-published-payload.py`, `check-pack-compatibility.py` and `sync-release-tag.py` are each
  called by **both** `publish-plugin.sh` and `publish-plugin.ps1`. Two hand-written implementations of
  one thing in two languages is what PLATFORM-NOTES already said nothing tests for.

- **Publishers now create the git tag and the GitHub release** (FB-010). v4.8.0 shipped with
  `plugin.json`, `CHANGELOG.md`, the marketplace entry and the release commit all agreeing it was
  4.8.0 — and no tag and no release. Earlier tags existed only because someone made them by hand while
  backfilling, so the first release without that manual step missed it. `release.yml` moved to
  `desktop-v*`, which is what it was always actually building.

- **`templates/lesson-learned.md` and a scaffolded `lessons-learned/`** — defined in SCHEMA.md with no
  template and no directory, so one facility's lessons went to `wiki/` instead.

- **An activity-log validator** (FB-012) reporting an aggregate census rather than per-line output,
  and a quiet-facility diagnostic that fires when the newest commit is 7+ days after the last log
  entry — commits as a gate, not a threshold.

### Fixed

- **The capability symlinks are gone** (FB-007). `packs/sred-canada` and the two `project-sred-*`
  skills were symlinks into `capabilities/sred/`; on a Windows checkout (`core.symlinks=false`) each
  is a plain text file, and `rsync -aL --delete` copying those stubs over the real published
  directories deleted ten SR&ED files with no error and a passing guard. The capability's `payload:`
  block is now the single record of what it owns. 59.5 KB of double-shipped payload removed.

- **Line endings are a property of the repo, not of your git config** (FB-008). `.gitattributes`
  gains `* text=auto eol=lf` above the existing specific rules. The file's own header had argued
  against this; that argument was measured and is false.

- **`classified_by` is single-valued and the curator is authoritative** (FB-006), documented in
  SCHEMA.md where it had never appeared. 34 double-keyed entries de-duplicated.

- **The scaffolder/onboarding collision was misdiagnosed** (FB-001). It is not an ordering problem —
  Chapter 8 calls the scaffolder before `project-state/` exists, so the new-project path never trips
  the abort. The failing path is re-orientation. The abort becomes conditional: still refuses when
  invoked bare, **adopts** an existing facility when given an intake record.

- **Duplicate milestone id M10.** The *lighter* record moves — `M10-v21-release` → M47, orphaning 23
  historical references instead of 90. Historical references are not rewritten.

### Four rulings that measurement reversed

Worth checking, because the obvious answer was wrong in each: the diagnostic threshold (a count of 10
commits would not have tripped until the day of the repair; days is the discriminating variable); the
capability payload (a keep-both compromise was recommended, then removed entirely once investigation
showed the symlinks had no runtime function at all); line endings (`git add --renormalize .` re-added
2511 paths and staged **3**); and the M10 duplicate (first-come-first-served pointed at the cancelled
record until reference counts inverted it).

### What the verification itself found

A noise-floor dry-run — run with no source change, purely to see what churns naturally — **deleted a
shipped file.** That is **FB-013**: `packs/pic-pcais/` is gitignored as "not distributed" while its
built copy is tracked and its manifest returns HTTP 200 from the public mirror. Gitignore does not
untrack what is already tracked; what it does is silently block *new* files, which is how
`profiles/onepager.yaml` came to exist only in build output with zero commits on its source path. A
fresh clone's first rebuild would have deleted all 12 files with every guard passing. A publish that
deletes a shipped file now fails.

### Deliberately not done

- **FB-014's pack ranges are untouched.** Five of eight packs declare `compatible_core '>=2.0,<3.0'`,
  excluding the 4.x core they ship in. Correcting the range would assert those packs work on 4.x, and
  PACK-SPEC's own testing checklist has not been run for any of them. Detection ships and warns;
  the fix is tracked on #17.
- **No migration of the 787 existing activity-log lines**, and no rewriting of historical M10
  references. Rewriting an append-only record to satisfy a schema written afterwards is worse than the
  inconsistency.

### After the merge

- **The platform docs now describe the repo that shipped.** CLAUDE.md and PLATFORM-NOTES still carried
  three claims the branch reversed — "do not add `* text=auto`", "the two `project-sred-*` skills are
  symlinks", and a Windows setup step requiring `core.autocrlf true`. CLAUDE.md loads into every agent
  session, so the next agent would have been instructed not to do the thing just deliberately done.
  Each correction now states what it used to say and why that was wrong.
- **`plugin/` rebuilt from sources.** The branch changed seven SKILL.md files and left the derived tree
  source-only by design, as its own notes said: *a rebuild is required at release for this branch's
  skill edits to reach the artifact.* This release is that rebuild — 209 lines of skill changes that
  4.8.0 could not have carried.

## v4.8.0 - 2026-08-21

Capabilities become installable by a person who has never seen one. The `sred` capability shipped in
4.6 with a full spec, two skills, a schema and a bundled pack — and no way for a new user to turn it
on. This release builds the missing front door and the missing verb behind it.

### Added

- **`enable` / `disable` / capability `validate` in `project-state`.** `docs/CAPABILITY-PLUGINS.md` §5
  specified enable as a memory-layer verb; nothing implemented it. The memory layer had zero mentions
  of capabilities, so nothing wrote the `capabilities:` manifest block, scaffolded the schema
  directories, created `state/<id>.json`, seeded the matrix, or armed the schedule. The two `sred`
  skills were writing into a substrate that no code created.

  Enable **refuses on missing REQUIRED config** rather than guessing. For `sred` that is
  `fiscal_year_end` — every deadline in the capability is computed from it, and a plausible default
  (December 31 is common) would put a confidently wrong filing deadline on an operator's dashboard.

- **`sred-onboarding`** — seven chapters: claimant identity, advisor, enable, the capture lens, first
  uncertainty, evidence sources, orientation. Its centre of gravity is Chapter 4, because the hard part
  of SR&ED is not the schema, it is knowing what counts. It ends on a real filing date rather than a
  summary of the conversation.

- **`capabilities/<id>/routine.yaml`, composed by `project-orchestrator`.** A capability declares what
  it wants looked at; the orchestrator ranks those items by severity alongside core items into one
  digest. Deliberately **not** a second orchestrator — two things answering "what should I do today"
  is worse than one thing answering it incompletely. `capabilities/sred/routine.yaml` ships with ten
  checks and a standing deadline strip.

### Fixed

- **SR&ED was offered as a project pack in three places.** `project-scaffolder`, `project-intake` and
  `project-onboarding` all listed `sred-canada` in their pack pickers. It is the *bundled* pack of the
  `sred` capability, loaded by that capability's enable step. Selecting it as a project pack produced a
  half-configured state: seeded matrix entries with no `sred/` directory, no runtime state and no
  filing deadline — the failure looked like success. All three now route to `sred-onboarding`.

  The milestone flag written during onboarding is renamed `sred_eligible` → `sred_candidate`. Nothing
  in an onboarding session can determine eligibility, and a field named `eligible` reads as a
  determination to the next person who opens the file.

- **`scripts/publish-plugin.sh` aborted before validating, on macOS.** The dangling-symlink guard used
  `find -xtype l`, a GNU extension BSD find does not have. Under `set -e` the failed assignment ended
  the run, so `claude plugin validate` never executed on any macOS publish. Replaced with the portable
  `-type l ! -exec test -e {} \; -print`. Same family as FB-007: a platform difference that fails
  silently in the direction of "looks like it worked".

### Note on the version number

This release is **4.8.0, not 4.7.0**, because 4.7.0 was published twice on consecutive days from two
different builds. A maintainer cut the continuous-lifecycle 4.7.0 on 2026-08-20; this work was cut from a
branch that predated that release commit and republished 4.7.0 over it a day later.

No content was lost — this build is a strict superset, carrying every lifecycle marker (increment ops,
the post-closeout diagnostic, `cycles_back_to` on all five presets, grant-default's explicit refusal)
alongside the SR&ED work. But two builds shared one version number, and **an install already on 4.7.0
would never have auto-updated to the second one**, because the updater compares versions and the
version had not moved. Bumping to 4.8.0 is what makes that update fire.

The lesson is not "check before publishing" — it is that nothing in the publish path noticed that the
target version already existed in the distribution repo's history. That guard does not exist yet.

## v4.7.0 - 2026-08-20

**The continuous lifecycle.** A phase ladder assumes the project ends. Most do; some don't — a product
ships and keeps shipping, a retainer renews, an ops facility never closes. Until now that was the only
model, so it got applied by default to facilities whose shape it didn't fit, silently.

Design of record: [`docs/CONTINUOUS-LIFECYCLE-SPEC.md`](docs/CONTINUOUS-LIFECYCLE-SPEC.md). Adopted by
`decisions/2026-08-19-adopt-continuous-lifecycle`. Tracked as `M46`. Filed as `FB-004`.

### Added

- **`phases.lifecycle`** — `terminal` | `continuous`, declared in the manifest. Asked in the operator's
  language ("does this project have an end date after which no further work is planned?"), never as
  "terminal or continuous".
- **Increments.** On a continuous facility, work arrives in bounded passes through the ladder — v1, v1.1,
  next quarter's retainer — each with its own closure. `increments/INC-<NN>-<label>/`.
- **`cycles_back_to` marks the increment boundary.** `agile-default` already shipped this key with nothing
  reading it; it is now load-bearing. Added to `open-source-default`, `client-engagement-default` and
  `waterfall-default` at the phase where work genuinely recurs. **`grant-default` declares none and never
  should** — declaring `continuous` against it is a validation error, not a warning.
- **`closed_what` is required to close an increment.** No default, nothing generated. One or two sentences
  on what the closure closed *and what it did not*. It is the cheapest thing in the design and removes most
  of the practical damage on its own.
- **`health.scope` and `health.increment`.** `overall_percent` keeps its exact computation and its all-time
  meaning — it now simply says so. On a continuous facility it is joined by an increment-scoped number,
  which answers *are we done with what we are doing now.*
- **A post-closeout diagnostic.** A facility can detect for itself that the terminal assumption has stopped
  holding: work added after closeout. Warns once per day, never refuses — a late deliverable during closeout
  is not a lifecycle mismatch.
- **`defaults.lifecycle` in pack data.** A suggestion, not a decision: onboarding pre-fills its question from
  it; the scaffolder writes `terminal` where a pack declares it and *nothing* where a pack suggests
  `continuous`. A pack cannot make a facility continuous.
- **`scripts/test-increment-lifecycle.py`** — 39 assertions over the spec. The one that matters: closing an
  increment preserves the outgoing pass's gate evidence, including a criterion closed `closed_unmet: true`.

### Changed

- Closeout artefacts belong to the increment on a continuous facility — `increments/INC-NN/reports/closeout-<date>.md`
  rather than a second file called `final`. Terminal facilities are untouched.
- A closed increment is **frozen**: no operation rewrites its records or its frozen `phases/`.
- The kanban dashboard and the website state layer prefer the increment-scoped number where present, and
  fall back to `overall_percent`. `overall_pct` keeps its name and value for existing consumers.
- Third increment state is `cancelled`, matching the word milestones already use.

### Compatibility

**A facility that declares no lifecycle behaves exactly as it did before.** Absence means `terminal`, is
permanently valid, and is never warned about — not as an error, not as a suggestion. No `increments/`
directory is created, no `health.increment` is written, `current_phase` stays a scalar and `gates` stays
keyed by phase id. Grant packs gain no new concepts. Verified against a live terminal facility, and
asserted in the harness rather than assumed.

### Known limitation

Phase manifests exist in two shapes — checklist form (from `templates/phase-manifests/`) and lightweight
form (scalar gate strings, from a preset). Both are valid and neither is silently upgraded. The freeze is
correct on both, but preserves materially less on a lightweight facility, because per-criterion gate
evidence was never recorded there. See `FB-005`.

## v4.6.2 - 2026-08-19

A one-defect patch: the plugin card renders its metadata again.

### Fixed

- **The Project State plugin card showed no version, author or description.** The card reads `version`
  and `author` from the **marketplace entry**, not from the plugin's own `plugin.json` — and the
  project-state entry carried neither. `plugin.json` was never at fault; it has had every field all
  along. Sibling entries in the same marketplace (`demo-forge`, `voice-forge`) were written correctly,
  which is why this went unnoticed.

  Not cosmetic: a card with no version cannot answer *which version am I running*. On the machine that
  reported it, that had hidden a two-month-stale 4.2.0 install.
- **The entry's description was stale** — it claimed 34 skills and 7 packs against a build of 41 and 8.

### Added

- **`scripts/sync-marketplace-entry.py`** — syncs `version` and `author` from `plugin.json` into the
  matching marketplace entry, called by **both** publishers so the two files cannot drift on a release.
  It exits non-zero when no matching entry exists, so a publish fails loudly rather than shipping a card
  that renders blank. It also warns when the entry's description states a skill or pack count that
  disagrees with the build — the exact staleness fixed above.

  `description` is deliberately not synced: the entry's is a short catalogue line, `plugin.json`'s is the
  long-form blurb, and overwriting one with the other would be a regression.

### Note for anyone on an older build

Because the card could not show a version, it is worth checking yours: `/plugin` in Claude Code, or the
plugin panel in the desktop app. Installs from as far back as 4.2.0 have been seen in the wild.

## v4.6.1 - 2026-08-19

A defect-fix patch. **No new features, no schema migration, nothing to configure.**

### Read this before you upgrade

This release teaches the validator to catch a class of silent data loss it has never caught before.
On first run against a real facility it found two pre-existing problems in that facility, both of
which had been there for months.

**It reports problems that already existed. It does not create them.** If `project-state validate`
starts naming files after you upgrade, those files were already wrong and nothing was telling you.
Nothing is auto-fixed, because the fixes are not mechanical - a duplicate key's correct value is
knowable only by whoever wrote it.

### Fixed

- **Duplicate YAML keys no longer parse silently** (`FB-005`). A default `safe_load` accepts a
  repeated mapping key at any level and keeps the last one, so the file parses, the earlier value is
  gone, and nothing reports it. Found in the wild: a phase manifest carried a duplicate `ended:` key
  and the phase read as undated while the file plainly stated a date. `validate` now loads every YAML
  in the facility through a duplicate-key-strict loader and reports duplicates as errors, naming both
  line numbers.
- **Duplicate entity ids across files are now reported.** Two milestones both claiming `M10` is the
  across-file form of the same collision, and it is why a facility can show `counters.milestones`
  disagreeing with `health.milestones_total` with nothing explaining the gap.
- **`classified_by` written twice into one document-index entry** (`FB-006`). `project-inbox` and
  `project-document-curator` both write the key; the second appends rather than replaces, so the
  first classifier is silently discarded. **Detection ships here; the write path does not.** Whether
  classification is a single value or a history is a design question, not a patch.

### Added

- **Phase manifests have a documented schema** for the first time. They were the only canonical files
  in a facility with no defined shape and nothing checking them.
- **`state.json` is documented** for the first time.
- **`scripts/verify-lifecycle.py`** - a read-only pass that runs these checks against any facility
  and modifies nothing. Run it before upgrading if you would rather see the report first.

### Changed

- **Validation severity is deliberately conservative.** Errors are reserved for: a file that does not
  parse, a duplicate key, an `id` disagreeing with its directory, an unknown `status` value, and a
  `cycles_back_to` naming a phase that does not exist. Missing dates and labels are warnings. Field
  aliases are notes. A validator that errors on every existing facility is a validator people switch
  off, which costs more than the defects it catches.
- **Phase manifests are accepted in both shapes that exist in the wild** - *checklist form* (gate
  objects with per-criterion evidence, what the templates write) and *lightweight form* (scalar gate
  strings, what a facility scaffolded from a preset gets). Neither is silently upgraded to the other:
  converting a lightweight manifest would invent gate criteria nobody agreed to.
- **Field aliases resolve on read** rather than failing: `status` accepts `active`/`completed`/
  `not_started`/`planned`/`in_progress`/`done` alongside the canonical `pending`/`current`/`complete`,
  and dates accept `entered`/`exited` alongside `started`/`ended`. Three status vocabularies and two
  date vocabularies were in use across templates and live facilities, and nothing had ever reconciled
  them because nothing had ever compared them.

### Documentation only, ahead of implementation

`docs/SCHEMA.md` and `docs/CONTINUOUS-LIFECYCLE-SPEC.md` describe the **continuous lifecycle** and the
**increment** entity, which land in v4.7.0. Every field is conditional on `phases.lifecycle:
continuous`, which no v4.6.1 facility can set, so all of it is inert here. It ships now because the
schema and validator reference it.

## v4.6.0 — 2026-08-17

> Reconstructed from commit history — this release predates the practice of writing a
> changelog entry at release time. Derived from the commits leading to [`79f5311`](https://github.com/Atomic-47-Labs/project-state/commit/79f5311),
> excluding auto-checkpoints and merges. Full list: [release v4.6.0](https://github.com/Atomic-47-Labs/project-state/releases/tag/v4.6.0).

10 commits since the previous release, 7 of them substantive. Selected:

- release: project-state plugin v4.6.0 — evaluation ladder + evidence cohort
- sred: evidence correlation — Jira, Confluence, and GitHub as a cohort
- sred: opportunity evaluation ladder + tiered evidence sources (Jira/Confluence first-class, Slack/Docs second-class)
- marketing: sred technical adoption page (for engineers)
- marketing: sred capability landing page
- sred: first capture pass — the capability build recorded in its own substrate
- kanban: fix profile identity leak under team auth

## v4.5.0 — 2026-08-17

> Reconstructed from commit history — this release predates the practice of writing a
> changelog entry at release time. Derived from the commits leading to [`641b377`](https://github.com/Atomic-47-Labs/project-state/commit/641b377),
> excluding auto-checkpoints and merges. Full list: [release v4.5.0](https://github.com/Atomic-47-Labs/project-state/releases/tag/v4.5.0).

36 commits since the previous release, 33 of them substantive. Selected:

- release: project-state plugin v4.5.0 — first release carrying the sred capability
- plugin: rebuild distribution tree — sred capability included
- publish: ship capability payloads and dereference capability symlinks
- sred: weekly progress digest + layered innovation criteria (capture lens)
- sred: build the capability plugin and enable it on the dogfood project
- docs: SR&ED capability specification — sred plugin + sred-canada pack
- pilot: define the week-six review with a worked example
- site: publish the diagnostic one-pager at /diagnostic/one-pager
- deck: diagnostic session deck, replacing the SR&ED pitch
- state: register the pilot process and the reframed diagnostic
- …and 21 more — see the [release notes](https://github.com/Atomic-47-Labs/project-state/releases/tag/v4.5.0)

## v4.4.0 — 2026-08-11

> Reconstructed from commit history — this release predates the practice of writing a
> changelog entry at release time. Derived from the commits leading to [`24508c0`](https://github.com/Atomic-47-Labs/project-state/commit/24508c0),
> excluding auto-checkpoints and merges. Full list: [release v4.4.0](https://github.com/Atomic-47-Labs/project-state/releases/tag/v4.4.0).

75 commits since the previous release, 59 of them substantive. Selected:

- feat(feedback): project-feedback skill v1 + plugin v4.4.0
- docs(feedback): project-feedback spec + adoption decision
- project-state: weekly report 2026-W33 + outbox card
- project-state: reconcile counters + change-register review log
- docs(telegram): Telegram bot interface spec for project-state.app
- chore(launch): add concierge-app preview server (port 3388)
- docs(concierge): Project Concierge spec + VPS backend diagrams
- docs(plan): 12-month development plan, partner brief series, health recompute
- feat(tour): v2 — TTS + voice panel, live-app highlighting, enriched feed, mission slide
- fix(tour): commentary names the step just finished; plain-prose guide output
- feat(tour): guided interactive tour — rail + agent on personal scratch projects
- feat(marketplace): list demo-forge in the project-state marketplace
- …and 47 more — see the [release notes](https://github.com/Atomic-47-Labs/project-state/releases/tag/v4.4.0)

## v4.3.0 — 2026-07-23

> Reconstructed from commit history — this release predates the practice of writing a
> changelog entry at release time. Derived from the commits leading to [`874689a`](https://github.com/Atomic-47-Labs/project-state/commit/874689a),
> excluding auto-checkpoints and merges. Full list: [release v4.3.0](https://github.com/Atomic-47-Labs/project-state/releases/tag/v4.3.0).

381 commits since the previous release, 248 of them substantive. Selected:

- chore(plugin): publish v4.3.0 + fix project-onepager frontmatter
- feat(harvest): per-user surface connectivity — deposit API, surface grants, binding seam
- merge: integrate main (Headscale self-host control-plane) into appliance branch
- chore(ci): prettier --write + register /m in nav-registry (green CI)
- chore(mcp): retire the legacy shared gateway token (KS_LEGACY_TOKEN=0)
- docs: Resend verified-domain gotcha + tabbed MCP client snippets
- polish(nav): unify the /config page name to "Settings" everywhere
- feat(mcp): tabbed per-client setup snippets on the MCP-access card
- fix(profile): show governance role (admin) not operator capability
- fix(mcp): app can't mint tokens — enumerate secret files vs blanket mask
- feat(mcp): personal + scoped service token classes with self-service + admin UI
- docs: rename keep-state-app → project-state.app across living docs
- …and 236 more — see the [release notes](https://github.com/Atomic-47-Labs/project-state/releases/tag/v4.3.0)

## v4.2.0 — 2026-06-09

> Reconstructed from commit history — this release predates the practice of writing a
> changelog entry at release time. Derived from the commits leading to [`b23e211`](https://github.com/Atomic-47-Labs/project-state/commit/b23e211),
> excluding auto-checkpoints and merges. Full list: [release v4.2.0](https://github.com/Atomic-47-Labs/project-state/releases/tag/v4.2.0).


## v4.1 — 2026-06-08

### Added

- **`project-jira-publisher`** (new skill) — publish milestones, risks, decisions, objectives, and KPIs to Jira as issues via REST. Supports `--emit-json` mode for the connector publish path. Full field mapping, status sync, and dry-run mode.
- **`project-goal-tracker`** (new skill) — objectives + KPI tracking layer over milestones. Create, update, and report on goals with reasoned (computed) KPIs, guidance, and descriptions. The dedicated Goals tab in the kanban.
- **`project-tech-reports`** (new skill) — catalog and generate technical reports with multi-select, versioned history, and a dedicated Tech Reports view in the kanban.
- **`project-admin`** (new skill) — manage projects in the local-first + GitHub-hub model: create a new project-state substrate and its private GitHub state repo, pull an existing project's state repo, list registered projects.

### Changed

- **`project-onboarding`** — three new modes: `first-intel` (minimal ~10-minute orient: ingest docs + URLs, produce Orientation Brief, queue inferred entities as drafts — no chapter interrogation); chapter threading (resume a section's prior thread instead of starting fresh); additive pack picker embedded in the pack-selection chapter.
- **Onboarding coverage assessment** — pack selection now contributes 15 pts to the coverage score (replacing `people`, which was not a chapter); "Pack selected" row added to the coverage checklist; pack picker triggers an immediate coverage re-grade after toggle.
- **Reporting matrix** — new visual page in the kanban (who / when / what / how, actionable).

### Fixed

- Onboarding: coverage read the wrong record for stakeholder count.
- Onboarding: pack-selection chapter was arriving empty; additive picker now embedded.

## v4.0 — 2026-05-28

### Architectural shift

**Cloud MCP server — git as the database, MCP as the API, local as an optional cache.** v3.x required every user to have the substrate on their local machine. v4.0 adds a centralized MCP server that hosts substrates for multiple organizations and projects. Users connect via bearer token from Claude Code, Claude Desktop, or any MCP-compatible IDE. The existing 30 skills work unchanged — only the transport layer between Claude and the files is different. Git runs invisibly behind the MCP API, providing versioning, audit, and durability. Users never touch git, never need a GitHub account, never see a commit SHA.

Local mode remains fully supported. The cloud server is additive, never required.

### Added

- **Cloud MCP server** (`server/`) — Node.js MCP server with streamable HTTP transport. Hosts project-state substrates for multiple orgs and projects. Auto-versions every write (git commit internally). Auto-syncs to company-controlled git remote (git push internally). Bearer token auth with org routing. See `docs/CLOUD-MCP-SPEC.md`.

- **Multi-tenant data model** — one server hosts many organizations, each with many projects. Isolation at filesystem, git remote, and auth level. Each org owns a `org.yaml` with member roster, git remote config, and token hashes. Each project directory is a git-backed working copy.

- **Three roles with per-project access** — Admin (create/destroy projects, manage tokens, configure git remote), Member (read/write assigned projects), Viewer (read-only). Per-member `projects: ["*"]` or `projects: ["volta"]` filtering. Consortium partners and external auditors get scoped access to specific projects.

- **Bearer token auth** — format `ps_{org}_{random_32chars}`. Org routing from prefix. Server stores bcrypt hash only. Plaintext shown once at issuance. Instant revocation.

- **MCP tools** — 25 tools across 6 categories:
  - Context & discovery: `whoami`, `set_context`, `list_projects`, `project_info`
  - File operations: `read_file`, `write_file`, `append_file`, `delete_file`, `list_dir`, `glob`
  - Batch operations: `begin_batch`, `end_batch`, `abort_batch`
  - History (no git vocabulary): `history`, `diff`, `inspect`, `who_changed`, `undo`
  - Local sync: `download_project`, `upload_project`
  - Admin: `create_project`, `destroy_project`, `import_project`, `export_project`, `issue_token`, `revoke_token`, `create_invite_link`, `revoke_invite_link`, `list_members`, `update_member`, `configure_remote`
  - Concurrency: `acquire_lock`, `release_lock`, `break_lock`

- **Hosted dashboard** (`/dash/:org/:project`) — team-facing kanban board, summary dashboard, entity inventory, reports, and milestone detail views. Served from the MCP server, reading from the same working copies on disk. Auth via bearer token or session cookie. Multi-project nav with project switcher. Replaces the need to run `npm run dev` locally.

- **Hosted project website** (`/site/:org/:project`) — stakeholder-facing project pages (overview, milestones, risks, decisions, reference docs). Configurable visibility: public, authenticated, or disabled. Replaces per-project Vercel/Netlify deploys.

- **Web onboarding wizard** (`/onboard`) — 6-step browser-based wizard for new companies: create org, connect data store (GitHub/GitLab/self-hosted), create first project with pack selection, invite team, get connection config, launch. No CLI required.

- **Team member join flow** (`/join/:org/:invite_code`) — shareable invite links with configurable expiry. Self-registration for team members. One-page setup: enter email → get token → copy config → done.

- **Local sync via zip** — `download_project()` packages current state as a zip (no `.git`, no git knowledge needed). `upload_project()` accepts a zip back, server diffs and merges. Users never run git.

- **Data sovereignty** — every org's substrates push to a git remote the company controls (GitHub, GitLab, Gitea, on-prem bare repo). The MCP server holds disposable working copies. If the server is decommissioned, the company retains everything. Self-hosted Docker deployment for regulated industries.

- **`project-state` skill (memory layer)** — added `## State Access` preamble with remote/local mode detection. When MCP tools are available from a `project-state` server, all file operations route through them. When no server is connected, reads/writes local `project-state/` directly. All 29 other skills route through `project-state` and do not need to know whether files are local or remote.

- **`/project-state cloud` commands** — `init`, `create`, `destroy`, `connect`, `download`, `upload`, `push`, `status`, `team`, `invite`, `revoke`, `access`.

- **`docs/CLOUD-MCP-SPEC.md`** — full design specification (v0.7). Mental model, data sovereignty, data model, roles & access, token management, local sync, easy install, MCP tools, concurrency, API transport, hosted dashboard & website, web onboarding wizard, team join flow, company onboarding journey, deployment, client config, skill adaptation, migration paths, security, cost model, 6 implementation phases.

- **`docs/USER-GUIDE.md`** — 12-part onboarding guide covering the cowork model, daily workflows, weekly reporting, document lifecycle, kanban dashboard, stakeholder reporting, compliance & governance, packs, collaboration & concurrency, grant submissions, and surface modes. Includes ASCII UX wireframes for onboarding chapters, kanban board, daily brief, reporting pipeline, and lifecycle phases.

### Changed

- **`project-scaffolder`** — when running in cloud mode, scaffolder initializes the substrate on the server via MCP tools instead of writing to local filesystem. Git initialization is handled by the server automatically.

- **`project-orchestrator`** — in cloud mode, end-of-session routine replaces `project-git checkpoint` suggestion with a status check against the server (changes are auto-versioned). In local mode, behavior unchanged.

- **`project-git`** — in cloud mode, the skill is informational only (history, status, diff via MCP tools). The server handles all versioning automatically. In local mode, behavior unchanged.

- **Kanban dashboard** — single Next.js app that detects its environment via `PS_SUBSTRATE_ROOT` env var. Cloud mode: reads from server working copies, served at `/dash/`. Local mode: reads from `./project-state/`, served on `localhost:3355`. Same code, same views, different root.

- **Project website** — same environment detection. Cloud mode: served at `/site/`, no deploy step. Local mode: deploy to Vercel/Netlify as before.

### Migration from v3.x

**Additive — no breaking changes.** Local mode works exactly as before. To add cloud:

```
1. Admin: /project-state cloud init
   → org created, token issued, git remote configured

2. Admin: /project-state cloud push
   → current local project uploaded to cloud

3. Admin: /project-state cloud invite <email>
   → token issued, admin sends to Alex

4. Alex: export PS_TOKEN=ps_acmecorp_...
   Alex: adds .mcp.json
   Alex: /project-state cloud connect volta
   → working immediately
```

Or use the web wizard at `/onboard` — no CLI needed.

**Exit path:** `/project-state cloud download` gives a zip. Or `git clone <remote>` for the full history. Local mode works unchanged. Zero lock-in.

---

## v3.2 — 2026-05-18

### Added

- **Interactive scaffolding design system** — shared presentation protocol adopted by `project-scaffolder`, `project-onboarding`, and `grant-scaffolder`. Defines two surface modes: HTML artifact mode for Claude Coworker (claude.ai) and markdown mode for Claude Code (CLI). HTML mode renders self-contained artifacts with ProgressBar, OptionCard, FormField, ToggleCard, SummaryRow, GapRow, QualityBar, and NavRow components plus mermaid.js diagrams — all without leaving the chat window. Markdown mode uses progress lines, Mermaid code blocks, markdown tables, and numbered prompts. Both modes produce identical substrate output.

### Changed

- **`project-onboarding`** — added `## Presentation Protocol` section with surface detection, design system reference, and per-chapter HTML artifact and markdown display specs. Chapter 1 (Pack Selection) renders OptionCards for each pack. Chapter 7 (Gaps) renders GapRows with inline [provide now / leave gap / synthesize] buttons in Coworker. Chapter 8 (Initialize) renders SummaryRows with source badges and a single large Confirm button. Chapter 9 (Orientation Check) renders QualityBar components for grounding, goals, and stakeholder depth scores. PreFilledField components replace QuestionBlocks for any field where `inbox-orientation.yaml` has a value — the user confirms rather than re-enters.
- **`grant-scaffolder`** — added `## Presentation Protocol` section with a five-step scaffolding wizard (Program Selection → Project Inputs → Compliance Gate Preview → Review & Confirm → Build Output) and a three-step award handoff mini-wizard. Step 1 renders 19 playbook OptionCards in a searchable grid. Step 3 renders a Mermaid gate-activation map and a gate table with required/recommended/N-A status chips. Step 4 renders a SummaryRow panel and a facility directory tree preview before the single Scaffold button.

---

## v3.1 — 2026-05-18

### Added

- **`grant-canada` pack** — Canadian grant submission lifecycle for project-state. Covers 19 programs: Tri-Council (NSERC/SSHRC/CIHR), IRAP, SIF, CFI JELF, Mitacs, NGen, SCALE.AI, Genome Canada, PacifiCan, FedDev, FedNor, CED, ACOA, CanNor, SR&ED, and agnostic-core fallback. Models 12 Canada-specific compliance gates (OCAP, GBA+, bilingual, TTO routing, stacking, IP declaration, Indigenous engagement, environmental, cost-share, ethics-REB, biosafety, data sovereignty). Compatible with `sred-canada` and `pic-pcais` packs. Ported from the v-mcp spec; adapted to the v3 skill/pack contract.
- **`grant-state` skill** — memory layer for `grant-state/` submission facilities. Mirrors the role of `project-state` for the pre-award phase. Enforces the write protocol and maintains the activity log.
- **`grant-scaffolder` skill** — scaffold a grant submission facility; match playbook from 19 Canadian programs; seed narrative sections, compliance gates, budget scaffold, and phase manifests. On award: freeze submission, spawn sibling `project-state/`, carry forward consortium people, IP rationale, gate snapshots, and re-baselined milestones.
- **`grant-ingestor` skill** — drain `grant-state/documents/inbox/` of program guides, eligibility docs, and partner materials; produce a strategy pass (program fit memo, section-coverage map, gate map, letter requirements, risk register seed, prioritized work order); generate eligibility verdict; harvest overnight Gmail/Slack signals; capture lessons from completed submissions.
- **`project-git` skill** — strategic git checkpointing for project-state facilities. Five sub-actions: `checkpoint` (commit with auto-generated message from activity log), `push` (share with team), `sync` (pull + rebase), `status`, `log`. Never auto-commits. Suggested at end of daily routine by `project-orchestrator`.

### Changed

- **`project-orchestrator`** — daily routine now suggests `project-git checkpoint` when uncommitted changes exist. New `end-of-session` routine: tails activity log, proposes checkpoint with auto-generated message, flags approaching deadlines, reminds to push. `project-git` added to Integration section.
- **`project-scaffolder`** — git initialization is now part of scaffolding: `git init` in project root, `.gitattributes` with `merge=union` on `logs/*.ndjson` (making log merges automatic), initial commit. Skipped when shared-drive team model is selected. `project-git` added to Integration section.
- **`plugin.json`** — updated to v3.1.0. Added `skills` and `packs` arrays so Claude Code registers all 28 slash commands on install (previously the plugin had no skills declaration).
- **`INSTALL.md`** — updated manual symlinks to include all 30 skills; updated pack table with `grant-canada` and `pic-pcais`; updated skill count from 23 to 28.

---

## v3.0 — 2026-05-11

### Architectural shift

**Unified reporting mechanism — one context, one document tree.** The v2.0 suite had two parallel documentation pipelines that didn't know about each other: `project-doc-suite-generator` (reading `project-state/` → 7 Office files) and the global `doc-suite-generator-v2` skill (reading a codebase scan → 11 markdown documents). The Architecture-Overview.docx had never read the actual codebase; the technical-specification.md had no idea which milestone it was delivering against. v3.0 collapses both into a single unified suite.

### Added

- **`project-doc-suite` skill (#20)** — unified documentation suite generator. Assembles a shared context object by merging `project-state/` substrate data (milestones, risks, phases, budget, manifest, reporting matrix) with a live codebase scan before generating any document. Produces 15 non-overlapping documents in `reports/unified-suite/YYYY-MM-DD/`. Replaces and supersedes `project-doc-suite-generator`. See `docs/UNIFIED-SUITE-V3.md`.
- **`docs/UNIFIED-SUITE-V3.md`** — full design reference. Documents the unified context schema, the complete v3 document tree (15 files, 4 bands), the two full document collapses (Architecture + tech-spec → one; Roadmap + business-benefits → one), the four enriched governance Office files, the 8-phase generation pipeline, pack extension point, and open implementation questions.
- **`v3/README.md`** — v3-specific README covering the unified suite design and upgrade path.
- **`v3/INSTALL.md`** — v3-specific install guide with fresh install and v2→v3 upgrade instructions.

### Changed

- **`project-doc-suite-generator`** — deprecated. The skill still functions on v2.x but will be removed in v3.1. Every invocation now shows a deprecation notice pointing to `project-doc-suite`. Output path was `reports/baseline/Baseline-Reports-YYYY-MM-DD/`; new path is `reports/unified-suite/YYYY-MM-DD/`.

### Document collapse (23 → 15, −35%)

| Removed | Replaced by |
|---------|-------------|
| `Baseline-Reports-Index.docx` + `00-executive-summary.md` | `00-suite-index.md` |
| `Architecture-Overview.docx` + `01-project-overview.md` + `01b-technical-specification.md` | `05-architecture-and-tech-spec.md` |
| `Roadmap-and-KPIs.docx` + `02-business-benefits.md` | `06-strategic-roadmap.md` |

### Governance documents enriched (not removed)

| Document | What's new |
|----------|------------|
| `01-project-tracker.xlsx` | Two new columns per milestone: primary codebase components + technical readiness score |
| `02-project-plan.docx` | Component Delivery Map table (phase → components entering production) |
| `03-risk-register.docx` | Technical Debt Risks section auto-populated from codebase scan readiness gaps |
| `04-milestone-specs.docx` | Delivery Components + Component Readiness section per milestone |

- **`packs/sred-canada/`** — new compliance pack for Canadian SR&ED T661 tax credit claims. Extends the substrate with `sred/` entities (TU/EX/ADV + evidence log + cost tracking). Provides funder-reporting, phase-gate, and external-comms profiles. Activates `project-sred-tracker` and `project-sred-reviewer`. See `packs/sred-canada/README.md`.
- **`project-sred-tracker` skill (#21)** — continuous capture of Technological Uncertainties, Experiments, Advancements, and evidence log entries. Enforces TU→EX→ADV traceability chain. Runs quarterly gap analysis and completeness reviews. Tracks 18-month CRA filing deadline. Active when `sred-canada` pack is loaded.
- **`project-sred-reviewer` skill (#22)** — T661 narrative review and audit-risk reduction. CRA-reviewer simulation, cross-section traceability check, risky language flagging, safer rewrites for Sections E/F/G, readiness verdict. Elevates the standalone `sred-submission-reviewer` skill into the project-state substrate. Active when `sred-canada` pack is loaded.
- **`project-onboarding` skill (#23)** — guided new-project onboarding. Interleaves facility orientation prose with targeted questions; handles pack selection (all 6 packs, branching logic), document ingestion and field extraction, stakeholder mapping, milestone capture, and freeform goals/examples/anti-patterns capture. Writes all captured context to substrate reference files. Calls `project-scaffolder` as its final step. Distinct from `project-scaffolder` (which initializes the filesystem); `project-onboarding` fills the context that makes the substrate useful. Synthetic content (when offered) is always labeled and requires user approval before writing.
- **`docs/PACK-CATALOG.md`** — updated to v3.0; `sred-canada` added; combinations table updated; roadmap cleaned of already-shipped packs.

### Migration from v2.x

Additive — no substrate changes required. ~10 minutes:
1. Symlink `project-doc-suite` into `~/.claude/skills/`
2. Replace any invocation of `project-doc-suite-generator` with `project-doc-suite`
3. Output path changes from `reports/baseline/Baseline-Reports-YYYY-MM-DD/` to `reports/unified-suite/YYYY-MM-DD/`

See `v3/INSTALL.md` for the full upgrade walkthrough.

---

## v2.0 — 2026-04-27

### Architectural shift

**Generic core + compliance packs.** The suite splits into a funder-agnostic core (12 unchanged skills + 6 abstracted skills + the new stakeholder reporting matrix) plus pluggable compliance packs that encode funder/customer/industry-specific behavior. The `pic-pcais` pack reproduces v1.x behavior exactly. Other packs (`client-services`, `board-investor`, `agile-default`, `open-source-community`) ship as reference implementations.

This is the change that turns the system from a grant-management tool into a multi-stakeholder reporting tool that grants happen to be one case of.

### Added

- **Stakeholder reporting matrix** (`reporting-matrix.yaml`) — first-class entity in the substrate. Encodes "for each stakeholder group, what report at what cadence in what format on which surface, by which generator." Orchestrator scans on every tick and dispatches. See `docs/REPORTING-MATRIX.md`.
- **Pack system** — packs are collections of profile YAMLs + templates + reporting-matrix-defaults that configure the generic core. See `docs/PACK-AUTHORING.md` and `docs/PACK-CATALOG.md`.
- **`packs/pic-pcais/`** — production pack reproducing v1.x `pic-pcais` behavior. Profiles for funder-reporting, review-meeting, external-comms, ip-tracker, archive, phase-gate. Templates for claim cover-email and SC Appendix-A agenda. Reporting-matrix-defaults seeding the funder.pic stakeholder.
- **`packs/client-services/`** — starter pack for consulting/customer engagements.
- **`packs/board-investor/`** — starter pack for PE/VC-backed startups.
- **`packs/agile-default/`** — starter pack for engineering teams.
- **`packs/open-source-community/`** — starter pack for OSS projects.
- **Phase preset library** in `templates/phase-presets/`: `grant-default`, `agile-default`, `waterfall-default`, `client-engagement-default`, `open-source-default`. Custom presets supported.
- **`templates/manifest-v2.yaml`** — new schema with stakeholders as first-class, phases.preset selection, packs_loaded list, reporting_matrix_path pointer, funder/customer namespaces.
- **`scripts/migrate-v1-to-v2.py`** — non-destructive migration utility. Backs up v1 manifest, writes v2 manifest with `pic-pcais` fields moved to funder.pic namespace, seeds reporting matrix from loaded packs.
- **`docs/REPORTING-MATRIX.md`** — full reference for the new entity.
- **`docs/PACK-AUTHORING.md`** — how to write your own pack.
- **`docs/PACK-CATALOG.md`** — what ships, combinations, roadmap.
- **`docs/MIGRATION-V1-TO-V2.md`** — five-step walkthrough.

### Changed (skill abstractions)

- **`project-claim-prep` → `project-funder-reporting`** — generic funder/customer reporting engine. Loads template/cadence/recipient from active pack profile. `pic-pcais` pack profile reproduces quarterly claim behavior.
- **`project-sc-meeting` → `project-review-meeting`** — generic recurring review meeting. Loads name/attendees/cadence/agenda from active pack profile. `pic-pcais` pack profile reproduces SC behavior.
- **`project-publications` → `project-external-comms`** — generic external-comms review pipeline. Loads review-window-by-content-class from profile. `pic-pcais` pack profile reproduces 30/14-day MPA behavior.
- **`project-ip-tracker`** — name unchanged but generic recipient via profile. `pic-pcais` pack profile routes to the funder's data and IP lead.
- **`project-archive`** — name unchanged but generic core + pack-driven items. `pic-pcais` pack profile contributes FTE confirmation, holdback release, etc.
- **`project-phase-gate`** — name unchanged but user-defined phases via preset + pack overrides. Five presets ship; custom presets supported.

### Migration from v1.x

Non-destructive. Substrate format unchanged. ~30 minutes total for an existing project. See `docs/MIGRATION-V1-TO-V2.md`. Rollback is `mv manifest.v1.bak.yaml manifest.yaml && rm reporting-matrix.yaml`.

### Aliases

The old skill names (`project-claim-prep`, `project-sc-meeting`, `project-publications`) remain as aliases when the `pic-pcais` pack is loaded, so existing user phrasings ("draft the Q2 claim", "schedule the next SC meeting", "we want to publish") continue to work.

---

## v1.1 — 2026-04-27

### Added

- **`project-website-publisher` skill (#18)** — bridges `documents/published/` to a static project website hosted on Vercel/Netlify/Cloudflare Pages/GitHub Pages. Stable URLs per doc, visibility-aware rendering (`team` / `consortium` / `public`), MPA publication-review enforcement on public pages, auto-deploy on `documents/published/` changes.
- **`docs/PROJECT-WEBSITE.md`** — full integration reference.
- **`templates/website/`** — Next.js + MDX starter template.
- **`website` block** in manifest template under `surfaces:`.

### Changed

- README and INSTALL bumped to v1.1; surface inventory now lists five surfaces (Slack, Gmail, Calendar, scsiwyg blog, project website).

---

## v1.0 — 2026-04-24

### Added

- Initial release.
- 17 skills covering project-state, scaffolder, orchestrator, phase-gate, document-curator, milestone-manager, status-reporter, notifier, sc-meeting, claim-prep, change-register, blog-publisher, onboarder, ip-tracker, publications, lessons, archive.
- `project-state/` substrate documented.
- Templates for manifest and six phase manifests.
- Install guide with symlink/copy/Cowork options.
- Four surfaces wired: Slack, Gmail (drafts), Calendar, scsiwyg blog.

### Battle-tested on

A grant-funded, multi-party project with quarterly funder claims and a steering committee.
