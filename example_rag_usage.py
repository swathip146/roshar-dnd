"""
Example usage of the RAG Agent for D&D document queries with Claude
"""
import os
from rag_agent import RAGAgent

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
        # Initialize RAG agent
        print("Initializing RAG agent...")
        agent = RAGAgent(collection_name="dnd_documents", top_k=3)
        
        # Get collection info
        info = agent.get_collection_info()
        if "error" not in info:
            print(f"✓ Connected to collection: {info['collection_name']}")
            print(f"✓ Total documents: {info['total_documents']}")
        print()
        
        # Run sample queries
        for i, question in enumerate(sample_questions, 1):
            print(f"[{i}/{len(sample_questions)}] Question: {question}")
            
            result = agent.query(question)
            
            if "error" in result:
                print(f"   ✗ Error: {result['error']}")
                continue
            
            print(f"   ✓ Found {len(result['retrieved_documents'])} relevant documents")
            
            # Show top source
            if result['source_documents']:
                top_source = result['source_documents'][0]
                print(f"   📄 Top source: {top_source['source_file']} ({top_source['document_tag']})")
            
            # Show answer (truncated for display)
            answer = result.get('answer', result.get('manual_answer', 'No answer'))
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
        agent = RAGAgent(collection_name="dnd_documents")
        
        # Custom question
        question = "What equipment does a level 1 fighter start with?"
        
        print(f"Question: {question}")
        result = agent.query(question)
        
        if "error" in result:
            print(f"Error: {result['error']}")
            return
        
        print("\nDetailed Results:")
        print("-" * 40)
        
        # Show full answer
        answer = result.get('answer', result.get('manual_answer', 'No answer'))
        print(f"Answer: {answer}")
        print()
        
        # Show all sources
        print("Retrieved Sources:")
        for source in result['source_documents']:
            print(f"  {source['rank']}. {source['source_file']}")
            print(f"     Tags: {source['document_tag']}")
            print(f"     Preview: {source['content_preview']}")
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
        agent = RAGAgent(collection_name="dnd_documents")
        
        results = []
        for question in questions:
            result = agent.query(question)
            results.append((question, result))
        
        # Display results
        for i, (question, result) in enumerate(results, 1):
            print(f"{i}. {question}")
            if "error" in result:
                print(f"   Error: {result['error']}")
            else:
                answer = result.get('answer', result.get('manual_answer', 'No answer'))
                if len(answer) > 100:
                    answer = answer[:100] + "..."
                print(f"   Answer: {answer}")
            print()
            
    except Exception as e:
        print(f"Error: {e}")


def main():
    """Main function to run examples"""
    print("RAG Agent Examples")
    print("==================")
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