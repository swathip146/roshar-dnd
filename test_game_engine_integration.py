#!/usr/bin/env python3
"""
Test script for GameEngine integration with Roshar characters
Tests the flow from character selection to game state management
"""

import sys
from pathlib import Path

# Add the project root to the path
sys.path.append(str(Path(__file__).parent))

from components.game_engine import create_game_engine
from components.policy import PolicyProfile

def create_test_aggi():
    """Create Aggi character data for testing"""
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
        "spells_known": [],
        "skills": {},
        "expertise_skills": [],
        "conditions": [],
        "features": ["Spellcasting", "Investiture Points", "Spren Bond"],
        "saving_throw_proficiencies": []
    }

def test_character_integration():
    """Test character integration with GameEngine"""
    print("🧪 TESTING GAME ENGINE INTEGRATION")
    print("=" * 50)
    
    # Create game engine
    engine = create_game_engine(PolicyProfile.HOUSE)
    
    # Add Aggi character
    aggi_data = create_test_aggi()
    char_id = engine.add_character(aggi_data)
    
    print(f"\n✅ Character added with ID: {char_id}")
    
    # Test character state retrieval
    print("\n📊 Testing character state retrieval:")
    
    # Get runtime state
    runtime_state = engine.get_character_runtime_state(char_id)
    print(f"Runtime state keys: {list(runtime_state.keys())}")
    print(f"Investiture spent this turn: {runtime_state.get('investiture_spent_this_turn', 0)}")
    print(f"Spren interaction state: {runtime_state.get('spren_interaction_state', 'unknown')}")
    
    # Get full character state
    full_state = engine.get_character_full_state(char_id)
    print(f"\nFull state sections: {list(full_state.keys())}")
    
    # Test Roshar-specific functionality
    print("\n🌟 Testing Roshar-specific functionality:")
    
    # Test investiture spending
    success = engine.spend_character_investiture(char_id, 2, "Illumination")
    print(f"Spent 2 investiture for Illumination: {success}")
    
    # Check updated runtime state
    runtime_state = engine.get_character_runtime_state(char_id)
    print(f"Investiture spent this turn: {runtime_state.get('investiture_spent_this_turn', 0)}")
    print(f"Surges used this scene: {runtime_state.get('surges_used_this_scene', [])}")
    
    # Test spren interaction
    engine.update_spren_interaction(char_id, "communicating")
    runtime_state = engine.get_character_runtime_state(char_id)
    print(f"Spren interaction state: {runtime_state.get('spren_interaction_state', 'unknown')}")
    
    # Test scenario context
    print("\n🎭 Testing scenario context:")
    scenario_context = engine.get_scenario_context()
    
    print(f"Scenario context sections: {list(scenario_context.keys())}")
    
    if "roshar_party_context" in scenario_context:
        roshar_context = scenario_context["roshar_party_context"]
        print(f"Cultural identities: {roshar_context.get('cultural_identities', {})}")
        print(f"Radiant orders: {roshar_context.get('radiant_orders', {})}")
        print(f"Total investiture: {roshar_context.get('total_investiture', 0)}")
        print(f"Active spren bonds: {roshar_context.get('active_spren_bonds', 0)}")
    
    # Test resource reset
    print("\n🔄 Testing resource reset:")
    engine.reset_turn_resources(char_id)
    engine.reset_scene_resources(char_id)
    
    runtime_state = engine.get_character_runtime_state(char_id)
    print(f"After reset - Investiture spent: {runtime_state.get('investiture_spent_this_turn', 0)}")
    print(f"After reset - Surges used: {runtime_state.get('surges_used_this_scene', [])}")
    print(f"After reset - Spren state: {runtime_state.get('spren_interaction_state', 'unknown')}")
    
    # Test skill check with Roshar character
    print("\n🎲 Testing skill check with Roshar character:")
    skill_check = {
        "action": "use Illumination to create a distraction",
        "actor": char_id,
        "skill": "deception",
        "context": {
            "difficulty": "medium",
            "using_investiture": True,
            "surge_type": "Illumination"
        }
    }
    
    result = engine.process_skill_check(skill_check)
    print(f"Skill check result: Success={result.get('success', False)}, Total={result.get('roll_total', 0)}")
    
    # Test oath progression
    print("\n🌟 Testing Radiant oath progression:")
    
    # Check initial ideal level
    initial_level = engine.character_manager.get_ideal_level(char_id)
    print(f"Initial ideal level: {initial_level} ({engine.character_manager.get_ideal_name(char_id)})")
    
    # Check oath readiness
    readiness = engine.check_oath_readiness(char_id)
    print(f"Ready for next oath: {readiness.get('ready', False)}")
    if readiness.get('ready'):
        print(f"Next ideal: {readiness.get('next_ideal_name', 'Unknown')}")
    
    # Speak First Ideal
    oath_result = engine.speak_oath(
        char_id, 
        "Life before death, strength before weakness, journey before destination",
        "Defending innocent civilians from Voidbringers"
    )
    print(f"First Ideal result: {oath_result}")
    
    # Check updated state
    new_level = engine.character_manager.get_ideal_level(char_id)
    print(f"New ideal level: {new_level} ({engine.character_manager.get_ideal_name(char_id)})")
    
    # Check oath history
    oath_history = engine.get_oath_history(char_id)
    print(f"Oath history: {len(oath_history)} oaths spoken")
    
    # Test oath opportunity
    opportunity = engine.trigger_oath_opportunity(
        char_id,
        "Witnessing injustice and choosing to act",
        "I will protect those who cannot protect themselves"
    )
    print(f"Oath opportunity created: {opportunity.get('opportunity_created', False)}")
    
    # Test debug functionality
    print("\n🔍 Testing debug character state functionality:")
    
    # Print party summary (simplified debug output)
    engine.debug_print_party_summary(turn_number=1)
    
    # Simulate some turn actions and show state changes
    print("\n🔄 Simulating turn actions...")
    
    # Spend some investiture and update state
    engine.spend_character_investiture(char_id, 1, "Illumination")
    engine.update_spren_interaction(char_id, "communicating")
    
    # Update character position and action
    if char_id in engine.game_state.characters:
        engine.game_state.characters[char_id]["position"] = {"x": 5, "y": 3}
        engine.game_state.characters[char_id]["last_action"] = "Cast Minor Illusion"
        engine.game_state.characters[char_id]["hidden"] = True
    
    # Show updated state
    print("\n🔍 Character state after actions:")
    engine.debug_print_party_summary(turn_number=2)
    
    print("\n✅ All integration tests completed successfully!")
    return True

def main():
    """Run integration tests"""
    try:
        success = test_character_integration()
        print(f"\n{'✅ TESTS PASSED' if success else '❌ TESTS FAILED'}")
        return success
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
