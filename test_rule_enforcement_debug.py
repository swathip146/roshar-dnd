#!/usr/bin/env python3
"""
Debug script for Rule Enforcement Agent issues
"""
import sys
import traceback
from rule_enforcement_agent import RuleEnforcementAgent
from haystack_pipeline_agent import HaystackPipelineAgent

def test_rule_enforcement():
    """Test rule enforcement agent in isolation"""
    print("🧪 Testing Rule Enforcement Agent...")
    
    try:
        # Test 1: Rule agent without RAG
        print("\n1. Testing Rule Agent (no RAG)...")
        rule_agent = RuleEnforcementAgent(rag_agent=None, strict_mode=False)
        result = rule_agent.check_rule("attack rolls", "combat")
        print(f"   Result: {result}")
        print(f"   Success: {'✅' if result.get('rule_text', '').startswith('Could not find') == False else '❌'}")
        
        # Test 2: Initialize Haystack agent
        print("\n2. Testing Haystack Agent initialization...")
        try:
            haystack_agent = HaystackPipelineAgent(collection_name="dnd_documents", verbose=True)
            print("   Haystack Agent initialized: ✅")
            
            # Test Haystack agent directly
            print("\n3. Testing Haystack Agent query...")
            response = haystack_agent.send_message_and_wait("haystack_pipeline", "query", {
                "query": "D&D 5e attack rolls",
                "context": "rule enforcement test"
            }, timeout=30.0)
            
            print(f"   Haystack Response: {'✅' if response and response.get('success') else '❌'}")
            if not response or not response.get('success'):
                print(f"   Haystack Error: Failed to get valid response")
            
        except Exception as e:
            print(f"   Haystack Agent failed: ❌ {e}")
            print(f"   Traceback: {traceback.format_exc()}")
            haystack_agent = None
        
        # Test 3: Rule agent with Haystack
        if haystack_agent:
            print("\n4. Testing Rule Agent with Haystack...")
            rule_agent_with_haystack = RuleEnforcementAgent(haystack_agent=haystack_agent, strict_mode=False)
            
            # Test the internal method directly
            try:
                result = rule_agent_with_haystack.check_rule("attack rolls", "combat")
                print(f"   Rule check result: {result}")
                print(f"   Success: {'✅' if result.get('confidence', 'low') != 'low' else '❌'}")
            except Exception as e:
                print(f"   Rule check failed: ❌ {e}")
                print(f"   Traceback: {traceback.format_exc()}")
        
        # Test 4: Test condition effects (should work without Haystack)
        print("\n5. Testing condition effects...")
        effects = rule_agent.get_condition_effects("poisoned")
        print(f"   Condition effects: {effects}")
        print(f"   Success: {'✅' if 'effects' in effects else '❌'}")
        
    except Exception as e:
        print(f"❌ Overall test failed: {e}")
        print(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    test_rule_enforcement()