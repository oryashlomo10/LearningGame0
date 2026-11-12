# CLAUDE.md - Conquest Project Context

## 1. What Conquest Is
- **Name:** Conquest — *Learn. Compete. Conquer.*
- **Problem:** Students struggle to study alone and stay motivated, and writing good practice questions from course material takes a lot of time.
- **Solution:** A competitive strategy game. Students join a study group for a course and upload course materials. An AI system turns the materials into questions. Players answer questions correctly to capture territories on a shared map and compete against classmates.
- **Team:** Uria Shlomo (product / programmer) and Shira Grinvald (AI-data / UI-UX). Course project, so keep things simple and demo-able.

## 2. Long-Term Vision
- Study groups per course, with a shared pool of materials.
- AI extracts text and topics from PDFs, slides and notes, then generates multiple-choice questions with correct answer, explanation, topic and difficulty (easy / medium / hard).
- Shared territory map: attack, defend, or practice. Rankings and group challenges.
- Learning progress per player: strong topics vs. topics to practice.
- Questions must be grounded in the uploaded material (show source, allow review/correction) to limit AI errors.

## 3. Current Project Structure
```
app.py             Streamlit UI: draws the screens (menu, map, question, result, end), wires buttons and map events
game_logic.py      Pure game rules/state (no Streamlit): territories, attacks, scoring, opponents, win/lose
question_bank.py   Loads + validates questions (only place that knows where questions come from)
styles.py          All page CSS (palette variables)
map_geometry.py    Generates the world map shapes + territory adjacency (pure Python, computed at import)
components/world_map/index.html   Custom Streamlit component (plain HTML/JS, no build): draws and handles clicks on the SVG map
data/questions.json   24 sample Hebrew CS questions (course "מבוא למדעי המחשב")
data/README.md     Notes about the data folder
requirements.txt   Dependencies (streamlit>=1.40)
.gitignore, README.md (Hebrew project definition), CLAUDE.md
```
Question schema (the contract for any future question source, e.g. AI): `id, question, options (exactly 4), correct_answer (exact text of one option), explanation, topic, difficulty (easy|medium|hard), points`.

## 4. Tech Stack
- Python, Streamlit (UI, session state), Git/GitHub.
- No other libraries. No database, no AI/API client.

## 5. Implemented So Far
- Main menu (Hebrew RTL, game identity) with a working "התחלת משחק" button.
- Playable single-player demo on an interactive WORLD MAP: 16 irregular territories (14 mainland regions + 2 islands linked by sea lanes), organic coastline, mountains/forests/hills/rivers, owner colors (player teal with glow, opponents red/purple/orange, neutral stone with hatching), hover tooltip, gold selection outline, conquest flash animation, compass. Plus legend, stats row, progress bars, leaderboard, battle log.
- Every territory has real `neighbors` (symmetric adjacency from the geometry, `game_logic.neighbors_of`).
- **Knowledge regions:** `REGIONS` in `game_logic.py` groups the 16 territories into 8 regions of 2 bordering territories; each region is one course topic. A territory only asks questions of its region's topic (`pick_question`: same topic + difficulty, then same topic, then the oldest-used question of the topic is recycled; a topic missing from the bank falls back to difficulty). Holding a whole region = `REGION_BONUS` (+20) points. No player starts with a whole region. Side panel "אזורי ידע" shows them.
- **Adjacency rule:** you may only attack a territory that borders one of yours (islands through sea lanes). If you own nothing you may attack anywhere. Attackable territories get a dashed gold outline on the map (`attackable` in `map_state`).
- **Defense:** after each attack the demo opponents get `OPPONENT_MOVES` (2) moves, each with chance `OPPONENT_MOVE_CHANCE`, only against territories next to their own land. A neutral territory is taken at once; an attack on yours opens a defense question (`game["current"]["kind"] == "defend"`, does not cost an attack). Correct = you keep it, wrong = the opponent takes it. At most one defense per turn. Flow: attack result screen -> "להגנה" button -> question screen -> defense result -> map.
- Rules: easy/medium/hard territories worth 10/20/30; 12 attacks per game; cannot attack own territory; a correct answer captures the territory, a wrong one wastes the attack. Score = territory points + region bonuses.
- Balance (simulated, 3000 games per row): random guessing wins ~0%, 50% correct ~15-35%, 75% correct ~90-97%. Re-run a simulation after changing any rule constant.
- 3 SCRIPTED demo opponents (עידו, מאיה, תמר), labeled "הדגמה" in the UI.
- End: victory = hold 9 of 16 territories, or finish with the top score when attacks run out; defeat otherwise (or if a demo opponent gets 9). A pending defense is answered before the game ends. End screen with "משחק חוזר", including successful defenses and full regions.
- Questions are loaded from JSON, validated, and passed into the game as plain dicts.
- State lives in `st.session_state` only (a full browser reload starts over).

## 6. Planned, NOT Implemented
Do not assume any of these exist:
- File upload (PDF / text) and text extraction
- AI question generation (LLM/API calls) - only the JSON bank exists
- Real multiplayer, study groups, login/accounts, database/persistence
- Smarter opponents (personalities, opponents attacking each other), real players.
- 3D board (planned next: tilted tabletop map, relief height = difficulty, built from the `map_geometry.py` shapes).
- Automated tests in the repo, per-topic progress tracking

## 7. Conventions & Guidelines
- **UI language:** Hebrew, RTL. Keep English only for "CONQUEST" and the tagline.
- Keep code simple and beginner-friendly: clear names, short functions, comments only where useful.
- Keep the layers separate: rules in `game_logic.py` (no `st.` calls), questions in `question_bank.py`, CSS in `styles.py`, drawing in `app.py`. Never hardcode questions in game logic.
- **The map is a custom component**, not Streamlit buttons: `app.py` sends `{geo: map_geometry.MAP, state: map_state(game)}` to `components/world_map/index.html`; clicks come back as `{type: "select" | "attack", id, n}` and are handled in `handle_map_event` (an `on_change` callback, so state is updated before the rerun). The SVG is built once in JS and only recolored on later renders.
- Territory ids are the contract between `map_geometry.py` (shapes: seeds 0-13, islands 14-15) and `TERRITORY_DEFS` / `START_OWNERS` / `REGIONS` in `game_logic.py`. Change them together.
- Region topics in `REGIONS` must be spelled exactly like the `topic` field of the questions. Every region/difficulty pair should have at least one question in the bank (the bank itself is Shira's area; tell her when a topic needs more questions).
- A question can be an attack or a defense: use `game["questions_asked"]` (not `game["attacks"]`) when something must be unique per question, e.g. widget keys.
- After changing seeds or noise in `map_geometry.py`, check that no outline self-intersects (a spike or loop on the coast) and look at the map in a browser. Territory shapes are weighted Voronoi cells; borders are bent by a function of position so neighbors always share the exact same border.
- Page CSS selectors (styles.py) depend on the Streamlit version (`data-testid`s). After changing `styles.py`, restart the server (it can serve a stale copy) and check the result visually.
- Build HTML strings without blank lines or 4-space-indented lines (markdown would break them) and escape dynamic text (`esc()` / `rich()` in `app.py`).
- Add a dependency only when it is actually needed, and add it to `requirements.txt`.
- Never commit secrets: API keys go in `.env` or `.streamlit/secrets.toml` (both git-ignored).
- Do not invent data or claim features work without running them. Do not present demo opponents as real users.

## 8. How to Run & Test
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py        # opens http://localhost:8501
```
- No automated tests are committed. After edits run `python -m py_compile app.py game_logic.py question_bank.py styles.py`, validate `data/questions.json` through `question_bank.load_question_bank()`, then play a round in the browser. `streamlit.testing.v1.AppTest` works for scripted UI flows (buttons have stable keys such as `start_game`, `attack_btn`, `submit_btn`, `continue_btn`, `play_again`). AppTest cannot click the custom map component: set `game["selected"]` in session state instead, and test real map clicks in a browser (e.g. Playwright with `frame_locator("iframe")`, clicking `.label` positions).

## 9. Instructions for Future Development
- Work in small tasks, one feature at a time; do only what is asked.
- Read `README.md` and the relevant files before changing anything.
- Do not modify unrelated files. Do not delete or overwrite existing documentation; update docs (this file, README) when behavior changes.
- Do not commit or push unless explicitly asked.
- **Next milestone (AI):** file upload (PDF/TXT) -> extract text -> generate questions that follow the schema above -> feed them to `new_game(questions)`. Mock first; a real LLM call needs an explicit decision on API key and cost. Keep AI output validated with `question_bank.validate_questions`.
- Update sections 5 and 6 of this file whenever a feature moves from planned to implemented.
