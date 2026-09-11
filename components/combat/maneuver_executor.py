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
from typing import Any, Dict, List, Optional, Sequence

from config.logging_config import get_logger

logger = get_logger(__name__)

# The six node types the authored data actually uses. An unrecognised type is an
# error, not something to skip: silently ignoring a node would execute half a
# maneuver and report success.
KNOWN_NODES = frozenset({"target", "save", "damage", "attack", "roll", "ieffect2"})

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
                 dice_roller=None, combat_state=None):
        self.wrapper = dnd_wrapper
        self.dice_pool = dice_pool
        self.rules = cosmere_rules
        self.combat_state = combat_state or {}

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
                targets: Optional[Sequence[str]] = None) -> ManeuverResult:
        """
        Run one maneuver.

        `targets` is who the actor chose; a `target` node uses them. Spends the
        resource FIRST and refunds nothing on a miss — 5e expends the die on use.
        """
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
        return int(entity.health.take_damage(amount, resolved, entity.uuid))
