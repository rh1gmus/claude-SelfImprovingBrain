#!/usr/bin/env bash
# SessionStart check for claude_brain. Output is shown to Claude as context.
# Config (env): CLAUDE_BRAIN (default: repo containing this script), BRAIN_OWNER (default: owner of BRAIN dir),
# BRAIN_REMOTE (origin URL to add if origin is missing; if unset, a missing origin is only warned about).
BRAIN="${CLAUDE_BRAIN:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
OWNER="${BRAIN_OWNER:-$(stat -c %U "$BRAIN" 2>/dev/null)}"
if [ "$(id -u)" = 0 ] && [ -n "$OWNER" ] && [ "$OWNER" != root ]; then
  chown -R "$OWNER": "$BRAIN"; exec sudo -u "$OWNER" -H env CLAUDE_BRAIN="$BRAIN" BRAIN_REMOTE="$BRAIN_REMOTE" bash "$0" "$@"; fi
REMOTE="${BRAIN_REMOTE:-}"
[ -d "$BRAIN" ] || { echo "brain-check: claude_brain not found at $BRAIN (set CLAUDE_BRAIN)"; exit 0; }
cd "$BRAIN" || exit 0
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git init -q -b main && git config core.hooksPath hooks && chmod +x hooks/* scripts/*.sh 2>/dev/null
  git add -A && git commit -q -m "docs: initial commit of claude_brain skeleton

Why: claude_brain must always be under version control
Trigger: brain-check found no git repo at session start" && echo "brain-check: initialized git repo and made initial commit"
fi
[ "$(git config core.hooksPath)" = "hooks" ] || { git config core.hooksPath hooks; echo "brain-check: set core.hooksPath=hooks"; }
git remote get-url origin >/dev/null 2>&1 || { [ -n "$REMOTE" ] && git remote add origin "$REMOTE" && echo "brain-check: added origin $REMOTE" || echo "brain-check: WARN no origin and BRAIN_REMOTE unset"; }
dirty=$(git status --porcelain)
if timeout 20 git fetch -q origin 2>/dev/null; then
  if git rev-parse -q --verify origin/main >/dev/null; then
    cur=$(git symbolic-ref --short -q HEAD)
    if [ "$cur" != main ]; then
      if [ -z "$dirty" ] && git merge-base --is-ancestor HEAD origin/main; then
        git switch -q main && git branch -q -d "$cur" && echo "brain-check: $cur was merged; back on main"
      else echo "brain-check: on $cur, awaiting maintainer merge"; fi
    fi
    if [ "$(git symbolic-ref --short -q HEAD)" = main ]; then
      behind=$(git rev-list --count main..origin/main)
      [ "$behind" -gt 0 ] && { [ -z "$dirty" ] && git merge -q --ff-only origin/main && echo "brain-check: pulled $behind commit(s)" || echo "brain-check: $behind remote commit(s) not merged (dirty tree or diverged); resolve manually"; }
      [ "$(git rev-list --count origin/main..main)" -gt 0 ] && echo "brain-check: WARN local commits on main; move them to a brain/<slug> branch and push that"
    fi
  else
    timeout 30 git push -q -u origin main && echo "brain-check: pushed initial commit" || echo "brain-check: PUSH FAILED; check SSH key/remote"
  fi
else
  echo "brain-check: fetch failed (offline or SSH issue); remote sync skipped"
fi
[ -n "$dirty" ] && echo "brain-check: UNCOMMITTED changes in claude_brain; review and commit per rules/git.md:" && echo "$dirty"
for f in CLAUDE.md rules/*.md instructions/*.md agents/*.md; do
  [ "$(wc -l <"$f")" -gt 60 ] && echo "brain-check: WARN $f is over 60 lines"; done
for f in agents/*.md; do
  m=$(sed -n 's/^model: *//p' "$f" | head -1)
  case "$m" in haiku|sonnet|opus) ;; *) echo "brain-check: WARN $f has invalid model '$m'";; esac; done
[ -x hooks/commit-msg ] || echo "brain-check: WARN hooks/commit-msg missing or not executable"
echo "brain-check: ok ($BRAIN @ $(git rev-parse --short HEAD))"
