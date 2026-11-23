#!/usr/bin/env python3
"""Phase 3 extractor. Standard library only.

Reads state/queue.jsonl, finds new human-authored user turns in each queued
transcript (past the offset in state/processed.json), pairs each with the
preceding assistant text, flags likely corrections, and writes
state/candidates/<run-id>.jsonl.

  extract.py                  extract new turns; offsets are NOT advanced
  extract.py --commit RUN_ID  advance offsets for that run (after a pass succeeded)
  extract.py --mark-dry RUN_ID   record a finished dry run (the first two passes must be dry)
  extract.py --brain DIR      brain dir (default: $CLAUDE_BRAIN_DIR or this file's repo)

Candidate files stay in gitignored state/ and hold truncated transcript text.
Never commit them; evidence written to the ledger must be a paraphrase.
"""
import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

REQUIRED_DRY_RUNS = 2  # first real run is allowed only after this many reviewed dry runs
ASSISTANT_CHARS = 400
USER_CHARS = 600

# Hint only, never a verdict. The LLM judges every turn.
CORRECTION_HINTS = [r"\bno\b", r"don'?t", r"\binstead\b", r"\bwrong\b",
                    r"\bI said\b", r"\brevert\b", r"\bundo\b", r"\bwhy did you\b",
                    r"\bstop\b"]
HINT_RE = re.compile("|".join(CORRECTION_HINTS), re.I)

# Text that starts a user record but was not typed by the human.
NON_HUMAN_PREFIXES = ("<command-name>", "<command-message>", "<command-args>",
                      "<local-command-", "<system-reminder>", "<task-notification>",
                      "<bash-input>", "<bash-stdout>", "<user-prompt-submit-hook>",
                      "Caveat:", "[Request interrupted")
PASTE_RE = re.compile(r"<pasted_content\b[^>]*>(.*?)</pasted_content[^>]*>", re.S)
REMINDER_RE = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc)


def blocks_text(content):
    """Text of a message.content that is a str or list of blocks (text blocks only)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content
                         if isinstance(b, dict) and b.get("type") == "text"
                         and isinstance(b.get("text"), str))
    return ""


def human_text(rec):
    """Return the human-typed text of a user record, or None if it is not one."""
    if rec.get("type") != "user" or rec.get("isMeta") or rec.get("isSidechain"):
        return None
    if rec.get("isCompactSummary") or rec.get("isVisibleInTranscriptOnly"):
        return None  # /compact summary injected as a user record
    if rec.get("toolUseResult") is not None:
        return None
    msg = rec.get("message")
    if not isinstance(msg, dict):
        return None
    content = msg.get("content")
    if isinstance(content, list) and any(
            isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
        return None
    text = blocks_text(content)
    text = REMINDER_RE.sub("", text).strip()
    if not text or text.startswith(NON_HUMAN_PREFIXES):
        return None
    # Pasted documents are not corrections; keep a marker instead of the body.
    text = PASTE_RE.sub(lambda m: f"[pasted {len(m.group(1))} chars]", text).strip()
    return text or None


def assistant_text(rec):
    if rec.get("type") != "assistant" or rec.get("isSidechain"):
        return ""
    msg = rec.get("message")
    return blocks_text(msg.get("content")) if isinstance(msg, dict) else ""


def read_turns(path, start):
    """Return (turns, total_lines). Scans the whole file for context but only
    emits human turns on lines >= start (0-based line index)."""
    turns, prev, total = [], "", 0
    with open(path, encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh):
            total = i + 1
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not isinstance(rec, dict):
                continue
            try:
                txt = human_text(rec)
                if txt is not None:
                    if i >= start:
                        turns.append({"line": i, "ts": rec.get("timestamp"),
                                      "user": txt[:USER_CHARS],
                                      "prev_assistant": prev[-ASSISTANT_CHARS:],
                                      "likely_correction": bool(HINT_RE.search(txt))})
                    prev = ""
                else:
                    a = assistant_text(rec)
                    if a:
                        prev = (prev + "\n" + a).strip()
            except Exception:
                continue  # skip anything we cannot interpret
    return turns, total


def load_json(p, default):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, ValueError):
        return default


def read_queue(path):
    """Group by session_id, keeping the most recent transcript_path/cwd."""
    sessions = {}
    if not path.exists():
        return sessions
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if not isinstance(e, dict) or not e.get("session_id") or not e.get("transcript_path"):
            continue
        sessions[e["session_id"]] = e  # later lines are more recent
    return sessions


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--commit", metavar="RUN_ID")
    ap.add_argument("--mark-dry", metavar="RUN_ID")
    ap.add_argument("--brain", default=os.environ.get("CLAUDE_BRAIN_DIR")
                    or str(Path(__file__).resolve().parent.parent))
    a = ap.parse_args()
    state = Path(a.brain) / "state"
    processed_p = state / "processed.json"
    cand_dir = state / "candidates"

    dry_log = state / "dryruns.jsonl"
    if a.mark_dry:
        if not (cand_dir / f"{a.mark_dry}.jsonl").exists():
            print(f"no candidate file for run {a.mark_dry}", file=sys.stderr)
            return 2
        with open(dry_log, "a") as fh:
            fh.write(json.dumps({"run": a.mark_dry, "ts": now_utc().isoformat(timespec="seconds")}) + "\n")
        print(f"recorded dry run {a.mark_dry}")
        return 0

    if a.commit:
        n_dry = len({json.loads(l).get("run") for l in dry_log.read_text().splitlines() if l.strip()}) \
            if dry_log.exists() else 0
        if n_dry < REQUIRED_DRY_RUNS:
            print(f"refusing to commit: only {n_dry} of {REQUIRED_DRY_RUNS} required dry runs "
                  f"recorded (use /reflect --dry-run, reviewed by the maintainer)", file=sys.stderr)
            return 3
        pend = cand_dir / f"{a.commit}.offsets.json"
        if not pend.exists() and (cand_dir / f"{a.commit}.offsets.done").exists():
            print(f"run {a.commit} already committed; nothing to do")
            return 0
        if not pend.exists():
            print(f"no pending offsets for run {a.commit}", file=sys.stderr)
            return 2
        processed = load_json(processed_p, {})
        for sid, n in load_json(pend, {}).items():
            processed[sid] = max(n, processed.get(sid, 0))
        tmp = processed_p.with_suffix(".tmp")
        tmp.write_text(json.dumps(processed, indent=1))
        tmp.replace(processed_p)
        pend.rename(pend.with_suffix(".done"))
        (cand_dir / f"{a.commit}.jsonl").unlink(missing_ok=True)  # scratch, not needed once committed
        print(f"committed offsets for {a.commit} ({len(processed)} sessions tracked)")
        return 0

    processed = load_json(processed_p, {})
    run_id = now_utc().strftime("%Y%m%dT%H%M%S%f")[:-3] + "Z"  # ms: unique per run
    cand_dir.mkdir(parents=True, exist_ok=True)
    offsets, out, n_sess, n_turns, n_flag, missing = {}, [], 0, 0, 0, []
    for sid, e in read_queue(state / "queue.jsonl").items():
        tp = Path(e["transcript_path"])
        if not tp.is_file():
            missing.append(sid)
            print(f"warn: transcript missing for session {sid}: {tp}", file=sys.stderr)
            continue
        start = processed.get(sid, 0)
        try:
            turns, total = read_turns(tp, start)
        except OSError as ex:
            print(f"warn: cannot read {tp}: {ex}", file=sys.stderr)
            continue
        if total < start:  # transcript shrank or was replaced: start over
            print(f"warn: {sid} shrank ({total} < {start}); rereading from 0", file=sys.stderr)
            turns, total = read_turns(tp, 0)
        offsets[sid] = total
        if not turns:
            continue
        n_sess += 1
        project = os.path.basename((e.get("cwd") or "").rstrip("/\\")) or None
        for t in turns:
            out.append({"run": run_id, "session_id": sid, "project": project, **t})
            n_turns += 1
            n_flag += t["likely_correction"]
    if not out:
        print(f"run {run_id}: no new human turns "
              f"({len(missing)} missing transcripts). Nothing to do.")
        return 0
    (cand_dir / f"{run_id}.jsonl").write_text(
        "\n".join(json.dumps(o, ensure_ascii=False) for o in out) + "\n")
    (cand_dir / f"{run_id}.offsets.json").write_text(json.dumps(offsets))
    print(f"run {run_id}: {n_sess} sessions, {n_turns} turns, {n_flag} flagged "
          f"({len(missing)} missing transcripts)")
    print(f"candidates: {cand_dir / (run_id + '.jsonl')}")
    print(f"after a successful pass: extract.py --commit {run_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
