"""Question generation from chunks (no Streamlit, no specific LLM).

Flow for each chunk:
    prompt (chunk text only) -> provider.generate_text -> parse JSON -> validate each question
    -> keep the valid ones (with source quote, chunk id and page), report the rest in Hebrew.

A generated question follows the game's question schema (question_bank.QUESTION_FIELDS)
plus source fields, so it can be passed to the game later without changes:
    id, question, options (4), correct_answer, explanation, topic, difficulty, points,
    source_quote, source_chunk_id, source_page, source_document
`source_page` is the page where the quote appears (None for TXT files).
"""

import json
import random
import re

from question_bank import DIFFICULTIES, validate_question
from qgen.providers import ProviderError, ProviderUnavailable

POINTS_BY_DIFFICULTY = {"easy": 10, "medium": 20, "hard": 30}   # same values as the game rules
MIN_QUOTE_CHARS = 12
MAX_QUESTIONS_PER_CHUNK = 5

SYSTEM_PROMPT = (
    "אתה מורה שכותב שאלות אמריקאיות בעברית לתלמידים, אך ורק על סמך קטע טקסט שיינתן לך.\n"
    "כללים:\n"
    "1. השתמש רק במידע שמופיע בקטע. אל תוסיף ידע חיצוני ואל תנחש.\n"
    "2. אם הקטע אינו מכיל מספיק מידע לשאלה טובה, החזר פחות שאלות, או רשימה ריקה.\n"
    "3. לכל שאלה בדיוק 4 תשובות שונות, ורק אחת נכונה לפי הקטע. התשובות השגויות סבירות אך שגויות.\n"
    "4. correct_answer חייב להיות זהה, מילה במילה, לאחת מהתשובות ב-options.\n"
    "5. source_quote חייב להיות ציטוט מדויק, מילה במילה, מתוך הקטע, שתומך בתשובה הנכונה "
    "(משפט או חלק ממשפט, לא שינוי ניסוח).\n"
    "6. explanation: הסבר קצר בעברית שמבוסס על הקטע.\n"
    "7. difficulty הוא אחד מ: easy, medium, hard.\n"
    "החזר אך ורק JSON במבנה הזה, בלי טקסט נוסף:\n"
    '{"questions": [{"question": "...", "options": ["...", "...", "...", "..."], '
    '"correct_answer": "...", "explanation": "...", "topic": "...", "difficulty": "easy", '
    '"source_quote": "..."}]}'
)


def build_user_prompt(chunk, questions_per_chunk):
    return (
        f"כתוב עד {questions_per_chunk} שאלות אמריקאיות על הקטע הבא בלבד.\n\n"
        f"--- תחילת הקטע ---\n{chunk['text']}\n--- סוף הקטע ---"
    )


# ----------------------------------------------------------------------
# Parsing the model's answer
# ----------------------------------------------------------------------
def parse_model_json(text):
    """Return the list of raw question objects from the model's text, or raise ValueError."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned)           # a markdown fence around the JSON
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")               # JSON surrounded by extra words
        if start == -1 or end <= start:
            raise ValueError("התשובה אינה JSON")
        try:
            data = json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError as error:
            raise ValueError("התשובה אינה JSON תקין") from error
    if isinstance(data, dict):
        data = data.get("questions")
    if not isinstance(data, list):
        raise ValueError("בתשובה חסרה רשימת שאלות (questions)")
    return data


# ----------------------------------------------------------------------
# Validation of one question
# ----------------------------------------------------------------------
def _clean(value):
    return re.sub(r"\s+", " ", value).strip() if isinstance(value, str) else ""


def find_quote(chunk_text, quote):
    """Locate the quote inside the chunk, ignoring differences in whitespace only.

    Returns (start, end) offsets inside chunk_text, or None when it does not appear.
    """
    words = quote.split()
    if not words:
        return None
    pattern = r"\s+".join(re.escape(word) for word in words)
    match = re.search(pattern, chunk_text)
    return (match.start(), match.end()) if match else None


def page_of_offset(document, offset):
    """Page number that contains this character offset of full_text (None if no pages)."""
    for page in document["pages"]:
        if page["page"] is not None and page["char_start"] <= offset < page["char_end"]:
            return page["page"]
    return None


def check_question(raw, chunk, document):
    """Validate one raw question from the model.

    Returns (question_without_id, None) when valid, or (None, hebrew_problem) when not.
    """
    if not isinstance(raw, dict):
        return None, "השאלה אינה אובייקט"
    for field in ("question", "correct_answer", "explanation", "topic", "difficulty", "source_quote"):
        if not _clean(raw.get(field)):
            return None, f"חסר שדה חובה: {field}"
    options = raw.get("options")
    if not isinstance(options, list) or len(options) != 4:
        return None, "חייבות להיות בדיוק 4 אפשרויות"
    if not all(isinstance(o, str) and _clean(o) for o in options):
        return None, "אפשרות ריקה או לא טקסטואלית"
    options = [_clean(o) for o in options]
    if len(set(options)) != 4:
        return None, "האפשרויות חייבות להיות שונות זו מזו"
    correct = _clean(raw["correct_answer"])
    if correct not in options:
        return None, "התשובה הנכונה אינה אחת מהאפשרויות"
    difficulty = _clean(raw["difficulty"]).lower()
    if difficulty not in DIFFICULTIES:
        return None, "רמת הקושי חייבת להיות easy, medium או hard"
    quote = _clean(raw["source_quote"])
    if len(quote) < MIN_QUOTE_CHARS:
        return None, "הציטוט קצר מדי"
    span = find_quote(chunk["text"], quote)
    if span is None:
        return None, "הציטוט אינו מופיע במקטע (ייתכן שהמודל המציא או שינה אותו)"

    offset = chunk["char_start"] + span[0]
    return {
        "question": _clean(raw["question"]),
        "options": options,
        "correct_answer": correct,
        "explanation": _clean(raw["explanation"]),
        "topic": _clean(raw["topic"]),
        "difficulty": difficulty,
        "points": POINTS_BY_DIFFICULTY[difficulty],
        "source_quote": chunk["text"][span[0]:span[1]],      # the exact text as it appears in the source
        "source_chunk_id": chunk["chunk_id"],
        "source_page": page_of_offset(document, offset),
        "source_document": chunk["document_name"],
    }, None


# ----------------------------------------------------------------------
# Whole run
# ----------------------------------------------------------------------
def generate_for_chunk(chunk, document, provider, questions_per_chunk=2):
    """Generate questions for one chunk. Returns (questions, problems[list of Hebrew strings]).

    Raises ProviderUnavailable when the provider cannot be used at all.
    """
    label = f"מקטע {chunk['index'] + 1}"
    try:
        text = provider.generate_text(SYSTEM_PROMPT, build_user_prompt(chunk, questions_per_chunk))
    except ProviderUnavailable:
        raise
    except ProviderError as error:
        return [], [f"{label}: {error}"]
    try:
        raw_questions = parse_model_json(text)
    except ValueError as error:
        return [], [f"{label}: תשובת המודל אינה תקינה ({error})"]
    if not raw_questions:
        return [], [f"{label}: המודל לא החזיר שאלות עבור המקטע הזה"]

    questions, problems = [], []
    for number, raw in enumerate(raw_questions[:MAX_QUESTIONS_PER_CHUNK], start=1):
        question, problem = check_question(raw, chunk, document)
        if problem:
            problems.append(f"{label}, שאלה {number}: נדחתה. {problem}")
            continue
        question["id"] = f"gen-{chunk['chunk_id']}-{number}"
        random.Random(question["id"]).shuffle(question["options"])   # models like to put the answer first
        issues = validate_question(question)                          # final check against the game schema
        if issues:
            problems.append(f"{label}, שאלה {number}: נדחתה. {'; '.join(issues)}")
            continue
        questions.append(question)
    return questions, problems


def generate_questions(chunks, document, provider, questions_per_chunk=2, progress=None):
    """Generate questions for several chunks.

    Never raises for provider/model problems. Returns:
        {"questions": [...], "problems": [hebrew, ...], "fatal": hebrew message or None}
    `progress(done, total)` is called after each chunk (optional).
    """
    questions, problems, seen = [], [], set()
    for done, chunk in enumerate(chunks, start=1):
        try:
            new, issues = generate_for_chunk(chunk, document, provider, questions_per_chunk)
        except ProviderUnavailable as error:
            return {"questions": questions, "problems": problems, "fatal": str(error)}
        except Exception:                      # a provider bug must not crash the game
            issues, new = [f"מקטע {chunk['index'] + 1}: אירעה שגיאה לא צפויה"], []
        problems.extend(issues)
        for question in new:
            key = question["question"]
            if key in seen:
                problems.append(f"מקטע {chunk['index'] + 1}: שאלה כפולה הוסרה")
                continue
            seen.add(key)
            questions.append(question)
        if progress:
            progress(done, len(chunks))
    return {"questions": questions, "problems": problems, "fatal": None}
