"""
RAG Retriever Agent - Semantic document retrieval
Integrates with existing document store for context enhancement using Haystack Agent framework
"""

# DEBUG CONTROL - Set to True to enable detailed debugging
DEBUG_RAG_AGENT = True
DEBUG_TOOLS = True
DEBUG_RETRIEVAL = True

import time
from typing import Dict, Any, List, Optional
from haystack.components.agents import Agent
from haystack.dataclasses import ChatMessage
from haystack.tools import tool
from config.llm_config import get_global_config_manager

def debug_rag_print(category: str, message: str, data: Any = None):
    """Centralized debug printing for RAG agent"""
    if DEBUG_RAG_AGENT:
        timestamp = time.strftime('%H:%M:%S')
        print(f"🐛 RAG [{timestamp}] {category}: {message}")
        if data is not None and DEBUG_RETRIEVAL:
            if isinstance(data, dict) and len(str(data)) > 300:
                print(f"    📊 Data keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
            else:
                print(f"    📊 Data: {data}")

# Global document store reference for tools
_global_document_store = None

@tool
def retrieve_documents(query: str, top_k: int = 3, context_type: str = "general",
                      filters: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Retrieve relevant documents from the knowledge base using Qdrant with contextual filters.
    
    Args:
        query: Search query for document retrieval
        top_k: Number of documents to retrieve
        context_type: Type of context needed (lore, rules, monsters, spells, etc.)
        filters: Contextual filters for enhanced retrieval (optional)
        
    Returns:
        Retrieved documents with content and metadata including filter information
    """
    debug_rag_print("TOOL", "🔍 retrieve_documents called", {"query": query, "top_k": top_k, "context_type": context_type, "filters": filters})
    
    global _global_document_store
    
    # Non-None store guard - explicit validation
    if _global_document_store is None:
        debug_rag_print("TOOL", "❌ Document store is None")
        return {
            "query": query,
            "documents": [],
            "context_summary": f"Document store is None - cannot retrieve documents for query: {query}",
            "context_type": context_type,
            "source": "no_document_store",
            "error": "Document store not initialized"
        }
    
    # Additional validation for query parameter
    if not query or not isinstance(query, str):
        return {
            "query": query or "",
            "documents": [],
            "context_summary": f"Invalid query provided: {query}",
            "context_type": context_type,
            "source": "invalid_query",
            "error": "Query must be a non-empty string"
        }
    
    # Use actual document store if available
    if _global_document_store:
        debug_rag_print("TOOL", f"✅ Document store available: {_global_document_store.collection_name}")
        try:
            # Apply contextual filters if provided
            enhanced_query = query
            filter_metadata = {}
            
            if filters:
                debug_rag_print("TOOL", f"📊 Applying contextual filters", filters)
                # Log filter usage
                print(f"📊 RAG Retrieval: Applying contextual filters: {filters}")
                
                # Enhance query based on filters
                if "content_category" in filters:
                    categories = filters["content_category"]
                    if isinstance(categories, list):
                        enhanced_query = f"{query} category:{' OR '.join(categories)}"
                    else:
                        enhanced_query = f"{query} category:{categories}"
                
                if "location_context" in filters:
                    location = filters["location_context"]
                    enhanced_query = f"{enhanced_query} location:{location}"
                
                if "situation" in filters:
                    situation = filters["situation"]
                    enhanced_query = f"{enhanced_query} situation:{situation}"
                
                filter_metadata = {
                    "filters_applied": filters,
                    "original_query": query,
                    "enhanced_query": enhanced_query
                }
                debug_rag_print("TOOL", f"🔍 Enhanced query", {"original": query, "enhanced": enhanced_query})
            
            # Use SimpleDocumentStore's search_with_metadata method for full results
            debug_rag_print("TOOL", f"🔎 Searching document store", {"enhanced_query": enhanced_query, "top_k": top_k})
            search_results = _global_document_store.search_with_metadata(enhanced_query, top_k)
            debug_rag_print("TOOL", f"📋 Search results", {"count": len(search_results), "results_type": type(search_results)})
            
            # Convert to expected format with filter information
            documents = []
            for result in search_results:
                doc_metadata = result.get("metadata", {}).copy()
                doc_metadata.update(filter_metadata)
                
                documents.append({
                    "content": result["content"],
                    "metadata": doc_metadata,
                    "score": result.get("score", 0.0)
                })
            
            context_summary = f"Retrieved {len(documents)} documents from {_global_document_store.collection_name}"
            if documents:
                context_summary += f" (avg score: {sum(d['score'] for d in documents)/len(documents):.3f})"
            
            if filters:
                context_summary += f" with {len(filters)} contextual filters"
                
            return {
                "query": enhanced_query,
                "original_query": query,
                "documents": documents,
                "context_summary": context_summary,
                "context_type": context_type,
                "filters": filters or {},
                "source": "qdrant_document_store_filtered"
            }
            
        except Exception as e:
            debug_rag_print("TOOL", f"💥 Document store search exception: {e}")
            # Fallback if document store fails
            return {
                "query": query,
                "original_query": query,
                "documents": [],
                "context_summary": f"Document retrieval failed: {e}",
                "context_type": context_type,
                "filters": filters or {},
                "source": "error_fallback"
            }
    # This should not be reached due to earlier guard, but keeping for safety
    return {
        "query": query,
        "original_query": query,
        "documents": [],
        "context_summary": f"Document store validation failed - using fallback for: {query}",
        "context_type": context_type,
        "filters": filters or {},
        "source": "validation_fallback",
        "error": "Document store failed validation checks"
    }


@tool(
    outputs_to_state={"formatted_context": {"source": "."}}
)
def format_context_for_scenario(documents: List[Dict[str, Any]] = None, query: str = "") -> Dict[str, str]:
    """
    Format retrieved documents into context suitable for scenario generation.
    
    Args:
        documents: List of retrieved documents (optional, defaults to empty list)
        query: Original query for context (optional, defaults to empty string)
        
    Returns:
        Formatted context string and metadata
    """
    debug_rag_print("TOOL", "📝 format_context_for_scenario called", {"documents_count": len(documents) if documents else 0, "query": query})
    
    # Handle None or invalid documents with default parameters
    if not documents or not isinstance(documents, list):
        debug_rag_print("TOOL", "⚠️ No valid documents provided")
        return {
            "context": f"No relevant documents found for query: '{query}'" if query else "No documents available",
            "source_count": 0,
            "relevance": "none",
            "query": query
        }
    
    context_parts = []
    valid_doc_count = 0
    
    for i, doc in enumerate(documents):
        # Handle None documents or non-dict documents
        if not doc or not isinstance(doc, dict):
            continue
            
        content = doc.get("content", "")
        
        # Handle None or non-string content
        if not content or not isinstance(content, str):
            continue
            
        # Truncate long content
        if len(content) > 200:
            content = content[:200] + "..."
            
        context_parts.append(f"Source {valid_doc_count + 1}: {content}")
        valid_doc_count += 1
    
    result = {
        "context": "\n".join(context_parts),
        "source_count": valid_doc_count,
        "relevance": "high" if valid_doc_count > 0 else "none"
    }
    debug_rag_print("TOOL", f"✅ Context formatting complete", {"source_count": valid_doc_count, "context_length": len(result["context"])})
    return result


def create_rag_retriever_agent(chat_generator: Optional[Any] = None,
                               collection_name=None,
                               document_store=None) -> Agent:
    """
    Create a Haystack Agent for RAG document retrieval and context enhancement.
    
    Args:
        chat_generator: Optional chat generator (uses LLM config if None)
        collection_name: Optional collection name for document store creation (legacy)
        document_store: Existing document store instance to use (preferred)
        
    Returns:
        Configured Haystack Agent for RAG retrieval
    """
    
    # Use LLM config manager to get appropriate generator
    if chat_generator is None:
        config_manager = get_global_config_manager()
        generator = config_manager.create_generator("rag_retriever")
    else:
        generator = chat_generator
    
    # Set global document store reference
    global _global_document_store
    
    if document_store is not None:
        # Use existing document store instance (preferred approach)
        _global_document_store = document_store
        print(f"📚 RAG Agent: Using existing document store for collection '{document_store.collection_name}'")
    elif collection_name is not None:
        # Legacy fallback: create new document store (not recommended due to resource conflicts)
        print(f"⚠️ RAG Agent: Creating new document store for '{collection_name}' - may cause resource conflicts")
        try:
            from storage.simple_document_store import SimpleDocumentStore
            _global_document_store = SimpleDocumentStore(collection_name=collection_name)
            _global_document_store.load_basic_content()
            print(f"📚 RAG Agent: Document store created for collection '{collection_name}'")
        except Exception as e:
            print(f"⚠️ RAG Agent: Failed to create document store for collection '{collection_name}': {e}")
            _global_document_store = None
    else:
        _global_document_store = None
        print("⚠️ RAG Agent: No document store provided - will use fallback responses")
    
    system_prompt = """
You are a RAG (Retrieval-Augmented Generation) assistant for a D&D game system.

Your role is to:
1. Retrieve relevant documents from the knowledge base based on provided queries and context
2. Format retrieved content for use in scenario generation

WORKFLOW:
1. Use retrieve_documents with appropriate query and context type (provided by the main interface agent)
2. IMPORTANT: Use format_context_for_scenario with the documents and query from step 1

CONTEXT TYPES:
- "lore": Game world history, legends, background information
- "rules": D&D mechanics, spells, abilities, rule clarifications
- "monsters": Creature descriptions, behaviors, combat stats
- "locations": Place descriptions, geography, notable features
- "general": Catch-all for other content

GUIDELINES:
- Use specific, targeted queries for better results
- Summarize and format content to be useful for scenario generation
- Limit context length to avoid overwhelming the scenario generator
- Apply contextual filters when provided to enhance retrieval accuracy

TOOL PARAMETER RULES:
- When using format_context_for_scenario, you MUST pass the "documents" list and "query" string from retrieve_documents
- Example: If retrieve_documents returns {"documents": [...], "query": "Alethi"}, then call format_context_for_scenario with documents=[...] and query="Alethi"

NOTE: RAG assessment is now handled by the main interface agent. This agent focuses purely on document retrieval and formatting.

CRITICAL: When calling format_context_for_scenario, you MUST:
1. First call retrieve_documents to get results
2. Extract 'documents' list and 'query' string from the retrieve_documents response
3. Pass these as separate parameters to format_context_for_scenario(documents=docs_list, query=query_string)

Always use the tools provided to complete your tasks and pass parameters correctly between tool calls.
"""

    agent = Agent(
        chat_generator=generator,
        tools=[retrieve_documents, format_context_for_scenario],
        system_prompt=system_prompt,
        exit_conditions=["format_context_for_scenario"],
        max_agent_steps=2,
        raise_on_tool_invocation_failure=False,
        state_schema={
            "formatted_context": {"type": dict}
        }
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
    
    # Test document retrieval and formatting
    test_cases = [
        {
            "query": "history of ancient dragon kings",
            "context_type": "lore"
        },
        {
            "query": "fireball spell mechanics",
            "context_type": "rules"
        },
        {
            "query": "tavern atmosphere and NPCs",
            "context_type": "locations"
        }
    ]
    
    for i, test_case in enumerate(test_cases):
        print(f"\n=== RAG Agent Test {i+1} ===")
        
        user_message = f"""
        Query: {test_case['query']}
        Context Type: {test_case['context_type']}
        
        Retrieve relevant documents for this query and format them for scenario generation.
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