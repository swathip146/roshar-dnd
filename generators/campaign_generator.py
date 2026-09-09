"""
Campaign Generator using RAG Agent
Generates D&D campaigns by leveraging existing campaigns, rules, and lore from the knowledge base
"""
import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime

# agents/haystack_pipeline_agent.py DOES NOT EXIST — this module has been
# unimportable, which is why the D1 `dnd_reference` collection had no working
# consumer. The agent was only ever used to fetch RAG context, so make it
# optional and fall back to querying the reference collection directly.
try:
    from agents.haystack_pipeline_agent import HaystackPipelineAgent  # type: ignore
    HAYSTACK_AGENT_AVAILABLE = True
except ImportError:
    HaystackPipelineAgent = None  # type: ignore
    HAYSTACK_AGENT_AVAILABLE = False

# Gemini-specific imports
try:
    from config.llm_utils import GeminiChatGenerator
    from haystack.dataclasses import ChatMessage
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

class CampaignGenerator:
    """D&D Campaign Generator using RAG-enhanced context"""
    
    def __init__(self, collection_name: str = "dnd_documents", verbose: bool = False):
        """
        Initialize the Campaign Generator
        
        Args:
            collection_name: Qdrant collection name for D&D documents
            verbose: Enable verbose output
        """
        self.verbose = verbose
        self.haystack_agent: Optional[HaystackPipelineAgent] = None
        self.current_campaign: Dict[str, Any] = {}
        
        # Initialize Haystack agent
        self._initialize_haystack_agent(collection_name)
        
        # Campaign template structure
        self.campaign_template = {
            "title": "",
            "theme": "",
            "setting": "",
            "level_range": "1-5",
            "duration": "4-6 sessions",
            "overview": "",
            "background": "",
            "main_plot": "",
            "key_npcs": [],
            "locations": [],
            "encounters": [],
            "hooks": [],
            "rewards": [],
            "dm_notes": "",
            "generated_on": "",
            "user_prompts": []
        }
    
    def _initialize_haystack_agent(self, collection_name: str) -> bool:
        """Initialize the Haystack agent for context retrieval"""
        try:
            if not HAYSTACK_AGENT_AVAILABLE:
                # No pipeline agent: retrieve straight from the collection.
                self.haystack_agent = None
                self._init_direct_retriever(collection_name)
                return self._retriever is not None
            self.haystack_agent = HaystackPipelineAgent(collection_name=collection_name, verbose=self.verbose)
            if self.verbose:
                print("✓ Haystack Agent initialized successfully")
            return True
        except Exception as e:
            if self.verbose:
                print(f"❌ Failed to initialize Haystack agent: {e}")
            return False
    
    def _init_direct_retriever(self, collection_name: str) -> None:
        """
        Retrieve from Qdrant directly (plan D1).

        The campaign generator reads `dnd_reference` — adventure modules and
        character sheets — for STRUCTURAL few-shots: how a hook opens, how acts
        escalate, how a campaign closes. That collection exists precisely so this
        content never pollutes the DM's `dnd_documents`.
        """
        self._retriever = None
        self._embedder = None
        try:
            from haystack.components.embedders import SentenceTransformersTextEmbedder
            from haystack_integrations.document_stores.qdrant import QdrantDocumentStore
            from haystack_integrations.components.retrievers.qdrant import (
                QdrantEmbeddingRetriever,
            )

            store = QdrantDocumentStore(path="qdrant_storage",
                                        index=collection_name,
                                        embedding_dim=1024)
            self._embedder = SentenceTransformersTextEmbedder(
                model="BAAI/bge-large-en-v1.5", progress_bar=False
            )
            self._embedder.warm_up()
            self._retriever = QdrantEmbeddingRetriever(document_store=store)
            print(f"✅ Campaign generator retrieving directly from '{collection_name}'")
        except Exception as e:
            print(f"⚠️ Direct retrieval unavailable ({e}); generating without context")

    def get_campaign_context(self, query: str) -> str:
        """Get context from existing campaigns and D&D resources"""
        if self.haystack_agent is None and getattr(self, "_retriever", None) is not None:
            try:
                embedding = self._embedder.run(text=query)["embedding"]
                docs = self._retriever.run(query_embedding=embedding, top_k=5)["documents"]
                return "\n\n".join(d.content for d in docs)
            except Exception as e:
                return f"Error retrieving context for: {query} ({e})"

        if not self.haystack_agent:
            return f"Haystack agent not available. Basic context for: {query}"
        
        try:
            response = self.haystack_agent.send_message_and_wait("haystack_pipeline", "query", {
                "query": query,
                "context": "campaign generation"
            }, timeout=30.0)
            
            if response and response.get("success"):
                result = response.get("result", {})
                return result.get("answer", f"No context found for: {query}")
            else:
                return f"Error retrieving context for: {query}"
        except Exception as e:
            return f"Error getting context: {e}"
    
    def generate_campaign(self, user_prompt: str) -> Dict[str, Any]:
        """
        Generate a new campaign based on user prompt and existing campaign knowledge

        Args:
            user_prompt: User's description of desired campaign

        Returns:
            Generated campaign dictionary
        """
        if not GEMINI_AVAILABLE:
            return {"error": "Haystack agent or Gemini not available for campaign generation"}
        
        # Get context from existing documents - use broader queries to find relevant content
        rules_context = self.get_campaign_context(
            f"D&D rules, mechanics, character classes, combat"
        )
        
        lore_context = self.get_campaign_context(
            f"fantasy settings, locations, creatures, magic {user_prompt}"
        )
        
        # Generate comprehensive campaign using Gemini with fallback approach
        generation_query = f"""You are an expert D&D Dungeon Master creating a complete campaign. Use your D&D knowledge to create an engaging campaign.

AVAILABLE D&D KNOWLEDGE (reference if relevant):
Rules Context: {rules_context[:500] if rules_context and not rules_context.startswith('<REJECT>') else 'Use standard D&D 5e rules'}

Lore Context: {lore_context[:500] if lore_context and not lore_context.startswith('<REJECT>') else 'Use standard fantasy tropes'}

USER REQUEST:
{user_prompt}

Create a comprehensive D&D campaign following this exact JSON structure:
{{
  "title": "Campaign title",
  "theme": "Main theme/genre",
  "setting": "Where the campaign takes place",
  "level_range": "Character level range (e.g., 1-5)",
  "duration": "Expected session count",
  "overview": "2-3 sentence campaign summary",
  "background": "Rich background explaining the world situation and conflict",
  "main_plot": "Detailed main storyline with beginning, middle, and end",
  "key_npcs": [
    {{"name": "NPC Name", "role": "Their role", "description": "2-3 sentence description", "motivation": "What drives them"}}
  ],
  "locations": [
    {{"name": "Location Name", "type": "City/Dungeon/Wilderness", "description": "Vivid description", "significance": "Why it's important"}}
  ],
  "encounters": [
    {{"id": "stable_snake_case_id", "title": "Encounter Name", "type": "Combat/Social/Exploration",
      "act": "act1", "quest": "quest_id_this_belongs_to", "location": "Location Name",
      "description": "What happens", "challenge": "Prose difficulty note",
      "difficulty": "easy|medium|hard|deadly",
      "trigger": {{"keywords": ["words that appear when this scene occurs"], "location": "Location Name", "quest_pending": "quest_id"}},
      "enemies": [
        {{"name": "Enemy Name", "count": 2, "estimated_cr": 0.5, "role": "skirmisher|soldier|caster|boss",
          "description": "What it looks like and how it fights", "keywords": ["tag", "tag"]}}
      ],
      "victory": {{"quest_objective": "exact objective text this completes", "xp": 100}}}}
  ],
  "hooks": [
    "Campaign hook option 1",
    "Campaign hook option 2",
    "Campaign hook option 3"
  ],
  "rewards": [
    "Reward/treasure type 1",
    "Reward/treasure type 2"
  ],
  "dm_notes": "Important tips and considerations for running this campaign",

  "schema_version": "2.0",
  "acts": [
    {{"id": "act1", "title": "Act title", "sessions": [1], "summary": "What happens in this act"}}
  ],
  "quests": [
    {{"id": "stable_snake_case_id", "title": "Quest title the player sees", "act": "act1",
      "objectives": ["Concrete thing to do", "Another concrete thing"],
      "prereqs": [], "status": "pending"}}
  ],
  "endgame": {{
    "condition": {{"all_of": ["quest:final_quest_id"]}},
    "closing_narration": "The authored final beat. Written for the DM to narrate when the condition is met.",
    "failure_condition": {{"any_of": ["flag:party_wiped"]}},
    "failure_narration": "The authored ending if the party fails."
  }}
}}

Requirements:
- Create an original campaign based on the user's request
- Use standard D&D 5e mechanics and concepts
- Make the campaign internally consistent and engaging
- Include specific, actionable content for a DM to run
- Ensure all JSON fields are properly filled with meaningful content
- If the user request is vague, add creative elements to make it interesting

STRUCTURED PROGRESSION (required — plan 2.14 / decision D2):
- "quests" must be OBJECTS, not bare strings. Each needs a stable snake_case
  "id" (referenced by endgame conditions), a player-facing "title", concrete
  "objectives", and "prereqs" listing the quest ids that must finish first.
  Chain them so the campaign has a real spine: later quests depend on earlier ones.
- "acts" must cover every session in "duration".
- "endgame.condition" is REQUIRED and must be machine-checkable. The game DETECTS
  the ending from live state; the DM never decides the story is over. Use:
      "quest:<id>"          that quest is complete
      "flag:<name>"         a campaign flag is set
      "location:<name>"     the party has been there
      "ideal:<n>"           a character reached Ideal n or higher
  combined with {{"all_of": [...]}}, {{"any_of": [...]}}, {{"none_of": [...]}},
  or {{"count": {{"predicate": "artifact_*", "at_least": 3}}}} to require N of a
  wildcard group.
- Reference only quest ids you actually defined, or the ending can never fire.
- "closing_narration" is the authored ending. Write it as an instruction to the
  DM, not as final prose to print verbatim.

ENCOUNTER AUTHORING RULES (these drive real combat, so they must be mechanically sound):
- Every encounter needs an "enemies" list. An EMPTY list is meaningful and correct
  for social, exploration or puzzle encounters — it tells the engine this scene is
  deliberately not a fight. Never omit the key.
- Balance "estimated_cr" against the party level for that act, not against how
  dramatic the scene sounds. A single enemy of CR roughly equal to party level is
  a fair fight; if several enemies appear at once, each one's CR must be LOWER.
  A level 1 party facing three CR 3 enemies is unwinnable.
- Use the campaign's own level_range to judge this: early-act encounters are for
  the bottom of the range, final-act encounters for the top.
- "trigger.keywords" must be words that genuinely appear when the scene happens
  (creature names, place names, the action that starts it). They are matched
  against the narration, so generic words like "fight" or "danger" cause an
  encounter to fire at the wrong moment.
- "victory.quest_objective" must copy an objective string from "quests" EXACTLY,
  or completing the encounter will not advance the quest.
- Give every encounter a stable snake_case "id", and reference real "act" and
  "quest" ids from this same campaign.

CRITICAL: Return ONLY a valid JSON object with no additional text, explanations, or formatting. Start with {{ and end with }}.
Example format: {{"title": "Campaign Name", "theme": "Horror", "setting": "Location"}}"""

        try:
            response_data = self.haystack_agent.send_message_and_wait("haystack_pipeline", "query", {
                "query": generation_query,
                "context": "campaign generation"
            }, timeout=60.0)
            
            if not response_data or not response_data.get("success"):
                return {"error": "Failed to generate campaign using Haystack agent"}
            
            # Parse the JSON response
            result = response_data.get("result", {})
            response = result.get("answer", "")
            
            # Try multiple approaches to extract JSON
            campaign_data = None
            
            # Method 1: Look for complete JSON object
            start = response.find('{')
            end = response.rfind('}') + 1
            
            if start != -1 and end != 0:
                json_str = response[start:end]
                try:
                    campaign_data = json.loads(json_str)
                except json.JSONDecodeError:
                    pass
            
            # Method 2: If no valid JSON found, create a basic structure from response
            if campaign_data is None:
                if self.verbose:
                    print(f"DEBUG: Could not parse JSON from response: {response[:200]}...")
                
                # Fallback: create basic campaign from response text
                campaign_data = {
                    "title": "Generated Campaign",
                    "theme": "Adventure",
                    "setting": "Fantasy world",
                    "level_range": "1-5",
                    "duration": "4-6 sessions",
                    "overview": response[:200] + "..." if len(response) > 200 else response,
                    "background": "Campaign background to be developed",
                    "main_plot": response,
                    "key_npcs": [{"name": "NPC", "role": "Supporting character", "description": "Details to be added", "motivation": "Unknown"}],
                    "locations": [{"name": "Starting Location", "type": "Settlement", "description": "To be detailed", "significance": "Campaign start"}],
                    "encounters": [{
                        "id": "opening_encounter",
                        "title": "Initial Encounter",
                        "type": "Social",
                        "description": "Campaign introduction",
                        "challenge": "Easy",
                        "difficulty": "easy",
                        "trigger": {"keywords": ["arrive", "introduction"]},
                        # Empty enemies = deliberately not a fight. The key must
                        # be PRESENT: CombatInitializer only treats an encounter
                        # as authored when "enemies" exists, and falls back to
                        # LLM extraction otherwise.
                        "enemies": [],
                        "victory": {},
                    }],
                    "hooks": ["Adventure begins", "Mystery unfolds", "Conflict arises"],
                    "rewards": ["Experience", "Gold", "Magic items"],
                    "dm_notes": "Campaign generated from RAG response. Requires further development."
                }
            
            # Add metadata
            campaign_data["generated_on"] = datetime.now().isoformat()
            campaign_data["user_prompts"] = [user_prompt]
            
            # Store as current campaign
            self.current_campaign = campaign_data
            
            return campaign_data
            
        except json.JSONDecodeError as e:
            return {"error": f"Failed to parse generated campaign JSON: {e}"}
        except Exception as e:
            return {"error": f"Campaign generation failed: {e}"}
    
    def refine_campaign(self, refinement_prompt: str) -> Dict[str, Any]:
        """
        Refine the current campaign based on user feedback
        
        Args:
            refinement_prompt: User's refinement request
            
        Returns:
            Updated campaign dictionary
        """
        if not self.current_campaign:
            return {"error": "No current campaign to refine. Generate a campaign first."}

        if not GEMINI_AVAILABLE:
            return {"error": "Haystack agent or Gemini not available for campaign refinement"}
        
        # Get additional context if needed
        additional_context = self.get_campaign_context(refinement_prompt)
        
        refinement_query = f"""You are refining an existing D&D campaign based on user feedback.

CURRENT CAMPAIGN:
{json.dumps(self.current_campaign, indent=2)}

ADDITIONAL CONTEXT (if relevant):
{additional_context}

USER REFINEMENT REQUEST:
{refinement_prompt}

Modify the campaign JSON to incorporate the user's feedback. Consider:
- What specific changes they're requesting
- How to maintain campaign coherence
- Whether new NPCs, locations, or encounters are needed
- How to adjust the plot or theme accordingly

Return the complete updated campaign JSON with all fields, maintaining the same structure as the original.
Return ONLY the JSON object, no additional text."""

        try:
            response_data = self.haystack_agent.send_message_and_wait("haystack_pipeline", "query", {
                "query": refinement_query,
                "context": "campaign refinement"
            }, timeout=60.0)
            
            if not response_data or not response_data.get("success"):
                return {"error": "Failed to refine campaign using Haystack agent"}
            
            result = response_data.get("result", {})
            response = result.get("answer", "")
            
            # Extract JSON from response
            start = response.find('{')
            end = response.rfind('}') + 1
            
            if start == -1 or end == 0:
                return {"error": "Invalid response format from Gemini"}
            
            json_str = response[start:end]
            refined_campaign = json.loads(json_str)
            
            # Update metadata
            refined_campaign["generated_on"] = self.current_campaign.get("generated_on", "")
            refined_campaign["user_prompts"] = self.current_campaign.get("user_prompts", []) + [refinement_prompt]
            
            # Store as current campaign
            self.current_campaign = refined_campaign
            
            return refined_campaign
            
        except json.JSONDecodeError as e:
            return {"error": f"Failed to parse refined campaign JSON: {e}"}
        except Exception as e:
            return {"error": f"Campaign refinement failed: {e}"}
    
    def get_campaign_suggestions(self, theme: str = "") -> List[str]:
        """Get campaign suggestions based on available knowledge"""
        if self.haystack_agent is None and getattr(self, "_retriever", None) is not None:
            try:
                embedding = self._embedder.run(text=query)["embedding"]
                docs = self._retriever.run(query_embedding=embedding, top_k=5)["documents"]
                return "\n\n".join(d.content for d in docs)
            except Exception as e:
                return f"Error retrieving context for: {query} ({e})"

        if not self.haystack_agent:
            return ["Haystack agent not available for suggestions"]
        
        suggestion_query = f"""Based on available D&D campaigns and lore, suggest 5 interesting campaign concepts.
        {f'Focus on themes related to: {theme}' if theme else ''}
        
        Provide diverse suggestions covering different:
        - Themes (horror, adventure, political intrigue, etc.)
        - Settings (urban, wilderness, planar, etc.)  
        - Level ranges
        - Styles (sandbox, linear, episodic, etc.)
        
        Format as a simple numbered list of campaign concepts, each in 1-2 sentences."""
        
        try:
            response_data = self.haystack_agent.send_message_and_wait("haystack_pipeline", "query", {
                "query": suggestion_query,
                "context": "campaign suggestions"
            }, timeout=30.0)
            
            if not response_data or not response_data.get("success"):
                return ["Error getting suggestions from Haystack agent"]
            
            # Parse suggestions from response
            suggestions = []
            result = response_data.get("result", {})
            answer = result.get("answer", "")
            lines = answer.split('\n')
            for line in lines:
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith('-') or line.startswith('•')):
                    # Clean up numbering/bullets
                    clean_line = line
                    for prefix in ['1.', '2.', '3.', '4.', '5.', '-', '•']:
                        if clean_line.startswith(prefix):
                            clean_line = clean_line[len(prefix):].strip()
                            break
                    if clean_line:
                        suggestions.append(clean_line)
            
            return suggestions[:5] if suggestions else ["No suggestions available"]
            
        except Exception as e:
            return [f"Error generating suggestions: {e}"]
    
    def save_campaign(self, filename: str) -> bool:
        """Save current campaign to JSON file"""
        if not self.current_campaign:
            if self.verbose:
                print("No campaign to save")
            return False
        
        try:
            with open(filename, 'w') as f:
                json.dump(self.current_campaign, f, indent=2)
            if self.verbose:
                print(f"✓ Campaign saved to {filename}")
            return True
        except Exception as e:
            if self.verbose:
                print(f"❌ Failed to save campaign: {e}")
            return False
    
    def load_campaign(self, filename: str) -> bool:
        """Load campaign from JSON file"""
        try:
            with open(filename, 'r') as f:
                self.current_campaign = json.load(f)
            if self.verbose:
                print(f"✓ Campaign loaded from {filename}")
            return True
        except Exception as e:
            if self.verbose:
                print(f"❌ Failed to load campaign: {e}")
            return False
    
    def display_campaign_summary(self) -> str:
        """Display a formatted summary of the current campaign"""
        if not self.current_campaign:
            return "No current campaign available"
        
        campaign = self.current_campaign
        
        summary = f"""
=== {campaign.get('title', 'Untitled Campaign')} ===

🎭 Theme: {campaign.get('theme', 'N/A')}
🗺️  Setting: {campaign.get('setting', 'N/A')}
📊 Level Range: {campaign.get('level_range', 'N/A')}
⏱️  Duration: {campaign.get('duration', 'N/A')}

📖 Overview:
{campaign.get('overview', 'No overview available')}

🎯 Main Plot:
{campaign.get('main_plot', 'No plot available')[:200]}{'...' if len(campaign.get('main_plot', '')) > 200 else ''}

👥 Key NPCs: {len(campaign.get('key_npcs', []))}
📍 Locations: {len(campaign.get('locations', []))}
⚔️  Encounters: {len(campaign.get('encounters', []))}
🎣 Hooks: {len(campaign.get('hooks', []))}
"""
        return summary


def run_campaign_generator():
    """Interactive campaign generator interface"""
    print("=== D&D Campaign Generator ===")
    print("Generate campaigns using your D&D knowledge base!")
    print()
    
    # Get collection name
    collection_name = input("Enter Qdrant collection name (default: dnd_documents): ").strip()
    if not collection_name:
        collection_name = "dnd_documents"
    
    # Initialize generator
    print("Initializing campaign generator...")
    generator = CampaignGenerator(collection_name=collection_name, verbose=True)

    if not GEMINI_AVAILABLE:
        print("❌ Gemini not available. Campaign generation requires Gemini integration.")
        return
    
    print("\nCommands:")
    print("  'generate <prompt>' - Generate new campaign")
    print("  'refine <prompt>' - Refine current campaign") 
    print("  'suggestions' - Get campaign suggestions")
    print("  'summary' - Show current campaign summary")
    print("  'save <filename>' - Save current campaign")
    print("  'load <filename>' - Load campaign")
    print("  'quit' - Exit")
    print()
    
    while True:
        try:
            user_input = input("Campaign Generator> ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break
            
            if not user_input:
                print("Please enter a command.")
                continue
            
            # Parse command
            parts = user_input.split(' ', 1)
            command = parts[0].lower()
            
            if command == 'generate':
                if len(parts) < 2:
                    print("Please provide a campaign prompt. Example: generate a dark fantasy campaign in a cursed forest")
                    continue
                
                prompt = parts[1]
                print(f"Generating campaign: {prompt}")
                print("This may take a moment...")
                
                result = generator.generate_campaign(prompt)
                
                if "error" in result:
                    print(f"❌ Error: {result['error']}")
                else:
                    print("✓ Campaign generated successfully!")
                    print(generator.display_campaign_summary())
            
            elif command == 'refine':
                if len(parts) < 2:
                    print("Please provide refinement details. Example: refine add more horror elements")
                    continue
                
                refinement = parts[1]
                print(f"Refining campaign: {refinement}")
                
                result = generator.refine_campaign(refinement)
                
                if "error" in result:
                    print(f"❌ Error: {result['error']}")
                else:
                    print("✓ Campaign refined successfully!")
                    print(generator.display_campaign_summary())
            
            elif command == 'suggestions':
                theme = parts[1] if len(parts) > 1 else ""
                print("Getting campaign suggestions...")
                
                suggestions = generator.get_campaign_suggestions(theme)
                
                print("\n🎲 Campaign Suggestions:")
                print("=" * 40)
                for i, suggestion in enumerate(suggestions, 1):
                    print(f"{i}. {suggestion}")
                print()
            
            elif command == 'summary':
                print(generator.display_campaign_summary())
            
            elif command == 'save':
                filename = parts[1] if len(parts) > 1 else "campaign.json"
                if generator.save_campaign(filename):
                    print(f"✓ Campaign saved to {filename}")
                else:
                    print("❌ Failed to save campaign")
            
            elif command == 'load':
                if len(parts) < 2:
                    print("Please provide filename. Example: load my_campaign.json")
                    continue
                
                filename = parts[1]
                if generator.load_campaign(filename):
                    print(f"✓ Campaign loaded from {filename}")
                    print(generator.display_campaign_summary())
                else:
                    print(f"❌ Failed to load campaign from {filename}")
            
            else:
                print(f"Unknown command: {command}")
                print("Available commands: generate, refine, suggestions, summary, save, load, quit")
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")


if __name__ == "__main__":
    run_campaign_generator()