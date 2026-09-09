"""
Automatic combat choices — for unattended runs (playtest, CI, soak tests).

CombatSessionManager asks the player to choose via an injected
`input_provider`; with none, it falls back to real `input()` and an unattended
run blocks forever on "Choose action type (1-2):". A live playtest hung exactly
there.

The naive stub — always answer "1" — is worse than it looks. Menu item 1 is
whatever the registry happened to order first, which in a live run was
*Lashing* against a shadow creature immune to it: the fight could not progress
and every round hit the stall-breaker. A useful auto-player has to choose by
what the action DOES, not by where it sits in the list.

So this reads the option text the session manager just printed and picks with a
simple, legible policy:

    heal when hurt  ->  attack  ->  anything else

That is enough to drive an encounter to a real outcome (victory or defeat),
which is what a test needs to assert on.
"""

from __future__ import annotations

import re
from typing import Callable, List, Optional

from config.logging_config import get_logger

logger = get_logger(__name__)


# Ordered by preference. The first pattern that matches an available option wins.
_ATTACK_PATTERNS = (
    r"attack with weapon",
    r"\battack\b",
    r"shardblade",
    r"strike",
)

_HEAL_PATTERNS = (
    r"heal",
    r"progression",
    r"regrowth",
)


class AutoCombatPlayer:
    """
    Answers combat prompts automatically, choosing by action meaning.

    Usage:
        player = AutoCombatPlayer(hp_fraction=lambda: 0.4)
        combat_agent.input_provider = player

    It sees only the prompt string, so the options themselves are captured from
    stdout by `observe_options()` — the session manager prints the numbered list
    immediately before asking. That keeps this decoupled from combat internals.
    """

    def __init__(self, hp_fraction: Optional[Callable[[], float]] = None,
                 heal_below: float = 0.35):
        self.hp_fraction = hp_fraction
        self.heal_below = heal_below
        self._options: List[str] = []
        self.decisions: List[str] = []

    # ------------------------------------------------------------------ input

    def observe_options(self, line: str) -> None:
        """
        Record a printed option line, e.g. "  1. Attack with weapon → Foe".

        Called by the stdout tap installed in `install()`.
        """
        match = re.match(r"\s*(\d+)\.\s+(.*)", line)
        if not match:
            return
        index = int(match.group(1))
        text = match.group(2).strip()
        # Options are printed 1..N in order; reset when we see a new list start.
        if index == 1:
            self._options = []
        while len(self._options) < index - 1:
            self._options.append("")
        self._options.append(text)

    def __call__(self, prompt: str = "") -> str:
        """Answer one prompt, 1-based, as the session manager expects."""
        limit = self._limit_from(prompt)

        # "Choose action type" is the category menu; the option list printed for
        # it is categories, not actions. Take the standard-actions category,
        # which is where attacks and healing live.
        if "action type" in prompt.lower():
            choice = self._pick_category(limit)
        else:
            choice = self._pick_action(limit)

        self.decisions.append(f"{prompt.strip()} -> {choice}")
        return str(choice)

    # --------------------------------------------------------------- policy

    def _pick_category(self, limit: Optional[int]) -> int:
        index = self._first_match(_ATTACK_PATTERNS + ("standard",))
        if index is not None and self._within(index, limit):
            return index
        return 1

    def _pick_action(self, limit: Optional[int]) -> int:
        if self._should_heal():
            index = self._first_match(_HEAL_PATTERNS)
            if index is not None and self._within(index, limit):
                logger.debug(f"   🤖 auto-combat: healing (option {index})")
                return index

        index = self._first_match(_ATTACK_PATTERNS)
        if index is not None and self._within(index, limit):
            logger.debug(f"   🤖 auto-combat: attacking (option {index})")
            return index

        # Nothing recognisable: fall back to the first option so the fight moves.
        return 1

    def _should_heal(self) -> bool:
        if self.hp_fraction is None:
            return False
        try:
            return self.hp_fraction() < self.heal_below
        except Exception:
            return False

    def _first_match(self, patterns) -> Optional[int]:
        """1-based index of the first option matching any pattern, in order."""
        for pattern in patterns:
            for position, text in enumerate(self._options, start=1):
                if re.search(pattern, text, re.IGNORECASE):
                    return position
        return None

    @staticmethod
    def _within(index: int, limit: Optional[int]) -> bool:
        return limit is None or 1 <= index <= limit

    @staticmethod
    def _limit_from(prompt: str) -> Optional[int]:
        """Read the upper bound out of "... (1-9): "."""
        match = re.search(r"\(1-(\d+)\)", prompt)
        return int(match.group(1)) if match else None

    # ------------------------------------------------------------------ setup

    def install(self) -> "_StdoutTap":
        """
        Tee stdout so option lines are observed as the session manager prints them.

        Returns the tap; use as a context manager, or call `.uninstall()`.
        """
        return _StdoutTap(self)


class _StdoutTap:
    """Passes stdout through untouched while feeding lines to the auto-player."""

    def __init__(self, player: AutoCombatPlayer):
        import sys

        self.player = player
        self._sys = sys
        self._real = sys.stdout
        sys.stdout = self

    def write(self, text: str) -> int:
        for line in text.splitlines():
            try:
                self.player.observe_options(line)
            except Exception:
                pass
        return self._real.write(text)

    def flush(self) -> None:
        self._real.flush()

    def __getattr__(self, name):
        return getattr(self._real, name)

    def uninstall(self) -> None:
        self._sys.stdout = self._real

    def __enter__(self) -> AutoCombatPlayer:
        return self.player

    def __exit__(self, *exc) -> None:
        self.uninstall()
