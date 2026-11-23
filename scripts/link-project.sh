#!/usr/bin/env bash
# Usage: link-project.sh --user          (all projects, via ~/.claude)
#        link-project.sh <project-dir>   (one project)
# Idempotent: prints "Linked: ... (changed)" only when it altered something.
set -e
BRAIN="${CLAUDE_BRAIN:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
line="@$BRAIN/CLAUDE.md"
changed=""
if [ "$1" = "--user" ]; then
  md="$HOME/.claude/CLAUDE.md"; mkdir -p "$HOME/.claude/agents"
  for f in "$BRAIN"/agents/*.md; do
    d="$HOME/.claude/agents/$(basename "$f")"
    [ "$(readlink "$d" 2>/dev/null)" = "$f" ] || { ln -sfn "$f" "$d"; changed=" (changed)"; }
  done
  # prune dangling links that pointed into this brain's agents/
  for d in "$HOME"/.claude/agents/*.md; do
    [ -L "$d" ] && [ ! -e "$d" ] && case "$(readlink "$d")" in "$BRAIN"/agents/*) rm -f "$d"; changed=" (changed)";; esac
  done
else
  md="$1/CLAUDE.md"
fi
grep -qF "$line" "$md" 2>/dev/null || { printf '\n# Shared brain\n%s\n' "$line" >> "$md"; changed=" (changed)"; }
echo "Linked: $md imports $line$changed"
