#!/usr/bin/env bash
# Usage: link-project.sh --user          (all projects, via ~/.claude)
#        link-project.sh <project-dir>   (one project)
set -e
BRAIN="${CLAUDE_BRAIN:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
line="@$BRAIN/CLAUDE.md"
if [ "$1" = "--user" ]; then
  md="$HOME/.claude/CLAUDE.md"; mkdir -p "$HOME/.claude/agents"
  ln -sfn "$BRAIN"/agents/*.md "$HOME/.claude/agents/"
else
  md="$1/CLAUDE.md"
fi
grep -qF "$line" "$md" 2>/dev/null || printf '\n# Shared brain\n%s\n' "$line" >> "$md"
echo "Linked: $md imports $line"
echo "Now merge templates/settings.json into ~/.claude/settings.json."
