"""
Battle maps — the data model, parser and validator for tactical combat.

Why this exists: `dnd_engine` ships a complete, working tactical grid
(`dnd.core.base_tiles.Tile` with `walkable`/`visible`, plus `get_fov()` and
`get_paths()`), and **nothing in this project ever used it**. Verified before
building anything: line of sight is correctly blocked by a wall, and pathing
detours through a doorway (a 5-step route around a 1-tile wall). The sixth
built-but-unwired subsystem.

So this module does not implement pathfinding or FOV. It turns a *map* — authored
in the campaign, or derived from a location when none exists — into engine `Tile`s,
and reads the result back for display.

**Maps are authored, not improvised.** The campaign generator draws them once, so a
location's terrain is identical on every run. That matters for three reasons: an
encounter's difficulty depends on its terrain, tests cannot assert on a battlefield
that changes every time, and a UI needs stable geometry to render. A runtime
fallback exists only so a location without a map still gets a playable grid.

Coordinates are `(x, y)`, y increasing downward, matching how the rows read as text.
One tile is **5 feet**, the 5e standard.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from config.logging_config import get_logger

logger = get_logger(__name__)

FEET_PER_TILE = 5

# The authored map legend. Deliberately small: every symbol has to mean something
# the engine can act on, or it is decoration pretending to be terrain.
#
#   .  open floor            walkable, transparent
#   #  wall / chasm          NOT walkable, NOT transparent (blocks line of sight)
#   H  high ground / cover   walkable, transparent — grants cover (see is_cover)
#   ~  difficult terrain     walkable at double cost (rubble, water, shattered rock)
#   P  party start           walkable floor, marked as a player spawn
#   E  enemy start           walkable floor, marked as a hostile spawn
#
# `#` blocks BOTH movement and sight, which is what makes a chasm different from
# cover: you can shoot over a rock, not through a wall.
FLOOR = "."
WALL = "#"
COVER = "H"
DIFFICULT = "~"
PARTY_SPAWN = "P"
ENEMY_SPAWN = "E"

_WALKABLE = {FLOOR, COVER, DIFFICULT, PARTY_SPAWN, ENEMY_SPAWN}
_TRANSPARENT = {FLOOR, COVER, DIFFICULT, PARTY_SPAWN, ENEMY_SPAWN}
_KNOWN = _WALKABLE | {WALL}

MAX_WIDTH = 40
MAX_HEIGHT = 40
MIN_WIDTH = 4
MIN_HEIGHT = 4


@dataclass
class BattleMap:
    """
    A parsed, validated battle map.

    `rows` is the authoritative grid; the spawn lists are derived from it. Anything
    that reads terrain should go through the accessors rather than indexing `rows`,
    so the symbol vocabulary stays in one place.
    """

    name: str
    rows: List[str]
    party_spawns: List[Tuple[int, int]] = field(default_factory=list)
    enemy_spawns: List[Tuple[int, int]] = field(default_factory=list)
    source: str = "authored"          # authored | generated | fallback
    legend: Dict[str, str] = field(default_factory=dict)

    # ------------------------------------------------------------------ shape

    @property
    def width(self) -> int:
        return len(self.rows[0]) if self.rows else 0

    @property
    def height(self) -> int:
        return len(self.rows)

    def symbol_at(self, position: Tuple[int, int]) -> str:
        x, y = position
        if 0 <= y < self.height and 0 <= x < len(self.rows[y]):
            return self.rows[y][x]
        return WALL          # off-map is solid, so nobody walks off the edge

    def is_walkable(self, position: Tuple[int, int]) -> bool:
        return self.symbol_at(position) in _WALKABLE

    def is_transparent(self, position: Tuple[int, int]) -> bool:
        return self.symbol_at(position) in _TRANSPARENT

    def is_cover(self, position: Tuple[int, int]) -> bool:
        """
        Does standing here grant cover? (5e: +2 AC for half cover.)

        Cover is transparent but obstructive — you can see and shoot over a rock,
        which is precisely what distinguishes it from a wall.
        """
        return self.symbol_at(position) == COVER

    def is_difficult(self, position: Tuple[int, int]) -> bool:
        """5e: difficult terrain costs 2 feet of movement per foot travelled."""
        return self.symbol_at(position) == DIFFICULT

    def walkable_positions(self) -> List[Tuple[int, int]]:
        return [(x, y)
                for y in range(self.height)
                for x in range(len(self.rows[y]))
                if self.is_walkable((x, y))]

    def describe(self, position: Tuple[int, int]) -> str:
        """A short phrase for narration — never a raw symbol."""
        return {
            FLOOR: "open ground",
            WALL: "impassable rock",
            COVER: "cover",
            DIFFICULT: "difficult ground",
            PARTY_SPAWN: "open ground",
            ENEMY_SPAWN: "open ground",
        }.get(self.symbol_at(position), "open ground")

    def to_dict(self) -> Dict[str, Any]:
        """Serialisable form, for saving and for a UI to render."""
        return {"name": self.name, "rows": list(self.rows),
                "source": self.source, "legend": dict(self.legend),
                "width": self.width, "height": self.height,
                "party_spawns": [list(p) for p in self.party_spawns],
                "enemy_spawns": [list(p) for p in self.enemy_spawns]}


class MapError(ValueError):
    """An authored map that cannot be used. Raised with the reason, never guessed."""


def parse_map(data: Any, name: str = "battlefield",
              source: str = "authored") -> BattleMap:
    """
    Parse and VALIDATE an authored map.

    Raises `MapError` with a specific reason rather than repairing silently. An
    unusable map must be loud: a quietly "fixed" battlefield is how an encounter
    ends up unwinnable, or how every attack cancels for want of a walkable tile —
    the exact failure mode that cost this project a full session when entities were
    positioned off the sense grid.

    Accepts either `{"rows": [...], "legend": {...}}` or a bare list of row strings.
    """
    if isinstance(data, dict):
        rows = data.get("rows")
        legend = data.get("legend") or {}
        name = data.get("name") or name
    else:
        rows, legend = data, {}

    if not isinstance(rows, list) or not rows:
        raise MapError("map has no rows")
    if not all(isinstance(row, str) for row in rows):
        raise MapError("every map row must be a string")

    rows = [row.rstrip("\n") for row in rows]

    widths = {len(row) for row in rows}
    if len(widths) != 1:
        raise MapError(
            f"ragged map: rows have differing widths {sorted(widths)} — every row "
            f"must be the same length, or coordinates do not line up")

    width, height = len(rows[0]), len(rows)
    if not (MIN_WIDTH <= width <= MAX_WIDTH and MIN_HEIGHT <= height <= MAX_HEIGHT):
        raise MapError(
            f"map is {width}x{height}; must be between {MIN_WIDTH}x{MIN_HEIGHT} "
            f"and {MAX_WIDTH}x{MAX_HEIGHT} ({MAX_WIDTH * MAX_HEIGHT} tiles is "
            f"already a lot to path across every turn)")

    unknown = {c for row in rows for c in row} - _KNOWN
    if unknown:
        raise MapError(
            f"unknown map symbols {sorted(unknown)}; allowed: {sorted(_KNOWN)}")

    battle_map = BattleMap(name=name, rows=rows, source=source, legend=legend)
    battle_map.party_spawns = _find(rows, PARTY_SPAWN)
    battle_map.enemy_spawns = _find(rows, ENEMY_SPAWN)

    _validate_playable(battle_map)
    return battle_map


def _find(rows: List[str], symbol: str) -> List[Tuple[int, int]]:
    return [(x, y) for y, row in enumerate(rows)
            for x, c in enumerate(row) if c == symbol]


def _validate_playable(battle_map: BattleMap) -> None:
    """
    Reject maps that would produce a broken encounter.

    Each check corresponds to a way combat has actually failed here:
      * no walkable tiles      -> nobody can be placed, every attack cancels
      * no spawns              -> placement falls back to a corner, out of reach
      * spawns unreachable     -> the fight cannot start, or cannot progress
    """
    walkable = battle_map.walkable_positions()
    if len(walkable) < 4:
        raise MapError(f"only {len(walkable)} walkable tiles; nobody could move")

    if not battle_map.party_spawns:
        raise MapError(f"no party spawn ('{PARTY_SPAWN}') on the map")
    if not battle_map.enemy_spawns:
        raise MapError(f"no enemy spawn ('{ENEMY_SPAWN}') on the map")

    # Every enemy must be REACHABLE from a party spawn. A map where the two sides
    # are separated by a wall produces a fight nobody can win — and since nothing
    # in the loop repositions across an impassable gap, it would run to the round
    # limit and report `unknown`.
    reachable = _flood(battle_map, battle_map.party_spawns[0])
    stranded = [p for p in battle_map.enemy_spawns if p not in reachable]
    if stranded:
        raise MapError(
            f"enemy spawns {stranded} are unreachable from the party spawn "
            f"{battle_map.party_spawns[0]} — the encounter could never resolve")


def _flood(battle_map: BattleMap, start: Tuple[int, int]) -> Set[Tuple[int, int]]:
    """Every tile reachable from `start` by walking (8-way, like the engine)."""
    seen = {start}
    frontier = [start]
    while frontier:
        x, y = frontier.pop()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nxt = (x + dx, y + dy)
                if nxt not in seen and battle_map.is_walkable(nxt):
                    seen.add(nxt)
                    frontier.append(nxt)
    return seen


def render(battle_map: BattleMap,
           occupants: Optional[Dict[Tuple[int, int], str]] = None,
           visible: Optional[Set[Tuple[int, int]]] = None) -> str:
    """
    Draw the map as text, with combatant initials overlaid.

    This is what the player sees each round, and it is deliberately the same data a
    UI would render — if the text map is wrong, the UI would be wrong too, so this
    doubles as a check on the grid itself.

    `visible` (optional) dims tiles outside the acting character's field of view, so
    the display cannot claim knowledge the character does not have.
    """
    occupants = occupants or {}
    width = battle_map.width

    header = "    " + " ".join(f"{x}" if x < 10 else f"{x % 10}"
                               for x in range(width))
    lines = [header]

    for y in range(battle_map.height):
        cells = []
        for x in range(width):
            position = (x, y)
            if position in occupants:
                cells.append(occupants[position][:1].upper())
            elif visible is not None and position not in visible:
                cells.append(" ")       # not seen: show nothing, not terrain
            else:
                cells.append(battle_map.rows[y][x])
        lines.append(f"{y:>3} " + " ".join(cells))

    key = [f"{FLOOR} open", f"{WALL} wall/chasm", f"{COVER} cover",
           f"{DIFFICULT} difficult"]
    lines.append("    " + "   ".join(key))
    return "\n".join(lines)
