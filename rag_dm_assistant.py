"""
RAG-Powered Dungeon Master Assistant
Integrates RAG agent functionality with DM gameplay logic
"""
import json
import random
from typing import Dict, List, Any, Optional

# Import RAG agent functionality
from rag_agent import RAGAgent, CLAUDE_AVAILABLE

# Set up RAG agent for context retrieval
rag_agent: Optional[RAGAgent] = None

def initialize_rag_agent(collection_name: str = "dnd_documents", verbose: bool = False):
    """Initialize the RAG agent for context retrieval"""
    global rag_agent
    try:
        rag_agent = RAGAgent(collection_name=collection_name, verbose=verbose)
        return True
    except Exception as e:
        print(f"Failed to initialize RAG agent: {e}")
        return False

def get_context(query: str) -> str:
    """Get context from RAG agent for DM decisions"""
    if not rag_agent:
        return f"RAG agent not initialized. Using basic context for: {query}"
    
    try:
        result = rag_agent.query(query)
        if "error" in result:
            return f"Error retrieving context: {result['error']}"
        return result["answer"]
    except Exception as e:
        return f"Error getting context: {e}"

# ------------------------------
#  Game State Storage
# ------------------------------
game_state = {
    "players": {},  # player_name: {"hp": int, "stats": {}, "inventory": []}
    "npcs": {},     # npc_name: {"description": str, "stats": {}}
    "world": {},    # arbitrary world flags or conditions
    "story_arc": "The story is set in the land of Roshar",
    "scene_history": [],
    "session": {    # session-specific info
        "location": "",
        "time": "",
        "events": []
    }
}

# ------------------------------
#  Claude-based LLM Integration
# ------------------------------
def call_claude_for_intent(instruction: str) -> Dict[str, Any]:
    """Use Claude via RAG agent to parse DM instructions"""
    if not rag_agent or not CLAUDE_AVAILABLE:
        # Fallback intent parsing without Claude
        return {"intent": "other", "params": {}}
    
    intent_query = f"""Parse this Dungeon Master instruction and return only a JSON object:

Instruction: "{instruction}"

Return JSON with:
{{
  "intent": one of ["add_player", "update_player", "add_npc", "update_npc", "update_world", "generate_scenario", "print_state", "other"],
  "params": {{...}} // key-value pairs with details
}}

Only return valid JSON, no commentary."""
    
    try:
        result = rag_agent.query(intent_query)
        if "error" in result:
            return {"intent": "other", "params": {}}
        
        # Try to extract JSON from the response
        response = result["answer"]
        # Look for JSON in the response
        start = response.find('{')
        end = response.rfind('}') + 1
        if start != -1 and end != 0:
            json_str = response[start:end]
            return json.loads(json_str)
        else:
            return {"intent": "other", "params": {}}
    except Exception:
        return {"intent": "other", "params": {}}

def generate_scenario_with_claude(context: str, state: str, query: str = "general adventure") -> str:
    """Generate scenario using Claude with RAG context and story continuity"""
    if not rag_agent:
        return "RAG agent not available for scenario generation."
    
    # Get last scene for continuity
    last_scene = game_state["scene_history"][-1] if game_state["scene_history"] else "No previous scene."
    
    scenario_query = f"""You are a Dungeon Master creating a scene for players.
You must continue the ongoing story while incorporating relevant lore/context.

RAG Context (lore, rules, descriptions):
{context}

Current Story Arc Summary:
{game_state["story_arc"]}

Last Scene:
{last_scene}

Current Game State:
{state}

Player/DM Request: {query}

Task:
- Generate the next scene in 3-5 sentences.
- Keep continuity with the story arc.
- Reflect recent events from the last scene.
- Introduce at least one interesting decision point for the players.

Only output the scene description. Do not include game mechanics."""
    
    try:
        result = rag_agent.query(scenario_query)
        if "error" in result:
            return f"Error generating scenario: {result['error']}"
        
        scene = result["answer"]
        
        # Store scene in history
        game_state["scene_history"].append(scene)
        
        # Update story arc summary
        updated_summary = update_story_arc_summary(scene)
        if updated_summary:
            game_state["story_arc"] = updated_summary
        
        return scene
    except Exception as e:
        return f"Error generating scenario: {e}"

def update_story_arc_summary(new_scene: str) -> str:
    """Update the story arc summary with new scene information"""
    if not rag_agent:
        return game_state["story_arc"]  # Return unchanged if no RAG agent
    
    summary_query = f"""You are a summarizer for an ongoing tabletop RPG story.

Current Story Arc Summary:
{game_state["story_arc"]}

New Scene:
{new_scene}

Update the story arc summary so it includes the important new events and developments from the new scene.
Keep it under 6 sentences."""
    
    try:
        result = rag_agent.query(summary_query)
        if "error" in result:
            return game_state["story_arc"]  # Return unchanged on error
        return result["answer"]
    except Exception:
        return game_state["story_arc"]  # Return unchanged on error

# ------------------------------
#  State Management Functions
# ------------------------------
def add_player(name: str, hp: int = 10, stats: Dict[str, Any] = None):
    """Add a new player to the game state"""
    game_state["players"][name] = {
        "hp": hp,
        "stats": stats or {},
        "inventory": []
    }

def update_player(name: str, updates: Dict[str, Any]):
    """Update an existing player's information"""
    if name in game_state["players"]:
        game_state["players"][name].update(updates)

def add_npc(name: str, description: str = "", stats: Dict[str, Any] = None):
    """Add a new NPC to the game state"""
    game_state["npcs"][name] = {
        "description": description,
        "stats": stats or {}
    }

def update_npc(name: str, updates: Dict[str, Any]):
    """Update an existing NPC's information"""
    if name in game_state["npcs"]:
        game_state["npcs"][name].update(updates)

def update_world(updates: Dict[str, Any]):
    """Update world state information"""
    game_state["world"].update(updates)

def update_session(updates: Dict[str, Any]):
    """Update session-specific information"""
    game_state["session"].update(updates)

def print_state() -> str:
    """Return formatted game state"""
    return json.dumps(game_state, indent=2)

def get_context_aware_help(topic: str) -> str:
    """Get help on D&D topics using RAG context"""
    help_query = f"Explain {topic} in D&D 5e rules. Be concise and practical for a Dungeon Master."
    return get_context(help_query)

# ------------------------------
#  Enhanced DM Assistant Functions
# ------------------------------
def process_dm_input(instruction: str) -> str:
    """Process DM instruction and return appropriate response"""
    # Parse intent using Claude
    parsed = call_claude_for_intent(instruction)
    intent = parsed.get("intent", "other")
    params = parsed.get("params", {})

    # Execute based on intent
    if intent == "add_player":
        name = params.get("name", "Unknown")
        hp = params.get("hp", 10)
        stats = params.get("stats", {})
        add_player(name, hp, stats)
        return f"✓ Player '{name}' added with {hp} HP."

    elif intent == "update_player":
        name = params.get("name", "")
        updates = params.get("updates", {})
        if name and name in game_state["players"]:
            update_player(name, updates)
            return f"✓ Player '{name}' updated: {updates}"
        return f"❌ Player '{name}' not found."

    elif intent == "add_npc":
        name = params.get("name", "Unknown")
        description = params.get("description", "")
        stats = params.get("stats", {})
        add_npc(name, description, stats)
        return f"✓ NPC '{name}' added."

    elif intent == "update_npc":
        name = params.get("name", "")
        updates = params.get("updates", {})
        if name and name in game_state["npcs"]:
            update_npc(name, updates)
            return f"✓ NPC '{name}' updated: {updates}"
        return f"❌ NPC '{name}' not found."

    elif intent == "update_world":
        update_world(params)
        return f"✓ World state updated: {params}"

    elif intent == "generate_scenario":
        query = params.get("query", instruction)
        # Get relevant context from RAG
        context = get_context(query)
        # Generate scenario with both context and current state
        scenario = generate_scenario_with_claude(context, json.dumps(game_state), query)
        return f"🎭 SCENARIO:\n{scenario}"

    elif intent == "print_state":
        return f"📊 GAME STATE:\n{print_state()}"

    else:
        # For other intents, try to get helpful context
        context = get_context(instruction)
        return f"💡 CONTEXT:\n{context}"

def run_dm_assistant():
    """Main interactive loop for the DM assistant"""
    print("=== RAG-Powered Dungeon Master Assistant ===")
    print("Enhanced with D&D knowledge base for intelligent assistance")
    
    # Initialize RAG agent
    collection_name = input("Enter Qdrant collection name (default: dnd_documents): ").strip()
    if not collection_name:
        collection_name = "dnd_documents"
    
    print("Initializing RAG agent...")
    if not initialize_rag_agent(collection_name, verbose=True):
        print("❌ Failed to initialize RAG agent. Some features may be limited.")
    else:
        print("✓ RAG agent initialized successfully!")
    
    print("\nCommands you can try:")
    print("  - 'Add player Alice with 15 HP'")
    print("  - 'Generate a forest encounter scenario'") 
    print("  - 'Show game state'")
    print("  - 'What are the rules for stealth?'")
    print("  - 'quit' to exit")
    print()

    while True:
        try:
            dm_input = input("\nDM> ").strip()
            
            if dm_input.lower() in ["quit", "exit", "q"]:
                print("Goodbye, Dungeon Master!")
                break
            
            if not dm_input:
                print("Please enter a command or question.")
                continue
            
            # Process the input
            response = process_dm_input(dm_input)
            print(response)
            
        except KeyboardInterrupt:
            print("\nGoodbye, Dungeon Master!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

# ------------------------------
#  Utility Functions
# ------------------------------
def save_game_state(filename: str) -> bool:
    """Save current game state to file"""
    try:
        with open(filename, 'w') as f:
            json.dump(game_state, f, indent=2)
        return True
    except Exception:
        return False

def load_game_state(filename: str) -> bool:
    """Load game state from file"""
    global game_state
    try:
        with open(filename, 'r') as f:
            game_state = json.load(f)
        return True
    except Exception:
        return False

def roll_dice(sides: int, count: int = 1) -> List[int]:
    """Roll dice for DM convenience"""
    return [random.randint(1, sides) for _ in range(count)]

def quick_npc_stats() -> Dict[str, int]:
    """Generate quick NPC stats"""
    return {
        "strength": roll_dice(20)[0],
        "dexterity": roll_dice(20)[0], 
        "constitution": roll_dice(20)[0],
        "intelligence": roll_dice(20)[0],
        "wisdom": roll_dice(20)[0],
        "charisma": roll_dice(20)[0]
    }

if __name__ == "__main__":
    run_dm_assistant()