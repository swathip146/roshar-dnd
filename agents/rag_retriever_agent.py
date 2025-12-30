"""
RAG Retriever Agent - Semantic document retrieval
Integrates with existing document store for context enhancement using Haystack Agent framework
"""

# DEBUG CONTROL - Set to True to enable detailed debugging
DEBUG_RAG_AGENT = True
DEBUG_TOOLS = True
DEBUG_RETRIEVAL = True

import time
from typing import Dict, Any, List, Optional, Callable
from haystack.components.agents import Agent
from haystack.components.builders import AnswerBuilder
from haystack.dataclasses import ChatMessage, Document
from haystack.tools import Tool
from config.llm_config import get_global_config_manager
from storage.simple_document_store import SimpleDocumentStore
from components.shared_contract import new_dto
from haystack import component

from config.logging_config import get_logger

# Initialize logger
logger = get_logger(__name__)


DEFAULT_TOP_K = 5

def debug_rag_print(category: str, message: str, data: Any = None):
    """Centralized debug printing for RAG agent"""
    if DEBUG_RAG_AGENT:
        timestamp = time.strftime('%H:%M:%S')
        logger.debug(f"🐛 RAG [{timestamp}] {category}: {message}")
        if data is not None and DEBUG_RETRIEVAL:
            if isinstance(data, dict) and len(str(data)) > 300:
                logger.debug(f"    📊 Data keys: {list(data.keys()) if isinstance(data, dict) else type(data)}")
            else:
                logger.debug(f"    📊 Data: {data}")


def create_retrieve_documents_tool(document_store: Optional[SimpleDocumentStore]) -> Tool:
    """Create a retrieve_documents tool with document store bound via closure."""
    
    def retrieve_documents(query: str, top_k: int = DEFAULT_TOP_K, context_type: str = "general",
                          filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Retrieve relevant documents from the knowledge base using Qdrant with contextual filters.
        
        Args:
            query: Search query for document retrieval
            top_k: Number of documents to retrieve
            context_type: Type of context needed (lore, rules, monsters, spells, general, etc.)
            filters: Contextual filters for enhanced retrieval (optional)
            
        Returns:
            Retrieved documents with content and metadata including filter information
        """
        debug_rag_print("TOOL", "🔍 retrieve_documents called", {"query": query, "top_k": top_k, "context_type": context_type, "filters": filters})
       
        # Non-None store guard - explicit validation
        if document_store is None:
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
        if document_store:
            debug_rag_print("TOOL", f"✅ Document store available: {document_store.collection_name}")
            try:
                # Start with base query and enhance with context and filters
                enhanced_query = query
                filter_metadata = {}
                
                if filters:
                    debug_rag_print("TOOL", f"📊 Applying contextual filters", filters)
                    # Log filter usage
                    logger.info(f"📊 RAG Retrieval: Applying contextual filters: {filters}")
                    
                    # Handle both list and dict filter formats
                    categories = []
                    if isinstance(filters, list):
                        # Direct list of categories from orchestrator
                        categories = filters
                    
                    if categories:
                        if isinstance(categories, list):
                            enhanced_query = f"{enhanced_query} category:{' OR '.join(categories)}"
                        else:
                            enhanced_query = f"{enhanced_query} category:{categories}"
                    
                    filter_metadata = {
                        "categories_used": categories,
                        "original_query": query,
                        "enhanced_query": enhanced_query
                    }
                    debug_rag_print("TOOL", f"🔍 Enhanced query with filters", {"original": query, "enhanced": enhanced_query, "categories": categories})
                    

                # Use SimpleDocumentStore's search_with_metadata method for full results
                debug_rag_print("TOOL", f"🔎 Searching document store", {"enhanced_query": enhanced_query, "top_k": top_k})
                search_results = document_store.search_with_metadata(enhanced_query, top_k)
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
                
                context_summary = f"Retrieved {len(documents)} documents from {document_store.collection_name}"
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
    
    return Tool(
        name="retrieve_documents",
        description="Retrieve relevant documents from the knowledge base using Qdrant with contextual filters",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for document retrieval"
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of documents to retrieve",
                    "default": DEFAULT_TOP_K
                },
                "context_type": {
                    "type": "string",
                    "description": "Type of context needed (lore, rules, monsters, spells, general, etc.)",
                    "default": "general"
                },
                "filters": {
                    "type": "object",
                    "description": "Contextual filters for enhanced retrieval (optional)"
                }
            },
            "required": ["query"]
        },
        function=retrieve_documents,
        inputs_from_state={
            "context_type": "context_type",
            "filters": "filters"
        },
        outputs_to_state={"retrieval_result": {}}
    )


# Haystack Component to replace format_rag_response_tool
@component
class RAGFormatterComponent:
    """
    Haystack component to format RAG response data without LLM coordination overhead.
    Replaces format_rag_response_tool for better pipeline performance.
    """
    
    @component.output_types(formatted_response=dict)
    def run(self, messages: List[ChatMessage]) -> dict:
        """
        Format RAG response data from agent messages into standardized format.
        
        Args:
            messages: List of ChatMessage objects from RAG agent
            
        Returns:
            Dictionary with formatted response
        """
        # Extract response text from the last message
        response_text = ""
        if messages:
            last_message = messages[-1]
            if hasattr(last_message, 'content'):
                response_text = last_message.content
            elif hasattr(last_message, 'text'):
                response_text = last_message.text
            else:
                response_text = str(last_message)
        
        # Calculate confidence based on response length and quality
        confidence = min(0.8, len(response_text) / 200.0) if response_text else 0.0
        
        return {"formatted_response": {
            "response": response_text,
            "confidence": max(0.0, min(1.0, confidence))
        }}


def create_rag_retriever_agent_simplified(chat_generator: Optional[Any] = None,
                                          document_store: Optional[Any] = None) -> Agent:
    """
    Create a simplified RAG agent that only uses document retrieval (no formatting tool).
    Designed for pipeline integration with RAGFormatterComponent.
    
    Args:
        chat_generator: Optional chat generator (uses LLM config if None)
        document_store: Existing document store instance to use
        
    Returns:
        Simplified Haystack Agent focused on document interpretation only
    """
    
    # Use LLM config manager to get appropriate generator
    if chat_generator is None:
        config_manager = get_global_config_manager()
        generator = config_manager.create_generator("rag_retriever")
    else:
        generator = chat_generator
    
    if document_store is not None:
        logger.info(f"📚 Simplified RAG Agent: Using existing document store for collection '{document_store.collection_name}'")
    else:
        logger.warning("Simplified RAG Agent: No document store provided - will use fallback responses")
    
    # Create retrieve_documents tool with document store bound via closure
    retrieve_documents_tool = create_retrieve_documents_tool(document_store)
    
    simplified_system_prompt = """
You are a RAG (Retrieval-Augmented Generation) assistant for a D&D game system.

Your role is to:
- Retrieve relevant documents from the knowledge base based on provided queries and context type
- Interpret and synthesize the retrieved information intelligently
- Generate concise, accurate responses based solely on retrieved information instead of your inner knowledge.

WORKFLOW:
1. Analyze the query to determine the most appropriate context_type and any helpful filters for optimal retrieval
2. Use retrieve_documents tool to get relevant documents with your chosen context_type and filters from the document_store
3. Analyze and synthesize the retrieved information
4. Generate concise, accurate responses based on the retrieved information instead of your inner knowledge.

INTELLIGENT PARAMETER SELECTION:
- Choose the most appropriate context_type based on what the query is asking for
- Add relevant filters when they would help narrow down results (e.g., ["spells"] for magic queries, ["combat"] for battle questions)
- If unsure, use the provided context_type and filters if available or use "general" context_type and no filters

RESPONSE FORMAT:
Your final response should be a clear, concise answer based on the retrieved documents.
Do NOT include any prefixes, explanations, or meta-commentary.
Just provide the factual information requested.

CONTEXT TYPES:
- "lore": Game world history, legends, character backgrounds, background information, past events
- "rules": D&D mechanics, spells, abilities, game rules, abilities, combat mechanics, skill checks
- "monsters": Creature descriptions, behaviors, combat stats
- "locations": Place descriptions, geography, notable features
- "campaigns": Requests about encounters, quests, storylines
- "general": Catch-all for other content

RETRIEVAL GUIDELINES:
- Use specific, targeted queries for better results
- Generate responses when sufficient context is available (high confidence scores)
- Return formatted context when response generation is not possible or confidence is low
- Apply contextual filters when provided to enhance retrieval accuracy

RESPONSE GUIDELINES:
- KEEP RESPONSES CONCISE: Limit responses to 150 words maximum
- EXTRACT KEY INFORMATION: Focus only on the most relevant facts that directly answer the query
- BE SPECIFIC: Include exact numbers, dice rolls, damage values, or specific rules when available
- PRIORITIZE RELEVANCE: If documents contain mixed content, extract only the parts that directly relate to the query
- NO VERBOSE EXPLANATIONS: Avoid lengthy introductions or background context unless specifically requested
- STRUCTURE CLEARLY: Use bullet points or short paragraphs for easy reading
- USE DIRECT QUOTES: When appropriate, use exact text from source documents for accuracy
- DO NOT GUESS: When the retrieved information is directly irrelevant, you should output "No response generated" to the format_rag_response tool.
- NO META-TEXT: Don't include phrases like "Based on the documents" or "According to the search results"

Example good response: "Dragons in this world have three age categories: wyrmling (CR 2-5), young adult (CR 8-12), and ancient (CR 15+). They possess breath weapons corresponding to their color type and can cast spells."

Example bad response: "Based on the retrieved documents, I found that dragons in this world have..."

Generate your direct factual response after retrieving and analyzing the documents.
"""

    agent = Agent(
        chat_generator=generator,
        tools=[retrieve_documents_tool],  # Only document retrieval - no formatting tool
        system_prompt=simplified_system_prompt,
        exit_conditions=[],  # No specific exit conditions - just process and respond
        max_agent_steps=2,  # Retrieve documents, then respond
        raise_on_tool_invocation_failure=False,
        state_schema={
            "context_type": {"type": str},
            "filters": {"type": list},
            "retrieval_result": {"type": dict}
        }
    )
    
    return agent


def create_rag_agent_for_orchestrator() -> Agent:
    """Create RAG retriever agent configured for orchestrator integration"""
    return create_rag_retriever_agent_simplified()


def connect_document_store(document_store: SimpleDocumentStore) -> Agent:
    """
    Create a RAG agent connected to an actual document store.
    
    Args:
        document_store: Document store instance (e.g., SimpleDocumentStore)
    
    Returns:
        RAG retriever agent configured with the document store
    """
    return create_rag_retriever_agent_simplified(document_store=document_store)


# Example usage and testing
if __name__ == "__main__":
    # Create the agent
    agent = create_rag_retriever_agent_simplified()
    
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
        logger.info(f"\n=== RAG Agent Test {i+1} ===")
        
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
                logger.info(f"{msg.role}: {msg.text}")
            
            # Check for tool results
            for key, value in response.items():
                if key not in ["messages"] and value:
                    logger.info(f"{key}: {value}")
                    
        except Exception as e:
            logger.error(f"RAG Agent test {i+1} failed: {e}")