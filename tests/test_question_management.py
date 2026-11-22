"""Tests for question management (question_bank.py) and its link to the game.

Run from the project folder:
    python -m unittest discover -s tests -t . -v

Safety: every test uses a temporary folder. The environment variables
CONQUEST_APPROVED_PATH and CONQUEST_ATTEMPTS_PATH point there, and a check at
the end of the run proves that the real data/approved_questions.json and
data/attempts.jsonl were not changed.
"""

import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

import attempts
import game_logic as gl
import question_bank as qb

ROOT = Path(__file__).resolve().parent.parent
REAL_FILES = [ROOT / "data" / "approved_questions.json", ROOT / "data" / "attempts.jsonl"]
GAME_TOPICS = [name for name, _ in gl.REGIONS]
_fingerprints = {}


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def setUpModule():
    for path in REAL_FILES:
        _fingerprints[path] = fingerprint(path)


def tearDownModule():
    for path in REAL_FILES:
        assert fingerprint(path) == _fingerprints[path], f"a test changed the real file {path}"


def make_generated(n=1, topic="נושא שהמודל המציא", text=None):
    """A question shaped like the output of qgen.generate."""
    return {
        "id": f"gen-abc123-{n}",
        "question": text or f"מה מדפיסה הלולאה מספר {n}?",
        "options": ["א", "ב", "ג", "ד"],
        "correct_answer": "ב",
        "explanation": "כי כך כתוב בחומר.",
        "topic": topic,
        "difficulty": "medium",
        "points": 20,
        "source_quote": "הלולאה רצה כל עוד התנאי נכון",
        "source_chunk_id": "abc123-000",
        "source_page": 3,
        "source_document": "notes.pdf",
    }


class TempFilesTestCase(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.dir = Path(folder.name)
        self.path = self.dir / "approved.json"
        patches = {qb.APPROVED_PATH_ENV_VAR: str(self.path),
                   attempts.PATH_ENV_VAR: str(self.dir / "attempts.jsonl")}
        for name, value in patches.items():
            old = os.environ.get(name)
            os.environ[name] = value
            self.addCleanup(lambda n=name, o=old: os.environ.pop(n, None) if o is None else os.environ.__setitem__(n, o))

    def stored(self):
        return json.loads(self.path.read_text(encoding="utf-8"))["questions"]


class ApproveAndLoadTests(TempFilesTestCase):
    def test_approve_saves_everything_and_survives_a_reload(self):
        q = make_generated()
        self.assertEqual(qb.approve_question(q, "לולאות", GAME_TOPICS), ("saved", ""))
        loaded = qb.load_approved(game_topics=GAME_TOPICS)      # read again from disk
        self.assertEqual(len(loaded), 1)
        saved = loaded[0]
        for field in qb.QUESTION_FIELDS + qb.SOURCE_FIELDS:
            self.assertIn(field, saved)
        self.assertEqual(saved["source_quote"], q["source_quote"])
        self.assertEqual(saved["source_chunk_id"], "abc123-000")
        self.assertEqual(saved["source_page"], 3)
        self.assertEqual(saved["source_document"], "notes.pdf")

    def test_game_topic_is_kept_apart_from_the_model_topic(self):
        qb.approve_question(make_generated(topic="משהו חופשי"), "מערכים", GAME_TOPICS)
        saved = qb.load_approved()[0]
        self.assertEqual(saved["original_topic"], "משהו חופשי")
        self.assertEqual(saved["game_topic"], "מערכים")
        self.assertEqual(saved["topic"], "מערכים")               # what the game and the answer log use

    def test_input_question_is_not_changed(self):
        q = make_generated()
        before = copy.deepcopy(q)
        qb.approve_question(q, "לולאות", GAME_TOPICS)
        self.assertEqual(q, before)

    def test_topic_must_be_a_game_topic(self):
        for bad in (None, "", "נושא שלא קיים"):
            status, _ = qb.approve_question(make_generated(), bad, GAME_TOPICS)
            self.assertEqual(status, "error")
        self.assertFalse(self.path.exists())

    def test_question_without_a_source_is_refused(self):
        for field in qb.SOURCE_FIELDS:
            q = make_generated()
            del q[field]
            self.assertEqual(qb.approve_question(q, "לולאות", GAME_TOPICS)[0], "error", field)
        q = make_generated()
        q["source_quote"] = "  "
        self.assertEqual(qb.approve_question(q, "לולאות", GAME_TOPICS)[0], "error")
        self.assertFalse(self.path.exists())

    def test_invalid_game_question_is_refused(self):
        q = make_generated()
        q["options"] = ["א", "ב", "ג"]
        self.assertEqual(qb.approve_question(q, "לולאות", GAME_TOPICS)[0], "error")

    def test_text_file_without_pages_can_be_approved(self):
        q = make_generated()
        q["source_page"] = None
        self.assertEqual(qb.approve_question(q, "לולאות", GAME_TOPICS)[0], "saved")

    def test_loading_skips_entries_that_are_not_valid_or_not_from_a_source(self):
        qb.approve_question(make_generated(1), "לולאות", GAME_TOPICS)
        stored = self.stored()
        no_source = copy.deepcopy(stored[0])
        no_source["id"] = "x-no-source"
        del no_source["source_quote"]
        wrong_topic = copy.deepcopy(stored[0])
        wrong_topic.update(id="x-wrong-topic", game_topic="לא קיים", topic="לא קיים")
        self.path.write_text(json.dumps({"version": 1, "questions": stored + [no_source, wrong_topic, "junk"]}),
                             encoding="utf-8")
        ids = [q["id"] for q in qb.load_approved(game_topics=GAME_TOPICS)]
        self.assertEqual(ids, ["gen-abc123-1"])

    def test_missing_file_means_nothing_approved(self):
        self.assertEqual(qb.load_approved(), [])
        self.assertEqual(qb.approved_ids(), set())


class DuplicateTests(TempFilesTestCase):
    def test_same_id_is_not_saved_twice(self):
        qb.approve_question(make_generated(1), "לולאות", GAME_TOPICS)
        status, message = qb.approve_question(make_generated(1), "לולאות", GAME_TOPICS)
        self.assertEqual(status, "duplicate")
        self.assertTrue(message)
        self.assertEqual(len(self.stored()), 1)

    def test_same_text_with_a_different_id_is_a_duplicate(self):
        qb.approve_question(make_generated(1, text="מה זה   לולאה?"), "לולאות", GAME_TOPICS)
        again = make_generated(2, text="  מה זה לולאה?  ")        # different id, spacing only
        self.assertEqual(qb.approve_question(again, "פונקציות", GAME_TOPICS)[0], "duplicate")
        self.assertEqual(len(self.stored()), 1)

    def test_different_questions_are_both_saved(self):
        qb.approve_question(make_generated(1), "לולאות", GAME_TOPICS)
        qb.approve_question(make_generated(2), "מערכים", GAME_TOPICS)
        self.assertEqual(len(self.stored()), 2)

    def test_hand_edited_duplicate_ids_are_loaded_once(self):
        qb.approve_question(make_generated(1), "לולאות", GAME_TOPICS)
        one = self.stored()
        self.path.write_text(json.dumps({"version": 1, "questions": one + one}), encoding="utf-8")
        self.assertEqual(len(qb.load_approved()), 1)


class RejectTests(TempFilesTestCase):
    def test_rejecting_an_approved_question_removes_it(self):
        qb.approve_question(make_generated(1), "לולאות", GAME_TOPICS)
        qb.approve_question(make_generated(2), "מערכים", GAME_TOPICS)
        self.assertEqual(qb.reject_question("gen-abc123-1")[0], "removed")
        self.assertEqual([q["id"] for q in self.stored()], ["gen-abc123-2"])

    def test_rejecting_a_question_that_was_never_approved_writes_nothing(self):
        self.assertEqual(qb.reject_question("gen-abc123-9")[0], "not_found")
        self.assertFalse(self.path.exists())

    def test_a_rejected_question_can_be_approved_again(self):
        qb.approve_question(make_generated(1), "לולאות", GAME_TOPICS)
        qb.reject_question("gen-abc123-1")
        self.assertEqual(qb.approve_question(make_generated(1), "לולאות", GAME_TOPICS)[0], "saved")


class BrokenFileTests(TempFilesTestCase):
    def test_a_corrupt_file_is_never_overwritten(self):
        self.path.write_text("{ this is not json", encoding="utf-8")
        before = self.path.read_bytes()
        self.assertEqual(qb.approve_question(make_generated(), "לולאות", GAME_TOPICS)[0], "error")
        self.assertEqual(qb.reject_question("gen-abc123-1")[0], "error")
        self.assertEqual(self.path.read_bytes(), before)

    def test_the_game_falls_back_to_demo_when_the_file_is_corrupt(self):
        self.path.write_text("{ this is not json", encoding="utf-8")
        self.assertEqual(qb.get_game_questions(GAME_TOPICS)["mode"], qb.MODE_DEMO)

    def test_no_temporary_file_is_left_behind(self):
        qb.approve_question(make_generated(), "לולאות", GAME_TOPICS)
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["approved.json"])


class GameQuestionsTests(TempFilesTestCase):
    def test_demo_mode_when_nothing_is_approved(self):
        bank = qb.get_game_questions(GAME_TOPICS)
        self.assertEqual(bank["mode"], qb.MODE_DEMO)
        self.assertEqual(len(bank["questions"]), 24)
        self.assertTrue(bank["course"])
        qb.validate_questions(bank["questions"])                 # existing sample questions are still valid

    def test_demo_mode_with_an_empty_approved_file(self):
        self.path.write_text('{"version": 1, "questions": []}', encoding="utf-8")
        self.assertEqual(qb.get_game_questions(GAME_TOPICS)["mode"], qb.MODE_DEMO)

    def test_approved_questions_replace_the_sample_questions(self):
        qb.approve_question(make_generated(1), "לולאות", GAME_TOPICS)
        bank = qb.get_game_questions(GAME_TOPICS)
        self.assertEqual(bank["mode"], qb.MODE_APPROVED)
        self.assertEqual([q["id"] for q in bank["questions"]], ["gen-abc123-1"])   # no sample question mixed in
        self.assertEqual(bank["course"], qb.UPLOADED_COURSE_LABEL)

    def test_back_to_demo_after_the_last_question_is_rejected(self):
        qb.approve_question(make_generated(1), "לולאות", GAME_TOPICS)
        qb.reject_question("gen-abc123-1")
        self.assertEqual(qb.get_game_questions(GAME_TOPICS)["mode"], qb.MODE_DEMO)

    def test_explicit_paths_work_too(self):
        other = self.dir / "other.json"
        qb.approve_question(make_generated(1), "לולאות", GAME_TOPICS, path=other)
        self.assertEqual(qb.get_game_questions(GAME_TOPICS, approved=other)["mode"], qb.MODE_APPROVED)
        self.assertFalse(self.path.exists())


class GameCompatibilityTests(TempFilesTestCase):
    """Approved questions work in the real game rules without changing them."""

    def play_one_attack(self, game, answer_correctly):
        territory_id = gl.attackable_ids(game)[0]
        current = gl.start_attack(game, territory_id)
        question = current["question"]
        answer = question["correct_answer"] if answer_correctly else next(
            o for o in current["options"] if o != question["correct_answer"])
        owner_before = gl.get_territory(game, territory_id)["owner"]
        result = gl.submit_answer(game, answer)
        return territory_id, owner_before, result

    def test_correct_answer_on_an_approved_question_captures_the_territory(self):
        for n, topic in enumerate(GAME_TOPICS, start=1):
            qb.approve_question(make_generated(n), topic, GAME_TOPICS)
        game = gl.new_game(qb.get_game_questions(GAME_TOPICS)["questions"])
        territory_id, _, result = self.play_one_attack(game, True)
        self.assertTrue(result["correct"])
        self.assertEqual(gl.get_territory(game, territory_id)["owner"], gl.PLAYER)
        self.assertTrue(result["question"].startswith("מה מדפיסה"))

    def test_wrong_answer_does_not_capture(self):
        qb.approve_question(make_generated(1), "לולאות", GAME_TOPICS)
        game = gl.new_game(qb.get_game_questions(GAME_TOPICS)["questions"])
        territory_id, owner_before, result = self.play_one_attack(game, False)
        self.assertFalse(result["correct"])
        self.assertNotEqual(gl.get_territory(game, territory_id)["owner"], gl.PLAYER)

    def test_one_approved_question_is_enough_to_play_a_full_game(self):
        qb.approve_question(make_generated(1), "לולאות", GAME_TOPICS)
        game = gl.new_game(qb.get_game_questions(GAME_TOPICS)["questions"])
        while not game["over"] and game["actions_left"] > 0:
            if game["current"] is not None:
                gl.submit_answer(game, game["current"]["options"][0])
            else:
                gl.start_attack(game, gl.attackable_ids(game)[0])
        self.assertLessEqual(game["attacks"], gl.MAX_ACTIONS)

    def test_the_answer_log_accepts_an_approved_question(self):
        qb.approve_question(make_generated(1), "לולאות", GAME_TOPICS)
        question = qb.load_approved()[0]
        record = attempts.build_record("s", "p", 1, question, "ב", True, 1500)
        self.assertEqual(record["question_id"], "gen-abc123-1")
        self.assertEqual(record["topic"], "לולאות")
        status, _ = attempts.save_attempt("s", "p", 1, question, "ב", True, 1500)   # goes to the temporary file
        self.assertEqual(status, "saved")
        self.assertTrue((self.dir / "attempts.jsonl").exists())


class AppModeTests(TempFilesTestCase):
    """start_game in the real app uses the right question source."""

    def start(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
        self.assertFalse(at.exception)
        at.button(key="start_game").click().run()
        self.assertFalse(at.exception)
        return at

    def test_demo_mode_is_marked(self):
        at = self.start()
        self.assertEqual(at.session_state["question_mode"], qb.MODE_DEMO)
        self.assertEqual(len(at.session_state["game"]["questions"]), 24)
        self.assertIn("מצב הדגמה", " ".join(m.value for m in at.markdown))

    def test_approved_mode_uses_only_approved_questions(self):
        qb.approve_question(make_generated(1), "לולאות", GAME_TOPICS)
        qb.approve_question(make_generated(2), "מערכים", GAME_TOPICS)
        at = self.start()
        self.assertEqual(at.session_state["question_mode"], qb.MODE_APPROVED)
        ids = {q["id"] for q in at.session_state["game"]["questions"]}
        self.assertEqual(ids, {"gen-abc123-1", "gen-abc123-2"})
        self.assertNotIn("שאלות לדוגמה", " ".join(m.value for m in at.markdown if "chip" in m.value))


if __name__ == "__main__":
    unittest.main()
