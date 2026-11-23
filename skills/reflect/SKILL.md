---
name: reflect
description: Batch pass over queued session transcripts that records which brain rules applied, which failed (user corrections) and which new patterns recur. Writes ledger events and proposal drafts, never rules. Use when asked to run /reflect, optionally with --dry-run.
---

# /reflect [--dry-run]

Brain dir: `$CLAUDE_BRAIN_DIR` (default: the brain checkout, `<BRAIN_DIR>`). Run everything from there. Evidence comes from the user's corrections, not your own self-assessment.

**Never edit `rules/` or `instructions/`. Never copy transcript text into any committed file.**

## Privacy (applies to every string you write)
Evidence is a paraphrase of at most 200 characters. No customer or tenant names, hostnames, IPs, usernames, emails or secrets. `ledger.py` rejects IPs and emails, but names and hostnames are on you.

## What counts as a correction
The user pushes back on something *you did* that would plausibly happen again: "no, don't X", "I told you to Y", undoing your change, re-asking because you ignored a constraint. A one-off task instruction ("make it blue", "use the other tenant") is NOT a correction. The `likely_correction` flag is a regex hint only: judge every turn.

## Procedure
1. `python3 reflect/extract.py`. If it prints "no new human turns", report that and stop. Note the run id. Candidates are in `state/candidates/<run-id>.jsonl` (gitignored; truncated turn text plus the preceding assistant text).
2. `python3 ledger/ledger.py rules` lists every non-retired rule with its ID and text.
3. For each session in the candidates (read the file; do not guess):
   - **Applicable.** For each rule whose situation came up, whether or not it was followed, write ONE event:
     `python3 ledger/ledger.py event --rule R-014 --kind applicable --session <sid> --evidence "<paraphrase>"`
     (exit 3 = already recorded for that session: fine, skip).
   - **Corrections.** For each real correction:
     - matches an existing rule: that rule failed. Write `--kind recurrence` (same command).
     - matches no rule: `ledger.py observe --session <sid> --evidence "<paraphrase>"`, then
       `ledger.py note --session <sid> --key <short-slug> --text "<paraphrase>"`. Reuse the key of a similar existing `CORR |` line in `instructions/observations.local.md` so its count increments.
   - A rejected command (exit 2) means fix the input; never work around the check.
4. **Promotion.** `note` prints `PROMOTE` when a key has 2+ distinct sessions. For each, draft `proposals/YYYY-MM-DD-<slug>.md` with: proposed directive text, target file, next free ID (max in `ledger/rules.csv` + 1), a paraphrased evidence summary, whether it fits best as a rule, skill or hook, and the unified diff (format per `rules/governance.md` R-005). Do not apply it.
5. `python3 ledger/lint.py` must pass. Then commit `ledger/events.jsonl` and any `proposals/` per `rules/git.md` (branch `brain/reflect-<date>` via `scripts/bgit`; area `scripts`; Why/Trigger lines; push; tell the maintainer it awaits merge).
6. `python3 reflect/extract.py --commit <run-id>` (only after steps 3 to 5 succeeded).
7. Report: sessions processed, corrections found, recurrences by rule ID, new and incremented observations, proposals drafted.

## --dry-run
Do steps 1 to 4 but add `--dry-run` to every `ledger.py` call (it prints and writes nothing) and print proposals instead of writing them. No lint, no commit, no `--commit`. Print a table: session, turn line, your verdict (correction / not), matched rule or new pattern, reasoning in one line. Finish with `python3 reflect/extract.py --mark-dry <run-id>` so the dry run is counted. `--commit` refuses until two dry runs are recorded, and the maintainer reviews each dry run's judgments before the next step.
