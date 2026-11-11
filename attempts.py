"""Collecting real answer attempts for the future ML model (no Streamlit code).

Every time a REAL player answers a question, one JSON line is appended to
data/attempts.jsonl. Nothing else is written there: no simulated opponents and
no synthetic data. No personal information is stored: player_id and session_id
are random ids that cannot be traced back to a person.

Record fields (schema_version 1):
    attempt_id       unique id of this attempt (also used to prevent duplicates)
    player_id        random anonymous id, one per browser session
    session_id       random anonymous id, one per game (a new one on "play again")
    timestamp        UTC time of the answer, ISO 8601
    question_id      id of the question (see question_bank.py)
    topic            topic of the question
    difficulty       easy | medium | hard
    chosen_option    the text of the option the player chose
    is_correct       true / false
    response_time_ms milliseconds from showing the question to the answer,
                     or null when it could not be measured reliably

The file path can be overridden with the CONQUEST_ATTEMPTS_PATH environment
variable (used by tests so they never write into the real data file).
"""

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
DEFAULT_PATH = Path(__file__).parent / "data" / "attempts.jsonl"
PATH_ENV_VAR = "CONQUEST_ATTEMPTS_PATH"

# Fixed namespace: the same (session, attempt number) always gives the same id,
# so saving the same attempt twice is detected as a duplicate.
_ID_NAMESPACE = uuid.UUID("6f1c2a52-8d3e-4c55-9a47-0c0f6d3b5e11")
_lock = threading.Lock()
_saved = set()                   # (path, attempt_id) of attempts saved by this process
log = logging.getLogger("conquest.attempts")


def attempts_path():
    return Path(os.environ.get(PATH_ENV_VAR) or DEFAULT_PATH)


def new_anonymous_id():
    """A random id with no relation to the person (not derived from anything)."""
    return uuid.uuid4().hex


def make_attempt_id(session_id, attempt_number):
    return str(uuid.uuid5(_ID_NAMESPACE, f"{session_id}:{attempt_number}"))


def build_record(session_id, player_id, attempt_number, question, chosen_option,
                 is_correct, response_time_ms=None):
    """Create the dictionary that is written to the file."""
    if response_time_ms is not None:
        response_time_ms = int(response_time_ms)
        if response_time_ms < 0:                 # a clock problem: do not store a wrong value
            response_time_ms = None
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    return {
        "schema_version": SCHEMA_VERSION,
        "attempt_id": make_attempt_id(session_id, attempt_number),
        "player_id": player_id,
        "session_id": session_id,
        "timestamp": now.replace("+00:00", "Z"),
        "question_id": question["id"],
        "topic": question["topic"],
        "difficulty": question["difficulty"],
        "chosen_option": chosen_option,
        "is_correct": bool(is_correct),
        "response_time_ms": response_time_ms,
    }


def _ends_with_newline(path):
    """False if the file ends in the middle of a line (e.g. after a crash)."""
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            if f.tell() == 0:
                return True
            f.seek(-1, os.SEEK_END)
            return f.read(1) == b"\n"
    except FileNotFoundError:
        return True


def save_attempt(session_id, player_id, attempt_number, question, chosen_option,
                 is_correct, response_time_ms=None, path=None):
    """Append one attempt to the file. Never raises.

    Returns (status, message): status is "saved", "duplicate" or "error".
    """
    try:
        path = Path(path) if path else attempts_path()
        record = build_record(session_id, player_id, attempt_number, question,
                              chosen_option, is_correct, response_time_ms)
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        key = (str(path), record["attempt_id"])
        with _lock:
            if key in _saved:
                return "duplicate", "attempt already saved"
            path.parent.mkdir(parents=True, exist_ok=True)
            prefix = "" if _ends_with_newline(path) else "\n"
            with open(path, "a", encoding="utf-8", newline="\n") as f:
                f.write(prefix + line)
                f.flush()
                os.fsync(f.fileno())                 # make sure it is on disk
            _saved.add(key)
        return "saved", ""
    except Exception as error:                      # data collection must never break the game
        log.warning("could not save attempt: %s", error)
        return "error", str(error)
