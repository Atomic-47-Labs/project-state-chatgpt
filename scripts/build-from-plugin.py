#!/usr/bin/env python3
"""Build the ChatGPT / Codex bundle (./project-state/) from a published Claude Code plugin tree.

    git -C <project-state repo> archive v5.7.4 plugin | tar -x -C /tmp/src
    python3 scripts/build-from-plugin.py /tmp/src/plugin --scrub <scrub.json>

The Claude plugin is the source; this script only translates it. What it changes:

  * .claude-plugin/plugin.json -> .codex-plugin/plugin.json (Codex manifest + marketplace interface).
  * .mcp.json: the same local project-state server, started with ${PLUGIN_ROOT} instead of
    ${CLAUDE_PLUGIN_ROOT}. Codex starts it; hosted ChatGPT cannot, and the skills fall back to files.
  * SKILL.md frontmatter: Codex accepts only name, description, license, allowed-tools and metadata,
    with no angle brackets in the description. Every other top-level key (map, tier, plugin,
    depends_on, slash_command, surfaces) moves, unchanged, under `metadata:`.
  * --scrub FILE (kept outside this public repo, since it has to name what it removes):
      {"drop": [paths], "sub": [[regex, replacement], ...], "deny": [regex, ...]}
    `drop` leaves files out, `sub` rewrites every text file, and the build fails if any `deny`
    pattern still matches anywhere in the bundle. It holds client, pilot and people names.

Everything else is copied byte for byte.
"""
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "project-state"

DROP = {
    ".claude-plugin",  # replaced by .codex-plugin/
    ".mcp.json",  # rewritten below
}

FRONTMATTER_KEEP = {"name", "description", "license", "allowed-tools", "metadata"}

MCP = {
    "mcpServers": {
        "project-state": {
            "command": "node",
            # no cwd: the server finds project-state/ from the session's folder. It finds the
            # capabilities next to itself (server/../capabilities), so no plugin-root env is needed.
            "args": ["${PLUGIN_ROOT}/server/state-mcp-local.mjs"],
            # Records carry a person's email or nothing: without PROJECT_STATE_ACTOR or a non-noreply
            # `git config user.email` the server serves reads only, instead of signing as the OS login.
            "env": {"PROJECT_STATE_NO_OS_ACTOR": "1"},
            # Codex hands an MCP server a minimal environment; these pass through when the user sets them.
            "env_vars": ["PROJECT_STATE_ACTOR", "PROJECT_STATE_DIR", "PROJECT_STATE_REGISTRY", "PS_WORKSPACE_ROOT"],
        }
    }
}


def manifest(src: dict) -> dict:
    return {
        "name": "project-state",
        "version": src["version"],
        "description": (
            "A local-first operational substrate for multi-stakeholder projects: milestones, objectives "
            "and KPIs, phase gates, documents, status reports, funder compliance, SR&ED, tenders, "
            "competitive intel, portfolios and research, shaped by swappable packs."
        ),
        "author": {"name": "Worksona", "email": "david@atomic47.co", "url": "https://atomic47.co"},
        "homepage": "https://github.com/Atomic-47-Labs/project-state-chatgpt",
        "repository": "https://github.com/Atomic-47-Labs/project-state-chatgpt",
        "license": src.get("license", "MIT"),
        "keywords": src.get("keywords", []) + ["intel", "portfolio", "research"],
        "skills": "./skills/",
        "mcpServers": "./.mcp.json",
        "interface": {
            "displayName": "Project State",
            "shortDescription": "Project operations, reporting, and compliance skills.",
            "longDescription": (
                "Manage project state, milestones, objectives, phase gates, documents, reports, grants, "
                "Canadian SR&ED records, tenders, competitive intel, portfolios and research from a "
                "shared local-first project-state/ folder. Where the host can run it, a bundled local "
                "server checks and signs every write."
            ),
            "developerName": "Worksona",
            "category": "Productivity",
            "capabilities": ["Interactive", "Write"],
            "websiteURL": "https://atomic47.co",
            "defaultPrompt": [
                "Set up Project State for this project.",
                "What needs attention on this project today?",
                "Draft this week's status report.",
            ],
        },
    }


def split_frontmatter(text: str):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        raise SystemExit("SKILL.md without frontmatter")
    return m.group(1), text[m.end():]


def codex_frontmatter(fm: str) -> str:
    """Top-level keys outside FRONTMATTER_KEEP move under metadata:, their lines indented two spaces."""
    keep, meta, cur = [], [], None
    for line in fm.split("\n"):
        k = re.match(r"([A-Za-z_-]+):", line)
        if k:
            cur = keep if k.group(1) in FRONTMATTER_KEEP else meta
            if k.group(1) == "metadata":
                raise SystemExit("SKILL.md already has metadata:; merge by hand")
        (cur if cur is not None else keep).append(line)
    out = keep
    if meta:
        out = keep + ["metadata:"] + [("  " + l) if l.strip() else l for l in meta]
    fm = "\n".join(out)
    # Codex refuses angle brackets in the description: `<slug>` becomes `slug`
    return re.sub(
        r"^(description:.*)$",
        lambda d: re.sub(r"<([^<>]*)>", r"\1", d.group(1)),
        fm,
        count=1,
        flags=re.M,
    )


def main():
    if len(sys.argv) != 4 or sys.argv[2] != "--scrub":
        raise SystemExit(__doc__)
    src = Path(sys.argv[1]).resolve()
    scrub = json.loads(Path(sys.argv[3]).read_text())
    drop = DROP | set(scrub.get("drop", []))
    subs = scrub.get("sub", [])
    src_manifest = json.loads((src / ".claude-plugin" / "plugin.json").read_text())

    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(src, OUT, ignore=lambda d, names: [
        n for n in names if str((Path(d) / n).relative_to(src)) in drop
    ])

    for f in sorted(OUT.rglob("*")):
        if not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        new = text
        for pat, rep in subs:
            new = re.sub(pat, rep, new)
        if f.name == "SKILL.md" and f.parent.parent.name == "skills":
            fm, body = split_frontmatter(new)
            new = f"---\n{codex_frontmatter(fm)}\n---\n{body}"
        if new != text:
            f.write_text(new, encoding="utf-8")

    (OUT / ".codex-plugin").mkdir()
    (OUT / ".codex-plugin" / "plugin.json").write_text(json.dumps(manifest(src_manifest), indent=2) + "\n")
    (OUT / ".mcp.json").write_text(json.dumps(MCP, indent=2) + "\n")
    survivors = [
        f"{f.relative_to(ROOT)}: {m.group(0)}"
        for f in sorted(OUT.rglob("*")) if f.is_file()
        for pat in scrub.get("deny", [])
        for m in re.finditer(pat, f.read_text(encoding="utf-8", errors="ignore"))
    ]
    if survivors:
        raise SystemExit("denied names survived the scrub:\n  " + "\n  ".join(survivors))
    print(f"built {OUT.relative_to(ROOT)} from {src} (version {src_manifest['version']})")


if __name__ == "__main__":
    main()
