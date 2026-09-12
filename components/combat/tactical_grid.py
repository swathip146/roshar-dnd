"""
Tactical movement — the missing half of combat.

The gap this closes: `move` was declared in the action registry with an
`end_position` parameter that **nothing ever supplied**, so every attempt raised a
pydantic error and the actor silently lost its turn. Combat ran on a fixed two-row
line where everyone was permanently adjacent. No flanking, no cover, no reach, no
retreat — the tactical half of 5e simply did not exist.

The engine already had everything needed and none of it was wired: `Tile` with
`walkable`/`visible`, `Tile.get_fov()` for line of sight, and `Tile.get_paths()`
for Dijkstra pathing. Verified before writing this — FOV is correctly blocked by a
wall, and pathing detours through a doorway.

This module is the seam between an authored `BattleMap` and those primitives:

    build_terrain(battle_map)      -> registers engine Tiles
    place_combatants(...)          -> spawns on the map's own P/E tiles
    movement_options(...)          -> what this character can usefully DO
    move_to(...)                   -> spend movement, update position AND senses

**Movement is offered as intent, not coordinates** ("Close in on the Scout",
"Take cover behind the rock"), because a text game should read like a story and a
future UI wants clickable targets rather than typed numbers. The grid underneath is
real either way.

5e rules honoured here: 1 tile = 5 ft; a Medium creature's base speed is 30 ft
(6 tiles); difficult terrain costs double; and a tile occupied by another creature
cannot be entered.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from config.logging_config import get_logger

from components.combat.battle_map import (COVER, DIFFICULT, FEET_PER_TILE,
                                          BattleMap)

logger = get_logger(__name__)

DEFAULT_SPEED_FEET = 30           # 5e Medium humanoid
MELEE_REACH_FEET = 5


@dataclass
class MoveOption:
    """One offered movement, described by what it ACHIEVES."""

    label: str                       # player-facing: "Close in on the Scout"
    destination: Tuple[int, int]
    cost_feet: int
    intent: str                      # close | cover | retreat | reposition
    target: Optional[str] = None     # the character this is relative to

    def display(self) -> str:
        return f"{self.label} ({self.cost_feet} ft)"


class TacticalGrid:
    """
    Owns the engine's tile grid for one encounter.

    Deliberately holds no combat state — HP, initiative and the action economy stay
    where they already live. This is only geometry, so there is one place that knows
    about tiles and one source of truth for position.
    """

    def __init__(self, battle_map: BattleMap, dnd_wrapper=None):
        self.map = battle_map
        self.dnd_wrapper = dnd_wrapper
        self._built = False

    # ------------------------------------------------------------------ terrain

    def build_terrain(self) -> int:
        """
        Register an engine `Tile` for every square of the map.

        Tiles are a CLASS-LEVEL registry keyed by position, exactly like
        `Entity._entity_by_position` — the index whose desync caused every attack to
        cancel for a whole session. So clear it first: leftover tiles from a previous
        encounter would silently overlay this map with the last one's walls.
        """
        from dnd.core.base_tiles import Tile
        from uuid import uuid4

        self._clear_tiles()
        source = uuid4()
        built = 0
        for y in range(self.map.height):
            for x in range(self.map.width):
                position = (x, y)
                Tile(position=position,
                     walkable=self.map.is_walkable(position),
                     visible=self.map.is_transparent(position),
                     name=self.map.describe(position),
                     source_entity_uuid=source)
                built += 1

        self._built = True
        logger.info(f"🗺️  Terrain built: {self.map.width}x{self.map.height} "
                    f"({built} tiles) from {self.map.source} map "
                    f"'{self.map.name}'")
        return built

    def teardown(self) -> None:
        """
        Remove this encounter's terrain from the engine.

        MUST be called when combat ends. `Tile` keeps a CLASS-LEVEL registry, so
        terrain outlives the encounter that built it and silently changes the world
        for whatever runs next. Measured: a test file that built a 12x8 map with a
        wall column left 96 tiles behind, and the NEXT file's combat ran inside that
        stale grid — the hero took no damage because line of sight was blocked by a
        wall from a different battlefield, and a death-save test failed with
        "test needs the hero downed: assert 4 == 0".

        Same failure shape as `Entity._entity_by_position`, which cost a whole
        session. A class-level registry is global state; global state needs an owner
        and a lifetime.
        """
        self._clear_tiles()
        self._built = False
        logger.debug("🗺️  Terrain cleared")

    @staticmethod
    def _clear_tiles() -> None:
        """Drop the previous encounter's terrain."""
        try:
            from dnd.core.base_tiles import Tile

            Tile._tile_registry.clear()
            Tile._tile_by_position.clear()
        except Exception as e:
            logger.debug(f"   Could not clear tiles: {e}")

    # ---------------------------------------------------------------- placement

    def place_combatants(self, player_ids: Sequence[str],
                         hostile_ids: Sequence[str]) -> Dict[str, Tuple[int, int]]:
        """
        Put everyone on the map's own spawn tiles, then refresh senses ONCE.

        Placement goes through `wrapper.set_entity_position()`, which maintains
        `Entity._entity_by_position`. Assigning `entity.position` directly updates
        the attribute and not the index, which is what made a second hostile
        invisible to every sense map and cancelled every attack involving it.
        """
        placed: Dict[str, Tuple[int, int]] = {}
        if self.dnd_wrapper is None:
            return placed

        for ids, spawns in ((player_ids, self.map.party_spawns),
                            (hostile_ids, self.map.enemy_spawns)):
            for index, char_id in enumerate(ids):
                position = self._spawn_for(spawns, index, placed)
                if position is None:
                    logger.warning(f"   ⚠️ No free tile for {char_id}")
                    continue
                if self.dnd_wrapper.set_entity_position(char_id, position):
                    placed[char_id] = position

        # One global refresh AFTER all placements: sense maps must include everyone.
        if hasattr(self.dnd_wrapper, "refresh_senses"):
            self.dnd_wrapper.refresh_senses()

        logger.info(f"   📍 Placed {len(placed)} combatant(s) on the grid: "
                    + ", ".join(f"{c}{p}" for c, p in placed.items()))
        return placed

    def _spawn_for(self, spawns: Sequence[Tuple[int, int]], index: int,
                   taken: Dict[str, Tuple[int, int]]) -> Optional[Tuple[int, int]]:
        """A free spawn tile, falling back to the nearest free walkable square."""
        occupied = set(taken.values())
        for position in list(spawns)[index:] + list(spawns):
            if position not in occupied:
                return position
        # More combatants than authored spawns: spread out from the last spawn
        # rather than stacking, since two creatures cannot share a tile.
        anchor = spawns[-1] if spawns else (0, 0)
        for position in sorted(self.map.walkable_positions(),
                              key=lambda p: _chebyshev(p, anchor)):
            if position not in occupied:
                return position
        return None

    # ----------------------------------------------------------------- geometry

    def position_of(self, char_id: str) -> Optional[Tuple[int, int]]:
        entity = (self.dnd_wrapper.entities.get(char_id)
                  if self.dnd_wrapper else None)
        return tuple(entity.position) if entity is not None else None

    def occupied(self) -> Dict[Tuple[int, int], str]:
        """position -> char_id, for rendering and for blocking movement."""
        if self.dnd_wrapper is None:
            return {}
        return {tuple(entity.position): char_id
                for char_id, entity in self.dnd_wrapper.entities.items()}

    def distance_feet(self, a: str, b: str) -> Optional[int]:
        """
        5e distance between two combatants, in feet.

        Chebyshev, which is how 5e counts diagonals: moving diagonally costs the
        same as orthogonally, so a diagonal neighbour is 5 ft away, not 7.07.
        """
        first, second = self.position_of(a), self.position_of(b)
        if first is None or second is None:
            return None
        return _chebyshev(first, second) * FEET_PER_TILE

    def reach_feet(self, char_id: str) -> int:
        """
        This character's melee reach, from its equipped weapon.

        5e: most weapons reach 5 ft, but a glaive, halberd, pike or whip reaches 10 —
        and `_WEAPON_STATS` has carried that number all along while nothing read it.
        A Shardblade reaches 10 ft too, which matters for a Roshar campaign.
        """
        entity = (self.dnd_wrapper.entities.get(char_id)
                  if self.dnd_wrapper else None)
        if entity is None:
            return MELEE_REACH_FEET
        try:
            weapon = entity.equipment.weapon_main_hand
            if weapon is not None and getattr(weapon, "range", None) is not None:
                normal = getattr(weapon.range, "normal", None)
                if isinstance(normal, int) and normal > 0:
                    return normal
        except Exception:
            pass
        return MELEE_REACH_FEET

    def in_melee_reach(self, a: str, b: str) -> bool:
        """Can `a` strike `b` with its melee weapon, honouring the weapon's reach?"""
        distance = self.distance_feet(a, b)
        return distance is not None and distance <= self.reach_feet(a)

    def visible_positions(self, char_id: str,
                          max_distance: int = 12) -> Set[Tuple[int, int]]:
        """Field of view from a character, via the engine's shadowcasting."""
        from dnd.core.base_tiles import Tile

        position = self.position_of(char_id)
        if position is None:
            return set()
        try:
            return set(Tile.get_fov(position, max_distance=max_distance))
        except Exception as e:
            logger.debug(f"   FOV failed for {char_id}: {e}")
            return set()

    def has_cover(self, char_id: str) -> bool:
        position = self.position_of(char_id)
        return position is not None and self.map.is_cover(position)

    # ----------------------------------------------------------------- movement

    def reachable(self, char_id: str,
                  speed_feet: int = DEFAULT_SPEED_FEET
                  ) -> Dict[Tuple[int, int], int]:
        """
        Every tile this character can reach this turn -> cost in FEET.

        Uses the engine's Dijkstra, then applies two rules it does not know about:
        difficult terrain costs double, and a tile holding another creature cannot be
        entered.
        """
        from dnd.core.base_tiles import Tile

        start = self.position_of(char_id)
        if start is None:
            return {}

        tiles = max(1, speed_feet // FEET_PER_TILE)
        try:
            # Ask for extra range, because difficult terrain makes the true cost
            # higher than the tile count the engine returns.
            distances, _ = Tile.get_paths(start, max_distance=tiles * 2)
        except Exception as e:
            logger.debug(f"   Pathing failed for {char_id}: {e}")
            return {}

        blocked = set(self.occupied().values()) and {
            position for position, occupant in self.occupied().items()
            if occupant != char_id}

        options: Dict[Tuple[int, int], int] = {}
        for position, steps in distances.items():
            if position == start or position in blocked:
                continue
            cost = steps * FEET_PER_TILE
            if self.map.is_difficult(position):
                cost += FEET_PER_TILE      # double cost for the final square
            if cost <= speed_feet:
                options[position] = cost
        return options

    def movement_options(self, char_id: str, hostiles: Sequence[str],
                         speed_feet: int = DEFAULT_SPEED_FEET,
                         limit: int = 4) -> List[MoveOption]:
        """
        The useful things this character could do with its movement.

        Offers INTENT, not coordinates: closing on a specific enemy, taking cover,
        or breaking away. A list of 30 reachable squares is not a decision a player
        (or an LLM) can make well, and it does not translate to a UI.
        """
        reachable = self.reachable(char_id, speed_feet)
        if not reachable:
            return []

        options: List[MoveOption] = []
        occupied = self.occupied()

        # 1. Close on each hostile that is currently OUT of reach — the single most
        #    valuable move, and the one whose absence made combat static.
        for hostile in hostiles:
            target = self.position_of(hostile)
            if target is None or self.in_melee_reach(char_id, hostile):
                continue
            adjacent = [(p, c) for p, c in reachable.items()
                        if _chebyshev(p, target) <= 1]
            if adjacent:
                position, cost = min(adjacent, key=lambda pair: pair[1])
                options.append(MoveOption(
                    label=f"Close in on {self._name(hostile)}",
                    destination=position, cost_feet=cost,
                    intent="close", target=hostile))

        # 1b. If nothing adjacent is reachable, offer the best PARTIAL advance.
        #
        # Without this, a combatant further than its speed from every enemy is offered
        # no movement at all — so it stands still and swings at nothing. That is
        # exactly the 334-round `unknown` outcome measured right after the grid was
        # wired: on a real map the two sides start beyond one move of each other, and
        # "close the distance" has to be available in stages.
        if not options and hostiles:
            nearest = min(
                (h for h in hostiles if self.position_of(h) is not None),
                key=lambda h: self.distance_feet(char_id, h) or 10 ** 6,
                default=None)
            if nearest is not None:
                goal = self.position_of(nearest)
                # Closest reachable tile to the target; cheapest wins a tie, so a
                # partial advance never wastes movement.
                destination, cost = min(
                    reachable.items(),
                    key=lambda item: (_chebyshev(item[0], goal), item[1]))
                if _chebyshev(destination, goal) < _chebyshev(
                        self.position_of(char_id) or destination, goal):
                    options.append(MoveOption(
                        label=f"Advance on {self._name(nearest)}",
                        destination=destination, cost_feet=cost,
                        intent="close", target=nearest))

        # 2. Take cover, if any is reachable and we are not already in it.
        if not self.has_cover(char_id):
            cover = [(p, c) for p, c in reachable.items() if self.map.is_cover(p)]
            if cover:
                position, cost = min(cover, key=lambda pair: pair[1])
                options.append(MoveOption(
                    label="Take cover", destination=position,
                    cost_feet=cost, intent="cover"))

        # 3. Break away, if anything is currently in reach of us.
        engaged = [h for h in hostiles if self.in_melee_reach(char_id, h)]
        if engaged:
            safe = [(p, c) for p, c in reachable.items()
                    if all(_chebyshev(p, self.position_of(h) or p) > 1
                           for h in engaged)]
            if safe:
                position, cost = min(safe, key=lambda pair: pair[1])
                options.append(MoveOption(
                    label="Retreat out of reach", destination=position,
                    cost_feet=cost, intent="retreat"))

        return options[:limit]

    def move_to(self, char_id: str, destination: Tuple[int, int],
                speed_feet: int = DEFAULT_SPEED_FEET) -> Dict[str, Any]:
        """
        Move a combatant, refusing anything the rules do not allow.

        Refuses rather than clamping: silently moving somewhere the player did not
        choose is worse than saying no, and a refusal the narrator can read keeps the
        fiction honest about what happened.
        """
        if self.dnd_wrapper is None:
            return {"moved": False, "reason": "no engine wrapper"}

        start = self.position_of(char_id)
        if start is None:
            return {"moved": False, "reason": f"{char_id} is not on the grid"}

        reachable = self.reachable(char_id, speed_feet)
        if destination not in reachable:
            if not self.map.is_walkable(destination):
                reason = f"{destination} is {self.map.describe(destination)}"
            elif destination in self.occupied():
                reason = f"{destination} is already occupied"
            else:
                reason = (f"{destination} is beyond {speed_feet} ft of movement")
            return {"moved": False, "from": start, "reason": reason}

        cost = reachable[destination]
        if not self.dnd_wrapper.set_entity_position(char_id, destination):
            return {"moved": False, "from": start,
                    "reason": "the engine refused the move"}

        logger.info(f"   🏃 {char_id}: {start} -> {destination} ({cost} ft)")
        return {"moved": True, "from": start, "to": destination,
                "cost_feet": cost, "terrain": self.map.describe(destination),
                "in_cover": self.map.is_cover(destination)}

    # -------------------------------------------------------------------- display

    def render(self, acting: Optional[str] = None) -> str:
        """The battlefield as text, from the acting character's point of view."""
        from components.combat.battle_map import render as render_map

        visible = self.visible_positions(acting) if acting else None
        return render_map(self.map, occupants=self.occupied(), visible=visible)

    def _name(self, char_id: str) -> str:
        manager = getattr(self.dnd_wrapper, "character_manager", None)
        character = (manager.characters.get(char_id)
                     if manager is not None else None)
        return getattr(character, "name", char_id)


def _chebyshev(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    """5e counts a diagonal as one square, so distance is the larger delta."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))
