"""
Polestone mechanics for Invested Arts (HB:13231-13241).

Some Invested Arts require infused polestones as material components. When such
an art is cast, the polestone has one of three outcomes:
1. CRACK - the polestone becomes worthless and is consumed
2. DRAIN - the polestone is emptied of Stormlight but remains intact
3. UNTOUCHED - only if the art is interrupted before completion

The consequence happens whether the art succeeds or fails. If an art is not fully
cast (interrupted), the polestone remains intact and infused.
"""

from dataclasses import dataclass
from typing import Dict, Any, Literal, Optional
import random

from config.logging_config import get_logger

logger = get_logger(__name__)


PolestoneOutcome = Literal["crack", "drain", "untouched"]


@dataclass
class Polestone:
    """
    A polestone used as a material component for Invested Arts.

    Per HB:13233-13241, polestones must be:
    - The correct type (e.g., diamond, heliodor, zircon)
    - The correct size (small, large, enormous)
    - Fully infused with Stormlight

    Size determines Stormlight capacity in sapphire marks (see HB Chapter 5):
    - Small polestone: ~10 sm
    - Large polestone: ~100 sm
    - Enormous polestone: ~500 sm
    """
    type: str  # e.g., "diamond", "heliodor", "zircon"
    size: str  # e.g., "small", "large", "enormous"
    value_sm: int  # Sapphire mark value
    infused: bool = True  # Whether it holds Stormlight
    cracked: bool = False  # Whether it's been destroyed

    def is_usable(self) -> bool:
        """Check if this polestone can be used for casting."""
        return self.infused and not self.cracked


def resolve_polestone_outcome(
    interrupted: bool = False,
    art_succeeded: bool = True,
) -> PolestoneOutcome:
    """
    Resolve what happens to a polestone after an Invested Art is cast.

    Per HB:13239:
    - If the art is interrupted (not fully cast), the polestone is UNTOUCHED
    - If the art is fully cast (regardless of success), the polestone is either:
      - CRACK: destroyed and worthless (most common outcome per handbook examples)
      - DRAIN: emptied of Stormlight but intact (some arts specify this)

    The handbook doesn't give explicit percentages, but examples (revivify, ritual
    of the Truthwatchers) show that arts requiring expensive polestones typically
    CRACK them. Arts that merely use polestones for power typically DRAIN them.

    For simplicity and adherence to the text:
    - Arts with "worth X sm" requirements → CRACK (like revivify)
    - Arts that "use" or "consume" Stormlight → DRAIN

    This function assumes CRACK for now (most conservative interpretation).
    Specific arts can override by calling this with a custom roll or by
    explicitly setting the outcome.

    Args:
        interrupted: Whether the art was interrupted before completion
        art_succeeded: Whether the art succeeded (doesn't affect outcome per HB:13239)

    Returns:
        PolestoneOutcome: "crack", "drain", or "untouched"
    """
    if interrupted:
        logger.info("   💎 Polestone UNTOUCHED (art was interrupted)")
        return "untouched"

    # Per HB:13239, the consequence happens whether the art succeeds or fails
    # For arts with material component costs (e.g., revivify), polestones crack
    # This is the default interpretation from handbook examples

    # Future enhancement: could read art metadata to determine crack vs. drain
    # For now, assume crack (most common in handbook)
    logger.info(f"   💎 Polestone CRACKED (art {'succeeded' if art_succeeded else 'failed'})")
    return "crack"


def apply_polestone_outcome(
    polestone: Polestone,
    outcome: PolestoneOutcome
) -> Dict[str, Any]:
    """
    Apply the outcome to a polestone and return the result.

    Args:
        polestone: The polestone to modify
        outcome: The outcome to apply

    Returns:
        Dict describing what happened and the polestone's new state
    """
    if outcome == "untouched":
        return {
            "outcome": "untouched",
            "polestone": polestone,
            "message": f"{polestone.size} {polestone.type} remains intact and infused"
        }

    elif outcome == "drain":
        polestone.infused = False
        return {
            "outcome": "drain",
            "polestone": polestone,
            "message": f"{polestone.size} {polestone.type} drained of Stormlight but intact"
        }

    elif outcome == "crack":
        polestone.cracked = True
        polestone.infused = False
        return {
            "outcome": "crack",
            "polestone": polestone,
            "message": f"{polestone.size} {polestone.type} cracked and destroyed (worthless)"
        }

    else:
        logger.error(f"Unknown polestone outcome: {outcome}")
        return {
            "outcome": "unknown",
            "polestone": polestone,
            "error": f"Unknown outcome: {outcome}"
        }


def consume_polestone_for_art(
    polestone: Polestone,
    art_name: str,
    interrupted: bool = False,
    art_succeeded: bool = True
) -> Dict[str, Any]:
    """
    Full cycle: check polestone usability, resolve outcome, apply it.

    Per HB:13239, the cost is paid even when the art FAILS. The only way a
    polestone remains untouched is if the art is interrupted before completion.

    Args:
        polestone: The polestone being used
        art_name: Name of the Invested Art
        interrupted: Whether the casting was interrupted
        art_succeeded: Whether the art succeeded (doesn't affect cost)

    Returns:
        Dict with outcome, polestone state, and messages
    """
    if not polestone.is_usable():
        error_msg = (
            "cracked and worthless" if polestone.cracked
            else "not infused with Stormlight"
        )
        logger.warning(f"⚠️ Cannot use {polestone.type} for {art_name}: {error_msg}")
        return {
            "success": False,
            "error": f"Polestone is {error_msg}",
            "polestone": polestone
        }

    outcome = resolve_polestone_outcome(interrupted, art_succeeded)
    result = apply_polestone_outcome(polestone, outcome)

    logger.info(
        f"💎 {art_name} used {polestone.size} {polestone.type} ({polestone.value_sm}sm) "
        f"→ {outcome.upper()}"
    )

    return {
        "success": True,
        **result
    }
