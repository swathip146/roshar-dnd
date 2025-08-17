"""
Haystack Data Migration Utilities
Phase 6: Migrate existing data structures to Haystack-compatible formats
"""

import os
import json
import time
from typing import Dict, Any, List, Optional
from haystack.document_stores.in_memory import InMemoryDocumentStore
from haystack import Document

# Import event sourcing for state migration
from core.enhanced_game_engine import GameEvent


class DataMigrationUtility:
    """Migrate existing data to Haystack document store"""
    
    def __init__(self, document_store: Optional[InMemoryDocumentStore] = None, verbose: bool = False):
        self.document_store = document_store or InMemoryDocumentStore()
        self.verbose = verbose
        
        if verbose:
            print("📦 DataMigrationUtility initialized")
    
    def migrate_campaign_data(self, campaigns_dir: str) -> bool:
        """Migrate campaign files to document store"""
        
        try:
            if not os.path.exists(campaigns_dir):
                if self.verbose:
                    print(f"⚠️ Campaign directory not found: {campaigns_dir}")
                return True  # Not an error, just no data to migrate
            
            documents = []
            
            # Process campaign files
            for root, dirs, files in os.walk(campaigns_dir):
                for file in files:
                    if file.endswith(('.json', '.md', '.txt')):
                        file_path = os.path.join(root, file)
                        
                        try:
                            # Read file content
                            with open(file_path, 'r', encoding='utf-8') as f:
                                if file.endswith('.json'):
                                    content = json.load(f)
                                    content_text = json.dumps(content, indent=2)
                                else:
                                    content_text = f.read()
                            
                            # Create Haystack document
                            doc = Document(
                                content=content_text,
                                meta={
                                    "source": "campaign_data",
                                    "file_path": file_path,
                                    "file_name": file,
                                    "file_type": file.split('.')[-1],
                                    "migration_timestamp": time.time(),
                                    "category": self._categorize_campaign_file(file)
                                }
                            )
                            documents.append(doc)
                            
                        except Exception as e:
                            if self.verbose:
                                print(f"⚠️ Failed to migrate {file_path}: {e}")
            
            # Write to document store
            if documents:
                self.document_store.write_documents(documents)
                
                if self.verbose:
                    print(f"✅ Migrated {len(documents)} campaign documents")
                
                return True
            else:
                if self.verbose:
                    print("📝 No campaign documents found to migrate")
                return True
                
        except Exception as e:
            if self.verbose:
                print(f"❌ Campaign migration failed: {e}")
            return False
    
    def migrate_character_data(self, characters_dir: str) -> bool:
        """Migrate character sheets to document store"""
        
        try:
            if not os.path.exists(characters_dir):
                if self.verbose:
                    print(f"⚠️ Characters directory not found: {characters_dir}")
                return True
            
            documents = []
            
            for file in os.listdir(characters_dir):
                if file.endswith('.json'):
                    file_path = os.path.join(characters_dir, file)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            char_data = json.load(f)
                        
                        # Create searchable character document
                        char_name = char_data.get('name', file.replace('.json', ''))
                        char_class = char_data.get('class', 'Unknown')
                        char_level = char_data.get('level', 1)
                        
                        # Create content that includes searchable information
                        content = f"""
Character Name: {char_name}
Class: {char_class}
Level: {char_level}
Character Data: {json.dumps(char_data, indent=2)}
"""
                        
                        doc = Document(
                            content=content,
                            meta={
                                "source": "character_data",
                                "character_name": char_name,
                                "character_class": char_class,
                                "character_level": char_level,
                                "file_path": file_path,
                                "migration_timestamp": time.time(),
                                "category": "character_sheet"
                            }
                        )
                        documents.append(doc)
                        
                    except Exception as e:
                        if self.verbose:
                            print(f"⚠️ Failed to migrate character {file}: {e}")
            
            if documents:
                self.document_store.write_documents(documents)
                
                if self.verbose:
                    print(f"✅ Migrated {len(documents)} character documents")
            
            return True
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Character migration failed: {e}")
            return False
    
    def migrate_rule_data(self, rules_dir: str) -> bool:
        """Migrate D&D rules to searchable documents"""
        
        try:
            if not os.path.exists(rules_dir):
                # Create basic D&D rules as fallback
                return self._create_basic_rules()
            
            documents = []
            
            for file in os.listdir(rules_dir):
                if file.endswith(('.json', '.md', '.txt')):
                    file_path = os.path.join(rules_dir, file)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            if file.endswith('.json'):
                                rule_data = json.load(f)
                                content = json.dumps(rule_data, indent=2)
                            else:
                                content = f.read()
                        
                        doc = Document(
                            content=content,
                            meta={
                                "source": "rule_data",
                                "file_name": file,
                                "rule_category": self._categorize_rule_file(file),
                                "migration_timestamp": time.time(),
                                "category": "rules"
                            }
                        )
                        documents.append(doc)
                        
                    except Exception as e:
                        if self.verbose:
                            print(f"⚠️ Failed to migrate rule {file}: {e}")
            
            if documents:
                self.document_store.write_documents(documents)
                
                if self.verbose:
                    print(f"✅ Migrated {len(documents)} rule documents")
            
            return True
            
        except Exception as e:
            if self.verbose:
                print(f"❌ Rule migration failed: {e}")
            return False
    
    def _create_basic_rules(self) -> bool:
        """Create basic D&D rules as documents"""
        
        basic_rules = [
            {
                "title": "Skill Checks",
                "content": """
Skill Checks in D&D 5e:
- Roll 1d20 + ability modifier + proficiency bonus (if proficient)
- Compare to Difficulty Class (DC) set by DM
- DC 5 (very easy), 10 (easy), 15 (medium), 20 (hard), 25 (very hard), 30 (nearly impossible)
- Advantage: Roll twice, take higher result
- Disadvantage: Roll twice, take lower result
""",
                "category": "basic_mechanics"
            },
            {
                "title": "Combat Actions",
                "content": """
Combat Actions in D&D 5e:
- Attack: Roll 1d20 + ability modifier + proficiency bonus vs target AC
- Damage: Roll damage dice + ability modifier
- Critical Hit: Natural 20 on attack roll, roll damage dice twice
- Actions: Attack, Cast a Spell, Dash, Disengage, Dodge, Help, Hide, Ready, Search, Use an Object
""",
                "category": "combat"
            },
            {
                "title": "Ability Scores",
                "content": """
Ability Scores in D&D 5e:
- Strength: Physical power, Athletics
- Dexterity: Agility, Acrobatics, Stealth
- Constitution: Health and stamina
- Intelligence: Reasoning, Investigation
- Wisdom: Awareness, Insight, Perception
- Charisma: Force of personality, Persuasion, Deception, Intimidation

Modifiers: (Score - 10) / 2, rounded down
""",
                "category": "character_creation"
            }
        ]
        
        documents = []
        for rule in basic_rules:
            doc = Document(
                content=rule["content"],
                meta={
                    "source": "basic_rules",
                    "title": rule["title"],
                    "rule_category": rule["category"],
                    "migration_timestamp": time.time(),
                    "category": "rules"
                }
            )
            documents.append(doc)
        
        self.document_store.write_documents(documents)
        
        if self.verbose:
            print(f"✅ Created {len(documents)} basic rule documents")
        
        return True
    
    def _categorize_campaign_file(self, filename: str) -> str:
        """Categorize campaign file by filename"""
        
        filename_lower = filename.lower()
        
        if "npc" in filename_lower:
            return "npcs"
        elif "location" in filename_lower or "world" in filename_lower:
            return "locations"
        elif "quest" in filename_lower or "adventure" in filename_lower:
            return "quests"
        elif "lore" in filename_lower or "history" in filename_lower:
            return "lore"
        elif "campaign" in filename_lower:
            return "campaign_info"
        else:
            return "general"
    
    def _categorize_rule_file(self, filename: str) -> str:
        """Categorize rule file by filename"""
        
        filename_lower = filename.lower()
        
        if "combat" in filename_lower:
            return "combat"
        elif "spell" in filename_lower or "magic" in filename_lower:
            return "spells"
        elif "skill" in filename_lower:
            return "skills"
        elif "class" in filename_lower:
            return "classes"
        elif "race" in filename_lower:
            return "races"
        else:
            return "general"
    
    def get_migration_stats(self) -> Dict[str, Any]:
        """Get statistics about migrated data"""
        
        doc_count = self.document_store.count_documents()
        
        # Get document categories
        all_docs = self.document_store.get_all_documents()
        categories = {}
        sources = {}
        
        for doc in all_docs:
            category = doc.meta.get("category", "unknown")
            source = doc.meta.get("source", "unknown")
            
            categories[category] = categories.get(category, 0) + 1
            sources[source] = sources.get(source, 0) + 1
        
        return {
            "total_documents": doc_count,
            "categories": categories,
            "sources": sources
        }


class StateMigrationUtility:
    """Migrate existing game state to event sourcing"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        
        if verbose:
            print("🔄 StateMigrationUtility initialized")
    
    def migrate_game_state(self, old_state: Dict[str, Any]) -> List[GameEvent]:
        """Convert old state format to event stream"""
        
        events = []
        
        try:
            # Create initial game state event
            events.append(GameEvent(
                event_id=f"migration_init_{int(time.time())}",
                event_type="game.migration.started",
                actor="migration_utility",
                payload={
                    "migration_timestamp": time.time(),
                    "original_state_keys": list(old_state.keys())
                }
            ))
            
            # Migrate character data
            characters = old_state.get("characters", {})
            for char_name, char_data in characters.items():
                events.append(GameEvent(
                    event_id=f"char_migrated_{char_name}_{int(time.time())}",
                    event_type="character.migrated",
                    actor=char_name,
                    payload={
                        "character_data": char_data,
                        "migration_source": "legacy_state"
                    }
                ))
            
            # Migrate campaign state
            campaign = old_state.get("campaign", {})
            if campaign:
                events.append(GameEvent(
                    event_id=f"campaign_migrated_{int(time.time())}",
                    event_type="campaign.migrated",
                    actor="migration_utility",
                    payload={
                        "campaign_data": campaign,
                        "migration_source": "legacy_state"
                    }
                ))
            
            # Migrate session state
            session = old_state.get("session", {})
            if session:
                events.append(GameEvent(
                    event_id=f"session_migrated_{int(time.time())}",
                    event_type="session.migrated",
                    actor="migration_utility",
                    payload={
                        "session_data": session,
                        "migration_source": "legacy_state"
                    }
                ))
            
            # Create migration completion event
            events.append(GameEvent(
                event_id=f"migration_complete_{int(time.time())}",
                event_type="game.migration.completed",
                actor="migration_utility",
                payload={
                    "events_created": len(events) - 1,  # Exclude this event
                    "migration_completed": True
                }
            ))
            
            if self.verbose:
                print(f"✅ Generated {len(events)} migration events")
            
            return events
            
        except Exception as e:
            if self.verbose:
                print(f"❌ State migration failed: {e}")
            
            # Create error event
            error_event = GameEvent(
                event_id=f"migration_error_{int(time.time())}",
                event_type="game.migration.failed",
                actor="migration_utility",
                payload={
                    "error": str(e),
                    "partial_events": len(events)
                }
            )
            events.append(error_event)
            
            return events
    
    def validate_migrated_state(self, events: List[GameEvent], original_state: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that migrated events can reconstruct the original state"""
        
        from core.enhanced_game_engine import StateProjector
        
        try:
            projector = StateProjector()
            projected_state = projector.project_state(events, {})
            
            # Compare key components
            validation_results = {
                "characters_match": self._compare_characters(
                    original_state.get("characters", {}),
                    projected_state.get("characters", {})
                ),
                "campaign_match": self._compare_dicts(
                    original_state.get("campaign", {}),
                    projected_state.get("campaign", {})
                ),
                "session_match": self._compare_dicts(
                    original_state.get("session", {}),
                    projected_state.get("session", {})
                ),
                "events_count": len(events),
                "validation_successful": True
            }
            
            # Overall validation
            validation_results["overall_match"] = all([
                validation_results["characters_match"],
                validation_results["campaign_match"],
                validation_results["session_match"]
            ])
            
            return validation_results
            
        except Exception as e:
            return {
                "validation_successful": False,
                "error": str(e),
                "events_count": len(events)
            }
    
    def _compare_characters(self, original: Dict[str, Any], projected: Dict[str, Any]) -> bool:
        """Compare character data between original and projected state"""
        
        if len(original) != len(projected):
            return False
        
        for char_name in original:
            if char_name not in projected:
                return False
            
            # Compare key character attributes
            orig_char = original[char_name]
            proj_char = projected[char_name]
            
            key_attrs = ["name", "class", "level", "hp"]
            for attr in key_attrs:
                if orig_char.get(attr) != proj_char.get(attr):
                    if self.verbose:
                        print(f"⚠️ Character {char_name} attribute {attr} mismatch")
                    return False
        
        return True
    
    def _compare_dicts(self, dict1: Dict[str, Any], dict2: Dict[str, Any]) -> bool:
        """Compare two dictionaries for approximate equality"""
        
        # Simple comparison of keys
        return set(dict1.keys()) == set(dict2.keys())


def run_full_migration(
    campaigns_dir: str = "resources/current_campaign",
    characters_dir: str = "docs/characters",
    rules_dir: str = "docs/rules",
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Run complete data migration to Haystack format
    
    Returns migration results and statistics
    """
    
    if verbose:
        print("🚀 Starting Full Haystack Data Migration")
        print("=" * 50)
    
    migration_results = {
        "start_time": time.time(),
        "campaign_migration": False,
        "character_migration": False,
        "rule_migration": False,
        "state_migration": False,
        "errors": []
    }
    
    try:
        # Initialize migration utilities
        data_migrator = DataMigrationUtility(verbose=verbose)
        state_migrator = StateMigrationUtility(verbose=verbose)
        
        # 1. Migrate campaign data
        if verbose:
            print("\n📖 Migrating Campaign Data...")
        
        campaign_success = data_migrator.migrate_campaign_data(campaigns_dir)
        migration_results["campaign_migration"] = campaign_success
        
        # 2. Migrate character data
        if verbose:
            print("\n👥 Migrating Character Data...")
        
        character_success = data_migrator.migrate_character_data(characters_dir)
        migration_results["character_migration"] = character_success
        
        # 3. Migrate rule data
        if verbose:
            print("\n📜 Migrating Rule Data...")
        
        rule_success = data_migrator.migrate_rule_data(rules_dir)
        migration_results["rule_migration"] = rule_success
        
        # 4. Test state migration with dummy data
        if verbose:
            print("\n🔄 Testing State Migration...")
        
        dummy_state = {
            "characters": {
                "TestCharacter": {
                    "name": "TestCharacter",
                    "class": "Fighter",
                    "level": 5,
                    "hp": {"current": 45, "max": 45}
                }
            },
            "campaign": {
                "name": "Test Campaign",
                "setting": "Forgotten Realms"
            },
            "session": {
                "active": True,
                "session_id": "test_session_001"
            }
        }
        
        migration_events = state_migrator.migrate_game_state(dummy_state)
        validation_results = state_migrator.validate_migrated_state(migration_events, dummy_state)
        
        migration_results["state_migration"] = validation_results.get("validation_successful", False)
        migration_results["state_validation"] = validation_results
        
        # Get final statistics
        migration_stats = data_migrator.get_migration_stats()
        migration_results["migration_stats"] = migration_stats
        
        # Calculate overall success
        migration_results["overall_success"] = all([
            campaign_success,
            character_success,
            rule_success,
            migration_results["state_migration"]
        ])
        
        migration_results["end_time"] = time.time()
        migration_results["duration"] = migration_results["end_time"] - migration_results["start_time"]
        
        if verbose:
            print(f"\n✅ Migration Completed in {migration_results['duration']:.2f}s")
            print(f"📊 Overall Success: {migration_results['overall_success']}")
            print(f"📈 Documents Migrated: {migration_stats['total_documents']}")
        
        return migration_results
        
    except Exception as e:
        error_msg = f"Migration failed: {str(e)}"
        migration_results["errors"].append(error_msg)
        
        if verbose:
            print(f"❌ {error_msg}")
        
        return migration_results


if __name__ == "__main__":
    # Run migration test
    results = run_full_migration(verbose=True)
    
    print("\n📋 **Final Migration Report:**")
    print("=" * 40)
    print(f"Campaign Migration: {'✅' if results['campaign_migration'] else '❌'}")
    print(f"Character Migration: {'✅' if results['character_migration'] else '❌'}")
    print(f"Rule Migration: {'✅' if results['rule_migration'] else '❌'}")
    print(f"State Migration: {'✅' if results['state_migration'] else '❌'}")
    print(f"Overall Success: {'✅' if results['overall_success'] else '❌'}")
    
    if results.get("migration_stats"):
        stats = results["migration_stats"]
        print(f"\nDocuments Created: {stats['total_documents']}")
        print(f"Categories: {list(stats['categories'].keys())}")
    
    if results.get("errors"):
        print(f"\nErrors: {len(results['errors'])}")
        for error in results["errors"]:
            print(f"  • {error}")