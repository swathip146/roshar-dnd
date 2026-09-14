"""
Suite B live-turn checks — L1-L10 from the strategy's §8.

WHAT THIS ASSERTS, AND WHAT IT MUST NOT
---------------------------------------
Assert: invariant and statistical properties — non-empty narration, no placeholder
leakage, the §6 state invariants after every real turn, that the model actually calls
tools, that routing reaches all four pipelines, that combat reaches an outcome.

Never assert: specific wording, exact damage numbers, that a given monster appears, or
that the model chose a particular action. Those make the suite flaky and train people to
ignore it — which is worse than not having it.

The suite reuses Suite A's `harness/invariants.py` verbatim, so a live turn is held to
exactly the same state invariants as a deterministic one. If the two disagree, the
difference is the model's behaviour, not the yardstick.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from config.logging_config import get_logger
from tests.integration.harness import invariants

logger = get_logger(__name__)

#: Text that must never reach a player. A superset of Suite A's list: a live model can
#: also leak raw JSON or an apology when a tool fails.
PLACEHOLDER_MARKERS = (
    "TODO", "FIXME", "Lorem ipsum", "XXX", "<placeholder>",
    "{{", "}}", "None None", "I'm sorry, but I cannot", "As an AI language model",
    '"scene":',            # raw schema JSON leaking into narration
    "Traceback (most recent",
)

#: Narration shorter than this is almost certainly a failure, not a terse DM.
MIN_NARRATION_CHARS = 40


@dataclass
class CheckResult:
    name: str
    ok: Optional[bool]      # None == skipped
    detail: str = ""


@dataclass
class LiveTurnReport:
    """Accumulates per-turn observations across a live run."""

    results: List[CheckResult] = field(default_factory=list)
    narrations: List[str] = field(default_factory=list)
    turn_errors: List[str] = field(default_factory=list)

    def check(self, name: str, ok: bool, detail: str = "") -> bool:
        self.results.append(CheckResult(name, bool(ok), detail))
        logger.info("   %s %s%s", "✅" if ok else "❌", name,
                    f" — {detail}" if detail else "")
        return bool(ok)

    def skip(self, name: str, why: str) -> None:
        self.results.append(CheckResult(name, None, why))
        logger.info("   ⏭️  %s — skipped: %s", name, why)

    @property
    def failures(self) -> List[CheckResult]:
        return [r for r in self.results if r.ok is False]

    def summary(self) -> Dict[str, Any]:
        passed = sum(1 for r in self.results if r.ok is True)
        failed = len(self.failures)
        skipped = sum(1 for r in self.results if r.ok is None)
        return {
            "passed": passed, "failed": failed, "skipped": skipped,
            "failures": [{"check": r.name, "detail": r.detail} for r in self.failures],
        }


# --------------------------------------------------------------------------- #
# L1 / L10 — narration quality (properties, never wording)
# --------------------------------------------------------------------------- #

def check_narration(text: Optional[str], turn: int) -> List[str]:
    """L1: non-empty, no placeholder leakage, no raw schema."""
    problems: List[str] = []
    body = (text or "").strip()

    if not body:
        problems.append(f"turn {turn}: empty narration")
        return problems
    if len(body) < MIN_NARRATION_CHARS:
        problems.append(f"turn {turn}: narration only {len(body)} chars: {body!r}")
    for marker in PLACEHOLDER_MARKERS:
        if marker in body:
            problems.append(f"turn {turn}: placeholder {marker!r} reached the player")
    return problems


def check_narration_varies(narrations: List[str]) -> List[str]:
    """L1: a DM that repeats itself verbatim has stopped advancing the story."""
    bodies = [n.strip() for n in narrations if (n or "").strip()]
    if len(bodies) < 3:
        return []
    if len(set(bodies)) == 1:
        return [f"all {len(bodies)} turns produced identical narration"]
    # Repeated openings are the observed failure mode, not full duplication.
    openings = [b[:80] for b in bodies]
    duplicates = len(openings) - len(set(openings))
    if duplicates >= max(2, len(openings) // 2):
        return [f"{duplicates}/{len(openings)} turns reused the same opening sentence"]
    return []


# --------------------------------------------------------------------------- #
# L2 — the §6 state invariants, on live turns
# --------------------------------------------------------------------------- #

def check_state_invariants(game, turn: int) -> List[str]:
    """L2: reuse Suite A's invariants so live and scripted turns share one yardstick."""
    character_manager = getattr(game, "character_manager", None)
    if character_manager is None:
        return []

    combat_state = None
    engine = getattr(game, "game_engine", None)
    for holder in (engine, game):
        candidate = getattr(holder, "combat_state", None)
        if isinstance(candidate, dict) and candidate:
            combat_state = candidate
            break

    problems = invariants.collect(character_manager=character_manager,
                                  combat_state=combat_state)
    return [f"turn {turn}: {p}" for p in problems]


# --------------------------------------------------------------------------- #
# L3 — the model must actually use its tools
# --------------------------------------------------------------------------- #

def check_tools_were_used(recorder, turns: int,
                          min_distinct: int = 3) -> List[str]:
    """L3: over a real run the model must call several distinct DM tools.

    Zero tool calls means the DM narrated without adjudicating — the failure the
    two-phase turn exists to prevent, and exactly what "reachable in principle" hides.
    """
    problems: List[str] = []
    distinct = len(recorder.tools_reached)
    if not recorder.calls:
        problems.append(
            f"the model made ZERO tool calls across {turns} turns; every outcome was "
            f"narrated rather than adjudicated")
        return problems
    if distinct < min_distinct:
        problems.append(
            f"only {distinct} distinct tool(s) used across {turns} turns "
            f"({sorted(recorder.tools_reached)}); expected at least {min_distinct}")
    return problems


def check_no_tool_crashed(recorder) -> List[str]:
    """A tool the model invoked that RAISED is a real bug, not a model choice."""
    return [f"{call.name} raised on turn {call.turn}: {call.detail}"
            for call in recorder.failures()]


# --------------------------------------------------------------------------- #
# L5 — narration must not claim rolls that never happened
# --------------------------------------------------------------------------- #

#: Phrases that assert a mechanical outcome. If narration uses one, a die should have
#: been rolled somewhere in that turn.
ROLL_CLAIM_PHRASES = (
    "you hit", "you miss", "your attack", "the blow lands",
    "you succeed", "you fail", "check succeeds", "check fails",
    "roll of", "you rolled",
)


def check_claims_are_backed_by_rolls(narration: str, recorder,
                                     turn: int) -> List[str]:
    """L5: a turn whose prose asserts an outcome should have rolled for it.

    Reported as an OBSERVATION rather than a hard failure by default — see the caller.
    A model can legitimately narrate "you fail to find anything" after a tool already
    reported failure, and English is ambiguous. The value is in the ratio over a run.
    """
    body = (narration or "").lower()
    claims = [p for p in ROLL_CLAIM_PHRASES if p in body]
    if not claims:
        return []
    rolled = any(call.turn == turn and call.name in
                 ("roll_skill_check", "roll_dice", "roll_social_check", "cast_spell",
                  "apply_damage")
                 for call in recorder.calls)
    if rolled:
        return []
    return [f"turn {turn}: narration claims {claims[:2]} but no die was rolled"]


# --------------------------------------------------------------------------- #
# L4 — intent routing
# --------------------------------------------------------------------------- #

#: A fixed battery, so routing is comparable run to run rather than free-form.
#: The hint is the PIPELINE the input ought to reach, since that is what
#: `_run_interface_pipeline` returns as `route` — and what the game actually does.
#: Treated as a hint, never asserted per-input (see below).
ROUTING_BATTERY = [
    ("attack the nearest enemy with my spear", "combat_pipeline"),
    ("what does the rulebook say about grappling?", "rag_pipeline"),
    ("ask the bridgeman about the chasmfiend", "npc_pipeline"),
    ("search the abandoned camp for supplies", "scenario_pipeline"),
    ("tell me about the history of the Shattered Plains", "rag_pipeline"),
    ("check my inventory", "scenario_pipeline"),
]


def check_routing_reached_pipelines(observed: List[str],
                                    minimum: int = 3) -> List[str]:
    """L4: the battery must reach several distinct intents, not collapse to one.

    Not asserted per-input: intent classification is a judgement call and "search the
    camp" could reasonably route to scenario_action or world_lore. Collapsing EVERY
    input to one intent is the real defect — it means routing is not discriminating.
    """
    distinct = {o for o in observed if o}
    if not distinct:
        return ["intent classification produced no usable primary for any input"]
    if len(distinct) < minimum:
        return [f"the {len(observed)}-input battery collapsed to {len(distinct)} "
                f"intent(s) ({sorted(distinct)}); expected at least {minimum}"]
    return []


# --------------------------------------------------------------------------- #
# L6 — combat reaches an outcome
# --------------------------------------------------------------------------- #

def check_combat_resolved(game) -> List[str]:
    """L6: combat must end, and must not be left active forever."""
    engine = getattr(game, "game_engine", None)
    state = getattr(engine, "combat_state", None) or getattr(game, "combat_state", None)
    if not isinstance(state, dict) or not state:
        return []
    if state.get("active"):
        return ["combat is still marked active at the end of the run"]
    return []
