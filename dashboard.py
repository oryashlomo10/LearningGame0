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
SOURCE_URL = "https://sites.google.com/site/assistmentsdata/home/2009-2010-assistment-data/skill-builder-data-2009-2010"
GAME_SOURCE = "Conquest (המשחק)"

# Response-time groups (seconds) used by the chart and the insight sentence.
TIME_BINS = [0, 5, 10, 20, 40, 80, 600]
TIME_LABELS = ["עד 5", "5-10", "10-20", "20-40", "40-80", "מעל 80"]

# Same palette as the game (styles.py), so the dashboard looks like part of it.
BG, PANEL, BORDER, TEXT, MUTED = "#090d1a", "#10172e", "#27315f", "#e9edff", "#8f9bc7"
GOLD, GOOD, BAD, TEAL = "#f5b942", "#34d399", "#f0616d", "#5eead4"

st.set_page_config(page_title="Conquest · נתונים", page_icon="📊", layout="wide")
st.markdown(
    f"""<style>
.stApp {{ background: {BG}; color: {TEXT}; }}
[data-testid="stSidebar"] {{ background: {PANEL}; border-left: 1px solid {BORDER}; }}
.block-container {{ direction: rtl; text-align: right; padding-top: 2rem; max-width: 1250px; }}
h1, h2, h3, p, label, span, div {{ color: {TEXT}; }}
[data-testid="stCaptionContainer"] p, .muted {{ color: {MUTED} !important; }}
[data-testid="stMetric"] {{
  direction: rtl; text-align: right; background: {PANEL}; border: 1px solid {BORDER};
  border-radius: 14px; padding: 14px 16px; box-shadow: 0 6px 20px rgba(0,0,0,.35);
}}
[data-testid="stMetricValue"] {{ color: {GOLD}; font-weight: 800; }}
[data-testid="stMetricLabel"] p {{ color: {MUTED}; font-size: 0.85rem; }}
.hero {{ font-size: 2.3rem; font-weight: 900; margin: 0;
  background: linear-gradient(180deg, #ffe08a, {GOLD}); -webkit-background-clip: text;
  -webkit-text-fill-color: transparent; }}
.card {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 14px; padding: 16px 20px; margin: 10px 0; }}
.card.gold {{ border-right: 5px solid {GOLD}; }}
.card.teal {{ border-right: 5px solid {TEAL}; }}
.card b {{ color: {GOLD}; }}
.card a {{ color: {TEAL}; }}
.tag {{ display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: .8rem; font-weight: 700;
  background: rgba(94,234,212,.15); color: {TEAL}; margin-left: 6px; }}
.tag.game {{ background: rgba(245,185,66,.15); color: {GOLD}; }}
h3 {{ color: {TEXT}; font-weight: 800; }}
</style>""",
    unsafe_allow_html=True,
)


def style(chart):
    """Gives every chart the dashboard look (transparent background, light text, soft grid)."""
    return (
        chart.configure(background="transparent")
        .configure_view(stroke=None)
        .configure_axis(labelColor=MUTED, titleColor=MUTED, gridColor=BORDER, domainColor=BORDER, tickColor=BORDER)
        .configure_legend(labelColor=TEXT, titleColor=MUTED)
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
                "source": GAME_SOURCE,
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
game_rows = int((df["source"] == GAME_SOURCE).sum())

# ---------- Sidebar filters ----------
st.sidebar.header("סינון")
sources = st.sidebar.multiselect("מקור הנתונים", sorted(df["source"].unique()), default=sorted(df["source"].unique()))
types = st.sidebar.multiselect("סוג שאלה", sorted(df["answer_type"].unique()), default=sorted(df["answer_type"].unique()))
skills = st.sidebar.multiselect("נושא (ברירת מחדל: כולם)", sorted(df["skill_name"].unique()), default=[])
max_time = st.sidebar.slider("זמן תגובה מקסימלי (שניות)", 5, 600, 600)

view = df[df["source"].isin(sources) & df["answer_type"].isin(types) & (df["response_sec"] <= max_time)]
if skills:
    view = view[view["skill_name"].isin(skills)]

# ---------- Header ----------
st.markdown('<p class="hero">📊 Conquest · מה הנתונים מספרים</p>', unsafe_allow_html=True)
st.caption("שאלת הפרויקט: מה הסיכוי ששחקן יענה נכון על שאלה (y = correct), ומה משפיע על זה?")

st.markdown(
    f"""<div class="card teal">
<span class="tag">מקור הנתונים</span> הנתונים שמוצגים כאן הובאו מ-
<a href="{SOURCE_URL}" target="_blank">ASSISTments 2009-2010</a>:
ניסיונות מענה של תלמידי בית ספר בתרגול מתמטיקה (אחרי ניקוי, {int((df['source'] == 'ASSISTments').sum()):,} שורות).<br>
<b>זה הבסיס ההתחלתי.</b> במהלך המשחק אנחנו אוספים נתונים משלנו: כל תשובה של שחקן נשמרת (נושא, זמן תגובה, נכון או לא),
והם יחליפו בהדרגה את הנתונים החיצוניים. מהם נלמד מה רמת הידע של כל שחקן בכל נושא, ונתאים לו שאלות בקושי המתאים.
<br><span class="tag game">נתוני המשחק עד כה</span> {game_rows:,} שורות.
</div>""",
    unsafe_allow_html=True,
)

# ---------- Insight (computed from ALL the data, not from the filter) ----------
by_time = df.groupby("time_group", observed=True)["correct"].mean() * 100
fast, mid, slow = by_time[TIME_LABELS[0]], by_time[TIME_LABELS[1]], by_time[TIME_LABELS[-1]]
st.markdown(
    f"""<div class="card gold"><b>גילינו ש...</b> הקשר בין זמן התגובה להצלחה אינו ישר: תשובה מהירה מאוד (עד 5 שניות)
נכונה רק ב-{fast:.0f}% מהמקרים, כמעט כמו ניחוש, הטווח הטוב ביותר הוא 5-10 שניות ({mid:.0f}%),
ומי שמתעכב מעל 80 שניות מצליח רק ב-{slow:.0f}%. מכאן שזמן תגובה מנבא הצלחה, ובמשחק אפשר להציע רמז
לשחקן שמתעכב ולא לסמוך על תשובה חפוזה.</div>""",
    unsafe_allow_html=True,
)

if view.empty:
    st.warning("אין שורות שמתאימות לסינון. שנו את הבחירה בצד.")
    st.stop()

# ---------- Metrics ----------
accuracy = view["correct"].mean() * 100
# The baseline is always computed on ALL the data, so it stays fixed while the filters change the KPI.
majority = max(df["correct"].mean(), 1 - df["correct"].mean()) * 100
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("אחוז תשובות נכונות (KPI)", f"{accuracy:.1f}%", f"{accuracy - majority:+.1f} מול ה-baseline")
c2.metric("baseline: תמיד לחזות 'נכון'", f"{majority:.1f}%")
c3.metric("מספר ניסיונות", f"{len(view):,}")
c4.metric("מספר נושאים", f"{view['skill_name'].nunique():,}")
c5.metric("זמן תגובה חציוני", f"{view['response_sec'].median():.1f} שנ'")
st.caption("ה-baseline הוא הדיוק שמודל חיזוי יקבל אם יגיד תמיד 'נכון' (על כל הנתונים). מודל ה-M3 צריך לנצח אותו.")

# ---------- Charts ----------
left, right = st.columns(2)

with left:
    st.subheader("אחוז הצלחה לפי זמן תגובה")
    chart_time = view.groupby("time_group", observed=True)["correct"].mean().mul(100).reset_index(name="success")
    line = alt.Chart(chart_time).mark_line(point=alt.OverlayMarkDef(size=90, filled=True), color=GOLD, strokeWidth=3).encode(
        x=alt.X("time_group:N", sort=TIME_LABELS, title="זמן תגובה (שניות)", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("success:Q", title="% תשובות נכונות", scale=alt.Scale(domain=[0, 100])),
        tooltip=[alt.Tooltip("time_group", title="זמן"), alt.Tooltip("success:Q", title="% נכון", format=".1f")],
    )
    base = alt.Chart(pd.DataFrame({"y": [majority]})).mark_rule(color=MUTED, strokeDash=[6, 4]).encode(y="y:Q")
    st.altair_chart(style(base + line), width="stretch")
    st.caption("הקו המקווקו הוא ה-baseline.")

with right:
    st.subheader("הנושאים הקשים והקלים ביותר")
    per_skill = view.groupby("skill_name")["correct"].agg(["mean", "size"])
    per_skill = per_skill[per_skill["size"] >= 100]
    if per_skill.empty:
        st.write("אין מספיק שורות לכל נושא (מינימום 100).")
    else:
        extremes = pd.concat([per_skill.nsmallest(7, "mean"), per_skill.nlargest(7, "mean")]).reset_index()
        extremes["success"] = extremes["mean"] * 100
        extremes["level"] = extremes["success"].apply(lambda s: "מעל ה-baseline" if s >= majority else "מתחת ל-baseline")
        bars = alt.Chart(extremes).mark_bar(cornerRadiusEnd=4).encode(
            x=alt.X("success:Q", title="% תשובות נכונות", scale=alt.Scale(domain=[0, 100])),
            y=alt.Y("skill_name:N", sort="x", title=None, axis=alt.Axis(labelLimit=260)),
            color=alt.Color("level:N", title=None, scale=alt.Scale(domain=["מעל ה-baseline", "מתחת ל-baseline"], range=[TEAL, BAD])),
            tooltip=[alt.Tooltip("skill_name", title="נושא"), alt.Tooltip("success:Q", title="% נכון", format=".1f"),
                     alt.Tooltip("size:Q", title="ניסיונות")],
        )
        st.altair_chart(style(bars), width="stretch")

left2, right2 = st.columns(2)

with left2:
    st.subheader("התפלגות זמן התגובה: נכון מול שגוי")
    hist = view[view["response_sec"] <= 120].copy()
    hist["result"] = hist["correct"].map({1: "נכון", 0: "שגוי"})
    hist_chart = alt.Chart(hist).mark_bar(opacity=0.65).encode(
        x=alt.X("response_sec:Q", bin=alt.Bin(maxbins=30), title="זמן תגובה (שניות)"),
        y=alt.Y("count():Q", stack=None, title="מספר ניסיונות"),
        color=alt.Color("result:N", title=None, scale=alt.Scale(domain=["נכון", "שגוי"], range=[GOOD, BAD])),
    )
    st.altair_chart(style(hist_chart), width="stretch")

with right2:
    st.subheader("האם חזרה על הנושא משפרת?")
    if "opportunity" in view and view["opportunity"].notna().any():
        opp = view.dropna(subset=["opportunity"]).copy()
        opp["opportunity"] = opp["opportunity"].clip(upper=15)
        opp_chart = opp.groupby("opportunity")["correct"].mean().mul(100).reset_index(name="success")
        area = alt.Chart(opp_chart).mark_area(
            line={"color": TEAL, "strokeWidth": 3},
            color=alt.Gradient(gradient="linear", stops=[alt.GradientStop(color="rgba(94,234,212,.45)", offset=0),
                                                         alt.GradientStop(color="rgba(94,234,212,0)", offset=1)],
                               x1=1, x2=1, y1=1, y2=0),
        ).encode(
            x=alt.X("opportunity:Q", title="הניסיון ה-N של השחקן באותו נושא (15 = 15 ומעלה)"),
            y=alt.Y("success:Q", title="% תשובות נכונות", scale=alt.Scale(domain=[0, 100])),
            tooltip=[alt.Tooltip("opportunity:Q", title="ניסיון"), alt.Tooltip("success:Q", title="% נכון", format=".1f")],
        )
        st.altair_chart(style(area), width="stretch")
    else:
        st.write("אין נתוני חזרה בשורות שנבחרו.")

# ---------- Table ----------
st.subheader("דוגמה מהנתונים הנקיים")
table = view.drop(columns=["time_group"]).sample(min(20, len(view)), random_state=1)
st.dataframe(table, width="stretch", hide_index=True)
