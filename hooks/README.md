# Hooks

## capture.py (phase 2: capture only)
Queues every session transcript for the phase 3 `/reflect` batch pass. No scoring, no LLM, no network.

- **Events:** `SessionEnd` and `PreCompact` only. Never `Stop` (fires every turn, can loop).
- **Captures:** one JSON line per event in `state/queue.jsonl`: `ts`, `host`, `event`, `session_id`, `transcript_path`, `cwd`, `reason` (SessionEnd `reason` or PreCompact `trigger`). Paths only, not transcript content.
- **Where:** `state/` in the brain repo (gitignored). Also `state/capture.log` for hook errors (self-truncates at 256 KB).
- **Safety:** always exits 0, stdlib only, no-op on empty stdin, bad JSON (logged) or a missing brain dir.
- **Guard:** `BRAIN_REFLECT=1` makes the hook do nothing. Phase 3 sets it for headless `claude -p` runs so they don't queue themselves.
- **Brain path:** `$CLAUDE_BRAIN_DIR`, else the repo containing `capture.py`.

## Install
Merge `settings-snippet.json` into user-level `~/.claude/settings.json` (append to existing `SessionEnd`/`PreCompact` arrays). Per machine, set the interpreter (`python3`, `python` or `py -3`) and brain path. The SessionEnd default timeout is 1.5 s, so keep `timeout: 10`.

## Disable
Remove the `SessionEnd` and `PreCompact` entries that call `capture.py` from `~/.claude/settings.json`.

## Per-machine queue
`state/` is not synced. Each machine keeps its own `queue.jsonl`; phase 3 must run on each machine (or the queues be merged by hand).
