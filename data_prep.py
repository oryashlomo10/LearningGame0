"""Cleans the raw ASSISTments 2009-2010 skill-builder file (corrected version).

Usage:
    python data_prep.py <path to skill_builder_data_corrected.csv>

Writes data/assistments_clean.csv and prints how many rows each cleaning step removed
(the numbers are copied into the "מה תיקנו ולמה" section of README.md).
The raw file (64MB) is NOT stored in the repo; the download link is in README.md.
"""
import sys
from pathlib import Path

import pandas as pd

OUTPUT = Path(__file__).parent / "data" / "assistments_clean.csv"

# A first response slower than this is almost always an abandoned session, not a real answer time.
MAX_RESPONSE_MS = 10 * 60 * 1000

# Columns we keep. correct is the target (y); the rest describe the student's attempt.
KEEP = [
    "user_id", "problem_id", "skill_id", "skill_name", "answer_type",
    "response_sec", "hint_count", "attempt_count", "opportunity", "correct",
]


def clean(raw):
    """Returns (clean_df, log) where log is a list of (step, rows_removed)."""
    log = []
    df = raw.copy()
    log.append(("שורות בקובץ המקורי", len(df)))

    # Rows without a skill cannot be used per topic (our game works per topic).
    before = len(df)
    df = df.dropna(subset=["skill_id", "skill_name"])
    log.append(("נמחקו: ללא נושא (skill)", before - len(df)))

    # Negative or zero times are impossible.
    before = len(df)
    df = df[df["ms_first_response"] > 0]
    log.append(("נמחקו: זמן תגובה אפס או שלילי", before - len(df)))

    before = len(df)
    df = df[df["ms_first_response"] <= MAX_RESPONSE_MS]
    log.append(("נמחקו: זמן תגובה מעל 10 דקות", before - len(df)))

    # The same student answering the same problem twice (the corrected file should have none).
    before = len(df)
    df = df.drop_duplicates(subset=["user_id", "problem_id"])
    log.append(("נמחקו: כפילויות (תלמיד+שאלה)", before - len(df)))

    df["response_sec"] = (df["ms_first_response"] / 1000).round(2)
    df["skill_name"] = df["skill_name"].str.strip()
    df["skill_id"] = df["skill_id"].astype(str)
    df["correct"] = df["correct"].astype(int)

    df = df[KEEP].reset_index(drop=True)
    log.append(("שורות אחרי ניקוי", len(df)))
    return df, log


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: python data_prep.py <path to raw csv>")
    # The file is Latin-1 encoded (no Hebrew in it).
    raw = pd.read_csv(sys.argv[1], encoding="latin-1", low_memory=False)
    df, log = clean(raw)
    OUTPUT.parent.mkdir(exist_ok=True)
    df.to_csv(OUTPUT, index=False)
    for step, count in log:
        print(f"{step}: {count:,}")
    print(f"נשמר ל-{OUTPUT} ({OUTPUT.stat().st_size / 1e6:.1f}MB)")


if __name__ == "__main__":
    main()
