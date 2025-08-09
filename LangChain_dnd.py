#!/usr/bin/env python3
"""
stormlight_dm_rag.py

Minimal Stormlight-flavored D&D DM that:
- Ingests rules, scenarios, and lore text files
- Builds a FAISS vector store (local)
- Uses RAG to generate a scenario
- Runs a tiny gameplay loop: player types an action, we do a pass/fail check,
  call the LLM with retrieved context to narrate, and optionally parse small
  structured updates (damage/heal) from the LLM output.

Notes:
- Only use public SRD or your own summaries for D&D rules.
- Do NOT drop copyrighted novels into "lore/". Use short summaries.
"""

import os
import re
import json
import random
from pathlib import Path
from typing import List

# LangChain + OpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.llms import OpenAI

# Dotenv for convenience
from dotenv import load_dotenv
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("Please set OPENAI_API_KEY in your environment or .env file.")

# Configuration
DATA_DIRS = {
    "rules": "rules",
    "scenarios": "scenarios",
    "lore": "lore"
}
FAISS_INDEX_PATH = "faiss_index"
EMBEDDING_MODEL = "text-embedding-3-small"   # OpenAI embedding model name (adjust if needed)
LLM_MODEL_NAME = "gpt-4o-mini"               # LLM for narration (adjust if allowed/available)

# Small helper: load files from a folder and return strings
def load_texts_from_folder(folder: str) -> List[str]:
    p = Path(folder)
    if not p.exists():
        return []
    texts = []
    for f in p.glob("*.txt") | p.glob("*.md"):
        try:
            txt = f.read_text(encoding="utf-8")
            if txt.strip():
                texts.append(txt.strip())
        except Exception as e:
            print(f"Skipping {f}: {e}")
    return texts

# Build or load FAISS vector store
def build_or_load_faiss(index_path: str = FAISS_INDEX_PATH):
    # Collect docs
    docs: List[Document] = []
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)

    for tag, folder in DATA_DIRS.items():
        texts = load_texts_from_folder(folder)
        for i, t in enumerate(texts):
            chunks = splitter.split_text(t)
            for j, chunk in enumerate(chunks):
                metadata = {"source": folder, "orig_index": i, "chunk_index": j}
                docs.append(Document(page_content=chunk, metadata=metadata))

    if not docs:
        raise RuntimeError(f"No docs found. Please put small text files into {list(DATA_DIRS.values())}")

    # Embeddings
    embed = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY, model=EMBEDDING_MODEL)

    # If index exists, load. Otherwise build.
    if os.path.exists(index_path):
        print("Loading existing FAISS index...")
        return FAISS.load_local(index_path, embed)
    else:
        print(f"Creating FAISS index with {len(docs)} chunks...")
        db = FAISS.from_documents(docs, embed)
        db.save_local(index_path)
        print("Saved FAISS index.")
        return db

# Simple rule: single pass/fail roll
def roll_success(dc: int = 10) -> bool:
    roll = random.randint(1, 20)
    return roll >= dc

# LLM helper
def get_llm():
    # LangChain OpenAI wrapper
    return OpenAI(openai_api_key=OPENAI_API_KEY, model_name=LLM_MODEL_NAME, temperature=0.9, max_tokens=300)

# Generate a scenario using RAG: pull rules + scenarios + lore
def generate_scenario(db: FAISS) -> dict:
    print("Generating scenario (retrieving docs)...")
    # Get top docs for each category query
    rules_hits = db.similarity_search("dnd rules attack roll healing ability checks", k=4)
    scenario_hits = db.similarity_search("example scenario encounter short adventure", k=4)
    lore_hits = db.similarity_search("Stormlight Roshar Shattered Plains spren highstorm", k=6)

    ctx = "\n\n".join([
        "[RULES]\n" + "\n".join([d.page_content for d in rules_hits]),
        "[SCENARIOS]\n" + "\n".join([d.page_content for d in scenario_hits]),
        "[LORE]\n" + "\n".join([d.page_content for d in lore_hits])
    ])

    llm = get_llm()
    prompt = f"""
You are a Dungeon Master. Using the context below (D&D rules, example scenarios, and Roshar/Stormlight-inspired lore),
compose a short playable scenario. The scenario must include:
1) A short scene description (1-3 sentences).
2) One immediate conflict (describe enemies or NPCs with brief stats: name, hp, one short trait).
3) Win/lose conditions (1 sentence each).
4) Suggested first encounter hook (1 sentence).

Context:
{ctx}

Return the output as JSON with keys: "scene", "enemies" (array of objects {name,hp,trait}), "win_condition", "lose_condition", "hook".
Only output JSON.
"""
    raw = llm(prompt)
    # try parse JSON
    try:
        parsed = json.loads(raw)
        return parsed
    except Exception:
        # fallback: attempt to extract JSON block
        m = re.search(r"\{.*\}", raw, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    # Last fallback: create a simple default scenario
    print("LLM did not return JSON cleanly. Using fallback scenario and printing raw LLM response for debug.")
    print("--- RAW ---")
    print(raw)
    fallback = {
        "scene": "A windswept plateau under an approaching highstorm.",
        "enemies": [{"name": "Small Chasmfiend Spawn", "hp": 12, "trait": "quick; skittering"}],
        "win_condition": "Defeat the chasmfiend spawn.",
        "lose_condition": "Player is reduced to 0 HP.",
        "hook": "The chasmfiend spawn barrels toward your party, attracted by noise."
    }
    return fallback

# Narrate a turn using RAG: include retrieved rules + lore + state + action + pass/fail
def narrate_turn(db: FAISS, state: dict, player_action: str, success: bool) -> dict:
    # Retrieve relevant docs based on action and scene
    query = f"{state['scene']} {player_action} {state['enemy']['name']}"
    hits = db.similarity_search(query, k=6)
    context = "\n\n".join([h.page_content for h in hits])

    outcome_text = "Success" if success else "Failure"
    prompt = f"""
You are a creative Dungeon Master with strong knowledge of D&D rules (short SRD) and a Stormlight Archive tone.
Use the context below to narrate the outcome of a player's action.

Context:
{context}

State:
Scene: {state['scene']}
Player HP: {state['player']['hp']}
Enemy: {state['enemy']['name']} (HP: {state['enemy']['hp']})
Player action (text): {player_action}
Outcome: {outcome_text}

Produce two outputs separated by a line:
1) A short vivid narration (2-4 sentences) describing what happens next.
2) A compact JSON object (on its own line) that may include optional fields: damage_to_enemy (int), damage_to_player (int), heal_amount (int), status (string).
If you do not want to change HP, return zeros. Example JSON:
{{"damage_to_enemy": 5, "damage_to_player": 0, "heal_amount":0, "status": ""}}

Only include the JSON on the last line so this script can parse it.
"""
    llm = get_llm()
    raw = llm(prompt)

    # split last JSON line
    lines = raw.strip().splitlines()
    narration = "\n".join(lines[:-1]).strip()
    last = lines[-1].strip()

    parsed = {"narration": narration, "json": {}}
    try:
        parsed_json = json.loads(last)
        parsed["json"] = parsed_json
    except Exception:
        # attempt to find a JSON-like substring
        m = re.search(r"\{.*\}", raw, re.S)
        if m:
            try:
                parsed["json"] = json.loads(m.group(0))
            except Exception:
                parsed["json"] = {}
        else:
            parsed["json"] = {}

    return parsed

# Main small gameplay loop
def run():
    random.seed()  # non-deterministic by default
    db = build_or_load_faiss()

    print("Producing a generated scenario from ingested documents...")
    scenario = generate_scenario(db)

    print("\n--- GENERATED SCENARIO ---")
    print("Scene:", scenario.get("scene"))
    enemies = scenario.get("enemies", [])
    first_enemy = enemies[0] if enemies else {"name": "Wild Thing", "hp": 10, "trait": "unkempt"}
    state = {
        "scene": scenario.get("scene"),
        "player": {"name": "Player", "hp": 20},
        "enemy": {"name": first_enemy.get("name", "Enemy"), "hp": int(first_enemy.get("hp", 10))},
        "log": []
    }
    print("Enemy:", state["enemy"]["name"], "HP:", state["enemy"]["hp"])
    print("Hook:", scenario.get("hook"))
    print("---------------------------\n")

    # simple turn loop
    while state["player"]["hp"] > 0 and state["enemy"]["hp"] > 0:
        action = input("\n> You: ").strip()
        if action.lower() in ("quit", "exit"):
            print("Goodbye.")
            break

        # Simple action parsing: if contains 'attack' -> attempt attack, else generic skill check
        is_attack = "attack" in action.lower() or "hit" in action.lower() or "strike" in action.lower()
        dc = 10
        success = roll_success(dc=dc)

        # narrate + allow LLM to decide damage via JSON
        result = narrate_turn(db, state, action, success)
        narration = result.get("narration", "")
        j = result.get("json", {})

        # Apply simple numeric updates if present
        dmg_to_enemy = int(j.get("damage_to_enemy", 0) or 0)
        dmg_to_player = int(j.get("damage_to_player", 0) or 0)
        heal_amt = int(j.get("heal_amount", 0) or 0)

        # If LLM didn't provide numbers but success==True and it's an attack, do a fallback small damage
        if is_attack and dmg_to_enemy == 0 and success:
            dmg_to_enemy = random.randint(1, 8)  # fallback d8
        if not is_attack and heal_amt == 0 and success and ("heal" in action.lower() or "rest" in action.lower()):
            heal_amt = random.randint(1, 6)  # fallback

        state["enemy"]["hp"] = max(0, state["enemy"]["hp"] - dmg_to_enemy)
        state["player"]["hp"] = max(0, state["player"]["hp"] - dmg_to_player)
        state["player"]["hp"] = min(999, state["player"]["hp"] + heal_amt)

        # log and show results
        state["log"].append({"action": action, "success": success, "narration": narration, "delta": j})
        print("\n" + (narration or "(The DM remains silent.)"))
        print(f"(enemy hp: {state['enemy']['hp']}, your hp: {state['player']['hp']})")

        # small break conditions
        if state["enemy"]["hp"] <= 0:
            print("\n--- VICTORY ---")
            print("You have defeated the enemy. Congratulations.")
            break
        if state["player"]["hp"] <= 0:
            print("\n--- DEFEAT ---")
            print("You have been reduced to 0 HP. The scene fades...")
            break

    # End: print log
    print("\nSession log (recent 6 events):")
    for e in state["log"][-6:]:
        print("-", e["action"], "| success:", e["success"], "| delta:", e["delta"])

if __name__ == "__main__":
    run()
