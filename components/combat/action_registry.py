"""
Combat Action Registry - Modular Action Definitions

This file defines all available combat actions for the Roshar D&D combat system.
Actions are registered here with metadata for generic discovery and validation.

**Design Philosophy:**
- D&D 5e actions use dnd_engine native implementations
- Roshar-specific actions implemented as custom Action classes
- Registry enables metadata-driven discovery (no hardcoded action lists)

**Expansion Plan:**
- Phase 3: Minimal registry (7 core actions)
- Post-Phase 3: Full Surge abilities (~30+ actions)
- See: docs/ROSHAR_COMBAT_MECHANICS_INTEGRATION.md for complete Surge list
"""

from typing import Dict, Any
from dnd.actions import Attack, Move
from dnd.conditions import Dashing, Dodging
from dnd.core.base_conditions import Duration, DurationType

# Import Roshar actions (to be implemented in Phase 3)
# Placeholder imports - these will be implemented
try:
    from components.combat.roshar_actions import (
        Lashing,
        ShardbladeAttack,
        ProgressionHealing
    )
    ROSHAR_ACTIONS_AVAILABLE = True
except ImportError:
    # Fallback if roshar_actions.py not yet implemented
    ROSHAR_ACTIONS_AVAILABLE = False
    Lashing = None
    ShardbladeAttack = None
    ProgressionHealing = None


# ============================================================================
# MINIMAL INITIAL REGISTRY (Phase 3)
# ============================================================================

ACTION_REGISTRY: Dict[str, Dict[str, Any]] = {
    # ========================================================================
    # D&D 5e STANDARD ACTIONS (via dnd_engine)
    # ========================================================================

    "attack": {
        "type": "dnd_action",
        "action_class": Attack,
        "description": "Attack with weapon",
        "params": ["target_entity_uuid", "weapon_slot"],
        "cost_type": "actions",
        "cost": 1,
        "requires": None
    },

    "move": {
        "type": "dnd_action",
        "action_class": Move,
        "description": "Move to new position",
        "params": ["end_position"],
        "cost_type": "movement",
        "cost": None,  # Variable based on distance
        "requires": None
    },

    # ========================================================================
    # D&D 5e STANDARD CONDITIONS (via dnd_engine)
    # ========================================================================

    "dash": {
        "type": "dnd_condition",
        "condition_class": Dashing,
        "description": "Double movement speed",
        "cost_type": "actions",
        "cost": 1,
        "requires": None,
        "params": []
    },

    "dodge": {
        "type": "dnd_condition",
        "condition_class": Dodging,
        "description": "Impose disadvantage on attacks against you",
        "cost_type": "actions",
        "cost": 1,
        "requires": None,
        "params": []
    },
}


# Add Roshar actions if available
if ROSHAR_ACTIONS_AVAILABLE:
    ROSHAR_ACTION_ENTRIES = {
        # ====================================================================
        # ROSHAR-SPECIFIC ACTIONS (Custom implementations)
        # ====================================================================

        "lashing": {
            "type": "roshar_action",
            "action_class": Lashing,
            "description": "Manipulate gravity (Windrunner/Skybreaker)",
            "params": ["target_entity_uuid", "lashing_type", "target_direction"],
            "cost_type": "actions",
            "cost": 1,
            "stormlight_cost": 1,
            "requires_order": ["Windrunner", "Skybreaker"],
            "min_surgebinding_level": 1,
            "surge_type": "Gravitation"
        },

        "shardblade_attack": {
            "type": "roshar_equipment",
            "action_class": ShardbladeAttack,
            "description": "Attack with Shardblade (soul damage)",
            "params": ["target_entity_uuid"],
            "cost_type": "actions",
            "cost": 1,
            "requires": "shardblade_summoned"
        },

        "progression_healing": {
            "type": "roshar_action",
            "action_class": ProgressionHealing,
            "description": "Heal wounds with Progression (Edgedancer/Truthwatcher)",
            "params": ["target_entity_uuid", "healing_amount"],
            "cost_type": "actions",
            "cost": 1,
            "stormlight_cost": 2,
            "requires_order": ["Edgedancer", "Truthwatcher"],
            "min_surgebinding_level": 2,
            "surge_type": "Progression"
        }
    }

    ACTION_REGISTRY.update(ROSHAR_ACTION_ENTRIES)


# ============================================================================
# FUTURE EXPANSION (Post-Phase 3)
# ============================================================================
"""
Planned additions (~30+ actions total):

GRAVITATION SURGE (Windrunner, Skybreaker):
- full_lashing: Reverse personal gravity completely
- reverse_lashing: Create gravity source on object
- gravitation_jump: Launch into air with partial lashing

ADHESION SURGE (Windrunner, Bondsmith):
- adhesion_bind: Stick objects together
- adhesion_shield: Create pressure barrier
- adhesion_climb: Stick to surfaces

DIVISION SURGE (Dustbringer, Skybreaker):
- division_blast: Disintegrate object
- division_flame: Create controlled fire
- friction_manipulation: Reduce friction

PROGRESSION SURGE (Edgedancer, Truthwatcher):
- regrowth_major: Heal critical wounds (3d8+mod)
- regrowth_minor: Heal light wounds (1d8+mod)
- life_sense: Detect living creatures

TRANSFORMATION SURGE (Lightweaver, Elsecaller):
- soulcasting_stone: Transform to stone
- soulcasting_smoke: Transform to smoke
- soulcasting_fire: Transform to fire

TRANSPORTATION SURGE (Elsecaller, Willshaper):
- elsecalling: Teleport through Cognitive Realm
- cognitive_step: Short-range teleport (30 ft)

ILLUMINATION SURGE (Lightweaver, Truthwatcher):
- illusion_visual: Create visual illusion
- illusion_sound: Create auditory illusion
- illusion_full: Create full sensory illusion

TENSION SURGE (Stoneward, Willshaper):
- tension_harden: Increase object durability
- tension_soften: Weaken object structure

COHESION SURGE (Stoneward, Dustbringer):
- cohesion_mold: Shape stone/crystal
- cohesion_shatter: Break crystalline structures

SPIRITUAL ADHESION (Bondsmith - unique):
- spiritual_connection: Form Connection bond
- spiritual_healing: Heal spirit/Connection damage

SHARDPLATE ACTIONS:
- shardplate_summon: Summon living Shardplate (4th Ideal)
- shardplate_repair: Repair Shardplate with Stormlight
- shardplate_strength: Enhanced strength burst (+4 STR for 1 turn)

SHARDBLADE ACTIONS:
- shardblade_summon: Summon Shardblade (1 Bonus Action)
- shardblade_dismiss: Dismiss to mist (Free Action)
- shardblade_form_change: Change living blade form (Bonus Action)

VOIDBINDING (Fused - enemy abilities):
- voidbinding_corruption: Spread Voidlight corruption
- gravity_spren: Manipulate gravity (similar to Lashing)
- destruction_surge: Enhanced Division-like power

See docs/ROSHAR_COMBAT_MECHANICS_INTEGRATION.md for complete specifications.
"""


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_actions_by_type(action_type: str) -> Dict[str, Dict]:
    """Get all actions of specified type."""
    return {
        name: metadata
        for name, metadata in ACTION_REGISTRY.items()
        if metadata.get("type") == action_type
    }


def get_actions_for_radiant_order(order: str) -> Dict[str, Dict]:
    """Get all actions available to specific Radiant Order."""
    return {
        name: metadata
        for name, metadata in ACTION_REGISTRY.items()
        if ("requires_order" in metadata and
            order in metadata["requires_order"])
    }


def get_actions_requiring_stormlight() -> Dict[str, Dict]:
    """Get all actions that consume Stormlight."""
    return {
        name: metadata
        for name, metadata in ACTION_REGISTRY.items()
        if "stormlight_cost" in metadata
    }


def get_available_action_types() -> list:
    """Get list of all registered action types."""
    return list(ACTION_REGISTRY.keys())


def get_action_metadata(action_type: str) -> Dict[str, Any]:
    """Get metadata for specific action type."""
    return ACTION_REGISTRY.get(action_type, {})
