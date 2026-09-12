"""
D&D 5e class features, as DATA (Rage, Sneak Attack, Second Wind, Action Surge, …).

WHAT WAS BROKEN
---------------
`CharacterData.features` has existed since the first commit and **nothing read it**:

    grep -rn "class_features" --include="*.py" components/ agents/ core/   ->  0 hits
    grep -rn '"features"'     --include="*.py" components/                 ->  writes only

`core/game_initialization.py:403` even authors `"features": ["Fighting Style",
"Second Wind"]` on the shipped Fighter. Those strings went into a list that no code
path ever looked at again, so a level-5 Barbarian and a level-5 Wizard fought
identically apart from their ability scores. No Rage, no Sneak Attack, no Second
Wind, no Action Surge — the entire "what your class does" half of 5e combat.

WHY DATA AND NOT CODE
---------------------
`data/rules/class_features/class_features.json` holds the table; this module is the
interpreter. Same lesson as plan 3.1b (`maneuver_executor.py`): Surgebinding stalled
at 4 of 10 surges because each new one needed a new Python class. Adding Uncanny
Dodge or Reckless Attack here means adding a JSON object.

THE FOUR ENGINE SEAMS, AND WHY THESE AND NOT OTHERS
---------------------------------------------------
Every effect below writes to a PERSISTENT engine value and records how to undo it.
`entity.ac_bonus()` and `entity.attack_bonus()` build a FRESH object per call, so
mutating what they return is silently discarded (see tactical_rules.py). Measured
against the live engine before writing a line of this module:

    melee_damage_bonus.self_static      +2  ->  greataxe damage bonus 4 -> 6, and 4
                                              again after remove_value_modifier
    health.damage_reduction.self_static RESISTANCE(Bludgeoning) -> take_damage(20)
                                              returns 20, then 10, then 20 once
                                              removed; FIRE stays 20 throughout
    equipment.extra_attack_damage_*     four PARALLEL lists; appending
                                              (6, 3, zero, Slashing) makes
                                              get_damages() return a second Damage
                                              of 3d6 on every attack
    action_economy.actions.self_static  a +1 NumericalModifier is a real extra
                                              action; reset_all_costs() clears it

`melee_damage_bonus` (not `damage_bonus`) is what Rage wants: the engine only folds
it in for non-ranged weapons, which is exactly 5e's "melee weapon attack using
Strength".

ONCE-PER-TURN WITHOUT TOUCHING THE RESOLVER
-------------------------------------------
Sneak Attack and Divine Smite trigger ON A HIT, and `combat_action_resolver.py` is
owned by another agent. So instead of a call site, this module ARMS the extra damage
before the attack and registers an `EventHandler` on `EventType.ATTACK` /
`EventPhase.EFFECT` that disarms it after. Verified: the handler fires with the
outcome already resolved (`AttackOutcome.HIT` visible) for exactly the entity that
attacked. A handler trigger must be SIMPLE (no source/target uuid) or it never
matches — `EventQueue._get_handlers_for_event` builds the lookup key from the
event's own source AND target, so a source-scoped trigger silently never fires. That
was measured too: zero handler calls with a source-scoped trigger, eight with a
simple one.

WHAT THIS DELIBERATELY DOES NOT DO
----------------------------------
Extra Attack lives in `components/combat/multiattack.py` (another agent's file).
Subclass features, Ki, Wild Shape and Metamagic are absent: they need seams that do
not exist yet, and half a feature that looks like it works is the failure this
project keeps repeating (plan §14e).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from uuid import UUID

from config.logging_config import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FEATURES_FILE = (PROJECT_ROOT / "data" / "rules" / "class_features"
                 / "class_features.json")

# The effect node types the authored table uses. An unknown type RAISES rather than
# being skipped: a feature that silently does nothing is indistinguishable from one
# that works, which is the bug class this module exists to end.
KNOWN_EFFECTS = frozenset({
    "heal", "grant_action", "melee_damage_bonus", "resistance",
    "extra_attack_damage", "inspiration_die", "save_or_condition",
})

# Activations that cost something from the action economy.
_COST_TYPE_BY_ACTIVATION = {
    "action": "actions",
    "bonus_action": "bonus_actions",
    "reaction": "reactions",
}


class FeatureDataError(ValueError):
    """A malformed feature entry. Raised loudly — see the module docstring."""


# ---------------------------------------------------------------------------
# The table
# ---------------------------------------------------------------------------

class ClassFeatureTable:
    """
    Loads `class_features.json` and answers "what does this character have?".

    Kept separate from the executor so the table can be queried by the character
    sheet (which features to grant at level-up) without constructing a combat
    engine.
    """

    def __init__(self, path: Path = FEATURES_FILE):
        self.path = Path(path)
        self._features: List[Dict[str, Any]] = []
        self.load()

    def load(self) -> int:
        """Load the table. Returns the number of features."""
        if not self.path.exists():
            logger.warning(f"⚠️ Class-feature table not found: {self.path}")
            return 0
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"❌ Could not parse {self.path.name}: {e}")
            return 0

        self._features = list(payload.get("features") or [])
        for entry in self._features:
            self._validate_entry(entry)

        logger.info(
            f"📖 Loaded {len(self._features)} class features from "
            f"{self.path.name}: "
            f"{', '.join(f['id'] for f in self._features)}")
        return len(self._features)

    @staticmethod
    def _validate_entry(entry: Dict[str, Any]) -> None:
        """A malformed entry is a DATA bug; say so at load time, not mid-combat."""
        for required in ("id", "name", "activation", "effects"):
            if required not in entry:
                raise FeatureDataError(
                    f"feature {entry.get('id', '?')!r} has no {required!r}")
        for node in entry["effects"]:
            if not isinstance(node, dict):
                raise FeatureDataError(
                    f"{entry['id']}: effect is {type(node).__name__}, not an object")
            if node.get("type") not in KNOWN_EFFECTS:
                raise FeatureDataError(
                    f"{entry['id']}: unknown effect type {node.get('type')!r}")

    # ------------------------------------------------------------- queries

    def all(self) -> List[Dict[str, Any]]:
        return list(self._features)

    def get(self, feature_id: str) -> Optional[Dict[str, Any]]:
        needle = (feature_id or "").strip().lower()
        for entry in self._features:
            if entry["id"] == needle or entry["name"].lower() == needle:
                return entry
        return None

    def for_character(self, character_class: str,
                      level: int) -> List[Dict[str, Any]]:
        """
        Features a character of this class and level has.

        Class matching is on the lowercased `character_class`, which is what
        CharacterData stores. A Roshar order ("Windrunner") matches nothing here
        by design: their abilities are Surges, in surgebinding.json.
        """
        char_class = (character_class or "").strip().lower()
        out = []
        for entry in self._features:
            classes = [c.lower() for c in (entry.get("classes") or [])]
            if classes and char_class not in classes:
                continue
            if int(level or 1) < int(entry.get("min_level", 1)):
                continue
            out.append(entry)
        return out


_TABLE: Optional[ClassFeatureTable] = None


def get_feature_table() -> ClassFeatureTable:
    """Shared ClassFeatureTable instance."""
    global _TABLE
    if _TABLE is None:
        _TABLE = ClassFeatureTable()
    return _TABLE


# ---------------------------------------------------------------------------
# Scaling
# ---------------------------------------------------------------------------

def _scaled(table: Dict[str, Any], level: int, default: int = 0) -> int:
    """
    Read a `{"1": 2, "9": 3}` level table: the highest key <= level wins.

    5e scaling tables are written as "at 9th level this becomes 3", so a naive
    exact-key lookup returns the default for every level in between.
    """
    best = default
    for key in sorted((int(k) for k in table), reverse=False):
        if level >= key:
            best = table[str(key)]
    return int(best)


def rage_damage_bonus(level: int) -> int:
    """5e: +2 at 1st, +3 at 9th, +4 at 16th."""
    entry = get_feature_table().get("rage") or {}
    return _scaled((entry.get("scaling") or {}).get("damage_bonus", {}),
                   int(level or 1), default=2)


def rage_uses(level: int) -> int:
    entry = get_feature_table().get("rage") or {}
    return _scaled((entry.get("scaling") or {}).get("uses", {}),
                   int(level or 1), default=2)


def sneak_attack_dice(level: int) -> int:
    """5e: one d6 per odd rogue level — 1 at 1st, 2 at 3rd, 3 at 5th …"""
    entry = get_feature_table().get("sneak_attack") or {}
    return _scaled((entry.get("scaling") or {}).get("dice_by_level", {}),
                   int(level or 1), default=1)


def bardic_die(level: int) -> int:
    entry = get_feature_table().get("bardic_inspiration") or {}
    return _scaled((entry.get("scaling") or {}).get("die_by_level", {}),
                   int(level or 1), default=6)


def max_uses(entry: Dict[str, Any], character) -> int:
    """
    How many times this character can use the feature between recoveries.

    `uses` may be an int, `"proficiency_bonus"`, `"charisma_modifier"` or
    `"unlimited"`; a per-level `scaling.uses` table overrides a plain int, which is
    how a 6th-level Barbarian gets four rages rather than the two the base entry
    names.
    """
    uses = entry.get("uses", 1)
    level = int(getattr(character, "level", 1) or 1)

    scaling = (entry.get("scaling") or {}).get("uses")
    if scaling:
        return _scaled(scaling, level, default=int(uses) if isinstance(uses, int) else 1)

    if uses == "unlimited":
        return -1                      # -1 reads as "never runs out"
    if uses == "proficiency_bonus":
        return int(getattr(character, "proficiency_bonus", 2) or 2)
    if isinstance(uses, str) and uses.endswith("_modifier"):
        ability = uses[: -len("_modifier")]
        mods = getattr(character, "ability_modifiers", {}) or {}
        return max(1, int(mods.get(ability, 0) or 0))
    return int(uses or 1)


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class FeatureResult:
    """
    What using a feature did.

    Granular on purpose: `events` is the ordered list of what happened so a
    narrator can describe it and a test can assert on measured outcomes rather
    than re-deriving them from prose.
    """

    feature: str
    actor: str
    success: bool = True
    error: str = ""
    events: List[Dict[str, Any]] = field(default_factory=list)
    healed: int = 0
    uses_remaining: int = 0

    def describe(self) -> str:
        if not self.success:
            return f"{self.actor} cannot use {self.feature}: {self.error}"
        parts = []
        if self.healed:
            parts.append(f"regains {self.healed} HP")
        for event in self.events:
            if event["type"] == "grant_action":
                parts.append("gains an extra action")
            elif event["type"] == "resistance":
                parts.append("resists " + "/".join(
                    t.lower() for t in event["damage_types"]))
            elif event["type"] == "melee_damage_bonus":
                parts.append(f"+{event['amount']} melee damage")
            elif event["type"] == "extra_attack_damage":
                parts.append(f"+{event['count']}d{event['dice']} on the next hit")
            elif event["type"] == "inspiration_die":
                parts.append(f"inspires {event['target']} (d{event['dice']})")
            elif event["type"] == "save_or_condition":
                parts.append(f"{event['target']} "
                             + ("is " + event["condition"] if event["failed"]
                                else "resists"))
        return f"{self.actor} uses {self.feature}" + (
            f" ({'; '.join(parts)})" if parts else "")


@dataclass
class _Applied:
    """
    A modifier that is currently applied, and everything needed to undo it.

    Recorded because these live on the ENTITY, which outlives the encounter. A
    modifier applied without its removal recipe is a permanent one — a barbarian
    who raged once would keep resistance to slashing for the rest of the campaign.
    """

    feature_id: str
    char_id: str
    value_modifiers: List[Tuple[Any, UUID]] = field(default_factory=list)
    resistances: List[Tuple[Any, UUID]] = field(default_factory=list)
    extra_damage_slots: int = 0          # entries appended to the parallel lists
    rounds_left: int = 0


# ---------------------------------------------------------------------------
# The engine
# ---------------------------------------------------------------------------

class ClassFeatureEngine:
    """
    Applies and clears class features against live combat state.

    CharacterManager stays the authority for *how many uses are left* (it is the
    character-data owner and the thing rests recharge); this engine owns only the
    per-encounter engine-side modifiers, which it must because it is the only
    thing holding their removal ids.
    """

    def __init__(self, dnd_wrapper, character_manager=None, combat_state=None,
                 dice_roller=None, tactical_grid=None):
        self.wrapper = dnd_wrapper
        self.characters = character_manager or getattr(
            dnd_wrapper, "character_manager", None)
        self.combat_state = combat_state if combat_state is not None else {}
        self.grid = tactical_grid
        self.table = get_feature_table()

        if dice_roller is None:
            from components.dice import DiceRoller
            dice_roller = DiceRoller()
        self.dice = dice_roller

        # feature_id -> char_id -> _Applied
        self._active: Dict[str, Dict[str, _Applied]] = {}
        # Registered EventHandlers, so they can be removed at end of combat.
        self._handlers: List[Any] = []
        # Attack events already consumed by an on-hit feature, keyed by lineage so
        # the same attack cannot fire Sneak Attack twice.
        self._seen_attacks: set = set()

    # ------------------------------------------------------------- discovery

    def available(self, char_id: str) -> List[Dict[str, Any]]:
        """
        Features this character can use RIGHT NOW.

        Filtered by class, level, remaining uses and — for on-hit features — by
        whether the trigger currently holds. An offered feature the actor cannot
        actually use is the same trap as an action needing a parameter nobody
        supplies (see `action_registry.is_offerable`).
        """
        character = self._character(char_id)
        if character is None:
            return []

        out = []
        for entry in self.table.for_character(
                getattr(character, "character_class", ""),
                int(getattr(character, "level", 1) or 1)):
            if self.uses_left(char_id, entry["id"]) == 0:
                continue
            if entry["id"] in self._active and char_id in self._active[entry["id"]]:
                continue          # already raging; do not offer it twice
            out.append(entry)
        return out

    def uses_left(self, char_id: str, feature_id: str) -> int:
        """
        Uses remaining before a recovery. -1 means unlimited.

        Reads CharacterData, which is the authority and the thing rests reset.
        """
        character = self._character(char_id)
        entry = self.table.get(feature_id)
        if character is None or entry is None:
            return 0
        from components.character_manager import feature_uses_left

        return feature_uses_left(character, entry)

    # --------------------------------------------------------------- execute

    def use(self, char_id: str, feature_id: str,
            target: str = "") -> FeatureResult:
        """
        Use one feature.

        Spends the use FIRST, then applies the effects — 5e expends the resource on
        use, and refunding on a partial effect would let a player fish for a good
        Second Wind roll.
        """
        entry = self.table.get(feature_id)
        result = FeatureResult(feature=(entry or {}).get("name", feature_id),
                               actor=char_id)

        blocked = self._blocked_reason(char_id, entry)
        if blocked:
            result.success = False
            result.error = blocked
            logger.info(f"   ⛔ {char_id} cannot use {feature_id}: {blocked}")
            return result

        assert entry is not None       # _blocked_reason covers None
        if not self._spend_use(char_id, entry):
            result.success = False
            result.error = "no uses remaining"
            return result

        logger.info(f"   ✨ {char_id} uses {entry['name']}")
        try:
            self._run_effects(entry, char_id, target, result)
        except FeatureDataError as e:
            result.success = False
            result.error = str(e)
            logger.error(f"❌ {entry['name']} is malformed: {e}")

        result.uses_remaining = self.uses_left(char_id, entry["id"])
        return result

    def _blocked_reason(self, char_id: str,
                        entry: Optional[Dict[str, Any]]) -> str:
        if entry is None:
            return "no such feature"
        character = self._character(char_id)
        if character is None:
            return "unknown character"

        char_class = (getattr(character, "character_class", "") or "").lower()
        classes = [c.lower() for c in (entry.get("classes") or [])]
        if classes and char_class not in classes:
            return f"{entry['name']} is a {'/'.join(classes)} feature"

        level = int(getattr(character, "level", 1) or 1)
        if level < int(entry.get("min_level", 1)):
            return f"requires level {entry['min_level']}"

        if self.uses_left(char_id, entry["id"]) == 0:
            return "no uses remaining"

        cost_type = _COST_TYPE_BY_ACTIVATION.get(str(entry.get("activation")))
        entity = self._entity(char_id)
        if cost_type and entity is not None:
            if not entity.action_economy.can_afford(cost_type, 1):
                return f"no {cost_type.replace('_', ' ')} remaining"

        if (entry.get("cost") or {}).get("spell_slot"):
            if self._lowest_spell_slot(character) is None:
                return "no spell slot to expend"
        return ""

    def _spend_use(self, char_id: str, entry: Dict[str, Any]) -> bool:
        """
        Debit a use, its spell-slot cost and the action economy.

        CharacterManager owns the per-rest use count. A feature whose cost is a
        spell slot (Divine Smite) must ALSO expend the slot here: `use()` promises
        it spends the resource on use, and Divine Smite is `uses: unlimited`, so
        without this its only cost is never paid and a paladin would smite for free
        on every hit. `_blocked_reason` has already confirmed a slot is available,
        and `spend_spell_slot_for` is a no-op returning True for a feature with no
        slot cost, so this is safe for every other feature.
        """
        from components.character_manager import spend_feature_use

        character = self._character(char_id)
        if character is None or not spend_feature_use(character, entry):
            return False
        if not self.spend_spell_slot_for(char_id, entry):
            return False

        cost_type = _COST_TYPE_BY_ACTIVATION.get(str(entry.get("activation")))
        entity = self._entity(char_id)
        if cost_type and entity is not None:
            try:
                entity.action_economy.consume(cost_type, 1,
                                              cost_name=entry["id"])
            except Exception as e:
                logger.debug(f"   Could not debit {cost_type} for {char_id}: {e}")
        return True

    # ------------------------------------------------------------ effects

    def _run_effects(self, entry: Dict[str, Any], char_id: str, target: str,
                     result: FeatureResult) -> None:
        applied = _Applied(feature_id=entry["id"], char_id=char_id,
                           rounds_left=int(entry.get("duration_rounds", 0) or 0))
        for node in entry.get("effects") or []:
            node_type = node.get("type")
            if node_type not in KNOWN_EFFECTS:
                raise FeatureDataError(f"unknown effect type {node_type!r}")
            getattr(self, f"_effect_{node_type}")(
                node, entry, char_id, target, result, applied)

        if applied.value_modifiers or applied.resistances or applied.extra_damage_slots:
            self._active.setdefault(entry["id"], {})[char_id] = applied

    def _effect_heal(self, node, entry, char_id, target, result, applied) -> None:
        """Restore HP (Second Wind). Never above maximum, as 5e requires."""
        entity = self._entity(char_id)
        character = self._character(char_id)
        if entity is None:
            return

        amount = self._roll(str(node.get("amount") or "0"), character)
        before = self.wrapper.get_entity_current_hp(entity)
        maximum = self.wrapper.get_entity_max_hp(entity)
        entity.health.heal(amount)
        after = self.wrapper.get_entity_current_hp(entity)
        healed = after - before

        # Keep CharacterData in step; it is the RECORD and combat_state the
        # display. Writing only the engine is how healing vanished at end of
        # encounter before `_sync_hp_from_engine` existed.
        if character is not None and isinstance(character.hit_points, dict):
            character.hit_points["current"] = after
        state = (self.combat_state.get("combatant_states") or {}).get(char_id)
        if isinstance(state, dict):
            state["hp_current"] = after

        result.healed += healed
        result.events.append({"type": "heal", "rolled": amount,
                              "healed": healed, "hp": after, "hp_max": maximum})
        logger.info(f"      💚 {char_id} regains {healed} HP ({after}/{maximum})")

    def _effect_grant_action(self, node, entry, char_id, target, result,
                             applied) -> None:
        """
        Action Surge: a REAL extra action, not a flag.

        A +1 NumericalModifier on `action_economy.actions.self_static` is what the
        economy actually reads, so the engine's own `Attack` cost evaluator lets a
        second attack through. Verified: actions 0 -> 1 and a second Attack that was
        refused now resolves.
        """
        from dnd.core.modifiers import NumericalModifier

        entity = self._entity(char_id)
        if entity is None:
            return
        cost_type = str(node.get("cost_type") or "actions")
        amount = int(node.get("amount", 1) or 1)
        pool = getattr(entity.action_economy, cost_type, None)
        if pool is None:
            raise FeatureDataError(f"no action pool {cost_type!r}")

        modifier = NumericalModifier(name=entry["id"], value=amount,
                                     source_entity_uuid=entity.uuid,
                                     target_entity_uuid=entity.uuid)
        applied.value_modifiers.append(
            (pool, pool.self_static.add_value_modifier(modifier)))
        result.events.append({"type": "grant_action", "cost_type": cost_type,
                              "amount": amount,
                              "now": pool.normalized_score})
        logger.info(f"      ⚡ {char_id} gains {amount} extra {cost_type} "
                    f"(now {pool.normalized_score})")

    def _effect_melee_damage_bonus(self, node, entry, char_id, target, result,
                                   applied) -> None:
        """
        Rage's +damage, on `equipment.melee_damage_bonus`.

        NOT `damage_bonus`: the engine folds `melee_damage_bonus` in only for
        non-ranged weapons, which is precisely 5e's "melee weapon attack using
        Strength". Putting it on `damage_bonus` would buff a longbow.
        """
        from dnd.core.modifiers import NumericalModifier

        entity = self._entity(char_id)
        character = self._character(char_id)
        if entity is None:
            return
        amount = self._resolve_amount(node.get("amount"), character)
        value = entity.equipment.melee_damage_bonus
        modifier = NumericalModifier(name=entry["id"], value=amount,
                                     source_entity_uuid=entity.uuid,
                                     target_entity_uuid=entity.uuid)
        applied.value_modifiers.append(
            (value, value.self_static.add_value_modifier(modifier)))
        result.events.append({"type": "melee_damage_bonus", "amount": amount})
        logger.info(f"      💪 {char_id}: +{amount} melee damage")

    def _effect_resistance(self, node, entry, char_id, target, result,
                           applied) -> None:
        """
        Rage's resistance, keyed PER damage type.

        The engine has no wildcard, so each type is added explicitly — the same
        shape `engine_conditions.Petrified` uses for "resistance to all damage".
        Measured: take_damage(20, Bludgeoning) returns 20, then 10 with the
        modifier, then 20 again once removed, while FIRE stays 20 throughout.
        """
        from dnd.core.modifiers import (DamageType, ResistanceModifier,
                                        ResistanceStatus)

        entity = self._entity(char_id)
        if entity is None:
            return
        reduction = entity.health.damage_reduction
        names = list(node.get("damage_types") or [])
        for name in names:
            try:
                damage_type = DamageType(str(name).capitalize())
            except ValueError:
                raise FeatureDataError(f"unknown damage type {name!r}")
            modifier = ResistanceModifier(
                name=entry["id"], value=ResistanceStatus.RESISTANCE,
                damage_type=damage_type,
                source_entity_uuid=entity.uuid, target_entity_uuid=entity.uuid)
            applied.resistances.append(
                (reduction, reduction.self_static.add_resistance_modifier(modifier)))
        result.events.append({"type": "resistance", "damage_types": names})
        logger.info(f"      🛡️  {char_id} resists {', '.join(names).lower()}")

    def _effect_extra_attack_damage(self, node, entry, char_id, target, result,
                                    applied) -> None:
        """
        ARM extra damage dice on the actor's next hit (Sneak Attack, Divine Smite).

        `equipment.extra_attack_damage_*` are four PARALLEL lists that
        `Equipment.get_damages()` zips into additional Damage objects, so an armed
        entry rides along on whatever attack happens next — including one made
        through the engine's own `Attack` action, which is why this needs no change
        to the resolver.

        `damage_type: "weapon"` means "same type as the weapon", which is what 5e
        says for Sneak Attack (it is not a separate damage type).
        """
        from dnd.core.modifiers import DamageType
        from dnd.core.values import ModifiableValue

        entity = self._entity(char_id)
        character = self._character(char_id)
        if entity is None:
            return

        count = self._resolve_amount(node.get("count"), character)
        dice = int(node.get("dice", 6) or 6)
        if count <= 0:
            return

        wanted = str(node.get("damage_type") or "weapon")
        if wanted == "weapon":
            weapon = getattr(entity.equipment, "weapon_main_hand", None)
            damage_type = getattr(weapon, "damage_type", DamageType.BLUDGEONING)
        else:
            try:
                damage_type = DamageType(wanted.capitalize())
            except ValueError:
                raise FeatureDataError(f"unknown damage type {wanted!r}")

        equipment = entity.equipment
        equipment.extra_attack_damage_dices.append(dice)
        equipment.extra_attack_damage_dices_numbers.append(count)
        equipment.extra_attack_damage_bonus.append(
            ModifiableValue.create(source_entity_uuid=entity.uuid, base_value=0,
                                   value_name=f"{entry['id']}_bonus"))
        equipment.extra_attack_damage_type.append(damage_type)
        applied.extra_damage_slots += 1

        result.events.append({"type": "extra_attack_damage", "dice": dice,
                              "count": count,
                              "damage_type": str(damage_type)})
        logger.info(f"      🗡️  {char_id} arms {count}d{dice} "
                    f"{str(damage_type).rsplit('.', 1)[-1]} on the next hit")

        # Disarm after the attack resolves. Without this the dice stay on EVERY
        # attack for the rest of the fight, which is the difference between Sneak
        # Attack and "the rogue deals +3d6 forever".
        self._arm_disarm_handler(char_id, entry["id"])

    def _effect_inspiration_die(self, node, entry, char_id, target, result,
                                applied) -> None:
        """
        Bardic Inspiration: hand an ally a die they can spend on one roll.

        Parked on the target's combat state rather than converted into a modifier,
        because 5e lets the RECIPIENT choose which roll to add it to — pre-applying
        it to an attack bonus would spend it for them. The session decides when it
        is used; this records that they have it.
        """
        recipient = target or char_id
        die = self._resolve_amount(node.get("dice"), self._character(char_id))
        states = self.combat_state.get("combatant_states")
        if isinstance(states, dict):
            state = states.setdefault(recipient, {})
            state.setdefault("inspiration_dice", []).append(int(die))
        result.events.append({"type": "inspiration_die", "dice": int(die),
                              "target": recipient})
        logger.info(f"      🎵 {char_id} inspires {recipient} (d{int(die)})")

    def _effect_save_or_condition(self, node, entry, char_id, target, result,
                                  applied) -> None:
        """Channel Divinity: a saving throw, and a 5e condition on a failure."""
        recipient = target or ""
        if not recipient:
            result.events.append({"type": "save_or_condition", "target": "",
                                  "failed": False, "condition": "",
                                  "note": "no target chosen"})
            return

        ability = str(node.get("ability") or "wisdom")
        dc = self._save_dc(char_id)
        roll = self._roll_save(recipient, ability)
        failed = roll < dc
        condition = str(node.get("condition") or "Frightened")

        if failed and self.wrapper is not None:
            self.wrapper.apply_condition(recipient, condition, source_id=char_id)

        result.events.append({"type": "save_or_condition", "target": recipient,
                              "ability": ability, "dc": dc, "roll": roll,
                              "failed": failed, "condition": condition})
        logger.info(f"      🎲 {recipient} {ability} save {roll} vs DC {dc} — "
                    f"{'FAIL' if failed else 'success'}")

    # ----------------------------------------------------------- on-hit path

    def on_hit_features(self, char_id: str,
                        target_id: str = "") -> List[Dict[str, Any]]:
        """
        On-hit features whose trigger currently holds (Sneak Attack, Divine Smite).

        Checked BEFORE the attack, because that is when the extra dice have to be
        armed. `advantage_or_ally_adjacent` is exactly 5e's Sneak Attack condition
        and both halves are real: advantage genuinely works since
        `Dice._roll_with_advantage` was fixed (it rolled one die and took max() of a
        one-element list), and adjacency comes from the tactical grid.
        """
        character = self._character(char_id)
        if character is None:
            return []

        out = []
        for entry in self.table.for_character(
                getattr(character, "character_class", ""),
                int(getattr(character, "level", 1) or 1)):
            if entry.get("activation") != "on_hit":
                continue
            if self.uses_left(char_id, entry["id"]) == 0:
                continue
            if not self.trigger_holds(entry, char_id, target_id):
                continue
            out.append(entry)
        return out

    def trigger_holds(self, entry: Dict[str, Any], char_id: str,
                      target_id: str = "") -> bool:
        """Whether an on-hit feature's `trigger` is satisfied right now."""
        trigger = str(entry.get("trigger") or "")
        if not trigger:
            return True
        if trigger == "spell_slot_available":
            return self._lowest_spell_slot(self._character(char_id)) is not None
        if trigger == "advantage_or_ally_adjacent":
            return (self._has_advantage(char_id)
                    or self._ally_adjacent_to(char_id, target_id))
        raise FeatureDataError(f"unknown trigger {trigger!r}")

    def _has_advantage(self, char_id: str) -> bool:
        """
        Does this attacker have advantage on its weapon attack?

        Read off the weapon's persistent attack_bonus, which is where every real
        source of advantage lands — flanking (tactical_rules), Reckless Attack,
        a prone target. Reading `entity.attack_bonus()` instead would work but
        rebuilds the whole object per call.
        """
        from dnd.core.modifiers import AdvantageStatus

        entity = self._entity(char_id)
        if entity is None:
            return False
        weapon = getattr(entity.equipment, "weapon_main_hand", None)
        bonus = getattr(weapon, "attack_bonus", None)
        if bonus is None:
            return False
        try:
            return bonus.advantage == AdvantageStatus.ADVANTAGE
        except Exception:
            return False

    def _ally_adjacent_to(self, char_id: str, target_id: str) -> bool:
        """
        5e: no advantage needed if another enemy of the target is within 5 feet.

        Needs the grid; without one there is no adjacency to speak of and this
        returns False rather than guessing — the pre-grid combat had everyone
        permanently adjacent, which would have made Sneak Attack unconditional.
        """
        grid = self.grid or self.combat_state.get("tactical_grid")
        if grid is None or not target_id:
            return False

        states = self.combat_state.get("combatant_states") or {}
        my_side = (states.get(char_id) or {}).get("is_hostile")
        target = grid.position_of(target_id)
        if target is None:
            return False

        for other_id, state in states.items():
            if other_id in (char_id, target_id):
                continue
            if state.get("is_hostile") != my_side:
                continue          # must be an ally of the attacker
            position = grid.position_of(other_id)
            if position is None:
                continue
            if max(abs(position[0] - target[0]),
                   abs(position[1] - target[1])) <= 1:
                return True
        return False

    def _arm_disarm_handler(self, char_id: str, feature_id: str) -> None:
        """
        Register the handler that removes armed extra dice after one attack.

        A SIMPLE trigger (no source/target uuid) is required:
        `EventQueue._get_handlers_for_event` builds its lookup key from the event's
        own source AND target uuids, so a source-scoped trigger never matches. That
        was measured — zero handler calls scoped, eight simple — and it is the sort
        of thing that would otherwise look like "Sneak Attack works" while the dice
        silently stayed armed all fight.
        """
        from dnd.core.events import (EventHandler, EventPhase, EventQueue,
                                     EventType, Trigger)

        entity = self._entity(char_id)
        if entity is None:
            return

        def processor(event, source_entity_uuid=None):
            # Only OUR attack, and only once per attack lineage: the queue
            # re-registers an event on each phase transition, so a handler sees
            # the same attack several times.
            if event.source_entity_uuid != entity.uuid:
                return None
            key = (feature_id, char_id, getattr(event, "lineage_uuid", None))
            if key in self._seen_attacks:
                return None
            self._seen_attacks.add(key)
            self.clear(feature_id, char_id)
            logger.debug(f"   🗡️  {char_id}'s {feature_id} dice spent")
            return None

        handler = EventHandler(
            name=f"{feature_id}:{char_id}",
            source_entity_uuid=entity.uuid,
            trigger_conditions=[Trigger(event_type=EventType.ATTACK,
                                        event_phase=EventPhase.EFFECT)],
            event_processor=processor)
        EventQueue.add_event_handler(handler)
        self._handlers.append(handler)

    # --------------------------------------------------------------- removal

    def is_active(self, feature_id: str, char_id: str) -> bool:
        return char_id in self._active.get(feature_id, {})

    def active_features(self, char_id: str) -> List[str]:
        return [fid for fid, holders in self._active.items()
                if char_id in holders]

    def clear(self, feature_id: str, char_id: str) -> bool:
        """
        Remove every modifier one feature applied to one character.

        Returns whether anything was removed. This is the half that makes
        "temporary" temporary; see `_Applied`.
        """
        applied = self._active.get(feature_id, {}).pop(char_id, None)
        if applied is None:
            return False

        for value, modifier_id in applied.value_modifiers:
            try:
                value.self_static.remove_value_modifier(modifier_id)
            except Exception as e:
                logger.debug(f"   Could not remove {feature_id} modifier: {e}")
        for reduction, modifier_id in applied.resistances:
            try:
                reduction.self_static.remove_resistance_modifier(modifier_id)
            except Exception as e:
                logger.debug(f"   Could not remove {feature_id} resistance: {e}")

        if applied.extra_damage_slots:
            self._pop_extra_damage(char_id, applied.extra_damage_slots)

        logger.info(f"   ⏹️  {char_id}'s {feature_id} ends")
        return True

    def _pop_extra_damage(self, char_id: str, count: int) -> None:
        """
        Drop the last `count` entries from the four parallel extra-damage lists.

        All four must be popped together or `Equipment.get_damages()` zips
        mismatched lists and silently drops the tail — an off-by-one here reads as
        "the feature stopped working" with no error anywhere.
        """
        entity = self._entity(char_id)
        if entity is None:
            return
        equipment = entity.equipment
        lists = (equipment.extra_attack_damage_dices,
                 equipment.extra_attack_damage_dices_numbers,
                 equipment.extra_attack_damage_bonus,
                 equipment.extra_attack_damage_type)
        for _ in range(count):
            for parallel in lists:
                if parallel:
                    parallel.pop()

    def clear_all(self) -> None:
        """
        MUST run at end of combat.

        These modifiers live on the Entity, which outlives the encounter, so a
        barbarian who raged in one fight would otherwise keep +2 damage and
        resistance to slashing for every fight afterwards.
        """
        from dnd.core.events import EventQueue

        for feature_id in list(self._active):
            for char_id in list(self._active[feature_id]):
                self.clear(feature_id, char_id)
        for handler in self._handlers:
            try:
                EventQueue.remove_event_handler(handler)
            except Exception:
                pass
        self._handlers.clear()
        self._seen_attacks.clear()

    # ------------------------------------------------------- round upkeep

    def tick_round(self) -> List[Tuple[str, str]]:
        """
        Advance durations, and end Rage for anyone who did not fight.

        5e: a rage ends early if you have neither attacked a hostile creature nor
        taken damage since your last turn. `combat_state` records both, so this
        stays a query rather than a parallel bookkeeping system.

        Returns the (feature_id, char_id) pairs that ended.
        """
        ended: List[Tuple[str, str]] = []
        states = self.combat_state.get("combatant_states") or {}

        for feature_id in list(self._active):
            entry = self.table.get(feature_id) or {}
            for char_id, applied in list(self._active[feature_id].items()):
                if applied.rounds_left > 0:
                    applied.rounds_left -= 1
                    if applied.rounds_left == 0:
                        self.clear(feature_id, char_id)
                        ended.append((feature_id, char_id))
                        continue

                if entry.get("ends_when") and self._went_quiet(
                        states.get(char_id) or {}):
                    logger.info(f"   😤 {char_id}'s {entry.get('name', feature_id)} "
                                f"ends: no attack made and no damage taken")
                    self.clear(feature_id, char_id)
                    ended.append((feature_id, char_id))

        # A new round means a new "once per turn": Sneak Attack can fire again.
        self._seen_attacks.clear()
        return ended

    @staticmethod
    def _went_quiet(state: Dict[str, Any]) -> bool:
        """Neither attacked nor took damage since the last turn."""
        return not (state.get("attacked_this_round")
                    or state.get("took_damage_this_round"))

    # ---------------------------------------------------------------- helpers

    def _entity(self, char_id: str):
        if self.wrapper is None:
            return None
        return self.wrapper.entities.get(char_id)

    def _character(self, char_id: str):
        if self.characters is None:
            return None
        return self.characters.characters.get(char_id)

    def _resolve_amount(self, value: Any, character) -> int:
        """
        Resolve a named scaling amount (`"rage_damage"`, `"sneak_attack_dice"`).

        An UNKNOWN name raises rather than resolving to zero: a feature that
        silently adds +0 damage looks like it works, which is the exact class of
        bug this module exists to end (compare `maneuver_executor._interpolate`).
        """
        if isinstance(value, int):
            return value
        level = int(getattr(character, "level", 1) or 1)
        named = {
            "rage_damage": lambda: rage_damage_bonus(level),
            "sneak_attack_dice": lambda: sneak_attack_dice(level),
            "bardic_die": lambda: bardic_die(level),
            "smite_dice": lambda: 2,       # 2d8 for a 1st-level slot
        }
        key = str(value or "")
        if key not in named:
            raise FeatureDataError(f"unknown scaling name {key!r}")
        return int(named[key]())

    def _roll(self, expression: str, character) -> int:
        """
        Roll `1d10+level` style expressions.

        `+level` is the only interpolation the table uses, so it is the only one
        supported and anything else raises — see `_resolve_amount`.
        """
        level = int(getattr(character, "level", 1) or 1)
        text = expression.replace("+level", f"+{level}")
        if re.search(r"\+[a-z_]+", text):
            raise FeatureDataError(
                f"unsupported interpolation in {expression!r}; only +level")
        outcome = self.dice.damage_roll(text)
        return int(outcome.get("total_damage", 0))

    @staticmethod
    def _lowest_spell_slot(character) -> Optional[int]:
        """The lowest spell level with a slot left, or None."""
        slots = getattr(character, "spell_slots", None) or {}
        for level in sorted(int(k) for k in slots):
            entry = slots[level] if level in slots else slots.get(str(level))
            if isinstance(entry, dict) and int(entry.get("current", 0) or 0) > 0:
                return level
        return None

    def _save_dc(self, char_id: str) -> int:
        """8 + proficiency + the class's spellcasting ability modifier."""
        character = self._character(char_id)
        if character is None:
            return 10
        proficiency = int(getattr(character, "proficiency_bonus", 2) or 2)
        mods = getattr(character, "ability_modifiers", {}) or {}
        ability = {"cleric": "wisdom", "druid": "wisdom", "paladin": "charisma",
                   "bard": "charisma", "sorcerer": "charisma",
                   "warlock": "charisma", "wizard": "intelligence"}.get(
            (getattr(character, "character_class", "") or "").lower(), "wisdom")
        return 8 + proficiency + int(mods.get(ability, 0) or 0)

    def _roll_save(self, char_id: str, ability: str) -> int:
        entity = self._entity(char_id)
        if entity is None:
            return 0
        try:
            save = entity.saving_throws.get_saving_throw(ability)
            bonus = int(getattr(save.bonus, "score", 0) or 0)
        except Exception:
            bonus = 0
        modifier = getattr(entity.ability_scores, ability).modifier
        outcome = self.dice.saving_throw(ability, modifier, proficiency=bonus)
        return int(outcome.get("total", 0))

    def spend_spell_slot_for(self, char_id: str, entry: Dict[str, Any]) -> bool:
        """
        Expend the lowest available slot (Divine Smite's cost).

        Separate from `_spend_use` because a slot is not a per-rest use count and
        CharacterManager already restores slots on a long rest.
        """
        if not (entry.get("cost") or {}).get("spell_slot"):
            return True
        character = self._character(char_id)
        level = self._lowest_spell_slot(character)
        if character is None or level is None:
            return False
        slots = character.spell_slots
        pool = slots[level] if level in slots else slots.get(str(level))
        pool["current"] = int(pool.get("current", 0)) - 1
        logger.info(f"      🔮 {char_id} expends a level-{level} spell slot "
                    f"({pool['current']} left)")
        return True
