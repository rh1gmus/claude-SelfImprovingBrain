#!/usr/bin/env python3
"""
.claude_brain capture hook (phase 2).

Wired to the Claude Code SessionEnd and PreCompact hooks. Reads the hook's JSON
payload on stdin and appends one line to <brain>/state/queue.jsonl so the
phase 3 /reflect pass can process the transcript later in a batch.

Guarantees:
  - always exits 0 and never blocks or fails the session
  - no network calls, no LLM calls, standard library only
  - does nothing when BRAIN_REFLECT=1 (keeps headless reflect runs from
    queuing themselves)

Brain location: $CLAUDE_BRAIN_DIR if set, otherwise the repo containing this file
"""
import datetime
import json
import os
import pathlib
import socket
import sys

BRAIN = pathlib.Path(
    os.environ.get("CLAUDE_BRAIN_DIR") or pathlib.Path(__file__).resolve().parents[1]
).expanduser()
STATE = BRAIN / "state"
QUEUE = STATE / "queue.jsonl"
LOG = STATE / "capture.log"
MAX_LOG_BYTES = 256 * 1024  # truncate the log once it passes this size


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def log(msg: str) -> None:
    """Best-effort diagnostics; never raises."""
    try:
        STATE.mkdir(parents=True, exist_ok=True)
        if LOG.exists() and LOG.stat().st_size > MAX_LOG_BYTES:
            LOG.write_text("", encoding="utf-8")
        with LOG.open("a", encoding="utf-8") as f:
            f.write(f"{_now()} {msg}\n")
    except Exception:
        pass


def main() -> None:
    if os.environ.get("BRAIN_REFLECT") == "1":
        return
    if not BRAIN.is_dir():
        return  # wrong/missing brain path: don't create a stray state/ dir

    raw = sys.stdin.read()
    if not raw.strip():
        return  # nothing to do

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        log(f"bad json on stdin: {e}")
        return
    if not isinstance(data, dict):
        log("stdin json was not an object")
        return

    session_id = data.get("session_id")
    transcript = data.get("transcript_path")
    if not session_id or not transcript:
        log(f"missing session_id/transcript_path (event={data.get('hook_event_name')})")
        return

    entry = {
        "ts": _now(),
        "host": socket.gethostname(),
        "event": data.get("hook_event_name"),
        "session_id": session_id,
        "transcript_path": transcript,
        "cwd": data.get("cwd"),
        # SessionEnd sends `reason` (exit, clear, logout...); PreCompact sends `trigger` (manual/auto)
        "reason": data.get("reason") or data.get("trigger"),
    }

    STATE.mkdir(parents=True, exist_ok=True)
    # Idempotence: a repeat of the same (session, event, transcript) as the last
    # queued line adds nothing (hook retries, double fires).
    try:
        last = QUEUE.read_text(encoding="utf-8").rstrip("\n").rsplit("\n", 1)[-1] if QUEUE.exists() else ""
        prev = json.loads(last) if last else {}
        if (prev.get("session_id"), prev.get("event"), prev.get("transcript_path")) == \
                (entry["session_id"], entry["event"], entry["transcript_path"]):
            return
    except (OSError, ValueError, AttributeError):
        pass
    # One short line per write; appends this small are effectively atomic,
    # so concurrent sessions won't interleave.
    with QUEUE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # never let the hook fail the session
        log(f"unhandled: {type(e).__name__}: {e}")
    sys.exit(0)