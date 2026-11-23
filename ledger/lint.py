#!/usr/bin/env python3
"""Lint the rule ledger. Standard library only. Exit 1 if any check fails."""
import csv, json, re, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ID_RE = re.compile(r"^[RI]-\d{3}$")
INLINE_RE = re.compile(r"\[([RI]-\d{3})\]")
STATUSES = {"active", "probation", "retired"}
KINDS = {"applicable", "recurrence", "observation", "revised"}
errors = []


def fail(check, msg):
    errors.append(f"FAIL [{check}] {msg}")


# registry
rows = []
with open(ROOT / "ledger" / "rules.csv", newline="") as fh:
    rows = list(csv.DictReader(fh))
ids = [r["id"] for r in rows]
for i, n in Counter(ids).items():
    if n > 1:
        fail("duplicate-id", f"{i} appears {n} times in rules.csv")
for r in rows:
    if not ID_RE.match(r["id"]):
        fail("id-format", f"malformed id {r['id']!r}")
    elif (r["id"][0] == "R") != r["file"].startswith("rules/"):
        fail("id-prefix", f"{r['id']} prefix does not match file {r['file']}")
    if r["status"] not in STATUSES:
        fail("status", f"{r['id']} has invalid status {r['status']!r}")
known = set(ids)
status = {r["id"]: r["status"] for r in rows}

# inline IDs in rules/ and instructions/ (observations.local.md excluded)
inline = Counter()
for d in ("rules", "instructions"):
    for p in sorted((ROOT / d).glob("*.md")):
        if p.name.endswith(".local.md"):
            continue
        for n, line in enumerate(p.read_text().splitlines(), 1):
            for m in INLINE_RE.findall(line):
                inline[m] += 1
                if m not in known:
                    fail("unregistered", f"{p.relative_to(ROOT)}:{n} {m} has no row in rules.csv")
for i, n in inline.items():
    if n > 1:
        fail("inline-duplicate", f"{i} appears inline {n} times")
for i in ids:
    if status[i] != "retired" and inline[i] != 1:
        fail("missing-inline", f"{i} is {status[i]} but appears inline {inline[i]} times (want 1)")
    if status[i] == "retired" and inline[i]:
        fail("retired-inline", f"{i} is retired but still appears inline")

# events
ev = ROOT / "ledger" / "events.jsonl"
for n, line in enumerate(ev.read_text().splitlines(), 1):
    if not line.strip():
        continue
    try:
        obj = json.loads(line)
    except ValueError as e:
        fail("events-parse", f"events.jsonl:{n} {e}")
        continue
    if not isinstance(obj, dict):
        fail("events-parse", f"events.jsonl:{n} not an object")
        continue
    rid = obj.get("rule_id")
    if rid is not None and rid not in known:
        fail("events-ref", f"events.jsonl:{n} unknown rule_id {rid!r}")
    if obj.get("kind") not in KINDS:
        fail("events-kind", f"events.jsonl:{n} invalid kind {obj.get('kind')!r}")

for e in errors:
    print(e)
if errors:
    sys.exit(1)
print(f"ok: {len(rows)} ids, {sum(inline.values())} inline, events parse")
