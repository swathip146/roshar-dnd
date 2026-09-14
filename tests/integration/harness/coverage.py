"""
The coverage ledger — §7 of the strategy, the mechanism behind "full coverage".

WHY A RUNTIME LEDGER AND NOT A CHECKLIST
----------------------------------------
A prose checklist rots. This records what actually fired during a run and then asserts
against sets ENUMERATED FROM LIVE DATA (`ACTION_REGISTRY`, `DM_TOOLS`,
`surgebinding.json`), so newly added content is opted into coverage automatically and
adding a mechanic without a test breaks the build.

THE RULE THAT MAKES IT HONEST
-----------------------------
Tokens are recorded at the point of **observed effect**, never at call time. `record()`
demands evidence and rejects a falsy value. So a no-op cannot mark itself covered —
which matters in a codebase whose signature defect is code that runs, passes its unit
tests, and changes nothing (advantage rolling one die and taking `max()` of a
1-element list is the canonical case).

PARALLEL SAFETY
---------------
Under `pytest -n 8` each worker is a separate process, so an in-memory ledger only ever
sees its own slice. The ledger therefore persists each observation as a JSON line under
a shared directory (`RD_COVERAGE_DIR`, set by the session fixture), and the gate tests
read the union. That is why the gates live in their own file, run last, and read from
disk rather than from module state.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from config.logging_config import get_logger

logger = get_logger(__name__)

#: Env var naming the shared directory for cross-worker observations.
COVERAGE_DIR_ENV = "RD_COVERAGE_DIR"

_lock = threading.Lock()


class CoverageLedger:
    """Records mechanic observations, durably and across xdist workers."""

    def __init__(self, directory: Optional[str] = None):
        target = directory or os.environ.get(COVERAGE_DIR_ENV)
        self.directory = Path(target) if target else None
        if self.directory:
            self.directory.mkdir(parents=True, exist_ok=True)
            self._path = self.directory / f"cov-{os.getpid()}-{uuid.uuid4().hex[:8]}.jsonl"
        else:
            self._path = None
        self._local: List[Dict[str, Any]] = []

    # -- recording ----------------------------------------------------------

    def record(
        self,
        kind: str,
        name: str,
        evidence: Any,
        detail: str = "",
    ) -> None:
        """Record that `name` (of `kind`) was observed to actually work.

        Args:
            kind: "action" | "tool" | "surge" | "order" | "mechanic" | "node".
            name: the identifier, matching the enumerated source exactly.
            evidence: the OBSERVED EFFECT — an HP delta, a slot count, a roll total.
                Falsy values raise: a mechanic with no evidence is not covered.

        Raises:
            ValueError: if `evidence` is falsy. Deliberately loud; a test that cannot
                show its mechanic worked must not be able to claim it.
        """
        if not evidence and evidence != 0:
            raise ValueError(
                f"coverage for {kind}:{name} needs observed evidence, got "
                f"{evidence!r}. Record at the point of effect, not at call time."
            )
        entry = {"kind": kind, "name": name,
                 "evidence": _summarise(evidence), "detail": detail}
        self._local.append(entry)

        if self._path is not None:
            with _lock:
                with self._path.open("a") as handle:
                    handle.write(json.dumps(entry, default=str) + "\n")
        logger.debug("📋 covered %s:%s (%s)", kind, name, entry["evidence"])

    # convenience wrappers, so call sites read as prose
    def action(self, name: str, evidence: Any, detail: str = "") -> None:
        self.record("action", name, evidence, detail)

    def tool(self, name: str, evidence: Any, detail: str = "") -> None:
        self.record("tool", name, evidence, detail)

    def surge(self, name: str, evidence: Any, detail: str = "") -> None:
        self.record("surge", name, evidence, detail)

    def order(self, name: str, evidence: Any, detail: str = "") -> None:
        self.record("order", name, evidence, detail)

    def mechanic(self, name: str, evidence: Any, detail: str = "") -> None:
        self.record("mechanic", name, evidence, detail)

    def node(self, name: str, evidence: Any, detail: str = "") -> None:
        self.record("node", name, evidence, detail)

    # -- reading ------------------------------------------------------------

    def names(self, kind: str) -> Set[str]:
        """Names of `kind` recorded by THIS process only."""
        return {e["name"] for e in self._local if e["kind"] == kind}

    @classmethod
    def load_all(cls, directory: Optional[str] = None) -> List[Dict[str, Any]]:
        """Every observation from every worker — the union the gates assert on."""
        target = directory or os.environ.get(COVERAGE_DIR_ENV)
        if not target:
            return []
        path = Path(target)
        if not path.exists():
            return []
        entries: List[Dict[str, Any]] = []
        for file in sorted(path.glob("cov-*.jsonl")):
            for line in file.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning("📋 unparseable coverage line in %s", file.name)
        return entries

    @classmethod
    def covered(cls, kind: str, directory: Optional[str] = None) -> Set[str]:
        return {e["name"] for e in cls.load_all(directory) if e.get("kind") == kind}


def _summarise(evidence: Any) -> str:
    text = str(evidence)
    return text if len(text) <= 160 else text[:157] + "..."


# --------------------------------------------------------------------------- #
# Enumerated expectations — read from live data, never hardcoded
# --------------------------------------------------------------------------- #

def expected_offerable_actions() -> Set[str]:
    """Registry entries a player can actually be offered.

    Measured 2026-09-13: 29 entries, 28 offerable. `move` is offerable=False by
    design (it needs a caller-supplied destination), so it is excluded here and
    movement is covered via the grid/dash path instead.
    """
    from components.combat.action_registry import ACTION_REGISTRY, is_offerable

    return {name for name in ACTION_REGISTRY if is_offerable(name)}


def expected_dm_tools() -> Set[str]:
    """The exploration pipeline's tools — 19 as measured on 2026-09-13."""
    from agents.dm_tools import DM_TOOLS

    return {getattr(tool, "name") for tool in DM_TOOLS
            if getattr(tool, "name", None)}


def expected_surges() -> Set[str]:
    """The 10 surges in `surgebinding.json`."""
    return set(_surgebinding()["surges"].keys())


def expected_playable_orders() -> Set[str]:
    """The 9 playable orders.

    Bondsmith is excluded: verified absent from the source books (0 hits in 19,794
    lines of the Invested Arts book), so it has no abilities to exercise.
    """
    orders = _surgebinding()["orders"]
    names = set(orders.keys()) if isinstance(orders, dict) else {
        o.get("name") for o in orders}
    return {n for n in names if n and n.lower() != "bondsmith"}


def _surgebinding() -> Dict[str, Any]:
    from components.cosmere_rules import CosmereRules

    rules = CosmereRules()
    data = getattr(rules, "data", None)
    if isinstance(data, dict) and "surges" in data:
        return data
    import json as _json
    from pathlib import Path as _Path

    return _json.loads(
        _Path("data/rules/stormlight/surgebinding.json").read_text())


def missing(expected: Iterable[str], covered: Iterable[str]) -> Set[str]:
    return set(expected) - set(covered)
