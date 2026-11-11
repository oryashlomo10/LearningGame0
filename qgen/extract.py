"""Text extraction from uploaded study material (PDF or TXT). No Streamlit code.

extract_document(data, filename) returns one dictionary:
    document_id    short id derived from the file content (same file = same id)
    document_name  the file name
    file_type      "pdf" or "txt"
    pages          [{"page": 1, "text": ..., "char_start": ..., "char_end": ...}]
                   (page is None for TXT; empty pages have char_start/end None)
    full_text      all page texts joined with a blank line. char_start/char_end
                   of pages and of chunks (see chunking.py) point into this text,
                   so every chunk is an exact substring of full_text.
    warnings       messages for the user (Hebrew) about possible quality problems
    stats          page_count, empty_pages, word_count, char_count

Problems the user should know about raise ExtractionError. Its message is Hebrew
and meant to be shown as is.
"""

import hashlib
import io
import logging
import re

from pypdf import PdfReader

log = logging.getLogger("conquest.qgen")

MAX_FILE_BYTES = 15 * 1024 * 1024
MAX_PAGES = 500
MIN_USEFUL_CHARS = 20            # less text than this in the whole file = "no text"
SUPPORTED_TYPES = {".pdf": "pdf", ".txt": "txt"}


class ExtractionError(Exception):
    """A problem with the uploaded file. str(error) is a clear Hebrew message."""


# ----------------------------------------------------------------------
# Cleaning
# ----------------------------------------------------------------------
# Invisible direction marks, BOM and soft hyphens only confuse later text matching.
_INVISIBLE = dict.fromkeys(map(ord, "‎‏‪‫‬‭‮⁦⁧⁨⁩﻿­"), None)
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def normalize_text(text):
    """Clean extracted text.

    Spaces are collapsed, a single line break inside a paragraph becomes a space
    (PDF lines are broken arbitrarily), and a blank line stays a paragraph break.
    """
    text = text.translate(_INVISIBLE).replace("\r\n", "\n").replace("\r", "\n")
    text = _CONTROL.sub("", text)
    text = re.sub(r"[^\S\n]+", " ", text)           # spaces, tabs, non-breaking spaces
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    return text.strip()


def count_words(text):
    return len(text.split())


# ----------------------------------------------------------------------
# Quality warnings
# ----------------------------------------------------------------------
_HEBREW = re.compile(r"[֐-׿]+")
_FINAL_LETTERS = "ךםןףץ"          # in correct Hebrew these appear only at the END of a word


def quality_warnings(text):
    """Messages about extracted text that may be unreliable."""
    warnings = []
    if not text:
        return warnings
    odd = text.count("�") + len(re.findall(r"[-]", text)) + 5 * text.count("(cid:")
    if odd / len(text) > 0.02:
        warnings.append("חלק מהתווים בטקסט שחולץ נראים משובשים (כנראה בגלל גופן שלא ניתן לפענח ב-PDF). "
                        "כדאי לבדוק את הטקסט לפני השימוש בו.")
    words = _HEBREW.findall(text)
    starts = sum(1 for w in words if w[0] in _FINAL_LETTERS)
    ends = sum(1 for w in words if w[-1] in _FINAL_LETTERS)
    if starts >= 5 and starts > 2 * ends:
        warnings.append("נראה שהעברית חולצה בסדר הפוך (אותיות סופיות מופיעות בתחילת מילים). "
                        "מומלץ לנסות לייצא את המסמך ל-PDF מחדש או להעלות אותו כקובץ TXT.")
    elif words and len(re.findall(r"[A-Za-z]{2,}|\d+", text)) >= 3:
        warnings.append("המסמך מכיל עברית לצד אנגלית או מספרים. ב-PDF, סדר המילים בשורות מעורבות כאלה "
                        "עלול להתבלבל בחילוץ. כדאי לעבור על הטקסט לפני יצירת שאלות.")
    return warnings


# ----------------------------------------------------------------------
# Readers
# ----------------------------------------------------------------------
def _page_list_text(numbers, limit=10):
    shown = ", ".join(str(n) for n in numbers[:limit])
    return shown + (f" ועוד {len(numbers) - limit}" if len(numbers) > limit else "")


def _read_pdf(data):
    """Return ([(page_number, text), ...], warnings)."""
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise ExtractionError("הקובץ מוגן בסיסמה, ולכן אי אפשר לקרוא אותו. הסירו את ההגנה ונסו שוב.")
        page_count = len(reader.pages)
    except ExtractionError:
        raise
    except Exception as error:
        log.info("could not open PDF: %s", error)
        raise ExtractionError("הקובץ אינו קובץ PDF תקין או שהוא פגום, ולכן לא ניתן לקרוא אותו.")
    if page_count == 0:
        raise ExtractionError("ה-PDF אינו מכיל עמודים.")
    if page_count > MAX_PAGES:
        raise ExtractionError(f"ה-PDF ארוך מדי ({page_count} עמודים). המקסימום הוא {MAX_PAGES} עמודים.")

    pages, failed = [], []
    for number in range(1, page_count + 1):
        try:
            raw = reader.pages[number - 1].extract_text() or ""
        except Exception as error:                  # one bad page must not stop the whole file
            log.info("page %s could not be read: %s", number, error)
            raw, failed = "", failed + [number]
        pages.append((number, normalize_text(raw)))

    warnings = []
    if failed:
        warnings.append(f"לא ניתן היה לקרוא את העמודים: {_page_list_text(failed)}.")
    return pages, warnings


def _decode_text(data):
    """Decode a text file: UTF-8 (with or without BOM), UTF-16, or Hebrew Windows (cp1255)."""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        encodings = ["utf-16"]
    else:
        encodings = ["utf-8-sig", "cp1255"]
    for encoding in encodings:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ExtractionError("לא ניתן לקרוא את הקובץ כקובץ טקסט. שמרו אותו בקידוד UTF-8 ונסו שוב.")


def _read_txt(data):
    text = _decode_text(data)
    if "\x00" in text or len(_CONTROL.findall(text)) > 0.02 * max(len(text), 1):
        raise ExtractionError("הקובץ אינו נראה כקובץ טקסט (הוא מכיל נתונים בינאריים).")
    return [(None, normalize_text(text))], []


# ----------------------------------------------------------------------
# Public function
# ----------------------------------------------------------------------
def extract_document(data, filename):
    """Extract the text of a PDF or TXT file. Raises ExtractionError with a Hebrew message."""
    name = filename or "ללא שם"
    suffix = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if suffix not in SUPPORTED_TYPES:
        raise ExtractionError("סוג הקובץ אינו נתמך. אפשר להעלות קובצי PDF או TXT בלבד.")
    if not data:
        raise ExtractionError("הקובץ ריק.")
    if len(data) > MAX_FILE_BYTES:
        raise ExtractionError(f"הקובץ גדול מדי. הגודל המקסימלי הוא {MAX_FILE_BYTES // (1024 * 1024)}MB.")

    file_type = SUPPORTED_TYPES[suffix]
    pages, warnings = _read_pdf(data) if file_type == "pdf" else _read_txt(data)

    total_chars = sum(len(text) for _, text in pages)
    if total_chars == 0 and file_type == "txt":
        raise ExtractionError("הקובץ ריק או מכיל רווחים בלבד.")
    if total_chars < MIN_USEFUL_CHARS and file_type == "txt":
        raise ExtractionError("בקובץ כמעט אין טקסט, ואי אפשר לחלק אותו למקטעים. העלו קובץ עם תוכן ארוך יותר.")
    if total_chars < MIN_USEFUL_CHARS:
        raise ExtractionError(
            "לא נמצא טקסט בקובץ. ייתכן שהוא סרוק (מכיל תמונות בלבד), ובשלב הזה אין זיהוי טקסט מתמונה (OCR). "
            "נסו קובץ שבו אפשר לסמן ולהעתיק טקסט.")

    # Join the pages and remember where each page is inside the full text.
    page_records, parts, position = [], [], 0
    for number, text in pages:
        if not text:
            page_records.append({"page": number, "text": "", "char_start": None, "char_end": None})
            continue
        if parts:
            position += 2                              # the "\n\n" between pages
        page_records.append({"page": number, "text": text, "char_start": position, "char_end": position + len(text)})
        parts.append(text)
        position += len(text)
    full_text = "\n\n".join(parts)

    empty = [p["page"] for p in page_records if not p["text"] and p["page"] is not None]
    if empty:
        warnings.append(f"בעמודים אלה לא נמצא טקסט (ייתכן שהם ריקים או סרוקים): {_page_list_text(empty)}.")
    warnings += quality_warnings(full_text)

    return {
        "document_id": hashlib.sha1(data).hexdigest()[:10],
        "document_name": name,
        "file_type": file_type,
        "pages": page_records,
        "full_text": full_text,
        "warnings": warnings,
        "stats": {
            "page_count": len(page_records) if file_type == "pdf" else None,
            "empty_pages": len(empty),
            "word_count": count_words(full_text),
            "char_count": len(full_text),
        },
    }
