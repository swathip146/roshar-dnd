"""
play_turn() must actually route through the LangGraph durable loop.

components/durable_turns.py was built and tested in Phase 3, but NOTHING
imported it — `grep -rn DurableTurnLoop` outside its own module matched only
tests, and play_turn() called the orchestrator directly. The migration was
built, not adopted, so Phase 3's "durable turns" claim was not true of the
running game.

These tests assert on the wiring itself, not just on the component in isolation:
the loop is used, the turn logic is not duplicated, and a turn genuinely
survives into a new DurableTurnLoop instance keyed only by thread_id.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _build_game(checkpoint_db=None, scene="A cold wind crosses the plateau."):
    """checkpoint_db=None uses the loop's default location."""
    """A game with a stubbed orchestrator, so this tests WIRING not the LLM."""
    from haystack_dnd_game import HaystackDnDGame
    from components.game_engine import GameEngine

    game = HaystackDnDGame.__new__(HaystackDnDGame)
    game.game_engine = GameEngine()
    game.game_engine.add_character({
        "character_id": "Aggi", "name": "Aggi", "level": 1,
        "ability_scores": {"strength": 10, "dexterity": 14, "constitution": 10,
                           "intelligence": 10, "wisdom": 10, "charisma": 10},
        "hit_points": {"current": 8, "maximum": 8, "temporary": 0},
        "armor_class": 12, "character_class": "Radiant", "race": "Alethi",
        "background": "Folk Hero",
    })
    game.character_manager = game.game_engine.character_manager
    game.policy_engine = game.game_engine.policy_engine
    game.current_choices = []
    game.turn_counter = 0
    game.dnd_engine_wrapper = None

    class _Session:
        save_directory = "/tmp"

        def get_session_metadata(self):
            return {"session_id": "wiring-test", "session_active": True}

        def record_turn_analytics(self, *a, **k):
            return None

        def record_routing_decision(self, *a, **k):
            return None

    game.session_manager = _Session()

    class _Orchestrator:
        calls = 0

        def process_request(self, dto):
            _Orchestrator.calls += 1
            return {"success": True, "response_type": "scenario",
                    "scenario": {"scene": scene, "choices": []}}

    game.orchestrator = _Orchestrator()

    if checkpoint_db is not None:
        from components.durable_turns import DurableTurnLoop
        game._turn_loop = DurableTurnLoop(on_resolve=game._resolve_turn_state,
                                          checkpoint_db=checkpoint_db)
    return game


class TestLoopIsActuallyUsed:

    def test_play_turn_goes_through_the_durable_loop(self, tmp_path, monkeypatch):
        """The regression: play_turn() used to bypass LangGraph entirely."""
        from components.durable_turns import DurableTurnLoop

        started = []
        original = DurableTurnLoop.start

        def spy(self, thread_id, **kwargs):
            started.append((thread_id, kwargs.get("player_input")))
            return original(self, thread_id, **kwargs)

        monkeypatch.setattr(DurableTurnLoop, "start", spy)

        game = _build_game(tmp_path / "turns.sqlite")
        narration = game.play_turn("I look around")

        assert started == [("wiring-test", "I look around")], \
            "play_turn did not route through DurableTurnLoop"
        assert "cold wind" in narration

    def test_play_turn_still_returns_a_string(self, tmp_path):
        """The CLI and every existing caller depend on this signature."""
        game = _build_game(tmp_path / "turns.sqlite")
        assert isinstance(game.play_turn("I look around"), str)

    def test_turn_logic_is_not_duplicated(self):
        """The direct fallback must BE resolve_turn, not a copy of it."""
        from haystack_dnd_game import HaystackDnDGame
        assert HaystackDnDGame._play_turn_direct is HaystackDnDGame.resolve_turn

    def test_blank_input_is_rejected_before_the_graph(self, tmp_path):
        game = _build_game(tmp_path / "turns.sqlite")
        assert game.play_turn("   ") == "The world waits for your action..."
        assert game.orchestrator.calls == 0


class TestFallbackWithoutLangGraph:

    def test_turn_still_resolves_when_the_loop_is_unavailable(self, tmp_path):
        """A missing LangGraph must degrade, not stop play."""
        game = _build_game(tmp_path / "turns.sqlite")
        game._turn_loop = None
        monkey = lambda self: None
        game._durable_loop = monkey.__get__(game)

        narration = game.play_turn("I look around")
        assert "cold wind" in narration


class TestUiAgnosticApi:
    """D4: the pending action is returned as DATA, not blocked on."""

    def test_begin_turn_without_input_interrupts(self, tmp_path):
        game = _build_game(tmp_path / "turns.sqlite")
        result = game.begin_turn()
        assert result["status"] == "awaiting_input"
        assert result["awaiting_input_for"] == "Aggi"
        assert result["prompt"]

    def test_begin_turn_with_input_resolves(self, tmp_path):
        game = _build_game(tmp_path / "turns.sqlite")
        result = game.begin_turn("I look around")
        assert result["status"] == "ok"
        assert "cold wind" in result["narration"]

    def test_resume_completes_a_paused_turn(self, tmp_path):
        game = _build_game(tmp_path / "turns.sqlite")
        assert game.begin_turn()["status"] == "awaiting_input"
        resumed = game.resume_turn("I look around")
        assert resumed["status"] == "ok"
        assert "cold wind" in resumed["narration"]


class TestSurvivesProcessExit:
    """
    The actual point of D4: resume in a DIFFERENT PROCESS.

    A game turn blocks on a human for minutes or days, so turn state must
    outlive the process. This runs two separate interpreters against one
    checkpoint file — the second has nothing in memory from the first.
    """

    PROBE = '''
import json, sys
sys.path.insert(0, {root!r})
sys.argv = ["probe"]
from tests.test_durable_turn_wiring import _build_game
game = _build_game({db!r})
phase = {phase!r}
if phase == "pause":
    r = game.begin_turn()
    print(json.dumps({{"status": r.get("status"),
                       "awaiting": r.get("awaiting_input_for")}}))
else:
    r = game.resume_turn("I look around")
    print(json.dumps({{"status": r.get("status"),
                       "narration": r.get("narration") or ""}}))
'''

    def _run(self, phase, db):
        code = self.PROBE.format(root=str(PROJECT_ROOT), db=str(db), phase=phase)
        finished = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=180,
                                  cwd=str(PROJECT_ROOT))
        lines = [l for l in finished.stdout.splitlines() if l.startswith("{")]
        assert lines, f"probe produced no result:\n{finished.stdout}\n{finished.stderr}"
        return json.loads(lines[-1])

    def test_turn_paused_in_one_process_resumes_in_another(self, tmp_path):
        db = tmp_path / "xproc.sqlite"

        paused = self._run("pause", db)
        assert paused["status"] == "awaiting_input"
        assert paused["awaiting"] == "Aggi"

        # A brand-new interpreter, keyed only by thread_id.
        resumed = self._run("resume", db)
        assert resumed["status"] == "ok", \
            "the turn did not survive process exit"
        assert "cold wind" in resumed["narration"]

    def test_checkpoint_file_is_actually_written(self, tmp_path):
        db = tmp_path / "xproc.sqlite"
        self._run("pause", db)
        assert db.exists() and db.stat().st_size > 0
