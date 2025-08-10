"""
Example usage of the RAG-powered D&D Character Generator
This script demonstrates how to use the character generation system programmatically
"""
from rag_character_generator import CharacterGenerator, CharacterDetails

def demo_character_generation():
    """Demonstrate programmatic character generation"""
    print("=== RAG Character Generator Demo ===")
    print("This script shows how to use the character generator programmatically")
    print()
    
    try:
        # Initialize the generator
        print("Initializing character generator...")
        generator = CharacterGenerator(verbose=True)
        
        # Show available options
        print(f"\nAvailable rulebooks: {generator.available_rulebooks}")
        print(f"Available races: {generator.get_available_races()}")
        print(f"Available classes: {generator.get_available_classes()}")
        print(f"Available backgrounds: {generator.get_available_backgrounds()}")
        
        # Generate a few example characters
        example_preferences = [
            {
                "name": "Thorin Ironforge",
                "race": "Dwarf",
                "class": "Fighter",
                "background": "Soldier",
                "level": 3,
                "ability_score_method": "4d6_drop_lowest"
            },
            {
                "name": "Lyralei Moonwhisper",
                "race": "Elf",
                "class": "Ranger",
                "background": "Outlander",
                "level": 2,
                "ability_score_method": "3d6"
            },
            {
                "name": "Finn Lightfingers",
                "race": "Halfling",
                "class": "Rogue",
                "background": "Criminal",
                "level": 1,
                "ability_score_method": "4d6_drop_lowest"
            }
        ]
        
        generated_characters = []
        
        for i, prefs in enumerate(example_preferences, 1):
            print(f"\n=== Generating Character {i}: {prefs['name']} ===")
            character = generator.create_character(prefs)
            generated_characters.append(character)
            
            # Display character sheet
            print(generator.format_character_sheet(character))
            
            # Save character to file
            filename = f"{prefs['name'].lower().replace(' ', '_')}.json"
            if generator.save_character(character, filename):
                print(f"✓ Character saved to: {filename}")
        
        print(f"\n✓ Generated {len(generated_characters)} characters successfully!")
        
        # Demonstrate RAG queries
        print("\n=== RAG Query Examples ===")
        test_queries = [
            "What are the starting hit points for a level 1 Fighter?",
            "What racial abilities do Elves have?",
            "What equipment does a Criminal background provide?",
            "How do ability score modifiers work in D&D 5e?"
        ]
        
        for query in test_queries:
            print(f"\nQuery: {query}")
            response = generator.query_rag(query)
            # Truncate response for demo
            if len(response) > 200:
                response = response[:200] + "..."
            print(f"Response: {response}")
        
    except Exception as e:
        print(f"❌ Error during demo: {e}")

def interactive_demo():
    """Run an interactive demo session"""
    print("\n=== Interactive Demo ===")
    print("This will run the full interactive character generator")
    
    from rag_character_generator import main
    main()

if __name__ == "__main__":
    # Run programmatic demo
    demo_character_generation()
    
    # Ask if user wants to run interactive demo
    print("\n" + "="*50)
    run_interactive = input("Run interactive character generator? (y/n): ").strip().lower()
    if run_interactive in ['y', 'yes']:
        interactive_demo()
    else:
        print("Demo complete!")