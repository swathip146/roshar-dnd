#!/usr/bin/env python3
"""
Test script for CharacterManager with Roshar/Cosmere characters
Tests Aggi and Kali character creation and all new methods
"""

import sys
import json
from pathlib import Path

# Add the project root to the path
sys.path.append(str(Path(__file__).parent))

# Import directly to avoid haystack dependency issues
sys.path.append(str(Path(__file__).parent / "components"))
from character_manager import create_character_manager

def create_aggi_character():
    """Create Aggi character based on aggi.txt"""
    return {
        "character_id": "Aggi",
        "name": "Aggi",
        "race": "Alethi",
        "identity": "Alethi", 
        "character_class": "Radiant",
        "radiant_order": "Lightweaver",
        "level": 1,
        "background": "Folk Hero",
        "rulebook": "Cosmere 5e (Roshar)",
        "ability_scores": {
            "strength": 8,
            "dexterity": 11,
            "constitution": 11,
            "intelligence": 8,
            "wisdom": 6,
            "charisma": 13
        },
        "hit_points": {"current": 8, "maximum": 8, "temporary": 0},
        "armor_class": 10,
        "proficiency_bonus": 2,
        "languages": ["Common", "Alethi"],
        "equipment": [],
        "personality": {
            "traits": ["Stands up for the common people", "Strong sense of justice"],
            "ideals": ["Justice and personal growth"],
            "bonds": ["Connected to folk hero background and alethi heritage"],
            "flaws": ["Sometimes too focused on goals to consider consequences"]
        },
        "backstory": "A Alethi Radiant who stands up for the common people and has a strong sense of justice.",
        "speed": 30,
        "investiture_points": {"current": 3, "maximum": 5},
        "spren": {"type": "Cryptic", "name": None, "status": "active"},
        "surges_known": ["Illumination", "Transformation"],
        "cantrips_known": [],
        "spells_known": []
    }

def create_kali_character():
    """Create Kali character based on kali.txt"""
    return {
        "character_id": "Kali",
        "name": "Kali",
        "race": "Azish",
        "identity": "Azish",
        "character_class": "Radiant", 
        "radiant_order": "Lightweaver",
        "level": 1,
        "background": "Hermit",
        "rulebook": "Cosmere 5e (Roshar)",
        "ability_scores": {
            "strength": 11,
            "dexterity": 15,
            "constitution": 16,
            "intelligence": 13,
            "wisdom": 12,
            "charisma": 14
        },
        "hit_points": {"current": 11, "maximum": 11, "temporary": 0},
        "armor_class": 12,
        "proficiency_bonus": 2,
        "languages": ["Common", "Azish", "Common Script", "Common Glyphs"],
        "equipment": [
            "Herbalism kit",
            "Scroll case with spiritual writings", 
            "Winter blanket",
            "Artisan's tools",
            "Belt pouch",
            "Common clothes"
        ],
        "personality": {
            "traits": ["Follows their chosen path", "Pursues their goals"],
            "ideals": ["Justice and personal growth"],
            "bonds": ["Connected to hermit background and azish heritage"],
            "flaws": ["Sometimes too focused on goals to consider consequences"]
        },
        "backstory": "An Azish Radiant who follows their chosen path and pursues their goals.",
        "speed": 30,
        "investiture_points": {"current": 4, "maximum": 6},
        "spren": {"type": "Cryptic", "name": None, "status": "active"},
        "surges_known": ["Illumination", "Transformation"],
        "cantrips_known": [],
        "spells_known": [],
        "tool_proficiencies": ["Herbalism kit"]
    }

def test_character_creation(manager):
    """Test basic character creation and data mapping"""
    print("=" * 60)
    print("TESTING CHARACTER CREATION")
    print("=" * 60)
    
    # Create characters
    aggi_data = create_aggi_character()
    kali_data = create_kali_character()
    
    aggi_id = manager.add_character(aggi_data)
    kali_id = manager.add_character(kali_data)
    
    print(f"\n✅ Created Aggi (ID: {aggi_id})")
    print(f"✅ Created Kali (ID: {kali_id})")
    
    # Test character summaries
    aggi_summary = manager.get_character_summary(aggi_id)
    kali_summary = manager.get_character_summary(kali_id)
    
    print(f"\n📊 Aggi Summary:")
    print(f"   Level: {aggi_summary['level']}")
    print(f"   Proficiency Bonus: {aggi_summary['proficiency_bonus']}")
    print(f"   Passive Perception: {aggi_summary['passive_scores']['perception']}")
    
    print(f"\n📊 Kali Summary:")
    print(f"   Level: {kali_summary['level']}")
    print(f"   Proficiency Bonus: {kali_summary['proficiency_bonus']}")
    print(f"   Passive Perception: {kali_summary['passive_scores']['perception']}")
    
    return aggi_id, kali_id

def test_roshar_methods(manager, aggi_id, kali_id):
    """Test Roshar-specific methods"""
    print("\n" + "=" * 60)
    print("TESTING ROSHAR-SPECIFIC METHODS")
    print("=" * 60)
    
    # Test investiture management
    print("\n🌟 Testing Investiture Management:")
    print(f"Aggi initial investiture: {manager.characters[aggi_id].investiture_points}")
    
    # Spend investiture
    success = manager.spend_investiture(aggi_id, 2)
    print(f"Spent 2 investiture: {success}")
    
    # Try to spend more than available
    success = manager.spend_investiture(aggi_id, 10)
    print(f"Tried to spend 10 investiture: {success}")
    
    # Update maximum investiture
    manager.update_investiture_points(aggi_id, maximum=8)
    manager.update_investiture_points(aggi_id, current=6)
    
    # Test spren bond management
    print("\n🧚 Testing Spren Bond Management:")
    manager.update_spren_bond(aggi_id, spren_name="Pattern", status="active")
    manager.update_spren_bond(kali_id, spren_name="Design", status="active")
    
    # Test surge management
    print("\n⚡ Testing Surge Management:")
    manager.add_surge(aggi_id, "Soulcasting")  # Should fail - already knows Illumination/Transformation
    manager.add_surge(kali_id, "Adhesion")     # Should succeed
    
    # Test invested arts
    print("\n✨ Testing Invested Arts:")
    manager.add_invested_art(aggi_id, "Minor Illusion", is_cantrip=True)
    manager.add_invested_art(aggi_id, "Disguise Self", is_cantrip=False)
    manager.add_invested_art(kali_id, "Light", is_cantrip=True)
    manager.add_invested_art(kali_id, "Color Spray", is_cantrip=False)

def test_equipment_methods(manager, aggi_id, kali_id):
    """Test equipment and proficiency methods"""
    print("\n" + "=" * 60)
    print("TESTING EQUIPMENT & PROFICIENCY METHODS")
    print("=" * 60)
    
    # Test equipment management
    print("\n🎒 Testing Equipment Management:")
    manager.add_equipment(aggi_id, "Shardblade (dormant)")
    manager.add_equipment(aggi_id, "Traveling clothes")
    manager.add_equipment(kali_id, "Meditation beads")
    
    # Remove equipment
    manager.remove_equipment(kali_id, "Belt pouch")
    
    # Test proficiency management
    print("\n🔧 Testing Proficiency Management:")
    manager.add_proficiency(aggi_id, "tool", "Smith's tools")
    manager.add_proficiency(aggi_id, "weapon", "Longsword")
    manager.add_proficiency(kali_id, "armor", "Light armor")
    manager.add_proficiency(kali_id, "tool", "Calligrapher's supplies")

def test_party_analysis(manager, aggi_id, kali_id):
    """Test party analysis with Roshar context"""
    print("\n" + "=" * 60)
    print("TESTING PARTY ANALYSIS")
    print("=" * 60)
    
    # Test individual character analysis
    print("\n👤 Individual Character Analysis:")
    aggi_analysis = manager.get_individual_character_analysis(aggi_id)
    print(f"Aggi Combat Assessment: {aggi_analysis['combat_assessment']}")
    print(f"Aggi Roleplay Hooks: {aggi_analysis['roleplay_hooks']}")
    
    kali_analysis = manager.get_individual_character_analysis(kali_id)
    print(f"Kali Combat Assessment: {kali_analysis['combat_assessment']}")
    print(f"Kali Roleplay Hooks: {kali_analysis['roleplay_hooks']}")
    
    # Test party composition
    print("\n👥 Party Composition Analysis:")
    party_comp = manager.get_party_composition()
    print(f"Party Size: {party_comp['party_size']}")
    print(f"Average Level: {party_comp['average_level']}")
    print(f"Classes: {party_comp['classes']}")
    print(f"Roles: {party_comp['roles']}")
    print(f"Strengths: {party_comp['party_strengths']}")
    print(f"Weaknesses: {party_comp['party_weaknesses']}")
    
    # Test party resources
    print("\n💎 Party Resources Analysis:")
    party_snapshot = manager.get_party_snapshot()
    print(f"Resources: {party_snapshot['resources']}")
    
    # Test Roshar-specific party context
    print("\n🌟 Roshar Party Context:")
    roshar_context = manager.get_party_roshar_context()
    print(f"Cultural Identities: {roshar_context['cultural_identities']}")
    print(f"Radiant Orders: {roshar_context['radiant_orders']}")
    print(f"Total Investiture: {roshar_context['total_investiture']}")
    print(f"Active Spren Bonds: {roshar_context['active_spren_bonds']}")
    print(f"Party Type: {roshar_context['roshar_party_type']}")

def test_roshar_summaries(manager, aggi_id, kali_id):
    """Test Roshar-specific summary methods"""
    print("\n" + "=" * 60)
    print("TESTING ROSHAR SUMMARIES")
    print("=" * 60)
    
    # Test Roshar character summaries
    print("\n📋 Roshar Character Summaries:")
    aggi_roshar = manager.get_roshar_character_summary(aggi_id)
    kali_roshar = manager.get_roshar_character_summary(kali_id)
    
    print(f"\n🔸 Aggi Roshar Summary:")
    print(f"   Identity: {aggi_roshar['identity']}")
    print(f"   Radiant Order: {aggi_roshar['radiant_order']}")
    print(f"   Investiture: {aggi_roshar['investiture_points']}")
    print(f"   Spren Bond: {aggi_roshar['spren_bond']}")
    print(f"   Surges Known: {aggi_roshar['surges_known']}")
    print(f"   Cantrips: {aggi_roshar['cantrips_known']}")
    print(f"   Spells: {aggi_roshar['spells_known']}")
    print(f"   Languages: {aggi_roshar['languages']}")
    print(f"   Equipment Count: {aggi_roshar['equipment_count']}")
    print(f"   Proficiencies: {aggi_roshar['proficiencies']}")
    
    print(f"\n🔸 Kali Roshar Summary:")
    print(f"   Identity: {kali_roshar['identity']}")
    print(f"   Radiant Order: {kali_roshar['radiant_order']}")
    print(f"   Investiture: {kali_roshar['investiture_points']}")
    print(f"   Spren Bond: {kali_roshar['spren_bond']}")
    print(f"   Surges Known: {kali_roshar['surges_known']}")
    print(f"   Cantrips: {kali_roshar['cantrips_known']}")
    print(f"   Spells: {kali_roshar['spells_known']}")
    print(f"   Languages: {kali_roshar['languages']}")
    print(f"   Equipment Count: {kali_roshar['equipment_count']}")
    print(f"   Proficiencies: {kali_roshar['proficiencies']}")

def test_skill_system(manager, aggi_id, kali_id):
    """Test skill system with new characters"""
    print("\n" + "=" * 60)
    print("TESTING SKILL SYSTEM")
    print("=" * 60)
    
    # Test skill data for various skills
    skills_to_test = ["athletics", "deception", "perception", "investigation", "persuasion"]
    
    for skill in skills_to_test:
        print(f"\n🎯 Testing {skill.title()} skill:")
        aggi_skill = manager.get_skill_data(aggi_id, skill)
        kali_skill = manager.get_skill_data(kali_id, skill)
        
        print(f"   Aggi {skill}: +{aggi_skill['modifier']} ({aggi_skill['breakdown']})")
        print(f"   Kali {skill}: +{kali_skill['modifier']} ({kali_skill['breakdown']})")
        
        # Test passive scores
        aggi_passive = manager.get_passive_score(aggi_id, skill)
        kali_passive = manager.get_passive_score(kali_id, skill)
        print(f"   Aggi Passive {skill.title()}: {aggi_passive['passive_score']}")
        print(f"   Kali Passive {skill.title()}: {kali_passive['passive_score']}")

def main():
    """Run all tests"""
    print("🧪 ROSHAR CHARACTER MANAGER TESTS")
    print("Testing with Aggi (Alethi Lightweaver) and Kali (Azish Lightweaver)")
    
    # Create character manager
    manager = create_character_manager()
    
    try:
        # Run all tests
        aggi_id, kali_id = test_character_creation(manager)
        test_roshar_methods(manager, aggi_id, kali_id)
        test_equipment_methods(manager, aggi_id, kali_id)
        test_party_analysis(manager, aggi_id, kali_id)
        test_roshar_summaries(manager, aggi_id, kali_id)
        test_skill_system(manager, aggi_id, kali_id)
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        
        # Final party list
        print("\n📋 Final Party List:")
        party_list = manager.list_characters()
        for char in party_list:
            print(f"   - {char['name']} (Level {char['level']}, {char['conditions']} conditions)")
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
