"""
Regression tests for the authored Surgebinding content (Windrunner Maneuvers and
Radiant order features) added to data/rules/stormlight/surgebinding.json.

Two things are guarded here:

  * THE DATA IS COMPLETE AND GROUNDED. Every Maneuver and feature carries a
    verbatim `quote` and a `source.line` into the Radiant's Handbook, and
    `verify_citations()` confirms the quote still appears at that line. An entry
    that cannot be checked against the source must be `reviewed:false` — but per
    plan D5 (and CosmereRules.unreviewed()) the maneuvers/features buckets must
    hold no unreviewed entries, so everything authored here is reviewed AND
    verified.

  * THE AUTHORED MANEUVERS EXECUTE. A reviewed maneuver is OFFERED to a player
    (CosmereRules.maneuvers() -> ManeuverExecutor.available()) and can be run, so
    each newly-authored maneuver must execute through the real interpreter
    without raising and produce at least one observable event. Effects the
    interpreter has no native node for (forced movement, temp HP, speed changes)
    are recorded as ieffect2 inline effects — the same convention as the original
    Evasive Movement / Distracting Attack maneuvers — never as invented numbers.

Progress is logged so a run reports what it checked.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "external" / "dnd_engine"))

from config.logging_config import get_logger
from components.cosmere_rules import CosmereRules

logger = get_logger(__name__)

# The 17 Windrunner Maneuvers authored on top of the original 9.
NEW_MANEUVERS = (
    "Feinting Attack", "Flourish", "Invested Focus", "Invested Perception",
    "Lash Ally", "Lash Enemy", "Lunging Strike", "Parry", "Precision Attack",
    "Quiet Lashing", "Rally", "Rampage", "Rescuing Wind", "Saving Lash",
    "Slowing Lash", "Thrown Lashing", "Tripping Lash",
)

# The 10 order features authored on top of the original 2 (one+ per non-Windrunner order).
NEW_FEATURES = (
    ("skyward", "Skybreaker"),
    ("stormlight_healing_skybreaker", "Skybreaker"),
    ("infused_skin", "Dustbringer"),
    ("infused_hands", "Dustbringer"),
    ("edgedance", "Edgedancer"),
    ("truth_dice", "Truthwatcher"),
    ("illusory_elusion", "Lightweaver"),
    ("stormlight_healing_elsecaller", "Elsecaller"),
    ("willshape", "Willshaper"),
    ("ward", "Stoneward"),
)


# ---------------------------------------------------------------------------
# The authored data is complete and grounded (no combat engine needed)
# ---------------------------------------------------------------------------

class TestAuthoredDataIsGrounded:

    @pytest.fixture
    def rules(self):
        return CosmereRules()

    def test_all_new_maneuvers_are_present_and_reviewed(self, rules):
        names = {m["name"] for m in rules.maneuvers()}  # reviewed_only=True by default
        missing = [n for n in NEW_MANEUVERS if n not in names]
        logger.info("🗡️  checking %d authored Maneuvers are present and reviewed",
                    len(NEW_MANEUVERS))
        assert not missing, f"authored Maneuvers missing or unreviewed: {missing}"
        assert len(rules.maneuvers()) >= 26, "expected at least 26 reviewed Maneuvers"

    def test_all_new_features_are_present_and_reviewed(self, rules):
        by_id = {f["id"]: f for f in rules.features()}  # reviewed_only=True
        logger.info("🛡️  checking %d authored order features across the orders",
                    len(NEW_FEATURES))
        for fid, order in NEW_FEATURES:
            assert fid in by_id, f"feature {fid!r} missing or unreviewed"
            assert order in by_id[fid]["orders"], f"{fid} not attributed to {order}"
        assert len(rules.features()) >= 12, "expected at least 12 reviewed features"

    def test_every_playable_order_has_at_least_one_feature(self, rules):
        playable = [name for name, o in rules._data.get("orders", {}).items()
                    if o.get("playable", True)]
        for order in playable:
            feats = rules.features(order=order)
            logger.info("   order %-12s -> %d feature(s)", order, len(feats))
            assert feats, f"{order} has no reviewed feature"

    def test_no_maneuver_or_feature_is_unreviewed(self, rules):
        """Plan D5: the maneuvers/features buckets must not carry an unreviewed entry."""
        stragglers = [u.get("name") for u in rules.unreviewed()]
        logger.info("🔍 unreviewed maneuvers/features/orders: %s", stragglers or "none")
        assert stragglers == [], f"unreviewed entries would silently not adjudicate: {stragglers}"

    def test_every_reviewed_quote_verifies_against_the_handbook(self, rules):
        result = rules.verify_citations()
        logger.info("📖 citations checked=%d verified=%d mismatched=%d",
                    result["checked"], result["verified"], len(result["mismatched"]))
        assert result["checked"] >= 45, "far fewer citations than expected were checked"
        assert not result["mismatched"], (
            f"{len(result['mismatched'])} citation(s) drifted: {result['mismatched'][:5]}")

    def test_authored_maneuvers_cost_a_lashing_die(self, rules):
        for name in NEW_MANEUVERS:
            m = rules.get_maneuver(name)
            assert m is not None, f"{name} not found"
            assert (m.get("cost") or {}).get("lashing_dice") == 1, (
                f"{name} must expend one Lashing die")

    def test_no_authored_tree_invents_a_placeholder(self, rules):
        """Only {lashing_die} is a supported interpolation; anything else is a data bug."""
        import re
        allowed = {"{lashing_die}"}

        def walk(node):
            if isinstance(node, str):
                for token in re.findall(r"\{[a-z_]+\}", node):
                    assert token in allowed, f"unsupported placeholder {token!r}"
            elif isinstance(node, dict):
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        for name in NEW_MANEUVERS:
            walk(rules.get_maneuver(name)["automation"])


# ---------------------------------------------------------------------------
# The authored Maneuvers actually execute (real interpreter, no mocks)
# ---------------------------------------------------------------------------

pytestmark_combat = pytest.mark.combat


@pytest.mark.combat
class TestAuthoredManeuversExecute:

    @pytest.fixture
    def field(self):
        from components.character_manager import CharacterManager
        from components.combat.lashing_dice import LashingDicePool
        from components.combat.maneuver_executor import KNOWN_NODES, ManeuverExecutor
        from components.combat.tactical_grid import TacticalGrid
        from components.dnd_engine_wrapper import DnDEngineWrapper

        TacticalGrid._clear_tiles()

        def sheet(cid, order=None, feeble=False):
            score = 6 if feeble else 16
            s = {
                "character_id": cid, "name": cid, "level": 5,
                "ability_scores": {"strength": score, "dexterity": score,
                                   "constitution": 14, "intelligence": 10,
                                   "wisdom": score, "charisma": 12},
                "hit_points": {"current": 200, "maximum": 200, "temporary": 0},
                "armor_class": 10 if feeble else 16,
                "character_class": "Fighter", "race": "Human",
                "background": "Soldier", "equipment": ["Spear"],
                "proficiency_bonus": 3,
            }
            if order:
                s.update({"radiant_order": order, "surgebinding_level": 3,
                          "stormlight_capacity": 10, "stormlight_current": 10})
            return s

        engine = type("E", (), {"game_state": type("S", (), {"characters": {}})()})()
        manager = CharacterManager()
        manager.add_character(sheet("Kal", order="Windrunner"))
        manager.add_character(sheet("Target", feeble=True))
        manager.add_character(sheet("Ally"))

        wrapper = DnDEngineWrapper(game_engine=engine, character_manager=manager)
        wrapper.set_entity_position("Kal", (0, 0))
        wrapper.set_entity_position("Target", (1, 0))
        wrapper.set_entity_position("Ally", (0, 1))
        wrapper.refresh_senses()

        rules = CosmereRules()
        pool = LashingDicePool(rules)
        pool.register("Kal", "Windrunner", 5)
        state = {"combatant_states": {"Kal": {}, "Target": {}, "Ally": {}}}
        executor = ManeuverExecutor(wrapper, dice_pool=pool, cosmere_rules=rules,
                                    combat_state=state)
        self._known = KNOWN_NODES
        yield executor, pool, rules
        TacticalGrid._clear_tiles()

    def test_every_new_maneuver_uses_only_known_node_types(self, field):
        _, _, rules = field

        def walk(node, name):
            if isinstance(node, dict):
                if "type" in node:
                    assert node["type"] in self._known, (
                        f"{name} uses unsupported node {node['type']!r}")
                for v in node.values():
                    walk(v, name)
            elif isinstance(node, list):
                for v in node:
                    walk(v, name)

        for name in NEW_MANEUVERS:
            walk(rules.get_maneuver(name)["automation"], name)

    @pytest.mark.parametrize("name", NEW_MANEUVERS)
    def test_each_new_maneuver_executes_and_does_something(self, field, name):
        executor, pool, rules = field
        maneuver = rules.get_maneuver(name)
        # Restore dice so the resource never confounds; targets cover ally- and
        # enemy-facing Maneuvers alike (roll-only Maneuvers ignore targets).
        pool.rest("Kal")
        result = executor.execute(maneuver, "Kal", targets=["Target"])
        logger.info("⚡ %-20s -> success=%s events=%d", name, result.success,
                    len(result.events))
        assert result.success is True, f"{name} failed to execute: {result.error}"
        assert result.events, f"{name} executed but produced no observable event"

    def test_a_windrunner_is_offered_the_new_maneuvers(self, field):
        executor, _, _ = field
        offered = {m["name"] for m in executor.available("Kal", "Windrunner", 5)}
        missing = [n for n in NEW_MANEUVERS if n not in offered]
        logger.info("🎯 Windrunner offered %d Maneuvers; new missing: %s",
                    len(offered), missing or "none")
        assert not missing, f"authored Maneuvers not offered in play: {missing}"
