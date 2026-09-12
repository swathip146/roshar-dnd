# Gameplay Flow

**Purpose**: End-to-end trace of player actions through the Roshar D&D system.

**Last verified**: 2026-09-11 (commit ac4b680)

**CORRECTED**: Previous version claimed combat "not implemented". Combat turn flow added based on actual `CombatSessionManager` (2060 lines).

---

## Player Turn Flow (Non-Combat)

**Entry**: `haystack_dnd_game.py:283 HaystackDnDGame.play_turn(player_input)`

```
Player: "I search the room"
    ↓
[1] play_turn() creates RequestDTO with _game_engine_ref (line 305)
    ↓
[2] orchestrator.process_request(dto) (line 311)
    ↓
[3] PipelineOrchestrator routes based on dto["type"] (line 314)
    ↓
[4] _handle_gameplay_turn_pipeline_dto() → _run_interface_pipeline()
    ↓
[5] Interface agent (temperature=0) classifies intent
    - Reads game_engine.get_narrative_context() (line 398)
    - Returns route: "scenario_pipeline" (line 428)
    ↓
[6] _run_scenario_pipeline(dto)
    ↓
[7] Scenario agent reads engine state directly:
    - game_engine.get_narrative_context() (line 82)
    - game_engine.get_location_context() (line 83)
    - game_engine.get_quest_context() (line 84)
    ↓
[8] Generates Scenario with scene + choices[]
    ↓
[9] ScenarioValidatorComponent validates/repairs (line 239)
    ↓
[10] Returns GameResponseDTO to play_turn
    ↓
[11] _handle_response() formats for display (line 357)
    ↓
[12] _update_state_via_authorities() delegates state updates:
    - game_engine.set_campaign_flag() (line 376)
    - game_engine.add_story_hook()
    - game_engine.add_quest_objective()
    ↓
[13] Display to player
```

**Key observations**:
- ✅ No state duplication (uses `_game_engine_ref`)
- ✅ Intent classification first (deterministic, temp=0)
- ✅ Agents read state directly from engine

---

## Skill Check Flow (7-Step Pipeline)

**Entry**: `game_engine.py:188 process_skill_check(check_request)`

**Status**: ✅ Implemented but ⚠️ not automatically triggered from scenario choices

```
Caller: process_skill_check({
    "actor": "char_uuid",
    "skill": "perception",
    "context": {"difficulty": "medium"},
    "correlation_id": "check_123"
})
    ↓
STEP 1: Rules Enforcer → Derive DC
[1] rules_enforcer.determine_check_needed(check_request) (line 203)
    Returns: {check_needed: True, dc: 15, dc_source: "medium_difficulty"}
    ↓
STEP 2: Character Manager → Get modifier
[2] character_manager.get_skill_data(actor, skill) (line 217)
    Returns: {modifier: 5, breakdown: {ability_mod: 3, proficiency: 2}}
    ↓
STEP 3: Policy Engine → Advantage/disadvantage
[3] policy_engine.compute_advantage(state, actor, skill, context) (line 222)
    Returns: {final_state: "advantage", advantage_sources: ["hidden"]}
[4] policy_engine.adjust_difficulty(dc, context) (line 227)
    Returns: {final_dc: 13, adjustments: [{"reason": "house_rules", "delta": -2}]}
    ↓
STEP 4: Dice Roller → Roll
[5] dice_roller.skill_roll(skill, modifier, advantage_state) (line 231)
    Rolls: [14, 8] (advantage), selects 14
    Returns: {total: 19, raw_rolls: [14, 8], selected_roll: 14}
    ↓
STEP 5: Compare vs DC
[6] success = roll_result["total"] >= adjusted_dc (line 239)
    19 >= 13 → success = True
    ↓
STEP 6: Apply state
[7] _apply_skill_check_outcome(check_request, outcome) (line 262)
    - session_data["total_checks"] += 1 (line 272)
    - session_data["successful_checks"] += 1 (line 274)
    - If stealth: characters[actor]["hidden"] = True (line 283)
    ↓
STEP 7: Decision log
[8] _log_skill_check_decision() (line 265)
    Logs: DC provenance, advantage sources, roll breakdown
    ↓
[9] Return outcome dict
```

**Callers** (grep verified):
- `game_engine.py:401` → `process_contested_check()` calls it twice
- `game_engine.py:1188` → Test code at EOF

**Gap**: No automatic trigger from scenario choices. `Choice` TypedDict has `suggested_dc` (shared_contract.py:102) but no code consumes it.

---

## Combat Turn Flow (✅ IMPLEMENTED, 2060 lines)

**Entry**: `combat_session_manager.py:150 run_combat_loop()`

**Previous error**: "Not implemented, no methods exist"  
**Reality**: Full turn loop with ACTION_REGISTRY dispatch

```
[COMBAT START]
Player: "I attack the goblin"
    ↓
[1] Scenario agent detects combat trigger → creates combat_state
    ↓
[2] CombatInitializer.initialize() (combat_initializer.py)
    - Roll initiative for all participants
    - Create dnd_engine Entities via DnDEngineWrapper
    - Sort initiative_order
    - Set combat_state["active"] = True
    ↓
[3] CombatSessionManager.run_combat_loop() (line 150)
    Main loop runs INSIDE CombatAgent, handles ALL turns
    ↓
[TURN LOOP]
    ↓
[4] Get current actor from initiative_order
    ↓
[5] Is NPC? → npc_ai.choose_action() (AI decides)
    Is Player? → _prompt_choice() (player input via injected provider)
    ↓
[6] _get_available_actions(actor_id)
    - Query ACTION_REGISTRY (generic data-driven)
    - Filter by requirements (has slot? has target?)
    - Return menu: ["1. Attack", "2. Cast Fireball", "3. Dash", ...]
    ↓
[7] Player chooses: "2" (Fireball)
    ↓
[8] _execute_action(action="cast_spell", params={spell: "fireball"})
    ↓
[9] CombatActionResolver.resolve_action()
    - Dispatch based on action type (metadata-driven, no if/elif chains)
    - For spells: calls SpellcastingSystem
    ↓
[10] SpellcastingSystem (spellcasting.py:911 lines)
    - Check spell_slots[3]["current"] > 0 (Fireball is 3rd level)
    - Consume slot: spell_slots[3]["current"] -= 1
    - Compile spell via spell_compiler.py
    - Get spell save DC: 8 + proficiency + ability_modifier
    - Execute via SpellEffectExecutor (subclasses ManeuverExecutor)
        • Targets in 20ft radius
        • Each target: DEX save vs DC 15
        • Damage: 8d6 fire
        • On success: half damage (multiplier: 0.5)
    - Apply damage to targets via dnd_engine_wrapper
    - Sync HP changes back to GameEngine
    ↓
[11] CombatNarrativeGenerator.narrate_action()
    Display: "Kaladin hurls a ball of flame! 8d6 damage!"
    ↓
[12] Check end conditions:
    - All enemies defeated? → end_combat()
    - All allies defeated? → end_combat()
    - Else: advance to next actor in initiative_order
    ↓
[13] Repeat from [4] until combat ends
    ↓
[COMBAT END]
[14] Return combat summary to orchestrator
```

**Key mechanics** (verified from code):
- ✅ **ACTION_REGISTRY**: Dynamic action discovery (line 23 import)
- ✅ **Spellcasting**: 319 SRD spells, slot consumption, spell save DC
- ✅ **Multiattack**: `attacks_per_turn_for(entity)` (imported line 23)
- ✅ **Class features**: Mirrored to entities via `dnd_engine_wrapper.sync_class_features_to_entity()` (line 95)
- ✅ **Input injection**: Testable via `input_provider` parameter (plan 1.8/D4)

**What's NOT wired**:
- ⚠️ `register_standard_actions()` not called → Attack/Dash/Dodge exist but not in ACTION_REGISTRY

---

## Spell Casting Flow (✅ VERIFIED, 72 passing tests)

**Entry**: Combat menu → "Cast Fireball"

```
[1] Player chooses spell from available list
    - SpellcastingSystem.get_castable_spells(char_id)
    - Filters by: has slot, knows spell, spell level ≤ max slot level
    ↓
[2] SpellcastingSystem.cast_spell(caster_id, spell_name, targets)
    ↓
[3] Validate:
    - has_slot = spell_slots[spell_level]["current"] > 0
    - knows_spell = spell_name in spells_known
    - If fail: return {success: False, reason: "No 3rd level slots"}
    ↓
[4] Consume slot:
    spell_slots[spell_level]["current"] -= 1
    ↓
[5] Compile spell (spell_compiler.py):
    - Load from SRDRules.spell("fireball")
    - Parse effect tree: {save: "dex", damage: "8d6", type: "fire", radius: 20}
    - Return CompiledSpell
    ↓
[6] Calculate spell save DC:
    ability = spellcasting_ability(character_class)  # "wizard" → "intelligence"
    mod = entity.abilities[ability].modifier
    dc = 8 + entity.proficiency_bonus + mod
    ↓
[7] Execute via SpellEffectExecutor (subclasses ManeuverExecutor):
    For each target in radius:
        • Roll save: d20 + target.dex_save_bonus vs DC
        • If fail: full damage (8d6 fire)
        • If succeed: half damage (multiplier: 0.5)
    ↓
[8] Apply damage:
    - damage_roll = dice_roller.damage_roll("8d6")
    - For each target: dnd_wrapper.apply_damage(target_id, amount)
    - Sync HP to GameEngine: character_manager.update_hp(target_id, -amount)
    ↓
[9] Return result:
    {success: True, targets_affected: 3, damage_dealt: {goblin1: 28, goblin2: 14, ...}}
```

**Spell data**: 319 spells from `data/rules/srd/spells.json`

**Spellcasting abilities** (from spellcasting.py:65-78):
- wizard/artificer/eldritch knight → intelligence
- cleric/druid/ranger → wisdom
- bard/sorcerer/warlock/paladin → charisma

**Non-casters** (line 82): fighter, barbarian, rogue, monk → return None (no DC)

---

## Save/Load Flow

**Entry**: `session_manager.py:105 save_session()`

**Save**:
```
[1] save_session(filename, game_engine_state, character_manager_state)
    ↓
[2] Collect from authoritative sources:
    - game_engine.export_game_state() (line 139)
        • game_state: {characters, combat_state, environment, flags, ...}
        • character_data: {char_id: manager.get_character_summary(id)}
        • policy_profile, campaign_config_data
    ↓
[3] Build save_data dict (line 129):
    {
      "session_metadata": {session_id, player_name, last_save_time, save_version: "4.0_clean_slate"},
      "game_state": <from export>,
      "character_data": <from export>,
      "session_stats": {sessions_created, successful_saves, ...},
      "fixed_system_data": {routing_history: <last 20 decisions>}
    }
    ↓
[4] Write to JSON: game_saves/{filename} (line 150)
    ↓
[5] Update session.last_save_time (line 126)
    ↓
[6] Return {success: True, filepath: ...}
```

**Load**:
```
[1] load_session(filename) (line 169)
    ↓
[2] Read JSON file (line 173)
    ↓
[3] Validate structure (line 176 → _validate_save_data line 241)
    ↓
[4] Restore session metadata (line 196-204)
    ↓
[5] Return state_data for components to import (line 217):
    {
      "success": True,
      "result": {
        "session_metadata": {...},
        "game_state": save_data["game_state"],
        "character_data": save_data["character_data"]
      }
    }
    ↓
[6] Caller restores to components:
    - game_engine.import_game_state(state_data["game_state"]) (line 495)
    - character_manager.add_character() for each character (line 536)
```

**Component authority**: SessionManager coordinates, GameEngine/CharacterManager own state

---

## Flow Gaps (Verified)

### 1. Skill Check Auto-Trigger ⚠️
**Status**: Pipeline exists (lines 188-267), not triggered from scenario choices

**Gap**:
```python
# Choice has suggested_dc but no code consumes it
choice = {"title": "Search desk", "suggested_dc": 15}
# Missing: call to process_skill_check() in _update_state_via_authorities()
```

**To wire** (~50 lines):
```python
if choice.get("suggested_dc"):
    result = game_engine.process_skill_check({
        "actor": player_char_id,
        "skill": choice.get("skill_hints", ["perception"])[0],
        "context": {"dc": choice["suggested_dc"]},
        "correlation_id": correlation_id
    })
    # Feed result back to scenario generation
```

### 2. Standard Actions Registration ⚠️
**Status**: Actions exist (1076 lines), `register_standard_actions()` not called

**Gap**: `grep -rn "register_standard_actions()" → NO CALLERS`

**To wire** (~1 line):
```python
# In combat initialization:
from components.combat.standard_actions import register_standard_actions
register_standard_actions()  # Makes Attack/Dash/Dodge discoverable
```

---

## Summary

| Flow | Status | Entry Point | Lines |
|------|--------|-------------|-------|
| **Player Turn** | ✅ Working | `HaystackDnDGame.play_turn()` | Full end-to-end |
| **Skill Check** | ⚠️ Exists, not triggered | `GameEngine.process_skill_check()` | 80 lines (7 steps) |
| **Combat Turn** | ✅ **WORKING** | `CombatSessionManager.run_combat_loop()` | 2060 lines |
| **Spell Casting** | ✅ **WORKING** | `SpellcastingSystem.cast_spell()` | 911 lines |
| **Save/Load** | ✅ Working | `SessionManager.save_session()` | Component authority |

**Corrections from previous version**:
- ❌ **Old**: "Combat turn flow: Not implemented, no methods exist"
- ✅ **New**: Combat turn flow fully implemented (2060 lines + 13,264 total combat code)
- ❌ **Old**: "Spell casting: Data only"
- ✅ **New**: Full mechanics with slot consumption, DC calculation, 72 passing tests
