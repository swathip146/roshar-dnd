"""
Invariants — §6 of the strategy. Cheap assertions run after EVERY turn.

WHY A POST-TURN HOOK RATHER THAN PER-TEST ASSERTIONS
----------------------------------------------------
A whole class of corruption (a negative resource, a combatant with no position, two
entities on one tile) is invisible to a test that only checks its own mechanic at the
end. Running these after every turn attributes the failure to *the turn that caused
it* instead of to some later unrelated test — which is what makes a long scenario like
A-1 debuggable at all.

Each returns a list of human-readable violations; `assert_all` raises with every
violation at once, so one bad turn does not hide the next.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from config.logging_config import get_logger

logger = get_logger(__name__)

#: The 15 SRD conditions (`data/rules/srd/conditions.json`), lowercased.
SRD_CONDITIONS = {
    "blinded", "charmed", "deafened", "frightened", "grappled", "incapacitated",
    "invisible", "paralyzed", "petrified", "poisoned", "prone", "restrained",
    "stunned", "unconscious", "exhaustion",
}

#: Placeholder text that must never reach a player (I10).
PLACEHOLDER_MARKERS = ("TODO", "FIXME", "Lorem ipsum", "XXX", "<placeholder>",
                       "None None", "{}", "n/a n/a")


# --------------------------------------------------------------------------- #
# I1-I3 — hit points and resources
# --------------------------------------------------------------------------- #

def check_hp_bounds(character_manager) -> List[str]:
    """I1: 0 <= current <= maximum, and maximum stays positive."""
    problems = []
    for char_id, character in character_manager.characters.items():
        hp = getattr(character, "hit_points", None) or {}
        current, maximum = hp.get("current"), hp.get("maximum")
        if current is None or maximum is None:
            problems.append(f"{char_id}: hit_points missing current/maximum: {hp!r}")
            continue
        if maximum <= 0:
            problems.append(f"{char_id}: max HP is {maximum} (must be > 0)")
        if current < 0:
            problems.append(f"{char_id}: current HP {current} < 0")
        if current > maximum:
            problems.append(f"{char_id}: current HP {current} > max {maximum}")
        if (hp.get("temporary") or 0) < 0:
            problems.append(f"{char_id}: temporary HP {hp.get('temporary')} < 0")
    return problems


def check_resources_non_negative(character_manager) -> List[str]:
    """I2: no resource pool may go negative.

    Spell slots, Stormlight, Investiture Points, hit dice and feature uses are all
    spent by different subsystems; a negative value means a spend path skipped its
    affordability gate.
    """
    problems = []
    scalar_fields = ("stormlight_current", "investiture_points",
                     "hit_dice_remaining", "experience_points", "level")

    for char_id, character in character_manager.characters.items():
        for field in scalar_fields:
            value = getattr(character, field, None)
            if isinstance(value, (int, float)) and value < 0:
                problems.append(f"{char_id}: {field} = {value} < 0")

        slots = getattr(character, "spell_slots", None) or {}
        if isinstance(slots, dict):
            for level, count in slots.items():
                if isinstance(count, int) and count < 0:
                    problems.append(f"{char_id}: spell slot L{level} = {count} < 0")

        capacity = getattr(character, "stormlight_capacity", None)
        current = getattr(character, "stormlight_current", None)
        if isinstance(capacity, int) and isinstance(current, int) and current > capacity:
            problems.append(
                f"{char_id}: stormlight {current} exceeds capacity {capacity}")
    return problems


# --------------------------------------------------------------------------- #
# I5-I8 — combat structure
# --------------------------------------------------------------------------- #

def check_positions_unique(combat_state: Optional[Dict[str, Any]]) -> List[str]:
    """I5: every combatant has a position and no two share a tile."""
    if not combat_state:
        return []
    problems, seen = [], {}
    for char_id, state in (combat_state.get("combatant_states") or {}).items():
        position = state.get("position") if isinstance(state, dict) else None
        if position is None:
            problems.append(f"{char_id}: no position in combat")
            continue
        key = tuple(position) if isinstance(position, (list, tuple)) else position
        if key in seen:
            problems.append(f"{char_id} shares tile {key} with {seen[key]}")
        else:
            seen[key] = char_id
    return problems


def check_conditions_are_srd(character_manager) -> List[str]:
    """I6: conditions are drawn from the 15 SRD names.

    Guards the orphaned-sub-condition crash too (`Stunned` then `Unconscious` once
    raised `list.remove(x): x not in list`), since a corrupted list shows up here.
    """
    problems = []
    for char_id, character in character_manager.characters.items():
        conditions = getattr(character, "conditions", None) or []
        if not isinstance(conditions, list):
            problems.append(f"{char_id}: conditions is {type(conditions).__name__}")
            continue
        for condition in conditions:
            name = str(condition).lower().split()[0] if condition else ""
            if name and name not in SRD_CONDITIONS:
                problems.append(f"{char_id}: unknown condition {condition!r}")
    return problems


def check_turn_index_valid(combat_state: Optional[Dict[str, Any]]) -> List[str]:
    """I8: the turn index always addresses a real combatant."""
    if not combat_state:
        return []
    order = combat_state.get("initiative_order") or combat_state.get("turn_order") or []
    index = combat_state.get("current_turn_index")
    if not order or index is None:
        return []
    if not 0 <= index < len(order):
        return [f"turn index {index} outside initiative order of {len(order)}"]
    return []


# --------------------------------------------------------------------------- #
# I10 — player-visible output
# --------------------------------------------------------------------------- #

def check_no_placeholder_text(text: Optional[str]) -> List[str]:
    """I10: no template leakage in anything shown to a player."""
    if not text:
        return []
    return [f"placeholder {marker!r} reached the player"
            for marker in PLACEHOLDER_MARKERS if marker in text]


# --------------------------------------------------------------------------- #
# G8 — engine global state
# --------------------------------------------------------------------------- #

def check_engine_registries_empty() -> List[str]:
    """G8: class-level registries are empty, so a leak fails its own test.

    `Entity._entity_by_position` and `Tile._tile_registry` are CLASS-level, so a leak
    otherwise surfaces as a mysterious failure in an unrelated later test on the same
    xdist worker.
    """
    from dnd.core.base_tiles import Tile
    from dnd.entity import Entity

    problems = []
    for cls, attr in ((Entity, "_entity_registry"), (Entity, "_entity_by_position"),
                      (Tile, "_tile_registry"), (Tile, "_tile_by_position")):
        registry = getattr(cls, attr, None)
        if registry:
            problems.append(f"{cls.__name__}.{attr} still holds {len(registry)} entries")
    return problems


# --------------------------------------------------------------------------- #
# Aggregate
# --------------------------------------------------------------------------- #

def collect(
    character_manager=None,
    combat_state: Optional[Dict[str, Any]] = None,
    player_text: Optional[str] = None,
) -> List[str]:
    """Run every applicable invariant and return all violations."""
    problems: List[str] = []
    if character_manager is not None:
        problems += check_hp_bounds(character_manager)
        problems += check_resources_non_negative(character_manager)
        problems += check_conditions_are_srd(character_manager)
    if combat_state is not None:
        problems += check_positions_unique(combat_state)
        problems += check_turn_index_valid(combat_state)
    if player_text is not None:
        problems += check_no_placeholder_text(player_text)
    return problems


def assert_all(
    character_manager=None,
    combat_state: Optional[Dict[str, Any]] = None,
    player_text: Optional[str] = None,
    context: str = "",
) -> None:
    """Raise with EVERY violation at once, so one does not mask the rest."""
    problems = collect(character_manager, combat_state, player_text)
    if problems:
        where = f" after {context}" if context else ""
        raise AssertionError(
            f"{len(problems)} invariant violation(s){where}:\n  - "
            + "\n  - ".join(problems)
        )
