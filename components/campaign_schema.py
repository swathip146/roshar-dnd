"""
Campaign schema and endgame detection — plan 2.12/2.13, decision D2.

D2 splits authority three ways:
    authoring   offline (generators/campaign_generator.py)
    extending   the DM, at runtime (add quests/NPCs/locations)
    closing     AUTHORED, code-detected  <- this module

The LLM narrates the ending; it does not decide when the story is over. Same
principle as rules adjudication: a model that invents DCs nothing enforces
should not hold authority over whether your campaign has finished.

The gap this fills: data/current_campaign/shards_of_honor.json is all prose —
main_plot, hooks, rewards — with no endgame condition, no acts, and quests as
bare title strings. Detecting "the campaign is over" was impossible.

Conditions are declarative and evaluated against live GameEngine state:

    {"all_of": ["quest:veden_crisis:complete", "flag:ritual_stopped"]}
    {"any_of": ["npc:odium:defeated", "flag:barrier_sealed"]}
    {"count": {"predicate": "quest:artifact_*:complete", "at_least": 3}}
"""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.logging_config import get_logger

logger = get_logger(__name__)


class EndgameEvaluator:
    """Evaluates a declarative endgame condition against GameEngine state."""

    def __init__(self, game_engine, quest_index: Optional[Dict[str, str]] = None):
        self.game_engine = game_engine
        # id -> title. GameEngine's quest_context stores objective TITLES, but
        # endgame conditions are written against stable quest IDs, so a
        # predicate like "quest:artifact_1" has to be resolved to the title
        # before it can match. Without this every quest predicate was False and
        # the endgame could never fire.
        self.quest_index = {k.lower(): v.lower()
                            for k, v in (quest_index or {}).items()}

    # ---------------------------------------------------------------- helpers

    def _completed_quests(self) -> List[str]:
        try:
            progress = self.game_engine.get_quest_progress()
            return [q.lower() for q in progress.get("completed", [])]
        except Exception:
            return []

    def _flags(self) -> Dict[str, Any]:
        try:
            return self.game_engine.game_state.campaign_flags or {}
        except Exception:
            return {}

    def _visited_locations(self) -> List[str]:
        try:
            graph = self.game_engine.game_state.location_context.get(
                "known_locations", {}
            ) or {}
            return [name.lower() for name, node in graph.items()
                    if node.get("visited")]
        except Exception:
            return []

    # -------------------------------------------------------------- predicates

    def check_predicate(self, predicate: str) -> bool:
        """
        Evaluate one `kind:target[:state]` predicate.

        Supported kinds:
            quest:<name>[:complete]   the objective is completed
            flag:<name>               a campaign flag is truthy
            location:<name>[:visited]  the party has been there
            ideal:<n>                 any character has reached Ideal >= n
        Wildcards (`artifact_*`) are allowed in the target.
        """
        parts = (predicate or "").split(":")
        if len(parts) < 2:
            logger.debug(f"   Malformed predicate: {predicate!r}")
            return False

        kind, target = parts[0].strip().lower(), parts[1].strip().lower()

        if kind == "quest":
            completed = self._completed_quests()
            candidates = {target}
            # Resolve id -> title, honouring wildcards in the id.
            for quest_id, title in self.quest_index.items():
                if fnmatch.fnmatch(quest_id, target) or quest_id == target:
                    candidates.add(title)
            return any(
                fnmatch.fnmatch(done, cand) or cand in done
                for done in completed for cand in candidates
            )

        if kind == "flag":
            flags = {str(k).lower(): v for k, v in self._flags().items()}
            for key, value in flags.items():
                if fnmatch.fnmatch(key, target) and value:
                    return True
            return False

        if kind == "location":
            return any(fnmatch.fnmatch(loc, target) or target in loc
                       for loc in self._visited_locations())

        if kind == "ideal":
            try:
                needed = int(target)
            except ValueError:
                return False
            characters = getattr(self.game_engine, "character_manager", None)
            if characters is None:
                return False
            return any((getattr(c, "ideal_level", 0) or 0) >= needed
                       for c in characters.characters.values())

        logger.debug(f"   Unknown predicate kind: {kind!r}")
        return False

    # --------------------------------------------------------------- evaluate

    def evaluate(self, condition: Any) -> bool:
        """Evaluate a condition tree. Unknown shapes return False, never raise."""
        if condition is None:
            return False
        if isinstance(condition, bool):
            return condition
        if isinstance(condition, str):
            return self.check_predicate(condition)

        if isinstance(condition, list):
            # A bare list means all_of
            return all(self.evaluate(c) for c in condition)

        if isinstance(condition, dict):
            if "all_of" in condition:
                return all(self.evaluate(c) for c in condition["all_of"])
            if "any_of" in condition:
                return any(self.evaluate(c) for c in condition["any_of"])
            if "none_of" in condition:
                return not any(self.evaluate(c) for c in condition["none_of"])
            if "count" in condition:
                spec = condition["count"] or {}
                predicate = spec.get("predicate", "")
                at_least = int(spec.get("at_least", 1))
                # Expand the wildcard against whatever the predicate targets
                kind = predicate.split(":")[0] if ":" in predicate else ""
                pattern = predicate.split(":")[1] if ":" in predicate else ""
                if kind in ("", "quest") or not kind:
                    # A bare pattern like "artifact_*" counts matching quest IDs
                    # that are complete.
                    pattern = pattern or predicate
                    matched_ids = [qid for qid in self.quest_index
                                   if fnmatch.fnmatch(qid, pattern)]
                    done = 0
                    for qid in matched_ids:
                        if self.check_predicate(f"quest:{qid}"):
                            done += 1
                    return done >= at_least
                pool = {"location": self._visited_locations}.get(kind, list)
                matches = [x for x in pool() if fnmatch.fnmatch(x, pattern)]
                return len(matches) >= at_least

        logger.debug(f"   Unevaluatable condition: {condition!r}")
        return False

    def progress(self, condition: Any) -> Dict[str, Any]:
        """
        Which parts of the condition are satisfied — for a progress display and
        for telling the DM how close the ending is.
        """
        satisfied, outstanding = [], []

        def walk(node):
            if isinstance(node, str):
                (satisfied if self.check_predicate(node) else outstanding).append(node)
            elif isinstance(node, list):
                for item in node:
                    walk(item)
            elif isinstance(node, dict):
                for key in ("all_of", "any_of", "none_of"):
                    for item in node.get(key, []) or []:
                        walk(item)
                if "count" in node:
                    label = f"{node['count'].get('predicate')} x{node['count'].get('at_least')}"
                    (satisfied if self.evaluate(node) else outstanding).append(label)

        walk(condition)
        total = len(satisfied) + len(outstanding)
        return {
            "satisfied": satisfied,
            "outstanding": outstanding,
            "complete": self.evaluate(condition),
            "percent": round(100 * len(satisfied) / total) if total else 0,
        }


class CampaignSchema:
    """
    Loads a structured campaign and reports whether it has ended (2.12/2.13).

    Tolerates the old prose-only format: `has_structure()` reports whether the
    campaign has been migrated, so the DM can degrade gracefully instead of
    pretending an endgame exists.
    """

    def __init__(self, campaign_path: Path, game_engine=None):
        self.path = Path(campaign_path)
        self.game_engine = game_engine
        self.data: Dict[str, Any] = {}
        self.load()

    def load(self) -> bool:
        if not self.path.exists():
            logger.warning(f"⚠️ Campaign not found: {self.path}")
            return False
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
            structured = "yes" if self.has_structure() else "NO (prose only)"
            logger.info(
                f"🗺️  Loaded campaign '{self.data.get('title', '?')}' "
                f"(structured: {structured}, "
                f"{len(self.quests())} quests, {len(self.acts())} acts)"
            )
            return True
        except Exception as e:
            logger.error(f"❌ Could not parse campaign {self.path.name}: {e}")
            return False

    # ----------------------------------------------------------------- access

    def has_structure(self) -> bool:
        """Whether this campaign has a machine-readable endgame and quests."""
        return bool(self.data.get("endgame")) and bool(self.data.get("quests"))

    def quests(self) -> List[Dict[str, Any]]:
        """Quest objects (id, title, objectives, prereqs, status)."""
        raw = self.data.get("quests", []) or []
        out = []
        for item in raw:
            if isinstance(item, dict):
                out.append(item)
            else:
                # Legacy: a bare title string
                out.append({"id": str(item).lower().replace(" ", "_"),
                            "title": str(item), "objectives": [],
                            "prereqs": [], "status": "pending"})
        return out

    def acts(self) -> List[Dict[str, Any]]:
        return self.data.get("acts", []) or []

    def quest(self, quest_id: str) -> Optional[Dict[str, Any]]:
        needle = (quest_id or "").strip().lower()
        for q in self.quests():
            if q.get("id", "").lower() == needle or q.get("title", "").lower() == needle:
                return q
        return None

    def available_quests(self) -> List[Dict[str, Any]]:
        """Quests whose prerequisites are met (2.12)."""
        if self.game_engine is None:
            return self.quests()
        evaluator = self._evaluator()
        return [q for q in self.quests()
                if q.get("status") != "complete"
                and all(evaluator.check_predicate(p) for p in (q.get("prereqs") or []))]

    # ---------------------------------------------------------------- endgame

    def _evaluator(self) -> "EndgameEvaluator":
        """An evaluator that knows this campaign's quest id -> title map."""
        return EndgameEvaluator(
            self.game_engine,
            quest_index={q.get("id", ""): q.get("title", "") for q in self.quests()},
        )

    def endgame_condition(self) -> Any:
        return (self.data.get("endgame") or {}).get("condition")

    def is_complete(self) -> bool:
        """
        Whether the campaign's authored ending condition is satisfied (2.13).

        The LLM narrates the ending; this decides IF there is one.
        """
        if self.game_engine is None or not self.data.get("endgame"):
            return False
        return self._evaluator().evaluate(self.endgame_condition())

    def endgame_progress(self) -> Dict[str, Any]:
        """How close the party is to the authored ending."""
        if self.game_engine is None or not self.data.get("endgame"):
            return {"satisfied": [], "outstanding": [], "complete": False,
                    "percent": 0, "structured": False}
        result = self._evaluator().progress(self.endgame_condition())
        result["structured"] = True
        return result

    def closing_narration(self) -> str:
        """The authored closing beat, handed to the DM to narrate (D2)."""
        return (self.data.get("endgame") or {}).get("closing_narration", "")
