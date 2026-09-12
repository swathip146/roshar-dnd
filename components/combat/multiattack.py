"""
Multiattack: how many attacks a monster's stat block actually grants per turn.

THE BUG THIS FIXES. `grep -rn multiattack components/ agents/ core/` returned
ZERO production hits, so every monster in the game attacked exactly ONCE per turn
regardless of its stat block. 148 of the 334 vendored SRD monsters have a
Multiattack action; an Ape that should throw two fists threw one, and a
CR 17 Adult Black Dragon that should bite once and claw twice made a single bite.

That is a BALANCE bug, not a cosmetic gap. `npc_stat_generator._clamp_to_cr_band`
derives HP/AC bands per CR from these same 334 monsters
(`scripts/derive_cr_bands.py`), and encounter difficulty was tuned against
MEASURED time-to-kill. Halving or thirding every monster's damage output silently
made every one of those calculations wrong in the party's favour.

WHERE THE NUMBERS COME FROM. The SRD JSON already carries structured hints, which
is the only trustworthy source here:

    "name": "Multiattack",
    "multiattack_type": "actions",
    "desc": "The dragon can use its Frightful Presence. It then makes three
             attacks: one with its bite and two with its claws.",
    "actions": [{"action_name": "Frightful Presence", "count": 1, "type": "ability"},
                {"action_name": "Bite",  "count": 1, "type": "melee"},
                {"action_name": "Claw",  "count": 2, "type": "melee"}]

All 148 entries have either `actions` (115) or `action_options` (33); NONE is
prose-only. So the structured fields are the primary parser and the prose regex
is a fallback for LLM-generated and third-party stat blocks, which do only have
prose.

WHAT WE DELIBERATELY DO NOT DO. Where neither path yields a confident count we
return ONE attack and log a warning naming the monster and the text we could not
read. Inventing a plausible number is the recurring defect class in this
codebase — see `_meta.correction` in data/rules/stormlight/surgebinding.json —
and a wrong multiattack count is invisible in play while being worth several
hundred percent of a monster's damage.

Two SRD counts are genuinely variable and CANNOT be a fixed integer:

    Hydra          "count": "Number of Heads"   -> depends on live head count
    Violet Fungus  "count": "1d4"               -> rolled each turn

Both fall back to one attack with a warning rather than guessing. A caller that
wants to model them can read `multiattack["variable"]`.

`type: "ability"` entries (Frightful Presence, Hurl Flame, Fire Breath) are NOT
weapon attacks and are excluded from `attacks_per_turn`; they are kept in
`sequence` so a future caller can fire them.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from config.logging_config import get_logger

logger = get_logger(__name__)

# Number words the SRD actually uses in Multiattack prose. Deliberately small:
# an open-ended word-to-number table invites guessing at text we have not seen.
_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8,
}

# "makes two attacks", "makes three scimitar attacks", "makes two melee attacks",
# "makes 1d4 Rotting Touch attacks" (caught as unparseable — see module docstring).
_MAKES_N_ATTACKS = re.compile(
    r"\bmakes?\s+(?:up\s+to\s+)?(?P<count>[a-z0-9]+)\s+"
    r"(?P<qualifier>[\w\s'-]{0,40}?)\battacks?\b",
    re.IGNORECASE,
)

# "one with its bite and two with its claws", "two with its scimitar"
_N_WITH_ITS = re.compile(
    r"\b(?P<count>[a-z0-9]+)\s+with\s+(?:its|his|her|their)\s+"
    # The weapon may be two words ("hand crossbow", "greataxe"), but must not
    # swallow the conjunction: "one with its bite and two with its claws" captured
    # "bite and" before this guard, so the sequence read back as a weapon named
    # "Bite And".
    r"(?P<weapon>(?!and\b|or\b)[a-z][\w'-]*"
    r"(?:\s+(?!and\b|or\b)[a-z][\w'-]*)?)",
    re.IGNORECASE,
)

# The most attacks any single turn may grant. SEVEN is the published maximum in
# the vendored SRD — the Marilith's six longswords plus its tail — so the cap is
# set from the data, not from memory. My first pass used 6 and silently demoted
# the Marilith to one attack, which is exactly the failure this module exists to
# prevent; the parse sweep over all 334 monsters caught it. Anything above the cap
# is a parse error rather than a monster.
MAX_ATTACKS_PER_TURN = 7


def _as_count(raw: Any) -> Optional[int]:
    """A positive int from `3`, `"3"` or `"three"`; None for anything else."""
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw if raw > 0 else None
    if isinstance(raw, str):
        token = raw.strip().lower()
        if token.isdigit():
            value = int(token)
            return value if value > 0 else None
        return _NUMBER_WORDS.get(token)
    return None


def _flatten_option(option: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    One `action_options` alternative flattened to a list of action entries.

    The SRD nests exactly two shapes (verified over all 33 `action_options`
    monsters): a bare `{"option_type": "action", ...}` and a
    `{"option_type": "multiple", "items": [...]}` bundle.
    """
    if not isinstance(option, dict):
        return []
    if option.get("option_type") == "multiple":
        return [item for item in (option.get("items") or [])
                if isinstance(item, dict)]
    if option.get("action_name"):
        return [option]
    return []


def _sequence_from_entries(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Turn SRD action entries into `{sequence, attacks_per_turn, variable}`.

    `variable` is True when any entry's count is not a fixed integer (Hydra's
    "Number of Heads", Violet Fungus's "1d4"), which makes the whole block
    unparseable rather than approximate.
    """
    sequence: List[Dict[str, Any]] = []
    variable = False
    for entry in entries:
        count = _as_count(entry.get("count"))
        if count is None:
            variable = True
            continue
        sequence.append({
            "name": entry.get("action_name") or "Attack",
            "count": count,
            # Only melee/ranged entries are attack ROLLS. "ability" entries
            # (Frightful Presence, Hurl Flame) ride along in the sequence but
            # must not inflate the attack count.
            "type": (entry.get("type") or "melee").lower(),
        })

    attacks = sum(item["count"] for item in sequence
                  if item["type"] in ("melee", "ranged"))
    return {"sequence": sequence, "attacks_per_turn": attacks,
            "variable": variable}


def _parse_structured(action: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The `actions` / `action_options` hints, which are authoritative when present."""
    entries = action.get("actions")
    if isinstance(entries, list) and entries:
        parsed = _sequence_from_entries([e for e in entries if isinstance(e, dict)])
        if parsed["attacks_per_turn"] >= 1:
            parsed["source"] = "srd_actions"
            return parsed
        # A block whose ONLY counts were variable (Hydra "Number of Heads",
        # Violet Fungus "1d4") yields no attacks at all. Report it as variable so
        # the caller can say WHY it fell back instead of blaming the prose.
        parsed["source"] = "variable"
        return parsed if parsed["variable"] else None

    options = action.get("action_options")
    if isinstance(options, dict):
        raw_options = ((options.get("from") or {}).get("options") or [])
        # A monster with alternatives ("three melee attacks ... Alternatively,
        # Hurl Flame twice") gets the option with the most ATTACK ROLLS. Picking
        # the first would under-count the Bandit Captain, whose second option is
        # a weaker ranged pair, and would over-weight ability-only options.
        best: Optional[Dict[str, Any]] = None
        for option in raw_options:
            parsed = _sequence_from_entries(_flatten_option(option))
            if parsed["attacks_per_turn"] < 1:
                continue
            if best is None or parsed["attacks_per_turn"] > best["attacks_per_turn"]:
                best = parsed
        if best is not None:
            best["source"] = "srd_action_options"
            return best
    return None


def _parse_prose(desc: str) -> Optional[Dict[str, Any]]:
    """
    A count read out of Multiattack prose, for stat blocks with no structured hints.

    Only the patterns actually observed are handled. Anything else returns None so
    the caller warns instead of guessing.
    """
    if not desc:
        return None

    # Only the sentence that grants attacks. Trailing sentences are conditional
    # riders ("If the chuul is grappling …", "Alternatively, …") and must not add
    # to the count.
    for sentence in re.split(r"(?<=[.;])\s+", desc):
        match = _MAKES_N_ATTACKS.search(sentence)
        if not match:
            continue
        total = _as_count(match.group("count"))
        if total is None:
            # "makes 1d4 Rotting Touch attacks" lands here: a real grant with a
            # count we refuse to invent.
            return None

        # A named breakdown ("one with its bite and two with its claws") gives the
        # per-weapon sequence. Trust the stated TOTAL over the breakdown when they
        # disagree — the breakdown often lists optional substitutions.
        named = [{"name": weapon.strip().rstrip('.').title(),
                  "count": count, "type": "melee"}
                 for count, weapon in
                 ((_as_count(m.group("count")), m.group("weapon"))
                  for m in _N_WITH_ITS.finditer(sentence))
                 if count is not None]
        if named and sum(item["count"] for item in named) == total:
            sequence = named
        else:
            qualifier = (match.group("qualifier") or "").strip()
            # "makes two melee attacks" names no weapon; "makes two fist attacks"
            # does. Drop the bare melee/ranged qualifiers.
            weapon = re.sub(r"\b(melee|ranged|weapon)\b", "", qualifier,
                            flags=re.IGNORECASE).strip()
            sequence = [{"name": weapon.title() if weapon else "Attack",
                         "count": total, "type": "melee"}]

        return {"sequence": sequence, "attacks_per_turn": total,
                "variable": False, "source": "prose"}
    return None


def parse_multiattack(action: Dict[str, Any],
                      monster_name: str = "unknown") -> Dict[str, Any]:
    """
    Read one Multiattack action into structured form.

    Returns:
        {
          "attacks_per_turn": int,     # >= 1, never a guess
          "sequence": [{"name", "count", "type"}, ...],
          "source": "srd_actions" | "srd_action_options" | "prose" | "fallback",
          "variable": bool,            # count depends on dice or live state
                                       # (Hydra's heads, Violet Fungus's 1d4)
          "desc": str,
          "parsed": bool,              # False => we fell back to one attack
        }

    On failure the count is ONE and a warning names the monster and the text.
    """
    desc = (action or {}).get("desc", "") or ""

    parsed = _parse_structured(action or {}) or _parse_prose(desc)

    if parsed and 1 <= parsed["attacks_per_turn"] <= MAX_ATTACKS_PER_TURN:
        breakdown = ", ".join("{}x {}".format(item["count"], item["name"])
                              for item in parsed["sequence"])
        logger.debug(
            f"⚔️ {monster_name}: Multiattack -> {parsed['attacks_per_turn']} "
            f"attacks/turn via {parsed['source']} ({breakdown})"
        )
        return {**parsed, "desc": desc, "parsed": True}

    if parsed and parsed.get("variable") and parsed["attacks_per_turn"] < 1:
        logger.warning(
            f"⚠️ {monster_name}: Multiattack count is VARIABLE (rolled, or "
            f"derived from live state) and cannot be a fixed number — using 1 "
            f"attack rather than guessing. Text: {desc!r}"
        )
    elif parsed:
        logger.warning(
            f"⚠️ {monster_name}: Multiattack parsed to "
            f"{parsed['attacks_per_turn']} attacks/turn, outside the plausible "
            f"1-{MAX_ATTACKS_PER_TURN} range — falling back to 1. Text: {desc!r}"
        )
    else:
        logger.warning(
            f"⚠️ {monster_name}: could not parse Multiattack; defaulting to 1 "
            f"attack rather than guessing. Text: {desc!r}"
        )
    return {"attacks_per_turn": 1, "sequence": [], "source": "fallback",
            "variable": bool(parsed and parsed.get("variable")),
            "desc": desc, "parsed": False}


def find_multiattack_action(actions: Optional[List[Dict[str, Any]]]
                            ) -> Optional[Dict[str, Any]]:
    """The Multiattack entry in an SRD-shaped `actions` list, if any."""
    for action in actions or []:
        if not isinstance(action, dict):
            continue
        if "multiattack" in (action.get("name") or "").lower():
            return action
    return None


def multiattack_for_monster(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Parsed Multiattack for a raw SRD monster entry, or None if it has none.

    A monster WITHOUT a Multiattack action returns None, and the caller must keep
    it at exactly one attack per turn — the 5e default.
    """
    action = find_multiattack_action(entry.get("actions"))
    if action is None:
        return None
    return parse_multiattack(action, entry.get("name", "unknown"))


def attacks_per_turn_for(character: Any, default: int = 1) -> int:
    """
    How many attack rolls THIS combatant gets from its action, clamped to sane.

    Reads `attacks_per_turn` then `multiattack["attacks_per_turn"]` off whatever
    the combat layer holds (a CharacterData with NPC attributes, or a plain stat
    dict), so the session manager never has to know which producer built the
    stat block.
    """
    getter = (character.get if isinstance(character, dict)
              else lambda key, fallback=None: getattr(character, key, fallback))

    count = _as_count(getter("attacks_per_turn", None))
    if count is None:
        block = getter("multiattack", None)
        if isinstance(block, dict):
            count = _as_count(block.get("attacks_per_turn"))
    if count is None:
        return default
    return max(1, min(int(count), MAX_ATTACKS_PER_TURN))
