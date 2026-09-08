"""
Rules gap tracker — plan 2.11.

The answer to "extraction will miss rules": it will, and the system should tell
you WHICH. Every time adjudication falls back below Tier 1/2 — a Tier-3 LLM
ruling or pure narration — it is recorded here with a use counter. Recurring
gaps rank themselves, so the extraction backlog is driven by real play rather
than guesswork.

Tiers (plan D5):
    1 canonical   Tier-1 SRD or Tier-2 Cosmere JSON     authoritative
    2 composed    built from canonical primitives       high confidence
    3 judged      LLM rules-judge, grounded + cited     provisional  <- logged
    4 narrative   no mechanical resolution              flavour      <- logged

A gap seen often is a rule worth structuring. A gap seen once is probably noise.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.logging_config import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STORE = PROJECT_ROOT / "data" / "rules" / "gaps.json"

TIER_CANONICAL = 1
TIER_COMPOSED = 2
TIER_JUDGED = 3
TIER_NARRATIVE = 4

TIER_NAMES = {
    TIER_CANONICAL: "canonical",
    TIER_COMPOSED: "composed",
    TIER_JUDGED: "judged",
    TIER_NARRATIVE: "narrative",
}


class RulesGapTracker:
    """Records where adjudication fell short, and ranks what to fix."""

    def __init__(self, store_path: Path = DEFAULT_STORE):
        self.store_path = Path(store_path)
        self._gaps: Dict[str, Dict[str, Any]] = {}
        self.load()

    # ------------------------------------------------------------- persistence

    def load(self) -> int:
        if not self.store_path.exists():
            return 0
        try:
            payload = json.loads(self.store_path.read_text(encoding="utf-8"))
            self._gaps = payload.get("gaps", {})
            return len(self._gaps)
        except Exception as e:
            logger.warning(f"⚠️ Could not read rules-gap store: {e}")
            self._gaps = {}
            return 0

    def save(self) -> bool:
        try:
            self.store_path.parent.mkdir(parents=True, exist_ok=True)
            self.store_path.write_text(
                json.dumps({"gaps": self._gaps}, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return True
        except Exception as e:
            logger.warning(f"⚠️ Could not write rules-gap store: {e}")
            return False

    # -------------------------------------------------------------- recording

    @staticmethod
    def _key(situation: str) -> str:
        """Normalise so 'Lash the boulder' and 'lash the boulder!' coincide."""
        return " ".join(
            w for w in "".join(
                ch.lower() if (ch.isalnum() or ch.isspace()) else " "
                for ch in (situation or "")
            ).split()
        )[:120]

    def record(self, situation: str, tier: int, *,
               ruling: Optional[str] = None,
               citations: Optional[List[str]] = None,
               actor: str = "", timestamp: Optional[float] = None) -> Dict[str, Any]:
        """
        Record one adjudication that fell below canonical.

        Tiers 1 and 2 are not gaps and are ignored, so callers can pass every
        adjudication without filtering.
        """
        if tier <= TIER_COMPOSED:
            return {}

        key = self._key(situation)
        if not key:
            return {}

        entry = self._gaps.setdefault(key, {
            "situation": situation,
            "uses": 0,
            "tiers": {},
            "first_seen": timestamp or time.time(),
            "rulings": [],
            "promoted": False,
        })
        entry["uses"] += 1
        entry["last_seen"] = timestamp or time.time()
        tier_name = TIER_NAMES.get(tier, str(tier))
        entry["tiers"][tier_name] = entry["tiers"].get(tier_name, 0) + 1
        if actor:
            entry.setdefault("actors", [])
            if actor not in entry["actors"]:
                entry["actors"].append(actor)
        if ruling:
            entry["rulings"].append({"ruling": ruling, "citations": citations or []})
            # Keep only the most recent few; this is a backlog, not an archive.
            del entry["rulings"][:-5]

        logger.info(
            f"📋 Rules gap [{tier_name}] '{situation[:60]}' "
            f"(seen {entry['uses']}x)"
        )
        self.save()
        return entry

    # --------------------------------------------------------------- reporting

    def backlog(self, min_uses: int = 2,
                include_promoted: bool = False) -> List[Dict[str, Any]]:
        """
        Gaps worth structuring, most-used first.

        `min_uses=2` by default: a rule that came up once is probably noise; one
        that keeps recurring is a real hole in the ruleset.
        """
        items = [
            {"key": key, **entry}
            for key, entry in self._gaps.items()
            if entry.get("uses", 0) >= min_uses
            and (include_promoted or not entry.get("promoted"))
        ]
        return sorted(items, key=lambda e: (-e["uses"], e["situation"]))

    def mark_promoted(self, situation: str) -> bool:
        """
        Mark a gap as now covered by a canonical rule.

        Called after the situation has been written into
        data/rules/stormlight/*.json and reviewed.
        """
        entry = self._gaps.get(self._key(situation))
        if entry is None:
            return False
        entry["promoted"] = True
        entry["promoted_at"] = time.time()
        self.save()
        logger.info(f"✅ Rules gap promoted to canonical: '{situation[:60]}'")
        return True

    def stats(self) -> Dict[str, Any]:
        """How much of play is running on canonical rules vs improvisation."""
        total_uses = sum(e.get("uses", 0) for e in self._gaps.values())
        by_tier: Dict[str, int] = {}
        for entry in self._gaps.values():
            for tier, count in (entry.get("tiers") or {}).items():
                by_tier[tier] = by_tier.get(tier, 0) + count
        return {
            "distinct_gaps": len(self._gaps),
            "total_fallbacks": total_uses,
            "by_tier": by_tier,
            "promoted": sum(1 for e in self._gaps.values() if e.get("promoted")),
            "backlog_size": len(self.backlog()),
        }

    def report(self, limit: int = 10) -> str:
        """Human-readable backlog, for a CLI command or a review session."""
        stats = self.stats()
        lines = [
            "Rules gap report",
            f"  distinct gaps    : {stats['distinct_gaps']}",
            f"  total fallbacks  : {stats['total_fallbacks']}",
            f"  by tier          : {stats['by_tier'] or 'none'}",
            f"  promoted         : {stats['promoted']}",
            "",
        ]
        backlog = self.backlog()
        if not backlog:
            lines.append("  No recurring gaps — play is running on canonical rules.")
        else:
            lines.append(f"  Top {min(limit, len(backlog))} to structure next:")
            for entry in backlog[:limit]:
                tiers = ", ".join(f"{k}x{v}" for k, v in entry["tiers"].items())
                lines.append(f"   {entry['uses']:>3}x  {entry['situation'][:64]}  [{tiers}]")
        return "\n".join(lines)


_GLOBAL: Optional[RulesGapTracker] = None


def get_gap_tracker() -> RulesGapTracker:
    """Shared RulesGapTracker instance."""
    global _GLOBAL
    if _GLOBAL is None:
        _GLOBAL = RulesGapTracker()
    return _GLOBAL
