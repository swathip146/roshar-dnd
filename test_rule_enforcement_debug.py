#!/usr/bin/env python3
"""
Debug script for Rule Enforcement Agent issues
"""
import sys
import traceback
from rule_enforcement_agent import RuleEnforcementAgent
from rag_agent_integrated import RAGAgent

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
        
        # Test 2: Initialize RAG agent
        print("\n2. Testing RAG Agent initialization...")
        try:
            rag_agent = RAGAgent(collection_name="dnd_documents", verbose=True)
            print("   RAG Agent initialized: ✅")
            
            # Test RAG agent directly
            print("\n3. Testing RAG Agent query...")
            rag_result = rag_agent.query("D&D 5e attack rolls")
            print(f"   RAG Result keys: {list(rag_result.keys())}")
            print(f"   RAG Success: {'✅' if 'error' not in rag_result else '❌'}")
            if 'error' in rag_result:
                print(f"   RAG Error: {rag_result['error']}")
            
        except Exception as e:
            print(f"   RAG Agent failed: ❌ {e}")
            print(f"   Traceback: {traceback.format_exc()}")
            rag_agent = None
        
        # Test 3: Rule agent with RAG
        if rag_agent:
            print("\n4. Testing Rule Agent with RAG...")
            rule_agent_with_rag = RuleEnforcementAgent(rag_agent=rag_agent, strict_mode=False)
            
            # Test the internal method directly 
            try:
                result = rule_agent_with_rag.check_rule("attack rolls", "combat")
                print(f"   Rule check result: {result}")
                print(f"   Success: {'✅' if result.get('confidence', 'low') != 'low' else '❌'}")
            except Exception as e:
                print(f"   Rule check failed: ❌ {e}")
                print(f"   Traceback: {traceback.format_exc()}")
        
        # Test 4: Test condition effects (should work without RAG)
        print("\n5. Testing condition effects...")
        effects = rule_agent.get_condition_effects("poisoned")
        print(f"   Condition effects: {effects}")
        print(f"   Success: {'✅' if 'effects' in effects else '❌'}")
        
    except Exception as e:
        print(f"❌ Overall test failed: {e}")
        print(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    test_rule_enforcement()