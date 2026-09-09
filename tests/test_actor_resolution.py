"""
Actor-id resolution and empty-but-normal replies — found by scripts/playtest.py.

Two live-run failures:

1. "⚠️ roll_skill_check failed: 'breakdown'" — four times in one run.
   get_skill_data()'s unknown-character branch omitted the "breakdown" key,
   which game_engine's 7-step pipeline reads by direct subscript, so an
   unrecognised actor raised KeyError instead of degrading to a 0 modifier.
   The actor was unrecognised only because the LLM said "aggi" for "Aggi".

2. "❌ GEMINI EMPTY RESPONSE: finish_reason=STOP" — a REGRESSION I introduced
   when making empty replies raise. STOP means the model completed normally
   with nothing to add (legitimate after a tool-only turn); only MAX_TOKENS or
   SAFETY indicate a reply that was cut off.
"""

import pytest

from components.character_manager import CharacterManager
from components.game_engine import GameEngine


pytestmark = pytest.mark.unit


CHARACTER = {
    "character_id": "Aggi", "name": "Aggi", "level": 1,
    "ability_scores": {"strength": 8, "dexterity": 16, "constitution": 10,
                       "intelligence": 10, "wisdom": 12, "charisma": 14},
    "hit_points": {"current": 8, "maximum": 8, "temporary": 0},
    "armor_class": 14, "character_class": "Radiant", "race": "Alethi",
    "background": "Folk Hero", "skills": {"stealth": True},
}


@pytest.fixture
def engine():
    game_engine = GameEngine()
    game_engine.add_character(dict(CHARACTER))
    return game_engine


class TestSkillDataContract:
    """get_skill_data must always return every key the pipeline subscripts."""

    def test_unknown_character_still_has_breakdown(self):
        manager = CharacterManager()
        data = manager.get_skill_data("nobody", "perception")
        assert "breakdown" in data, \
            "game_engine reads char_data['breakdown'] directly — KeyError otherwise"
        assert data["modifier"] == 0

    def test_known_character_has_breakdown(self):
        manager = CharacterManager()
        manager.add_character(dict(CHARACTER))
        assert "breakdown" in manager.get_skill_data("Aggi", "stealth")

    def test_unknown_actor_degrades_instead_of_raising(self, engine):
        """The exact live failure: KeyError killed the whole skill check."""
        result = engine.process_skill_check(
            {"actor": "Nobody At All", "skill": "perception", "dc": 12,
             "context": {}})
        assert result["character_modifier"] == 0
        assert "success" in result


class TestActorResolution:
    """The LLM supplies whatever the narration used."""

    @pytest.mark.parametrize("actor", [
        "Aggi",                    # exact
        "aggi",                    # the live failure
        "AGGI",
        "  Aggi  ",
        "Aggi the Lightweaver",    # name inside a phrase
    ])
    def test_variants_resolve_to_the_real_character(self, engine, actor):
        result = engine.process_skill_check(
            {"actor": actor, "skill": "perception", "dc": 12, "context": {}})
        # DEX 16 / WIS 12 -> a real modifier, not the unknown-actor 0.
        assert result["character_modifier"] != 0, f"{actor!r} did not resolve"

    def test_resolve_returns_canonical_id(self):
        manager = CharacterManager()
        manager.add_character(dict(CHARACTER))
        assert manager.resolve_character_id("aggi") == "Aggi"
        assert manager.resolve_character_id("Aggi the Lightweaver") == "Aggi"

    def test_resolve_rejects_non_matches(self):
        manager = CharacterManager()
        manager.add_character(dict(CHARACTER))
        assert manager.resolve_character_id("Dalinar") is None
        assert manager.resolve_character_id("") is None
        assert manager.resolve_character_id(None) is None

    def test_single_letter_does_not_match_everything(self):
        """Substring matching would map 'a' onto 'Aggi'."""
        manager = CharacterManager()
        manager.add_character(dict(CHARACTER))
        assert manager.resolve_character_id("a") is None


class TestEmptyButNormalReply:
    """finish_reason=STOP is success, not failure."""

    def _generator_with(self, monkeypatch, finish_name):
        from config.llm_utils import GeminiChatGenerator

        class _Content:
            parts = None

        class _Candidate:
            content = _Content()
            finish_reason = type("R", (), {"name": finish_name})()

        class _Response:
            candidates = [_Candidate()]
            prompt_feedback = None
            text = ""

        generator = GeminiChatGenerator(
            model_name="gemini-2.5-flash", generation_config={})

        class _FakeModels:
            def generate_content(self, model, contents, config):
                return _Response()

        class _FakeClient:
            models = _FakeModels()

        monkeypatch.setattr(generator, "client", _FakeClient())
        return generator

    def test_stop_with_no_text_does_not_raise(self, monkeypatch):
        """A tool-only turn legitimately produces no prose."""
        from haystack.dataclasses import ChatMessage

        generator = self._generator_with(monkeypatch, "STOP")
        result = generator.run(messages=[ChatMessage.from_user("hi")])
        assert result["replies"][0].text == ""

    @pytest.mark.parametrize("finish", ["MAX_TOKENS", "SAFETY", "RECITATION"])
    def test_truncated_or_filtered_still_raises(self, monkeypatch, finish):
        from config.llm_utils import GeminiAPIError
        from haystack.dataclasses import ChatMessage

        generator = self._generator_with(monkeypatch, finish)
        with pytest.raises(GeminiAPIError, match=finish):
            generator.run(messages=[ChatMessage.from_user("hi")])
