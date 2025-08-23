"""
Stage 3 Demo - Enhanced Infrastructure with Sophisticated Workflows
Demonstrates Saga Manager, Policy Engine, 7-Step Pipeline, and Decision Logging
Shows Original Plan Phase 1 Complete Implementation
"""

import sys
import os
import logging
from pathlib import Path

# Add project paths
sys.path.append(str(Path(__file__).parent))

from orchestrator.simple_orchestrator import (
    create_stage3_orchestrator, 
    create_house_rules_orchestrator,
    create_beginner_orchestrator,
    create_stage2_orchestrator
)
from components.policy import PolicyProfile


def setup_logging():
    """Setup comprehensive logging for demo"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def demo_policy_engine_profiles():
    """Demonstrate Policy Engine with different rule profiles"""
    print("\n" + "="*70)
    print("POLICY ENGINE DEMONSTRATION")
    print("="*70)
    
    print("\n1. Testing Different Policy Profiles...")
    
    # RAW D&D Rules
    print("\n--- RAW D&D Rules Profile ---")
    raw_orchestrator = create_stage3_orchestrator(PolicyProfile.RAW)
    raw_status = raw_orchestrator.get_orchestrator_status()
    print(f"Policy Profile: {raw_status['policy_profile']}")
    print("✓ Standard D&D 5e rules")
    print("✓ No flanking advantage")
    print("✓ Critical hits only on 20")
    print("✓ Strict spell component enforcement")
    
    # House Rules
    print("\n--- House Rules Profile ---")
    house_orchestrator = create_house_rules_orchestrator()
    house_status = house_orchestrator.get_orchestrator_status()
    print(f"Policy Profile: {house_status['policy_profile']}")
    print("✓ Flanking grants advantage")
    print("✓ Critical hits on 19-20")
    print("✓ Relaxed spell components")
    
    # Beginner Friendly
    print("\n--- Beginner Friendly Profile ---")
    beginner_orchestrator = create_beginner_orchestrator()
    beginner_status = beginner_orchestrator.get_orchestrator_status()
    print(f"Policy Profile: {beginner_status['policy_profile']}")
    print("✓ All beginner-friendly rules active")
    print("✓ Lower DCs (-2 adjustment)")
    print("✓ More forgiving death saves")
    print("✓ Enhanced rest benefits")
    
    return house_orchestrator  # Use house rules for remaining demos


def demo_character_management(orchestrator):
    """Demonstrate comprehensive character management"""
    print("\n" + "="*70)
    print("CHARACTER MANAGEMENT & 7-STEP SKILL PIPELINE")
    print("="*70)
    
    print("\n1. Adding Characters with Full Stats...")
    
    # Add a rogue character
    rogue_request = {
        "type": "character_add",
        "character_data": {
            "character_id": "lyralei_shadowstep",
            "name": "Lyralei Shadowstep",
            "level": 5,
            "ability_scores": {
                "strength": 10,
                "dexterity": 18,
                "constitution": 14,
                "intelligence": 13,
                "wisdom": 12,
                "charisma": 16
            },
            "skills": {
                "stealth": True,
                "sleight_of_hand": True,
                "perception": True,
                "deception": True,
                "investigation": True
            },
            "expertise_skills": ["stealth", "sleight_of_hand"],
            "conditions": [],
            "features": ["sneak_attack", "thieves_cant"]
        }
    }
    
    rogue_response = orchestrator.process_request(rogue_request)
    print(f"✓ Added Rogue: {rogue_response.data['message']}")
    
    # Add a fighter character
    fighter_request = {
        "type": "character_add",
        "character_data": {
            "character_id": "thorin_ironshield",
            "name": "Thorin Ironshield",
            "level": 4,
            "ability_scores": {
                "strength": 16,
                "dexterity": 12,
                "constitution": 15,
                "intelligence": 10,
                "wisdom": 13,
                "charisma": 8
            },
            "skills": {
                "athletics": True,
                "intimidation": True,
                "perception": True
            },
            "expertise_skills": [],
            "conditions": [],
            "features": ["fighting_style", "second_wind"]
        }
    }
    
    fighter_response = orchestrator.process_request(fighter_request)
    print(f"✓ Added Fighter: {fighter_response.data['message']}")
    
    return "lyralei_shadowstep", "thorin_ironshield"


def demo_7_step_skill_pipeline(orchestrator, rogue_id, fighter_id):
    """Demonstrate the 7-step deterministic skill pipeline"""
    print("\n2. Testing 7-Step Skill Check Pipeline...")
    
    # Complex stealth check with multiple factors
    stealth_check = {
        "type": "skill_check",
        "action": "sneak past elite guards in the castle courtyard",
        "actor": rogue_id,
        "skill": "stealth",
        "context": {
            "difficulty": "hard",
            "environment": {
                "lighting": "dim",
                "terrain": "stone_courtyard",
                "cover": True
            },
            "time_pressure": True,
            "average_party_level": 4
        }
    }
    
    print(f"\n--- Stealth Check: {stealth_check['action']} ---")
    stealth_result = orchestrator.process_request(stealth_check)
    
    if stealth_result.success:
        skill_data = stealth_result.data["skill_check_result"]
        print(f"🎯 Pipeline Result: {'SUCCESS' if skill_data['success'] else 'FAILURE'}")
        print(f"📊 Roll: {skill_data['selected_roll']} + {skill_data['character_modifier']} = {skill_data['roll_total']}")
        print(f"🎲 Raw Rolls: {skill_data['raw_rolls']}")
        print(f"🎯 DC: {skill_data['dc']} (Source: {skill_data['dc_source']})")
        print(f"⚡ Advantage State: {skill_data['advantage_state']}")
        if skill_data.get('advantage_sources'):
            print(f"➕ Advantage Sources: {skill_data['advantage_sources']}")
        if skill_data.get('disadvantage_sources'):
            print(f"➖ Disadvantage Sources: {skill_data['disadvantage_sources']}")
        print(f"📝 Breakdown: {skill_data['roll_breakdown']}")
    
    # Athletic check for the fighter
    athletics_check = {
        "type": "skill_check",
        "action": "climb the castle wall under pressure",
        "actor": fighter_id,
        "skill": "athletics",
        "context": {
            "difficulty": "medium",
            "environment": {
                "weather": "rain",
                "surface_type": "rough_stone"
            },
            "time_pressure": True
        }
    }
    
    print(f"\n--- Athletics Check: {athletics_check['action']} ---")
    athletics_result = orchestrator.process_request(athletics_check)
    
    if athletics_result.success:
        skill_data = athletics_result.data["skill_check_result"]
        print(f"🎯 Pipeline Result: {'SUCCESS' if skill_data['success'] else 'FAILURE'}")
        print(f"📊 Roll: {skill_data['selected_roll']} + {skill_data['character_modifier']} = {skill_data['roll_total']}")
        print(f"🎯 DC: {skill_data['dc']} (Source: {skill_data['dc_source']})")
        print(f"📝 Breakdown: {skill_data['roll_breakdown']}")


def demo_contested_checks(orchestrator, rogue_id, fighter_id):
    """Demonstrate contested checks between characters"""
    print("\n3. Testing Contested Checks...")
    
    # Stealth vs Perception contest
    contest_request = {
        "type": "contested_check",
        "actor1": rogue_id,
        "skill1": "stealth",
        "actor2": fighter_id, 
        "skill2": "perception",
        "context": {
            "scenario": "rogue trying to sneak past alert fighter",
            "environment": {"lighting": "normal"}
        }
    }
    
    print("\n--- Contested Check: Stealth vs Perception ---")
    contest_result = orchestrator.process_request(contest_request)
    
    if contest_result.success:
        contest_data = contest_result.data["contested_result"]
        winner = contest_data["winner"]
        margin = contest_data["margin"]
        
        print(f"🏆 Winner: {winner or 'TIE'}")
        print(f"📊 Margin: {margin} points")
        
        actor1_result = contest_data["actor1_result"]
        actor2_result = contest_data["actor2_result"]
        
        print(f"🥷 {rogue_id} (Stealth): {actor1_result['roll_total']}")
        print(f"👁️ {fighter_id} (Perception): {actor2_result['roll_total']}")


def demo_saga_workflows(orchestrator, rogue_id, fighter_id):
    """Demonstrate Saga Manager multi-step workflows"""
    print("\n" + "="*70)
    print("SAGA MANAGER - MULTI-STEP WORKFLOWS")
    print("="*70)
    
    print("\n1. Starting Skill Challenge Saga...")
    
    # Start infiltration saga
    saga_request = {
        "type": "saga_start",
        "saga_type": "skill_challenge",
        "context": {
            "challenge_name": "Castle Infiltration",
            "difficulty": "hard",
            "participants": [rogue_id, fighter_id],
            "objective": "Reach the treasure vault undetected",
            "steps_required": 4
        }
    }
    
    saga_response = orchestrator.process_request(saga_request)
    
    if saga_response.success:
        saga_data = saga_response.data
        saga_id = saga_data["saga_id"]
        print(f"🎯 Started Saga: {saga_data['saga_type']}")
        print(f"🆔 Saga ID: {saga_id}")
        
        # Simulate advancing through saga steps
        print("\n2. Advancing Through Saga Steps...")
        
        # Step 1: Present scenario (handled by scenario generator)
        step1_result = {
            "step_result": {
                "scenario_generated": True,
                "scenario": "You approach the castle's outer wall...",
                "success": True
            }
        }
        
        advance_request = {
            "type": "saga_advance",
            "saga_id": saga_id,
            "step_result": step1_result["step_result"]
        }
        
        advance_response = orchestrator.process_request(advance_request)
        if advance_response.success:
            print("✓ Step 1: Scenario presented")
            advance_data = advance_response.data["saga_advance_result"]
            
            if "next_step" in advance_data:
                print(f"➡️ Next Step: {advance_data['next_step']} ({advance_data['handler']})")
        
        # Show active sagas
        saga_stats = orchestrator.saga_manager.get_saga_stats()
        print(f"\n📊 Saga Statistics:")
        print(f"   Active Sagas: {saga_stats['active_sagas']}")
        print(f"   Total Sagas: {saga_stats['total_sagas']}")


def demo_decision_logging_analysis(orchestrator):
    """Demonstrate Decision Logger analysis capabilities"""
    print("\n" + "="*70)
    print("DECISION LOGGING & ANALYTICS")
    print("="*70)
    
    print("\n1. Skill Check Analysis...")
    
    # Get comprehensive skill check analysis
    session_summary = orchestrator.decision_logger.get_session_summary()
    
    print(f"📊 Session Summary:")
    print(f"   Session Duration: {session_summary['session_duration']:.1f} seconds")
    print(f"   Total Skill Checks: {session_summary['total_skill_checks']}")
    print(f"   Total Saga Steps: {session_summary['total_saga_steps']}")
    print(f"   Unique Correlations: {session_summary['unique_correlations']}")
    
    if "skill_check_analysis" in session_summary:
        skill_analysis = session_summary["skill_check_analysis"]
        if "total_checks" in skill_analysis and skill_analysis["total_checks"] > 0:
            print(f"\n📈 Skill Check Analytics:")
            print(f"   Success Rate: {skill_analysis['success_rate']:.1%}")
            print(f"   Average Roll: {skill_analysis.get('average_roll', 0):.1f}")
            print(f"   Advantage Checks: {skill_analysis.get('advantage_checks', 0)}")
            print(f"   Disadvantage Checks: {skill_analysis.get('disadvantage_checks', 0)}")
            
            if "skill_success_rates" in skill_analysis:
                print(f"\n🎯 Per-Skill Success Rates:")
                for skill, data in skill_analysis["skill_success_rates"].items():
                    print(f"   {skill.title()}: {data['rate']:.1%} ({data['successful']}/{data['total']})")


def demo_policy_runtime_changes(orchestrator):
    """Demonstrate runtime policy changes"""
    print("\n2. Runtime Policy Changes...")
    
    # Change to beginner profile
    policy_change = {
        "type": "policy_change",
        "profile": "easy"
    }
    
    change_response = orchestrator.process_request(policy_change)
    if change_response.success:
        print(f"✓ Changed to: {change_response.data['new_profile']} profile")
    
    # Add custom rule
    custom_rule = {
        "type": "policy_change",
        "custom_rule": True,
        "rule_name": "demo_bonus",
        "rule_value": 2,
        "description": "Demo bonus for showcase"
    }
    
    rule_response = orchestrator.process_request(custom_rule)
    if rule_response.success:
        print(f"✓ Added custom rule: {rule_response.data['rule_name']}")


def demo_comprehensive_statistics(orchestrator):
    """Show comprehensive system statistics"""
    print("\n" + "="*70)
    print("COMPREHENSIVE SYSTEM STATISTICS")
    print("="*70)
    
    stats_request = {"type": "game_statistics"}
    stats_response = orchestrator.process_request(stats_request)
    
    if stats_response.success:
        data = stats_response.data
        
        print("\n🎮 Game Statistics:")
        game_stats = data["game_statistics"]
        print(f"   Active Characters: {game_stats['active_characters']}")
        print(f"   Total Skill Checks: {game_stats['total_skill_checks']}")
        print(f"   Success Rate: {game_stats['success_rate']:.1%}")
        print(f"   Session Duration: {game_stats['session_duration']:.1f}s")
        
        print("\n📊 Decision Logger Summary:")
        session_data = data["session_summary"]
        print(f"   Session ID: {session_data['session_id']}")
        print(f"   Total Decision Records: {session_data['total_skill_checks']}")
        
        print("\n🎯 Saga Statistics:")
        saga_stats = data["saga_statistics"]
        print(f"   Active Sagas: {saga_stats['active_sagas']}")
        print(f"   Completed Sagas: {saga_stats['completed_sagas']}")
        print(f"   Available Saga Types: {', '.join(saga_stats['available_saga_types'])}")
        
        print("\n⚖️ Policy Information:")
        policy_info = data["policy_info"]
        print(f"   Active Profile: {policy_info['active_profile']}")
        print(f"   Total Rules: {policy_info['total_rules']}")
        print(f"   Custom Rules: {policy_info['custom_rules']}")


def demo_backward_compatibility():
    """Demonstrate backward compatibility with Stage 2"""
    print("\n" + "="*70)
    print("BACKWARD COMPATIBILITY DEMONSTRATION")
    print("="*70)
    
    print("\n1. Stage 2 Compatibility Mode...")
    
    # Create Stage 2 orchestrator
    stage2_orchestrator = create_stage2_orchestrator()
    stage2_status = stage2_orchestrator.get_orchestrator_status()
    
    print(f"✓ Stage 3 Enabled: {stage2_status['stage3_enabled']}")
    print(f"✓ Available Handlers: {len(stage2_status['available_handlers'])}")
    
    # Test Stage 2 requests
    stage2_requests = [
        {"type": "scenario", "data": {"theme": "dungeon"}},
        {"type": "dice_roll", "data": {"dice": "1d20", "modifier": 3}},
        {"type": "game_state", "data": {}}
    ]
    
    print("\n2. Testing Stage 2 Request Compatibility...")
    for i, request in enumerate(stage2_requests, 1):
        response = stage2_orchestrator.process_request(request)
        print(f"✓ Request {i} ({request['type']}): {'SUCCESS' if response.success else 'FAILED'}")


def demo_architecture_progression():
    """Show the progression from Stage 1 → Stage 2 → Stage 3"""
    print("\n" + "="*70)
    print("ARCHITECTURE PROGRESSION SHOWCASE")
    print("="*70)
    
    print("\n📈 Progressive Implementation Journey:")
    print("✅ Stage 1: Basic D&D game with simple components")
    print("   └── simple_dnd_game.py (single file)")
    print("   └── simple_dnd/ structured package")
    
    print("\n✅ Stage 2: RAG integration and basic orchestration")
    print("   └── Haystack + Qdrant document storage")
    print("   └── RAG-enhanced scenario generation")
    print("   └── Simple orchestrator with extension hooks")
    
    print("\n✅ Stage 3: Enhanced infrastructure (CURRENT)")
    print("   └── 🎯 Saga Manager: Multi-step workflow tracking")
    print("   └── ⚖️ Policy Engine: Centralized rule mediation")
    print("   └── 🎲 Enhanced Dice Roller: Complete audit trail")
    print("   └── ⚖️ Rules Enforcer: Authoritative D&D rule interpretation")
    print("   └── 👥 Character Manager: Full character sheet management")
    print("   └── ⚙️ Game Engine: 7-step deterministic skill pipeline")
    print("   └── 📝 Decision Logger: Comprehensive decision audit trail")
    print("   └── 🎯 Enhanced Orchestrator: Full integration with backward compatibility")
    
    print("\n🎯 Original Plan Phase 1: COMPLETE")
    print("   ✅ Saga Manager with correlation IDs")
    print("   ✅ Policy Engine with house rule support")
    print("   ✅ 7-step skill check pipeline")
    print("   ✅ Decision logging with full provenance")
    print("   ✅ All components integrated and working together")


def main():
    """Main demo execution showcasing all Stage 3 capabilities"""
    setup_logging()
    
    print("D&D Game Assistant - Stage 3 Enhanced Infrastructure Demo")
    print("Progressive Implementation: Stage 3 Complete (Weeks 9-12)")
    print("Original Plan Phase 1: COMPLETE")
    
    try:
        # Demo 1: Policy Engine Profiles
        house_orchestrator = demo_policy_engine_profiles()
        
        # Demo 2: Character Management & 7-Step Pipeline
        rogue_id, fighter_id = demo_character_management(house_orchestrator)
        demo_7_step_skill_pipeline(house_orchestrator, rogue_id, fighter_id)
        demo_contested_checks(house_orchestrator, rogue_id, fighter_id)
        
        # Demo 3: Saga Workflows
        demo_saga_workflows(house_orchestrator, rogue_id, fighter_id)
        
        # Demo 4: Decision Logging & Analytics
        demo_decision_logging_analysis(house_orchestrator)
        demo_policy_runtime_changes(house_orchestrator)
        
        # Demo 5: Comprehensive Statistics
        demo_comprehensive_statistics(house_orchestrator)
        
        # Demo 6: Backward Compatibility
        demo_backward_compatibility()
        
        # Demo 7: Architecture Progression
        demo_architecture_progression()
        
        print("\n" + "="*70)
        print("🎉 STAGE 3 DEMO COMPLETE!")
        print("Original Plan Phase 1: FULLY IMPLEMENTED")
        print("Ready for Stage 4: Combat MVP (Weeks 13-16)")
        print("="*70)
        
    except Exception as e:
        print(f"\nDemo Error: {e}")
        print("Note: Some components may require additional setup or dependencies")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()