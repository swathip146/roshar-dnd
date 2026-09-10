"""
The campaign bible — persistent context injected into every DM prompt (plan 0.19).

The problem it solves: RAG only surfaces what you think to query. The scenario
prompt had sections for narrative, location, quests, policy and RAG — and NOTHING
about the campaign itself. The DM never saw who the party were, which NPCs
mattered, what the acts were, or where the story was going, so it improvised
those every turn and the campaign had no spine.

Plan 0.19 called for "a hand-authored ~2-3k-token markdown file". This DERIVES it
from the structured campaign instead, for one reason: a hand-authored file is a
second source of truth that drifts. `shards_of_honor.json` already carries the
title, setting, acts, quests, NPCs, locations and endgame (schema 2.1, D2), and
the party lives in CharacterManager. Deriving keeps the bible correct by
construction — when a quest completes or a character levels, the bible follows.

An optional `data/current_campaign/bible.md` is still honoured and appended, so
anything the author wants to say that the schema cannot express has a home.

Bounded on purpose: this goes into EVERY prompt, so it is capped and the cap is
tested. An unbounded bible would quietly consume the scenario agent's budget and
truncate the scene it was meant to inform.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from config.logging_config import get_logger

logger = get_logger(__name__)

# ~2-3k tokens, per plan 0.19. Characters, because that is what we can measure
# cheaply and deterministically; roughly 4 chars per token.
MAX_BIBLE_CHARS = 9000

OPTIONAL_BIBLE_PATH = Path("data/current_campaign/bible.md")


class CampaignBible:
    """
    Assembles the persistent campaign context for the DM prompt.

    Cached: the campaign schema is immutable (CampaignConfig, per CLAUDE.md), so
    the static half is built once. The dynamic half — party HP, active quests,
    current location — is refreshed on every call, because a bible that reports
    yesterday's HP is worse than none.
    """

    def __init__(self, campaign: Optional[Dict[str, Any]] = None,
                 character_manager=None, game_engine=None):
        self.campaign = campaign or {}
        self.character_manager = character_manager
        self.game_engine = game_engine
        self._static_cache: Optional[str] = None

    # ------------------------------------------------------------------ public

    def render(self) -> str:
        """The full bible: static campaign spine + live party/progress state."""
        sections = [self._static(), self._dynamic()]
        text = "\n\n".join(s for s in sections if s).strip()

        if len(text) > MAX_BIBLE_CHARS:
            # Truncate the STATIC half, never the live state: stale HP or a
            # missing active quest causes contradictions the player will notice,
            # whereas a trimmed act summary merely costs some colour.
            logger.debug(f"📖 Campaign bible trimmed from {len(text)} chars")
            text = text[:MAX_BIBLE_CHARS].rstrip() + "\n…[bible truncated]"
        return text

    # ------------------------------------------------------------------ static

    def _static(self) -> str:
        if self._static_cache is not None:
            return self._static_cache

        campaign = self.campaign
        lines: List[str] = ["=== CAMPAIGN BIBLE (authoritative; do not contradict) ==="]

        title = campaign.get("title")
        if title:
            lines.append(f"Campaign: {title}")
        for key, label in (("setting", "Setting"), ("theme", "Theme"),
                           ("level_range", "Levels")):
            value = campaign.get(key)
            if value:
                lines.append(f"{label}: {value}")

        overview = campaign.get("overview") or campaign.get("main_plot")
        if overview:
            lines.append(f"\nPremise: {_clip(overview, 700)}")

        acts = campaign.get("acts") or []
        if acts:
            lines.append("\nStructure:")
            for act in acts[:5]:
                if isinstance(act, dict):
                    name = act.get("title") or act.get("name") or act.get("id", "Act")
                    summary = _clip(act.get("description") or act.get("summary") or "", 220)
                    lines.append(f"  - {name}: {summary}" if summary else f"  - {name}")
                else:
                    lines.append(f"  - {act}")

        npcs = campaign.get("key_npcs") or campaign.get("npcs") or []
        if npcs:
            lines.append("\nKey NPCs (use these, do not invent replacements):")
            for npc in npcs[:8]:
                if isinstance(npc, dict):
                    name = npc.get("name", "Unnamed")
                    role = npc.get("role") or npc.get("occupation") or ""
                    note = _clip(npc.get("description") or npc.get("personality") or "", 140)
                    lines.append(f"  - {name}"
                                 + (f" ({role})" if role else "")
                                 + (f": {note}" if note else ""))
                else:
                    lines.append(f"  - {npc}")

        locations = campaign.get("locations") or []
        if locations:
            names = [loc.get("name", "?") if isinstance(loc, dict) else str(loc)
                     for loc in locations[:10]]
            lines.append(f"\nEstablished locations: {', '.join(names)}")

        endgame = campaign.get("endgame")
        if isinstance(endgame, dict):
            condition = (endgame.get("description")
                         or endgame.get("condition") or "")
            if condition:
                lines.append(f"\nHow the campaign ENDS: {_clip(condition, 300)}")

        self._static_cache = "\n".join(lines)
        return self._static_cache

    # ----------------------------------------------------------------- dynamic

    def _dynamic(self) -> str:
        """Live state: who the party are, where they are, what is open."""
        lines: List[str] = ["=== CURRENT STATE (live; authoritative) ==="]

        party = self._party_lines()
        if party:
            lines.append("Party:")
            lines.extend(f"  - {line}" for line in party)

        engine = self.game_engine
        if engine is not None:
            location = self._safe(
                lambda: engine.game_state.location_context.get("current_location"))
            if location:
                lines.append(f"Location: {location}")

            time = self._safe(lambda: engine.get_game_time())
            if isinstance(time, dict) and time.get("day"):
                lines.append(
                    f"Time: day {time['day']}, {time.get('part_of_day', '')}"
                    f" (highstorm in {time.get('days_until_highstorm', '?')} days)")

            objectives = self._safe(
                lambda: engine.game_state.quest_context.get("pending_objectives"))
            if objectives:
                lines.append("Open objectives:")
                for objective in objectives[:6]:
                    text = (objective.get("text") if isinstance(objective, dict)
                            else str(objective))
                    if text:
                        lines.append(f"  - {text}")

            done = self._safe(
                lambda: engine.game_state.quest_context.get("completed_objectives"))
            if done:
                lines.append(f"Completed objectives: {len(done)}")

        return "\n".join(lines) if len(lines) > 1 else ""

    def _party_lines(self) -> List[str]:
        manager = self.character_manager
        if manager is None:
            return []
        try:
            npcs = set(manager.get_npcs() or [])
        except Exception:
            npcs = set()

        lines = []
        for char_id, character in getattr(manager, "characters", {}).items():
            if char_id in npcs:
                continue
            hp = character.hit_points if isinstance(character.hit_points, dict) else {}
            status = ""
            if getattr(character, "is_dead", False) is True:
                status = " — DEAD"
            elif hp.get("current", 1) <= 0:
                status = " — DYING"
            order = getattr(character, "radiant_order", None)
            ideal = getattr(character, "ideal_level", 0)
            lines.append(
                f"{character.name}: level {character.level} "
                f"{character.character_class}"
                + (f" ({order}, Ideal {ideal})" if order else "")
                + f", HP {hp.get('current', '?')}/{hp.get('maximum', '?')}"
                + status)
        return lines

    @staticmethod
    def _safe(getter):
        try:
            return getter()
        except Exception:
            return None


def _clip(text: Any, limit: int) -> str:
    text = str(text or "").strip().replace("\n", " ")
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def build_campaign_bible(campaign: Optional[Dict[str, Any]] = None,
                         character_manager=None, game_engine=None) -> str:
    """
    Render the campaign bible for injection into a DM prompt (plan 0.19).

    Returns "" rather than raising if nothing is available — a missing bible must
    degrade the prompt, never break the turn.
    """
    try:
        text = CampaignBible(campaign, character_manager, game_engine).render()
        extra = _optional_author_notes()
        if extra:
            text = f"{text}\n\n=== AUTHOR NOTES ===\n{extra}"
        return text
    except Exception as e:
        logger.warning(f"⚠️ Could not build the campaign bible: {e}")
        return ""


def _optional_author_notes() -> str:
    """Hand-written additions the schema cannot express (optional file)."""
    try:
        if OPTIONAL_BIBLE_PATH.exists():
            return _clip(OPTIONAL_BIBLE_PATH.read_text(encoding="utf-8"), 2000)
    except Exception as e:
        logger.debug(f"   No author notes: {e}")
    return ""
