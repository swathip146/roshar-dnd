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

import sys
from pathlib import Path
from typing import Dict, Any

# Add dnd_engine to path (required for dnd imports)
dnd_engine_path = Path(__file__).parent.parent.parent / "external" / "dnd_engine"
if str(dnd_engine_path) not in sys.path:
    sys.path.insert(0, str(dnd_engine_path))

from dnd.actions import Attack, Move
from dnd.conditions import Dashing, Dodging
from dnd.core.base_conditions import Duration, DurationType

# Import Roshar actions (to be implemented in Phase 3)
# Placeholder imports - these will be implemented
try:
    from components.combat.roshar_actions import (
    Illumination, Soulcast,
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

    # ========================================================================
    # 5e SPELLCASTING
    #
    # 319 SRD spells were indexed and NONE were castable: there was no `cast`
    # action here at all, so neither the player menu nor the NPC AI could ever
    # choose one, and nothing consumed `CharacterData.spell_slots` (grep found it
    # read only for the analytics summary).
    #
    # `type` is "spell_action", not "dnd_action": there is no spell system in the
    # vendored engine to delegate to (`import dnd.spells` fails, and `dnd.actions`
    # exports only Attack and Move), and a `BaseAction` subclass could not reach
    # the slot table — `_apply` sees only `Entity.get(uuid)`, while `spell_slots`
    # lives on CharacterData. The resolver dispatches this type to
    # components/combat/spellcasting.py.
    # ========================================================================

    "cast_spell": {
        "type": "spell_action",
        "action_class": None,
        "description": "Cast a spell",
        "params": ["target_entity_uuid", "spell_name", "at_level"],
        # `spell_name` MUST have a supplier or `is_offerable()` filters the whole
        # action out and casting stays unplayable — exactly what happened to four
        # of the five Surges. None means "the service picks a spell the caster
        # knows and can currently pay for" (SpellcastingService.default_spell),
        # cantrips before slots. `at_level` None means the cheapest legal slot.
        #
        # `spell_name` was MISSING from this dict while the comment above already
        # described the fix, so required_caller_params() returned ['spell_name'],
        # is_offerable() returned False, and cast_spell was excluded from both the
        # player menu (combat_session_manager.py:790) and the NPC menu (:1976).
        # All 319 SRD spells compiled and resolved correctly and NONE were castable
        # in a real session. spellcasting.py:790-791 already falls back to
        # default_spell() when the name is absent, so None is the correct value.
        "param_defaults": {"spell_name": None, "at_level": None},
        "cost_type": "actions",
        "cost": 1,
        "requires": "spellcasting",
    },

    # ========================================================================
    # INVESTED ARTS (plan 2.9)
    #
    # Mirrors cast_spell but spends Investiture Points instead of spell slots.
    # The art_name default is CRITICAL — without it, is_offerable() returns
    # False and the action is filtered out of both menus (the exact bug that
    # made cast_spell unplayable until 2026-09-11).
    # ========================================================================

    "cast_art": {
        "type": "art_action",
        "action_class": None,
        "description": "Use an Invested Art",
        "params": ["target_entity_uuid", "art_name"],
        # art_name MUST have a default or the action is not offerable
        "param_defaults": {"art_name": None},
        "cost_type": "actions",
        "cost": 1,
        "requires": "invested_arts",
    },

    # ========================================================================
    # ACTIVATED CLASS FEATURES (plan 2.10: Rage, Second Wind, Action Surge)
    #
    # These are ACTIVATED features (chosen on a turn), not passive/on-hit.
    # `ClassFeatureEngine.use()` applies their effects (heal, grant-action,
    # melee-damage-bonus). The registry entry makes them OFFERABLE in combat.
    # ========================================================================

    "rage": {
        "type": "class_feature",
        "action_class": None,
        "description": "Enter a rage (Barbarian)",
        "params": [],
        "cost_type": "bonus_actions",
        "cost": 1,
        "requires": "class_feature",
        "feature_id": "rage",
    },

    "second_wind": {
        "type": "class_feature",
        "action_class": None,
        "description": "Regain hit points (Fighter)",
        "params": [],
        "cost_type": "bonus_actions",
        "cost": 1,
        "requires": "class_feature",
        "feature_id": "second_wind",
    },

    "action_surge": {
        "type": "class_feature",
        "action_class": None,
        "description": "Take an extra action (Fighter)",
        "params": [],
        # No cost_type - it's a free action that grants an extra action
        "requires": "class_feature",
        "feature_id": "action_surge",
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
            # A basic downward Lashing is the sensible default, so the surge is
            # OFFERABLE without a caller inventing a gravity vector. See
            # `param_defaults` in is_offerable().
            "param_defaults": {"lashing_type": "basic",
                               "target_direction": (0, 0, -1)},
            "cost_type": "actions",
            "cost": 1,
            # Gravitation/Adhesion are cantrips: FREE (was an invented 1-sphere
            # cost). The key stays present (metadata contract) but 0 = no gate.
            "stormlight_cost": 0,
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
            # None means "roll 2d8 + WIS" — the RAW behaviour. The action already
            # implements that branch; nothing was passing the parameter to reach it.
            "param_defaults": {"healing_amount": None},
            "cost_type": "actions",
            "cost": 1,
            # Regrowth is a COSTED Invested Art, not a Stormlight-sphere cantrip.
            # `stormlight_cost` stays present (metadata contract) but 0; the real
            # cost is `art_level` Investiture Points, spent through the ledger and
            # gated in unusable_reason via cosmere_rules.investiture_cost().
            "stormlight_cost": 0,
            "art_level": 1,   # Regrowth (1st-level) -> 2 IP (Elsecaller: 1)
            "requires_order": ["Edgedancer", "Truthwatcher"],
            # First Ideal / 1st level, not the Second (AUDIT §4.3).
            "min_surgebinding_level": 1,
            "surge_type": "Progression"
        },

        # Plan 2.7: Lightweaver surges. Only Lashing (Windrunner/Skybreaker)
        # and Progression (Edgedancer/Truthwatcher) were registered, yet BOTH
        # shipped PCs are Lightweavers -- so the party had zero usable Surges
        # and the central fantasy of the setting never appeared in play.
        "illumination": {
            "type": "roshar_action",
            "action_class": Illumination,
            "description": "Weave light and sound into an illusion (Lightweaver/Truthwatcher)",
            "params": ["target_entity_uuid", "illusion_type"],
            "param_defaults": {"illusion_type": "figment"},
            "cost_type": "actions",
            "cost": 1,
            # Illumination is a free cantrip (IA:469). Key kept, value 0.
            "stormlight_cost": 0,
            # Fix per AUDIT_HARDCODED_SURGE_ACCURACY.md §4.4: Illumination belongs to
            # Lightweaver + Truthwatcher, not Lightweaver + Elsecaller
            "requires_order": ["Lightweaver", "Truthwatcher"],
            "min_surgebinding_level": 1,
            "surge_type": "Illumination"
        },
        "soulcast": {
            "type": "roshar_action",
            "action_class": Soulcast,
            "description": "Transform matter with Transformation (Lightweaver/Elsecaller)",
            "params": ["target_entity_uuid", "target_essence"],
            "param_defaults": {"target_essence": "smoke"},
            "cost_type": "actions",
            "cost": 1,
            # The menu Surge is the free Transformation cantrip (IA:498). The
            # costed, save-based 5th-level Soulcast Art is the class's art_level>=5
            # tier (paid in Investiture Points), not this menu entry.
            "stormlight_cost": 0,
            "requires_order": ["Lightweaver", "Elsecaller"],
            "min_surgebinding_level": 2,
            "surge_type": "Transformation"
        }
    }

    ACTION_REGISTRY.update(ROSHAR_ACTION_ENTRIES)


# ============================================================================
# STANDARD 5e ACTIONS (Grapple, Shove, Help, Ready, Hide, Search, Disengage,
# two-weapon fighting)
#
# Defined in components/combat/standard_actions.py as real `BaseAction`
# subclasses. They cannot insert themselves — this module owns ACTION_REGISTRY —
# so `register_standard_actions()` merges `STANDARD_ACTION_ENTRIES` in here, the
# same shape as the ROSHAR_ACTION_ENTRIES merge above. The call is idempotent, so
# importing standard_actions first (its own callers do) and reaching this line
# later both leave exactly one copy of each entry.
#
# Guarded like the Roshar import: a failure to import the PHB actions must not
# take the whole registry — and every action already registered above — down with
# it.
# ============================================================================
try:
    from components.combat.standard_actions import register_standard_actions

    register_standard_actions()
except ImportError:  # pragma: no cover - the module ships with the registry
    pass


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

# Parameters the resolver can always supply itself, so an action needing only these
# is offerable. Everything else has to come from the caller.
_AUTO_SUPPLIED_PARAMS = frozenset({"target_entity_uuid", "weapon_slot"})


def required_caller_params(action_type: str) -> list:
    """
    Parameters the CALLER must provide for this action, beyond the automatic ones.

    A param listed in the entry's `param_defaults` does NOT count as required: the
    resolver fills it in. That is what makes the four Surges offerable — each needed
    one flavour parameter (`lashing_type`, `illusion_type`, `target_essence`,
    `healing_amount`) that nothing in the game ever supplied, so a Windrunner could
    never choose to Lash. The action classes already had sensible defaults; the
    registry simply never passed them.
    """
    metadata = ACTION_REGISTRY.get(action_type) or {}
    defaults = metadata.get("param_defaults") or {}
    return [p for p in (metadata.get("params") or [])
            if p not in _AUTO_SUPPLIED_PARAMS and p not in defaults]


def param_defaults(action_type: str) -> Dict[str, Any]:
    """Default values the resolver should supply for this action's params."""
    metadata = ACTION_REGISTRY.get(action_type) or {}
    return dict(metadata.get("param_defaults") or {})


def is_offerable(action_type: str) -> bool:
    """
    Can this action actually be CHOSEN right now?

    Five of the nine registered actions need a parameter nothing supplies —
    `move` (end_position), `lashing` (lashing_type, target_direction),
    `progression_healing` (healing_amount), `illumination` (illusion_type) and
    `soulcast` (target_essence). They were offered anyway, to the player menu and to
    the NPC AI.

    Measured in one live encounter: **15 of 28 NPC actions were wasted** on `move`
    and `progression_healing`, each refused for a missing parameter. The fight
    dragged to 11 rounds and every wasted action still cost a real LLM call. Worse,
    an actor whose action was refused kept its economy, so the turn loop spun until
    the stall-breaker forced it along — visible as "still has actions after 4
    attempts".

    Filtering here means both consumers are fixed at once, and any action that later
    grows a real supplier becomes offerable automatically.
    """
    # An UNKNOWN action is not offerable. `required_caller_params` returns [] for a
    # name that is not in the registry, so without this check a hallucinated action
    # ("teleport_to_shadesmar") would read as perfectly usable and then fail at
    # dispatch with "Unknown action type".
    if action_type not in ACTION_REGISTRY:
        return False
    return not required_caller_params(action_type)


def offerable_actions() -> Dict[str, Dict]:
    """The registry, minus actions nobody can currently supply parameters for."""
    return {name: meta for name, meta in ACTION_REGISTRY.items()
            if is_offerable(name)}


def unusable_reason(action_type: str, actor_state: Any) -> "str | None":
    """
    Why THIS actor cannot take this action right now — or None if it can.

    `is_offerable()` is actor-independent: it only asks whether the resolver can
    supply the parameters. It says yes to all four Surges, which is correct as far
    as it goes and *badly wrong* as an action menu. A goblin has no Radiant Order,
    no Surgebinding level and no Stormlight, so `roshar_actions._validate` cancels
    every surge it declares — but the goblin was told it could Lash, Soulcast,
    Illuminate and heal with Progression anyway.

    Measured before this filter (see the probe in the sibling test): the NPC menu
    for a plain goblin was
        ['attack', 'dash', 'dodge', 'lashing', 'progression_healing',
         'illumination', 'soulcast']
    — four of seven entries unresolvable, i.e. **57% of the menu was a trap**. That
    is the same failure mode `is_offerable` was written for: 15 of 28 NPC actions in
    one live encounter went to actions the resolver refused, each burning a real LLM
    call while the actor kept its action economy, so the turn loop spun until the
    stall-breaker forced it.

    The gates checked here mirror the ones the action classes enforce:
      * `requires_order`          -> actor.radiant_order
      * `min_surgebinding_level`  -> actor.surgebinding_level
      * `stormlight_cost`         -> actor.stormlight_current
      * `requires`                -> shardblade_summoned / surgebinding / spheres

    `actor_state` may be a `CharacterData`, a dnd_engine `Entity` mirror, or a plain
    dict — anything attribute- or key-addressable. Missing state reads as absent
    (0 / None), which correctly *denies* a surge rather than silently allowing it:
    the action classes' own `hasattr` guards skip when the attribute is missing, and
    that leniency is exactly how "no Shardblade bonded" reached the menu.

    Returns a human-readable reason so the caller can log or display it.
    """
    if action_type not in ACTION_REGISTRY:
        return f"unknown action '{action_type}'"
    if not is_offerable(action_type):
        missing = ", ".join(required_caller_params(action_type))
        return f"needs caller-supplied parameter(s): {missing}"

    metadata = ACTION_REGISTRY[action_type]

    def read(attr, default=None):
        if actor_state is None:
            return default
        if isinstance(actor_state, dict):
            value = actor_state.get(attr, default)
        else:
            value = getattr(actor_state, attr, default)
        return default if value is None else value

    required_orders = metadata.get("requires_order")
    if required_orders:
        order = read("radiant_order")
        if order not in required_orders:
            return (f"requires Radiant Order {'/'.join(required_orders)}, "
                    f"actor is {order or 'not a Radiant'}")

    min_level = metadata.get("min_surgebinding_level")
    if min_level:
        level = read("surgebinding_level", 0) or 0
        if level < min_level:
            return (f"requires Surgebinding level {min_level}, "
                    f"actor has {level}")

    cost = metadata.get("stormlight_cost")
    if cost:
        stormlight = read("stormlight_current", 0) or 0
        if stormlight < cost:
            return (f"requires {cost} Stormlight, actor has {stormlight}")

    # Costed Invested Arts (plan 2.9 economy): a surge/art marked with `art_level`
    # is paid in Investiture Points, not Stormlight. The book-accurate cost comes
    # from cosmere_rules.investiture_cost(art_level, order); a drained IP pool
    # filters it off the menu, exactly as the sphere gate did for the old model.
    # A cantrip (art_level 0) is free and never reaches here.
    art_level = metadata.get("art_level")
    if art_level:
        from components.cosmere_rules import get_cosmere_rules

        order = read("radiant_order") or ""
        ip_cost = get_cosmere_rules().investiture_cost(int(art_level), order)
        if ip_cost > 0:
            ip_pool = read("investiture_points", {})
            current_ip = (int(ip_pool.get("current", 0) or 0)
                          if isinstance(ip_pool, dict) else 0)
            if current_ip < ip_cost:
                return (f"requires {ip_cost} Investiture Points, "
                        f"actor has {current_ip}")

    requires = metadata.get("requires")
    if requires == "shardblade_summoned":
        if not read("shardblade_summoned", False):
            return "requires a summoned Shardblade"
    elif requires == "surgebinding":
        if (read("surgebinding_level", 0) or 0) <= 0:
            return "requires Surgebinding"
    elif requires == "stormlight_spheres":
        if (read("stormlight_current", 0) or 0) <= 0:
            return "requires Stormlight spheres"
    elif requires == "spellcasting":
        # Same trap as the Surges, one layer up: `cast_spell` is offerable for
        # everyone (the resolver can supply every parameter), so without this a
        # goblin would be told it can cast Fireball and the service would refuse
        # it every single round. The gate lives in spellcasting.py so this module
        # does not learn about class tables or slot dicts.
        from components.combat.spellcasting import can_cast_any

        allowed, reason = can_cast_any(actor_state)
        if not allowed:
            return f"cannot cast spells: {reason}"
    elif requires == "invested_arts":
        # Same pattern: `cast_art` is offerable for everyone (the resolver can
        # supply every parameter), so without this a goblin would be offered
        # cast_art and the resolver would refuse it every round. Only actors with
        # Investiture Points can use arts.
        ip_pool = read("investiture_points", {})
        if not isinstance(ip_pool, dict):
            return "no Investiture Points"
        max_ip = int(ip_pool.get("maximum", 0) or 0)
        if max_ip <= 0:
            return "no Invested Arts capability"
        # And there must be a CASTABLE art. `_cast_art` compiles and runs an art's
        # `automation` tree; the only arts authored so far are cantrips that carry
        # no automation (they defer to surgebinding.json prose), so cast_art would
        # refuse every time — the same menu-trap the gates above exist to stop.
        # Gate on a real automation tree so cast_art becomes offerable
        # automatically once an executable art is authored.
        from components.cosmere_rules import get_cosmere_rules
        if not any(a.get("automation") for a in get_cosmere_rules().arts()):
            return "no castable Invested Art available yet"
    elif requires == "class_feature":
        # Activated class features (Rage, Second Wind, Action Surge): only offer
        # them to actors who HAVE the feature AND have uses remaining. A Fighter
        # with no Second Wind uses left, or a Wizard, must not be offered it.
        #
        # We need the ClassFeatureEngine to check uses, but we can't import it here
        # without circular imports. Instead, check if the feature is in the
        # character's features list and has uses (will be verified at resolution).
        feature_id = metadata.get("feature_id")
        if not feature_id:
            return "no feature_id specified"

        # Check if the character has this feature
        features = read("features", [])
        if not isinstance(features, list):
            return f"no {feature_id} feature"

        # Features can be stored as either strings or dicts with "id" keys
        # Feature IDs in the registry are lowercase with underscores (e.g., "second_wind")
        # Features in CharacterData.features are title case (e.g., "Second Wind")
        feature_display_name = feature_id.replace("_", " ").title()
        has_feature = False
        for f in features:
            if isinstance(f, str) and f == feature_display_name:
                has_feature = True
                break
            elif isinstance(f, dict) and f.get("id") == feature_id:
                has_feature = True
                break

        if not has_feature:
            return f"does not have {feature_id.replace('_', ' ').title()}"

        # Check if the character has uses remaining - this is approximate since we
        # can't access ClassFeatureEngine here, but we can check the character's
        # class_feature_uses dict. Note: class_feature_uses tracks SPENT uses,
        # not remaining uses. The ClassFeatureEngine (via character_manager's
        # feature_uses_left) calculates remaining = maximum - spent.
        # Here we just do a rough check - the real gating happens in use().
        # Skip the check for now and let ClassFeatureEngine.use() handle it.

    return None


def is_usable_by(action_type: str, actor_state: Any) -> bool:
    """Whether THIS actor can legally take this action. See unusable_reason()."""
    return unusable_reason(action_type, actor_state) is None


def usable_actions(actor_state: Any) -> Dict[str, Dict]:
    """
    The action menu for ONE actor: offerable AND legal for them.

    This is the function both menu builders should call —
    `CombatSessionManager._get_available_actions` (player) and
    `._build_npc_context` (NPC AI). `offerable_actions()` is the actor-independent
    half and is not safe to offer directly.
    """
    return {name: meta for name, meta in ACTION_REGISTRY.items()
            if is_usable_by(name, actor_state)}


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
