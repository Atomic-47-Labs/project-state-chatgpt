---
name: project-admin
description: "Create, pull or list project-state projects in the local-first + GitHub-hub model — 'create a new project repo', 'pull project X', 'list our projects', 'register this project'."
metadata:
  map:
    tier: P3
    stage: keep
    requires: [memory, python, shell, git, local-fs]
    reads: [manifest]
    calls: [project-scaffolder]
    delivers: [github-hub]
---

# Project Admin

> **When to use — full trigger description.** The frontmatter carries a short, trigger-first
> description so all of the suite's skills fit Claude Code's skill-listing budget (see
> docs/SKILL-SPEC.md, *Description budget*). The complete version, kept here:
>
> Manage project-state projects in the local-first + GitHub-hub model. Sub-actions: create (scaffold a new project-state substrate, create its private GitHub state repo, push, and — only when the operator has configured one — register it in a read-only viewer), pull (clone an existing project's state repo to a local working copy), list (show the projects this machine and the GitHub owner know about). Use when the user says 'create a new project', 'new project-state', 'pull down project X', 'clone the state for X', 'check out a project', 'list projects', 'what projects exist', 'register a project with the dashboard', or any request to create, fetch, or enumerate project-state projects. Members and roles are managed via GitHub repo permissions, not here.

Manage project-state **projects** in the local-first model: local substrate is
authoritative and a per-project GitHub repo is the hub. A read-only Vercel viewer
that reads the repos listed in its `GITHUB_STATE_REPOS` env var is **optional and
off unless the operator configures it** (see *Optional: a read-only viewer*) — it
belongs to the retired GitHub-hub model, and this skill names no one's Vercel team.

**Members/roles are NOT managed here** — they are GitHub repo permissions
(collaborators / org teams). To add an editor, grant them `write` on the state
repo; to add a viewer, share the dashboard URL + a view token.

## Conventions

- A project `org/name` (e.g. `worksona/q3-fun`) maps to one **private GitHub
  state repo** (e.g. `worksona/q3-fun-state`).
- The repo holds the substrate at `project-state/` in its root.
- The repo description is `project-state: <org>/<name>` — `list` finds hub repos by it.

Require `gh` authenticated with `repo` scope for repo create/clone/collaborators.

## Optional: a read-only viewer

Skip this section — and every viewer step below — unless `~/.project-state/config.json`
carries a `viewer` block. **Never** go looking for one: do not read a Vercel CLI auth file,
guess a team, or assume a project name. An install without the block has no viewer, and
`create`, `pull` and `list` work fully without it.

```json
"viewer": {
  "kind": "vercel",
  "project": "<vercel project name>",
  "team_id": "<team_…>",
  "dashboard_url": "https://<your-viewer-host>/dash/{org}/{name}/kanban",
  "token": "env:VERCEL_TOKEN"
}
```

`token` says where the Vercel API token comes from, and only what it says is read:

- `env:<VAR>` (the default if omitted) — the named environment variable. If it is unset,
  stop and say so; do not fall back to anything else.
- `vercel-cli` — the operator has explicitly chosen to reuse the Vercel CLI's stored login
  (`~/Library/Application Support/com.vercel.cli/auth.json` on macOS,
  `~/.local/share/com.vercel.cli/auth.json` on Linux). Read it only under this setting, and
  say once that you are doing so.

```bash
TOK="$VERCEL_TOKEN"     # or the CLI auth file, only when token is "vercel-cli"
TEAM=<viewer.team_id>
PROJECT=<viewer.project>
```

The viewer's registry is its `GITHUB_STATE_REPOS` env var:
`{"<org>/<name>": "<owner>/<repo>", ...}`. Writing it changes a deployed service's
configuration, so confirm with the operator before each upsert.

---

## `create`

Create a new project end to end.

1. Confirm `org`, `name`, and compliance `pack` with the user. Derive the state
   repo name (default `<name>-state`, owner = the GitHub org).
2. Scaffold the substrate locally by invoking **`project-scaffolder`** in the
   target directory — it creates `project-state/` with the chosen pack.
3. Create the private repo and push:
   ```bash
   gh repo create <owner>/<repo> --private --description "project-state: <org>/<name>"
   cd <project-dir>
   git init -b main 2>/dev/null || git checkout -B main
   git add project-state && git commit -m "Initialize <org>/<name> substrate"
   git remote add origin "https://github.com/<owner>/<repo>.git" 2>/dev/null || git remote set-url origin "https://github.com/<owner>/<repo>.git"
   git push -u origin main
   ```
4. **Only if a viewer is configured** — register it in the viewer's `GITHUB_STATE_REPOS`
   (read → merge key → confirm → upsert): read the current value from Vercel, add
   `"<org>/<name>": "<owner>/<repo>"`, and upsert via
   `POST /v10/projects/$PROJECT/env?teamId=$TEAM&upsert=true` with
   `{key:"GITHUB_STATE_REPOS", value:<merged json>, type:"encrypted", target:["production","preview","development"]}`.
   With no viewer, skip this step silently.
5. Report where the project lives: the local path and the state repo URL. If a viewer is
   configured, also the dashboard URL from `viewer.dashboard_url` with `{org}` and `{name}`
   filled. Never print a viewer URL the operator did not configure.
6. **Launch the project context page automatically** — no manual navigation needed:
   ```bash
   # Start the local kanban on port 3355 if it isn't already running
   if ! lsof -ti tcp:3355 > /dev/null 2>&1; then
     KANBAN_DIR="$(pwd)/project-state/kanban"
     [ ! -d "$KANBAN_DIR/node_modules" ] && (cd "$KANBAN_DIR" && npm install)
     cd "$KANBAN_DIR" && npm run dev > /tmp/project-kanban.log 2>&1 &
     for i in $(seq 1 15); do lsof -ti tcp:3355 > /dev/null 2>&1 && break; sleep 1; done
   fi
   open http://localhost:3355/onboarding
   ```
   Print: `✓ <org>/<name> created. Opening the setup page — select your compliance packs and orient the project.`

---

## `pull`

Fetch an existing project's state to a local working copy (to edit locally).

1. Resolve the repo: from the argument, or look it up with `list`. If given `org/name`,
   map → `<owner>/<repo>` (default `<org>/<name>-state`).
2. Clone it:
   ```bash
   gh repo clone <owner>/<repo> <dest-dir>
   ```
   The substrate is at `<dest-dir>/project-state/`. The user works there; the
   Stop hook / `project-git` skill commit+push changes back to the hub.
3. If they already have a local copy, prefer `project-git sync` (rebase-safe
   pull) instead of a fresh clone.
4. Report the local path and confirm `project-state/manifest.yaml` is present.

---

## `list`

Show the projects this operator has.

1. **Local:** if `~/.project-state/config.json` names a `workspaceRoot`, read
   `<workspaceRoot>/registry.json` → `projects[]` (the fan-out registry; see `project-fanout`).
2. **Hub:** for each GitHub owner the operator names (ask if unknown), list state repos by
   their description:
   ```bash
   gh repo list <owner> --limit 200 --json nameWithOwner,description \
     --jq '.[] | select(.description | startswith("project-state:")) | "\(.description[15:]) → \(.nameWithOwner)"'
   ```
3. **Viewer (only if configured):** read `GITHUB_STATE_REPOS`:
   ```bash
   curl -s "https://api.vercel.com/v9/projects/$PROJECT/env?teamId=$TEAM&decrypt=true" \
     -H "Authorization: Bearer $TOK" | python3 -c "..."   # find key GITHUB_STATE_REPOS
   ```
4. Present one table: `org/name → owner/repo`, grouped by org, marking which source(s)
   each came from. Optionally annotate each with its latest commit
   (`gh api repos/<repo>/commits --jq '.[0].commit.committer.date'`).

---

## Reads
- `~/.project-state/config.json` — `workspaceRoot` and the optional `viewer` block
- GitHub repos via `gh`
- `GITHUB_STATE_REPOS` (Vercel env) — only when a viewer is configured

## Writes
- New GitHub repos (`create`), local clones (`pull`)
- The `GITHUB_STATE_REPOS` Vercel env var — only with a configured viewer, after confirmation
- Never edits members/permissions — that is GitHub-native

## Related
- `project-scaffolder` — creates the substrate (called by `create`)
- `project-git` — manual commit/push/sync; the Stop hook is the auto path
