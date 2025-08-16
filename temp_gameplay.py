import os
import random
import json
import re

from haystack.document_stores import QdrantDocumentStore
from haystack.nodes import EmbeddingRetriever, PromptNode, PromptTemplate
from haystack.pipelines import Pipeline

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
assert OPENAI_API_KEY, "Set OPENAI_API_KEY in env."

# Connect to Qdrant (assumes vector DB with relevant data is already populated)
document_store = QdrantDocumentStore(
    host="localhost",
    port=6333,
    collection_name="stormlight_dnd",
    embedding_dim=1536,
    prefer_grpc=True,
)

retriever = EmbeddingRetriever(
    document_store=document_store,
    embedding_model="text-embedding-ada-002",
    api_key=OPENAI_API_KEY,
)

# --- Prompt Nodes ---

# Intent parser prompt: convert user text to structured action JSON
intent_prompt_template = PromptTemplate(
    name="intent_parser",
    prompt_text="""
You are a game command parser for a Stormlight Archive inspired D&D game.
Given a player's input, identify the intended action and relevant details.

Player input: "{player_input}"

Return a JSON object with:
- "action": one of ["attack", "defend", "heal", "flee", "wait"]
- "weapon": string or null
- "target": string or null
- "notes": string or empty

Example:
{{"action":"attack", "weapon":"shard blade", "target":"enemy", "notes":""}}

Only output valid JSON.
"""
)
intent_parser_node = PromptNode(
    model_name="gpt-4o-mini",
    api_key=OPENAI_API_KEY,
    default_prompt_template=intent_prompt_template,
)

# Scenario generation prompt
scenario_prompt = PromptTemplate(
    name="scenario_generation",
    prompt_text="""
You are a Dungeon Master creating a short Stormlight Archive inspired D&D scenario.

Use the retrieved context to create:

- A concise 3-4 sentence scene description
- One enemy NPC with name, HP (10-20), and a short trait
- Simple victory and defeat conditions

Context:
{join(documents)}

Respond ONLY with the scenario text in plain sentences (no JSON).
"""
)
scenario_prompt_node = PromptNode(
    model_name="gpt-4o-mini",
    api_key=OPENAI_API_KEY,
    default_prompt_template=scenario_prompt,
)

# Turn narration prompt
turn_prompt = PromptTemplate(
    name="turn_narration",
    prompt_text="""
You are a Dungeon Master narrating a turn in a Stormlight Archive inspired D&D combat.

Context:
{join(documents)}

Current Scene: {scene}
Enemy: {enemy_name} (HP: {enemy_hp})
Player HP: {player_hp}
Player Action: {player_action}

Describe what happens next in 2-4 vivid sentences, including any combat results.
"""
)
turn_prompt_node = PromptNode(
    model_name="gpt-4o-mini",
    api_key=OPENAI_API_KEY,
    default_prompt_template=turn_prompt,
)

# --- Pipelines ---

scenario_pipe = Pipeline()
scenario_pipe.add_node(component=retriever, name="Retriever", inputs=["Query"])
scenario_pipe.add_node(component=scenario_prompt_node, name="PromptNode", inputs=["Retriever"])

turn_pipe = Pipeline()
turn_pipe.add_node(component=retriever, name="Retriever", inputs=["Query"])
turn_pipe.add_node(component=turn_prompt_node, name="PromptNode", inputs=["Retriever"])

# --- Utility functions ---

def roll_success(dc=10):
    roll = random.randint(1, 20)
    return roll >= dc

def parse_enemy_from_text(text):
    # Try to extract enemy name and HP from generated scenario text
    enemy_name = "Enemy"
    enemy_hp = 15
    m_name = re.search(r"enemy (?:named )?([A-Za-z ]+)", text, re.I)
    m_hp = re.search(r"HP(?: is|:)? (\d+)", text, re.I)
    if m_name:
        enemy_name = m_name.group(1).strip()
    if m_hp:
        enemy_hp = int(m_hp.group(1))
    return enemy_name, enemy_hp

# --- Main gameplay loop ---

def main():
    print("Welcome to Stormlight D&D!\n")

    print("Generating scenario...\n")
    scenario_result = scenario_pipe.run(query="stormlight archive dnd scenario creation", params={"Retriever": {"top_k": 5}})
    scenario_text = scenario_result["results"][0]
    print("Scenario:\n", scenario_text)

    enemy_name, enemy_hp = parse_enemy_from_text(scenario_text)
    player_hp = 20
    scene = scenario_text.split("\n")[0]

    print(f"\nEnemy: {enemy_name} (HP: {enemy_hp})")
    print(f"Player HP: {player_hp}")

    print("\nYou can type commands like:")
    print("- I attack the enemy with my shard blade")
    print("- I defend and brace for impact")
    print("- I heal myself using a stormlight infusion")
    print("- I wait and observe")
    print("- I try to flee\n")

    while player_hp > 0 and enemy_hp > 0:
        user_input = input("\nWhat do you do? ").strip()
        if user_input.lower() in ("quit", "exit"):
            print("Exiting game. Goodbye!")
            break

        # Parse intent
        intent_response = intent_parser_node.run(player_input=user_input)
        intent_json_text = intent_response.get("generated_text") or intent_response
        try:
            intent = json.loads(intent_json_text)
        except Exception:
            print("Sorry, I couldn't understand that command. Please try again.")
            continue

        action = intent.get("action", "wait")
        weapon = intent.get("weapon")
        target = intent.get("target")

        # Basic success roll
        success = roll_success()

        # Build context query for narration
        query = f"{scene} {enemy_name} {action} {weapon or ''} {target or ''}".strip()

        turn_result = turn_pipe.run(
            query=query,
            params={
                "Retriever": {"top_k": 5},
                "PromptNode": {
                    "scene": scene,
                    "enemy_name": enemy_name,
                    "enemy_hp": enemy_hp,
                    "player_hp": player_hp,
                    "player_action": user_input,
                },
            },
        )
        narration = turn_result["results"][0]
        print("\nDM narrates:")
        print(narration)

        # Resolve game logic from intent & success
        if action == "attack":
            if success:
                dmg = random.randint(4, 8)
                enemy_hp = max(0, enemy_hp - dmg)
                print(f"You hit {enemy_name} for {dmg} damage!")
            else:
                print("Your attack misses!")
        elif action == "heal":
            if success:
                heal_amt = random.randint(5, 10)
                player_hp = min(20, player_hp + heal_amt)
                print(f"You heal yourself for {heal_amt} HP!")
            else:
                print("Your healing attempt fails.")
        elif action == "defend":
            print("You prepare yourself to reduce incoming damage.")
        elif action == "flee":
            if success:
                print("You successfully flee the combat. You live to fight another day!")
                break
            else:
                print("You fail to flee and must continue fighting.")
        elif action == "wait":
            print("You wait and observe the enemy carefully.")

        # Enemy attacks if alive
        if enemy_hp > 0 and action != "flee":
            enemy_attack_success = roll_success()
            if enemy_attack_success:
                dmg = random.randint(3, 7)
                # Simple defend reduces damage
                if action == "defend":
                    dmg = max(0, dmg - random.randint(1, 4))
                player_hp = max(0, player_hp - dmg)
                print(f"{enemy_name} attacks you and deals {dmg} damage!")
            else:
                print(f"{enemy_name}'s attack misses!")

        print(f"\nPlayer HP: {player_hp} | {enemy_name} HP: {enemy_hp}")

        if player_hp == 0:
            print("\nYou have been defeated. The battle ends here.")
            break
        if enemy_hp == 0:
            print(f"\nYou defeated {enemy_name}! Victory is yours.")
            break

if __name__ == "__main__":
    main()
