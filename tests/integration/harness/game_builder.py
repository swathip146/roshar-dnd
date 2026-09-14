"""
Builds real games for the deterministic suite.

EVERYTHING HERE IS REAL except the LLM. `GameEngine`, `CharacterManager`, the vendored
`dnd_engine`, the tactical grid, dice and all rules JSON are the production objects.
Determinism comes from `random.seed()`, never from stubbing dice — stubbing dice is
exactly what let the advantage no-op survive for so long (`_roll_with_advantage` rolled
one die and took `max()` of a 1-element list, invisible to any mocked roll).

NO `unittest.mock` HERE, DELIBERATELY. Three of the four stale tests this suite replaces
failed precisely because a `Mock` drifted from the real contract — one of them produced
`TypeError: unsupported operand type(s) for -: 'Mock' and 'Mock'` when real encumbrance
code did arithmetic on a mock speed. A Mock accepts any call, so it passes right up
until it needs a real value. `tests/integration/conftest.py` enforces the ban.
"""

from __future__ import annotations

import copy
import random
from typing import Any, Dict, List, Optional

from config.logging_config import get_logger

logger = get_logger(__name__)

#: Default seed. Any test asserting on a distribution states its own seed so a
#: failure is reproducible from the message alone.
DEFAULT_SEED = 1_234_567


# --------------------------------------------------------------------------- #
# Character templates — real 5e/Roshar shapes
# --------------------------------------------------------------------------- #

def character_template(
    char_id: str = "aggi",
    name: str = "Aggi",
    level: int = 3,
    character_class: str = "Fighter",
    **overrides: Any,
) -> Dict[str, Any]:
    """A complete character dict, matching what `add_character` really consumes."""
    template: Dict[str, Any] = {
        "character_id": char_id,
        "name": name,
        "level": level,
        "character_class": character_class,
        "race": "Alethi",
        "background": "Soldier",
        "ability_scores": {"strength": 16, "dexterity": 14, "constitution": 14,
                           "intelligence": 10, "wisdom": 12, "charisma": 10},
        "hit_points": {"current": 28, "maximum": 28, "temporary": 0},
        "armor_class": 16,
        "speed": 30,
        "skills": {"athletics": True, "perception": True},
        "equipment": ["longsword", "chain mail", "shield"],
        "experience_points": 900,
    }
    template.update(overrides)
    return template


def radiant_template(
    char_id: str = "shallan",
    name: str = "Shallan",
    order: str = "Lightweaver",
    level: int = 5,
    **overrides: Any,
) -> Dict[str, Any]:
    """A Knight Radiant, for the Cosmere scenarios (R1-R11)."""
    template = character_template(
        char_id=char_id, name=name, level=level, character_class=order,
        ability_scores={"strength": 10, "dexterity": 14, "constitution": 12,
                        "intelligence": 16, "wisdom": 12, "charisma": 14},
        hit_points={"current": 38, "maximum": 38, "temporary": 0},
        armor_class=14,
        equipment=["shardblade", "leather armor"],
    )
    template.update({
        "radiant_order": order,
        "stormlight_current": 8,
        "stormlight_capacity": 8,
        "ideal_level": 3,
        "surgebinding_level": level,
        # `{"current": N, "maximum": M}` — a single pool, NOT a bare int and not
        # leveled like spell slots. `InvestiturePointLedger._pool()` returns
        # {"current": 0} for anything that is not a dict
        # (`components/combat/investiture_ledger.py:73-76`), so a bare int silently
        # leaves a Radiant with zero Investiture.
        "investiture_points": {"current": 12, "maximum": 12},
        # A bonded Blade must be SUMMONED before it can swing: `ShardbladeAttack`
        # refuses with "Shardblade not summoned (use 1 Bonus Action to summon)"
        # (`roshar_actions.py:327-332`), and the registry gates on this field.
        "has_shardblade": True,
        "shardblade_summoned": True,
    })
    template.update(overrides)
    return template


def caster_template(
    char_id: str = "jasnah",
    name: str = "Jasnah",
    character_class: str = "Wizard",
    level: int = 5,
    **overrides: Any,
) -> Dict[str, Any]:
    """A spellcaster with real slots, for C9."""
    template = character_template(
        char_id=char_id, name=name, level=level, character_class=character_class,
        ability_scores={"strength": 8, "dexterity": 14, "constitution": 12,
                        "intelligence": 17, "wisdom": 12, "charisma": 10},
        hit_points={"current": 32, "maximum": 32, "temporary": 0},
        armor_class=12,
        equipment=["quarterstaff"],
    )
    template.update({
        # The real shape is {level: {"current": N, "maximum": N}} — NOT {level: N}.
        # `SpellSlotLedger._slots()` skips any value that is not a dict
        # (`components/combat/spellcasting.py:232-241`), so bare ints make a fully
        # stocked wizard report "no spell slots at all". Found exactly that way.
        "spell_slots": {
            1: {"current": 4, "maximum": 4},
            2: {"current": 3, "maximum": 3},
            3: {"current": 2, "maximum": 2},
        },
        "spells_known": ["fire bolt", "magic missile", "cure wounds",
                         "shield", "fireball"],
        "spellcasting_ability": "intelligence",
    })
    template.update(overrides)
    return template


# --------------------------------------------------------------------------- #
# Engine construction
# --------------------------------------------------------------------------- #

def build_engine(
    characters: Optional[List[Dict[str, Any]]] = None,
    policy_profile: Any = None,
    seed: Optional[int] = DEFAULT_SEED,
):
    """A real `GameEngine` with real characters.

    Args:
        characters: dicts for `add_character`. Defaults to one Fighter.
        policy_profile: a `PolicyProfile`; defaults to RAW.
        seed: seeds the global RNG the engine's dice read. None leaves it alone.
    """
    from components.game_engine import GameEngine, PolicyProfile

    if seed is not None:
        random.seed(seed)

    engine = GameEngine(policy_profile=policy_profile or PolicyProfile.RAW)
    for data in (characters if characters is not None else [character_template()]):
        engine.add_character(copy.deepcopy(data))

    logger.debug("🧪 engine built with %d characters",
                 len(engine.character_manager.characters))
    return engine


def build_wrapper(engine):
    """A real `DnDEngineWrapper` over the engine — entities, senses, positions.

    Both arguments are required: it is a dataclass with `game_engine` and
    `character_manager` fields (`components/dnd_engine_wrapper.py:140-141`), and
    `__post_init__` does the real work — syncing entities, equipping weapons, and
    mirroring Roshar/class-feature attributes onto each Entity. Passing the engine's
    own manager keeps a single source of truth rather than a second copy.
    """
    from components.dnd_engine_wrapper import DnDEngineWrapper

    return DnDEngineWrapper(
        game_engine=engine,
        character_manager=engine.character_manager,
    )


class HeadlessGame:
    """A `HaystackDnDGame`-shaped object with no stdin, no network, no orchestrator.

    Built with `__new__` and populated field by field — the pattern
    `scripts/playtest.py:828-876` already uses for its `--no-llm` mode. The real
    `__init__` builds pipelines and reads the environment for API keys.
    """

    def __init__(self, engine, save_dir: Optional[str] = None):
        from haystack_dnd_game import HaystackDnDGame

        game = HaystackDnDGame.__new__(HaystackDnDGame)
        game.game_engine = engine
        game.character_manager = engine.character_manager
        game.dnd_engine_wrapper = None
        game.current_choices = []
        game.turn_counter = 0
        game.session_manager = _InMemorySession(save_dir)

        self.game = game
        self.engine = engine

    def __getattr__(self, item):
        return getattr(self.game, item)


class _InMemorySession:
    """A real-shaped session manager that writes to a tmp dir instead of game_saves/."""

    def __init__(self, save_directory: Optional[str] = None):
        import tempfile

        self.save_directory = save_directory or tempfile.mkdtemp(prefix="rd-itest-")
        self.saved: Dict[str, Any] = {}

    def get_session_metadata(self) -> Dict[str, Any]:
        return {"session_id": "integration", "session_active": True}

    def save_session(self, filename=None, game_engine_state=None,
                     character_manager_state=None) -> Dict[str, Any]:
        import json
        from pathlib import Path

        target = Path(self.save_directory) / (filename or "integration.json")
        target.parent.mkdir(parents=True, exist_ok=True)
        blob = {
            "session_metadata": {"player_name": "Integration"},
            "game_state": game_engine_state or {},
            "character_data": character_manager_state or {},
        }
        target.write_text(json.dumps(blob, indent=1, default=str))
        self.saved[str(target)] = blob
        return {"success": True, "result": {"filepath": str(target)}}
