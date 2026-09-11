"""
Surgebinding maneuvers as DATA: the automation-tree interpreter (plan 3.1b).

THE SCHEMA WAS ALWAYS THERE; NOTHING READ IT. All nine maneuvers in
`data/rules/stormlight/surgebinding.json` carry complete Avrae-style `automation`
trees — reviewed, with line citations — and the only reader anywhere was
`test_phase2_regressions.py:862`, which asserts the JSON *exists*. So it passed while
**0 of 9 maneuvers could be played**, and `roshar_actions.py` grew one imperative
Python class per ability instead. That is why Surgebinding stalled at 4 of the
rulebook's 10 surges: each new one needed new CODE.

This is the mechanism that makes a maneuver data. The tests therefore assert two
different things, and the second matters more:

  * each node type does what 5e says (save branches, hit/miss, damage, conditions)
  * **the nine AUTHORED maneuvers execute**, not just hand-written fixtures. A test
    that only exercises a synthetic tree would pass while the shipped data stayed
    unplayable — the exact failure mode above.

Two real bugs surfaced while building this, both recorded here as regressions:
  * `DnDEngineWrapper.execute_attack()` had zero callers and crashes on any hit —
    it builds `Dice(num_dice=…, die_value=…)` when the fields are `count`/`value`.
    Maneuver attacks go through the engine's real `Attack` action instead.
  * a maneuver with an unresolvable placeholder used to be able to deal 0 damage
    silently; that now raises.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "external" / "dnd_engine"))

pytestmark = [pytest.mark.combat]

from components.character_manager import CharacterManager
from components.combat.lashing_dice import (STARTING_DICE, STARTING_DIE_SIZE,
                                            LashingDicePool)
from components.combat.maneuver_executor import (KNOWN_NODES, AutomationError,
                                                 ManeuverExecutor)
from components.cosmere_rules import get_cosmere_rules
from components.dnd_engine_wrapper import DnDEngineWrapper

ALL_NINE = ("Full Lashing", "Reverse Lashing", "Distracting Attack",
            "Goading Attack", "Evasive Movement", "Riposte", "Alerted Lash",
            "Athletic Lashings", "Acrobatic Lashings")


class _Engine:
    def __init__(self):
        self.game_state = type("S", (), {"characters": {}})()


def _sheet(char_id, order=None, feeble=False):
    """A Radiant, or a deliberately feeble target that fails most saves."""
    score = 6 if feeble else 16
    sheet = {
        "character_id": char_id, "name": char_id, "level": 5,
        "ability_scores": {"strength": score, "dexterity": score,
                           "constitution": 14, "intelligence": 10,
                           "wisdom": score, "charisma": 12},
        # Large pool so damage tests never tip into death saves.
        "hit_points": {"current": 200, "maximum": 200, "temporary": 0},
        "armor_class": 10 if feeble else 16,
        "character_class": "Fighter", "race": "Human", "background": "Soldier",
        "equipment": ["Spear"], "proficiency_bonus": 3,
    }
    if order:
        sheet.update({"radiant_order": order, "surgebinding_level": 3,
                      "stormlight_capacity": 10, "stormlight_current": 10})
    return sheet


@pytest.fixture
def field():
    """A Windrunner, a feeble target, and a non-Radiant."""
    from components.combat.tactical_grid import TacticalGrid

    TacticalGrid._clear_tiles()
    manager = CharacterManager()
    manager.add_character(_sheet("Kal", order="Windrunner"))
    manager.add_character(_sheet("Target", feeble=True))
    manager.add_character(_sheet("Farmer"))

    wrapper = DnDEngineWrapper(game_engine=_Engine(), character_manager=manager)
    wrapper.set_entity_position("Kal", (0, 0))
    wrapper.set_entity_position("Target", (1, 0))
    wrapper.set_entity_position("Farmer", (2, 0))
    wrapper.refresh_senses()

    rules = get_cosmere_rules()
    pool = LashingDicePool(rules)
    pool.register("Kal", "Windrunner", 5)
    state = {"combatant_states": {"Kal": {}, "Target": {}, "Farmer": {}}}
    executor = ManeuverExecutor(wrapper, dice_pool=pool, cosmere_rules=rules,
                               combat_state=state)
    yield executor, wrapper, pool, state
    TacticalGrid._clear_tiles()


def _maneuver(name):
    for entry in get_cosmere_rules().maneuvers(order="Windrunner") or []:
        if entry["name"] == name:
            return entry
    raise AssertionError(f"{name} is not in surgebinding.json")


def _run(executor, pool, name, targets=("Target",), tries=1):
    """Execute a maneuver, restoring dice first so the resource never confounds."""
    results = []
    for _ in range(tries):
        pool.rest("Kal")
        results.append(executor.execute(_maneuver(name), "Kal",
                                        targets=list(targets)))
    return results[0] if tries == 1 else results


# ---------------------------------------------------------------------------
# The authored data is now reachable
# ---------------------------------------------------------------------------

class TestTheAuthoredManeuversExecute:
    """
    The check that would have caught the gap: run the SHIPPED trees, not fixtures.
    """

    def test_all_nine_maneuvers_are_authored(self):
        names = {m["name"] for m in get_cosmere_rules().maneuvers(order="Windrunner")}
        assert set(ALL_NINE) <= names

    @pytest.mark.parametrize("name", ALL_NINE)
    def test_each_authored_maneuver_executes(self, field, name):
        executor, _, pool, _ = field
        result = _run(executor, pool, name)
        assert result.success is True, f"{name}: {result.error}"

    @pytest.mark.parametrize("name", ALL_NINE)
    def test_each_maneuver_does_something_observable(self, field, name):
        """
        Succeeding is not enough — a no-op that reports success is the bug class this
        project keeps hitting. Every maneuver must produce at least one event.

        Run several times because two of them branch on a saving throw, and a target
        that saves legitimately produces only the save event.
        """
        executor, _, pool, _ = field
        results = _run(executor, pool, name, tries=6)
        assert all(r.events for r in results), f"{name} produced no events"

    @pytest.mark.parametrize("name", ALL_NINE)
    def test_every_node_in_the_authored_trees_is_supported(self, name):
        """
        An unknown node type raises rather than being skipped, so this guards against
        someone authoring a node the interpreter cannot run.
        """
        def walk(node):
            if isinstance(node, dict):
                if "type" in node:
                    assert node["type"] in KNOWN_NODES, (
                        f"{name} uses unsupported node {node['type']!r}")
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(_maneuver(name)["automation"])

    def test_a_windrunner_is_offered_all_nine(self, field):
        executor, _, _, _ = field
        offered = {m["name"] for m in executor.available("Kal", "Windrunner", 5)}
        assert set(ALL_NINE) <= offered


# ---------------------------------------------------------------------------
# Node semantics
# ---------------------------------------------------------------------------

class TestSaveNodeBranches:
    """Full Lashing: STR save or be Restrained and take damage."""

    def test_a_failed_save_applies_both_effects(self, field):
        """
        The target has STR 6 (-2) so it fails most of the time. On a failure the
        RAW effect is BOTH the condition and the damage.
        """
        executor, _, pool, _ = field
        results = _run(executor, pool, "Full Lashing", tries=12)

        failed = [r for r in results
                  if any(e["type"] == "save" and not e["passed"] for e in r.events)]
        assert failed, "STR 6 never failed a save in 12 tries — check the DC"
        worst = failed[0]
        assert worst.damage_dealt > 0
        assert any("Restrained" in c for c in worst.conditions_applied)

    def test_a_successful_save_stops_the_tree(self, field):
        """On a success neither branch effect happens — `success: []` in the data."""
        executor, _, pool, _ = field
        results = _run(executor, pool, "Full Lashing", tries=16)

        passed = [r for r in results
                  if any(e["type"] == "save" and e["passed"] for e in r.events)]
        if not passed:
            pytest.skip("no successful save in 16 tries")
        assert passed[0].damage_dealt == 0
        assert not passed[0].conditions_applied

    def test_the_dc_uses_the_handbook_formula(self, field):
        """
        Invested save DC = 8 + proficiency + Investiture ability modifier, and for a
        Windrunner the ability is "highest of Strength or Dexterity" — read from the
        data, not hardcoded. STR 16 (+3), proficiency 3 -> DC 14.
        """
        executor, _, pool, _ = field
        result = _run(executor, pool, "Full Lashing")
        save = next(e for e in result.events if e["type"] == "save")
        assert save["dc"] == 8 + 3 + 3


class TestAttackNode:
    """Riposte: an attack roll, damage only on a hit."""

    def test_damage_happens_only_on_a_hit(self, field):
        executor, _, pool, _ = field
        for result in _run(executor, pool, "Riposte", tries=10):
            attack = next(e for e in result.events if e["type"] == "attack")
            if attack["hit"]:
                assert result.damage_dealt > 0, "hit dealt no damage"
            else:
                assert result.damage_dealt == 0, "miss still dealt damage"

    def test_it_does_not_use_the_broken_wrapper_helper(self, field):
        """
        REGRESSION. `execute_attack()` had zero callers and crashes on any hit
        (`Dice(num_dice=…)` vs the engine's `count`/`value`). Routing maneuver
        attacks through it made Riposte raise a pydantic ValidationError.
        """
        executor, wrapper, pool, _ = field

        def explode(*args, **kwargs):
            raise AssertionError("maneuver attacks must not call execute_attack()")

        wrapper.execute_attack = explode
        assert _run(executor, pool, "Riposte").success is True


class TestDamageAndRollNodes:
    def test_damage_reduces_the_targets_hit_points(self, field):
        """Asserted on HP, not on the reported number."""
        executor, wrapper, pool, _ = field
        entity = wrapper.entities["Target"]
        con = entity.ability_scores.constitution.modifier
        before = entity.health.get_total_hit_points(con)

        for _ in range(8):
            pool.rest("Kal")
            executor.execute(_maneuver("Distracting Attack"), "Kal",
                             targets=["Target"])
        after = entity.health.get_total_hit_points(con)
        assert after < before, f"HP unchanged: {before} -> {after}"

    def test_a_roll_node_reports_a_named_bonus(self, field):
        """
        Alerted Lash rolls a lashing die as an initiative bonus. Reported rather
        than applied — the thing it modifies is rolled elsewhere.
        """
        executor, _, pool, _ = field
        result = _run(executor, pool, "Alerted Lash")
        assert "initiative_bonus" in result.rolls
        assert 1 <= result.rolls["initiative_bonus"] <= STARTING_DIE_SIZE + 2

    def test_the_lashing_die_scales_the_roll(self, field):
        """
        `{lashing_die}` must resolve to the ACTOR's die. At level 17 it is a d10, so
        a d4-only interpolation would cap the observed maximum at 4.
        """
        executor, _, pool, _ = field
        pool.register("Kal", "Windrunner", 17)
        assert pool.die_size("Kal") == 10

        best = max(_run(executor, pool, "Athletic Lashings",
                        tries=25)[i].rolls.get("check_bonus", 0)
                   for i in range(25))
        assert best > 4, f"never rolled above a d4: {best}"


class TestIeffectNode:
    def test_a_named_5e_condition_goes_through_the_engine(self, field):
        """
        "Restrained" is a real 5e condition, so it must be applied as one — that is
        what makes it compose with attacks, saves and the rest of the engine.
        """
        executor, wrapper, pool, _ = field
        for _ in range(12):
            pool.rest("Kal")
            result = executor.execute(_maneuver("Full Lashing"), "Kal",
                                      targets=["Target"])
            if result.conditions_applied:
                assert any("restrained" in c.lower()
                           for c in wrapper.get_conditions("Target"))
                return
        pytest.skip("target saved every time")

    def test_an_inline_effect_is_recorded_on_combat_state(self, field):
        """
        "Evasive" is not a 5e condition — it is `{"ac_bonus": "{lashing_die}"}`. It
        is parked on the combatant's state so the session can see and clear it,
        rather than inventing an engine condition per maneuver.
        """
        executor, _, pool, state = field
        result = _run(executor, pool, "Evasive Movement", targets=("Kal",))

        assert result.effects_applied
        effect = result.effects_applied[0]
        assert effect["name"] == "Evasive"
        assert isinstance(effect["effects"]["ac_bonus"], int)
        assert state["combatant_states"]["Kal"]["maneuver_effects"]

    def test_duration_is_kept_verbatim(self, field):
        """
        Durations are prose for a human DM ("until you stop moving"). Parsing them
        into rounds would invent rules, so they are recorded as written.
        """
        executor, _, pool, _ = field
        result = _run(executor, pool, "Evasive Movement", targets=("Kal",))
        assert result.effects_applied[0]["duration"] == "until you stop moving"


# ---------------------------------------------------------------------------
# The resource
# ---------------------------------------------------------------------------

class TestLashingDiceEconomy:
    """
    `lashing_dice` gates every maneuver and had ZERO references anywhere in
    components/, agents/ or core/ — so the trees could not have run even with an
    interpreter, because there was nothing to spend.
    """

    def test_a_windrunner_starts_with_two_d4s(self):
        pool = LashingDicePool(get_cosmere_rules())
        dice = pool.register("Kal", "Windrunner", 1)
        assert (dice.total, dice.size) == (STARTING_DICE, STARTING_DIE_SIZE)

    def test_a_non_windrunner_gets_no_pool(self):
        """
        Only orders whose economy is `lashing_dice` get one. A Lightweaver uses
        investiture points and must not be able to spend Windrunner dice.
        """
        pool = LashingDicePool(get_cosmere_rules())
        assert pool.register("Shallan", "Lightweaver", 5) is None
        assert pool.get("Shallan") is None

    def test_using_a_maneuver_spends_a_die(self, field):
        executor, _, pool, _ = field
        before = pool.remaining("Kal")
        executor.execute(_maneuver("Alerted Lash"), "Kal", targets=["Target"])
        assert pool.remaining("Kal") == before - 1

    def test_an_exhausted_pool_refuses_the_maneuver(self, field):
        executor, _, pool, _ = field
        while pool.remaining("Kal"):
            pool.spend("Kal")

        result = executor.execute(_maneuver("Alerted Lash"), "Kal",
                                  targets=["Target"])
        assert result.success is False
        assert "lashing dice" in result.error

    def test_an_exhausted_pool_offers_nothing(self, field):
        """Never offer what cannot be paid for — the same trap as a missing param."""
        executor, _, pool, _ = field
        while pool.remaining("Kal"):
            pool.spend("Kal")
        assert executor.available("Kal", "Windrunner", 5) == []

    def test_a_rest_restores_every_die(self, field):
        _, _, pool, _ = field
        pool.spend("Kal", pool.remaining("Kal"))
        pool.rest("Kal")
        assert pool.remaining("Kal") == pool.get("Kal").total

    def test_dice_and_die_size_grow_with_level(self):
        """DERIVED, not cited — the Windrunner table is unextracted prose."""
        assert LashingDicePool.dice_for_level(1) == STARTING_DICE
        assert LashingDicePool.dice_for_level(20) > STARTING_DICE
        assert LashingDicePool.die_size_for_level(1) == 4
        assert LashingDicePool.die_size_for_level(20) == 10
        sizes = [LashingDicePool.die_size_for_level(n) for n in range(1, 21)]
        assert sizes == sorted(sizes), "die size must never shrink with level"


# ---------------------------------------------------------------------------
# Gating and failure modes
# ---------------------------------------------------------------------------

class TestGatingAndMalformedTrees:
    def test_a_non_radiant_cannot_use_a_maneuver(self, field):
        executor, _, _, _ = field
        result = executor.execute(_maneuver("Full Lashing"), "Farmer",
                                  targets=["Target"])
        assert result.success is False
        assert "Radiant" in result.error

    def test_the_wrong_order_is_refused(self, field):
        """All nine authored maneuvers are Windrunner-only."""
        executor, wrapper, _, _ = field
        wrapper.set_roshar_attr("Farmer", "radiant_order", "Stoneward")

        result = executor.execute(_maneuver("Full Lashing"), "Farmer",
                                  targets=["Target"])
        assert result.success is False
        assert "Stoneward" in result.error

    def test_a_non_radiant_is_offered_nothing(self, field):
        executor, _, _, _ = field
        assert executor.available("Farmer") == []

    def test_an_unknown_node_type_raises(self, field):
        executor, _, _, _ = field
        broken = {"name": "Broken", "orders": ["Windrunner"],
                  "automation": [{"type": "teleport_to_shadesmar"}]}
        result = executor.execute(broken, "Kal", targets=["Target"])
        assert result.success is False
        assert "unknown node type" in result.error

    def test_an_unknown_placeholder_raises_instead_of_dealing_zero(self, field):
        """
        THE IMPORTANT FAILURE MODE. An unresolved `{...}` would make the dice parser
        return 0, so the maneuver would report success having done nothing. Only
        `{lashing_die}` exists in the reviewed data, so anything else is a data bug.
        """
        executor, _, _, _ = field
        broken = {"name": "Broken", "orders": ["Windrunner"],
                  "cost": {"lashing_dice": 1},
                  "automation": [{"type": "damage", "damage": "{stormlight_die}"}]}
        result = executor.execute(broken, "Kal", targets=["Target"])
        assert result.success is False
        assert "placeholder" in result.error

    def test_a_maneuver_with_no_tree_is_refused(self, field):
        executor, _, _, _ = field
        result = executor.execute({"name": "Empty"}, "Kal", targets=["Target"])
        assert result.success is False

    def test_no_target_does_not_crash(self, field):
        """
        A target node with nobody chosen reports that plainly. Choosing a target is
        the player's job; crashing mid-tree is not an acceptable answer.
        """
        executor, _, pool, _ = field
        result = _run(executor, pool, "Full Lashing", targets=())
        assert result.success is True
        assert result.damage_dealt == 0

    def test_the_die_is_spent_even_on_a_malformed_tree(self, field):
        """
        5e expends the die on USE. A refund on a data bug would let a player retry
        for free and mask the bug.
        """
        executor, _, pool, _ = field
        before = pool.remaining("Kal")
        executor.execute({"name": "Broken", "orders": ["Windrunner"],
                          "cost": {"lashing_dice": 1},
                          "automation": [{"type": "nonsense"}]},
                         "Kal", targets=["Target"])
        assert pool.remaining("Kal") == before - 1

    def test_gating_happens_before_any_dice_are_spent(self, field):
        """A refused maneuver must not cost the resource."""
        executor, _, pool, _ = field
        before = pool.remaining("Kal")
        executor.execute(_maneuver("Full Lashing"), "Farmer", targets=["Target"])
        assert pool.remaining("Kal") == before


class TestResultReporting:
    def test_describe_summarises_what_happened(self, field):
        executor, _, pool, _ = field
        result = _run(executor, pool, "Alerted Lash")
        text = result.describe()
        assert "Kal" in text and "Alerted Lash" in text

    def test_describe_explains_a_refusal(self, field):
        executor, _, _, _ = field
        result = executor.execute(_maneuver("Full Lashing"), "Farmer",
                                  targets=["Target"])
        assert "cannot" in result.describe()
