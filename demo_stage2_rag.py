"""
Stage 2 Demo - RAG Integration and Simple Orchestrator
Demonstrates Haystack RAG with orchestrator patterns from Weeks 5-8
"""

import os
import sys
import logging
from pathlib import Path
from typing import Dict, Any

# Add project paths
sys.path.append(str(Path(__file__).parent))

from storage.simple_document_store import SimpleDocumentStore
from simple_dnd.scenario_generator_rag import RAGScenarioGenerator
from orchestrator.simple_orchestrator import SimpleOrchestrator, GameRequest, GameResponse


def setup_logging():
    """Setup logging for demo"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def create_sample_documents():
    """Create sample D&D content for RAG demonstration"""
    documents = [
        {
            "content": "The Goblin Caves: A network of dark tunnels filled with goblin tribes. "
                      "Features include trapped passages, treasure hoards, and a goblin king's throne room. "
                      "Suitable for levels 1-3. Contains magical artifacts and ancient runes.",
            "meta": {"type": "dungeon", "level": "1-3", "theme": "caves"}
        },
        {
            "content": "The Haunted Manor: An old aristocrat's mansion now infested with undead spirits. "
                      "Multiple floors with secret passages, a haunted library, and spectral encounters. "
                      "Suitable for levels 3-5. The basement contains a necromancer's laboratory.",
            "meta": {"type": "dungeon", "level": "3-5", "theme": "haunted"}
        },
        {
            "content": "The Dragon's Lair: A massive cavern system housing an ancient red dragon. "
                      "Filled with kobold servants, deadly traps, and an enormous treasure hoard. "
                      "Suitable for levels 8-12. The dragon has been terrorizing nearby villages.",
            "meta": {"type": "dungeon", "level": "8-12", "theme": "dragon"}
        },
        {
            "content": "The Elvish Forest: A mystical woodland where time flows differently. "
                      "Home to forest spirits, talking animals, and ancient tree guardians. "
                      "Suitable for levels 2-6. Contains a portal to the Feywild realm.",
            "meta": {"type": "wilderness", "level": "2-6", "theme": "forest"}
        },
        {
            "content": "The Pirate's Cove: A hidden bay where smugglers and pirates gather. "
                      "Features a tavern, black market, and several moored ships ready for adventure. "
                      "Suitable for levels 4-7. Rumors speak of a legendary treasure map.",
            "meta": {"type": "town", "level": "4-7", "theme": "pirates"}
        }
    ]
    
    return documents


def demo_rag_integration():
    """Demonstrate RAG document store and retrieval"""
    print("\n" + "="*60)
    print("STAGE 2 DEMO: RAG Integration")
    print("="*60)
    
    # Initialize document store
    print("\n1. Initializing RAG Document Store...")
    doc_store = SimpleDocumentStore()
    
    # Load sample documents
    print("2. Loading sample D&D content...")
    documents = create_sample_documents()
    doc_store.load_documents(documents)
    
    # Test retrieval
    print("3. Testing document retrieval...")
    queries = [
        "dragon treasure cave",
        "haunted mansion undead",
        "forest magical creatures"
    ]
    
    for query in queries:
        print(f"\nQuery: '{query}'")
        results = doc_store.retrieve_documents(query, top_k=2)
        for i, doc in enumerate(results, 1):
            content_preview = doc.content[:100] + "..." if len(doc.content) > 100 else doc.content
            print(f"  Result {i}: {content_preview}")
    
    return doc_store


def demo_rag_scenario_generation(doc_store):
    """Demonstrate RAG-enhanced scenario generation"""
    print("\n" + "="*60)
    print("RAG-Enhanced Scenario Generation")
    print("="*60)
    
    # Initialize RAG scenario generator with shared document store
    print("\n1. Initializing RAG Scenario Generator...")
    generator = RAGScenarioGenerator(doc_store)
    
    # Test scenario generation with different contexts
    scenarios = [
        {"context": "dungeon", "campaign": "Forgotten Realms"},
        {"context": "forest", "campaign": None},
        {"context": "tavern", "campaign": "Forgotten Realms"}
    ]
    
    print("2. Generating RAG-enhanced scenarios...")
    for i, scenario_request in enumerate(scenarios, 1):
        print(f"\n--- Scenario {i} ---")
        print(f"Request: {scenario_request}")
        
        try:
            scenario = generator.generate_scenario(**scenario_request)
            print(f"Generated Scene: {scenario.get('scene', 'N/A')[:150]}...")
            print(f"Choices: {len(scenario.get('choices', []))} options available")
            print(f"Method: {scenario.get('generation_method', 'unknown')}")
        except Exception as e:
            print(f"Error: {e}")
            print("Note: This demo shows the integration pattern - actual generation requires API keys")


def demo_orchestrator_integration():
    """Demonstrate orchestrator with extension hooks"""
    print("\n" + "="*60)
    print("Simple Orchestrator with Extension Hooks")
    print("="*60)
    
    # Create orchestrator
    print("\n1. Creating Simple Orchestrator...")
    orchestrator = SimpleOrchestrator()
    
    # Add custom hooks for demonstration
    def demo_pre_hook(request: Dict[str, Any]) -> Dict[str, Any]:
        request_type = request.get("type", request.get("request_type", "unknown"))
        print(f"  PRE-HOOK: Processing {request_type} request")
        return request
    
    def demo_post_hook(request: Dict[str, Any], response: Dict[str, Any]) -> Dict[str, Any]:
        success = response.get("success", False)
        print(f"  POST-HOOK: Processed response (success: {success})")
        return response
    
    orchestrator.add_pre_hook(demo_pre_hook)
    orchestrator.add_post_hook(demo_post_hook)
    
    # Test different request types
    print("\n2. Testing orchestrator request routing...")
    test_requests = [
        GameRequest("scenario", {"theme": "dungeon", "difficulty": "medium"}),
        GameRequest("dice_roll", {"dice": "1d20", "modifier": 3}),
        GameRequest("game_state", {"action": "get_current_state"}),
        GameRequest("unknown_type", {"test": "data"})  # Error case
    ]
    
    for request in test_requests:
        print(f"\nRequest: {request.request_type}")
        try:
            response = orchestrator.process_request(request)
            print(f"Success: {response.success}")
            if response.data:
                message = response.data.get('message', response.data.get('error', 'No message'))
                print(f"Response: {message}")
        except Exception as e:
            print(f"Error: {e}")


def demo_integration_patterns():
    """Demonstrate how components work together"""
    print("\n" + "="*60)
    print("Integration Patterns - Stage 2 Architecture")
    print("="*60)
    
    print("\n1. Component Integration:")
    print("   ✓ SimpleDocumentStore (Haystack + Qdrant)")
    print("   ✓ RAGScenarioGenerator (hwtgenielib + RAG)")
    print("   ✓ SimpleOrchestrator (Extension hooks)")
    
    print("\n2. Extension Points for Stage 3+:")
    print("   → Pre-hooks: Saga Manager integration")
    print("   → Post-hooks: Decision logging system")
    print("   → Handler registration: New request types")
    print("   → RAG enhancement: Campaign-specific content")
    
    print("\n3. Backward Compatibility:")
    print("   → Stage 1 simple_dnd_game.py still works")
    print("   → Stage 1 components remain unchanged")
    print("   → Stage 2 adds capabilities without breaking existing code")


def main():
    """Main demo execution"""
    setup_logging()
    
    print("D&D Game Assistant - Stage 2 Demo")
    print("Progressive Implementation: Weeks 5-8")
    print("Features: RAG Integration + Simple Orchestrator")
    
    try:
        # Demo RAG integration
        doc_store = demo_rag_integration()
        
        # Demo RAG scenario generation
        demo_rag_scenario_generation(doc_store)
        
        # Demo orchestrator
        demo_orchestrator_integration()
        
        # Show integration patterns
        demo_integration_patterns()
        
        print("\n" + "="*60)
        print("Stage 2 Demo Complete!")
        print("Ready for Stage 3: Advanced Saga Management")
        print("="*60)
        
    except Exception as e:
        print(f"\nDemo Error: {e}")
        print("Note: Some features require API keys and dependencies to be fully configured")


if __name__ == "__main__":
    main()