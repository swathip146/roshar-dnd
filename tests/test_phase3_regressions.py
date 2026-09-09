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
        """
        Assert on the agent's real budget, not on a literal in the source.

        This pinned "max_agent_steps=6" and broke when the ceiling was raised to
        10 — a live playtest showed 6 was too tight: two turns spent every step
        on tool calls and never wrote the scene.
        """
        from agents.scenario_generator_agent import create_scenario_generator_agent

        agent = create_scenario_generator_agent()
        assert agent.max_agent_steps > 1, "still a single-shot call"
        assert agent.max_agent_steps >= 6, \
            "too few steps to inspect state, look up a rule, roll, then narrate"

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


# ------------------------------------------------- 3.5 durable turns (LangGraph)

from components.durable_turns import DurableTurnLoop


class TestDurableTurns:
    """
    3.5 / D4 — a turn blocks on a human for minutes or days, so turn state must
    survive process exit and resume in a NEW process.

    Haystack 2.21 had AgentBreakpoint/AgentSnapshot; 3.0 REMOVED them
    ("pausing and resuming execution inside an Agent is no longer supported"),
    which is why the plan migrates the agent layer to LangGraph.
    """

    @pytest.fixture
    def db(self, tmp_path):
        return tmp_path / "turns.sqlite"

    @pytest.fixture
    def counter(self):
        return {"resolves": 0}

    @pytest.fixture
    def loop(self, db, counter):
        def resolve(state):
            counter["resolves"] += 1
            return {"narration": f"You did: {state.get('player_input', '')}",
                    "choices": [{"title": "Continue"}]}

        made = DurableTurnLoop(on_resolve=resolve, checkpoint_db=db)
        yield made
        made.close()

    def test_langgraph_is_available(self, loop):
        assert loop.available, "LangGraph missing — durable turns cannot work"

    def test_a_turn_resolves(self, loop):
        result = loop.start("camp", player_input="I look around")
        assert result["status"] == "ok"
        assert "I look around" in result["narration"]

    def test_a_turn_without_input_pauses(self, loop):
        loop.start("camp", player_input="first")
        assert loop.start("camp")["status"] == "awaiting_input"

    def test_pausing_returns_data_not_a_blocking_call(self, loop):
        """D4: the interrupt returns the pending action AS DATA."""
        loop.start("camp", player_input="first")
        paused = loop.start("camp")
        assert "prompt" in paused and "choices" in paused
        assert isinstance(paused["choices"], list)

    def test_resume_works_in_a_new_process(self, db, counter):
        """
        The actual requirement: nothing in memory survives, only the checkpoint.
        """
        def resolve(state):
            counter["resolves"] += 1
            return {"narration": f"You did: {state.get('player_input', '')}"}

        first = DurableTurnLoop(on_resolve=resolve, checkpoint_db=db)
        first.start("camp", player_input="open the door")
        first.start("camp")          # pause
        first.close()                # process exits

        second = DurableTurnLoop(on_resolve=resolve, checkpoint_db=db)
        result = second.resume("camp", "I draw my blade")
        second.close()
        assert result["status"] == "ok"
        assert "I draw my blade" in result["narration"]

    def test_resume_does_not_re_execute_the_turn(self, db, counter):
        """
        THE gotcha: LangGraph re-executes a node from the top on resume, so a
        resumed turn would re-roll dice and re-bill tokens if interrupt() shared
        a node with resolution. interrupt() gets its own node for this reason.
        """
        def resolve(state):
            counter["resolves"] += 1
            return {"narration": "resolved"}

        loop = DurableTurnLoop(on_resolve=resolve, checkpoint_db=db)
        loop.start("camp", active_character="aggi")   # pauses immediately
        for i in range(3):
            loop.close()
            loop = DurableTurnLoop(on_resolve=resolve, checkpoint_db=db)
            loop.resume("camp", f"action {i}")
            loop.start("camp")                        # pause for the next turn
        loop.close()
        assert counter["resolves"] == 3, (
            f"resolver ran {counter['resolves']}x for 3 turns — re-execution"
        )

    def test_turn_number_advances(self, loop):
        loop.start("camp", player_input="one")
        assert loop.get_state("camp").get("turn_number", 0) >= 2

    def test_history_accumulates_and_is_bounded(self, db):
        loop = DurableTurnLoop(on_resolve=lambda s: {"narration": "x" * 50},
                               checkpoint_db=db)
        for i in range(30):
            loop.start("camp", player_input=f"turn {i}")
        history = loop.get_state("camp").get("history", [])
        loop.close()
        assert 0 < len(history) <= 20, "history must be bounded"

    def test_threads_are_isolated(self, loop):
        loop.start("camp-a", player_input="alpha")
        loop.start("camp-b", player_input="beta")
        assert "alpha" in loop.get_state("camp-a")["history"][0]
        assert "beta" in loop.get_state("camp-b")["history"][0]

    def test_threads_can_be_listed(self, loop):
        loop.start("camp-a", player_input="x")
        loop.start("camp-b", player_input="y")
        assert {"camp-a", "camp-b"} <= set(loop.list_threads())

    def test_a_failing_resolver_does_not_lose_the_thread(self, db):
        def boom(state):
            raise RuntimeError("resolution exploded")

        loop = DurableTurnLoop(on_resolve=boom, checkpoint_db=db)
        result = loop.start("camp", player_input="x")
        loop.close()
        assert result["status"] == "error"
        assert "could not be resolved" in result["narration"]

    def test_state_is_json_serialisable(self, loop):
        """Live components must stay OUT of checkpointed state."""
        loop.start("camp", player_input="x")
        json.dumps(loop.get_state("camp"))  # must not raise


# ------------------------------------- 3.3/3.4 retry-with-reasoning + memory

from components.retry_with_reasoning import (
    ConversationMemory, ValidationFailure, extract_json,
    generate_with_retry, require_keys,
)


def _validator(text):
    payload = extract_json(text)
    require_keys(payload, ["scene", "choices"])
    return payload


class _Replayer:
    """Generator stub that returns scripted replies and records what it saw."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.seen = []

    def run(self, messages):
        self.seen.append(messages)
        text = self.replies.pop(0) if self.replies else ""

        class _Reply:
            pass
        reply = _Reply()
        reply.text = text
        return {"replies": [reply]}


class TestRetryWithReasoning:
    """
    3.3 — every failure path substituted a canned fallback and continued, so the
    model was never told what went wrong and the player silently got degraded
    output that looked deliberate.
    """

    GOOD = json.dumps({"scene": "A storm gathers", "choices": []})

    def test_valid_output_passes_first_time(self):
        result, info = generate_with_retry(_Replayer([self.GOOD]), [], _validator)
        assert info["attempts"] == 1
        assert result["scene"] == "A storm gathers"

    def test_broken_json_is_retried_and_recovers(self):
        generator = _Replayer(["this is not json", self.GOOD])
        result, info = generate_with_retry(generator, [], _validator)
        assert info["recovered"] is True
        assert info["attempts"] == 2
        assert result["scene"] == "A storm gathers"

    def test_the_model_is_told_what_was_wrong(self):
        """The whole point of 3.3 — a fallback teaches the model nothing."""
        generator = _Replayer(["not json", self.GOOD])
        generate_with_retry(generator, [], _validator)
        feedback = generator.seen[1][-1].text
        assert "rejected" in feedback.lower()
        assert "json" in feedback.lower()

    def test_feedback_names_the_missing_key(self):
        generator = _Replayer([json.dumps({"scene": "x"}), self.GOOD])
        generate_with_retry(generator, [], _validator)
        assert "choices" in generator.seen[1][-1].text

    def test_prior_attempt_is_included_for_context(self):
        generator = _Replayer(["broken output here", self.GOOD])
        generate_with_retry(generator, [], _validator)
        texts = [m.text for m in generator.seen[1]]
        assert any("broken output here" in t for t in texts)

    def test_fallback_only_after_exhaustion(self):
        generator = _Replayer(["bad", "worse", "worst"])
        result, info = generate_with_retry(
            generator, [], _validator, fallback=lambda: {"scene": "fallback"})
        assert info["used_fallback"] is True
        assert info["attempts"] == 3
        assert result["scene"] == "fallback"

    def test_failure_is_flagged_not_hidden(self):
        generator = _Replayer(["bad", "bad", "bad"])
        _, info = generate_with_retry(generator, [], _validator,
                                      fallback=lambda: {})
        assert info["used_fallback"] is True
        assert info["errors"], "the errors must be reported, not swallowed"

    def test_no_fallback_raises(self):
        with pytest.raises(ValidationFailure):
            generate_with_retry(_Replayer(["bad"] * 3), [], _validator)

    def test_generator_errors_are_retried(self):
        class Flaky:
            def __init__(self):
                self.calls = 0

            def run(self, messages):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("transient API error")

                class _R:
                    text = TestRetryWithReasoning.GOOD
                return {"replies": [_R()]}

        result, info = generate_with_retry(Flaky(), [], _validator)
        assert info["attempts"] == 2
        assert result["scene"]

    def test_max_attempts_is_respected(self):
        generator = _Replayer(["bad"] * 10)
        _, info = generate_with_retry(generator, [], _validator, max_attempts=2,
                                      fallback=lambda: {})
        assert info["attempts"] == 2


class TestJsonExtraction:
    """Models emit fences and prose even under a response schema."""

    def test_plain_json(self):
        assert extract_json('{"a": 1}')["a"] == 1

    def test_fenced_json(self):
        assert extract_json('```json\n{"a": 1}\n```')["a"] == 1

    def test_json_after_prose(self):
        assert extract_json('Here you go:\n{"a": 1}')["a"] == 1

    def test_empty_response_is_actionable(self):
        with pytest.raises(ValidationFailure) as caught:
            extract_json("")
        assert "empty" in caught.value.message.lower()

    def test_no_json_is_actionable(self):
        with pytest.raises(ValidationFailure) as caught:
            extract_json("just some prose")
        assert caught.value.hint, "the model needs a hint it can act on"


class TestConversationMemory:
    """
    3.4 — every LLM call was stateless. llm_utils flattened all messages into a
    single string, and since Gemini has no system role the system prompt was
    prepended as user text, destroying conversational structure.
    """

    def test_messages_accumulate(self):
        memory = ConversationMemory()
        memory.append("t", "user", "hello")
        memory.append("t", "assistant", "a storm gathers")
        assert len(memory.messages("t")) == 2

    def test_roles_are_preserved(self):
        """Not flattened into one undifferentiated string."""
        memory = ConversationMemory()
        memory.append("t", "system", "You are the DM")
        memory.append("t", "user", "I look around")
        roles = [m["role"] for m in memory.messages("t")]
        assert roles == ["system", "user"]

    def test_history_is_bounded(self):
        memory = ConversationMemory(max_messages=5)
        for i in range(20):
            memory.append("t", "user", f"turn {i}")
        assert len(memory.messages("t")) <= 5

    def test_system_message_survives_trimming(self):
        memory = ConversationMemory(max_messages=5)
        memory.append("t", "system", "You are the DM")
        for i in range(20):
            memory.append("t", "user", f"turn {i}")
        assert memory.messages("t")[0]["role"] == "system"

    def test_threads_are_isolated(self):
        memory = ConversationMemory()
        memory.append("a", "user", "alpha")
        memory.append("b", "user", "beta")
        assert memory.messages("a")[0]["content"] == "alpha"
        assert len(memory.messages("b")) == 1

    def test_converts_to_chat_messages(self):
        memory = ConversationMemory()
        memory.append("t", "system", "You are the DM")
        memory.append("t", "user", "hello")
        assert len(memory.as_chat_messages("t")) == 2

    def test_empty_content_is_ignored(self):
        memory = ConversationMemory()
        memory.append("t", "user", "")
        assert memory.messages("t") == []

    def test_clear_removes_a_thread(self):
        memory = ConversationMemory()
        memory.append("t", "user", "x")
        memory.clear("t")
        assert memory.messages("t") == []


# ------------------------------------------------ Phase 3 turn-loop integration

class TestPhase3IsWiredIntoTheTurnLoop:
    """
    The components in 3.3-3.8 are only worth building if the live turn loop
    actually uses them. This checks the wiring, not just the parts.
    """

    @pytest.fixture
    def game(self, engine):
        from haystack_dnd_game import HaystackDnDGame

        g = HaystackDnDGame.__new__(HaystackDnDGame)
        g.game_engine = engine
        g.character_manager = engine.character_manager
        g.dnd_engine_wrapper = None
        g.current_choices = []

        class _Session:
            def get_session_metadata(self):
                return {"session_id": "test-thread", "session_active": True}

        g.session_manager = _Session()
        return g

    def test_thread_id_comes_from_the_session(self, game):
        assert game.thread_id == "test-thread"

    def test_thread_id_degrades_without_a_session(self, game):
        game.session_manager = None
        assert game.thread_id == "default-campaign"

    def test_player_and_dm_turns_are_both_recorded(self, game):
        from components.retry_with_reasoning import get_conversation_memory

        memory = get_conversation_memory()
        memory.clear("test-thread")
        game._remember("user", "I look around")
        game._remember("assistant", "A storm gathers.")
        roles = [m["role"] for m in memory.messages("test-thread")]
        assert roles == ["user", "assistant"]

    def test_play_turn_records_the_player_input(self):
        """
        3.4 — the player's turn reaches persistent history.

        Asserts on OBSERVABLE STATE rather than on play_turn's source text. The
        original version grepped the source for '_remember("user"', which broke
        the moment the turn body moved into resolve_turn() for the LangGraph
        wiring even though the behaviour was unchanged — a test that fails on
        refactors but would also pass on a call that recorded nothing.
        """
        from tests.test_durable_turn_wiring import _build_game
        from components.retry_with_reasoning import get_conversation_memory

        game = _build_game()
        memory = get_conversation_memory()
        memory.clear(game.thread_id)

        game.play_turn("I look around")

        recorded = memory.messages(game.thread_id)
        assert any(m["role"] == "user" and "look around" in m["content"]
                   for m in recorded), "player turns not recorded (3.4)"
        assert getattr(game, "_turn_started_at", None), \
            "turn boundary not marked (3.8)"

    def test_play_turn_records_and_annotates_the_reply(self):
        """3.4/3.8 — the DM's reply is recorded and passed through annotation."""
        from tests.test_durable_turn_wiring import _build_game
        from components.retry_with_reasoning import get_conversation_memory

        game = _build_game(scene="A storm gathers over the plateau.")
        memory = get_conversation_memory()
        memory.clear(game.thread_id)

        narration = game.play_turn("I look around")

        recorded = memory.messages(game.thread_id)
        assert any(m["role"] == "assistant" and "storm gathers" in m["content"]
                   for m in recorded), "DM replies not recorded (3.4)"
        # _annotate_rulings passes text through untouched when nothing was
        # improvised, so the reply must still arrive intact.
        assert "storm gathers" in narration

    def test_house_rulings_are_surfaced(self, game, tmp_path):
        """3.8 — improvisation must be visible, not silently passed off."""
        import time
        import components.rules_gap_tracker as module
        from components.rules_gap_tracker import RulesGapTracker, TIER_JUDGED

        module._GLOBAL = RulesGapTracker(store_path=tmp_path / "gaps.json")
        game._turn_started_at = time.time() - 1
        module._GLOBAL.record("Lash the boulder onto the Fused", TIER_JUDGED)

        annotated = game._annotate_rulings("You heave the stone skyward.")
        assert "House ruling" in annotated
        assert "You heave the stone skyward." in annotated

    def test_older_rulings_are_not_re_annotated(self, game, tmp_path):
        import time
        import components.rules_gap_tracker as module
        from components.rules_gap_tracker import RulesGapTracker, TIER_JUDGED

        module._GLOBAL = RulesGapTracker(store_path=tmp_path / "gaps.json")
        module._GLOBAL.record("something from a previous turn", TIER_JUDGED)
        game._turn_started_at = time.time() + 999  # nothing happened this turn

        assert game._annotate_rulings("Plain narration.") == "Plain narration."

    def test_annotation_never_breaks_the_turn(self, game):
        """A tracker failure must not cost the player their narration."""
        import components.rules_gap_tracker as module

        module._GLOBAL = None
        game._turn_started_at = 0
        assert "Plain narration." in game._annotate_rulings("Plain narration.")

    def test_memory_failure_never_breaks_the_turn(self, game):
        import components.retry_with_reasoning as module

        original = module.get_conversation_memory
        module.get_conversation_memory = lambda: (_ for _ in ()).throw(
            RuntimeError("memory unavailable"))
        try:
            game._remember("user", "still fine")  # must not raise
        finally:
            module.get_conversation_memory = original

    def test_dm_tools_are_wired_at_startup(self):
        """3.1 — the tools must be pointed at live components by the orchestrator."""
        import inspect
        from orchestrator.pipeline_integration import PipelineOrchestrator

        src = inspect.getsource(
            PipelineOrchestrator._initialize_pipeline_infrastructure)
        assert "set_dm_tool_context" in src
        assert "get_srd_rules" in src and "get_cosmere_rules" in src
