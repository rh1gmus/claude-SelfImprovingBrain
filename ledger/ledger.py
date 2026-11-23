#!/usr/bin/env python3
"""Validated, append-only writes to ledger/events.jsonl. Standard library only.

  ledger.py event   --rule R-014 --kind applicable|recurrence|revised --session ID --evidence "..."
  ledger.py observe --session ID --evidence "..."      (rule_id null, kind observation)
  ledger.py rules   (list non-retired rules: ID, status, directive text)
  ledger.py note    --session ID --key slug --text "..." (bump a pattern count in
                    instructions/observations.local.md; prints count and distinct sessions)

Add --dry-run to any subcommand to print what would be written and write nothing.
Exit codes: 0 ok, 2 rejected input, 3 duplicate applicable (rule+session), 1 other error.
Existing lines are never rewritten.
"""
import argparse
import csv
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVENTS = ROOT / "ledger" / "events.jsonl"
RULES = ROOT / "ledger" / "rules.csv"
OBS = ROOT / "instructions" / "observations.local.md"
MAX_EVIDENCE = 200
RULE_KINDS = {"applicable", "recurrence", "revised"}
IP_RE = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b|(?<![0-9a-f])(?:[0-9a-f]{0,4}:){2,7}[0-9a-f]{0,4}(?![0-9a-f])", re.I)
EMAIL_RE = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{4,64}$")
KEY_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,60}$")


class Reject(Exception):
    def __init__(self, msg, code=2):
        super().__init__(msg)
        self.code = code


def rules():
    with open(RULES, newline="") as fh:
        return {r["id"]: r["status"] for r in csv.DictReader(fh)}


def check_evidence(ev):
    ev = (ev or "").strip()
    if not ev:
        raise Reject("evidence is empty")
    if len(ev) > MAX_EVIDENCE:
        raise Reject(f"evidence is {len(ev)} chars (max {MAX_EVIDENCE})")
    if "\n" in ev:
        raise Reject("evidence must be a single line")
    if IP_RE.search(ev):
        raise Reject("evidence looks like it contains an IP address")
    if EMAIL_RE.search(ev):
        raise Reject("evidence looks like it contains an email address")
    return ev


def check_session(s):
    if not SESSION_RE.match(s or ""):
        raise Reject(f"bad session id {s!r}")
    return s


def existing_events():
    if not EVENTS.exists():
        return []
    out = []
    for line in EVENTS.read_text().splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out


def append(obj, dry):
    line = json.dumps(obj, ensure_ascii=False, sort_keys=False)
    if dry:
        print(f"DRY-RUN would append to events.jsonl: {line}")
        return
    with open(EVENTS, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    print(f"appended: {line}")


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def cmd_event(a):
    known = rules()
    if a.rule not in known:
        raise Reject(f"unknown rule id {a.rule!r}")
    if known[a.rule] == "retired" and a.kind != "revised":
        raise Reject(f"{a.rule} is retired")
    ev, sid = check_evidence(a.evidence), check_session(a.session)
    if a.kind == "applicable" and any(
            e.get("rule_id") == a.rule and e.get("kind") == "applicable"
            and e.get("session_id") == sid for e in existing_events()):
        raise Reject(f"applicable already recorded for {a.rule} in session {sid}", 3)
    append({"ts": stamp(), "session_id": sid, "rule_id": a.rule,
            "kind": a.kind, "evidence": ev}, a.dry_run)


def cmd_observe(a):
    append({"ts": stamp(), "session_id": check_session(a.session), "rule_id": None,
            "kind": "observation", "evidence": check_evidence(a.evidence)}, a.dry_run)


def cmd_note(a):
    """Track a candidate pattern: line `CORR | key | count=N | sessions=a,b | text`."""
    sid, text = check_session(a.session), check_evidence(a.text)
    if not KEY_RE.match(a.key or ""):
        raise Reject(f"bad key {a.key!r} (lowercase slug, 3-61 chars)")
    lines = OBS.read_text().splitlines() if OBS.exists() else []
    pat = re.compile(r"^CORR \| " + re.escape(a.key) + r" \| count=(\d+) \| sessions=([^|]*) \| ")
    for i, ln in enumerate(lines):
        m = pat.match(ln)
        if m:
            sessions = [s for s in m.group(2).split(",") if s]
            if sid not in sessions:
                sessions.append(sid)
            count = int(m.group(1)) + 1
            lines[i] = (f"CORR | {a.key} | count={count} | sessions={','.join(sessions)}"
                        f" | {ln.split(' | ', 4)[4]}")
            break
    else:
        sessions, count = [sid], 1
        lines.append(f"CORR | {a.key} | count=1 | sessions={sid} | {text}")
    distinct = len(sessions)
    verdict = "PROMOTE" if distinct >= 2 else "keep"
    print(f"{'DRY-RUN ' if a.dry_run else ''}note {a.key}: count={count} "
          f"distinct_sessions={distinct} -> {verdict}")
    if not a.dry_run:
        OBS.write_text("\n".join(lines) + "\n")


def cmd_rules(a):
    inline = re.compile(r"\[([RI]-\d{3})\]")
    status, text = rules(), {}
    for d in ("rules", "instructions"):
        for p in sorted((ROOT / d).glob("*.md")):
            if p.name.endswith(".local.md"):
                continue
            for ln in p.read_text().splitlines():
                for rid in inline.findall(ln):
                    text[rid] = inline.sub("", ln).strip(" -*|`")
    for rid, st in status.items():
        if st != "retired":
            print(f"{rid} [{st}] {text.get(rid, '(text not found)')}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("event")
    e.add_argument("--rule", required=True)
    e.add_argument("--kind", required=True, choices=sorted(RULE_KINDS))
    e.add_argument("--session", required=True)
    e.add_argument("--evidence", required=True)
    e.set_defaults(fn=cmd_event)
    o = sub.add_parser("observe")
    o.add_argument("--session", required=True)
    o.add_argument("--evidence", required=True)
    o.set_defaults(fn=cmd_observe)
    n = sub.add_parser("note")
    n.add_argument("--session", required=True)
    n.add_argument("--key", required=True)
    n.add_argument("--text", required=True)
    n.set_defaults(fn=cmd_note)
    r = sub.add_parser("rules")
    r.set_defaults(fn=cmd_rules, dry_run=False)
    for p in (e, o, n):
        p.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    try:
        a.fn(a)
    except Reject as ex:
        print(f"rejected: {ex}", file=sys.stderr)
        return ex.code
    return 0


if __name__ == "__main__":
    sys.exit(main())
