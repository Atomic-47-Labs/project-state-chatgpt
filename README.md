# Project State — ChatGPT / Codex plugin

**Project State** is a local-first operational substrate for multi-stakeholder
projects. It bundles **41 active skills** that turn routine reporting into a byproduct of
normal work — milestones, objectives and KPIs, phase gates, document curation,
status reports, funder and grant compliance, Canadian SR&ED records, and tender
pursuit. Behaviour is configured by swappable **compliance packs**, not hardcoded
logic.

This repository is the distribution source for the **ChatGPT / Codex** build of
the plugin. It carries the `.codex-plugin/plugin.json` manifest, including the
marketplace interface metadata (display name, category, capabilities, starter
prompts). The Claude Code build lives in
[Atomic-47-Labs/project-state-plugin-public](https://github.com/Atomic-47-Labs/project-state-plugin-public).

Version **4.9.0** · MIT licensed · built by [Atomic 47 Labs](https://atomic47.co).

## What's in this repo

| Path | What it is |
|------|------------|
| [`project-state/`](./project-state) | The plugin bundle, uncompressed. Point Codex at this folder. |
| [`dist/project-state-4.9.0.zip`](./dist/project-state-4.9.0.zip) | The same bundle as a single archive, for sending to someone who is not cloning the repo. |
| [`dist/project-state-4.9.0.zip.sha256`](./dist/project-state-4.9.0.zip.sha256) | Checksum for that archive. |
| [`Project-State-Installation-and-Onboarding.md`](./Project-State-Installation-and-Onboarding.md) | The full installation, onboarding, verification, and troubleshooting guide. Start here. |
| [`scripts/verify-bundle.sh`](./scripts/verify-bundle.sh) | Confirms the uncompressed tree is byte-identical to the archive. |

The uncompressed tree and the archive hold the same 169 files. Neither is derived
from the other at build time, so the verification script exists to keep them
honest.

```bash
./scripts/verify-bundle.sh
```

## Install

Read [the installation guide](./Project-State-Installation-and-Onboarding.md)
before running anything. It covers the account prerequisites, the exact prompts
to paste, how to verify the install in a fresh task, and what to do when a step
fails. The short version:

```bash
git clone https://github.com/Atomic-47-Labs/project-state-chatgpt.git
```

Open `project-state-chatgpt/project-state/` as a local project in Codex, then ask
it to register that bundle in your personal plugin marketplace and install
`project-state` from it. Confirm the folder contains `.codex-plugin/plugin.json`,
`skills/`, `packs/`, and `templates/` first. Once the marketplace entry validates,
installation is:

```bash
codex plugin add project-state@personal
```

Substitute your own marketplace name if it is not `personal`. Verify in a **new**
task that `project-state:project-onboarding`, `project-state:project-state`, and
`project-state:project-milestone-manager` load.

If you are downloading the archive instead of cloning, extract it and use the
extracted `project-state` folder the same way.

Note that `project-state/README.md` inside the bundle carries **Claude Code**
install commands. Ignore those here; the guide in this repo is the Codex path.

## Then start a project

Installation makes the workflows available. It does not create any project
records. Open a **separate** folder for the real project and run guided
onboarding there:

```text
Use project-state:project-onboarding to onboard this project in the current folder.
```

The guide walks through the intake, pack selection, and the first-week
conversations. The plugin folder holds reusable instructions; your project folder
holds your project's records. They stay separate.

## What's inside the bundle

| Group | Skills |
|-------|--------|
| Foundation | `project-state` (memory layer), `project-scaffolder`, `project-onboarding`, `project-onboarder`, `project-admin` |
| Core ops | `project-phase-gate`, `project-document-curator`, `project-milestone-manager`, `project-goal-tracker`, `project-status-reporter`, `project-inbox` |
| Surfaces & automation | `project-orchestrator`, `project-automator`, `project-notifier`, `project-review-meeting`, `project-funder-reporting`, `project-change-register`, `project-blog-publisher`, `project-website-publisher`, `project-jira-publisher`, `project-harvester`, `project-doc-suite`, `project-tech-reports`, `project-onepager`, `mindmap-vibe` |
| Compliance | `project-sred-tracker`, `project-sred-reviewer`, `sred-onboarding` |
| Tender pursuit | `tender-harvester`, `tender-qualifier`, `tender-pipeline`, `tender-monitor` |
| Grant submission | `grant-state`, `grant-scaffolder`, `grant-ingestor` |
| Closeout & polish | `project-ip-tracker`, `project-external-comms`, `project-lessons`, `project-archive`, `project-git`, `project-feedback` |

A 42nd skill directory, `project-doc-suite-generator`, ships marked deprecated.
`project-doc-suite` replaces it.

**Packs** (`project-state/packs/`) — `pic-pcais`, `grant-canada`, `sred-canada`,
`board-investor`, `client-services`, `agile-default`, `open-source-community`.
Several skills are profile-driven: they read their behaviour from the active
pack's YAML profiles rather than from their own instructions.

**Capabilities** (`project-state/capabilities/`) — larger bolt-on surfaces with
their own schemas and views: Canadian SR&ED and tender intelligence.

**Templates** (`project-state/templates/`) — scaffolder seeds: phase presets,
phase manifests, the manifest and reporting-matrix templates, one-pager layouts,
and a website starter.

## How it works

State is the source of truth. Everything lives in a typed `project-state/`
filesystem — YAML, JSON, NDJSON, and markdown — created by the scaffolder.
Reports are generated *from* state. When an artifact disagrees with state, you
regenerate the artifact rather than editing it.

Nothing leaves your machine on its own. External sends — email, funder claims,
steering-committee packs, public posts — always stop at a draft for human review.
Optional integrations such as Slack, Google Drive, Jira, and GitHub use your own
accounts and are off until you connect them.

## Updates

This repo pins version 4.9.0. Cloning does not establish automatic updates. Keep
the installed source folder where it is; when a new version lands here, update
that folder and reinstall from your existing marketplace entry, then verify again
in a new task.

Back up your **project** folder, including `project-state/` and source documents,
with your normal backup system. Handing someone the plugin gives them the
workflows, not your project records or account connections.

## License

MIT — see [LICENSE](./LICENSE).
