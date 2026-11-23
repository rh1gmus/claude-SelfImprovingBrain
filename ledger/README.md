# Ledger

Registry and evidence log for every rule and instruction in the brain.

## Files
- `rules.csv`: one row per ID. Columns: `id,file,summary,added,source,status,status_changed,notes`.
- `events.jsonl`: append-only evidence, one JSON object per line (written by the phase 3 reflect pass):
  `{"ts": "ISO-8601 UTC", "session_id": "...", "rule_id": "R-014 or null", "kind": "...", "evidence": "short paraphrase"}`
- `lint.py`: standard-library check. Run `python3 ledger/lint.py`; exits nonzero and names the failed check.

## IDs
- `R-###` for lines in `rules/`, `I-###` for lines in `instructions/`. Zero-padded, sequential.
- The ID is appended to the directive's line as ` [R-014]` (inside the last cell for table rows).
- IDs are permanent: never renumber, never reuse a retired ID.
- `observations.local.md` entries get no IDs; they are not rules yet.
- A new rule gets the next free ID and a `rules.csv` row in the same commit.

## Status lifecycle
`active` -> `probation` -> `retired`.
Retiring a rule sets `status=retired` and removes its line from its file. The row is kept forever.
`source` is `pre-ledger` for rules that existed before the ledger; later it points to the observation or proposal that created the rule.

## Event kinds
- `applicable`: the rule applied in a session (with how it went).
- `recurrence`: the problem the rule targets happened again.
- `observation`: a note about a rule or gap that is not yet a change (`rule_id` may be null).
- `revised`: the rule's wording changed.

## Privacy rule
Evidence is always a short paraphrase. Never paste verbatim transcript text, and never include customer or tenant names, hostnames, IPs, usernames, emails or secrets. This repo is committed and the transcripts it summarizes come from customer work.
