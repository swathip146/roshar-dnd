"""
Example usage of the Campaign Generator
Demonstrates how to use the RAG-powered campaign generator programmatically
"""
import json
from campaign_generator import CampaignGenerator

def example_basic_generation():
    """Example of basic campaign generation"""
    print("=== Basic Campaign Generation Example ===")
    
    try:
        # Initialize the generator
        generator = CampaignGenerator(collection_name="dnd_documents", verbose=True)
        
        # Generate a campaign
        prompt = "A dark fantasy campaign where players must investigate a cursed village plagued by undead"
        print(f"\nGenerating campaign with prompt: {prompt}")
        
        campaign = generator.generate_campaign(prompt)
        
        if "error" in campaign:
            print(f"❌ Error: {campaign['error']}")
            return
        
        print("✓ Campaign generated successfully!")
        print("\n" + "="*50)
        print(generator.display_campaign_summary())
        
        # Show some specific details
        print("\n🎣 Campaign Hooks:")
        for i, hook in enumerate(campaign.get('hooks', []), 1):
            print(f"  {i}. {hook}")
        
        print("\n👥 Key NPCs:")
        for npc in campaign.get('key_npcs', []):
            print(f"  • {npc.get('name', 'Unknown')} - {npc.get('role', 'Unknown role')}")
            print(f"    {npc.get('description', 'No description')}")
        
        return generator
        
    except Exception as e:
        print(f"❌ Error in basic generation: {e}")
        return None

def example_campaign_refinement(generator):
    """Example of campaign refinement"""
    if not generator or not generator.current_campaign:
        print("⚠️  No campaign to refine. Run basic generation first.")
        return
    
    print("\n=== Campaign Refinement Example ===")
    
    try:
        # Refine the campaign
        refinement = "Add steampunk elements and include airships and mechanical constructs"
        print(f"\nRefining campaign: {refinement}")
        
        refined_campaign = generator.refine_campaign(refinement)
        
        if "error" in refined_campaign:
            print(f"❌ Error: {refined_campaign['error']}")
            return
        
        print("✓ Campaign refined successfully!")
        print("\n" + "="*50)
        print(generator.display_campaign_summary())
        
        # Show the user prompts history
        print(f"\n📝 Refinement History:")
        for i, prompt in enumerate(refined_campaign.get('user_prompts', []), 1):
            print(f"  {i}. {prompt}")
        
    except Exception as e:
        print(f"❌ Error in refinement: {e}")

def example_campaign_suggestions():
    """Example of getting campaign suggestions"""
    print("\n=== Campaign Suggestions Example ===")
    
    try:
        generator = CampaignGenerator(collection_name="dnd_documents", verbose=False)
        
        # Get general suggestions
        print("\n🎲 General Campaign Suggestions:")
        suggestions = generator.get_campaign_suggestions()
        for i, suggestion in enumerate(suggestions, 1):
            print(f"  {i}. {suggestion}")
        
        # Get themed suggestions
        print("\n🎲 Horror-themed Suggestions:")
        horror_suggestions = generator.get_campaign_suggestions("horror")
        for i, suggestion in enumerate(horror_suggestions, 1):
            print(f"  {i}. {suggestion}")
        
    except Exception as e:
        print(f"❌ Error getting suggestions: {e}")

def example_save_and_load():
    """Example of saving and loading campaigns"""
    print("\n=== Save and Load Example ===")
    
    try:
        generator = CampaignGenerator(collection_name="dnd_documents", verbose=True)
        
        # Generate a simple campaign
        campaign = generator.generate_campaign("A political intrigue campaign in a royal court")
        
        if "error" in campaign:
            print(f"❌ Error generating campaign: {campaign['error']}")
            return
        
        # Save the campaign
        filename = "example_campaign.json"
        if generator.save_campaign(filename):
            print(f"✓ Campaign saved to {filename}")
        
        # Create a new generator and load the campaign
        new_generator = CampaignGenerator(collection_name="dnd_documents", verbose=True)
        if new_generator.load_campaign(filename):
            print(f"✓ Campaign loaded successfully")
            print(new_generator.display_campaign_summary())
        
    except Exception as e:
        print(f"❌ Error in save/load: {e}")

def example_programmatic_usage():
    """Example of using the generator programmatically without CLI"""
    print("\n=== Programmatic Usage Example ===")
    
    try:
        generator = CampaignGenerator(collection_name="dnd_documents", verbose=False)
        
        # Generate multiple campaign variations
        base_prompt = "An exploration campaign"
        variations = [
            "in the Underdark with strange creatures",
            "in floating sky islands with aerial navigation",
            "in a post-apocalyptic wasteland with scarce resources"
        ]
        
        campaigns = []
        for variation in variations:
            full_prompt = f"{base_prompt} {variation}"
            print(f"Generating: {full_prompt}")
            
            campaign = generator.generate_campaign(full_prompt)
            if "error" not in campaign:
                campaigns.append({
                    "prompt": full_prompt,
                    "title": campaign.get("title", "Untitled"),
                    "theme": campaign.get("theme", "Unknown"),
                    "overview": campaign.get("overview", "No overview")
                })
                print(f"  ✓ Generated: {campaign.get('title', 'Untitled')}")
            else:
                print(f"  ❌ Error: {campaign['error']}")
        
        # Display comparison
        print(f"\n📊 Generated {len(campaigns)} campaign variations:")
        for i, camp in enumerate(campaigns, 1):
            print(f"\n{i}. {camp['title']}")
            print(f"   Theme: {camp['theme']}")
            print(f"   Overview: {camp['overview'][:100]}{'...' if len(camp['overview']) > 100 else ''}")
        
    except Exception as e:
        print(f"❌ Error in programmatic usage: {e}")

def check_prerequisites():
    """Check if the system is ready for campaign generation"""
    print("=== Prerequisites Check ===")
    
    try:
        from rag_agent import RAGAgent, CLAUDE_AVAILABLE
        
        if not CLAUDE_AVAILABLE:
            print("❌ Claude integration not available")
            print("   Campaign generation requires Claude for LLM functionality")
            return False
        else:
            print("✓ Claude integration available")
        
        # Try to initialize RAG agent
        try:
            agent = RAGAgent(collection_name="dnd_documents", verbose=False)
            print("✓ RAG agent initialization successful")
            
            # Check collection info
            info = agent.get_collection_info()
            if "error" not in info:
                print(f"✓ Document collection ready: {info['total_documents']} documents")
            else:
                print(f"⚠️  Collection issue: {info['error']}")
            
            return True
            
        except Exception as e:
            print(f"❌ RAG agent initialization failed: {e}")
            print("   Make sure Qdrant is running: docker run -p 6333:6333 qdrant/qdrant")
            return False
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def main():
    """Run all examples"""
    print("Campaign Generator Examples")
    print("==========================")
    
    # Check prerequisites first
    if not check_prerequisites():
        print("\n❌ Prerequisites not met. Please fix the issues above before running examples.")
        return
    
    print("\nRunning examples...\n")
    
    try:
        # Run examples in sequence
        generator = example_basic_generation()
        
        if generator:
            example_campaign_refinement(generator)
        
        example_campaign_suggestions()
        example_save_and_load()
        example_programmatic_usage()
        
        print("\n" + "="*50)
        print("✓ All examples completed successfully!")
        print("\nTo run the interactive campaign generator:")
        print("  python campaign_generator.py")
        
    except Exception as e:
        print(f"❌ Error running examples: {e}")

if __name__ == "__main__":
    main()