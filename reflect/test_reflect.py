#!/usr/bin/env python3
"""Tests for extract.py and ledger.py. Run: python3 reflect/test_reflect.py
All fixtures are synthetic and live in a temp dir; the real ledger/state are untouched."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PY = sys.executable


def run(args, **kw):
    return subprocess.run([PY, *map(str, args)], capture_output=True, text=True, **kw)


def user(text, **extra):
    return {"type": "user", "timestamp": "2026-01-01T00:00:00Z", "message": {"role": "user", "content": text}, **extra}


def asst(text):
    return {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


def write_lines(p, recs):
    with open(p, "a") as fh:
        for r in recs:
            fh.write((r if isinstance(r, str) else json.dumps(r)) + "\n")


class ExtractTests(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        (self.d / "state").mkdir()
        self.t = self.d / "t.jsonl"
        write_lines(self.t, [
            "not json at all",
            {"type": "mode"},
            user("add a login page"),
            asst("I added the login page using sessions."),
            {"type": "user", "toolUseResult": {"x": 1}, "message": {"content": [{"type": "tool_result", "content": "no no no"}]}},
            user("<system-reminder>no hooks</system-reminder>"),
            user("<command-name>/compact</command-name>"),
            user("injected meta, no", isMeta=True),
            user("This session is being continued, no", isCompactSummary=True, isVisibleInTranscriptOnly=True),
            user("sidechain no", isSidechain=True),
            asst("Done. I used a cookie."),
            user("no, don't use a cookie, use a token instead"),
            user("looks good thanks"),
            user("see this:\n<pasted_content id=\"ab\">" + "x" * 5000 + "</pasted_content id=\"ab\">"),
        ])
        self.sid = "sess-aaaa"
        self.queue(self.sid, "PreCompact")

    def tearDown(self):
        shutil.rmtree(self.d)

    def queue(self, sid, event):
        write_lines(self.d / "state" / "queue.jsonl", [{
            "ts": "t", "event": event, "session_id": sid,
            "transcript_path": str(self.t), "cwd": "/x/proj", "reason": "x"}])

    def extract(self, *a):
        return run([HERE / "extract.py", "--brain", self.d, *a])

    def cands(self):
        out = []
        for f in sorted((self.d / "state" / "candidates").glob("*.jsonl")):
            out += [json.loads(l) for l in f.read_text().splitlines()]
        return out

    def run_id(self, r):
        return r.stdout.split("run ")[1].split(":")[0]

    def test_filters_and_pairing(self):
        r = self.extract()
        self.assertEqual(r.returncode, 0, r.stderr)
        turns = self.cands()
        texts = [t["user"] for t in turns]
        self.assertEqual(texts[0], "add a login page")
        self.assertEqual(len(turns), 4, texts)  # no tool_result/meta/command/reminder/sidechain
        corr = turns[1]
        self.assertTrue(corr["likely_correction"])
        self.assertIn("cookie", corr["prev_assistant"])
        self.assertFalse(turns[2]["likely_correction"])
        self.assertLess(len(turns[3]["user"]), 100)  # paste collapsed
        self.assertIn("pasted 5000 chars", turns[3]["user"])

    def test_offsets_not_advanced_until_commit(self):
        r = self.extract()
        self.extract()  # second run before commit sees the same turns again
        self.assertFalse((self.d / "state" / "processed.json").exists())
        self.assertEqual(len(self.cands()), 8)
        self.mark_two_dry()
        self.extract("--commit", self.run_id(r))
        self.assertTrue((self.d / "state" / "processed.json").exists())

    def test_double_capture_and_resume_reads_no_line_twice(self):
        self.queue(self.sid, "SessionEnd")  # same session captured twice
        r = self.extract()
        self.assertIn("1 sessions, 4 turns", r.stdout)
        self.mark_two_dry()
        self.extract("--commit", self.run_id(r))
        r2 = self.extract()
        self.assertIn("no new human turns", r2.stdout)
        write_lines(self.t, [asst("ok"), user("one more thing, revert that")])  # session kept going
        r3 = self.extract()
        self.assertIn("1 turns", r3.stdout)
        last = [json.loads(l) for l in (self.d / "state" / "candidates" / (self.run_id(r3) + ".jsonl")).read_text().splitlines()]
        self.assertEqual([t["user"] for t in last], ["one more thing, revert that"])
        self.assertEqual(last[0]["prev_assistant"], "ok")

    def test_missing_transcript_logged_and_skipped(self):
        write_lines(self.d / "state" / "queue.jsonl", [{
            "session_id": "gone-1", "transcript_path": "/nonexistent/x.jsonl", "event": "SessionEnd"}])
        r = self.extract()
        self.assertEqual(r.returncode, 0)
        self.assertIn("missing", r.stderr)
        self.assertIn("1 sessions", r.stdout)

    def mark_two_dry(self):
        for _ in range(2):
            r = self.extract()
            self.assertEqual(self.extract("--mark-dry", self.run_id(r)).returncode, 0)

    def test_commit_unknown_run_fails(self):
        self.mark_two_dry()
        self.assertEqual(self.extract("--commit", "nope").returncode, 2)

    def test_commit_refused_before_two_dry_runs(self):
        r = self.extract()
        self.assertEqual(self.extract("--commit", self.run_id(r)).returncode, 3)
        self.extract("--mark-dry", self.run_id(r))
        self.assertEqual(self.extract("--commit", self.run_id(r)).returncode, 3)  # one is not two
        self.assertFalse((self.d / "state" / "processed.json").exists())


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        (self.d / "ledger").mkdir()
        (self.d / "instructions").mkdir()
        shutil.copy(ROOT / "ledger" / "ledger.py", self.d / "ledger")
        (self.d / "ledger" / "rules.csv").write_text(
            "id,file,summary,added,source,status,status_changed,notes\n"
            "R-001,rules/a.md,x,2026-01-01,pre-ledger,active,2026-01-01,\n"
            "R-002,rules/a.md,y,2026-01-01,pre-ledger,retired,2026-01-01,\n")
        (self.d / "ledger" / "events.jsonl").write_text("")

    def tearDown(self):
        shutil.rmtree(self.d)

    def led(self, *a):
        return run([self.d / "ledger" / "ledger.py", *a])

    def events(self):
        return (self.d / "ledger" / "events.jsonl").read_text().splitlines()

    def ev(self, **kw):
        base = dict(rule="R-001", kind="recurrence", session="sess-aaaa", evidence="agent skipped the check again")
        base.update(kw)
        return self.led("event", *[x for k, v in base.items() for x in (f"--{k}", v)])

    def test_accepts_and_appends(self):
        self.assertEqual(self.ev().returncode, 0)
        e = json.loads(self.events()[0])
        self.assertEqual((e["rule_id"], e["kind"], e["session_id"]), ("R-001", "recurrence", "sess-aaaa"))
        self.assertEqual(self.led("observe", "--session", "sess-aaaa", "--evidence", "new pattern").returncode, 0)
        self.assertIsNone(json.loads(self.events()[1])["rule_id"])

    def test_rejects(self):
        bad = [dict(rule="R-999"), dict(rule="R-002"), dict(rule="nope"), dict(evidence=""), dict(evidence="  "),
               dict(evidence="x" * 201), dict(evidence="host at 10.1.2.3 failed"),
               dict(evidence="mail bob@example.com"), dict(evidence="ipv6 fe80::1ff:fe23:4567:890a"),
               dict(kind="observation"), dict(kind="bogus"), dict(session="bad id!"), dict(evidence="a\nb")]
        for kw in bad:
            r = self.ev(**kw)
            self.assertNotEqual(r.returncode, 0, kw)
        self.assertEqual(self.events(), [])  # nothing written
        self.assertNotEqual(self.led("observe", "--session", "s-123", "--evidence", "ip 192.168.0.1").returncode, 0)

    def test_evidence_boundary_and_dry_run(self):
        self.assertEqual(self.ev(evidence="x" * 200).returncode, 0)
        r = self.led("event", "--rule", "R-001", "--kind", "revised", "--session", "sess-aaaa", "--evidence", "ok", "--dry-run")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(len(self.events()), 1)

    def test_one_applicable_per_rule_per_session(self):
        self.assertEqual(self.ev(kind="applicable").returncode, 0)
        self.assertEqual(self.ev(kind="applicable").returncode, 3)
        self.assertEqual(self.ev(kind="applicable", session="sess-bbbb").returncode, 0)
        self.assertEqual(len(self.events()), 2)

    def test_note_counts_distinct_sessions(self):
        n = lambda s, t="repeat the same fix": self.led("note", "--session", s, "--key", "same-fix", "--text", t)
        self.assertIn("count=1 distinct_sessions=1 -> keep", n("sess-aaaa").stdout)
        self.assertIn("count=2 distinct_sessions=1 -> keep", n("sess-aaaa").stdout)  # same session: no promotion
        self.assertIn("count=3 distinct_sessions=2 -> PROMOTE", n("sess-bbbb").stdout)
        self.assertEqual(len((self.d / "instructions" / "observations.local.md").read_text().splitlines()), 1)
        self.assertNotEqual(self.led("note", "--session", "s-123", "--key", "Bad Key", "--text", "x").returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
