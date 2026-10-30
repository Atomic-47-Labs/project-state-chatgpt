# Verifying a project-state install

Shipped in the plugin as `VERIFY.md` (copied from `docs/VERIFY-INSTALL.md` by
`scripts/publish-plugin.sh` and `scripts/publish-plugin.ps1`). Everything here runs against the
installed plugin alone — no access to the source repository is needed.

**What the plugin does not ship.** The test suites (`scripts/test-*.py`, the server's end-to-end
test, the skill evals under `evals/`) live in the source repository and run there, before every
release: the publishers refuse to build a plugin whose local server fails its end-to-end test, or
whose declared capability payload did not land. What an install can check is that it is the
version it claims, that it loads, and that its server and validators answer on your own project.

## 1. Which version you have, and what changed

```
claude plugin list
```

`CHANGELOG.md` at the plugin root is the full release history, with the names of the
developer's clients, grants and contributors taken out. To read what an upgrade brings,
read every `## v…` section between the version you had and the one `claude plugin list` now
shows. Sections flagged **breaking** or **migration** say what to run.

## 2. The plugin loads

```
claude plugin validate <path-to-the-installed-plugin>
```

The path is the plugin's folder in Claude Code's plugin cache (`claude plugin list` shows it, or
it is the folder holding this file). A clean result means the manifest, skills and MCP
declaration parse.

## 3. The local server answers

In a folder that has a `project-state/` substrate, start Claude Code and ask *"list my
projects"*. The plugin's local project-state server (`server/state-mcp-local.mjs`, started by
`.mcp.json`) answers through its `project_list` tool with the project's folder and whether you
can write. If the tool is missing, run `/mcp` and look for `project-state`: a failure there names
the cause (most often Node not on `PATH`; the server needs Node 20 or later).

## 4. The validators pass on your project

- **Core:** ask *"validate the manifest"* (`project-state` skill). It checks the substrate against
  the project's own `project-state/SCHEMA.md` and composes each enabled capability's validator.
- **Research capability**, if enabled — an executable validator ships with the plugin:

  ```
  python3 <plugin>/capabilities/research/validator/scripts/check.py <path-to>/project-state
  ```

  Exit 0 clean, 1 errors, 2 no facility.

## 5. Nothing points at someone else's infrastructure

A fresh install names no company but yours. If you enable SR&ED, `sred-onboarding` writes your
company's capture lens to `project-state/sred/company-criteria.yaml`; the pack's
`innovation-criteria.yaml` profile ships blank. `project-admin` registers projects in a Vercel
viewer only when `~/.project-state/config.json` carries a `viewer` block you wrote.
`project-feedback` files `severity: data-risk` issues without a confirmation pause only when your
manifest sets `feedback.data_risk_autofile: true`.
