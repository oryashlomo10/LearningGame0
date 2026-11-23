"""EDA dashboard for the Conquest data (Milestone 2).

Run:  streamlit run dashboard.py

Data: data/assistments_clean.csv (cleaned ASSISTments 2009-2010, see README.md)
plus, when it exists, the real answers collected by the game (data/attempts.jsonl).
Target (y): correct = did the student answer the question correctly on the first try.
"""
import json
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).parent / "data"
ASSIST_FILE = DATA_DIR / "assistments_clean.csv"
ATTEMPTS_FILE = DATA_DIR / "attempts.jsonl"

# Response-time groups (seconds) used by the chart and the insight sentence.
TIME_BINS = [0, 5, 10, 20, 40, 80, 600]
TIME_LABELS = ["עד 5", "5-10", "10-20", "20-40", "40-80", "מעל 80"]

st.set_page_config(page_title="Conquest · נתונים", page_icon="📊", layout="wide")
st.markdown(
    "<style>.block-container{direction:rtl;text-align:right}"
    "[data-testid='stMetric']{direction:rtl;text-align:right}</style>",
    unsafe_allow_html=True,
)


def read_game_attempts():
    """Real answers collected by the game, in the same columns as the ASSISTments file."""
    if not ATTEMPTS_FILE.exists():
        return pd.DataFrame()
    rows = []
    for line in ATTEMPTS_FILE.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
            rows.append({
                "user_id": str(item["player_id"]),
                "problem_id": str(item["question_id"]),
                "skill_id": item["topic"],
                "skill_name": item["topic"],
                "answer_type": "choose_1",
                "response_sec": item["response_time_ms"] / 1000,
                "correct": int(bool(item["is_correct"])),
                "source": "Conquest (המשחק)",
            })
        except (ValueError, KeyError, TypeError):
            continue  # skip a broken line, the dashboard must still open
    return pd.DataFrame(rows)


@st.cache_data
def load_data():
    df = pd.read_csv(ASSIST_FILE, dtype={"skill_id": str})
    df["user_id"] = df["user_id"].astype(str)
    df["problem_id"] = df["problem_id"].astype(str)
    df["source"] = "ASSISTments"
    game = read_game_attempts()
    if not game.empty:
        df = pd.concat([df, game], ignore_index=True)
    df["time_group"] = pd.cut(df["response_sec"], TIME_BINS, labels=TIME_LABELS)
    return df


df = load_data()

# ---------- Sidebar filters ----------
st.sidebar.header("סינון")
sources = st.sidebar.multiselect("מקור הנתונים", sorted(df["source"].unique()), default=sorted(df["source"].unique()))
types = st.sidebar.multiselect("סוג שאלה", sorted(df["answer_type"].unique()), default=sorted(df["answer_type"].unique()))
skills = st.sidebar.multiselect("נושא (ברירת מחדל: כולם)", sorted(df["skill_name"].unique()), default=[])
max_time = st.sidebar.slider("זמן תגובה מקסימלי (שניות)", 5, 600, 600)

view = df[df["source"].isin(sources) & df["answer_type"].isin(types) & (df["response_sec"] <= max_time)]
if skills:
    view = view[view["skill_name"].isin(skills)]

st.title("📊 Conquest · מה הנתונים מספרים")

# ---------- Insight (computed from ALL the data, not from the filter) ----------
by_time = df.groupby("time_group", observed=True)["correct"].mean() * 100
fast, mid, slow = by_time[TIME_LABELS[0]], by_time[TIME_LABELS[1]], by_time[TIME_LABELS[-1]]
st.info(
    f"**גילינו ש...** הקשר בין זמן התגובה להצלחה אינו ישר: תשובה מהירה מאוד (עד 5 שניות) נכונה רק ב-{fast:.0f}% מהמקרים, "
    f"כמעט כמו ניחוש, הטווח הטוב ביותר הוא 5-10 שניות ({mid:.0f}%), ומי שמתעכב מעל 80 שניות מצליח רק ב-{slow:.0f}%. "
    "מכאן שזמן תגובה מנבא הצלחה, ובמשחק אפשר להציע רמז לשחקן שמתעכב ולא לסמוך על תשובה חפוזה."
)

st.caption("שאלת הפרויקט: איזה סיכוי יש לשחקן לענות נכון על שאלה (y = correct), ומה משפיע על זה?")

if view.empty:
    st.warning("אין שורות שמתאימות לסינון. שנו את הבחירה בצד.")
    st.stop()

# ---------- Metrics ----------
accuracy = view["correct"].mean() * 100
# The baseline is always computed on ALL the data, so it stays fixed while the filters change the KPI.
majority = max(df["correct"].mean(), 1 - df["correct"].mean()) * 100
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("אחוז תשובות נכונות (KPI)", f"{accuracy:.1f}%")
c2.metric("baseline: תמיד לנחש את הקטגוריה הנפוצה", f"{majority:.1f}%")
c3.metric("מספר ניסיונות", f"{len(view):,}")
c4.metric("מספר נושאים", f"{view['skill_name'].nunique():,}")
c5.metric("זמן תגובה חציוני", f"{view['response_sec'].median():.1f} שנ'")
st.caption("ה-baseline הוא הדיוק שמודל חיזוי יקבל אם יגיד תמיד 'נכון' (על כל הנתונים). מודל ה-M3 צריך לנצח אותו.")

# ---------- Charts ----------
left, right = st.columns(2)

with left:
    st.subheader("אחוז הצלחה לפי זמן תגובה")
    chart_time = (
        view.groupby("time_group", observed=True)["correct"].mean().mul(100).reset_index(name="success")
    )
    st.altair_chart(
        alt.Chart(chart_time).mark_line(point=True).encode(
            x=alt.X("time_group:N", sort=TIME_LABELS, title="זמן תגובה (שניות)"),
            y=alt.Y("success:Q", title="% תשובות נכונות", scale=alt.Scale(domain=[0, 100])),
            tooltip=["time_group", alt.Tooltip("success:Q", format=".1f")],
        ),
        width="stretch",
    )

with right:
    st.subheader("הנושאים הקשים והקלים ביותר")
    per_skill = view.groupby("skill_name")["correct"].agg(["mean", "size"])
    per_skill = per_skill[per_skill["size"] >= 100]
    if per_skill.empty:
        st.write("אין מספיק שורות לכל נושא (מינימום 100).")
    else:
        extremes = pd.concat([per_skill.nsmallest(7, "mean"), per_skill.nlargest(7, "mean")]).reset_index()
        extremes["success"] = extremes["mean"] * 100
        st.altair_chart(
            alt.Chart(extremes).mark_bar().encode(
                x=alt.X("success:Q", title="% תשובות נכונות", scale=alt.Scale(domain=[0, 100])),
                y=alt.Y("skill_name:N", sort="x", title=None),
                tooltip=["skill_name", alt.Tooltip("success:Q", format=".1f"), "size"],
            ),
            width="stretch",
        )

left2, right2 = st.columns(2)

with left2:
    st.subheader("התפלגות זמן התגובה: נכון מול שגוי")
    hist = view[view["response_sec"] <= 120].copy()
    hist["result"] = hist["correct"].map({1: "נכון", 0: "שגוי"})
    st.altair_chart(
        alt.Chart(hist).mark_bar(opacity=0.6).encode(
            x=alt.X("response_sec:Q", bin=alt.Bin(maxbins=30), title="זמן תגובה (שניות)"),
            y=alt.Y("count():Q", stack=None, title="מספר ניסיונות"),
            color=alt.Color("result:N", title=None),
        ),
        width="stretch",
    )

with right2:
    st.subheader("האם חזרה על הנושא משפרת? (לפי מספר הנסיונות הקודמים)")
    if "opportunity" in view and view["opportunity"].notna().any():
        opp = view.dropna(subset=["opportunity"]).copy()
        opp["opportunity"] = opp["opportunity"].clip(upper=15)
        opp_chart = opp.groupby("opportunity")["correct"].mean().mul(100).reset_index(name="success")
        st.altair_chart(
            alt.Chart(opp_chart).mark_area(opacity=0.5, line=True).encode(
                x=alt.X("opportunity:Q", title="הניסיון ה-N באותו נושא (15 = 15 ומעלה)"),
                y=alt.Y("success:Q", title="% תשובות נכונות", scale=alt.Scale(domain=[0, 100])),
            ),
            width="stretch",
        )
    else:
        st.write("אין נתוני חזרה בשורות שנבחרו.")

# ---------- Table ----------
st.subheader("דוגמה מהנתונים הנקיים")
st.dataframe(view.drop(columns=["time_group"]).sample(min(20, len(view)), random_state=1), width="stretch")
