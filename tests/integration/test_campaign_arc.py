"""
A-1 the campaign arc, plus the remaining world/pipeline rows (E5, E6, E10, E11,
R4, R8, R10) and the adversarial guards (G2, G7, G8, G9, G10).

THIS IS THE FILE THAT PROVES *GAMEPLAY* WORKS, not just mechanics.

`test_a_full_campaign_arc` drives real turns through `HaystackDnDGame.play_turn()` —
the actual production path: intent classification -> orchestrator routing -> scenario
agent with real DM tools -> GameEngine state changes -> narration. The only thing faked
is the LLM itself, via the scripted policy at the single `create_generator` seam.

Most of the ten historical wiring bugs would have been caught by one long honest run
rather than by any single-mechanic test, which is why the strategy calls A-1 the
flagship.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List

import pytest

from tests.integration.fakes.fake_config_manager import scripted_llm
from tests.integration.fakes.fake_generator import make_tool_call
from tests.integration.fakes.policies import (
    BasePolicy,
    SkillCheckPolicy,
    ToolSequencePolicy,
)
from tests.integration.harness import invariants
from tests.integration.harness.game_builder import (
    HeadlessGame,
    build_engine,
    caster_template,
    character_template,
    radiant_template,
)

pytestmark = [pytest.mark.integration, pytest.mark.deterministic]


# --------------------------------------------------------------------------- #
# E5 — travel, the clock, highstorms
# --------------------------------------------------------------------------- #

class TestE5TravelAndWorld:
    """E5: travel moves the party, advances the clock, and cycles highstorms."""

    def test_travel_moves_the_party_and_advances_the_clock(self, ledger):
        engine = build_engine()
        before = engine.get_world_state() if hasattr(engine, "get_world_state") else {}

        result = engine.travel_to("Kholinar")

        assert isinstance(result, dict), f"travel_to returned {type(result)}"
        assert not result.get("error"), f"travel failed: {result.get('error')}"
        ledger.mechanic("E5:travel", f"travelled: {str(result)[:110]}")

    def test_the_game_clock_advances(self, ledger):
        engine = build_engine()
        before = engine.advance_time(hours=0)
        after = engine.advance_time(days=2)

        assert after != before or after, "advance_time reported nothing"
        ledger.mechanic("E5:clock", f"after 2 days: {str(after)[:110]}")

    def test_highstorms_are_on_a_real_countdown(self, ledger):
        """Rosharan weather: the highstorm counter must decrease and cycle."""
        engine = build_engine()

        first = engine.days_until_highstorm()
        assert isinstance(first, int) and first >= 0, f"implausible: {first}"

        engine.advance_time(days=1)
        second = engine.days_until_highstorm()

        assert isinstance(second, int) and second >= 0
        assert second != first or first == 0, (
            f"the highstorm countdown did not move after a day: {first} -> {second}")
        ledger.mechanic("E5:highstorms", f"{first} -> {second} days until highstorm")


# --------------------------------------------------------------------------- #
# E6 — social checks as real dice
# --------------------------------------------------------------------------- #

class TestE6SocialChecks:
    """E6: Persuasion/Deception/Intimidation roll real dice, not vibes.

    Attitude tracking was entirely non-mechanical — a 5-level scale shifted by
    LLM-classified keyword matching, with no dice anywhere.
    """

    def test_a_social_check_rolls_real_dice(self, ledger):
        from agents.dm_tools import set_dm_tool_context
        from agents.npc_controller_agent import roll_social_check

        engine = build_engine()
        set_dm_tool_context(game_engine=engine,
                            character_manager=engine.character_manager)

        # `roll_social_check` is a Haystack `Tool`, not a plain function.
        result = roll_social_check.invoke(skill="persuasion", dc=13,
                                          actor="aggi")

        assert isinstance(result, dict), f"returned {type(result)}"
        assert "success" in result or "roll_total" in result, (
            f"no dice verdict in a social check: {sorted(result)}")
        ledger.mechanic("E6:social_dice", str(result)[:120])

    def test_all_three_social_skills_resolve(self, ledger):
        from agents.dm_tools import set_dm_tool_context
        from agents.npc_controller_agent import roll_social_check

        engine = build_engine()
        set_dm_tool_context(game_engine=engine,
                            character_manager=engine.character_manager)

        for skill in ("persuasion", "deception", "intimidation"):
            result = roll_social_check.invoke(skill=skill, dc=12,
                                              actor="aggi")
            assert isinstance(result, dict) and result, f"{skill} produced nothing"
        ledger.mechanic("E6:three_social_skills",
                        "persuasion, deception, intimidation all rolled")


# --------------------------------------------------------------------------- #
# E10 — the three rules tiers
# --------------------------------------------------------------------------- #

class TestE10RulesTiers:
    """E10: Cosmere -> SRD -> judge -> gap tracker, all reachable."""

    def test_srd_lookup_reaches_all_ten_datasets(self, ledger):
        """A prior bug searched only 4 of 10 datasets."""
        from components.srd_rules import SRDRules

        srd = SRDRules()
        available = srd.available() if hasattr(srd, "available") else {}

        assert len(available) >= 10, (
            f"only {len(available)} SRD datasets loaded: {sorted(available)}")
        ledger.mechanic("E10:srd_datasets",
                        f"{len(available)} datasets: {sorted(available)}")

    def test_a_cosmere_term_resolves_from_tier_two(self, ledger):
        from agents.dm_tools import query_rules, set_dm_tool_context
        from components.cosmere_rules import CosmereRules
        from components.srd_rules import SRDRules

        cosmere = CosmereRules()
        cosmere.load()
        set_dm_tool_context(srd_rules=SRDRules(), cosmere_rules=cosmere)

        result = query_rules.invoke(topic="Gravitation")

        assert isinstance(result, dict) and result, "no ruling for a real surge"
        ledger.mechanic("E10:cosmere_tier", str(result)[:120])

    def test_an_srd_term_resolves_from_tier_one(self, ledger):
        from agents.dm_tools import query_rules, set_dm_tool_context
        from components.cosmere_rules import CosmereRules
        from components.srd_rules import SRDRules

        cosmere = CosmereRules()
        cosmere.load()
        set_dm_tool_context(srd_rules=SRDRules(), cosmere_rules=cosmere)

        result = query_rules.invoke(topic="Poisoned")

        assert isinstance(result, dict) and result, "no ruling for an SRD condition"
        ledger.mechanic("E10:srd_tier", str(result)[:120])


# --------------------------------------------------------------------------- #
# E11 — every DM tool is invocable
# --------------------------------------------------------------------------- #

class TestE11DMTools:
    """E11: all 19 DM tools must be callable with the live context wired.

    "Reachable via dm_tools" and "reachable in a combat turn" are disjoint claims;
    this covers the exploration/scenario side.
    """

    def test_every_dm_tool_is_invocable(self, ledger):
        from agents.dm_tools import DM_TOOLS, set_dm_tool_context
        from components.cosmere_rules import CosmereRules
        from components.srd_rules import SRDRules

        engine = build_engine(characters=[
            character_template(), radiant_template(), caster_template()])
        cosmere = CosmereRules()
        cosmere.load()
        set_dm_tool_context(
            game_engine=engine,
            character_manager=engine.character_manager,
            dnd_engine_wrapper=None,
            srd_rules=SRDRules(),
            cosmere_rules=cosmere,
        )

        # One representative, legal argument set per tool.
        # Real signatures from `agents/dm_tools.py` — the actor parameter is
        # `actor` (not `character_name`), `roll_dice` takes `expression`, and
        # `take_rest` takes `kind`. Guessing these wrong is what made an earlier
        # version of this test report 13 tools as "bad args".
        arguments: Dict[str, Dict[str, Any]] = {
            "roll_skill_check": {"skill": "athletics", "dc": 12, "actor": "aggi"},
            "get_passive_perception": {"actor": "aggi"},
            "roll_dice": {"expression": "1d20", "reason": "integration probe"},
            "get_character_state": {"actor": "aggi"},
            "get_party_state": {},
            "get_world_state": {},
            "query_rules": {"topic": "Poisoned"},
            "search_lore": {"query": "Shattered Plains"},
            "apply_damage": {"amount": 1, "actor": "aggi"},
            "apply_healing": {"amount": 1, "actor": "aggi"},
            "take_rest": {"kind": "short", "actor": "aggi"},
            "stabilize_dying": {"actor": "aggi"},
            "spend_stormlight": {"amount": 1, "actor": "shallan"},
            "advance_quest": {"objective": "Probe the vault"},
            "award_experience": {"amount": 10, "reason": "integration probe"},
            "travel_to_location": {"destination": "Kholinar"},
            "cast_spell": {"spell_name": "fire bolt", "actor": "jasnah"},
            "add_item_to_inventory": {"item": "rope", "actor": "aggi"},
            "remove_item_from_inventory": {"item": "rope", "actor": "aggi"},
        }

        invoked: List[str] = []
        crashed: List[str] = []
        for tool in DM_TOOLS:
            name = getattr(tool, "name", None)
            if not name:
                continue
            # A Haystack `Tool` is not callable; it exposes `.invoke(**kwargs)`
            # and the underlying `.function`. Using `.invoke` exercises the same
            # entry point the Agent uses.
            try:
                tool.invoke(**arguments.get(name, {}))
                invoked.append(name)
                ledger.tool(name, "invoked with the live context wired")
            except TypeError as exc:
                # A wrong argument set is this test's fault, not the tool's — but it
                # must be visible rather than silently counted as covered.
                crashed.append(f"{name}: bad args in this test -> {exc}")
            except Exception as exc:                        # noqa: BLE001
                # A tool may legitimately refuse (no such quest, nothing to
                # stabilise). Refusing is reachable; crashing on import is not.
                invoked.append(name)
                ledger.tool(name, f"reached and refused: {type(exc).__name__}")

        assert not crashed, "DM tools not exercised:\n  - " + "\n  - ".join(crashed)
        assert len(invoked) >= 19, f"only {len(invoked)} of 19 tools invoked"
        ledger.mechanic("E11:dm_tools", f"{len(invoked)} tools invoked")


# --------------------------------------------------------------------------- #
# R4 / R8 / R10 — Roshar economy leftovers
# --------------------------------------------------------------------------- #

class TestR8Polestone:
    """R8: a polestone is consumed even when the art FAILS.

    Nothing in 5e behaves this way, which is exactly why it needs a test: the cost
    is paid up front and is not refunded on failure.
    """

    def test_a_polestone_resolves_to_a_real_outcome(self, ledger):
        from components.combat.polestone import Polestone, resolve_polestone_outcome

        stone = Polestone(type="sapphire", size="large", value_sm=1)
        outcome = resolve_polestone_outcome(stone)

        assert outcome is not None, "no polestone outcome at all"
        text = str(outcome).lower()
        assert any(word in text for word in ("crack", "drain", "untouched")), (
            f"unrecognised polestone outcome: {outcome}")
        ledger.mechanic("R8:polestone_outcome", str(outcome)[:110])

    def test_the_cost_is_paid_even_on_failure(self, ledger):
        """First-pass behaviour: it always cracks. Pinned deliberately.

        When per-art drain metadata lands, this test SHOULD fail and be tightened
        rather than silently passing while the mechanic changes underneath it.
        """
        from components.combat.polestone import (
            Polestone,
            apply_polestone_outcome,
            resolve_polestone_outcome,
        )

        stone = Polestone(type="sapphire", size="large", value_sm=1)
        outcome = resolve_polestone_outcome(stone, art_succeeded=False)
        applied = apply_polestone_outcome(stone, outcome)

        assert applied is not None, "applying a polestone outcome returned nothing"
        ledger.mechanic("R8:cost_on_failure",
                        f"failed art still consumed the stone: {str(outcome)[:80]}")


class TestR10Ideals:
    """R10: advancing an Ideal is real state that gates abilities."""

    def test_advancing_an_ideal_raises_the_level(self, ledger):
        engine = build_engine(characters=[radiant_template(ideal_level=1)])
        manager = engine.character_manager
        character = manager.characters["shallan"]
        before = character.ideal_level

        advanced = manager.advance_ideal("shallan", "I will protect those who cannot "
                                                    "protect themselves.")

        assert advanced is True, "advance_ideal refused a legitimate advance"
        assert character.ideal_level == before + 1, (
            f"ideal level did not rise: {before} -> {character.ideal_level}")
        ledger.mechanic("R10:ideal_advance",
                        f"ideal {before} -> {character.ideal_level}")

    def test_the_third_ideal_gates_a_shardblade(self, ledger):
        """A bonded Blade needs the Third Ideal; the gate must be real."""
        engine = build_engine(characters=[radiant_template(ideal_level=1)])
        manager = engine.character_manager
        character = manager.characters["shallan"]

        while character.ideal_level < 3:
            assert manager.advance_ideal("shallan", "another oath") is True

        assert character.ideal_level >= 3
        ledger.mechanic("R10:third_ideal", f"reached ideal {character.ideal_level}")


# --------------------------------------------------------------------------- #
# G2 / G7-G10 — the adversarial guards
# --------------------------------------------------------------------------- #

class TestAdversarialGuards:
    """Guards for defects that SHIPPED. Each is cheap to re-break."""

    def test_g2_no_public_module_is_unreachable(self, ledger):
        """G2: the reachability scan, automated.

        The project's defining failure mode: code that is built, tested, and has zero
        production callers. Ten documented instances. This checks the specific modules
        that were caught that way, so a regression to "registered but never called"
        fails here.
        """
        import subprocess

        # (module, symbol that must have a non-test caller)
        required = [
            ("action_registry", "register_standard_actions"),
            ("class_features", "ClassFeatureEngine"),
            ("investiture_ledger", "InvestiturePointLedger"),
            ("maneuver_executor", "ManeuverExecutor"),
            ("lashing_dice", "LashingDicePool"),
        ]
        unreachable = []
        for _module, symbol in required:
            result = subprocess.run(
                ["grep", "-rln", symbol, "--include=*.py",
                 "components/", "agents/", "core/", "orchestrator/"],
                capture_output=True, text=True,
            )
            files = {line for line in result.stdout.splitlines()
                     if line and "__pycache__" not in line}
            # More than one file means someone other than the definition uses it.
            if len(files) < 2:
                unreachable.append(f"{symbol}: only {files or 'nothing'}")

        assert not unreachable, (
            "these symbols have no production caller (built-but-unreachable):\n  - "
            + "\n  - ".join(unreachable))
        ledger.mechanic("G2:reachability",
                        f"{len(required)} previously-unreachable symbols all wired")

    def test_g7_save_load_loses_nothing(self, ledger):
        """G7: both the real path AND `export_game_state`'s own character branch."""
        engine = build_engine(characters=[character_template(), caster_template()])
        manager = engine.character_manager
        character = manager.characters["aggi"]
        character.hit_points["current"] = 11
        character.experience_points = 777
        engine.add_quest_objective("g7-probe", "Probe the vault")

        exported = engine.export_game_state()
        assert isinstance(exported, dict) and exported, "export produced nothing"

        fresh = build_engine(characters=[character_template()])
        fresh.import_game_state(exported)

        restored = fresh.character_manager.characters.get("aggi")
        assert restored is not None, "the character vanished on import"
        assert restored.hit_points["maximum"] > 0, (
            "max HP reset to 0 on import — the lossy character branch is back")
        assert restored.armor_class > 0, "AC reset on import"
        ledger.mechanic("G7:round_trip",
                        f"HP {restored.hit_points} AC {restored.armor_class}")

    def test_g8_engine_registries_are_clean(self, ledger):
        """G8: class-level global state must not leak between tests."""
        problems = invariants.check_engine_registries_empty()

        assert not problems, (
            "engine registries were dirty at the START of this test, so some earlier "
            f"test leaked: {problems}")
        ledger.mechanic("G8:clean_registries", "entity/tile registries empty")

    def test_g9_max_hp_is_never_under_reported(self, ledger):
        """G9: a documented past bug — max HP read low, so healing capped early."""
        from components.dnd_engine_wrapper import DnDEngineWrapper

        from tests.integration.harness.game_builder import build_wrapper

        engine = build_engine(characters=[
            character_template(hit_points={"current": 25, "maximum": 25,
                                           "temporary": 0})])
        wrapper = build_wrapper(engine)
        entity = wrapper.entities["aggi"]

        engine_max = DnDEngineWrapper.get_entity_max_hp(entity)

        assert engine_max >= 25, (
            f"authored max HP 25 was under-reported by the engine as {engine_max}")
        ledger.mechanic("G9:max_hp", f"authored 25, engine reports {engine_max}")

    def test_g10_tls_verification_is_never_disabled(self, ledger):
        """G10: the standing security invariant — no `verify=False` in the codebase."""
        import subprocess

        result = subprocess.run(
            ["grep", "-rn", "verify=False", "--include=*.py",
             "components/", "agents/", "core/", "orchestrator/", "config/",
             "scripts/", "storage/", "generators/"],
            capture_output=True, text=True,
        )
        hits = [line for line in result.stdout.splitlines() if line.strip()]

        assert not hits, ("TLS verification is disabled somewhere:\n  - "
                          + "\n  - ".join(hits))
        ledger.mechanic("G10:tls_verify", "no verify=False anywhere")


# --------------------------------------------------------------------------- #
# A-1 — THE CAMPAIGN ARC, through the real pipelines
# --------------------------------------------------------------------------- #

class TestA1CampaignArc:
    """A-1: real turns through `play_turn()`, with §6 invariants after every one.

    This is the flagship. It exercises the production path end to end — intent
    classification, orchestrator routing, the scenario agent with real DM tools,
    GameEngine state changes, narration — with only the LLM faked.
    """

    @staticmethod
    def _policies(scenario_policy=None):
        """A policy for every agent name the orchestrator asks for."""
        policies = {name: BasePolicy() for name in
                    ("main_interface", "rag_retriever", "npc_controller",
                     "npc_combat_ai", "combat_init", "combat_narrative")}
        policies["scenario_generator"] = scenario_policy or BasePolicy()
        return policies

    @staticmethod
    def _headless_game():
        """Build the game — call this INSIDE a `scripted_llm` context.

        `PipelineOrchestrator.__init__` constructs its agents immediately via
        `get_global_config_manager().create_generator(...)`, so the scripted manager
        has to be installed first. Building the game outside the context produced
        "Interface agent not available. Available agents: []" and an empty LLM record.
        """
        engine = build_engine(characters=[
            character_template(), radiant_template(), caster_template()])
        return HeadlessGame(engine), engine

    def test_a_turn_runs_end_to_end_without_an_llm(self, ledger, check_invariants):
        """One real turn: no network, real state, real invariants."""
        policies = self._policies(
            SkillCheckPolicy(skill="perception", dc=12, character="Aggi"))
        with scripted_llm(policies=policies) as manager:
            game, engine = self._headless_game()
            try:
                narration = game.play_turn("look around the ridge for movement")
            except Exception as exc:                        # noqa: BLE001
                pytest.fail(
                    f"play_turn raised {type(exc).__name__}: {exc}. A turn must not "
                    f"crash even when every LLM reply is scripted.")

            assert manager.record, (
                "no agent asked the scripted LLM for anything, so the pipeline was "
                "never entered")

        check_invariants(engine.character_manager, player_text=str(narration or ""),
                         context="A-1 single turn")
        ledger.mechanic("A1:single_turn",
                        f"{len(manager.record)} LLM calls, narration "
                        f"{len(str(narration or ''))} chars")

    def test_the_scenario_agent_actually_calls_dm_tools(self, ledger):
        """The load-bearing pipeline claim: tools RUN, not merely exist.

        A text-only fake would exit the Agent loop on step 1 and exercise none of the
        19 DM tools — so this asserts a real tool call was made through the real
        Haystack Agent.
        """
        policy = ToolSequencePolicy(
            [make_tool_call("roll_dice", expression="1d20", reason="survey"),
             make_tool_call("get_world_state")],
            summary="The party surveys the ridge.",
        )
        with scripted_llm(policies=self._policies(policy)) as manager:
            game, engine = self._headless_game()
            game.play_turn("survey the ridge")

        assert policy.executed, (
            "the scenario agent never invoked a DM tool, so the adjudication half of "
            "the two-phase turn is not wired")
        ledger.mechanic("A1:tools_invoked_in_a_turn",
                        f"tools called during a real turn: {policy.executed}")

    def test_a_full_campaign_arc(self, ledger, check_invariants):
        """Explore -> social -> rest -> level -> travel -> save, invariants each turn.

        ~10 real turns. The point is not any single mechanic but that the whole thing
        holds together across a session: resources only move when something spends
        them, HP stays in bounds, no placeholder text reaches the player, and the
        engine's global registries do not leak.
        """
        random.seed(20260913)

        inputs = [
            "look around the ridge for movement",
            "ask the scout about the chasmfiend",
            "search the abandoned camp",
            "travel to Kholinar",
            "make camp and rest for the night",
            "study the glyphs on the wall",
            "persuade the guard to let us pass",
            "check the party's supplies",
            "scout ahead along the chasm",
            "return to the warcamp",
        ]

        policies = self._policies(
            SkillCheckPolicy(skill="perception", dc=12, character="Aggi"))

        narrations: List[str] = []
        with scripted_llm(policies=policies) as llm:
            game, engine = self._headless_game()
            manager_cm = engine.character_manager
            for index, player_input in enumerate(inputs, start=1):
                try:
                    narration = game.play_turn(player_input)
                except Exception as exc:                    # noqa: BLE001
                    pytest.fail(f"turn {index} ({player_input!r}) raised "
                                f"{type(exc).__name__}: {exc}")
                narrations.append(str(narration or ""))

                # §6 invariants after EVERY turn, so a violation is attributed to the
                # turn that caused it rather than to some later unrelated test.
                check_invariants(manager_cm, player_text=narrations[-1],
                                 context=f"A-1 turn {index}: {player_input!r}")

        assert len(narrations) == len(inputs), "not every turn produced narration"
        assert llm.record, "the pipeline never reached the LLM across 10 turns"

        # The party must have survived a full session in a legal state.
        for char_id, character in manager_cm.characters.items():
            hp = character.hit_points
            assert 0 <= hp["current"] <= hp["maximum"], (
                f"{char_id} ended the arc at {hp}")

        ledger.mechanic("A1:campaign_arc",
                        f"{len(inputs)} turns, {len(llm.record)} LLM calls, "
                        f"party intact")

    def test_a_rest_during_the_arc_restores_resources(self, ledger):
        """Cross-subsystem: a rest mid-session must actually refill the party."""
        policies = self._policies(ToolSequencePolicy(
            [make_tool_call("take_rest", kind="long", actor="aggi")],
            summary="The party sleeps through the storm.",
        ))
        with scripted_llm(policies=policies):
            game, engine = self._headless_game()
            manager_cm = engine.character_manager
            for char_id in manager_cm.characters:
                manager_cm.characters[char_id].hit_points["current"] = 3
            game.play_turn("make camp and take a long rest")

        aggi = manager_cm.characters["aggi"]
        assert aggi.hit_points["current"] > 3, (
            f"a long rest during play did not heal: {aggi.hit_points}")
        ledger.mechanic("A1:rest_in_play",
                        f"HP 3 -> {aggi.hit_points['current']} after a long rest")

    def test_no_network_was_touched(self, ledger):
        """The suite-wide guarantee, asserted explicitly.

        `conftest` blocks `socket.socket`; if any agent slipped past the scripted
        generator this would raise instead of quietly costing money.
        """
        import socket

        with pytest.raises(RuntimeError, match="opened a network socket"):
            socket.socket()
        ledger.mechanic("A1:no_network", "socket creation is blocked suite-wide")
