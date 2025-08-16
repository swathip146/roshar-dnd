"""
RAG-Powered D&D Character Generation Assistant
Uses the RAG agent to generate D&D player characters based on rule queries and user preferences
"""
import json
import os
import random
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict

# Set tokenizers parallelism to avoid fork warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# D&D 5e Point Buy cost table
POINT_BUY_COST = {
    8: 0, 9: 1, 10: 2, 11: 3,
    12: 4, 13: 5, 14: 7, 15: 9
}

POINTS_BUDGET = 27  # standard 5e budget

# Direct vector database imports
from qdrant_client import QdrantClient
from haystack.components.embedders import SentenceTransformersTextEmbedder
from haystack import Document
import warnings
warnings.filterwarnings("ignore")

# Claude imports for LLM generation
try:
    from hwtgenielib.components.generators.chat import AppleGenAIChatGenerator
    from hwtgenielib.dataclasses import ChatMessage
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False

@dataclass
class CharacterStats:
    """Character ability scores"""
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10

@dataclass
class CharacterDetails:
    """Complete character information"""
    name: str = ""
    race: str = ""
    character_class: str = ""
    level: int = 1
    background: str = ""
    stats: CharacterStats = None
    hit_points: int = 0
    armor_class: int = 10
    proficiency_bonus: int = 2
    skills: List[str] = None
    equipment: List[str] = None
    spells: List[str] = None
    features: List[str] = None
    personality_traits: str = ""
    ideals: str = ""
    bonds: str = ""
    flaws: str = ""
    backstory: str = ""
    
    def __post_init__(self):
        if self.stats is None:
            self.stats = CharacterStats()
        if self.skills is None:
            self.skills = []
        if self.equipment is None:
            self.equipment = []
        if self.spells is None:
            self.spells = []
        if self.features is None:
            self.features = []

def calculate_point_buy_cost(score):
    """Return the point-buy cost of a given ability score."""
    return POINT_BUY_COST.get(score, None)

def total_point_buy_cost(scores):
    """Return total point cost for a list of scores."""
    return sum(calculate_point_buy_cost(s) for s in scores)

class CharacterGenerator:
    """RAG-powered character generation system"""
    
    # Default number of documents to retrieve from vector database
    DEFAULT_TOP_K = 5
    EQUIPMENT_TOP_K = 5
    PERSONALITY_TOP_K = 5
    
    def __init__(self, collection_name: str = "dnd_documents", verbose: bool = False):
        """Initialize the character generator with RAG agent"""
        self.collection_name = collection_name
        self.verbose = verbose
        self.rulebook = "D&D 5e SRD"  # Default rulebook
        self.available_rulebooks = [
            "D&D 5e SRD",
            "Cosmere 5e (Roshar)"
        ]
        
        # Initialize direct vector database access and LLM
        self._initialize_vector_client()
        self._initialize_llm()
    
    def _initialize_llm(self):
        """Initialize Claude LLM for content generation"""
        try:
            if CLAUDE_AVAILABLE:
                self.llm = AppleGenAIChatGenerator(
                    model="aws:anthropic.claude-sonnet-4-20250514-v1:0"
                )
                if self.verbose:
                    print("✓ Claude LLM initialized for content generation")
            else:
                self.llm = None
                if self.verbose:
                    print("⚠️  Claude not available, using fallback content generation")
        except Exception as e:
            self.llm = None
            if self.verbose:
                print(f"❌ Failed to initialize Claude: {e}")
    
    def _initialize_vector_client(self):
        """Initialize direct vector database client"""
        try:
            self.vector_client = QdrantClient(host="localhost", port=6333)
            self.embedder = SentenceTransformersTextEmbedder(
                model="sentence-transformers/all-MiniLM-L6-v2"
            )
            self.embedder.warm_up()
            if self.verbose:
                print("✓ Direct vector database client initialized")
        except Exception as e:
            if self.verbose:
                print(f"❌ Failed to initialize vector client: {e}")
            self.vector_client = None
            self.embedder = None
    
    def retrieve_context_documents(self, query: str, top_k: int = None) -> List[Document]:
        """Directly retrieve relevant documents from vector database"""
        if not self.vector_client or not self.embedder:
            return []
        
        if top_k is None:
            top_k = self.DEFAULT_TOP_K
        
        try:
            # Generate embedding for the query
            embedding_result = self.embedder.run(text=query)
            query_embedding = embedding_result["embedding"]
            
            # Search in vector database
            search_result = self.vector_client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=top_k
            )
            
            # Convert to Haystack Documents
            documents = []
            for hit in search_result:
                doc = Document(
                    content=hit.payload.get("content", ""),
                    meta={
                        "source_file": hit.payload.get("source_file", "Unknown"),
                        "document_tag": hit.payload.get("document_tag", "Unknown"),
                        "score": hit.score
                    }
                )
                documents.append(doc)
            
            return documents
        except Exception as e:
            if self.verbose:
                print(f"Error retrieving context: {e}")
            return []
    
    def generate_with_llm(self, prompt: str, context: str = "") -> str:
        """Generate content using Claude LLM with context"""
        if not self.llm:
            return "LLM not available for content generation"
        
        try:
            full_prompt = f"""You are a D&D character creation assistant. Generate specific, detailed, and rule-appropriate content.

Context from D&D rules database:
{context}

Task: {prompt}

Generate detailed, specific content that fits D&D 5e rules. Be creative but accurate to the game's mechanics and lore."""

            messages = [ChatMessage.from_user(full_prompt)]
            result = self.llm.run(messages=messages)
            
            if result and "replies" in result and result["replies"]:
                return result["replies"][0].text
            else:
                return "Failed to generate content"
                
        except Exception as e:
            if self.verbose:
                print(f"Error generating with LLM: {e}")
            return "Error generating content"
    
    def set_rulebook(self, rulebook: str) -> bool:
        """Set the rulebook to use for character generation"""
        if rulebook in self.available_rulebooks:
            self.rulebook = rulebook
            if self.verbose:
                print(f"✓ Rulebook set to: {rulebook}")
            return True
        else:
            if self.verbose:
                print(f"❌ Unknown rulebook: {rulebook}")
                print(f"Available rulebooks: {', '.join(self.available_rulebooks)}")
            return False
    
    def get_available_races(self) -> List[str]:
        """Get available character races from the rulebook"""
        # Standard D&D 5e races
        common_races = [
            "Human", "Elf", "Dwarf", "Halfling", "Dragonborn",
            "Gnome", "Half-Elf", "Half-Orc", "Tiefling"
        ]
        
        if "Roshar" in self.rulebook or "Cosmere" in self.rulebook:
            common_races.extend(["Alethi", "Azish", "Thaylen", "Veden", "Horneater"])
        
        return common_races
    
    def get_available_classes(self) -> List[str]:
        """Get available character classes from the rulebook"""
        # Standard D&D 5e classes
        common_classes = [
            "Barbarian", "Bard", "Cleric", "Druid", "Fighter",
            "Monk", "Paladin", "Ranger", "Rogue", "Sorcerer",
            "Warlock", "Wizard"
        ]
        
        if "Roshar" in self.rulebook or "Cosmere" in self.rulebook:
            common_classes.extend(["Radiant", "Worldsinger"])
        
        return common_classes
    
    def get_available_backgrounds(self) -> List[str]:
        """Get available character backgrounds from the rulebook"""
        # Standard backgrounds
        backgrounds = [
            "Acolyte", "Criminal", "Folk Hero", "Noble", "Sage",
            "Soldier", "Charlatan", "Entertainer", "Guild Artisan",
            "Hermit", "Outlander", "Sailor"
        ]
        
        return backgrounds
    
    def roll_ability_scores(self, method: str = "4d6_drop_lowest") -> CharacterStats:
        """Generate ability scores using specified method"""
        if method == "4d6_drop_lowest":
            def roll_stat():
                rolls = [random.randint(1, 6) for _ in range(4)]
                return sum(sorted(rolls)[1:])  # Drop lowest
        elif method == "3d6":
            def roll_stat():
                return sum(random.randint(1, 6) for _ in range(3))
        elif method == "point_buy":
            return self._handle_point_buy()
        else:
            def roll_stat():
                rolls = [random.randint(1, 6) for _ in range(4)]
                return sum(sorted(rolls)[1:])  # Default to 4d6 drop lowest
        
        return CharacterStats(
            strength=roll_stat(),
            dexterity=roll_stat(),
            constitution=roll_stat(),
            intelligence=roll_stat(),
            wisdom=roll_stat(),
            charisma=roll_stat()
        )
    
    def _handle_point_buy(self, race: str = "", character_class: str = "") -> CharacterStats:
        """Handle point buy ability score generation with user input"""
        print("\n=== Point Buy System ===")
        print("You have 27 points to spend on ability scores.")
        print("Each ability starts at 8. Costs:")
        print("  Score 9-13: 1 point each")
        print("  Score 14-15: 2 extra points each")
        print("  Maximum base score: 15 (before racial bonuses)")
        
        # Show racial bonuses if race is provided
        if race:
            racial_bonuses = self.get_racial_modifiers(race)
            if racial_bonuses:
                print(f"\n{race} racial bonuses that will be applied:")
                for ability, bonus in racial_bonuses.items():
                    if bonus > 0:
                        print(f"  {ability.title()}: +{bonus}")
                print("\nAfter racial bonuses: Max 1 ability at 17 (others ≤15) OR Max 2 abilities at 16")
            else:
                print(f"\n{race} has no racial ability score bonuses.")
        
        while True:
            print("\nEnter ability scores separated by commas (Str,Dex,Con,Int,Wis,Cha):")
            print("Example: 15,14,13,12,10,8")
            try:
                scores_input = input("Base scores (8-15 each): ").strip()
                
                # Parse comma-separated values
                score_strings = [s.strip() for s in scores_input.split(',')]
                if len(score_strings) != 6:
                    print("❌ Please enter exactly 6 ability scores separated by commas.")
                    continue
                
                scores = [int(s) for s in score_strings]
                strength, dexterity, constitution, intelligence, wisdom, charisma = scores
                
                # Validate range
                if any(score < 8 or score > 15 for score in scores):
                    print("❌ All base scores must be between 8 and 15.")
                    continue
                
                # Create base stats and apply racial bonuses first
                base_stats = CharacterStats(strength, dexterity, constitution, intelligence, wisdom, charisma)
                
                # Apply racial bonuses before calculating point cost
                if race:
                    final_stats = self.apply_racial_modifiers(base_stats, race)
                    final_scores = [final_stats.strength, final_stats.dexterity, final_stats.constitution,
                                  final_stats.intelligence, final_stats.wisdom, final_stats.charisma]
                else:
                    final_stats = base_stats
                    final_scores = scores
                
                # Calculate point cost using base scores only (before racial bonuses)
                total_cost = total_point_buy_cost(scores)
                
                if total_cost != POINTS_BUDGET:
                    print(f"❌ Point cost is {total_cost}, but you need exactly {POINTS_BUDGET} points.")
                    print("Point costs: 8=0, 9=1, 10=2, 11=3, 12=4, 13=5, 14=7, 15=9")
                    if race:
                        print("Note: Point costs are calculated BEFORE racial bonuses are applied.")
                    retry = input("Try again? (y/n/random): ").strip().lower()
                    if retry in ['n', 'no']:
                        print("Using random 4d6 drop lowest instead.")
                        return self.roll_ability_scores("4d6_drop_lowest")
                    elif retry in ['random', 'r']:
                        return self._generate_random_point_buy()
                    continue
                
                # Check final score constraints (no ability can exceed 17)
                if max(final_scores) > 17:
                    print("❌ No ability can exceed 17 after racial bonuses.")
                    continue
                
                print(f"\n✓ Point buy valid! Used {total_cost}/{POINTS_BUDGET} points.")
                if race:
                    print("Final scores after racial bonuses:")
                    print(f"  Str: {base_stats.strength} → {final_stats.strength}")
                    print(f"  Dex: {base_stats.dexterity} → {final_stats.dexterity}")
                    print(f"  Con: {base_stats.constitution} → {final_stats.constitution}")
                    print(f"  Int: {base_stats.intelligence} → {final_stats.intelligence}")
                    print(f"  Wis: {base_stats.wisdom} → {final_stats.wisdom}")
                    print(f"  Cha: {base_stats.charisma} → {final_stats.charisma}")
                else:
                    print(f"✓ Point buy valid! Used {total_cost}/{POINTS_BUDGET} points.")
                
                return base_stats
                    
            except ValueError:
                print("❌ Please enter valid numbers separated by commas.")
                continue
    
    def _generate_random_point_buy(self) -> CharacterStats:
        """Generate a random valid point buy allocation using the correct D&D 5e logic"""
        while True:
            scores = [8] * 6
            points_left = POINTS_BUDGET

            # Randomly distribute points
            while points_left > 0:
                idx = random.randint(0, 5)
                if scores[idx] < 15:
                    cost_next = calculate_point_buy_cost(scores[idx] + 1) - calculate_point_buy_cost(scores[idx])
                    if points_left >= cost_next:
                        scores[idx] += 1
                        points_left -= cost_next
                    else:
                        break
                else:
                    continue

            if total_point_buy_cost(scores) <= POINTS_BUDGET:
                return CharacterStats(*scores)
    
    def get_racial_modifiers(self, race: str) -> Dict[str, int]:
        """Get ability score modifiers for a race"""
        # Standard D&D 5e racial ability score increases
        racial_bonuses = {
            "human": {"strength": 1, "dexterity": 1, "constitution": 1, "intelligence": 1, "wisdom": 1, "charisma": 1},
            "elf": {"dexterity": 2},
            "dwarf": {"constitution": 2},
            "halfling": {"dexterity": 2},
            "dragonborn": {"strength": 2, "charisma": 1},
            "gnome": {"intelligence": 2},
            "half-elf": {"charisma": 2},
            "half-orc": {"strength": 2, "constitution": 1},
            "tiefling": {"intelligence": 1, "charisma": 2}
        }
        
        return racial_bonuses.get(race.lower(), {})
    
    def apply_racial_modifiers(self, stats: CharacterStats, race: str) -> CharacterStats:
        """Apply racial ability score modifiers"""
        modifiers = self.get_racial_modifiers(race)
        
        stats.strength += modifiers.get("strength", 0)
        stats.dexterity += modifiers.get("dexterity", 0)
        stats.constitution += modifiers.get("constitution", 0)
        stats.intelligence += modifiers.get("intelligence", 0)
        stats.wisdom += modifiers.get("wisdom", 0)
        stats.charisma += modifiers.get("charisma", 0)
        
        return stats
    
    def calculate_derived_stats(self, character: CharacterDetails) -> CharacterDetails:
        """Calculate HP, AC, and other derived statistics"""
        # Hit Points calculation based on class
        class_hp_base = {
            "barbarian": 12, "fighter": 10, "paladin": 10, "ranger": 10,
            "bard": 8, "cleric": 8, "druid": 8, "monk": 8, "rogue": 8, "warlock": 8,
            "sorcerer": 6, "wizard": 6
        }
        
        base_hp = class_hp_base.get(character.character_class.lower(), 8)
        con_modifier = (character.stats.constitution - 10) // 2
        character.hit_points = base_hp + con_modifier + (character.level - 1) * (base_hp // 2 + 1 + con_modifier)
        
        # Armor Class (base 10 + dex modifier, will be modified by armor)
        dex_modifier = (character.stats.dexterity - 10) // 2
        character.armor_class = 10 + dex_modifier
        
        # Proficiency bonus
        character.proficiency_bonus = 2 + ((character.level - 1) // 4)
        
        return character
    
    def get_starting_equipment(self, character_class: str, background: str) -> List[str]:
        """Get starting equipment using vector database and LLM generation"""
        # Query for class equipment
        class_query = f"{character_class} starting equipment armor weapons tools gear"
        class_docs = self.retrieve_context_documents(class_query, top_k=self.EQUIPMENT_TOP_K)
        
        # Query for background equipment
        background_query = f"{background} background equipment tools starting gear"
        background_docs = self.retrieve_context_documents(background_query, top_k=self.EQUIPMENT_TOP_K)
        
        # Combine context from retrieved documents
        context = ""
        for doc in class_docs + background_docs:
            if len(doc.content) > 50:
                context += f"Source: {doc.meta.get('source_file', 'Unknown')}\n{doc.content[:300]}\n\n"
        
        # Use LLM to generate equipment list based on context
        if context and self.llm:
            prompt = f"Based on the D&D 5e rules context provided, list the starting equipment for a {character_class} with {background} background. Provide a clean list of equipment items only, one per line."
            equipment_text = self.generate_with_llm(prompt, context)
            
            # Parse equipment from LLM response
            equipment = []
            if equipment_text and "not available" not in equipment_text.lower():
                lines = equipment_text.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and len(line) > 3 and len(line) < 60:
                        # Clean up list markers
                        line = line.lstrip('•-*123456789. ')
                        if line:
                            equipment.append(line)
        else:
            equipment = []
        
        # If no equipment found, use fallback
        if not equipment:
            equipment = self._get_fallback_equipment(character_class, background)
        
        return equipment[:8]  # Limit to reasonable number of items
    
    def _get_fallback_equipment(self, character_class: str, background: str) -> List[str]:
        """Fallback equipment when vector database doesn't provide sufficient information"""
        class_equipment = {
            "fighter": ["Leather armor", "Shield", "Longsword", "Handaxe (2)", "Explorer's pack"],
            "wizard": ["Spellbook", "Dagger", "Component pouch", "Scholar's pack"],
            "rogue": ["Leather armor", "Shortsword (2)", "Thieves' tools", "Dagger", "Burglar's pack"],
            "cleric": ["Scale mail", "Shield", "Mace", "Light crossbow", "Priest's pack"],
            "barbarian": ["Leather armor", "Shield", "Handaxe (2)", "Javelin (4)", "Explorer's pack"],
            "ranger": ["Leather armor", "Shortsword (2)", "Longbow", "Quiver with 20 arrows", "Explorer's pack"],
            "paladin": ["Chain mail", "Shield", "Longsword", "Javelin (5)", "Explorer's pack"],
            "monk": ["Leather armor", "Shortsword", "Dart (10)", "Dungeoneer's pack"],
            "bard": ["Leather armor", "Rapier", "Lute", "Dagger", "Entertainer's pack"],
            "sorcerer": ["Dagger (2)", "Component pouch", "Light crossbow", "Dungeoneer's pack"],
            "warlock": ["Leather armor", "Scimitar", "Simple weapon", "Light crossbow", "Dungeoneer's pack"],
            "druid": ["Leather armor", "Shield", "Scimitar", "Dart (4)", "Explorer's pack"]
        }
        
        background_equipment = {
            "acolyte": ["Holy symbol", "Prayer book", "Incense (5 sticks)", "Vestments", "Belt pouch with 15 gp"],
            "criminal": ["Crowbar", "Dark clothes with hood", "Thieves' tools", "Belt pouch with 15 gp"],
            "folk hero": ["Smith's tools", "Shovel", "Work clothes", "Belt pouch with 10 gp"],
            "noble": ["Signet ring", "Fine clothes", "Scroll of pedigree", "Purse with 25 gp"],
            "sage": ["Ink and quill", "Parchment sheets (10)", "Robes", "Belt pouch with 10 gp"],
            "soldier": ["Insignia of rank", "Playing cards", "Common clothes", "Belt pouch with 10 gp"]
        }
        
        equipment = []
        equipment.extend(class_equipment.get(character_class.lower(), ["Basic gear"]))
        equipment.extend(background_equipment.get(background.lower(), ["Belt pouch with 10 gp"]))
        return equipment
    
    def get_class_features(self, character_class: str, level: int) -> List[str]:
        """Get class features using vector database and LLM generation"""
        query = f"{character_class} level {level} class features abilities spellcasting"
        docs = self.retrieve_context_documents(query, top_k=self.DEFAULT_TOP_K)
        
        # Combine context from retrieved documents
        context = ""
        for doc in docs:
            if character_class.lower() in doc.content.lower():
                context += f"Source: {doc.meta.get('source_file', 'Unknown')}\n{doc.content}\n\n"
        
        features = []
        
        # Use LLM to extract and format features from context
        if context and self.llm:
            prompt = f"Extract the specific class features for a level {level} {character_class} from the provided D&D 5e rules. List each feature with a brief description. Format as: 'Feature Name: Description'"
            features_text = self.generate_with_llm(prompt, context)
            
            if features_text and "not available" not in features_text.lower():
                lines = features_text.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and len(line) > 10 and ':' in line:
                        features.append(line)
        
        # If no features found from vector database, use fallback
        if not features:
            features = self._get_fallback_class_features(character_class, level)
        
        return features[:6]  # Limit to most relevant features
    
    def _get_fallback_class_features(self, character_class: str, level: int) -> List[str]:
        """Fallback class features based on D&D 5e rules"""
        class_features = {
            1: {
                "fighter": ["Fighting Style: Choose a fighting style", "Second Wind: Regain 1d10+level hit points"],
                "wizard": ["Spellcasting: Can cast wizard spells", "Arcane Recovery: Recover spell slots on short rest"],
                "rogue": ["Expertise: Double proficiency bonus on two skills", "Sneak Attack: Extra 1d6 damage", "Thieves' Cant: Secret language"],
                "cleric": ["Spellcasting: Can cast cleric spells", "Divine Domain: Choose a divine domain"],
                "barbarian": ["Rage: +2 damage, advantage on Strength checks, resistance to physical damage", "Unarmored Defense: AC = 10 + Dex + Con"],
                "ranger": ["Favored Enemy: Choose a favored enemy type", "Natural Explorer: Choose a favored terrain"],
                "paladin": ["Divine Sense: Detect celestials, fiends, and undead", "Lay on Hands: Heal 5 hit points per level"],
                "monk": ["Unarmored Defense: AC = 10 + Dex + Wis", "Martial Arts: Use Dexterity for unarmed strikes"],
                "bard": ["Spellcasting: Can cast bard spells", "Bardic Inspiration: Give allies bonus dice"],
                "sorcerer": ["Spellcasting: Can cast sorcerer spells", "Sorcerous Origin: Choose magical origin"],
                "warlock": ["Otherworldly Patron: Choose a patron", "Pact Magic: Short rest spell recovery"],
                "druid": ["Druidcraft: Ritual spell casting and nature magic", "Spellcasting: Can cast druid spells"]
            }
        }
        
        return class_features.get(level, {}).get(character_class.lower(), [f"{character_class} Level {level} features"])
    
    def get_racial_traits(self, race: str) -> List[str]:
        """Get racial traits using vector database and LLM generation"""
        query = f"{race} racial traits abilities darkvision resistance proficiency"
        docs = self.retrieve_context_documents(query, top_k=self.DEFAULT_TOP_K)
        
        # Combine context from retrieved documents
        context = ""
        for doc in docs:
            if race.lower() in doc.content.lower():
                context += f"Source: {doc.meta.get('source_file', 'Unknown')}\n{doc.content}\n\n"
        
        traits = []
        
        # Use LLM to extract racial traits from context
        if context and self.llm:
            prompt = f"Extract the specific racial traits and abilities for {race} from the provided D&D 5e rules. List each trait with a brief description. Format as: 'Trait Name: Description'"
            traits_text = self.generate_with_llm(prompt, context)
            
            if traits_text and "not available" not in traits_text.lower():
                lines = traits_text.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and len(line) > 10 and ':' in line:
                        traits.append(line)
        
        # If no traits found from vector database, use fallback
        if not traits:
            traits = self._get_fallback_racial_traits(race)
        
        return traits[:6]  # Limit to most relevant traits
    
    def _get_fallback_racial_traits(self, race: str) -> List[str]:
        """Fallback racial traits based on D&D 5e rules"""
        racial_traits = {
            "human": ["Versatile: +1 to all ability scores", "Extra Language: Learn one additional language", "Extra Skill: Gain proficiency in one skill"],
            "elf": ["Darkvision: See in dim light within 60 feet", "Keen Senses: Proficiency in Perception", "Fey Ancestry: Advantage against charm, immune to sleep", "Trance: Meditate for 4 hours instead of sleeping"],
            "dwarf": ["Darkvision: See in dim light within 60 feet", "Dwarven Resilience: Advantage against poison", "Stonecunning: Double proficiency on stonework History checks", "Dwarven Combat Training: Proficiency with battleaxe, handaxe, light hammer, warhammer"],
            "halfling": ["Lucky: Reroll natural 1s on attack rolls, ability checks, and saving throws", "Brave: Advantage on saving throws against being frightened", "Halfling Nimbleness: Move through space of Medium or larger creatures"],
            "dragonborn": ["Draconic Ancestry: Choose a dragon type for breath weapon and resistance", "Breath Weapon: Use action to exhale destructive energy", "Damage Resistance: Resist damage type associated with draconic ancestry"],
            "gnome": ["Darkvision: See in dim light within 60 feet", "Gnome Cunning: Advantage on Intelligence, Wisdom, and Charisma saving throws against magic"],
            "half-elf": ["Darkvision: See in dim light within 60 feet", "Fey Ancestry: Advantage against charm, immune to sleep", "Two Skills: Gain proficiency in two skills", "Extra Language: Learn one additional language"],
            "half-orc": ["Darkvision: See in dim light within 60 feet", "Relentless Endurance: Drop to 1 hit point instead of 0 once per long rest", "Savage Attacks: Roll one additional weapon damage die on critical hits"],
            "tiefling": ["Darkvision: See in dim light within 60 feet", "Hellish Resistance: Resistance to fire damage", "Infernal Legacy: Know thaumaturgy cantrip, cast hellish rebuke and darkness spells"]
        }
        
        return racial_traits.get(race.lower(), [f"{race} racial traits"])
    
    def generate_personality(self, race: str, character_class: str, background: str) -> Dict[str, str]:
        """Generate personality using vector database context and LLM"""
        # Retrieve context about race, class, and background
        race_query = f"{race} culture society personality traits"
        race_docs = self.retrieve_context_documents(race_query, top_k=self.PERSONALITY_TOP_K)
        
        background_query = f"{background} background personality traits ideals bonds"
        background_docs = self.retrieve_context_documents(background_query, top_k=self.PERSONALITY_TOP_K)
        
        # Combine context from retrieved documents
        context = ""
        for doc in race_docs + background_docs:
            if len(doc.content) > 50:
                context += f"Source: {doc.meta.get('source_file', 'Unknown')}\n{doc.content[:300]}\n\n"
        
        # Use LLM to generate personality based on context
        if context and self.llm:
            prompt = f"""Create personality traits, ideals, bonds, and flaws for a {race} {character_class} with {background} background.
            
Generate exactly 4 items in this format:
Personality Traits: [specific trait description]
Ideals: [character's driving ideals]
Bonds: [what connects them to the world]
Flaws: [character weakness or quirk]

Make them specific and interesting for roleplay."""
            
            personality_text = self.generate_with_llm(prompt, context)
            
            # Parse personality from LLM response
            personality = {}
            if personality_text:
                lines = personality_text.split('\n')
                for line in lines:
                    line = line.strip()
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip().lower().replace(' ', '_')
                        if key in ['personality_traits', 'ideals', 'bonds', 'flaws']:
                            personality[key] = value.strip()
        else:
            personality = {}
        
        # Ensure all personality fields are present
        if len(personality) < 4:
            personality = self._generate_fallback_personality(race, character_class, background, context)
        
        return personality
    
    def _generate_fallback_personality(self, race: str, character_class: str, background: str, rag_response: str) -> Dict[str, str]:
        """Generate fallback personality when RAG response is insufficient"""
        
        # Background-based traits
        background_traits = {
            "acolyte": "devoted to their faith and seeks to spread their deity's influence",
            "criminal": "has a network of contacts in the underworld and values loyalty among thieves",
            "folk hero": "stands up for the common people and has a strong sense of justice",
            "noble": "expects to be treated with respect befitting their station",
            "sage": "is always curious about ancient lore and forgotten knowledge",
            "soldier": "has strong discipline and loyalty to their former unit"
        }
        
        # Class-based motivations
        class_motivations = {
            "fighter": "seeks to prove their combat prowess and protect others",
            "wizard": "pursues arcane knowledge and magical understanding",
            "rogue": "values freedom and operates by their own moral code",
            "cleric": "serves their deity's will and helps those in need",
            "barbarian": "follows their instincts and fights for their tribe's honor",
            "monk": "seeks inner peace and physical perfection"
        }
        
        # Use RAG response content if available, otherwise use templates
        if len(rag_response) > 100 and "error" not in rag_response.lower():
            # Try to extract meaningful content from RAG response
            trait_text = f"A {race} {character_class} who {background_traits.get(background.lower(), 'follows their chosen path')} and {class_motivations.get(character_class.lower(), 'pursues their goals')}. {rag_response[:200]}..."
        else:
            trait_text = f"A {race} {character_class} who {background_traits.get(background.lower(), 'follows their chosen path')} and {class_motivations.get(character_class.lower(), 'pursues their goals')}."
        
        return {
            "personality_traits": trait_text,
            "ideals": f"Justice and {class_motivations.get(character_class.lower(), 'personal growth')}",
            "bonds": f"Connected to their {background.lower()} background and {race.lower()} heritage",
            "flaws": f"Sometimes too focused on their {class_motivations.get(character_class.lower(), 'goals')} to consider consequences"
        }
    
    def create_character(self, preferences: Dict[str, Any]) -> CharacterDetails:
        """Create a complete character based on user preferences"""
        character = CharacterDetails()
        
        # Set basic information
        character.name = preferences.get("name", "")
        character.race = preferences.get("race", "")
        character.character_class = preferences.get("class", "")
        character.level = preferences.get("level", 1)
        character.background = preferences.get("background", "")
        
        # Generate ability scores
        score_method = preferences.get("ability_score_method", "4d6_drop_lowest")
        if score_method == "point_buy":
            # Pass race and class info for point buy validation
            character.stats = self._handle_point_buy(character.race, character.character_class)
        else:
            character.stats = self.roll_ability_scores(score_method)
        
        # Apply racial modifiers
        if character.race:
            character.stats = self.apply_racial_modifiers(character.stats, character.race)
        
        # Calculate derived stats
        character = self.calculate_derived_stats(character)
        
        # Get equipment
        if character.character_class and character.background:
            character.equipment = self.get_starting_equipment(character.character_class, character.background)
        
        # Get class features
        if character.character_class:
            character.features.extend(self.get_class_features(character.character_class, character.level))
        
        # Get racial traits
        if character.race:
            character.features.extend(self.get_racial_traits(character.race))
        
        # Generate personality
        if character.race and character.character_class and character.background:
            personality = self.generate_personality(character.race, character.character_class, character.background)
            character.personality_traits = personality["personality_traits"]
            character.ideals = personality["ideals"]
            character.bonds = personality["bonds"]
            character.flaws = personality["flaws"]
        
        return character
    
    def format_character_sheet(self, character: CharacterDetails) -> str:
        """Format character as a readable character sheet"""
        sheet = f"""
=== D&D CHARACTER SHEET ===
Rulebook: {self.rulebook}

NAME: {character.name or '[Name]'}
RACE: {character.race or '[Race]'}
CLASS: {character.character_class or '[Class]'}
LEVEL: {character.level}
BACKGROUND: {character.background or '[Background]'}

ABILITY SCORES:
  Strength:     {character.stats.strength} ({(character.stats.strength-10)//2:+d})
  Dexterity:    {character.stats.dexterity} ({(character.stats.dexterity-10)//2:+d})
  Constitution: {character.stats.constitution} ({(character.stats.constitution-10)//2:+d})
  Intelligence: {character.stats.intelligence} ({(character.stats.intelligence-10)//2:+d})
  Wisdom:       {character.stats.wisdom} ({(character.stats.wisdom-10)//2:+d})
  Charisma:     {character.stats.charisma} ({(character.stats.charisma-10)//2:+d})

COMBAT STATS:
  Hit Points: {character.hit_points}
  Armor Class: {character.armor_class}
  Proficiency Bonus: +{character.proficiency_bonus}

FEATURES & TRAITS:
{chr(10).join(f"  - {feature}" for feature in character.features)}

EQUIPMENT:
{chr(10).join(f"  - {item}" for item in character.equipment)}

PERSONALITY:
  Traits: {character.personality_traits}
  Ideals: {character.ideals}
  Bonds: {character.bonds}
  Flaws: {character.flaws}

BACKSTORY:
{character.backstory or '[To be developed]'}
"""
        return sheet
    
    def export_character_to_txt(self, character: CharacterDetails, filename: str) -> bool:
        """Export character to text file for vector database indexing"""
        try:
            # Create comprehensive text content for vector database
            content = f"""CHARACTER: {character.name or 'Unnamed'}

BASIC INFORMATION:
Name: {character.name or 'Unnamed'}
Race: {character.race or 'Unknown'}
Class: {character.character_class or 'Unknown'}
Level: {character.level}
Background: {character.background or 'Unknown'}
Rulebook: {self.rulebook}

ABILITY SCORES:
Strength: {character.stats.strength} (modifier: {(character.stats.strength-10)//2:+d})
Dexterity: {character.stats.dexterity} (modifier: {(character.stats.dexterity-10)//2:+d})
Constitution: {character.stats.constitution} (modifier: {(character.stats.constitution-10)//2:+d})
Intelligence: {character.stats.intelligence} (modifier: {(character.stats.intelligence-10)//2:+d})
Wisdom: {character.stats.wisdom} (modifier: {(character.stats.wisdom-10)//2:+d})
Charisma: {character.stats.charisma} (modifier: {(character.stats.charisma-10)//2:+d})

COMBAT STATISTICS:
Hit Points: {character.hit_points}
Armor Class: {character.armor_class}
Proficiency Bonus: +{character.proficiency_bonus}

FEATURES AND TRAITS:
{chr(10).join(f"- {feature}" for feature in character.features)}

EQUIPMENT:
{chr(10).join(f"- {item}" for item in character.equipment)}

SKILLS:
{chr(10).join(f"- {skill}" for skill in character.skills) if character.skills else "No specific skills listed"}

SPELLS:
{chr(10).join(f"- {spell}" for spell in character.spells) if character.spells else "No spells known"}

PERSONALITY:
Personality Traits: {character.personality_traits}
Ideals: {character.ideals}
Bonds: {character.bonds}
Flaws: {character.flaws}

BACKSTORY:
{character.backstory or 'Backstory to be developed'}

CHARACTER BUILD SUMMARY:
This is a level {character.level} {character.race} {character.character_class} with {character.background} background.
Key ability scores: STR {character.stats.strength}, DEX {character.stats.dexterity}, CON {character.stats.constitution}, INT {character.stats.intelligence}, WIS {character.stats.wisdom}, CHA {character.stats.charisma}.
Combat stats: {character.hit_points} HP, AC {character.armor_class}, +{character.proficiency_bonus} proficiency bonus.

TAGS FOR INDEXING:
Character, {character.race}, {character.character_class}, {character.background}, Level{character.level}, {self.rulebook}"""

            # Write to text file
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return True
        except Exception as e:
            if self.verbose:
                print(f"Error exporting character to txt: {e}")
            return False

    def save_character(self, character: CharacterDetails, filename: str) -> bool:
        """Save character to JSON file and export to TXT for vector database indexing"""
        try:
            # Save JSON file
            character_data = asdict(character)
            with open(filename, 'w') as f:
                json.dump(character_data, f, indent=2)
            
            # Create corresponding TXT file for vector database
            txt_filename = filename.replace('.json', '.txt')
            if not txt_filename.endswith('.txt'):
                txt_filename += '.txt'
            
            txt_success = self.export_character_to_txt(character, txt_filename)
            
            if self.verbose and txt_success:
                print(f"✓ Character also exported to: {txt_filename}")
            
            return True
        except Exception as e:
            if self.verbose:
                print(f"Error saving character: {e}")
            return False
    
    def load_character(self, filename: str) -> Optional[CharacterDetails]:
        """Load character from JSON file"""
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
            
            # Reconstruct CharacterStats
            if 'stats' in data:
                data['stats'] = CharacterStats(**data['stats'])
            
            return CharacterDetails(**data)
        except Exception as e:
            if self.verbose:
                print(f"Error loading character: {e}")
            return None


def main():
    """Main function for interactive character generation"""
    print("=== RAG-Powered D&D Character Generator ===")
    print("Generate D&D characters using AI-assisted rule queries")
    print()
    
    # Initialize character generator
    print("Initializing character generator...")
    generator = CharacterGenerator(verbose=True)
    
    # Select rulebook
    print("\nAvailable rulebooks:")
    for i, rulebook in enumerate(generator.available_rulebooks, 1):
        print(f"{i}. {rulebook}")
    
    rulebook_choice = input(f"Select rulebook (1-{len(generator.available_rulebooks)}, default: 1): ").strip()
    
    if rulebook_choice.isdigit():
        choice_index = int(rulebook_choice) - 1
        if 0 <= choice_index < len(generator.available_rulebooks):
            selected_rulebook = generator.available_rulebooks[choice_index]
            generator.set_rulebook(selected_rulebook)
        else:
            print("Invalid choice, using default: D&D 5e SRD")
    elif rulebook_choice:
        # Handle direct name input as fallback
        if generator.set_rulebook(rulebook_choice):
            pass  # Successfully set
        else:
            print("Invalid rulebook name, using default: D&D 5e SRD")
    
    print("\n=== Character Generation Wizard ===")
    print("Press Enter to skip any field for random/default selection")
    
    preferences = {}
    
    # Character name
    preferences["name"] = input("\nCharacter name: ").strip()
    
    # Race selection
    available_races = generator.get_available_races()
    print("\nAvailable races:")
    for i, race in enumerate(available_races, 1):
        print(f"{i}. {race}")
    
    race_choice = input(f"Select race (1-{len(available_races)}, Enter for random): ").strip()
    
    if race_choice.isdigit():
        choice_index = int(race_choice) - 1
        if 0 <= choice_index < len(available_races):
            preferences["race"] = available_races[choice_index]
        else:
            print("Invalid choice, using random selection")
            preferences["race"] = random.choice(available_races)
    elif race_choice:
        # Handle direct name input as fallback
        if race_choice.title() in available_races:
            preferences["race"] = race_choice.title()
        else:
            print(f"Unknown race '{race_choice}', using random selection")
            preferences["race"] = random.choice(available_races)
    else:
        preferences["race"] = random.choice(available_races)
        print(f"Random race selected: {preferences['race']}")
    
    # Class selection
    available_classes = generator.get_available_classes()
    print("\nAvailable classes:")
    for i, character_class in enumerate(available_classes, 1):
        print(f"{i}. {character_class}")
    
    class_choice = input(f"Select class (1-{len(available_classes)}, Enter for random): ").strip()
    
    if class_choice.isdigit():
        choice_index = int(class_choice) - 1
        if 0 <= choice_index < len(available_classes):
            preferences["class"] = available_classes[choice_index]
        else:
            print("Invalid choice, using random selection")
            preferences["class"] = random.choice(available_classes)
    elif class_choice:
        # Handle direct name input as fallback
        if class_choice.title() in available_classes:
            preferences["class"] = class_choice.title()
        else:
            print(f"Unknown class '{class_choice}', using random selection")
            preferences["class"] = random.choice(available_classes)
    else:
        preferences["class"] = random.choice(available_classes)
        print(f"Random class selected: {preferences['class']}")
    
    # Background selection
    available_backgrounds = generator.get_available_backgrounds()
    print("\nAvailable backgrounds:")
    for i, background in enumerate(available_backgrounds, 1):
        print(f"{i}. {background}")
    
    background_choice = input(f"Select background (1-{len(available_backgrounds)}, Enter for random): ").strip()
    
    if background_choice.isdigit():
        choice_index = int(background_choice) - 1
        if 0 <= choice_index < len(available_backgrounds):
            preferences["background"] = available_backgrounds[choice_index]
        else:
            print("Invalid choice, using random selection")
            preferences["background"] = random.choice(available_backgrounds)
    elif background_choice:
        # Handle direct name input as fallback
        if background_choice.title() in available_backgrounds:
            preferences["background"] = background_choice.title()
        else:
            print(f"Unknown background '{background_choice}', using random selection")
            preferences["background"] = random.choice(available_backgrounds)
    else:
        preferences["background"] = random.choice(available_backgrounds)
        print(f"Random background selected: {preferences['background']}")
    
    # Level
    level_input = input("\nCharacter level (1-20, default 1): ").strip()
    try:
        level = int(level_input) if level_input else 1
        preferences["level"] = max(1, min(20, level))
    except ValueError:
        preferences["level"] = 1
    
    # Ability score method
    print("\nAbility score methods:")
    print("1. 4d6 drop lowest (default)")
    print("2. 3d6 straight")
    print("3. Point buy")
    method_choice = input("Select method (1-3): ").strip()
    
    method_map = {"1": "4d6_drop_lowest", "2": "3d6", "3": "point_buy"}
    preferences["ability_score_method"] = method_map.get(method_choice, "4d6_drop_lowest")
    
    # Generate character
    print("\n🎲 Generating character...")
    character = generator.create_character(preferences)
    
    # Display character sheet
    character_sheet = generator.format_character_sheet(character)
    print(character_sheet)
    
    # Character modification loop
    while True:
        print("\n=== Character Review ===")
        print("1. Accept character")
        print("2. Regenerate ability scores")
        print("3. Change name")
        print("4. Save character")
        print("5. Generate new character")
        print("6. Quit")
        
        choice = input("Select option (1-6): ").strip()
        
        if choice == "1":
            print("✓ Character accepted!")
            break
        elif choice == "2":
            character.stats = generator.roll_ability_scores(preferences["ability_score_method"])
            character.stats = generator.apply_racial_modifiers(character.stats, character.race)
            character = generator.calculate_derived_stats(character)
            print("\n🎲 New ability scores generated!")
            print(generator.format_character_sheet(character))
        elif choice == "3":
            new_name = input("Enter new name: ").strip()
            if new_name:
                character.name = new_name
                print(f"✓ Name changed to: {new_name}")
        elif choice == "4":
            filename = input("Enter filename (with .json extension): ").strip()
            if not filename.endswith('.json'):
                filename += '.json'
            if generator.save_character(character, filename):
                print(f"✓ Character saved to: {filename}")
            else:
                print("❌ Failed to save character")
        elif choice == "5":
            main()  # Restart character generation
            return
        elif choice == "6":
            print("Goodbye!")
            return
        else:
            print("Invalid choice, please try again.")


if __name__ == "__main__":
    main()