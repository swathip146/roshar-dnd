"""
DM tools — plan 3.1. The LLM narrates; code adjudicates.

This is the highest-leverage change for quality in the whole plan. Before it,
the model emitted a `suggested_dc` that nothing enforced, invented Stormlight
costs, and described mechanics it had no way to resolve. Now it calls tools that
return real results computed from real state, and narrates what came back.

The split, stated plainly:
    the model decides WHAT is attempted    -> selects a tool, supplies arguments
    the code decides WHAT HAPPENS          -> rolls, checks, mutates state

Tools are thin: each one delegates to the component that already owns the
domain (GameEngine, CharacterManager, SRDRules, CosmereRules) rather than
re-implementing anything. Every tool returns a dict, never prose, so the model
cannot mistake a mechanical result for narration it may freely rewrite.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from haystack.tools import tool

from config.logging_config import get_logger

logger = get_logger(__name__)


# The tools need access to live game components. Haystack tools are plain
# functions, so the wiring goes through a module-level registry set once at
# orchestrator startup rather than through closures.
_CONTEXT: Dict[str, Any] = {}


def set_dm_tool_context(*, game_engine=None, character_manager=None,
                        dnd_engine_wrapper=None, srd_rules=None,
                        cosmere_rules=None, gap_tracker=None,
                        rules_judge=None) -> None:
    """Wire the live components the tools adjudicate against (plan 3.1)."""
    _CONTEXT.update({
        k: v for k, v in {
            "game_engine": game_engine,
            "character_manager": character_manager,
            "dnd_engine_wrapper": dnd_engine_wrapper,
            "srd_rules": srd_rules,
            "cosmere_rules": cosmere_rules,
            "gap_tracker": gap_tracker,
            "rules_judge": rules_judge,
        }.items() if v is not None
    })
    logger.info(f"🔧 DM tool context set: {sorted(_CONTEXT)}")


def clear_dm_tool_context() -> None:
    _CONTEXT.clear()
    # Clear the per-turn read state too. Clearing the cache but NOT the counters
    # left the stop-polling guard tripped: a fresh context would answer the very
    # first read with "you have already called this 2 times" and refuse the data.
    _READ_CACHE.clear()
    _READ_COUNTS.clear()


# Per-turn cache for READ-ONLY state tools.
#
# A live playtest turn called get_world_state 6 times and get_party_state 4
# times, exhausting max_agent_steps before the model ever wrote the scene — the
# player got a generic fallback instead. These tools are pure reads that return
# the same answer throughout a turn, so re-asking cannot teach the model
# anything; it only burns the step budget. The prompt now says "at most once per
# turn", but a prompt cannot enforce an invariant, so this makes a repeat call
# free rather than merely discouraged.
#
# Mutating tools (apply_damage, roll_skill_check, ...) are NEVER cached: their
# whole purpose is to change state or produce a fresh roll.
_READ_CACHE: Dict[str, Any] = {}


def begin_dm_tool_turn() -> None:
    """Drop the per-turn read cache and repeat counters. Called each turn."""
    _READ_CACHE.clear()
    _READ_COUNTS.clear()


def invalidate_dm_tool_reads() -> None:
    """
    Drop cached reads after a MUTATION.

    Without this the cache would be actively wrong, not merely stale: a model
    that calls apply_damage and then get_character_state must see the new HP, or
    it will narrate the character as unharmed.

    The repeat COUNTS are deliberately kept: state changing does not license the
    model to resume polling, and a mutation must not reset the loop-breaker.
    """
    _READ_CACHE.clear()


# How many times a read may return data before the tool starts answering with an
# instruction instead. One re-read is a reasonable double-check; beyond that the
# model is looping.
_MAX_READS_PER_TURN = 2

_READ_COUNTS: Dict[str, int] = {}


def _cached_read(key: str, compute):
    """
    Return a cached read, and BREAK THE LOOP if the model keeps re-asking.

    Caching alone was not enough. A live turn showed the model requesting
    get_world_state and get_party_state TOGETHER on every single step, ten steps
    running, until it hit max_agent_steps with no scene written — the player got
    "A mysterious pause settles over the scene." Making the repeats free (the
    first fix) only made it loop faster: 46 cache hits, still no scene.

    The model will not break out on its own, so the tool has to. After
    _MAX_READS_PER_TURN the payload is replaced by a directive telling it the
    data is unchanged and it must now narrate. That reaches the model as a tool
    RESULT, which is the one channel it is guaranteed to read.
    """
    _READ_COUNTS[key] = _READ_COUNTS.get(key, 0) + 1
    count = _READ_COUNTS[key]

    if count > _MAX_READS_PER_TURN:
        logger.warning(
            f"⚠️ {key} requested {count}× this turn — returning a "
            f"stop-polling directive instead of the payload"
        )
        return {
            "unchanged": True,
            "note": (
                f"You have already called this tool {count - 1} times this turn "
                f"and NOTHING HAS CHANGED. Calling it again cannot give you new "
                f"information. Stop gathering information and WRITE THE SCENE "
                f"NOW using what you already have. If you keep calling tools you "
                f"will run out of steps and the player will receive a generic "
                f"fallback instead of your scene."
            ),
        }

    if key not in _READ_CACHE:
        _READ_CACHE[key] = compute()
        return _READ_CACHE[key]
    logger.debug(f"🔧 {key}: served from this turn's cache (no step wasted)")
    return _READ_CACHE[key]


def _need(key: str):
    """Fetch a component, or raise a message the model can act on."""
    value = _CONTEXT.get(key)
    if value is None:
        raise RuntimeError(f"{key} is not available to DM tools")
    return value


def _active_actor(actor: str = "") -> str:
    """Resolve an actor id, defaulting to the first party member."""
    if actor:
        return actor
    manager = _CONTEXT.get("character_manager")
    if manager is None:
        return ""
    npcs = set()
    try:
        npcs = set(manager.get_npcs() or [])
    except Exception:
        pass
    for char_id in manager.characters:
        if char_id not in npcs:
            return char_id
    return next(iter(manager.characters), "")


# ---------------------------------------------------------------------------
# Dice and checks
# ---------------------------------------------------------------------------

@tool
def roll_skill_check(skill: str, dc: int, actor: str = "") -> Dict[str, Any]:
    """
    Roll an ability or skill check and return the real result.

    Use this instead of asserting whether an attempt succeeded. Never decide the
    outcome yourself — call this and narrate what it returns.

    Args:
        skill: The skill or ability, e.g. "stealth", "persuasion", "athletics"
        dc: Difficulty Class, 5 (trivial) to 25 (near-impossible)
        actor: Character id; defaults to the acting party member

    Returns:
        success, selected_roll, roll_total, dc, character_modifier
    """
    try:
        engine = _need("game_engine")
        actor_id = _active_actor(actor)
        result = engine.process_skill_check({
            "actor": actor_id,
            "skill": skill,
            "dc": int(dc),
            "context": {"source": "dm_tool"},
        })
        return {
            "actor": actor_id,
            "skill": skill,
            "dc": result.get("dc", dc),
            "selected_roll": result.get("selected_roll"),
            "roll_total": result.get("roll_total"),
            "character_modifier": result.get("character_modifier", 0),
            "success": bool(result.get("success")),
            "advantage_state": result.get("advantage_state", "normal"),
        }
    except Exception as e:
        logger.warning(f"⚠️ roll_skill_check failed: {e}")
        return {"error": str(e), "success": False}


@tool
def roll_dice(expression: str, reason: str = "") -> Dict[str, Any]:
    """
    Roll a dice expression and return the real total.

    Supports full standard notation (parsed by avrae/d20): "2d6", "1d8+3",
    "4d6kh3" (keep highest 3), "2d20kl1" (keep lowest), "1d8-1", exploding
    "4d6e6", reroll "4d6ro1"/"4d6rr1", min/max "4d6mi2"/"4d6ma5",
    parentheses "(1d6+2)*2", and damage-type annotations like "2d6[fire]".

    Malformed expressions are REJECTED with an error rather than returning 0 —
    if you get an error back, fix the notation and roll again.

    Args:
        expression: Dice expression to roll
        reason: What the roll is for (recorded in the log)

    Returns:
        total, rolls, breakdown
    """
    try:
        from components.dice import DiceRoller

        result = DiceRoller().damage_roll(expression)
        logger.info(f"🎲 {reason or 'roll'}: {result['breakdown']}")
        return {
            "expression": expression,
            "total": result["total_damage"],
            "rolls": result["damage_rolls"],
            "breakdown": result["breakdown"],
            "reason": reason,
        }
    except Exception as e:
        logger.warning(f"⚠️ roll_dice failed: {e}")
        return {"error": str(e), "total": 0}


# ---------------------------------------------------------------------------
# State inspection
# ---------------------------------------------------------------------------

@tool
def get_character_state(actor: str = "") -> Dict[str, Any]:
    """
    Read a character's real current state.

    Call this before describing anyone's condition — do not assume HP, Stormlight
    or Ideal from earlier narration, which may be stale.

    Args:
        actor: Character id; defaults to the acting party member

    Returns:
        name, level, hit_points, armor_class, conditions, stormlight, ideal_level
    """
    try:
        manager = _need("character_manager")
        actor_id = _active_actor(actor)
        character = manager.characters.get(actor_id)
        if character is None:
            return {"error": f"unknown character {actor_id!r}"}

        # Cached per turn: a pure read, so a repeat call costs no step.
        return _cached_read(f"character_state:{actor_id}", lambda: {
            "id": actor_id,
            "name": character.name,
            "level": character.level,
            "character_class": character.character_class,
            "radiant_order": getattr(character, "radiant_order", None),
            "hit_points": dict(character.hit_points or {}),
            "armor_class": character.armor_class,
            "conditions": list(character.conditions or []),
            "stormlight_current": getattr(character, "stormlight_current", 0),
            "stormlight_capacity": getattr(character, "stormlight_capacity", 0),
            "ideal_level": getattr(character, "ideal_level", 0),
            "experience_points": getattr(character, "experience_points", 0),
            "is_dying": (character.hit_points or {}).get("current", 1) <= 0,
            "is_dead": getattr(character, "is_dead", False),
        })
    except Exception as e:
        logger.warning(f"⚠️ get_character_state failed: {e}")
        return {"error": str(e)}


@tool
def get_party_state() -> Dict[str, Any]:
    """
    Read the whole party's state at once.

    Use this when the scene involves more than one character, so nobody is
    described as healthy when they are dying.

    Returns:
        members: a list of per-character summaries
    """
    try:
        manager = _need("character_manager")
        npcs = set()
        try:
            npcs = set(manager.get_npcs() or [])
        except Exception:
            pass

        members = []
        for char_id, character in manager.characters.items():
            if char_id in npcs:
                continue
            hp = character.hit_points or {}
            members.append({
                "id": char_id,
                "name": character.name,
                "level": character.level,
                "hp_current": hp.get("current", 0),
                "hp_max": hp.get("maximum", 0),
                "conditions": list(character.conditions or []),
                "stormlight": getattr(character, "stormlight_current", 0),
                "is_dying": hp.get("current", 1) <= 0,
                "is_dead": getattr(character, "is_dead", False),
            })
        # Cached per turn: a pure read, so a repeat call costs no step.
        return _cached_read("party_state",
                            lambda: {"members": members,
                                     "party_size": len(members)})
    except Exception as e:
        logger.warning(f"⚠️ get_party_state failed: {e}")
        return {"error": str(e), "members": []}


@tool
def get_world_state() -> Dict[str, Any]:
    """
    Read the current location, time, weather and quest progress.

    Call this rather than inferring the situation from earlier narration.

    Returns:
        location, exits, hazards, day, part_of_day, weather,
        days_until_highstorm, quests
    """
    try:
        engine = _need("game_engine")
        location = engine.game_state.location_context
        time_info = (engine.get_game_time()
                     if hasattr(engine, "get_game_time") else {})
        quests = (engine.get_quest_progress()
                  if hasattr(engine, "get_quest_progress") else {})
        # Cached per turn: a pure read, so a repeat call costs no step.
        return _cached_read("world_state", lambda: {
            "location": location.get("current_location", "unknown"),
            "description": location.get("description", ""),
            "exits": (engine.get_available_exits()
                      if hasattr(engine, "get_available_exits") else []),
            "hazards": location.get("hazards", []),
            "day": time_info.get("day"),
            "part_of_day": time_info.get("part_of_day"),
            "weather": engine.game_state.environment.get("weather"),
            "days_until_highstorm": time_info.get("days_until_highstorm"),
            "quests_pending": quests.get("pending", []),
            "quests_completed": quests.get("completed", []),
        })
    except Exception as e:
        logger.warning(f"⚠️ get_world_state failed: {e}")
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Rules lookup — Tier 1 and Tier 2 (never Tier 3 for mechanics)
# ---------------------------------------------------------------------------

@tool
def query_rules(topic: str, kind: str = "auto") -> Dict[str, Any]:
    """
    Look up an actual rule rather than recalling one.

    Searches the canonical rulesets: SRD 5e (monsters, spells, conditions,
    equipment) and the Cosmere Radiant's Handbook (Surges, Maneuvers, orders,
    resource economies). Prefer this over your own memory of the rules — the
    campaign's Handbook may differ from published Cosmere material.

    Args:
        topic: What to look up, e.g. "Goblin", "Fireball", "prone", "Full Lashing",
            "Perception", "Longsword", "Bag of Holding", "finesse", "necrotic"
        kind: "monster" | "spell" | "condition" | "skill" | "equipment" |
            "magic_item" | "weapon_property" | "damage_type" | "ability_score" |
            "rule" | "cosmere" | "auto"

    Returns:
        found, tier, source, and the rule data
    """
    try:
        srd = _CONTEXT.get("srd_rules")
        cosmere = _CONTEXT.get("cosmere_rules")

        if kind in ("cosmere", "auto") and cosmere is not None:
            maneuver = cosmere.get_maneuver(topic)
            if maneuver:
                return {"found": True, "tier": 2, "source": "Radiant's Handbook",
                        "kind": "maneuver", "data": maneuver}
            order = cosmere.order(topic)
            if order:
                return {"found": True, "tier": 2, "source": "Radiant's Handbook",
                        "kind": "order", "data": order}

        if srd is not None:
            # Search EVERY loaded dataset. This used to name just four —
            # monsters, spells, conditions, equipment — while SRDRules loaded ten.
            # So "Perception" (in skills.json) fell through to the rules judge and
            # was logged as a Tier-3 gap; see `data/rules/gaps.json`. 386 entries
            # across six datasets were loaded but unreachable.
            hit = srd.lookup(topic, kind)
            if hit:
                return {"found": True, "tier": 1, "source": "SRD 5e (OGL 1.0a)",
                        "kind": hit["kind"], "data": hit["data"]}

        # Nothing canonical (Tier 1/2). Before telling the DM to improvise, let
        # the rules judge try to rule from RETRIEVED text (D5 Tier 3).
        #
        # This branch used to record the gap and return "you may improvise, but
        # say so openly" — with no grounded judgment and no precedent lookup. So
        # `RulesJudge.judge()` and `find_precedent()`, both built and tested,
        # never ran in production, and an improvised ruling was inconsistent from
        # one turn to the next. The gap tracker WAS wired, so a missing rule was
        # counted but never ruled on.
        judge = _CONTEXT.get("rules_judge")
        if judge is not None:
            try:
                ruling = judge.judge(f"rules lookup: {topic}")
                if ruling and ruling.get("tier") == 3:
                    logger.info(f"⚖️  Tier 3 ruling for '{topic}' "
                                f"(precedent={ruling.get('followed_precedent')})")
                    return {"found": True, "tier": 3,
                            "source": "rules judge (grounded, cited)",
                            "kind": "ruling", "data": ruling,
                            "followed_precedent": ruling.get("followed_precedent",
                                                            False),
                            "cites": ruling.get("cites", []),
                            "note": ("This is an adjudicated ruling, not published "
                                     "text. It is grounded in the cited passages "
                                     "and binds future turns.")}
                # Tier 4 (narrative): the judge declined for want of grounding.
                # That is the correct outcome, not a failure — fall through to the
                # honest "no rule" answer below.
                if ruling:
                    logger.info(f"   ⚖️  Judge declined to rule on '{topic}': "
                                f"{ruling.get('reason', 'no grounding')}")
            except Exception as e:
                # Never let adjudication break the turn.
                logger.warning(f"⚠️ Rules judge failed on '{topic}': {e}")

        # Record the gap so it ranks into the backlog (2.11).
        tracker = _CONTEXT.get("gap_tracker")
        if tracker is not None:
            tracker.record(f"rules lookup: {topic}", 3)
        return {"found": False, "topic": topic,
                "note": ("No canonical rule found. You may improvise, but say so "
                         "openly — do not present an invented rule as official.")}
    except Exception as e:
        logger.warning(f"⚠️ query_rules failed: {e}")
        return {"found": False, "error": str(e)}


@tool
def search_lore(query: str) -> Dict[str, Any]:
    """
    Search Roshar narrative lore (novels, world history, Coppermind).

    For FLAVOUR ONLY. Never use this to decide a mechanic — lore prose has no
    dice, costs or DCs. Use query_rules for anything mechanical.

    Args:
        query: What to look up, e.g. "who is Kaladin", "what are highstorms"

    Returns:
        passages: retrieved lore snippets
    """
    try:
        from haystack.components.embedders import SentenceTransformersTextEmbedder
        from haystack_integrations.document_stores.qdrant import QdrantDocumentStore
        from haystack_integrations.components.retrievers.qdrant import (
            QdrantEmbeddingRetriever,
        )

        store = _CONTEXT.get("_lore_store")
        embedder = _CONTEXT.get("_lore_embedder")
        if store is None:
            store = QdrantDocumentStore(path="qdrant_storage",
                                        index="dnd_documents", embedding_dim=1024)
            embedder = SentenceTransformersTextEmbedder(
                model="BAAI/bge-large-en-v1.5", progress_bar=False)
            embedder.warm_up()
            _CONTEXT["_lore_store"] = store
            _CONTEXT["_lore_embedder"] = embedder

        retriever = QdrantEmbeddingRetriever(document_store=store)
        embedding = embedder.run(text=query)["embedding"]
        docs = retriever.run(query_embedding=embedding, top_k=4)["documents"]
        return {
            "query": query,
            "passages": [{"text": d.content[:600],
                          "source": (d.meta or {}).get("source_file", "?"),
                          "score": round(getattr(d, "score", 0) or 0, 3)}
                         for d in docs],
            "note": "Flavour only — do not derive mechanics from these passages.",
        }
    except Exception as e:
        logger.warning(f"⚠️ search_lore failed: {e}")
        return {"query": query, "passages": [], "error": str(e)}


# ---------------------------------------------------------------------------
# State mutation — the DM asks, code applies
# ---------------------------------------------------------------------------

@tool
def apply_damage(amount: int, actor: str = "",
                 damage_type: str = "bludgeoning") -> Dict[str, Any]:
    """
    Apply real damage to a character.

    Do not narrate someone being wounded without calling this; otherwise the
    fiction and the character sheet drift apart.

    Args:
        amount: Hit points of damage (positive)
        actor: Character id; defaults to the acting party member
        damage_type: slashing, piercing, fire, necrotic, …

    Returns:
        hp_before, hp_after, is_dying, is_dead
    """
    try:
        invalidate_dm_tool_reads()  # cached reads are now stale
        manager = _need("character_manager")
        actor_id = _active_actor(actor)
        character = manager.characters.get(actor_id)
        if character is None:
            return {"error": f"unknown character {actor_id!r}"}

        hp = character.hit_points
        before = hp.get("current", 0)
        hp["current"] = max(0, before - max(0, int(amount)))

        logger.info(f"💥 {character.name} takes {amount} {damage_type} "
                    f"({before} -> {hp['current']})")
        return {
            "actor": actor_id, "name": character.name,
            "damage": int(amount), "damage_type": damage_type,
            "hp_before": before, "hp_after": hp["current"],
            "is_dying": hp["current"] <= 0,
            "is_dead": getattr(character, "is_dead", False),
        }
    except Exception as e:
        logger.warning(f"⚠️ apply_damage failed: {e}")
        return {"error": str(e)}


@tool
def apply_healing(amount: int, actor: str = "") -> Dict[str, Any]:
    """
    Heal a character, capped at their maximum hit points.

    Args:
        amount: Hit points to restore
        actor: Character id; defaults to the acting party member

    Returns:
        hp_before, hp_after, healed
    """
    try:
        invalidate_dm_tool_reads()  # cached reads are now stale
        manager = _need("character_manager")
        actor_id = _active_actor(actor)
        character = manager.characters.get(actor_id)
        if character is None:
            return {"error": f"unknown character {actor_id!r}"}

        hp = character.hit_points
        before = hp.get("current", 0)
        hp["current"] = min(hp.get("maximum", 0), before + max(0, int(amount)))
        return {"actor": actor_id, "name": character.name,
                "healed": hp["current"] - before,
                "hp_before": before, "hp_after": hp["current"]}
    except Exception as e:
        logger.warning(f"⚠️ apply_healing failed: {e}")
        return {"error": str(e)}


@tool
def take_rest(kind: str = "long", actor: str = "") -> Dict[str, Any]:
    """
    Rest the party, restoring hit points and advancing the game clock.

    Call this whenever the party makes camp, sleeps, or stops to recover — a rest
    the player asked for and you only narrated leaves them still wounded on the next
    turn, and the in-world clock never moves.

    Args:
        kind: "long" (8 hours, full HP, resources reset) or "short" (1 hour,
              spend a hit die)
        actor: Character id; defaults to the whole party

    Returns:
        kind, hours, rested (per character: hp_before, hp_after)
    """
    try:
        invalidate_dm_tool_reads()  # cached reads are now stale
        manager = _need("character_manager")
        engine = _CONTEXT.get("game_engine")

        long_rest = str(kind).strip().lower() != "short"
        hours = 8 if long_rest else 1

        # Default to the WHOLE PARTY: a party that camps together rests together,
        # and resting one member while the rest stay wounded is never what was
        # meant.
        if actor:
            targets = [actor]
        else:
            try:
                npcs = set(manager.get_npcs() or [])
            except Exception:
                npcs = set()
            targets = [cid for cid in manager.characters if cid not in npcs]

        rested = {}
        for char_id in targets:
            character = manager.characters.get(char_id)
            if character is None:
                continue
            before = dict(character.hit_points or {})
            if long_rest:
                manager.long_rest(char_id)
            else:
                manager.short_rest(char_id, hit_dice_to_spend=1)
            rested[char_id] = {
                "name": character.name,
                "hp_before": before.get("current"),
                "hp_after": character.hit_points.get("current"),
                "hp_max": character.hit_points.get("maximum"),
            }

        # A rest that costs no time is not a rest — the highstorm cycle and every
        # timed quest depend on the clock moving.
        if engine is not None:
            try:
                engine.advance_time(hours=hours,
                                    reason=f"{'long' if long_rest else 'short'} rest")
            except Exception as e:
                logger.warning(f"⚠️ Could not advance the clock for a rest: {e}")

        return {"kind": "long" if long_rest else "short", "hours": hours,
                "rested": rested}
    except Exception as e:
        logger.warning(f"⚠️ take_rest failed: {e}")
        return {"error": str(e)}


@tool
def stabilize_dying(actor: str = "") -> Dict[str, Any]:
    """
    Stabilise a dying character, e.g. after a successful Medicine check (DC 10).

    Use this when someone tends a companion who is at 0 hit points. A stabilised
    character stops rolling death saves and is no longer at risk of dying, but
    remains unconscious at 0 HP until healed.

    Args:
        actor: Character id; defaults to the acting party member

    Returns:
        stabilized, is_stable, is_dead, hit_points
    """
    try:
        invalidate_dm_tool_reads()  # cached reads are now stale
        manager = _need("character_manager")
        actor_id = _active_actor(actor)
        character = manager.characters.get(actor_id)
        if character is None:
            return {"error": f"unknown character {actor_id!r}"}

        if character.hit_points.get("current", 0) > 0:
            return {"stabilized": False,
                    "note": f"{character.name} is conscious and does not need "
                            f"stabilising."}
        if getattr(character, "is_dead", False) is True:
            return {"stabilized": False,
                    "note": f"{character.name} is already dead; stabilising "
                            f"cannot help."}

        stabilized = manager.stabilize(actor_id)
        return {"actor": actor_id, "name": character.name,
                "stabilized": bool(stabilized),
                "is_stable": getattr(character, "is_stable", False),
                "is_dead": getattr(character, "is_dead", False),
                "hit_points": dict(character.hit_points),
                "note": ("Stabilised: no more death saves, but still "
                         "unconscious at 0 HP until healed.")}
    except Exception as e:
        logger.warning(f"⚠️ stabilize_dying failed: {e}")
        return {"error": str(e)}


@tool
def spend_stormlight(amount: int, actor: str = "") -> Dict[str, Any]:
    """
    Spend Stormlight, refusing the spend if the character cannot afford it.

    Surgebinding is not free. Call this whenever a character uses a Surge; if it
    returns affordable=False, narrate the attempt failing for want of Stormlight.

    Args:
        amount: Stormlight to spend
        actor: Character id; defaults to the acting party member

    Returns:
        affordable, spent, remaining
    """
    try:
        invalidate_dm_tool_reads()  # cached reads are now stale
        manager = _need("character_manager")
        actor_id = _active_actor(actor)
        character = manager.characters.get(actor_id)
        if character is None:
            return {"error": f"unknown character {actor_id!r}"}

        current = getattr(character, "stormlight_current", 0) or 0
        amount = max(0, int(amount))
        if amount > current:
            return {"affordable": False, "spent": 0, "remaining": current,
                    "note": f"needs {amount}, has {current}"}

        character.stormlight_current = current - amount
        wrapper = _CONTEXT.get("dnd_engine_wrapper")
        if wrapper is not None and hasattr(wrapper, "sync_roshar_attrs_to_entity"):
            wrapper.sync_roshar_attrs_to_entity(actor_id)
        return {"affordable": True, "spent": amount,
                "remaining": character.stormlight_current}
    except Exception as e:
        logger.warning(f"⚠️ spend_stormlight failed: {e}")
        return {"error": str(e)}


@tool
def advance_quest(objective: str, action: str = "complete") -> Dict[str, Any]:
    """
    Add or complete a quest objective.

    Call this when the story actually moves — a quest the player never sees
    recorded may as well not exist.

    Args:
        objective: The objective text
        action: "complete" or "add"

    Returns:
        pending, completed, percent_complete
    """
    try:
        invalidate_dm_tool_reads()  # cached reads are now stale
        engine = _need("game_engine")
        if action == "add":
            engine.add_quest_objective(objective)
        else:
            engine.complete_quest_objective(objective)
        return {"action": action, "objective": objective,
                **engine.get_quest_progress()}
    except Exception as e:
        logger.warning(f"⚠️ advance_quest failed: {e}")
        return {"error": str(e)}


@tool
def award_experience(amount: int, reason: str = "") -> Dict[str, Any]:
    """
    Award XP to the whole party, levelling anyone who crosses a threshold.

    Args:
        amount: XP per character
        reason: What earned it

    Returns:
        awards: per-character xp/level results
    """
    try:
        invalidate_dm_tool_reads()  # cached reads are now stale
        manager = _need("character_manager")
        npcs = set()
        try:
            npcs = set(manager.get_npcs() or [])
        except Exception:
            pass
        awards = {cid: manager.award_xp(cid, amount)
                  for cid in manager.characters if cid not in npcs}
        leveled = [cid for cid, r in awards.items() if r.get("leveled_up")]
        return {"amount": amount, "reason": reason,
                "awards": awards, "leveled_up": leveled}
    except Exception as e:
        logger.warning(f"⚠️ award_experience failed: {e}")
        return {"error": str(e)}


@tool
def travel_to_location(destination: str) -> Dict[str, Any]:
    """
    Move the party to a new location, advancing the game clock.

    Args:
        destination: Where to travel

    Returns:
        success, from, to, description, hazards, available_exits
    """
    try:
        invalidate_dm_tool_reads()  # cached reads are now stale
        return _need("game_engine").travel_to(destination)
    except Exception as e:
        logger.warning(f"⚠️ travel_to_location failed: {e}")
        return {"success": False, "error": str(e)}


# All DM tools, for wiring into an Agent.
DM_TOOLS = [
    roll_skill_check,
    roll_dice,
    get_character_state,
    get_party_state,
    get_world_state,
    query_rules,
    search_lore,
    apply_damage,
    apply_healing,
    take_rest,
    stabilize_dying,
    spend_stormlight,
    advance_quest,
    award_experience,
    travel_to_location,
]


def dm_tool_names() -> List[str]:
    """The names of the available DM tools."""
    return [t.name for t in DM_TOOLS]
