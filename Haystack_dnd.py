# pip install farm-haystack[all] openai

import os
from haystack.document_stores import InMemoryDocumentStore
from haystack.nodes import EmbeddingRetriever
from haystack.nodes import PromptNode, PromptTemplate
from haystack.pipelines import Pipeline
from haystack import Document
import openai

# ====== SETUP ======
openai.api_key = os.getenv("OPENAI_API_KEY")

# Store your SRD & lore text file paths here
DOC_PATHS = [
    "data/dnd_srd_combat.txt",
    "data/dnd_srd_ability_checks.txt",
    "data/example_scenarios.txt",
    "data/stormlight_lore.txt"
]

# ====== 1. LOAD DOCUMENTS ======
docs = []
for path in DOC_PATHS:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    # Chunk manually (Haystack also has splitters)
    chunks = [text[i:i+800] for i in range(0, len(text), 800)]
    for chunk in chunks:
        docs.append(Document(content=chunk))

# ====== 2. INIT DOCUMENT STORE & RETRIEVER ======
document_store = InMemoryDocumentStore(embedding_dim=1536)  # match OpenAI dimensions

retriever = EmbeddingRetriever(
    document_store=document_store,
    embedding_model="text-embedding-ada-002",  # OpenAI embeddings
    api_key=openai.api_key
)

document_store.write_documents(docs)
document_store.update_embeddings(retriever)

# ====== 3. PROMPT NODE ======
scenario_prompt = PromptTemplate(
    name="stormlight_dnd_scenario",
    prompt_text="""
You are a Dungeon Master combining Dungeons & Dragons rules with Stormlight Archive lore.
Use the retrieved context to create a playable D&D scenario.

Context:
{join(documents)}

Include:
1. Scene description in Stormlight style
2. Initial situation and conflict
3. Enemies/NPCs with stats
4. Victory/defeat conditions
5. Special environmental effects
"""
)

prompt_node = PromptNode(
    model_name="gpt-4o-mini",   # LLM for scenario generation
    api_key=openai.api_key,
    default_prompt_template=scenario_prompt
)

# ====== 4. PIPELINE ======
pipe = Pipeline()
pipe.add_node(component=retriever, name="Retriever", inputs=["Query"])
pipe.add_node(component=prompt_node, name="PromptNode", inputs=["Retriever"])

# ====== 5. RUN ======
query = "Generate a Stormlight Archive inspired D&D combat encounter"
result = pipe.run(query=query, params={"Retriever": {"top_k": 5}})
print("\n=== GENERATED SCENARIO ===\n")
print(result["results"][0])
