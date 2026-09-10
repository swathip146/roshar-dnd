#!/usr/bin/env python3
"""
Derive the per-CR HP/AC bands used by NPCStatGenerator from the SRD monster list.

The bands in `components/combat/npc_stat_generator.py` must come from DATA, not
from anyone's memory of the DMG. A first hand-written attempt capped CR 1/4 at
AC 13 — wrong, since the MM goblin is AC 15 — and an existing test caught it.

Run this after re-vendoring `data/rules/srd/` (scripts/vendor_srd_data.py) and
paste the output over `_CR_BANDS`:

    python scripts/derive_cr_bands.py

Columns: (hp_min, hp_max, ac_max, ev_max) where ev_max is the highest HP×AC of
any published monster at that CR. The EV term is what catches stat blocks whose
numbers are each individually legal but whose COMBINATION is not: a Dretch has
18 HP at CR 1/4, but at AC 11 — an 18 HP monster with AC 13 is harder than
anything published at that CR.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

SRD_MONSTERS = (Path(__file__).resolve().parent.parent
                / "data" / "rules" / "srd" / "monsters.json")

# Only CRs an encounter in this campaign plausibly uses. Above this the sample
# size per CR drops into single digits and the band stops being meaningful.
MAX_CR = 10.0
MIN_SAMPLE = 3


def _armor_class(monster: dict) -> int | None:
    """SRD 5.2 stores armor_class as a list of {type, value} entries."""
    value = monster.get("armor_class")
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return value[0].get("value")
    return value if isinstance(value, int) else None


def main() -> int:
    monsters = json.loads(SRD_MONSTERS.read_text())
    print(f"# derived from {len(monsters)} SRD monsters in {SRD_MONSTERS.name}")

    grouped: dict[float, list[tuple[int, int]]] = defaultdict(list)
    for monster in monsters:
        cr = monster.get("challenge_rating")
        hp = monster.get("hit_points")
        ac = _armor_class(monster)
        if (isinstance(cr, (int, float)) and not isinstance(cr, bool)
                and isinstance(hp, int) and isinstance(ac, int)
                and float(cr) <= MAX_CR):
            grouped[float(cr)].append((hp, ac))

    print("    _CR_BANDS = {")
    for cr in sorted(grouped):
        rows = grouped[cr]
        if len(rows) < MIN_SAMPLE:
            continue
        hps = [hp for hp, _ in rows]
        acs = [ac for _, ac in rows]
        ev_max = max(hp * ac for hp, ac in rows)
        key = f"{cr}:".ljust(7)
        print(f"        {key}({min(hps)}, {max(hps)}, {max(acs)}, {ev_max}),"
              f"   # n={len(rows)}")
    print("    }")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
