"""
Fixtures and guards for the deterministic integration suite (Suite A).

THREE GUARANTEES THIS FILE ENFORCES
-----------------------------------
1. **No mocks of game state.** A collection-time guard rejects any test module here
   that imports `unittest.mock`. Three of the four stale tests this suite replaces
   failed because a Mock drifted from the real contract — one produced
   `TypeError: unsupported operand type(s) for -: 'Mock' and 'Mock'` when real
   encumbrance code did arithmetic on a mock speed. A Mock accepts any call, so it
   passes right up until it needs a real value. Only the LLM boundary is faked, via
   `fakes/`.

2. **No network.** `socket.socket` is blocked for the whole suite, so a missed
   generator injection fails loudly instead of silently calling the real API (and
   silently costing money).

3. **Parallel safety.** Per-test teardown of the engine's CLASS-level registries
   (`Entity._entity_by_position`, `Tile._tile_registry`), so a leak fails its own test
   rather than a neighbour's on the same xdist worker. Coverage observations go to a
   shared directory because under `-n 8` each worker is a separate process and an
   in-memory ledger would only ever see its own slice.
"""

from __future__ import annotations

import os
import random
import socket
import tempfile
from pathlib import Path
from typing import List

import pytest

from config.logging_config import get_logger
from tests.integration.harness import invariants
from tests.integration.harness.coverage import COVERAGE_DIR_ENV, CoverageLedger

logger = get_logger(__name__)


def _resolve_coverage_dir() -> Path:
    """The one directory this whole run records into, controller and workers alike.

    DO NOT compute this at import time from `PYTEST_XDIST_TESTRUNUID`. That variable
    does not exist yet when the CONTROLLER imports this module, but does by the time
    each WORKER imports it — so controller and workers derived DIFFERENT directories.
    The workers wrote 23 observation files into their own directory while the
    controller's gates read an empty one, and the partial-run negative control
    silently "passed" because the gates found nothing to check.

    So: `RD_COVERAGE_DIR` wins if already set (the controller sets it in
    `pytest_configure`, and pytest-xdist propagates os.environ to workers). Only when
    it is unset is a fresh path minted, keyed by PID so concurrent runs stay separate.
    """
    existing = os.environ.get(COVERAGE_DIR_ENV)
    if existing:
        return Path(existing)
    return Path(tempfile.gettempdir()) / f"roshar-coverage-{os.getpid()}"


# --------------------------------------------------------------------------- #
# Guard 1 — the mock ban
# --------------------------------------------------------------------------- #

def pytest_collectstart(collector):
    """Reject `unittest.mock` anywhere in this suite, at collection time."""
    path = getattr(collector, "path", None)
    if path is None or path.suffix != ".py":
        return
    try:
        source = path.read_text()
    except OSError:
        return
    for banned in ("from unittest.mock", "import unittest.mock",
                   "from unittest import mock"):
        if banned in source:
            raise pytest.UsageError(
                f"{path.name} imports unittest.mock, which Suite A forbids: only the "
                f"LLM boundary may be faked (see tests/integration/fakes/). Mock-based "
                f"tests are what decayed into the four failures this suite replaces."
            )


# --------------------------------------------------------------------------- #
# Guard 2 — no network
# --------------------------------------------------------------------------- #

class _BlockedSocket(socket.socket):
    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            "Suite A opened a network socket. Some agent did not receive a scripted "
            "generator — install one with `scripted_llm(...)` or the `scripted_game` "
            "fixture. (A real LLM call here would be non-deterministic and cost money.)"
        )


@pytest.fixture(autouse=True, scope="session")
def _no_network():
    """Block outbound sockets for the whole suite; restore afterwards."""
    real = socket.socket
    socket.socket = _BlockedSocket           # type: ignore[misc,assignment]
    try:
        yield
    finally:
        socket.socket = real                 # type: ignore[misc,assignment]


# --------------------------------------------------------------------------- #
# Guard 3 — engine global state, per test
# --------------------------------------------------------------------------- #

def _clear_engine_registries() -> None:
    """Empty every shared dnd_engine registry in place.

    `.clear()` rather than reassignment preserves each ClassVar's identity and, for
    `_entity_by_position`, its `defaultdict(list)` factory. Mirrors
    `tests/combat/conftest.py`, which documents the same hazard.
    """
    from dnd.core.base_object import BaseObject
    from dnd.core.base_tiles import Tile
    from dnd.entity import Entity

    for cls, attr in ((Entity, "_entity_registry"), (Entity, "_entity_by_position"),
                      (Tile, "_tile_registry"), (Tile, "_tile_by_position"),
                      (BaseObject, "_registry")):
        registry = getattr(cls, attr, None)
        if registry is not None:
            registry.clear()


@pytest.fixture(autouse=True)
def isolate_engine_state():
    """Fresh engine registries and a pinned RNG for every test."""
    _clear_engine_registries()
    random.seed(1_234_567)
    yield
    _clear_engine_registries()


# --------------------------------------------------------------------------- #
# Coverage
# --------------------------------------------------------------------------- #

def pytest_configure(config):
    """Set up the coverage directory before ANY test runs, and purge stale runs.

    This must be a hook rather than a session fixture. A fixture only executes when a
    test first requests it, so its ordering relative to the first recording test is
    not guaranteed — and a sequential run reuses the `-local` directory key. That
    combination let a PARTIAL run's gates pass on 449 observation files left by
    earlier runs: the mechanic tokens were all present, just not from this run. A
    gate satisfied by yesterday's evidence is exactly the "passes while proving
    nothing" failure this suite exists to prevent.

    Only the controller purges. A worker clearing the directory mid-run would delete
    its siblings' observations.
    """
    directory = _resolve_coverage_dir()
    directory.mkdir(parents=True, exist_ok=True)
    # Publishing this makes the controller's choice authoritative: pytest-xdist
    # propagates os.environ to workers, so they resolve to the same directory.
    os.environ[COVERAGE_DIR_ENV] = str(directory)

    if os.environ.get("PYTEST_XDIST_WORKER") is None:
        stale = list(directory.glob("cov-*.jsonl"))
        for path in stale:
            path.unlink(missing_ok=True)
        if stale:
            logger.debug("📋 purged %d stale coverage file(s) from %s",
                         len(stale), directory)


@pytest.fixture(scope="session", autouse=True)
def _coverage_dir():
    """The run-shared coverage directory, already prepared by `pytest_configure`."""
    return _resolve_coverage_dir()


@pytest.fixture
def ledger(_coverage_dir) -> CoverageLedger:
    """A durable, cross-worker coverage ledger."""
    return CoverageLedger(directory=str(_coverage_dir))


# --------------------------------------------------------------------------- #
# Game fixtures — all real below the LLM
# --------------------------------------------------------------------------- #

@pytest.fixture
def engine():
    """A real GameEngine with one real Fighter."""
    from tests.integration.harness.game_builder import build_engine

    return build_engine()


@pytest.fixture
def party_engine():
    """A real GameEngine with a Fighter, a Radiant and a caster."""
    from tests.integration.harness.game_builder import (
        build_engine, caster_template, character_template, radiant_template,
    )

    return build_engine(characters=[
        character_template(), radiant_template(), caster_template(),
    ])


@pytest.fixture
def wrapper(engine):
    """A real DnDEngineWrapper — entities, positions, senses."""
    from tests.integration.harness.game_builder import build_wrapper

    return build_wrapper(engine)


@pytest.fixture
def check_invariants():
    """Assert the §6 invariants; call after each turn.

        check_invariants(engine.character_manager, context="turn 3")
    """
    def _check(character_manager=None, combat_state=None, player_text=None,
               context=""):
        invariants.assert_all(character_manager, combat_state, player_text, context)
    return _check


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #

def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print a coverage digest so a run's reach is visible without a separate tool."""
    try:
        entries = CoverageLedger.load_all(str(_resolve_coverage_dir()))
    except Exception:
        return
    if not entries:
        return
    counts: dict = {}
    for entry in entries:
        counts.setdefault(entry.get("kind", "?"), set()).add(entry.get("name"))
    terminalreporter.write_sep("-", "Suite A mechanic coverage")
    for kind in sorted(counts):
        terminalreporter.write_line(f"  {kind:9s} {len(counts[kind]):3d} distinct")

    problems = getattr(config, "_roshar_gate_violations", None)
    if problems:
        terminalreporter.write_sep("=", "COVERAGE GATE FAILED", red=True, bold=True)
        for problem in problems:
            terminalreporter.write_line(f"  ✗ {problem}")
    elif problems == []:
        # An empty list means the gates actually RAN and found nothing wrong. A
        # skipped gate leaves the attribute unset, and must not be reported as a
        # pass — claiming coverage was verified when it was not is the precise
        # dishonesty this suite exists to eliminate.
        terminalreporter.write_line("  ✓ coverage gates passed")
    else:
        terminalreporter.write_line(
            "  – coverage gates not evaluated (partial run; "
            "run `uv run pytest tests/integration/` for the full gate)")


# --------------------------------------------------------------------------- #
# The coverage gates — whole-run assertions, evaluated once
# --------------------------------------------------------------------------- #

def pytest_sessionfinish(session, exitstatus):
    """Evaluate the §7 coverage gates after EVERY worker has finished.

    These are inherently whole-run assertions, so they cannot be ordinary tests.
    Under `pytest -n 8` each worker is a separate PROCESS with no cross-worker
    ordering guarantee, so a gate running as a test lands on an arbitrary worker and
    reads a ledger the other seven are still writing. That produced a real false
    failure: the terminal summary showed all 28 actions recorded while the gate on
    `gw2` reported 24 of them "never exercised".

    Running here, on the CONTROLLER only, means the ledger is complete. A violation
    still fails the build — `session.exitstatus` is set to TESTS_FAILED — it simply
    fails once, for the right reason, with the whole picture.
    """
    import pytest as _pytest

    from tests.integration.harness import gates

    # Workers must not evaluate the gates: each sees only its own slice.
    try:
        from xdist.plugin import is_xdist_worker

        if is_xdist_worker(session):
            return
    except ImportError:
        pass

    # A partial run cannot satisfy whole-suite gates, so do not report a misleading
    # failure. Iterating on one scenario file must stay green.
    if not gates.have_any_observations():
        return
    if not _whole_suite_ran(session):
        logger.debug("📋 skipping coverage gates: not a whole-suite run")
        return

    # Do not pile a gate failure on top of already-failing tests; the real cause is
    # the test failure, and an unexercised mechanic is its symptom.
    if exitstatus not in (0, _pytest.ExitCode.OK):
        logger.debug("📋 skipping coverage gates: tests already failed")
        return

    violations = gates.run_all_gates()
    session.config._roshar_gate_violations = violations
    if violations:
        session.exitstatus = _pytest.ExitCode.TESTS_FAILED
        for problem in violations:
            logger.error("📋 coverage gate: %s", problem)


def _whole_suite_ran(session) -> bool:
    """True when this invocation targets the whole suite rather than a subset.

    The gates assert over the WHOLE suite, so they are only meaningful when the whole
    suite ran. Without this check, `pytest tests/integration/test_exploration_full.py`
    exits 1: 23 tests pass, then the gates correctly observe that no combat or Cosmere
    mechanic was recorded. Correct in the abstract, useless in practice — it makes
    per-file iteration look broken.

    DETECTION USES `config.args`, NOT `session.items`. Under xdist the CONTROLLER
    collects nothing (the workers do), so `session.items` is empty there and an
    items-based check reports "partial" for every parallel run — measured directly:
    `PROBE SKIP items=0 args=['tests/integration/']`. The invocation arguments are
    available on both controller and workers.

    The relationship to test is "is the target the suite directory, or an ANCESTOR of
    it" (`tests/integration/`, `tests/`) — NOT "is the target inside the suite". Those
    are opposites, and getting them backwards made a single scenario file count as a
    whole-suite run while `tests/` did not.

    A subset selected with `-k` or `-m` also counts as partial, since those cannot
    satisfy whole-suite gates either.
    """
    config = session.config
    if config.getoption("-k", default="") or config.getoption("-m", default=""):
        return False

    suite_root = Path(__file__).parent.resolve()
    args = [str(a).split("::", 1)[0] for a in getattr(config, "args", []) or []]
    if not args:
        return False

    for arg in args:
        resolved = Path(arg).resolve()
        is_suite_or_ancestor = (resolved == suite_root
                                or resolved in suite_root.parents)
        if not is_suite_or_ancestor:
            return False
    return True
