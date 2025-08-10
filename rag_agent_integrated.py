"""
RAG (Retrieval-Augmented Generation) Agent - Agent Framework Integration
Provides both standalone and agent-framework integrated RAG capabilities
"""
import os
import time
from typing import List, Dict, Any, Optional

# Set tokenizers parallelism to avoid fork warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"
# Suppress transformers progress bars
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

from agent_framework import BaseAgent, MessageType, AgentMessage
from rag_agent import RAGAgent as LegacyRAGAgent

# Claude-specific imports
try:
    from hwtgenielib.components.generators.chat import AppleGenAIChatGenerator
    from hwtgenielib.dataclasses import ChatMessage
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False

import warnings
warnings.filterwarnings("ignore")


class RAGAgentFramework(BaseAgent):
    """RAG Agent that integrates with the agent framework for coordinated AI assistance"""
    
    def __init__(self, 
                 collection_name: str = "dnd_documents",
                 host: str = "localhost",
                 port: int = 6333,
                 top_k: int = 20,
                 verbose: bool = False,
                 orchestrator=None):
        """
        Initialize RAG Agent with agent framework integration
        
        Args:
            collection_name: Qdrant collection name
            host: Qdrant host
            port: Qdrant port
            top_k: Number of documents to retrieve
            verbose: Enable verbose output
            orchestrator: Optional orchestrator for proxy to HaystackPipelineAgent
        """
        super().__init__("rag_agent_framework", "RAGAgent")
        
        self.collection_name = collection_name
        self.host = host
        self.port = port
        self.top_k = top_k
        self.verbose = verbose
        self.orchestrator = orchestrator
        self.has_llm = CLAUDE_AVAILABLE
        
        # Check if we should proxy to HaystackPipelineAgent
        self.use_proxy = orchestrator is not None
        
        if not self.use_proxy:
            # Initialize our own RAG agent
            try:
                self.rag_agent = LegacyRAGAgent(
                    collection_name=collection_name,
                    host=host,
                    port=port,
                    top_k=top_k,
                    verbose=verbose
                )
            except Exception as e:
                if verbose:
                    print(f"⚠️ Failed to initialize legacy RAG agent: {e}")
                self.rag_agent = None
    
    def _setup_handlers(self):
        """Setup message handlers for RAG agent"""
        self.register_handler("query", self._handle_query)
        self.register_handler("query_scenario", self._handle_query_scenario)
        self.register_handler("query_npc", self._handle_query_npc)
        self.register_handler("query_rules", self._handle_query_rules)
        self.register_handler("get_collection_info", self._handle_get_collection_info)
        self.register_handler("get_status", self._handle_get_status)
    
    def _handle_query(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle general query request"""
        query = message.data.get("query")
        if not query:
            return {"success": False, "error": "No query provided"}
        
        try:
            result = self.query(query)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_query_scenario(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle scenario-specific query request"""
        query = message.data.get("query")
        campaign_context = message.data.get("campaign_context", "")
        game_state = message.data.get("game_state", "")
        
        if not query:
            return {"success": False, "error": "No query provided"}
        
        try:
            if self.use_proxy and self.orchestrator:
                result = self._proxy_query_scenario(query, campaign_context, game_state)
            else:
                # Use general query for scenarios if no proxy
                result = self.query(f"Scenario context: {campaign_context}\nGame state: {game_state}\nQuery: {query}")
            
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_query_npc(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle NPC-specific query request"""
        query = message.data.get("query")
        game_state = message.data.get("game_state", "")
        
        if not query:
            return {"success": False, "error": "No query provided"}
        
        try:
            if self.use_proxy and self.orchestrator:
                result = self._proxy_query_npc(query, game_state)
            else:
                # Use general query for NPCs if no proxy
                result = self.query(f"NPC context: {game_state}\nQuery: {query}")
            
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_query_rules(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle rules-specific query request"""
        query = message.data.get("query")
        if not query:
            return {"success": False, "error": "No query provided"}
        
        try:
            if self.use_proxy and self.orchestrator:
                result = self._proxy_query_rules(query)
            else:
                # Use general query for rules if no proxy
                result = self.query(f"D&D Rules Query: {query}")
            
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_get_collection_info(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle collection info request"""
        try:
            info = self.get_collection_info()
            if "error" in info:
                return {"success": False, "error": info["error"]}
            return {"success": True, "info": info}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_get_status(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle status request"""
        return {
            "success": True,
            "status": {
                "use_proxy": self.use_proxy,
                "has_llm": self.has_llm,
                "collection": self.collection_name,
                "rag_agent_available": self.rag_agent is not None,
                "orchestrator_available": self.orchestrator is not None
            }
        }
    
    def query(self, question: str) -> Dict[str, Any]:
        """
        Answer a question using RAG - with agent framework integration
        
        Args:
            question: User's question
            
        Returns:
            Dictionary with answer and sources
        """
        if self.use_proxy and self.orchestrator:
            return self._proxy_query(question)
        elif self.rag_agent:
            return self.rag_agent.query(question)
        else:
            return {"error": "No RAG agent available"}
    
    def _proxy_query(self, question: str) -> Dict[str, Any]:
        """Proxy query to HaystackPipelineAgent through orchestrator"""
        try:
            message_id = self.orchestrator.send_message_to_agent("haystack_pipeline", "query_rag", {
                "query": question
            })
            
            return self._wait_for_response(message_id)
            
        except Exception as e:
            return {"error": f"Proxy query failed: {e}"}
    
    def _proxy_query_scenario(self, query: str, campaign_context: str, game_state: str) -> Dict[str, Any]:
        """Proxy scenario query to HaystackPipelineAgent"""
        try:
            message_id = self.orchestrator.send_message_to_agent("haystack_pipeline", "query_scenario", {
                "query": query,
                "campaign_context": campaign_context,
                "game_state": game_state
            })
            
            return self._wait_for_response(message_id)
            
        except Exception as e:
            return {"error": f"Proxy scenario query failed: {e}"}
    
    def _proxy_query_npc(self, query: str, game_state: str) -> Dict[str, Any]:
        """Proxy NPC query to HaystackPipelineAgent"""
        try:
            message_id = self.orchestrator.send_message_to_agent("haystack_pipeline", "query_npc", {
                "query": query,
                "game_state": game_state
            })
            
            return self._wait_for_response(message_id)
            
        except Exception as e:
            return {"error": f"Proxy NPC query failed: {e}"}
    
    def _proxy_query_rules(self, query: str) -> Dict[str, Any]:
        """Proxy rules query to HaystackPipelineAgent"""
        try:
            message_id = self.orchestrator.send_message_to_agent("haystack_pipeline", "query_rules", {
                "query": query
            })
            
            return self._wait_for_response(message_id)
            
        except Exception as e:
            return {"error": f"Proxy rules query failed: {e}"}
    
    def _wait_for_response(self, message_id: str, timeout: float = 5.0) -> Dict[str, Any]:
        """Wait for response from orchestrator"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            history = self.orchestrator.message_bus.get_message_history(limit=50)
            for msg in reversed(history):
                if (msg.get("response_to") == message_id and 
                    msg.get("message_type") == "response"):
                    response_data = msg.get("data", {})
                    if response_data.get("success"):
                        return response_data.get("result", {"error": "No result in response"})
                    else:
                        return {"error": response_data.get("error", "Unknown error from pipeline")}
            time.sleep(0.1)
        
        return {"error": "Timeout waiting for pipeline response"}
    
    def get_collection_info(self) -> Dict[str, Any]:
        """Get information about the current collection"""
        if self.use_proxy and self.orchestrator:
            try:
                message_id = self.orchestrator.send_message_to_agent("haystack_pipeline", "get_collection_info", {})
                response = self._wait_for_response(message_id)
                return response
            except Exception as e:
                return {"error": f"Failed to get collection info via proxy: {e}"}
        elif self.rag_agent:
            return self.rag_agent.get_collection_info()
        else:
            return {"error": "No RAG agent available"}
    
    def process_tick(self):
        """Process RAG agent tick - mostly reactive, no regular processing needed"""
        pass


# Enhanced RAGAgent that can work as standalone or with orchestrator
class RAGAgent:
    """Enhanced RAG Agent that can work standalone or with agent framework"""
    
    def __init__(self, 
                 collection_name: str = "dnd_documents",
                 host: str = "localhost",
                 port: int = 6333,
                 top_k: int = 20,
                 verbose: bool = False,
                 orchestrator=None):
        """
        Initialize enhanced RAG Agent
        
        Args:
            collection_name: Qdrant collection name
            host: Qdrant host
            port: Qdrant port
            top_k: Number of documents to retrieve
            verbose: Enable verbose output
            orchestrator: Optional orchestrator for agent framework integration
        """
        self.collection_name = collection_name
        self.host = host
        self.port = port
        self.top_k = top_k
        self.verbose = verbose
        self.orchestrator = orchestrator
        self.has_llm = CLAUDE_AVAILABLE
        
        # Initialize based on availability
        if orchestrator:
            # Use agent framework integration
            self.agent_framework = RAGAgentFramework(
                collection_name=collection_name,
                host=host,
                port=port,
                top_k=top_k,
                verbose=verbose,
                orchestrator=orchestrator
            )
            self.legacy_agent = None
        else:
            # Use legacy standalone agent
            try:
                self.legacy_agent = LegacyRAGAgent(
                    collection_name=collection_name,
                    host=host,
                    port=port,
                    top_k=top_k,
                    verbose=verbose
                )
                self.agent_framework = None
            except Exception as e:
                if verbose:
                    print(f"⚠️ Failed to initialize RAG agent: {e}")
                self.legacy_agent = None
                self.agent_framework = None
    
    def query(self, question: str) -> Dict[str, Any]:
        """Answer a question using RAG"""
        if self.agent_framework:
            return self.agent_framework.query(question)
        elif self.legacy_agent:
            return self.legacy_agent.query(question)
        else:
            return {"error": "No RAG agent available"}
    
    def get_collection_info(self) -> Dict[str, Any]:
        """Get information about the current collection"""
        if self.agent_framework:
            return self.agent_framework.get_collection_info()
        elif self.legacy_agent:
            return self.legacy_agent.get_collection_info()
        else:
            return {"error": "No RAG agent available"}
    
    def save_pipeline_diagram(self, filename: str = "rag_pipeline.png") -> bool:
        """Save pipeline visualization as PNG file"""
        if self.legacy_agent:
            return self.legacy_agent.save_pipeline_diagram(filename)
        else:
            if self.verbose:
                print("❌ Pipeline diagram only available in standalone mode")
            return False


# Factory function for creating the appropriate RAG agent
def create_rag_agent(collection_name: str = "dnd_documents",
                    host: str = "localhost",
                    port: int = 6333,
                    top_k: int = 20,
                    verbose: bool = False,
                    orchestrator=None) -> RAGAgent:
    """
    Factory function to create the appropriate RAG agent
    
    Args:
        collection_name: Qdrant collection name
        host: Qdrant host
        port: Qdrant port
        top_k: Number of documents to retrieve
        verbose: Enable verbose output
        orchestrator: Optional orchestrator for agent framework integration
        
    Returns:
        Configured RAG agent
    """
    return RAGAgent(
        collection_name=collection_name,
        host=host,
        port=port,
        top_k=top_k,
        verbose=verbose,
        orchestrator=orchestrator
    )