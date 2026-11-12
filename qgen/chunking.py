"""Splitting extracted text into chunks that remember where they came from.

chunk_document(document) takes the dictionary returned by extract.extract_document
and returns a list of chunks. Every chunk is an EXACT substring of
document["full_text"], so a quote taken from a chunk can always be found again.

How it works:
  1. The text is split into sentences (after . ! ? and at blank lines). A sentence
     never crosses a page boundary, and a sentence longer than max_words is cut
     into pieces of at most max_words words.
  2. Sentences are packed into a chunk until adding the next one would exceed
     max_words.
  3. The next chunk starts with the last sentences of the previous chunk (up to
     overlap_words words), so a sentence at the border keeps its context.
  4. A very short last piece is attached to the previous chunk.

Each chunk is a dictionary:
    chunk_id        "<document_id>-<index>", e.g. "3fa9c1d20b-004"
    index           0, 1, 2, ...
    document_id, document_name
    text            the chunk text
    char_start/char_end   position inside full_text
    page_start/page_end   first/last page of the chunk (None for TXT)
    word_count      words in the chunk
    overlap_words   words shared with the previous chunk (0 for the first)
"""

import re

DEFAULT_MAX_WORDS = 200
DEFAULT_OVERLAP_WORDS = 30
MIN_LAST_CHUNK_WORDS = 25

_SENTENCE_BREAK = re.compile(r"(?<=[.!?…])\s+|\n{2,}")
_WORD = re.compile(r"\S+")


def _sentence_spans(text):
    """(start, end) of every sentence in text."""
    position = 0
    for match in _SENTENCE_BREAK.finditer(text):
        if match.start() > position:
            yield position, match.start()
        position = match.end()
    if position < len(text):
        yield position, len(text)


def _units(text, max_words):
    """Sentences as {"start", "end", "words"}; too-long sentences are cut by words."""
    units = []
    for start, end in _sentence_spans(text):
        words = list(_WORD.finditer(text, start, end))
        if not words:
            continue
        for first in range(0, len(words), max_words):
            piece = words[first:first + max_words]
            units.append({"start": piece[0].start(), "end": piece[-1].end(), "words": len(piece)})
    return units


def _overlap_tail(units, overlap_words):
    """The last units of a chunk whose total size is at most overlap_words."""
    tail, total = [], 0
    for unit in reversed(units):
        if total + unit["words"] > overlap_words:
            break
        tail.insert(0, unit)
        total += unit["words"]
    return tail


def _pack(units, max_words, overlap_words):
    """Group units into chunks. Returns [{"units": [...], "new_from": index of first new unit}]."""
    chunks, current, new_from, words = [], [], 0, 0
    for unit in units:
        if current and len(current) > new_from and words + unit["words"] > max_words:
            chunks.append({"units": current, "new_from": new_from})
            current = _overlap_tail(current, overlap_words)
            words = sum(u["words"] for u in current)
            if words + unit["words"] > max_words:       # no room left for the overlap
                current, words = [], 0
            new_from = len(current)
        current.append(unit)
        words += unit["words"]
    if len(current) > new_from:
        chunks.append({"units": current, "new_from": new_from})

    # a tiny last chunk is better attached to the one before it
    if len(chunks) >= 2:
        last = chunks[-1]
        new_units = last["units"][last["new_from"]:]
        if sum(u["words"] for u in new_units) < MIN_LAST_CHUNK_WORDS:
            chunks[-2]["units"] = chunks[-2]["units"] + new_units
            chunks.pop()
    return chunks


def _page_at(pages, offset):
    """The page number that contains the character at offset (None for TXT)."""
    for page in pages:
        if page["char_start"] is not None and page["char_start"] <= offset < page["char_end"]:
            return page["page"]
    return None


def chunk_document(document, max_words=DEFAULT_MAX_WORDS, overlap_words=DEFAULT_OVERLAP_WORDS):
    """Split an extracted document into chunks (see the module docstring)."""
    if not 30 <= max_words <= 1000:
        raise ValueError("max_words must be between 30 and 1000")
    if not 0 <= overlap_words <= max_words // 2:
        raise ValueError("overlap_words must be between 0 and max_words / 2")

    text = document["full_text"]
    packed = _pack(_units(text, max_words), max_words, overlap_words)
    chunks, previous_end = [], 0
    for index, item in enumerate(packed):
        start, end = item["units"][0]["start"], item["units"][-1]["end"]
        chunks.append({
            "chunk_id": f"{document['document_id']}-{index:03d}",
            "index": index,
            "document_id": document["document_id"],
            "document_name": document["document_name"],
            "text": text[start:end],
            "char_start": start,
            "char_end": end,
            "page_start": _page_at(document["pages"], start),
            "page_end": _page_at(document["pages"], end - 1),
            "word_count": len(_WORD.findall(text, start, end)),
            "overlap_words": len(_WORD.findall(text, start, previous_end)) if index and start < previous_end else 0,
        })
        previous_end = end
    return chunks
