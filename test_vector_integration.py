"""
Test script for the enhanced vector database integration in character generator
"""
from rag_character_generator import CharacterGenerator

def test_vector_integration():
    """Test the direct vector database integration"""
    print("=== Testing Enhanced Vector Database Integration ===")
    
    try:
        # Initialize generator
        generator = CharacterGenerator(verbose=True)
        
        # Test direct document retrieval
        print("\n1. Testing direct document retrieval...")
        query = "fighter starting equipment armor weapons"
        docs = generator.retrieve_context_documents(query, top_k=3)
        
        print(f"Retrieved {len(docs)} documents for query: '{query}'")
        for i, doc in enumerate(docs, 1):
            print(f"  {i}. Source: {doc.meta.get('source_file', 'Unknown')}")
            print(f"     Preview: {doc.content[:100]}...")
            print(f"     Score: {doc.meta.get('score', 'N/A')}")
        
        # Test equipment generation with vector context
        print("\n2. Testing equipment generation...")
        equipment = generator.get_starting_equipment("Fighter", "Soldier")
        print(f"Fighter/Soldier equipment: {equipment}")
        
        # Test class features with vector context
        print("\n3. Testing class features...")
        features = generator.get_class_features("Fighter", 1)
        print(f"Fighter Level 1 features: {features}")
        
        # Test racial traits with vector context
        print("\n4. Testing racial traits...")
        traits = generator.get_racial_traits("Dwarf")
        print(f"Dwarf racial traits: {traits}")
        
        # Test personality generation with context
        print("\n5. Testing personality generation...")
        personality = generator.generate_personality("Dwarf", "Fighter", "Soldier")
        for key, value in personality.items():
            print(f"{key}: {value}")
        
        print("\n✓ Vector integration test completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

def test_point_buy():
    """Test the enhanced point buy system"""
    print("\n=== Testing Point Buy System ===")
    
    try:
        generator = CharacterGenerator(verbose=True)
        
        # Test random point buy generation
        print("Testing random point buy generation...")
        stats = generator._generate_random_point_buy()
        
        print(f"Generated stats: STR:{stats.strength} DEX:{stats.dexterity} CON:{stats.constitution}")
        print(f"                 INT:{stats.intelligence} WIS:{stats.wisdom} CHA:{stats.charisma}")
        
        # Calculate point cost to verify
        total_cost = 0
        for score in [stats.strength, stats.dexterity, stats.constitution, 
                     stats.intelligence, stats.wisdom, stats.charisma]:
            if score <= 13:
                total_cost += score - 8
            elif score == 14:
                total_cost += 7
            elif score == 15:
                total_cost += 9
        
        print(f"Point cost verification: {total_cost}/27 points")
        
        if total_cost == 27:
            print("✓ Point buy generation working correctly!")
        else:
            print(f"❌ Point buy error: used {total_cost} points instead of 27")
            
    except Exception as e:
        print(f"❌ Point buy test failed: {e}")

if __name__ == "__main__":
    test_vector_integration()
    test_point_buy()