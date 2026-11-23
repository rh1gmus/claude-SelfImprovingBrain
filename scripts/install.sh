#!/usr/bin/env bash
# Idempotent install of claude_brain for the current user. Safe to re-run; prints "no changes" when nothing was needed.
# Env: CLAUDE_BRAIN (default: repo containing this script), HOME (target user dir).
set -u
BRAIN="${CLAUDE_BRAIN:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
cd "$BRAIN" || exit 1
changed=0
note() { echo "install: $*"; changed=1; }
# exec bits
for f in hooks/* scripts/*; do
  case "$f" in *.md|*.json) continue;; esac
  [ -x "$f" ] || { chmod +x "$f" && note "chmod +x $f"; }
done
# git hooks path (only when brain is a git repo)
if git rev-parse --is-inside-work-tree >/dev/null 2>&1 && [ "$(git config core.hooksPath)" != hooks ]; then
  git config core.hooksPath hooks && note "set core.hooksPath=hooks"
fi
# user-level link: CLAUDE.md import + agent symlinks (link-project.sh is itself idempotent)
out=$(CLAUDE_BRAIN="$BRAIN" bash scripts/link-project.sh --user) || exit 1
[ -n "$out" ] && echo "$out" | grep -q '^Linked:.*(changed)' && changed=1
# settings merge
m=$(python3 scripts/merge_settings.py --brain "$BRAIN") || exit 1
[ "$m" = "no changes" ] || note "$m"
[ "$changed" = 0 ] && echo "no changes"
exit 0
