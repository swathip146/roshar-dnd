"""
PHASE 0 GO/NO-GO — can a scripted fake drive the real Haystack `Agent` tool loop?

This is the one genuine unknown in the whole strategy. `docs/mechanics/
INTEGRATION_TEST_STRATEGY.md` §10 calls it out: if a fake generator cannot satisfy the
Haystack `Agent` loop, Suite A must instead drive `PipelineOrchestrator` beneath the
`Agent` layer — narrower coverage, and worth knowing on day one rather than in phase 5.

So this file tests the *fake infrastructure itself*, not the game. It must pass before
anything is built on top of it.

The load-bearing assertion is `test_agent_loop_executes_real_tools`: a real
`haystack.Agent`, real `DM_TOOLS`, a scripted generator, and proof the tool actually
RAN (a real d20 result came back) rather than merely being requested.
"""

from __future__ import annotations

import json

import pytest
from haystack.dataclasses import ChatMessage, ToolCall

from tests.integration.fakes.fake_config_manager import (
    ScriptedConfigManager,
    scripted_llm,
)
from tests.integration.fakes.fake_generator import (
    FakeGeneratorError,
    ScriptedChatGenerator,
    make_tool_call,
)
from tests.integration.fakes.policies import (
    BasePolicy,
    NarrateOnlyPolicy,
    ToolSequencePolicy,
    intent_json,
    scenario_json,
)

pytestmark = pytest.mark.integration


# --------------------------------------------------------------------------- #
# The generator honours the production contract
# --------------------------------------------------------------------------- #

class TestGeneratorContract:
    """`run(messages, tools=None) -> {"replies": [ChatMessage]}`, per llm_utils.py:431."""

    def test_text_reply_shape(self):
        gen = ScriptedChatGenerator(policy=NarrateOnlyPolicy(), agent_name="npc_controller")
        out = gen.run([ChatMessage.from_user("hello")])

        assert set(out) == {"replies"}
        assert len(out["replies"]) == 1
        assert isinstance(out["replies"][0], ChatMessage)
        assert out["replies"][0].text

    def test_tool_call_reply_shape(self):
        """A ToolCall must survive onto the ChatMessage — llm_utils.py:585-600."""
        gen = ScriptedChatGenerator(
            policy=ToolSequencePolicy([make_tool_call("roll_dice", notation="1d20")]),
            agent_name="scenario_generator",
        )

        class _Tool:
            name = "roll_dice"

        reply = gen.run([ChatMessage.from_user("roll")], tools=[_Tool()])["replies"][0]

        assert reply.tool_calls, "tool_calls did not survive onto the ChatMessage"
        assert reply.tool_calls[0].tool_name == "roll_dice"
        assert reply.tool_calls[0].arguments == {"notation": "1d20"}

    def test_structured_output_is_valid_json(self):
        """With a response_schema the reply text must parse and satisfy required keys."""
        from agents.scenario_generator_agent import SCENARIO_RESPONSE_SCHEMA

        gen = ScriptedChatGenerator(
            policy=BasePolicy(),
            response_schema=SCENARIO_RESPONSE_SCHEMA,
            agent_name="scenario_generator",
        )
        payload = json.loads(gen.run([ChatMessage.from_user("scene")])["replies"][0].text)

        for key in SCENARIO_RESPONSE_SCHEMA["required"]:
            assert key in payload, f"schema requires {key!r}"
        for choice in payload["choices"]:
            for key in ("id", "title", "description", "skill_hints",
                        "suggested_dc", "combat_trigger"):
                assert key in choice

    def test_intent_schema_payload_is_valid(self):
        from agents.main_interface_agent_fixed import INTENT_ANALYSIS_SCHEMA

        gen = ScriptedChatGenerator(
            policy=BasePolicy(),
            response_schema=INTENT_ANALYSIS_SCHEMA,
            agent_name="main_interface",
        )
        payload = json.loads(gen.run([ChatMessage.from_user("go north")])["replies"][0].text)

        assert payload["primary"]
        assert 0.0 <= payload["confidence"] <= 1.0

    def test_prose_where_schema_demanded_fails_loudly(self):
        """A silent fallback here would let a test pass while exercising nothing."""
        class _Prose:
            def next_reply(self, **kw):
                return "not json at all"

        gen = ScriptedChatGenerator(policy=_Prose(), response_schema={"type": "object"},
                                    agent_name="main_interface")
        with pytest.raises(FakeGeneratorError, match="schema-shaped JSON"):
            gen.run([ChatMessage.from_user("x")])

    def test_calls_are_recorded_for_assertions(self):
        record: list = []
        gen = ScriptedChatGenerator(policy=NarrateOnlyPolicy(), agent_name="rag_retriever",
                                    record=record)
        gen.run([ChatMessage.from_user("a")])
        gen.run([ChatMessage.from_user("b")])

        assert len(record) == 2
        assert [c["call_index"] for c in record] == [0, 1]
        assert {c["agent"] for c in record} == {"rag_retriever"}


# --------------------------------------------------------------------------- #
# THE GO/NO-GO
# --------------------------------------------------------------------------- #

class TestHaystackAgentLoop:
    """Does a real `haystack.Agent` accept a scripted generator and RUN the tools?

    Mirrors `scenario_generator_agent.py:832`: real DM_TOOLS, exit_conditions=["text"],
    max_agent_steps=10.
    """

    def test_agent_accepts_a_scripted_generator(self):
        from haystack.components.agents import Agent
        from agents.dm_tools import DM_TOOLS

        agent = Agent(
            chat_generator=ScriptedChatGenerator(
                policy=NarrateOnlyPolicy(), agent_name="scenario_generator"),
            tools=DM_TOOLS,
            system_prompt="You are a test DM.",
            exit_conditions=["text"],
            max_agent_steps=10,
            raise_on_tool_invocation_failure=False,
            state_schema={},
        )
        assert agent is not None

    def test_agent_loop_executes_real_tools(self):
        """THE decisive assertion: the tool must actually run, not just be requested.

        `roll_dice` is chosen because its output is unforgeable — a real 1d20 result
        lands in [1,20]. If the loop only *recorded* the request, no result message
        would exist to parse.
        """
        from haystack.components.agents import Agent
        from agents.dm_tools import DM_TOOLS

        policy = ToolSequencePolicy(
            [make_tool_call("roll_dice", notation="1d20")],
            summary="A die was rolled.",
        )
        agent = Agent(
            chat_generator=ScriptedChatGenerator(
                policy=policy, agent_name="scenario_generator"),
            tools=DM_TOOLS,
            system_prompt="You are a test DM. Use tools.",
            exit_conditions=["text"],
            max_agent_steps=10,
            raise_on_tool_invocation_failure=False,
            state_schema={},
        )

        result = agent.run(messages=[ChatMessage.from_user("Roll a d20.")])
        messages = result["messages"]

        assert policy.executed == ["roll_dice"], (
            f"the Agent never invoked the tool; executed={policy.executed}"
        )

        results = [m for m in messages if getattr(m, "tool_call_results", None)]
        assert results, (
            "no tool RESULT message — the Agent requested the tool but never ran it, "
            "so tool-driven coverage is impossible through this path"
        )

        payload = results[0].tool_call_results[0].result
        assert payload, "tool returned an empty result"
        assert any(str(n) in str(payload) for n in range(1, 21)), (
            f"no plausible d20 value in the real tool output: {payload!r}"
        )

    def test_agent_loop_exits_on_text(self):
        """After its scripted calls the policy emits text, so the loop terminates."""
        from haystack.components.agents import Agent
        from agents.dm_tools import DM_TOOLS

        policy = ToolSequencePolicy(
            [make_tool_call("roll_dice", notation="1d6"),
             make_tool_call("roll_dice", notation="1d8")],
            summary="Two dice were rolled.",
        )
        agent = Agent(
            chat_generator=ScriptedChatGenerator(
                policy=policy, agent_name="scenario_generator"),
            tools=DM_TOOLS,
            system_prompt="Test DM.",
            exit_conditions=["text"],
            max_agent_steps=10,
            raise_on_tool_invocation_failure=False,
            state_schema={},
        )

        messages = agent.run(messages=[ChatMessage.from_user("Roll twice.")])["messages"]

        assert policy.executed == ["roll_dice", "roll_dice"]
        assert messages[-1].text, "loop did not end on a text reply"
        assert len(messages) < 25, "loop ran away instead of exiting on text"


# --------------------------------------------------------------------------- #
# The global injection hook
# --------------------------------------------------------------------------- #

class TestGlobalInjection:
    """`set_global_config_manager()` must redirect all 13 call sites, then restore."""

    def test_scripted_manager_serves_every_agent_name(self):
        agents = ["scenario_generator", "rag_retriever", "npc_controller",
                  "main_interface", "npc_combat_ai", "combat_init",
                  "combat_narrative"]
        manager = ScriptedConfigManager(policy=BasePolicy())

        for name in agents:
            assert isinstance(manager.create_generator(name), ScriptedChatGenerator)

    def test_missing_policy_raises_rather_than_defaulting(self):
        manager = ScriptedConfigManager(policies={"main_interface": BasePolicy()})
        manager.create_generator("main_interface")           # fine

        with pytest.raises(AssertionError, match="no scripted policy"):
            manager.create_generator("scenario_generator")

    def test_context_manager_installs_and_restores(self):
        from config.llm_config import get_global_config_manager

        try:
            before = get_global_config_manager()
        except Exception:
            before = None

        with scripted_llm(policy=BasePolicy()) as manager:
            assert get_global_config_manager() is manager

        assert get_global_config_manager() is before, "global manager leaked"

    def test_config_shape_survives_subclassing(self):
        """Agents read manager.config.<agent>.model/temperature; keep it real."""
        manager = ScriptedConfigManager(policy=BasePolicy())

        for name in ("scenario_generator", "rag_retriever", "npc_controller",
                     "main_interface", "default_fallback"):
            cfg = getattr(manager.config, name)
            assert cfg.model == "fake-model"
            assert 0.0 <= cfg.temperature <= 1.0
            assert cfg.max_tokens > 0

    def test_tool_calls_made_is_queryable(self):
        with scripted_llm(policy=ToolSequencePolicy(
                [make_tool_call("get_world_state")])) as manager:
            class _Tool:
                name = "get_world_state"

            manager.create_generator("scenario_generator").run(
                [ChatMessage.from_user("look")], tools=[_Tool()])

            assert "get_world_state" in manager.tool_calls_made()
