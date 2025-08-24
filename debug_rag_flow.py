#!/usr/bin/env python3
"""
Debug RAG Flow - Trace how lore queries are processed
"""

import logging
from orchestrator.pipeline_integration import create_full_haystack_orchestrator, GameRequest
from storage.simple_document_store import SimpleDocumentStore

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

def debug_rag_query_flow():
    """Debug the complete RAG query flow"""
    
    print("🔍 DEBUGGING RAG QUERY FLOW")
    print("=" * 50)
    
    # 1. Initialize document store
    print("1️⃣ Setting up document store...")
    try:
        document_store = SimpleDocumentStore(collection_name="debug_rag_test")
        document_store.load_basic_content()
        print(f"✅ Document store initialized with collection: {document_store.collection_name}")
    except Exception as e:
        print(f"❌ Document store failed: {e}")
        return
    
    # 2. Create orchestrator with document store
    print("\n2️⃣ Creating orchestrator with document store...")
    try:
        orchestrator = create_full_haystack_orchestrator(document_store=document_store)
        print("✅ Orchestrator created with RAG capabilities")
    except Exception as e:
        print(f"❌ Orchestrator creation failed: {e}")
        return
    
    # 3. Test lore query processing
    print("\n3️⃣ Testing lore query: 'I have a query about lore- who are the Alethi?'")
    
    # Test the exact input that failed
    lore_query = "I have a query about lore- who are the Alethi?"
    
    # Create the same request as would be created in game
    context = {
        "location": "Tavern",
        "difficulty": "medium",
        "environment": {
            "lighting": "normal",
            "atmosphere": "tavern"
        },
        "recent_history": "This is the beginning of your adventure.",
        "session_duration": 100.0,
        "enhanced_mode": True,
        "average_party_level": 1
    }
    
    request = GameRequest(
        request_type="gameplay_turn",
        data={
            "player_input": lore_query,
            "actor": "player",
            "context": context
        }
    )
    
    print(f"📨 Request created: {request.request_type}")
    print(f"📨 Player input: '{lore_query}'")
    
    # 4. Process through orchestrator
    print("\n4️⃣ Processing through orchestrator...")
    try:
        response = orchestrator.process_request(request)
        print(f"✅ Response success: {response.success}")
        
        if response.success:
            print("📋 Response data keys:", list(response.data.keys()) if isinstance(response.data, dict) else "Not a dict")
            
            # Look for RAG content
            if isinstance(response.data, dict):
                for key, value in response.data.items():
                    print(f"  {key}: {str(value)[:100]}...")
                    
                    # Check if RAG was used
                    if "rag" in key.lower() or "document" in str(value).lower() or "alethi" in str(value).lower():
                        print(f"🎯 Potential RAG content found in {key}")
        else:
            print(f"❌ Response failed: {response.data}")
            
    except Exception as e:
        print(f"❌ Processing failed: {e}")
        import traceback
        traceback.print_exc()
    
    # 5. Test direct RAG retrieval
    print("\n5️⃣ Testing direct RAG retrieval...")
    try:
        rag_request = GameRequest(
            request_type="rag_query",
            data={"query": "who are the Alethi"}
        )
        
        rag_response = orchestrator.process_request(rag_request)
        print(f"✅ Direct RAG response success: {rag_response.success}")
        
        if rag_response.success:
            print("📋 RAG Response data:", rag_response.data)
        else:
            print(f"❌ Direct RAG failed: {rag_response.data}")
            
    except Exception as e:
        print(f"❌ Direct RAG test failed: {e}")
    
    # 6. Test interface agent routing
    print("\n6️⃣ Testing interface agent routing...")
    try:
        interface_request = GameRequest(
            request_type="interface_processing",
            data={
                "player_input": lore_query,
                "game_context": context
            }
        )
        
        interface_response = orchestrator.process_request(interface_request)
        print(f"✅ Interface response success: {interface_response.success}")
        
        if interface_response.success:
            print("📋 Interface routing data:", interface_response.data)
            
            # Check routing strategy
            routing_strategy = interface_response.data.get("routing_strategy", "unknown")
            print(f"🎯 Routing strategy: {routing_strategy}")
            
            if routing_strategy == "scenario_pipeline":
                print("✅ Correctly routed to scenario pipeline (should use RAG)")
            else:
                print(f"⚠️ Routed to {routing_strategy} instead of scenario_pipeline")
        else:
            print(f"❌ Interface routing failed: {interface_response.data}")
            
    except Exception as e:
        print(f"❌ Interface routing test failed: {e}")

if __name__ == "__main__":
    debug_rag_query_flow()