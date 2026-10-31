#!/usr/bin/env bash
# Verify both downloads in dist/ against ./project-state/ and their checksums:
#   project-state-<v>.zip          byte-identical to ./project-state/
#   project-state-<v>-chatgpt.zip  the same, less .mcp.json and server/state-mcp-local.mjs,
#                                  with only .codex-plugin/plugin.json differing
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
v="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["version"])' "$root/project-state/.codex-plugin/plugin.json")"
full="$root/dist/project-state-$v.zip"
gpt="$root/dist/project-state-$v-chatgpt.zip"

( cd "$root/dist" && shasum -a 256 -c "$(basename "$full").sha256" "$(basename "$gpt").sha256" )

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir "$tmp/full" "$tmp/gpt"
unzip -q "$full" -d "$tmp/full"
unzip -q "$gpt" -d "$tmp/gpt"

hash_tree() { ( cd "$1" && find . -type f | LC_ALL=C sort | xargs shasum -a 256 ); }

a="$(hash_tree "$tmp/full/project-state")"
b="$(hash_tree "$root/project-state")"
if [ "$a" = "$b" ]; then
  echo "codex zip: OK — $(printf '%s\n' "$b" | wc -l | tr -d ' ') files match the tree"
else
  echo "codex zip: MISMATCH"; diff <(printf '%s\n' "$a") <(printf '%s\n' "$b") || true; exit 1
fi

expected="$(printf '%s\n' "$b" | grep -v -e ' \./\.mcp\.json$' -e ' \./server/state-mcp-local\.mjs$' -e ' \./\.codex-plugin/plugin\.json$')"
got="$(hash_tree "$tmp/gpt/project-state" | grep -v ' \./\.codex-plugin/plugin\.json$')"
if [ "$expected" = "$got" ] && ! grep -q mcpServers "$tmp/gpt/project-state/.codex-plugin/plugin.json"; then
  echo "chatgpt zip: OK — $(printf '%s\n' "$got" | wc -l | tr -d ' ') files + manifest, no MCP server declared"
else
  echo "chatgpt zip: MISMATCH"; diff <(printf '%s\n' "$expected") <(printf '%s\n' "$got") || true; exit 1
fi
