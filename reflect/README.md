# reflect (phase 3)

Turns queued transcripts (`state/queue.jsonl`, written by `hooks/capture.py`) into ledger evidence: which rules applied, which failed, which new patterns recur. Scoring and pruning are phase 4.

## Pieces
- `extract.py`: deterministic. Reads new human turns past `state/processed.json` offsets, pairs each with the preceding assistant text (400 chars), adds a regex `likely_correction` hint, writes `state/candidates/<run-id>.jsonl`. Offsets advance only via `--commit <run-id>`, so a failed pass is reprocessed. A session captured by both PreCompact and SessionEnd is one entry; resumed sessions read only new lines.
- `../ledger/ledger.py`: validated append-only writes (`event`, `observe`, `note`, `rules`, all with `--dry-run`). Rejects unknown or retired IDs, empty or over-200-char evidence, IPs, emails.
- `../skills/reflect/SKILL.md`: the LLM judgment step (applicability, corrections, promotion).
- `test_reflect.py`: `python3 reflect/test_reflect.py` (synthetic fixtures only).

## Procedure
`/reflect` runs extract, judges each session, writes events, drafts `proposals/*.md` when a pattern reaches 2+ distinct sessions, lints, commits `ledger/events.jsonl` and proposals, then commits offsets. Proposals are reviewed under `rules/governance.md`; reflect never edits `rules/` or `instructions/`.

## Dry run
`/reflect --dry-run` prints every event, observation and proposal it would write and changes nothing in the ledger (candidate files in gitignored `state/` are scratch). It ends with `extract.py --mark-dry <run-id>`. **The first two runs must be dry runs**: `extract.py --commit` refuses (exit 3) until two are recorded in `state/dryruns.jsonl`. Review the judgments after each.

## Install the skill
Source lives in the brain, like `agents/`. Link it per machine: `ln -s <BRAIN_DIR>/skills/reflect ~/.claude/skills/reflect`.

## Headless (documented, not scheduled)
Flags checked against `claude --help` (v2.1.330). Example for cron on a compute node:

```bash
cd <BRAIN_DIR> && BRAIN_REFLECT=1 claude -p "/reflect" \
  --model sonnet --permission-mode acceptEdits --no-session-persistence \
  --max-budget-usd 2 \
  --allowedTools "Read" "Edit(instructions/observations.local.md)" \
    "Write(proposals/*)" "Bash(python3 reflect/extract.py:*)" \
    "Bash(python3 ledger/ledger.py:*)" "Bash(python3 ledger/lint.py)" \
    "Bash(scripts/bgit:*)"
```
- `BRAIN_REFLECT=1` stops the hooks queueing the reflect run itself; `--no-session-persistence` also keeps it out of future transcripts.
- Do not use `--dangerously-skip-permissions`. Only the tools listed run; anything else is denied when no one can approve it.
- Your `~/.claude/settings.json` `ask`/`deny` rules still apply: expect `Write(proposals/*)` to be fine but `hooks/`, `rules/`, `scripts/` stay blocked.
- Run only after the two dry runs and one reviewed real run. Not tested unattended yet; try it by hand first. Each machine has its own `state/`, so run it per machine.
