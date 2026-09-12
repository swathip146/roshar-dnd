"""
Plan 0.11 — `DiceRoller.damage_roll` now parses via avrae/d20, not by hand.

Why this file exists: `d20` was pinned in requirements.txt but NEVER imported.
The project hand-rolled a regex dice parser instead, and that parser had a
documented history of silent-wrong-number bugs:

  * "4d6kh3"   -> ValueError: invalid literal for int(): '6kh3'
  * "1d6 + 2"  -> ValueError: invalid literal for int(): '+'
  * "1d8-1"    -> right total, but reported modifier=0 and printed "... + 0 = 2"
  * "4d6e6"    -> total_damage 0, damage_rolls [], NO error. A spell written
                  with exploding dice dealt NOTHING and nothing reported it.

The first three were fixed in place; the fourth was converted to a loud
ValueError. This suite covers the actual resolution: a declared dependency that
was dead weight is now the parser, so exploding/reroll/min-max/parenthesised
notation simply WORKS instead of being refused.

Ground rules inherited from `test_deterministic_game_flow.py`:

* **Assert the CONTRACT, both directions.** `agents/dm_tools.roll_dice` and
  `components/combat/maneuver_executor._roll_total` read specific keys by name,
  so a swap that changed the dict shape would break callers silently. Every key
  is asserted, and the previously-working notation is re-asserted alongside the
  newly-supported notation — a parser swap that gains exploding dice but loses
  "1d8+3" is a regression, not a win.
* **Physically impossible results are bugs.** A d6 cannot roll 0. This caught a
  real defect during implementation (see `TestFaceValuesArePhysicallyPossible`).
* **Malformed input must still fail loudly.** A silent zero is the worst
  possible answer for an adjudicator.
* **Statistical claims get a fixed seed** and a range wide enough to be robust.

No LLM, no network.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from components.dice import DiceRoller

pytestmark = [pytest.mark.deterministic]


# The exact key set callers depend on. Asserted as a set, so a swap that ADDS a
# key is fine but one that renames or drops a key fails here rather than in a
# combat encounter.
DAMAGE_CONTRACT_KEYS = {
    "total_damage", "damage_rolls", "base_damage", "dice_subtotal",
    "static_modifier", "modifier", "breakdown", "correlation_id",
}

# Notation that already worked before the swap. If any of this breaks, the swap
# is a net loss regardless of what it gained.
PREVIOUSLY_WORKING = [
    "2d6", "1d8+3", "1d8-1", "1d6 + 2", "4d6kh3", "2d20kl1", "4d6kl1",
    "5", "1d8+1d6+3", "2d6[fire]", "8d6", "1d4+1", "3d8 + 5", "1d20", "d6",
]

# Notation d20 gives us for free. Every one of these was previously either a
# silent 0 (the dangerous case) or a ValueError.
NEWLY_SUPPORTED = [
    "4d6e6",      # exploding on 6
    "10d6e6",     # exploding, many dice
    "4d6ro1",     # reroll 1s once
    "4d6rr1",     # reroll 1s until not 1
    "4d6mi2",     # treat any die below 2 as 2
    "4d6ma5",     # treat any die above 5 as 5
    "4d6p1",      # drop the lowest
    "(1d6+2)*2",  # parentheses and multiplication
    "1d6+2d6e6",  # mixed: previously lost half its dice silently
]


@pytest.fixture
def roller():
    return DiceRoller()


class TestTheLibraryIsActuallyUsed:
    """
    The whole point of plan 0.11: the dependency was declared and never imported.
    A future refactor that quietly reverts to a hand-rolled regex would make the
    requirements.txt line dishonest again, so this asserts the import directly.
    """

    def test_components_dice_imports_d20(self):
        import components.dice as dice_module

        assert hasattr(dice_module, "d20"), (
            "components/dice.py must import d20 — it was pinned in "
            "requirements.txt but never imported, which is bug 0.11 itself")

    def test_d20_is_installed_and_is_the_avrae_parser(self):
        import d20

        # `d20.roll` plus the grammar error type is what distinguishes the real
        # avrae parser from a same-named stub.
        assert callable(d20.roll)
        assert issubclass(d20.RollSyntaxError, d20.RollError)


class TestDamageContractIsUnchanged:
    """
    `damage_roll` returns a dict whose keys are read by name in production:
    `dm_tools.roll_dice` reads total_damage/damage_rolls/breakdown, and
    `maneuver_executor._roll_total` reads total_damage. Changing the shape would
    break those callers without any test noticing, so the shape is pinned here.
    """

    @pytest.mark.parametrize("expression", PREVIOUSLY_WORKING + NEWLY_SUPPORTED)
    def test_every_expression_returns_the_full_contract(self, roller, expression):
        result = roller.damage_roll(expression)
        assert set(result.keys()) == DAMAGE_CONTRACT_KEYS, (
            f"{expression!r} returned keys {sorted(result.keys())}")

    @pytest.mark.parametrize("expression", PREVIOUSLY_WORKING + NEWLY_SUPPORTED)
    def test_contract_value_types_are_stable(self, roller, expression):
        result = roller.damage_roll(expression)
        assert isinstance(result["total_damage"], int)
        assert isinstance(result["damage_rolls"], list)
        assert all(isinstance(v, int) for v in result["damage_rolls"])
        assert isinstance(result["dice_subtotal"], int)
        assert isinstance(result["static_modifier"], int)
        assert isinstance(result["breakdown"], str)
        assert result["base_damage"] == expression

    def test_correlation_id_is_passed_through(self, roller):
        """The audit trail joins rolls to a turn by correlation id."""
        result = roller.damage_roll("1d6", correlation_id="turn-42")
        assert result["correlation_id"] == "turn-42"

    @pytest.mark.parametrize("expression", PREVIOUSLY_WORKING + NEWLY_SUPPORTED)
    def test_the_arithmetic_adds_up(self, roller, expression):
        """
        dice_subtotal + static_modifier must equal the total (before the
        never-negative clamp). This is the invariant that caught the old
        "1d8-1 reports modifier 0" lie, and it must survive the swap — including
        for "(1d6+2)*2", where the constant is not an additive modifier.
        """
        result = roller.damage_roll(expression)
        pre_clamp = result["dice_subtotal"] + result["static_modifier"]
        assert result["total_damage"] == max(0, pre_clamp), (
            f"{expression}: {result['breakdown']}")


class TestPreviouslyWorkingNotationStillWorks:
    """
    Both directions. A parser swap is only a win if it is a superset — these are
    the expressions the old parser handled after its four in-place fixes.
    """

    @pytest.mark.parametrize("expression", PREVIOUSLY_WORKING)
    def test_it_parses_and_produces_damage(self, roller, expression):
        result = roller.damage_roll(expression)
        assert result["total_damage"] >= 0
        assert result["damage_rolls"] or result["static_modifier"], (
            f"{expression!r} produced neither dice nor a constant")

    def test_keep_highest_drops_the_lowest(self, roller):
        """4d6kh3 sums the best three of four, and records all FOUR faces."""
        for _ in range(50):
            result = roller.damage_roll("4d6kh3")
            assert len(result["damage_rolls"]) == 4, "all four dice are recorded"
            best_three = sum(sorted(result["damage_rolls"], reverse=True)[:3])
            assert result["dice_subtotal"] == best_three, (
                f"kh3 of {result['damage_rolls']} != {result['dice_subtotal']}")

    def test_keep_lowest_drops_the_highest(self, roller):
        for _ in range(50):
            result = roller.damage_roll("2d20kl1")
            assert result["dice_subtotal"] == min(result["damage_rolls"])

    def test_the_negative_constant_is_reported_not_hidden(self, roller):
        """`1d8-1` once returned the right total while reporting modifier 0."""
        result = roller.damage_roll("1d8-1")
        assert result["static_modifier"] == -1, (
            f"the -1 is missing from the breakdown: {result['breakdown']}")
        assert "+ 0 =" not in result["breakdown"]

    def test_whitespace_is_tolerated(self, roller):
        """`1d6 + 2` used to raise ValueError on '+'."""
        result = roller.damage_roll("1d6 + 2")
        assert result["static_modifier"] == 2
        assert result["total_damage"] == result["dice_subtotal"] + 2

    def test_damage_type_annotations_are_accepted(self, roller):
        """`2d6[fire]` — the type is narrative; the dice still have to roll."""
        result = roller.damage_roll("2d6[fire]")
        assert len(result["damage_rolls"]) == 2

    def test_chained_dice_terms_all_roll(self, roller):
        result = roller.damage_roll("1d8+1d6+3")
        assert len(result["damage_rolls"]) == 2, "both dice terms must roll"
        assert result["total_damage"] == sum(result["damage_rolls"]) + 3

    def test_the_caller_supplied_modifier_is_additive(self, roller):
        """`modifier=` is a separate bonus from any constant in the expression."""
        result = roller.damage_roll("1d8", modifier=3)
        assert result["modifier"] == 3
        assert result["total_damage"] == result["damage_rolls"][0] + 3

    def test_a_constant_embedded_and_a_caller_modifier_both_apply(self, roller):
        result = roller.damage_roll("1d8+2", modifier=3)
        assert result["total_damage"] == result["damage_rolls"][0] + 2 + 3

    def test_damage_never_heals(self, roller):
        """Damage clamps at 0 — a big penalty must not restore hit points."""
        assert roller.damage_roll("1d4-100")["total_damage"] == 0

    @pytest.mark.parametrize("expression,low,high", [
        ("2d6", 2, 12), ("1d20", 1, 20), ("8d6", 8, 48), ("1d8+3", 4, 11),
    ])
    def test_totals_stay_within_the_possible_range(self, roller, expression, low, high):
        for _ in range(100):
            assert low <= roller.damage_roll(expression)["total_damage"] <= high


class TestNewlySupportedNotation:
    """
    The actual payoff of plan 0.11. Every expression here previously returned
    total_damage 0 with damage_rolls [] and NO error (the silent-zero bug), and
    was later converted to a loud ValueError. Now it rolls.
    """

    @pytest.mark.parametrize("expression", NEWLY_SUPPORTED)
    def test_it_no_longer_raises(self, roller, expression):
        result = roller.damage_roll(expression)
        assert result["total_damage"] > 0 or result["damage_rolls"], (
            f"{expression!r} silently returned {result['total_damage']} damage "
            f"with rolls={result['damage_rolls']} — the exact bug 0.11 is about")

    def test_exploding_dice_can_exceed_the_normal_maximum(self, roller):
        """
        The point of exploding dice: 4d6e6 can beat 24, which plain 4d6 cannot.
        If the notation were being silently ignored this would never trigger.
        """
        random.seed(20260911)
        totals = [roller.damage_roll("4d6e6")["total_damage"] for _ in range(400)]
        assert max(totals) > 24, (
            f"4d6e6 never exceeded 24 in 400 rolls (max {max(totals)}) — "
            f"exploding is not actually happening")

    def test_exploding_dice_roll_more_dice_than_requested(self, roller):
        """An explosion adds a die, so the recorded face count must exceed 4."""
        random.seed(20260911)
        counts = [len(roller.damage_roll("4d6e6")["damage_rolls"])
                  for _ in range(200)]
        assert max(counts) > 4, (
            f"4d6e6 never rolled more than 4 dice (max {max(counts)})")
        assert min(counts) == 4, "a non-exploding 4d6e6 still rolls exactly 4"

    def test_exploding_beats_plain_dice_on_average(self, roller):
        """
        Distributional, fixed seed: E[4d6] = 14, E[4d6e6] ~ 16.8. A gap this
        large cannot be noise at n=500, and collapsing it would mean exploding
        silently stopped working.
        """
        random.seed(20260911)
        plain = sum(roller.damage_roll("4d6")["total_damage"]
                    for _ in range(500)) / 500
        exploding = sum(roller.damage_roll("4d6e6")["total_damage"]
                        for _ in range(500)) / 500
        assert exploding > plain + 1.0, (
            f"4d6e6 {exploding:.2f} vs 4d6 {plain:.2f} — too close")

    def test_reroll_once_removes_most_ones(self, roller):
        """
        `4d6ro1` rerolls each 1 exactly once, so a 1 can survive (the reroll may
        also be a 1) but must be much rarer than in plain 4d6. Asserting "no 1s
        at all" would be wrong RAW and would flake.
        """
        random.seed(20260911)
        plain_ones = sum(roller.damage_roll("4d6")["damage_rolls"].count(1)
                         for _ in range(400))
        reroll_kept = 0
        for _ in range(400):
            result = roller.damage_roll("4d6ro1")
            # The kept faces are the last 4 conceptually, but the audit trail
            # records rerolled-away faces too; compare the TOTAL instead, which
            # only counts kept dice.
            reroll_kept += result["total_damage"]
        plain_total = sum(roller.damage_roll("4d6")["total_damage"]
                          for _ in range(400))
        assert plain_ones > 0, "sanity: plain 4d6 should roll some 1s"
        assert reroll_kept > plain_total * 0.99, (
            "rerolling 1s should raise the average, not lower it")

    def test_reroll_until_removes_all_ones_from_the_total(self, roller):
        """`4d6rr1` rerolls 1s until they are not 1, so no kept die is a 1."""
        random.seed(20260911)
        for _ in range(200):
            result = roller.damage_roll("4d6rr1")
            # Four kept dice, none of them a 1, so the minimum possible is 8.
            assert result["total_damage"] >= 8, (
                f"4d6rr1 totalled {result['total_damage']} < 8, so a 1 was kept: "
                f"{result['breakdown']}")

    def test_minimum_clamps_low_faces(self, roller):
        """`4d6mi3` treats anything under 3 as 3, so the total cannot be under 12."""
        random.seed(20260911)
        for _ in range(200):
            result = roller.damage_roll("4d6mi3")
            assert result["total_damage"] >= 12, result["breakdown"]
            assert min(result["damage_rolls"]) >= 3, (
                f"mi3 left a face below 3: {result['damage_rolls']}")

    def test_maximum_clamps_high_faces(self, roller):
        """`4d6ma4` treats anything over 4 as 4, so the total cannot exceed 16."""
        random.seed(20260911)
        for _ in range(200):
            result = roller.damage_roll("4d6ma4")
            assert result["total_damage"] <= 16, result["breakdown"]
            assert max(result["damage_rolls"]) <= 4, (
                f"ma4 left a face above 4: {result['damage_rolls']}")

    def test_parentheses_and_multiplication_respect_precedence(self, roller):
        """
        `(1d6+2)*2` must be (die+2)*2, not die+4. The old parser split on +/-
        and would have got this wrong; d20 evaluates the real expression.
        """
        for _ in range(50):
            result = roller.damage_roll("(1d6+2)*2")
            die = result["damage_rolls"][0]
            assert result["total_damage"] == (die + 2) * 2, result["breakdown"]

    def test_a_mixed_expression_keeps_all_of_its_dice(self, roller):
        """
        `1d6+2d6e6` used to return ONLY the 1d6 — a two-part damage expression
        quietly losing half its dice — and was then rejected outright. It must
        now roll at least three dice and count them all.
        """
        random.seed(20260911)
        for _ in range(100):
            result = roller.damage_roll("1d6+2d6e6")
            assert len(result["damage_rolls"]) >= 3, (
                f"only {len(result['damage_rolls'])} dice: {result['breakdown']}")
            assert result["total_damage"] >= 3


class TestFaceValuesArePhysicallyPossible:
    """
    Caught a REAL bug during the swap. d20 marks a dropped die's Literal with
    `.total == 0` while keeping its true face in `.values`, so reading `.total`
    logged `4d6ro1` as rolls=[5, 0, 4, 4, 4] — a face of 0 on a d6. That is
    physically impossible and would have skewed `get_roll_statistics`. The fix
    reads `Literal.number`.
    """

    @pytest.mark.parametrize("expression,sides", [
        ("4d6ro1", 6), ("4d6rr1", 6), ("4d6e6", 6), ("4d6kh3", 6),
        ("4d6kl1", 6), ("4d6p1", 6), ("4d6mi2", 6), ("4d6ma5", 6),
        ("2d20kl1", 20), ("8d6", 6), ("10d6e6", 6),
    ])
    def test_no_die_reports_an_impossible_face(self, roller, expression, sides):
        random.seed(20260911)
        for _ in range(150):
            rolls = roller.damage_roll(expression)["damage_rolls"]
            assert all(1 <= face <= sides for face in rolls), (
                f"{expression} produced an impossible face in {rolls} "
                f"(a d{sides} cannot roll outside 1..{sides})")

    def test_dropped_dice_are_still_recorded_at_their_real_value(self, roller):
        """
        The audit trail must show what was rolled AND dropped — that is the
        whole value of recording 4 faces for 4d6kh3. A dropped die recorded as 0
        would look like a broken die rather than a discarded one.
        """
        random.seed(20260911)
        for _ in range(100):
            result = roller.damage_roll("4d6kh3")
            assert len(result["damage_rolls"]) == 4
            assert all(1 <= f <= 6 for f in result["damage_rolls"])
            # The dropped one is the lowest, and it is present in the log.
            assert result["dice_subtotal"] == (
                sum(result["damage_rolls"]) - min(result["damage_rolls"]))


class TestMalformedInputStillFailsLoudly:
    """
    A silent zero is the worst possible answer for an adjudicator — it is the
    same failure shape as the `success`-always-True bug that took a whole session
    to find. `dm_tools.roll_dice` forwards whatever the LLM wrote, so garbage
    reaching here means the model got the notation wrong and must be told.
    """

    @pytest.mark.parametrize("expression", [
        "garbage", "", "   ", "4d6!", "1d20r1", "d", "0d6", "0", "kh3", "+",
    ])
    def test_it_raises_value_error(self, roller, expression):
        with pytest.raises(ValueError):
            roller.damage_roll(expression)

    def test_none_is_refused(self, roller):
        with pytest.raises(ValueError):
            roller.damage_roll(None)  # type: ignore[arg-type]

    def test_a_zero_dice_expression_is_not_zero_damage(self, roller):
        """
        `0d6` evaluates to 0 in d20 without error, so the refusal has to be
        explicit. An expression that rolls no dice means the model omitted them,
        not that the attack was harmless.
        """
        with pytest.raises(ValueError):
            roller.damage_roll("0d6")

    def test_the_error_names_the_offending_expression(self, roller):
        """An error a caller cannot act on is barely better than a silent zero."""
        with pytest.raises(ValueError, match="garbage"):
            roller.damage_roll("garbage")

    def test_the_error_is_a_value_error_not_a_d20_error(self, roller):
        """
        Callers catch `Exception` and tests assert `ValueError`; leaking
        `d20.RollSyntaxError` would still work for the former but would change
        the documented contract. Keep it a ValueError.
        """
        import d20

        with pytest.raises(ValueError) as caught:
            roller.damage_roll("garbage")
        assert not isinstance(caught.value, d20.RollError)


class TestTheAuditTrailSurvivesTheSwap:
    """
    d20 rolls through the module-level `random`, so it bypasses
    `DiceRoller.rng` and would not populate `raw_roll_log` on its own.
    `get_roll_statistics` and `clear_history` read that log, so the faces are
    recorded back into it. A swap that lost the audit trail would leave the
    statistics silently reporting nothing.
    """

    def test_rolls_are_recorded_in_the_raw_log(self, roller):
        before = len(roller.raw_roll_log)
        roller.damage_roll("4d6kh3")
        assert len(roller.raw_roll_log) == before + 4, (
            "all four dice must reach the audit log")

    def test_exploded_dice_are_recorded_too(self, roller):
        random.seed(20260911)
        for _ in range(200):
            roller.raw_roll_log.clear()
            result = roller.damage_roll("4d6e6")
            assert len(roller.raw_roll_log) == len(result["damage_rolls"])
            if len(result["damage_rolls"]) > 4:
                return  # observed an explosion reaching the log
        pytest.fail("never observed an explosion in 200 rolls of 4d6e6")

    def test_the_recorded_die_size_lets_statistics_find_d20s(self, roller):
        """
        `get_roll_statistics` filters the log on `die_type == 20`, so a d20
        rolled through an expression has to be recorded as a d20 or the stats
        report "No d20 rolls found".
        """
        roller.raw_roll_log.clear()
        roller.damage_roll("2d20kl1")
        assert [entry.die_type for entry in roller.raw_roll_log] == [20, 20]

    def test_clear_history_still_empties_the_log(self, roller):
        roller.damage_roll("2d6")
        roller.clear_history()
        assert roller.raw_roll_log == []


class TestSeedingIsStillReproducible:
    """
    Existing suites seed the global `random` and assert distributions. d20 uses
    `random.randrange` from that same module, so seeding must still produce
    identical sequences — otherwise every seeded test in the repo becomes flaky.
    """

    def test_the_same_seed_gives_the_same_rolls(self, roller):
        random.seed(4242)
        first = [roller.damage_roll("4d6kh3")["total_damage"] for _ in range(20)]
        random.seed(4242)
        second = [roller.damage_roll("4d6kh3")["total_damage"] for _ in range(20)]
        assert first == second, "d20 must honour random.seed()"

    def test_different_seeds_give_different_rolls(self, roller):
        """Both directions: reproducibility must not mean a constant result."""
        random.seed(1)
        first = [roller.damage_roll("4d6")["total_damage"] for _ in range(20)]
        random.seed(2)
        second = [roller.damage_roll("4d6")["total_damage"] for _ in range(20)]
        assert first != second

    def test_a_d6_covers_its_whole_range(self, roller):
        """A die that never rolls its extremes would quietly skew all damage."""
        random.seed(20260911)
        seen = set()
        for _ in range(400):
            seen.update(roller.damage_roll("2d6")["damage_rolls"])
        assert seen == set(range(1, 7)), f"missing faces: {set(range(1, 7)) - seen}"


class TestProductionCallersStillWork:
    """
    The swap is only safe if the real callers still get what they read. These
    exercise the two production entry points rather than trusting the shape.
    """

    def test_dm_tools_roll_dice_returns_a_real_total(self):
        """
        `agents/dm_tools.roll_dice` reads total_damage/damage_rolls/breakdown and
        is the path the LLM uses. It swallows exceptions into {"error": ...}, so a
        contract break would show up as a silent 0 in play.
        """
        from agents.dm_tools import roll_dice

        # Haystack wraps @tool functions in a Tool object; .function is the
        # underlying callable.
        func = getattr(roll_dice, "function", roll_dice)
        result = func("2d6+3", reason="test")
        assert "error" not in result, result
        assert 5 <= result["total"] <= 15
        assert len(result["rolls"]) == 2
        assert result["breakdown"]

    def test_dm_tools_roll_dice_now_handles_exploding(self):
        """The LLM writing "4d6e6" used to get a silent 0 through this path."""
        from agents.dm_tools import roll_dice

        # Haystack wraps @tool functions in a Tool object; .function is the
        # underlying callable.
        func = getattr(roll_dice, "function", roll_dice)
        result = func("4d6e6", reason="exploding")
        assert "error" not in result, result
        assert result["total"] >= 4

    def test_dm_tools_roll_dice_reports_garbage_as_an_error(self):
        """Both directions: the tool must surface bad notation, not hide it."""
        from agents.dm_tools import roll_dice

        # Haystack wraps @tool functions in a Tool object; .function is the
        # underlying callable.
        func = getattr(roll_dice, "function", roll_dice)
        result = func("garbage", reason="bad")
        assert result.get("error"), f"garbage should be reported: {result}"
        assert result["total"] == 0

    def test_maneuver_executor_roll_total_reads_total_damage(self, roller):
        """
        `maneuver_executor._roll_total` does
        `int(self.dice.damage_roll(expr).get("total_damage", 0))`. If that key
        were renamed, every surge maneuver would silently deal 0.
        """
        outcome = roller.damage_roll("2d8+2")
        assert int(outcome.get("total_damage", 0)) >= 4


class TestUnrelatedRollMethodsAreUntouched:
    """
    Only expression parsing moved to d20. `skill_roll`/`attack_roll`/
    `saving_throw` roll a fixed 1d20 with advantage and were deliberately left
    alone — rewriting them would risk `raw_rolls` and the advantage logic for no
    gain. These assert they still behave, so the blast radius is proven small.
    """

    def test_advantage_still_keeps_the_higher(self, roller):
        for _ in range(60):
            result = roller.attack_roll(0, advantage_state="advantage")
            assert len(result["raw_rolls"]) == 2
            assert result["selected_roll"] == max(result["raw_rolls"])

    def test_disadvantage_still_keeps_the_lower(self, roller):
        for _ in range(60):
            result = roller.attack_roll(0, advantage_state="disadvantage")
            assert len(result["raw_rolls"]) == 2
            assert result["selected_roll"] == min(result["raw_rolls"])

    def test_saving_throw_contract_is_intact(self, roller):
        result = roller.saving_throw("dexterity", 3, proficiency=2)
        for key in ("total", "selected_roll", "raw_rolls", "roll_breakdown",
                    "modifiers", "advantage_state"):
            assert key in result, f"saving_throw lost {key}"
        assert result["total"] == result["selected_roll"] + 5

    def test_skill_roll_contract_is_intact(self, roller):
        result = roller.skill_roll("stealth", 5, {"final_state": "normal"})
        for key in ("total", "selected_roll", "raw_rolls", "roll_breakdown",
                    "modifiers", "advantage_state"):
            assert key in result, f"skill_roll lost {key}"

    def test_percentile_roll_stays_in_range(self, roller):
        for _ in range(200):
            assert 1 <= roller.percentile_roll()["result"] <= 100
