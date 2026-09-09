"""
The scenario agent must not spend its whole step budget on redundant reads.

A live playtest turn called get_world_state SIX times and get_party_state FOUR
times, hit max_agent_steps=6, and never wrote the scene — so the player got a
generic 118-char fallback. Two turns out of six ended that way.

Fixes, and what each is for:
  - the prompt now says read-only tools are one-shot per turn (guidance)
  - those reads are CACHED per turn, so a repeat costs no step (enforcement,
    because a prompt cannot guarantee an invariant)
  - max_agent_steps raised 6 -> 10 (headroom; one live turn legitimately needed
    7 calls and did produce a scene)

The cache must be correct as well as cheap: stale within a turn is fine for
world state, but NOT after a mutation — a model that applies damage and then
reads HP must see the new value.
"""

import pytest

from components.game_engine import GameEngine


pytestmark = pytest.mark.unit


CHARACTER = {
    "character_id": "Aggi", "name": "Aggi", "level": 1,
    "ability_scores": {"strength": 10, "dexterity": 14, "constitution": 10,
                       "intelligence": 10, "wisdom": 10, "charisma": 10},
    "hit_points": {"current": 20, "maximum": 20, "temporary": 0},
    "armor_class": 12, "character_class": "Radiant", "race": "Alethi",
    "background": "Folk Hero", "skills": {"stealth": True},
    "stormlight_current": 6, "stormlight_capacity": 6,
}


@pytest.fixture
def tools():
    from agents import dm_tools

    engine = GameEngine()
    engine.add_character(dict(CHARACTER))
    engine.register_location("Camp", "a windbreak camp", exits=[])
    engine.set_location("Camp")
    dm_tools.set_dm_tool_context(game_engine=engine,
                                 character_manager=engine.character_manager)
    dm_tools.begin_dm_tool_turn()
    yield dm_tools, engine
    dm_tools.clear_dm_tool_context()


class TestReadsAreCachedWithinATurn:

    def test_repeat_world_state_is_free(self, tools):
        dm_tools, _ = tools
        first = dm_tools.get_world_state.function()
        second = dm_tools.get_world_state.function()
        assert first is second, "a repeat read should cost nothing"

    def test_repeat_party_state_is_free(self, tools):
        dm_tools, _ = tools
        assert (dm_tools.get_party_state.function()
                is dm_tools.get_party_state.function())

    def test_repeat_character_state_is_free(self, tools):
        dm_tools, _ = tools
        assert (dm_tools.get_character_state.function()
                is dm_tools.get_character_state.function())

    def test_cache_is_per_actor(self, tools):
        """Two different characters must not share one cached read."""
        dm_tools, engine = tools
        engine.add_character({**CHARACTER, "character_id": "Kali", "name": "Kali"})
        aggi = dm_tools.get_character_state.function(actor="Aggi")
        kali = dm_tools.get_character_state.function(actor="Kali")
        assert aggi["name"] == "Aggi" and kali["name"] == "Kali"


class TestCacheDoesNotGoStaleWhereItMatters:

    def test_mutation_invalidates_reads(self, tools):
        """apply_damage then read HP must show the NEW value."""
        dm_tools, _ = tools
        assert dm_tools.get_character_state.function()["hit_points"]["current"] == 20
        dm_tools.apply_damage.function(amount=7)
        assert dm_tools.get_character_state.function()["hit_points"]["current"] == 13, \
            "the model would narrate an unharmed character"

    def test_healing_invalidates_reads(self, tools):
        dm_tools, _ = tools
        dm_tools.apply_damage.function(amount=10)
        dm_tools.apply_healing.function(amount=5)
        assert dm_tools.get_character_state.function()["hit_points"]["current"] == 15

    def test_stormlight_spend_invalidates_reads(self, tools):
        dm_tools, _ = tools
        assert dm_tools.get_character_state.function()["stormlight_current"] == 6
        dm_tools.spend_stormlight.function(amount=4)
        assert dm_tools.get_character_state.function()["stormlight_current"] == 2

    def test_new_turn_drops_the_cache(self, tools):
        """Otherwise the DM would narrate last turn's weather and HP."""
        dm_tools, engine = tools
        before = dm_tools.get_world_state.function()
        engine.advance_time(days=1)
        dm_tools.begin_dm_tool_turn()
        after = dm_tools.get_world_state.function()
        assert after is not before
        assert after["day"] != before["day"]


class TestRollsAreNeverCached:
    """Caching a roll would make every check in a turn return one result."""

    def test_skill_checks_still_vary(self, tools):
        dm_tools, _ = tools
        rolls = {dm_tools.roll_skill_check.function(skill="stealth", dc=10)["selected_roll"]
                 for _ in range(30)}
        assert len(rolls) > 5, "rolls look cached — every check would be identical"

    def test_dice_rolls_still_vary(self, tools):
        dm_tools, _ = tools
        totals = {dm_tools.roll_dice.function(expression="3d6")["total"]
                  for _ in range(30)}
        assert len(totals) > 3


class TestStepBudgetHeadroom:

    def test_scenario_agent_has_room_to_narrate(self):
        """
        6 was too tight: a live turn spent 7 calls and still produced a scene,
        while two others exhausted the budget before writing anything.
        """
        from agents.scenario_generator_agent import create_scenario_generator_agent
        agent = create_scenario_generator_agent()
        assert agent.max_agent_steps >= 10

    def test_prompt_warns_about_the_budget(self):
        import inspect
        from agents import scenario_generator_agent

        source = inspect.getsource(scenario_generator_agent)
        assert "STEP BUDGET" in source
        assert "AT MOST ONCE" in source


class TestTurnBoundaryIsWired:
    """The cache is only safe if something actually resets it each turn."""

    def test_resolve_turn_resets_the_cache(self):
        import inspect
        from haystack_dnd_game import HaystackDnDGame

        source = inspect.getsource(HaystackDnDGame.resolve_turn)
        assert "begin_dm_tool_turn" in source, \
            "without a per-turn reset the cache leaks stale state across turns"


class TestCharactersAreIsolatedBetweenEngines:
    """
    add_character() stored nested dicts BY REFERENCE.

    Found while writing the healing test above: it failed because a previous
    test's damage had leaked in. Two GameEngines built from the same template
    produced distinct CharacterData objects that shared ONE hit_points dict, so
    damaging a character in one game changed it in the other — and a caller that
    reused its own template dict had the game write back into it.
    """

    def test_two_engines_do_not_share_hit_points(self):
        first, second = GameEngine(), GameEngine()
        first.add_character(dict(CHARACTER))
        second.add_character(dict(CHARACTER))

        first.character_manager.characters["Aggi"].hit_points["current"] = 1

        assert second.character_manager.characters["Aggi"].hit_points["current"] == 20, \
            "damaging one game's character changed another game's character"

    def test_the_callers_template_is_not_mutated(self):
        template = dict(CHARACTER)
        engine = GameEngine()
        engine.add_character(template)

        engine.character_manager.characters["Aggi"].hit_points["current"] = 3

        assert template["hit_points"]["current"] == 20, \
            "the game wrote back into the caller's own dict"

    def test_nested_collections_are_copied(self):
        template = {**CHARACTER, "equipment": ["spear"], "conditions": []}
        engine = GameEngine()
        engine.add_character(template)

        character = engine.character_manager.characters["Aggi"]
        assert character.hit_points is not template["hit_points"]
        assert character.ability_scores is not template["ability_scores"]
