"""
Deterministic terrain templates — a battlefield for a location with no authored map.

Maps are meant to be AUTHORED, in the campaign, by the generator. This module is the
fallback for a location that has none, so a fight always has real terrain instead of
the two-row line where everyone starts permanently adjacent.

**Deterministic, not generated.** Same location name and type gives the same map on
every run. That matters because an encounter's difficulty depends on its terrain, a
test cannot assert on a battlefield that changes every time, and a UI needs stable
geometry. Where randomness is used (scattering cover), it is seeded from the location
NAME, so "The Shattered Plains" is always laid out identically.

Templates are chosen from the location's authored `type` — "city", "wilderness",
"dungeon" and so on. Unknown types get open ground with light cover, which is the
safe default: flat and winnable.
"""

from __future__ import annotations

import random
from typing import List, Optional

from config.logging_config import get_logger

from components.combat.battle_map import (COVER, DIFFICULT, ENEMY_SPAWN, FLOOR,
                                          PARTY_SPAWN, WALL, BattleMap,
                                          MapError, parse_map)

logger = get_logger(__name__)

# Big enough for 30 ft of movement (6 tiles) to matter, small enough to render in a
# terminal and to path across quickly every turn.
DEFAULT_WIDTH = 12
DEFAULT_HEIGHT = 8


def map_for_location(name: str, location_type: str = "",
                     party_size: int = 1,
                     hostile_count: int = 1) -> Optional[BattleMap]:
    """
    A deterministic battle map for a location.

    Returns None only if even the fallback fails validation, which would be a bug in
    this module rather than in the campaign.
    """
    template = _template_for(location_type)
    rows = template(name, party_size, hostile_count)

    try:
        battle_map = parse_map({"rows": rows, "name": name}, source="generated")
        logger.info(f"   🗺️  Generated a '{_label(location_type)}' battlefield for "
                    f"{name!r} ({battle_map.width}x{battle_map.height})")
        return battle_map
    except MapError as e:
        # The templates are ours, so this is our bug — say so rather than silently
        # returning None and leaving the caller to guess.
        logger.error(f"❌ Generated map for {name!r} is invalid: {e}")
        return None


def _label(location_type: str) -> str:
    return _TEMPLATE_LABELS.get(_normalise(location_type), "open ground")


def _normalise(location_type: str) -> str:
    """Map an authored type onto a template key, tolerating free text."""
    text = (location_type or "").strip().lower()
    for key, words in _TYPE_WORDS.items():
        if any(word in text for word in words):
            return key
    return "open"


# Authored `type` values are free text ("City/Dungeon/Wilderness" in the generator's
# own schema), so match on words rather than requiring an exact enum.
_TYPE_WORDS = {
    "chasm": ("chasm", "plains", "plateau", "shattered", "canyon", "rift"),
    "urban": ("city", "town", "settlement", "village", "camp", "market", "palace"),
    "dungeon": ("dungeon", "cavern", "cave", "crypt", "tomb", "ruin", "tunnel"),
    "forest": ("forest", "wood", "jungle", "grove"),
    "open": ("wilderness", "field", "open", "hill"),
}

_TEMPLATE_LABELS = {
    "chasm": "chasm-riven plateau",
    "urban": "built-up ground",
    "dungeon": "enclosed chamber",
    "forest": "broken woodland",
    "open": "open ground",
}


def _template_for(location_type: str):
    return {
        "chasm": _chasm_plateau,
        "urban": _urban,
        "dungeon": _dungeon,
        "forest": _forest,
        "open": _open_ground,
    }[_normalise(location_type)]


# --------------------------------------------------------------------------
# Templates. Each returns rows; spawns are placed on opposite sides so both
# lines start OUT of melee reach — the whole point is that closing the distance
# becomes a decision rather than a given.
# --------------------------------------------------------------------------

def _blank(width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT) -> List[List[str]]:
    return [[FLOOR for _ in range(width)] for _ in range(height)]


def _finish(grid: List[List[str]], party_size: int,
            hostile_count: int) -> List[str]:
    """
    Place spawns and return rows.

    Party on the left edge, hostiles on the right, both vertically centred. Spawn
    tiles are forced to open floor: a spawn inside a wall would be unreachable, and
    the validator would (correctly) reject the map.
    """
    height, width = len(grid), len(grid[0])
    middle = height // 2

    def place(symbol: str, x: int, count: int) -> None:
        placed = 0
        # Walk outward from the middle row so a small party stands together.
        for offset in _outward(height):
            if placed >= count:
                return
            y = middle + offset
            if 0 <= y < height:
                grid[y][x] = symbol
                placed += 1
        # More combatants than rows: spill into the adjacent column.
        step = 1 if x < width // 2 else -1
        for offset in _outward(height):
            if placed >= count:
                return
            y = middle + offset
            if 0 <= y < height and 0 <= x + step < width:
                grid[y][x + step] = symbol
                placed += 1

    place(PARTY_SPAWN, 0, max(1, party_size))
    place(ENEMY_SPAWN, width - 1, max(1, hostile_count))
    return ["".join(row) for row in grid]


def _outward(height: int) -> List[int]:
    """Row offsets from the centre: 0, -1, +1, -2, +2, ..."""
    offsets = [0]
    for step in range(1, height):
        offsets.extend([-step, step])
    return offsets


def _rng(name: str) -> random.Random:
    """Seeded from the location NAME, so a place always looks the same."""
    return random.Random(f"battlefield:{name}")


def _chasm_plateau(name: str, party_size: int, hostile_count: int) -> List[str]:
    """
    Roshar's signature terrain: open plateau split by an impassable chasm.

    The chasm has a crossing, so the map is playable — a fight where the two sides
    cannot reach each other would never resolve, and the validator rejects it.
    """
    grid = _blank()
    height, width = len(grid), len(grid[0])
    rng = _rng(name)

    chasm_x = width // 2
    crossing = height // 2 + rng.choice((-1, 0, 1))
    for y in range(height):
        if y != crossing:
            grid[y][chasm_x] = WALL
    # A rubble-strewn approach to the crossing: crossing it should cost something.
    grid[crossing][max(0, chasm_x - 1)] = DIFFICULT
    grid[crossing][min(width - 1, chasm_x + 1)] = DIFFICULT

    for _ in range(3):
        grid[rng.randrange(height)][rng.randrange(2, width - 2)] = COVER
    return _finish(grid, party_size, hostile_count)


def _urban(name: str, party_size: int, hostile_count: int) -> List[str]:
    """Streets between buildings: hard corners, so cover and LOS both matter."""
    grid = _blank()
    height, width = len(grid), len(grid[0])
    rng = _rng(name)

    # Two building blocks, leaving a clear street between and around them.
    for corner_x, corner_y in ((3, 1), (width - 5, height - 4)):
        for dx in range(2):
            for dy in range(2):
                y, x = corner_y + dy, corner_x + dx
                if 0 < y < height - 1 and 0 < x < width - 1:
                    grid[y][x] = WALL

    for _ in range(2):
        grid[rng.randrange(height)][rng.randrange(2, width - 2)] = COVER
    return _finish(grid, party_size, hostile_count)


def _dungeon(name: str, party_size: int, hostile_count: int) -> List[str]:
    """A chamber with pillars — cover without blocking the route."""
    grid = _blank()
    height, width = len(grid), len(grid[0])

    for y in range(2, height - 1, 3):
        for x in range(3, width - 2, 4):
            grid[y][x] = WALL          # pillar: blocks sight and movement
    return _finish(grid, party_size, hostile_count)


def _forest(name: str, party_size: int, hostile_count: int) -> List[str]:
    """Scattered trunks and undergrowth: lots of cover, slow going."""
    grid = _blank()
    height, width = len(grid), len(grid[0])
    rng = _rng(name)

    for _ in range(6):
        grid[rng.randrange(height)][rng.randrange(2, width - 2)] = COVER
    for _ in range(5):
        grid[rng.randrange(height)][rng.randrange(2, width - 2)] = DIFFICULT
    return _finish(grid, party_size, hostile_count)


def _open_ground(name: str, party_size: int, hostile_count: int) -> List[str]:
    """
    The safe default: flat, with a little cover.

    Used for any unrecognised location type. Deliberately dull — an unknown location
    should be winnable, not a surprise deathtrap.
    """
    grid = _blank()
    height, width = len(grid), len(grid[0])
    rng = _rng(name)

    for _ in range(2):
        grid[rng.randrange(height)][rng.randrange(2, width - 2)] = COVER
    return _finish(grid, party_size, hostile_count)
