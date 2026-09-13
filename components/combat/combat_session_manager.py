"""
Combat Session Manager - Internal Combat Turn Loop

Manages complete combat session from start to finish without returning to orchestrator.
This class handles ALL combat turns internally. Player choices come from an
injected input_provider (defaults to input() for CLI play) -- see plan 1.8/D4.

**ARCHITECTURE (2026-01-03): Generic Data-Driven Design**

This class uses a fully generic approach that leverages dnd_engine and ACTION_REGISTRY:
- ✅ No hardcoded action lists - discovers actions from ACTION_REGISTRY
- ✅ No if/elif chains for action types - uses metadata dispatch
- ✅ Works with both D&D 5e actions and Roshar extensions seamlessly
- ✅ New actions can be added to ACTION_REGISTRY without modifying this code

Based on: COMBAT_ENGINE_IMPLEMENTATION_PLAN.md Phase 3
"""

from typing import Dict, Any, List, Optional, Tuple

from config.logging_config import get_logger

from components.combat.multiattack import attacks_per_turn_for

logger = get_logger(__name__)


# Actions that help their target, so they must be aimed at allies (including
# self) rather than at enemies. Kept as a module constant so action_registry
# entries can also opt in with "beneficial": True.
_BENEFICIAL_ACTIONS = {
    "progression_healing",
    "regrowth",
    "stormlight_infusion",
}


class CombatSessionManager:
    """
    Manages internal combat turn loop.

    IMPORTANT: This runs INSIDE CombatAgent.run() and handles
    ALL combat turns without returning to orchestrator.

    Responsibilities:
    - Run combat turn loop
    - Get player choices via the injected input_provider
    - Execute NPC AI actions
    - Advance turns
    - Check end conditions
    - Display combat status after each turn
    """

    def __init__(
        self,
        combat_state: Dict[str, Any],
        game_engine,
        character_manager,
        dnd_engine_wrapper,
        combat_action_resolver,
        combat_narrative_generator,
        npc_ai_agent,
        input_provider=None,
    ):
        """
        Initialize Combat Session Manager.

        Args:
            combat_state: Combat state dict from CombatInitializer
            game_engine: GameEngine instance
            character_manager: CharacterManager instance
            dnd_engine_wrapper: DnDEngineWrapper instance
            combat_action_resolver: CombatActionResolver instance
            combat_narrative_generator: CombatNarrativeGenerator instance
            npc_ai_agent: NPCAIAgent instance
            input_provider: Callable[[str], str] used to ask the player to
                choose. Defaults to builtins.input for CLI play.

                Plan 1.8 / D4: nothing below the interface layer should call
                input() directly. Doing so made combat unsavable, untestable
                (it hung CI to zero output), and undriveable from any non-CLI
                UI. Injecting the provider lets tests and future UIs supply
                choices without touching stdin. The next step is for this to
                return `awaiting_player_input` as data rather than calling out
                at all.
        """
        self.combat_state = combat_state
        self.game_engine = game_engine
        self.character_manager = character_manager
        self.dnd_wrapper = dnd_engine_wrapper
        self.action_resolver = combat_action_resolver
        self.narrative_gen = combat_narrative_generator
        self.npc_ai = npc_ai_agent
        # Store the override (may be None). Resolve late in _prompt_choice so
        # that patching builtins.input still works for CLI play and tests --
        # binding `input` here would capture the unpatched builtin.
        self._input_provider_override = input_provider
        self.logger = get_logger(__name__)
        # Multiattack bookkeeping: {char_id: {attack_index: modifier_uuid}} for
        # the temporary action grants that pay for the 2nd..Nth attack of a
        # Multiattack. See _resolve_extra_attacks.
        self._extra_action_modifiers: Dict[str, Dict[int, Any]] = {}

    @property
    def input_provider(self):
        """The injected provider, or the current builtins.input."""
        return self._input_provider_override or input

    @input_provider.setter
    def input_provider(self, provider):
        self._input_provider_override = provider

    # Bound the prompt loop so a provider that never returns a valid choice
    # (a test stub, a disconnected UI) cannot spin forever.
    MAX_INPUT_ATTEMPTS = 10

    def _prompt_choice(self, prompt: str, num_options: int, default_index: int = 0):
        """
        Ask the player to pick 1..num_options, returning a 0-based index.

        Falls back to `default_index` after MAX_INPUT_ATTEMPTS invalid or
        unavailable responses, so combat degrades instead of hanging.
        """
        for attempt in range(self.MAX_INPUT_ATTEMPTS):
            try:
                raw = self.input_provider(prompt)
                choice = str(raw).strip()
            except (EOFError, KeyboardInterrupt):
                self.logger.warning("   ⚠️ Input stream closed; using default choice")
                return default_index
            except Exception as e:
                self.logger.warning(f"   ⚠️ Input provider failed ({e}); using default")
                return default_index

            if not choice.isdigit():
                print("❌ Please enter a number")
                continue

            idx = int(choice) - 1
            if 0 <= idx < num_options:
                return idx
            print(f"❌ Please choose 1-{num_options}")

        self.logger.warning(
            f"   ⚠️ No valid choice after {self.MAX_INPUT_ATTEMPTS} attempts; "
            f"defaulting to option {default_index + 1}"
        )
        return default_index

    def run_combat_loop(self) -> Dict[str, Any]:
        """
        Run complete combat from start to finish.

        Process:
        1. Display combat start
        2. Loop through turns until combat ends
        3. Return final combat result

        Returns:
            {
                "outcome": "victory|defeat|fled",
                "rounds": 5,
                "combat_log": [...],
                "final_states": {...}
            }
        """
        self.logger.info("🗡️ Combat loop starting...")
        self.logger.info(f"   Initial round: {self.combat_state['round_number']}")
        self.logger.info(f"   Total combatants: {len(self.combat_state['active_combatants'])}")
        self.logger.info(f"   Combatants: {self.combat_state['active_combatants']}")

        # Display combat start
        self._display_combat_start()

        # Main combat loop
        loop_iteration = 0
        stall_breaks = 0
        # A turn is action + bonus action + a little slack; beyond that the
        # economy plainly is not being consumed, so advance rather than spin.
        MAX_ACTIONS_PER_TURN = 4
        consecutive_same_actor = 0
        last_actor_id = None
        while not self._is_combat_over():
            loop_iteration += 1
            self.logger.info(f"🔄 COMBAT LOOP ITERATION {loop_iteration}")
            self.logger.info(f"   Round: {self.combat_state['round_number']}")
            self.logger.info(f"   Turn index: {self.combat_state['current_turn_index']}")

            # Get current actor
            current_actor_id = self._get_current_actor()
            self.logger.info(f"   Current actor: {current_actor_id}")

            # Reset the stall counter whenever the actor changes
            if current_actor_id != last_actor_id:
                consecutive_same_actor = 0
                last_actor_id = current_actor_id

            # Check if actor is alive. At 0 HP a PLAYER is *dying*, not out: 5e
            # gives them a death saving throw at the start of each of their turns.
            # This used to skip straight past, so the encounter ended the instant
            # anyone dropped and death saves never ran in play at all.
            if self._is_combatant_dead(current_actor_id):
                self._roll_death_save_for(current_actor_id)
                self.logger.info(
                    f"   ⚠️ {current_actor_id} is down, advancing turn")
                self._advance_turn()
                consecutive_same_actor = 0
                continue

            # Execute turn based on actor type
            is_player = self._is_player(current_actor_id)
            self.logger.info(f"   Actor type: {'Player' if is_player else 'NPC'}")

            if is_player:
                self.logger.info(f"   ▶️ Executing player turn for {current_actor_id}")
                self._execute_player_turn(current_actor_id)
            else:
                self.logger.info(f"   ▶️ Executing NPC turn for {current_actor_id}")
                self._execute_npc_turn(current_actor_id)

            # Check if combatant has more actions
            has_actions = self._has_actions_remaining(current_actor_id)
            self.logger.info(f"   Actions remaining for {current_actor_id}: {has_actions}")

            if not has_actions:
                # Advance to next combatant
                self.logger.info(f"   ⏭️ No actions remaining, advancing turn")
                self._advance_turn()
                consecutive_same_actor = 0
            else:
                # An actor keeping actions is legitimate (action + bonus action),
                # but if its economy never decreases we would spin forever. That
                # is exactly what happened when an action failed to consume:
                # 1001 iterations, then the safety break, and combat reported
                # outcome "unknown" because it never reached an end condition.
                # Force the turn along after a bounded number of retries.
                consecutive_same_actor += 1
                if consecutive_same_actor >= MAX_ACTIONS_PER_TURN:
                    # Counted, not just logged. This is a SAFETY NET for
                    # production; if it fires at all, some actor's economy is not
                    # decreasing and the turn logic is broken. Exposing the count
                    # lets a test fail on it instead of silently limping — the
                    # `actions OR bonus_actions` bug ran 355 iterations across 30
                    # rounds while three loop tests passed, because the breaker
                    # kept advancing play and the tests only checked termination.
                    stall_breaks += 1
                    self.logger.warning(
                        f"   ⚠️ {current_actor_id} still has actions after "
                        f"{consecutive_same_actor} attempts and its economy is not "
                        f"decreasing — forcing turn advance to avoid a stall"
                    )
                    self._advance_turn()
                    consecutive_same_actor = 0
                else:
                    self.logger.info(f"   ⏸️ Actor still has actions, continuing their turn")

            # Safety check to prevent infinite loops
            if loop_iteration > 1000:
                self.logger.error("❌ INFINITE LOOP DETECTED - Breaking combat loop")
                break

        # Combat ended
        self.logger.info(f"🏁 Combat loop ended after {loop_iteration} iterations")

        # Clear all class feature effects when combat ends
        try:
            class_feat_engine = self.dnd_wrapper.class_feature_engine(
                combat_state=self.combat_state
            )
            class_feat_engine.clear_all()
            self.logger.debug("✨ Cleared all class feature effects")
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to clear class features: {e}")

        outcome = self._determine_outcome()
        self.logger.info(f"⚔️ Combat ended: {outcome}")

        return {
            "outcome": outcome,
            "rounds": self.combat_state["round_number"],
            "combat_log": self.combat_state["combat_log"],
            "final_states": self.combat_state["combatant_states"],
            # Diagnostics. `iterations` makes inefficiency measurable: a healthy
            # encounter runs about rounds x combatants, so a 4x overshoot is
            # visible instead of merely slow. `stall_breaks` should always be 0.
            "iterations": loop_iteration,
            "stall_breaks": stall_breaks,
        }

    def _execute_player_turn(self, player_char_id: str):
        """
        Execute player's turn using hierarchical menu navigation.

        **UPDATED (2026-01-03)**: Implemented two-level menu system to prevent
        UI overload when many targets/abilities exist.

        Process:
        1. Display combat status
        2. Show action categories (Level 1)
        3. Get category selection
        4. Show specific actions in category (Level 2)
        5. Get action selection
        6. Parse and validate action
        7. Execute via action resolver
        8. Generate and display narrative
        9. Update combat state
        """
        self.logger.info(f"🎮 Player turn: {player_char_id}")

        # Display status
        print("\n" + "="*60)
        print(self.narrative_gen.generate_combat_status(self.combat_state))
        print("="*60)

        # Cover and flanking follow from where everyone is standing, so recompute them
        # before the player sees their options — a +2 AC that appears only after you
        # commit is not a choice.
        self._refresh_tactics(player_char_id)

        # Show the battlefield BEFORE the menu, so movement choices make sense.
        # This is the same grid data a UI would render, so if the text map is wrong
        # the UI would be wrong too — it doubles as a check on the geometry.
        self._print_battlefield(player_char_id)

        # Get available action categories
        action_categories = self._get_available_actions(player_char_id)

        # Movement is a category of its own, offered as INTENT rather than
        # coordinates ("Close in on the Scout (15 ft)"). `move` used to be in the
        # registry needing an `end_position` nobody supplied, so it was refused on
        # every attempt and the tactical half of 5e did not exist.
        movement = self._movement_actions(player_char_id)
        if movement:
            action_categories = dict(action_categories)
            action_categories["movement"] = {
                "name": "🏃 Movement",
                "description": f"Reposition ({self._speed_remaining(player_char_id)} ft left)",
                "cost_type": "movement",
                "actions": movement,
            }

        # Surgebinding maneuvers, offered from the AUTHORED automation data rather
        # than from hardcoded action classes. The executor had zero production
        # callers until this call site existed, so all nine maneuvers passed their
        # tests while no player could reach one.
        maneuvers = self._maneuver_actions(player_char_id)
        if maneuvers:
            action_categories = dict(action_categories)
            remaining = self._dice_pool().remaining(player_char_id)
            action_categories["maneuvers"] = {
                "name": "⚡ Maneuvers",
                "description": f"Surgebinding ({remaining} lashing dice left)",
                "cost_type": "actions",
                "actions": maneuvers,
            }

        if not action_categories:
            print("❌ No actions available (no actions remaining)")
            return

        # LEVEL 1: Choose action category
        print("\n📋 Choose Action Type:")
        category_keys = list(action_categories.keys())
        for i, category_key in enumerate(category_keys, 1):
            category = action_categories[category_key]
            action_count = len(category["actions"])
            print(f"  {i}. {category['name']} - {category['description']} ({action_count} options)")

        choice_idx = self._prompt_choice(
            f"\n{player_char_id}> Choose action type (1-{len(category_keys)}): ",
            len(category_keys),
        )
        selected_category_key = category_keys[choice_idx]

        # LEVEL 2: Choose specific action within category
        selected_category = action_categories[selected_category_key]
        specific_actions = selected_category["actions"]

        print(f"\n{selected_category['name']} - Choose Target/Action:")
        for i, action_item in enumerate(specific_actions, 1):
            print(f"  {i}. {action_item['display']}")

        action_idx = self._prompt_choice(
            f"\n{player_char_id}> Choose action (1-{len(specific_actions)}): ",
            len(specific_actions),
        )
        selected_action_item = specific_actions[action_idx]

        # MOVEMENT takes its own path: it is not an action in 5e (it is a separate
        # budget), so it must not go through the action resolver or consume the
        # action economy. Charging an action for a step would make repositioning
        # strictly worse than standing still.
        if selected_category_key == "movement":
            result = self._execute_movement(player_char_id, selected_action_item)
            print(f"\n{result['description']}")
            self._log_combat_action(
                {"actor": player_char_id, "action_type": "move",
                 "target": selected_action_item.get("target")}, result)
            self.logger.info(f"✅ Player movement: {result.get('description')}")
            return

        # MANEUVERS take their own path too: they are resolved by the automation
        # interpreter against the authored JSON, not by the action resolver, which
        # only knows ACTION_REGISTRY classes. Routing them through the resolver
        # would mean re-adding a Python class per maneuver — exactly what the
        # declarative schema exists to avoid.
        if selected_category_key == "maneuvers":
            # The target is baked into the menu entry's params, the same way every
            # other action carries it — see _parse_hierarchical_action.
            target_id = (selected_action_item.get("params") or {}).get("target", "")
            if selected_action_item.get("requires_target") and not target_id:
                hostiles = [h for h in self._hostiles_of(player_char_id)
                            if not self._is_out_of_the_fight(h)]
                if not hostiles:
                    print("❌ No target available")
                    return
                target_id = hostiles[0]

            result = self._execute_maneuver(
                player_char_id, selected_action_item.get("maneuver_id"), target_id)
            print(f"\n{result['description']}")
            self._log_combat_action(
                {"actor": player_char_id, "action_type": "maneuver",
                 "target": target_id}, result)

            if result.get("success"):
                # Spend the action EXPLICITLY. `_consume_action` only mirrors the
                # engine's economy into combat_state for display — the engine
                # normally debits it inside `action.apply()`. A maneuver never goes
                # through an engine action, so without this the actor would keep its
                # action and could maneuver all round.
                self._spend_maneuver_action(player_char_id, selected_action_item)
            return

        # DASH grants extra movement equal to your speed (5e). It was registered and
        # offerable but added NOTHING, so choosing it simply wasted the turn.
        if selected_action_item.get("action_type") == "dash":
            rules = self._rules()
            bonus = rules.dash_bonus_feet(player_char_id) if rules else 0
            if bonus:
                state = self.combat_state["combatant_states"].setdefault(
                    player_char_id, {})
                state["movement_remaining"] = (
                    self._speed_remaining(player_char_id) + bonus)
                print(f"\n{self._display_name(player_char_id)} dashes "
                      f"(+{bonus} ft of movement).")

        # Parse action from selection
        action = self._parse_hierarchical_action(
            player_char_id,
            selected_category_key,
            selected_action_item
        )

        # Validate action
        if not self._validate_action(action):
            print("❌ Action not valid in current state")
            return  # Try again

        # Execute action
        result = self.action_resolver.resolve_action(action)

        # Log action
        self._log_combat_action(action, result)

        # A REFUSED action did not happen, so do not narrate it. The engine
        # returns refused=True when it declines (usually: no action left), and a
        # live combat printed a vivid missed sword swing for every one of them —
        # fiction contradicting mechanics, which is the exact drift the DM tools
        # exist to prevent.
        if result.get("refused"):
            self.logger.debug(
                f"   (not narrating a refused {action.get('action_type')})")
        else:
            narrative = self.narrative_gen.generate_action_narrative(
                action=action,
                result=result,
                combat_state=self.combat_state
            )
            print(f"\n{narrative}")

        # Consume action
        self._consume_action(player_char_id, action["action_type"])

        self.logger.info(f"✅ Player action executed: {action['action_type']}")

    def _execute_npc_turn(self, npc_char_id: str):
        """
        Execute NPC's turn using AI decision.

        Process:
        1. Build context for NPC AI
        2. LLM decides action
        3. Validate action
        4. Execute action
        5. Generate and display narrative
        6. Update combat state
        """
        self.logger.info(f"🤖 NPC turn: {npc_char_id}")

        # CLOSE THE DISTANCE FIRST.
        #
        # With a real map, combatants no longer start adjacent — the authored
        # Shattered Plains puts them 75 ft apart across a chasm. An NPC that only
        # ever attacks then swings at nothing forever: measured immediately after
        # wiring the grid, `test_full_combat_session` ran **334 rounds and returned
        # `unknown`**, because neither side could reach the other.
        #
        # Movement is a separate budget from the action, so a monster closes AND
        # attacks in the same turn, exactly as 5e intends. This runs before the AI is
        # consulted so the AI's choice is made from where the NPC ENDS UP.
        self._npc_close_distance(npc_char_id)

        # Same for the NPC: it moved, so its cover and flanking may have changed.
        self._refresh_tactics(npc_char_id)

        # Build context for AI
        context = self._build_npc_context(npc_char_id)

        # Get AI decision
        ai_decision = self.npc_ai.decide_action(context)

        # Convert to action dict
        action = {
            "actor": npc_char_id,
            "action_type": ai_decision["action_type"],
            "target": ai_decision.get("target"),
            "weapon": ai_decision.get("weapon"),
            "reasoning": ai_decision.get("reasoning", "")
        }

        # Validate
        if not self._validate_action(action):
            # Fallback to basic attack
            self.logger.warning(f"NPC AI action invalid, using fallback")
            action = self._get_fallback_action(npc_char_id)

        # Execute action
        result = self.action_resolver.resolve_action(action)

        # Log action
        self._log_combat_action(action, result)

        # A REFUSED action did not happen, so do not narrate it. The engine
        # returns refused=True when it declines (usually: no action left), and a
        # live combat printed a vivid missed sword swing for every one of them —
        # fiction contradicting mechanics, which is the exact drift the DM tools
        # exist to prevent.
        if result.get("refused"):
            self.logger.debug(
                f"   (not narrating a refused {action.get('action_type')})")
        else:
            narrative = self.narrative_gen.generate_action_narrative(
                action=action,
                result=result,
                combat_state=self.combat_state
            )
            print(f"\n{narrative}")

        # MULTIATTACK: the rest of the attacks this stat block grants.
        self._resolve_extra_attacks(npc_char_id, action, result)

        # Consume action
        self._consume_action(npc_char_id, action["action_type"])

        self.logger.info(f"✅ NPC action executed: {action['action_type']}")

    def _resolve_extra_attacks(self, npc_char_id: str, action: Dict[str, Any],
                               first_result: Dict[str, Any]) -> int:
        """
        Take the SECOND and later attacks a Multiattack stat block grants.

        THE BUG. Nothing anywhere read Multiattack, so every monster in the game
        attacked exactly once per turn: an Ape that should throw two fists threw
        one, an Owlbear beaked without clawing, and an Adult Black Dragon made a
        single bite instead of bite + two claws. 148 of the 334 vendored SRD
        monsters have Multiattack, so this halved or thirded most monsters'
        damage — and since the CR HP/AC bands were tuned against MEASURED
        time-to-kill (`scripts/derive_cr_bands.py`), every difficulty figure was
        wrong in the party's favour.

        WHY THE ECONOMY IS GRANTED RATHER THAN BYPASSED. dnd_engine's `Attack`
        debits `action_economy.actions` itself and `apply()` returns None once the
        pool is empty — that is what stops a monster attacking forever, and it must
        keep doing so. In 5e, Multiattack is ONE action that makes several attack
        rolls, which the engine has no concept of. So for each extra attack we
        add one action to the pool, spend it on the attack, and then remove any
        unspent remainder. The turn therefore stays bounded by
        `attacks_per_turn` — a number that itself comes from the stat block and is
        clamped to 1..MAX_ATTACKS_PER_TURN — and the actor still ends its turn
        with an empty pool, so the turn loop advances exactly as before.

        Only ATTACKS repeat. A monster that dodged, dashed or cast is unaffected,
        and a first attack the engine refused is not retried.

        Returns the number of extra attacks actually resolved (0 for a monster
        without Multiattack), so tests can assert on the count.
        """
        if action.get("action_type") != "attack":
            return 0
        if first_result.get("refused"):
            # The first swing never happened (no action, or the engine declined);
            # granting more actions here would manufacture attacks out of nothing.
            return 0

        character = self.character_manager.characters.get(npc_char_id)
        total_attacks = attacks_per_turn_for(character, default=1)
        if total_attacks <= 1:
            return 0

        entity = self.dnd_wrapper.entities.get(npc_char_id)
        economy = getattr(entity, "action_economy", None)
        if economy is None:
            self.logger.warning(
                f"⚠️ {npc_char_id} has no action economy; multiattack skipped")
            return 0

        self.logger.info(
            f"   ⚔️ Multiattack: {self._display_name(npc_char_id)} makes "
            f"{total_attacks} attacks this turn")

        resolved = 0
        for index in range(2, total_attacks + 1):
            # A target that has dropped ends the flurry — 5e lets a monster
            # redirect, but silently beating a corpse is worse than stopping, and
            # target reselection belongs to the NPC AI.
            target = action.get("target")
            if target and self._is_combatant_dead(target):
                self.logger.info(
                    f"   ⚔️ {target} is down; {self._display_name(npc_char_id)} "
                    f"stops after {resolved + 1} of {total_attacks} attacks")
                break

            if not self._grant_extra_action(npc_char_id, economy, index):
                break

            pool_before = self._action_pool(economy)
            extra = dict(action)
            extra["multiattack_index"] = index
            result = self.action_resolver.resolve_action(extra)
            self._log_combat_action(extra, result)

            if result.get("refused"):
                self.logger.warning(
                    f"⚠️ {npc_char_id} multiattack {index}/{total_attacks} was "
                    f"refused despite a granted action; stopping")
                self._revoke_extra_action(npc_char_id, economy, index,
                                          pool_before)
                break

            resolved += 1
            narrative = self.narrative_gen.generate_action_narrative(
                action=extra, result=result, combat_state=self.combat_state)
            print(f"\n{narrative}")

            # Take the grant back ONLY if the attack did not spend it (a Roshar
            # action, or a stubbed resolver). See _revoke_extra_action.
            self._revoke_extra_action(npc_char_id, economy, index, pool_before)

        self._sync_hp_from_engine()
        self.logger.info(
            f"   ⚔️ Multiattack complete: {resolved + 1}/{total_attacks} attacks "
            f"made by {npc_char_id}")
        return resolved

    def _extra_action_modifier_name(self, index: int) -> str:
        return f"multiattack_{index}"

    @staticmethod
    def _action_pool(economy) -> int:
        """The actor's remaining actions, or 0 if the pool cannot be read."""
        try:
            return int(economy.actions.normalized_score)
        except Exception:
            return 0

    def _grant_extra_action(self, char_id: str, economy,
                            index: int) -> bool:
        """
        Add one action to the pool so the next attack of a Multiattack can be paid.

        A POSITIVE modifier, named so `_revoke_extra_action` can find it again.
        `ActionEconomy.consume()` only ever adds negative modifiers, so this is the
        mirror image and uses the same machinery — no new state to keep in sync.
        """
        try:
            from dnd.core.modifiers import NumericalModifier
            modifier = NumericalModifier.create(
                source_entity_uuid=economy.source_entity_uuid,
                name=self._extra_action_modifier_name(index),
                value=1,
            )
            economy.actions.self_static.add_value_modifier(modifier)
            self._extra_action_modifiers.setdefault(char_id, {})[index] = modifier.uuid
            return True
        except Exception as e:
            self.logger.warning(
                f"⚠️ Could not grant a multiattack action to {char_id}: {e}")
            return False

    def _revoke_extra_action(self, char_id: str, economy, index: int,
                             pool_before: Optional[int] = None) -> None:
        """
        Take a granted multiattack action back — but ONLY if it went unspent.

        This is the subtle half of the mechanism, and getting it wrong cost the
        third attack of every 3-attack monster. `Attack.apply()` pays by adding its
        own -1 `cost` modifier; the grant's +1 stays in the pool as its
        counterweight. Removing the grant afterwards therefore leaves an unmatched
        -1 and drives the pool NEGATIVE, so the next attack is refused. Measured:
        a Brute with attacks_per_turn=3 made 2 attacks, and the third was logged
        as "refused despite a granted action".

        So: if the pool DROPPED across the attack, the grant was consumed and must
        stay. If it did not (a Roshar action that costs Stormlight instead, or a
        stubbed resolver), the grant is removed so it cannot accumulate into a free
        extra turn. Either way the actor ends the turn with a pool of zero, which
        is what makes the turn loop advance.

        `pool_before=None` forces removal, for the caller that never ran an attack.
        """
        modifier_uuid = self._extra_action_modifiers.get(char_id, {}).pop(index, None)
        if modifier_uuid is None:
            return

        if pool_before is not None and self._action_pool(economy) < pool_before:
            self.logger.debug(
                f"   ⏳ {char_id} spent the multiattack {index} grant; keeping it "
                f"to balance the action's own cost")
            return

        try:
            economy.actions.self_static.remove_value_modifier(modifier_uuid)
            self.logger.debug(
                f"   ↩️ {char_id}: unspent multiattack {index} grant returned")
        except Exception as e:
            self.logger.debug(
                f"   (multiattack grant {index} for {char_id} already gone: {e})")

    def _get_available_actions(self, char_id: str) -> Dict[str, Dict[str, Any]]:
        """
        Get hierarchical action categories for character using ACTION_REGISTRY.

        **UPDATED (2026-01-03)**: Generic data-driven approach that queries
        ACTION_REGISTRY to discover available actions dynamically.

        Returns action categories with sub-options:
        {
            "standard_actions": {
                "name": "⚔️ Standard Actions",
                "description": "Attack, cast spells, use abilities",
                "cost_type": "actions",
                "actions": [...]
            },
            "bonus_actions": {
                "name": "⚡ Bonus Actions",
                "description": "Quick abilities and reactions",
                "cost_type": "bonus_actions",
                "actions": [...]
            },
            "utility": {
                "name": "🛡️ Utility",
                "description": "Defensive and movement options",
                "cost_type": "actions",
                "actions": []
            }
        }
        """
        categories = {
            "standard_actions": {
                "name": "⚔️ Standard Actions",
                "description": "Attack, cast spells, use abilities",
                "cost_type": "actions",
                "actions": []
            },
            "bonus_actions": {
                "name": "⚡ Bonus Actions",
                "description": "Quick abilities and reactions",
                "cost_type": "bonus_actions",
                "actions": []
            },
            "utility": {
                "name": "🛡️ Utility",
                "description": "Defensive and movement options",
                "cost_type": "actions",
                "actions": []
            }
        }

        char_state = self.combat_state["combatant_states"][char_id]
        character = self.character_manager.characters[char_id]

        # Query ACTION_REGISTRY to discover available actions
        from components.combat.action_registry import is_offerable

        for action_type, metadata in self.action_resolver.ACTION_REGISTRY.items():
            # Never OFFER an action the resolver will refuse. `progression_healing`
            # was on the player menu every round and always refused for a missing
            # `healing_amount` — a live auto-play picked it at 4/22 HP and simply
            # lost the turn. An offered action that cannot be taken is a trap.
            if not is_offerable(action_type):
                continue

            # Check if character can afford this action
            if not self._can_character_afford_action(char_id, metadata):
                continue

            # Check if THIS character meets the action's gates. Offerability is
            # actor-independent, so it happily offers a Lightweaver's Soulcast to a
            # Windrunner (and to a goblin); only this check knows about Order,
            # Surgebinding level and Stormlight.
            if not self._character_meets_requirements(character, metadata,
                                                      action_type):
                continue

            # Determine which category this action belongs to
            category = self._categorize_action(action_type, metadata)

            # Generate action options (with targets if needed)
            action_options = self._generate_action_options(
                char_id, action_type, metadata
            )

            categories[category]["actions"].extend(action_options)

        # Remove empty categories
        return {k: v for k, v in categories.items() if v["actions"]}

    def _can_character_afford_action(self, char_id: str, action_metadata: Dict) -> bool:
        """
        Check if character has resources for action using dnd_engine.

        **SIMPLIFIED (2026-01-03):** Uses entity.action_economy.can_afford() exclusively.
        No fallback to manual checking.

        Args:
            char_id: Character ID
            action_metadata: Action metadata from ACTION_REGISTRY

        Returns:
            True if character can afford the action, False otherwise
        """
        entity = self.dnd_wrapper.entities[char_id]
        action_class = action_metadata.get("action_class")

        # Plan 1.2: this used to guard on `hasattr(action_class, "cost_type")`
        # and `"cost"`. dnd_engine actions have NEITHER — they carry a `costs`
        # LIST of Cost objects, each with .cost_type and .cost. The guard never
        # matched, so this method unconditionally returned True and the action
        # economy was never enforced (despite the "no fallback" comment).
        if action_class is None:
            return True

        costs = getattr(action_class, "costs", None)
        # `costs` may be a pydantic FieldInfo on the class rather than a real
        # list; only a concrete iterable is meaningful here.
        if not isinstance(costs, (list, tuple)) or not costs:
            # Genuinely free action (e.g. most Roshar surges gate on Stormlight
            # instead of the action economy).
            return True

        for cost in costs:
            cost_type = getattr(cost, "cost_type", None)
            amount = getattr(cost, "cost", None)
            if cost_type is None or amount is None:
                continue
            if not entity.action_economy.can_afford(cost_type, amount):
                logger.debug(
                    f"   ⛔ {char_id} cannot afford {cost_type} x{amount}"
                )
                return False

        return True

    def _character_meets_requirements(self, character, action_metadata: Dict,
                                      action_type: Optional[str] = None) -> bool:
        """
        Whether THIS character satisfies the action's gates.

        Delegates to `action_registry.unusable_reason`, which is the single place
        that knows the gates the action classes enforce (`requires_order`,
        `min_surgebinding_level`, `stormlight_cost`, `requires`).

        What was here before checked `requires` first and returned True whenever it
        was falsy — and `requires` is None for all four Surges. So the
        `requires_order` block below it was UNREACHABLE, and every surge gate was
        skipped: a plain goblin's NPC menu came back as
        ['attack', 'dash', 'dodge', 'lashing', 'progression_healing',
         'illumination', 'soulcast'] and all four surges were then cancelled by
        `roshar_actions._validate`. Stormlight and Surgebinding level were never
        checked here at all, in any code path.

        `action_type` is optional only so older callers keep working; without it the
        name is recovered from the registry by identity.
        """
        from components.combat.action_registry import (ACTION_REGISTRY,
                                                       unusable_reason)

        if action_type is None:
            action_type = next(
                (name for name, meta in ACTION_REGISTRY.items()
                 if meta is action_metadata),
                None)
        if action_type is None:
            return True  # not a registry action; nothing to gate on

        reason = unusable_reason(action_type, character)
        if reason:
            logger.debug(f"   ⛔ {action_type} unavailable: {reason}")
            return False
        return True

    def _categorize_action(self, action_type: str, metadata: Dict) -> str:
        """Determine which UI category an action belongs to."""
        # Check cost_type from metadata directly (for class features and actions without action_class)
        cost_type = metadata.get("cost_type")
        if cost_type == "bonus_actions":
            return "bonus_actions"

        # Check if it's a bonus action via action_class
        action_class = metadata.get("action_class")
        if action_class and hasattr(action_class, "cost_type"):
            if action_class.cost_type == "bonus_actions":
                return "bonus_actions"

        # Categorize based on action characteristics
        if metadata.get("type") in ["dnd_condition", "roshar_condition"]:
            # Conditions like Dash, Dodge are utility
            return "utility"
        elif metadata.get("type") == "class_feature":
            # Class features (Rage, Second Wind, Action Surge)
            # Rage and Second Wind are bonus actions, Action Surge is free
            if action_type == "action_surge":
                return "utility"
            else:
                return "bonus_actions"
        elif action_type in ["attack", "shardblade_attack", "lashing", "progression_healing"]:
            # Offensive/active actions
            return "standard_actions"

        return "utility"

    def _generate_action_options(
        self,
        char_id: str,
        action_type: str,
        metadata: Dict
    ) -> List[Dict[str, Any]]:
        """
        Generate action options (with targets if action requires targeting).

        Returns list of action options:
        [
            {
                "action_type": "attack",
                "display": "Attack Goblin Warrior (HP: 7/7)",
                "params": {"target": "goblin_001"}
            }
        ]
        """
        requires_target = "target_entity_uuid" in metadata.get("params", [])

        if requires_target:
            # Generate option for each valid target
            options = []
            # Beneficial actions target ALLIES; everything else targets enemies.
            # _get_valid_targets returns only opposite-hostility combatants, so
            # a live combat offered "Heal wounds with Progression → Shadow-Fused
            # Soldier" three times and no option to heal the wounded player at
            # 13/32 HP. The action was unusable as written.
            if metadata.get("beneficial") or action_type in _BENEFICIAL_ACTIONS:
                targets = [char_id] + self._get_allies(char_id)
                targets = [t for t in targets if not self._is_combatant_dead(t)]
            else:
                targets = self._get_valid_targets(char_id)

            for target_id in targets:
                target_char = self.character_manager.characters[target_id]
                target_state = self.combat_state["combatant_states"][target_id]
                hp_current = target_state["hp_current"]
                hp_max = target_state["hp_max"]

                # Get action description from metadata
                description = metadata.get("description", action_type)
                display = f"{description} → {target_char.name} (HP: {hp_current}/{hp_max})"

                options.append({
                    "action_type": action_type,
                    "display": display,
                    "params": {"target": target_id}
                })

            return options
        else:
            # Single option (no targeting)
            description = metadata.get("description", action_type)
            return [{
                "action_type": action_type,
                "display": description,
                "params": {}
            }]

    # ------------------------------------------------------------------ tactical
    #
    # Movement was declared in ACTION_REGISTRY needing an `end_position` that NOTHING
    # supplied, so every attempt was refused and combat ran on a fixed two-row line
    # where everyone was permanently adjacent. No flanking, cover, reach or retreat.
    # These methods are the seam to the real grid; `tactical_grid` is None when the
    # encounter fell back to the simple line, and every one of them degrades quietly
    # in that case.

    MOVEMENT_BUDGET_FEET = 30          # 5e Medium humanoid base speed

    def _grid(self):
        """The encounter's TacticalGrid, or None when there is no map."""
        return self.combat_state.get("tactical_grid")

    def _rules(self):
        """
        Position-derived rules (cover, flanking, opportunity attacks, dash).

        Built lazily and cached on combat_state, so the modifiers it applies can be
        removed by the same instance that added them. Applying a temporary modifier
        without holding its id is how "temporary" becomes permanent.
        """
        rules = self.combat_state.get("tactical_rules")
        if rules is None and self._grid() is not None:
            from components.combat.tactical_rules import TacticalRules

            rules = TacticalRules(self._grid(), self.dnd_wrapper,
                                 self.combat_state)
            self.combat_state["tactical_rules"] = rules
        return rules

    def _dice_pool(self):
        """
        The encounter's LashingDicePool, built lazily and cached.

        Registers a pool for every combatant whose order uses lashing dice (only
        Windrunners today); everyone else gets nothing, so a Lightweaver cannot
        spend Windrunner dice.
        """
        pool = self.combat_state.get("lashing_dice_pool")
        if pool is None:
            from components.combat.lashing_dice import LashingDicePool

            pool = LashingDicePool(self._cosmere_rules())
            for combatant_id in (self.combat_state.get("combatant_states") or {}):
                entity = (self.dnd_wrapper.entities.get(combatant_id)
                          if self.dnd_wrapper else None)
                if entity is None:
                    continue
                pool.register(combatant_id,
                              str(getattr(entity, "radiant_order", "") or ""),
                              int(getattr(entity, "level", 1) or 1))
            self.combat_state["lashing_dice_pool"] = pool
        return pool

    def _cosmere_rules(self):
        rules = self.combat_state.get("cosmere_rules")
        if rules is None:
            from components.cosmere_rules import get_cosmere_rules

            rules = get_cosmere_rules()
            self.combat_state["cosmere_rules"] = rules
        return rules

    def _maneuvers(self):
        """
        The encounter's ManeuverExecutor, built lazily and cached.

        WIRING THIS IS THE WHOLE POINT. The executor and its 58 tests existed with
        ZERO production callers — so all nine authored maneuvers passed their tests
        and no player could use one. That is the seventh instance of the
        built-tested-unreachable pattern catalogued in the plan's §14e, and it is
        why this accessor exists rather than a test-only fixture.
        """
        executor = self.combat_state.get("maneuver_executor")
        if executor is None:
            from components.combat.maneuver_executor import ManeuverExecutor

            executor = ManeuverExecutor(
                self.dnd_wrapper,
                dice_pool=self._dice_pool(),
                cosmere_rules=self._cosmere_rules(),
                combat_state=self.combat_state)
            self.combat_state["maneuver_executor"] = executor
        return executor

    def _maneuver_actions(self, char_id: str) -> List[Dict[str, Any]]:
        """
        Maneuvers this Radiant can use right now, as menu entries.

        Empty for a non-Radiant, for an order with no authored maneuvers, and for a
        Radiant out of lashing dice — an offered option that cannot be paid for is
        the same trap as an action needing a parameter nobody supplies.
        """
        try:
            executor = self._maneuvers()
            entity = (self.dnd_wrapper.entities.get(char_id)
                      if self.dnd_wrapper else None)
            if entity is None:
                return []
            order = str(getattr(entity, "radiant_order", "") or "")
            if not order:
                return []

            options = []
            for maneuver in executor.available(char_id, order,
                                              int(getattr(entity, "level", 1) or 1)):
                cost = (maneuver.get("cost") or {}).get("lashing_dice", 1)
                options.append({
                    "action_type": "maneuver",
                    "maneuver_id": maneuver.get("id"),
                    "name": maneuver.get("name", "Maneuver"),
                    "description": (f"{maneuver.get('action_type', 'action')}"
                                    f" — {cost} lashing die"),
                    "requires_target": self._maneuver_needs_target(maneuver),
                })
            return options
        except Exception as e:
            self.logger.debug(f"   Could not list maneuvers for {char_id}: {e}")
            return []

    @staticmethod
    def _maneuver_needs_target(maneuver: Dict[str, Any]) -> bool:
        """A maneuver needs a target only if its tree has a `target` node."""
        def walk(node) -> bool:
            if isinstance(node, dict):
                if node.get("type") == "target":
                    return True
                return any(walk(v) for v in node.values())
            if isinstance(node, list):
                return any(walk(v) for v in node)
            return False

        return walk(maneuver.get("automation"))

    def _execute_maneuver(self, char_id: str, maneuver_id: str,
                          target_id: str = "") -> Dict[str, Any]:
        """Run a chosen maneuver and report the result to the combat log."""
        executor = self._maneuvers()
        maneuver = self._cosmere_rules().get_maneuver(maneuver_id)
        if maneuver is None:
            return {"success": False, "error": f"unknown maneuver {maneuver_id!r}"}

        targets = [target_id] if target_id else []
        result = executor.execute(maneuver, char_id, targets=targets)
        self.logger.info(f"   {result.describe()}")
        return {"success": result.success, "error": result.error,
                "description": result.describe(),
                "damage": result.damage_dealt, "events": result.events}

    def _spend_maneuver_action(self, char_id: str,
                               action_item: Dict[str, Any]) -> None:
        """
        Debit the action economy for a maneuver.

        Maneuvers declare their own economy in the authored data — `action_type` is
        "action", "reaction", "on_hit", "on_move", "on_initiative" or "on_check".
        Only a full action is charged here: the trigger types ride along on
        something the actor is already doing, and charging them would make a
        Windrunner strictly worse for having options.
        """
        maneuver = self._cosmere_rules().get_maneuver(
            action_item.get("maneuver_id") or "") or {}
        kind = str(maneuver.get("action_type") or "action")

        cost_type = {"action": "actions", "reaction": "reactions",
                     "bonus_action": "bonus_actions"}.get(kind)
        if cost_type is None:
            return          # a triggered maneuver costs no separate action

        entity = self.dnd_wrapper.entities.get(char_id) if self.dnd_wrapper else None
        if entity is None:
            return
        try:
            entity.action_economy.consume(cost_type, 1)
        except Exception as e:
            self.logger.debug(f"   Could not debit {cost_type} for {char_id}: {e}")
        self._consume_action(char_id, "maneuver")

    def _refresh_tactics(self, char_id: str) -> None:
        """
        Recompute cover and flanking before an actor decides.

        Once per turn rather than continuously: position only changes on someone's
        turn, and recomputing on every read would be slower and harder to reason
        about.
        """
        rules = self._rules()
        if rules is None:
            return
        try:
            rules.refresh_cover()
            rules.refresh_flanking(char_id, self._hostiles_of(char_id))
        except Exception as e:
            self.logger.debug(f"   Could not refresh tactics for {char_id}: {e}")

    def _hostiles_of(self, char_id: str) -> List[str]:
        """Everyone on the other side who can still fight."""
        states = self.combat_state.get("combatant_states") or {}
        my_side = (states.get(char_id) or {}).get("is_hostile")
        return [cid for cid, state in states.items()
                if state.get("is_hostile") != my_side
                and not self._is_combatant_dead(cid)]

    def _speed_remaining(self, char_id: str) -> int:
        """
        Feet of movement left this turn.

        Tracked per turn on the combatant's own state, so a character cannot walk
        the whole map by choosing Movement repeatedly.
        """
        state = self.combat_state["combatant_states"].get(char_id) or {}
        remaining = state.get("movement_remaining")
        if remaining is None:
            remaining = self.MOVEMENT_BUDGET_FEET
            state["movement_remaining"] = remaining
        return int(remaining)

    def _spend_movement(self, char_id: str, feet: int) -> None:
        state = self.combat_state["combatant_states"].get(char_id) or {}
        state["movement_remaining"] = max(
            0, self._speed_remaining(char_id) - int(feet))

    def _print_battlefield(self, acting: str) -> None:
        """Draw the grid from the acting character's point of view."""
        grid = self._grid()
        if grid is None:
            return
        try:
            print("\n" + grid.render(acting=acting))
        except Exception as e:
            self.logger.debug(f"   Could not render the battlefield: {e}")

    def _movement_actions(self, char_id: str) -> List[Dict[str, Any]]:
        """Movement offers for the menu, in the same shape as other actions."""
        grid = self._grid()
        if grid is None:
            return []

        remaining = self._speed_remaining(char_id)
        if remaining <= 0:
            return []

        hostiles = [cid for cid, state
                    in self.combat_state["combatant_states"].items()
                    if state.get("is_hostile") != self.combat_state[
                        "combatant_states"].get(char_id, {}).get("is_hostile")
                    and not self._is_combatant_dead(cid)]
        try:
            options = grid.movement_options(char_id, hostiles,
                                           speed_feet=remaining)
        except Exception as e:
            self.logger.debug(f"   Movement options failed for {char_id}: {e}")
            return []

        return [{"action_type": "move",
                 "display": option.display(),
                 "end_position": option.destination,
                 "cost_feet": option.cost_feet,
                 "intent": option.intent,
                 "target": option.target}
                for option in options]

    def _execute_movement(self, char_id: str,
                          action_item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Move on the grid and report it.

        Movement is NOT an action in 5e — it is a separate budget — so this does not
        consume the action economy. Charging an action for a step is what would make
        repositioning strictly worse than standing still.
        """
        grid = self._grid()
        if grid is None:
            return {"success": False, "refused": True,
                    "description": "There is no room to manoeuvre here."}

        destination = tuple(action_item.get("end_position"))

        # Work out who is provoked BEFORE moving. Afterwards the mover is already out
        # of reach, so nobody would qualify and opportunity attacks would never fire.
        rules = self._rules()
        provoked = (rules.opportunity_attackers(char_id, destination)
                    if rules is not None else [])

        result = grid.move_to(char_id, destination,
                             speed_feet=self._speed_remaining(char_id))

        if not result.get("moved"):
            return {"success": False, "refused": True,
                    "description": f"{char_id} cannot move there — "
                                   f"{result.get('reason', 'no route')}."}

        self._spend_movement(char_id, result.get("cost_feet", 0))

        # 5e: leaving an enemy's reach provokes an opportunity attack, using their
        # REACTION — so each enemy gets at most one per round. Without this,
        # "Retreat out of reach" is free, and disengaging is strictly better than
        # standing your ground in every situation.
        self._resolve_opportunity_attacks(char_id, provoked)

        name = self._display_name(char_id)
        cover = " into cover" if result.get("in_cover") else ""
        return {"success": True, "moved": True,
                "from": result.get("from"), "to": result.get("to"),
                "cost_feet": result.get("cost_feet"),
                "description": (f"{name} moves {result.get('cost_feet')} ft"
                                f"{cover} to {result.get('terrain')}.")}

    def _npc_close_distance(self, npc_char_id: str) -> None:
        """
        Move an NPC toward its nearest reachable enemy, if it cannot already strike.

        Deliberately simple and deterministic — no LLM call. Tactical *intent* (flank,
        take cover, focus the wounded) belongs to the AI; getting within reach is
        table stakes, and spending a model call on "walk towards the enemy" would be
        both slow and unreliable. The AI already wasted 15 of 28 actions choosing
        `move` with no destination.
        """
        grid = self._grid()
        if grid is None:
            return

        my_state = self.combat_state["combatant_states"].get(npc_char_id) or {}
        enemies = [cid for cid, state
                   in self.combat_state["combatant_states"].items()
                   if state.get("is_hostile") != my_state.get("is_hostile")
                   and not self._is_combatant_dead(cid)]
        if not enemies:
            return

        # Already in reach of something: stand and fight.
        if any(grid.in_melee_reach(npc_char_id, enemy) for enemy in enemies):
            return

        remaining = self._speed_remaining(npc_char_id)
        if remaining <= 0:
            return

        try:
            options = grid.movement_options(npc_char_id, enemies,
                                           speed_feet=remaining)
        except Exception as e:
            self.logger.debug(f"   NPC movement failed for {npc_char_id}: {e}")
            return

        closing = [o for o in options if o.intent == "close"]
        if not closing:
            # Nothing adjacent is reachable this turn — take the single step that
            # most reduces the distance, or a fight across a chasm never progresses.
            self._npc_step_toward(npc_char_id, enemies, remaining)
            return

        chosen = min(closing, key=lambda o: o.cost_feet)
        result = grid.move_to(npc_char_id, chosen.destination,
                             speed_feet=remaining)
        if result.get("moved"):
            self._spend_movement(npc_char_id, result.get("cost_feet", 0))
            print(f"\n{self._display_name(npc_char_id)} closes in "
                  f"({result['cost_feet']} ft).")

    def _npc_step_toward(self, npc_char_id: str, enemies: List[str],
                         remaining: int) -> None:
        """Move as far toward the nearest enemy as this turn's budget allows."""
        grid = self._grid()
        target = None
        best = None
        for enemy in enemies:
            distance = grid.distance_feet(npc_char_id, enemy)
            if distance is not None and (best is None or distance < best):
                best, target = distance, enemy
        if target is None:
            return

        goal = grid.position_of(target)
        reachable = grid.reachable(npc_char_id, remaining)
        if not goal or not reachable:
            return

        # Closest reachable tile to the target, cheapest first on ties.
        def score(item):
            position, cost = item
            return (max(abs(position[0] - goal[0]), abs(position[1] - goal[1])),
                    cost)

        destination, _ = min(reachable.items(), key=score)
        result = grid.move_to(npc_char_id, destination, speed_feet=remaining)
        if result.get("moved"):
            self._spend_movement(npc_char_id, result.get("cost_feet", 0))
            print(f"\n{self._display_name(npc_char_id)} advances "
                  f"({result['cost_feet']} ft).")

    def _resolve_opportunity_attacks(self, mover: str,
                                     provoked: List[str]) -> None:
        """
        Let each provoked enemy take its reaction attack.

        Resolved through the normal action resolver, so an opportunity attack rolls,
        hits and damages exactly like any other — a "reaction attack" that used
        different maths would drift from the rest of combat.
        """
        rules = self._rules()
        if rules is None or not provoked:
            return

        for watcher in provoked:
            if self._is_combatant_dead(watcher):
                continue
            result = self.action_resolver.resolve_action(
                {"actor": watcher, "action_type": "attack", "target": mover})
            rules.spend_reaction(watcher)

            outcome = "hits" if result.get("success") else "misses"
            damage = result.get("damage") or 0
            print(f"\n⚡ {self._display_name(watcher)} strikes as "
                  f"{self._display_name(mover)} breaks away — {outcome}"
                  + (f" for {damage}." if damage else "."))
            self._log_combat_action(
                {"actor": watcher, "action_type": "opportunity_attack",
                 "target": mover}, result)
            self._sync_hp_from_engine()

    def _display_name(self, char_id: str) -> str:
        character = self.character_manager.characters.get(char_id)
        return getattr(character, "name", char_id)

    def _reset_movement(self) -> None:
        """Restore everyone's movement at the start of a round."""
        for state in self.combat_state["combatant_states"].values():
            state["movement_remaining"] = self.MOVEMENT_BUDGET_FEET

    def _parse_hierarchical_action(
        self,
        char_id: str,
        category_key: str,
        action_item: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Parse hierarchical menu selection into action dict.

        **UPDATED (2026-01-03)**: Generic data-driven approach that uses
        action_item metadata directly (no hardcoded if/elif chains).

        Args:
            char_id: Actor char_id
            category_key: Selected category ("standard_actions", "utility", "bonus_actions")
            action_item: Selected action dict from _generate_action_options()

        Returns:
            {
                "actor": "aggi",
                "action_type": "attack",
                "target": "goblin_001"
            }
        """
        # Build action dict from action_item metadata
        action = {
            "actor": char_id,
            "action_type": action_item["action_type"]
        }

        # Merge in any parameters (target, weapon, etc.)
        action.update(action_item.get("params", {}))

        return action

    def _validate_action(self, action: Dict) -> bool:
        """
        Validate action is legal in current combat state.

        **OPTIMIZED (2026-01-03):** For dnd_engine actions, leverages their native
        _validate() method which checks range, line of sight, and prerequisites.
        This reduces validation code and improves correctness.

        Args:
            action: Action dict with actor, action_type, target, etc.

        Returns:
            True if action is valid, False otherwise
        """
        actor_id = action["actor"]
        action_type = action["action_type"]

        # Get action metadata from ACTION_REGISTRY
        metadata = self.action_resolver.ACTION_REGISTRY.get(action_type)
        if not metadata:
            self.logger.warning(f"Unknown action type: {action_type}")
            return False

        # Check action economy via metadata
        if not self._can_character_afford_action(actor_id, metadata):
            return False

        # Check character meets requirements
        character = self.character_manager.characters.get(actor_id)
        if not self._character_meets_requirements(character, metadata):
            return False

        # For dnd_engine/Roshar actions, let Action._validate() handle detailed checks
        if metadata.get("type") in ["dnd_action", "roshar_action", "roshar_equipment"]:
            # dnd_engine Actions validate:
            # - Range/line of sight
            # - Action economy (via prerequisites)
            # - Target validity
            # - Resource costs
            # We only check high-level requirements here; Action.apply() will validate everything else
            return True

        # For non-dnd_engine actions, do manual validation
        # Validate target (if action requires targeting)
        if "target" in action:
            target_id = action["target"]

            # Target must be in combat
            if target_id not in self.combat_state["active_combatants"]:
                return False

            # Target must be alive
            if self._is_combatant_dead(target_id):
                return False

        return True

    def _consume_action(self, char_id: str, action_type: str):
        """
        Sync action economy from dnd_engine to combat state.

        **SIMPLIFIED (2026-01-03)**: dnd_engine Actions automatically consume action economy
        during action.apply(). This method syncs that state to combat_state for UI display only.

        Note: Action economy is ONLY tracked in dnd_engine. combat_state values are read-only
        mirrors for UI purposes.
        """
        entity = self.dnd_wrapper.entities[char_id]

        # Sync from dnd_engine to combat_state (UI display only).
        # Plan 1.2: ModifiableValue has NO `.value` attribute — the comment here
        # asserted otherwise and every read raised AttributeError. The real
        # accessor is `.normalized_score` (`.score` is the un-normalized form).
        char_state = self.combat_state["combatant_states"][char_id]
        char_state["actions_remaining"] = entity.action_economy.actions.normalized_score
        char_state["bonus_actions_remaining"] = entity.action_economy.bonus_actions.normalized_score
        char_state["reaction_available"] = entity.action_economy.reactions.normalized_score > 0

        # Mirror HP too. combat_state["hp_current"] was never written back from
        # the engine, so the status panel and the action menu showed starting HP
        # for the whole fight ("Voidbringer Scout: 22/22" while it was actually
        # being wounded). End conditions read the engine directly, so this was
        # cosmetic — but it made a working fight look broken, and it hid the
        # damage that WAS being dealt.
        self._sync_hp_from_engine()

    def _sync_hp_from_engine(self) -> None:
        """
        Copy every combatant's live HP from dnd_engine into combat_state AND
        back onto CharacterData.

        The CharacterData half was missing, and that produced two visible bugs:

        1. A 7-round fight that ended in `defeat` left the character untouched on
           record (still 13/36), so the next turn re-initialised the same
           encounter against a nominally healthy character and combat restarted.
        2. `roll_death_save()` reads `character.hit_points["current"]` and returns
           `{"skipped": "character is conscious"}` for anything above 0 — so even
           once death saves were wired, they could never fire while the record
           said the character was at full health.

        `combat_state` is the DISPLAY; `CharacterData` is the RECORD. Writing only
        the display is what let the damage vanish at the end of the encounter.
        """
        for cid, state in self.combat_state["combatant_states"].items():
            entity = self.dnd_wrapper.entities.get(cid)
            if entity is None:
                continue
            try:
                current = self.dnd_wrapper.get_entity_current_hp(entity)
                state["hp_current"] = current

                character = self.character_manager.characters.get(cid)
                if character is not None and isinstance(character.hit_points, dict):
                    # Never let HP display below 0; 5e treats excess damage as 0
                    # (barring instant death, which is handled separately).
                    character.hit_points["current"] = max(0, current)
            except Exception as e:
                self.logger.debug(f"   Could not sync HP for {cid}: {e}")

    def _has_actions_remaining(self, char_id: str) -> bool:
        """
        Check if combatant has actions/bonus actions remaining.

        **SIMPLIFIED (2026-01-03):** Queries dnd_engine directly. No fallback.
        """
        entity = self.dnd_wrapper.entities[char_id]
        # Plan 1.2: `.value` does not exist on ModifiableValue (see above).
        #
        # ONLY the action pool. This used to be `actions OR bonus_actions`, and
        # since every action offered by the menu costs an ACTION, spending it
        # left bonus_actions untouched at 1 — so this returned True forever and
        # the turn never ended. A live combat ran 355 iterations across 30 rounds
        # with the stall-breaker firing on every single turn.
        #
        # Bonus actions are not yet offered as separate choices, so counting
        # them here can only ever produce a turn that cannot end. When bonus
        # actions become selectable this needs to consider whether an
        # AFFORDABLE action of either kind actually remains.
        return entity.action_economy.actions.normalized_score > 0

    def _advance_turn(self):
        """
        Advance to next combatant in initiative order.

        **OPTIMIZED (2026-01-03):** Uses dnd_engine's action_economy.reset() and enables
        TURN_START event triggers for condition durations.

        Process:
        1. Increment current_turn_index
        2. If wrapped around, new round (reset action economy via dnd_engine)
        3. Trigger TURN_START events for condition processing
        4. Skip unconscious/dead combatants
        """
        self.combat_state["current_turn_index"] += 1

        # Check if new round
        if self.combat_state["current_turn_index"] >= len(self.combat_state["initiative_order"]):
            self._begin_new_round()

        # Skip combatants who are down — but a DYING PLAYER still gets its death
        # saving throw at the start of its turn, so it must not be skipped
        # silently. This loop used to advance past anyone at 0 HP, which bypassed
        # the death-save hook in the main loop entirely.
        #
        # Bounded, because "everyone still standing is down" is reachable (a lone
        # hero drops while a hostile lives) and an unbounded while-loop then spins
        # forever: this cost 1001 iterations and an "unknown" outcome the first
        # time death saves were wired without touching it.
        for _ in range(len(self.combat_state["initiative_order"]) + 1):
            actor = self._get_current_actor()
            if not self._is_combatant_dead(actor):
                return

            # Dying player: roll the save, then move on. Once dead or stable the
            # save is a no-op and this simply advances.
            self._roll_death_save_for(actor)
            if not self._is_combatant_dead(actor):
                # A natural 20 revived them mid-skip; it is their turn.
                return

            self.combat_state["current_turn_index"] += 1
            if self.combat_state["current_turn_index"] >= len(self.combat_state["initiative_order"]):
                # A round boundary crossed while SKIPPING must reset the economy
                # too. My first version only bumped `round_number` here, so once a
                # combatant died and the skip loop started wrapping the round,
                # nothing was ever reset again: every survivor's attack was refused
                # for "no action available" forever. Measured: 496 rounds, 978
                # refusals, outcome `unknown`, with a live goblin and a 12 HP hero
                # unable to touch each other.
                self._begin_new_round()

    def _begin_new_round(self) -> None:
        """
        Start a new round: reset every combatant's action economy.

        Extracted because there are TWO paths that cross a round boundary — the
        normal advance and the skip loop above — and only one of them used to
        reset. A round that begins without resetting the economy is a permanent
        stalemate.
        """
        self.combat_state["current_turn_index"] = 0
        self.combat_state["round_number"] += 1

        # Movement is a per-turn budget like the action economy, so it resets with
        # the round. Without this a character could only ever move once per fight.
        self._reset_movement()

        # Reactions too: each combatant gets one opportunity attack per round, and
        # without a reset the first one spent would be the last of the whole fight.
        rules = self._rules()
        if rules is not None:
            rules.reset_reactions()

        for char_id in self.combat_state["active_combatants"]:
            entity = self.dnd_wrapper.entities.get(char_id)
            if entity and hasattr(entity, 'action_economy'):
                # Plan 1.2: ActionEconomy has no reset(); it is reset_all_costs().
                entity.action_economy.reset_all_costs()

                # TODO: Trigger TURN_START events for conditions with turn-based
                # duration (e.g. Blinded, Stormlight Infused).

            char_state = self.combat_state["combatant_states"].get(char_id)
            if char_state is not None:
                char_state["actions_remaining"] = 1
                char_state["bonus_actions_remaining"] = 1
                char_state["reaction_available"] = True

        # Tick class features at round start (durations, conditions, etc.)
        try:
            class_feat_engine = self.dnd_wrapper.class_feature_engine(
                combat_state=self.combat_state
            )
            for char_id in self.combat_state["active_combatants"]:
                class_feat_engine.tick_round(char_id)
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to tick class features: {e}")

        self.logger.info(f"🔄 Round {self.combat_state['round_number']} begins")
        print(f"\n{'='*60}")
        print(f"  🔄 ROUND {self.combat_state['round_number']}")
        print(f"{'='*60}")

    def _is_combat_over(self) -> bool:
        """Check if combat should end"""
        ended, reason = self._check_end_conditions()

        # Add detailed logging
        self.logger.debug(f"🔍 _is_combat_over check: ended={ended}, reason={reason}")

        if ended:
            self.combat_state["end_reason"] = reason
            self.logger.info(f"⚔️ Combat ending: {reason}")
            return True

        return False

    def _check_end_conditions(self) -> Tuple[bool, Optional[str]]:
        """
        Check end conditions.

        Hostiles: out at 0 HP. Players: out only once DEAD or STABLE — at 0 HP
        they are dying and a natural 20 or an ally's heal can still bring them
        back, so ending the encounter there is wrong and skipped death saves
        entirely.

        (An earlier docstring here claimed dnd_engine "enables proper D&D 5e death
        saves". It does not — its Health block has no death-save API at all.
        `CharacterManager.roll_death_save()` is the authority.)

        Returns:
            (combat_ended: bool, reason: str)
        """
        # Log combatant states
        self.logger.debug(f"🔍 Checking end conditions:")
        self.logger.debug(f"   Total combatants: {len(self.combat_state['combatant_states'])}")

        # Check all hostiles defeated
        hostile_ids = [
            cid for cid, state in self.combat_state["combatant_states"].items()
            if state["is_hostile"]
        ]

        self.logger.debug(f"   Hostiles: {hostile_ids}")

        # Use dnd_engine's authoritative health system
        hostile_dead_status = {}
        for hid in hostile_ids:
            is_dead = self._is_combatant_dead(hid)
            hostile_dead_status[hid] = is_dead
            self.logger.debug(f"      {hid}: dead={is_dead}")

        all_hostiles_dead = all(hostile_dead_status.values()) if hostile_ids else False

        self.logger.debug(f"   All hostiles dead: {all_hostiles_dead}")

        if all_hostiles_dead and hostile_ids:  # Added check for empty hostile_ids
            return (True, "all_hostiles_defeated")

        # Check all players out of the fight (dead or stable — NOT merely at 0 HP)
        player_ids = [
            cid for cid, state in self.combat_state["combatant_states"].items()
            if not state["is_hostile"]
        ]

        self.logger.debug(f"   Players: {player_ids}")

        player_out_status = {}
        for pid in player_ids:
            is_out = self._is_out_of_the_fight(pid)
            player_out_status[pid] = is_out
            self.logger.debug(f"      {pid}: out={is_out}")

        all_players_out = all(player_out_status.values()) if player_ids else False

        self.logger.debug(f"   All players out: {all_players_out}")

        if all_players_out and player_ids:  # Added check for empty player_ids
            return (True, "all_players_defeated")

        return (False, None)

    def _determine_outcome(self) -> str:
        """Determine combat outcome"""
        reason = self.combat_state.get("end_reason", "unknown")

        if reason == "all_hostiles_defeated":
            return "victory"
        elif reason == "all_players_defeated":
            return "defeat"
        elif reason == "fled":
            return "fled"
        else:
            return "unknown"

    def _get_current_actor(self) -> str:
        """Get char_id of current actor from initiative order"""
        idx = self.combat_state["current_turn_index"]
        return self.combat_state["initiative_order"][idx]["char_id"]

    def _is_player(self, char_id: str) -> bool:
        """Check if char_id is a player character"""
        return not self.combat_state["combatant_states"][char_id]["is_hostile"]

    def _is_combatant_dead(self, char_id: str) -> bool:
        """
        Is this combatant at 0 HP?

        The name is historical and slightly wrong: for a PLAYER, 0 HP means
        *dying*, not dead. Use `_is_out_of_the_fight()` when deciding whether the
        encounter is over.

        (A previous docstring claimed "D&D 5e death save mechanics are handled
        entirely by dnd_engine". They are not — the engine has no death-save API.
        See `_roll_death_save_for()`.)

        Returns:
            True if the combatant is at or below 0 HP.
        """
        entity = self.dnd_wrapper.entities[char_id]
        # Get constitution modifier from entity (modifier is a property, not a method)
        constitution_mod = entity.ability_scores.constitution.modifier
        # Get current HP using dnd_engine's get_total_hit_points method
        current_hp = entity.health.get_total_hit_points(constitution_mod)

        # LOG DETAILED HP CHECK
        self.logger.debug(f"      💊 HP check for {char_id}:")
        self.logger.debug(f"         Constitution modifier: {constitution_mod}")
        self.logger.debug(f"         entity.health.damage_taken: {entity.health.damage_taken}")
        self.logger.debug(f"         Total HP: {current_hp}")
        self.logger.debug(f"         Is dead/unconscious: {current_hp <= 0}")

        # Dead/unconscious if current HP <= 0
        return current_hp <= 0

    def _roll_death_save_for(self, char_id: str) -> Optional[Dict[str, Any]]:
        """
        Roll one death saving throw for a downed PLAYER (5e: start of its turn).

        Monsters do not make death saves — a monster at 0 HP is simply dead — so
        this is players only.

        Authority is `CharacterManager.roll_death_save()`, which implements RAW:
        DC 10, three successes stabilise, three failures kill, natural 20 revives
        at 1 HP, natural 1 counts as two failures. Note that `dnd_engine` has NO
        death-save support whatsoever (grep its Health block) — two docstrings in
        this file claimed "death saves are handled entirely by dnd_engine", which
        was simply untrue and is why the mechanic silently did not exist.

        It reads `character.hit_points["current"]`, so `_sync_hp_from_engine()`
        must have written the record first, or every call returns
        `{"skipped": "character is conscious"}`.
        """
        if self.combat_state["combatant_states"].get(char_id, {}).get("is_hostile"):
            return None

        character = self.character_manager.characters.get(char_id)
        if character is None:
            return None
        # `is True` — see _is_out_of_the_fight on the Mock() hazard.
        if (getattr(character, "is_dead", False) is True
                or getattr(character, "is_stable", False) is True):
            return None
        if not isinstance(getattr(character, "hit_points", None), dict):
            # A Mock or a malformed character: no sheet to roll against.
            return None

        # The record must reflect the engine before the save can fire.
        self._sync_hp_from_engine()

        result = self.character_manager.roll_death_save(char_id)
        if not isinstance(result, dict) or "roll" not in result:
            return result

        state = self.combat_state["combatant_states"].get(char_id, {})
        if result.get("revived"):
            # Back on 1 HP: tell the engine too, or it still reports 0 and the
            # combatant is skipped again next turn.
            self._heal_engine_to(char_id, 1)
            state["hp_current"] = 1
            print(f"\n✨ {character.name} rolls a 20 and rises at 1 HP!")
        elif result.get("dead"):
            print(f"\n☠️  {character.name} has died "
                  f"({result.get('failures')} failed death saves).")
        elif result.get("stable"):
            print(f"\n🛡️  {character.name} is stable but unconscious.")
        else:
            print(f"\n🎲 {character.name} death save: rolled {result['roll']} — "
                  f"{result.get('successes', 0)}✓ / {result.get('failures', 0)}✗")

        self.combat_state.setdefault("death_saves", []).append(
            {"round": self.combat_state["round_number"], "actor": char_id, **result})
        return result

    def _heal_engine_to(self, char_id: str, hp: int) -> None:
        """Set a combatant's engine HP to `hp` (used when a nat 20 revives)."""
        entity = self.dnd_wrapper.entities.get(char_id)
        if entity is None:
            return
        try:
            current = self.dnd_wrapper.get_entity_current_hp(entity)
            if current < hp:
                entity.health.heal(hp - current)
        except Exception as e:
            self.logger.warning(f"⚠️ Could not revive {char_id} in the engine: {e}")

    def _is_out_of_the_fight(self, char_id: str) -> bool:
        """
        Can this combatant no longer influence the encounter?

        Distinct from `_is_combatant_dead()` (which is really "is at 0 HP"): a
        player at 0 HP is *dying* and can still be revived by a nat 20 or a heal,
        so the encounter is NOT over. It is over for them only once they are dead
        or stably unconscious.
        """
        if self.combat_state["combatant_states"].get(char_id, {}).get("is_hostile"):
            return self._is_combatant_dead(char_id)

        character = self.character_manager.characters.get(char_id)
        if character is not None:
            # `is True`, not truthiness: these flags must be real booleans. A
            # Mock() character auto-creates `is_dead` as a truthy Mock attribute,
            # which silently reported every player as dead and ended combat on
            # round 1 — the same mock hazard plan 1.3 exists to eliminate.
            if getattr(character, "is_dead", False) is True:
                return True
            if getattr(character, "is_stable", False) is True:
                return True
        return False

    def _log_combat_action(self, action: Dict, result: Dict):
        """Log action to combat log"""
        self.combat_state["combat_log"].append({
            "round": self.combat_state["round_number"],
            "actor": action["actor"],
            "action_type": action["action_type"],
            "target": action.get("target"),
            "result": result
        })

    def _display_combat_start(self):
        """Display combat start message"""
        print("\n" + "="*60)
        print("  ⚔️  COMBAT BEGINS!")
        print("="*60)

        # Show initiative order
        print("\n📊 Initiative Order:")
        for entry in self.combat_state["initiative_order"]:
            char_name = self.character_manager.characters[entry["char_id"]].name
            print(f"  {entry['initiative']}: {char_name}")

        print("\n" + "="*60)

    def _build_npc_context(self, npc_char_id: str) -> Dict:
        """
        Build context for NPC AI decision.

        **SIMPLIFIED (2026-01-03):** Uses dnd_engine HP exclusively and dynamically discovers
        available actions from ACTION_REGISTRY (enables NPCs to use Roshar abilities automatically).

        Args:
            npc_char_id: NPC character ID

        Returns:
            Context dict for NPC AI with available actions and targets
        """
        npc_char = self.character_manager.characters[npc_char_id]
        entity = self.dnd_wrapper.entities[npc_char_id]

        # Get HP from dnd_engine
        con_mod = entity.ability_scores.constitution.modifier
        npc_hp = entity.health.get_total_hit_points(con_mod)
        # get_max_hit_dices_points() omits max_hit_points_bonus, which plan 1.7
        # uses to reconcile to the authored max_hp -- so it under-reports.
        npc_max_hp = self.dnd_wrapper.get_entity_max_hp(entity)

        # Dynamically get available actions — but only ones THIS NPC can actually
        # take. Two independent filters, and both are needed.
        #
        # 1. `is_offerable`: five of nine registered actions needed a parameter
        #    nothing supplied (move/end_position, progression_healing/healing_amount,
        #    ...). Offering them wasted 15 of 28 NPC actions in one live encounter:
        #    each was refused, each cost a real LLM call, and the actor kept its
        #    economy so the turn loop spun until the stall-breaker forced it along.
        #
        # 2. `_character_meets_requirements`: offerability is actor-INDEPENDENT, so
        #    it says yes to all four Surges for everyone. A plain goblin was being
        #    told it could Lash, Soulcast, Illuminate and heal with Progression —
        #    four of seven menu entries, every one cancelled by the surge's own
        #    `_validate` for having no Radiant Order, no Surgebinding level and no
        #    Stormlight. Exactly the harm filter 1 exists to prevent, reintroduced
        #    one layer down.
        from components.combat.action_registry import is_offerable

        available_actions = [
            action_type
            for action_type, metadata in self.action_resolver.ACTION_REGISTRY.items()
            if (is_offerable(action_type) and
                self._can_character_afford_action(npc_char_id, metadata) and
                self._character_meets_requirements(npc_char, metadata,
                                                   action_type))
        ]

        return {
            "npc": npc_char,
            "npc_hp": npc_hp,
            "npc_max_hp": npc_max_hp,
            "available_targets": self._get_valid_targets(npc_char_id),
            "available_actions": available_actions,  # Dynamic action discovery
            "allies": self._get_allies(npc_char_id),
            "enemies": self._get_enemies(npc_char_id),
            "round_number": self.combat_state["round_number"]
        }

    def _get_valid_targets(self, char_id: str) -> List[str]:
        """
        Get list of valid targets for character.

        **OPTIMIZED (2026-01-03):** Uses entity.health for proper death checks and enables
        optional range/line of sight validation via entity.senses.

        Args:
            char_id: Character ID

        Returns:
            List of valid target character IDs
        """
        entity = self.dnd_wrapper.entities.get(char_id)
        is_hostile = self.combat_state["combatant_states"][char_id]["is_hostile"]

        targets = []
        for cid, state in self.combat_state["combatant_states"].items():
            if cid == char_id:
                continue  # Can't target self

            # Use dnd_engine health check for proper death state
            if self._is_combatant_dead(cid):
                continue  # Can't target dead/unconscious

            # Hostiles target players, players target hostiles
            if is_hostile != state["is_hostile"]:
                # TODO: Optional range/line of sight check
                # if entity and hasattr(entity, 'senses'):
                #     target_entity = self.dnd_wrapper.entities.get(cid)
                #     if target_entity and entity.senses.can_see(target_entity):
                #         targets.append(cid)
                # else:
                #     targets.append(cid)

                targets.append(cid)

        return targets

    def _get_allies(self, char_id: str) -> List[str]:
        """Get list of allies (same hostility status)"""
        is_hostile = self.combat_state["combatant_states"][char_id]["is_hostile"]

        return [
            cid for cid, state in self.combat_state["combatant_states"].items()
            if cid != char_id and state["is_hostile"] == is_hostile
        ]

    def _get_enemies(self, char_id: str) -> List[str]:
        """Get list of enemies (opposite hostility status)"""
        return self._get_valid_targets(char_id)

    def _get_fallback_action(self, npc_char_id: str) -> Dict:
        """Get fallback action if AI decision fails"""
        targets = self._get_valid_targets(npc_char_id)

        if targets:
            return {
                "actor": npc_char_id,
                "action_type": "attack",
                "target": targets[0],  # Attack first valid target
                "weapon": "unarmed"
            }
        else:
            return {
                "actor": npc_char_id,
                "action_type": "dodge"
            }
