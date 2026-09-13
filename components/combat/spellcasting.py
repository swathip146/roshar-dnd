"""
5e SPELLCASTING: the seam that makes the 319 indexed SRD spells castable.

WHAT WAS ACTUALLY WRONG
----------------------
`data/rules/srd/spells.json` has held 319 spells all along, reachable through
`SRDRules.spell()`. `CharacterData` has held `spell_slots` and `spells_known` all
along. And **zero spells could be cast**, because:

  * nothing consumed `spell_slots` — grep showed it read only for display and
    for the analytics summary ("spell_slots_remaining: 'high'"), never spent;
  * there was no `cast` action in ACTION_REGISTRY, so neither the player menu nor
    the NPC AI could ever choose one;
  * `import dnd.spells` fails: the vendored engine exports exactly two actions,
    `Attack` and `Move`. There is no spell system underneath us to delegate to.

So this is built at OUR seam. `external/dnd_engine` stays frozen (plan §4).

WHY IT REUSES THE MANEUVER EXECUTOR
-----------------------------------
`ManeuverExecutor` is a working declarative effect interpreter for Surgebinding
maneuvers. A spell is the same shape of problem (save, branch, damage, condition),
so `SpellEffectExecutor` SUBCLASSES it and adds exactly what spells need:

    heal          restore hit points (no maneuver heals, so the node is new)
    spell_attack  a spell attack roll — proficiency + ability mod vs AC, NOT a
                  weapon attack. The inherited `attack` node swings the actor's
                  MAIN_HAND weapon, which for a wizard is a dagger.
    multiplier    halve damage on a successful save (Fireball's split)
    {mod}         interpolate the caster's spellcasting ability modifier
    spell_save_dc resolve the DC as 8 + proficiency + ability modifier

Writing a second effect engine would have doubled the surface where a silent zero
can hide, and the maneuver executor's 58 tests would not have covered it.

WHAT IS DELIBERATELY REFUSED
----------------------------
A spell whose mechanics exist only in prose returns
`success=False, needs_adjudication=True` with a reason, and **no slot is spent**.
See `spell_compiler.py` for the full list. The rule comes from
`data/rules/stormlight/surgebinding.json`'s `_meta.correction`: invented numbers
here were "plausible and wrong", and the #1 recurring defect in this codebase is
the silent zero that reports success.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from components.combat.maneuver_executor import (AutomationError,
                                                 ManeuverExecutor)
from components.combat.spell_compiler import MOD, CompiledSpell, compile_spell
from config.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Spellcasting ability per class (PHB / SRD). Roshar's Radiants use Stormlight
# and Surges, which have their own resource and their own DC (`invested_save_dc`
# in cosmere_rules) — they are NOT in this table, so a Windrunner does not
# silently acquire a wizard's spell save DC.
# ---------------------------------------------------------------------------
SPELLCASTING_ABILITY: Dict[str, str] = {
    "wizard": "intelligence",
    "artificer": "intelligence",
    "eldritch knight": "intelligence",
    "arcane trickster": "intelligence",
    "cleric": "wisdom",
    "druid": "wisdom",
    "ranger": "wisdom",
    "monk": "wisdom",
    "bard": "charisma",
    "sorcerer": "charisma",
    "warlock": "charisma",
    "paladin": "charisma",
}

#: Classes with no spellcasting at all — asked for a DC, they get None rather
#: than a plausible-looking 8 + proficiency + 0.
NON_CASTERS = frozenset({"fighter", "barbarian", "rogue", "monk"})

# The highest spell level 5e defines. A "level 10 slot" is not a thing.
MAX_SPELL_LEVEL = 9


class SpellcastingError(ValueError):
    """A spellcasting request that cannot be honoured at all."""


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def spellcasting_ability(character_class: str) -> Optional[str]:
    """
    The ability a class casts with, or None if it does not cast.

    Matched on whole words so "Wizard (School of Evocation)" and
    "Cleric of the Almighty" both resolve, while a substring test would match
    "Ranger" inside "Rangers of the Shattered Plains" only by luck.
    """
    text = (character_class or "").strip().lower()
    if not text:
        return None
    if text in SPELLCASTING_ABILITY:
        return SPELLCASTING_ABILITY[text]

    words = set(re.findall(r"[a-z]+", text))
    for name, ability in SPELLCASTING_ABILITY.items():
        if name in text or name in words:
            return ability
    return None


def _ability_modifier(character, ability: str) -> int:
    """
    The caster's modifier for `ability`, from CharacterData or an engine Entity.

    CharacterData carries `ability_modifiers` (a plain dict, already derived); the
    dnd_engine Entity carries `ability_scores.<name>.modifier`. Both are accepted
    so this works whichever side of the mirror the caller holds.
    """
    modifiers = getattr(character, "ability_modifiers", None)
    if isinstance(modifiers, dict) and ability in modifiers:
        return int(modifiers[ability] or 0)

    scores = getattr(character, "ability_scores", None)
    if isinstance(scores, dict) and ability in scores:
        return (int(scores[ability]) - 10) // 2
    block = getattr(scores, ability, None) if scores is not None else None
    if block is not None and hasattr(block, "modifier"):
        return int(block.modifier)
    return 0


def _proficiency_bonus(character) -> int:
    value = getattr(character, "proficiency_bonus", None)
    if value is None:
        level = int(getattr(character, "level", 1) or 1)
        return 2 + (level - 1) // 4
    return int(getattr(value, "score", value) or 2)


@dataclass
class SpellcastingStats:
    """A caster's derived numbers. `is_caster` False means every field is moot."""

    character_id: str
    character_class: str
    ability: Optional[str]
    ability_modifier: int
    proficiency_bonus: int
    save_dc: Optional[int]
    attack_bonus: Optional[int]
    level: int = 1

    @property
    def is_caster(self) -> bool:
        return self.ability is not None

    def describe(self) -> str:
        if not self.is_caster:
            return f"{self.character_id} is not a spellcaster ({self.character_class})"
        return (f"{self.character_id}: {self.ability[:3].upper()} caster, "
                f"save DC {self.save_dc}, spell attack +{self.attack_bonus}")


def spellcasting_stats(character, character_id: str = "") -> SpellcastingStats:
    """
    Spell save DC = 8 + proficiency + ability modifier.
    Spell attack bonus = proficiency + ability modifier.

    A non-caster gets `save_dc=None`, not 8 + proficiency + 0. Returning a number
    for a fighter would make "cast Fireball" look computable, and something
    downstream would then use it.
    """
    character_class = str(getattr(character, "character_class", "") or "")
    ability = spellcasting_ability(character_class)
    level = int(getattr(character, "level", 1) or 1)
    proficiency = _proficiency_bonus(character)

    if ability is None:
        return SpellcastingStats(
            character_id=character_id or str(getattr(character, "character_id", "")),
            character_class=character_class, ability=None, ability_modifier=0,
            proficiency_bonus=proficiency, save_dc=None, attack_bonus=None,
            level=level)

    modifier = _ability_modifier(character, ability)
    return SpellcastingStats(
        character_id=character_id or str(getattr(character, "character_id", "")),
        character_class=character_class, ability=ability,
        ability_modifier=modifier, proficiency_bonus=proficiency,
        save_dc=8 + proficiency + modifier,
        attack_bonus=proficiency + modifier, level=level)


# ---------------------------------------------------------------------------
# Slots
# ---------------------------------------------------------------------------

@dataclass
class SlotSpend:
    """The outcome of trying to pay for a spell. A refusal carries its reason."""

    spent: bool
    level: int = 0
    reason: str = ""
    remaining: int = 0


class SpellSlotLedger:
    """
    Reads and spends `CharacterData.spell_slots`, which nothing consumed before.

    The dict is `{level: {"current": N, "maximum": N}}`. It is keyed by INT after
    `add_character`, and by STR after a save/load round trip (`to_dict` stringifies
    the keys, `from_dict` restores ints — but a hand-written save, or JSON coming
    back from the session store, can leave strings). Both are accepted: a ledger
    that silently sees no slots would report "no slots remaining" for a full
    wizard, which is the same class of bug as a silent zero.
    """

    def __init__(self, character_manager):
        self.character_manager = character_manager

    # ------------------------------------------------------------------ reads

    def _slots(self, character_id: str) -> Dict[int, Dict[str, int]]:
        character = self.character_manager.characters.get(character_id)
        raw = getattr(character, "spell_slots", None) or {}
        normalized: Dict[int, Dict[str, int]] = {}
        for key, value in raw.items():
            try:
                level = int(key)
            except (TypeError, ValueError):
                continue
            if isinstance(value, dict):
                normalized[level] = value
        return normalized

    def available(self, character_id: str) -> Dict[int, int]:
        """{slot level: slots remaining}, only levels with at least one left."""
        return {level: int(data.get("current", 0) or 0)
                for level, data in sorted(self._slots(character_id).items())
                if int(data.get("current", 0) or 0) > 0}

    def has_any(self, character_id: str) -> bool:
        return bool(self.available(character_id))

    def highest_available(self, character_id: str) -> int:
        available = self.available(character_id)
        return max(available) if available else 0

    def lowest_usable(self, character_id: str, spell_level: int) -> Optional[int]:
        """
        The cheapest slot that can cast a level-N spell — N or higher (5e upcasting).

        A 1st-level spell cast from a 3rd-level slot is legal and burns the bigger
        slot; returning only exact matches would tell a wizard with 3rd-level slots
        left that they cannot cast Cure Wounds.
        """
        candidates = [level for level in self.available(character_id)
                      if level >= spell_level]
        return min(candidates) if candidates else None

    # ------------------------------------------------------------------ writes

    def spend(self, character_id: str, spell_level: int,
              at_level: Optional[int] = None) -> SlotSpend:
        """
        Consume a slot. Cantrips (level 0) cost nothing and always succeed.

        Refuses — with a reason, never an exception — when there is no slot, when
        the requested slot is too low for the spell, or when the character has no
        slot table at all.
        """
        character = self.character_manager.characters.get(character_id)
        if character is None:
            return SlotSpend(False, reason=f"unknown character {character_id}")

        if spell_level <= 0:
            return SlotSpend(True, level=0, reason="cantrip — no slot required")

        if at_level is not None and at_level < spell_level:
            return SlotSpend(
                False,
                reason=(f"a level {at_level} slot cannot cast a level "
                        f"{spell_level} spell"))
        if spell_level > MAX_SPELL_LEVEL:
            return SlotSpend(False,
                             reason=f"there is no level {spell_level} spell slot")

        slots = self._slots(character_id)
        if not slots:
            return SlotSpend(False,
                             reason=f"{character_id} has no spell slots at all")

        level = at_level if at_level is not None else self.lowest_usable(
            character_id, spell_level)
        if level is None:
            highest = self.highest_available(character_id)
            detail = (f"highest remaining is level {highest}" if highest
                      else "no slots remaining")
            return SlotSpend(
                False,
                reason=(f"no level {spell_level} or higher spell slot remaining "
                        f"({detail})"))

        entry = slots.get(level)
        current = int((entry or {}).get("current", 0) or 0)
        if entry is None or current <= 0:
            return SlotSpend(
                False, reason=f"no level {level} spell slot remaining")

        entry["current"] = current - 1
        logger.info(f"   🔮 {character_id} spent a level {level} slot "
                    f"({entry['current']}/{entry.get('maximum', '?')} left)")
        return SlotSpend(True, level=level, remaining=entry["current"])

    def restore(self, character_id: str, level: int, count: int = 1) -> int:
        """Give slots back (used when a cast is refused after payment)."""
        slots = self._slots(character_id)
        entry = slots.get(level)
        if entry is None:
            return 0
        maximum = int(entry.get("maximum", 0) or 0)
        entry["current"] = min(maximum, int(entry.get("current", 0) or 0) + count)
        return entry["current"]


# ---------------------------------------------------------------------------
# Concentration
# ---------------------------------------------------------------------------

@dataclass
class ConcentrationTracker:
    """
    Who is concentrating on what. Starting a new one DROPS the old one (PHB 203).

    Deliberately not doing the damage-triggered CON save: that needs a hook on
    every damage application, which lives in the engine's event system, and a
    half-wired hook that fires for some damage sources and not others would be
    worse than none — it would make concentration look enforced.
    """

    active: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def start(self, caster: str, spell: str, duration: str = "") -> Optional[str]:
        """Begin concentrating; returns the spell that was dropped, if any."""
        dropped = None
        existing = self.active.get(caster)
        if existing:
            dropped = existing.get("spell")
            logger.info(f"   🧠 {caster} stops concentrating on {dropped}")
        self.active[caster] = {"spell": spell, "duration": duration}
        logger.info(f"   🧠 {caster} concentrates on {spell} ({duration})")
        return dropped

    def concentrating_on(self, caster: str) -> Optional[str]:
        entry = self.active.get(caster)
        return entry.get("spell") if entry else None

    def stop(self, caster: str) -> Optional[str]:
        entry = self.active.pop(caster, None)
        return entry.get("spell") if entry else None


# ---------------------------------------------------------------------------
# The executor
# ---------------------------------------------------------------------------

class SpellEffectExecutor(ManeuverExecutor):
    """
    Runs a COMPILED spell's automation tree.

    Subclasses `ManeuverExecutor` so `target` / `save` / `damage` / `ieffect2` /
    `roll` behave identically to Surgebinding, and adds only what spells need.
    The inherited `attack` node is left alone — it swings a weapon, which is not
    what a spell attack is — and `spell_attack` is added beside it.
    """

    #: Node types this executor understands beyond the maneuver set.
    SPELL_NODES = frozenset({"heal", "spell_attack"})

    def __init__(self, dnd_wrapper, character_manager=None, dice_roller=None,
                 combat_state=None, concentration=None):
        concentration_tracker = concentration or ConcentrationTracker()
        super().__init__(dnd_wrapper, dice_pool=None, cosmere_rules=None,
                         dice_roller=dice_roller, combat_state=combat_state,
                         concentration=concentration_tracker)
        self.character_manager = character_manager
        self.concentration = concentration_tracker
        #: Set for the duration of one cast, so the DC/{mod}/attack bonus nodes
        #: resolve against the right caster without threading them through every
        #: node signature (the parent's node methods take a fixed argument list).
        self._stats: Optional[SpellcastingStats] = None

    # ------------------------------------------------------------ node dispatch

    def _run_nodes(self, nodes: Sequence[Dict[str, Any]], actor: str,
                   targets: List[str], result) -> None:
        """
        Extend the parent's dispatch with the spell nodes.

        Same contract as the parent: an UNKNOWN node type raises rather than being
        skipped, because skipping executes half a spell and reports success.
        """
        for node in nodes or []:
            if not isinstance(node, dict):
                raise AutomationError(
                    f"node is {type(node).__name__}, not an object")
            node_type = node.get("type")
            if node_type in self.SPELL_NODES:
                getattr(self, f"_node_{node_type}")(node, actor, targets, result)
            else:
                super()._run_nodes([node], actor, targets, result)

    # -------------------------------------------------------------- spell nodes

    def _node_heal(self, node, actor, targets, result) -> None:
        """Restore hit points. No maneuver heals, so this node is spell-only."""
        expression = self._interpolate(str(node.get("heal") or ""), actor)
        amount = self._roll_total(expression)
        multiplier = float(node.get("multiplier", 1) or 1)
        amount = int(amount * multiplier)

        for target in (targets or [actor]):
            if target is None:
                continue
            healed = self._apply_healing(target, amount)
            result.events.append({"type": "heal", "target": target,
                                  "amount": healed, "expression": expression})
            # Reuse the parent's numeric channel so `describe()` and any existing
            # consumer see the spell did something.
            result.rolls["healing"] = result.rolls.get("healing", 0) + healed
            logger.info(f"      💚 {target} regains {healed} HP")

    def _node_spell_attack(self, node, actor, targets, result) -> None:
        """
        A SPELL attack roll: d20 + proficiency + spellcasting modifier vs AC.

        Not the inherited `attack` node, which resolves the actor's MAIN_HAND
        weapon through the engine. For a wizard casting Fire Bolt that would roll
        a dagger's attack bonus and, on a hit, apply the dagger's damage — a
        plausible-looking number that is not the spell's.
        """
        bonus = self._stats.attack_bonus if self._stats else None
        if bonus is None:
            raise AutomationError(
                "spell attack requires a spellcasting ability; this caster has none")

        for target in (targets or [None]):
            if target is None:
                continue
            armor_class = self._armor_class(target, actor)
            roll = self.dice.attack_roll(int(bonus))
            total = int(roll.get("total", roll.get("selected_roll", 0)) or 0)
            natural = int(roll.get("selected_roll", 0) or 0)
            hit = bool(roll.get("is_critical_hit")) or (
                total >= armor_class and not roll.get("is_critical_miss"))

            result.events.append({"type": "spell_attack", "target": target,
                                  "roll": total, "natural": natural,
                                  "ac": armor_class, "hit": hit,
                                  "critical": bool(roll.get("is_critical_hit"))})
            logger.info(f"      ✨ spell attack on {target}: {total} vs AC "
                        f"{armor_class} — {'HIT' if hit else 'miss'}")
            self._run_nodes(node.get("hit" if hit else "miss") or [],
                            actor, [target], result)

    # ------------------------------------------------------------ node overrides

    def _node_damage(self, node, actor, targets, result) -> None:
        """
        The parent's damage node, plus `multiplier` for a halved save.

        Fireball's "half as much damage on a successful one" is the single most
        common spell mechanic in the SRD (`dc_success: "half"`), and the maneuver
        schema has no way to express it.
        """
        multiplier = float(node.get("multiplier", 1) or 1)
        if multiplier == 1:
            super()._node_damage(node, actor, targets, result)
            return

        expression = self._interpolate(str(node.get("damage") or ""), actor)
        rolled = self._roll_total(expression)
        amount = int(rolled * multiplier)
        damage_type = str(node.get("damage_type") or "force")

        for target in (targets or [None]):
            if target is None:
                continue
            dealt = self._apply_damage(target, amount, damage_type)
            result.damage_dealt += dealt
            result.events.append({"type": "damage", "target": target,
                                  "amount": dealt, "damage_type": damage_type,
                                  "expression": expression,
                                  "multiplier": multiplier})
            logger.info(f"      💥 {target} takes {dealt} {damage_type} "
                        f"(halved: {rolled} -> {amount})")

    def _interpolate(self, text: str, actor: str) -> str:
        """
        Resolve `{mod}` (the caster's spellcasting modifier), then defer.

        The parent raises on an unknown placeholder, and that behaviour is kept:
        a spell whose expression still contains `{...}` would make the dice parser
        return 0, i.e. Cure Wounds silently healing nothing.
        """
        if text and MOD in text:
            modifier = self._stats.ability_modifier if self._stats else 0
            # "1d8 + {mod}" with a NEGATIVE modifier must not become "1d8 + -1";
            # d20's grammar rejects that. Fold the sign in instead.
            text = re.sub(r"\s*\+\s*" + re.escape(MOD),
                          f" + {modifier}" if modifier >= 0 else f" - {abs(modifier)}",
                          text)
            text = text.replace(MOD, str(modifier))
        if not text:
            return text
        # The parent needs a dice_pool to resolve {lashing_die}; spells have none,
        # so only report a leftover placeholder rather than crashing on a missing
        # pool.
        leftover = re.search(r"\{([a-z_]+)\}", text)
        if leftover:
            raise AutomationError(
                f"unknown placeholder {{{leftover.group(1)}}} in a spell expression")
        return text

    def _resolve_dc(self, dc: Any, actor: str) -> int:
        """`"spell_save_dc"` -> 8 + proficiency + spellcasting ability modifier."""
        if isinstance(dc, int):
            return dc
        if str(dc) == "spell_save_dc":
            if self._stats is None or self._stats.save_dc is None:
                raise AutomationError(
                    "spell save DC requested for a character with no "
                    "spellcasting ability")
            return int(self._stats.save_dc)
        return super()._resolve_dc(dc, actor)

    # ----------------------------------------------------------------- helpers

    def _armor_class(self, target: str, actor: str) -> int:
        """The target's real AC from the engine, including armour and modifiers."""
        entity = self.wrapper.entities.get(target) if self.wrapper else None
        attacker = self.wrapper.entities.get(actor) if self.wrapper else None
        if entity is None:
            return 10
        try:
            value = entity.ac_bonus(attacker.uuid if attacker else None)
            return int(getattr(value, "normalized_score", 10) or 10)
        except Exception as e:  # pragma: no cover - engine guard
            logger.warning(f"⚠️ could not read AC for {target}: {e}")
            return 10

    def _apply_healing(self, target: str, amount: int) -> int:
        """
        Heal, and report how much actually landed.

        Clamped to the wound: healing 20 on a target missing 5 HP restores 5, and
        reporting 20 would make a test on "HP rose by the rolled amount" pass while
        the ledger lies.
        """
        entity = self.wrapper.entities.get(target) if self.wrapper else None
        if entity is None or amount <= 0:
            return 0
        con = entity.ability_scores.constitution.modifier
        before = entity.health.get_total_hit_points(con)
        entity.health.heal(int(amount))
        after = entity.health.get_total_hit_points(con)
        return int(after - before)

    # -------------------------------------------------------------------- cast

    def cast(self, compiled: CompiledSpell, actor: str,
             stats: SpellcastingStats,
             targets: Optional[Sequence[str]] = None):
        """Run a compiled spell's tree with `stats` bound for DC/{mod}/attack."""
        from components.combat.maneuver_executor import ManeuverResult

        result = ManeuverResult(maneuver=compiled.name, actor=actor)
        self._stats = stats
        try:
            self._run_nodes(compiled.automation, actor, list(targets or []),
                            result)
        except AutomationError as e:
            result.success = False
            result.error = str(e)
            logger.error(f"❌ {compiled.name} could not be executed: {e}")
        finally:
            self._stats = None
        return result


# ---------------------------------------------------------------------------
# The service the resolver calls
# ---------------------------------------------------------------------------

@dataclass
class CastResult:
    """
    What casting a spell did, in the resolver's dict-friendly shape.

    `needs_adjudication` is a first-class outcome, not an error: the spell is real
    and the caster could pay for it, but the SRD does not describe its effect in
    data. The rules judge takes it from here, and NO slot has been spent.
    """

    success: bool
    spell: str = ""
    description: str = ""
    error: str = ""
    needs_adjudication: bool = False
    slot_level: int = 0
    damage: int = 0
    healing: int = 0
    events: List[Dict[str, Any]] = field(default_factory=list)
    concentration: bool = False
    dropped_concentration: str = ""

    def as_dict(self) -> Dict[str, Any]:
        payload = {
            "success": self.success,
            "spell": self.spell,
            "description": self.description,
            "slot_level": self.slot_level,
            "damage": self.damage,
            "healing": self.healing,
            "events": self.events,
            "concentration": self.concentration,
        }
        if self.error:
            payload["error"] = self.error
        if self.needs_adjudication:
            payload["needs_adjudication"] = True
            payload["refused"] = True
        if self.dropped_concentration:
            payload["dropped_concentration"] = self.dropped_concentration
        return payload


class SpellcastingService:
    """
    Casting one spell, end to end: look it up, gate it, pay for it, execute it.

    Holds the wrapper AND the character manager, which is why `cast_spell` is a
    registry entry of its own type rather than a `BaseAction` subclass: the engine
    `Entity` is a pydantic model with no room for a slot table, and a
    `BaseAction._apply` only gets `Entity.get(uuid)` — it cannot reach
    CharacterData, which owns `spell_slots`. Mirroring slots onto the entity the
    way the Roshar surges mirror Stormlight would give two copies of the
    authoritative resource.
    """

    def __init__(self, dnd_engine_wrapper, character_manager, combat_state=None,
                 srd_rules=None, dice_roller=None, concentration=None):
        self.wrapper = dnd_engine_wrapper
        self.character_manager = character_manager
        self.combat_state = combat_state if combat_state is not None else {}
        self.slots = SpellSlotLedger(character_manager)
        self.concentration = concentration or ConcentrationTracker()

        if srd_rules is None:
            from components.srd_rules import get_srd_rules
            srd_rules = get_srd_rules()
        self.srd = srd_rules

        self.executor = SpellEffectExecutor(
            dnd_engine_wrapper, character_manager=character_manager,
            dice_roller=dice_roller, combat_state=self.combat_state,
            concentration=self.concentration)

    # ------------------------------------------------------------------ queries

    def stats_for(self, character_id: str) -> SpellcastingStats:
        character = self.character_manager.characters.get(character_id)
        if character is None:
            return SpellcastingStats(character_id=character_id,
                                     character_class="", ability=None,
                                     ability_modifier=0, proficiency_bonus=2,
                                     save_dc=None, attack_bonus=None)
        return spellcasting_stats(character, character_id)

    def known_spells(self, character_id: str) -> List[str]:
        """
        The spells this character could actually cast, in the SRD.

        `spells_known` is free text on CharacterData and doubles as the Roshar
        "Invested Arts" list, so a name with no SRD entry is dropped here rather
        than failing at cast time.
        """
        character = self.character_manager.characters.get(character_id)
        names = list(getattr(character, "spells_known", None) or [])
        names += list(getattr(character, "cantrips_known", None) or [])
        out = []
        for name in names:
            entry = self.srd.spell(name)
            if entry is not None and entry.get("name") not in out:
                out.append(entry["name"])
        return out

    def castable_spells(self, character_id: str) -> List[Dict[str, Any]]:
        """
        Known spells the caster can pay for RIGHT NOW.

        Same discipline as `ManeuverExecutor.available()`: never offer something
        that will be refused. Cantrips are always affordable; a levelled spell
        needs a slot of that level or higher.
        """
        stats = self.stats_for(character_id)
        if not stats.is_caster:
            return []

        out = []
        for name in self.known_spells(character_id):
            entry = self.srd.spell(name) or {}
            level = int(entry.get("level", 0) or 0)
            if level > 0 and self.slots.lowest_usable(character_id, level) is None:
                continue
            out.append({"name": entry.get("name", name), "level": level,
                        "concentration": bool(entry.get("concentration")),
                        "school": (entry.get("school") or {}).get("name", "")})
        return out

    def default_spell(self, character_id: str) -> Optional[str]:
        """
        The spell to cast when the caller names none.

        This is what makes `cast_spell` OFFERABLE. An action needing a parameter
        nothing supplies is filtered out of both menus by `is_offerable()` — the
        bug that made four of five Surges unplayable — so `spell_name` has to have
        a supplier. Preference: an executable spell (one whose effect compiles),
        cheapest slot first, cantrips before slots so a wizard does not burn a
        3rd-level slot by default.
        """
        candidates = self.castable_spells(character_id)
        if not candidates:
            return None

        stats = self.stats_for(character_id)

        def rank(entry):
            # `caster_level` MUST be passed: a cantrip's damage table is keyed on
            # character level, so compiling without it reports needs_adjudication
            # and every cantrip would be ranked as unexecutable — which made a
            # wizard default to burning a Cure Wounds slot instead of Fire Bolt.
            compiled = self.compile(entry["name"], entry["level"],
                                    caster_level=stats.level)
            return (compiled is None or compiled.needs_adjudication,
                    entry["level"])

        return sorted(candidates, key=rank)[0]["name"]

    def compile(self, spell_name: str, slot_level: Optional[int] = None,
                caster_level: Optional[int] = None) -> Optional[CompiledSpell]:
        entry = self.srd.spell(spell_name)
        if entry is None:
            return None
        return compile_spell(entry, slot_level=slot_level,
                             caster_level=caster_level)

    # --------------------------------------------------------------------- cast

    def cast(self, caster_id: str, spell_name: Optional[str] = None,
             targets: Optional[Sequence[str]] = None,
             at_level: Optional[int] = None) -> CastResult:
        """
        Cast a spell. Every refusal is a RESULT with a reason, never an exception.

        Order matters and is 5e's: verify the caster and the spell, check the slot,
        compile the effect, and only then spend. A spell that cannot be executed
        must not cost a slot — the player would lose the resource and get nothing,
        which is worse than being told to ask the DM.
        """
        character = self.character_manager.characters.get(caster_id)
        if character is None:
            return CastResult(False, error=f"unknown character {caster_id}",
                              description=f"{caster_id} is not in this encounter")

        stats = self.stats_for(caster_id)
        if not stats.is_caster:
            return CastResult(
                False, error="not a spellcaster",
                description=(f"{caster_id} is a "
                             f"{stats.character_class or 'non-caster'} and cannot "
                             f"cast spells"))

        if not spell_name:
            spell_name = self.default_spell(caster_id)
            if not spell_name:
                return CastResult(
                    False, error="no castable spell",
                    description=(f"{caster_id} has no spell they can cast right "
                                 f"now (no known spell with a slot to pay for it)"))

        entry = self.srd.spell(spell_name)
        if entry is None:
            return CastResult(
                False, spell=str(spell_name), error="unknown spell",
                description=f"'{spell_name}' is not in the SRD spell list")

        name = entry.get("name", spell_name)
        level = int(entry.get("level", 0) or 0)

        # Can it be paid for? Checked BEFORE compiling so "no slot" is reported as
        # a resource problem rather than as an adjudication request.
        if level > 0:
            slot_level = (at_level if at_level is not None
                          else self.slots.lowest_usable(caster_id, level))
            if slot_level is None:
                refusal = self.slots.spend(caster_id, level, at_level=at_level)
                return CastResult(
                    False, spell=name, error=refusal.reason,
                    description=f"{caster_id} cannot cast {name}: {refusal.reason}")
        else:
            slot_level = 0

        compiled = compile_spell(entry, slot_level=max(slot_level, level),
                                 caster_level=stats.level)
        if compiled.needs_adjudication and not compiled.automation:
            logger.info(f"   📜 {name} needs adjudication: {compiled.reason}")
            return CastResult(
                False, spell=name, needs_adjudication=True,
                slot_level=0, error=compiled.reason,
                description=(f"{name} cannot be resolved from the SRD data "
                             f"({compiled.reason}). No slot was spent — refer it "
                             f"to the rules judge."))

        spend = self.slots.spend(caster_id, level, at_level=at_level)
        if not spend.spent:
            return CastResult(
                False, spell=name, error=spend.reason,
                description=f"{caster_id} cannot cast {name}: {spend.reason}")

        logger.info(f"🔮 {caster_id} casts {name} "
                    f"(level {level}, slot {spend.level}, DC {stats.save_dc})")

        dropped = ""
        if compiled.concentration:
            dropped = self.concentration.start(caster_id, name,
                                               compiled.duration) or ""

        outcome = self.executor.cast(compiled, caster_id, stats, targets=targets)
        if not outcome.success:
            # The tree was malformed or unresolvable. The slot is already gone —
            # 5e expends it on use — but say plainly that nothing landed.
            return CastResult(
                False, spell=name, error=outcome.error, slot_level=spend.level,
                events=outcome.events, concentration=compiled.concentration,
                dropped_concentration=dropped,
                description=f"{name} fizzles: {outcome.error}")

        healing = int(outcome.rolls.get("healing", 0) or 0)
        parts = []
        if outcome.damage_dealt:
            parts.append(f"{outcome.damage_dealt} {compiled.damage_type or ''}"
                         f" damage".replace("  ", " "))
        if healing:
            parts.append(f"{healing} HP healed")
        if compiled.needs_adjudication:
            parts.append(f"partially resolved ({compiled.reason})")

        return CastResult(
            True, spell=name, slot_level=spend.level,
            damage=outcome.damage_dealt, healing=healing,
            events=outcome.events, concentration=compiled.concentration,
            dropped_concentration=dropped,
            needs_adjudication=compiled.needs_adjudication,
            description=(f"{caster_id} casts {name}"
                         + (f" — {'; '.join(parts)}" if parts else "")))


def can_cast_any(character) -> Tuple[bool, str]:
    """
    Whether a character could cast ANYTHING — the gate `unusable_reason` needs.

    Kept here rather than in the registry so the registry does not learn about
    class tables and slot dicts. A goblin must not be offered `cast_spell`: an
    offered action that is always refused is a trap, and one live encounter wasted
    15 of 28 NPC actions on exactly that.
    """
    if character is None:
        return False, "no character state"

    character_class = str(getattr(character, "character_class", "") or "")
    if spellcasting_ability(character_class) is None:
        return False, f"{character_class or 'this creature'} is not a spellcaster"

    known = list(getattr(character, "spells_known", None) or [])
    known += list(getattr(character, "cantrips_known", None) or [])
    if not known:
        return False, "knows no spells"

    slots = getattr(character, "spell_slots", None) or {}
    has_slot = any(int((data or {}).get("current", 0) or 0) > 0
                   for data in slots.values() if isinstance(data, dict))

    # A caster with no slots left can still cast cantrips, so this is only a
    # refusal if nothing they know is a cantrip. Resolving that needs the SRD.
    if not has_slot:
        from components.srd_rules import get_srd_rules
        srd = get_srd_rules()
        for name in known:
            entry = srd.spell(name)
            if entry is not None and int(entry.get("level", 0) or 0) == 0:
                return True, ""
        return False, "no spell slots remaining and no cantrips known"

    return True, ""
