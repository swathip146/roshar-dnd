"""
A DM tool must never crash on an argument the model invented.

Found by a live Suite B run:

    TypeError: roll_skill_check() got an unexpected keyword argument 'reason'

on the single most-used tool in the game — which cost the player the whole turn. The
model generalised reasonably: `roll_dice(expression, reason=...)` and
`award_experience(amount, reason=...)` both take a `reason`, so it assumed
`roll_skill_check` did too. It now does; and because 16 other tools carried the same
hazard for any similarly plausible argument, `_tolerate_unknown_kwargs` drops
undeclared keywords (logging each) rather than raising.

Needs no LLM: the defect is in the tool signatures, not in the model.
"""

from __future__ import annotations

import inspect

import pytest

from agents.dm_tools import DM_TOOLS, set_dm_tool_context
from tests.integration.harness.game_builder import build_engine, character_template

pytestmark = pytest.mark.integration


@pytest.fixture
def tools_with_context():
    """Live components wired, so a tool does real work rather than erroring early."""
    engine = build_engine(characters=[character_template()])
    set_dm_tool_context(game_engine=engine,
                        character_manager=engine.character_manager)
    return {getattr(t, "name"): t for t in DM_TOOLS if getattr(t, "name", None)}


class TestToolsSurviveInventedArguments:

    def test_the_exact_crash_suite_b_found(self, tools_with_context):
        """`roll_skill_check(..., reason=...)` used to raise TypeError."""
        result = tools_with_context["roll_skill_check"].invoke(
            skill="athletics", dc=12, actor="aggi", reason="climbing a rock face")

        assert isinstance(result, dict), f"returned {type(result).__name__}"
        assert "error" not in result or not result["error"], result

    def test_roll_skill_check_now_declares_reason(self):
        """It is declared, not merely tolerated — the model asks for it repeatedly."""
        function = next(t.function for t in DM_TOOLS
                        if getattr(t, "name", None) == "roll_skill_check")

        assert "reason" in inspect.signature(function).parameters, (
            "roll_skill_check should declare `reason` for parity with roll_dice and "
            "award_experience, which both take one")

    @pytest.mark.parametrize("tool_name,kwargs", [
        ("get_world_state", {"reason": "curiosity"}),
        ("get_party_state", {"reason": "checking on everyone"}),
        ("get_character_state", {"actor": "aggi", "detail": "full"}),
        ("query_rules", {"topic": "grappling", "reason": "player asked"}),
        ("roll_dice", {"expression": "1d20", "purpose": "wind"}),
    ])
    def test_an_undeclared_argument_is_dropped_not_raised(
            self, tools_with_context, tool_name, kwargs):
        result = tools_with_context[tool_name].invoke(**kwargs)

        assert isinstance(result, dict), (
            f"{tool_name} did not survive {sorted(kwargs)}: {result!r}")

    def test_every_tool_tolerates_a_wholly_invented_argument(self,
                                                             tools_with_context):
        """One sweep, so a newly added tool cannot reintroduce the hazard."""
        crashed = []
        for name, tool in sorted(tools_with_context.items()):
            try:
                tool.invoke(**{"totally_made_up_argument": "x"})
            except TypeError as exc:
                crashed.append(f"{name}: {exc}")
            except Exception:  # noqa: BLE001
                # Any OTHER error is fine here: a tool refusing because it lacks its
                # real required arguments is correct behaviour. Only TypeError from an
                # unexpected KEYWORD is the bug under test.
                pass

        assert not crashed, (
            "these tools still raise TypeError on an invented argument, which costs "
            "the player the turn:\n  - " + "\n  - ".join(crashed))

    def test_a_declared_argument_still_validates(self, tools_with_context):
        """The hardening must not swallow a genuine caller error in OUR code.

        Omitting a REQUIRED argument must still fail loudly — otherwise the fix would
        trade a visible crash for a silent no-op.
        """
        with pytest.raises(TypeError):
            tools_with_context["roll_skill_check"].function()   # no skill, no dc

    def test_positional_calls_still_work(self, tools_with_context):
        """Several callers invoke these POSITIONALLY, e.g. `roll_dice("2d6+3")`.

        My first version of the hardening wrapper was keyword-only, so a positional
        argument bound to the wrapper's own `_function` default instead of reaching the
        tool. Three dice tests caught it immediately. This pins the contract.
        """
        result = tools_with_context["roll_dice"].function("2d6+3")

        assert isinstance(result, dict), f"positional call returned {result!r}"
        assert result.get("total") or result.get("result") or not result.get("error"), (
            f"a positional roll_dice produced no usable total: {result}")
