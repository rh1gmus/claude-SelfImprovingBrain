# claude-SelfImprovingBrain

A shared, version-controlled instruction set for Claude Code that **improves itself under human control**, plus a working branch for making its setup **idempotent**.

> Status: work in progress. This is a sanitized fork of a personal "brain" repo. Paths, owner names and remotes are being made configurable (see [Roadmap](#roadmap)).

## Purpose
Claude Code loads `CLAUDE.md` files every session. This project keeps one shared `CLAUDE.md` that every project imports, and adds a loop so those instructions get better over time:

1. **Capture**: a SessionEnd/PreCompact hook queues each session transcript path (paths only, no content).
2. **Reflect**: a batch `/reflect` pass finds which rules applied, which were corrected by the user, and which patterns recur. It writes short, paraphrased evidence to a ledger.
3. **Propose**: patterns seen in 2+ sessions become proposals. Tunable guidance (`instructions/`, `agents/`) can be edited by Claude. Protected guidance (`rules/` and the machinery around it) changes only after explicit human approval.

## Layout
| Path | Role | Who may change it |
|---|---|---|
| `rules/` | governance and git rules | human approval only |
| `hooks/`, `scripts/`, `templates/`, `ledger/`, `reflect/`, `skills/`, `CLAUDE.md` | enforcement and tooling (treated as rules) | human approval only |
| `instructions/`, `agents/` | tunable guidance and tiered subagents | Claude, one commit per change |
| `state/` | local queue, offsets, scratch (gitignored) | machine-local |

## Confirmations (guardrails)
- **Approval gate**: protected paths need a proposal (file, diff, why, trigger) and an explicit "yes" before any edit. Claude Code `ask` permissions in `templates/settings.json` back this up.
- **`hooks/commit-msg`**: rejects commits that lack the `<area>: <what changed>` subject, `Why:` and `Trigger:` lines, or that touch protected paths without a `Rules-Approved-By:` trailer.
- **`scripts/bgit`**: runs git as the repo owner, refuses `--no-verify`, force pushes, `core.hooksPath` changes and pushes to `main`.
- **`scripts/brain-check.sh`** (SessionStart): confirms the repo, hooks path and remote; fast-forwards `main`; warns on dirty trees, local commits on `main`, files over 60 lines and invalid agent models.
- **Ledger**: every rule has a permanent ID. `ledger/ledger.py` only appends validated events and rejects empty or over-200-char evidence, IPs and emails.
- **Reflect dry runs**: `extract.py --commit` refuses until two reviewed dry runs are recorded.

## Tests
```bash
python3 ledger/lint.py                  # IDs in rules.csv match IDs inline; events.jsonl parses
python3 -m unittest reflect.test_reflect  # extractor, offsets, ledger validation (synthetic fixtures only)
bash -n scripts/*.sh                    # syntax check
```
Planned: `scripts/test_idempotent.sh`, which runs each setup step twice in a scratch `HOME` and diffs a snapshot of the file tree, git status, settings JSON and queue length. A passing test must also fail when a guard is deliberately removed.

## Idempotence goal
Any setup, check or hook step should end in the same state whether it runs once or many times. Audit findings and the plan:

| Gap | Status |
|---|---|
| `capture.py` defaulted to a non-existent `~/.claude_brain` | fixed: defaults to the repo containing the script |
| `brain-check.sh` hardcoded the brain path for `chown`/re-exec | fixed: derived from script location or `CLAUDE_BRAIN` |
| Settings merge is manual; no drift check | planned: `install.sh` plus a drift warning |
| Exec bits only set on first init | planned |
| Dangling agent symlinks never pruned | planned |
| Reflect `--commit` / ledger append not proven repeat-safe | planned: markers and event keys |

## Roadmap
- Add `scripts/install.sh` and `scripts/test_idempotent.sh`.

## Placeholders and environment
Files use these placeholders; replace them for your install:
- `<BRAIN_DIR>`: absolute path of your checkout (`templates/settings.json`, docs).
- `<OWNER>`: the non-root user that owns the repo (`rules/git.md`). Scripts read `BRAIN_OWNER`, default: owner of the brain dir.
- `<REMOTE_URL>`: your brain repo's `origin`. `brain-check.sh` reads `BRAIN_REMOTE`; if unset it only warns about a missing origin.
- `CLAUDE_BRAIN` / `CLAUDE_BRAIN_DIR`: override the brain path; default is the repo containing the script.

`ledger/events.jsonl` ships empty and `ledger/rules.csv` keeps the ID registry. This repo was published as a single commit with no history.

## Using it
Not yet turnkey. Point `CLAUDE_BRAIN` and `CLAUDE_BRAIN_DIR` at your checkout, import its `CLAUDE.md` from `~/.claude/CLAUDE.md`, and merge `templates/settings.json` into your Claude Code settings. Review everything under `rules/` first: it encodes one maintainer's preferences.
