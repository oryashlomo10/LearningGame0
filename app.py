"""Conquest - Streamlit UI.

Screens (st.session_state.view): menu -> map -> question -> result -> map ... -> end
All rules live in game_logic.py, all questions come from question_bank.py,
all CSS is in styles.py. This file only draws screens and wires up buttons.
"""

import html
import logging
import re
import time
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

import attempts
import game_logic as gl
from game_logic import PLAYER, PLAYERS
from map_geometry import MAP
from qgen.chunking import DEFAULT_MAX_WORDS, DEFAULT_OVERLAP_WORDS, chunk_document
from qgen.extract import ExtractionError, extract_document
from question_bank import load_question_bank
from styles import build_css

st.set_page_config(page_title="Conquest", page_icon="🏰", layout="wide")

DIFFICULTY_ORDER = ["easy", "medium", "hard"]

# The interactive world map is a small custom component (plain HTML/JS, no build step).
world_map = components.declare_component(
    "conquest_world_map", path=str(Path(__file__).parent / "components" / "world_map"))


# ======================================================================
# Small helpers
# ======================================================================
def esc(text):
    """Escape text before putting it inside HTML."""
    return html.escape(str(text))


def rich(text):
    """Escape text and turn `code` spans into <code> tags."""
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", esc(text))


def pips(difficulty):
    """Difficulty as 1-3 diamonds."""
    return "◆" * (DIFFICULTY_ORDER.index(difficulty) + 1)


def owner_name(owner):
    if owner is None:
        return "פנוי"
    return "את/ה" if owner == PLAYER else PLAYERS[owner]["name"]


def owner_color(owner):
    return PLAYERS[owner]["color"] if owner else "#3a4570"


@st.cache_data
def get_question_bank():
    return load_question_bank()


# ======================================================================
# Button callbacks (they run before the page reruns, so state is fresh)
# ======================================================================
def start_game():
    bank = get_question_bank()
    st.session_state.game = gl.new_game(bank["questions"])
    st.session_state.course = bank["course"]
    st.session_state.view = "map"
    # Anonymous ids for data collection: a new session_id for every game,
    # one player_id for the whole browser session (random, not personal).
    st.session_state.session_id = attempts.new_anonymous_id()
    st.session_state.setdefault("player_id", attempts.new_anonymous_id())


def go_menu():
    st.session_state.view = "menu"


def go_materials():
    st.session_state.view = "materials"


def select_territory(territory_id):
    gl.select_territory(st.session_state.game, territory_id)


def attack_selected():
    game = st.session_state.game
    gl.start_attack(game, game["selected"])
    st.session_state.view = "question"


def handle_map_event():
    """Called by Streamlit when the user clicks the map (before the rerun)."""
    event = st.session_state.get("world_map")
    game = st.session_state.game
    if not event or game is None or game["current"] is not None:
        return
    gl.select_territory(game, event["id"])
    if event["type"] == "attack" and gl.can_attack(game, event["id"])[0]:
        attack_selected()


def response_time_ms(game):
    """Milliseconds since this question was first shown (None if unknown)."""
    shown = st.session_state.get("question_shown")
    if (shown and shown["session"] == st.session_state.get("session_id")
            and shown["attack"] == game["attacks"]):
        return int((time.monotonic() - shown["t"]) * 1000)
    return None


def log_attempt(game, question, chosen, correct, elapsed_ms):
    """Save one real answer for the future ML model. Never breaks the game."""
    try:
        status, _ = attempts.save_attempt(
            st.session_state.session_id, st.session_state.player_id, game["attacks"],
            question, chosen, correct, elapsed_ms)
    except Exception:                       # e.g. ids missing from the session
        status = "error"
    if status == "error":
        st.session_state.attempt_save_error = True


def submit_answer(answer_key):
    answer = st.session_state.get(answer_key)
    if answer is None:            # the button is disabled in this case, just be safe
        return
    game = st.session_state.game
    current = game["current"]
    if current is None:           # already answered (e.g. a double click): nothing to do or save
        return
    question, elapsed_ms = current["question"], response_time_ms(game)
    result = gl.submit_answer(game, answer)
    st.session_state.view = "result"
    log_attempt(game, question, answer, result["correct"], elapsed_ms)


def continue_after_result():
    game = st.session_state.game
    if game["current"] is not None:          # a demo opponent attacks you: defend
        st.session_state.view = "question"
    else:
        st.session_state.view = "end" if game["over"] else "map"


# ======================================================================
# Shared HTML pieces
# ======================================================================
def render_topbar(game):
    if game["over"]:
        status = '<span class="chip">המשחק הסתיים</span>'
    else:
        used = game["attacks"]
        status = f'<span class="chip live">● משחק פעיל · תקיפה {used} מתוך {gl.MAX_ACTIONS}</span>'
    st.markdown(
        '<div class="topbar">'
        '<div class="brand"><span class="brand-mark">◆</span><span class="brand-name">CONQUEST</span></div>'
        f'<div class="course">קורס: <b>{esc(st.session_state.course)}</b></div>'
        '<div class="topbar-end">' + status +
        '<div class="profile"><div class="avatar">א</div>'
        '<div><div class="pname">את/ה</div><div class="prole">שחקן · מצב הדגמה</div></div></div>'
        "</div></div>",
        unsafe_allow_html=True,
    )


def stat_tile(label, value, small="", style=""):
    small_html = f"<small> {small}</small>" if small else ""
    return (f'<div class="stat {style}"><div class="stat-label">{label}</div>'
            f'<div class="stat-value">{value}{small_html}</div></div>')


def render_stats(game):
    total = len(game["territories"])
    mine = gl.territory_count(game, PLAYER)
    tiles = (
        stat_tile("שטחים בשליטתך", mine, f"/ {total}", "teal")
        + stat_tile("ניקוד", gl.score(game, PLAYER), "נק׳", "gold")
        + stat_tile("תקיפות שנותרו", game["actions_left"], f"/ {gl.MAX_ACTIONS}")
        + stat_tile("דירוג", f"#{gl.player_rank(game)}", f"מתוך {len(PLAYERS)}")
    )
    used_pct = 100 * game["attacks"] / gl.MAX_ACTIONS
    goal_pct = min(100, 100 * mine / gl.MAJORITY)
    st.markdown(
        f'<div class="stats">{tiles}</div>'
        '<div class="progress-row">'
        f'<div><div class="progress-label"><span>התקדמות המשחק</span><span>{game["attacks"]}/{gl.MAX_ACTIONS} תקיפות</span></div>'
        f'<div class="bar gold"><span style="width:{used_pct:.0f}%"></span></div></div>'
        f'<div><div class="progress-label"><span>המטרה: שליטה ב-{gl.MAJORITY} שטחים</span><span>{mine}/{gl.MAJORITY}</span></div>'
        f'<div class="bar teal"><span style="width:{goal_pct:.0f}%"></span></div></div>'
        "</div>",
        unsafe_allow_html=True,
    )


def leaderboard_html(game):
    rows = ""
    for row in gl.ranking(game):
        demo = '<span class="lb-demo">הדגמה</span>' if row["demo"] else ""
        me = " me" if row["key"] == PLAYER else ""
        rows += (
            f'<div class="lb-row{me}"><span class="lb-rank">{row["rank"]}</span>'
            f'<span class="owner-dot" style="background:{row["color"]}"></span>'
            f'<span class="lb-name">{esc(row["name"])}{demo}</span>'
            f'<span class="lb-count">{row["count"]} שטחים</span>'
            f'<span class="lb-score">{row["score"]}</span></div>'
        )
    return rows


def render_leaderboard(game):
    st.markdown(
        '<div class="panel"><div class="panel-title">טבלת דירוג</div>'
        + leaderboard_html(game)
        + '<div class="lb-note">היריבים הם דמויות הדגמה מדומות, לא משתמשים אמיתיים.</div></div>',
        unsafe_allow_html=True,
    )


# ======================================================================
# Screen: main menu
# ======================================================================
STEPS = [
    ("📚", "לומדים", "מעלים את חומרי הקורס, והמערכת הופכת אותם לאתגרים."),
    ("❓", "עונים על שאלות", "שאלות מהחומר שלכם, ברמות קושי שונות."),
    ("🚩", "כובשים שטחים", "כל תשובה נכונה מרחיבה את השליטה שלכם על המפה."),
]


def render_menu():
    cards = ""
    for i, (icon, name, desc) in enumerate(STEPS, start=1):
        cards += (
            f'<div class="step"><div class="step-num">0{i}</div><div class="step-icon">{icon}</div>'
            f'<div class="step-name">{name}</div><div class="step-desc">{desc}</div></div>'
        )
    st.markdown(
        '<div class="hero"><div class="logo-icon">🏰</div><h1 class="title">CONQUEST</h1>'
        '<div class="tagline">Learn. Compete. <b>Conquer.</b></div></div>'
        '<div class="desc">הופכים את הלימודים לקרב אסטרטגי. בוחרים שטח על המפה, עונים על שאלה מחומר הקורס, '
        "וכובשים אותו. ככל שהשטח קשה יותר – הפרס גדול יותר. הידע שלכם הוא הנשק.</div>",
        unsafe_allow_html=True,
    )
    with st.container(key="start_btn"):
        st.button("התחלת משחק", type="primary", key="start_game", on_click=start_game)
    with st.container(key="materials_btn"):
        st.button("העלאת חומר לימוד", key="open_materials", on_click=go_materials)
    st.markdown(
        '<div class="steps-title">איך זה עובד</div>'
        f'<div class="steps">{cards}</div>'
        f'<div class="footer">מצב הדגמה: {gl.MAX_ACTIONS} תקיפות · תוקפים רק שטח שגובל בשטח שלך · '
        f"כל אזור הוא נושא בקורס (אזור שלם = +{gl.REGION_BONUS}) · מגינים על שטחים בשאלת הגנה · "
        f"ניצחון בשליטה ב-{gl.MAJORITY} שטחים או בסיום במקום הראשון · יריבים מדומים · שאלות לדוגמה</div>",
        unsafe_allow_html=True,
    )


# ======================================================================
# Screen: map
# ======================================================================
def map_state(game):
    """Everything that changes during the game, as plain JSON for the map."""
    selected = game["selected"]
    allowed, reason = gl.can_attack(game, selected)
    attackable = set(gl.attackable_ids(game))
    return {
        "territories": [
            {
                "id": t["id"],
                "name": t["name"],
                "owner": t["owner"],
                "ownerName": owner_name(t["owner"]),
                "points": t["points"],
                "pips": pips(t["difficulty"]),
                "diffLabel": gl.DIFFICULTY_LABELS[t["difficulty"]],
                "topic": t["topic"],
                "attackable": t["id"] in attackable,
            }
            for t in game["territories"]
        ],
        "selected": selected,
        "canAttack": allowed,
        "colors": {key: info["color"] for key, info in PLAYERS.items()},
    }


def render_board(game):
    """The world map. Clicks come back through handle_map_event()."""
    with st.container(key="map_board"):
        world_map(geo=MAP, state=map_state(game), key="world_map",
                  on_change=handle_map_event, default=None)
    st.markdown(
        '<div class="legend">'
        '<span><span class="dot" style="background:#2dd4bf"></span>השטחים שלך</span>'
        + "".join(
            f'<span><span class="dot" style="background:{PLAYERS[k]["color"]}"></span>{PLAYERS[k]["name"]} (הדגמה)</span>'
            for k in gl.OPPONENTS)
        + '<span><span class="dot stone"></span>שטח פנוי</span>'
        '<span><span class="dot dashed"></span>אפשר לתקוף (גובל בשטח שלך)</span>'
        "<span>◆ קל · ◆◆ בינוני · ◆◆◆ קשה</span></div>",
        unsafe_allow_html=True,
    )


def render_selection_panel(game):
    selected = game["selected"]
    if selected is None:
        st.markdown(
            '<div class="panel"><div class="panel-title">השטח הנבחר</div>'
            '<div class="empty-hint">לחצו על שטח במפה כדי לראות את פרטיו ולתקוף אותו. '
            "אפשר לתקוף רק שטח שגובל בשטח שלך (מסומן בקו מקווקו). "
            "שטחים קשים מעניקים יותר נקודות – אבל הם גם מסוכנים יותר.</div></div>",
            unsafe_allow_html=True,
        )
    else:
        t = gl.get_territory(game, selected)
        color = owner_color(t["owner"])
        st.markdown(
            '<div class="panel"><div class="panel-title">השטח הנבחר</div>'
            f'<div class="sel-name">{esc(t["name"])}</div>'
            f'<div class="sel-row"><span>נושא (אזור)</span><span>{esc(t["topic"])}</span></div>'
            f'<div class="sel-row"><span>בעלים</span><span><span class="owner-dot" style="background:{color}"></span>{esc(owner_name(t["owner"]))}</span></div>'
            f'<div class="sel-row"><span>קושי</span><span>{pips(t["difficulty"])} {gl.DIFFICULTY_LABELS[t["difficulty"]]}</span></div>'
            f'<div class="sel-row"><span>פרס בכיבוש</span><span style="color:var(--gold);font-weight:800">{t["points"]} נק׳</span></div>'
            f'<div class="sel-row"><span>גובל ב</span><span class="nbrs">{esc(", ".join(n["name"] for n in gl.neighbors_of(game, selected)))}</span></div></div>',
            unsafe_allow_html=True,
        )
    allowed, reason = gl.can_attack(game, selected)
    label = f"תקיפת {gl.get_territory(game, selected)['name']}" if allowed else "תקיפה"
    st.button(label, type="primary", key="attack_btn", disabled=not allowed,
              on_click=attack_selected, use_container_width=True)
    if not allowed:
        st.markdown(f'<div class="reason">{esc(reason)}</div>', unsafe_allow_html=True)
    st.markdown("<div style='height:0.9rem'></div>", unsafe_allow_html=True)


def render_regions(game):
    """The 8 knowledge regions: a full region gives its holder a bonus."""
    rows = ""
    for region in gl.region_info(game):
        dots = "".join(
            f'<span class="owner-dot" style="background:{owner_color(t["owner"])}" title="{esc(t["name"])}"></span>'
            for t in region["territories"])
        holder = region["holder"]
        if holder:
            status = f'<span class="rg-bonus" style="color:{owner_color(holder)}">{esc(owner_name(holder))} +{gl.REGION_BONUS}</span>'
        else:
            status = '<span class="rg-open">פתוח</span>'
        me = " me" if holder == PLAYER else ""
        rows += f'<div class="rg-row{me}"><span class="rg-dots">{dots}</span><span class="rg-name">{esc(region["topic"])}</span>{status}</div>'
    st.markdown(
        '<div class="panel"><div class="panel-title">אזורי ידע</div>'
        f'<div class="lb-note" style="margin:0 0 .4rem">כל אזור הוא נושא בקורס. שליטה בשני השטחים של אזור = +{gl.REGION_BONUS} נק׳.</div>'
        + rows + "</div>",
        unsafe_allow_html=True,
    )


def render_log(game):
    if not game["log"]:
        return
    items = "".join(f'<div class="log-item {e["kind"]}">{esc(e["text"])}</div>' for e in game["log"])
    st.markdown(f'<div class="panel"><div class="panel-title">יומן קרב</div>{items}</div>',
                unsafe_allow_html=True)


def render_map():
    game = st.session_state.game
    render_topbar(game)
    render_stats(game)
    map_col, side_col = st.columns([3.6, 1.25], gap="large")
    with map_col:
        render_board(game)
    with side_col:
        render_selection_panel(game)
        render_leaderboard(game)
        render_regions(game)
        render_log(game)


# ======================================================================
# Screen: question challenge
# ======================================================================
def render_question():
    game = st.session_state.game
    current = game["current"]
    if current is None:            # nothing to answer (e.g. page reload) - go back
        st.session_state.view = "map"
        st.rerun()
    question = current["question"]
    territory = gl.get_territory(game, current["territory_id"])
    defending = current["kind"] == "defend"

    # Remember when this question was FIRST shown (reruns while the player picks
    # an option must not reset it). Used to measure the response time.
    shown = st.session_state.get("question_shown")
    session_id = st.session_state.get("session_id")
    if not shown or shown["session"] != session_id or shown["attack"] != game["attacks"]:
        st.session_state.question_shown = {
            "session": session_id, "attack": game["attacks"], "t": time.monotonic()}

    render_topbar(game)
    _, center, _ = st.columns([1, 4, 1])
    with center:
        with st.container(key="question_card"):
            if defending:
                rival = PLAYERS[current["opponent"]]["name"]
                first_chip = f'<span class="chip red">🛡️ הגנה מפני {esc(rival)} (הדגמה)</span>'
                place = f"השטח שלך: {esc(territory['name'])}"
            else:
                first_chip = f'<span class="chip gold">אתגר {game["attacks"]} מתוך {gl.MAX_ACTIONS}</span>'
                place = f"יעד: {esc(territory['name'])}"
            st.markdown(
                '<div class="q-meta">'
                + first_chip
                + f'<span class="chip">{place}</span>'
                f'<span class="chip">{esc(question["topic"])}</span>'
                f'<span class="chip">{pips(territory["difficulty"])} {gl.DIFFICULTY_LABELS[territory["difficulty"]]} · {territory["points"]} נק׳</span>'
                "</div>"
                f'<div class="q-text">{rich(question["question"])}</div>',
                unsafe_allow_html=True,
            )
            answer_key = f"answer_{game['questions_asked']}"   # new key for every question
            choice = st.radio("בחרו תשובה", current["options"], index=None,
                              key=answer_key, label_visibility="collapsed")
            st.button("שליחת תשובה", type="primary", key="submit_btn",
                      disabled=choice is None, on_click=submit_answer,
                      args=(answer_key,), use_container_width=True)
            if choice is None:
                hint = "בחרו תשובה כדי לשלוח."
            elif defending:
                hint = "תשובה נכונה שומרת על השטח. ההגנה לא עולה תקיפה."
            else:
                hint = "ההתקפה כבר החלה – אין נסיגה."
            st.markdown(f'<div class="q-hint">{hint}</div>', unsafe_allow_html=True)


# ======================================================================
# Screen: result of an attack
# ======================================================================
def options_review_html(result):
    out = ""
    for option in result["options"]:
        if option == result["correct_answer"]:
            css, mark, tag = "right", "✓", "התשובה הנכונה"
        elif option == result["chosen"]:
            css, mark, tag = "wrong", "✗", "התשובה שלך"
        else:
            css, mark, tag = "", "", ""
        if option == result["correct_answer"] and option == result["chosen"]:
            tag = "התשובה שלך"
        out += (f'<div class="opt {css}"><span class="opt-mark">{mark}</span>'
                f'<span>{rich(option)}</span><span class="opt-tag">{tag}</span></div>')
    return out


def render_result():
    game = st.session_state.game
    result = game["last_result"]
    render_topbar(game)
    if st.session_state.pop("attempt_save_error", False):
        st.warning("לא הצלחנו לשמור את נתוני המענה הזה. המשחק ממשיך כרגיל.")
    _, center, _ = st.columns([1, 4, 1])
    with center:
        name = esc(result["territory_name"])
        if result["kind"] == "defend":
            rival_name = esc(PLAYERS[result["opponent"]]["name"])
            if result["correct"]:
                banner = ('<div class="banner win"><div class="banner-title">תשובה נכונה – הגנת על השטח!</div>'
                          f'<div class="banner-sub">{name} נשאר בשליטתך · {rival_name} (הדגמה) נהדף/ה</div></div>')
            else:
                banner = ('<div class="banner loss"><div class="banner-title">התשובה שגויה – השטח נפל</div>'
                          f'<div class="banner-sub">{name} עבר לידי {rival_name} (הדגמה)</div></div>')
        elif result["correct"]:
            banner = ('<div class="banner win"><div class="banner-title">תשובה נכונה – השטח נכבש!</div>'
                      f'<div class="banner-sub">{name} עבר לשליטתך · +{result["points"]} נק׳</div></div>')
        else:
            previous = result["previous_owner"]
            stays = "נשאר פנוי" if previous is None else f"נשאר בידי {owner_name(previous)}"
            banner = ('<div class="banner loss"><div class="banner-title">התשובה שגויה – ההתקפה נכשלה</div>'
                      f'<div class="banner-sub">{name} {esc(stays)}</div></div>')
        rival = ""
        for event in result["rival_events"]:
            who = f'<b>{esc(PLAYERS[event["opponent"]]["name"])}</b> (יריב הדגמה)'
            if event["kind"] == "attack_on_player":
                rival += (f'<div class="rival alert">⚔️ {who} תוקף/ת את השטח שלך <b>{esc(event["territory_name"])}</b>! '
                          "ענו נכון על שאלת הגנה כדי לשמור עליו.</div>")
            else:
                rival += f'<div class="rival">בינתיים במפה: {who} כבש/ה את <b>{esc(event["territory_name"])}</b>.</div>'
        st.markdown(
            banner
            + f'<div class="q-text" style="font-size:1.25rem">{rich(result["question"])}</div>'
            + options_review_html(result)
            + f'<div class="explain"><b>הסבר:</b> {rich(result["explanation"])}</div>'
            + rival,
            unsafe_allow_html=True,
        )
        if game["current"] is not None:
            label = "🛡️ להגנה על השטח"
        else:
            label = "לסיכום המשחק" if game["over"] else "חזרה למפה"
        st.button(label, type="primary", key="continue_btn",
                  on_click=continue_after_result, use_container_width=True)


# ======================================================================
# Screen: end of game
# ======================================================================
def end_reason_text(game):
    reason = game["end_reason"]
    if reason == "majority":
        return f"השתלטת על {gl.MAJORITY} שטחים – רוב המפה!"
    if reason == "rival_majority":
        return "יריב הדגמה השתלט על רוב המפה."
    if game["outcome"] == "victory":
        return "נגמרו התקיפות, ואת/ה במקום הראשון בניקוד."
    return f"נגמרו התקיפות, ודורגת במקום #{gl.player_rank(game)}."


def render_end():
    game = st.session_state.game
    victory = game["outcome"] == "victory"
    render_topbar(game)
    title = "ניצחון! 👑" if victory else "הפסד"
    sub = end_reason_text(game)
    st.markdown(
        f'<div class="end-hero {game["outcome"]}"><div class="end-title">{title}</div>'
        f'<div class="end-sub">{esc(sub)}</div></div>',
        unsafe_allow_html=True,
    )
    tiles = (
        stat_tile("שטחים בשליטתך", gl.territory_count(game, PLAYER), f"/ {len(game['territories'])}", "teal")
        + stat_tile("ניקוד סופי", gl.score(game, PLAYER), "נק׳", "gold")
        + stat_tile("דירוג", f"#{gl.player_rank(game)}", f"מתוך {len(PLAYERS)}")
        + stat_tile("כיבושים מוצלחים", game["conquests"], f"/ {game['attacks']} תקיפות")
        + stat_tile("הגנות מוצלחות", game["defenses_won"], f"/ {game['defenses']}")
        + stat_tile("אזורים שלמים", gl.regions_held(game, PLAYER), f"/ {len(gl.REGIONS)}")
    )
    st.markdown(f'<div class="stats six">{tiles}</div>', unsafe_allow_html=True)
    _, center, _ = st.columns([1, 3, 1])
    with center:
        render_leaderboard(game)
        st.button("משחק חוזר", type="primary", key="play_again",
                  on_click=start_game, use_container_width=True)
        st.button("למסך הראשי", key="to_menu", on_click=go_menu, use_container_width=True)


# ======================================================================
# Screen: upload study material (stage 2: extraction and chunking only)
# ======================================================================
@st.cache_data(show_spinner=False, ttl=900, max_entries=4)
def process_material(data, name, max_words, overlap_words):
    """Extract and chunk an uploaded file. Returns {"error": ...} or {"document", "chunks"}.

    Cached for a few minutes only so that the screen can rerun without
    re-reading the file. Nothing is written to disk.
    """
    try:
        document = extract_document(data, name)
        return {"document": document, "chunks": chunk_document(document, max_words, overlap_words)}
    except ExtractionError as error:
        return {"error": str(error)}
    except Exception:                       # a bug or a very odd file: do not crash the app
        logging.getLogger("conquest.qgen").exception("unexpected error while processing %s", name)
        return {"error": "אירעה שגיאה לא צפויה בעיבוד הקובץ. נסו קובץ אחר."}


def page_label(start, end):
    if start is None:
        return "ללא עמודים (קובץ טקסט)"
    return f"עמוד {start}" if start == end else f"עמודים {start}–{end}"


def chunks_html(chunks):
    cards = ""
    for chunk in chunks:
        overlap = f'<span class="chip">חפיפה: {chunk["overlap_words"]} מילים</span>' if chunk["overlap_words"] else ""
        cards += (
            '<div class="chunk"><div class="q-meta">'
            f'<span class="chip gold">מקטע {chunk["index"] + 1}</span>'
            f'<span class="chip">{page_label(chunk["page_start"], chunk["page_end"])}</span>'
            f'<span class="chip">{chunk["word_count"]} מילים</span>{overlap}</div>'
            f'<div class="chunk-text">{esc(chunk["text"])}</div></div>'
        )
    return f'<div class="scrollbox">{cards}</div>'


def document_html(document):
    parts = ""
    for page in document["pages"]:
        if page["page"] is not None:
            parts += f'<div class="page-mark">— עמוד {page["page"]} —</div>'
        parts += f'<div class="chunk-text">{esc(page["text"]) if page["text"] else "(אין טקסט בעמוד הזה)"}</div>'
    return f'<div class="scrollbox">{parts}</div>'


def render_materials():
    st.button("→ חזרה למסך הראשי", key="materials_back", on_click=go_menu)
    st.markdown(
        '<div class="panel"><div class="panel-title">העלאת חומר לימוד</div>'
        '<div class="empty-hint">העלו קובץ PDF או TXT כדי לראות את הטקסט שחולץ ממנו ואת החלוקה למקטעים. '
        "בשלב הזה עדיין לא נוצרות שאלות, והקובץ אינו נשמר.</div></div>",
        unsafe_allow_html=True,
    )
    uploaded = st.file_uploader("בחרו קובץ PDF או TXT", type=["pdf", "txt"], key="material_file")
    with st.expander("הגדרות חלוקה למקטעים"):
        max_words = st.slider("גודל מקטע (מילים)", 60, 400, DEFAULT_MAX_WORDS, step=10)
        overlap_words = st.slider("חפיפה בין מקטעים (מילים)", 0, 100, DEFAULT_OVERLAP_WORDS, step=5)
        overlap_words = min(overlap_words, max_words // 2)        # the splitter requires this
    if uploaded is None:
        st.info("עדיין לא נבחר קובץ.")
        return

    result = process_material(uploaded.getvalue(), uploaded.name, max_words, overlap_words)
    if "error" in result:
        st.error(result["error"])
        return
    document, chunks = result["document"], result["chunks"]
    stats = document["stats"]
    average = round(sum(c["word_count"] for c in chunks) / len(chunks)) if chunks else 0
    st.markdown(
        '<div class="stats">'
        + stat_tile("קובץ", f'<span style="font-size:1rem">{esc(document["document_name"])}</span>')
        + stat_tile("עמודים", stats["page_count"] if stats["page_count"] else "—")
        + stat_tile("מילים", stats["word_count"])
        + stat_tile("מקטעים", len(chunks), f"· ממוצע {average} מילים")
        + "</div>",
        unsafe_allow_html=True,
    )
    for warning in document["warnings"]:
        st.warning(warning)
    chunks_tab, text_tab = st.tabs(["מקטעים", "הטקסט שחולץ"])
    with chunks_tab:
        st.markdown(chunks_html(chunks), unsafe_allow_html=True)
    with text_tab:
        st.markdown(document_html(document), unsafe_allow_html=True)


# ======================================================================
# Main
# ======================================================================
st.markdown(build_css(), unsafe_allow_html=True)
st.session_state.setdefault("view", "menu")
st.session_state.setdefault("game", None)
st.session_state.setdefault("course", "")

SCREENS = {
    "menu": render_menu,
    "map": render_map,
    "question": render_question,
    "result": render_result,
    "end": render_end,
    "materials": render_materials,
}
if st.session_state.view not in ("menu", "materials") and st.session_state.game is None:
    st.session_state.view = "menu"      # e.g. session was reset
SCREENS[st.session_state.view]()
