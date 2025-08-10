"""
Patched RAG DM Assistant (full patch)

Drop this file into your repo as `rag_dm_assistant_full_patch.py` (or replace existing
`rag_dm_assistant.py` after review). This patch adds:
  - GameEngine: authoritative tick loop and action processing
  - NPCController: hybrid rule-based + RAG-driven NPC decisions
  - ScenarioGenerator: deterministic seed + optional RAG augmentation
  - HaystackRAG wrapper: minimal Qdrant -> Haystack retriever pipeline
  - A small JSON persister for state checkpoints
  - A CLI entrypoint demonstrating wiring with an existing RAG agent if present

Integration notes:
  - If you already have a RAG agent (e.g., rag_agent or RAGDMAssistant class), this patch
    will try to import `ExistingRAGAgent` from `rag_dm_assistant` or `rag_agent`.
    If not found, a dummy local rag adapter will be used (no external calls).
  - The ScenarioGenerator and NPCController expect the rag agent to provide `.query(prompt, top_k=1)`
    returning a dictionary-like response (or a string). Adapt the adapter to your agent API.

Requirements:
  - haystack, qdrant-client, and their dependencies if you plan to use HaystackRAG.
  - This file is intentionally conservative: it will function without Haystack installed (fallbacks).

"""

import json
import threading
import time
import random
import os
from typing import Dict, Any, List, Optional, Tuple

# --------------------------------------------------
# RAG agent adapter: try to import existing agent from repo
# --------------------------------------------------

class DummyRAGAdapter:
    """A tiny stand-in adapter: returns canned responses and echoes prompts.
    Replace or adapt to call your project's RAG agent / LLM wrapper.
    """
    def query(self, prompt: str, top_k: int = 1) -> Dict[str, Any]:
        # Very small heuristic: if prompt asks for scene, return structured dict
        lower = prompt.lower()
        if "describe" in lower or "scene" in lower:
            return {
                "scene_text": "A dimly lit alley with a single lantern. You hear footsteps.",
                "options_text": "1. Investigate the footsteps.\n2. Hide and watch.\n3. Call out and try to talk.\n4. Retreat silently."
            }
        if "what should this npc do" in lower or "what should this npc" in lower:
            return {"move_to": "nearby_rooftop"}
        if "describe the immediate consequence" in lower or "describe the immediate" in lower:
            return {"continuation": "The party's choice draws a shadowed figure out; a tense conversation ensues."}
        # fallback
        return {"scene_text": "The world is unchanged.", "options_text": "1. Wait. 2. Move on."}

# attempt to import existing agent (non-fatal)
try:
    # If your repo defines ExistingRAGAgent in rag_dm_assistant or rag_agent, import it
    from rag_dm_assistant import ExistingRAGAgent  # type: ignore
    def make_rag_agent():
        return ExistingRAGAgent()
except Exception:
    try:
        from rag_agent import ExistingRAGAgent  # type: ignore
        def make_rag_agent():
            return ExistingRAGAgent()
    except Exception:
        def make_rag_agent():
            return DummyRAGAdapter()

# --------------------------------------------------
# Persister (file-based JSON for checkpointing)
# --------------------------------------------------
class JSONPersister:
    def __init__(self, path: str = "./game_state_checkpoint.json"):
        self.path = path

    def save(self, game_state: Dict[str, Any]):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(game_state, f, indent=2)
        except Exception as e:
            print(f"Persister save error: {e}")

    def load(self) -> Optional[Dict[str, Any]]:
        if not os.path.exists(self.path):
            return None
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

# --------------------------------------------------
# Game Engine
# --------------------------------------------------
DEFAULT_TICK_SECONDS = 0.8

class GameEngine:
    def __init__(self,
                 initial_state: Optional[Dict[str, Any]] = None,
                 npc_controller=None,
                 scenario_generator=None,
                 persister: Optional[JSONPersister] = None,
                 tick_seconds: float = DEFAULT_TICK_SECONDS):
        self.game_state = initial_state or {
            "players": {},
            "npcs": {},
            "world": {"locations": []},
            "story_arc": "",
            "scene_history": [],
            "current_scenario": "",
            "current_options": "",
            "session": {"location": "unknown", "time": "", "events": []},
            "action_queue": []
        }
        self.npc_controller = npc_controller
        self.scenario_generator = scenario_generator
        self.persister = persister
        self.tick_seconds = tick_seconds
        self.running = False
        self.lock = threading.RLock()

    def enqueue_action(self, action: Dict[str, Any]):
        with self.lock:
            self.game_state["action_queue"].append(action)

    def _process_player_action(self, action: Dict[str, Any]):
        typ = action.get("type")
        actor = action.get("actor")
        args = action.get("args", {})
        if typ == "move":
            new_loc = args.get("to")
            if actor in self.game_state["players"]:
                self.game_state["players"][actor]["location"] = new_loc
                self.game_state["session"]["events"].append(f"{actor} moved to {new_loc}")
        elif typ == "choose_option":
            choice = args.get("choice")
            if self.scenario_generator:
                cont = self.scenario_generator.apply_player_choice(self.game_state, actor, choice)
                if cont:
                    self.game_state["scene_history"].append(cont)
                    self.game_state["current_scenario"] = cont
        elif typ == "raw_event":
            ev = args.get("text")
            if ev:
                self.game_state["session"]["events"].append(ev)
        else:
            self.game_state["session"]["events"].append(f"Unhandled action type: {typ}")

    def _process_npcs(self):
        if not self.npc_controller:
            return
        decisions = []
        try:
            decisions = self.npc_controller.decide(self.game_state)
        except Exception as e:
            # fail-safe
            self.game_state["session"]["events"].append(f"NPC controller error: {e}")
        for d in decisions:
            # NPC decisions are applied the same way as player actions
            self._process_player_action(d)

    def _should_generate_scene(self) -> bool:
        if not self.game_state.get("current_scenario"):
            return True
        recent_events = self.game_state["session"].get("events", [])[-4:]
        # trigger on a player choice or explicit DM request event
        return any("chose" in e.lower() or "new scene requested" in e.lower() for e in recent_events)

    def tick(self):
        with self.lock:
            # process action queue FIFO
            while self.game_state.get("action_queue"):
                act = self.game_state["action_queue"].pop(0)
                try:
                    self._process_player_action(act)
                except Exception as e:
                    self.game_state["session"]["events"].append(f"Error processing action: {e}")

            # NPCs
            self._process_npcs()

            # Scenario generation
            if self.scenario_generator and self._should_generate_scene():
                try:
                    scene_json, options_text = self.scenario_generator.generate(self.game_state)
                    self.game_state["scene_history"].append(scene_json)
                    self.game_state["current_scenario"] = scene_json
                    self.game_state["current_options"] = options_text
                    self.game_state["session"]["events"].append("New scene generated")
                except Exception as e:
                    self.game_state["session"]["events"].append(f"Scenario generation error: {e}")

            # persist
            if self.persister:
                try:
                    self.persister.save(self.game_state)
                except Exception:
                    pass

    def start(self):
        self.running = True
        def loop():
            while self.running:
                self.tick()
                time.sleep(self.tick_seconds)
        t = threading.Thread(target=loop, daemon=True)
        t.start()

    def stop(self):
        self.running = False

# --------------------------------------------------
# NPC Controller
# --------------------------------------------------
class NPCController:
    def __init__(self, rag_agent=None, mode="hybrid"):
        self.rag_agent = rag_agent
        self.mode = mode

    def decide(self, game_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        actions = []
        for npc_name, npc in game_state.get("npcs", {}).items():
            # Normalize NPC structure
            npc_obj = npc if isinstance(npc, dict) else {"name": npc}
            if npc_obj.get("type") == "simple":
                a = self._rule_based(npc_obj, game_state)
                if a:
                    actions.append(a)
            else:
                if self.mode in ("rag", "hybrid") and self.rag_agent:
                    prompt = self._build_prompt_for_npc(npc_obj, game_state)
                    try:
                        plan = self.rag_agent.query(prompt, top_k=1)
                        # Accept multiple shapes: dict or string
                        if isinstance(plan, dict):
                            dest = plan.get("move_to") or plan.get("to")
                            if dest:
                                actions.append({"actor": npc_name, "type": "move", "args": {"to": dest}})
                        elif isinstance(plan, str):
                            # best-effort parse: look for 'to <location>'
                            if "to " in plan:
                                to_idx = plan.index("to ")
                                dest = plan[to_idx + 3:].split()[0]
                                actions.append({"actor": npc_name, "type": "move", "args": {"to": dest}})
                    except Exception:
                        # degrade to rule-based
                        a = self._rule_based(npc_obj, game_state)
                        if a:
                            actions.append(a)
        return actions

    def _rule_based(self, npc: Dict[str, Any], game_state: Dict[str, Any]):
        # Example priorities: flee if HP low, attack or patrol
        hp = npc.get("hp", 9999)
        max_hp = npc.get("max_hp", hp)
        if max_hp and hp < max(1, max_hp * 0.25):
            return {"actor": npc.get("name"), "type": "move", "args": {"to": npc.get("flee_to", "safe_spot")}}
        # If player in same location, choose to approach
        players = game_state.get("players", {})
        for p, pdata in players.items():
            if pdata.get("location") == npc.get("location"):
                return {"actor": npc.get("name"), "type": "raw_event", "args": {"text": f"{npc.get('name')} engages {p}."}}
        # Else random patrol
        locs = game_state.get("world", {}).get("locations", []) or []
        if locs:
            return {"actor": npc.get("name"), "type": "move", "args": {"to": random.choice(locs)}}
        return None

    def _build_prompt_for_npc(self, npc, game_state):
        # Keep prompt concise but informative
        sb = [f"NPC: {npc.get('name')}", f"Role: {npc.get('role', 'unknown')}", f"HP: {npc.get('hp', '?')}" ]
        sb.append(f"Location: {npc.get('location', '?')}")
        sb.append("Recent events: " + ", ".join(game_state.get('session', {}).get('events', [])[-4:]))
        sb.append("What should this NPC do next? Be concise and return a tiny JSON-like answer with move_to if moving.")
        return "\n".join(sb)

# --------------------------------------------------
# Scenario Generator
# --------------------------------------------------
class ScenarioGenerator:
    def __init__(self, rag_agent=None, verbose=False):
        self.rag_agent = rag_agent
        self.verbose = verbose

    def _seed_scene(self, state: Dict[str, Any]) -> Dict[str, Any]:
        seed = {
            "location": state["session"].get("location") or "unknown",
            "recent": state["session"].get("events", [])[-4:],
            "party": list(state.get("players", {}).keys())[:8],
            "story_arc": state.get("story_arc", "")
        }
        return seed

    def _build_prompt(self, seed: Dict[str, Any]) -> str:
        prompt = (
            f"You are the Dungeon Master. Create a vivid short scene (2-3 sentences) and offer 3-4 numbered options.\n"
            f"Location: {seed['location']}\nRecent: {seed['recent']}\nParty: {seed['party']}\nStory arc: {seed['story_arc']}\n"
            "Return a JSON-like object with fields: scene_text, options_text."
        )
        return prompt

    def generate(self, state: Dict[str, Any]) -> Tuple[str, str]:
        seed = self._seed_scene(state)
        scene_text = f"You are at {seed['location']}. Recent events: {', '.join(seed['recent'])}."
        options_text = ""
        if self.rag_agent:
            try:
                prompt = self._build_prompt(seed)
                resp = self.rag_agent.query(prompt, top_k=1)
                if isinstance(resp, dict):
                    scene_text = resp.get("scene_text", scene_text)
                    options_text = resp.get("options_text", "")
                elif isinstance(resp, str):
                    # quick heuristic: treat as scene_text
                    scene_text = resp
            except Exception:
                pass
        if not options_text:
            # fallback options
            options = [
                "1. Investigate the suspicious noise.",
                "2. Approach openly and ask questions.",
                "3. Set up an ambush and wait.",
                "4. Leave and gather more information."
            ]
            random.shuffle(options)
            options_text = "\n".join(options[:4])

        scene_json = {
            "scene_text": scene_text,
            "seed": seed,
            "options": [line.strip() for line in options_text.splitlines() if line.strip()]
        }
        return json.dumps(scene_json, indent=2), options_text

    def apply_player_choice(self, state: Dict[str, Any], player: str, choice_value: int) -> str:
        try:
            current_options = state.get("current_options", "")
            lines = [l for l in current_options.splitlines() if l.strip()]
            target = None
            # try numeric match
            for l in lines:
                if l.strip().startswith(f"{choice_value}."):
                    target = l
                    break
            if not target and lines:
                # fallback: pick by index
                idx = max(0, min(len(lines) - 1, choice_value - 1))
                target = lines[idx]
            if not target:
                return f"No such option: {choice_value}"
            cont = f"{player} chose: {target}"
            # ask rag agent for consequence
            if self.rag_agent:
                prompt = (
                    f"CONTEXT: {state.get('story_arc')}\nCHOICE: {target}\n"
                    "Describe the immediate consequence in 2-3 sentences and return a short 'continuation' field."
                )
                try:
                    resp = self.rag_agent.query(prompt, top_k=1)
                    if isinstance(resp, dict):
                        return resp.get("continuation", cont)
                    elif isinstance(resp, str):
                        return resp
                except Exception:
                    pass
            return cont
        except Exception as e:
            return f"Error applying choice: {e}"

# --------------------------------------------------
# Minimal Haystack wrapper (optional)
# --------------------------------------------------
try:
    from haystack.document_stores import QdrantDocumentStore
    from haystack.nodes import DensePassageRetriever
    from haystack.pipelines import Pipeline
    HAYSTACK_AVAILABLE = True
except Exception:
    HAYSTACK_AVAILABLE = False

class HaystackRAG:
    def __init__(self, qdrant_url: str = "http://localhost:6333", index: str = "dnd_documents", embedding_dim: int = 1536):
        if not HAYSTACK_AVAILABLE:
            raise RuntimeError("Haystack not available in this environment. Install haystack, qdrant-client, etc.")
        self.docstore = QdrantDocumentStore(url=qdrant_url, prefer_grpc=False, collection_name=index, embedding_dim=embedding_dim)
        self.retriever = DensePassageRetriever(document_store=self.docstore,
                                              query_embedding_model="facebook/dpr-question_encoder-single-nq-base",
                                              passage_embedding_model="facebook/dpr-ctx_encoder-single-nq-base",
                                              use_gpu=False)
        self.docstore.update_embeddings(self.retriever)
        self.pipeline = Pipeline()
        self.pipeline.add_node(component=self.retriever, name="Retriever", inputs=["Query"])

    def get_context(self, query: str, top_k: int = 5) -> str:
        out = self.pipeline.run(query=query, params={"Retriever": {"top_k": top_k}})
        docs = out.get("documents", [])
        return "\n\n".join([d.content for d in docs])

# --------------------------------------------------
# CLI / wiring example
# --------------------------------------------------

def build_default_state() -> Dict[str, Any]:
    return {
        "players": {
            "Alice": {"location": "town_square", "hp": 20},
            "Bob": {"location": "town_square", "hp": 18}
        },
        "npcs": {
            "watchman": {"name": "watchman", "location": "gate", "type": "simple", "hp": 12, "role": "guard"},
            "mysterious_stranger": {"name": "mysterious_stranger", "location": "alley", "type": "complex", "hp": 15, "role": "unknown"}
        },
        "world": {"locations": ["town_square", "alley", "gate", "tavern"]},
        "story_arc": "The caravan was robbed and a clue points to the city.",
        "scene_history": [],
        "current_scenario": "",
        "current_options": "",
        "session": {"location": "town_square", "time": "dawn", "events": ["Party arrived in town."]},
        "action_queue": []
    }


def cli_demo_loop(engine: GameEngine):
    print("DM engine started — demo CLI. Type 'help' for commands.")
    try:
        while True:
            cmd = input("> ").strip()
            if not cmd:
                continue
            if cmd == "help":
                print("Commands: state, tick, enqueue, choose <player> <n>, show_scene, stop, quit")
                continue
            if cmd == "state":
                print(json.dumps(engine.game_state, indent=2)[:2000])
                continue
            if cmd == "show_scene":
                print("Current scenario:\n", engine.game_state.get("current_scenario"))
                print("Options:\n", engine.game_state.get("current_options"))
                continue
            if cmd.startswith("enqueue "):
                payload = cmd[len("enqueue "):]
                # quick parse: actor:type:arg
                # Example: enqueue Alice:move:alley
                parts = payload.split(":")
                if len(parts) >= 3:
                    actor, typ, arg = parts[0], parts[1], parts[2]
                    engine.enqueue_action({"actor": actor, "type": typ, "args": {"to": arg}})
                    print("Enqueued")
                else:
                    print("Bad enqueue format. Use actor:type:arg")
                continue
            if cmd.startswith("choose "):
                try:
                    _, player, n = cmd.split()
                    n = int(n)
                    engine.enqueue_action({"actor": player, "type": "choose_option", "args": {"choice": n}})
                    print("Choice enqueued")
                except Exception as e:
                    print("Bad choose command", e)
                continue
            if cmd in ("stop", "quit"):
                engine.stop()
                print("Engine stopped. Exiting.")
                break
            if cmd == "tick":
                engine.tick()
                print("Ticked")
                continue
            print("Unknown command")
    except KeyboardInterrupt:
        engine.stop()
        print("Stopped by user")


if __name__ == "__main__":
    rag = make_rag_agent()
    pers = JSONPersister("./game_state_checkpoint.json")
    # load persisted state if present
    state = pers.load() or build_default_state()

    scen = ScenarioGenerator(rag_agent=rag, verbose=True)
    npc = NPCController(rag_agent=rag, mode="hybrid")
    engine = GameEngine(initial_state=state, npc_controller=npc, scenario_generator=scen, persister=pers, tick_seconds=1.0)

    engine.start()
    # Print one immediate scene generation if none
    time.sleep(1.2)
    print("Initial scene (if any):\n", engine.game_state.get("current_scenario"))

    # CLI demo — interactive loop
    cli_demo_loop(engine)
