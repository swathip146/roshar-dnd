"""
RAG-Powered Dungeon Master Assistant with Haystack Pipeline
Integrates Haystack RAG pipeline with campaign management and DM gameplay logic
"""
import json
import random
import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path

# Set tokenizers parallelism to avoid fork warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Import existing RAG agent
from rag_agent import RAGAgent, CLAUDE_AVAILABLE

# Claude-specific imports for text condenser
try:
    from hwtgenielib import component
    from hwtgenielib.components.generators.chat import AppleGenAIChatGenerator
    from hwtgenielib.dataclasses import ChatMessage
except ImportError:
    CLAUDE_AVAILABLE = False
    def component(cls):
        return cls

import warnings
warnings.filterwarnings("ignore")

# Helper function for text condensing
def condense_text(text: str, max_length: int = 800) -> str:
    """Condense text using Claude if available, otherwise truncate."""
    if not CLAUDE_AVAILABLE or len(text) <= max_length:
        return text[:max_length] + "..." if len(text) > max_length else text
    
    try:
        condense_prompt = f"""Condense and summarize the following text while preserving key information:

Text to condense:
{text}

Requirements:
- Keep it under {max_length} characters
- Preserve essential facts and details
- Maintain clarity and readability
- Focus on actionable information

Condensed version:"""
        
        chat_generator = AppleGenAIChatGenerator(
            model="aws:anthropic.claude-sonnet-4-20250514-v1:0"
        )
        messages = [ChatMessage.from_user(condense_prompt)]
        result = chat_generator.run(messages=messages)
        
        if result and "replies" in result and result["replies"]:
            return result["replies"][0].text
        else:
            return text[:max_length] + "..." if len(text) > max_length else text
    except Exception:
        return text[:max_length] + "..." if len(text) > max_length else text

# Campaign Data Classes
@dataclass
class Player:
    """Represents a player character in the game."""
    name: str
    race: str
    character_class: str
    level: int
    background: str
    rulebook: str
    ability_scores: Dict[str, int] = field(default_factory=dict)
    combat_stats: Dict[str, Any] = field(default_factory=dict)
    features_and_traits: List[str] = field(default_factory=list)
    equipment: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    spells: List[str] = field(default_factory=list)
    personality: Dict[str, str] = field(default_factory=dict)
    backstory: str = ""
    build_summary: str = ""
    game_state: Dict[str, Any] = field(default_factory=lambda: {
        "current_hp": 0,
        "max_hp": 0,
        "status_effects": [],
        "inventory": [],
        "location": "",
        "notes": ""
    })
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Player to JSON-serializable dictionary."""
        return asdict(self)

@dataclass
class CampaignNPC:
    """Represents an NPC in a campaign."""
    name: str
    role: str
    description: str
    motivation: str
    stats: Dict[str, Any] = field(default_factory=dict)

@dataclass
class CampaignLocation:
    """Represents a location in a campaign."""
    name: str
    location_type: str
    description: str
    significance: str
    floorplan: Optional[str] = None

@dataclass
class CampaignEncounter:
    """Represents an encounter in a campaign."""
    title: str
    encounter_type: str
    description: str
    challenge: str

@dataclass
class Campaign:
    """Represents a complete D&D campaign."""
    title: str
    theme: str
    setting: str
    level_range: str
    overview: str
    background: str
    main_plot: str
    npcs: List[CampaignNPC] = field(default_factory=list)
    locations: List[CampaignLocation] = field(default_factory=list)
    encounters: List[CampaignEncounter] = field(default_factory=list)
    hooks: List[str] = field(default_factory=list)
    rewards: List[str] = field(default_factory=list)
    dm_notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

class PlayerLoader:
    """Loads player characters from text files."""
    
    @staticmethod
    def load_from_file(file_path: Path) -> Optional[Player]:
        """Load a player character from a text file."""
        try:
            if not file_path.exists():
                return None
            
            content = file_path.read_text(encoding='utf-8')
            return PlayerLoader._parse_player_text(content)
        except Exception as e:
            print(f"Error loading player from {file_path}: {e}")
            return None
    
    @staticmethod
    def _parse_player_text(content: str) -> Player:
        """Parse player character from text format."""
        lines = content.split('\n')
        player_data = {
            "name": "",
            "race": "",
            "character_class": "",
            "level": 1,
            "background": "",
            "rulebook": "",
            "ability_scores": {},
            "combat_stats": {},
            "features_and_traits": [],
            "equipment": [],
            "skills": [],
            "spells": [],
            "personality": {},
            "backstory": "",
            "build_summary": ""
        }
        
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Parse basic information
            if line.startswith("Name:"):
                player_data["name"] = line.replace("Name:", "").strip()
            elif line.startswith("Race:"):
                player_data["race"] = line.replace("Race:", "").strip()
            elif line.startswith("Class:"):
                player_data["character_class"] = line.replace("Class:", "").strip()
            elif line.startswith("Level:"):
                try:
                    player_data["level"] = int(line.replace("Level:", "").strip())
                except ValueError:
                    player_data["level"] = 1
            elif line.startswith("Background:"):
                player_data["background"] = line.replace("Background:", "").strip()
            elif line.startswith("Rulebook:"):
                player_data["rulebook"] = line.replace("Rulebook:", "").strip()
            
            # Parse ability scores
            elif ":" in line and any(ability in line for ability in ["Strength", "Dexterity", "Constitution", "Intelligence", "Wisdom", "Charisma"]):
                parts = line.split(":")
                if len(parts) == 2:
                    ability = parts[0].strip()
                    score_text = parts[1].strip()
                    # Extract number from format like "8 (modifier: -1)"
                    try:
                        score = int(score_text.split()[0])
                        player_data["ability_scores"][ability.lower()] = score
                    except (ValueError, IndexError):
                        pass
            
            # Parse combat stats
            elif line.startswith("Hit Points:"):
                try:
                    hp = int(line.replace("Hit Points:", "").strip())
                    player_data["combat_stats"]["hit_points"] = hp
                except ValueError:
                    pass
            elif line.startswith("Armor Class:"):
                try:
                    ac = int(line.replace("Armor Class:", "").strip())
                    player_data["combat_stats"]["armor_class"] = ac
                except ValueError:
                    pass
            elif line.startswith("Proficiency Bonus:"):
                try:
                    bonus = line.replace("Proficiency Bonus:", "").strip()
                    player_data["combat_stats"]["proficiency_bonus"] = bonus
                except ValueError:
                    pass
            
            # Parse sections
            elif line.upper() in ["FEATURES AND TRAITS:", "EQUIPMENT:", "SKILLS:", "SPELLS:", "PERSONALITY:", "BACKSTORY:", "CHARACTER BUILD SUMMARY:"]:
                current_section = line.upper().replace(":", "")
            elif current_section == "FEATURES AND TRAITS" and line.startswith("-"):
                player_data["features_and_traits"].append(line[1:].strip())
            elif current_section == "EQUIPMENT" and line.startswith("-"):
                player_data["equipment"].append(line[1:].strip())
            elif current_section == "SKILLS" and line.startswith("-"):
                player_data["skills"].append(line[1:].strip())
            elif current_section == "SPELLS" and line.startswith("-"):
                player_data["spells"].append(line[1:].strip())
            elif current_section == "PERSONALITY":
                if ":" in line:
                    key, value = line.split(":", 1)
                    player_data["personality"][key.strip().lower()] = value.strip()
            elif current_section == "BACKSTORY":
                if player_data["backstory"]:
                    player_data["backstory"] += "\n" + line
                else:
                    player_data["backstory"] = line
            elif current_section == "CHARACTER BUILD SUMMARY":
                if player_data["build_summary"]:
                    player_data["build_summary"] += "\n" + line
                else:
                    player_data["build_summary"] = line
        
        # Create Player object
        player = Player(
            name=player_data["name"],
            race=player_data["race"],
            character_class=player_data["character_class"],
            level=player_data["level"],
            background=player_data["background"],
            rulebook=player_data["rulebook"],
            ability_scores=player_data["ability_scores"],
            combat_stats=player_data["combat_stats"],
            features_and_traits=player_data["features_and_traits"],
            equipment=player_data["equipment"],
            skills=player_data["skills"],
            spells=player_data["spells"],
            personality=player_data["personality"],
            backstory=player_data["backstory"],
            build_summary=player_data["build_summary"]
        )
        
        # Initialize game state with HP
        if "hit_points" in player_data["combat_stats"]:
            player.game_state["max_hp"] = player_data["combat_stats"]["hit_points"]
            player.game_state["current_hp"] = player_data["combat_stats"]["hit_points"]
        
        return player

class CampaignLoader:
    """Loads campaigns from various file formats."""
    
    @staticmethod
    def load_from_file(file_path: Path) -> Optional[Campaign]:
        """Load a campaign from a file."""
        try:
            if not file_path.exists():
                return None
            
            content = file_path.read_text(encoding='utf-8')
            
            if file_path.suffix == '.json':
                return CampaignLoader._parse_json_campaign(content)
            elif file_path.suffix == '.txt':
                if content.startswith('==='):
                    return CampaignLoader._parse_structured_campaign(content)
                else:
                    return CampaignLoader._parse_json_campaign(content)
            
            return None
        except Exception as e:
            print(f"Error loading campaign from {file_path}: {e}")
            return None
    
    @staticmethod
    def _parse_json_campaign(content: str) -> Campaign:
        """Parse JSON format campaign."""
        data = json.loads(content)
        
        campaign = Campaign(
            title=data.get("title", "Unknown Campaign"),
            theme=data.get("theme", "Adventure"),
            setting=data.get("setting", "Fantasy World"),
            level_range=data.get("level_range", "1-10"),
            overview=data.get("overview", ""),
            background=data.get("background", ""),
            main_plot=data.get("main_plot", ""),
            dm_notes=data.get("dm_notes", ""),
            metadata=data
        )
        
        # Parse NPCs
        for npc_data in data.get("key_npcs", []):
            npc = CampaignNPC(
                name=npc_data.get("name", "Unknown"),
                role=npc_data.get("role", "NPC"),
                description=npc_data.get("description", ""),
                motivation=npc_data.get("motivation", "")
            )
            campaign.npcs.append(npc)
        
        # Parse Locations
        for loc_data in data.get("locations", []):
            location = CampaignLocation(
                name=loc_data.get("name", "Unknown"),
                location_type=loc_data.get("type", "Location"),
                description=loc_data.get("description", ""),
                significance=loc_data.get("significance", "")
            )
            campaign.locations.append(location)
        
        # Parse Encounters
        for enc_data in data.get("encounters", []):
            encounter = CampaignEncounter(
                title=enc_data.get("title", "Unknown"),
                encounter_type=enc_data.get("type", "Combat"),
                description=enc_data.get("description", ""),
                challenge=enc_data.get("challenge", "Medium")
            )
            campaign.encounters.append(encounter)
        
        campaign.hooks = data.get("hooks", [])
        campaign.rewards = data.get("rewards", [])
        
        return campaign
    
    @staticmethod
    def _parse_structured_campaign(content: str) -> Campaign:
        """Parse structured text format campaign."""
        sections = {}
        current_section = None
        current_content = []
        
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('===') and line.endswith('==='):
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = line.replace('===', '').strip()
                current_content = []
            elif line:
                current_content.append(line)
        
        if current_section:
            sections[current_section] = '\n'.join(current_content)
        
        # Extract basic info
        campaign = Campaign(
            title=sections.get("CAMPAIGN METADATA", "").split("TITLE:")[-1].split("\n")[0].strip() if "TITLE:" in sections.get("CAMPAIGN METADATA", "") else "Unknown Campaign",
            theme=sections.get("CAMPAIGN METADATA", "").split("THEME:")[-1].split("\n")[0].strip() if "THEME:" in sections.get("CAMPAIGN METADATA", "") else "Adventure",
            setting=sections.get("CAMPAIGN METADATA", "").split("SETTING:")[-1].split("\n")[0].strip() if "SETTING:" in sections.get("CAMPAIGN METADATA", "") else "Fantasy World",
            level_range=sections.get("CAMPAIGN METADATA", "").split("LEVEL_RANGE:")[-1].split("\n")[0].strip() if "LEVEL_RANGE:" in sections.get("CAMPAIGN METADATA", "") else "1-10",
            overview=sections.get("CAMPAIGN OVERVIEW", "").split("CAMPAIGN:")[-1].strip() if "CAMPAIGN:" in sections.get("CAMPAIGN OVERVIEW", "") else "",
            background=sections.get("CAMPAIGN BACKGROUND", "").split("CAMPAIGN:")[-1].strip() if "CAMPAIGN:" in sections.get("CAMPAIGN BACKGROUND", "") else "",
            main_plot=sections.get("MAIN PLOT", "").split("CAMPAIGN:")[-1].strip() if "CAMPAIGN:" in sections.get("MAIN PLOT", "") else "",
            dm_notes=sections.get("DM NOTES", "").split("CAMPAIGN:")[-1].strip() if "CAMPAIGN:" in sections.get("DM NOTES", "") else ""
        )
        
        # Parse NPCs
        for section_name, section_content in sections.items():
            if section_name.startswith("NPC:"):
                npc_name = section_name.replace("NPC:", "").strip()
                lines = section_content.split('\n')
                npc_role = ""
                npc_desc = ""
                npc_motivation = ""
                
                for line in lines:
                    if line.startswith("NPC_ROLE:"):
                        npc_role = line.replace("NPC_ROLE:", "").strip()
                    elif line.startswith("DESCRIPTION:"):
                        npc_desc = line.replace("DESCRIPTION:", "").strip()
                    elif line.startswith("MOTIVATION:"):
                        npc_motivation = line.replace("MOTIVATION:", "").strip()
                
                npc = CampaignNPC(
                    name=npc_name,
                    role=npc_role,
                    description=npc_desc,
                    motivation=npc_motivation
                )
                campaign.npcs.append(npc)
        
        # Parse Locations
        for section_name, section_content in sections.items():
            if section_name.startswith("LOCATION:"):
                loc_name = section_name.replace("LOCATION:", "").strip()
                lines = section_content.split('\n')
                loc_type = ""
                loc_desc = ""
                loc_sig = ""
                floorplan = ""
                
                in_floorplan = False
                for line in lines:
                    if line.startswith("LOCATION_TYPE:"):
                        loc_type = line.replace("LOCATION_TYPE:", "").strip()
                    elif line.startswith("DESCRIPTION:"):
                        loc_desc = line.replace("DESCRIPTION:", "").strip()
                    elif line.startswith("SIGNIFICANCE:"):
                        loc_sig = line.replace("SIGNIFICANCE:", "").strip()
                    elif line.startswith("FLOORPLAN:"):
                        in_floorplan = True
                    elif in_floorplan and (line.startswith("#") or line.startswith("`")):
                        floorplan += line + "\n"
                
                location = CampaignLocation(
                    name=loc_name,
                    location_type=loc_type,
                    description=loc_desc,
                    significance=loc_sig,
                    floorplan=floorplan.strip() if floorplan else None
                )
                campaign.locations.append(location)
        
        # Parse Encounters
        for section_name, section_content in sections.items():
            if section_name.startswith("ENCOUNTER:"):
                enc_title = section_name.replace("ENCOUNTER:", "").strip()
                lines = section_content.split('\n')
                enc_type = ""
                enc_desc = ""
                enc_challenge = ""
                
                for line in lines:
                    if line.startswith("ENCOUNTER_TYPE:"):
                        enc_type = line.replace("ENCOUNTER_TYPE:", "").strip()
                    elif line.startswith("DESCRIPTION:"):
                        enc_desc = line.replace("DESCRIPTION:", "").strip()
                    elif line.startswith("CHALLENGE:"):
                        enc_challenge = line.replace("CHALLENGE:", "").strip()
                
                encounter = CampaignEncounter(
                    title=enc_title,
                    encounter_type=enc_type,
                    description=enc_desc,
                    challenge=enc_challenge
                )
                campaign.encounters.append(encounter)
        
        # Parse hooks and rewards
        hooks_content = sections.get("CAMPAIGN HOOKS", "")
        if hooks_content:
            for line in hooks_content.split('\n'):
                if line.startswith("HOOK_"):
                    hook = line.split(":", 1)[1].strip() if ":" in line else ""
                    if hook:
                        campaign.hooks.append(hook)
        
        rewards_content = sections.get("CAMPAIGN REWARDS", "")
        if rewards_content:
            for line in rewards_content.split('\n'):
                if line.startswith("REWARD_"):
                    reward = line.split(":", 1)[1].strip() if ":" in line else ""
                    if reward:
                        campaign.rewards.append(reward)
        
        return campaign

class RAGDMAssistant:
    """RAG-powered Dungeon Master Assistant using existing RAG Agent."""
    
    def __init__(self, collection_name: str = "dnd_documents",
                 campaigns_dir: str = "docs/current_campaign",
                 players_dir: str = "docs/players",
                 verbose: bool = False):
        """Initialize the DM Assistant."""
        self.collection_name = collection_name
        self.campaigns_dir = Path(campaigns_dir)
        self.players_dir = Path(players_dir)
        self.verbose = verbose
        self.has_llm = CLAUDE_AVAILABLE
        
        # Core components
        self.rag_agent: Optional[RAGAgent] = None
        
        # Campaign management
        self.available_campaigns: List[Campaign] = []
        self.selected_campaign: Optional[Campaign] = None
        
        # Player management
        self.available_players: List[Player] = []
        self.active_players: List[Player] = []
        
        # Game state
        self.game_state = {
            "players": {},
            "npcs": {},
            "world": {},
            "story_arc": "",
            "scene_history": [],
            "current_scenario": "",
            "current_options": "",
            "last_command": "",
            "session": {
                "location": "",
                "time": "",
                "events": []
            }
        }
        
        # Initialize components
        self._setup_rag_agent()
        self._load_campaigns()
        self._load_players()
    
    def _setup_rag_agent(self):
        """Setup the RAG agent for context retrieval."""
        try:
            self.rag_agent = RAGAgent(
                collection_name=self.collection_name,
                verbose=self.verbose
            )
            if self.verbose:
                print(f"✓ RAG Agent initialized for collection: {self.collection_name}")
        except Exception as e:
            if self.verbose:
                print(f"✗ Failed to initialize RAG Agent: {e}")
            raise
    
    def _load_campaigns(self):
        """Load available campaigns from the campaigns directory."""
        if not self.campaigns_dir.exists():
            if self.verbose:
                print(f"⚠️  Campaigns directory not found: {self.campaigns_dir}")
            return
        
        for file_path in self.campaigns_dir.glob("*"):
            if file_path.is_file() and file_path.suffix in ['.json', '.txt']:
                campaign = CampaignLoader.load_from_file(file_path)
                if campaign:
                    self.available_campaigns.append(campaign)
                    if self.verbose:
                        print(f"✓ Loaded campaign: {campaign.title}")
        
        if self.verbose:
            print(f"✓ Loaded {len(self.available_campaigns)} campaigns")
    
    def _load_players(self):
        """Load available players from the players directory."""
        if not self.players_dir.exists():
            if self.verbose:
                print(f"⚠️  Players directory not found: {self.players_dir}")
            return
        
        for file_path in self.players_dir.glob("*.txt"):
            if file_path.is_file():
                player = PlayerLoader.load_from_file(file_path)
                if player:
                    self.available_players.append(player)
                    if self.verbose:
                        print(f"✓ Loaded player: {player.name} ({player.race} {player.character_class})")
        
        if self.verbose:
            print(f"✓ Loaded {len(self.available_players)} players")
        
        # Auto-add all players to the game
        self._add_all_players_to_game()
    
    def _add_all_players_to_game(self):
        """Add all loaded players to the active game state."""
        for player in self.available_players:
            self.active_players.append(player)
            self.game_state["players"][player.name] = {
                "character": player,
                "current_hp": player.game_state["current_hp"],
                "max_hp": player.game_state["max_hp"],
                "status_effects": player.game_state["status_effects"].copy(),
                "inventory": player.game_state["inventory"].copy(),
                "location": player.game_state["location"],
                "notes": player.game_state["notes"]
            }
        
        if self.verbose and self.available_players:
            player_names = [p.name for p in self.available_players]
            print(f"✓ Added {len(self.available_players)} players to game: {', '.join(player_names)}")
    
    def _should_use_rag(self, query: str, campaign_context: str = "") -> Tuple[bool, str]:
        """
        Intelligently decide if RAG context is needed based on query and available campaign data.
        Returns: (should_use_rag, reasoning)
        """
        if not self.rag_agent or not self.has_llm:
            return False, "RAG agent or LLM not available"
        
        query_lower = query.lower()
        
        # Always use RAG for general D&D rules questions
        rules_keywords = ["rules", "mechanics", "spell", "class", "race", "saving throw",
                         "ability score", "combat", "initiative", "advantage", "disadvantage",
                         "proficiency", "armor class", "hit points", "damage", "attack"]
        
        if any(keyword in query_lower for keyword in rules_keywords):
            return True, "Query relates to D&D rules/mechanics"
        
        # Use RAG for lore questions that might not be in campaign
        lore_keywords = ["lore", "history", "god", "deity", "plane", "cosmology",
                        "roshar", "stormlight", "shard", "spren", "highstorm",
                        "cultivation", "honor", "odium", "investiture", "surgebinding"]
        
        if any(keyword in query_lower for keyword in lore_keywords):
            return True, "Query relates to world lore/cosmology"
        
        # If we have a campaign selected, check if campaign data might be sufficient
        if self.selected_campaign and campaign_context:
            try:
                decision_prompt = f"""You are a DM Assistant with access to campaign data. Analyze this query to determine if you need external lore/rules context.

QUERY: {query}

AVAILABLE CAMPAIGN DATA:
{campaign_context}

DECISION CRITERIA:
- If the query can be answered with campaign data (NPCs, locations, plot points), return "NO"
- If the query needs D&D rules, mechanics, or external lore not in campaign, return "YES"
- If unsure or the query is complex/ambiguous, return "YES"

Respond with only "YES" or "NO" followed by a brief reason."""

                if CLAUDE_AVAILABLE:
                    chat_generator = AppleGenAIChatGenerator(
                        model="aws:anthropic.claude-sonnet-4-20250514-v1:0"
                    )
                    messages = [ChatMessage.from_user(decision_prompt)]
                    result = chat_generator.run(messages=messages)
                    
                    if result and "replies" in result and result["replies"]:
                        response = result["replies"][0].text.strip()
                        if response.startswith("YES"):
                            return True, response.replace("YES", "").strip()
                        elif response.startswith("NO"):
                            return False, response.replace("NO", "").strip()
                        else:
                            return True, "Ambiguous decision, defaulting to RAG"
                    
            except Exception:
                pass  # Fall through to default
        
        # Default to using RAG for safety
        return True, "Default decision - better to have too much context"
    
    def _serialize_game_state(self, state_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Convert game state to JSON-serializable format by handling Player objects."""
        serializable_state = {}
        
        for key, value in state_dict.items():
            if key == "players":
                # Handle players dictionary which may contain Player objects
                serializable_players = {}
                for player_name, player_data in value.items():
                    serializable_player_data = {}
                    for data_key, data_value in player_data.items():
                        if data_key == "character" and data_value is not None:
                            # Convert Player object to dictionary
                            if hasattr(data_value, 'to_dict'):
                                serializable_player_data[data_key] = data_value.to_dict()
                            else:
                                serializable_player_data[data_key] = str(data_value)
                        else:
                            serializable_player_data[data_key] = data_value
                    serializable_players[player_name] = serializable_player_data
                serializable_state[key] = serializable_players
            else:
                serializable_state[key] = value
        
        return serializable_state
    
    def get_rag_context(self, query: str) -> str:
        """Get context from RAG agent."""
        if not self.rag_agent:
            return f"RAG agent not available for: {query}"
        
        try:
            result = self.rag_agent.query(query)
            if "error" in result:
                return f"Error retrieving context: {result['error']}"
            
            # Extract the answer and condense if needed
            answer = result.get("answer", "")
            if len(answer) > 800:
                return condense_text(answer, max_length=800)
            else:
                return answer
            
        except Exception as e:
            return f"Error retrieving context: {e}"
    
    def _merge_contexts(self, campaign_context: str, rag_context: str, query: str) -> str:
        """Merge campaign and RAG contexts into a coherent narrative."""
        if not self.has_llm:
            return f"CAMPAIGN CONTEXT:\n{campaign_context}\n\nRAG CONTEXT:\n{rag_context}"
        
        try:
            merge_prompt = f"""You are a DM Assistant. Merge these information sources into a coherent context for answering the query.

QUERY: {query}

CAMPAIGN CONTEXT:
{campaign_context}

EXTERNAL CONTEXT (Rules/Lore):
{rag_context}

TASK: Create a unified context that:
1. Prioritizes campaign-specific information
2. Integrates relevant external context seamlessly
3. Removes redundant information
4. Maintains narrative coherence
5. Stays focused on the query

Provide the merged context in 2-3 paragraphs:"""

            if CLAUDE_AVAILABLE:
                chat_generator = AppleGenAIChatGenerator(
                    model="aws:anthropic.claude-sonnet-4-20250514-v1:0"
                )
                messages = [ChatMessage.from_user(merge_prompt)]
                result = chat_generator.run(messages=messages)
                
                if result and "replies" in result and result["replies"]:
                    return result["replies"][0].text
            
            # Fallback if LLM fails
            return f"CAMPAIGN CONTEXT:\n{campaign_context}\n\nADDITIONAL CONTEXT:\n{rag_context}"
            
        except Exception:
            return f"CAMPAIGN CONTEXT:\n{campaign_context}\n\nADDITIONAL CONTEXT:\n{rag_context}"
    
    def list_campaigns(self) -> List[str]:
        """List available campaigns."""
        return [f"{i+1}. {campaign.title} ({campaign.theme})" 
                for i, campaign in enumerate(self.available_campaigns)]
    
    def select_campaign(self, campaign_index: int) -> bool:
        """Select a campaign by index."""
        if 0 <= campaign_index < len(self.available_campaigns):
            self.selected_campaign = self.available_campaigns[campaign_index]
            
            # Initialize game state with campaign info
            self.game_state["story_arc"] = self.selected_campaign.overview
            self.game_state["world"]["campaign"] = self.selected_campaign.title
            self.game_state["world"]["setting"] = self.selected_campaign.setting
            
            # Add campaign NPCs to game state
            for npc in self.selected_campaign.npcs:
                self.game_state["npcs"][npc.name] = {
                    "description": npc.description,
                    "role": npc.role,
                    "motivation": npc.motivation,
                    "stats": npc.stats
                }
            
            return True
        return False
    
    def get_campaign_info(self) -> str:
        """Get information about the selected campaign."""
        if not self.selected_campaign:
            return "No campaign selected. Use 'select campaign' to choose one."
        
        campaign = self.selected_campaign
        info = f"📖 CAMPAIGN: {campaign.title}\n"
        info += f"🎭 Theme: {campaign.theme}\n"
        info += f"🗺️  Setting: {campaign.setting}\n"
        info += f"📊 Level Range: {campaign.level_range}\n\n"
        info += f"📝 Overview:\n{campaign.overview}\n\n"
        
        if campaign.npcs:
            info += f"👥 Key NPCs ({len(campaign.npcs)}):\n"
            for npc in campaign.npcs[:3]:  # Show first 3
                info += f"  • {npc.name} ({npc.role})\n"
            if len(campaign.npcs) > 3:
                info += f"  ... and {len(campaign.npcs) - 3} more\n"
            info += "\n"
        
        if campaign.locations:
            info += f"📍 Locations ({len(campaign.locations)}):\n"
            for loc in campaign.locations[:3]:  # Show first 3
                info += f"  • {loc.name} ({loc.location_type})\n"
            if len(campaign.locations) > 3:
                info += f"  ... and {len(campaign.locations) - 3} more\n"
            info += "\n"
        
        return info
    
    def list_players(self) -> str:
        """List all available and active players."""
        info = "👥 PLAYERS:\n\n"
        
        if self.active_players:
            info += f"🎮 ACTIVE PLAYERS ({len(self.active_players)}):\n"
            for i, player in enumerate(self.active_players, 1):
                hp_info = f"HP: {player.game_state['current_hp']}/{player.game_state['max_hp']}" if player.game_state['max_hp'] > 0 else "HP: Unknown"
                info += f"  {i}. {player.name} ({player.race} {player.character_class} Level {player.level}) - {hp_info}\n"
            info += "\n"
        
        # Show manual players if any
        manual_players = [name for name, data in self.game_state["players"].items() if not data.get("character")]
        if manual_players:
            info += f"📝 MANUAL PLAYERS ({len(manual_players)}):\n"
            for i, player_name in enumerate(manual_players, 1):
                player_data = self.game_state["players"][player_name]
                hp_info = f"HP: {player_data['current_hp']}/{player_data['max_hp']}"
                info += f"  {i}. {player_name} - {hp_info}\n"
            info += "\n"
        
        if not self.active_players and not manual_players:
            info += "❌ No players found. Check docs/players directory for character files.\n"
        
        return info
    
    def get_player_info(self, player_name: str) -> str:
        """Get detailed information about a specific player."""
        # Find player in active players
        player = next((p for p in self.active_players if p.name.lower() == player_name.lower()), None)
        
        if player:
            info = f"👤 PLAYER: {player.name}\n"
            info += f"🎭 Race: {player.race}\n"
            info += f"⚔️  Class: {player.character_class} (Level {player.level})\n"
            info += f"📚 Background: {player.background}\n"
            info += f"📖 Rulebook: {player.rulebook}\n\n"
            
            # Combat stats
            if player.combat_stats:
                info += "⚔️  COMBAT STATS:\n"
                for stat, value in player.combat_stats.items():
                    stat_name = stat.replace('_', ' ').title()
                    info += f"  • {stat_name}: {value}\n"
                info += "\n"
            
            # Ability scores
            if player.ability_scores:
                info += "📊 ABILITY SCORES:\n"
                for ability, score in player.ability_scores.items():
                    modifier = (score - 10) // 2
                    modifier_str = f"+{modifier}" if modifier >= 0 else str(modifier)
                    info += f"  • {ability.title()}: {score} ({modifier_str})\n"
                info += "\n"
            
            # Game state
            info += "🎮 CURRENT STATE:\n"
            info += f"  • HP: {player.game_state['current_hp']}/{player.game_state['max_hp']}\n"
            if player.game_state['status_effects']:
                info += f"  • Status Effects: {', '.join(player.game_state['status_effects'])}\n"
            if player.game_state['location']:
                info += f"  • Location: {player.game_state['location']}\n"
            if player.game_state['notes']:
                info += f"  • Notes: {player.game_state['notes']}\n"
            
            # Personality
            if player.personality:
                info += "\n🎭 PERSONALITY:\n"
                for trait, value in player.personality.items():
                    info += f"  • {trait.title()}: {value}\n"
            
            return info
        
        # Check manual players
        elif player_name in self.game_state["players"]:
            player_data = self.game_state["players"][player_name]
            if not player_data.get("character"):  # It's a manual player
                info = f"👤 MANUAL PLAYER: {player_name}\n"
                info += f"💚 HP: {player_data['current_hp']}/{player_data['max_hp']}\n"
                if player_data['status_effects']:
                    info += f"🔮 Status Effects: {', '.join(player_data['status_effects'])}\n"
                if player_data['location']:
                    info += f"📍 Location: {player_data['location']}\n"
                if player_data['notes']:
                    info += f"📝 Notes: {player_data['notes']}\n"
                return info
        
        return f"❌ Player '{player_name}' not found. Use 'list players' to see available players."
    
    def generate_scenario_from_campaign(self, user_query: str) -> str:
        """Generate a scenario based on the selected campaign and user query using intelligent RAG decision."""
        if not self.selected_campaign:
            return "❌ No campaign selected. Please select a campaign first."
        
        if not self.has_llm:
            return "❌ LLM not available for scenario generation."
        
        # Prepare campaign context
        campaign = self.selected_campaign
        campaign_context = f"""
Campaign: {campaign.title}
Setting: {campaign.setting}
Current Story Arc: {self.game_state['story_arc']}

Available NPCs: {', '.join([npc.name for npc in campaign.npcs[:5]])}
Available Locations: {', '.join([loc.name for loc in campaign.locations[:5]])}
Available Encounters: {', '.join([enc.title for enc in campaign.encounters[:3]])}
"""
        
        # Get current game state
        state_for_serialization = {
            "players": self.game_state["players"],
            "current_location": self.game_state["session"].get("location", "Unknown"),
            "recent_events": self.game_state["session"].get("events", [])[-3:],
            "last_scene": self.game_state["scene_history"][-1] if self.game_state["scene_history"] else "Beginning of adventure"
        }
        serializable_state = self._serialize_game_state(state_for_serialization)
        current_state = json.dumps(serializable_state, indent=2)
        
        # Step 1: Decide if we need RAG context
        should_use_rag, rag_reasoning = self._should_use_rag(user_query, campaign_context)
        
        if self.verbose:
            print(f"🤔 RAG Decision: {'YES' if should_use_rag else 'NO'} - {rag_reasoning}")
        
        # Step 2: Get context based on decision
        if should_use_rag:
            rag_context = self.get_rag_context(user_query)
            merged_context = self._merge_contexts(campaign_context, rag_context, user_query)
            context_info = "🔍 Using campaign data + external lore/rules"
        else:
            merged_context = campaign_context
            context_info = "📖 Using campaign data only"
        
        # Create comprehensive prompt
        prompt = f"""You are an expert Dungeon Master running the campaign "{campaign.title}".

CONTEXT:
{merged_context}

CURRENT GAME STATE:
{current_state}

USER REQUEST: {user_query}

TASK:
Generate the next scenario/scene for the players that:
1. Continues the existing story arc naturally
2. Incorporates elements from the campaign (NPCs, locations, encounters)
3. Responds to the user's specific request
4. Uses relevant context information appropriately
5. Provides 3-4 clear decision points/options for players at the end
6. Maintains the campaign's theme and setting

Generate a detailed scenario in 4-6 sentences that advances the story, then provide 3-4 numbered player options:"""
        
        try:
            if CLAUDE_AVAILABLE:
                chat_generator = AppleGenAIChatGenerator(
                    model="aws:anthropic.claude-sonnet-4-20250514-v1:0"
                )
                messages = [ChatMessage.from_user(prompt)]
                result = chat_generator.run(messages=messages)
                
                if result and "replies" in result and result["replies"]:
                    scenario_response = result["replies"][0].text
                    
                    # Generate numbered player options using a follow-up prompt
                    options_prompt = f"""Based on this scenario, create 3-4 numbered player options that the DM can select from:

SCENARIO: {scenario_response}

Format the options as:
1. [First option - action the players could take]
2. [Second option - alternative action]
3. [Third option - different approach]
4. [Fourth option - creative/unexpected choice]

Make each option specific, actionable, and engaging for the players."""

                    options_result = chat_generator.run(messages=[ChatMessage.from_user(options_prompt)])
                    
                    player_options = ""
                    if options_result and "replies" in options_result and options_result["replies"]:
                        player_options = options_result["replies"][0].text
                    
                    # Combine scenario and options
                    full_scenario = f"{scenario_response}\n\n🎯 **PLAYER OPTIONS:**\n{player_options}"
                    
                    # Store the scenario and options in game history
                    self.game_state["scene_history"].append(full_scenario)
                    self.game_state["current_scenario"] = full_scenario
                    self.game_state["current_options"] = player_options
                    
                    # Update story arc
                    self._update_story_arc(scenario_response)
                    
                    # Add player addition message if this is the first scenario
                    player_message = ""
                    if len(self.game_state["scene_history"]) == 1 and self.active_players:
                        player_names = [p.name for p in self.active_players]
                        player_message = f"\n\n👥 **PLAYERS JOINED THE ADVENTURE:**\nThe following heroes have joined this quest: {', '.join(player_names)}. Each brings their unique skills and background to face the challenges ahead."
                    
                    return f"🎭 SCENARIO:\n{full_scenario}{player_message}\n\n💡 {context_info}\n\n📝 *DM: Type 'select option [number]' to choose a player option and continue the story.*"
                else:
                    return "❌ Failed to generate scenario - no response from LLM"
            else:
                return "❌ Claude not available for scenario generation"
                
        except Exception as e:
            return f"❌ Error generating scenario: {e}"
    
    def _update_story_arc(self, new_scenario: str):
        """Update the story arc summary with the new scenario."""
        if not self.has_llm:
            return
        
        try:
            current_arc = self.game_state["story_arc"]
            update_prompt = f"""Update this story arc summary with the new scenario:

Current Summary: {current_arc}

New Scenario: {new_scenario}

Provide an updated 2-3 sentence summary that incorporates the new developments:"""
            
            if CLAUDE_AVAILABLE:
                chat_generator = AppleGenAIChatGenerator(
                    model="aws:anthropic.claude-sonnet-4-20250514-v1:0"
                )
                messages = [ChatMessage.from_user(update_prompt)]
                result = chat_generator.run(messages=messages)
                
                if result and "replies" in result and result["replies"]:
                    updated_arc = result["replies"][0].text
                    self.game_state["story_arc"] = updated_arc
                    
        except Exception:
            pass  # Silently fail, keep original arc
    
    def select_player_option(self, option_number: int) -> str:
        """Handle DM selection of a player option and continue the story."""
        if not self.selected_campaign:
            return "❌ No campaign selected. Please select a campaign first."
        
        if not self.has_llm:
            return "❌ LLM not available for option processing."
        
        if "current_options" not in self.game_state or not self.game_state["current_options"]:
            return "❌ No current player options available. Use 'introduce scenario' first."
        
        current_options = self.game_state["current_options"]
        current_scenario = self.game_state.get("current_scenario", "")
        
        # Extract the specific option chosen
        options_lines = current_options.split('\n')
        selected_option = None
        for line in options_lines:
            if line.strip().startswith(f"{option_number}."):
                selected_option = line.strip()
                break
        
        if not selected_option:
            # Count available options
            option_count = len([line for line in options_lines if line.strip() and any(line.strip().startswith(f"{i}.") for i in range(1, 10))])
            return f"❌ Invalid option number. Available options: 1-{option_count}"
        
        # Generate continuation based on selected option
        continuation_prompt = f"""You are a Dungeon Master. The players have chosen an option. Continue the story based on their choice.

CURRENT SCENARIO:
{current_scenario}

SELECTED PLAYER OPTION:
{selected_option}

TASK:
1. Describe the immediate consequences of the players' choice (2-3 sentences)
2. Advance the story naturally based on their decision
3. Set up the next situation or challenge
4. Provide 3-4 new numbered options for the players to choose from

Generate the continuation and new options:"""
        
        try:
            if CLAUDE_AVAILABLE:
                chat_generator = AppleGenAIChatGenerator(
                    model="aws:anthropic.claude-sonnet-4-20250514-v1:0"
                )
                messages = [ChatMessage.from_user(continuation_prompt)]
                result = chat_generator.run(messages=messages)
                
                if result and "replies" in result and result["replies"]:
                    continuation_response = result["replies"][0].text
                    
                    # Generate new numbered options
                    new_options_prompt = f"""Based on this story continuation, create 3-4 numbered player options:

CONTINUATION: {continuation_response}

Format as:
1. [First option]
2. [Second option]
3. [Third option]
4. [Fourth option]

Make each option specific and actionable."""

                    new_options_result = chat_generator.run(messages=[ChatMessage.from_user(new_options_prompt)])
                    
                    new_options = ""
                    if new_options_result and "replies" in new_options_result and new_options_result["replies"]:
                        new_options = new_options_result["replies"][0].text
                    
                    # Combine continuation and new options
                    full_continuation = f"{continuation_response}\n\n🎯 **NEW PLAYER OPTIONS:**\n{new_options}"
                    
                    # Update game state
                    self.game_state["scene_history"].append(full_continuation)
                    self.game_state["current_scenario"] = full_continuation
                    self.game_state["current_options"] = new_options
                    self.game_state["session"]["events"].append(f"Players chose: {selected_option}")
                    
                    return f"✅ **SELECTED:** {selected_option}\n\n🎭 **STORY CONTINUES:**\n{full_continuation}\n\n📝 *DM: Type 'select option [number]' to choose the next player option.*"
                else:
                    return "❌ Failed to generate story continuation - no response from LLM"
            else:
                return "❌ Claude not available for story continuation"
                
        except Exception as e:
            return f"❌ Error processing option selection: {e}"
    
    def process_dm_input(self, instruction: str) -> str:
        """Process DM instruction and return appropriate response."""
        instruction_lower = instruction.lower().strip()
        
        # Check if user just typed a number after listing campaigns
        if instruction.strip().isdigit() and self.game_state.get("last_command") == "list_campaigns":
            campaign_idx = int(instruction.strip()) - 1
            if self.select_campaign(campaign_idx):
                self.game_state["last_command"] = ""  # Clear the last command
                return f"✓ Selected campaign: {self.selected_campaign.title}"
            else:
                return f"❌ Invalid campaign number. Available: 1-{len(self.available_campaigns)}"
        
        # Campaign management commands
        if "list campaigns" in instruction_lower or "show campaigns" in instruction_lower:
            campaigns = self.list_campaigns()
            if campaigns:
                self.game_state["last_command"] = "list_campaigns"  # Track that we just listed campaigns
                return "📚 AVAILABLE CAMPAIGNS:\n" + "\n".join(campaigns) + "\n\n💡 *Type the campaign number to select it*"
            else:
                return "❌ No campaigns available. Check campaigns directory."
        
        elif "select campaign" in instruction_lower:
            self.game_state["last_command"] = ""  # Clear last command
            campaigns = self.list_campaigns()
            if not campaigns:
                return "❌ No campaigns available."
            
            # Try to extract campaign number
            words = instruction.split()
            for word in words:
                if word.isdigit():
                    campaign_idx = int(word) - 1
                    if self.select_campaign(campaign_idx):
                        return f"✓ Selected campaign: {self.selected_campaign.title}"
                    else:
                        return f"❌ Invalid campaign number. Available: 1-{len(self.available_campaigns)}"
            
            return f"❌ Please specify campaign number (1-{len(self.available_campaigns)})"
        
        elif "campaign info" in instruction_lower or "show campaign" in instruction_lower:
            self.game_state["last_command"] = ""  # Clear last command
            return self.get_campaign_info()
        
        # Scenario generation - handle both old and new commands
        elif any(keyword in instruction_lower for keyword in ["introduce scenario", "generate", "scenario", "scene", "encounter", "adventure"]):
            self.game_state["last_command"] = ""  # Clear last command
            return self.generate_scenario_from_campaign(instruction)
        
        # Option selection
        elif "select option" in instruction_lower:
            self.game_state["last_command"] = ""  # Clear last command
            # Try to extract option number
            words = instruction.split()
            for word in words:
                if word.isdigit():
                    option_num = int(word)
                    return self.select_player_option(option_num)
            
            return "❌ Please specify option number (e.g., 'select option 2')"
        
        # Game state management
        elif "game state" in instruction_lower or "show state" in instruction_lower:
            self.game_state["last_command"] = ""  # Clear last command
            serializable_state = self._serialize_game_state(self.game_state)
            return f"📊 GAME STATE:\n{json.dumps(serializable_state, indent=2)}"
        
        elif "list players" in instruction_lower or "show players" in instruction_lower:
            self.game_state["last_command"] = ""  # Clear last command
            return self.list_players()
        
        elif "player info" in instruction_lower or "show player" in instruction_lower:
            self.game_state["last_command"] = ""  # Clear last command
            # Try to extract player name
            words = instruction.split()
            player_name = None
            for i, word in enumerate(words):
                if word.lower() in ["info", "player"] and i + 1 < len(words):
                    player_name = words[i + 1]
                    break
            
            if player_name:
                return self.get_player_info(player_name)
            else:
                return "❌ Please specify player name. Usage: player info [name]"
        
        elif "add player" in instruction_lower:
            self.game_state["last_command"] = ""  # Clear last command
            # This is for manually adding a simple player, but we auto-load from files
            words = instruction.split()
            if len(words) >= 3:
                player_name = words[2]
                # Check if this player already exists in loaded players
                existing_player = next((p for p in self.available_players if p.name.lower() == player_name.lower()), None)
                if existing_player:
                    return f"✓ Player {player_name} is already loaded from character file"
                else:
                    # Create a simple manual player
                    self.game_state["players"][player_name] = {
                        "character": None,  # Manual player, no character sheet
                        "current_hp": 10,
                        "max_hp": 10,
                        "status_effects": [],
                        "inventory": [],
                        "location": "",
                        "notes": ""
                    }
                    return f"✓ Added manual player: {player_name}"
            return "❌ Usage: add player [name]"
        
        # General D&D help using intelligent RAG decision
        else:
            # Clear last_command state for any other command
            self.game_state["last_command"] = ""
            return self._handle_general_query(instruction)
    
    def _handle_general_query(self, query: str) -> str:
        """Handle general queries with intelligent RAG decision making."""
        # Prepare campaign context if available
        campaign_context = ""
        if self.selected_campaign:
            campaign_context = f"""
Current Campaign: {self.selected_campaign.title}
Setting: {self.selected_campaign.setting}
Available NPCs: {', '.join([npc.name for npc in self.selected_campaign.npcs[:3]])}
Available Locations: {', '.join([loc.name for loc in self.selected_campaign.locations[:3]])}
"""
        
        # Step 1: Decide if we need RAG context
        should_use_rag, rag_reasoning = self._should_use_rag(query, campaign_context)
        
        if self.verbose:
            print(f"🤔 RAG Decision: {'YES' if should_use_rag else 'NO'} - {rag_reasoning}")
        
        # Step 2: Process based on decision
        if should_use_rag:
            # Get RAG context and merge if we have campaign data
            rag_context = self.get_rag_context(query)
            
            if campaign_context and self.has_llm:
                # Merge contexts intelligently
                merged_context = self._merge_contexts(campaign_context, rag_context, query)
                return f"💡 CONTEXT (Campaign + External):\n{merged_context}"
            else:
                return f"💡 CONTEXT:\n{rag_context}"
        
        elif campaign_context and self.has_llm:
            # Use campaign context only, but enhance with LLM
            try:
                campaign_prompt = f"""You are a DM Assistant. Answer this query using only the available campaign information.

QUERY: {query}

CAMPAIGN CONTEXT:
{campaign_context}

If the campaign context doesn't contain enough information to answer the query, say so clearly and suggest what additional information might be needed.

Provide a helpful response focused on the campaign:"""

                if CLAUDE_AVAILABLE:
                    chat_generator = AppleGenAIChatGenerator(
                        model="aws:anthropic.claude-sonnet-4-20250514-v1:0"
                    )
                    messages = [ChatMessage.from_user(campaign_prompt)]
                    result = chat_generator.run(messages=messages)
                    
                    if result and "replies" in result and result["replies"]:
                        return f"📖 CAMPAIGN CONTEXT:\n{result['replies'][0].text}"
                
                # Fallback
                return f"📖 CAMPAIGN CONTEXT:\n{campaign_context}\n\n❓ For more detailed information, try asking about specific D&D rules or lore."
                
            except Exception as e:
                return f"📖 CAMPAIGN CONTEXT:\n{campaign_context}\n\n❌ Error processing query: {e}"
        
        else:
            # No campaign selected or no LLM - default to RAG
            context = self.get_rag_context(query)
            return f"💡 CONTEXT:\n{context}"
    
    def run_interactive(self):
        """Run the interactive DM assistant."""
        print("=== RAG-Powered Dungeon Master Assistant with Intelligent Context Selection ===")
        print("🧠 NEW: Intelligently decides when to use RAG vs campaign data")
        print("🔄 Architecture: Campaign Data → Smart Decision → RAG Agent (if needed) → Merged Response")
        print(f"RAG Context: {'✓ Available' if self.rag_agent else '❌ Unavailable'}")
        print(f"LLM Generation: {'✓ Claude Sonnet 4' if self.has_llm else '❌ Unavailable'}")
        print(f"Campaigns Available: {len(self.available_campaigns)}")
        print(f"Verbose Mode: {'✓ Shows RAG decisions' if self.verbose else '❌ Silent mode'}")
        print()
        
        print("🎯 How it works:")
        print("  1. DM asks question → 2. Assistant analyzes campaign data")
        print("  3. Decides if external lore/rules needed → 4. Calls RAG only if necessary")
        print("  5. Merges contexts intelligently → 6. Provides unified response")
        print()
        
        print("Commands you can try:")
        print("  📚 'list campaigns' - Show available campaigns")
        print("  🎯 'select campaign [number]' - Choose a campaign")
        print("  📖 'campaign info' - Show current campaign details")
        print("  👥 'list players' - Show all loaded players")
        print("  👤 'player info [name]' - Show detailed player information")
        print("  🎭 'introduce scenario' - Create scenario (smart context)")
        print("  🎯 'select option [number]' - Choose a numbered player option")
        print("  👥 'add player Alice' - Add a manual player")
        print("  📊 'show game state' - Display current state")
        print("  ❓ 'What are saving throws?' - Get D&D help (smart context)")
        print("  ❓ 'Tell me about Kaladin' - Campaign vs lore decision test")
        print("  🚪 'quit' to exit")
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
                
                response = self.process_dm_input(dm_input)
                print(response)
                
            except KeyboardInterrupt:
                print("\nGoodbye, Dungeon Master!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")

def main():
    """Main function to run the DM assistant."""
    try:
        # Get configuration from user
        collection_name = input("Enter Qdrant collection name (default: dnd_documents): ").strip()
        if not collection_name:
            collection_name = "dnd_documents"
        
        print("Initializing RAG DM Assistant...")
        assistant = RAGDMAssistant(
            collection_name=collection_name,
            verbose=True
        )
        
        assistant.run_interactive()
        
    except Exception as e:
        print(f"❌ Failed to initialize DM Assistant: {e}")
        print("Make sure Qdrant is running: docker run -p 6333:6333 qdrant/qdrant")

if __name__ == "__main__":
    main()