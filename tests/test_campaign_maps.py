"""
Battle maps in the campaign: the authored data and the generator's contract.

Maps are AUTHORED once (by the generator, or by hand) rather than improvised per
encounter, so a location's terrain is identical on every run. That matters because an
encounter's difficulty depends on its terrain, a test cannot assert on a battlefield
that changes every time, and a UI needs stable geometry to render.

These tests cover the DATA — the shipped campaign and the generator's prompt — without
calling the network. Live authoring is verified separately: the model produced a valid
14x8 flooded-market map on its first attempt.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "external" / "dnd_engine"))

pytestmark = [pytest.mark.unit]

from components.combat.battle_map import (COVER, ENEMY_SPAWN, PARTY_SPAWN,
                                          MapError, parse_map)

CAMPAIGN = PROJECT_ROOT / "data" / "current_campaign" / "shards_of_honor.json"


def _locations():
    return json.loads(CAMPAIGN.read_text()).get("locations", [])


class TestTheShippedCampaignHasUsableMaps:
    def test_every_location_has_a_map(self):
        missing = [l["name"] for l in _locations() if not l.get("map")]
        assert not missing, f"locations with no battle map: {missing}"

    @pytest.mark.parametrize("index", range(3))
    def test_each_map_parses_and_validates(self, index):
        """
        `parse_map` rejects a map that would break an encounter — ragged rows, unknown
        symbols, missing spawns, or enemies walled off from the party.
        """
        locations = _locations()
        if index >= len(locations):
            pytest.skip("fewer locations than expected")
        location = locations[index]
        parse_map(location["map"], name=location["name"])

    def test_combatants_do_not_start_adjacent(self):
        """
        The whole point of a grid. One tile is 5 ft and a character moves 6 tiles a
        turn, so spawning in reach of each other removes every tactical choice — which
        is exactly what the old two-row line did.
        """
        for location in _locations():
            battle_map = parse_map(location["map"], name=location["name"])
            nearest = min(
                max(abs(p[0] - e[0]), abs(p[1] - e[1]))
                for p in battle_map.party_spawns
                for e in battle_map.enemy_spawns)
            assert nearest >= 5, (
                f"{location['name']}: spawns only {nearest} tiles apart "
                f"({nearest * 5} ft)")

    def test_each_map_has_real_terrain(self):
        """A bare field plays identically everywhere; terrain is the point."""
        for location in _locations():
            battle_map = parse_map(location["map"], name=location["name"])
            interesting = sum(row.count(c) for row in battle_map.rows
                              for c in ("#", COVER, "~"))
            assert interesting >= 4, (
                f"{location['name']} is effectively a bare field "
                f"({interesting} terrain tiles)")

    def test_each_map_declares_a_legend(self):
        """The legend is what a UI renders and what the DM narrates from."""
        for location in _locations():
            legend = (location["map"] or {}).get("legend") or {}
            assert legend, f"{location['name']} has no legend"

    def test_the_schema_version_records_maps(self):
        version = json.loads(CAMPAIGN.read_text()).get("schema_version", "")
        assert version >= "2.2", (
            f"schema_version is {version!r}; maps are part of the contract now")


class TestTheGeneratorAsksForMaps:
    """
    The generator authors maps ONCE, at campaign creation. If its prompt does not
    demand them, every future campaign falls back to generic templates.
    """

    def _prompt(self) -> str:
        import inspect

        from generators.campaign_generator import CampaignGenerator

        return inspect.getsource(CampaignGenerator.generate_campaign)

    def test_the_schema_includes_a_map_block(self):
        prompt = self._prompt()
        assert '"map"' in prompt
        assert '"rows"' in prompt and '"legend"' in prompt

    def test_every_symbol_is_documented(self):
        """A symbol the model does not know about is a symbol it will not use."""
        prompt = self._prompt()
        for symbol in (".", "#", "H", "~", "P", "E"):
            assert f"  {symbol}  " in prompt or f"'{symbol}'" in prompt, (
                f"symbol {symbol!r} is not explained to the model")

    def test_the_hard_rules_are_stated(self):
        """
        Each rule corresponds to a way `parse_map` rejects a map. Stating them is
        cheaper than a rejected map and a fallback to a generic template.
        """
        prompt = self._prompt().lower()
        assert "exactly the same length" in prompt
        assert "reachable" in prompt
        assert "opposite sides" in prompt

    def test_the_prompt_warns_against_adjacent_spawns(self):
        prompt = self._prompt().lower()
        assert "5 tiles apart" in prompt or "at least 5" in prompt

    def test_the_worked_example_is_itself_valid(self):
        """
        An invalid example teaches the model to produce invalid maps. Extract the rows
        from the prompt and run them through the real validator.
        """
        import re

        prompt = self._prompt()
        # The LAST "rows" block is the worked example; the first is the schema stub,
        # which is deliberately two placeholder rows and not a real map.
        blocks = re.findall(r'"rows": \[(.*?)\]', prompt, re.S)
        assert blocks, "the prompt has no rows example at all"
        rows = re.findall(r'"([.#H~PE]+)"', blocks[-1])
        assert len(rows) >= 4, (
            f"the worked example has only {len(rows)} rows; the model will copy its "
            f"shape, so it must be a real map")
        battle_map = parse_map({"rows": rows}, name="prompt example")
        assert battle_map.party_spawns and battle_map.enemy_spawns


class TestAnUnusableMapIsRejectedNotRepaired:
    """
    A silently "fixed" battlefield is how an encounter becomes unwinnable. Each case
    below is a way a hand-written or generated map goes wrong.
    """

    @pytest.mark.parametrize("rows,why", [
        (["....", "..."], "ragged rows"),
        (["....", "....", "....", "...."], "no spawns"),
        (["PP..", "####", "..EE", "...."], "enemies walled off"),
        (["PX.E", "....", "....", "...."], "unknown symbol"),
        (["PE", ".."], "too small"),
    ])
    def test_broken_maps_raise(self, rows, why):
        with pytest.raises(MapError):
            parse_map({"rows": rows})

    def test_the_error_says_what_is_wrong(self):
        """A caller cannot fix a map from 'invalid'."""
        with pytest.raises(MapError, match="unreachable"):
            parse_map({"rows": ["PP..", "####", "..EE", "...."]})
