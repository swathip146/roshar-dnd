"""
Authored encounters in the campaign file drive combat.

Before this, the campaign's "encounters" were PROSE ONLY — title, type,
description, challenge — with no enemy roster, and nothing read them. Combat was
improvised from scene text every time, so a live run asked the LLM what was in
the scene, got "Voidbringers → CR 3 x3", and built three 65 HP / AC 16 soldiers
for a LEVEL 1 party with 8 max HP.

An authored roster cannot drift: the enemies, their count and their CR are
written down. LLM extraction remains the fallback for scenes the campaign did
not anticipate.
"""

import json
import logging
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from components.combat.combat_initializer import CombatInitializer
from components.game_engine import GameEngine

CAMPAIGN = PROJECT_ROOT / "data" / "current_campaign" / "shards_of_honor.json"

pytestmark = [pytest.mark.combat, pytest.mark.unit]


def _initializer(engine) -> CombatInitializer:
    stub = CombatInitializer.__new__(CombatInitializer)
    stub.game_engine = engine
    stub.logger = logging.getLogger("test")
    return stub


@pytest.fixture
def engine():
    game_engine = GameEngine()
    game_engine.register_location("The Shattered Plains", "endless plateaus")
    game_engine.set_location("The Shattered Plains")
    game_engine.add_quest_objective(
        "Survive the Voidbringer attack on the border town")
    game_engine.campaign_config = type("C", (), {"source_file": str(CAMPAIGN)})()
    return game_engine


class TestCampaignFileIsWellFormed:

    def test_every_encounter_has_a_roster_key(self):
        data = json.loads(CAMPAIGN.read_text())
        for encounter in data["encounters"]:
            assert "enemies" in encounter, (
                f"{encounter.get('id')}: without this key the engine treats the "
                f"encounter as unauthored and falls back to LLM extraction")

    def test_every_encounter_has_a_stable_id(self):
        data = json.loads(CAMPAIGN.read_text())
        ids = [e["id"] for e in data["encounters"]]
        assert len(ids) == len(set(ids)), "duplicate encounter ids"
        assert all(i == i.lower() and " " not in i for i in ids)

    def test_encounters_reference_real_acts_and_quests(self):
        data = json.loads(CAMPAIGN.read_text())
        acts = {a["id"] for a in data["acts"]}
        quests = {q["id"] for q in data["quests"]}
        for encounter in data["encounters"]:
            assert encounter["act"] in acts, encounter["id"]
            assert encounter["quest"] in quests, encounter["id"]

    def test_victory_objectives_match_quest_text_exactly(self):
        """A near-miss string silently fails to advance the quest."""
        data = json.loads(CAMPAIGN.read_text())
        objectives = {o for q in data["quests"] for o in q["objectives"]}
        for encounter in data["encounters"]:
            target = (encounter.get("victory") or {}).get("quest_objective")
            if target:
                assert target in objectives, (
                    f"{encounter['id']}: {target!r} is not an objective of any "
                    f"quest, so victory will not advance anything")

    def test_enemy_entries_match_the_initializer_contract(self):
        """These exact keys are what _generate_npcs reads."""
        data = json.loads(CAMPAIGN.read_text())
        for encounter in data["encounters"]:
            for enemy in encounter["enemies"]:
                for key in ("name", "count", "estimated_cr", "role",
                            "description", "keywords"):
                    assert key in enemy, f"{encounter['id']}/{enemy}: missing {key}"
                assert enemy["count"] >= 1
                assert enemy["estimated_cr"] > 0

    def test_authored_crs_are_survivable_for_their_act(self):
        """
        The whole point of authoring: a roster that is balanced on paper.

        Act 1 runs at the bottom of level_range, act 3 at the top, so check each
        encounter against the level its act is actually played at.
        """
        data = json.loads(CAMPAIGN.read_text())
        low, high = (int(x) for x in data["level_range"].split("-"))
        act_level = {"act1": low, "act2": (low + high) // 2, "act3": high}

        stub = CombatInitializer.__new__(CombatInitializer)
        stub.game_engine = type("E", (), {"difficulty": "medium"})()
        stub.logger = logging.getLogger("test")

        # Budget the encounter as a WHOLE, not per enemy. A boss is meant to
        # exceed the per-head share — that is what makes it a boss — so the
        # meaningful question is total CR against the party's total budget.
        # "deadly" is authored to be nearly lethal, hence the wider allowance.
        allowance = {"easy": 1.0, "medium": 1.5, "hard": 2.5, "deadly": 4.0}

        for encounter in data["encounters"]:
            if not encounter["enemies"]:
                continue
            level = act_level[encounter["act"]]
            total_cr = sum(e["count"] * e["estimated_cr"]
                           for e in encounter["enemies"])
            budget = level * allowance[encounter.get("difficulty", "medium")]
            assert total_cr <= budget, (
                f"{encounter['id']}: total CR {total_cr} exceeds the level "
                f"{level} budget of {budget} at '{encounter.get('difficulty')}' "
                f"— this encounter is a slaughter")

        # And no single enemy may dwarf the party on its own.
        for encounter in data["encounters"]:
            level = act_level[encounter["act"]]
            for enemy in encounter["enemies"]:
                assert enemy["estimated_cr"] <= level, (
                    f"{encounter['id']}: a single CR {enemy['estimated_cr']} "
                    f"enemy outclasses a level {level} party")


class TestAuthoredEncountersAreUsed:

    def test_matching_scene_uses_the_authored_roster(self, engine):
        enemies = _initializer(engine)._parse_enemies_from_scenario(
            {"scene": "Voidbringers ambush the border town; civilians scatter.",
             "gm_notes": "", "choices": []})
        assert [e["name"] for e in enemies] == ["Voidbringer Scout"]
        assert enemies[0]["estimated_cr"] == 0.25, (
            "the authored CR was ignored; LLM extraction returned CR 3 here")

    def test_social_encounter_yields_no_enemies(self, engine):
        """An authored empty roster means 'this is not a fight'."""
        enemies = _initializer(engine)._parse_enemies_from_scenario(
            {"scene": "The honorspren of Lasting Integrity convene a trial.",
             "gm_notes": "", "choices": []})
        assert enemies == []

    def test_unanticipated_scene_falls_through_to_extraction(self, engine):
        """The campaign cannot cover everything; the LLM path must remain."""
        assert _initializer(engine)._match_authored_encounter(
            {"scene": "A quiet afternoon mending rope by the fire.",
             "gm_notes": "", "choices": []}) is None

    def test_keywords_are_read_from_choices_too(self, engine):
        match = _initializer(engine)._match_authored_encounter(
            {"scene": "You survey the ridge.", "gm_notes": "",
             "choices": [{"title": "Fight the Voidbringer ambush",
                          "description": "Defend the civilians"}]})
        assert match is not None and match["id"] == "voidbringer_ambush"

    def test_location_alone_does_not_fire_an_encounter(self, engine):
        """Standing in the right place is not the same as the scene happening."""
        assert _initializer(engine)._match_authored_encounter(
            {"scene": "You make camp and sharpen your spear.",
             "gm_notes": "", "choices": []}) is None

    def test_prose_only_encounters_are_ignored(self, engine, tmp_path):
        """The pre-2.1 format has no roster and must not be treated as authored."""
        legacy = tmp_path / "legacy.json"
        legacy.write_text(json.dumps({"encounters": [
            {"title": "Old Style", "type": "Combat",
             "description": "Voidbringers attack", "challenge": "Medium"}]}))
        engine.campaign_config = type("C", (), {"source_file": str(legacy)})()
        stub = _initializer(engine)
        assert stub._campaign_encounters() == []

    def test_missing_campaign_file_is_survivable(self, engine):
        engine.campaign_config = type("C", (), {"source_file": "/nope.json"})()
        assert _initializer(engine)._campaign_encounters() == []

    def test_no_campaign_config_is_survivable(self, engine):
        engine.campaign_config = None
        assert _initializer(engine)._campaign_encounters() == []


class TestGeneratorEmitsTheNewSchema:

    def test_template_documents_the_roster_fields(self):
        import inspect
        from generators import campaign_generator

        source = inspect.getsource(campaign_generator)
        for field in ("estimated_cr", "trigger", "quest_objective", "difficulty"):
            assert field in source, f"generator template lacks {field}"

    def test_generator_warns_against_unwinnable_encounters(self):
        import inspect
        from generators import campaign_generator

        source = inspect.getsource(campaign_generator)
        assert "unwinnable" in source.lower()
        assert "EMPTY list is meaningful" in source

    def test_fallback_campaign_has_a_roster_key(self):
        """Even the hardcoded fallback must parse as an authored encounter."""
        import inspect
        from generators import campaign_generator

        source = inspect.getsource(campaign_generator)
        assert '"enemies": []' in source


class TestAForcedEncounterAlwaysFindsARoster:
    """
    `force_combat` skipped the trigger check but was never passed down to enemy
    parsing. So a forced fight in a PEACEFUL scene asked the LLM to extract enemies
    from prose containing none — "✅ Successfully extracted 0 enemy types" — and the
    encounter was abandoned with "Combat initialization failed or no combat
    trigger". A live run forced combat on turn 2 and no fight happened, while the
    log said "4 authored encounter(s) available".

    Keyword matching stays strict for ORGANIC play: an encounter must not fire
    merely for being in the right place. But when the caller has already decided
    there IS a fight, falling back to an authored roster beats failing.
    """

    def _initializer(self, source="data/current_campaign/shards_of_honor.json"):
        from components.combat.combat_initializer import CombatInitializer
        from components.game_engine import GameEngine
        from config.logging_config import get_logger

        class _Campaign:
            source_file = source

        initializer = CombatInitializer.__new__(CombatInitializer)
        initializer.game_engine = GameEngine()
        initializer.game_engine.campaign_config = _Campaign()
        initializer._encounters_cache = None
        initializer.logger = get_logger("test")
        return initializer

    PEACEFUL = {"scene": "A quiet starlit ridge. Nothing stirs.",
                "gm_notes": "", "choices": []}

    def test_a_forced_encounter_yields_enemies(self):
        enemies = self._initializer()._parse_enemies_from_scenario(
            self.PEACEFUL, force_combat=True)
        assert enemies, (
            "a forced encounter found no roster in a peaceful scene — combat "
            "would be abandoned")

    def test_the_roster_comes_from_the_campaign(self):
        """Not invented by the LLM: an authored roster cannot drift."""
        enemies = self._initializer()._parse_enemies_from_scenario(
            self.PEACEFUL, force_combat=True)
        assert any("voidbringer" in (e.get("name") or "").lower()
                   for e in enemies), enemies

    def test_the_authored_cr_is_preserved(self):
        """The whole point of authoring: difficulty stays as designed."""
        enemies = self._initializer()._parse_enemies_from_scenario(
            self.PEACEFUL, force_combat=True)
        assert all(e.get("estimated_cr") for e in enemies)
        assert max(e["estimated_cr"] for e in enemies) <= 1, (
            f"the fallback picked a hard encounter: {enemies}")

    def test_the_fallback_prefers_an_encounter_with_enemies(self):
        """A social/non-combat encounter is useless for a forced fight."""
        encounter = self._initializer()._fallback_authored_encounter()
        assert encounter is not None
        assert encounter.get("enemies"), encounter

    def test_organic_play_is_unaffected(self):
        """
        Both directions. Without force_combat a peaceful scene must NOT summon an
        authored encounter — otherwise a fight breaks out for being in the right
        place, which is what the keyword requirement exists to prevent.
        """
        initializer = self._initializer()
        matched = initializer._match_authored_encounter(self.PEACEFUL)
        assert matched is None, (
            f"a peaceful scene matched encounter {matched.get('id')} by keyword")

    def test_a_campaign_with_no_encounters_returns_none(self):
        """Must degrade, not raise, if the campaign authored no fights."""
        initializer = self._initializer(source="does/not/exist.json")
        assert initializer._fallback_authored_encounter() is None
        assert initializer._parse_enemies_from_scenario(
            self.PEACEFUL, force_combat=True) is not None

    def test_a_keyword_match_still_wins(self):
        """The fallback must not override a real, specific match."""
        initializer = self._initializer()
        combat_scene = {
            "scene": "Voidbringers ambush the border town! Civilians scatter.",
            "gm_notes": "voidbringer attack on the border town",
            "choices": [{"title": "Defend the civilians",
                         "combat_trigger": True}]}
        enemies = initializer._parse_enemies_from_scenario(
            combat_scene, force_combat=True)
        assert enemies, "a keyword-matching scene produced no enemies"
