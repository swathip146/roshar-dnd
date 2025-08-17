#!/usr/bin/env python3
"""
Enhanced Game Engine Integration Test
Demonstrates the enhanced game engine working with Haystack pipelines for event sourcing
"""

import sys
import os
import time
import json
from typing import Dict, Any, Optional

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from agent_framework import AgentOrchestrator
from core.command_envelope import create_command_envelope


def test_enhanced_game_engine_integration(verbose: bool = True):
    """Test enhanced game engine integration with Haystack pipelines"""
    
    print("🧪 Enhanced Game Engine Integration Test")
    print("=" * 50)
    
    # 1. Initialize orchestrator with enhanced game engine
    orchestrator = AgentOrchestrator(enable_haystack=True, verbose=verbose)
    
    try:
        # Initialize all agents
        orchestrator.initialize_dnd_agents(verbose=verbose)
        orchestrator.start()
        
        print("✅ Orchestrator and agents initialized")
        time.sleep(1)  # Allow agents to start
        
        # 2. Test event sourcing - create initial character state
        print("\n🎯 Testing Event Sourcing - Character Creation")
        
        character_envelope = create_command_envelope(
            intent="SKILL_CHECK",
            utterance="I want to make an Athletics check",
            actor={
                "name": "Kaladin",
                "type": "player_character",
                "level": 5
            },
            entities={"skill": "athletics"},
            context={"scenario": "climbing_rope"}
        )
        
        result = orchestrator.handle_command_envelope(character_envelope)
        print(f"📊 Initial skill check result: {json.dumps(result, indent=2)}")
        
        # 3. Check event store in enhanced game engine
        print("\n🔍 Checking Event Store")
        
        enhanced_engine = orchestrator.enhanced_game_engine_agent
        if enhanced_engine:
            event_count = len(enhanced_engine.event_store.events)
            print(f"📈 Events in store: {event_count}")
            
            if event_count > 0:
                latest_event = enhanced_engine.event_store.events[-1]
                print(f"📋 Latest event: {latest_event.event_type}")
                print(f"   Actor: {latest_event.payload.get('actor', 'Unknown')}")
                print(f"   Timestamp: {time.ctime(latest_event.timestamp)}")
            
            # Test state projection
            print("\n🎪 Testing State Projection")
            current_state = enhanced_engine.state_projector.project_state(
                enhanced_engine.event_store.events, enhanced_engine.base_state.copy()
            )
            
            print(f"🎭 Current game state keys: {list(current_state.keys())}")
            if "characters" in current_state:
                print(f"🎪 Characters in state: {list(current_state['characters'].keys())}")
                if "Kaladin" in current_state["characters"]:
                    kaladin_state = current_state["characters"]["Kaladin"]
                    print(f"   Kaladin state: {json.dumps(kaladin_state, indent=4)}")
        
        # 4. Test multiple skill checks to see event accumulation
        print("\n🎲 Testing Multiple Skill Checks")
        
        skills_to_test = ["perception", "stealth", "persuasion"]
        for skill in skills_to_test:
            envelope = create_command_envelope(
                intent="SKILL_CHECK",
                utterance=f"I want to make a {skill} check",
                actor={"name": "Kaladin", "type": "player_character"},
                entities={"skill": skill},
                context={"scenario": f"testing_{skill}"}
            )
            
            result = orchestrator.handle_command_envelope(envelope)
            success = result.get("success", False)
            print(f"   {skill.capitalize()}: {'✅' if success else '❌'}")
            
            time.sleep(0.5)  # Brief pause between checks
        
        # 5. Final event store analysis
        print("\n📈 Final Event Store Analysis")
        
        if enhanced_engine:
            final_event_count = len(enhanced_engine.event_store.events)
            print(f"📊 Total events after testing: {final_event_count}")
            
            # Show event types
            event_types = {}
            for event in enhanced_engine.event_store.events:
                event_type = event.event_type
                event_types[event_type] = event_types.get(event_type, 0) + 1
            
            print("📋 Event types breakdown:")
            for event_type, count in event_types.items():
                print(f"   {event_type}: {count}")
            
            # Test event stream persistence
            print("\n💾 Testing Event Stream Persistence")
            enhanced_engine.save_event_stream("test_event_stream.json")
            print("✅ Event stream saved to test_event_stream.json")
            
            # Test loading from saved stream
            new_enhanced_engine = enhanced_engine.__class__(verbose=verbose)
            new_enhanced_engine.load_event_stream("test_event_stream.json")
            
            loaded_event_count = len(new_enhanced_engine.event_store.events)
            print(f"📥 Loaded {loaded_event_count} events from saved stream")
            
            # Compare states
            original_state = enhanced_engine.state_projector.project_state(
                enhanced_engine.event_store.events, enhanced_engine.base_state.copy()
            )
            loaded_state = new_enhanced_engine.state_projector.project_state(
                new_enhanced_engine.event_store.events, new_enhanced_engine.base_state.copy()
            )
            
            states_match = json.dumps(original_state, sort_keys=True) == json.dumps(loaded_state, sort_keys=True)
            print(f"🔄 State reconstruction after load: {'✅ Match' if states_match else '❌ Mismatch'}")
        
        # 6. Test backward compatibility 
        print("\n🔄 Testing Backward Compatibility")
        
        # Send message directly to regular game engine
        if orchestrator.game_engine_agent:
            message_id = orchestrator.send_message_to_agent(
                receiver_id="game_engine",
                action="get_character_data", 
                data={"actor": "Kaladin", "request_type": "character.ref.request"}
            )
            print("✅ Successfully sent message to legacy game engine")
            time.sleep(0.5)
            
            # Check message history for response
            history = orchestrator.message_bus.get_message_history(limit=10)
            response_found = False
            for msg in reversed(history):
                if msg.get("response_to") == message_id:
                    response_found = True
                    break
            print(f"🔄 Legacy game engine response: {'✅ Received' if response_found else '❌ Not found'}")
        
        print("\n✅ Enhanced Game Engine Integration Test Complete")
        return True
        
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        orchestrator.stop()
        print("🛑 Orchestrator stopped")


def test_event_sourcing_patterns(verbose: bool = True):
    """Test specific event sourcing patterns"""
    
    print("\n🧪 Event Sourcing Patterns Test")
    print("=" * 40)
    
    # Test direct enhanced game engine usage
    from core.enhanced_game_engine import EnhancedGameEngineAgent, GameEvent
    
    # Create enhanced game engine instance
    engine = EnhancedGameEngineAgent(verbose=verbose)
    
    print("🎭 Testing Direct Event Operations")
    
    # 1. Test direct event creation
    test_event = GameEvent(
        event_id="test_001",
        event_type="character.created",
        actor="TestCharacter", 
        payload={
            "character_name": "TestCharacter",
            "class": "Fighter",
            "level": 1,
            "hp": 12
        }
    )
    
    engine.event_store.append_event(test_event)
    print("✅ Direct event appended to store")
    
    # 2. Test state projection
    state = engine.state_projector.project_state(engine.event_store.events, engine.base_state.copy())
    print(f"🎪 Projected state keys: {list(state.keys())}")
    
    # 3. Test event filtering
    character_events = engine.event_store.get_events_by_type("character.created")
    print(f"🔍 Character creation events: {len(character_events)}")
    
    skill_events = engine.event_store.get_events_by_type("skill_check.resolved")
    print(f"🎲 Skill check events: {len(skill_events)}")
    
    # 4. Test event replay
    print("\n🔄 Testing Event Replay")
    
    # Add more events
    events_to_add = [
        GameEvent(
            event_id="test_002",
            event_type="skill_check.resolved",
            actor="TestCharacter",
            payload={
                "skill": "athletics",
                "roll": 15,
                "modifier": 3,
                "total": 18,
                "success": True
            }
        ),
        GameEvent(
            event_id="test_003", 
            event_type="character.leveled_up",
            actor="TestCharacter",
            payload={
                "old_level": 1,
                "new_level": 2,
                "hp_gained": 7
            }
        )
    ]
    
    for event in events_to_add:
        engine.event_store.append_event(event)
    
    # Project final state
    final_state = engine.state_projector.project_state(engine.event_store.events, engine.base_state.copy())
    
    if "characters" in final_state and "TestCharacter" in final_state["characters"]:
        char_state = final_state["characters"]["TestCharacter"]
        print(f"🎭 Final TestCharacter state: {json.dumps(char_state, indent=2)}")
    
    print("✅ Event Sourcing Patterns Test Complete")


if __name__ == "__main__":
    print("🚀 Starting Enhanced Game Engine Integration Tests")
    print("=" * 60)
    
    # Run integration test
    integration_success = test_enhanced_game_engine_integration(verbose=True)
    
    # Run event sourcing patterns test
    test_event_sourcing_patterns(verbose=True)
    
    print("\n" + "=" * 60)
    if integration_success:
        print("🎉 All tests completed successfully!")
    else:
        print("⚠️ Some tests failed - check output above")
        
    # Clean up test files
    import os
    test_files = ["test_event_stream.json"]
    for file in test_files:
        if os.path.exists(file):
            os.remove(file)
            print(f"🧹 Cleaned up {file}")