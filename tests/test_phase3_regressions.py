"""
Phase 3 regression tests (docs/REBUILD_PLAN_V5.md §5).

Tier-2 assertions per §12: assert on observable end state, never on
"the method was called."
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from components.cosmere_rules import CosmereRules
from components.game_engine import GameEngine
from components.rules_gap_tracker import RulesGapTracker
from components.rules_judge import (
    RulesJudge, RulingStore, describe_tier,
    TIER_CANONICAL, TIER_COMPOSED, TIER_JUDGED, TIER_NARRATIVE,
)
from components.srd_rules import SRDRules


PC = {
    "character_id": "aggi",
    "name": "Aggi",
    "level": 3,
    "ability_scores": {"strength": 12, "dexterity": 16, "constitution": 12,
                       "intelligence": 10, "wisdom": 12, "charisma": 14},
    "hit_points": {"current": 24, "maximum": 24, "temporary": 0},
    "armor_class": 14,
    "character_class": "Lightweaver",
    "race": "Alethi",
    "background": "Soldier",
    "skills": {"stealth": True, "perception": True},
    "radiant_order": "Lightweaver",
    "stormlight_current": 6,
    "stormlight_capacity": 6,
    "ideal_level": 1,
}


@pytest.fixture
def engine():
    ge = GameEngine()
    ge.add_character(dict(PC))
    return ge


@pytest.fixture
def wired(engine):
    """DM tools wired to live components (plan 3.1)."""
    from agents import dm_tools

    dm_tools.set_dm_tool_context(
        game_engine=engine,
        character_manager=engine.character_manager,
        srd_rules=SRDRules(),
        cosmere_rules=CosmereRules(),
    )
    yield dm_tools
    dm_tools.clear_dm_tool_context()


# ------------------------------------------------------------------- 3.1 tools

class TestDMToolsAdjudicate:
    """
    3.1 — the LLM narrates, code adjudicates. Before this the model emitted a
    suggested_dc that nothing enforced, invented Stormlight costs, and described
    mechanics it had no way to resolve.
    """

    def test_all_tools_are_registered(self, wired):
        names = set(wired.dm_tool_names())
        for expected in ("roll_skill_check", "roll_dice", "get_character_state",
                         "get_world_state", "query_rules", "apply_damage",
                         "spend_stormlight", "advance_quest", "award_experience"):
            assert expected in names, f"{expected} missing from DM tools"

    def test_skill_check_returns_a_real_roll(self, wired):
        result = wired.roll_skill_check.function(skill="stealth", dc=13)
        assert 1 <= result["selected_roll"] <= 20
        assert isinstance(result["success"], bool)

    def test_skill_check_outcomes_vary(self, wired):
        rolls = {wired.roll_skill_check.function(skill="stealth", dc=13)["selected_roll"]
                 for _ in range(30)}
        assert len(rolls) > 5, "dice look fixed"

    def test_dice_tool_handles_real_notation(self, wired):
        assert wired.roll_dice.function(expression="4d6kh3")["total"] > 0
        assert wired.roll_dice.function(expression="2d6+3")["total"] >= 5

    def test_character_state_is_live(self, wired, engine):
        engine.character_manager.characters["aggi"].hit_points["current"] = 7
        assert wired.get_character_state.function()["hit_points"]["current"] == 7

    def test_world_state_reports_time_and_weather(self, wired, engine):
        engine.advance_time(days=1)
        state = wired.get_world_state.function()
        assert state["day"] == 2
        assert state["weather"] is not None

    def test_query_rules_finds_srd_monsters(self, wired):
        result = wired.query_rules.function(topic="Goblin")
        assert result["found"] is True
        assert result["tier"] == 1

    def test_query_rules_finds_cosmere_maneuvers(self, wired):
        result = wired.query_rules.function(topic="Full Lashing")
        assert result["found"] is True
        assert result["tier"] == 2

    def test_query_rules_admits_when_it_has_nothing(self, wired):
        result = wired.query_rules.function(topic="Zorblatt Manoeuvre")
        assert result["found"] is False
        assert "improvis" in result["note"].lower(), \
            "must tell the model to flag improvisation, not fake a rule"

    def test_damage_mutates_real_state(self, wired, engine):
        character = engine.character_manager.characters["aggi"]
        character.hit_points["current"] = 24
        result = wired.apply_damage.function(amount=10)
        assert result["hp_after"] == 14
        assert character.hit_points["current"] == 14

    def test_damage_floors_at_zero_and_flags_dying(self, wired):
        result = wired.apply_damage.function(amount=999)
        assert result["hp_after"] == 0
        assert result["is_dying"] is True

    def test_healing_caps_at_max(self, wired, engine):
        engine.character_manager.characters["aggi"].hit_points["current"] = 20
        result = wired.apply_healing.function(amount=999)
        assert result["hp_after"] == 24

    def test_stormlight_spend_is_enforced(self, wired):
        assert wired.spend_stormlight.function(amount=4)["remaining"] == 2

    def test_stormlight_overspend_is_refused(self, wired, engine):
        """Surgebinding is not free — the tool must be able to say no."""
        result = wired.spend_stormlight.function(amount=99)
        assert result["affordable"] is False
        assert result["spent"] == 0
        assert engine.character_manager.characters["aggi"].stormlight_current == 6

    def test_quest_tool_advances_real_state(self, wired, engine):
        wired.advance_quest.function(objective="Find the artifact", action="add")
        assert "Find the artifact" in engine.get_quest_progress()["pending"]

    def test_xp_tool_awards_the_party(self, wired, engine):
        wired.award_experience.function(amount=300, reason="test")
        assert engine.character_manager.characters["aggi"].experience_points == 300

    def test_tools_return_dicts_never_prose(self, wired):
        """The model must not mistake a mechanical result for rewritable text."""
        for call in (lambda: wired.roll_skill_check.function(skill="stealth", dc=10),
                     lambda: wired.get_character_state.function(),
                     lambda: wired.get_world_state.function(),
                     lambda: wired.query_rules.function(topic="Goblin")):
            assert isinstance(call(), dict)

    def test_tools_degrade_without_context(self):
        from agents import dm_tools
        dm_tools.clear_dm_tool_context()
        result = dm_tools.roll_skill_check.function(skill="stealth", dc=10)
        assert "error" in result and result["success"] is False


class TestScenarioAgentIsAgentic:
    """
    3.2 — the audit's verdict was "an LLM-call pipeline, not an agentic system",
    and this line was the reason: tools=[], max_agent_steps=1.
    """

    def _source(self):
        import inspect
        from agents.scenario_generator_agent import create_scenario_generator_agent
        return inspect.getsource(create_scenario_generator_agent)

    def test_agent_has_tools(self):
        """
        Match the Agent(...) CALL, not the file text: the explanatory comment
        legitimately quotes the old `tools=[], max_agent_steps=1`.
        """
        src = self._source()
        assert "tools=dm_tools" in src
        agent_call = src[src.index("agent = Agent("):]
        assert "tools=[]" not in agent_call, "still a single-shot call"

    def test_agent_can_take_multiple_steps(self):
        src = self._source()
        assert "max_agent_steps=1," not in src
        assert "max_agent_steps=6" in src

    def test_prompt_forbids_deciding_outcomes(self):
        src = self._source()
        assert "roll_skill_check" in src
        assert "NEVER" in src, "the model must be told not to invent outcomes"


# ------------------------------------------------------- 3.6/3.7/3.8 rules judge

def _ruling(**over):
    base = {"legal": True, "reason": "Full Lashing restrains a creature",
            "cost": {"lashing_dice": 1},
            "resolution": {"type": "save", "stat": "strength", "dc": 13},
            "cites": ["Radiant's Handbook / Full Lashing"],
            "confidence": "high"}
    base.update(over)
    return base


class _Generator:
    """A stand-in chat generator returning a fixed ruling."""

    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def run(self, messages):
        self.calls += 1
        text = json.dumps(self.payload)

        class _Reply:
            pass
        reply = _Reply()
        reply.text = text
        return {"replies": [reply]}


@pytest.fixture
def judge_parts(tmp_path):
    return {
        "store": RulingStore(path=tmp_path / "rulings.json"),
        "tracker": RulesGapTracker(store_path=tmp_path / "gaps.json"),
        "srd": SRDRules(),
        "cosmere": CosmereRules(),
    }


def _judge(parts, generator):
    return RulesJudge(chat_generator=generator, srd_rules=parts["srd"],
                      cosmere_rules=parts["cosmere"],
                      gap_tracker=parts["tracker"], store=parts["store"])


class TestRulesJudgeIsGrounded:
    """
    3.6 / D5 — the model gets discretion, but not invisibly and not from memory.
    """

    SITUATION = "Full Lashing the Fused"

    def test_retrieval_finds_rules_text(self, judge_parts):
        judge = _judge(judge_parts, _Generator(_ruling()))
        assert len(judge.retrieve_rules_text(self.SITUATION)) > 0

    def test_a_cited_ruling_is_accepted(self, judge_parts):
        result = _judge(judge_parts, _Generator(_ruling())).judge(self.SITUATION)
        assert result["tier"] == TIER_JUDGED
        assert result["cites"]

    def test_an_uncited_ruling_is_downgraded(self, judge_parts):
        """A ruling with no citations is exactly what D5 forbids."""
        result = _judge(judge_parts, _Generator(_ruling(cites=[]))).judge(self.SITUATION)
        assert result["tier"] == TIER_NARRATIVE
        assert result["resolution"]["type"] == "none"

    def test_no_generator_means_no_ruling(self, judge_parts):
        """Degrade to flavour rather than guessing."""
        judge = RulesJudge(chat_generator=None, srd_rules=judge_parts["srd"],
                           cosmere_rules=judge_parts["cosmere"],
                           gap_tracker=judge_parts["tracker"],
                           store=judge_parts["store"])
        assert judge.judge(self.SITUATION)["tier"] == TIER_NARRATIVE

    def test_ungroundable_situation_is_narrative(self, judge_parts):
        judge = _judge(judge_parts, _Generator(_ruling()))
        result = judge.judge("I invent an entirely novel physics")
        assert result["tier"] == TIER_NARRATIVE

    def test_a_refusal_is_a_valid_ruling(self, judge_parts):
        result = _judge(judge_parts,
                        _Generator(_ruling(legal=False))).judge(self.SITUATION)
        assert result["legal"] is False
        assert result["tier"] == TIER_JUDGED, "a cited refusal is still a ruling"

    def test_malformed_output_degrades(self, judge_parts):
        class Broken:
            def run(self, messages):
                class R:
                    text = "not json at all"
                return {"replies": [R()]}

        result = _judge(judge_parts, Broken()).judge(self.SITUATION)
        assert result["tier"] == TIER_NARRATIVE

    def test_lore_cannot_ground_a_mechanic(self, judge_parts):
        """search_lore is flavour; only rules-tagged text may ground a ruling."""
        import inspect
        src = inspect.getsource(RulesJudge.retrieve_rules_text)
        assert 'document_tag' in src and 'rules' in src


class TestPrecedentBinds:
    """
    3.7 — the classic failure this prevents: the same action costing 1 Stormlight
    today and 3 tomorrow.
    """

    SITUATION = "Full Lashing the Fused"

    def test_the_same_situation_reuses_the_ruling(self, judge_parts):
        generator = _Generator(_ruling())
        judge = _judge(judge_parts, generator)
        judge.judge(self.SITUATION)
        judge.judge(self.SITUATION)
        assert generator.calls == 1, "the model was asked twice for one situation"

    def test_precedent_overrides_a_contradicting_judge(self, judge_parts):
        _judge(judge_parts, _Generator(_ruling(legal=True))).judge(self.SITUATION)
        second = _judge(judge_parts,
                        _Generator(_ruling(legal=False, reason="changed my mind")))
        result = second.judge("I Full Lashing that Fused")
        assert result["followed_precedent"] is True
        assert result["legal"] is True, "consistency must beat a fresh opinion"

    def test_costs_stay_stable(self, judge_parts):
        _judge(judge_parts,
               _Generator(_ruling(cost={"lashing_dice": 1}))).judge(self.SITUATION)
        second = _judge(judge_parts,
                        _Generator(_ruling(cost={"lashing_dice": 3})))
        assert second.judge(self.SITUATION)["cost"] == {"lashing_dice": 1}

    def test_unrelated_situations_do_not_bind(self, judge_parts):
        generator = _Generator(_ruling())
        judge = _judge(judge_parts, generator)
        judge.judge(self.SITUATION)
        judge.judge("Soulcast the wall to smoke with Transformation")
        assert generator.calls == 2, "an unrelated attempt must get its own ruling"

    def test_rulings_survive_a_restart(self, tmp_path, judge_parts):
        path = tmp_path / "persist.json"
        first = RulingStore(path=path)
        first.record("Full Lashing the Fused", _ruling())
        assert RulingStore(path=path).find_precedent("Full Lashing the Fused")


class TestRulingPromotion:
    """D5's payoff: the ruleset grows by play."""

    def test_recurring_rulings_become_candidates(self, judge_parts):
        judge = _judge(judge_parts, _Generator(_ruling()))
        for _ in range(4):
            judge.judge("Full Lashing the Fused")
        assert judge_parts["store"].promotion_candidates(3)

    def test_rare_rulings_are_not_candidates(self, judge_parts):
        _judge(judge_parts, _Generator(_ruling())).judge("Full Lashing the Fused")
        assert judge_parts["store"].promotion_candidates(3) == []

    def test_promotion_clears_the_candidate(self, judge_parts):
        judge = _judge(judge_parts, _Generator(_ruling()))
        for _ in range(4):
            judge.judge("Full Lashing the Fused")
        assert judge_parts["store"].mark_promoted("Full Lashing the Fused") is True
        assert judge_parts["store"].promotion_candidates(3) == []

    def test_judged_rulings_reach_the_gap_tracker(self, judge_parts):
        _judge(judge_parts, _Generator(_ruling())).judge("Full Lashing the Fused")
        assert judge_parts["tracker"].stats()["distinct_gaps"] >= 1


class TestTierMarkers:
    """3.8 — improvisation must stay legible to the player."""

    def test_canonical_tiers_are_unmarked(self):
        assert describe_tier(TIER_CANONICAL) == ""
        assert describe_tier(TIER_COMPOSED) == ""

    def test_judged_is_marked_a_house_ruling(self):
        assert describe_tier(TIER_JUDGED) == "House ruling"

    def test_narrative_says_no_mechanical_effect(self):
        assert describe_tier(TIER_NARRATIVE) == "No mechanical effect"
