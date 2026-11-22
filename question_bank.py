"""Loading, validating and managing questions.

This is the ONLY place that knows where questions come from. The game logic
just receives a list of question dictionaries.

Two sources exist:
    data/questions.json           sample questions, used for DEMO mode only
    data/approved_questions.json  generated questions that a person approved
                                  (they come from material the user uploaded)

get_game_questions() decides which source the game uses: approved questions if
there are any, otherwise the sample questions in a clearly marked demo mode.
Question GENERATION lives in qgen/ and game RULES in game_logic.py; this module
only stores, checks and hands out questions.

Question schema:
    id             unique string
    question       the question text (Hebrew)
    options        list of exactly 4 different answer strings
    correct_answer one of the options (the exact text)
    explanation    short explanation shown after answering
    topic          topic name
    difficulty     "easy" | "medium" | "hard"
    points         integer reward
"""

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PATH = Path(__file__).parent / "data" / "questions.json"
APPROVED_PATH = Path(__file__).parent / "data" / "approved_questions.json"
APPROVED_PATH_ENV_VAR = "CONQUEST_APPROVED_PATH"     # tests point this at a temporary file

QUESTION_FIELDS = (
    "id", "question", "options", "correct_answer",
    "explanation", "topic", "difficulty", "points",
)
DIFFICULTIES = ("easy", "medium", "hard")


def validate_question(q):
    """Return a list of problems found in one question (empty list = valid)."""
    if not isinstance(q, dict):
        return ["question is not an object"]
    problems = [f"missing field '{f}'" for f in QUESTION_FIELDS if f not in q]
    if problems:
        return problems

    options = q["options"]
    if not isinstance(options, list) or len(options) != 4:
        problems.append("options must be a list of exactly 4 items")
    elif len(set(options)) != 4:
        problems.append("options must be 4 different answers")
    elif q["correct_answer"] not in options:
        problems.append("correct_answer must be one of the options")
    if q["difficulty"] not in DIFFICULTIES:
        problems.append("difficulty must be easy, medium or hard")
    if not isinstance(q["points"], int) or q["points"] <= 0:
        problems.append("points must be a positive integer")
    return problems


def validate_questions(questions):
    """Raise ValueError if any question is invalid or ids are duplicated."""
    seen = set()
    for index, q in enumerate(questions):
        problems = validate_question(q)
        qid = q.get("id", f"#{index}") if isinstance(q, dict) else f"#{index}"
        if qid in seen:
            problems.append("duplicate id")
        seen.add(qid)
        if problems:
            raise ValueError(f"Invalid question {qid}: {'; '.join(problems)}")


def load_question_bank(path=DEFAULT_PATH):
    """Load a question bank from a JSON file.

    Returns {"course": str, "questions": [question, ...]}.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    validate_questions(data["questions"])
    return {"course": data.get("course", ""), "questions": data["questions"]}


# ----------------------------------------------------------------------
# Approved questions (generated from uploaded material, checked by a person)
# ----------------------------------------------------------------------
# An approved question is a normal game question plus where it came from.
#   topic          = game_topic, so the game and the answer log work unchanged
#   game_topic     the game topic (one of the REGIONS topics) chosen by the reviewer
#   original_topic the free-text topic the AI model wrote (kept, never used by the game)
#   source_*       the quote, chunk, page and document the question is based on
APPROVED_FILE_VERSION = 1
SOURCE_FIELDS = ("source_quote", "source_chunk_id", "source_page", "source_document")
APPROVED_TEXT_FIELDS = ("source_quote", "source_chunk_id", "source_document", "game_topic", "original_topic")

MODE_APPROVED = "approved"
MODE_DEMO = "demo"
UPLOADED_COURSE_LABEL = "חומר שהועלה"

log = logging.getLogger("conquest.question_bank")
_lock = threading.Lock()


class ApprovedFileError(ValueError):
    """The approved questions file exists but cannot be read safely."""


def approved_path():
    return Path(os.environ.get(APPROVED_PATH_ENV_VAR) or APPROVED_PATH)


def _normalize(text):
    """Text for comparing questions: no case and no whitespace differences."""
    return " ".join(str(text).split()).casefold()


def validate_approved_question(q, game_topics=None):
    """Problems of a stored approved question (empty list = valid).

    It must be a valid game question AND carry its source, so a question that is
    not based on uploaded material can never reach the game through this file.
    """
    problems = validate_question(q)
    if problems:
        return problems
    for field in SOURCE_FIELDS:
        if field not in q:
            problems.append(f"missing field '{field}'")
    for field in APPROVED_TEXT_FIELDS:
        if not isinstance(q.get(field), str) or not q[field].strip():
            problems.append(f"'{field}' must be a non-empty text")
    if problems:
        return problems
    if q["topic"] != q["game_topic"]:
        problems.append("topic must equal game_topic")
    if game_topics is not None and q["game_topic"] not in game_topics:
        problems.append("game_topic is not a game topic")
    return problems


def _read_approved_file(path):
    """Return the stored list. Missing file = empty list. Raises ApprovedFileError if unreadable."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as error:
        raise ApprovedFileError(f"cannot read {path}: {error}") from error
    if not isinstance(data, dict) or not isinstance(data.get("questions"), list):
        raise ApprovedFileError(f"{path} has no 'questions' list")
    return data["questions"]


def _write_approved_file(path, questions):
    """Write the whole file in one step (temporary file + replace), so it is never half-written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    data = {"version": APPROVED_FILE_VERSION, "questions": questions}
    with open(temp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)


def load_approved(path=None, game_topics=None):
    """All valid approved questions. Never raises: a broken file or entry is skipped (and logged)."""
    path = Path(path) if path else approved_path()
    try:
        stored = _read_approved_file(path)
    except ApprovedFileError as error:
        log.warning("%s", error)
        return []
    questions, seen = [], set()
    for q in stored:
        problems = validate_approved_question(q, game_topics)
        if not problems and q["id"] in seen:
            problems = ["duplicate id"]
        if problems:
            name = q.get("id") if isinstance(q, dict) else "?"
            log.warning("skipping approved question %s: %s", name, "; ".join(problems))
            continue
        seen.add(q["id"])
        questions.append(q)
    return questions


def approved_ids(path=None):
    return {q["id"] for q in load_approved(path)}


def approve_question(generated, game_topic, game_topics, path=None):
    """Save one generated question as approved, under a game topic chosen by the reviewer.

    generated    a question from qgen.generate (game schema + source_* fields)
    game_topic   must be one of game_topics (the topics of the game regions)
    Returns (status, message): "saved", "duplicate" (same id or same question text)
    or "error". Never raises and never changes `generated`.
    """
    try:
        if game_topic not in game_topics:
            return "error", "יש לבחור נושא מתוך נושאי המשחק"
        record = dict(generated)
        record["original_topic"] = generated.get("topic", "")      # what the model wrote
        record["topic"] = record["game_topic"] = game_topic        # what the game uses
        record["approved_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        problems = validate_approved_question(record, game_topics)
        if problems:
            return "error", "השאלה אינה תקינה: " + "; ".join(problems)

        path = Path(path) if path else approved_path()
        with _lock:
            stored = _read_approved_file(path)         # refuses to overwrite a file it cannot read
            ids = {q.get("id") for q in stored if isinstance(q, dict)}
            texts = {_normalize(q.get("question", "")) for q in stored if isinstance(q, dict)}
            if record["id"] in ids or _normalize(record["question"]) in texts:
                return "duplicate", "שאלה כזו כבר קיימת במאגר המאושר"
            _write_approved_file(path, stored + [record])
        return "saved", ""
    except Exception as error:                          # the review screen must not crash
        log.warning("could not save approved question: %s", error)
        return "error", f"השמירה נכשלה: {error}"


def reject_question(question_id, path=None):
    """Make sure a question is NOT in the approved file (rejecting what was approved).

    Returns (status, message): "removed", "not_found" or "error". A question that
    was never approved is simply "not_found" and nothing is written.
    """
    try:
        path = Path(path) if path else approved_path()
        with _lock:
            stored = _read_approved_file(path)
            kept = [q for q in stored if not (isinstance(q, dict) and q.get("id") == question_id)]
            if len(kept) == len(stored):
                return "not_found", ""
            _write_approved_file(path, kept)
        return "removed", ""
    except Exception as error:
        log.warning("could not remove approved question: %s", error)
        return "error", f"ההסרה נכשלה: {error}"


# ----------------------------------------------------------------------
# What the game plays
# ----------------------------------------------------------------------
def get_game_questions(game_topics=None, approved=None, demo_path=DEFAULT_PATH):
    """The question bank for a new game.

    Approved questions from uploaded material if there are any (only those are
    used then). Otherwise the sample questions, with mode "demo" so the UI can
    say so. Returns {"mode": "approved" | "demo", "course": str, "questions": [...]}.
    game_topics: only approved questions of these topics are used (None = all).
    """
    questions = load_approved(approved, game_topics)
    if questions:
        return {"mode": MODE_APPROVED, "course": UPLOADED_COURSE_LABEL, "questions": questions}
    bank = load_question_bank(demo_path)
    return {"mode": MODE_DEMO, "course": bank["course"], "questions": bank["questions"]}
