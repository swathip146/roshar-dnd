#!/usr/bin/env python3
"""
Test script to verify just the RAG document retrieval (without LLM)
"""

import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

def test_rag_document_retrieval():
    """Test just the document retrieval part of RAG agent"""
    try:
        from agents.rag_retriever_agent import create_retrieve_documents_tool
        from storage.simple_document_store import SimpleDocumentStore
        
        print("🧪 Testing RAG document retrieval tool...")
        
        # Create document store
        doc_store = SimpleDocumentStore(collection_name="test_rag_retrieval", storage_path="./test_qdrant_retrieval")
        
        # Load sample content that includes weapon information
        print("📚 Loading sample content...")
        doc_store.load_basic_content()
        
        # Add some weapon information to test longsword query
        weapon_content = """
        Weapon Statistics - Longsword
        
        Longsword
        - Damage: 1d8 slashing (versatile 1d10)
        - Properties: Versatile
        - Weight: 3 lbs
        - Cost: 15 gp
        - Category: Martial Melee Weapon
        
        A longsword is a versatile weapon that can be wielded with one or two hands.
        When wielded with two hands, it deals 1d10 damage instead of 1d8.
        """
        
        doc_store.add_campaign_content(weapon_content, {
            "type": "rules",
            "category": "weapons",
            "name": "Longsword Statistics"
        })
        print("✅ Added weapon data to document store")
        
        # Create the retrieve_documents tool
        retrieve_tool = create_retrieve_documents_tool(doc_store)
        print("✅ Created retrieve_documents tool")
        
        # Test the tool directly by calling its function
        print("🔍 Testing tool with longsword query...")
        result = retrieve_tool._function(
            query="longsword damage dice statistics weapon properties",
            top_k=5,
            context_type="rules",
            filters={"categories": ["weapons", "longsword", "damage", "statistics"]}
        )
        
        print("📊 Tool result keys:", list(result.keys()) if result else "None")
        
        if result and "documents" in result:
            documents = result["documents"]
            print(f"✅ Retrieved {len(documents)} documents")
            
            for i, doc in enumerate(documents):
                print(f"  {i+1}. Score: {doc.get('score', 0):.3f}")
                content = doc.get('content', '')
                print(f"     Content preview: {content[:100]}...")
                
                # Check if we found weapon-related content
                if 'longsword' in content.lower() or 'damage' in content.lower():
                    print(f"     ✅ Found relevant weapon content!")
            
            return True
        else:
            print("⚠️ No documents in result")
            return False
            
    except Exception as e:
        print(f"❌ RAG retrieval test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🔧 Testing RAG Document Retrieval (No LLM)")
    print("=" * 50)
    
    success = test_rag_document_retrieval()
    
    print(f"\n📋 Test Result: {'✅ PASS' if success else '❌ FAIL'}")
    
    if success:
        print("\n🎉 RAG document retrieval is working!")
        print("The original 'Missing input for component ranker: query' error should be fixed!")
    else:
        print("\n⚠️ RAG retrieval still has issues")