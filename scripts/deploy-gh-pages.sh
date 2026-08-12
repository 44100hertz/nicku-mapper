#!/usr/bin/env bash
# Build the static site from the ISO and push it to the gh-pages branch.
#
# The main branch never contains generated game data; the gh-pages branch
# holds the built site (viewer + collision/entities JSON). Regenerating is a
# one-liner:
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
trap 'rm -rf "$TMP" "$ROOT/.gh-pages-worktree"' EXIT

echo "== extracting ISO -> site =="
nix run .#extract -- --iso "$ISO" --out "$TMP"

echo "== overlaying viewer =="
# extractor writes collision/ + entities/ + build-info.json; overlay the viewer
# source on top so the result is a self-contained static site.
cp -r viewer/. "$TMP"/

# gh-pages worktree (create the branch if it doesn't exist yet)
git fetch origin --quiet || true
if git rev-parse --verify "origin/$BRANCH" >/dev/null 2>&1; then
  git worktree add -f .gh-pages-worktree "origin/$BRANCH"
  (cd .gh-pages-worktree && git checkout -B "$BRANCH" --track "origin/$BRANCH")
else
  git worktree add -f .gh-pages-worktree -b "$BRANCH"
fi

echo "== syncing into gh-pages =="
(cd .gh-pages-worktree && git rm -rf --ignore-unmatch . >/dev/null 2>&1 || true)
rsync -a --delete --exclude=.git "$TMP"/ .gh-pages-worktree/

cd .gh-pages-worktree
git add -A
if git diff --cached --quiet; then
  echo "no changes to deploy"
else
  git commit -m "deploy: $(date -u +%Y-%m-%dT%H:%M:%SZ) (iso $(basename "$ISO"))"
  git push origin "$BRANCH"
  echo "deployed to $BRANCH"
fi
