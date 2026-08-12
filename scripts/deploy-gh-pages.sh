#!/usr/bin/env bash
# Build the static site from the ISO and push it to the gh-pages branch.
#
# The main branch never contains generated game data; the gh-pages branch
# holds the built site (viewer + collision/entities JSON). Regenerate with:
#
#   NICK_ISO=/path/nicktoonsunite.iso scripts/deploy-gh-pages.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

ISO="${NICK_ISO:-${1:-}}"
if [ -z "$ISO" ]; then
  echo "usage: deploy-gh-pages.sh /path/nicktoonsunite.iso   (or set NICK_ISO)" >&2
  exit 2
fi
[ -f "$ISO" ] || { echo "ISO not found: $ISO" >&2; exit 2; }

BRANCH="${PAGES_BRANCH:-gh-pages}"
TMP="$(mktemp -d)"
WT="$(mktemp -d)"
rmdir "$WT"  # worktree add needs a non-existent path
cleanup() { cd "$ROOT"; rm -rf "$TMP"; git worktree remove --force "$WT" 2>/dev/null || rm -rf "$WT"; }
trap cleanup EXIT

echo "== extracting ISO -> site =="
nix run .#extract -- --iso "$ISO" --out "$TMP"

echo "== overlaying viewer =="
cp -r viewer/. "$TMP"/

echo "== publishing to $BRANCH =="
git fetch origin --quiet || true
if git rev-parse --verify "origin/$BRANCH" >/dev/null 2>&1; then
  git worktree add -f "$WT" "origin/$BRANCH" -B "$BRANCH"
else
  git worktree add -f --orphan "$WT" -B "$BRANCH"
fi

(cd "$WT" && git rm -rf --quiet . 2>/dev/null || true)
rsync -a --delete --exclude=.git "$TMP"/ "$WT"/
cd "$WT"
git add -A
if git diff --cached --quiet; then
  echo "no changes to deploy"
else
  git commit -m "deploy: $(date -u +%Y-%m-%dT%H:%M:%SZ) ($(basename "$ISO"))"
  git push origin "$BRANCH"
  echo "deployed to $BRANCH"
fi
