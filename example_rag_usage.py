"""
Example usage of the RAG Agent for D&D document queries with Claude
"""
import os
from haystack_pipeline_agent import HaystackPipelineAgent

def example_queries():
    """Run example queries against the RAG agent"""
    
    # Example questions to demonstrate the system
    sample_questions = [
        "What are the different character classes in D&D?",
        "How do I create a character sheet?",
        "What are the rules for combat?",
        "Tell me about spellcasting mechanics",
        "What races are available for players?",
        "How does initiative work in combat?",
        "What are the different types of dice used?",
        "Explain the leveling system"
    ]
    
    print("=== RAG Agent Example Usage ===")
    print("This script demonstrates how to use the RAG agent programmatically")
    print()
    
    try:
        # Initialize Haystack agent
        print("Initializing Haystack agent...")
        agent = HaystackPipelineAgent(collection_name="dnd_documents", verbose=True)
        
        # Get collection info (basic status)
        print(f"✓ Connected to Haystack pipeline agent")
        print()
        
        # Run sample queries
        for i, question in enumerate(sample_questions, 1):
            print(f"[{i}/{len(sample_questions)}] Question: {question}")
            
            response = agent.send_message_and_wait("haystack_pipeline", "query", {
                "query": question,
                "context": "example usage"
            }, timeout=30.0)
            
            if not response or not response.get("success"):
                print(f"   ✗ Error: Failed to get response from Haystack agent")
                continue
            
            result = response.get("result", {})
            answer = result.get("answer", "No answer available")
            sources = result.get("source_documents", [])
            
            print(f"   ✓ Found response from Haystack pipeline")
            
            # Show top source if available
            if sources:
                print(f"   📄 Sources found: {len(sources)} documents")
            
            # Show answer (truncated for display)
            if len(answer) > 150:
                answer = answer[:150] + "..."
            print(f"   💬 Answer: {answer}")
            print()
        
        print("Example queries completed!")
        
    except Exception as e:
        print(f"Error running examples: {e}")


def custom_query_example():
    """Example of custom query functionality"""
    print("=== Custom Query Example ===")
    
    try:
        agent = HaystackPipelineAgent(collection_name="dnd_documents")
        
        # Custom question
        question = "What equipment does a level 1 fighter start with?"
        
        print(f"Question: {question}")
        response = agent.send_message_and_wait("haystack_pipeline", "query", {
            "query": question,
            "context": "custom query example"
        }, timeout=30.0)
        
        if not response or not response.get("success"):
            print("Error: Failed to get response from Haystack agent")
            return
        
        print("\nDetailed Results:")
        print("-" * 40)
        
        # Show full answer
        result = response.get("result", {})
        answer = result.get("answer", "No answer available")
        print(f"Answer: {answer}")
        print()
        
        # Show sources if available
        sources = result.get("source_documents", [])
        if sources:
            print("Retrieved Sources:")
            for i, source in enumerate(sources, 1):
                source_info = source if isinstance(source, str) else str(source)
                print(f"  {i}. {source_info}")
            print()
            
    except Exception as e:
        print(f"Error: {e}")


def batch_query_example():
    """Example of processing multiple queries at once"""
    print("=== Batch Query Example ===")
    
    questions = [
        "How much damage does a longsword do?",
        "What is the armor class of leather armor?",
        "How many hit points does a wizard have at level 1?"
    ]
    
    try:
        agent = HaystackPipelineAgent(collection_name="dnd_documents")
        
        results = []
        for question in questions:
            response = agent.send_message_and_wait("haystack_pipeline", "query", {
                "query": question,
                "context": "batch query"
            }, timeout=30.0)
            results.append((question, response))
        
        # Display results
        for i, (question, response) in enumerate(results, 1):
            print(f"{i}. {question}")
            if not response or not response.get("success"):
                print(f"   Error: Failed to get response from Haystack agent")
            else:
                result = response.get("result", {})
                answer = result.get("answer", "No answer available")
                if len(answer) > 100:
                    answer = answer[:100] + "..."
                print(f"   Answer: {answer}")
            print()
            
    except Exception as e:
        print(f"Error: {e}")


def main():
    """Main function to run examples"""
    print("Haystack Pipeline Agent Examples")
    print("================================")
    print("Choose an example to run:")
    print("1. Sample Questions")
    print("2. Custom Query")
    print("3. Batch Queries")
    print("4. All Examples")
    print()
    
    choice = input("Enter choice (1-4): ").strip()
    print()
    
    if choice == "1":
        example_queries()
    elif choice == "2":
        custom_query_example()
    elif choice == "3":
        batch_query_example()
    elif choice == "4":
        example_queries()
        print("\n" + "="*50 + "\n")
        custom_query_example()
        print("\n" + "="*50 + "\n")
        batch_query_example()
    else:
        print("Invalid choice. Running sample questions...")
        example_queries()


if __name__ == "__main__":
    main()