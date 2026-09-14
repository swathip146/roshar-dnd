"""
Combat integration scenarios C-1…C-6 — the largest mechanic block.

Every test drives the REAL `CombatActionResolver` over the REAL vendored engine. The
LLM is the only thing faked, and most of this file does not need one at all: combat
resolution is code, not prose.

Assertions are on OBSERVABLE END STATE — HP fell, a slot was consumed, the action was
refused — never on "the method was called". Mock-based assertions are precisely what
let `entity.health.is_dead()` and `action_economy.reset()` (neither of which exists)
pass for months.

Coverage tokens are recorded at the point of observed effect, so a no-op cannot claim
coverage. See `harness/coverage.py`.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

import pytest

from tests.integration.harness.game_builder import (
    build_engine,
    build_wrapper,
    caster_template,
    character_template,
)

pytestmark = [pytest.mark.integration, pytest.mark.deterministic]


# --------------------------------------------------------------------------- #
# Helpers — real objects only
# --------------------------------------------------------------------------- #

def monster_template(char_id: str, name: str, **over: Any) -> Dict[str, Any]:
    """A hostile NPC as a real character record."""
    template = character_template(
        char_id=char_id, name=name, level=1, character_class="Monster",
        ability_scores={"strength": 14, "dexterity": 12, "constitution": 12,
                        "intelligence": 6, "wisdom": 8, "charisma": 6},
        hit_points={"current": 18, "maximum": 18, "temporary": 0},
        armor_class=12,
        equipment=["spear"],
    )
    template["is_npc"] = True
    template.update(over)
    return template


def build_battle(characters: Optional[List[Dict[str, Any]]] = None, seed: int = 20260913):
    """A real engine + wrapper + resolver, with entities placed adjacently.

    Returns `(engine, wrapper, resolver)`. Positions matter: before the Phase-1 fix
    every attack cancelled because entities had no position and could not see each
    other, so placement is part of the setup rather than an afterthought.
    """
    from components.combat.combat_action_resolver import CombatActionResolver

    random.seed(seed)
    engine = build_engine(
        characters=characters or [character_template(), monster_template("gob", "Goblin")],
        seed=seed,
    )
    wrapper = build_wrapper(engine)

    ids = list(wrapper.entities)
    for index, char_id in enumerate(ids):
        entity = wrapper.entities[char_id]
        entity.position = (index, 0)
    if hasattr(wrapper, "refresh_senses"):
        wrapper.refresh_senses()

    combat_state: Dict[str, Any] = {
        "active": True,
        "round": 1,
        "current_turn_index": 0,
        "combatant_states": {
            char_id: {"position": wrapper.entities[char_id].position,
                      "movement_remaining": 30}
            for char_id in ids
        },
        "initiative_order": ids,
    }
    resolver = CombatActionResolver(
        dnd_engine_wrapper=wrapper,
        character_manager=engine.character_manager,
        combat_state=combat_state,
    )
    return engine, wrapper, resolver


def hp_of(engine, char_id: str) -> int:
    """HP as recorded on CharacterData — the RECORD, not the display."""
    return engine.character_manager.characters[char_id].hit_points["current"]


def entity_hp(wrapper, char_id: str) -> int:
    """An entity's live HP inside the vendored engine — the AUTHORITY mid-combat.

    IMPORTANT LAYERING (learned the hard way while writing this suite):
    `CombatActionResolver.resolve_action` does NOT write damage back onto
    CharacterData. It only syncs the *display* (`_sync_hp_to_combat_state`).
    Copying HP back onto the record is `CombatSessionManager._sync_hp_from_engine()`
    (`combat_session_manager.py:1610`), whose own docstring puts it plainly:
    "`combat_state` is the DISPLAY; `CharacterData` is the RECORD."

    So a test that calls the resolver directly and then reads CharacterData will see
    an untouched character no matter how much damage landed. Read the entity instead;
    the session-level tests below assert the record separately.
    """
    from components.dnd_engine_wrapper import DnDEngineWrapper

    return DnDEngineWrapper.get_entity_current_hp(wrapper.entities[char_id])


def hit_landed(result: Dict[str, Any]) -> bool:
    """Did this attack connect?

    Two traps, both learned here rather than assumed:

    1. `success: False` on an attack means **the attack MISSED**, not that the action
       failed: the result still carries a real `AttackEvent`, `attack_outcome=MISS`,
       and no `error` key. Conflating them makes every miss look like a broken action.

    2. Outcome names must be matched EXACTLY after splitting, never by substring.
       `"CRIT" in "CRIT_MISS"` is True, so a substring test counts a natural 1 as a
       critical hit — which showed up as a "hit" that dealt 0 damage. The mirror image
       of this trap (matching only `"HIT"` and thereby dropping `CRIT`, making an
       auto-critting target measure 0% hit rate) is documented at
       `tests/combat/test_tactical_rules.py:97-100`.
    """
    outcome = str(result.get("attack_outcome") or "").rsplit(".", 1)[-1].upper()
    return outcome in ("HIT", "CRIT")


def action_failed(result: Dict[str, Any]) -> bool:
    """Did the action fail to execute at all (as opposed to missing)?"""
    return bool(result.get("error")) or result.get("event") is None


def attack(resolver, actor: str, target: str) -> Dict[str, Any]:
    return resolver.resolve_action(
        {"actor": actor, "action_type": "attack", "target": target})


def reset_economy(wrapper, char_id: str) -> None:
    """Refresh an entity's action economy between scripted attacks.

    The real method is `reset_all_costs`, NOT `reset` — a Mock happily accepted
    `reset()` for months while doing nothing.
    """
    economy = wrapper.entities[char_id].action_economy
    economy.reset_all_costs()


# --------------------------------------------------------------------------- #
# C-1 — attacks, damage, AC, action economy
# --------------------------------------------------------------------------- #

class TestC1Skirmish:
    """Attack resolution over the real engine (C1, C2, C6)."""

    def test_attacks_resolve_and_eventually_deal_damage(self, ledger, check_invariants):
        engine, wrapper, resolver = build_battle()
        start = entity_hp(wrapper, "gob")

        hits = misses = 0
        for _ in range(40):
            reset_economy(wrapper, "aggi")
            result = attack(resolver, "aggi", "gob")
            assert not action_failed(result), f"the attack action failed: {result}"
            if hit_landed(result):
                hits += 1
            else:
                misses += 1

        assert hits > 0, "40 attacks never landed — attacks are being cancelled"
        assert entity_hp(wrapper, "gob") < start, (
            f"{hits} hits landed but entity HP never moved "
            f"({start} -> {entity_hp(wrapper, 'gob')})")
        ledger.action("attack", f"{hits} hits, {misses} misses")
        ledger.mechanic("C1:attack_rolls", f"hits={hits} misses={misses}")
        check_invariants(engine.character_manager, context="C-1 attacks")

    def test_both_hits_and_misses_occur(self, ledger):
        """AC must matter: an all-hit or all-miss result means AC is ignored."""
        engine, wrapper, resolver = build_battle(
            characters=[character_template(), monster_template("gob", "Goblin",
                                                               armor_class=17)],
        )
        outcomes = []
        for _ in range(60):
            reset_economy(wrapper, "aggi")
            outcomes.append(hit_landed(attack(resolver, "aggi", "gob")))

        assert any(outcomes), "never hit AC 17 in 60 attacks"
        assert not all(outcomes), "never missed AC 17 — AC is not being checked"
        ledger.mechanic("C1:ac_matters",
                        f"{sum(outcomes)}/{len(outcomes)} hit vs AC 17")

    def test_damage_is_bounded_by_the_weapon(self, ledger):
        """A longsword cannot deal 0 or 100. Guards damage-dice wiring.

        Each swing gets a FRESH target. Reusing one lets HP run deeply negative
        (observed: -282 after 60 swings), and past a point the engine stops reducing
        it further, so a landed hit reports 0 damage — a corpse-flogging artifact of
        the test, not a damage bug. Sampling one swing per battle avoids reading that
        as a real zero.
        """
        deltas = []
        for trial in range(40):
            _, wrapper, resolver = build_battle(seed=4100 + trial)
            before = entity_hp(wrapper, "gob")
            if hit_landed(attack(resolver, "aggi", "gob")):
                deltas.append(before - entity_hp(wrapper, "gob"))

        assert deltas, "no damage was ever dealt across 40 fresh battles"
        assert all(1 <= d <= 30 for d in deltas), f"implausible damage: {deltas}"
        ledger.mechanic("C2:damage_bounded",
                        f"{len(deltas)} hits in {min(deltas)}..{max(deltas)}")

    def test_action_is_consumed_and_second_attack_refused(self, ledger):
        """C6: the economy actually gates a second attack in one turn."""
        engine, wrapper, resolver = build_battle()

        first = attack(resolver, "aggi", "gob")
        assert not action_failed(first), f"the first attack failed outright: {first}"

        second = attack(resolver, "aggi", "gob")
        refused = action_failed(second) or "econom" in str(second).lower()
        assert refused, f"a second attack was allowed in one turn: {second}"

        reset_economy(wrapper, "aggi")
        third = attack(resolver, "aggi", "gob")
        assert not action_failed(third), f"reset did not restore the action: {third}"
        ledger.mechanic("C6:action_economy", "2nd attack refused; reset restored it")


# --------------------------------------------------------------------------- #
# C-4 — resistance, immunity, vulnerability
# --------------------------------------------------------------------------- #

class TestC4DamageModifiers:
    """C3: resistance halves, vulnerability doubles, immunity zeroes.

    Driven through `health.damage_reduction.self_static.add_resistance_modifier` —
    the same engine path monster stat blocks and the `_node_resistance` interpreter
    node use — so this covers the wiring the audit records as fixed in `eb15312`.

    `ResistanceModifier` takes `name=` and `value=` (NOT `status=`); copied from the
    working production call at `components/combat/maneuver_executor.py:713-719`
    rather than guessed.
    """

    @staticmethod
    def _apply(entity, amount: int, damage_type_name: str) -> int:
        """Deal damage and return how much actually landed.

        `Health.take_damage(damage, damage_type, source_entity_uuid)` returns the
        applied amount, which is more direct than diffing HP.
        """
        from dnd.core.events import DamageType

        return entity.health.take_damage(
            amount, getattr(DamageType, damage_type_name), entity.uuid)

    @staticmethod
    def _add_modifier(entity, damage_type_name: str, status_name: str) -> None:
        from dnd.core.events import DamageType
        from dnd.core.modifiers import ResistanceModifier, ResistanceStatus

        damage_type = getattr(DamageType, damage_type_name)
        entity.health.damage_reduction.self_static.add_resistance_modifier(
            ResistanceModifier(
                name=f"{status_name.title()} to {damage_type.value}",
                value=getattr(ResistanceStatus, status_name),
                damage_type=damage_type,
                source_entity_uuid=entity.uuid,
                target_entity_uuid=entity.uuid,
            )
        )

    def test_resistance_halves_damage(self, ledger):
        _, wrapper, _ = build_battle()
        entity = wrapper.entities["gob"]

        plain = self._apply(entity, 20, "FIRE")
        self._add_modifier(entity, "FIRE", "RESISTANCE")
        resisted = self._apply(entity, 20, "FIRE")

        assert resisted == plain // 2, (
            f"resistance should halve {plain}, gave {resisted}")
        ledger.mechanic("C3:resistance", f"{plain} -> {resisted}")

    def test_immunity_zeroes_damage(self, ledger):
        _, wrapper, _ = build_battle()
        entity = wrapper.entities["gob"]

        self._add_modifier(entity, "POISON", "IMMUNITY")

        assert self._apply(entity, 25, "POISON") == 0, "immunity let damage through"
        ledger.mechanic("C3:immunity", "25 poison -> 0")

    def test_vulnerability_doubles_damage(self, ledger):
        _, wrapper, _ = build_battle()
        entity = wrapper.entities["gob"]

        plain = self._apply(entity, 6, "COLD")
        self._add_modifier(entity, "COLD", "VULNERABILITY")
        doubled = self._apply(entity, 6, "COLD")

        assert doubled == plain * 2, f"expected {plain * 2}, got {doubled}"
        ledger.mechanic("C3:vulnerability", f"{plain} -> {doubled}")

    def test_an_unrelated_damage_type_is_unaffected(self, ledger):
        """Resistance must be type-scoped, not a blanket reduction."""
        _, wrapper, _ = build_battle()
        entity = wrapper.entities["gob"]

        plain = self._apply(entity, 10, "SLASHING")
        self._add_modifier(entity, "FIRE", "RESISTANCE")
        after = self._apply(entity, 10, "SLASHING")

        assert after == plain, (
            f"fire resistance changed slashing damage: {plain} -> {after}")
        ledger.mechanic("C3:resistance_scoped", f"slashing stayed {after}")


# --------------------------------------------------------------------------- #
# C-1 cont. — advantage (G3, the patched no-op)
# --------------------------------------------------------------------------- #

class TestC5Advantage:
    """G3/C5: advantage must move the hit rate by a real margin.

    Historically a total no-op — `Dice._roll_with_advantage` rolled ONE die and took
    `max()` of a 1-element list, giving a measured delta of +0.0pp. Patched in
    `components/engine_patches.py`. This test exists to keep it fixed.

    Both arms are seeded identically and the threshold (+10pp, against a measured
    +25.2pp) sits well outside observed noise: an earlier version of this measurement
    showed |delta| up to 9.8pp under the null hypothesis, so 600 trials and a 10pp bar
    are deliberate rather than arbitrary.

    Advantage is granted the way production does it — an `AdvantageModifier` on
    `weapon.attack_bonus.self_static` (`components/combat/tactical_rules.py:139-143`).
    That matters: `entity.attack_bonus()` returns a FRESH object each call, so a
    modifier added to it is discarded. The persistent seam is the weapon's.
    """

    TRIALS = 600

    @staticmethod
    def _hit_rate(wrapper, attacker: str, target: str, trials: int) -> float:
        """Fraction of real `Attack` events that HIT or CRIT.

        Counting only "HIT" by substring would exclude CRIT and make an auto-critting
        target measure as unhittable — a trap the existing tactical-rules suite
        documents at `tests/combat/test_tactical_rules.py:97-100`.
        """
        from dnd.actions import Attack
        from dnd.blocks.equipment import WeaponSlot

        entity = wrapper.entities[attacker]
        hits = 0
        for _ in range(trials):
            entity.action_economy.reset_all_costs()
            event = Attack(
                source_entity_uuid=entity.uuid,
                target_entity_uuid=wrapper.entities[target].uuid,
                weapon_slot=WeaponSlot.MAIN_HAND,
            ).apply(parent_event=None)
            outcome = str(getattr(event, "attack_outcome", ""))
            if outcome.rsplit(".", 1)[-1] in ("HIT", "CRIT"):
                hits += 1
        return hits / trials

    @staticmethod
    def _grant_advantage(wrapper, char_id: str) -> None:
        from dnd.core.modifiers import AdvantageModifier, AdvantageStatus

        entity = wrapper.entities[char_id]
        weapon = entity.equipment.weapon_main_hand
        assert weapon is not None, (
            "no main-hand weapon equipped, so there is no persistent attack_bonus "
            "seam to modify")
        weapon.attack_bonus.self_static.add_advantage_modifier(
            AdvantageModifier(
                name="test-advantage", value=AdvantageStatus.ADVANTAGE,
                source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid)
        )

    def test_advantage_raises_the_hit_rate(self, ledger):
        import random as _random

        _random.seed(11)
        _, wrapper, _ = build_battle(seed=11)
        base = self._hit_rate(wrapper, "aggi", "gob", self.TRIALS)

        _random.seed(11)
        _, wrapper2, _ = build_battle(seed=11)
        self._grant_advantage(wrapper2, "aggi")
        adv = self._hit_rate(wrapper2, "aggi", "gob", self.TRIALS)

        delta = adv - base
        assert delta > 0.10, (
            f"advantage moved the hit rate by only {delta:+.1%} "
            f"(base={base:.1%} adv={adv:.1%}, seed=11, {self.TRIALS} trials). "
            f"A near-zero delta means the advantage patch regressed to rolling one "
            f"die and taking max() of a 1-element list."
        )
        ledger.mechanic("C5:advantage",
                        f"base={base:.1%} adv={adv:.1%} delta={delta:+.1%}")


# --------------------------------------------------------------------------- #
# C-1 cont. — conditions
# --------------------------------------------------------------------------- #

class TestC10Conditions:
    """C10: all 15 SRD conditions apply through the real engine.

    The vendored engine natively has 13; Petrified and Exhaustion were added in
    `components/engine_conditions.py`. Applying all 15 guards both.
    """

    ALL_15 = ["Blinded", "Charmed", "Deafened", "Frightened", "Grappled",
              "Incapacitated", "Invisible", "Paralyzed", "Petrified", "Poisoned",
              "Prone", "Restrained", "Stunned", "Unconscious", "Exhaustion"]

    def test_every_srd_condition_applies(self, ledger):
        applied = []
        for name in self.ALL_15:
            _, wrapper, _ = build_battle()
            result = wrapper.apply_condition("gob", name)
            assert result is not False, f"{name} was refused by the engine"
            applied.append(name)

        assert len(applied) == 15, f"only {len(applied)}/15 applied"
        ledger.mechanic("C10:conditions", f"{len(applied)}/15 applied")

    def test_petrified_and_exhaustion_are_the_added_two(self, ledger):
        """These two are patched in, so they are the likeliest to regress."""
        for name in ("Petrified", "Exhaustion"):
            _, wrapper, _ = build_battle()
            assert wrapper.apply_condition("gob", name) is not False, name
        ledger.mechanic("C10:patched_conditions", "Petrified + Exhaustion applied")


# --------------------------------------------------------------------------- #
# C-5 — death, dying, stabilising
# --------------------------------------------------------------------------- #

class TestC11DeathAndDying:
    """C11: death saves, stabilising, and unconscious-at-0 as distinct from dead."""

    def test_three_failed_saves_kill(self, ledger):
        """The real signature is `roll_death_save(id, roll=...)`, not `forced_roll=`."""
        engine = build_engine()
        manager = engine.character_manager
        manager.characters["aggi"].hit_points["current"] = 0

        result = None
        for _ in range(10):
            result = manager.roll_death_save("aggi", roll=2)
            if result.get("dead") or result.get("stable"):
                break

        assert result is not None and result.get("dead") is True, (
            f"repeated failed death saves did not kill: {result}")
        ledger.mechanic("C11:death_saves", f"dead after failures: {result}")

    def test_natural_twenty_revives_at_one_hp(self, ledger):
        engine = build_engine()
        manager = engine.character_manager
        manager.characters["aggi"].hit_points["current"] = 0

        result = manager.roll_death_save("aggi", roll=20)

        assert result.get("revived") is True, f"a nat 20 did not revive: {result}"
        assert manager.characters["aggi"].hit_points["current"] == 1
        ledger.mechanic("C11:nat20_revive", "revived at 1 HP")

    def test_a_conscious_character_is_not_asked_to_save(self, ledger):
        """Guards the interaction the sync docstring warns about.

        `roll_death_save` returns `{"skipped": ...}` above 0 HP, so if combat damage
        never reached CharacterData a downed character could never roll at all.
        """
        engine = build_engine()
        result = engine.character_manager.roll_death_save("aggi", roll=2)

        assert result.get("skipped"), f"a healthy character rolled a death save: {result}"
        ledger.mechanic("C11:save_gated_on_hp", str(result))

    def test_a_player_at_zero_hp_is_dying_not_dead(self, ledger):
        engine = build_engine()
        character = engine.character_manager.characters["aggi"]
        character.hit_points["current"] = 0

        assert getattr(character, "is_dead", False) is False, (
            "a PC at 0 HP was marked dead; 5e makes them unconscious and dying")
        ledger.mechanic("C11:dying_not_dead", "0 HP PC is not is_dead")

    def test_stabilizing_stops_the_death_spiral(self, ledger):
        engine = build_engine()
        manager = engine.character_manager
        manager.characters["aggi"].hit_points["current"] = 0

        result = manager.stabilize("aggi")

        assert result is not False, f"stabilize failed: {result}"
        assert getattr(manager.characters["aggi"], "is_stable", None) is True
        ledger.mechanic("C11:stabilize", "is_stable=True")


# --------------------------------------------------------------------------- #
# C-3 — spellcasting
# --------------------------------------------------------------------------- #

class TestC9Spellcasting:
    """C9: slots, cantrips, upcasting, save DC — through the real service."""

    def _caster_battle(self):
        return build_battle(characters=[
            caster_template(), monster_template("gob", "Goblin")])

    @staticmethod
    def _slots_remaining(engine, char_id: str) -> Dict[int, int]:
        """{level: remaining}, read the way `SpellSlotLedger` reads it.

        Slots are `{level: {"current": N, "maximum": N}}`; a bare-int dict is silently
        ignored by the ledger, so this mirrors its normalisation rather than trusting
        the raw field.
        """
        from components.combat.spellcasting import SpellSlotLedger

        return SpellSlotLedger(engine.character_manager).available(char_id)

    def test_casting_a_leveled_spell_consumes_a_slot(self, ledger):
        engine, wrapper, resolver = self._caster_battle()
        before = self._slots_remaining(engine, "jasnah")
        assert before, "the caster started with no slots; fixture is wrong"

        result = resolver.resolve_action({
            "actor": "jasnah", "action_type": "cast_spell",
            "target": "gob", "spell_name": "magic missile",
        })

        assert not result.get("error"), f"casting failed outright: {result}"
        after = self._slots_remaining(engine, "jasnah")
        assert sum(after.values()) == sum(before.values()) - 1, (
            f"exactly one slot should be spent: {before} -> {after}")
        ledger.action("cast_spell", f"slots {before} -> {after}")
        ledger.mechanic("C9:slot_spent", f"{before} -> {after}")

    def test_a_cantrip_costs_no_slot(self, ledger):
        engine, wrapper, resolver = self._caster_battle()
        before = self._slots_remaining(engine, "jasnah")

        result = resolver.resolve_action({
            "actor": "jasnah", "action_type": "cast_spell",
            "target": "gob", "spell_name": "fire bolt",
        })

        assert not result.get("error"), f"cantrip failed outright: {result}"
        after = self._slots_remaining(engine, "jasnah")
        assert after == before, f"a cantrip consumed a slot: {before} -> {after}"
        ledger.mechanic("C9:cantrip_free", f"slots unchanged at {after}")

    def test_upcasting_spends_the_higher_slot(self, ledger):
        """C9: `at_level` must consume the requested level, not the lowest."""
        engine, wrapper, resolver = self._caster_battle()
        before = self._slots_remaining(engine, "jasnah")

        result = resolver.resolve_action({
            "actor": "jasnah", "action_type": "cast_spell",
            "target": "gob", "spell_name": "magic missile", "at_level": 3,
        })

        assert not result.get("error"), f"upcast failed outright: {result}"
        after = self._slots_remaining(engine, "jasnah")
        assert after.get(3, 0) == before.get(3, 0) - 1, (
            f"a level-3 upcast did not spend a level-3 slot: {before} -> {after}")
        ledger.mechanic("C9:upcasting", f"L3 {before.get(3)} -> {after.get(3)}")

    def test_save_dc_follows_the_5e_formula(self, ledger):
        """8 + proficiency + ability modifier, via `spellcasting_stats()`."""
        from components.combat.spellcasting import spellcasting_stats

        engine = build_engine(characters=[caster_template()])
        character = engine.character_manager.characters["jasnah"]

        stats = spellcasting_stats(character, "jasnah")
        modifier = (character.ability_scores["intelligence"] - 10) // 2
        expected = 8 + stats.proficiency_bonus + modifier

        assert stats.is_caster, f"a Wizard was not detected as a caster: {stats}"
        assert stats.save_dc == expected, (
            f"save DC {stats.save_dc} != 8+{stats.proficiency_bonus}+{modifier}")
        assert stats.attack_bonus == stats.proficiency_bonus + modifier
        ledger.mechanic("C9:save_dc",
                        f"DC {stats.save_dc}, atk +{stats.attack_bonus}")

    def test_a_non_caster_gets_no_save_dc(self, ledger):
        """Deliberate design: a Fighter's save_dc is None, not 8+prof+0.

        Returning a number would make "cast Fireball" look computable, and something
        downstream would eventually use it (`spellcasting.py:170-180`).
        """
        from components.combat.spellcasting import spellcasting_stats

        engine = build_engine()
        stats = spellcasting_stats(engine.character_manager.characters["aggi"], "aggi")

        assert stats.is_caster is False
        assert stats.save_dc is None, f"a Fighter was given save DC {stats.save_dc}"
        ledger.mechanic("C9:non_caster_has_no_dc", "Fighter save_dc is None")


# --------------------------------------------------------------------------- #
# C-2 — every offerable action is reachable (G1)
# --------------------------------------------------------------------------- #

class TestC2ActionRegistry:
    """G1: no registry entry may be unreachable for want of a default.

    This is the `cast_spell`/`spell_name` bug class, which shipped: the entry was
    registered, the comment above it described the fix, and one missing dict key kept
    all 319 spells out of every menu.
    """

    def test_every_registry_entry_is_offerable_or_explains_itself(self, ledger):
        from components.combat.action_registry import (
            ACTION_REGISTRY, is_offerable, required_caller_params,
        )

        #: `move` legitimately needs a caller-supplied destination.
        allowed_unofferable = {"move"}
        unofferable = {name for name in ACTION_REGISTRY if not is_offerable(name)}

        unexpected = unofferable - allowed_unofferable
        assert not unexpected, (
            "these actions are filtered out of every menu, so no player can choose "
            f"them: { {n: required_caller_params(n) for n in sorted(unexpected)} }"
        )
        ledger.mechanic("G1:offerability",
                        f"{len(ACTION_REGISTRY) - len(unofferable)} offerable")

    def test_offerable_actions_have_a_dispatch_path(self, ledger):
        """Each offerable action must resolve or refuse cleanly — never crash."""
        from components.combat.action_registry import ACTION_REGISTRY, is_offerable

        crashed: List[str] = []
        exercised: List[str] = []

        for name in sorted(ACTION_REGISTRY):
            if not is_offerable(name):
                continue
            engine, wrapper, resolver = build_battle(characters=[
                character_template(), monster_template("gob", "Goblin")])
            try:
                result = resolver.resolve_action(
                    {"actor": "aggi", "action_type": name, "target": "gob"})
                assert isinstance(result, dict), f"{name} returned {type(result)}"
                assert "success" in result or "error" in result, (
                    f"{name} returned an unreadable result: {result}")
                exercised.append(name)
            except Exception as exc:                     # noqa: BLE001
                crashed.append(f"{name}: {type(exc).__name__}: {exc}")

        assert not crashed, "offerable actions crashed:\n  - " + "\n  - ".join(crashed)
        for name in exercised:
            ledger.action(name, "dispatched without crashing")
        ledger.mechanic("C7:all_actions_dispatch", f"{len(exercised)} actions")
