#!/usr/bin/env bash
# Verify that ./project-state/ is byte-identical to the project-state/ tree
# inside dist/project-state-<version>.zip, and that the zip matches its checksum.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
zip="$(ls "$root"/dist/project-state-*.zip | head -1)"
sums="$zip.sha256"

echo "zip: $(basename "$zip")"
( cd "$root/dist" && shasum -a 256 -c "$(basename "$sums")" )

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
unzip -q "$zip" -d "$tmp"

hash_tree() { ( cd "$1" && find . -type f | LC_ALL=C sort | xargs shasum -a 256 ); }

a="$(hash_tree "$tmp/project-state")"
b="$(hash_tree "$root/project-state")"

if [ "$a" = "$b" ]; then
  echo "tree: OK — $(printf '%s\n' "$b" | wc -l | tr -d ' ') files match the archive"
else
  echo "tree: MISMATCH"
  diff <(printf '%s\n' "$a") <(printf '%s\n' "$b") || true
  exit 1
fi
