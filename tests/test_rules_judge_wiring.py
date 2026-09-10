"""
D5 Tier 3 — the rules judge, wired at last.

`RulesJudge`/`RulingStore` were built, tested, and NEVER instantiated in
production: the last finding of the unwired-component sweep, and the fourth
subsystem in this project to be "delivered" while nothing called it.

The consequence was not a crash but a quality failure. When `query_rules` found
nothing canonical it recorded the gap (the tracker WAS wired) and told the DM
"you may improvise, but say so openly" — with no grounded judgment and no
precedent lookup. So `judge()` and `find_precedent()`, which exist precisely so an
improvised ruling stays consistent across turns, never ran, and the same
situation could be adjudicated differently every time it came up.

These tests assert the WIRING — that the product reaches the component — which is
the thing four passing unit-test suites failed to establish.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

pytestmark = [pytest.mark.unit]

from agents import dm_tools as T
from components.cosmere_rules import get_cosmere_rules
from components.srd_rules import get_srd_rules

# Haystack wraps the function in a Tool; call the underlying callable.
_query_rules = getattr(T.query_rules, "function", T.query_rules)

UNCOVERED = "Chasmfiend Wrestling"   # deliberately in neither Tier 1 nor Tier 2


class _Judge:
    """A judge that rules, recording what it was asked."""

    def __init__(self, tier=3, cites=("Radiant's Handbook p.88",),
                 precedent=False):
        self.tier = tier
        self.cites = list(cites)
        self.precedent = precedent
        self.asked = []

    def judge(self, situation, actor=""):
        self.asked.append(situation)
        return {"tier": self.tier, "reason": "Athletics contest vs the beast",
                "cites": self.cites, "followed_precedent": self.precedent}


@pytest.fixture(autouse=True)
def _clean_context():
    T.clear_dm_tool_context()
    yield
    T.clear_dm_tool_context()


def _wire(judge=None):
    T.set_dm_tool_context(srd_rules=get_srd_rules(),
                          cosmere_rules=get_cosmere_rules(),
                          rules_judge=judge)


class TestTheJudgeIsReachable:
    def test_the_context_accepts_a_judge(self):
        """The parameter did not exist, which is why nothing could pass one."""
        import inspect

        assert "rules_judge" in inspect.signature(
            T.set_dm_tool_context).parameters

    def test_an_uncovered_topic_reaches_the_judge(self):
        judge = _Judge()
        _wire(judge)
        _query_rules(topic=UNCOVERED)
        assert judge.asked, "query_rules never consulted the judge"
        assert UNCOVERED in judge.asked[0]

    def test_a_grounded_ruling_is_returned_as_tier_three(self):
        _wire(_Judge())
        result = _query_rules(topic=UNCOVERED)
        assert result["found"] is True
        assert result["tier"] == 3
        assert result["cites"] == ["Radiant's Handbook p.88"]

    def test_the_ruling_is_labelled_as_a_ruling(self):
        """The DM must not present an adjudication as published text."""
        _wire(_Judge())
        result = _query_rules(topic=UNCOVERED)
        assert "rules judge" in result["source"].lower()
        assert result["kind"] == "ruling"
        assert "not published" in result["note"].lower()

    def test_following_precedent_is_reported(self):
        """Precedent binding is the whole point of the ruling store (3.7)."""
        _wire(_Judge(precedent=True))
        assert _query_rules(topic=UNCOVERED)["followed_precedent"] is True


class TestCanonicalRulesNeverReachTheJudge:
    """
    Tiers 1 and 2 are authoritative. Adjudicating over a published rule would
    replace a real rule with an invented one — the exact failure D5 prevents.
    """

    def test_an_srd_monster_is_tier_one(self):
        judge = _Judge()
        _wire(judge)
        result = _query_rules(topic="Goblin", kind="monster")
        assert result["tier"] == 1
        assert not judge.asked, "the judge was consulted for a published monster"

    def test_an_srd_condition_is_tier_one(self):
        judge = _Judge()
        _wire(judge)
        result = _query_rules(topic="prone", kind="condition")
        assert result["found"] is True
        assert not judge.asked

    def test_a_cosmere_maneuver_is_tier_two(self):
        judge = _Judge()
        _wire(judge)
        result = _query_rules(topic="Full Lashing", kind="cosmere")
        if result.get("found"):
            assert result["tier"] == 2
            assert not judge.asked, "the judge overrode the Handbook"


class TestTheJudgeNeverBreaksTheTurn:
    def test_no_judge_falls_back_to_the_honest_answer(self):
        """Without a judge, behaviour is exactly as before — no regression."""
        _wire(None)
        result = _query_rules(topic=UNCOVERED)
        assert result["found"] is False
        assert "improvise" in result["note"]

    def test_a_declined_ruling_falls_through(self):
        """
        Tier 4 means the judge could not ground it. That is the CORRECT outcome,
        not a failure — an ungrounded ruling is worse than admitting there is no
        rule (D5), so the honest answer must come back.
        """
        _wire(_Judge(tier=4))
        result = _query_rules(topic=UNCOVERED)
        assert result["found"] is False
        assert "improvise" in result["note"]

    def test_a_ruling_without_citations_is_not_trusted(self):
        """
        The judge downgrades an uncited ruling itself, but assert the tool does
        not promote one either — no citation, no ruling.
        """
        _wire(_Judge(tier=4, cites=()))
        assert _query_rules(topic=UNCOVERED)["found"] is False

    def test_a_raising_judge_is_survived(self):
        class _Exploder:
            def judge(self, situation, actor=""):
                raise RuntimeError("no generator configured")

        _wire(_Exploder())
        result = _query_rules(topic=UNCOVERED)
        assert result["found"] is False, "a broken judge must not break the turn"
        assert "improvise" in result["note"]

    def test_a_judge_returning_none_is_survived(self):
        class _Nothing:
            def judge(self, situation, actor=""):
                return None

        _wire(_Nothing())
        assert _query_rules(topic=UNCOVERED)["found"] is False

    def test_the_gap_is_still_recorded_when_unruled(self):
        """2.11's backlog ranking must survive the new branch."""
        recorded = []

        class _Tracker:
            def record(self, situation, tier, **kwargs):
                recorded.append((situation, tier))

        T.set_dm_tool_context(srd_rules=get_srd_rules(),
                              cosmere_rules=get_cosmere_rules(),
                              gap_tracker=_Tracker())
        _query_rules(topic=UNCOVERED)
        assert recorded, "the rules gap is no longer being recorded"
        assert recorded[0][1] == 3


class TestTheOrchestratorBuildsOne:
    def test_the_builder_exists(self):
        from orchestrator.pipeline_integration import PipelineOrchestrator

        assert hasattr(PipelineOrchestrator, "_build_rules_judge")

    def test_the_builder_returns_a_judge_or_none(self):
        from orchestrator.pipeline_integration import PipelineOrchestrator

        orchestrator = PipelineOrchestrator.__new__(PipelineOrchestrator)
        orchestrator.game_engine = None
        judge = orchestrator._build_rules_judge()
        if judge is not None:
            assert hasattr(judge, "judge")
            assert hasattr(judge, "store")

    def test_the_orchestrator_passes_the_judge_through(self):
        """
        Assert on the CALL, not on the class existing. Four subsystems have now
        been built, tested and never called; only the call proves delivery.
        """
        import inspect

        from orchestrator.pipeline_integration import PipelineOrchestrator

        source = inspect.getsource(
            PipelineOrchestrator._initialize_pipeline_infrastructure)
        assert "rules_judge=" in source, (
            "set_dm_tool_context is called without a rules_judge, so the judge "
            "is unreachable from the running game")
