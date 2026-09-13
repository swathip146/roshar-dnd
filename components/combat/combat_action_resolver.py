"""
Combat Action Resolver - Unified Action Resolution

Dispatches combat actions to appropriate handlers:
- D&D 5e actions via dnd_engine native implementations
- Roshar-specific actions via custom Action classes
- Both integrate seamlessly via dnd_engine's event system

Based on: COMBAT_ENGINE_IMPLEMENTATION_PLAN.md Phase 3
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional
from uuid import UUID
import json

# Add dnd_engine to path (required for dnd imports)
dnd_engine_path = Path(__file__).parent.parent.parent / "external" / "dnd_engine"
if str(dnd_engine_path) not in sys.path:
    sys.path.insert(0, str(dnd_engine_path))

from dnd.actions import Attack, WeaponSlot, AttackEvent
from dnd.core.dice import AttackOutcome
from dnd.core.modifiers import DamageType

from components.combat.action_registry import ACTION_REGISTRY, param_defaults
from components.combat.roshar_actions import (
    LashingEvent,
    ShardbladeAttackEvent,
    ProgressionHealingEvent
)
from config.logging_config import get_logger

logger = get_logger(__name__)


class CombatActionResolver:
    """
    Unified action resolver: dnd_engine foundation + Roshar extensions.

    **Design Philosophy:**
    - D&D 5e actions → Use dnd_engine native Actions
    - Roshar abilities → Custom Actions following dnd_engine patterns
    - Both types integrate seamlessly via event system
    - ACTION_REGISTRY is external for modular expansion

    **Action Registry:**
    - Minimal initial registry (7 core actions) - Phase 3
    - Expanded post-Phase 3 with full Surge abilities (~30+ actions)
    - See: components/combat/action_registry.py and docs/ROSHAR_COMBAT_MECHANICS_INTEGRATION.md
    """

    def __init__(self, dnd_engine_wrapper, character_manager, combat_state):
        """
        Initialize Combat Action Resolver.

        Args:
            dnd_engine_wrapper: DnDEngineWrapper instance for entity access
            character_manager: CharacterManager instance for character data
            combat_state: Current combat state dict
        """
        self.dnd_wrapper = dnd_engine_wrapper
        self.character_manager = character_manager
        self.combat_state = combat_state
        self.logger = get_logger(__name__)
        self.ACTION_REGISTRY = ACTION_REGISTRY  # Expose for CombatSessionManager
        # Built lazily: constructing it loads the 319-spell SRD dataset, and every
        # test that builds a resolver should not pay for that unless it casts.
        self._spellcasting = None

    @property
    def spellcasting(self):
        """
        The SpellcastingService for this encounter (5e spells).

        Lives on the resolver rather than being constructed per cast so slot
        spending and concentration persist across a fight — a per-call service
        would forget that the wizard is already concentrating on Bless.
        """
        if self._spellcasting is None:
            from components.combat.spellcasting import SpellcastingService

            self._spellcasting = SpellcastingService(
                dnd_engine_wrapper=self.dnd_wrapper,
                character_manager=self.character_manager,
                combat_state=self.combat_state)
        return self._spellcasting

    @property
    def investiture_ledger(self):
        """
        The Investiture Point ledger for this encounter (Cosmere arts).

        Lives on the resolver (same pattern as spellcasting) so IP spending
        persists across the fight.
        """
        if not hasattr(self, '_investiture_ledger'):
            from components.combat.investiture_ledger import InvestiturePointLedger
            from components.cosmere_rules import CosmereRules

            rules = CosmereRules()
            self._investiture_ledger = InvestiturePointLedger(
                character_manager=self.character_manager,
                cosmere_rules=rules)
        return self._investiture_ledger

    def _cast_spell(self, action: Dict[str, Any],
                    metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve `cast_spell` through SpellcastingService.

        `spell_name` and `at_level` come from the caller if given, otherwise from
        the registry's `param_defaults` (both None), which the service reads as
        "pick a spell this caster knows and can pay for, using the cheapest legal
        slot". That default is what makes `cast_spell` OFFERABLE at all — an
        action needing a parameter nothing supplies is filtered out of both menus.
        """
        defaults = param_defaults(action["action_type"])
        spell_name = action.get("spell_name", defaults.get("spell_name"))
        at_level = action.get("at_level", defaults.get("at_level"))

        target = action.get("target")
        targets = [target] if target else []

        result = self.spellcasting.cast(action["actor"], spell_name=spell_name,
                                        targets=targets, at_level=at_level)
        payload = result.as_dict()
        # `attempted` tells resolve_action whether to charge the action economy: a
        # cast that reached the executor spent its slot and its action, a refusal
        # spent neither.
        payload["attempted"] = bool(result.slot_level) or result.success
        payload["event"] = None
        if target:
            entity = self.dnd_wrapper.entities.get(target)
            if entity is not None:
                self._sync_hp_to_combat_state(entity.uuid)
        return payload

    def _cast_art(self, action: Dict[str, Any],
                  metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve `cast_art` through Investiture Point ledger and executor (plan 2.9).

        Mirrors `_cast_spell` but:
          - Uses InvestiturePointLedger instead of spell slots
          - Gets arts from CosmereRules.get_art()
          - Compiles via compile_art()

        `art_name` comes from the caller if given, otherwise from param_defaults
        (None), meaning "pick any art the actor knows and can afford."
        """
        from components.combat.spell_compiler import compile_art
        from components.cosmere_rules import CosmereRules

        defaults = param_defaults(action["action_type"])
        art_name = action.get("art_name", defaults.get("art_name"))
        actor_id = action["actor"]

        # Get character data to determine order
        character = self.character_manager.characters.get(actor_id)
        if character is None:
            return {
                "success": False,
                "attempted": False,
                "error": f"Unknown character {actor_id}",
                "event": None,
            }

        order = getattr(character, "radiant_order", "")

        # If no art specified, refuse for now (auto-selection logic can be added later)
        if not art_name:
            return {
                "success": False,
                "attempted": False,
                "error": "No art specified",
                "event": None,
            }

        # Load the art from rules
        rules = CosmereRules()
        art = rules.get_art(art_name)
        if art is None:
            self.logger.warning(f"   ❌ Art '{art_name}' not found in rules data")
            return {
                "success": False,
                "attempted": False,
                "error": f"Unknown art: {art_name}",
                "event": None,
            }

        # Compile the art
        art_level = int(art.get("level", 0) or 0)
        compiled = compile_art(art, art_level=art_level)

        # Check if it needs adjudication
        if compiled.needs_adjudication:
            self.logger.info(f"   ⚖️  {art_name} needs adjudication: {compiled.reason}")
            return {
                "success": False,
                "attempted": False,
                "error": f"Art needs adjudication: {compiled.reason}",
                "event": None,
            }

        # Pay the IP cost
        spend_result = self.investiture_ledger.spend(actor_id, art_level, order)
        if not spend_result.spent:
            self.logger.info(f"   ⛔ Cannot cast {art_name}: {spend_result.reason}")
            return {
                "success": False,
                "attempted": False,
                "error": spend_result.reason,
                "event": None,
            }

        # Execute the art through the maneuver executor
        try:
            from components.combat.maneuver_executor import ManeuverExecutor

            target = action.get("target")
            targets = [target] if target else []

            executor = ManeuverExecutor(
                dnd_wrapper=self.dnd_wrapper,
                character_manager=self.character_manager,
                combat_state=self.combat_state)

            # Execute the automation tree
            exec_result = executor.execute(
                actor_id=actor_id,
                automation=compiled.automation,
                targets=targets)

            # Sync HP if there was a target
            if target:
                entity = self.dnd_wrapper.entities.get(target)
                if entity is not None:
                    self._sync_hp_to_combat_state(entity.uuid)

            return {
                "success": exec_result.get("success", False),
                "attempted": True,
                "event": None,
                "description": exec_result.get("description", f"Cast {art_name}"),
                "art_name": art_name,
                "art_level": art_level,
                "ip_spent": spend_result.cost,
                "ip_remaining": spend_result.remaining,
            }

        except Exception as e:
            # Refund the IP if execution failed
            self.investiture_ledger.restore(actor_id, spend_result.cost)
            self.logger.error(f"❌ Art execution failed: {e}", exc_info=True)
            return {
                "success": False,
                "attempted": False,
                "error": str(e),
                "event": None,
            }

    def _use_class_feature(self, action: Dict[str, Any],
                           metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve activated class features (Rage, Second Wind, Action Surge).

        Delegates to ClassFeatureEngine.use(), which:
          - Checks if the actor has the feature and has uses remaining
          - Spends the use and applies effects (heal, grant-action, melee-damage-bonus)
          - Manages the lifecycle (tick_round, clear_all)
        """
        actor_id = action["actor"]
        feature_id = metadata.get("feature_id")

        if not feature_id:
            return {
                "success": False,
                "attempted": False,
                "error": "No feature_id in metadata",
                "event": None,
            }

        # Get the ClassFeatureEngine from the wrapper
        engine = self.dnd_wrapper.class_feature_engine(
            combat_state=self.combat_state)

        # Use the feature
        result = engine.use(actor_id, feature_id)

        # Convert FeatureResult to resolver format
        return {
            "success": result.success,
            "attempted": True,  # Always attempted if we got this far
            "error": result.error if not result.success else None,
            "event": None,
            "description": (
                f"{result.actor} uses {result.feature}" if result.success
                else f"{result.actor} cannot use {result.feature}: {result.error}"
            ),
            "healed": result.healed,
            "events": result.events,
            "uses_remaining": result.uses_remaining,
        }

    def resolve_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Unified action resolution for D&D + Roshar.

        Args:
            action: {
                "actor": "char_id",
                "action_type": "attack" | "lashing" | "progression_healing",
                "target": "target_char_id",  # Optional
                ...params
            }

        Returns:
            {
                "success": True,
                "event": AttackEvent | LashingEvent | ...,
                "description": "Human-readable result"
            }
        """
        action_type = action["action_type"]

        # Lookup in external registry
        if action_type not in ACTION_REGISTRY:
            self.logger.error(f"Unknown action type: {action_type}")
            return {
                "success": False,
                "error": f"Unknown action: {action_type}"
            }

        # An unknown actor/target must not crash the combat loop. Unknown
        # action_type already returned a graceful error dict (above), but an
        # unknown character raised ValueError out of _get_entity_uuid() and
        # took the whole encounter with it. Validate up front, symmetrically.
        actor_id = action.get("actor")
        if actor_id not in self.dnd_wrapper.entities:
            self.logger.error(f"Unknown actor: {actor_id}")
            return {
                "success": False,
                "error": f"Entity not found for character {actor_id}",
            }

        target_id = action.get("target")
        if target_id is not None and target_id not in self.dnd_wrapper.entities:
            self.logger.error(f"Unknown target: {target_id}")
            return {
                "success": False,
                "error": f"Entity not found for character {target_id}",
            }

        metadata = ACTION_REGISTRY[action_type]

        # Dispatch based on type
        if metadata["type"] in ["dnd_action", "roshar_action", "roshar_equipment"]:
            # Costed Invested Arts (plan 2.9 economy): a surge marked with
            # `art_level` is paid in Investiture Points. Spend through the ledger
            # BEFORE executing (so an empty pool refuses the action without eating
            # the turn), and refund if the action then cancels or is refused.
            art_level = metadata.get("art_level")
            spend = None
            if art_level:
                character = self.character_manager.characters.get(actor_id)
                order = getattr(character, "radiant_order", "") if character else ""
                spend = self.investiture_ledger.spend(
                    actor_id, int(art_level), order or "")
                if not spend.spent:
                    self.logger.info(
                        f"   ⛔ {action_type} refused: {spend.reason}")
                    return {
                        "success": False, "attempted": False, "refused": True,
                        "event": None, "error": spend.reason,
                        "description": (f"{actor_id} cannot use {action_type}: "
                                        f"{spend.reason}"),
                    }

            result = self._execute_action(action, metadata)

            if spend is not None and spend.spent:
                event = result.get("event")
                declined = (result.get("refused") is True
                            or event is None
                            or getattr(event, "canceled", False))
                if declined:
                    self.investiture_ledger.restore(actor_id, spend.cost)
                    self.logger.debug(
                        f"   ↩️  refunded {spend.cost} IP to {actor_id} "
                        f"(action did not take effect)")
                else:
                    result["ip_spent"] = spend.cost
                    result["ip_remaining"] = spend.remaining

            self._consume_action_cost(actor_id, metadata)
            return result
        elif metadata["type"] == "spell_action":
            result = self._cast_spell(action, metadata)
            # Only charge the action if the spell was actually attempted. A
            # refusal (no slot, not a caster, needs adjudication) must not eat the
            # turn: `progression_healing` used to be offered and refused every
            # round, and the actor silently lost its action each time.
            if result.get("success") or result.get("attempted"):
                self._consume_action_cost(actor_id, metadata)
            return result
        elif metadata["type"] == "art_action":
            result = self._cast_art(action, metadata)
            # Same attempted-before-charging logic as spell_action
            if result.get("success") or result.get("attempted"):
                self._consume_action_cost(actor_id, metadata)
            return result
        elif metadata["type"] in ["dnd_condition", "roshar_condition"]:
            result = self._apply_condition(action, metadata)
            self._consume_action_cost(actor_id, metadata)
            return result
        elif metadata["type"] == "class_feature":
            result = self._use_class_feature(action, metadata)
            # Only charge the action economy if the feature was actually used
            if result.get("success") or result.get("attempted"):
                self._consume_action_cost(actor_id, metadata)
            return result
        else:
            return {
                "success": False,
                "error": f"Invalid action type metadata: {metadata['type']}"
            }

    def _consume_action_cost(self, actor_id: str, metadata: Dict) -> None:
        """
        Spend the actor's action economy for the action just taken.

        NOTHING did this before, so `has_actions` stayed True forever: in a live
        combat every actor took four actions and was then cut off by the session
        manager's stall-breaker ("still has actions after 4 attempts and its
        economy is not decreasing — forcing turn advance"). Three enemies each
        attacked four times per round instead of once.

        The cost is declared per action in ACTION_REGISTRY (cost_type/cost), so
        this reads it rather than assuming one action per turn — bonus actions and
        movement-cost actions stay correct.
        """
        cost = metadata.get("cost")
        cost_type = metadata.get("cost_type")
        if not cost or not cost_type:
            return

        entity = self.dnd_wrapper.entities.get(actor_id)
        economy = getattr(entity, "action_economy", None)
        if economy is None:
            return

        # Some dnd_engine actions (Attack among them) already debit the economy
        # themselves. Only pay it here if the pool still has the cost available,
        # otherwise a second consume raises "Not enough actions to consume".
        try:
            pool = getattr(economy, cost_type, None)
            available = getattr(pool, "normalized_score", None)
            if available is not None and available < int(cost):
                self.logger.debug(
                    f"   ⏳ {actor_id}: {cost_type} already spent by the action")
                return
        except Exception:
            pass

        try:
            economy.consume(cost_type, int(cost),
                            cost_name=metadata.get("description", "action"))
            self.logger.debug(f"   ⏳ {actor_id} spent {cost} {cost_type}")
        except Exception as e:
            # Never let accounting break a resolved action; the stall-breaker
            # remains as a backstop.
            self.logger.warning(f"⚠️ Could not consume {cost_type} for "
                                f"{actor_id}: {e}")

    def _execute_action(self, action: Dict, metadata: Dict) -> Dict:
        """
        Execute Action (D&D or Roshar) via dnd_engine event system.

        Uses: dnd_wrapper.execute_dnd_action(action_class, **kwargs)
        """
        action_class = metadata["action_class"]
        actor_uuid = self._get_entity_uuid(action["actor"])

        # Build action parameters
        kwargs = {
            "source_entity_uuid": actor_uuid
        }

        # Add target if present
        if "target" in action and action["target"]:
            kwargs["target_entity_uuid"] = self._get_entity_uuid(action["target"])

        # Add additional parameters from metadata
        #
        # A param with a registry default is filled in here rather than refused. The
        # four Surges each declared one flavour parameter that NOTHING in the game
        # ever supplied — `lashing_type`, `illusion_type`, `target_essence`,
        # `healing_amount` — so a Windrunner could never actually choose to Lash. The
        # action classes already had sensible defaults; nothing passed them through.
        defaults = param_defaults(action["action_type"])
        missing_required = []
        for param in metadata.get("params", []):
            if param == "target_entity_uuid":
                continue  # Already handled above
            elif param in action:
                kwargs[param] = action[param]
            elif param == "weapon_slot":
                # Default to main hand
                kwargs[param] = WeaponSlot.MAIN_HAND
            elif param in defaults:
                kwargs[param] = defaults[param]
            else:
                missing_required.append(param)

        # A declared parameter nobody supplies is a REFUSAL, not a crash.
        #
        # `move` declares `end_position`, and nothing in the menu or the NPC AI
        # ever provides one — tactical movement is not implemented (the combat grid
        # is a fixed two-row line). So every attempt raised
        # "1 validation error for Move: end_position Field required", four times in
        # one live encounter, logged as "Action execution failed" while the actor
        # silently lost its turn. Refusing states the reason and keeps the fight
        # moving.
        if missing_required:
            self.logger.info(
                f"   ⛔ {action.get('action_type')} needs "
                f"{', '.join(missing_required)}, which was not supplied "
                f"(not implemented for this action yet)")
            return {
                "success": False,
                "event": None,
                "refused": True,
                "description": (
                    f"{action.get('actor', 'The actor')} cannot "
                    f"{action.get('action_type', 'act')} right now — "
                    f"that action needs {', '.join(missing_required)}."),
            }

        # Execute via dnd_engine
        try:
            # Check for on-hit class features BEFORE the attack (Sneak Attack, Divine Smite)
            # These arm extra damage that will be included in the attack's damage rolls
            if metadata.get("type") == "dnd_action" and "Attack" in action_class.__name__:
                actor_id = action.get("actor", "")
                target_id = action.get("target", "")
                if actor_id and target_id:
                    try:
                        class_feat_engine = self.dnd_wrapper.class_feature_engine()
                        features = class_feat_engine.on_hit_features(actor_id, target_id)
                        for feature_entry in features:
                            feature_id = feature_entry.get("id", "")
                            if feature_id:
                                result = class_feat_engine.use(actor_id, feature_id, target_id)
                                if result.success:
                                    self.logger.debug(
                                        f"   ⚔️ Armed {feature_entry.get('name', feature_id)} "
                                        f"for {actor_id}'s attack"
                                    )
                    except Exception as e:
                        self.logger.warning(f"⚠️ Failed to arm on-hit features: {e}")

            # Instantiate and apply action
            action_instance = action_class(**kwargs)
            event = action_instance.apply()

            # apply() returns None when the engine REFUSES the action — most
            # often because the actor has no action left in its economy. A live
            # combat hit this on every second attack once the economy was
            # actually being consumed, and the bare `event.canceled` raised
            # AttributeError: 'NoneType' object has no attribute 'canceled',
            # which the caller reported as "Action execution failed" while the
            # narrator cheerfully described the swing anyway.
            if event is None:
                # Read from `action`: _execute_action receives the action DICT,
                # not the unpacked names that resolve_action has in scope. My
                # first version referenced action_type/actor_id directly and
                # raised NameError on every refusal, turning a clean "no action
                # left" into a traceback.
                refused_type = action.get("action_type", "that action")
                refused_actor = action.get("actor", "the actor")
                self.logger.info(
                    f"   ⛔ {refused_type} refused for {refused_actor} "
                    f"(no action available, or the engine declined it)")
                return {
                    "success": False,
                    "event": None,
                    "refused": True,
                    "description": (f"{refused_actor} cannot {refused_type} "
                                    f"right now — no action remaining this turn."),
                }

            # Check if action succeeded
            success = not event.canceled

            # Extract results based on action type
            if isinstance(event, AttackEvent):
                # For an ATTACK, "success" must mean IT HIT — not merely that the
                # event was not cancelled. A miss is a perfectly valid,
                # non-cancelled event, so `not event.canceled` was True for every
                # attack ever resolved.
                #
                # Both consumers read this field: the narrator prints "Hit!" or
                # "Miss!" from it, and the LLM prompt states "Success: {success}".
                # So every attack was reported to the model as a success while
                # damage was applied correctly underneath — 13 attacks across 5
                # live rounds all narrated as misses with nobody losing HP.
                outcome = getattr(event, "attack_outcome", None)
                hit = outcome in (AttackOutcome.HIT, AttackOutcome.CRIT)

                result = {
                    "success": hit,
                    "event": event,
                    "attack_outcome": outcome,
                    "damage": sum(roll.total for roll in event.damage_rolls) if hasattr(event, 'damage_rolls') and event.damage_rolls else 0,
                    "critical": event.attack_outcome == AttackOutcome.CRIT if hasattr(event, 'attack_outcome') else False,
                    "description": self._format_attack_result(event)
                }
            elif isinstance(event, LashingEvent):
                result = {
                    "success": success,
                    "event": event,
                    "lashing_type": event.lashing_type if hasattr(event, 'lashing_type') else None,
                    "stormlight_consumed": event.stormlight_cost if hasattr(event, 'stormlight_cost') else 0,
                    "description": f"Lashing applied" if success else event.status_message
                }
            elif isinstance(event, ShardbladeAttackEvent):
                result = {
                    "success": success,
                    "event": event,
                    "soul_damage": event.soul_damage if hasattr(event, 'soul_damage') else 0,
                    "description": f"Shardblade dealt {event.soul_damage} soul damage" if success and hasattr(event, 'soul_damage') else event.status_message
                }
            elif isinstance(event, ProgressionHealingEvent):
                result = {
                    "success": success,
                    "event": event,
                    "healing_amount": event.healing_amount if hasattr(event, 'healing_amount') else 0,
                    "description": f"Healed {event.healing_amount} HP" if success and hasattr(event, 'healing_amount') else event.status_message
                }
            else:
                # Generic result
                result = {
                    "success": success,
                    "event": event,
                    "description": event.status_message if hasattr(event, 'status_message') else "Action executed"
                }

            # Update combat state HP if damage dealt or healing applied
            if hasattr(event, 'target_entity_uuid') and event.target_entity_uuid:
                self._sync_hp_to_combat_state(event.target_entity_uuid)

            return result

        except Exception as e:
            self.logger.error(f"Action execution failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def _apply_condition(self, action: Dict, metadata: Dict) -> Dict:
        """Apply Condition (D&D or Roshar) via dnd_engine condition system"""
        condition_class = metadata["condition_class"]
        actor_uuid = self._get_entity_uuid(action["actor"])

        # Build condition parameters
        kwargs = {
            "source_entity_uuid": actor_uuid,
            "target_entity_uuid": actor_uuid  # Most conditions target self
        }

        # Add duration if specified in metadata
        if metadata.get("duration"):
            kwargs["duration"] = metadata["duration"]

        # Add custom parameters
        for param in metadata.get("params", []):
            if param in action:
                kwargs[param] = action[param]

        # Apply via dnd_engine
        try:
            condition = condition_class(**kwargs)
            event = condition.apply()

            success = not event.canceled if hasattr(event, 'canceled') else True

            return {
                "success": success,
                "event": event,
                "condition": condition_class.__name__,
                "description": metadata.get("description", "Condition applied")
            }

        except Exception as e:
            self.logger.error(f"Condition application failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def _get_entity_uuid(self, char_id: str) -> UUID:
        """
        Get dnd_engine entity UUID from character ID.

        Args:
            char_id: Character ID

        Returns:
            Entity UUID

        Raises:
            ValueError: If entity not found for character
        """
        entity = self.dnd_wrapper.entities.get(char_id)
        if entity:
            return entity.uuid
        else:
            raise ValueError(f"Entity not found for character {char_id}")

    def _sync_hp_to_combat_state(self, target_uuid: UUID):
        """
        Sync HP from dnd_engine entity to combat state.

        Args:
            target_uuid: Target entity UUID
        """
        # Safety check: combat_state might not have combatant_states key
        if not self.combat_state or "combatant_states" not in self.combat_state:
            self.logger.warning("Combat state missing 'combatant_states', skipping HP sync")
            return

        # Find character by UUID
        for char_id, entity in self.dnd_wrapper.entities.items():
            if entity.uuid == target_uuid:
                char = self.character_manager.characters.get(char_id)
                if char and char_id in self.combat_state["combatant_states"]:
                    # Sync current HP from entity to combat state
                    con_mod = entity.ability_scores.constitution.modifier
                    current_hp = entity.health.get_total_hit_points(con_mod)
                    # Must include max_hit_points_bonus (plan 1.7)
                    max_hp = self.dnd_wrapper.get_entity_max_hp(entity)

                    self.combat_state["combatant_states"][char_id]["hp_current"] = current_hp
                    self.combat_state["combatant_states"][char_id]["hp_max"] = max_hp

                    self.logger.debug(f"Synced HP for {char_id}: {current_hp}/{max_hp}")
                break

    def _format_attack_result(self, event: AttackEvent) -> str:
        """
        Format attack event into human-readable description.

        Args:
            event: AttackEvent from dnd_engine

        Returns:
            Human-readable description string
        """
        if not hasattr(event, 'attack_outcome'):
            return event.status_message if hasattr(event, 'status_message') else "Attack executed"

        if event.attack_outcome == AttackOutcome.HIT:
            damage = sum(roll.total for roll in event.damage_rolls) if hasattr(event, 'damage_rolls') and event.damage_rolls else 0
            return f"Hit! Dealt {damage} damage."
        elif event.attack_outcome == AttackOutcome.CRIT:
            damage = sum(roll.total for roll in event.damage_rolls) if hasattr(event, 'damage_rolls') and event.damage_rolls else 0
            return f"Critical Hit! Dealt {damage} damage!"
        elif event.attack_outcome == AttackOutcome.MISS:
            return "Miss!"
        elif event.attack_outcome == AttackOutcome.CRIT_MISS:
            return "Critical Miss!"
        else:
            return event.status_message if hasattr(event, 'status_message') else "Attack outcome unknown"
