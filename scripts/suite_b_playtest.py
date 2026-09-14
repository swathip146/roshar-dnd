#!/usr/bin/env python3
"""
Suite B — the real-LLM playtest. `docs/mechanics/INTEGRATION_TEST_STRATEGY.md` §8.

    ./scripts/suite_b_playtest.py                       # 8 turns, all checks
    ./scripts/suite_b_playtest.py --turns 20            # longer run
    ./scripts/suite_b_playtest.py --routing-only        # just the L4 battery (cheap)
    ./scripts/suite_b_playtest.py --full-coverage       # 20 turns, one per DM tool
    ./scripts/suite_b_playtest.py --require-coverage roll_skill_check,query_rules
    ./scripts/suite_b_playtest.py --report out.json     # machine-readable
    ./scripts/suite_b_playtest.py --seed 7              # seed the DICE, not the model

WHAT THIS ANSWERS THAT SUITE A CANNOT
-------------------------------------
Suite A (146 tests, all 57 mechanic rows) proves every mechanic WORKS, using a scripted
policy that is a competent DM by construction. This asks whether a REAL model, given the
real prompts, ever reaches those mechanics. A mechanic that is correct but never
triggered is invisible to players.

**The gap between the two is this script's product.** It prints
"reached by the LLM" vs "never reached", and that delta is the review artifact.

COST
----
~2-5 LLM calls per turn on Gemini Flash, so a default 8-turn run is well under a cent.
Exit 0 = every check passed.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "external" / "dnd_engine"))

from tests.llm_playtest import live_checks  # noqa: E402
from tests.llm_playtest.instrumentation import (  # noqa: E402
    ToolCallRecorder,
    coverage_report,
    write_report,
)

#: Inputs chosen to invite DIFFERENT mechanics, so a run has a chance of reaching
#: skills, lore, social, inventory, rest and travel. Deliberately phrased as a player
#: would, not as instructions to call a tool — the point is whether the model decides
#: to adjudicate on its own.
DEFAULT_SCRIPT = [
    "look around carefully for tracks or movement",
    "ask the nearest soldier what happened here",
    "search the abandoned camp for anything useful",
    "what do I know about chasmfiends?",
    "check what I am carrying",
    "try to climb the rock formation for a better view",
    "make camp and rest until morning",
    "head toward the warcamp",
]

#: `--full-coverage`: one turn per tool, each phrased to make ONE tool the obvious
#: choice. Still player-phrased — never "call award_experience" — because the thing
#: under test is whether the model maps intent to the right tool. The `expects` column
#: is the tool this turn is TRYING to provoke, so a run reports per-turn hit/miss
#: rather than only an aggregate.
#:
#: Ordering matters: damage before healing and stabilising (something must be hurt
#: first), and the two inventory turns are adjacent so the remove has something to
#: remove.
#:
#: SOME MISSES ARE STRUCTURAL, NOT PROMPT FAILURES — read a report with that in mind:
#:   * `cast_spell` — the default campaign character is a **Lightweaver**, and
#:     `spellcasting_ability("Lightweaver")` is None. A Radiant has no spell slots;
#:     healing is Regrowth paid in Investiture. So "cast a healing spell" has no
#:     cast_spell path for THIS party, and the turn correctly does not force one.
#:     Verified separately: `cast_spell` DOES fire live for "heal my wounds with
#:     Regrowth" when the surge route is available.
#:   * `stabilize_dying` — needs an ally actually at 0 HP. Narrating a collapse does
#:     not create one, and Suite B must not fake state to make a tool fire.
#:   * `get_passive_perception` — only meaningful when something is hidden.
#: Those three are situational. `search_lore`, `roll_social_check`,
#: `travel_to_location` and `apply_healing` are NOT: they have a live path and the
#: model still does not choose them, which is prompt work.
COVERAGE_SCRIPT: List[tuple] = [
    ("look around carefully for tracks or movement", "roll_skill_check"),
    ("who is in the party and how are they holding up?", "get_party_state"),
    ("what is my character's condition right now?", "get_character_state"),
    ("what time is it and what is the weather doing?", "get_world_state"),
    ("what is my passive perception for spotting a hidden ambush?",
     "get_passive_perception"),
    ("what does the rulebook say about grappling a larger creature?",
     "query_rules"),
    ("roll a d20 for me to see how the wind shifts", "roll_dice"),
    ("tell me the lore of the Knights Radiant and the Oathpact", "search_lore"),
    ("try to persuade Nale to let us through the gate", "roll_social_check"),
    ("I stumble into the chasm and scrape myself badly on the rocks",
     "apply_damage"),
    ("use a healing potion from my pack to restore my hit points",
     "apply_healing"),
    ("my companion has collapsed and is bleeding out — I tend to them",
     "stabilize_dying"),
    ("draw in Stormlight and lash myself upward", "spend_stormlight"),
    ("heal my wounds with Regrowth", "cast_spell"),
    ("pick up the rope and spear lying in the camp", "add_item_to_inventory"),
    ("drop the rope, it is too heavy to carry", "remove_item_from_inventory"),
    ("make camp and take a long rest until morning", "take_rest"),
    ("set out and travel to Kholinar", "travel_to_location"),
    ("we have found Herald Kalak — that completes what we set out to do",
     "advance_quest"),
    ("we survived that and learned a great deal; the party has earned it",
     "award_experience"),
]


class ScriptedInput:
    """Answers `game_initialization`'s prompts without a terminal."""

    def __init__(self, answers: List[str]):
        self.answers = list(answers)
        self.index = 0

    def __call__(self, prompt: str = "") -> str:
        value = self.answers[self.index] if self.index < len(self.answers) else ""
        self.index += 1
        return value


# --------------------------------------------------------------------------- #

def build_live_game(report: live_checks.LiveTurnReport):
    """Initialise the REAL game: real orchestrator, real agents, real LLM."""
    try:
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        pass

    # Optional machine-local gateway; absent, the direct Gemini API is used.
    try:
        from config.gateway import resolve_provider

        provider = resolve_provider()
    except ImportError:
        provider = "gemini"
    if provider != "gateway" and not (os.getenv("GEMINI_API_KEY")
                                        or os.getenv("GOOGLE_API_KEY")):
        report.check("Credentials", False,
                     "no GEMINI_API_KEY and provider is not the local gateway")
        return None
    print(f"   transport: {provider}")

    # `GameInitializationSystem` now takes an input_provider (added while building
    # Suite A), so this no longer has to monkey-patch builtins.input.
    from core.game_initialization import GameInitializationSystem
    from haystack_dnd_game import HaystackDnDGame

    answers = ScriptedInput(["", "1", "1", "1", "1", "1"])
    system = GameInitializationSystem(input_provider=answers)
    config = system.initialize_game()
    game = HaystackDnDGame(config=config)
    return game


def play_turns(game, script: List[str], recorder: ToolCallRecorder,
               report: live_checks.LiveTurnReport, verbose: bool,
               expectations: Optional[List[str]] = None) -> None:
    """Play real turns, checking properties after each one.

    `expectations[i]` names the tool turn i is TRYING to provoke (`--full-coverage`).
    A miss is reported per turn but is NOT a failure: the model declining to call a
    tool is data about the prompts, not a broken mechanic. Only a crash is a failure.
    """
    narration_problems: List[str] = []
    invariant_problems: List[str] = []
    unbacked_claims: List[str] = []
    hits: List[str] = []
    misses: List[tuple] = []

    for index, player_input in enumerate(script, start=1):
        recorder.turn = index
        wanted = (expectations[index - 1] if expectations
                  and index <= len(expectations) else None)
        label = f" [want {wanted}]" if wanted else ""
        print(f"\n── turn {index}/{len(script)}: {player_input!r}{label}")
        started = time.time()
        try:
            narration = game.play_turn(player_input)
        except Exception as exc:  # noqa: BLE001
            report.turn_errors.append(f"turn {index}: {type(exc).__name__}: {exc}")
            traceback.print_exc()
            continue
        elapsed = time.time() - started

        text = str(narration or "")
        report.narrations.append(text)
        calls_this_turn = [c.name for c in recorder.calls if c.turn == index]

        mark = ""
        if wanted:
            if wanted in calls_this_turn or wanted in recorder.tools_reached:
                mark = "  ✅ hit"
                hits.append(wanted)
            else:
                mark = f"  ⚠️  missed {wanted}"
                misses.append((wanted, player_input))
        print(f"   {elapsed:.1f}s · {len(text)} chars · tools: "
              f"{calls_this_turn or '(none)'}{mark}")
        if verbose and text:
            print("   " + text[:400].replace("\n", "\n   "))

        narration_problems += live_checks.check_narration(text, index)
        invariant_problems += live_checks.check_state_invariants(game, index)
        unbacked_claims += live_checks.check_claims_are_backed_by_rolls(
            text, recorder, index)

    report.check("No turn raised", not report.turn_errors,
                 "; ".join(report.turn_errors[:2]) or f"{len(script)} turns ran")
    report.check("Narration is well-formed on every turn",
                 not narration_problems, "; ".join(narration_problems)[:200])
    report.check("State invariants held after every live turn",
                 not invariant_problems,
                 "; ".join(invariant_problems)[:200] or "reused Suite A's invariants")
    report.check("Narration varies between turns",
                 not live_checks.check_narration_varies(report.narrations))

    if expectations:
        # Reported, never asserted: a per-turn miss is prompt data. `--require-coverage`
        # is how a caller turns a specific tool into a hard requirement.
        report.skip("Per-turn tool targeting",
                    f"{len(hits)}/{len(expectations)} turns provoked their target tool")
        if misses:
            print("\n  turns whose target tool was never called:")
            for wanted, prompt in misses:
                print(f"     ⚠️  {wanted:28s} <- {prompt[:52]!r}")

    unbacked = unbacked_claims
    if unbacked:
        # An OBSERVATION, not a failure: English is ambiguous and the model may be
        # narrating a result a tool already produced. The ratio is what matters.
        report.skip("Every outcome claim backed by a roll",
                    f"{len(unbacked)}/{len(script)} turns — review: {unbacked[0][:90]}")
    else:
        report.check("Every outcome claim backed by a roll", True)


def run_routing_battery(game, report: live_checks.LiveTurnReport) -> List[str]:
    """L4: does intent classification discriminate between kinds of input?"""
    observed: List[str] = []
    print("\n── intent routing battery")
    for player_input, expected in live_checks.ROUTING_BATTERY:
        try:
            classified = classify(game, player_input)
        except Exception as exc:  # noqa: BLE001
            print(f"   ⚠️  {player_input[:40]!r} raised {type(exc).__name__}: {exc}")
            observed.append("")
            continue
        observed.append(classified)
        mark = "≈" if classified != expected else "="
        print(f"   {mark} {player_input[:46]!r:50s} -> {classified or '(none)'} "
              f"(hint: {expected})")

    report.check("Intent routing discriminates between input kinds",
                 not live_checks.check_routing_reached_pipelines(observed),
                 f"distinct intents: {sorted({o for o in observed if o})}")
    return observed


def classify(game, player_input: str) -> str:
    """Run ONE real intent classification and return the pipeline it routed to.

    The real entry point is `PipelineOrchestrator._run_interface_pipeline(dto)`
    (`orchestrator/pipeline_integration.py:655`) — it takes a RequestDTO, not a bare
    string, and returns a DTO whose `route` key names the chosen pipeline. There is no
    `classify_player_intent` method on the orchestrator; that function lives in
    `agents/main_interface_agent_fixed.py` and post-processes the LLM's output.
    """
    orchestrator = getattr(game, "orchestrator", None)
    if orchestrator is None:
        return ""
    runner = getattr(orchestrator, "_run_interface_pipeline", None)
    if not callable(runner):
        return ""

    dto: Dict[str, Any] = {
        "player_input": player_input,
        "request_type": "gameplay_turn",
        "_game_engine_ref": getattr(game, "game_engine", None),
        "_policy_engine_ref": getattr(game, "policy_engine", None),
    }
    result = runner(dto) or {}
    # `route` is the routing decision (what the game will actually DO); `primary` is
    # the model's own label. Prefer route, since that is the observable behaviour.
    return str(result.get("route")
               or (result.get("intent") or {}).get("primary")
               or result.get("type") or "")


# --------------------------------------------------------------------------- #

def _accumulate(path: Path, reached: set) -> set:
    """Merge this run's reached-tool set into `path` and return the union.

    The model is nondeterministic in which tools it picks: two 20-turn runs each
    reached 12 of 20, but not the SAME 12 (union 13). A single run therefore
    understates real reach, and "never reached in ANY run" is the honest measure of a
    genuinely unreachable tool.
    """
    previous: set = set()
    runs = 0
    if path.exists():
        try:
            cached = json.loads(path.read_text())
            previous = set(cached.get("reached", []))
            runs = int(cached.get("runs_merged", 0) or 0)
        except Exception:  # noqa: BLE001 - a corrupt cache must not fail the run
            previous, runs = set(), 0
    union = previous | set(reached)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(
        {"reached": sorted(union), "runs_merged": runs + 1}, indent=2))
    return union


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--turns", type=int, default=len(DEFAULT_SCRIPT),
                        help="how many real turns to play")
    parser.add_argument("--verbose", action="store_true",
                        help="print each turn's narration")
    parser.add_argument("--routing-only", action="store_true",
                        help="run only the L4 intent battery (cheapest useful check)")
    parser.add_argument("--full-coverage", action="store_true",
                        help="one turn per DM tool (20 turns), each phrased to make "
                             "ONE tool the obvious choice; reports per-turn hit/miss")
    parser.add_argument("--require-coverage", default="",
                        help="comma-separated tool names that MUST be reached; the run "
                             "fails if the model never calls one")
    parser.add_argument("--report", type=Path, default=None,
                        help="write a machine-readable JSON report here")
    parser.add_argument("--seed", type=int, default=None,
                        help="seed the DICE (not the model), so divergence between "
                             "runs is attributable to the model")
    parser.add_argument("--accumulate", type=Path, default=None,
                        metavar="FILE",
                        help="merge this run's reached-tool set into FILE and report "
                             "the UNION across runs. The model is nondeterministic — "
                             "two 20-turn runs each reached 12/20 but different 12s "
                             "(union 13/20) — so a single run understates real reach.")
    args = parser.parse_args()

    print("=" * 70)
    print("SUITE B — real-LLM playtest (docs/mechanics/INTEGRATION_TEST_STRATEGY.md §8)")
    print("=" * 70)

    if args.seed is not None:
        random.seed(args.seed)
        print(f"   dice seeded with {args.seed}")

    report = live_checks.LiveTurnReport()
    recorder = ToolCallRecorder()

    print("\n🎮 Initialising the FULL game (real LLM)")
    try:
        game = build_live_game(report)
    except Exception as exc:  # noqa: BLE001
        report.check("Game initialisation", False, f"{type(exc).__name__}: {exc}")
        traceback.print_exc()
        game = None
    if game is None:
        print(json.dumps(report.summary(), indent=2))
        return 1
    print("   ✅ live game ready")

    # Combat asks the player to choose an action. Without a provider the encounter
    # stalls at "Choose how you want to start:" and the turn returns a stub — so a
    # combat turn could never be measured. `CombatAgent.input_provider` is the
    # documented seam (plan 1.8/D4, `agents/combat_agent.py:72`); "1" takes the first
    # offered action every time, which is enough to drive a fight to an outcome.
    combat_agent = (getattr(game.orchestrator, "agents", {}) or {}).get("combat")
    if combat_agent is not None:
        combat_agent.input_provider = lambda prompt="": "1"
        print("   ⚔️  combat input provider wired (always takes action 1)")

    instrumented = recorder.install()
    report.check("DM tools instrumented", instrumented >= 19,
                 f"{instrumented} tools wrapped")

    try:
        if args.routing_only:
            run_routing_battery(game, report)
        else:
            if args.full_coverage:
                script = [prompt for prompt, _ in COVERAGE_SCRIPT]
                expectations = [tool for _, tool in COVERAGE_SCRIPT]
                if args.turns != len(DEFAULT_SCRIPT):   # an explicit --turns wins
                    script, expectations = script[:args.turns], expectations[:args.turns]
            else:
                script = (DEFAULT_SCRIPT
                          * ((args.turns // len(DEFAULT_SCRIPT)) + 1))[:args.turns]
                expectations = None
            play_turns(game, script, recorder, report, args.verbose, expectations)
            run_routing_battery(game, report)

            report.check("The model used its DM tools",
                         not live_checks.check_tools_were_used(recorder, len(script)),
                         f"{len(recorder.calls)} calls across "
                         f"{len(recorder.tools_reached)} distinct tools")
            report.check("No DM tool crashed when the model called it",
                         not live_checks.check_no_tool_crashed(recorder),
                         "; ".join(live_checks.check_no_tool_crashed(recorder))[:200])
            report.check("Combat is not left running",
                         not live_checks.check_combat_resolved(game))
    finally:
        recorder.restore()

    # ---------------------------------------------------------------- coverage
    coverage = coverage_report(recorder)
    print("\n" + "=" * 70)
    print("SUITE A ↔ SUITE B GAP — the product of this run")
    print("=" * 70)
    print(f"  tools the live model reached : {len(coverage['reached_by_llm'])}"
          f" ({coverage['reach_ratio']:.0%})")
    for name in coverage["reached_by_llm"]:
        print(f"     ✅ {name} x{recorder.counts[name]}")
    if coverage["never_reached_by_llm"]:
        print(f"\n  NEVER reached by the model (Suite A covers these, real play did not):")
        for name in coverage["never_reached_by_llm"]:
            print(f"     ⚠️  {name}")
        print("\n  These are correct-but-invisible: the mechanic works (Suite A proves")
        print("  it) yet the prompts never lead the model to use it. That is a PROMPT")
        print("  gap, not a mechanics gap — and it is what this suite exists to find.")

    if args.accumulate:
        union = _accumulate(args.accumulate, set(coverage["reached_by_llm"]))
        all_tools = set(coverage["reached_by_llm"]) | set(
            coverage["never_reached_by_llm"])
        print(f"\n  UNION across accumulated runs: {len(union)}/{len(all_tools)} "
              f"({len(union) / max(1, len(all_tools)):.0%})")
        still_missing = sorted(all_tools - union)
        if still_missing:
            print(f"     never reached in ANY run: {still_missing}")

    required = [t.strip() for t in args.require_coverage.split(",") if t.strip()]
    if required:
        missing = sorted(set(required) - recorder.tools_reached)
        report.check("Required tools were reached", not missing,
                     f"missing: {missing}" if missing else f"all of {required}")

    payload = {
        "summary": report.summary(),
        "turns": len(report.narrations),
        "tool_calls": recorder.summary(),
        "coverage": coverage,
    }
    if args.report:
        write_report(args.report, payload)

    print("\n" + "=" * 70)
    summary = report.summary()
    print(f"  {summary['passed']} passed · {summary['failed']} failed · "
          f"{summary['skipped']} skipped")
    for failure in summary["failures"]:
        print(f"     ❌ {failure['check']}: {failure['detail'][:160]}")
    print("=" * 70)
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
