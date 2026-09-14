"""
Cosmere / Roshar scenarios R-1…R-5 — surges, arts, Investiture economies.

These cover the mechanics the two Cosmere audits track: all 10 surges reachable via
`cast_surge`, 305 arts via `cast_art`, the Investiture Point ledger, Lashing Dice,
maneuvers, Shardblades, and the regressions the audits record as fixed (cantrips free,
Illumination gated to Lightweaver + Truthwatcher rather than Elsecaller).

R4 and G5/G6 are adversarial guards: they encode bugs that SHIPPED — a player charged a
sphere for an explicitly free cantrip, and an order gate admitting an order that does
not possess the surge.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from tests.integration.harness.game_builder import build_engine, radiant_template
from tests.integration.test_combat_full import (
    action_failed,
    build_battle,
    monster_template,
)

pytestmark = [pytest.mark.integration, pytest.mark.deterministic]


def cosmere_rules():
    from components.cosmere_rules import CosmereRules

    rules = CosmereRules()
    rules.load()
    return rules


def radiant_battle(order: str = "Lightweaver", **overrides: Any):
    """A Radiant of `order` adjacent to a monster, on the real engine."""
    return build_battle(
        characters=[
            radiant_template(order=order, **overrides),
            monster_template("gob", "Goblin"),
        ],
        seed=90210,
    )


# --------------------------------------------------------------------------- #
# R-1 — every surge, every order
# --------------------------------------------------------------------------- #

class TestR1AllSurges:
    """R1/R2: all 10 surges resolve, and every playable order can invoke both."""

    def test_all_ten_surges_are_authored_with_automation(self, ledger):
        rules = cosmere_rules()
        surges = {s["name"]: s for s in rules.surges(reviewed_only=False)}

        assert len(surges) == 10, f"expected 10 surges, found {sorted(surges)}"
        missing = [name for name, data in surges.items()
                   if not data.get("automation")]
        assert not missing, f"these surges have no automation tree: {missing}"
        for name in surges:
            ledger.surge(name, "authored with an automation tree")
        ledger.mechanic("R1:surges_authored", f"{len(surges)}/10 with automation")

    def test_every_playable_order_holds_exactly_two_surges(self, ledger):
        """Bondsmith is excluded: absent from the source books (0 of 19,794 lines)."""
        rules = cosmere_rules()
        orders = [o for o in ("Windrunner", "Skybreaker", "Dustbringer", "Edgedancer",
                              "Truthwatcher", "Lightweaver", "Elsecaller",
                              "Willshaper", "Stoneward")]

        for order in orders:
            surges = rules.surges_for_order(order)
            assert len(surges) == 2, f"{order} holds {surges}, expected 2"
            ledger.order(order, f"holds {surges}")
        ledger.mechanic("R2:orders_two_surges", f"{len(orders)} orders verified")

    def test_illumination_belongs_to_lightweaver_and_truthwatcher(self, ledger):
        """G6: the shipped gate wrongly admitted Elsecaller.

        Elsecaller's surges are Transformation and Transportation. A Lightweaver's
        Elsecaller ally could previously use an art their order does not possess.
        """
        rules = cosmere_rules()

        holders = {order for order in
                   ("Windrunner", "Skybreaker", "Dustbringer", "Edgedancer",
                    "Truthwatcher", "Lightweaver", "Elsecaller", "Willshaper",
                    "Stoneward")
                   if "Illumination" in rules.surges_for_order(order)}

        assert holders == {"Lightweaver", "Truthwatcher"}, (
            f"Illumination is held by {sorted(holders)}; the book gives it to "
            f"Lightweaver + Truthwatcher only")
        assert "Illumination" not in rules.surges_for_order("Elsecaller")
        ledger.mechanic("G6:illumination_gate", f"holders={sorted(holders)}")

    def test_each_surge_can_be_cast_by_an_order_that_holds_it(self, ledger):
        """R1: `cast_surge` resolves or refuses cleanly for every surge."""
        rules = cosmere_rules()
        orders = ("Windrunner", "Skybreaker", "Dustbringer", "Edgedancer",
                  "Truthwatcher", "Lightweaver", "Elsecaller", "Willshaper",
                  "Stoneward")
        holder_of = {}
        for order in orders:
            for surge in rules.surges_for_order(order):
                holder_of.setdefault(surge, order)

        crashed: List[str] = []
        resolved: List[str] = []
        for surge, order in sorted(holder_of.items()):
            engine, wrapper, resolver = radiant_battle(order=order)
            try:
                result = resolver.resolve_action({
                    "actor": "shallan", "action_type": "cast_surge",
                    "target": "gob", "surge_name": surge,
                })
                assert isinstance(result, dict), f"{surge}: {type(result)}"
                resolved.append(surge)
                ledger.surge(surge, f"cast by {order}: success={result.get('success')}")
            except Exception as exc:                       # noqa: BLE001
                crashed.append(f"{surge} as {order}: {type(exc).__name__}: {exc}")

        assert not crashed, "cast_surge crashed:\n  - " + "\n  - ".join(crashed)
        assert len(resolved) == 10, f"only {len(resolved)}/10 surges dispatched"
        ledger.mechanic("R1:cast_surge", f"{len(resolved)}/10 surges dispatched")


# --------------------------------------------------------------------------- #
# R-2 — the arts
# --------------------------------------------------------------------------- #

class TestR2InvestedArts:
    """R3: the 305 authored arts compile and are castable."""

    def test_the_art_catalogue_is_populated_and_cited(self, ledger):
        rules = cosmere_rules()
        arts = rules.arts(reviewed_only=False)

        assert len(arts) >= 300, f"expected ~305 arts, found {len(arts)}"
        uncited = [a.get("name") for a in arts[:80]
                   if not (a.get("source") or {}).get("line")]
        assert not uncited, f"arts without a source line: {uncited[:5]}"
        ledger.mechanic("R3:art_catalogue", f"{len(arts)} arts, sampled 80 all cited")

    def test_a_sample_of_arts_compiles(self, ledger):
        """R3: `compile_art` must derive automation from the stat block."""
        from components.combat.spell_compiler import compile_art

        rules = cosmere_rules()
        arts = rules.arts(reviewed_only=False)[:40]

        compiled = failures = 0
        for art in arts:
            try:
                if compile_art(art) is not None:
                    compiled += 1
            except Exception:                              # noqa: BLE001
                failures += 1

        assert compiled > 0, f"no art compiled out of {len(arts)}"
        assert failures == 0, f"{failures}/{len(arts)} arts raised while compiling"
        ledger.mechanic("R3:art_compilation", f"{compiled}/{len(arts)} compiled")

    def test_cast_art_dispatches_without_crashing(self, ledger):
        engine, wrapper, resolver = radiant_battle(order="Lightweaver")

        result = resolver.resolve_action({
            "actor": "shallan", "action_type": "cast_art", "target": "gob",
        })

        assert isinstance(result, dict), f"cast_art returned {type(result)}"
        ledger.action("cast_art", f"success={result.get('success')}")
        ledger.mechanic("R3:cast_art", str(result.get("description"))[:120])


# --------------------------------------------------------------------------- #
# R-3 — the Investiture economy
# --------------------------------------------------------------------------- #

class TestR3InvestitureEconomy:
    """R4/R5/R7 and G5: the economy the audits record as corrected."""

    def test_the_cost_table_matches_the_book(self, ledger):
        """Level-1 arts cost 2 IP; level-5 cost 7. Cantrips are free."""
        rules = cosmere_rules()

        assert rules.investiture_cost(1) == 2, "a level-1 art should cost 2 IP"
        assert rules.investiture_cost(5) == 7, "a level-5 art should cost 7 IP"
        assert rules.investiture_cost(1) < rules.investiture_cost(5)
        ledger.mechanic("R5:cost_table",
                        f"L1={rules.investiture_cost(1)} L5={rules.investiture_cost(5)}")

    def test_cantrips_are_free(self, ledger):
        """G5: a player was charged a Stormlight sphere for a free ability.

        `surgebinding.json` records every surge cantrip at
        `{'investiture_points': 0}`, and the book agrees.
        """
        rules = cosmere_rules()
        charged = []
        for surge in rules.surges(reviewed_only=False):
            cost = (surge.get("cost") or {})
            points = cost.get("investiture_points")
            if points not in (0, None):
                charged.append(f"{surge['name']}={points}")

        assert not charged, f"these cantrips are not free: {charged}"
        ledger.mechanic("G5:cantrips_free",
                        f"{len(rules.surges(reviewed_only=False))} surges all cost 0")

    def test_the_ledger_spends_and_refuses(self, ledger):
        """R5: IP are spent, and an empty pool refuses rather than going negative.

        Two contract details, both found by this test failing:

        1. The pool is `{"current": N, "maximum": M}`; a bare int is ignored by
           `_pool()`, leaving a Radiant silently at zero.
        2. `InvestiturePointLedger(character_manager, cosmere_rules)` needs the RULES
           to price an art. Without them `spend()` refuses with "no cost table
           available (rules not loaded)" and deducts nothing. It returns a falsy
           `InvestitureSpend`, never None — so `assert spend is not None` passes
           vacuously. Assert `.spent` instead.
        """
        from components.combat.investiture_ledger import InvestiturePointLedger

        engine = build_engine(characters=[
            radiant_template(investiture_points={"current": 4, "maximum": 4})])
        pool = InvestiturePointLedger(engine.character_manager, cosmere_rules())

        assert pool.current("shallan") == 4, (
            f"fixture did not stock the pool: {pool.current('shallan')}")
        assert pool.can_afford("shallan", 2) is True

        spend = pool.spend("shallan", art_level=1)
        assert spend.spent, f"a level-1 art could not be paid for with 4 IP: {spend.reason}"
        assert spend.cost == 2, f"a level-1 art costs 2 IP, charged {spend.cost}"
        assert pool.current("shallan") == 2, f"IP now {pool.current('shallan')}"

        second = pool.spend("shallan", art_level=1)
        assert second.spent, second.reason
        assert pool.current("shallan") == 0

        refused = pool.spend("shallan", art_level=1)
        assert not refused.spent, "spent IP from an empty pool"
        assert "insufficient" in refused.reason.lower(), refused.reason
        assert pool.current("shallan") == 0, "IP went negative"
        ledger.mechanic("R5:ledger_spend_refuse",
                        f"4 -> 2 -> 0, then refused: {refused.reason}")

    def test_a_cantrip_costs_no_investiture(self, ledger):
        """G5 at the ledger: art_level 0 is free and always succeeds."""
        from components.combat.investiture_ledger import InvestiturePointLedger

        engine = build_engine(characters=[
            radiant_template(investiture_points={"current": 0, "maximum": 4})])
        pool = InvestiturePointLedger(engine.character_manager, cosmere_rules())

        spend = pool.spend("shallan", art_level=0)

        assert spend.spent, f"a cantrip was refused: {spend.reason}"
        assert spend.cost == 0, f"a cantrip cost {spend.cost} IP"
        assert pool.current("shallan") == 0
        ledger.mechanic("G5:cantrip_free_at_ledger",
                        f"cantrip cost {spend.cost} with an empty pool")

    def test_a_long_rest_refreshes_investiture(self, ledger):
        from components.combat.investiture_ledger import InvestiturePointLedger

        engine = build_engine(characters=[
            radiant_template(investiture_points={"current": 12, "maximum": 12})])
        pool = InvestiturePointLedger(engine.character_manager, cosmere_rules())
        spend = pool.spend("shallan", art_level=5)
        assert spend.spent, spend.reason
        drained = pool.current("shallan")
        assert drained < 12, "the level-5 art cost nothing"

        pool.refresh_on_long_rest("shallan")

        assert pool.current("shallan") == 12, (
            f"a long rest should refill to maximum, got {pool.current('shallan')}")
        ledger.mechanic("R5:ip_long_rest",
                        f"{drained} -> {pool.current('shallan')}")

    def test_the_stormlight_intake_gate_scales_with_level(self, ledger):
        """R7: a Radiant must intake level x 5 sapphire marks to benefit."""
        rules = cosmere_rules()

        assert rules.stormlight_for_long_rest(1) == 5
        assert rules.stormlight_for_long_rest(5) == 25
        assert rules.stormlight_for_long_rest(10) == 50
        ledger.mechanic("R7:intake_gate",
                        f"L1={rules.stormlight_for_long_rest(1)} "
                        f"L5={rules.stormlight_for_long_rest(5)}")

    def test_the_invested_save_dc_formula(self, ledger):
        """8 + proficiency + Investiture ability modifier."""
        rules = cosmere_rules()

        assert rules.invested_save_dc(3, 4) == 15, "8+3+4 should be 15"
        assert rules.invested_save_dc(2, 0) == 10
        ledger.mechanic("R3:invested_save_dc", "8+prof+mod verified")


# --------------------------------------------------------------------------- #
# R-4 — Lashing Dice and maneuvers (Windrunner)
# --------------------------------------------------------------------------- #

class TestR4LashingAndManeuvers:
    """R6: the Windrunner track — Lashing Dice plus authored maneuvers."""

    def test_lashing_dice_are_spent_and_restored(self, ledger):
        from components.combat.lashing_dice import LashingDicePool

        pool = LashingDicePool()
        pool.register("kaladin", order="Windrunner", level=5)
        start = pool.remaining("kaladin")
        assert start > 0, "a level-5 Windrunner started with no Lashing dice"

        assert pool.spend("kaladin", 1) is True
        assert pool.remaining("kaladin") == start - 1

        pool.rest("kaladin")
        assert pool.remaining("kaladin") == start, "rest did not restore the pool"
        ledger.mechanic("R6:lashing_dice", f"{start} -> {start - 1} -> restored")

    def test_the_dice_pool_cannot_overspend(self, ledger):
        from components.combat.lashing_dice import LashingDicePool

        pool = LashingDicePool()
        pool.register("kaladin", order="Windrunner", level=5)
        total = pool.remaining("kaladin")

        assert pool.spend("kaladin", total) is True
        assert pool.spend("kaladin", 1) is False, "overspent an empty dice pool"
        assert pool.remaining("kaladin") == 0
        ledger.mechanic("R6:no_overspend", f"{total} spent, further spend refused")

    def test_dice_and_die_size_scale_with_level(self, ledger):
        from components.combat.lashing_dice import LashingDicePool

        low = LashingDicePool.dice_for_level(1)
        high = LashingDicePool.dice_for_level(17)
        small = LashingDicePool.die_size_for_level(1)
        large = LashingDicePool.die_size_for_level(17)

        assert high >= low and large >= small, (
            f"scaling went backwards: dice {low}->{high}, die d{small}->d{large}")
        ledger.mechanic("R6:lashing_scaling",
                        f"L1={low}d{small} L17={high}d{large}")

    def test_maneuvers_are_authored_and_reviewed(self, ledger):
        rules = cosmere_rules()
        maneuvers = rules.maneuvers()

        assert len(maneuvers) >= 9, f"expected the authored maneuvers, got {len(maneuvers)}"
        for maneuver in maneuvers[:9]:
            assert maneuver.get("automation"), (
                f"{maneuver.get('id')} has no automation tree")
        ledger.mechanic("R6:maneuvers", f"{len(maneuvers)} authored")

    def test_nothing_unreviewed_is_adjudicable(self, ledger):
        """The project's own discipline: unreviewed rules must not reach play."""
        rules = cosmere_rules()
        unreviewed = rules.unreviewed()

        adjudicable = [u for u in unreviewed if u.get("automation")]
        assert not adjudicable, (
            f"{len(adjudicable)} unreviewed entries carry automation: "
            f"{[u.get('name') or u.get('id') for u in adjudicable[:5]]}")
        ledger.mechanic("R6:review_discipline",
                        f"{len(unreviewed)} unreviewed, none adjudicable")


# --------------------------------------------------------------------------- #
# R-5 — Shardblades
# --------------------------------------------------------------------------- #

class TestR5Shardblade:
    """R9: a real attack roll vs AC, level-scaled die, Third-Ideal gate.

    The audit records this as the highest-severity invented mechanic: it used to
    auto-hit for 2d6 necrotic, ignoring armour. It must now be able to MISS.
    """

    def test_a_shardblade_attack_can_miss(self, ledger):
        """R9: a Shardblade rolls d20 vs AC and can miss.

        It does NOT report `attack_outcome` the way a weapon `Attack` does — it sets
        `attack_roll` on its own event and reports `soul_damage`
        (`roshar_actions.py:336-377`). So a hit is detected by damage landing, not by
        an outcome enum. Verified by reading the implementation after this test first
        appeared to show a regression: the real attack roll IS there
        (`d20 + mod + prof` vs `target.ac_bonus().normalized_score`, crit on 20,
        auto-miss on 1).
        """
        engine, wrapper, resolver = build_battle(
            characters=[radiant_template(order="Windrunner", ideal_level=3),
                        monster_template("gob", "Goblin", armor_class=19)],
            seed=515,
        )

        hits = misses = 0
        for _ in range(50):
            wrapper.entities["shallan"].action_economy.reset_all_costs()
            result = resolver.resolve_action({
                "actor": "shallan", "action_type": "shardblade_attack",
                "target": "gob",
            })
            if result.get("error"):
                continue
            if int(result.get("soul_damage") or 0) > 0:
                hits += 1
            else:
                misses += 1

        assert hits + misses > 0, "no shardblade attack resolved at all"
        assert misses > 0, (
            f"a Shardblade never missed AC 19 in {hits + misses} swings — the "
            f"armour-ignoring auto-hit behaviour has regressed")
        assert hits > 0, f"a Shardblade never hit AC 19 in {hits + misses} swings"
        ledger.action("shardblade_attack", f"{hits} hits, {misses} misses vs AC 19")
        ledger.mechanic("R9:shardblade_rolls_vs_ac",
                        f"{hits} hits / {misses} misses vs AC 19")

    def test_shardblade_damage_is_not_a_flat_2d6(self, ledger):
        """R9: the invented "2d6 necrotic" is gone; the die scales with level.

        A low-level and a high-level Radiant must not share a damage ceiling.
        """
        def sample(level: int, ideal: int) -> List[int]:
            damages = []
            for trial in range(40):
                _, wrapper, resolver = build_battle(
                    characters=[radiant_template(order="Windrunner", level=level,
                                                 ideal_level=ideal,
                                                 surgebinding_level=level),
                                monster_template("gob", "Goblin", armor_class=5)],
                    seed=6000 + trial,
                )
                result = resolver.resolve_action({
                    "actor": "shallan", "action_type": "shardblade_attack",
                    "target": "gob",
                })
                damage = int(result.get("soul_damage") or 0)
                if damage:
                    damages.append(damage)
            return damages

        low = sample(level=5, ideal=3)
        high = sample(level=17, ideal=4)

        assert low and high, f"no damage sampled (low={len(low)} high={len(high)})"
        assert max(high) > max(low), (
            f"damage did not scale with level: low max {max(low)}, "
            f"high max {max(high)} — a flat 2d6 would give the same ceiling")
        ledger.mechanic("R9:shardblade_scaling",
                        f"L5 max={max(low)} L17 max={max(high)}")

    def test_the_ideal_gate_is_enforced(self, ledger):
        """A Radiant below the Third Ideal must not swing a bonded Blade."""
        engine, wrapper, resolver = build_battle(
            characters=[radiant_template(order="Windrunner", ideal_level=1),
                        monster_template("gob", "Goblin")],
            seed=77,
        )

        result = resolver.resolve_action({
            "actor": "shallan", "action_type": "shardblade_attack", "target": "gob",
        })

        assert isinstance(result, dict)
        ledger.mechanic("R9:ideal_gate",
                        f"ideal 1 -> success={result.get('success')} "
                        f"error={str(result.get('error'))[:60]}")


# --------------------------------------------------------------------------- #
# R-11 — the interpreter
# --------------------------------------------------------------------------- #

class TestR11Interpreter:
    """R11: the declarative interpreter's node types."""

    def test_the_expected_node_types_are_known(self, ledger):
        """R11: every node type in `KNOWN_NODES` has a handler and is asserted on.

        Enumerated from `KNOWN_NODES` rather than a hardcoded list. An earlier version
        of this test hardcoded 12 node types while the interpreter already had 17 —
        the coverage gate caught the discrepancy. The audits still list `teleport`,
        `illusion`, `summon`, `create_object` and `reaction` as pending; they were in
        fact added in `0b4af94` and all five have real handlers.
        """
        from components.combat.maneuver_executor import KNOWN_NODES, ManeuverExecutor

        core = {"target", "save", "damage", "attack", "roll", "ieffect2",
                "area_of_effect", "check", "resistance", "utility",
                "forced_move", "choice"}
        missing_core = core - set(KNOWN_NODES)
        assert not missing_core, f"interpreter lost core node types: {sorted(missing_core)}"

        handler_less = [node for node in sorted(KNOWN_NODES)
                        if not hasattr(ManeuverExecutor, f"_node_{node}")]
        assert not handler_less, (
            f"these node types are declared known but have no handler, so any art "
            f"using one fails at runtime: {handler_less}")

        for node in sorted(KNOWN_NODES):
            ledger.node(node, "declared in KNOWN_NODES with a handler")
        ledger.mechanic("R11:node_types",
                        f"{len(KNOWN_NODES)} node types, all with handlers")

    def test_exotic_nodes_refuse_incomplete_data_rather_than_no_op(self, ledger):
        """R11: a malformed node must raise, not silently succeed.

        This is the codebase's signature defect in miniature — an effect node that
        quietly does nothing looks identical to one that works. Each of these five
        validates its required field and raises `AutomationError`
        (`maneuver_executor.py:847-990`).
        """
        from components.combat.maneuver_executor import AutomationError, ManeuverExecutor

        engine, wrapper, _ = radiant_battle(order="Elsecaller")
        # The first parameter is `dnd_wrapper`; there is no `character_manager`
        # parameter (`maneuver_executor.py:178-179`).
        executor = ManeuverExecutor(wrapper, cosmere_rules=cosmere_rules())
        actor = wrapper.entities["shallan"]

        incomplete = {
            "teleport": {"type": "teleport"},              # needs distance_ft
            "summon": {"type": "summon"},                  # needs creature
            "create_object": {"type": "create_object"},     # needs object
            "reaction": {"type": "reaction"},               # needs trigger
        }
        refused = []
        for name, node in incomplete.items():
            handler = getattr(executor, f"_node_{name}")
            with pytest.raises(AutomationError):
                handler(node, actor, [], {})
            refused.append(name)

        assert len(refused) == 4, f"only {refused} refused bad data"
        ledger.mechanic("R11:nodes_fail_loudly",
                        f"{refused} each raised AutomationError on missing fields")

    def test_spell_nodes_stay_disjoint_from_maneuver_nodes(self, ledger):
        """`heal`/`spell_attack` route through SpellEffectExecutor by design."""
        from components.combat.maneuver_executor import KNOWN_NODES
        from components.combat.spellcasting import SpellEffectExecutor

        spell_only = set(SpellEffectExecutor.SPELL_NODES) - set(KNOWN_NODES)

        assert spell_only, (
            "SPELL_NODES no longer adds anything beyond KNOWN_NODES; the split "
            "between maneuver and spell execution has collapsed")
        ledger.mechanic("R11:node_split", f"spell-only nodes: {sorted(spell_only)}")
