#!/usr/bin/env node
// Write an org's own copy of the Project State pages (decision 2026-10-01-surfaces-directory-and-console-front-door,
// item 2): the Console plus its single pages, ready to publish into the admin's own claude.ai account.
//
// The plugin ships one page, console.html, and manifest.json, both built by artifacts/project-state-views/build.mjs.
// Every single page is the Console with three lines changed (title, description, boot line), so they are made here
// rather than shipped 18 times. build.mjs checks that this output equals its own dist/, byte for byte.
//
//   node make.mjs <outdir>     writes <outdir>/<file> for every manifest entry and prints the publish list as JSON

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// One page from the Console: its <title>, its <meta name="description"> and its PS.boot line.
export function pageHtml(consoleHtml, entry) {
  const lines = consoleHtml.split('\n')
  if (!lines[0].startsWith('<title>') || !lines[1].startsWith('<meta name="description"')) throw new Error('console.html does not start with its title and description')
  const boot = lines.findIndex((l) => l.startsWith('PS.boot('))
  if (boot < 0) throw new Error('console.html has no PS.boot line')
  lines[0] = `<title>${entry.title}</title>`
  lines[1] = `<meta name="description" content="${entry.description.replace(/"/g, '&quot;')}">`
  lines[boot] = `PS.boot({ viewIds: ${JSON.stringify(entry.views)}, single: ${entry.views.length === 1}, title: ${JSON.stringify(entry.title)} })`
  return lines.join('\n')
}

const isMain = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
if (isMain) {
  const here = path.dirname(fileURLToPath(import.meta.url))
  const out = process.argv[2]
  if (!out) { console.error('usage: node make.mjs <outdir>'); process.exit(2) }
  const consoleHtml = fs.readFileSync(path.join(here, 'console.html'), 'utf8')
  const manifest = JSON.parse(fs.readFileSync(path.join(here, 'manifest.json'), 'utf8'))
  fs.mkdirSync(out, { recursive: true })
  const list = manifest.map((e) => {
    const file = path.resolve(out, e.file)
    fs.writeFileSync(file, pageHtml(consoleHtml, e))
    return { key: e.key, file, title: e.title, description: e.description, tools: e.tools }
  })
  console.log(JSON.stringify(list, null, 2))
}
