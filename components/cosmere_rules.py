"""
Cosmere rules loader — Tier 2 of the three-tier rules architecture (plan §8, 2.9).

Tier 1  SRD JSON (5e-bits)      -> baseline D&D mechanics        } code adjudicates
Tier 2  data/rules/stormlight/  -> Cosmere/Surgebinding          }
Tier 3  Qdrant vectors          -> narrative lore                  never adjudicates

The hard rule (plan D5): an entry may only adjudicate if it is REVIEWED. An
unreviewed entry is confidently wrong and indistinguishable from a correct one,
which is worse than having no rule at all — so `get_*()` filters them out by
default and `unreviewed()` exposes them for review.

Every entry carries source.line into
parsed_data/863203275-cosmere-5e-radiant-s-handbook-v2-0/docling.md plus the
verbatim `quote`, so any claim can be checked against the Handbook. Run
verify_citations() to confirm nothing has drifted.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.logging_config import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RULES_DIR = PROJECT_ROOT / "data" / "rules" / "stormlight"
HANDBOOK_MD = (PROJECT_ROOT / "parsed_data"
               / "863203275-cosmere-5e-radiant-s-handbook-v2-0" / "docling.md")


class CosmereRules:
    """Loads and queries the Tier-2 Cosmere ruleset."""

    def __init__(self, rules_dir: Path = RULES_DIR):
        self.rules_dir = Path(rules_dir)
        self._data: Dict[str, Any] = {}
        self.load()

    # ------------------------------------------------------------------ load

    def load(self) -> int:
        """Load every rules file in the directory. Returns the file count."""
        self._data = {}
        if not self.rules_dir.exists():
            logger.warning(f"⚠️ Cosmere rules directory not found: {self.rules_dir}")
            return 0

        count = 0
        for path in sorted(self.rules_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.error(f"❌ Could not parse {path.name}: {e}")
                continue
            for key, value in payload.items():
                if key == "_meta":
                    continue
                if isinstance(value, list):
                    self._data.setdefault(key, []).extend(value)
                elif isinstance(value, dict):
                    self._data.setdefault(key, {}).update(value)
                else:
                    self._data[key] = value
            count += 1

        logger.info(
            f"📖 Loaded Cosmere rules from {count} file(s): "
            f"{len(self.maneuvers())} maneuvers, {len(self.features())} features, "
            f"{len(self._data.get('orders', {}))} orders "
            f"({len(self.unreviewed())} entries unreviewed)"
        )
        return count

    # --------------------------------------------------------------- queries

    @staticmethod
    def _reviewed(entry: Dict[str, Any]) -> bool:
        return bool((entry.get("source") or {}).get("reviewed"))

    def maneuvers(self, order: Optional[str] = None,
                  reviewed_only: bool = True) -> List[Dict[str, Any]]:
        """Maneuvers, optionally filtered to one Radiant order."""
        items = self._data.get("maneuvers", []) or []
        if reviewed_only:
            items = [m for m in items if self._reviewed(m)]
        if order:
            order_lower = order.strip().lower()
            items = [m for m in items
                     if any(o.lower() == order_lower for o in m.get("orders", []))]
        return items

    def features(self, order: Optional[str] = None,
                 reviewed_only: bool = True) -> List[Dict[str, Any]]:
        """Class features, optionally filtered to one order."""
        items = self._data.get("features", []) or []
        if reviewed_only:
            items = [f for f in items if self._reviewed(f)]
        if order:
            order_lower = order.strip().lower()
            items = [f for f in items
                     if any(o.lower() == order_lower for o in f.get("orders", []))]
        return items

    def get_maneuver(self, maneuver_id: str,
                     reviewed_only: bool = True) -> Optional[Dict[str, Any]]:
        """One maneuver by id or name (case-insensitive)."""
        needle = (maneuver_id or "").strip().lower()
        for m in self.maneuvers(reviewed_only=reviewed_only):
            if m.get("id", "").lower() == needle or m.get("name", "").lower() == needle:
                return m
        return None

    def get_art(self, art_name: str,
                reviewed_only: bool = True) -> Optional[Dict[str, Any]]:
        """
        One Invested Art by name (plan 2.9).

        Searches the top-level `invested_arts` bucket (or `arts`), mirroring
        `get_maneuver()`. The bucket may be empty for now — the authoring agent
        fills it. Returns None if not found.
        """
        needle = (art_name or "").strip().lower()
        # Try both possible bucket names
        for bucket_name in ("invested_arts", "arts"):
            items = self._data.get(bucket_name, []) or []
            if reviewed_only:
                items = [a for a in items if self._reviewed(a)]
            for art in items:
                if art.get("name", "").lower() == needle:
                    return art
        return None

    def order(self, name: str) -> Optional[Dict[str, Any]]:
        """The surges and economy of one Radiant order."""
        orders = self._data.get("orders", {}) or {}
        for key, value in orders.items():
            if key.lower() == (name or "").strip().lower():
                return {"name": key, **value}
        return None

    def surges_for_order(self, name: str) -> List[str]:
        entry = self.order(name)
        return list(entry.get("surges", [])) if entry else []

    def economy_for_order(self, name: str) -> Optional[Dict[str, Any]]:
        """The resource economy an order spends (Lashing Dice, Investiture …)."""
        entry = self.order(name)
        if not entry:
            return None
        economies = self._data.get("economies", {}) or {}
        return economies.get(entry.get("economy"))

    def investiture_cost(self, art_level: int, order: str = "") -> int:
        """
        Investiture Point cost for an Invested Art (plan 2.9).

        Quoted from the Handbook: 1st=2, 2nd=3, 3rd=5, 4th=6, 5th=7; cantrips
        are free; Elsecallers always spend exactly 1.
        """
        economy = (self._data.get("economies", {}) or {}).get("investiture_points", {})
        if (order or "").strip().lower() == "elsecaller" and art_level >= 1:
            return 1
        if art_level <= 0:
            return int(economy.get("cantrip_cost", 0))
        table = economy.get("cost_by_art_level", {}) or {}
        return int(table.get(str(art_level), 0))

    def invested_save_dc(self, proficiency_bonus: int, ability_modifier: int) -> int:
        """Invested save DC = 8 + proficiency + Investiture ability modifier."""
        return 8 + int(proficiency_bonus) + int(ability_modifier)

    def stormlight_for_long_rest(self, level: int) -> int:
        """Sapphire marks of Stormlight needed to benefit from a long rest."""
        return max(0, int(level)) * 5

    # ------------------------------------------------------------- integrity

    def unreviewed(self) -> List[Dict[str, Any]]:
        """
        Entries that must NOT adjudicate (plan D5).

        These are the extraction backlog: real rules exist in the Handbook, but
        nobody has read them into structured form and confirmed them yet.
        """
        out = []
        for bucket in ("maneuvers", "features"):
            for entry in self._data.get(bucket, []) or []:
                if not self._reviewed(entry):
                    out.append({"bucket": bucket, **entry})
        for name, entry in (self._data.get("orders", {}) or {}).items():
            if not self._reviewed(entry):
                out.append({"bucket": "orders", "name": name, **entry})
        return out

    def verify_citations(self, handbook_md: Path = HANDBOOK_MD) -> Dict[str, Any]:
        """
        Confirm every reviewed quote still appears at its cited line.

        Guards against silent drift: if the Handbook is re-parsed and line
        numbers shift, a "grounded" rule could quietly stop being grounded.
        """
        if not Path(handbook_md).exists():
            return {"checked": 0, "verified": 0, "mismatched": [],
                    "error": f"source not found: {handbook_md}"}

        lines = Path(handbook_md).read_text(encoding="utf-8").split("\n")

        def walk(obj, path=""):
            found = []
            if isinstance(obj, dict):
                if "source" in obj and "quote" in obj:
                    found.append((path or obj.get("id", "?"), obj["source"], obj["quote"]))
                for k, v in obj.items():
                    found += walk(v, f"{path}.{k}" if path else k)
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    found += walk(v, f"{path}[{i}]")
            return found

        checked = verified = 0
        mismatched = []
        for name, source, quote in walk(self._data):
            if not source.get("reviewed"):
                continue
            checked += 1
            line_no = int(source.get("line", 0))
            fragment = re.sub(r"\s+", " ", quote)[:60].strip().rstrip(".")
            window = re.sub(
                r"\s+", " ", " ".join(lines[max(0, line_no - 3): line_no + 3])
            )
            if fragment and fragment in window:
                verified += 1
            else:
                mismatched.append({"entry": name, "line": line_no,
                                   "fragment": fragment})

        if mismatched:
            logger.warning(f"⚠️ {len(mismatched)} Cosmere citation(s) no longer match "
                           f"the Handbook — rules may have drifted")
        return {"checked": checked, "verified": verified, "mismatched": mismatched}

    # ------------------------------------------------------------ DM support

    def describe_for_prompt(self, order: str) -> str:
        """
        A compact, citable rules summary for the DM prompt.

        This is what lets the DM narrate Surgebinding using the campaign's ACTUAL
        rules instead of inventing plausible numbers.
        """
        entry = self.order(order)
        if not entry:
            return ""

        economy = self.economy_for_order(order) or {}
        lines = [
            f"{entry['name']} — Surges: {', '.join(entry.get('surges', [])) or 'unknown'}",
        ]
        if economy:
            lines.append(
                f"Resource: {economy.get('name', '?')} "
                f"(recovery: {economy.get('recovery', '?')})"
            )
        maneuvers = self.maneuvers(order=order)
        if maneuvers:
            lines.append("Available Maneuvers:")
            for m in maneuvers:
                cost = ", ".join(f"{v} {k}" for k, v in (m.get("cost") or {}).items())
                lines.append(f"  - {m['name']} ({m.get('action_type', 'action')}"
                             f"{', ' + cost if cost else ''})")
        for f in self.features(order=order):
            lines.append(f"  * {f['name']}: {f.get('effect', {})}")
        return "\n".join(lines)


_GLOBAL: Optional[CosmereRules] = None


def get_cosmere_rules() -> CosmereRules:
    """Shared CosmereRules instance."""
    global _GLOBAL
    if _GLOBAL is None:
        _GLOBAL = CosmereRules()
    return _GLOBAL
