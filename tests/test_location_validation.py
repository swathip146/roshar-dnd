"""
state_changes.location must be a place NAME, not narration — found by playtest.

A live run logged:

    🏔️ Moved to location: Playtest Ridge is now understood as a site of recent
       and significant conflict, a gateway to the wider devastation.

The scenario prompt listed "location" directly beneath "narrative" with only
"..." as guidance, so the model wrote a sentence and set_location() stored it
verbatim. That corrupts the location graph: known_locations is keyed by name and
travel_to() matches those keys, so exits stop resolving once a key is a
paragraph.
"""

import pytest

from components.game_engine import GameEngine


pytestmark = pytest.mark.unit


@pytest.fixture
def world():
    engine = GameEngine()
    engine.register_location("The Shattered Plains", "Endless plateaus",
                             exits=["Kholinar"])
    engine.register_location("Kholinar", "A shattered city", exits=[])
    engine.set_location("The Shattered Plains")
    return engine


def _current(engine) -> str:
    return engine.game_state.location_context.get("current_location", "")


class TestNarrativeTextIsRejected:

    def test_the_exact_live_failure(self, world):
        """Verbatim from the playtest log."""
        prose = ("Playtest Ridge is now understood as a site of recent and "
                 "significant conflict, a gateway to the wider devastation.")
        assert world._apply_location_change(prose) is False
        assert _current(world) == "The Shattered Plains"
        assert prose not in world.game_state.location_context["known_locations"]

    def test_second_live_failure(self, world):
        prose = ("The player is now entering a denser area of wreckage on "
                 "Playtest Ridge, closer to the path leading down to the "
                 "border town.")
        assert world._apply_location_change(prose) is False
        assert _current(world) == "The Shattered Plains"

    def test_prose_does_not_pollute_the_location_graph(self, world):
        """The graph must stay keyed by names travel_to() can match."""
        world._apply_location_change(
            "Kholinar is now a smoking ruin and the party is deeply shaken.")
        for name in world.game_state.location_context["known_locations"]:
            assert len(name.split()) <= 6, f"prose leaked into the graph: {name!r}"


class TestRealNamesStillWork:

    def test_bare_name_is_accepted(self, world):
        assert world._apply_location_change("Kholinar") is True
        assert _current(world) == "Kholinar"

    def test_unknown_but_name_shaped_place_is_accepted(self, world):
        """The DM must still be able to invent places mid-story."""
        assert world._apply_location_change("Sadeas Warcamp") is True
        assert _current(world) == "Sadeas Warcamp"

    def test_known_name_matches_case_insensitively(self, world):
        assert world._apply_location_change("kholinar") is True
        assert _current(world) == "Kholinar"

    def test_no_change_when_already_there(self, world):
        assert world._apply_location_change("The Shattered Plains") is False
        assert _current(world) == "The Shattered Plains"

    def test_trailing_period_and_quotes_are_stripped(self, world):
        assert world._apply_location_change('"Kholinar".') is True
        assert _current(world) == "Kholinar"


class TestSalvage:

    def test_known_location_named_inside_prose_is_used(self, world):
        """Better to honour the intent than discard the update."""
        assert world._apply_location_change(
            "The party has now arrived at Kholinar, which lies in ruins "
            "after the assault, and the streets are burning.") is True
        assert _current(world) == "Kholinar"

    def test_longest_match_wins(self, world):
        world.register_location("Plains", "A generic plain")
        assert world._known_location_named_in(
            "somewhere on the shattered plains today") == "The Shattered Plains"


class TestJunkInput:

    @pytest.mark.parametrize("value", ["", "   ", None, 42, [], {}])
    def test_junk_is_ignored_without_raising(self, world, value):
        assert world._apply_location_change(value) is False
        assert _current(world) == "The Shattered Plains"


class TestEndToEndThroughScenarioUpdate:
    """The real path: process_scenario_state_updates -> _apply_location_change."""

    def test_scenario_narration_does_not_move_the_party(self, world):
        world.process_scenario_state_updates({
            "scene": "You survey the wreckage.",
            "state_changes": {
                "location": ("Playtest Ridge is now understood as a site of "
                             "recent and significant conflict."),
            },
        }, turn_number=1)
        assert _current(world) == "The Shattered Plains"

    def test_scenario_real_move_is_applied(self, world):
        world.process_scenario_state_updates({
            "scene": "You pass through the gates.",
            "state_changes": {"location": "Kholinar"},
        }, turn_number=2)
        assert _current(world) == "Kholinar"


class TestAgentStepBudgets:
    """
    Lock in each agent's step budget.

    The playtest log shows "Agent reached maximum agent steps of 1, stopping."
    once per turn, which looks alarming but is the INTERFACE agent doing its
    single classification call by design. The scenario agent has a real step budget and all
    tools and does not hit its ceiling. These assertions make a real regression
    (the scenario agent silently dropping to one step, which would disable the
    Phase 3.1/3.2 tool loop) fail loudly instead of hiding in the same warning.
    """

    def test_scenario_agent_has_a_real_tool_loop(self):
        from agents.scenario_generator_agent import create_scenario_generator_agent
        agent = create_scenario_generator_agent()
        # Against the registry, not a hardcoded count — see the same fix in
        # test_two_phase_turn.py.
        from agents.dm_tools import DM_TOOLS

        assert agent.tools, "DM tools missing — the loop is decorative"
        assert len(agent.tools) == len(DM_TOOLS), (
            f"agent has {len(agent.tools)} tools, registry has {len(DM_TOOLS)}")
        assert agent.max_agent_steps >= 6, (
            "the scenario agent needs several steps to inspect state, look up a "
            "rule, roll, then narrate")

    def test_interface_agent_is_deliberately_single_step(self):
        from agents.main_interface_agent_fixed import create_fixed_interface_agent
        agent = create_fixed_interface_agent()
        assert agent.max_agent_steps == 1
        assert len(agent.tools) == 0
