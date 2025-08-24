
"""
Deterministic Interface Agent (Intent → RAG need → Route)
- Replaces brittle keyword checks and LLM-freeform tool usage.
- Uses a constrained JSON intent classifier (temperature=0) and a sequential, code-driven pipeline.
- Optionally falls back to an embeddings router when confidence is low.
"""

from __future__ import annotations
from typing import Dict, Any, Optional, List, Tuple
import json
import time
import uuid

# Keep compatibility with your config manager
try:
    from config.llm_config import get_global_config_manager
except Exception:  # pragma: no cover
    def get_global_config_manager():
        raise RuntimeError("get_global_config_manager() not available in this environment.")


# --- DTO (shared contract-lite) ------------------------------------------------------------------

def _new_dto(player_input: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "correlation_id": str(uuid.uuid4()),
        "ts": time.time(),
        "type": "meta",                     # will become rules_lookup | npc_interaction | scenario | meta
        "player_input": player_input,
        "action": "",
        "target": None,
        "context": ctx or {},
        "arguments": {},
        "rag": {"needed": False, "query": "", "filters": {}, "docs": []},
        "route": None,
        "debug": {},
    }

# --- LLM helpers ----------------------------------------------------------------------------------

def _call_llm_text(llm, prompt: str, temperature: float = 0.0, max_tokens: Optional[int] = None) -> str:
    """Adapter for different llm client shapes."""
    # Try common call shapes
    if hasattr(llm, "invoke"):
        return llm.invoke(prompt, temperature=temperature, max_tokens=max_tokens)  # type: ignore
    if hasattr(llm, "generate"):
        out = llm.generate(prompt=prompt, temperature=temperature, max_tokens=max_tokens)  # type: ignore
        # try to extract text
        if isinstance(out, dict) and "text" in out:  # custom wrapper
            return out["text"]
        return str(out)
    if callable(llm):
        return llm(prompt, temperature=temperature, max_tokens=max_tokens)  # type: ignore
    raise RuntimeError("Unsupported LLM client interface")

def _safe_load_json(raw: str) -> dict:
    raw = raw.strip()
    # Strip code fences if present
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) >= 2 else raw
    try:
        return json.loads(raw)
    except Exception:
        # last resort: try to locate first and last braces
        try:
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(raw[start:end+1])
        except Exception:
            pass
    return {"primary":"meta","secondary":[],"action_verb":"","target_string":"","target_kind":"unknown","arguments":{},"confidence":0.0,"rationale":"parse_error"}

# --- Intent classification ------------------------------------------------------------------------

_INTENT_SYSTEM = (
    "You are an intent router for a D&D 5e game. "
    "Output ONLY valid JSON using this schema: "
    '{ "primary": "rules_lookup|npc_interaction|scenario_action|world_lore|inventory_management|party_management|meta", '
    '"secondary": ["..."], "action_verb": "...", "target_string": "...", '
    '"target_kind": "npc|object|place|unknown", "arguments": {}, "confidence": 0..1, "rationale": "..." } '
    "Do not add commentary."
)

_INTENT_FEWSHOTS = [
    {
        "in": "cast fireball at level 5",
        "out": {"primary":"rules_lookup","secondary":[],"action_verb":"cast","target_string":"fireball","target_kind":"object","arguments":{"spell":"fireball","level":5},"confidence":0.9,"rationale":"spell inquiry"}
    },
    {
        "in": "ask the bartender about rumors",
        "out": {"primary":"npc_interaction","secondary":[],"action_verb":"ask","target_string":"bartender","target_kind":"npc","arguments":{},"confidence":0.85,"rationale":"npc talk"}
    },
    {
        "in": "search the alcove for hidden levers",
        "out": {"primary":"scenario_action","secondary":[],"action_verb":"search","target_string":"alcove","target_kind":"object","arguments":{},"confidence":0.8,"rationale":"environment action"}
    },
    {
        "in": "what is the Dragonbone Spire?",
        "out": {"primary":"world_lore","secondary":[],"action_verb":"query","target_string":"Dragonbone Spire","target_kind":"place","arguments":{},"confidence":0.8,"rationale":"lore query"}
    },
]

def _render_intent_prompt(player_input: str, ctx: Dict[str, Any], npc_names: List[str], place_names: List[str]) -> str:
    few = "\n".join([
        f'Example:\nUser: {ex["in"]}\nJSON: {json.dumps(ex["out"], ensure_ascii=False)}'
        for ex in _INTENT_FEWSHOTS
    ])
    return (
        f"{_INTENT_SYSTEM}\n\n"
        f"{few}\n\n"
        f"User Input: {player_input}\n"
        f"Game Context JSON: {json.dumps(ctx, ensure_ascii=False)}\n"
        f"Known NPC Names: {', '.join(npc_names) if npc_names else ''}\n"
        f"Known Places: {', '.join(place_names) if place_names else ''}\n"
        f"JSON:"
    )

def _map_primary_to_type(primary: str) -> str:
    m = {
        "rules_lookup": "rules_lookup",
        "npc_interaction": "npc_interaction",
        "scenario_action": "scenario",
        "world_lore": "scenario",           # lore handled via scenario generation, with RAG
        "inventory_management": "scenario",
        "party_management": "scenario",
        "meta": "meta",
    }
    return m.get(primary, "scenario")

# --- Embedding router (optional) ------------------------------------------------------------------

# --- RAG need prediction --------------------------------------------------------------------------

_RAG_PREDICTOR_PROMPT = (
    "Decide if the user's request needs external knowledge. Output JSON: "
    '{ "needed": true|false, "category": "rules|lore|statblock|none", "confidence": 0..1 }.\n'
    "User: {text}\n"
)

def _predict_rag_need(dto: Dict[str, Any], llm) -> Dict[str, Any]:
    text = dto["player_input"]
    raw = _call_llm_text(llm, _RAG_PREDICTOR_PROMPT.format(text=text), temperature=0.0)
    data = _safe_load_json(raw)
    needed = bool(data.get("needed", False))
    cat = data.get("category", "none")
    conf = float(max(0.0, min(1.0, data.get("confidence", 0.0))))
    dto["rag"]["needed"] = needed
    dto["rag"]["query"] = text if needed else ""
    dto["rag"]["filters"] = {}
    # refine file_type filter
    if needed and cat in ("rules","lore","statblock"):
        dto["rag"]["filters"]["file_type"] = [cat if cat != "none" else "lore"]
    dto["debug"]["rag_predictor"] = {"category": cat, "confidence": conf}
    return dto

# --- Target resolution (simple fuzzy) -------------------------------------------------------------

def _resolve_target(target_string: Optional[str], world_state) -> Tuple[Optional[str], str]:
    """Resolve a free-text target to a world entity id. world_state must expose .npcs (dict) and .places (list/dict)."""
    if not target_string:
        return None, "unknown"
    t = target_string.lower().strip()
    # NPCs
    if hasattr(world_state, "npcs"):
        for npc_id, npc in world_state.npcs.items():
            names = {npc_id.lower()}
            if isinstance(npc, dict):
                for alias in npc.get("aliases", []):
                    names.add(str(alias).lower())
                if "name" in npc:
                    names.add(str(npc["name"]).lower())
            if t in names:
                return npc_id, "npc"
    # Places
    places = getattr(world_state, "places", [])
    for p in places or []:
        if str(p).lower() == t:
            return str(p), "place"
    return target_string, "unknown"

# --- Public API -----------------------------------------------------------------------------------

def build_interface_agent(world_state, *, use_embeddings_router: bool = True, intent_conf_thresh: float = 0.35):
    """
    Returns a callable `decide(player_input: str, game_context: dict) -> dict (DTO)`.
    Sequences: normalize → intent (LLM) → (embed fallback) → resolve target → rag predictor (LLM) → route.
    """
    cfg = get_global_config_manager()
    llm = getattr(cfg, "llm", None) or getattr(cfg, "intent_llm", None)
    embedder = getattr(cfg, "embedder", None)
    centroids = getattr(cfg, "intent_centroids", None) or {}  # dict[str, list[float]]

    if llm is None:
        raise RuntimeError("Interface agent: LLM is not configured (cfg.llm or cfg.intent_llm).")

    def decide(player_input: str, game_context: Dict[str, Any]) -> Dict[str, Any]:
        dto = _new_dto(player_input, game_context)
        _log_event(dto, "start", {"text": player_input})

        # 1) Intent classification
        prompt = _render_intent_prompt(
            player_input=player_input,
            ctx=game_context,
            npc_names=list(getattr(world_state, "npcs", {}).keys()),
            place_names=list(getattr(world_state, "places", []) or []),
        )
        raw = _call_llm_text(llm, prompt, temperature=0.0)
        data = _safe_load_json(raw)
        conf = float(max(0.0, min(1.0, data.get("confidence", 0.0))))
        primary = str(data.get("primary", "scenario") or "scenario")
        dto["type"] = _map_primary_to_type(primary)
        dto["action"] = data.get("action_verb", "") or ""
        dto["target"] = data.get("target_string") or None
        dto["arguments"] = data.get("arguments", {}) or {}
        dto["debug"]["intent"] = {"primary": primary, "confidence": conf, "raw": data}

        _log_event(dto, "intent", {"type": dto["type"], "conf": conf, "embed": dto["debug"].get("embed_router")})

        # 3) Target resolution (no LLM; deterministic)
        resolved_id, resolved_kind = _resolve_target(dto.get("target"), world_state)
        dto["target"] = resolved_id
        dto["debug"]["target_kind"] = resolved_kind

        # 4) RAG need prediction (LLM, temp 0)
        dto = _predict_rag_need(dto, llm)

        # 5) Route
        if dto["type"] == "rules_lookup":
            dto["route"] = "rules"
        elif dto["type"] == "npc_interaction" or resolved_kind == "npc":
            dto["route"] = "npc"
        else:
            dto["route"] = "scenario"
            # force RAG on for lore-like intents mapped to scenario
            if (data.get("primary") == "world_lore") and not dto["rag"]["needed"]:
                dto["rag"]["needed"] = True
                dto["rag"]["query"] = dto["player_input"]

        _log_event(dto, "route", {"route": dto["route"]})
        return dto

    return decide

# --- Simple smoke test (optional) -----------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    class _World:
        def __init__(self):
            self.npcs = {"bartender": {"name": "Bart", "aliases": ["barkeep", "bartender"]}}
            self.places = ["Dragonbone Spire", "Tavern"]
    world = _World()

    # Dummy cfg stub if running standalone (replace with real cfg in your app)
    class _LLMStub:
        def __call__(self, prompt, temperature=0.0, max_tokens=None):
            if "cast fireball" in prompt:
                return json.dumps({"primary":"rules_lookup","secondary":[],"action_verb":"cast","target_string":"fireball","target_kind":"object","arguments":{"spell":"fireball","level":5},"confidence":0.9,"rationale":""})
            if "bartender" in prompt:
                return json.dumps({"primary":"npc_interaction","secondary":[],"action_verb":"ask","target_string":"bartender","target_kind":"npc","arguments":{},"confidence":0.8,"rationale":""})
            if "Dragonbone Spire" in prompt:
                return json.dumps({"primary":"world_lore","secondary":[],"action_verb":"query","target_string":"Dragonbone Spire","target_kind":"place","arguments":{},"confidence":0.8,"rationale":""})
            return json.dumps({"primary":"scenario_action","secondary":[],"action_verb":"search","target_string":"","target_kind":"unknown","arguments":{},"confidence":0.6,"rationale":""})

    class _Cfg:
        llm = _LLMStub()
        embedder = None
        intent_centroids = {}

    # monkeypatch
    def _get_cfg():
        return _Cfg()
    globals()['get_global_config_manager'] = _get_cfg

    decide = build_interface_agent(world)
    for text in [
        "cast fireball at level 5",
        "ask the bartender about rumors",
        "what is the Dragonbone Spire?",
        "search the alcove for levers",
    ]:
        out = decide(text, {"location":"Tavern"})
        print(text, "→", out["type"], out["route"], out["rag"])
