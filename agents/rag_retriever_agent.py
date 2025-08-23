"""
RAG Retriever Agent - Semantic document retrieval
Integrates with existing document store for context enhancement using Haystack Agent framework
"""

from typing import Dict, Any, List, Optional
from haystack.components.agents import Agent
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.dataclasses import ChatMessage
from haystack.tools import tool


@tool
def retrieve_documents(query: str, top_k: int = 3, context_type: str = "general") -> Dict[str, Any]:
    """
    Retrieve relevant documents from the knowledge base.
    
    Args:
        query: Search query for document retrieval
        top_k: Number of documents to retrieve
        context_type: Type of context needed (lore, rules, monsters, spells, etc.)
        
    Returns:
        Retrieved documents with content and metadata
    """
    # This will be connected to the actual document store in integration
    # For now, return placeholder structure
    return {
        "query": query,
        "documents": [],
        "context_summary": f"Retrieved {top_k} documents related to: {query}",
        "context_type": context_type
    }


@tool
def format_context_for_scenario(documents: List[Dict[str, Any]], query: str) -> Dict[str, str]:
    """
    Format retrieved documents into context suitable for scenario generation.
    
    Args:
        documents: List of retrieved documents
        query: Original query for context
        
    Returns:
        Formatted context string and metadata
    """
    if not documents:
        return {
            "context": "",
            "source_count": 0,
            "relevance": "none"
        }
    
    context_parts = []
    for i, doc in enumerate(documents):
        content = doc.get("content", "")
        # Truncate long content
        if len(content) > 200:
            content = content[:200] + "..."
        context_parts.append(f"Source {i+1}: {content}")
    
    return {
        "context": "\n".join(context_parts),
        "source_count": len(documents),
        "relevance": "high" if documents else "none"
    }


@tool
def assess_rag_need(action: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Determine if RAG retrieval is needed for the given action and context.
    
    Args:
        action: Player action
        context: Game context
        
    Returns:
        Assessment of whether RAG is needed and what type
    """
    action_lower = action.lower()
    
    # Define RAG triggers
    lore_triggers = ["history", "lore", "legend", "story", "past", "ancient"]
    rule_triggers = ["spell", "magic", "cast", "ability", "rule", "mechanic"]
    monster_triggers = ["creature", "monster", "beast", "dragon", "demon"]
    location_triggers = ["place", "location", "city", "dungeon", "area"]
    
    rag_needed = False
    rag_type = "general"
    confidence = 0.0
    
    if any(trigger in action_lower for trigger in lore_triggers):
        rag_needed = True
        rag_type = "lore"
        confidence = 0.8
    elif any(trigger in action_lower for trigger in rule_triggers):
        rag_needed = True
        rag_type = "rules"
        confidence = 0.9
    elif any(trigger in action_lower for trigger in monster_triggers):
        rag_needed = True
        rag_type = "monsters"
        confidence = 0.7
    elif any(trigger in action_lower for trigger in location_triggers):
        rag_needed = True
        rag_type = "locations"
        confidence = 0.6
    
    # Check context for additional hints
    if context.get("environment", {}).get("type") in ["library", "archive", "study"]:
        rag_needed = True
        rag_type = "lore"
        confidence = max(confidence, 0.7)
    
    return {
        "rag_needed": rag_needed,
        "rag_type": rag_type,
        "confidence": confidence,
        "reasoning": f"Action contains {rag_type} triggers" if rag_needed else "No RAG triggers found"
    }


def create_rag_retriever_agent(chat_generator: Optional[Any] = None) -> Agent:
    """
    Create a Haystack Agent for RAG document retrieval and context enhancement.
    
    Args:
        chat_generator: Optional chat generator (defaults to OpenAI)
        
    Returns:
        Configured Haystack Agent for RAG retrieval
    """
    
    if chat_generator is None:
        generator = OpenAIChatGenerator(model="gpt-4o-mini")
    else:
        generator = chat_generator
    
    system_prompt = """
You are a RAG (Retrieval-Augmented Generation) assistant for a D&D game system.

Your role is to:
1. Assess whether document retrieval is needed for player actions
2. Retrieve relevant documents from the knowledge base
3. Format retrieved content for use in scenario generation

WORKFLOW:
1. First, use assess_rag_need to determine if retrieval is necessary
2. If needed, use retrieve_documents with appropriate query and context type
3. Use format_context_for_scenario to prepare the retrieved content

CONTEXT TYPES:
- "lore": Game world history, legends, background information
- "rules": D&D mechanics, spells, abilities, rule clarifications
- "monsters": Creature descriptions, behaviors, combat stats
- "locations": Place descriptions, geography, notable features
- "general": Catch-all for other content

GUIDELINES:
- Only retrieve when action suggests need for external knowledge
- Use specific, targeted queries for better results
- Summarize and format content to be useful for scenario generation
- Limit context length to avoid overwhelming the scenario generator

Always use the tools provided to complete your tasks.
"""

    agent = Agent(
        chat_generator=generator,
        tools=[assess_rag_need, retrieve_documents, format_context_for_scenario],
        system_prompt=system_prompt,
        exit_conditions=["format_context_for_scenario", "assess_rag_need"],
        max_agent_steps=3,
        raise_on_tool_invocation_failure=False
    )
    
    return agent


def create_rag_agent_for_orchestrator() -> Agent:
    """Create RAG retriever agent configured for orchestrator integration"""
    return create_rag_retriever_agent()


# Example integration function for connecting to existing document store
def connect_document_store(agent: Agent, document_store):
    """
    Connect the RAG agent to an actual document store.
    This would replace the placeholder retrieve_documents function.
    
    Args:
        agent: RAG retriever agent
        document_store: Document store instance (e.g., SimpleDocumentStore)
    """
    # This would modify the retrieve_documents tool to use the actual document store
    # Implementation would depend on the specific document store interface
    pass


# Example usage and testing
if __name__ == "__main__":
    # Create the agent
    agent = create_rag_retriever_agent()
    
    # Test RAG assessment and retrieval
    test_cases = [
        {
            "action": "I want to research the history of the ancient dragon kings",
            "context": {"location": "Library", "environment": {"type": "archive"}}
        },
        {
            "action": "I cast fireball at the goblins", 
            "context": {"location": "Combat", "environment": {"type": "battlefield"}}
        },
        {
            "action": "I look around the room",
            "context": {"location": "Tavern", "environment": {"type": "social"}}
        }
    ]
    
    for i, test_case in enumerate(test_cases):
        print(f"\n=== RAG Agent Test {i+1} ===")
        
        user_message = f"""
        Player Action: {test_case['action']}
        Game Context: {test_case['context']}
        
        Assess if RAG retrieval is needed and retrieve relevant documents if necessary.
        """
        
        try:
            # Run the agent
            response = agent.run(messages=[ChatMessage.from_user(user_message)])
            
            print("Messages:")
            for msg in response["messages"]:
                print(f"{msg.role}: {msg.text}")
            
            # Check for tool results
            for key, value in response.items():
                if key not in ["messages"] and value:
                    print(f"{key}: {value}")
                    
        except Exception as e:
            print(f"❌ RAG Agent test {i+1} failed: {e}")