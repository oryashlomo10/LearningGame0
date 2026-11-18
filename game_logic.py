"""Pure game logic for Conquest (no Streamlit code in here).

The game state is one plain dictionary created by new_game(). The UI calls the
functions below and only displays the result. Questions are passed in as a
list of dictionaries and never hardcoded here.

Rules in short:
- 16 territories with real neighbors (see map_geometry.py). Each has a difficulty: easy = 10, medium = 20, hard = 30 points.
- The map is split into 8 REGIONS of 2 territories. Every region is one course
  topic, and its territories only ask questions about that topic.
  Holding a whole region gives REGION_BONUS extra points.
- The player has MAX_ACTIONS attacks. You may only attack a territory that
  borders one of yours (islands border the coast through sea lanes).
  A correct answer captures the territory.
- After every attack a demo opponent may attack a territory that borders its
  own. A neutral territory is simply taken. If it attacks one of YOUR
  territories, you answer a defense question: correct = you keep it.
  Defending does not cost an attack.
- Score = points of the territories you own + region bonuses.
- Victory: hold MAJORITY territories, or finish with the highest score
  when the attacks run out.
"""

import random

from map_geometry import NEIGHBORS

# ---------- Game settings ----------
MAX_ACTIONS = 12
MAJORITY = 9                     # more than half of the 16 territories
REGION_BONUS = 20                # extra points for holding a whole region
# After each attack the demo opponents get OPPONENT_MOVES moves, each one
# happening with OPPONENT_MOVE_CHANCE. Tuned by simulation: random guessing
# almost never wins, a student answering 75% right wins most games.
OPPONENT_MOVES = 2
OPPONENT_MOVE_CHANCE = 0.8
NEUTRAL_WEIGHT = 3               # opponents prefer neutral land this many times over yours
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
    ("גבעות החיפוש", "easy"),        # 0  north-west
    ("מעבר הפרמטרים", "medium"),     # 1
    ("פסגת הרקורסיה", "hard"),       # 2
    ("חוף האיטרציות", "medium"),     # 3
    ("מגדל הסיבוכיות", "hard"),      # 4
    ("נמל הטיפוסים", "easy"),        # 5
    ("שדות האינדקסים", "medium"),    # 6
    ("יער הלולאות", "medium"),       # 7  center
    ("ערבות זמן הריצה", "medium"),   # 8
    ("כפר המחסניות", "easy"),        # 9
    ("עמק המשתנים", "easy"),         # 10 south-west
    ("חוף הרשימות", "easy"),         # 11
    ("ממלכת המחלקות", "easy"),       # 12
    ("מפרץ ההכמסה", "medium"),       # 13
    ("מבצר המיון", "hard"),          # 14 island
    ("אי המצביעים", "hard"),         # 15 island
]
# Regions: (topic, [territory ids]). The topic must be written exactly like the
# "topic" field of the questions. The two territories of a region always border
# each other, and no player starts with a whole region.
# If the question bank has no questions for a topic, questions are picked by
# difficulty only (so a different course still works).
REGIONS = [
    ("אלגוריתמים בסיסיים", [0, 14]),
    ("פונקציות", [1, 2]),
    ("לולאות", [3, 7]),
    ("סיבוכיות זמן", [4, 8]),
    ("משתנים וטיפוסי נתונים", [5, 10]),
    ("מערכים", [6, 11]),
    ("מבני נתונים בסיסיים", [9, 15]),
    ("תכנות מונחה עצמים", [12, 13]),
]
# Who owns what at the start. Everything else is neutral (owner = None).
START_OWNERS = {10: "me", 11: "me", 0: "o1", 1: "o1",
                3: "o2", 4: "o2", 9: "o3", 13: "o3"}


def _region_of(territory_id):
    return next(i for i, (_, ids) in enumerate(REGIONS) if territory_id in ids)


# ---------- Creating a game ----------
def new_game(questions, rng=None):
    """Create a fresh game state using the given question list."""
    territories = []
    for i, (name, difficulty) in enumerate(TERRITORY_DEFS):
        region = _region_of(i)
        territories.append({
            "id": i,
            "name": name,
            "difficulty": difficulty,
            "points": DIFFICULTY_POINTS[difficulty],
            "owner": START_OWNERS.get(i),
            "neighbors": NEIGHBORS[i],      # ids of bordering territories
            "region": region,               # index in REGIONS
            "topic": REGIONS[region][0],
        })
    return {
        "territories": territories,
        "questions": list(questions),
        "used_question_ids": [],  # oldest first
        "rng": rng or random.Random(),
        "actions_left": MAX_ACTIONS,
        "selected": None,        # id of the selected territory
        "current": None,         # the question in progress (see _open_question)
        "last_result": None,     # result of the last answered question
        "log": [],               # newest first: {"kind", "text"}
        "attacks": 0,
        "conquests": 0,
        "defenses": 0,           # defense questions asked
        "defenses_won": 0,
        "questions_asked": 0,    # attacks + defenses (a unique number per question)
        "over": False,
        "outcome": None,         # "victory" | "defeat"
        "end_reason": None,      # "majority" | "rival_majority" | "actions_out"
    }


# ---------- Reading the state ----------
def get_territory(game, territory_id):
    return game["territories"][territory_id]


def neighbors_of(game, territory_id):
    """The territories that border the given one."""
    return [get_territory(game, n) for n in get_territory(game, territory_id)["neighbors"]]


def territory_count(game, owner):
    return sum(1 for t in game["territories"] if t["owner"] == owner)


def borders_owner(game, territory_id, owner):
    """True if the territory borders a territory of this owner."""
    return any(n["owner"] == owner for n in neighbors_of(game, territory_id))


def region_info(game):
    """One row per region: topic, territories and who holds all of it (or None)."""
    rows = []
    for index, (topic, ids) in enumerate(REGIONS):
        owners = {get_territory(game, i)["owner"] for i in ids}
        holder = owners.pop() if len(owners) == 1 else None
        rows.append({"index": index, "topic": topic,
                     "territories": [get_territory(game, i) for i in ids],
                     "holder": holder})
    return rows


def regions_held(game, owner):
    return sum(1 for r in region_info(game) if r["holder"] == owner)


def score(game, owner):
    points = sum(t["points"] for t in game["territories"] if t["owner"] == owner)
    return points + REGION_BONUS * regions_held(game, owner)


def ranking(game):
    """All players sorted by score (ties: more territories, then the human)."""
    rows = [
        {"key": key, **info,
         "score": score(game, key), "count": territory_count(game, key),
         "regions": regions_held(game, key)}
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
        return False, "יש שאלה פתוחה"
    if game["actions_left"] <= 0:
        return False, "נגמרו התקיפות"
    if territory_id is None:
        return False, "בחרו שטח במפה"
    if get_territory(game, territory_id)["owner"] == PLAYER:
        return False, "השטח כבר בשליטתך"
    # Without any territory left you may land anywhere (a way back into the game).
    if territory_count(game, PLAYER) > 0 and not borders_owner(game, territory_id, PLAYER):
        return False, "אפשר לתקוף רק שטח שגובל בשטח שלך"
    return True, ""


def attackable_ids(game):
    """Ids of the territories the player may attack right now."""
    return [t["id"] for t in game["territories"] if can_attack(game, t["id"])[0]]


# ---------- Actions ----------
def select_territory(game, territory_id):
    game["selected"] = territory_id


def pick_question(game, territory):
    """Choose a question for a territory: its region's topic, at its difficulty.

    Prefers questions not used yet in this game: first the same topic and
    difficulty, then the same topic at any difficulty. When the topic is used
    up, the question of that topic that was used longest ago comes back.
    A topic with no questions at all falls back to the difficulty.
    """
    rng = game["rng"]
    questions = game["questions"]
    used = game["used_question_ids"]
    same_topic = [q for q in questions if q["topic"] == territory["topic"]]
    if same_topic:
        tiers = [[q for q in same_topic if q["difficulty"] == territory["difficulty"]], same_topic]
    else:
        tiers = [[q for q in questions if q["difficulty"] == territory["difficulty"]], questions]
    tiers = [tier for tier in tiers if tier]

    question = None
    for tier in tiers:
        fresh = [q for q in tier if q["id"] not in used]
        if fresh:
            question = rng.choice(fresh)
            break
    if question is None:                # everything was used: recycle the oldest
        question = min(tiers[0], key=lambda q: used.index(q["id"]))
        used.remove(question["id"])
    used.append(question["id"])
    return question


def _open_question(game, kind, territory_id, opponent=None):
    """Make a question the current one. kind is "attack" or "defend"."""
    territory = get_territory(game, territory_id)
    question = pick_question(game, territory)
    options = list(question["options"])
    game["rng"].shuffle(options)       # answer position is random each time
    game["questions_asked"] += 1
    game["current"] = {
        "kind": kind,
        "territory_id": territory_id,
        "question": question,
        "options": options,
        "opponent": opponent,          # who attacks you (defense only)
    }
    return game["current"]


def start_attack(game, territory_id):
    """Spend one action and open a question challenge for the territory."""
    allowed, reason = can_attack(game, territory_id)
    if not allowed:
        raise ValueError(reason)
    game["actions_left"] -= 1
    game["attacks"] += 1
    return _open_question(game, "attack", territory_id)


def submit_answer(game, answer):
    """Check the answer to the current question (attack or defense).

    Updates ownership, lets the demo opponents move after an attack, and
    returns a result dict. After an attack, game["current"] may hold a new
    defense question (an opponent attacked one of your territories).
    """
    current = game["current"]
    if current is None:
        raise ValueError("אין שאלה פתוחה")
    if answer not in current["options"]:
        raise ValueError("יש לבחור אחת מהתשובות")

    question = current["question"]
    territory = get_territory(game, current["territory_id"])
    previous_owner = territory["owner"]
    correct = answer == question["correct_answer"]
    game["current"] = None
    rival_events = []

    if current["kind"] == "attack":
        if correct:
            territory["owner"] = PLAYER
            game["conquests"] += 1
            _add_log(game, "win", f"כבשת את {territory['name']} (+{territory['points']})")
        else:
            _add_log(game, "loss", f"ההתקפה על {territory['name']} נכשלה")
        if territory_count(game, PLAYER) < MAJORITY:     # a win ends the game at once
            rival_events = opponent_turn(game)
    else:
        rival = PLAYERS[current["opponent"]]["name"]
        if correct:
            game["defenses_won"] += 1
            _add_log(game, "win", f"הגנת על {territory['name']} מפני {rival} (הדגמה)")
        else:
            territory["owner"] = current["opponent"]
            _add_log(game, "rival", f"{rival} (הדגמה) השתלט/ה על {territory['name']}")

    if game["current"] is None:        # no defense waiting
        _check_game_over(game)

    result = {
        "kind": current["kind"],
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
        "opponent": current["opponent"],
        "rival_events": rival_events,   # what the demo opponents did after an attack
    }
    game["last_result"] = result
    return result


def opponent_turn(game):
    """Let the DEMO opponents make up to OPPONENT_MOVES moves.

    Every move (with chance OPPONENT_MOVE_CHANCE) attacks a territory next to
    the opponent's own land. A neutral territory is captured right away. An
    attack on the player's territory opens a defense question and ends the
    turn, so there is never more than one defense at a time. These opponents
    are scripted, not real users. Returns a list of event dicts.
    """
    events = []
    for _ in range(OPPONENT_MOVES):
        event = _opponent_move(game)
        if event:
            events.append(event)
            if event["kind"] == "attack_on_player":
                break
    return events


def _opponent_move(game):
    rng = game["rng"]
    if rng.random() >= OPPONENT_MOVE_CHANCE:
        return None
    targets = [t for t in game["territories"]
               if t["owner"] in (None, PLAYER)
               and any(borders_owner(game, t["id"], o) for o in OPPONENTS)]
    if not targets:
        return None
    weights = [NEUTRAL_WEIGHT if t["owner"] is None else 1 for t in targets]
    target = rng.choices(targets, weights=weights)[0]
    opponent = rng.choice([o for o in OPPONENTS if borders_owner(game, target["id"], o)])
    name = PLAYERS[opponent]["name"]

    if target["owner"] == PLAYER:
        game["defenses"] += 1
        _open_question(game, "defend", target["id"], opponent)
        _add_log(game, "rival", f"{name} (הדגמה) תוקף/ת את {target['name']}")
        return {"kind": "attack_on_player", "opponent": opponent, "territory_name": target["name"]}

    target["owner"] = opponent
    _add_log(game, "rival", f"{name} (הדגמה) כבש/ה את {target['name']}")
    return {"kind": "capture", "opponent": opponent, "territory_name": target["name"]}


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
