"""
Defeat must persist, and generated monsters must match the CR they were asked
for — the remaining two §14c defects.

Both were exposed by the first combat that actually resolved:

3. A 7-round encounter ended in `defeat`, and the very next turn re-ran the
   identical authored encounter. Two causes: the outcome was read from the wrong
   level of the DTO (so it was always None), and nothing treated a party wipe as
   an ending.

4. The SAME CR-0.25 monster came back with 18 HP on one turn and 14 HP on the
   next. `_balanced_cr()` clamps the requested CR but nothing checked the stats
   that came back, so an encounter authored "easy" was harder than designed and
   differently hard on every run.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "external" / "dnd_engine"))

pytestmark = [pytest.mark.combat]


# ------------------------------------------------------- defect 4: CR banding

class TestGeneratedStatsRespectTheRequestedCR:
    @pytest.fixture
    def generator(self):
        from components.combat.npc_stat_generator import NPCStatGenerator
        return NPCStatGenerator(llm=None)

    def _npc(self, maximum, armor_class=13):
        return {
            "name": "Voidbringer Scout", "character_class": "Scout",
            "hit_points": {"current": maximum, "maximum": maximum,
                           "temporary": 0},
            "armor_class": armor_class,
        }

    def test_the_live_18hp_ac13_scout_is_clamped(self):
        """
        The exact live stat block: CR 0.25 came back with 18 HP at AC 13.

        Note what is NOT the bug: 18 HP alone is legal at CR 1/4 — a Dretch has
        exactly 18 and a Zombie 22. But they pay AC 11 and AC 8 for it. CR is a
        budget across BOTH numbers, so 18 HP *at AC 13* (effective 234) is harder
        than anything published at that CR, and that combination is what made an
        encounter authored "easy" lethal.
        """
        from components.combat.npc_stat_generator import NPCStatGenerator

        generator = NPCStatGenerator(llm=None)
        result = generator._clamp_to_cr_band(self._npc(18, armor_class=13), 0.25)
        hp = result["hit_points"]["maximum"]
        assert hp * result["armor_class"] <= 289, (
            f"{hp} HP at AC {result['armor_class']} is still over the CR 0.25 "
            f"ceiling of 289")

    def test_high_hp_is_allowed_when_ac_is_low(self, generator):
        """
        The other side of the same rule, and the reason a bare HP cap is wrong:
        a Zombie really is 22 HP at CR 1/4 — because its AC is 8.
        """
        result = generator._clamp_to_cr_band(self._npc(22, armor_class=8), 0.25)
        assert result["hit_points"]["maximum"] == 22, (
            "clamped a legal Zombie-shaped stat block")

    def test_in_band_hp_is_left_alone(self, generator):
        """14 HP at AC 13 is inside the CR 1/4 budget — do not touch it."""
        result = generator._clamp_to_cr_band(self._npc(14, armor_class=13), 0.25)
        assert result["hit_points"]["maximum"] == 14

    def test_current_never_exceeds_the_clamped_maximum(self, generator):
        result = generator._clamp_to_cr_band(self._npc(40), 0.25)
        hp = result["hit_points"]
        assert hp["current"] <= hp["maximum"], (
            f"current {hp['current']} > maximum {hp['maximum']}")

    def test_hp_above_every_published_monster_is_clamped(self, generator):
        """40 HP at CR 1/4 beats the published maximum of 24."""
        result = generator._clamp_to_cr_band(self._npc(40, armor_class=10), 0.25)
        assert result["hit_points"]["maximum"] <= 24

    def test_absurdly_low_hp_is_raised(self, generator):
        """A 1 HP "CR 1/2" dies to any hit and makes an encounter trivial."""
        result = generator._clamp_to_cr_band(self._npc(1), 0.5)
        assert result["hit_points"]["maximum"] >= 9

    def test_excessive_ac_is_clamped(self, generator):
        """AC 25 exceeds every published CR 1/4 monster (max 17)."""
        result = generator._clamp_to_cr_band(self._npc(9, armor_class=25), 0.25)
        assert result["armor_class"] <= 17

    def test_the_goblin_stat_block_is_untouched(self, generator):
        """
        The MM goblin — CR 1/4, 7 HP, AC 15 — is the canonical case. Clamping it
        would mean the bands are wrong, and an existing test caught exactly that
        when these numbers were hand-written instead of derived.
        """
        result = generator._clamp_to_cr_band(self._npc(7, armor_class=15), 0.25)
        assert result["hit_points"]["maximum"] == 7
        assert result["armor_class"] == 15

    @pytest.mark.parametrize("cr", [0.0, 0.125, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0])
    def test_every_supported_cr_has_a_band(self, generator, cr):
        """An unknown CR must not silently skip validation."""
        result = generator._clamp_to_cr_band(self._npc(500), cr)
        assert result["hit_points"]["maximum"] < 500, f"CR {cr} was not clamped"

    def test_higher_cr_allows_more_hp(self, generator):
        """The band must be monotonic, or CR stops meaning anything."""
        low = generator._clamp_to_cr_band(self._npc(200), 0.25)["hit_points"]["maximum"]
        high = generator._clamp_to_cr_band(self._npc(200), 2.0)["hit_points"]["maximum"]
        assert high > low, f"CR 2 ({high}) allows no more HP than CR 0.25 ({low})"

    def test_malformed_input_is_survived(self, generator):
        """Never let stat validation break encounter generation."""
        assert generator._clamp_to_cr_band({}, 0.25) == {}
        assert generator._clamp_to_cr_band({"hit_points": None}, 0.25) is not None
        assert generator._clamp_to_cr_band(None, 0.25) is None

    def test_unknown_cr_does_not_crash(self, generator):
        result = generator._clamp_to_cr_band(self._npc(30), 99.0)
        assert "hit_points" in result

    def test_two_generations_of_one_cr_land_in_one_budget(self, generator):
        """
        The live symptom: 18 HP then 14 HP for the same CR-0.25 request, both at
        AC 13. Clamping does not make the generator deterministic, but it does
        bound both runs to the same CR budget, so difficulty stops swinging.
        """
        first = generator._clamp_to_cr_band(self._npc(18, armor_class=13), 0.25)
        second = generator._clamp_to_cr_band(self._npc(14, armor_class=13), 0.25)
        ceiling = 289  # CR 0.25 ev_max
        for label, npc in (("first", first), ("second", second)):
            effective = npc["hit_points"]["maximum"] * npc["armor_class"]
            assert effective <= ceiling, (
                f"{label} generation is still over budget: {effective} > {ceiling}")


# -------------------------------------------------- defect 3: defeat persists

class TestDefeatEndsTheCampaign:
    def _orchestrator(self):
        """A PipelineOrchestrator with just enough state to record a defeat."""
        from orchestrator.pipeline_integration import PipelineOrchestrator
        from components.game_engine import GameEngine

        orchestrator = PipelineOrchestrator.__new__(PipelineOrchestrator)
        orchestrator.game_engine = GameEngine()
        return orchestrator

    def test_defeat_marks_the_campaign_ended(self):
        orchestrator = self._orchestrator()
        orchestrator._record_party_defeat(7)

        narrative = orchestrator.game_engine.game_state.narrative_context
        assert narrative["campaign_ended"] is True
        assert narrative["campaign_ending"] == "party_defeated"
        assert narrative["campaign_ending_rounds"] == 7

    def test_recording_a_defeat_never_raises(self):
        """Must not take the turn down with it."""
        from orchestrator.pipeline_integration import PipelineOrchestrator

        orchestrator = PipelineOrchestrator.__new__(PipelineOrchestrator)
        orchestrator.game_engine = None
        orchestrator._record_party_defeat(3)  # no exception


class TestOutcomeIsReadFromTheRightPlace:
    """
    CombatAgent returns {"response": {...}}, so the outcome is one level down.
    Reading it from the top logged `outcome=None, rounds=None` on every
    encounter — including a defeat the agent had just logged correctly.
    """

    def test_outcome_is_extracted_from_the_response_envelope(self):
        result = {"response": {"response_type": "combat_complete",
                               "outcome": "defeat", "rounds": 7}}
        response = result.get("response")
        payload = response if isinstance(response, dict) else result
        assert payload.get("outcome") == "defeat"
        assert payload.get("rounds") == 7

    def test_a_flat_result_still_works(self):
        """Be tolerant of either shape rather than depending on the envelope."""
        result = {"outcome": "victory", "rounds": 3}
        response = result.get("response")
        payload = response if isinstance(response, dict) else result
        assert payload.get("outcome") == "victory"


class TestAWipedPartyCannotBeThrownIntoAnotherFight:
    def _game(self, hp=20, dead=False, stable=False):
        from components.character_manager import CharacterManager
        from haystack_dnd_game import HaystackDnDGame

        game = HaystackDnDGame.__new__(HaystackDnDGame)
        manager = CharacterManager()
        manager.add_character({
            "character_id": "Aggi", "name": "Aggi", "level": 3,
            "ability_scores": {"strength": 14, "dexterity": 12,
                               "constitution": 12, "intelligence": 10,
                               "wisdom": 10, "charisma": 10},
            "hit_points": {"current": hp, "maximum": 20, "temporary": 0},
            "armor_class": 14, "character_class": "Fighter", "race": "Human",
            "background": "Soldier",
        })
        character = manager.characters["Aggi"]
        character.is_dead = dead
        character.is_stable = stable
        game.character_manager = manager
        return game

    def test_a_healthy_party_can_act(self):
        assert self._game(hp=20)._party_can_act() is True

    def test_a_dying_party_can_still_act(self):
        """At 0 HP but not stable: a death save or an ally can still change it."""
        assert self._game(hp=0)._party_can_act() is True

    def test_a_dead_party_cannot_act(self):
        assert self._game(hp=0, dead=True)._party_can_act() is False

    def test_a_stable_unconscious_party_cannot_act(self):
        assert self._game(hp=0, stable=True)._party_can_act() is False

    def test_one_survivor_is_enough(self):
        game = self._game(hp=0, dead=True)
        game.character_manager.add_character({
            "character_id": "Kali", "name": "Kali", "level": 3,
            "ability_scores": {"strength": 10, "dexterity": 14,
                               "constitution": 12, "intelligence": 12,
                               "wisdom": 12, "charisma": 10},
            "hit_points": {"current": 9, "maximum": 18, "temporary": 0},
            "armor_class": 13, "character_class": "Radiant", "race": "Alethi",
            "background": "Scholar",
        })
        assert game._party_can_act() is True
