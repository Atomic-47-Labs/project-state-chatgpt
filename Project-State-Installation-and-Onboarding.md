# Project State 5.7.4
## Installation and first-project guide

For recipients of `project-state-5.7.4-chatgpt.zip` (ChatGPT) or `project-state-5.7.4.zip` (Codex) • Prepared 30 October 2026

**Upgrading from 4.9?** Your project folder needs no migration. Read `UPGRADE-4.9-to-5.7.4.md`, then reinstall with sections 2–4 and skip onboarding.

Project State helps an AI assistant maintain project records, milestones, decisions, risks, documents, and reports in a folder on your computer. Installing the plugin makes its workflows available. Onboarding then creates the records for your particular project. These are two separate steps.

## 1. Before you start

Use **Codex desktop with a local project folder** for the procedure below. Sign in with your own account and confirm you can start a local task that reads and writes files. If you have not installed Codex, start at [OpenAI’s Codex documentation](https://learn.chatgpt.com/docs/).

ChatGPT Work with local file access and Plugin Creator may also support the local marketplace workflow. Its controls and account availability can differ; this guide does not assume a regular ChatGPT conversation can install a ZIP. If you only have ordinary ChatGPT chat, use Codex for this installation.

Have these ready:

- The supplied ZIP.
- **Node 20.10 or later** (`node --version`). Without it everything still works, but the plugin's local server cannot start, so writes are not checked by it (see section 4a).
- The email address your records should be signed with.
- A project name and one sentence describing its purpose.
- The project lead and any known start/end dates.
- Any existing proposal, scope of work, milestone schedule, or reporting example. Documents are optional; unknown information can remain marked as missing.

You do not need Slack, Google Drive, Jira, GitHub, or a separate dashboard for the basic local workflow. Those are optional additions.

## 2. Extract and open the plugin

1. Download and extract the zip using your computer’s usual ZIP utility. In ChatGPT, use `project-state-5.7.4-chatgpt.zip`: it asks for no connector. In Codex with Node 20.10+, `project-state-5.7.4.zip` adds the local server that checks every write.
2. Move the extracted `project-state` folder to a stable location, such as **Documents → Codex Plugins → project-state**. Keep it there after installation.
3. Confirm it contains `skills`, `packs`, and `templates`. It also contains a hidden `.codex-plugin` folder with `plugin.json`; Codex can check that for you.
4. In Codex, open or add the extracted `project-state` folder as a local project and start a task there. If the app asks for a folder, select the folder itself, not the ZIP.

**Expected result:** Codex can read the extracted plugin files. It has not yet installed the plugin.

## 3. Register and install

Paste this entire prompt into that task:

```text
Install this existing Project State 5.7.4 plugin for my local Codex account.

Use the built-in plugin-creator skill and its supported helpers. First verify
that the current folder contains .codex-plugin/plugin.json with name
project-state, plus skills/, packs/, and templates/.

Register this existing bundle in my personal plugin marketplace. Preserve
all its content and any other marketplace entries. Do not replace it with
a blank scaffold. If a stable source copy is needed for the helper's layout,
copy the complete bundle and tell me where that source copy lives.

Read and validate the actual marketplace name, then install project-state
from that marketplace using the supported Codex plugin installation command.
The default personal marketplace is discovered automatically; do not add
an extra marketplace for it. Validate the manifest and check the installation
result. Tell me the installed version and source location.

This task is installation only. Do not initialize a project, connect external
accounts, create a GitHub repository, or publish anything.
```

Allow the file access needed to install it if your app requests it. Let Codex finish and report the result. The standard installation command, **after registration**, is `codex plugin add project-state@personal` when the validated marketplace name is `personal`. If your marketplace has a different name, Codex must use that name.

**Expected result:** Codex reports successful installation and the 5.7.4 base version. A local cache suffix may follow the version. If it only reports “files copied” or “marketplace created,” ask it to complete installation and verify the installed entry.

The upstream `project-state/README.md` contains **Claude Code** installation commands. Use this guide for Codex; do not run those `/plugin` instructions here.

## 4. Verify in a new task

Start a **new task** so the installed skills can be picked up. Paste:

```text
Verify that the installed project-state plugin is available in this task.
Confirm that you can load project-state:project-onboarding,
project-state:project-state, and project-state:project-milestone-manager.
Report their actual availability and the installed plugin version.
Do not create or change project files yet.
```

**Pass:** the assistant confirms those installed skills are available. A description of what Project State could do, without confirming actual availability, is not a completed check.

If skills are missing, refresh or restart Codex and try another new task. If still missing, use the troubleshooting table below.

## 4a. Sign your records

Every record names the person responsible by email.

**ChatGPT zip:** there is no server. The assistant writes the files itself and asks once whose name to put on them. Answer with your email address, not your name.

**Codex zip:** set it once, in a terminal:

```bash
git config --global user.email you@example.com
```

Or set `PROJECT_STATE_ACTOR` to your email in the environment Codex starts from. Without either, the plugin's local server answers questions but refuses to write ("writes need a signed-in person to attribute them to"). It never signs records with your computer's login name. A GitHub no-reply address doesn't count.

To check, start a new task in your project folder and ask: "Use project-state's project_list and tell me who writes are signed as." If the server is not running (no Node), the assistant writes the files itself and asks once whose name to put on them.

## 5. Create your first project folder

1. Create a separate folder for the real project, such as **Documents → Projects → Community Pilot**.
2. Open or add that folder as a local Codex project and start a new task in it.
3. Put any source documents in a `source-documents` subfolder, or attach them to the task. Keep originals intact.

The plugin folder holds reusable instructions. Your new project folder holds your project’s records. Use the project folder for ongoing work.

## 6. Run guided onboarding

Replace the bracketed text, then paste:

```text
Use project-state:project-onboarding to onboard this project in the current
folder. My project is [PROJECT NAME]. Its purpose is [ONE SENTENCE].
The project lead is [NAME]. Known dates are [DATES OR UNKNOWN].
Read any documents in source-documents/ and any attachments first.

Use a plain-language conversation suitable for Codex. Ask only for information
you cannot establish from the documents. Show extracted facts for correction.
Leave missing facts explicitly unknown; do not invent dates, budgets,
stakeholders, commitments, or progress.

For this first setup, use local single-user storage. Leave external
integrations, publishing, remote repositories, and scheduled automations off.
Recommend suitable packs based on my project. Show the proposed setup and
file location before initialization. After I confirm, initialize project-state/
using the captured intake without asking the same questions again.

Complete the orientation check and show the files created, the next milestone,
and any missing information. Do not assume I have a separate dashboard.
```

Onboarding collects the following information. You can supply documents instead of answering everything from memory.

| Topic | What to provide |
|---|---|
| Project context | Purpose, stage, sponsor/client, and whether the work ends or continues |
| Identity | Name, lead, organizations, dates, and known budget |
| Documents | Proposal, agreement, scope, schedule, and reporting requirements |
| People | Owners, contributors, reviewers, and intended report recipients |
| Milestones | Deliverables, owners, dates, and evidence of completion |
| Examples | A report you like and any style or content you want to avoid |
| Gaps | What remains unknown and who can resolve it |

### Choosing packs

Packs supply defaults for different project relationships. Select only those that match your work; multiple packs can apply.

Packs come on two axes. Pick one **work** pack (what the project makes happen) and any **accountability** packs (who hears how it's going). Onboarding recommends them from your answers.

| Your situation | Pack to discuss |
|---|---|
| General project, nothing more specific fits | `work-general` |
| Sprint-based software product | `agile-default` |
| Campaign, event, recurring operations cycle | `work-campaign`, `work-event`, `work-ops-cycle` |
| Sales pursuit, research, partnership, organisational change, content | `work-sales-pursuit`, `work-research`, `work-partnership`, `work-org-change`, `work-content` |
| Reports to an internal sponsor (the default) | `sponsor-internal` |
| Work for a paying client | `client-services` |
| Board or investor reporting | `board-investor` |
| Protein Industries Canada / PCAIS project | `pic-pcais` |
| Canadian grant | `grant-canada`; ask whether separate grant onboarding is appropriate |

SR&ED, tender pursuit, competitive intel, portfolio and research are **capabilities** with their own onboarding (`sred-onboarding`, `intel-onboarding`, `portfolio-onboarding`, `research-onboarding`). Ask for those separately if relevant; they are not prerequisites for a first project, and their packs are not chosen as project packs.

### Review and initialize

Check the proposed project name, destination folder, packs, milestones, and unknowns. When correct, reply **“Confirm and initialize.”** The bundled onboarding workflow includes this review before initialization.

**Expected result:** a `project-state/` directory inside your project folder, including `manifest.yaml`, project state, reporting configuration, and supporting records. The assistant should identify what it actually created and any incomplete fields. Onboarding should not require a second identical interview from the scaffolder.

## 7. Check that the project is usable

Paste:

```text
Use project-state to validate this project's stored records. Then summarize
the project purpose, active phase, milestones and owners, next deadline,
risks, and missing information. Identify the files supporting the summary.
Do not fill gaps with invented information.
```

Compare the answer with your source documents. Correct errors before relying on reports.

Then try one real update:

```text
Record this decision in project-state: [DECISION].
Reason: [REASON]. Owner: [NAME]. Date: [DATE].
Confirm the saved record and where it was written.
```

Start another task in the **same project folder** and ask for the latest decision. If it retrieves the saved record, you have verified that the information persists across conversations.

## 8. Your first week

Use ordinary requests like these:

- “Show the next milestones and anything blocked.”
- “Update [milestone] with this progress: [facts and evidence].”
- “Record this risk, its owner, and the mitigation: [details].”
- “Triage the documents I added and flag obligations or dates for review.”
- “Draft a weekly status report from the saved records. Mark missing information and do not send it.”

Goals and KPIs are a separate setup step. Ask: “Use project-goal-tracker to help me define one objective and a measurable KPI, including its baseline, target, owner, and measurement cadence.” The bundle mentions a Goals tab in a separate dashboard; that dashboard is not included. Use the skill through conversation and have the assistant report any runtime dependency it cannot satisfy.

Connect external services only when you need them, using your own accounts. A reporting schedule stored in files does not by itself prove that a recurring automation is running; ask for separate scheduling setup and verification when ready.

## Troubleshooting

| Symptom | What to do |
|---|---|
| “I cannot access local files” | Use a local Codex project and open the extracted folder. A regular chat attachment is insufficient for this workflow. |
| Plugin Creator is unavailable | Confirm you are in a supported local Codex environment. Ask the assistant to locate the built-in skill; do not have it invent installation commands. |
| “Marketplace/plugin not found” | Ask Codex to inspect the personal marketplace entry, validate its actual name, and confirm its source points to the complete plugin folder before retrying installation. |
| Installed, but skills absent | Refresh/restart Codex and start a new task. Ask it to inspect the installed plugin entry and enabled state. |
| `codex` command not found | Ask Codex to locate its supported CLI or use its available plugin installation controls. Stop short of claiming installation succeeded. |
| Asked to use Claude, a Goals tab, or keep-state dashboard | Say: “I am using Codex without that dashboard. Use the installed skills through conversation and report any unavailable dependency.” |
| Onboarding asks the same questions twice | Ask it to pass the captured intake to project-scaffolder rather than restarting the interactive wizard. |
| `project-state/` already exists | Request validation or re-orientation of the existing project. Do not start a fresh scaffold over it. |
| Report contains unsupported details | Ask it to identify the source, correct the underlying record, and regenerate the report. |
| External service unavailable | Continue local work; connect that service separately when needed. |
| "writes need a signed-in person to attribute them to" | Set your email (section 4a), then start a new task. |
| The `project-state` MCP server does not start | Check `node --version` is 20.10 or later and on your `PATH`. Until it is, the skills write the files directly; ask for validation after each session. |
| The assistant offers to "migrate" a 4.9 project | Decline. 5.7.4 reads a 4.9 folder as it is; see `UPGRADE-4.9-to-5.7.4.md`. |

## Updates and backups

This ZIP is a snapshot of version 5.7.4; it does not establish automatic updates. Keep the installed source folder. For a future supplied version, ask Plugin Creator to update that source and reinstall from the existing marketplace using its supported update workflow, then verify in a new task.

Back up your **project folder**, including `project-state/` and source documents, using your normal backup system. Sending someone the plugin does not give them your project records, account connections, or access to your project.

## Verification scope and references

This guide was checked against the supplied plugin's manifest, onboarding/scaffolder/goal-tracker instructions, the installed Plugin Creator instructions, and local `codex plugin` command help. The bundle installs in a clean Codex home (`codex plugin add`), every skill passes Codex's skill validator, and the bundled server was run against a 4.9 project folder. It has not been tested on the recipient's account or computer. Some bundled skills retain Claude-specific and separate-dashboard references (see the README's "What cannot be carried over"); installation does not establish compatibility of every optional workflow.

- [OpenAI: Build plugins — local marketplace installation and new-conversation testing](https://learn.chatgpt.com/docs/build-plugins)
- Bundle: `.codex-plugin/plugin.json`, `skills/project-onboarding/SKILL.md`, `skills/project-scaffolder/SKILL.md`, and `skills/project-goal-tracker/SKILL.md`

**Finished when:** installation is verified in a new task, onboarding has created the intended project records, the summary matches your facts, and a later task can retrieve a saved decision.
