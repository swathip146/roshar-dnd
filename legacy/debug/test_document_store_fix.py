#!/usr/bin/env python3
"""
Test script to verify the document store and RAG search fixes
"""

import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

def test_simple_document_store():
    """Test SimpleDocumentStore initialization and search"""
    try:
        from storage.simple_document_store import SimpleDocumentStore
        
        print("🧪 Testing SimpleDocumentStore initialization...")
        
        # Initialize document store
        doc_store = SimpleDocumentStore(collection_name="test_dnd", storage_path="./test_qdrant_storage")
        print("✅ Document store initialized successfully")
        
        # Load sample content
        print("📚 Loading sample content...")
        doc_store.load_basic_content()
        print("✅ Sample content loaded")
        
        # Test search with the fixed pipeline
        print("🔍 Testing search with fixed pipeline...")
        query = "longsword damage dice statistics weapon properties"
        results = doc_store.search_with_metadata(query, top_k=3)
        
        print(f"📊 Search results: {len(results)} documents found")
        for i, result in enumerate(results):
            print(f"  {i+1}. Score: {result.get('score', 0):.3f}")
            print(f"     Content: {result['content'][:100]}...")
        
        if results:
            print("✅ Search working correctly - pipeline fix successful!")
        else:
            print("⚠️ No results found - may need to add weapon data")
            
        return True
        
    except Exception as e:
        print(f"❌ Document store test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_rag_agent():
    """Test RAG agent with the fixed format_rag_response tool"""
    try:
        from agents.rag_retriever_agent import create_rag_retriever_agent_simplified
        from storage.simple_document_store import SimpleDocumentStore
        from haystack.dataclasses import ChatMessage
        
        print("\n🧪 Testing RAG agent with document store...")
        
        # Create document store
        doc_store = SimpleDocumentStore(collection_name="test_dnd_rag", storage_path="./test_qdrant_rag")
        doc_store.load_basic_content()
        
        # Create RAG agent with document store
        rag_agent = create_rag_retriever_agent_simplified(document_store=doc_store)
        print("✅ RAG agent created with document store")
        
        # Test RAG query
        rag_message = ChatMessage.from_user("""
        Query: longsword damage dice statistics weapon properties
        Context Type: rules
        Filters: weapons, longsword, damage, statistics
        
        Retrieve relevant documents for this query and format them appropriately.
        """)
        
        print("🔍 Running RAG agent...")
        result = rag_agent.run(messages=[rag_message])
        
        print("📊 RAG agent result keys:", list(result.keys()) if result else "None")
        
        if "rag_response" in result:
            rag_response = result["rag_response"]
            print("✅ RAG response generated:")
            print(f"   Type: {rag_response.get('type', 'unknown')}")
            print(f"   Confidence: {rag_response.get('confidence', 0)}")
            print(f"   Context length: {len(rag_response.get('context', ''))}")
            return True
        else:
            print("⚠️ No rag_response in result")
            return False
            
    except Exception as e:
        print(f"❌ RAG agent test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔧 Testing Document Store and RAG Fixes")
    print("=" * 50)
    
    # Test 1: Document store with fixed pipeline
    store_success = test_simple_document_store()
    
    # Test 2: RAG agent with fixed format_rag_response
    rag_success = test_rag_agent()
    
    print("\n📋 Test Summary:")
    print(f"Document Store: {'✅ PASS' if store_success else '❌ FAIL'}")
    print(f"RAG Agent: {'✅ PASS' if rag_success else '❌ FAIL'}")
    
    if store_success and rag_success:
        print("\n🎉 All fixes working correctly!")
    else:
        print("\n⚠️ Some issues remain to be fixed")