"""
Shared fixtures for the combat suite.

Two kinds of cross-test global state leak between combat tests and are reset
here for isolation:

1. The **global `random` module**. `external/dnd_engine/dnd/core/dice.py` rolls
   with module-level `random.randint`, and nothing seeds it (pytest-randomly is
   not installed, so `-p no:randomly` is a no-op). Every dice-rolling test
   advances one shared RNG stream, so how far it has advanced when a given test
   runs depends on which other tests ran first on that xdist worker.

   `test_encounter_does_not_end_at_zero_hp` swings a single greatsword and needs
   it to land to down the hero; from an unlucky RNG offset the swing missed, the
   hero stayed up, and "test needs the hero downed" failed. It passed alone and
   in its own file (fixed roll count) but failed intermittently in the full
   parallel suite (variable roll count). NOTE: the folklore that blamed the
   class-level entity/tile registries is wrong — resetting those does not fix it.

   The reseed is scoped to `test_death_saves_in_combat.py` on purpose: forcing
   one fixed dice stream on *every* combat test perturbs the statistical
   proficiency tests (e.g. `test_a_higher_level_character_is_not_wildly_more_
   accurate`), so we only pin the RNG for the file whose single-swing lethality
   tests actually need reproducible dice.

2. The engine's class-level registries (`Entity._entity_registry` /
   `_entity_by_position`, `Tile._tile_registry` / `_tile_by_position`,
   `BaseObject._registry`). These accumulate every entity, tile and condition
   ever created and are never cleared; clearing them per test is cheap global-
   state hygiene applied to the whole combat suite.
"""

import random

import pytest

# tests/conftest.py already inserts external/dnd_engine onto sys.path, so the
# dnd_engine package imports cleanly here at collection time.
from dnd.entity import Entity
from dnd.core.base_tiles import Tile
from dnd.core.base_object import BaseObject
from config.logging_config import get_logger

logger = get_logger(__name__)

# A fixed, arbitrary seed. Its only requirement is reproducibility; tests that
# care about a specific roll script it themselves (see `_session(rolls=...)` in
# test_death_saves_in_combat.py).
_RNG_SEED = 1_234_567

# Tests whose dice must be reproducible regardless of what ran before them.
_RNG_PINNED_FILES = {"test_death_saves_in_combat.py"}

# (class, attribute) for every class-level registry that accumulates across tests.
_ENGINE_REGISTRIES = [
    (Entity, "_entity_registry"),
    (Entity, "_entity_by_position"),
    (Tile, "_tile_registry"),
    (Tile, "_tile_by_position"),
    (BaseObject, "_registry"),
]


def _clear_engine_registries() -> None:
    """Empty every shared dnd_engine registry in place.

    `.clear()` (rather than reassignment) preserves the ClassVar's identity and,
    for `_entity_by_position`, its ``defaultdict(list)`` factory.
    """
    for cls, attr in _ENGINE_REGISTRIES:
        registry = getattr(cls, attr, None)
        if registry is not None:
            registry.clear()


@pytest.fixture(autouse=True)
def reset_engine_global_state(request):
    """Isolate each combat test from another test's leftover engine state."""
    _clear_engine_registries()
    if request.node.path.name in _RNG_PINNED_FILES:
        random.seed(_RNG_SEED)
        logger.debug("🎲 Pinned dnd_engine RNG for %s", request.node.path.name)
    yield
    _clear_engine_registries()
