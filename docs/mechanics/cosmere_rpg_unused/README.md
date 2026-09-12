# Cosmere RPG (Brotherwise) — NOT USED

**Set aside 2026-09-12.** These four documents catalogue the **standalone Cosmere RPG** by
Brotherwise Games. The project does **not** implement it.

## What the project uses instead

**Cosmere 5e** — the *Radiant's Handbook* plus *The Invested Arts of the Cosmere (v2.0)*.
See `../COSMERE_SYSTEMS_MAP.md`.

The reason is that the codebase already *is* a D&D 5e engine: it vendors
`external/dnd_engine`, carries 1,321 entries of 2014 SRD data, and computes AC, saving
throws, proficiency and concentration. Cosmere 5e is built on that same chassis, so those
books pair with the engine. The standalone Cosmere RPG would require replacing it.

## Why these are kept rather than deleted

The feasibility audit here contains the *measured* evidence for that decision. Deleting it
would leave the decision looking arbitrary, and would invite someone to re-litigate it from
scratch. Concretely, it demonstrated live that a Cosmere RPG attribute of `3` — which **is**
a +3 in that system — becomes **−4** when read through 5e's `(score-10)//2`, with no error
raised. Silent corruption, which is why a partial retrofit would be worse than either
system alone.

## The files

| File | Contents |
|---|---|
| `COSMERE_RPG_CORE.md` | The system: plot die, three Defenses, Focus, grazing, Deflect, fast/slow turns, 13 conditions, injury rolls, 165 mechanic rows |
| `COSMERE_RPG_SURGEBINDING.md` | Its Radiant/setting material. **0 of 10 surges specified** — it defers to a full *Stormlight Handbook* we don't have (cited 20×) |
| `AUDIT_COSMERE_RPG_FEASIBILITY.md` | Why the 5e engine cannot host it, with live evidence |
| `AUDIT_STORMLIGHT_CONTENT.md` | **Content, not rules** — see the note below; still useful |

## `AUDIT_STORMLIGHT_CONTENT.md` is still worth reading

It audits *content* rather than mechanics, and most of its findings are
system-independent — fiction ports even when rules don't:

- **~14,800 lines of new material are 0% indexed into Qdrant.** The indexer already works,
  so this is pure upside regardless of system.
- **The Rosharan bestiary is absent from the repo entirely.** 334 D&D monsters, zero
  Rosharan creatures — which is why a Roshar campaign currently fights goblins. It lives in
  an unacquired *Creature Compendium*.
- The Rosharan currency table (spheres: chip/mark/broam × 5 gems), 11 weapons and 6 armors
  exist as data in the Starter Rules and nowhere in `data/rules/`.
- A second pregen pack (`sl007-bridge-nine-pregens`) and three complete fan scenarios,
  structurally richer than anything currently in the project.

The 20 pregenerated characters and the adversary stat blocks are Cosmere-RPG-shaped, so
they would need conversion — but the *characters, places and creatures* they describe are
reusable.

## If this decision is ever revisited

Read `AUDIT_COSMERE_RPG_FEASIBILITY.md` first. It costs out three options — keep 5e, dual
support, or migrate — and recommends against dual support specifically, because the 5e
assumptions fail quietly rather than loudly.
