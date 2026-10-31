#!/usr/bin/env bash
# Package ./project-state/ into the two downloads in dist/:
#   project-state-<v>-chatgpt.zip  ChatGPT: files only. No MCP server is declared, so ChatGPT asks for no
#                                  connector and the skills write the project-state/ files directly.
#   project-state-<v>.zip          Codex: the whole tree, with .mcp.json and the local server.
# Each gets a .sha256. Run after scripts/build-from-plugin.py; then scripts/verify-bundle.sh.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
v="$(python3 -c 'import json;print(json.load(open("project-state/.codex-plugin/plugin.json"))["version"])')"
rm -f dist/*.zip dist/*.sha256
mkdir -p dist
zip -qrX "dist/project-state-$v.zip" project-state

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
cp -R project-state "$tmp/"
rm "$tmp/project-state/.mcp.json" "$tmp/project-state/server/state-mcp-local.mjs"
python3 - "$tmp/project-state/.codex-plugin/plugin.json" <<'PY'
import json, sys
p = sys.argv[1]; m = json.load(open(p))
m.pop("mcpServers")
m["interface"]["longDescription"] = m["interface"]["longDescription"].replace(
    " Where the host can run it, a bundled local server checks and signs every write.", "")
open(p, "w").write(json.dumps(m, indent=2) + "\n")
PY
(cd "$tmp" && zip -qrX "$root/dist/project-state-$v-chatgpt.zip" project-state)

cd dist
for z in *.zip; do shasum -a 256 "$z" > "$z.sha256"; done
ls -la
