---
name: project-console
description: "Open Project State where it lives — 'open my console', 'open the admin', 'show me Runs'. Cloud: the Console pages; local: the kanban or a snapshot. Org admins: 'publish our console' puts the org's own pages in their account."
metadata:
  map:
    tier: P2
    stage: generate
    requires: [memory]
    reads: [manifest]
    calls: [project-artifacts]
    delivers: [artifact, kanban, chat]
---

# Project Console (the front door: where each project opens)

> **When to use — full trigger description.** The frontmatter carries a short, trigger-first
> description so all of the suite's skills fit Claude Code's skill-listing budget (see
> docs/SKILL-SPEC.md, *Description budget*). The complete version, kept here:
>
> Find and open the place a person works on their projects. Cloud projects open in the Project State
> Console and its single pages (Today, Harvest, …; Admin and Runs for org admins), live through the
> Project State connector. Local projects open in the kanban (live and editable, on this machine) or
> as a snapshot (a private, read-only picture published by `/project-artifacts`). Someone who has
> both gets one answer that says which project opens where and where each one is changed. Trigger on
> 'open my console', 'open the project state console', 'where is my dashboard', 'how do I see my
> projects', 'open the admin', 'where do I manage people', 'show me the Runs page', 'open the
> kanban', 'what links do I have', 'where do I open project X'. For an org admin it also publishes the
> org's own copy of the pages from this plugin and registers them ('publish our console', 'set up the
> console for my org', 'update our pages'; section 5). Trigger:
> /project-console [project | admin | runs | <page> | publish]

Decision `2026-10-01-surfaces-directory-and-console-front-door`. The links come from the servers,
never from this file: each server's `project_list` (and the cloud's `whoami`) carries `surfaces`.

## 1. See what is connected

There are two servers a person can have, and either, both or neither may be present:

- **Local**: the plugin's own server (in Claude Code it is `plugin:project-state:project-state`).
  Its `project_list` rows carry a `folder`; its `surfaces` has `kanban` and `snapshots`.
- **Cloud**: the **Project State** connector (`cloud.project-state.app`). It has `whoami`; its
  `surfaces` has `connector`, `orgs[].pages` and, for admins, `web_admin`.

Call `project_list` on each one present, in parallel. In claude.ai only the cloud can be present.

With **neither**, say how to connect and stop:
- cloud: in claude.ai, Settings → Connectors → Add custom connector, named exactly **Project State**,
  URL `https://cloud.project-state.app/mcp`, then sign in by the emailed link;
- local: install the project-state plugin in Claude Code or the desktop app, in a folder that holds
  a `project-state/`.

A `surfaces` key missing from an answer means that server predates this skill (a plugin or server
from before it): say the links are not listed there yet and fall back to section 4's defaults.

## 2. Place each project

Every project has one **home**, and is changed only there:

| Seen as | Home | Opens in | Changed in |
|---|---|---|---|
| cloud row, `home: server` | cloud | the Console | the Console, or Claude through the connector |
| cloud row, `home: local` | someone's machine (a read-only **mirror**) | the Console, read-only | at its home: the kanban or Claude Code there |
| local row, `home: local` | this machine | the kanban, or a snapshot | the kanban, or Claude Code through the local server |
| local row, `moved_to` set | cloud | the Console | the Console (this folder is read-only) |

The same project on both servers is one project: match by `moved_to`, or by name when a cloud
mirror and a local folder carry the same one. Say it once, with its home.

## 3. Open the right thing

Use what the person asked for; with no target, open the Console for cloud work and name the
kanban for local work.

- **The Console or a page** (`today`, `harvest`, `queue`, …): take the URL from the cloud
  `surfaces.orgs[].pages` of the org the project belongs to. Open it with the Artifact tool
  (`action: "open"`) where there is one; otherwise give the link. Pages read live through the
  viewer's own connector and hold no data, so the person sees only their own projects.
- **Admin or Runs**: the same, from that org's pages; they are listed only for its admins. Also
  give `web_admin` (people, roles, project access, moves) when it is present. A person who is not an
  admin gets neither: say who can (their org's admins) rather than looking for a way round.
- **No page set for the org** (`note` on that org): read the note to the person. If they are an
  org admin, offer section 5: publish the org's own pages from this plugin and register them. If
  they already have published pages, you can instead set the links they give you with `admin_org`
  `action: "links"`. Both are changes, so confirm first. Meanwhile answer from the connector
  directly (`view_today`, …).
- **A local project**: the kanban at `surfaces.kanban.url`. In Claude Code you may check it is up
  (`curl -s -o /dev/null -w '%{http_code}' http://localhost:3355`); if it is not, offer
  `/project-kanban`. If `surfaces.snapshots` has this project, give that link and when it was
  taken, and offer to refresh it. If there is none and the person wants a page in Claude, hand
  over to **project-artifacts** (`make`), which records and publishes it only on their go-ahead.
- **A mirror**: open it in the Console, and say plainly that edits happen at its home.

## 4. Answer

Short: one line per project (name, where it opens, where it is changed) and the links. For someone
with both kinds, a small table is clearest. Never paste project data; the pages show it.

When a server gave no `surfaces`: cloud, give the connector URL and say an org admin can list the
pages once the server is updated; local, the kanban is `http://localhost:3355` (`/project-kanban`).

## 5. Publish the org's pages (org admins)

Decision `2026-10-01-surfaces-directory-and-console-front-door`, item 2: the page, not the link. The
pages hold no data, so each org publishes its own copy into an admin's claude.ai account. Nobody
depends on another org's account, and the pages open for that org's people once the admin shares
them. A page that reads a connector cannot be public, so another org's copies are no use.

The plugin ships them in this skill's `pages/` folder: `console.html`, `manifest.json` (one entry
per page: its `key` in the org's links, file, title, description and the exact tools it calls) and
`make.mjs`, which writes the single pages from the Console.

1. **Check who and where.** The cloud `whoami` must show the person as `admin` of the org (or a
   superadmin). Publishing needs the Artifact tool. Without it (claude.ai chat, for instance), say
   this step runs in Claude Code and stop.
2. **Confirm before anything is published.** Name the org and say what will happen: the manifest's
   pages are published into *their* claude.ai account, private until they share them, then
   registered for the org so every member's `whoami` lists them. If `surfaces.orgs[].pages` already
   lists pages for the org, this is an **update**: each page is republished to the URL it already
   has, so links people saved keep working. Go on only on a clear yes.
3. **Make the pages.** Run `node <this skill's folder>/pages/make.mjs <scratchpad>/ps-pages`. It
   writes one file per manifest entry and prints the publish list (key, file, title, description,
   tools). Read `console.html` in full before the first publish: every other page is the same file
   with its title, description and boot line changed.
4. **Publish each page.** Use the Artifact tool once per entry, with:
   - `file_path`: the entry's file; `title` and `description` from the entry;
   - `capabilities`: `{"mcp":{"servers":[{"server":"Project State","tools":<the entry's tools>}]}}`;
   - `icon: "dashboard"` on a new page. On an update, pass the page's current URL as `url`, read
     it first (`action: "read"`) as the tool requires, and leave `icon` out.

   Record each URL against its `key`. If a publish is refused, stop and report the refusal word for
   word. Never change a page or its capabilities to get it through.
5. **Register.** Call `admin_org` `action: "links"` for the org, with `links` an object (not a
   string) of every key and URL. A connector whose `admin_org` has no `links` action, or rejects an
   object, has a stale tool list: say so and suggest a fresh session.
6. **Check.** Call `whoami`. The org's `pages` must list every key from the manifest, the Console
   first, with no `note`.
7. **Hand over.** Give the Console link and say what is left for them:
   - share each page in claude.ai (open it, then Share), the Console and Harvest first. Until they
     do, members are listed the links but cannot open them;
   - pages from an earlier publisher can be deleted by whoever owns them once the new ones work.
     Never delete one yourself.

When the plugin is updated, its pages may change: run this section again and it updates them in
place.

## Rules

- **Reads, apart from two changes.** It can set the org's links (`admin_org` `links`) and publish
  the org's pages (section 5). Both are done for an org admin, only after they confirm.
- **Links come from the servers.** Never guess an artifact URL, and never reuse one from another
  org's answer.
- **Private pages.** A page opens for the people its publisher shared it with. If it will not open
  for someone, its publisher shares it from claude.ai; a snapshot holds data and is shared only by
  the person who made it.

## Not this skill

- **project-artifacts**: records and publishes a snapshot of a local project.
- **project-admin**: creates, pulls and lists local projects and their GitHub hub.
- **project-orchestrator**: "what should I do today" — the answer, not the place to see it.
