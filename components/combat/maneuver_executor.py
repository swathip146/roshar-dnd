"""
Executes the Avrae-style `automation` trees on Surgebinding maneuvers (plan 3.1b).

THE SCHEMA WAS ALREADY THERE. All nine maneuvers in
`data/rules/stormlight/surgebinding.json` carry complete automation trees — reviewed,
with line citations back to the Handbook — using six node types:

    target     pick who the effects apply to
    save       a saving throw, with `fail` / `success` branches
    damage     roll and apply damage
    attack     an attack roll, with `hit` / `miss` branches
    roll       roll dice and report the total (a bonus for something else)
    ieffect2   apply a temporary effect: a named 5e condition, or an inline
               `effects` dict for things 5e has no condition for

**Nothing read them.** The only reader anywhere was a test asserting the JSON exists,
so it passed while no maneuver could be played. `roshar_actions.py` grew one imperative
Python class per ability instead — which is why Surgebinding stalled at 4 of the
rulebook's 10 surges: each new one needed new *code*.

This interpreter makes a maneuver DATA. Adding Division or Cohesion becomes a JSON
entry, not a new class.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
`{lashing_die}` is the only interpolation in the authored data, so that is the only one
supported. An unknown placeholder RAISES rather than silently resolving to zero — a
maneuver that quietly deals 0 damage looks like it works, which is the failure mode
this project keeps hitting.

Durations are recorded verbatim ("until the start of your next turn") and attached to
the effect, not parsed into rounds. The strings are prose written for a human DM, and
guessing at them would invent rules; the session decides when to clear them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from config.logging_config import get_logger

logger = get_logger(__name__)


def _parse_damage_type_for_resistance(damage_type_str: str):
    """
    Parse a damage type string to DamageType enum for resistance nodes.

    Handles simple types like "acid", "fire", "slashing".
    Skips complex conditions like "bludgeoning from nonmagical weapons".
    Returns None for unknown types (logs a warning in the caller).

    This is identical to dnd_engine_wrapper._parse_damage_type but kept local
    to avoid a circular import (wrapper imports maneuver_executor's result types).
    """
    from dnd.core.modifiers import DamageType

    if not damage_type_str:
        return None

    dtype_lower = damage_type_str.strip().lower()

    # Skip complex conditions
    if " from " in dtype_lower or "," in dtype_lower:
        return None

    damage_type_map = {
        "acid": DamageType.ACID,
        "bludgeoning": DamageType.BLUDGEONING,
        "cold": DamageType.COLD,
        "fire": DamageType.FIRE,
        "force": DamageType.FORCE,
        "lightning": DamageType.LIGHTNING,
        "necrotic": DamageType.NECROTIC,
        "piercing": DamageType.PIERCING,
        "poison": DamageType.POISON,
        "psychic": DamageType.PSYCHIC,
        "radiant": DamageType.RADIANT,
        "slashing": DamageType.SLASHING,
        "thunder": DamageType.THUNDER,
    }

    return damage_type_map.get(dtype_lower)


# Node types the automation trees can use. An unrecognised type is an error, not
# something to skip: silently ignoring a node would execute half a maneuver and
# report success.
#
# ORIGINAL 6: target, save, damage, attack, roll, ieffect2
# INVESTED ARTS ADDITIONS (plan 2.9): area_of_effect, check, resistance
# SURGE CANTRIP ADDITIONS (surge-complete): utility, forced_move, choice
#   * utility     — a cantrip effect with no combat mechanic (kindle a fire,
#                   recolor eyes, reshape stone). SUCCEEDS and returns narration,
#                   which is what makes such a cantrip resolvable, not adjudicated.
#   * forced_move — push/pull a target a fixed distance (a Gravitation creature
#                   Lash, an Abrasion slide), RECORDED like the reviewed
#                   Lash Enemy / Lash Ally maneuvers already record forced_move_ft.
#   * choice      — "choose one of the following effects": most surge cantrips
#                   offer 2-4 discrete effects and the caster picks one.
# NOTE: 'heal' is in SpellEffectExecutor.SPELL_NODES, not here, to preserve
# the test contract that spell nodes are additions to maneuver nodes.
KNOWN_NODES = frozenset({
    "target", "save", "damage", "attack", "roll", "ieffect2",
    "area_of_effect", "check", "resistance",
    "utility", "forced_move", "choice"
})

# The only placeholder in the reviewed data.
LASHING_DIE = "{lashing_die}"

# 5e conditions an ieffect2 can name directly; anything else is an inline effect.
_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")


class AutomationError(ValueError):
    """A malformed automation tree. Raised loudly — see the module docstring."""


@dataclass
class ManeuverResult:
    """
    What executing a maneuver did.

    Deliberately granular: `events` is the ordered list of what happened, so a
    narrator can describe it and a test can assert on it without re-deriving
    anything from prose.
    """

    maneuver: str
    actor: str
    success: bool = True
    error: str = ""
    events: List[Dict[str, Any]] = field(default_factory=list)
    damage_dealt: int = 0
    conditions_applied: List[str] = field(default_factory=list)
    effects_applied: List[Dict[str, Any]] = field(default_factory=list)
    rolls: Dict[str, int] = field(default_factory=dict)
    dice_spent: int = 0
    # Narrations from `utility` nodes — cantrip effects with no combat mechanic
    # (kindle a fire, recolor eyes, see into the Cognitive Realm). Recording them
    # is what makes such a cantrip RESOLVABLE instead of falling to adjudication.
    narrations: List[str] = field(default_factory=list)

    def describe(self) -> str:
        """One line for the combat log."""
        if not self.success:
            return f"{self.actor} cannot use {self.maneuver}: {self.error}"
        parts = []
        if self.damage_dealt:
            parts.append(f"{self.damage_dealt} damage")
        if self.conditions_applied:
            parts.append(", ".join(self.conditions_applied))
        if self.effects_applied:
            parts.append(", ".join(e["name"] for e in self.effects_applied))
        for name, value in self.rolls.items():
            parts.append(f"{name} +{value}")
        if self.narrations:
            parts.extend(n for n in self.narrations if n)
        return f"{self.actor} uses {self.maneuver}" + (
            f" ({'; '.join(parts)})" if parts else "")


class ManeuverExecutor:
    """
    Runs a maneuver's automation tree against live combat state.

    Depends on the wrapper for entities/conditions, a DiceRoller for rolls, and a
    LashingDicePool for the resource. All three are injected so this stays testable
    without a combat session.
    """

    def __init__(self, dnd_wrapper, dice_pool=None, cosmere_rules=None,
                 dice_roller=None, combat_state=None, concentration=None):
        self.wrapper = dnd_wrapper
        self.dice_pool = dice_pool
        self.rules = cosmere_rules
        self.combat_state = combat_state or {}
        self.concentration = concentration
        # Which option a `choice` node should run for the current execute() call.
        self._selected_choice: Any = None
        # Track applied resistances for teardown: target -> [(reduction, modifier_id), ...]
        self._applied_resistances: Dict[str, List[Tuple[Any, Any]]] = {}

        if dice_roller is None:
            from components.dice import DiceRoller
            dice_roller = DiceRoller()
        self.dice = dice_roller

    # ------------------------------------------------------------------ public

    def available(self, actor: str, order: str = "",
                  level: int = 1) -> List[Dict[str, Any]]:
        """
        Maneuvers this character can use RIGHT NOW.

        Filtered by order and by whether any lashing dice remain — an offered
        maneuver the actor cannot pay for is the same trap as an unsatisfiable
        action parameter.
        """
        if self.rules is None:
            return []

        order = order or self._order_of(actor)
        if not order:
            return []
        if self.dice_pool is not None and self.dice_pool.remaining(actor) <= 0:
            return []

        return [m for m in (self.rules.maneuvers(order=order) or [])
                if self._affordable(actor, m)]

    def execute(self, maneuver: Dict[str, Any], actor: str,
                targets: Optional[Sequence[str]] = None,
                choice: Optional[Any] = None) -> ManeuverResult:
        """
        Run one maneuver.

        `targets` is who the actor chose; a `target` node uses them. Spends the
        resource FIRST and refunds nothing on a miss — 5e expends the die on use.

        `choice` selects which branch of a `choice` node runs (by option id/label,
        or an int index). None uses the option flagged `default`, else the first —
        so a surge that offers "one of the following effects" always resolves.
        """
        # Reset per-call so a reused executor never carries a stale selection.
        self._selected_choice = choice
        name = maneuver.get("name", "maneuver")
        result = ManeuverResult(maneuver=name, actor=actor)

        tree = maneuver.get("automation")
        if not tree:
            result.success = False
            result.error = "no automation tree"
            return result

        # Gate on order and resource before anything is rolled.
        blocked = self._blocked_reason(actor, maneuver)
        if blocked:
            result.success = False
            result.error = blocked
            logger.info(f"   ⚡ {actor} cannot use {name}: {blocked}")
            return result

        cost = int((maneuver.get("cost") or {}).get("lashing_dice", 0) or 0)
        if cost and self.dice_pool is not None:
            if not self.dice_pool.spend(actor, cost):
                result.success = False
                result.error = "no lashing dice remaining"
                return result
            result.dice_spent = cost

        logger.info(f"   ⚡ {actor} uses {name}")
        try:
            self._run_nodes(tree, actor, list(targets or []), result)
        except AutomationError as e:
            # A malformed tree is a DATA bug. Report it rather than pretending the
            # maneuver worked; the die is already spent, which is the honest outcome.
            result.success = False
            result.error = str(e)
            logger.error(f"❌ {name} has a malformed automation tree: {e}")
        return result

    # ------------------------------------------------------------------- gating

    def _blocked_reason(self, actor: str, maneuver: Dict[str, Any]) -> str:
        orders = maneuver.get("orders") or []
        if orders:
            order = self._order_of(actor)
            if not order:
                return "not a Radiant"
            if order not in orders:
                return f"{order} cannot use a {'/'.join(orders)} maneuver"
        return ""

    def _affordable(self, actor: str, maneuver: Dict[str, Any]) -> bool:
        cost = int((maneuver.get("cost") or {}).get("lashing_dice", 0) or 0)
        if not cost or self.dice_pool is None:
            return True
        return self.dice_pool.remaining(actor) >= cost

    def _order_of(self, actor: str) -> str:
        entity = self.wrapper.entities.get(actor) if self.wrapper else None
        return str(getattr(entity, "radiant_order", "") or "") if entity else ""

    # -------------------------------------------------------------- interpreter

    def _run_nodes(self, nodes: Sequence[Dict[str, Any]], actor: str,
                   targets: List[str], result: ManeuverResult) -> None:
        for node in nodes or []:
            if not isinstance(node, dict):
                raise AutomationError(f"node is {type(node).__name__}, not an object")
            node_type = node.get("type")
            if node_type not in KNOWN_NODES:
                raise AutomationError(f"unknown node type {node_type!r}")
            getattr(self, f"_node_{node_type}")(node, actor, targets, result)

    def _node_target(self, node, actor, targets, result) -> None:
        """
        `target: "chosen"` — the effects apply to whoever the actor picked.

        With no target chosen the node is a no-op rather than an error: choosing a
        target is the player's job, and a maneuver aimed at nobody should report
        that plainly instead of crashing mid-tree.
        """
        chosen = list(targets)
        if not chosen:
            result.events.append({"type": "target", "targets": [],
                                  "note": "no target chosen"})
            return
        for target in chosen:
            self._run_nodes(node.get("effects") or [], actor, [target], result)

    def _node_save(self, node, actor, targets, result) -> None:
        """A saving throw against the actor's Invested save DC."""
        stat = str(node.get("stat") or "").lower()
        if not stat:
            raise AutomationError("save node has no `stat`")

        dc = self._resolve_dc(node.get("dc"), actor)
        for target in (targets or [None]):
            if target is None:
                continue
            roll = self._roll_save(target, stat)
            passed = roll >= dc
            result.events.append({"type": "save", "target": target, "stat": stat,
                                  "dc": dc, "roll": roll, "passed": passed})
            logger.info(f"      🎲 {target} {stat} save: {roll} vs DC {dc} "
                        f"— {'success' if passed else 'FAIL'}")
            branch = node.get("success" if passed else "fail") or []
            self._run_nodes(branch, actor, [target], result)

    def _node_attack(self, node, actor, targets, result) -> None:
        """
        An attack roll, branching on hit or miss.

        Goes through the engine's own `Attack` action, NOT
        `DnDEngineWrapper.execute_attack()`. That helper had zero callers before this
        interpreter and crashes on any hit — it builds `Dice(num_dice=..., die_value=...)`
        when the engine's fields are `count`/`value`:

            ValidationError: count Field required / value Field required

        It also derives `target_ac = 10 + dex_modifier` by hand, ignoring armour and
        every AC modifier — so cover, Reverse Lashing and Shardplate would all be
        invisible to it. Using the real action keeps maneuver attacks identical to
        every other attack in the game.
        """
        from dnd.actions import Attack
        from dnd.blocks.equipment import WeaponSlot

        attacker = self.wrapper.entities.get(actor) if self.wrapper else None
        for target in (targets or [None]):
            if target is None or attacker is None:
                continue
            defender = self.wrapper.entities.get(target)
            if defender is None:
                continue

            # A reaction attack does not consume the actor's action; the maneuver
            # already charged a lashing die for it.
            attacker.action_economy.reset_all_costs()
            event = Attack(source_entity_uuid=attacker.uuid,
                           target_entity_uuid=defender.uuid,
                           weapon_slot=WeaponSlot.MAIN_HAND).apply(parent_event=None)
            outcome = str(getattr(event, "attack_outcome", "")).rsplit(".", 1)[-1]
            hit = outcome in ("HIT", "CRIT")

            result.events.append({"type": "attack", "target": target, "hit": hit,
                                  "outcome": outcome})
            logger.info(f"      ⚔️  attack on {target}: {outcome or 'no roll'}")
            self._run_nodes(node.get("hit" if hit else "miss") or [],
                            actor, [target], result)

    def _node_damage(self, node, actor, targets, result) -> None:
        """Roll damage and apply it."""
        expression = self._interpolate(str(node.get("damage") or ""), actor)
        amount = self._roll_total(expression)
        damage_type = str(node.get("damage_type") or "bludgeoning")

        for target in (targets or [None]):
            if target is None:
                continue
            dealt = self._apply_damage(target, amount, damage_type)
            result.damage_dealt += dealt
            result.events.append({"type": "damage", "target": target,
                                  "amount": dealt, "damage_type": damage_type,
                                  "expression": expression})
            logger.info(f"      💥 {target} takes {dealt} {damage_type}")

    def _node_roll(self, node, actor, targets, result) -> None:
        """
        Roll dice and report the total under a name.

        Used for bonuses the maneuver grants to something else — an initiative or
        ability-check bonus. Reported rather than applied, because the thing it
        modifies is rolled elsewhere.
        """
        name = str(node.get("name") or "roll")
        expression = self._interpolate(str(node.get("dice") or ""), actor)
        total = self._roll_total(expression)
        result.rolls[name] = result.rolls.get(name, 0) + total
        result.events.append({"type": "roll", "name": name, "total": total,
                              "expression": expression})
        logger.info(f"      🎲 {name}: +{total}")

    def _node_ieffect2(self, node, actor, targets, result) -> None:
        """
        Apply a temporary effect.

        Two shapes in the authored data:
          * a NAMED 5e condition ("Restrained") -> goes through the engine, so it
            composes with everything else that reads conditions.
          * an inline `effects` dict (`{"ac_bonus": "{lashing_die}"}`) for things 5e
            has no condition for -> recorded on the effect, since inventing an
            engine condition per maneuver is what this interpreter exists to avoid.

        Duration is kept VERBATIM. The strings are prose for a human DM ("until you
        stop moving"); parsing them into rounds would invent rules.
        """
        name = str(node.get("name") or "").strip()
        if not name:
            raise AutomationError("ieffect2 node has no `name`")

        duration = str(node.get("duration") or "")
        inline = {key: self._resolve_value(value, actor)
                  for key, value in (node.get("effects") or {}).items()}

        for target in (targets or [actor]):
            applied = False
            if not inline:
                # A bare name is a 5e condition. Only claim it if the engine took it.
                applied = bool(self.wrapper
                               and self.wrapper.apply_condition(target, name,
                                                                source_id=actor))
                if applied:
                    result.conditions_applied.append(f"{target}: {name}")
                    logger.info(f"      🌀 {target} is {name} ({duration})")

            if not applied:
                effect = {"name": name, "target": target, "duration": duration,
                          "effects": inline}
                result.effects_applied.append(effect)
                self._record_effect(target, effect)
                detail = (", ".join(f"{k}={v}" for k, v in inline.items())
                          if inline else name)
                logger.info(f"      🌀 {target}: {name} [{detail}] ({duration})")

            result.events.append({"type": "ieffect2", "target": target,
                                  "name": name, "duration": duration,
                                  "effects": inline, "as_condition": applied})

    # ----------------------------------------------------------------- helpers

    def _record_effect(self, target: str, effect: Dict[str, Any]) -> None:
        """
        Park an inline effect on the combatant's state so the session can see and
        clear it. Combat state is the owner of per-encounter data.
        """
        states = self.combat_state.get("combatant_states")
        if not isinstance(states, dict):
            return
        state = states.setdefault(target, {})
        state.setdefault("maneuver_effects", []).append(effect)

    def _interpolate(self, text: str, actor: str) -> str:
        """
        Replace `{lashing_die}` with the actor's die (e.g. `1d6`).

        An UNKNOWN placeholder raises. Leaving it in place would make the dice
        parser return 0, and a maneuver that silently deals no damage looks like it
        works — the exact class of bug this project keeps finding.
        """
        if not text:
            return text
        die = self.dice_pool.die_size(actor) if self.dice_pool else 4
        text = text.replace(LASHING_DIE, f"1d{die}")

        leftover = _PLACEHOLDER.search(text)
        if leftover:
            raise AutomationError(
                f"unknown placeholder {{{leftover.group(1)}}} — only "
                f"{LASHING_DIE} is supported")
        return text

    def _resolve_value(self, value: Any, actor: str) -> Any:
        """Interpolate inside an inline effect value, leaving non-strings alone."""
        if isinstance(value, str) and "{" in value:
            return self._roll_total(self._interpolate(value, actor))
        return value

    def _roll_total(self, expression: str) -> int:
        """Roll a dice expression like `1d6` or `2d8+3`."""
        if not expression:
            raise AutomationError("empty dice expression")
        outcome = self.dice.damage_roll(expression)
        return int(outcome.get("total_damage", 0))

    def _resolve_dc(self, dc: Any, actor: str) -> int:
        """
        `"invested_save_dc"` -> 8 + proficiency + Investiture ability modifier.

        Computed from the Handbook's own formula via CosmereRules, not hardcoded.
        """
        if isinstance(dc, int):
            return dc
        if str(dc) != "invested_save_dc":
            raise AutomationError(f"unsupported dc {dc!r}")

        entity = self.wrapper.entities.get(actor) if self.wrapper else None
        if entity is None:
            return 10

        proficiency = self._proficiency(entity)
        modifier = self._investiture_modifier(entity)
        if self.rules is not None:
            return int(self.rules.invested_save_dc(proficiency, modifier))
        return 8 + proficiency + modifier

    def _investiture_modifier(self, entity) -> int:
        """
        Windrunner: "highest of Strength or Dexterity" — read from the Handbook
        rather than assumed, since each order names its own ability.
        """
        scores = entity.ability_scores
        order = str(getattr(entity, "radiant_order", "") or "")
        spec = ""
        if self.rules is not None:
            order_data = self.rules.order(order) or {}
            spec = str(order_data.get("investiture_ability") or "")

        names = re.findall(r"strength|dexterity|constitution|intelligence|wisdom"
                           r"|charisma", spec.lower())
        if not names:
            names = ["strength", "dexterity"]
        return max(getattr(scores, n).modifier for n in names)

    @staticmethod
    def _proficiency(entity) -> int:
        value = getattr(entity, "proficiency_bonus", None)
        if value is None:
            return 2
        return int(getattr(value, "score", value) or 2)

    def _roll_save(self, target: str, stat: str) -> int:
        entity = self.wrapper.entities.get(target) if self.wrapper else None
        if entity is None:
            return 0
        save = entity.saving_throws.get_saving_throw(stat)
        bonus = int(getattr(save.bonus, "score", 0) or 0)
        modifier = getattr(entity.ability_scores, stat).modifier
        outcome = self.dice.saving_throw(stat, modifier, proficiency=bonus)
        return int(outcome.get("total", 0))

    def _apply_damage(self, target: str, amount: int, damage_type: str) -> int:
        from dnd.core.modifiers import DamageType

        entity = self.wrapper.entities.get(target) if self.wrapper else None
        if entity is None or amount <= 0:
            return 0
        try:
            resolved = DamageType(damage_type.capitalize())
        except ValueError:
            resolved = DamageType.BLUDGEONING
        dealt = int(entity.health.take_damage(amount, resolved, entity.uuid))

        # Concentration check: DC = max(10, damage/2), CON save (PHB 203)
        if dealt > 0 and self.concentration is not None:
            concentrating_on = self.concentration.concentrating_on(target)
            if concentrating_on:
                dc = max(10, dealt // 2)
                save_total = self._roll_save(target, "constitution")
                success = save_total >= dc
                logger.info(f"      🧠 {target} takes damage while concentrating on "
                           f"{concentrating_on}: CON save {save_total} vs DC {dc} "
                           f"— {'maintains' if success else 'loses'} concentration")
                if not success:
                    self.concentration.stop(target)

        return dealt

    # --------------------------------------------------------- new nodes (plan 2.9)
    # NOTE: 'heal' is in SpellEffectExecutor, not here, to preserve the test
    # contract that spell nodes are additions to maneuver nodes.

    def _node_area_of_effect(self, node, actor, targets, result) -> None:
        """
        Expand a single chosen target to all entities inside an area (Invested Arts addition).

        The grid already computes distance and FOV. This node queries it for everyone
        inside the shape (sphere/cone/cube/line) and runs the child effects on each.
        """
        shape = str(node.get("shape") or "").lower()  # sphere, cone, cube, line
        size = int(node.get("size", 0) or 0)  # radius/length in feet

        if not shape or size <= 0:
            raise AutomationError(
                f"area_of_effect node needs shape and size (got {shape!r}, {size})")

        # For now, use the first chosen target as the center/origin
        center = targets[0] if targets else actor
        affected = self._get_entities_in_area(center, shape, size)

        result.events.append({"type": "area_of_effect", "shape": shape,
                              "size": size, "center": center,
                              "affected": affected})
        logger.info(f"      🌊 AoE {shape} ({size}ft) affects {len(affected)} entities")

        self._run_nodes(node.get("effects") or [], actor, affected, result)

    def _get_entities_in_area(self, center: str, shape: str, size: int) -> List[str]:
        """
        Query the tactical grid for entities inside an area.

        For now, return everyone within `size` feet of `center` as a sphere approximation.
        The shape parameter is recorded but all shapes use distance for now.
        """
        center_entity = self.wrapper.entities.get(center) if self.wrapper else None
        if center_entity is None or not hasattr(center_entity, "position"):
            return []

        center_pos = center_entity.position
        all_entities = list(self.wrapper.entities.keys())
        affected = []

        for entity_id in all_entities:
            entity = self.wrapper.entities.get(entity_id)
            if entity is None or not hasattr(entity, "position"):
                continue
            # Simple Euclidean distance in feet (assuming 5ft grid squares)
            dx = (entity.position[0] - center_pos[0]) * 5
            dy = (entity.position[1] - center_pos[1]) * 5
            distance = int((dx ** 2 + dy ** 2) ** 0.5)
            if distance <= size:
                affected.append(entity_id)

        return affected

    def _node_check(self, node, actor, targets, result) -> None:
        """
        Ability check vs DC (Invested Arts addition).

        Used by Dispel/Counter-Invest mechanics that check ability vs a level-derived DC.
        """
        stat = str(node.get("stat") or "").lower()
        if not stat:
            raise AutomationError("check node has no `stat`")

        dc = self._resolve_dc(node.get("dc"), actor)

        for target in (targets or [actor]):
            roll = self._roll_check(target, stat)
            passed = roll >= dc

            result.events.append({"type": "check", "target": target, "stat": stat,
                                  "dc": dc, "roll": roll, "passed": passed})
            logger.info(f"      🎲 {target} {stat} check: {roll} vs DC {dc} "
                        f"— {'success' if passed else 'FAIL'}")

            branch = node.get("success" if passed else "fail") or []
            self._run_nodes(branch, actor, [target], result)

    def _roll_check(self, target: str, stat: str) -> int:
        """Roll an ability check (d20 + modifier + proficiency if applicable)."""
        entity = self.wrapper.entities.get(target) if self.wrapper else None
        if entity is None:
            return 0

        modifier = getattr(entity.ability_scores, stat).modifier
        # For now, assume no proficiency on raw ability checks
        # (skill checks would need the skill proficiency lookup)
        outcome = self.dice.ability_check(modifier, proficiency=0)
        return int(outcome.get("total", 0))

    def _node_resistance(self, node, actor, targets, result) -> None:
        """
        Grant damage resistance (Invested Arts addition).

        Now fully wired: applies ResistanceModifier to the entity's
        health.damage_reduction so damage is actually halved, following the same
        pattern class_features._effect_resistance uses for Rage.
        """
        from dnd.core.modifiers import DamageType, ResistanceModifier, ResistanceStatus

        damage_type = str(node.get("damage_type") or "").lower()
        if not damage_type:
            raise AutomationError("resistance node has no `damage_type`")

        duration = str(node.get("duration") or "")

        for target in (targets or [actor]):
            # Record as an inline effect so the session can see it
            effect = {
                "name": f"Resistance to {damage_type}",
                "target": target,
                "duration": duration,
                "effects": {"resistance": damage_type}
            }
            result.effects_applied.append(effect)
            self._record_effect(target, effect)

            # WIRE TO ENGINE: actually grant the resistance
            entity = self.wrapper.entities.get(target) if self.wrapper else None
            if entity is not None:
                dtype = _parse_damage_type_for_resistance(damage_type)
                if dtype is not None:
                    modifier = ResistanceModifier(
                        name=f"Resistance to {dtype.value}",
                        value=ResistanceStatus.RESISTANCE,
                        damage_type=dtype,
                        source_entity_uuid=entity.uuid,
                        target_entity_uuid=entity.uuid
                    )
                    reduction = entity.health.damage_reduction
                    modifier_id = reduction.self_static.add_resistance_modifier(modifier)
                    # Track for teardown
                    self._applied_resistances.setdefault(target, []).append(
                        (reduction, modifier_id))
                    logger.info(f"      🛡️  {target} gains resistance to {damage_type} "
                               f"({duration}) — damage halved")
                else:
                    logger.warning(f"      ⚠️  Unknown damage type {damage_type!r}, "
                                 f"resistance recorded but not applied to engine")

            result.events.append({"type": "resistance", "target": target,
                                  "damage_type": damage_type, "duration": duration})

    # ------------------------------------------------- surge cantrip nodes (surge-complete)

    def _node_utility(self, node, actor, targets, result) -> None:
        """
        A cantrip effect with no combat mechanic — kindle a fire, recolor eyes,
        reshape stone, see hazily into the Cognitive Realm.

        It SUCCEEDS and records a narration string. That is the whole point: a
        purely narrative surge effect is RESOLVABLE (it happens, the DM narrates
        it), not `needs_adjudication`. No dice, no target math, no invented rules.
        """
        narration = str(node.get("narration") or node.get("description") or "")
        result.narrations.append(narration)
        result.events.append({"type": "utility", "narration": narration,
                              "targets": list(targets or [])})
        logger.info(f"      ✨ {narration}" if narration else "      ✨ utility effect")

    def _node_forced_move(self, node, actor, targets, result) -> None:
        """
        Move a target a fixed distance (a Gravitation creature-Lash on a hit, an
        Abrasion slide of the caster's own body).

        The distance and direction are RECORDED as an event and an applied effect
        for the session to enact — exactly the convention the reviewed Lash Enemy
        and Lash Ally maneuvers already use for `forced_move_ft`. The combat grid
        is a fixed two-row line (see combat_action_resolver on `move`), so
        physically relocating an entity here would invent map positions that do
        not exist; recording the movement is the honest, composable outcome.
        """
        distance = int(node.get("distance_ft", 0) or 0)
        if distance <= 0:
            raise AutomationError("forced_move node needs a positive distance_ft")
        direction = str(node.get("direction") or "a direction the caster chooses")

        for target in (targets or [actor]):
            effect = {"name": "Forced Movement", "target": target,
                      "duration": "instant",
                      "effects": {"forced_move_ft": distance, "direction": direction}}
            result.effects_applied.append(effect)
            self._record_effect(target, effect)
            result.events.append({"type": "forced_move", "target": target,
                                  "distance_ft": distance, "direction": direction})
            logger.info(f"      💨 {target} is Lashed {distance} ft ({direction})")

    def _node_choice(self, node, actor, targets, result) -> None:
        """
        "Choose one of the following effects."

        Most surge cantrips list 2-4 discrete effects and the caster picks one.
        The selection comes from `execute(..., choice=<id>)`; with none supplied,
        the option flagged `"default": true` runs, else the first. The chosen
        option's `effects` subtree is then executed like any other node list, so a
        choice can wrap a mechanical branch (attack + forced_move) or a utility one.
        """
        options = node.get("options") or []
        if not options:
            raise AutomationError("choice node has no options")

        sel = self._selected_choice
        chosen = None
        if sel is not None:
            for opt in options:
                if str(opt.get("id")) == str(sel) or str(opt.get("label")) == str(sel):
                    chosen = opt
                    break
            if chosen is None and isinstance(sel, int) and 0 <= sel < len(options):
                chosen = options[sel]
        if chosen is None:
            chosen = next((o for o in options if o.get("default")), options[0])

        label = chosen.get("id") or chosen.get("label") or "option"
        result.events.append({"type": "choice", "selected": chosen.get("id"),
                              "label": chosen.get("label", "")})
        logger.info(f"      🔀 chose '{label}'")
        self._run_nodes(chosen.get("effects") or [], actor, list(targets or []),
                        result)

    # ------------------------------------------------------------------ teardown

    def clear_all(self) -> None:
        """
        Remove all engine resistances granted by maneuver resistance nodes.

        MUST run at end of combat. Resistances live on the Entity, which outlives
        the encounter, so a resistance granted in one fight would otherwise persist
        for every fight afterwards (matching the class_features teardown pattern).
        """
        for target, modifiers in list(self._applied_resistances.items()):
            for reduction, modifier_id in modifiers:
                try:
                    reduction.self_static.remove_resistance_modifier(modifier_id)
                except Exception as e:
                    logger.debug(f"   Could not remove resistance from {target}: {e}")
        self._applied_resistances.clear()
        logger.info("   ⏹️  Cleared all maneuver resistances")
