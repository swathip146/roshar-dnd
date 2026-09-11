"""
Lashing dice — the resource every Surgebinding maneuver spends (plan 3.1b).

Every one of the nine authored maneuvers in `data/rules/stormlight/surgebinding.json`
costs `{"lashing_dice": 1}`, and **the resource did not exist**: `lashing_dice` had
zero references anywhere in `components/`, `agents/` or `core/`. So the automation
trees could not have been executed even with an interpreter, because there was nothing
to spend.

Held here rather than on the engine `Entity` because it is a Roshar concept the
vendored engine knows nothing about, and rather than on `CharacterData` because it is
per-encounter combat state that resets on a rest — the same reasoning that puts the
action economy in the combat session.

    "You have two Lashing dice to fuel your Maneuvers ..., which are d4s, and you earn
     more at higher levels ... A Lashing die is expended when you use it. You regain
     all of your expended Lashing dice when you finish a short or long rest."
        — Radiant's Handbook, line 1862 (quoted in surgebinding.json, reviewed)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from config.logging_config import get_logger

logger = get_logger(__name__)

# From `economies.lashing_dice` in surgebinding.json: two d4s at first level.
STARTING_DICE = 2
STARTING_DIE_SIZE = 4


@dataclass
class LashingDice:
    """
    One Radiant's pool: how many dice remain, and how big they are.

    `size` is the die a maneuver rolls for `{lashing_die}`; `remaining` is how many
    uses are left before a rest.
    """

    total: int = STARTING_DICE
    size: int = STARTING_DIE_SIZE
    remaining: int = STARTING_DICE

    def spend(self, count: int = 1) -> bool:
        """Expend dice. False (and no change) if the pool is short."""
        if count <= 0 or self.remaining < count:
            return False
        self.remaining -= count
        return True

    def restore(self) -> None:
        """A short or long rest regains ALL expended dice."""
        self.remaining = self.total


class LashingDicePool:
    """
    Tracks lashing dice for every Radiant in an encounter.

    Only orders whose `economy` is `lashing_dice` get a pool — currently Windrunner.
    Asking about anyone else returns None rather than inventing a resource, so a
    Lightweaver cannot accidentally spend Windrunner dice.
    """

    def __init__(self, cosmere_rules=None):
        self._pools: Dict[str, LashingDice] = {}
        self._rules = cosmere_rules

    # ------------------------------------------------------------------ set-up

    def register(self, char_id: str, order: str = "",
                 level: int = 1) -> Optional[LashingDice]:
        """
        Give a character a pool if their order uses lashing dice.

        Returns the pool, or None if the order does not use this economy.
        """
        if not self._uses_lashing_dice(order):
            return None

        total = self.dice_for_level(level)
        size = self.die_size_for_level(level)
        pool = LashingDice(total=total, size=size, remaining=total)
        self._pools[char_id] = pool
        logger.info(f"   ⚡ {char_id} ({order}): {total} lashing dice (d{size})")
        return pool

    def _uses_lashing_dice(self, order: str) -> bool:
        if not order:
            return False
        if self._rules is not None:
            economy = self._rules.economy_for_order(order)
            if isinstance(economy, dict):
                return economy.get("id") == "lashing_dice"
            # An order the Handbook knows but with a different economy.
            if self._rules.order(order) is not None:
                return False
        return order.strip().lower() == "windrunner"

    # -------------------------------------------------------------- progression

    @staticmethod
    def dice_for_level(level: int) -> int:
        """
        How many lashing dice at a given Windrunner level.

        DERIVED, NOT CITED. `surgebinding.json` records the level-1 values (2 dice,
        d4) and says both "increase with level per the Windrunner table" — but that
        TABLE is prose in the Handbook and was never extracted, so there is no
        reviewed data to read. This interpolates one extra die every four levels,
        which matches the level-1 anchor and 5e's usual cadence for such tables.

        Flagged rather than silently assumed: if the Windrunner table is ever
        extracted, replace this with the data.
        """
        return STARTING_DICE + max(0, (max(1, level) - 1) // 4)

    @staticmethod
    def die_size_for_level(level: int) -> int:
        """
        Lashing die size by level. DERIVED — see `dice_for_level`.

        Steps d4 -> d6 -> d8 -> d10 at levels 5/11/17, the progression 5e uses for
        comparable scaling dice (Martial Arts, Sneak Attack cadence).
        """
        for threshold, size in ((17, 10), (11, 8), (5, 6)):
            if max(1, level) >= threshold:
                return size
        return STARTING_DIE_SIZE

    # ------------------------------------------------------------------- access

    def get(self, char_id: str) -> Optional[LashingDice]:
        return self._pools.get(char_id)

    def spend(self, char_id: str, count: int = 1) -> bool:
        """Expend dice for a maneuver. False if there is no pool or too few dice."""
        pool = self._pools.get(char_id)
        if pool is None:
            return False
        spent = pool.spend(count)
        if spent:
            logger.info(f"   ⚡ {char_id} expends {count} lashing die "
                        f"({pool.remaining}/{pool.total} left)")
        else:
            logger.info(f"   ⚡ {char_id} has no lashing dice left "
                        f"(0/{pool.total})")
        return spent

    def die_size(self, char_id: str) -> int:
        """The die a maneuver rolls for `{lashing_die}`."""
        pool = self._pools.get(char_id)
        return pool.size if pool is not None else STARTING_DIE_SIZE

    def remaining(self, char_id: str) -> int:
        pool = self._pools.get(char_id)
        return pool.remaining if pool is not None else 0

    def rest(self, char_id: str = "") -> None:
        """A short or long rest regains all expended dice."""
        pools = ([self._pools[char_id]] if char_id in self._pools
                 else list(self._pools.values()))
        for pool in pools:
            pool.restore()
        if pools:
            logger.info(f"   ⚡ Lashing dice restored"
                        f"{f' for {char_id}' if char_id else ''}")

    def clear(self) -> None:
        self._pools.clear()
