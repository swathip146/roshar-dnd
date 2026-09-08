"""
Rules judge — plan 3.6/3.7/3.8, decision D5.

Tier 3 of the adjudication ladder. When no canonical rule covers what a player
attempts, this rules on it — but as a *grounded* judge, not a free improviser.

Three properties make the model's discretion trustworthy, none of which the
current system has:

  grounded    it must RETRIEVE the Handbook/SRD and cite the chunks it relied
              on. A ruling with no citation is downgraded to narrative-only.
              This is why 0.17 (index the Handbook) and 0.2 (make retrieval
              reach the prompt) are prerequisites.

  consistent  before judging, it searches prior rulings for the same situation
              and MUST follow one if it exists. Precedent binds. This is what
              stops the classic failure: the same action costing 1 Stormlight
              today and 3 tomorrow.

  legible     every ruling is recorded with its tier, so the player sees a
              "House ruling" marker and you can review before promotion.

The payoff (D5): rulings are a QUEUE, not a dead log. A ruling that recurs is a
rule worth writing into data/rules/stormlight/ — so the ruleset grows by play.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.logging_config import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RULINGS_PATH = PROJECT_ROOT / "data" / "rules" / "rulings.json"

# Tiers, mirroring components/rules_gap_tracker.py
TIER_CANONICAL = 1
TIER_COMPOSED = 2
TIER_JUDGED = 3
TIER_NARRATIVE = 4

# The structured shape the judge must emit. Code applies the mechanics; the model
# never gets to hand back prose and have it treated as a rule.
RULING_SCHEMA = {
    "type": "object",
    "properties": {
        "legal": {"type": "boolean",
                  "description": "Whether the attempt is permitted by the rules"},
        "reason": {"type": "string",
                   "description": "Why, referencing the retrieved rules text"},
        "cost": {"type": "object",
                 "description": "Resources spent, e.g. {\"stormlight\": 1}"},
        "resolution": {
            "type": "object",
            "description": "How to resolve it mechanically",
            "properties": {
                "type": {"type": "string",
                         "description": "check | attack | save | none"},
                "skill": {"type": "string"},
                "dc": {"type": "integer"},
                "damage": {"type": "string",
                           "description": "Dice expression, e.g. 2d6[bludgeoning]"},
            },
        },
        "cites": {"type": "array", "items": {"type": "string"},
                  "description": "Sources relied on. REQUIRED for a valid ruling."},
        "confidence": {"type": "string",
                       "description": "high | medium | low"},
    },
    "required": ["legal", "reason", "cites"],
}

JUDGE_SYSTEM_PROMPT = """\
You are the RULES JUDGE for a Cosmere 5e campaign. You do not narrate. You rule.

You are given: the player's attempted action, retrieved rules text, and any
binding precedent. Produce a structured ruling.

HARD CONSTRAINTS:

1. RULE FROM THE RETRIEVED TEXT, NOT FROM MEMORY. Your own recollection of
   Cosmere or D&D rules may contradict THIS campaign's Handbook. Use only what
   the retrieved passages actually say.

2. CITE WHAT YOU USED. Every ruling must list the sources in `cites`. A ruling
   with no citations is discarded and the action becomes flavour only. If the
   retrieved text does not cover the attempt, say so in `reason` and cite
   nothing rather than inventing support.

3. PRECEDENT BINDS. If a prior ruling for this situation is supplied, follow it
   exactly — same cost, same DC, same resolution. Consistency matters more than
   your preferred reading. Note that you are following precedent in `reason`.

4. YOU MAY SAY NO. `legal: false` is a valid and expected outcome. But a refusal
   must cite a rule too, exactly like an approval.

5. BE CONSERVATIVE WITH COSTS. Prefer the cheapest reading the text supports.
   Set `confidence` honestly: "low" when the text barely covers it.

Return ONLY the structured ruling.
"""


class RulingStore:
    """Persistent ruling log with precedent lookup (plan 3.7)."""

    def __init__(self, path: Path = RULINGS_PATH):
        self.path = Path(path)
        self._rulings: Dict[str, Dict[str, Any]] = {}
        self.load()

    # ------------------------------------------------------------- persistence

    def load(self) -> int:
        if not self.path.exists():
            return 0
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            self._rulings = payload.get("rulings", {})
            return len(self._rulings)
        except Exception as e:
            logger.warning(f"⚠️ Could not read ruling store: {e}")
            self._rulings = {}
            return 0

    def save(self) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps({"rulings": self._rulings}, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return True
        except Exception as e:
            logger.warning(f"⚠️ Could not write ruling store: {e}")
            return False

    # ---------------------------------------------------------------- indexing

    @staticmethod
    def _key(situation: str) -> str:
        """
        Normalise a situation so paraphrases collide.

        Drops filler words so "I lash the boulder onto the Fused" and "lash a
        boulder at that Fused" resolve to the same precedent.
        """
        stop = {"i", "a", "an", "the", "at", "on", "onto", "to", "with", "my",
                "that", "this", "then", "and", "of", "it", "him", "her", "them"}
        words = re.findall(r"[a-z0-9']+", (situation or "").lower())
        return " ".join(w for w in words if w not in stop)[:120]

    def find_precedent(self, situation: str) -> Optional[Dict[str, Any]]:
        """
        A binding prior ruling for this situation, if any (plan 3.7).

        Exact normalised match first, then a strong keyword overlap, so a
        rephrasing still finds it.
        """
        key = self._key(situation)
        if not key:
            return None

        exact = self._rulings.get(key)
        if exact:
            return exact

        words = set(key.split())
        if len(words) < 2:
            return None
        best, best_score = None, 0.0
        for stored_key, ruling in self._rulings.items():
            stored_words = set(stored_key.split())
            if not stored_words:
                continue
            overlap = len(words & stored_words) / max(len(words), len(stored_words))
            if overlap > best_score:
                best, best_score = ruling, overlap
        # 0.6 is deliberately strict: a loose match would bind the judge to a
        # precedent about something else, which is worse than no precedent.
        return best if best_score >= 0.6 else None

    def record(self, situation: str, ruling: Dict[str, Any]) -> Dict[str, Any]:
        """Store a ruling, incrementing its use counter."""
        key = self._key(situation)
        if not key:
            return {}
        entry = self._rulings.setdefault(key, {
            "situation": situation,
            "ruling": ruling,
            "uses": 0,
            "first_ruled": time.time(),
            "promoted": False,
        })
        entry["uses"] += 1
        entry["last_used"] = time.time()
        # Keep the first ruling as the binding one; later identical calls just
        # bump the counter. Changing it would break the consistency guarantee.
        self.save()
        return entry

    def promotion_candidates(self, min_uses: int = 3) -> List[Dict[str, Any]]:
        """
        Rulings used often enough to be worth writing into the canonical
        ruleset, most-used first (plan D5's promotion path).
        """
        items = [
            {"key": k, **v} for k, v in self._rulings.items()
            if v.get("uses", 0) >= min_uses and not v.get("promoted")
        ]
        return sorted(items, key=lambda e: -e["uses"])

    def mark_promoted(self, situation: str) -> bool:
        entry = self._rulings.get(self._key(situation))
        if entry is None:
            return False
        entry["promoted"] = True
        entry["promoted_at"] = time.time()
        self.save()
        return True

    def all_rulings(self) -> List[Dict[str, Any]]:
        return [{"key": k, **v} for k, v in self._rulings.items()]


class RulesJudge:
    """
    Adjudicates what canonical rules do not cover (plan 3.6).

    Requires a chat generator that supports structured output. Without one it
    degrades to narrative-only rather than guessing — an ungrounded ruling is
    worse than admitting there is no rule.
    """

    def __init__(self, chat_generator=None, srd_rules=None, cosmere_rules=None,
                 gap_tracker=None, store: Optional[RulingStore] = None,
                 retriever=None, embedder=None):
        self.generator = chat_generator
        self.srd = srd_rules
        self.cosmere = cosmere_rules
        self.gap_tracker = gap_tracker
        self.store = store or RulingStore()
        self.retriever = retriever
        self.embedder = embedder

    # ---------------------------------------------------------------- grounding

    def retrieve_rules_text(self, situation: str, top_k: int = 4) -> List[Dict[str, str]]:
        """
        Retrieve rules passages for the judge to reason from (plan 3.6).

        The judge is NOT allowed to rule from memory, so if this returns nothing
        the ruling is downgraded to narrative.
        """
        passages: List[Dict[str, str]] = []

        # Canonical hits first — if a real rule exists this should not be Tier 3.
        #
        # Match KNOWN RULE NAMES against the situation rather than extracting
        # candidate terms from it: a regex over the sentence grabbed
        # "Full Lashing the Fused" as one token, so nothing ever matched and the
        # judge was left ungrounded on every call.
        lowered = (situation or "").lower()

        if self.cosmere is not None:
            for maneuver in self.cosmere.maneuvers():
                name = maneuver.get("name", "")
                if name and name.lower() in lowered:
                    passages.append({
                        "source": f"Radiant's Handbook / {name}",
                        "text": maneuver.get("quote", json.dumps(maneuver)),
                    })
            for order_name in ("Windrunner", "Skybreaker", "Dustbringer",
                               "Edgedancer", "Truthwatcher", "Lightweaver",
                               "Elsecaller", "Willshaper", "Stoneward"):
                if order_name.lower() in lowered:
                    order = self.cosmere.order(order_name)
                    if order:
                        passages.append({
                            "source": f"Radiant's Handbook / {order_name}",
                            "text": json.dumps(order)[:500],
                        })
            # The resource economies are what most cost questions turn on.
            for surge_word in ("stormlight", "lashing", "investiture", "soulcast"):
                if surge_word in lowered:
                    economies = self.cosmere._data.get("economies", {})
                    for economy in economies.values():
                        passages.append({
                            "source": f"Radiant's Handbook / {economy.get('name')}",
                            "text": economy.get("quote", json.dumps(economy))[:500],
                        })
                    break

        if self.srd is not None:
            for dataset, lookup in (("condition", self.srd.condition),
                                    ("equipment", self.srd.equipment)):
                for entry in self.srd._data.get(f"{dataset}s", []):
                    name = entry.get("name", "")
                    if name and len(name) > 3 and name.lower() in lowered:
                        passages.append({
                            "source": f"SRD 5e / {dataset} / {name}",
                            "text": str(entry.get("desc") or entry)[:500],
                        })

        # Then the indexed Handbook, for anything the structured data misses.
        if self.retriever is not None and self.embedder is not None:
            try:
                embedding = self.embedder.run(text=situation)["embedding"]
                docs = self.retriever.run(query_embedding=embedding,
                                          top_k=top_k)["documents"]
                for doc in docs:
                    meta = doc.meta or {}
                    if meta.get("document_tag") != "rules":
                        continue  # lore must never ground a mechanic
                    passages.append({
                        "source": f"{meta.get('source_file', '?')}",
                        "text": (doc.content or "")[:700],
                    })
            except Exception as e:
                logger.warning(f"⚠️ Judge retrieval failed: {e}")

        return passages[:6]

    # ------------------------------------------------------------------- ruling

    def judge(self, situation: str, actor: str = "") -> Dict[str, Any]:
        """
        Rule on an attempted action.

        Returns a ruling dict with `tier` set to what actually resolved it:
            3 judged     grounded, cited, applied
            4 narrative  no grounding or no citation -> flavour only
        """
        # 1. Precedent binds (plan 3.7)
        precedent = self.store.find_precedent(situation)
        if precedent is not None:
            entry = self.store.record(situation, precedent["ruling"])
            logger.info(f"⚖️  Following precedent for '{situation[:50]}' "
                        f"(used {entry['uses']}x)")
            if self.gap_tracker is not None:
                self.gap_tracker.record(situation, TIER_JUDGED,
                                        ruling=precedent["ruling"].get("reason"),
                                        citations=precedent["ruling"].get("cites"),
                                        actor=actor)
            return {**precedent["ruling"], "tier": TIER_JUDGED,
                    "followed_precedent": True}

        # 2. Ground it
        passages = self.retrieve_rules_text(situation)
        if not passages:
            return self._narrative_only(
                situation, actor,
                "no rules text could be retrieved for this attempt")

        if self.generator is None:
            return self._narrative_only(
                situation, actor, "no rules-judge generator configured")

        # 3. Ask for a structured ruling
        try:
            from haystack.dataclasses import ChatMessage

            evidence = "\n\n".join(
                f"[{p['source']}]\n{p['text']}" for p in passages
            )
            user = (
                f"PLAYER ATTEMPTS: {situation}\n\n"
                f"RETRIEVED RULES TEXT:\n{evidence}\n\n"
                f"Rule on this. Cite the sources above that you actually used."
            )
            reply = self.generator.run(messages=[
                ChatMessage.from_system(JUDGE_SYSTEM_PROMPT),
                ChatMessage.from_user(user),
            ])
            text = reply["replies"][0].text
            ruling = json.loads(re.sub(r"^```(?:json)?|```$", "", text.strip(),
                                       flags=re.MULTILINE).strip())
        except Exception as e:
            logger.warning(f"⚠️ Rules judge failed: {e}")
            return self._narrative_only(situation, actor, f"judge error: {e}")

        # 4. No citation, no ruling (plan 3.6/D5)
        cites = ruling.get("cites") or []
        if not cites:
            logger.warning(f"⚠️ Judge returned no citations for "
                           f"'{situation[:50]}' — downgrading to narrative")
            return self._narrative_only(
                situation, actor, "ruling had no citations")

        ruling["tier"] = TIER_JUDGED
        ruling["followed_precedent"] = False
        entry = self.store.record(situation, ruling)
        if self.gap_tracker is not None:
            self.gap_tracker.record(situation, TIER_JUDGED,
                                    ruling=ruling.get("reason"),
                                    citations=cites, actor=actor)
        logger.info(
            f"⚖️  Ruled '{situation[:50]}': legal={ruling.get('legal')} "
            f"({len(cites)} citation(s), seen {entry['uses']}x)"
        )
        return ruling

    def _narrative_only(self, situation: str, actor: str,
                        why: str) -> Dict[str, Any]:
        """Degrade to flavour, visibly (plan 3.8)."""
        if self.gap_tracker is not None:
            self.gap_tracker.record(situation, TIER_NARRATIVE, actor=actor)
        logger.info(f"📖 Narrative-only for '{situation[:50]}': {why}")
        return {
            "legal": True,
            "reason": f"No mechanical resolution ({why}).",
            "cost": {},
            "resolution": {"type": "none"},
            "cites": [],
            "confidence": "low",
            "tier": TIER_NARRATIVE,
            "followed_precedent": False,
        }


def describe_tier(tier: int) -> str:
    """
    The marker the player sees (plan 3.8).

    Improvisation must stay legible: you should always be able to tell whether a
    result came from the Handbook, from composed primitives, or from the model
    making something up.
    """
    return {
        TIER_CANONICAL: "",
        TIER_COMPOSED: "",
        TIER_JUDGED: "House ruling",
        TIER_NARRATIVE: "No mechanical effect",
    }.get(tier, "House ruling")
