#!/usr/bin/env python3
"""
Vendor the SRD 5e dataset — Tier 1 of the rules architecture (plan 2.9, §8).

Downloads structured SRD JSON from 5e-bits/5e-database (932★, MIT; the data
itself is SRD content under OGL 1.0a) into data/rules/srd/.

Why vendor rather than hand-author: the plan is explicit that 334 monsters plus
all spells, conditions and equipment should come from a maintained dataset, not
be transcribed. Why vendor rather than call their API at runtime: a live HTTP
dependency in the turn loop is a failure mode we do not need.

    Tier 1  data/rules/srd/          <- THIS (baseline D&D 5e)   } code
    Tier 2  data/rules/stormlight/   <- Cosmere/Surgebinding     } adjudicates
    Tier 3  Qdrant vectors           <- narrative lore, never adjudicates

Usage:
    conda run -n dndenv python scripts/vendor_srd_data.py
    conda run -n dndenv python scripts/vendor_srd_data.py --check   # verify only
"""

import argparse
import json
import sys
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRD_DIR = PROJECT_ROOT / "data" / "rules" / "srd"

RAW_BASE = ("https://raw.githubusercontent.com/5e-bits/5e-database/"
            "main/src/2014/en")

# The files we actually adjudicate from. Deliberately NOT the whole repo:
# Features/Levels/Equipment-Categories are large and unused for now.
FILES = {
    "monsters": "5e-SRD-Monsters.json",
    "spells": "5e-SRD-Spells.json",
    "conditions": "5e-SRD-Conditions.json",
    "equipment": "5e-SRD-Equipment.json",
    "magic_items": "5e-SRD-Magic-Items.json",
    "rules": "5e-SRD-Rules.json",
    "skills": "5e-SRD-Skills.json",
    "damage_types": "5e-SRD-Damage-Types.json",
    "weapon_properties": "5e-SRD-Weapon-Properties.json",
    "ability_scores": "5e-SRD-Ability-Scores.json",
}

ATTRIBUTION = """\
# SRD 5e data — Tier 1 rules

Source: https://github.com/5e-bits/5e-database (`src/2014/en`)

The repository is MIT-licensed; the DATA is System Reference Document content
distributed under the **Open Gaming License 1.0a**. It is vendored here rather
than fetched at runtime so the turn loop has no live HTTP dependency, and rather
than hand-authored because a maintained dataset already exists (plan §8).

Downloaded by `scripts/vendor_srd_data.py`. Re-run that script to refresh.
"""


def fetch(name: str, filename: str) -> dict:
    url = f"{RAW_BASE}/{filename}"
    print(f"  ↓ {name:18} {filename}")
    with urllib.request.urlopen(url, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="report what is present without downloading")
    args = ap.parse_args()

    if args.check:
        if not SRD_DIR.exists():
            print(f"❌ {SRD_DIR} does not exist — run without --check to vendor")
            return 1
        total = 0
        for name in FILES:
            path = SRD_DIR / f"{name}.json"
            if path.exists():
                data = json.loads(path.read_text())
                n = len(data) if isinstance(data, list) else len(data.keys())
                total += n
                print(f"  ✅ {name:18} {n:>5} entries")
            else:
                print(f"  ❌ {name:18} MISSING")
        print(f"\n{total} SRD entries vendored")
        return 0

    SRD_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Vendoring SRD 5e data -> {SRD_DIR}\n")

    failures = []
    counts = {}
    for name, filename in FILES.items():
        try:
            data = fetch(name, filename)
            (SRD_DIR / f"{name}.json").write_text(
                json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8"
            )
            counts[name] = len(data) if isinstance(data, list) else len(data)
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            failures.append(name)

    (SRD_DIR / "README.md").write_text(ATTRIBUTION, encoding="utf-8")

    print()
    for name, n in counts.items():
        print(f"  {name:18} {n:>5} entries")
    print(f"\n{'❌ ' + str(len(failures)) + ' failed' if failures else '✅ complete'}"
          f" — {sum(counts.values())} entries total")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
