import json
from typing import Dict, Any
from haystack.nodes import PromptNode, PromptTemplate

# ------------------------------
#  Placeholder for RAG
# ------------------------------
def get_context(query: str) -> str:
    return f"(Lore/context for: {query})"

# ------------------------------
#  Game State with Story
# ------------------------------
game_state = {
    "players": {},
    "npcs": {},
    "world": {},
    "story_arc": "The story begins in the city of Kholinar, on the edge of war.",
    "scene_history": []
}

# ------------------------------
#  Prompts
# ------------------------------
intent_prompt = PromptTemplate(
    name="dm_intent_parser",
    prompt_text="""
You are an intent parser for a Dungeon Master assistant.
Given the Dungeon Master's instruction, return JSON:

{
  "intent": one of ["add_player", "update_player", "add_npc", "update_npc", "update_world", "generate_scenario", "print_state", "other"],
  "params": {...}
}

Instruction: {instruction}

Only output JSON. No explanations.
"""
)

scenario_prompt = PromptTemplate(
    name="stateful_scenario_generator",
    prompt_text="""
You are a scenario generator for a tabletop RPG.
You must continue the ongoing story while incorporating relevant lore/context.

Lore Context:
{context}

Current Story Arc Summary:
{story_arc}

Last Scene:
{last_scene}

Game State:
{state}

Task:
- Generate the next scene in 3-5 sentences.
- Keep continuity with the story arc.
- Reflect recent events from the last scene.
- Introduce at least one interesting decision point for the players.

Only output the scene description. Do not include game mechanics.
"""
)

summary_prompt = PromptTemplate(
    name="story_arc_updater",
    prompt_text="""
You are a summarizer for an ongoing tabletop RPG story.

Current Story Arc Summary:
{story_arc}

New Scene:
{new_scene}

Update the story arc summary so it includes the important new events and developments from the new scene.
Keep it under 6 sentences.
"""
)

# ------------------------------
#  LLM Nodes
# ------------------------------
intent_parser_node = PromptNode("gpt-4o-mini", default_prompt_template=intent_prompt)
scenario_node = PromptNode("gpt-4o-mini", default_prompt_template=scenario_prompt)
summary_node = PromptNode("gpt-4o-mini", default_prompt_template=summary_prompt)

# ------------------------------
#  State Management
# ------------------------------
def add_player(name: str, hp: int = 10, stats: Dict[str, Any] = None):
    game_state["players"][name] = {"hp": hp, "stats": stats or {}, "inventory": []}

def update_player(name: str, updates: Dict[str, Any]):
    if name in game_state["players"]:
        game_state["players"][name].update(updates)

def add_npc(name: str, description: str = "", stats: Dict[str, Any] = None):
    game_state["npcs"][name] = {"description": description, "stats": stats or {}}

def update_npc(name: str, updates: Dict[str, Any]):
    if name in game_state["npcs"]:
        game_state["npcs"][name].update(updates)

def update_world(updates: Dict[str, Any]):
    game_state["world"].update(updates)

def print_state():
    return json.dumps(game_state, indent=2)

# ------------------------------
#  Scenario Generation with Continuity
# ------------------------------
def generate_scenario(query: str = "general adventure"):
    ctx = get_context(query)
    last_scene = game_state["scene_history"][-1] if game_state["scene_history"] else "No previous scene."
    scene = scenario_node.run(
        context=ctx,
        story_arc=game_state["story_arc"],
        last_scene=last_scene,
        state=json.dumps(game_state)
    )["results"][0]

    # Store scene
    game_state["scene_history"].append(scene)

    # Update story arc summary
    updated_summary = summary_node.run(
        story_arc=game_state["story_arc"],
        new_scene=scene
    )["results"][0]
    game_state["story_arc"] = updated_summary

    return scene

# ------------------------------
#  Main DM Input Processor
# ------------------------------
def process_dm_input(instruction: str):
    intent_raw = intent_parser_node.run(instruction=instruction)
    try:
        parsed = json.loads(intent_raw["results"][0])
    except Exception:
        return "Couldn't parse that."

    intent = parsed.get("intent")
    params = parsed.get("params", {})

    if intent == "add_player":
        add_player(params.get("name"), params.get("hp", 10), params.get("stats"))
        return f"Player {params.get('name')} added."

    elif intent == "update_player":
        update_player(params.get("name"), params.get("updates", {}))
        return f"Player {params.get('name')} updated."

    elif intent == "add_npc":
        add_npc(params.get("name"), params.get("description", ""), params.get("stats"))
        return f"NPC {params.get('name')} added."

    elif intent == "update_npc":
        update_npc(params.get("name"), params.get("updates", {}))
        return f"NPC {params.get('name')} updated."

    elif intent == "update_world":
        update_world(params)
        return "World state updated."

    elif intent == "generate_scenario":
        return generate_scenario(params.get("query", "general adventure"))

    elif intent == "print_state":
        return print_state()

    else:
        return "No matching intent."

# ------------------------------
#  Run Loop
# ------------------------------
if __name__ == "__main__":
    print("=== DM Story Assistant ===")
    while True:
        dm_input = input("\nDM> ")
        if dm_input.lower() in ["quit", "exit"]:
            break
        print(process_dm_input(dm_input))