"""Loading and validating questions.

This is the ONLY place that knows where questions come from. The game logic
just receives a list of question dictionaries. In the future, an AI generator
can return the same structure (see QUESTION_FIELDS) and nothing else changes.

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
from pathlib import Path

DEFAULT_PATH = Path(__file__).parent / "data" / "questions.json"

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
