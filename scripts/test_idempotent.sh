#!/usr/bin/env bash
# Runs each setup/hook step twice in a scratch HOME and brain copy; the second run must change nothing.
# Never touches the real HOME or the brain it is run from. Usage: bash scripts/test_idempotent.sh
set -u
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export HOME="$T/home"; mkdir -p "$HOME"
B="$T/brain"; cp -a "$SRC" "$B"; rm -rf "$B/state"; mkdir "$B/state"
git init -q --bare "$T/origin.git"; (cd "$B" && git remote remove origin 2>/dev/null; git remote add origin "$T/origin.git"
  git branch -M main; git add -A; git -c user.name=t -c user.email=t@t commit -q -m "docs: scratch snapshot for idempotence test
Why: test fixture
Trigger: test_idempotent.sh" --no-verify; git push -q -u origin main)
export CLAUDE_BRAIN="$B" CLAUDE_BRAIN_DIR="$B" BRAIN_REMOTE="$T/origin.git"
fail=0
snap() { { (cd "$HOME" && find . -type f -o -type l | sort | xargs -r -d '\n' sh -c 'for f; do echo "$f $(readlink "$f" 2>/dev/null || sha1sum <"$f")"; done' _)
           (cd "$B" && git status --porcelain && git rev-parse HEAD && find state -type f | sort | xargs -r sha1sum); } | sha1sum; }
check() { # name, command...
  local n="$1"; shift
  "$@" >"$T/out1" 2>&1; local s1; s1=$(snap)
  "$@" >"$T/out2" 2>&1; local s2; s2=$(snap)
  if [ "$s1" = "$s2" ]; then echo "PASS $n"; else echo "FAIL $n: state changed on 2nd run"; diff "$T/out1" "$T/out2" | head -5; fail=1; fi
}
expect() { # name, grep pattern, file
  grep -q "$2" "$3" && echo "PASS $1" || { echo "FAIL $1: expected /$2/ in:"; head -5 "$3"; fail=1; }; }

check install bash "$B/scripts/install.sh"
expect "install 2nd run says no changes" '^no changes$' "$T/out2"
check link-user bash "$B/scripts/link-project.sh" --user
mkdir "$T/proj"; check link-project bash "$B/scripts/link-project.sh" "$T/proj"
[ "$(grep -c "@$B/CLAUDE.md" "$T/proj/CLAUDE.md")" = 1 ] && echo "PASS project import appears once" || { echo "FAIL import duplicated"; fail=1; }
ln -s "$B/agents/gone.md" "$HOME/.claude/agents/gone.md"; bash "$B/scripts/link-project.sh" --user >/dev/null
if [ -L "$HOME/.claude/agents/gone.md" ]; then echo "FAIL dangling link kept"; fail=1; else echo "PASS dangling link pruned"; fi
check brain-check bash "$B/scripts/brain-check.sh"
chmod -x "$B/hooks/capture.py"; bash "$B/scripts/brain-check.sh" 2>&1 | grep -q "capture.py not executable" && echo "PASS brain-check warns on exec bit" || { echo "FAIL no exec-bit warning"; fail=1; }
bash "$B/scripts/install.sh" >/dev/null; [ -x "$B/hooks/capture.py" ] && echo "PASS install restores exec bit" || { echo "FAIL exec bit"; fail=1; }
ev='{"session_id":"sess-1","transcript_path":"/x.jsonl","hook_event_name":"SessionEnd","reason":"exit"}'
cap() { echo "$ev" | python3 "$B/hooks/capture.py"; }
check capture cap
[ "$(wc -l <"$B/state/queue.jsonl")" = 1 ] && echo "PASS capture queues one line" || { echo "FAIL capture duplicated"; fail=1; }
check ledger-dup bash -c "cd '$B' && python3 ledger/ledger.py event --rule R-004 --kind recurrence --session sess-1 --evidence 'same evidence twice'"
grep -q "same evidence twice" "$B/ledger/events.jsonl" && [ "$(wc -l <"$B/ledger/events.jsonl")" = 1 ] && echo "PASS ledger keeps one event" || { echo "FAIL ledger duplicated"; fail=1; }
exit $fail
