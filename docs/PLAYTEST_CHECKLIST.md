# How to play-test the game

**Purpose:** a checklist you can work through in one sitting to satisfy yourself
that each mechanic works *in play*. Each row gives you something to type and the
observable result to look for.

**Honest framing first.** Every mechanic below is wired and has tests, and the
automated gate is green. But on 2026-09-10, **six consecutive live runs each found
new defects after the test suite went green**, and four of the last five were
integration defects invisible to ~1,270 unit tests. So treat this as a checklist for
finding the *next* bug, not a formality. When something looks wrong, it usually is —
that instinct has been right every time this session.

```bash
./run_game.sh                                   # play
LLM_PROVIDER=floodgate ./scripts/playtest.py --turns 6   # automated gate first
```

Run the automated gate before you start. If it isn't green, play-testing will just
rediscover whatever it caught.

---

## 1. Before you start

| Check | How | Expected |
|---|---|---|
| Tests pass | `pytest tests/ -q --ignore=tests/combat -k "not test_gemini_ and not test_tool_calling and not test_api_connection and not test_game_"` | 886 passed |
| Combat tests pass | `pytest tests/combat/ -q` | 388 passed, 4 failed (all environmental — see below) |
| Automated gate | `LLM_PROVIDER=floodgate ./scripts/playtest.py --turns 6` | all checks pass, **0 errors logged** |
| Transport | `python -c "from config.floodgate import describe; print(describe())"` | prints the active provider, no secrets |

The 4 expected combat failures: three make real LLM calls and get HTTP 403 through a
sandboxed proxy (they should pass on your machine), and
`test_combat_agent_error_handling` expects an error from an empty DTO that combat now
tolerates.

**Delete any stale save first** — `rm -f game_saves/playtest_save.json`. A save from
an older format is how `current HP 13 / max 8` got into a live run.

---

## 2. The play-test script

Type these in order. The **Watch for** column is the actual assertion — if you see
something different, that is a bug worth reporting.

### A. Opening and state

| # | Type this | Watch for |
|---|---|---|
| A1 | *(start the game)* | Party panel shows **Aggi, L1 Radiant, HP 8/8, AC 14**. Not "Unknown" class, not 0 HP |
| A2 | `party` | Level, HP, AC, order and Ideal for each member. `current` never exceeds `maximum` |
| A3 | `I look around and take stock of my surroundings.` | A scene naming a **real** location, with 3-5 numbered choices. Some choices show `**Skill Check (DC n)**` |

### B. Skill checks — the 7-step pipeline

| # | Type this | Watch for |
|---|---|---|
| B1 | `I search the ground carefully for tracks or anything hidden.` | The DM states a **roll and a DC** ("rolled 7 against DC 11"), not just "you find nothing" |
| B2 | Repeat B1 three times | **Different rolls.** Identical results three times means the die isn't being rolled |
| B3 | `I try to leap across the chasm in a single bound.` | A *hard* DC (15+) and a plausible failure. If everything succeeds, difficulty isn't reaching the roll |

> **Why this matters:** the skill pipeline had zero production callers until recently
> — the game was "freeform improv wearing a d20 costume". And the requested DC used
> to be discarded, so DC 5 and DC 25 both resolved as 14.

### C. Combat

| # | Type this | Watch for |
|---|---|---|
| C1 | `I ready my weapon and advance towards whatever lies ahead.` | If a fight starts: an **initiative order**, then a round-by-round loop |
| C2 | *(in combat)* choose **Attack** | `💥 Hit! N damage dealt.` or `🎯 Miss!` — and **HP visibly falling** in the status panel |
| C3 | Keep attacking | Combat **ends** in `🎉 VICTORY!` or `💀 DEFEAT!` within ~10 rounds. Not 30+, and never `outcome: unknown` |
| C4 | Let your HP reach 0 | `🎲 death save: rolled N — 1✓/0✗`, then either `☠️ has died (3 failed death saves)` or `🛡️ is stable`. **Not** instant defeat at 0 HP |
| C5 | After combat, `party` | HP on the sheet **matches** what combat showed. A full-health party after a beating means damage isn't persisting |

> **Watch especially for:** every attack missing (was three separate bugs), HP stuck
> at full in the panel, or combat running 100+ rounds.

### D. Roshar mechanics

| # | Type this | Watch for |
|---|---|---|
| D1 | `I speak my oath: Life before death, strength before weakness, journey before destination.` | Ideal advances 0 → 1, acknowledged in the narration |
| D2 | `party` | `Ideal 1` and Stormlight shown for a Radiant |
| D3 | `I draw in Stormlight and lash myself upward.` | Stormlight **decreases**. Infinite Stormlight means the deduction isn't persisting |
| D4 | `What are the rules for Full Lashing?` | A cited answer from the **Radiant's Handbook**, not invented prose |

### E. World, travel and time

| # | Type this | Watch for |
|---|---|---|
| E1 | `Where can I go from here?` | Named exits |
| E2 | `I travel onwards to the next location.` | Location **changes**, and time advances (~4 hours) |
| E3 | `What time is it, and when is the next highstorm?` | A day number, part of day, and a countdown that **decreases** as you travel |
| E4 | `I make camp and take a long rest to recover.` | HP restored to maximum; the day advances |

### F. NPCs and quests

| # | Type this | Watch for |
|---|---|---|
| F1 | `I look for someone to talk to, and ask them about the Voidbringers.` | An NPC speaks in **quoted dialogue** — actual words, not "the guard responds to your action" |
| F2 | Ask the same NPC something else | They **remember** the earlier exchange |
| F3 | `What am I supposed to be doing?` | Current quest objectives, matching the campaign |
| F4 | Complete an objective | It is **recorded** — check with F3 again |

### G. Memory and continuity

| # | Type this | Watch for |
|---|---|---|
| G1 | Play 10+ turns, then `What has happened so far?` | Events from **early** turns, not just the last one |
| G2 | Check two consecutive scenes | Not **identical prose**. Repeated text means an LLM call failed and a canned scene was substituted |

### H. Save/load — do this last

| # | Type this | Watch for |
|---|---|---|
| H1 | `save` | Confirmation |
| H2 | `quit`, restart, `load` | HP, level, XP, equipment, location, quests and Ideal **all preserved** |
| H3 | `party` | Class is the real class, HP is what it was. Not "Unknown"/0 HP |

---

## 3. Red flags — stop and report

These each correspond to a bug fixed this session; recurrence means a regression.

| Symptom | What it meant last time |
|---|---|
| Every attack misses over several rounds | Entities not really on the grid (position index desynced) |
| Combat runs 30+ rounds or ends `unknown` | Action economy not reset at a round boundary |
| HP stuck at full while damage is narrated | HP written to the display, not the record |
| The same defeat narrated every turn | A wiped party being re-ambushed |
| A fight starts in an obviously peaceful scene | A keyword scan overriding the DM's `combat_trigger: false` |
| `The world seems momentarily confused by your action` | The turn's response was discarded |
| Identical narration on different turns | The LLM call failed; a canned scene was substituted |
| `current HP > maximum` anywhere | Stale save data |
| The DM invents a DC or a Stormlight cost | It stopped calling its tools |
| The DM cites a rule that isn't in the Handbook | Ungrounded adjudication |

---

## 4. Known gaps — expected, not bugs

Working as designed, or deliberately deferred. Don't spend time on these.

| Gap | Effect in play |
|---|---|
| **No tactical movement** | You cannot reposition, flank or take cover. The grid is a fixed two-row line; `move` is refused with a reason |
| **Exploding/reroll dice** | `4d6e6`, `1d20r1` are rejected with an error (deliberately loud rather than silently dealing 0) |
| **`Petrified`** | The one PHB condition the vendored engine lacks |
| **Rules long tail (2.10)** | Only Surgebinding and the SRD basics are structured Tier-1/2. Anything else is adjudicated by the rules judge and marked as a ruling |
| **Avrae automation schema** | Surges are code, not data. Adding a new surge needs code |
| **No economy / downtime / multiclassing / full spellcasting** | v2 backlog (D6) |
| **CLI only** | Streamlit UI is Phase 5 |

---

## 5. Is it worth releasing?

My honest read, stated as a recommendation rather than a verdict:

**Ready for you to play and for a small friendly audience.** The mechanics are wired,
the rules are RAW-correct where tested, the campaign has an authored spine and an
ending, and the automated gate exercises the whole turn loop.

**Not ready for an unattended public release**, for three reasons:

1. **The defect-discovery rate has not flattened.** Six live runs today, six new
   defects. That curve needs to flatten across several *clean* sessions before
   "no more bugs" is a claim anyone should make.
2. **No tactical movement.** For a D&D audience this is a conspicuous absence, not a
   subtle one — no flanking, cover, or AoE positioning.
3. **One player, one campaign, one path.** Party support exists (D3) but has not been
   played through. `Shards of Honor` has not been completed start to finish by
   anyone, which is D6's own definition of done.

**The one thing I'd fix before release:** tactical movement (~2-3 days). It is the
largest gap between this and what a player expects from 5e.

**The gate to keep:** `LLM_PROVIDER=floodgate ./scripts/playtest.py --turns 6` must
stay green, and don't run `pytest` at the same time — both write to
`logs/dnd_game_*.log`.
