"""
Haystack Integration Demo for D&D Assistant
Demonstrates the complete end-to-end orchestrated workflow
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from typing import Dict, Any, Optional
import json
import time

# Import Haystack integration components
from core.command_envelope import create_command_envelope
from core.haystack_bridge import HaystackOrchestrator
from agent_framework import AgentOrchestrator


def demo_haystack_integration(verbose: bool = True):
    """
    Demonstrate the complete Haystack integration workflow
    
    Args:
        verbose: Whether to print detailed demo output
        
    Returns:
        Dict containing demo results
    """
    if verbose:
        print("🎮 D&D Assistant Haystack Integration Demo")
        print("=" * 50)
    
    demo_results = {
        "initialization": {},
        "skill_check_demo": {},
        "scenario_choice_demo": {},
        "enhanced_game_engine_demo": {},
        "pipeline_info": {},
        "errors": []
    }
    
    try:
        # 1. Initialize AgentOrchestrator with Haystack integration
        if verbose:
            print("\n🚀 Phase 1: Initializing AgentOrchestrator with Haystack integration...")
        
        orchestrator = AgentOrchestrator(enable_haystack=True, verbose=verbose)
        
        # Check if Haystack integration is available
        if not orchestrator.enable_haystack:
            error_msg = "Haystack integration not available"
            demo_results["errors"].append(error_msg)
            if verbose:
                print(f"❌ {error_msg}")
            return demo_results
        
        # Start the orchestrator
        orchestrator.start()
        time.sleep(0.5)  # Let it initialize
        
        demo_results["initialization"] = {
            "haystack_enabled": orchestrator.enable_haystack,
            "orchestrator_running": orchestrator.running,
            "pipeline_registry_available": orchestrator.haystack_orchestrator.pipeline_registry is not None
        }
        
        if verbose:
            print("✅ AgentOrchestrator initialized successfully")
            print(f"   - Haystack enabled: {demo_results['initialization']['haystack_enabled']}")
            print(f"   - Pipeline registry: {demo_results['initialization']['pipeline_registry_available']}")
        
        # 2. Get pipeline information
        if verbose:
            print("\n📊 Phase 2: Checking available pipelines...")
        
        pipeline_info = orchestrator.haystack_orchestrator.get_pipeline_info()
        demo_results["pipeline_info"] = pipeline_info
        
        if verbose:
            print(f"   - Registered pipelines: {pipeline_info.get('registered_intents', [])}")
            print(f"   - Total pipelines: {pipeline_info.get('total_pipelines', 0)}")
        
        # 3. Demo Skill Check Pipeline
        if verbose:
            print("\n⚔️ Phase 3: Demonstrating Skill Check Pipeline...")
        
        skill_check_result = demo_skill_check_pipeline(orchestrator, verbose)
        demo_results["skill_check_demo"] = skill_check_result
        
        # 4. Demo Scenario Choice Pipeline
        if verbose:
            print("\n🎭 Phase 4: Demonstrating Scenario Choice Pipeline...")
        
        scenario_choice_result = demo_scenario_choice_pipeline(orchestrator, verbose)
        demo_results["scenario_choice_demo"] = scenario_choice_result
        
        # 5. Demo Enhanced Game Engine - Event Sourcing
        if verbose:
            print("\n📈 Phase 5: Demonstrating Enhanced Game Engine - Event Sourcing...")
        
        enhanced_engine_result = demo_enhanced_game_engine(orchestrator, verbose)
        demo_results["enhanced_game_engine_demo"] = enhanced_engine_result
        
        # 6. Show final statistics
        if verbose:
            print("\n📈 Phase 5: Final Statistics...")
            stats = orchestrator.get_message_statistics()
            print(f"   - Total messages processed: {stats.get('total_messages', 0)}")
            print(f"   - Active pipelines: {stats.get('haystack_pipelines', [])}")
            print(f"   - Haystack enabled: {stats.get('haystack_enabled', False)}")
        
        demo_results["final_stats"] = orchestrator.get_message_statistics()
        
        # Stop the orchestrator
        orchestrator.stop()
        
        if verbose:
            print("\n🎉 Demo completed successfully!")
        
        return demo_results
        
    except Exception as e:
        error_msg = f"Demo failed: {str(e)}"
        demo_results["errors"].append(error_msg)
        if verbose:
            print(f"❌ {error_msg}")
        return demo_results


def demo_skill_check_pipeline(orchestrator: AgentOrchestrator, verbose: bool = True) -> Dict[str, Any]:
    """
    Demonstrate the skill check pipeline
    
    Args:
        orchestrator: The AgentOrchestrator instance
        verbose: Whether to print demo output
        
    Returns:
        Dict containing demo results
    """
    try:
        # Create a skill check command envelope
        envelope = create_command_envelope(
            intent="SKILL_CHECK",
            utterance="I want to make an athletics check to climb the cliff",
            actor={"name": "Thorin Ironforge", "type": "player", "class": "fighter"},
            entities={"skill": "athletics", "dc": 15},
            context={
                "situation": "climbing a rocky cliff face",
                "weather": "clear day",
                "difficulty": "moderate"
            },
            parameters={"advantage": False, "disadvantage": False},
            metadata={"source": "haystack_demo", "demo_type": "skill_check"}
        )
        
        if verbose:
            print(f"   📝 Created skill check envelope: {envelope.header.correlation_id}")
            print(f"   🎯 Intent: {envelope.header.intent}")
            print(f"   👤 Actor: {envelope.header.actor['name']}")
            print(f"   🎲 Skill: {envelope.body.entities.get('skill')} (DC {envelope.body.entities.get('dc')})")
        
        # Process through Haystack orchestrator
        result = orchestrator.handle_command_envelope(envelope)
        
        if verbose:
            success = result.get("success", False)
            status_icon = "✅" if success else "❌"
            print(f"   {status_icon} Skill check result: {success}")
            
            if "applied_result" in result:
                applied = result["applied_result"]
                if "data" in applied:
                    skill_data = applied["data"]
                    print(f"      🎲 Roll: {skill_data.get('roll', '?')}")
                    print(f"      ➕ Modifier: {skill_data.get('modifier', '?')}")
                    print(f"      🎯 Total: {skill_data.get('total', '?')}")
                    print(f"      🏆 Success: {skill_data.get('success', '?')}")
        
        return {
            "success": True,
            "envelope": envelope.to_dict(),
            "result": result
        }
        
    except Exception as e:
        if verbose:
            print(f"   ❌ Skill check demo failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def demo_scenario_choice_pipeline(orchestrator: AgentOrchestrator, verbose: bool = True) -> Dict[str, Any]:
    """
    Demonstrate the scenario choice pipeline
    
    Args:
        orchestrator: The AgentOrchestrator instance
        verbose: Whether to print demo output
        
    Returns:
        Dict containing demo results
    """
    try:
        # Create a scenario choice command envelope
        envelope = create_command_envelope(
            intent="SCENARIO_CHOICE",
            utterance="I choose to sneak past the guards (option 1)",
            actor={"name": "Shadowstep", "type": "player", "class": "rogue"},
            entities={"choice": 1, "skill": "stealth"},
            context={
                "current_scenario": {
                    "description": "You approach the castle gates and see two guards",
                    "options": [
                        "Sneak past the guards (Stealth DC 14)",
                        "Distract the guards with a noise",
                        "Walk up boldly and try to bluff your way in"
                    ]
                },
                "location": "castle_entrance",
                "time_of_day": "midnight"
            },
            parameters={"stealth_bonus": 5},
            metadata={"source": "haystack_demo", "demo_type": "scenario_choice"}
        )
        
        if verbose:
            print(f"   📝 Created scenario choice envelope: {envelope.header.correlation_id}")
            print(f"   🎯 Intent: {envelope.header.intent}")
            print(f"   👤 Actor: {envelope.header.actor['name']}")
            print(f"   🎭 Choice: Option {envelope.body.entities.get('choice')}")
            print(f"   📍 Context: {envelope.body.context.get('location')}")
        
        # Process through Haystack orchestrator
        result = orchestrator.handle_command_envelope(envelope)
        
        if verbose:
            success = result.get("success", False)
            status_icon = "✅" if success else "❌"
            print(f"   {status_icon} Scenario choice result: {success}")
            
            if "updated_state" in result:
                print(f"      🔄 Game state updated")
            
            # Look for consequence text if available
            if isinstance(result, dict):
                for key, value in result.items():
                    if "consequence" in key.lower() or "scenario" in key.lower():
                        if isinstance(value, dict) and "consequence_text" in value:
                            print(f"      📖 Consequence: {value['consequence_text'][:100]}...")
        
        return {
            "success": True,
            "envelope": envelope.to_dict(),
            "result": result
        }
        
    except Exception as e:
        if verbose:
            print(f"   ❌ Scenario choice demo failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def demo_enhanced_game_engine(orchestrator: AgentOrchestrator, verbose: bool = True) -> Dict[str, Any]:
    """
    Demonstrate the enhanced game engine with event sourcing
    
    Args:
        orchestrator: The AgentOrchestrator instance
        verbose: Whether to print demo output
        
    Returns:
        Dict containing demo results
    """
    try:
        enhanced_engine = orchestrator.enhanced_game_engine_agent
        
        if not enhanced_engine:
            if verbose:
                print("   ⚠️ Enhanced Game Engine not available")
            return {"success": False, "error": "Enhanced Game Engine not available"}
        
        if verbose:
            print("   🎯 Enhanced Game Engine detected - demonstrating event sourcing")
        
        # Get initial event count
        initial_events = len(enhanced_engine.event_store.events)
        if verbose:
            print(f"   📊 Initial events in store: {initial_events}")
        
        # Create character setup envelope for enhanced game engine
        character_envelope = create_command_envelope(
            intent="SKILL_CHECK",
            utterance="Kaladin attempts to climb the sheer cliff face using his Windrunner abilities",
            actor={
                "name": "Kaladin",
                "type": "player_character",
                "class": "Windrunner",
                "level": 4,
                "surgebinding": ["Adhesion", "Gravitation"]
            },
            entities={"skill": "athletics", "difficulty": "hard", "dc": 18},
            context={
                "scenario": "cliff_climbing",
                "environment": "stormy",
                "stormlight_available": True
            }
        )
        
        if verbose:
            print(f"   🧗 Character Action: {character_envelope.header.actor['name']} - Cliff Climbing")
        
        # Process through orchestrator (which should use enhanced game engine)
        result = orchestrator.handle_command_envelope(character_envelope)
        
        # Check event accumulation
        after_events = len(enhanced_engine.event_store.events)
        new_events = after_events - initial_events
        
        if verbose:
            success = result.get("success", False)
            print(f"   {'✅' if success else '❌'} Skill check processed: {success}")
            print(f"   📈 New events created: {new_events}")
        
        # Demonstrate state projection
        current_state = enhanced_engine.state_projector.project_state(
            enhanced_engine.event_store.events, enhanced_engine.base_state.copy()
        )
        
        if verbose:
            print(f"   🎭 Game state components: {list(current_state.keys())}")
            if "characters" in current_state and current_state["characters"]:
                print("   👥 Characters in game state:")
                for char_name, char_data in current_state["characters"].items():
                    print(f"      {char_name}: Level {char_data.get('level', '?')}, Class {char_data.get('class', '?')}")
        
        # Show recent events
        if verbose and enhanced_engine.event_store.events:
            print("   📋 Recent Event History:")
            recent_events = enhanced_engine.event_store.events[-2:]  # Last 2 events
            for i, event in enumerate(recent_events, 1):
                print(f"      {i}. {event.event_type} by {event.actor}")
                print(f"         ID: {event.event_id[:8]}...")
        
        # Test event filtering
        skill_events = enhanced_engine.event_store.get_events_by_type("skill_check.resolved")
        character_events = enhanced_engine.event_store.get_events_by_actor("Kaladin")
        
        if verbose:
            print(f"   🔍 Event Filtering:")
            print(f"      🎲 Skill check events: {len(skill_events)}")
            print(f"      🎭 Kaladin's events: {len(character_events)}")
        
        # Test event stream persistence
        if verbose:
            print("   💾 Testing Event Stream Persistence...")
        
        stream_file = "demo_event_stream.json"
        enhanced_engine.save_event_stream(stream_file)
        
        # Create new engine and test loading
        from core.enhanced_game_engine import EnhancedGameEngineAgent
        test_engine = EnhancedGameEngineAgent(verbose=False)
        test_engine.load_event_stream(stream_file)
        
        loaded_count = len(test_engine.event_store.events)
        original_count = len(enhanced_engine.event_store.events)
        
        if verbose:
            print(f"   📥 Event persistence test: {loaded_count}/{original_count} events")
        
        # Compare state reconstruction
        original_state = enhanced_engine.state_projector.project_state(
            enhanced_engine.event_store.events, enhanced_engine.base_state.copy()
        )
        loaded_state = test_engine.state_projector.project_state(
            test_engine.event_store.events, test_engine.base_state.copy()
        )
        
        states_equal = json.dumps(original_state, sort_keys=True) == json.dumps(loaded_state, sort_keys=True)
        
        if verbose:
            print(f"   🔄 State reconstruction: {'✅ Perfect match' if states_equal else '❌ Mismatch'}")
        
        # Clean up test file
        if os.path.exists(stream_file):
            os.remove(stream_file)
        
        return {
            "success": True,
            "initial_events": initial_events,
            "new_events": new_events,
            "total_events": after_events,
            "skill_events": len(skill_events),
            "character_events": len(character_events),
            "state_projection_successful": True,
            "persistence_test_successful": states_equal,
            "envelope": character_envelope.to_dict(),
            "result": result
        }
        
    except Exception as e:
        if verbose:
            print(f"   ❌ Enhanced game engine demo failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def test_pipeline_directly(orchestrator: AgentOrchestrator, verbose: bool = True) -> Dict[str, Any]:
    """
    Test pipelines directly through the registry
    
    Args:
        orchestrator: The AgentOrchestrator instance
        verbose: Whether to print test output
        
    Returns:
        Dict containing test results
    """
    if verbose:
        print("\n🧪 Testing Pipelines Directly...")
    
    test_results = {}
    
    if orchestrator.haystack_orchestrator and orchestrator.haystack_orchestrator.pipeline_registry:
        registry = orchestrator.haystack_orchestrator.pipeline_registry
        
        # Test each registered pipeline
        for intent in registry.get_registered_intents():
            if verbose:
                print(f"   🔬 Testing {intent} pipeline...")
            
            test_result = registry.test_pipeline(intent)
            test_results[intent] = test_result
            
            if verbose:
                success = test_result.get("success", False)
                status_icon = "✅" if success else "❌"
                print(f"      {status_icon} Test result: {success}")
                if not success:
                    print(f"         Error: {test_result.get('error', 'Unknown error')}")
    
    return test_results


if __name__ == "__main__":
    # Run the demo
    print("Starting D&D Assistant Haystack Integration Demo...")
    results = demo_haystack_integration(verbose=True)
    
    print(f"\n📊 Demo Summary:")
    print(f"   - Initialization successful: {not results['initialization'].get('errors')}")
    print(f"   - Skill check demo successful: {results['skill_check_demo'].get('success', False)}")
    print(f"   - Scenario choice demo successful: {results['scenario_choice_demo'].get('success', False)}")
    print(f"   - Enhanced game engine demo successful: {results['enhanced_game_engine_demo'].get('success', False)}")
    print(f"   - Errors encountered: {len(results.get('errors', []))}")
    
    if results.get('errors'):
        print(f"\n❌ Errors:")
        for error in results['errors']:
            print(f"   - {error}")
    else:
        print(f"\n🎉 All demos completed successfully!")
    
    # Save results to file
    with open("haystack_demo_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to haystack_demo_results.json")