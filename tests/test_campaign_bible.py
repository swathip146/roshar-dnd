"""
The campaign bible — plan 0.19, the last open Phase-0 item.

RAG only surfaces what you think to query, and the scenario prompt had sections
for narrative, location, quests, policy and RAG — and NOTHING about the campaign.
The DM never saw who the party were, which NPCs mattered, what the three acts
were, or how the campaign ends, so it improvised all of that every turn and the
story had no spine.

Plan 0.19 asked for a hand-authored markdown file. This DERIVES the bible from the
structured campaign instead, because a hand-authored file is a second source of
truth that drifts: `shards_of_honor.json` already carries the acts, quests, NPCs,
locations and endgame (schema 2.1, D2), and the party lives in CharacterManager.
An optional `bible.md` is still appended for anything the schema cannot express.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

pytestmark = [pytest.mark.unit]

from components.campaign_bible import (MAX_BIBLE_CHARS, CampaignBible,
                                       build_campaign_bible)
from components.character_manager import CharacterManager
from components.game_engine import GameEngine

CAMPAIGN = {
    "title": "Shards of Honor",
    "setting": "Roshar, the kingdom of Vedens",
    "theme": "Epic Fantasy",
    "level_range": "1-10",
    "overview": "Newly awakened Knights Radiant must prevent a conquest.",
    "acts": [
        {"title": "The First Oath", "description": "Bond a spren under attack."},
        {"title": "The Three Artifacts", "description": "Retrieve three relics."},
        {"title": "The Ritual", "description": "A massive battle."},
    ],
    "key_npcs": [
        {"name": "Kalak the Herald", "role": "Mentor",
         "description": "One of the ten Heralds."},
        {"name": "Nale the Herald", "role": "Antagonist",
         "description": "Hunts Radiants."},
    ],
    "locations": [{"name": "Kholinar"}, {"name": "The Shattered Plains"}],
    "endgame": {"description": "The Ritual is stopped and Odium is bound."},
}


@pytest.fixture
def engine():
    engine = GameEngine()
    engine.add_character({
        "character_id": "Aggi", "name": "Aggi", "level": 3,
        "ability_scores": {"strength": 14, "dexterity": 13, "constitution": 12,
                           "intelligence": 8, "wisdom": 10, "charisma": 13},
        "hit_points": {"current": 8, "maximum": 24, "temporary": 0},
        "armor_class": 14, "character_class": "Radiant", "race": "Alethi",
        "background": "Folk Hero",
    })
    return engine


def _bible(engine=None, campaign=CAMPAIGN):
    return build_campaign_bible(
        campaign=campaign,
        character_manager=getattr(engine, "character_manager", None),
        game_engine=engine)


class TestTheSpineIsPresent:
    def test_the_title_and_setting(self):
        text = _bible()
        assert "Shards of Honor" in text
        assert "Roshar" in text

    def test_every_act_appears(self):
        """Without the acts the DM cannot tell where the story is going."""
        text = _bible()
        for act in ("The First Oath", "The Three Artifacts", "The Ritual"):
            assert act in text, f"{act} is missing from the bible"

    def test_key_npcs_appear_with_their_roles(self):
        text = _bible()
        assert "Kalak the Herald" in text and "Mentor" in text
        assert "Nale the Herald" in text

    def test_the_dm_is_told_not_to_replace_the_npcs(self):
        """The failure mode is inventing a new mentor instead of using Kalak."""
        assert "do not invent" in _bible().lower()

    def test_the_endgame_appears(self):
        """D2: the DM must know what it is building towards."""
        assert "Odium is bound" in _bible()

    def test_established_locations_appear(self):
        text = _bible()
        assert "Kholinar" in text and "The Shattered Plains" in text

    def test_the_bible_declares_itself_authoritative(self):
        assert "do not contradict" in _bible().lower()


class TestLiveStateIsPresent:
    """
    Static campaign text alone would let the DM narrate a healthy party while a
    character was dying. The live half must be there and must be current.
    """

    def test_the_party_appears_with_hp(self, engine):
        text = _bible(engine)
        assert "Aggi" in text
        assert "8/24" in text, f"live HP is missing from the bible:\n{text}"

    def test_the_level_and_class_appear(self, engine):
        text = _bible(engine)
        assert "level 3" in text and "Radiant" in text

    def test_a_dying_character_is_flagged(self, engine):
        engine.character_manager.characters["Aggi"].hit_points["current"] = 0
        assert "DYING" in _bible(engine)

    def test_a_dead_character_is_flagged(self, engine):
        character = engine.character_manager.characters["Aggi"]
        character.hit_points["current"] = 0
        character.is_dead = True
        assert "DEAD" in _bible(engine)

    def test_the_current_location_appears(self, engine):
        engine.set_location("Kholinar")
        assert "Kholinar" in _bible(engine)

    def test_open_objectives_appear(self, engine):
        engine.game_state.quest_context["pending_objectives"] = [
            {"text": "Survive the Voidbringer attack"}]
        assert "Survive the Voidbringer attack" in _bible(engine)

    def test_the_game_clock_appears(self, engine):
        """Highstorm timing drives real decisions on Roshar."""
        assert "highstorm" in _bible(engine).lower()

    def test_live_state_tracks_changes(self, engine):
        """A cached bible reporting yesterday's HP is worse than none."""
        first = _bible(engine)
        engine.character_manager.characters["Aggi"].hit_points["current"] = 24
        second = _bible(engine)
        assert first != second, "the bible is cached and no longer reflects state"
        assert "24/24" in second


class TestItIsBounded:
    """This goes into EVERY prompt, so its size must be predictable."""

    def test_a_normal_bible_is_within_budget(self, engine):
        assert len(_bible(engine)) <= MAX_BIBLE_CHARS

    def test_an_enormous_campaign_is_truncated(self, engine):
        huge = dict(CAMPAIGN)
        huge["overview"] = "x" * 50_000
        huge["acts"] = [{"title": f"Act {i}", "description": "y" * 2000}
                        for i in range(50)]
        huge["key_npcs"] = [{"name": f"NPC {i}", "description": "z" * 500}
                            for i in range(100)]
        assert len(_bible(engine, huge)) <= MAX_BIBLE_CHARS + 50

    def test_live_state_survives_truncation(self, engine):
        """
        Truncate the static half, never the live state: stale HP causes
        contradictions the player notices, a trimmed act summary only costs colour.
        """
        huge = dict(CAMPAIGN)
        huge["overview"] = "x" * 40_000
        text = _bible(engine, huge)
        assert "Aggi" in text, "the party was truncated out of the bible"


class TestItDegradesInsteadOfBreaking:
    def test_no_campaign_still_renders_the_party(self, engine):
        text = _bible(engine, campaign={})
        assert "Aggi" in text

    def test_no_engine_still_renders_the_campaign(self):
        assert "Shards of Honor" in _bible(engine=None)

    def test_nothing_at_all_returns_empty_not_an_error(self):
        assert build_campaign_bible(campaign=None) is not None

    def test_a_malformed_campaign_does_not_raise(self, engine):
        for broken in ({"acts": "not a list"}, {"key_npcs": [None, 42]},
                       {"endgame": "a string"}, {"locations": [{}]}):
            assert isinstance(_bible(engine, broken), str)

    def test_a_broken_character_manager_does_not_raise(self):
        class _Broken:
            @property
            def characters(self):
                raise RuntimeError("boom")

        assert isinstance(
            build_campaign_bible(campaign=CAMPAIGN,
                                 character_manager=_Broken()), str)


class TestItReachesThePrompt:
    """
    The step that separates this from four subsystems that were built and never
    called. A bible in state that never reaches the DM changes nothing.
    """

    def test_the_prompt_builder_injects_it(self):
        source = (PROJECT_ROOT / "agents"
                  / "scenario_generator_agent.py").read_text()
        assert "campaign_bible" in source
        assert "{campaign_bible" in source, (
            "the bible is built but never interpolated into the prompt")

    def test_the_helper_returns_real_content(self, engine):
        from agents.scenario_generator_agent import _campaign_bible_for

        text = _campaign_bible_for(engine)
        assert len(text) > 200, "the bible is empty for a live engine"
        assert "CAMPAIGN BIBLE" in text

    def test_the_helper_reads_the_authored_campaign(self, engine):
        """It must find the real campaign, not just a passed-in dict."""
        from agents.scenario_generator_agent import _campaign_bible_for

        text = _campaign_bible_for(engine)
        assert "Shards of Honor" in text, (
            "the authored campaign in data/current_campaign was not found")

    def test_the_helper_never_raises(self):
        from agents.scenario_generator_agent import _campaign_bible_for

        assert _campaign_bible_for(None) is not None
        assert _campaign_bible_for(object()) is not None
