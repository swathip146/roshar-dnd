#!/usr/bin/env python3
"""
Test the actual format of rule query responses through the DM assistant
"""
from modular_dm_assistant import ModularDMAssistant

def test_rule_query_format():
    """Test what rule queries actually return through the DM assistant"""
    print("🧪 Testing Rule Query Response Format...")
    
    try:
        assistant = ModularDMAssistant(collection_name="dnd_documents", verbose=True)
        assistant.start()
        
        # Test the same queries used in the comprehensive test
        rule_queries = [
            "how does advantage work",
            "what is the poisoned condition", 
            "explain spell concentration"
        ]
        
        for i, query in enumerate(rule_queries, 1):
            print(f"\n{i}. Testing query: '{query}'")
            response = assistant.process_dm_input(query)
            print(f"   Response length: {len(response)}")
            print(f"   Contains 'RULE': {'RULE' in response}")
            print(f"   Contains 'CONDITION': {'CONDITION' in response}")
            print(f"   Contains 'Failed to find rule': {'Failed to find rule' in response}")
            print(f"   Response preview: {response[:200]}...")
            
            # Check what success criteria should be
            has_meaningful_content = len(response) > 50 and "❌" not in response
            print(f"   Meaningful content: {has_meaningful_content}")
        
        assistant.stop()
        
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    test_rule_query_format()