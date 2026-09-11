"""
Corrections to the vendored `dnd_engine`, applied at import.

`external/dnd_engine` is frozen third-party code (plan §4): 24 stars, single author,
no test suite for ~15k LOC. It has real bugs, and the project's rule is to fix them at
the seam rather than editing the vendored tree — so a future `git pull` of the engine
does not silently drop our corrections, and every fix stays visible in one file with
its evidence.

Each patch below records what was measured, not what was assumed.

Import this module before using the engine. `dnd_engine_wrapper` does so, which covers
every production path.
"""

from __future__ import annotations

from config.logging_config import get_logger

logger = get_logger(__name__)

_APPLIED: list[str] = []


def apply_engine_patches() -> list[str]:
    """Apply every correction. Idempotent; returns the names applied."""
    if _APPLIED:
        return list(_APPLIED)

    _patch_advantage_rolls()

    if _APPLIED:
        logger.info(f"🔧 dnd_engine corrections applied: {', '.join(_APPLIED)}")
    return list(_APPLIED)


def _patch_advantage_rolls() -> None:
    """
    ADVANTAGE AND DISADVANTAGE NEVER WORKED.

    `Dice._roll_with_advantage` is:

        rolls = [random.randint(1, self.value) for _ in range(self.count)]
        return max(rolls), rolls

    `self.count` is the number of dice in the expression — **1** for a d20 attack or
    check. So "roll twice and keep the higher" rolled ONE die and took the maximum of
    a single-element list. Disadvantage had the identical bug with `min`.

    Measured before the fix, 2000 attacks at +4 versus AC 16:

        base       45.4%
        advantage  45.4%      delta +0.0%

    Not noise — identical to the decimal, because the same single die was rolled.

    This is not only a flanking problem. Advantage is how 5e expresses a large part of
    its rules: attacking a Prone or Restrained target, Dodging, Invisible attackers,
    help from an ally, and several Roshar surges. All of them were decorative.

    5e RAW: advantage rolls **two** d20s and keeps the higher, regardless of how many
    dice the rest of the expression uses. So roll `count` pairs and keep the better of
    each pair — which is also correct for the rare multi-die advantage case.
    """
    try:
        import random

        from dnd.core.dice import Dice
    except Exception as e:                      # pragma: no cover - import guard
        logger.warning(f"⚠️ Could not patch advantage rolls: {e}")
        return

    def _roll_with_advantage(self):
        """Roll two d20s per die and keep the HIGHER. Returns (best, all_rolls)."""
        rolls = []
        best = []
        for _ in range(self.count):
            pair = [random.randint(1, self.value), random.randint(1, self.value)]
            rolls.extend(pair)
            best.append(max(pair))
        return sum(best), rolls

    def _roll_with_disadvantage(self):
        """Roll two d20s per die and keep the LOWER. Returns (worst, all_rolls)."""
        rolls = []
        worst = []
        for _ in range(self.count):
            pair = [random.randint(1, self.value), random.randint(1, self.value)]
            rolls.extend(pair)
            worst.append(min(pair))
        return sum(worst), rolls

    Dice._roll_with_advantage = _roll_with_advantage
    Dice._roll_with_disadvantage = _roll_with_disadvantage
    _APPLIED.append("advantage/disadvantage roll two dice")
