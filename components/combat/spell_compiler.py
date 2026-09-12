"""
Compiles an SRD spell entry into the automation tree ManeuverExecutor already runs.

WHY A COMPILER AND NOT A SECOND EFFECT ENGINE
---------------------------------------------
`data/rules/srd/spells.json` holds 319 spells and **not one was castable**: nothing
anywhere consumed `spell_slots`, no `cast` action existed, and `import dnd.spells`
fails because the vendored engine has no spell system at all.

The obvious move is a spell-effect interpreter. That interpreter already exists:
`components/combat/maneuver_executor.py` runs Avrae-style `automation` trees
(`target` / `save` / `damage` / `attack` / `roll` / `ieffect2`) for Surgebinding
maneuvers, with 58 tests on it. A spell is the same problem — roll a save, branch,
deal damage — so this module TRANSLATES SRD JSON into that schema instead of
growing a parallel engine. Only one node type is new (`heal`), added by the
executor subclass in `spellcasting.py`.

WHAT IT REFUSES TO DO
---------------------
The SRD's structured fields cover 66 spells with `damage`, 92 with `dc`, 10 with
`heal_at_slot_level` and 16 with `attack_type`. Everything else — Wish, Bless,
Counterspell, Polymorph — carries its mechanics ONLY in English prose (`desc`).

Those are returned as `needs_adjudication`, never as an empty tree. That is the
project's hard-won rule: `_meta.correction` in
`data/rules/stormlight/surgebinding.json` records that hand-invented Stormlight
costs were "plausible and wrong", and the recurring defect class here is the
silent zero — an ability that reports success while doing nothing. A spell with no
derivable numbers must fall through to the rules judge, loudly.

Specifically NOT invented:
  * conditions from prose ("the target is paralysed") — the SRD gives no
    structured condition field, and guessing which 5e condition a sentence means
    is exactly the LLM hallucination the Tier-1 rules layer exists to remove.
  * area-of-effect target selection. `area_of_effect` gives shape and size, but
    who is inside it is a grid question; the caster's chosen targets are used and
    the area is reported so a DM (or the tactical grid) can widen it.
  * `damage_at_character_level` for a monster/NPC caster with no class level —
    the level is required to pick the row, and picking row "1" for a level-17
    archmage would under-report by 3d10.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from config.logging_config import get_logger

logger = get_logger(__name__)

# The SRD writes save abilities as three-letter codes in `dc.dc_type.index`.
_ABILITY_BY_CODE = {
    "str": "strength", "dex": "dexterity", "con": "constitution",
    "int": "intelligence", "wis": "wisdom", "cha": "charisma",
}

# `dc.dc_success` values the SRD actually uses, and what each means mechanically.
#   "none" -> a successful save takes NO damage
#   "half" -> a successful save takes half damage
#   "other" -> the prose decides (e.g. "the target is freed on a success"), which
#              this compiler will not guess at.
_SAVE_HALVES = "half"
_SAVE_NEGATES = "none"

#: Placeholder for the caster's spellcasting ability modifier, used by the SRD's
#: own healing strings ("1d8 + MOD"). Kept as a placeholder rather than baked in
#: so a compiled tree stays inspectable and testable without a caster.
MOD = "{mod}"


@dataclass
class CompiledSpell:
    """
    A spell reduced to what code can execute, plus everything it could NOT derive.

    `needs_adjudication` is the honest failure: True means "the structured data does
    not describe this spell's effect", and the caller must route it to the rules
    judge rather than reporting a successful cast that changed nothing.
    """

    name: str
    level: int
    school: str = ""
    automation: List[Dict[str, Any]] = field(default_factory=list)
    needs_adjudication: bool = False
    reason: str = ""
    concentration: bool = False
    duration: str = ""
    spell_range: str = ""
    components: List[str] = field(default_factory=list)
    ritual: bool = False
    casting_time: str = "1 action"
    area_of_effect: Optional[Dict[str, Any]] = None
    damage_type: str = ""
    attack_type: str = ""
    save_ability: str = ""
    save_success: str = ""
    slot_level: int = 0
    description: str = ""

    @property
    def is_cantrip(self) -> bool:
        return self.level == 0

    def describe(self) -> str:
        parts = [f"{self.name} (level {self.level})"]
        if self.needs_adjudication:
            parts.append(f"needs adjudication: {self.reason}")
        else:
            parts.append(f"{len(self.automation)} automation node(s)")
        if self.concentration:
            parts.append("concentration")
        return " — ".join(parts)


def _text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or value.get("index") or "")
    return str(value or "")


def _pick_slot_row(table: Dict[str, Any], slot_level: int) -> Optional[str]:
    """
    The damage/heal row for the slot used, clamped to the table's own range.

    The SRD tables are keyed by slot level as STRINGS. A 3rd-level Fireball cast
    from a 5th-level slot must read row "5"; casting Cure Wounds from a 9th-level
    slot must not fall off the end.
    """
    if not isinstance(table, dict) or not table:
        return None
    levels = sorted(int(k) for k in table if str(k).lstrip("-").isdigit())
    if not levels:
        return None
    chosen = max((lvl for lvl in levels if lvl <= slot_level), default=levels[0])
    return str(table[str(chosen)])


def _pick_character_row(table: Dict[str, Any],
                        caster_level: Optional[int]) -> Optional[str]:
    """
    A cantrip's damage row for the caster's level.

    Returns None when the caster level is unknown. Cantrip scaling is keyed on
    CHARACTER level (1/5/11/17), and defaulting to row "1" would silently
    under-report a high-level caster's Fire Bolt by up to 3d10 — a wrong number
    that looks exactly like a right one.
    """
    if caster_level is None:
        return None
    return _pick_slot_row(table, int(caster_level))


def compile_spell(spell: Dict[str, Any], slot_level: Optional[int] = None,
                  caster_level: Optional[int] = None) -> CompiledSpell:
    """
    Translate one SRD spell entry into an executable automation tree.

    `slot_level` is the slot actually spent (>= the spell's own level, for
    upcasting); it defaults to the spell's level. `caster_level` is needed only for
    cantrips, whose damage scales on character level.
    """
    name = str(spell.get("name") or "unknown spell")
    level = int(spell.get("level", 0) or 0)
    slot = int(slot_level if slot_level is not None else level)

    compiled = CompiledSpell(
        name=name,
        level=level,
        school=_text(spell.get("school")),
        concentration=bool(spell.get("concentration")),
        duration=str(spell.get("duration") or ""),
        spell_range=str(spell.get("range") or ""),
        components=list(spell.get("components") or []),
        ritual=bool(spell.get("ritual")),
        casting_time=str(spell.get("casting_time") or "1 action"),
        area_of_effect=spell.get("area_of_effect"),
        attack_type=str(spell.get("attack_type") or ""),
        slot_level=slot,
        description=" ".join(spell.get("desc") or []),
    )

    effects: List[Dict[str, Any]] = []

    heal_expression = _heal_expression(spell, slot)
    if heal_expression:
        effects.append({"type": "heal", "heal": heal_expression})

    damage_node = _damage_node(spell, slot, caster_level, compiled)
    if damage_node is not None:
        effects.append(damage_node)
    elif spell.get("damage") and not heal_expression:
        # There IS a damage block but no row we can honestly read. Do not fall
        # through to "no effect"; say why.
        compiled.needs_adjudication = True
        compiled.reason = compiled.reason or (
            f"{name} has a damage table this caster's level cannot index")
        return compiled

    if not effects:
        compiled.needs_adjudication = True
        compiled.reason = (
            f"{name} has no structured damage, healing or attack data in the SRD — "
            f"its effect is described only in prose")
        logger.info(f"   📜 {name}: needs adjudication ({compiled.reason})")
        return compiled

    tree = _wrap_in_save_or_attack(effects, spell, compiled)
    compiled.automation = [{"type": "target", "target": "chosen",
                            "effects": tree}]
    logger.debug(f"   📜 compiled {compiled.describe()}")
    return compiled


def _heal_expression(spell: Dict[str, Any], slot: int) -> str:
    """`heal_at_slot_level` -> a dice expression with {mod} left as a placeholder."""
    row = _pick_slot_row(spell.get("heal_at_slot_level") or {}, slot)
    if not row:
        return ""
    # The SRD writes "3d8 + MOD"; keep it as our own placeholder token so the
    # executor substitutes the caster's real modifier.
    return re.sub(r"\bMOD\b", MOD, row)


def _damage_node(spell: Dict[str, Any], slot: int,
                 caster_level: Optional[int],
                 compiled: CompiledSpell) -> Optional[Dict[str, Any]]:
    """A `damage` node from `damage_at_slot_level` or `damage_at_character_level`."""
    damage = spell.get("damage") or {}
    if not damage:
        return None

    damage_type = _text(damage.get("damage_type")).lower() or "force"
    compiled.damage_type = damage_type

    expression = _pick_slot_row(damage.get("damage_at_slot_level") or {}, slot)
    if not expression:
        expression = _pick_character_row(
            damage.get("damage_at_character_level") or {}, caster_level)
    if not expression:
        if damage.get("damage_at_character_level"):
            compiled.reason = (
                f"{compiled.name} scales on character level and the caster's "
                f"level is unknown")
        return None

    return {"type": "damage", "damage": expression, "damage_type": damage_type}


def _wrap_in_save_or_attack(effects: List[Dict[str, Any]],
                            spell: Dict[str, Any],
                            compiled: CompiledSpell) -> List[Dict[str, Any]]:
    """
    Put the effects behind a saving throw or a spell attack roll, per the SRD.

    Three shapes:
      * `dc` present  -> a `save` node. `dc_success: "half"` gives the classic
        Fireball split (full on a fail, half on a success); `"none"` means a
        successful save takes nothing.
      * `attack_type` -> a `spell_attack` node (hit/miss branches).
      * neither       -> automatic effect (Magic Missile, Cure Wounds).
    """
    dc = spell.get("dc") or {}
    if dc:
        code = _text(dc.get("dc_type")).lower()
        ability = _ABILITY_BY_CODE.get(code[:3], "")
        success_mode = str(dc.get("dc_success") or "").lower()
        compiled.save_ability = ability
        compiled.save_success = success_mode

        if not ability:
            compiled.needs_adjudication = True
            compiled.reason = (
                f"{compiled.name} requires a save against an ability the SRD does "
                f"not name ({dc.get('dc_type')!r})")
            return effects

        node: Dict[str, Any] = {"type": "save", "stat": ability,
                                "dc": "spell_save_dc", "fail": effects}
        if success_mode == _SAVE_HALVES:
            node["success"] = [dict(e, multiplier=0.5) for e in effects]
        elif success_mode == _SAVE_NEGATES:
            node["success"] = []
        else:
            # "other" — the prose decides what a success does. Run the fail
            # branch only, and flag it so the judge can add the rest.
            node["success"] = []
            compiled.needs_adjudication = True
            compiled.reason = (
                f"{compiled.name}'s save result is '{dc.get('dc_success')}', which "
                f"the SRD describes only in prose")
        return [node]

    if compiled.attack_type:
        return [{"type": "spell_attack", "attack_type": compiled.attack_type,
                 "hit": effects, "miss": []}]

    return effects
