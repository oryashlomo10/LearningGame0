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
qgen/extract.py    Text extraction from uploaded PDF/TXT (pypdf), page numbers kept, Hebrew error messages (no Streamlit)
qgen/chunking.py   Splits extracted text into overlapping chunks that remember page + character position (no Streamlit)
qgen/providers.py  LLM Provider interface (generate_text), OllamaProvider (local HTTP API, urllib), MockProvider (tests), provider_from_env (no Streamlit)
qgen/generate.py   Prompts (chunk text only), JSON parsing, validation (4 options, answer, difficulty, quote found in chunk), source page/chunk id (no Streamlit)
attempts.py        Appends each REAL answer attempt to data/attempts.jsonl (anonymous, never raises)
styles.py          All page CSS (palette variables)
map_geometry.py    Generates the world map shapes + territory adjacency (pure Python, computed at import)
components/world_map/index.html   Custom Streamlit component (plain HTML/JS, no build): draws and handles clicks on the SVG map
data/questions.json   24 sample Hebrew CS questions (course "מבוא למדעי המחשב")
data/attempts.jsonl  Collected answer attempts (one JSON line each) - real players only
data/README.md     Notes about the data folder
requirements.txt   Dependencies (streamlit>=1.40)
.gitignore, README.md (Hebrew project definition), CLAUDE.md
```
Question schema (the contract for any future question source, e.g. AI): `id, question, options (exactly 4), correct_answer (exact text of one option), explanation, topic, difficulty (easy|medium|hard), points`.

## 4. Tech Stack
- Python, Streamlit (UI, session state), `pypdf` (PDF text extraction), Git/GitHub.
- No other libraries. No database, no AI/API client.

## 5. Implemented So Far
- Main menu (Hebrew RTL, game identity) with a working "התחלת משחק" button.
- Playable single-player demo on an interactive WORLD MAP: 16 irregular territories (14 mainland regions + 2 islands linked by sea lanes), organic coastline, mountains/forests/hills/rivers, owner colors (player teal with glow, opponents red/purple/orange, neutral stone with hatching), hover tooltip, gold selection outline, conquest flash animation, compass. Plus legend, stats row, progress bars, leaderboard, battle log.
- Every territory has real `neighbors` (symmetric adjacency from the geometry, `game_logic.neighbors_of`). It is shown in the side panel but NOT used by the attack rules yet (you can still attack any non-owned territory).
- Attack flow: select territory -> attack -> 4-option question (difficulty matches territory) -> submit (disabled until an answer is chosen) -> result with explanation -> back to map.
- Rules: easy/medium/hard territories worth 10/20/30; 12 attacks per game; cannot attack own territory; a correct answer captures the territory, a wrong one wastes the attack.
- 3 SCRIPTED demo opponents (עידו, מאיה, תמר), labeled "הדגמה" in the UI; one may capture a territory after each attack (chance in `OPPONENT_MOVE_CHANCE`, tuned by simulation).
- End: victory = hold 9 of 16 territories, or finish with the top score when attacks run out; defeat otherwise (or if a demo opponent gets 9). End screen with "משחק חוזר".
- Questions are loaded from JSON, validated, and passed into the game as plain dicts.
- Upload screen (menu -> "העלאת חומר לימוד"): upload a PDF or TXT, see the extracted text (with page markers) and the chunks (page range, word count, overlap). Nothing is saved and no questions are generated yet. Bad files (empty, corrupt, encrypted, scanned/image-only, binary, too big/long) give a clear Hebrew message. Chunks are exact substrings of `full_text`, so a quote from a chunk can always be located again. Known limitation: lines that mix Hebrew with English/numbers can come out of PDFs in scrambled order (the screen warns about it); scanned PDFs need OCR, which does not exist.
- Data collection for the future ML model: every answer by the real player is appended to `data/attempts.jsonl` (fields: schema_version, attempt_id, player_id, session_id, timestamp, question_id, topic, difficulty, chosen_option, is_correct, response_time_ms). Simulated opponents are never recorded. ids are random (player_id per browser session, session_id per game); response time is measured on the server from the first display of the question. A save failure shows a warning and the game continues. Duplicate attempts are ignored.
- Question generation (upload screen, tab "יצירת שאלות (ניסיוני)"): button sends the first N chunks (one request per chunk) to a local Ollama model and shows the valid questions with answer, explanation, topic, difficulty, source quote, chunk id and page; rejected questions/chunks are listed with a Hebrew reason. Display/review only: NOT connected to the game, nothing saved. Config via env vars `CONQUEST_OLLAMA_MODEL` (required, no default), `CONQUEST_OLLAMA_URL` (default http://localhost:11434), `CONQUEST_OLLAMA_TIMEOUT` (seconds, default 180). Models are never downloaded automatically. The source quote must appear in the chunk (whitespace-insensitive); duplicate question texts are dropped; options are shuffled deterministically. Generated question = game schema + `source_quote, source_chunk_id, source_page, source_document`, id `gen-<chunk_id>-<n>`. Tested only with MockProvider and a fake local HTTP server, not with a real Ollama model yet.
- State lives in `st.session_state` only (a full browser reload starts over).

## 6. Planned, NOT Implemented
Do not assume any of these exist:
- DOCX/PPTX upload and OCR for scanned PDFs
- Feeding generated questions into the game (they are display/review only), blind-solve / second-model reliability checks (`verify.py`), saving generated questions, paid or hosted LLM providers
- Real multiplayer, study groups, login/accounts, database/persistence
- Adjacency-based rules (attack only neighbors, region bonuses, defending borders) - the data exists, the rules do not. Defending, real players.
- Automated tests in the repo, per-topic progress tracking

## 7. Conventions & Guidelines
- **UI language:** Hebrew, RTL. Keep English only for "CONQUEST" and the tagline.
- Keep code simple and beginner-friendly: clear names, short functions, comments only where useful.
- Keep the layers separate: rules in `game_logic.py` (no `st.` calls), questions in `question_bank.py`, CSS in `styles.py`, drawing in `app.py`. Never hardcode questions in game logic.
- **The map is a custom component**, not Streamlit buttons: `app.py` sends `{geo: map_geometry.MAP, state: map_state(game)}` to `components/world_map/index.html`; clicks come back as `{type: "select" | "attack", id, n}` and are handled in `handle_map_event` (an `on_change` callback, so state is updated before the rerun). The SVG is built once in JS and only recolored on later renders.
- Territory ids are the contract between `map_geometry.py` (shapes: seeds 0-13, islands 14-15) and `TERRITORY_DEFS` / `START_OWNERS` in `game_logic.py`. Change them together.
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
- **Next milestone (AI):** human review of generated questions, a reliability check, then feed approved questions to `new_game(questions)`. Keep AI output validated (`question_bank.validate_question` is already applied in `qgen/generate.py`).
- **Never write test data into `data/attempts.jsonl`** (it must contain real players only): tests set the `CONQUEST_ATTEMPTS_PATH` environment variable to a temporary file. Playing the game locally also appends there, so decide before committing that file (it is not git-ignored yet).
- Update sections 5 and 6 of this file whenever a feature moves from planned to implemented.
