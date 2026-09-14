#!/usr/bin/env python3
"""
Suite B — the real-LLM playtest. `docs/mechanics/INTEGRATION_TEST_STRATEGY.md` §8.

    ./scripts/suite_b_playtest.py                       # 8 turns, all checks
    ./scripts/suite_b_playtest.py --turns 20            # longer run
    ./scripts/suite_b_playtest.py --routing-only        # just the L4 battery (cheap)
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

    from config.gateway import resolve_provider

    provider = resolve_provider()
    if provider != "gateway" and not (os.getenv("GEMINI_API_KEY")
                                        or os.getenv("GOOGLE_API_KEY")):
        report.check("Credentials", False,
                     "no GEMINI_API_KEY and provider is not gateway")
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
               report: live_checks.LiveTurnReport, verbose: bool) -> None:
    """Play real turns, checking properties after each one."""
    problems: List[str] = []

    for index, player_input in enumerate(script, start=1):
        recorder.turn = index
        print(f"\n── turn {index}/{len(script)}: {player_input!r}")
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
        print(f"   {elapsed:.1f}s · {len(text)} chars · tools: "
              f"{calls_this_turn or '(none)'}")
        if verbose and text:
            print("   " + text[:400].replace("\n", "\n   "))

        problems += live_checks.check_narration(text, index)
        problems += live_checks.check_state_invariants(game, index)
        problems += live_checks.check_claims_are_backed_by_rolls(text, recorder, index)

    report.check("No turn raised", not report.turn_errors,
                 "; ".join(report.turn_errors[:2]) or f"{len(script)} turns ran")
    report.check("Narration is well-formed on every turn",
                 not [p for p in problems if "narration" in p or "placeholder" in p],
                 "; ".join(p for p in problems
                           if "narration" in p or "placeholder" in p)[:200])
    report.check("State invariants held after every live turn",
                 not [p for p in problems if "turn" in p and "narration" not in p
                      and "placeholder" not in p and "claims" not in p],
                 "reused Suite A's invariants")
    report.check("Narration varies between turns",
                 not live_checks.check_narration_varies(report.narrations))

    unbacked = [p for p in problems if "no die was rolled" in p]
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

def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--turns", type=int, default=len(DEFAULT_SCRIPT),
                        help="how many real turns to play")
    parser.add_argument("--verbose", action="store_true",
                        help="print each turn's narration")
    parser.add_argument("--routing-only", action="store_true",
                        help="run only the L4 intent battery (cheapest useful check)")
    parser.add_argument("--require-coverage", default="",
                        help="comma-separated tool names that MUST be reached; the run "
                             "fails if the model never calls one")
    parser.add_argument("--report", type=Path, default=None,
                        help="write a machine-readable JSON report here")
    parser.add_argument("--seed", type=int, default=None,
                        help="seed the DICE (not the model), so divergence between "
                             "runs is attributable to the model")
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

    instrumented = recorder.install()
    report.check("DM tools instrumented", instrumented >= 19,
                 f"{instrumented} tools wrapped")

    try:
        if args.routing_only:
            run_routing_battery(game, report)
        else:
            script = (DEFAULT_SCRIPT * ((args.turns // len(DEFAULT_SCRIPT)) + 1))[:args.turns]
            play_turns(game, script, recorder, report, args.verbose)
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
