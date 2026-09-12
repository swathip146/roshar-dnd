"""
SRD 5e rules loader — Tier 1 of the rules architecture (plan 2.9, §8).

    Tier 1  data/rules/srd/          <- THIS (baseline D&D 5e)   } code
    Tier 2  data/rules/stormlight/   <- Cosmere/Surgebinding     } adjudicates
    Tier 3  Qdrant vectors           <- narrative lore, never adjudicates

Why this matters: RAG-over-PDFs is the wrong tool for RULES. A retrieved chunk
saying "goblins are weak but cunning" is narrative colour that the LLM must then
interpret — reintroducing exactly the hallucination we are engineering out. The
SRD JSON gives structured fields code can compute with:

    Goblin -> armor_class 15, hit_points 7, hit_dice "2d6", challenge_rating 0.25
              actions[0] = Scimitar, attack_bonus 4, 1d6+2 slashing

That feeds npc_stat_generator and the combat engine directly. Keep Qdrant for
Roshar narrative lore, where prose is the point.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.logging_config import get_logger

from components.combat.multiattack import multiattack_for_monster

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRD_DIR = PROJECT_ROOT / "data" / "rules" / "srd"


class SRDRules:
    """Queries the vendored SRD 5e dataset."""

    DATASETS = ("monsters", "spells", "conditions", "equipment", "magic_items",
                "rules", "skills", "damage_types", "weapon_properties",
                "ability_scores")

    def __init__(self, srd_dir: Path = SRD_DIR):
        self.srd_dir = Path(srd_dir)
        self._data: Dict[str, List[Dict[str, Any]]] = {}
        self.load()

    def load(self) -> int:
        """Load every vendored dataset. Returns the total entry count."""
        self._data = {}
        if not self.srd_dir.exists():
            logger.warning(
                f"⚠️ SRD data not vendored at {self.srd_dir} — "
                f"run scripts/vendor_srd_data.py"
            )
            return 0

        total = 0
        for name in self.DATASETS:
            path = self.srd_dir / f"{name}.json"
            if not path.exists():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                self._data[name] = payload if isinstance(payload, list) else [payload]
                total += len(self._data[name])
            except Exception as e:
                logger.error(f"❌ Could not load SRD {name}: {e}")

        logger.info(
            f"📚 Loaded SRD Tier-1 rules: {total} entries "
            f"({len(self._data.get('monsters', []))} monsters, "
            f"{len(self._data.get('spells', []))} spells, "
            f"{len(self._data.get('conditions', []))} conditions)"
        )
        return total

    # ------------------------------------------------------------ generic get

    def _find(self, dataset: str, name: str,
              exact_only: bool = False) -> Optional[Dict[str, Any]]:
        """Exact then whole-word partial match (never a naive substring)."""
        entries = self._data.get(dataset, [])
        needle = (name or "").strip().lower()
        if not needle:
            return None

        for entry in entries:
            if entry.get("name", "").lower() == needle:
                return entry
            if entry.get("index", "").lower() == needle:
                return entry
            # ability_scores.json keys entries as "STR"/"DEX" and puts the word
            # anyone would actually search for in `full_name`, so a lookup for
            # "Dexterity" matched nothing at all until this was checked.
            if entry.get("full_name", "").lower() == needle:
                return entry

        if exact_only:
            return None

        # Whole-word partial: "goblin warrior" -> Goblin. A plain substring test
        # would match "A" inside "Shattered Plains" (the 2.6 bug class).
        needle_words = set(re.findall(r"[a-z0-9']+", needle))
        best = None
        for entry in entries:
            entry_words = set(re.findall(r"[a-z0-9']+", entry.get("name", "").lower()))
            shared = needle_words & entry_words
            if shared and max(len(w) for w in shared) >= 4:
                score = len(shared)
                if best is None or score > best[0]:
                    best = (score, entry)
        return best[1] if best else None

    # ---------------------------------------------------------------- monsters

    def monster(self, name: str) -> Optional[Dict[str, Any]]:
        """A monster statblock by name (e.g. 'Goblin')."""
        return self._find("monsters", name)

    def monster_stats(self, name: str) -> Optional[Dict[str, Any]]:
        """
        A monster reduced to the fields our combat layer needs.

        Shaped to match what npc_stat_generator produces, so an SRD monster can
        be used in place of an LLM-generated statblock.
        """
        entry = self.monster(name)
        if not entry:
            return None

        # armor_class is a list of typed entries in the 2014 dataset
        ac = 10
        ac_field = entry.get("armor_class")
        if isinstance(ac_field, list) and ac_field:
            ac = int(ac_field[0].get("value", 10))
        elif isinstance(ac_field, int):
            ac = ac_field

        hp = int(entry.get("hit_points", 1))
        attacks = []
        for action in entry.get("actions", []) or []:
            if "attack_bonus" not in action:
                continue
            damage = (action.get("damage") or [{}])[0]
            dtype = damage.get("damage_type") or {}
            attacks.append({
                "name": action.get("name", "Attack"),
                "attack_bonus": int(action.get("attack_bonus", 0)),
                "damage_dice": damage.get("damage_dice", "1d4"),
                "damage_type": (dtype.get("name") or "bludgeoning").lower(),
                "desc": action.get("desc", ""),
            })

        # MULTIATTACK. The loop above skips every action without `attack_bonus`,
        # and Multiattack has none — so it was dropped here, and 148 of the 334
        # vendored monsters silently attacked ONCE per turn instead of two or
        # three times. Since the CR HP/AC bands (npc_stat_generator) were tuned
        # against measured time-to-kill, that made every difficulty calculation
        # wrong in the party's favour. See components/combat/multiattack.py.
        multiattack = multiattack_for_monster(entry)
        attacks_per_turn = (multiattack["attacks_per_turn"]
                            if multiattack else 1)

        speed = entry.get("speed") or {}
        walk = speed.get("walk", "30 ft.")
        walk_ft = int(re.sub(r"[^0-9]", "", str(walk)) or 30)

        return {
            "name": entry.get("name", name),
            "character_class": entry.get("type", "monster"),
            "race": entry.get("subtype") or entry.get("type", "monster"),
            "size": entry.get("size", "Medium"),
            "armor_class": ac,
            "hit_points": {"current": hp, "maximum": hp, "temporary": 0},
            "hit_dice": entry.get("hit_dice", ""),
            "challenge_rating": entry.get("challenge_rating", 0),
            "ability_scores": {
                "strength": entry.get("strength", 10),
                "dexterity": entry.get("dexterity", 10),
                "constitution": entry.get("constitution", 10),
                "intelligence": entry.get("intelligence", 10),
                "wisdom": entry.get("wisdom", 10),
                "charisma": entry.get("charisma", 10),
            },
            "speed": walk_ft,
            "attacks": attacks,
            # How many attack ROLLS this creature's Attack action grants. Always
            # >= 1; a monster with no Multiattack keeps the 5e default of one.
            "attacks_per_turn": attacks_per_turn,
            # The parse itself, so callers can see the named sequence and whether
            # it was read from structured data, from prose, or fell back.
            "multiattack": multiattack,
            "special_abilities": [a.get("name", "")
                                  for a in (entry.get("special_abilities") or [])],
            # Damage modifiers and senses (plan 0, monster stat wiring)
            "damage_resistances": entry.get("damage_resistances", []),
            "damage_vulnerabilities": entry.get("damage_vulnerabilities", []),
            "damage_immunities": entry.get("damage_immunities", []),
            "senses": entry.get("senses", {}),
            "source": "SRD 5e (OGL 1.0a)",
        }

    def monsters_by_cr(self, min_cr: float = 0, max_cr: float = 30) -> List[str]:
        """Monster names within a challenge-rating band (encounter building)."""
        out = []
        for entry in self._data.get("monsters", []):
            cr = entry.get("challenge_rating", 0)
            try:
                if min_cr <= float(cr) <= max_cr:
                    out.append(entry["name"])
            except (TypeError, ValueError):
                continue
        return sorted(out)

    # ------------------------------------------------------------------ others

    def spell(self, name: str) -> Optional[Dict[str, Any]]:
        return self._find("spells", name)

    def condition(self, name: str) -> Optional[Dict[str, Any]]:
        """A condition and its rules text (blinded, prone, restrained …)."""
        return self._find("conditions", name)

    def equipment(self, name: str) -> Optional[Dict[str, Any]]:
        return self._find("equipment", name)

    def weapon_damage(self, name: str) -> Optional[Dict[str, Any]]:
        """
        A weapon's real damage dice from the SRD.

        Supersedes the hand-written _WEAPON_STATS table in dnd_engine_wrapper
        (plan 1.4), which I authored from memory.
        """
        entry = self.equipment(name)
        if not entry or "damage" not in entry:
            return None
        damage = entry["damage"] or {}
        dtype = damage.get("damage_type") or {}
        return {
            "name": entry.get("name", name),
            "damage_dice": damage.get("damage_dice", "1d4"),
            "damage_type": (dtype.get("name") or "bludgeoning").lower(),
            "properties": [p.get("name") for p in (entry.get("properties") or [])],
            "category": (entry.get("weapon_category") or ""),
            "range": entry.get("range") or {},
        }

    def rule(self, name: str) -> Optional[Dict[str, Any]]:
        return self._find("rules", name)

    def skill(self, name: str) -> Optional[Dict[str, Any]]:
        return self._find("skills", name)

    def magic_item(self, name: str) -> Optional[Dict[str, Any]]:
        return self._find("magic_items", name)

    def damage_type(self, name: str) -> Optional[Dict[str, Any]]:
        return self._find("damage_types", name)

    def weapon_property(self, name: str) -> Optional[Dict[str, Any]]:
        """A weapon property's rules text (finesse, reach, two-handed …)."""
        return self._find("weapon_properties", name)

    def ability_score(self, name: str) -> Optional[Dict[str, Any]]:
        """An ability and the skills it governs (e.g. 'dexterity', 'DEX')."""
        return self._find("ability_scores", name)

    # The datasets a generic lookup should search, in priority order, paired with
    # the `kind` label reported back to the caller.
    #
    # This ordering matters: it is the sequence `query_rules(kind="auto")` walks.
    # Narrower, more mechanically specific datasets come first so a lookup for
    # "Perception" resolves to the SKILL rather than to the "Using Ability Scores"
    # rules chapter that also mentions it.
    LOOKUP_ORDER = (
        ("condition", "conditions"),
        ("monster", "monsters"),
        ("spell", "spells"),
        ("skill", "skills"),
        ("equipment", "equipment"),
        ("magic_item", "magic_items"),
        ("weapon_property", "weapon_properties"),
        ("damage_type", "damage_types"),
        ("ability_score", "ability_scores"),
        ("rule", "rules"),
    )

    def lookup(self, name: str,
               kind: str = "auto") -> Optional[Dict[str, Any]]:
        """
        Search EVERY loaded dataset, not just the four that had callers.

        All ten datasets were loaded from the start, but `query_rules` only ever
        searched monsters, spells, conditions and equipment. So a lookup for
        "Perception" — plainly present in `skills.json` — fell through to the rules
        judge and was recorded as a Tier-3 gap. `data/rules/gaps.json` shows it
        happening: `"rules lookup perception"`, tier `judged`.

        That is the 2.10 "rules long tail" in miniature. The tail was not missing
        data; 386 entries across six datasets were simply unreachable.

        Returns `{kind, dataset, data}` or None.
        """
        pairs = [(k, d) for k, d in self.LOOKUP_ORDER if k == kind] or self.LOOKUP_ORDER

        # TWO PASSES, and the order is the point. An exact hit in ANY dataset must
        # beat a fuzzy hit in an earlier one: searching magic_items before
        # damage_types made "Necrotic" resolve to "Potion of Necrotic Resistance"
        # rather than to the damage type. No priority ordering can fix that —
        # exactness has to outrank position.
        for exact_only in (True, False):
            for label, dataset in pairs:
                entry = self._find(dataset, name, exact_only=exact_only)
                if entry:
                    return {"kind": label, "dataset": dataset, "data": entry}
        return None

    def available(self) -> Dict[str, int]:
        """What is loaded, for diagnostics."""
        return {name: len(entries) for name, entries in self._data.items()}


_GLOBAL: Optional[SRDRules] = None


def get_srd_rules() -> SRDRules:
    """Shared SRDRules instance."""
    global _GLOBAL
    if _GLOBAL is None:
        _GLOBAL = SRDRules()
    return _GLOBAL
