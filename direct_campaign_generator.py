"""
Direct Campaign Generator using Qdrant
Generates D&D campaigns by directly querying Qdrant documents and using Claude
"""
import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime

# Set tokenizers parallelism to avoid fork warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Direct Qdrant and embedding imports
from qdrant_client import QdrantClient
from haystack.components.embedders import SentenceTransformersTextEmbedder
from haystack import Document

# Claude-specific imports
try:
    from hwtgenielib import component
    from hwtgenielib.components.generators.chat import AppleGenAIChatGenerator
    from hwtgenielib.dataclasses import ChatMessage
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False
    def component(cls):
        return cls

class DirectCampaignGenerator:
    """D&D Campaign Generator using direct Qdrant access"""
    
    def __init__(self, collection_name: str = "dnd_documents", 
                 host: str = "localhost", port: int = 6333, verbose: bool = False):
        """
        Initialize the Direct Campaign Generator
        
        Args:
            collection_name: Qdrant collection name for D&D documents
            host: Qdrant host
            port: Qdrant port
            verbose: Enable verbose output
        """
        self.collection_name = collection_name
        self.host = host
        self.port = port
        self.verbose = verbose
        self.current_campaign: Dict[str, Any] = {}
        
        # Initialize components
        self.qdrant_client = None
        self.embedder = None
        self.chat_generator = None
        
        self._initialize_components()
        
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
    
    def _initialize_components(self):
        """Initialize Qdrant client, embedder, and Claude generator"""
        try:
            # Initialize Qdrant client
            self.qdrant_client = QdrantClient(host=self.host, port=self.port)
            
            # Test connection
            collections = self.qdrant_client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if self.collection_name not in collection_names:
                raise ValueError(f"Collection '{self.collection_name}' not found. Available: {collection_names}")
            
            if self.verbose:
                print(f"✓ Connected to Qdrant collection: {self.collection_name}")
                
            # Initialize embedder
            self.embedder = SentenceTransformersTextEmbedder(
                model="sentence-transformers/all-MiniLM-L6-v2"
            )
            self.embedder.warm_up()
            
            if self.verbose:
                print("✓ Text embedder initialized")
            
            # Initialize Claude generator if available
            if CLAUDE_AVAILABLE:
                self.chat_generator = AppleGenAIChatGenerator(
                    model="aws:anthropic.claude-sonnet-4-20250514-v1:0"
                )
                if self.verbose:
                    print("✓ Claude generator initialized")
            else:
                if self.verbose:
                    print("⚠️  Claude not available")
                    
        except Exception as e:
            if self.verbose:
                print(f"❌ Initialization failed: {e}")
            raise
    
    def search_documents(self, query: str, limit: int = 10) -> List[Document]:
        """Search for documents in Qdrant using semantic similarity"""
        if not self.qdrant_client or not self.embedder:
            return []
        
        try:
            # Create query embedding
            embedding_result = self.embedder.run(text=query)
            query_embedding = embedding_result["embedding"]
            
            # Search in Qdrant
            search_result = self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=limit
            )
            
            # Convert to Haystack Documents
            documents = []
            for point in search_result:
                doc = Document(
                    content=point.payload.get("content", ""),
                    meta={
                        "source_file": point.payload.get("source_file", "Unknown"),
                        "document_tag": point.payload.get("document_tag", "Unknown"),
                        "score": point.score
                    }
                )
                documents.append(doc)
            
            if self.verbose:
                print(f"Found {len(documents)} documents for query: {query[:50]}...")
            
            return documents
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Document search failed: {e}")
            return []
    
    def get_campaign_context(self, user_prompt: str) -> Dict[str, List[Document]]:
        """Get contextual documents for campaign generation"""
        context = {}
        
        # Search for different types of relevant content
        searches = {
            "campaigns": f"campaign adventure story plot {user_prompt}",
            "rules": "D&D rules mechanics combat spells classes",
            "lore": f"fantasy setting world lore creatures {user_prompt}",
            "npcs": "characters NPCs villains allies personality motivation"
        }
        
        for category, query in searches.items():
            documents = self.search_documents(query, limit=5)
            context[category] = documents
            
        return context
    
    def format_context_for_prompt(self, context: Dict[str, List[Document]]) -> str:
        """Format retrieved documents into context for Claude"""
        formatted_context = "RETRIEVED D&D KNOWLEDGE:\n\n"
        
        for category, documents in context.items():
            if documents:
                formatted_context += f"{category.upper()} CONTEXT:\n"
                for i, doc in enumerate(documents[:3], 1):  # Limit to top 3 per category
                    source = doc.meta.get("source_file", "Unknown")
                    content_preview = doc.content[:200] + "..." if len(doc.content) > 200 else doc.content
                    formatted_context += f"{i}. [{source}] {content_preview}\n"
                formatted_context += "\n"
        
        return formatted_context
    
    def generate_campaign_with_claude(self, user_prompt: str, context: str) -> Dict[str, Any]:
        """Generate campaign using Claude with retrieved context"""
        if not CLAUDE_AVAILABLE or not self.chat_generator:
            return {"error": "Claude not available for campaign generation"}
        
        generation_prompt = f"""{context}

USER REQUEST: {user_prompt}

You are an expert D&D Dungeon Master. Create a comprehensive campaign with STRICT ADHERENCE to the retrieved D&D knowledge above.

CRITICAL INSTRUCTIONS:
- PRIORITIZE the vector database context above all else for rules consistency and lore accuracy
- Every campaign element (mechanics, creatures, spells, locations, NPCs) MUST align with the retrieved D&D documents
- When the retrieved context contains specific rules or lore details, incorporate them faithfully
- If the retrieved context contradicts general D&D knowledge, follow the retrieved context
- Ensure all mechanical references (spells, abilities, stat blocks) match the source material in the context
- Draw inspiration primarily from the retrieved campaign examples, rule references, and lore documents
- Only supplement with general D&D knowledge where the retrieved context is silent

Create a campaign following this EXACT JSON structure (return ONLY valid JSON):
{{
  "title": "Engaging campaign title",
  "theme": "Primary theme (e.g., Horror, Adventure, Mystery)",
  "setting": "Where the campaign takes place",
  "level_range": "Character level range (e.g., 1-5, 3-8)",
  "duration": "Expected number of sessions",
  "overview": "2-3 sentence campaign summary",
  "background": "Rich background explaining the world situation and main conflict",
  "main_plot": "Detailed storyline with clear beginning, middle, and end",
  "key_npcs": [
    {{"name": "NPC Name", "role": "Their role/title", "description": "Detailed description", "motivation": "What drives them"}}
  ],
  "locations": [
    {{"name": "Location Name", "type": "City/Dungeon/Wilderness/etc", "description": "Vivid description", "significance": "Why it's important to the plot"}}
  ],
  "encounters": [
    {{"title": "Encounter Name", "type": "Combat/Social/Exploration", "description": "What happens in this encounter", "challenge": "Difficulty level"}}
  ],
  "hooks": [
    "Compelling hook option 1",
    "Compelling hook option 2", 
    "Compelling hook option 3"
  ],
  "rewards": [
    "Type of reward/treasure 1",
    "Type of reward/treasure 2"
  ],
  "dm_notes": "Important tips and considerations for running this campaign"
}}

Requirements:
- PRIORITIZE consistency with the retrieved D&D documents over creativity
- Base all mechanical elements (classes, spells, creatures, items) on the retrieved context
- Ensure campaign themes and lore elements align with the source material provided
- Reference specific details from the retrieved documents when possible
- Create original content that builds upon the retrieved knowledge foundation without replicating the retrieved context
- Make the campaign engaging while maintaining strict adherence to source material
- Include specific, actionable details for a DM that match official D&D 5e rules and content
- Ensure all JSON fields contain meaningful content consistent with retrieved sources

Return ONLY the JSON object, no other text."""

        try:
            # Convert prompt to ChatMessage
            messages = [ChatMessage.from_user(generation_prompt)]
            
            # Generate response
            result = self.chat_generator.run(messages=messages)
            
            if not result or "replies" not in result or not result["replies"]:
                return {"error": "No response from Claude"}
            
            response_text = result["replies"][0].text
            
            # Extract and parse JSON
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            
            if start == -1 or end == 0:
                if self.verbose:
                    print(f"DEBUG: No JSON found in response: {response_text[:200]}...")
                return {"error": "No valid JSON in Claude response"}
            
            json_str = response_text[start:end]
            campaign_data = json.loads(json_str)
            
            # Add metadata
            campaign_data["generated_on"] = datetime.now().isoformat()
            campaign_data["user_prompts"] = [user_prompt]
            
            return campaign_data
            
        except json.JSONDecodeError as e:
            if self.verbose:
                print(f"DEBUG: JSON parsing failed: {e}")
                print(f"Response: {response_text[:300]}...")
            return {"error": f"Invalid JSON from Claude: {e}"}
        except Exception as e:
            if self.verbose:
                print(f"DEBUG: Generation failed: {e}")
            return {"error": f"Campaign generation failed: {e}"}
    
    def generate_campaign(self, user_prompt: str) -> Dict[str, Any]:
        """
        Generate a new campaign based on user prompt and document knowledge
        
        Args:
            user_prompt: User's description of desired campaign
            
        Returns:
            Generated campaign dictionary
        """
        if not CLAUDE_AVAILABLE:
            return {"error": "Claude integration required for campaign generation"}
        
        try:
            # Get relevant documents
            context = self.get_campaign_context(user_prompt)
            
            # Format context for Claude
            formatted_context = self.format_context_for_prompt(context)
            
            # Generate campaign
            campaign = self.generate_campaign_with_claude(user_prompt, formatted_context)
            
            if "error" not in campaign:
                self.current_campaign = campaign
                if self.verbose:
                    print("✓ Campaign generated successfully")
            
            return campaign
            
        except Exception as e:
            return {"error": f"Campaign generation failed: {e}"}
    
    def refine_campaign(self, refinement_prompt: str) -> Dict[str, Any]:
        """Refine the current campaign based on user feedback"""
        if not self.current_campaign:
            return {"error": "No current campaign to refine. Generate a campaign first."}
        
        if not CLAUDE_AVAILABLE or not self.chat_generator:
            return {"error": "Claude not available for campaign refinement"}
        
        # Get additional context for refinement
        context = self.get_campaign_context(refinement_prompt)
        formatted_context = self.format_context_for_prompt(context)
        
        refinement_prompt_text = f"""{formatted_context}

CURRENT CAMPAIGN:
{json.dumps(self.current_campaign, indent=2)}

USER REFINEMENT REQUEST: {refinement_prompt}

Modify the campaign to incorporate the user's feedback while maintaining coherence and quality.
Return the complete updated campaign in the same JSON format.

Return ONLY the updated JSON object, no other text."""

        try:
            messages = [ChatMessage.from_user(refinement_prompt_text)]
            result = self.chat_generator.run(messages=messages)
            
            if not result or "replies" not in result or not result["replies"]:
                return {"error": "No response from Claude"}
            
            response_text = result["replies"][0].text
            
            # Extract and parse JSON
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            
            if start == -1 or end == 0:
                return {"error": "No valid JSON in refinement response"}
            
            json_str = response_text[start:end]
            refined_campaign = json.loads(json_str)
            
            # Update metadata
            refined_campaign["generated_on"] = self.current_campaign.get("generated_on", "")
            refined_campaign["user_prompts"] = self.current_campaign.get("user_prompts", []) + [refinement_prompt]
            
            self.current_campaign = refined_campaign
            
            if self.verbose:
                print("✓ Campaign refined successfully")
            
            return refined_campaign
            
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON in refinement: {e}"}
        except Exception as e:
            return {"error": f"Campaign refinement failed: {e}"}
    
    def get_campaign_suggestions(self, theme: str = "") -> List[str]:
        """Get campaign suggestions based on available knowledge"""
        if not CLAUDE_AVAILABLE or not self.chat_generator:
            return ["Claude not available for suggestions"]
        
        # Search for inspiration
        query = f"campaign ideas adventure themes {theme}" if theme else "campaign adventure examples"
        documents = self.search_documents(query, limit=5)
        
        context = "INSPIRATION FROM D&D DOCUMENTS:\n"
        for doc in documents:
            source = doc.meta.get("source_file", "Unknown")
            content_preview = doc.content[:150] + "..." if len(doc.content) > 150 else doc.content
            context += f"[{source}] {content_preview}\n"
        
        prompt = f"""{context}

Generate 5 diverse and creative D&D campaign suggestions.
{f'Focus on themes related to: {theme}' if theme else ''}

Provide variety in:
- Themes (horror, adventure, mystery, political intrigue, etc.)
- Settings (urban, wilderness, planar, underwater, etc.)
- Level ranges and campaign styles

Format as a numbered list, each suggestion in 1-2 sentences.
Be creative and inspiring while staying true to D&D concepts."""

        try:
            messages = [ChatMessage.from_user(prompt)]
            result = self.chat_generator.run(messages=messages)
            
            if not result or "replies" not in result or not result["replies"]:
                return ["Error getting suggestions from Claude"]
            
            response = result["replies"][0].text
            
            # Parse suggestions
            suggestions = []
            lines = response.split('\n')
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
            
            return suggestions[:5] if suggestions else ["No suggestions generated"]
            
        except Exception as e:
            return [f"Error generating suggestions: {e}"]
    
    def save_campaign(self, filename: str) -> bool:
        """Save current campaign to JSON file"""
        if not self.current_campaign:
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
    
    def generate_location_floorplan(self, location: Dict[str, Any]) -> str:
        """Generate ASCII floorplan for a location using Claude"""
        if not CLAUDE_AVAILABLE or not self.chat_generator:
            return "Floorplan generation requires Claude integration"
        
        location_name = location.get('name', 'Unknown Location')
        location_type = location.get('type', 'Unknown')
        location_desc = location.get('description', 'No description')
        
        floorplan_prompt = f"""Create a simple ASCII art floorplan for this D&D location:

Location: {location_name}
Type: {location_type}
Description: {location_desc}

Generate a floorplan using these ASCII characters:
- # for walls
- . for floor/walkable space
- + for doors
- ~ for water
- ^ for stairs/elevation changes
- @ for important features/objects
- T for tables/furniture
- X for traps/hazards

Requirements:
- Maximum 25 characters wide, 15 characters tall
- Include a legend explaining symbols used
- Make it practical for D&D gameplay
- Show room layout, entrances, and key features

Return only the ASCII floorplan with legend, no other text."""

        try:
            messages = [ChatMessage.from_user(floorplan_prompt)]
            result = self.chat_generator.run(messages=messages)
            
            if not result or "replies" not in result or not result["replies"]:
                return "Error generating floorplan"
            
            floorplan = result["replies"][0].text
            return floorplan
            
        except Exception as e:
            return f"Error generating floorplan: {e}"
    
    def export_to_vector_text(self, filename: str) -> bool:
        """Export campaign to structured text file for vector database parsing"""
        if not self.current_campaign:
            if self.verbose:
                print("No campaign to export")
            return False
        
        try:
            campaign = self.current_campaign
            
            with open(filename, 'w', encoding='utf-8') as f:
                # Write metadata header
                f.write("=== CAMPAIGN METADATA ===\n")
                f.write(f"DOCUMENT_TYPE: D&D_Campaign\n")
                f.write(f"TITLE: {campaign.get('title', 'Untitled')}\n")
                f.write(f"THEME: {campaign.get('theme', 'Unknown')}\n")
                f.write(f"SETTING: {campaign.get('setting', 'Unknown')}\n")
                f.write(f"LEVEL_RANGE: {campaign.get('level_range', 'Unknown')}\n")
                f.write(f"GENERATED_ON: {campaign.get('generated_on', 'Unknown')}\n")
                f.write(f"SOURCE: Campaign_Generator\n\n")
                
                # Campaign Overview (chunk 1)
                f.write("=== CAMPAIGN OVERVIEW ===\n")
                f.write(f"CHUNK_TYPE: Overview\n")
                f.write(f"CAMPAIGN: {campaign.get('title', 'Untitled')}\n")
                f.write(f"{campaign.get('overview', 'No overview available')}\n\n")
                
                # Background (chunk 2)
                f.write("=== CAMPAIGN BACKGROUND ===\n")
                f.write(f"CHUNK_TYPE: Background\n")
                f.write(f"CAMPAIGN: {campaign.get('title', 'Untitled')}\n")
                f.write(f"{campaign.get('background', 'No background available')}\n\n")
                
                # Main Plot (chunk 3)
                f.write("=== MAIN PLOT ===\n")
                f.write(f"CHUNK_TYPE: Plot\n")
                f.write(f"CAMPAIGN: {campaign.get('title', 'Untitled')}\n")
                f.write(f"{campaign.get('main_plot', 'No plot available')}\n\n")
                
                # NPCs (individual chunks)
                for i, npc in enumerate(campaign.get('key_npcs', []), 1):
                    f.write(f"=== NPC: {npc.get('name', f'NPC_{i}')} ===\n")
                    f.write(f"CHUNK_TYPE: NPC\n")
                    f.write(f"CAMPAIGN: {campaign.get('title', 'Untitled')}\n")
                    f.write(f"NPC_NAME: {npc.get('name', 'Unknown')}\n")
                    f.write(f"NPC_ROLE: {npc.get('role', 'Unknown')}\n")
                    f.write(f"DESCRIPTION: {npc.get('description', 'No description')}\n")
                    f.write(f"MOTIVATION: {npc.get('motivation', 'Unknown motivation')}\n\n")
                
                # Locations with floorplans (individual chunks)
                for i, location in enumerate(campaign.get('locations', []), 1):
                    f.write(f"=== LOCATION: {location.get('name', f'Location_{i}')} ===\n")
                    f.write(f"CHUNK_TYPE: Location\n")
                    f.write(f"CAMPAIGN: {campaign.get('title', 'Untitled')}\n")
                    f.write(f"LOCATION_NAME: {location.get('name', 'Unknown')}\n")
                    f.write(f"LOCATION_TYPE: {location.get('type', 'Unknown')}\n")
                    f.write(f"DESCRIPTION: {location.get('description', 'No description')}\n")
                    f.write(f"SIGNIFICANCE: {location.get('significance', 'Unknown significance')}\n")
                    
                    # Generate and include floorplan
                    if self.verbose:
                        print(f"Generating floorplan for {location.get('name', 'location')}...")
                    floorplan = self.generate_location_floorplan(location)
                    f.write(f"FLOORPLAN:\n{floorplan}\n\n")
                
                # Encounters (individual chunks)
                for i, encounter in enumerate(campaign.get('encounters', []), 1):
                    f.write(f"=== ENCOUNTER: {encounter.get('title', f'Encounter_{i}')} ===\n")
                    f.write(f"CHUNK_TYPE: Encounter\n")
                    f.write(f"CAMPAIGN: {campaign.get('title', 'Untitled')}\n")
                    f.write(f"ENCOUNTER_TITLE: {encounter.get('title', 'Unknown')}\n")
                    f.write(f"ENCOUNTER_TYPE: {encounter.get('type', 'Unknown')}\n")
                    f.write(f"DESCRIPTION: {encounter.get('description', 'No description')}\n")
                    f.write(f"CHALLENGE: {encounter.get('challenge', 'Unknown difficulty')}\n\n")
                
                # Campaign Hooks (chunk)
                f.write("=== CAMPAIGN HOOKS ===\n")
                f.write(f"CHUNK_TYPE: Hooks\n")
                f.write(f"CAMPAIGN: {campaign.get('title', 'Untitled')}\n")
                for i, hook in enumerate(campaign.get('hooks', []), 1):
                    f.write(f"HOOK_{i}: {hook}\n")
                f.write("\n")
                
                # Rewards (chunk)
                f.write("=== CAMPAIGN REWARDS ===\n")
                f.write(f"CHUNK_TYPE: Rewards\n")
                f.write(f"CAMPAIGN: {campaign.get('title', 'Untitled')}\n")
                for i, reward in enumerate(campaign.get('rewards', []), 1):
                    f.write(f"REWARD_{i}: {reward}\n")
                f.write("\n")
                
                # DM Notes (chunk)
                f.write("=== DM NOTES ===\n")
                f.write(f"CHUNK_TYPE: DM_Notes\n")
                f.write(f"CAMPAIGN: {campaign.get('title', 'Untitled')}\n")
                f.write(f"{campaign.get('dm_notes', 'No DM notes available')}\n\n")
                
                # User Prompts History (chunk)
                f.write("=== GENERATION HISTORY ===\n")
                f.write(f"CHUNK_TYPE: Generation_History\n")
                f.write(f"CAMPAIGN: {campaign.get('title', 'Untitled')}\n")
                for i, prompt in enumerate(campaign.get('user_prompts', []), 1):
                    f.write(f"PROMPT_{i}: {prompt}\n")
                f.write("\n")
            
            if self.verbose:
                print(f"✓ Campaign exported to {filename} for vector database parsing")
            return True
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Failed to export campaign: {e}")
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


def run_direct_campaign_generator():
    """Interactive campaign generator interface"""
    print("=== Direct D&D Campaign Generator ===")
    print("Generate campaigns using direct Qdrant document access!")
    print()
    
    # Get collection name
    collection_name = input("Enter Qdrant collection name (default: dnd_documents): ").strip()
    if not collection_name:
        collection_name = "dnd_documents"
    
    # Initialize generator
    print("Initializing direct campaign generator...")
    try:
        generator = DirectCampaignGenerator(collection_name=collection_name, verbose=True)
    except Exception as e:
        print(f"❌ Failed to initialize generator: {e}")
        return
    
    if not CLAUDE_AVAILABLE:
        print("❌ Claude not available. Campaign generation requires Claude integration.")
        return
    
    print("\nCommands:")
    print("  'generate <prompt>' - Generate new campaign")
    print("  'refine <prompt>' - Refine current campaign")
    print("  'suggestions [theme]' - Get campaign suggestions")
    print("  'summary' - Show current campaign summary")
    print("  'save <filename>' - Save current campaign")
    print("  'load <filename>' - Load campaign")
    print("  'export <filename>' - Export to text file with floorplans for vector DB")
    print("  'quit' - Exit")
    print()
    
    while True:
        try:
            user_input = input("Direct Generator> ").strip()
            
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
                    print("Please provide a campaign prompt. Example: generate a horror campaign in a haunted mansion")
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
                    print("Please provide refinement details. Example: refine add more political elements")
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
            
            elif command == 'export':
                filename = parts[1] if len(parts) > 1 else f"{generator.current_campaign.get('title', 'campaign').replace(' ', '_').lower()}_vectordb.txt"
                if not generator.current_campaign:
                    print("❌ No campaign to export. Generate a campaign first.")
                    continue
                    
                print(f"Exporting campaign with floorplans to {filename}...")
                print("This may take a few moments to generate floorplans...")
                
                if generator.export_to_vector_text(filename):
                    print(f"✓ Campaign exported to {filename} for vector database parsing")
                else:
                    print("❌ Failed to export campaign")
            
            else:
                print(f"Unknown command: {command}")
                print("Available commands: generate, refine, suggestions, summary, save, load, export, quit")
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")


if __name__ == "__main__":
    run_direct_campaign_generator()