"""Pure game logic for Conquest (no Streamlit code in here).

The game state is one plain dictionary created by new_game(). The UI calls the
functions below and only displays the result. Questions are passed in as a
list of dictionaries and never hardcoded here.

Rules in short:
- 16 territories with real neighbors (see map_geometry.py). Each has a difficulty: easy = 10, medium = 20, hard = 30 points.
- The player has MAX_ACTIONS attacks. Each attack asks one question whose
  difficulty matches the territory. Correct answer = territory captured.
- After every attack a simulated demo opponent may capture a territory.
- Score = total points of the territories you own.
- Victory: hold MAJORITY territories, or finish with the highest score
  when the attacks run out.
"""

import random

from map_geometry import NEIGHBORS

# ---------- Game settings ----------
MAX_ACTIONS = 12
MAJORITY = 9                     # more than half of the 16 territories
# Chance that a demo opponent acts after each attack. Tuned by simulation:
# random guessing wins ~5% of games, a student answering 75% right wins ~75%.
OPPONENT_MOVE_CHANCE = 0.8
LOG_SIZE = 5

DIFFICULTY_POINTS = {"easy": 10, "medium": 20, "hard": 30}
DIFFICULTY_LABELS = {"easy": "קל", "medium": "בינוני", "hard": "קשה"}

# ---------- Players ----------
PLAYER = "me"
PLAYERS = {
    "me": {"name": "את/ה", "color": "#2dd4bf", "demo": False},
    "o1": {"name": "עידו", "color": "#f0616d", "demo": True},
    "o2": {"name": "מאיה", "color": "#a78bfa", "demo": True},
    "o3": {"name": "תמר", "color": "#fb923c", "demo": True},
}
OPPONENTS = [key for key in PLAYERS if key != PLAYER]

# ---------- Map (ids 0-15; the shapes live in map_geometry.py) ----------
# The order must match the territory ids in map_geometry.py:
# 0-13 are the mainland regions, 14-15 are islands.
TERRITORY_DEFS = [
    ("עמק המשתנים", "easy"),         # 0  north-west
    ("יער הלולאות", "medium"),       # 1
    ("פסגת הרקורסיה", "hard"),       # 2
    ("חוף המערכים", "medium"),       # 3
    ("מגדל הסיבוכיות", "hard"),      # 4
    ("נמל המחרוזות", "easy"),        # 5
    ("שדות התנאים", "easy"),         # 6
    ("גשר האלגוריתמים", "medium"),   # 7  center
    ("ערבות המחסניות", "medium"),    # 8
    ("כפר הפקודות", "easy"),         # 9
    ("מעגן הפונקציות", "easy"),      # 10 south-west
    ("חוף הרשימות", "easy"),         # 11
    ("עמק המילונים", "medium"),      # 12
    ("מפרץ התורים", "medium"),       # 13
    ("מבצר המיון", "hard"),          # 14 island
    ("אי הזיכרון", "hard"),          # 15 island
]
# Who owns what at the start. Everything else is neutral (owner = None).
START_OWNERS = {10: "me", 11: "me", 0: "o1", 1: "o1",
                3: "o2", 4: "o2", 9: "o3", 13: "o3"}


# ---------- Creating a game ----------
def new_game(questions, rng=None):
    """Create a fresh game state using the given question list."""
    territories = [
        {
            "id": i,
            "name": name,
            "difficulty": difficulty,
            "points": DIFFICULTY_POINTS[difficulty],
            "owner": START_OWNERS.get(i),
            "neighbors": NEIGHBORS[i],      # ids of bordering territories
        }
        for i, (name, difficulty) in enumerate(TERRITORY_DEFS)
    ]
    return {
        "territories": territories,
        "questions": list(questions),
        "used_question_ids": [],
        "rng": rng or random.Random(),
        "actions_left": MAX_ACTIONS,
        "selected": None,        # id of the selected territory
        "current": None,         # the attack in progress (see start_attack)
        "last_result": None,     # result of the last answered question
        "log": [],               # newest first: {"kind", "text"}
        "attacks": 0,
        "conquests": 0,
        "over": False,
        "outcome": None,         # "victory" | "defeat"
        "end_reason": None,      # "majority" | "rival_majority" | "actions_out"
    }


# ---------- Reading the state ----------
def get_territory(game, territory_id):
    return game["territories"][territory_id]


def neighbors_of(game, territory_id):
    """The territories that border the given one (not used by the rules yet)."""
    return [get_territory(game, n) for n in get_territory(game, territory_id)["neighbors"]]


def territory_count(game, owner):
    return sum(1 for t in game["territories"] if t["owner"] == owner)


def score(game, owner):
    return sum(t["points"] for t in game["territories"] if t["owner"] == owner)


def ranking(game):
    """All players sorted by score (ties: more territories, then the human)."""
    rows = [
        {"key": key, **info,
         "score": score(game, key), "count": territory_count(game, key)}
        for key, info in PLAYERS.items()
    ]
    rows.sort(key=lambda r: (-r["score"], -r["count"], r["key"] != PLAYER))
    for position, row in enumerate(rows, start=1):
        row["rank"] = position
    return rows


def player_rank(game):
    return next(r["rank"] for r in ranking(game) if r["key"] == PLAYER)


def can_attack(game, territory_id):
    """Return (allowed, reason_in_hebrew_if_not)."""
    if game["over"]:
        return False, "המשחק הסתיים"
    if game["current"] is not None:
        return False, "יש התקפה פעילה"
    if game["actions_left"] <= 0:
        return False, "נגמרו התקיפות"
    if territory_id is None:
        return False, "בחרו שטח במפה"
    if get_territory(game, territory_id)["owner"] == PLAYER:
        return False, "השטח כבר בשליטתך"
    return True, ""


# ---------- Actions ----------
def select_territory(game, territory_id):
    game["selected"] = territory_id


def pick_question(game, difficulty):
    """Choose a not-yet-used question of the given difficulty.

    When all questions of that difficulty were used, they are recycled so the
    game never runs out of questions.
    """
    rng = game["rng"]
    pool = [q for q in game["questions"] if q["difficulty"] == difficulty]
    if not pool:                       # no question of this level: use any
        pool = game["questions"]
    used = game["used_question_ids"]
    fresh = [q for q in pool if q["id"] not in used]
    if not fresh:
        pool_ids = {q["id"] for q in pool}
        game["used_question_ids"] = [i for i in used if i not in pool_ids]
        fresh = pool
    question = rng.choice(fresh)
    game["used_question_ids"].append(question["id"])
    return question


def start_attack(game, territory_id):
    """Spend one action and open a question challenge for the territory."""
    allowed, reason = can_attack(game, territory_id)
    if not allowed:
        raise ValueError(reason)
    territory = get_territory(game, territory_id)
    question = pick_question(game, territory["difficulty"])
    options = list(question["options"])
    game["rng"].shuffle(options)       # answer position is random each time
    game["actions_left"] -= 1
    game["attacks"] += 1
    game["current"] = {
        "territory_id": territory_id,
        "question": question,
        "options": options,
    }
    return game["current"]


def submit_answer(game, answer):
    """Check the answer, update ownership/score, and return a result dict."""
    current = game["current"]
    if current is None:
        raise ValueError("אין התקפה פעילה")
    if answer not in current["options"]:
        raise ValueError("יש לבחור אחת מהתשובות")

    question = current["question"]
    territory = get_territory(game, current["territory_id"])
    previous_owner = territory["owner"]
    correct = answer == question["correct_answer"]

    if correct:
        territory["owner"] = PLAYER
        game["conquests"] += 1
        text = f"כבשת את {territory['name']} (+{territory['points']})"
        _add_log(game, "win", text)
    else:
        _add_log(game, "loss", f"ההתקפה על {territory['name']} נכשלה")

    game["current"] = None
    rival_event = simulate_opponents(game)
    _check_game_over(game)

    result = {
        "correct": correct,
        "chosen": answer,
        "correct_answer": question["correct_answer"],
        "explanation": question["explanation"],
        "question": question["question"],
        "options": current["options"],
        "topic": question["topic"],
        "difficulty": question["difficulty"],
        "territory_name": territory["name"],
        "points": territory["points"] if correct else 0,
        "previous_owner": previous_owner,
        "rival_event": rival_event,
    }
    game["last_result"] = result
    return result


def simulate_opponents(game):
    """Maybe let one DEMO opponent capture a neutral or player-owned territory.

    These opponents are scripted, not real users.
    """
    rng = game["rng"]
    if rng.random() >= OPPONENT_MOVE_CHANCE:
        return None
    targets = [t for t in game["territories"] if t["owner"] in (None, PLAYER)]
    if not targets:
        return None
    weights = [3 if t["owner"] is None else 1 for t in targets]   # prefer neutral
    target = rng.choices(targets, weights=weights)[0]
    opponent = rng.choice(OPPONENTS)
    previous_owner = target["owner"]
    target["owner"] = opponent
    event = {
        "opponent": opponent,
        "territory_name": target["name"],
        "took_from_player": previous_owner == PLAYER,
    }
    name = PLAYERS[opponent]["name"]
    verb = "השתלט/ה על" if previous_owner == PLAYER else "כבש/ה את"
    _add_log(game, "rival", f"{name} (הדגמה) {verb} {target['name']}")
    return event


# ---------- Ending the game ----------
def _check_game_over(game):
    if territory_count(game, PLAYER) >= MAJORITY:
        _finish(game, "victory", "majority")
    elif any(territory_count(game, o) >= MAJORITY for o in OPPONENTS):
        _finish(game, "defeat", "rival_majority")
    elif game["actions_left"] <= 0:
        outcome = "victory" if player_rank(game) == 1 else "defeat"
        _finish(game, outcome, "actions_out")


def _finish(game, outcome, reason):
    game["over"] = True
    game["outcome"] = outcome
    game["end_reason"] = reason


def _add_log(game, kind, text):
    game["log"].insert(0, {"kind": kind, "text": text})
    del game["log"][LOG_SIZE:]
