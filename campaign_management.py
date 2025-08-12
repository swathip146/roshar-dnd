"""
Campaign Management for DM Assistant
Handles campaign data, player management, and campaign operations
"""
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from pathlib import Path

from agent_framework import BaseAgent, MessageType, AgentMessage


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
        except Exception:
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
        except Exception:
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
            title=CampaignLoader._extract_field(sections.get("CAMPAIGN METADATA", ""), "TITLE:", "Unknown Campaign"),
            theme=CampaignLoader._extract_field(sections.get("CAMPAIGN METADATA", ""), "THEME:", "Adventure"),
            setting=CampaignLoader._extract_field(sections.get("CAMPAIGN METADATA", ""), "SETTING:", "Fantasy World"),
            level_range=CampaignLoader._extract_field(sections.get("CAMPAIGN METADATA", ""), "LEVEL_RANGE:", "1-10"),
            overview=CampaignLoader._extract_field(sections.get("CAMPAIGN OVERVIEW", ""), "CAMPAIGN:", ""),
            background=CampaignLoader._extract_field(sections.get("CAMPAIGN BACKGROUND", ""), "CAMPAIGN:", ""),
            main_plot=CampaignLoader._extract_field(sections.get("MAIN PLOT", ""), "CAMPAIGN:", ""),
            dm_notes=CampaignLoader._extract_field(sections.get("DM NOTES", ""), "CAMPAIGN:", "")
        )
        
        # Parse NPCs, Locations, Encounters from sections
        CampaignLoader._parse_structured_npcs(campaign, sections)
        CampaignLoader._parse_structured_locations(campaign, sections)
        CampaignLoader._parse_structured_encounters(campaign, sections)
        CampaignLoader._parse_structured_hooks_rewards(campaign, sections)
        
        return campaign
    
    @staticmethod
    def _extract_field(content: str, field: str, default: str) -> str:
        """Extract a field from structured content"""
        if field in content:
            return content.split(field)[-1].split("\n")[0].strip()
        return default
    
    @staticmethod
    def _parse_structured_npcs(campaign: Campaign, sections: Dict[str, str]):
        """Parse NPCs from structured sections"""
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
    
    @staticmethod
    def _parse_structured_locations(campaign: Campaign, sections: Dict[str, str]):
        """Parse locations from structured sections"""
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
    
    @staticmethod
    def _parse_structured_encounters(campaign: Campaign, sections: Dict[str, str]):
        """Parse encounters from structured sections"""
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
    
    @staticmethod
    def _parse_structured_hooks_rewards(campaign: Campaign, sections: Dict[str, str]):
        """Parse hooks and rewards from structured sections"""
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


class CampaignManagerAgent(BaseAgent):
    """Campaign Manager agent for handling campaign and player operations"""
    
    def __init__(self, campaigns_dir: str = "docs/current_campaign", players_dir: str = "docs/players"):
        super().__init__("campaign_manager", "CampaignManager")
        self.campaigns_dir = Path(campaigns_dir)
        self.players_dir = Path(players_dir)
        
        # Campaign and player data
        self.available_campaigns: List[Campaign] = []
        self.selected_campaign: Optional[Campaign] = None
        self.available_players: List[Player] = []
        self.active_players: List[Player] = []
        
        # Load data
        self._load_campaigns()
        self._load_players()
        
        # CRITICAL FIX: Setup message handlers
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup message handlers for campaign manager"""
        self.register_handler("list_campaigns", self._handle_list_campaigns)
        self.register_handler("select_campaign", self._handle_select_campaign)
        self.register_handler("get_campaign_info", self._handle_get_campaign_info)
        self.register_handler("list_players", self._handle_list_players)
        self.register_handler("get_player_info", self._handle_get_player_info)
        self.register_handler("add_player_to_game", self._handle_add_player_to_game)
        self.register_handler("get_campaign_context", self._handle_get_campaign_context)
    
    def _load_campaigns(self):
        """Load available campaigns from the campaigns directory"""
        if not self.campaigns_dir.exists():
            return
        
        for file_path in self.campaigns_dir.glob("*"):
            if file_path.is_file() and file_path.suffix in ['.json', '.txt']:
                campaign = CampaignLoader.load_from_file(file_path)
                if campaign:
                    self.available_campaigns.append(campaign)
    
    def _load_players(self):
        """Load available players from the players directory"""
        if not self.players_dir.exists():
            return
        
        for file_path in self.players_dir.glob("*.txt"):
            if file_path.is_file():
                player = PlayerLoader.load_from_file(file_path)
                if player:
                    self.available_players.append(player)
    
    def _handle_list_campaigns(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle campaign listing request"""
        campaigns = [f"{i+1}. {campaign.title} ({campaign.theme})" 
                    for i, campaign in enumerate(self.available_campaigns)]
        return {"campaigns": campaigns}
    
    def _handle_select_campaign(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle campaign selection request"""
        campaign_index = message.data.get("index")
        if campaign_index is None:
            return {"success": False, "error": "No campaign index provided"}
        
        if 0 <= campaign_index < len(self.available_campaigns):
            self.selected_campaign = self.available_campaigns[campaign_index]
            
            # Broadcast campaign selection event
            self.broadcast_event("campaign_selected", {
                "campaign": {
                    "title": self.selected_campaign.title,
                    "theme": self.selected_campaign.theme,
                    "setting": self.selected_campaign.setting,
                    "overview": self.selected_campaign.overview,
                    "npcs": [{"name": npc.name, "role": npc.role} for npc in self.selected_campaign.npcs],
                    "locations": [{"name": loc.name, "type": loc.location_type} for loc in self.selected_campaign.locations]
                }
            })
            
            return {"success": True, "campaign": self.selected_campaign.title}
        
        return {"success": False, "error": "Invalid campaign index"}
    
    def _handle_get_campaign_info(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle campaign info request"""
        if not self.selected_campaign:
            return {"success": False, "error": "No campaign selected"}
        
        campaign = self.selected_campaign
        return {
            "success": True,
            "campaign": {
                "title": campaign.title,
                "theme": campaign.theme,
                "setting": campaign.setting,
                "level_range": campaign.level_range,
                "overview": campaign.overview,
                "background": campaign.background,
                "main_plot": campaign.main_plot,
                "npcs": [asdict(npc) for npc in campaign.npcs],
                "locations": [asdict(loc) for loc in campaign.locations],
                "encounters": [asdict(enc) for enc in campaign.encounters],
                "hooks": campaign.hooks,
                "rewards": campaign.rewards,
                "dm_notes": campaign.dm_notes
            }
        }
    
    def _handle_list_players(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle player listing request"""
        players = []
        for player in self.available_players:
            hp_info = f"{player.game_state['current_hp']}/{player.game_state['max_hp']}" if player.game_state['max_hp'] > 0 else "Unknown"
            players.append({
                "name": player.name,
                "race": player.race,
                "character_class": player.character_class,
                "level": player.level,
                "hp": hp_info
            })
        
        return {"players": players}
    
    def _handle_get_player_info(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle player info request"""
        player_name = message.data.get("name")
        if not player_name:
            return {"success": False, "error": "No player name provided"}
        
        player = next((p for p in self.available_players if p.name.lower() == player_name.lower()), None)
        if not player:
            return {"success": False, "error": f"Player '{player_name}' not found"}
        
        return {"success": True, "player": player.to_dict()}
    
    def _handle_add_player_to_game(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle adding player to active game"""
        player_name = message.data.get("name")
        if not player_name:
            return {"success": False, "error": "No player name provided"}
        
        player = next((p for p in self.available_players if p.name.lower() == player_name.lower()), None)
        if not player:
            return {"success": False, "error": f"Player '{player_name}' not found"}
        
        if player not in self.active_players:
            self.active_players.append(player)
            
            # Notify game engine about new player
            self.send_message("game_engine", "update_game_state", {
                "updates": {
                    f"players.{player.name}": {
                        "character": player.to_dict(),
                        "current_hp": player.game_state["current_hp"],
                        "max_hp": player.game_state["max_hp"],
                        "status_effects": player.game_state["status_effects"].copy(),
                        "inventory": player.game_state["inventory"].copy(),
                        "location": player.game_state["location"],
                        "notes": player.game_state["notes"]
                    }
                }
            })
        
        return {"success": True, "message": f"Player {player.name} added to game"}
    
    def _handle_get_campaign_context(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle campaign context request for RAG operations"""
        if not self.selected_campaign:
            return {"success": False, "error": "No campaign selected"}
        
        campaign = self.selected_campaign
        context = {
            "campaign": campaign.title,
            "setting": campaign.setting,
            "overview": campaign.overview,
            "background": campaign.background,
            "main_plot": campaign.main_plot,
            "npcs": [{"name": npc.name, "role": npc.role, "description": npc.description} 
                    for npc in campaign.npcs[:5]],  # Limit for context size
            "locations": [{"name": loc.name, "type": loc.location_type, "description": loc.description} 
                         for loc in campaign.locations[:5]],
            "encounters": [{"title": enc.title, "type": enc.encounter_type} 
                          for enc in campaign.encounters[:3]]
        }
        
        return {"success": True, "context": context}
    
    def process_tick(self):
        """Process campaign manager tick - mostly reactive, no regular processing needed"""
        pass