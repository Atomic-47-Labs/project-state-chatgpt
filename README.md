# Project State — ChatGPT / Codex plugin

**Project State** is a local-first operational substrate for multi-stakeholder
projects. It bundles **73 skills** that turn routine reporting into a byproduct
of normal work: milestones, objectives and KPIs, phase gates, document curation,
status reports, funder and grant compliance, Canadian SR&ED records, tender
pursuit, competitive intel, portfolios and research. Behaviour is configured by
swappable **packs**, not hardcoded logic.

This repository is the distribution source for the **ChatGPT / Codex** build of
the plugin. It carries the `.codex-plugin/plugin.json` manifest, with the
marketplace interface metadata (display name, category, capabilities, starter
prompts). It is generated from the Claude Code plugin by
[`scripts/build-from-plugin.py`](./scripts/build-from-plugin.py); the skills,
packs, capabilities and templates are the same files.

Version **5.7.4** · proprietary, all rights reserved · maintained by Worksona (David Olsson,
<david@atomic47.co>) for [Atomic 47 Labs](https://atomic47.co).

**Upgrading from 4.9?** Read [UPGRADE-4.9-to-5.7.4.md](./UPGRADE-4.9-to-5.7.4.md).
Your `project-state/` folder needs no migration.

## What's in this repo

| Path | What it is |
|------|------------|
| [`project-state/`](./project-state) | The plugin bundle, uncompressed. Point Codex at this folder. |
| [`dist/project-state-5.7.4.zip`](./dist/project-state-5.7.4.zip) | The same bundle as a single archive, for sending to someone who is not cloning the repo. |
| [`dist/project-state-5.7.4.zip.sha256`](./dist/project-state-5.7.4.zip.sha256) | Checksum for that archive. |
| [`Project-State-Installation-and-Onboarding.md`](./Project-State-Installation-and-Onboarding.md) | Installation, onboarding, verification and troubleshooting. Start here. |
| [`UPGRADE-4.9-to-5.7.4.md`](./UPGRADE-4.9-to-5.7.4.md) | What changes for a 4.9 user, and what does not. |
| [`scripts/build-from-plugin.py`](./scripts/build-from-plugin.py) | Regenerates `project-state/` from a Claude Code plugin release. |
| [`scripts/verify-bundle.sh`](./scripts/verify-bundle.sh) | Confirms the uncompressed tree is byte-identical to the archive. |

```bash
./scripts/verify-bundle.sh
```

## Install

Read [the installation guide](./Project-State-Installation-and-Onboarding.md)
before running anything. The short version:

```bash
git clone https://github.com/Atomic-47-Labs/project-state-chatgpt.git
```

Open `project-state-chatgpt/project-state/` as a local project in Codex, then ask
it to register that bundle in your personal plugin marketplace and install
`project-state` from it. Once the marketplace entry validates:

```bash
codex plugin add project-state@personal
```

Substitute your own marketplace name if it is not `personal`. Verify in a **new**
task that `project-state:project-onboarding`, `project-state:project-state` and
`project-state:project-milestone-manager` load.

`project-state/README.md` and `project-state/VERIFY.md` inside the bundle carry
**Claude Code** commands (`/plugin`, `claude plugin …`). Ignore those here; the
guide in this repo is the Codex path.

## How skills write: the local server, or the files

State is the source of truth: a typed `project-state/` folder of YAML, JSON,
NDJSON and Markdown in your project. Since 5.0 the skills can write it two ways,
and choose for themselves (`skills/project-state/SKILL.md`, "Substrate binding").

**1. Through the bundled local server (Codex).** The bundle ships
`server/state-mcp-local.mjs`, a local MCP server, declared in
`project-state/.mcp.json`. Codex starts it for a task, over the
`project-state/` folder of the project you are working in. Every write goes
through it: it is checked against the kind registry, refused if the file
changed on disk since it was read, stamped (`last_modified`,
`last_modified_by`), and logged to `logs/activity.ndjson` with your email as the
actor. It needs **Node 20.10 or later** on your `PATH`.

**Who your records are signed by.** The server signs with
`$PROJECT_STATE_ACTOR` if set, else `git config user.email` (no-reply addresses
are skipped). In this build it **never** falls back to your computer's login
name: with neither set, it serves reads only and refuses writes with "writes
need a signed-in person to attribute them to". Set one of them once:

```bash
git config --global user.email you@example.com
```

**2. Directly on the files (hosted ChatGPT, or no Node).** A ChatGPT chat
cannot start a local server, and Codex cannot start this one without Node.
The skills then write the files themselves, following the same rules the
server enforces, as every version before 5.0 did:

- one file per entity, named by convention: `milestones/M<NN>-<slug>.yaml`,
  `decisions/YYYY-MM-DD-<slug>.yaml`, `risks/R-<NN>-<slug>.yaml`, and so on;
- `created` / `created_by` and `last_modified` / `last_modified_by` on every
  write, in ISO-8601 UTC;
- an advisory `<file>.lock` (300 s TTL) around each write;
- one line appended to `logs/activity.ndjson` per write (`ts`, `actor`,
  `event`, `id`, `summary`); existing lines are never rewritten;
- the actor is your email: `$PROJECT_STATE_ACTOR`, else the one the host says
  you are signed in as, else `git config user.email`, else the assistant asks
  once and reuses the answer.

Nothing checks these writes but the assistant. To have them checked, use Codex
with Node, or ask for validation after a session ("use project-state to
validate this project's stored records").

## What cannot be carried over to ChatGPT / Codex

| Claude Code feature | In this build |
|---|---|
| **Subagents** (`agents/research-*.md`, dispatched in parallel by the research skills) | Shipped as files. Codex plugins have no subagents, so the research skills run those steps themselves, one at a time. Slower; same output. |
| **Slash commands** (`/project-kanban`, `/project-feedback`, …) | None. Ask for the skill by name or by what you want ("draft this week's status report"). |
| **Claude artifacts** (`project-artifacts`, `project-console` snapshot pages) | Not available. The HTML templates ship, but nothing publishes them. |
| **claude.ai routines and Claude Desktop scheduled tasks** (`project-harvest-setup`, `project-scheduler host setup`, `project-fanout`) | Not available. The reporting schedule is still stored; run the daily tick by asking ("run the orchestrator tick"). The OS-scheduler host runs Claude Code headless, so it does not apply either. |
| **The Project State cloud connector** (projects with `home: server`) | Not wired. A folder whose project moved to the cloud is read-only here, and the skills say where it lives. |
| **The local kanban / desktop app** | Not part of either plugin. |

## What's inside the bundle

| Group | Skills |
|-------|--------|
| Foundation | `project-state` (memory layer), `project-scaffolder`, `project-onboarding`, `project-onboarder`, `project-admin`, `project-educator` |
| Core ops | `project-phase-gate`, `project-document-curator`, `project-milestone-manager`, `project-goal-tracker`, `project-status-reporter`, `project-inbox` |
| Surfaces & automation | `project-orchestrator`, `project-automator`, `project-scheduler`, `project-fanout`, `project-harvest-setup`, `project-notifier`, `project-review-meeting`, `project-funder-reporting`, `project-change-register`, `project-blog-publisher`, `project-website-publisher`, `project-jira-publisher`, `project-harvester`, `project-doc-suite`, `project-tech-reports`, `project-onepager`, `project-artifacts`, `project-console`, `mindmap-vibe` |
| SR&ED | `sred-onboarding`, `project-sred-tracker`, `project-sred-reviewer` |
| Tender pursuit | `tender-harvester`, `tender-qualifier`, `tender-pipeline`, `tender-monitor` |
| Competitive intel | `intel-onboarding`, `intel-harvester`, `intel-ingest`, `intel-ask`, `intel-brief`, `intel-battlecard`, `intel-compare`, `intel-deal-coach`, `intel-map`, `intel-monitor`, `intel-winloss` |
| Portfolio | `portfolio-onboarding`, `portfolio-collector`, `portfolio-reviewer` |
| Research | `research-onboarding`, `research-mandate`, `research-step`, `research-walk`, `research-deepweb`, `research-ingest`, `research-longlist`, `research-ask`, `research-brief`, `research-redteam`, `research-retro` |
| Grant submission | `grant-state`, `grant-scaffolder`, `grant-ingestor` |
| Closeout & polish | `project-ip-tracker`, `project-external-comms`, `project-lessons`, `project-archive`, `project-git`, `project-feedback` |

`project-doc-suite-generator` ships marked deprecated; `project-doc-suite`
replaces it.

**Packs** (`project-state/packs/`) describe a project on three axes. Work:
`work-general`, `work-campaign`, `work-event`, `work-ops-cycle`, `agile-default`,
`work-sales-pursuit`, `work-research`, `work-partnership`, `work-org-change`,
`work-content`. Accountability: `sponsor-internal`, `pic-pcais`,
`grant-canada`, `client-services`, `board-investor`, `open-source-community`.
Capability defaults: `sred-canada`, `tender-pursuit`, `intel-default`,
`portfolio-default`, `research-default`.

**Capabilities** (`project-state/capabilities/`): SR&ED, tender, intel,
portfolio and research, each with its own schemas, validator and views. Some
validators are Python scripts and need Python 3 with PyYAML.

## Updates

This repo pins version 5.7.4. Cloning does not establish automatic updates.
Keep the installed source folder where it is; when a new version lands here,
update that folder and reinstall from your existing marketplace entry, then
verify again in a new task.

Back up your **project** folder, including `project-state/` and source
documents, with your normal backup system.

## Rebuilding from a Claude Code release

```bash
git -C <project-state source repo> archive v5.7.4 plugin | tar -x -C /tmp/ps-src
python3 scripts/build-from-plugin.py /tmp/ps-src/plugin --scrub <scrub.json>
rm -f dist/*.zip dist/*.sha256
zip -qrX dist/project-state-5.7.4.zip project-state
(cd dist && shasum -a 256 project-state-5.7.4.zip > project-state-5.7.4.zip.sha256)
./scripts/verify-bundle.sh
```

The script's header says what it rewrites and leaves out, and why. The scrub
file is the maintainers' list of client, pilot and people names to remove from
the public bundle. It is not in this repo, because it has to name them; the
build fails if any of them survive.

## License

Proprietary. Copyright Atomic 47 Labs Inc., all rights reserved. This
repository is public so authorised users can install from it; that grants no
licence. Use needs a written agreement with Atomic 47 Labs Inc. See
[LICENSE](./LICENSE).
