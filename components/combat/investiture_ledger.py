"""
Investiture Point ledger for Invested Arts economy (plan 2.9).

WHAT THIS IS
-----------
`InvestiturePointLedger` mirrors `SpellSlotLedger` but spends
`CharacterData.investiture_points` against the book-accurate cost table in
`CosmereRules.investiture_cost()`. Before this, `investiture_cost()` existed
and had zero callers — the tenth instance of that pattern.

DIFFERENCES FROM SPELL SLOTS
----------------------------
1. **Simple pool, not leveled slots:** `investiture_points` is a single
   `{"current": X, "maximum": Y}` dict, not `{1: {...}, 2: {...}}` by level.
   An art costs N points; the ledger spends N if available.

2. **No upcasting:** Spells can be cast from higher slots; arts cannot be
   "upcast" in the same way. The cost is fixed by art level.

3. **Elsecaller exception:** Elsecallers always spend exactly 1 IP for any
   leveled art (HB rules, already in `investiture_cost()`).

LONG REST REFRESH
-----------------
`refresh_on_long_rest()` restores all IP to maximum, matching the book's
long-rest economy (HB:13133-13141). The Stormlight-intake gate (level × 5
sapphire marks) is NOT enforced here — that is a higher-level rest mechanic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from config.logging_config import get_logger

if TYPE_CHECKING:
    from components.character_manager import CharacterManager
    from components.cosmere_rules import CosmereRules

logger = get_logger(__name__)

# The highest art level Cosmere 5e defines.
MAX_ART_LEVEL = 5


@dataclass
class InvestitureSpend:
    """The outcome of trying to pay for an Invested Art. A refusal carries its reason."""

    spent: bool
    cost: int = 0
    reason: str = ""
    remaining: int = 0


class InvestiturePointLedger:
    """
    Reads and spends `CharacterData.investiture_points` against the book's cost table.

    The field is `{"current": N, "maximum": M}` — a single pool, not leveled like
    spell slots. Cantrips (art_level 0) cost nothing and always succeed.
    """

    def __init__(self, character_manager: CharacterManager,
                 cosmere_rules: Optional[CosmereRules] = None):
        self.character_manager = character_manager
        self.rules = cosmere_rules

    # ------------------------------------------------------------------ reads

    def _pool(self, character_id: str) -> dict:
        """The raw IP pool, or {"current": 0, "maximum": 0} if absent."""
        character = self.character_manager.characters.get(character_id)
        if character is None:
            return {"current": 0, "maximum": 0}
        pool = getattr(character, "investiture_points", None)
        if not isinstance(pool, dict):
            return {"current": 0, "maximum": 0}
        return pool

    def current(self, character_id: str) -> int:
        """IP remaining right now."""
        pool = self._pool(character_id)
        return int(pool.get("current", 0) or 0)

    def maximum(self, character_id: str) -> int:
        """The character's IP capacity."""
        pool = self._pool(character_id)
        return int(pool.get("maximum", 0) or 0)

    def has_any(self, character_id: str) -> bool:
        """True if at least one IP remains."""
        return self.current(character_id) > 0

    def can_afford(self, character_id: str, cost: int) -> bool:
        """True if the character has enough IP for this cost."""
        return self.current(character_id) >= cost

    # ------------------------------------------------------------------ writes

    def spend(self, character_id: str, art_level: int,
              order: str = "") -> InvestitureSpend:
        """
        Consume IP for an Invested Art. Cantrips (level 0) cost nothing and always succeed.

        Refuses — with a reason, never an exception — when there are insufficient
        points or when the character has no IP pool at all.
        """
        character = self.character_manager.characters.get(character_id)
        if character is None:
            return InvestitureSpend(False,
                                    reason=f"unknown character {character_id}")

        if art_level < 0:
            return InvestitureSpend(False, reason=f"invalid art level {art_level}")

        # Cantrips are free
        if art_level == 0:
            return InvestitureSpend(True, cost=0,
                                    reason="cantrip — no IP required")

        # Calculate cost from the book's table
        if self.rules is None:
            return InvestitureSpend(False,
                                    reason="no cost table available (rules not loaded)")

        cost = self.rules.investiture_cost(art_level, order)
        if cost <= 0:
            return InvestitureSpend(False,
                                    reason=f"art level {art_level} has no defined cost")

        if art_level > MAX_ART_LEVEL:
            return InvestitureSpend(False,
                                    reason=f"there is no level {art_level} art")

        pool = self._pool(character_id)
        current = int(pool.get("current", 0) or 0)
        maximum = int(pool.get("maximum", 0) or 0)

        if maximum <= 0:
            return InvestitureSpend(False,
                                    reason=f"{character_id} has no investiture points at all")

        if current < cost:
            return InvestitureSpend(
                False,
                cost=cost,
                reason=f"insufficient IP: need {cost}, have {current}")

        # Spend it
        pool["current"] = current - cost
        logger.info(f"   ✨ {character_id} spent {cost} IP "
                    f"({pool['current']}/{maximum} left)")
        return InvestitureSpend(True, cost=cost, remaining=pool["current"])

    def restore(self, character_id: str, amount: int) -> int:
        """
        Give IP back (used when a cast is refused after payment).

        Returns the new current amount, clamped to maximum.
        """
        pool = self._pool(character_id)
        maximum = int(pool.get("maximum", 0) or 0)
        current = int(pool.get("current", 0) or 0)
        pool["current"] = min(maximum, current + amount)
        return pool["current"]

    def refresh_on_long_rest(self, character_id: str) -> bool:
        """
        Restore all IP to maximum (book rule: full refresh on long rest).

        Returns True if successful, False if the character has no IP pool.
        """
        character = self.character_manager.characters.get(character_id)
        if character is None:
            return False

        pool = self._pool(character_id)
        maximum = int(pool.get("maximum", 0) or 0)

        if maximum <= 0:
            return False

        pool["current"] = maximum
        logger.info(f"   🌅 {character_id} refreshed IP to {maximum} on long rest")
        return True
