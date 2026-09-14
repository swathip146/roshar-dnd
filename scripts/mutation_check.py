#!/usr/bin/env python3
"""
Mutation check — does Suite A actually FAIL when the product is broken?

A passing suite proves the tests RUN, not that they would notice a defect. This breaks
real product code one change at a time and asserts the suite goes red.

    uv run python scripts/mutation_check.py     # ~8 min: reruns Suite A per mutant

It found a genuine hole. Three C14 cover tests asserted
`after == before + HALF_COVER_AC`, importing the very constant under test — a tautology.
Setting `HALF_COVER_AC = 0` makes the assertion read `after == before`, which is exactly
what the broken code produces, so cover could stop granting AC entirely while C14 still
reported ✅ PASS. Fixed by stating the 5e value as a literal and checking the constant
separately; the score went 7/8 -> 8/8.

Every mutant restores its file in a `finally`, so an interrupted run leaves the tree
clean. Add a mutant whenever a new mechanic is claimed as covered — a claim nothing can
falsify is not coverage.
"""

import pathlib, subprocess
M = [
 ("components/combat/tactical_rules.py","HALF_COVER_AC = 2","HALF_COVER_AC = 0","C14 cover AC"),
 ("components/character_manager.py","return 2 + ((level - 1) // 4)","return 2","P4 proficiency"),
 ("components/cosmere_rules.py","return 8 + int(proficiency_bonus) + int(ability_modifier)","return 8","R3 invested DC"),
 ("components/character_manager.py",'"speed_penalty": 10,','"speed_penalty": 0,',"E3 encumbrance speed"),
 ("components/character_manager.py",'character.hit_points["temporary"] = 0',"pass","C4 temp HP on rest"),
 ("components/combat/investiture_ledger.py",'pool["current"] = current - cost','pool["current"] = current',"R5 IP deduction"),
 ("components/character_manager.py","def get_carrying_capacity(self, character_id: str) -> Optional[int]:",
  "def get_carrying_capacity(self, character_id: str) -> Optional[int]:\n        return 9999","E3 capacity"),
 ("components/engine_patches.py","def _patch_advantage_rolls","def _unused_patch_advantage_rolls","C5 advantage patch off"),
]
def run():
    return subprocess.run(["uv","run","pytest","tests/integration/","-q","-p","no:randomly","-x","--timeout=200"],
                          capture_output=True, text=True).returncode
c=k=0
for path,old,new,label in M:
    p=pathlib.Path(path); src=p.read_text()
    if old not in src:
        print(f"SKIP      {label}"); continue
    p.write_text(src.replace(old,new,1))
    try: rc=run()
    finally: p.write_text(src)
    if rc!=0: c+=1; print(f"CAUGHT    {label}")
    else:     k+=1; print(f"SURVIVED  {label}   <-- GAP")
print(f"RESULT {c}/{c+k} caught ({c/(c+k):.0%})")
