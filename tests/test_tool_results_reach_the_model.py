"""
Tool calls and tool RESULTS must reach the model.

The symptom was a DM agent asking for the same state over and over:

    ⚠️ world_state requested 5× this turn — returning a stop-polling directive
    ⚠️ party_state requested 4× this turn — ...
    ⚠️ character_state:Aggi requested 5× this turn — ...

That reads like a model problem. It was not. Measured in a live turn:
**30 function calls, 0 function responses.**

`GeminiChatGenerator` flattens the conversation into a single prompt string, and
both halves of a tool exchange carry `.text is None`:

  * `ChatMessage.from_tool(...)` keeps its payload in `.tool_call_results`
  * `ChatMessage.from_assistant(tool_calls=[...])` keeps its request in `.tool_calls`

The converter read only `.text`/`.content`, so BOTH were converted to `""` and
dropped. From the model's point of view it had never asked — so it asked again,
every step, until it exhausted `max_agent_steps` with no scene written and the
player received a canned fallback.

The `_cached_read` stop-polling directive in `dm_tools.py` was built to suppress
this loop, and it worked only because its counter lives in Python rather than in
the conversation — the directive it returned was itself being dropped. With the
exchange actually reaching the model, that guard becomes a backstop.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

pytestmark = [pytest.mark.unit]

from haystack.dataclasses import ChatMessage, ToolCall

import config.llm_utils as llm_utils


@pytest.fixture
def generator():
    """The converter only — no client, no network."""
    return llm_utils.GeminiChatGenerator.__new__(llm_utils.GeminiChatGenerator)


@pytest.fixture
def exchange():
    call = ToolCall(tool_name="get_world_state", arguments={}, id="c1")
    return [
        ChatMessage.from_user("Aggi looks around."),
        ChatMessage.from_assistant(tool_calls=[call]),
        ChatMessage.from_tool(
            tool_result='{"location":"Kholinar","day":1}', origin=call),
    ]


class TestHaystackKeepsToolDataOutsideText:
    """Pin the API fact the bug depended on, so it cannot silently change."""

    def test_a_tool_result_has_no_text(self):
        call = ToolCall(tool_name="get_world_state", arguments={}, id="c1")
        message = ChatMessage.from_tool(tool_result='{"day":1}', origin=call)
        assert message.text is None, (
            "if .text is populated now, the converter's fallback is dead code")
        assert message.tool_call_results, "the payload must live somewhere"

    def test_a_tool_call_has_no_text(self):
        call = ToolCall(tool_name="get_world_state", arguments={}, id="c1")
        message = ChatMessage.from_assistant(tool_calls=[call])
        assert message.text is None
        assert message.tool_calls


class TestTheResultReachesThePrompt:
    def test_the_payload_appears(self, generator, exchange):
        """The regression proper: this used to convert to ''."""
        prompt = generator._convert_messages_to_prompt(exchange)
        assert "Kholinar" in prompt, (
            f"the tool's answer never reached the model:\n{prompt}")

    def test_the_tool_name_appears(self, generator, exchange):
        """The model must be able to tell WHICH tool answered."""
        assert "get_world_state" in generator._convert_messages_to_prompt(exchange)

    def test_the_models_own_request_appears(self, generator, exchange):
        """
        Without its own call in the transcript the model cannot see that it
        already asked — which is precisely why it kept re-asking.
        """
        prompt = generator._convert_messages_to_prompt(exchange)
        assert "called get_world_state" in prompt

    def test_the_result_is_labelled_as_a_tool_result(self, generator, exchange):
        """Unlabelled, the model may narrate the raw JSON back at the player."""
        assert "Tool result" in generator._convert_messages_to_prompt(exchange)

    def test_ordinary_messages_still_convert(self, generator, exchange):
        """Both directions — the fallback must not disturb normal text."""
        prompt = generator._convert_messages_to_prompt(exchange)
        assert "User: Aggi looks around." in prompt

    def test_a_failed_tool_call_is_reported_as_failed(self, generator):
        """
        A silent failure is worse than a loud one: the model would otherwise
        assume the tool worked and narrate a result it never got.
        """
        call = ToolCall(tool_name="roll_skill_check", arguments={}, id="c1")
        message = ChatMessage.from_tool(
            tool_result="unknown actor 'aggi'", origin=call, error=True)
        prompt = generator._convert_messages_to_prompt([message])
        assert "FAILED" in prompt
        assert "unknown actor" in prompt

    def test_several_results_in_one_message(self, generator):
        calls = [ToolCall(tool_name=f"tool_{i}", arguments={}, id=f"c{i}")
                 for i in range(2)]
        message = ChatMessage.from_tool(tool_result="ok", origin=calls[0])
        assert "tool_0" in generator._convert_messages_to_prompt([message])

    def test_the_arguments_of_a_call_appear(self, generator):
        """`get_character_state(actor='Kali')` differs from `actor='Aggi'`."""
        call = ToolCall(tool_name="get_character_state",
                        arguments={"actor": "Kali"}, id="c1")
        prompt = generator._convert_messages_to_prompt(
            [ChatMessage.from_assistant(tool_calls=[call])])
        assert "Kali" in prompt


class TestTheStructuredConverterToo:
    """`_convert_messages_to_gemini` had the identical `if not content: continue`."""

    def test_the_result_survives(self, generator, exchange):
        contents = generator._convert_messages_to_gemini(exchange)
        rendered = " ".join(part.text for c in contents for part in c.parts)
        assert "Kholinar" in rendered

    def test_no_message_is_dropped(self, generator, exchange):
        assert len(generator._convert_messages_to_gemini(exchange)) == len(exchange)

    def test_roles_are_valid_for_gemini(self, generator, exchange):
        """Gemini accepts only user/model; a `tool` role would be rejected."""
        for content in generator._convert_messages_to_gemini(exchange):
            assert content.role in ("user", "model"), content.role

    def test_the_tool_result_is_labelled(self, generator, exchange):
        contents = generator._convert_messages_to_gemini(exchange)
        tool_texts = [p.text for c in contents for p in c.parts
                      if "Kholinar" in p.text]
        assert tool_texts and tool_texts[0].startswith("Tool result:")

    def test_an_assistant_tool_call_keeps_the_model_role(self, generator):
        call = ToolCall(tool_name="get_world_state", arguments={}, id="c1")
        contents = generator._convert_messages_to_gemini(
            [ChatMessage.from_assistant(tool_calls=[call])])
        assert contents[0].role == "model", (
            "the model's own action must not be attributed to the player")


class TestTheGuardBecomesABackstop:
    """
    `dm_tools._cached_read` still counts reads, but with results reaching the model
    it should not be the thing that ends the loop. Keep it — belt and braces — and
    keep asserting its contract.
    """

    def test_the_directive_is_still_returned_after_the_limit(self):
        from agents import dm_tools

        dm_tools.clear_dm_tool_context()
        for _ in range(dm_tools._MAX_READS_PER_TURN):
            dm_tools._cached_read("probe", lambda: {"data": 1})
        result = dm_tools._cached_read("probe", lambda: {"data": 1})
        assert result.get("unchanged") is True
        assert "WRITE THE SCENE" in result["note"]

    def test_reads_within_the_limit_return_data(self):
        from agents import dm_tools

        dm_tools.clear_dm_tool_context()
        assert dm_tools._cached_read("probe2", lambda: {"data": 7})["data"] == 7

    @pytest.mark.parametrize("reset", ["begin_dm_tool_turn",
                                       "clear_dm_tool_context"])
    def test_the_counter_resets(self, reset):
        """
        A per-turn guard that never resets breaks turn 2 onward — the FIRST read
        of a new turn would be answered with "you have already called this twice".

        Both entry points must reset it. `clear_dm_tool_context()` cleared the
        cache and NOT the counters, which left the guard tripped; found by this
        test.
        """
        from agents import dm_tools

        dm_tools.begin_dm_tool_turn()
        for _ in range(5):
            dm_tools._cached_read("probe3", lambda: {"data": 1})

        getattr(dm_tools, reset)()
        assert dm_tools._cached_read("probe3", lambda: {"data": 1}) == {"data": 1}, (
            f"{reset}() does not reset the read counter")
