"""
The scenario turn is TWO calls: adjudicate, then narrate.

THE DESIGN ERROR THIS FIXES. One call tried to be both agentic (13 DM tools) and
structured-output (a JSON schema). Gemini rejects that combination:

    400 INVALID_ARGUMENT "Function calling with a response mime type:
    'application/json' is unsupported"

An earlier patch hid the 400 by silently DROPPING the schema whenever tools were
present. The model was then told by prompt to emit schema-shaped JSON with
nothing enforcing it, so it kept calling tools hunting for certainty and never
wrote the plain-text message that satisfies exit_conditions=["text"]. Live turns
burned all 10 steps; the player got "A mysterious pause settles over the scene."

Note this is a GEMINI constraint, not a Haystack one — the same request from
LangGraph or the raw SDK returns the same 400. Splitting the phases is required
regardless of framework.

  Phase A  create_scenario_generator_agent()  tools, NO schema  -> facts
  Phase B  narrate_scene()                    schema, NO tools  -> scene JSON
"""

import json

import pytest
from haystack.dataclasses import ChatMessage


pytestmark = pytest.mark.unit


VALID_SCENE = {
    "scene": "The ridge wind claws at your cloak; rockbud shells crack underfoot.",
    "choices": [
        {"id": "c1", "title": "Press on", "description": "Follow the tracks",
         "skill_hints": ["survival"], "suggested_dc": 12, "combat_trigger": False},
    ],
    "gm_notes": "nothing hidden",
}

# The canned strings that used to reach the player when the single call failed.
CANNED = ("A mysterious pause settles over the scene",
          "You find yourself in a moment of decision",
          "Wait and Observe",
          "Continue Forward")


class _Generator:
    """Returns fixed JSON and records how it was called."""

    def __init__(self, payload=None):
        self.payload = payload if payload is not None else VALID_SCENE
        self.calls = 0

    def run(self, messages):
        self.calls += 1
        self.last_messages = messages
        body = (self.payload if isinstance(self.payload, str)
                else json.dumps(self.payload))
        return {"replies": [ChatMessage.from_assistant(body)]}


class TestPhasesAreSeparated:

    def test_adjudication_phase_has_tools_and_no_schema(self):
        """Tools + schema is the 400. This phase must carry tools only."""
        from agents.scenario_generator_agent import create_scenario_generator_agent

        agent = create_scenario_generator_agent()
        assert len(agent.tools) == 13, "adjudication needs the DM tools"
        config = agent.chat_generator.generation_config
        assert "response_schema" not in config, \
            "a schema here makes every tool call 400"
        assert "response_mime_type" not in config

    def test_narration_phase_has_schema_and_no_tools(self):
        """The schema is now genuinely enforced, not silently dropped."""
        from config.llm_config import get_global_config_manager
        from agents.scenario_generator_agent import SCENARIO_RESPONSE_SCHEMA

        generator = get_global_config_manager().create_generator(
            "scenario_generator", response_schema=SCENARIO_RESPONSE_SCHEMA)
        assert generator.generation_config["response_mime_type"] == "application/json"
        assert generator.generation_config["response_schema"]

    def test_adjudication_prompt_forbids_prose(self):
        """Phase A must summarise facts, not write the scene."""
        import inspect
        from agents import scenario_generator_agent

        source = inspect.getsource(
            scenario_generator_agent.create_scenario_generator_agent)
        assert "NOT PLAYER-FACING" in source
        assert "do NOT emit JSON" in source

    def test_narration_prompt_forbids_changing_outcomes(self):
        from agents.scenario_generator_agent import NARRATION_SYSTEM_PROMPT

        assert "MAY NOT CHANGE WHAT HAPPENED" in NARRATION_SYSTEM_PROMPT
        assert "roll failed" in NARRATION_SYSTEM_PROMPT


class TestNarrateScene:

    def test_produces_a_scene_from_findings(self):
        from agents.scenario_generator_agent import narrate_scene

        generator = _Generator()
        result = narrate_scene("Stealth 14 vs DC 13 -> success. No damage.",
                               "LOCATION: Playtest Ridge",
                               chat_generator=generator)
        assert result["scene"] == VALID_SCENE["scene"]
        assert generator.calls == 1

    def test_findings_are_sent_to_the_model(self):
        """Otherwise the narration would invent what happened."""
        from agents.scenario_generator_agent import narrate_scene

        generator = _Generator()
        narrate_scene("Stealth 14 vs DC 13 -> FAILED.", "LOCATION: Ridge",
                      chat_generator=generator)
        sent = " ".join(getattr(m, "text", "") or "" for m in generator.last_messages)
        assert "Stealth 14 vs DC 13 -> FAILED." in sent
        assert "LOCATION: Ridge" in sent

    def test_empty_scene_is_rejected(self):
        from agents.scenario_generator_agent import narrate_scene

        generator = _Generator({"scene": "   ", "choices": [], "gm_notes": ""})
        assert narrate_scene("f", "c", chat_generator=generator) == {}
        assert generator.calls == 2, "should retry before giving up"

    def test_unparseable_output_gives_up_cleanly(self):
        from agents.scenario_generator_agent import narrate_scene

        generator = _Generator("this is not json at all")
        assert narrate_scene("f", "c", chat_generator=generator) == {}


class TestValidatorRunsPhaseB:

    def _scene_of(self, result):
        payload = result["validated_scenario"]
        return (payload.get("scenario") or payload).get("scene", "")

    def test_findings_text_is_narrated_not_shown(self, monkeypatch):
        """
        Phase A returns "Stealth 14 vs DC 13: success" — mechanical notes.

        The old code lifted the first long line straight into "scene", so the
        player could be shown the DM's working. It must go through Phase B.
        """
        import agents.scenario_generator_agent as module

        monkeypatch.setattr(module, "narrate_scene",
                            lambda findings, context, recent_scenes=None: dict(VALID_SCENE))
        validator = module.ScenarioValidatorComponent()
        result = validator.run(
            messages=[ChatMessage.from_assistant(
                "Stealth check 14 vs DC 13: success. Nothing was damaged.")],
            prompt_context="LOCATION: Playtest Ridge")

        scene = self._scene_of(result)
        assert scene == VALID_SCENE["scene"]
        assert "DC 13" not in scene, "mechanical notes leaked to the player"

    def test_phase_b_receives_the_findings_and_context(self, monkeypatch):
        import agents.scenario_generator_agent as module

        seen = {}

        def spy(findings, context, recent_scenes=None):
            seen["findings"], seen["context"] = findings, context
            return dict(VALID_SCENE)

        monkeypatch.setattr(module, "narrate_scene", spy)
        module.ScenarioValidatorComponent().run(
            messages=[ChatMessage.from_assistant("Rolled 14, succeeded.")],
            prompt_context="LOCATION: Ridge | QUEST: find the spren")

        assert "Rolled 14" in seen["findings"]
        assert "find the spren" in seen["context"]

    def test_json_from_the_agent_is_still_honoured(self, monkeypatch):
        """A caller that does emit scene JSON must not be second-guessed."""
        import agents.scenario_generator_agent as module

        called = {"n": 0}

        def spy(findings, context, recent_scenes=None):
            called["n"] += 1
            return {}

        monkeypatch.setattr(module, "narrate_scene", spy)
        result = module.ScenarioValidatorComponent().run(
            messages=[ChatMessage.from_assistant(json.dumps(VALID_SCENE))],
            prompt_context="")

        assert self._scene_of(result) == VALID_SCENE["scene"]
        assert called["n"] == 0, "Phase B should not run when JSON already exists"

    def test_no_canned_text_when_narration_fails(self, monkeypatch):
        """
        The last-resort fallback must be honest, and must not be one of the
        strings that made two live turns identical.
        """
        import agents.scenario_generator_agent as module

        monkeypatch.setattr(module, "narrate_scene",
                            lambda findings, context, recent_scenes=None: {})
        result = module.ScenarioValidatorComponent().run(
            messages=[ChatMessage.from_assistant("some findings")],
            prompt_context="")

        scene = self._scene_of(result)
        assert scene, "a turn must never return an empty scene"
        for phrase in CANNED:
            assert phrase not in scene, f"canned text {phrase!r} still reachable"


class TestPromptContextIsWired:
    """Phase B needs the same context block Phase A adjudicated against."""

    def test_prompt_builder_emits_prompt_context(self):
        from agents.scenario_generator_agent import PromptBuilderComponent

        output = PromptBuilderComponent().run(dto={"player_input": "look around"})
        assert output.get("prompt_context"), \
            "without this the narration call does not know where the party is"
        assert output["messages"]

    def test_pipeline_connects_it_to_the_validator(self):
        import inspect
        from orchestrator import pipeline_integration

        source = inspect.getsource(pipeline_integration)
        assert 'prompt_builder.prompt_context' in source
        assert 'validator.prompt_context' in source


class TestAutomaticFunctionCallingIsDisabled:
    """
    AFC must be off on EVERY call, not only tool-carrying ones.

    The SDK defaults it ON ("Default to enable AFC if not specified" —
    google/genai/_extra_utils.should_disable_afc). A first attempt at this fix
    put the disable inside the `if gemini_tools` branch, so tool-less calls (the
    interface agent, Phase B narration) still entered the AFC path and the live
    log still printed "AFC is enabled with max remote calls: 10" ten times.
    """

    def _config_for(self, tools):
        from config.llm_utils import GeminiChatGenerator

        generator = GeminiChatGenerator(
            model_name="gemini-2.5-flash", generation_config={})
        captured = {}

        class _Part:
            text = "ok"
            function_call = None

        class _Content:
            parts = [_Part()]

        class _Candidate:
            content = _Content()
            finish_reason = None

        class _Response:
            candidates = [_Candidate()]
            prompt_feedback = None
            text = "ok"

        class _FakeModels:
            def generate_content(self, model, contents, config):
                captured["config"] = config
                return _Response()

        class _FakeClient:
            models = _FakeModels()

        generator.client = _FakeClient()
        generator.run(messages=[ChatMessage.from_user("hi")], tools=tools)
        return captured["config"]

    def test_disabled_with_tools(self):
        from google.genai import _extra_utils
        from agents.dm_tools import DM_TOOLS

        config = self._config_for(DM_TOOLS)
        assert config.automatic_function_calling.disable is True
        assert _extra_utils.should_disable_afc(config) is True

    def test_disabled_without_tools(self):
        """The case the first attempt missed."""
        from google.genai import _extra_utils

        config = self._config_for(None)
        assert config.automatic_function_calling.disable is True
        assert _extra_utils.should_disable_afc(config) is True, \
            "a tool-less call still entered the SDK's AFC path"


# The actual repeated scene from the 12-turn playtest (turns 8 and 9), trimmed.
REPEATED_SCENE = (
    "Your meticulous search of the immediate descent area from Playtest Ridge, "
    "following your initial overview, yields little in the way of immediate "
    "utility. The ground is a churned mess of fractured rockbuds and shattered "
    "wood, smelling sharply of ozone, ash, and the metallic tang of dried blood."
)

FRESH_SCENE = (
    "You hold your breath, straining your ears against the whipping wind. A "
    "rhythmic thump carries up from the ruined town below, too regular and too "
    "heavy to be settling debris."
)


class TestDuplicateSceneDetection:
    """
    A 12-turn playtest returned a byte-identical 2339-char scene on turns 8 and 9
    — with DIFFERENT player inputs ("search the area" vs "listen carefully") and
    two fresh skill checks rolled on turn 9. Adjudication worked; the narration
    ignored both the new action and the new rolls.

    Cause: story_so_far puts previous scenes verbatim into the prompt under
    "maintain continuity with these", so the model had the old scene in front of
    it and echoed it. Nothing said the new scene had to differ.
    """

    def test_exact_repeat_is_detected(self):
        from agents.scenario_generator_agent import _scenes_are_duplicates
        assert _scenes_are_duplicates(REPEATED_SCENE, REPEATED_SCENE)

    def test_same_opening_is_detected(self):
        """Changing the tail does not make it a new scene to the player."""
        from agents.scenario_generator_agent import _scenes_are_duplicates
        assert _scenes_are_duplicates(
            REPEATED_SCENE + " A shadow moves at the treeline.", REPEATED_SCENE)

    def test_whitespace_and_case_do_not_hide_a_repeat(self):
        from agents.scenario_generator_agent import _scenes_are_duplicates
        assert _scenes_are_duplicates(
            REPEATED_SCENE.upper().replace(" ", "  "), REPEATED_SCENE)

    def test_genuinely_new_prose_is_allowed(self):
        """
        The threshold must not reject good writing. Consecutive scenes in one
        location legitimately share vocabulary (wind, rockbuds, ozone).
        """
        from agents.scenario_generator_agent import _scenes_are_duplicates
        assert not _scenes_are_duplicates(FRESH_SCENE, REPEATED_SCENE)

    def test_empty_input_is_not_a_duplicate(self):
        from agents.scenario_generator_agent import _scenes_are_duplicates
        assert not _scenes_are_duplicates("", REPEATED_SCENE)
        assert not _scenes_are_duplicates(REPEATED_SCENE, "")


class TestNarrationRejectsRepeats:

    def _generator(self, scenes):
        """Yields each scene in turn, so a retry can produce something new."""
        class _Gen:
            calls = 0

            def run(self, messages):
                payload = {
                    "scene": scenes[min(_Gen.calls, len(scenes) - 1)],
                    "choices": [{"id": "c1", "title": "t", "description": "d",
                                 "skill_hints": [], "suggested_dc": 0,
                                 "combat_trigger": False}],
                    "gm_notes": "n",
                }
                _Gen.calls += 1
                return {"replies": [ChatMessage.from_assistant(json.dumps(payload))]}

        return _Gen()

    def test_a_repeat_is_retried_and_recovers(self):
        from agents.scenario_generator_agent import narrate_scene

        generator = self._generator([REPEATED_SCENE, FRESH_SCENE])
        result = narrate_scene("rolled 14, succeeded", "LOCATION: Ridge",
                               chat_generator=generator,
                               recent_scenes=[REPEATED_SCENE])
        assert generator.calls == 2, "the duplicate should have been rejected"
        assert result["scene"] == FRESH_SCENE

    def test_a_persistent_repeat_gives_up_rather_than_shipping_it(self):
        from agents.scenario_generator_agent import narrate_scene

        generator = self._generator([REPEATED_SCENE])
        result = narrate_scene("rolled 14", "LOCATION: Ridge",
                               chat_generator=generator,
                               recent_scenes=[REPEATED_SCENE])
        assert result == {}, "a known repeat must not reach the player"

    def test_no_recent_scenes_means_nothing_is_rejected(self):
        """First turn of a campaign has no history."""
        from agents.scenario_generator_agent import narrate_scene

        generator = self._generator([REPEATED_SCENE])
        result = narrate_scene("f", "c", chat_generator=generator)
        assert result["scene"] == REPEATED_SCENE
        assert generator.calls == 1

    def test_prompt_demands_a_new_scene(self):
        from agents.scenario_generator_agent import NARRATION_SYSTEM_PROMPT

        assert "THIS SCENE MUST BE NEW" in NARRATION_SYSTEM_PROMPT
        assert "NEVER repeat a previous scene" in NARRATION_SYSTEM_PROMPT


class TestRecentScenesAreWired:
    """Detection is useless if the previous scenes never reach Phase B."""

    def test_prompt_builder_emits_recent_scenes(self):
        from agents.scenario_generator_agent import PromptBuilderComponent
        from components.game_engine import GameEngine

        engine = GameEngine()
        engine.process_scenario_state_updates(
            {"scene": "An older scene the player already saw."}, turn_number=1)

        output = PromptBuilderComponent().run(
            dto={"player_input": "look", "_game_engine_ref": engine})

        assert output["recent_scenes"], "previous scenes never reach Phase B"
        assert any("older scene" in s for s in output["recent_scenes"])

    def test_prompt_builder_survives_without_an_engine(self):
        from agents.scenario_generator_agent import PromptBuilderComponent

        output = PromptBuilderComponent().run(dto={"player_input": "look"})
        assert output["recent_scenes"] == []

    def test_pipeline_connects_recent_scenes(self):
        import inspect
        from orchestrator import pipeline_integration

        source = inspect.getsource(pipeline_integration)
        assert "prompt_builder.recent_scenes" in source
        assert "validator.recent_scenes" in source
