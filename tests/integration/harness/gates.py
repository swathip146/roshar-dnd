"""
The coverage gate checks — §7 of the strategy. This is what makes "full coverage" real.

Every expectation is ENUMERATED FROM LIVE DATA (`ACTION_REGISTRY`, `DM_TOOLS`,
`surgebinding.json`), never from a hardcoded list, so newly added content is opted into
coverage automatically and adding a mechanic without a test breaks the build. A prose
checklist rots; this cannot.

WHY THIS IS A MODULE OF FUNCTIONS AND NOT A TEST FILE
-----------------------------------------------------
The gates are inherently WHOLE-RUN assertions: they can only be evaluated once every
scenario has recorded its observations. Under `pytest -n 8` each worker is a separate
PROCESS, and xdist gives no cross-worker ordering guarantee — so a gate running as an
ordinary test lands on some arbitrary worker and reads a ledger the other seven workers
are still writing to. That produced a real, reproducible false failure: the terminal
summary showed all 28 actions and 71 mechanics recorded, while the gate on `gw2`
reported 24 actions "never exercised".

So the gates run from `pytest_sessionfinish` in `conftest.py`, on the xdist CONTROLLER,
after every worker has finished. `conftest.py` turns any violation into a non-zero exit
status, so the build still fails — it simply fails for the right reason, once, with the
complete picture.
"""

from __future__ import annotations

import os
from typing import List, Set

from tests.integration.harness.coverage import (
    COVERAGE_DIR_ENV,
    CoverageLedger,
    expected_dm_tools,
    expected_offerable_actions,
    expected_playable_orders,
    expected_surges,
    missing,
)

#: Registry entries that are legitimately not offerable, with the reason.
#: `move` needs a caller-supplied destination, so it is filtered from menus by
#: design; movement is exercised through the grid/dash path instead.
INTENTIONALLY_NOT_OFFERED = {"move"}

#: Every mechanic row from §4 of the strategy that Suite A claims to cover. Each MUST
#: be recorded by some scenario via `ledger.mechanic(...)`. Listing a row here without
#: a scenario fails the gate; shipping a mechanic without adding a row is caught in
#: review against the audit docs.
CLAIMED_MECHANICS = {
    # Combat
    "C1:attack_rolls", "C1:ac_matters", "C2:damage_bounded",
    "C3:resistance", "C3:immunity", "C3:vulnerability", "C3:resistance_scoped",
    "C5:advantage", "C6:action_economy", "C7:all_actions_dispatch",
    "C9:slot_spent", "C9:cantrip_free", "C9:upcasting", "C9:save_dc",
    "C9:non_caster_has_no_dc",
    "C10:conditions", "C10:patched_conditions",
    "C11:death_saves", "C11:nat20_revive", "C11:dying_not_dead", "C11:stabilize",
    "C11:save_gated_on_hp",
    # Character / exploration / progression
    "E1:skill_check", "E1:dice_vary", "E1:proficiency", "E1:policy_scaling",
    "E2:tool_gate", "E2:passive_perception",
    "E3:carrying_capacity", "E3:encumbrance",
    "E4:long_rest_hp", "E4:long_rest_slots", "E4:short_rest",
    "E4:long_rest_reports", "E4:stormlight_rest",
    "E7:quest_objective",
    "E8:armour_ac", "E8:dex_cap",
    "E9:character_round_trip", "E9:slots_round_trip",
    "P1:level_up", "P1:level_1_to_20", "P2:asi_level_4", "P2:no_asi_off_level",
    "P4:proficiency_table",
    # Cosmere
    "R1:surges_authored", "R1:cast_surge", "R2:orders_two_surges",
    "R3:art_catalogue", "R3:art_compilation", "R3:cast_art",
    "R3:invested_save_dc",
    "R5:cost_table", "R5:ledger_spend_refuse", "R5:ip_long_rest",
    "R6:lashing_dice", "R6:no_overspend", "R6:lashing_scaling", "R6:maneuvers",
    "R6:review_discipline",
    "R7:intake_gate",
    "R9:shardblade_rolls_vs_ac", "R9:shardblade_scaling", "R9:ideal_gate",
    "R11:node_types", "R11:node_split", "R11:nodes_fail_loudly",
    # Adversarial guards for bugs that shipped
    "G1:offerability", "G5:cantrips_free", "G5:cantrip_free_at_ledger",
    "G6:illumination_gate",
    # Tactical combat (C4, C8, C12-C20)
    "C12:initiative_order", "C12:initiative_varies", "C13:difficult_terrain",
    "C13:distance", "C13:terrain_built", "C13:walls", "C14:cover_ac",
    "C14:cover_no_stack", "C14:cover_removed", "C14:flanking",
    "C14:flanking_requires_opposite", "C15:no_provoke_in_reach", "C15:provoked",
    "C15:reaction_economy", "C16:ranged_at_distance", "C16:reach",
    "C17:attacks_per_turn", "C17:parse_prose", "C17:srd_prevalence",
    "C18:activated_offerable", "C18:all_classes_covered", "C18:gaps_declared",
    "C18:granted_at_creation", "C18:rage_effect", "C19:line_of_sight",
    "C19:senses_present", "C20:cr_bands", "C20:cr_bands_permissive",
    "C20:difficulty_scaling", "C20:xp_budget", "C4:temp_hp_absorbs",
    "C4:temp_hp_overflow", "C4:temp_hp_sheet", "C8:grapple_contested",
    "C8:registered", "C8:resolve",
    # World, social, rules tiers, DM tools (E5, E6, E10, E11)
    "E10:cosmere_tier", "E10:srd_datasets", "E10:srd_tier", "E11:dm_tools",
    "E5:clock", "E5:highstorms", "E5:travel", "E6:social_dice",
    "E6:three_social_skills",
    # Progression + Roshar leftovers (P3, R8, R10)
    "P3:extra_attack", "R10:ideal_advance", "R10:third_ideal",
    "R8:cost_on_failure", "R8:polestone_outcome",
    # Adversarial guards (G2, G4, G7-G10). G3 (advantage) is recorded as
    # C5:advantage and R4 (Lashing Dice) as R6:lashing_* — the strategy's row
    # numbering overlaps there; the mechanics themselves are covered.
    "G4:proficiency_counted_once",
    "G10:tls_verify", "G2:reachability", "G7:round_trip", "G8:clean_registries",
    "G9:max_hp",
    # A-1 the campaign arc, through the real pipelines
    "A1:campaign_arc", "A1:no_network", "A1:rest_in_play", "A1:single_turn",
    "A1:tools_invoked_in_a_turn",
}


def _covered(kind: str) -> Set[str]:
    return CoverageLedger.covered(kind, os.environ.get(COVERAGE_DIR_ENV))


# --------------------------------------------------------------------------- #
# Individual gates. Each returns a list of violation strings (empty == pass).
# --------------------------------------------------------------------------- #

def gate_every_offerable_action_was_exercised() -> List[str]:
    """Each action a player can be offered must have been dispatched for real.

    This is the `cast_spell`/`spell_name` bug class turned into a gate: that action
    was registered, its comment described the fix, and one missing dict key kept all
    319 spells out of every menu. Nothing failed — it just silently vanished.
    """
    gap = missing(expected_offerable_actions(), _covered("action"))
    if not gap:
        return []
    return [
        f"{len(gap)} offerable action(s) were never exercised by any scenario: "
        f"{sorted(gap)}. Add a scenario that uses them, or record the exclusion in "
        f"INTENTIONALLY_NOT_OFFERED."
    ]


def gate_no_registry_entry_is_silently_unreachable() -> List[str]:
    """G1: an action filtered out of every menu is unplayable, however well tested."""
    from components.combat.action_registry import (
        ACTION_REGISTRY,
        is_offerable,
        required_caller_params,
    )

    unexpected = {name for name in ACTION_REGISTRY
                  if not is_offerable(name)} - INTENTIONALLY_NOT_OFFERED
    if not unexpected:
        return []
    detail = "; ".join(f"{name} needs caller params {required_caller_params(name)}"
                       for name in sorted(unexpected))
    return [f"these registry entries can never be offered to a player: {detail}"]


def gate_every_surge_was_cast() -> List[str]:
    """All 10 surges must actually resolve — 6 of them had no code at all once."""
    expected = expected_surges()
    problems = []
    gap = missing(expected, _covered("surge"))
    if gap:
        problems.append(f"{len(gap)} surge(s) never cast: {sorted(gap)}")
    if len(expected) != 10:
        problems.append(f"expected 10 surges in the data, found {len(expected)}")
    return problems


def gate_every_playable_order_was_exercised() -> List[str]:
    """Each of the 9 playable orders must appear.

    Bondsmith is excluded by `expected_playable_orders()`: verified absent from the
    source books (0 hits in 19,794 lines), so it has no abilities to exercise.
    """
    expected = expected_playable_orders()
    problems = []
    gap = missing(expected, _covered("order"))
    if gap:
        problems.append(f"{len(gap)} playable order(s) unexercised: {sorted(gap)}")
    if "Bondsmith" in expected:
        problems.append(
            "Bondsmith is now in the data — if a source book added it, give it a "
            "scenario and stop excluding it")
    return problems


def gate_every_interpreter_node_type_is_present() -> List[str]:
    """R11: the declarative interpreter's node types must not silently shrink."""
    from components.combat.maneuver_executor import KNOWN_NODES

    gap = missing(set(KNOWN_NODES), _covered("node"))
    if not gap:
        return []
    return [f"node types in KNOWN_NODES but never asserted on: {sorted(gap)}"]


def gate_claimed_mechanics_match_observed() -> List[str]:
    """The §4 inventory is executable, not prose — checked in BOTH directions.

    A missing token means a scenario stopped recording it (the mechanic may have
    silently broken). An extra token means §4 drifted behind the suite.
    """
    observed = _covered("mechanic")
    problems = []

    unobserved = missing(CLAIMED_MECHANICS, observed)
    if unobserved:
        problems.append(
            f"{len(unobserved)} claimed mechanic(s) recorded no observation: "
            f"{sorted(unobserved)}")

    unclaimed = observed - CLAIMED_MECHANICS
    if unclaimed:
        problems.append(
            f"{len(unclaimed)} mechanic token(s) recorded but not listed in "
            f"CLAIMED_MECHANICS: {sorted(unclaimed)}. Add them here and to §4 of "
            f"docs/mechanics/INTEGRATION_TEST_STRATEGY.md")
    return problems


def gate_every_dm_tool_was_invoked() -> List[str]:
    """E11: every DM tool must have been invoked by some scenario.

    Specified in strategy §7. The exploration pipeline's tools are the LLM's only
    means of changing game state, so a tool that is defined, registered in
    `DM_TOOLS`, and never invoked is the same defect class as an unofferable combat
    action: present, plausible, and unreachable in play.
    """
    gap = missing(expected_dm_tools(), _covered("tool"))
    if not gap:
        return []
    return [f"{len(gap)} DM tool(s) never invoked by any scenario: {sorted(gap)}"]


def gate_dm_tools_are_enumerable() -> List[str]:
    """E11: the 19 DM tools must stay discoverable, since the gate enumerates them."""
    tools = expected_dm_tools()
    problems = []
    if len(tools) < 19:
        problems.append(f"expected at least 19 DM tools, found {len(tools)}")
    for required in ("roll_skill_check", "cast_spell"):
        if required not in tools:
            problems.append(f"DM tool {required!r} has disappeared")
    return problems


#: Every gate, run in order by `conftest.pytest_sessionfinish`.
ALL_GATES = (
    ("offerable actions exercised", gate_every_offerable_action_was_exercised),
    ("no unreachable registry entry", gate_no_registry_entry_is_silently_unreachable),
    ("every surge cast", gate_every_surge_was_cast),
    ("every playable order exercised", gate_every_playable_order_was_exercised),
    ("every interpreter node asserted", gate_every_interpreter_node_type_is_present),
    ("claimed mechanics match observed", gate_claimed_mechanics_match_observed),
    ("every DM tool invoked", gate_every_dm_tool_was_invoked),
    ("DM tools enumerable", gate_dm_tools_are_enumerable),
)


def run_all_gates() -> List[str]:
    """Run every gate; return a flat list of violations across all of them."""
    violations: List[str] = []
    for name, gate in ALL_GATES:
        try:
            for problem in gate():
                violations.append(f"[{name}] {problem}")
        except Exception as exc:                            # noqa: BLE001
            violations.append(f"[{name}] gate itself raised {type(exc).__name__}: {exc}")
    return violations


def have_any_observations() -> bool:
    """True if this run recorded anything at all.

    The gates are meaningless for a partial run (a single scenario file during
    development), so `conftest` skips them entirely rather than reporting a
    misleading failure.
    """
    return bool(CoverageLedger.load_all(os.environ.get(COVERAGE_DIR_ENV)))
