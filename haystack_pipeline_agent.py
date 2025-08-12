"""
Haystack Pipeline Agent for DM Assistant
Integrates Haystack RAG pipelines with the agent framework for enhanced DM operations
"""
import os
from typing import Dict, List, Any, Optional
from pathlib import Path

# Set tokenizers parallelism to avoid fork warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"
# Suppress transformers progress bars
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

from haystack import Document, Pipeline
from haystack_integrations.components.retrievers.qdrant import QdrantEmbeddingRetriever
from haystack.components.embedders import SentenceTransformersTextEmbedder
from haystack.components.builders import PromptBuilder, AnswerBuilder
from haystack.components.rankers import SentenceTransformersSimilarityRanker
from haystack_integrations.document_stores.qdrant import QdrantDocumentStore

from agent_framework import BaseAgent, MessageType, AgentMessage

# Configuration constants
DEFAULT_TOP_K = 20
DEFAULT_RANKER_TOP_K = 5
DEFAULT_EMBEDDING_DIM = 384
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Claude-specific imports
try:
    from hwtgenielib import component
    from hwtgenielib.components.generators.chat import AppleGenAIChatGenerator
    from hwtgenielib.dataclasses import ChatMessage
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False
    def component(cls):
        return cls

from qdrant_client import QdrantClient
import warnings
warnings.filterwarnings("ignore")


@component
class StringToChatMessages:
    """Converts a string prompt into a list of ChatMessage objects."""
    
    @component.output_types(messages=list[ChatMessage] if CLAUDE_AVAILABLE else list)
    def run(self, prompt: str):
        """Run the component."""
        if CLAUDE_AVAILABLE:
            return {"messages": [ChatMessage.from_user(prompt)]}
        else:
            return {"messages": [{"role": "user", "content": prompt}]}


class HaystackPipelineAgent(BaseAgent):
    """Haystack Pipeline Agent that provides RAG services to other agents"""
    
    def __init__(self,
                 collection_name: str = "dnd_documents",
                 host: str = "localhost",
                 port: int = 6333,
                 top_k: int = DEFAULT_TOP_K,
                 verbose: bool = False):
        super().__init__("haystack_pipeline", "HaystackPipeline")
        
        self.collection_name = collection_name
        self.host = host
        self.port = port
        self.top_k = top_k
        self.verbose = verbose
        self.has_llm = CLAUDE_AVAILABLE
        
        self.document_store = None
        self.pipeline = None
        
        # Pipeline variants for different use cases
        self.scenario_pipeline = None
        self.npc_pipeline = None
        self.rules_pipeline = None
        
        # Initialize components
        self._setup_document_store()
        self._setup_pipelines()
        
        # CRITICAL FIX: Setup message handlers
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup message handlers for Haystack pipeline agent"""
        self.register_handler("query_rag", self._handle_query_rag)
        self.register_handler("query_scenario", self._handle_query_scenario)
        self.register_handler("query_npc", self._handle_query_npc)
        self.register_handler("query_rules", self._handle_query_rules)
        self.register_handler("get_pipeline_status", self._handle_get_pipeline_status)
        self.register_handler("get_collection_info", self._handle_get_collection_info)
    
    def _setup_document_store(self):
        """Setup Qdrant document store connection"""
        try:
            # Test connection
            client = QdrantClient(host=self.host, port=self.port)
            collections = client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if self.collection_name not in collection_names:
                if self.verbose:
                    print(f"⚠️ Collection '{self.collection_name}' not found. Available: {collection_names}")
                # Don't raise error, just disable document store
                self.document_store = None
                return
            
            # Initialize document store
            self.document_store = QdrantDocumentStore(
                host=self.host,
                port=self.port,
                index=self.collection_name,
                embedding_dim=DEFAULT_EMBEDDING_DIM
            )
            
            if self.verbose:
                print(f"✓ Connected to Qdrant collection: {self.collection_name}")
                
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Qdrant not available, running in offline mode: {e}")
            # Don't raise error, just disable document store for graceful degradation
            self.document_store = None
    
    def _create_embedder(self) -> SentenceTransformersTextEmbedder:
        """Create and configure text embedder"""
        embedder = SentenceTransformersTextEmbedder(model=EMBEDDING_MODEL)
        embedder.warm_up()
        return embedder
    
    def _create_retriever(self) -> Optional[QdrantEmbeddingRetriever]:
        """Create document retriever"""
        if self.document_store is None:
            return None
        return QdrantEmbeddingRetriever(
            document_store=self.document_store,
            top_k=self.top_k
        )
    
    def _create_ranker(self) -> SentenceTransformersSimilarityRanker:
        """Create document ranker"""
        ranker = SentenceTransformersSimilarityRanker(
            model="cross-encoder/ms-marco-MiniLM-L-6-v2",
            top_k=DEFAULT_RANKER_TOP_K
        )
        ranker.warm_up()
        return ranker
    
    def _create_general_prompt_builder(self) -> PromptBuilder:
        """Create general RAG prompt builder"""
        template = """You are a helpful D&D assistant. Answer based on the provided context.

Retrieved information:
{% for document in documents %}
  Source: {{ document.meta.source_file }}
  Content: {{ document.content }}
  Score: {{ document.score }}
  ---
{% endfor %}

Query: {{ query }}

Answer:"""
        return PromptBuilder(template=template)
    
    def _create_scenario_prompt_builder(self) -> PromptBuilder:
        """Create scenario-specific prompt builder"""
        template = """You are an expert Dungeon Master creating engaging scenarios.

{% if documents %}
Context from D&D materials:
{% for document in documents %}
  {{ document.content }}
  ---
{% endfor %}
{% endif %}

Current situation: {{ query }}
Campaign info: {{ campaign_context }}
Game state: {{ game_state }}

{% if documents %}
Generate a compelling scenario based on the provided context (2-3 sentences) and 3-4 numbered player options.
{% else %}
You are continuing an ongoing D&D story. Based on the current situation, campaign info, and game state provided, create a compelling narrative continuation. Use your creativity to advance the story in an engaging way that makes sense for a D&D adventure. Provide 2-3 sentences describing what happens next, followed by 3-4 numbered options for the players to choose from.
{% endif %}"""
        return PromptBuilder(template=template)
    
    def _create_npc_prompt_builder(self) -> PromptBuilder:
        """Create NPC-specific prompt builder"""
        template = """You are an NPC behavior specialist. Use D&D context to determine NPC actions.

D&D Context:
{% for document in documents %}
  {{ document.content }}
  ---
{% endfor %}

NPC situation: {{ query }}
Game context: {{ game_state }}

Provide a brief action plan for this NPC (JSON format with 'action' and 'reasoning'):"""
        return PromptBuilder(template=template)
    
    def _create_rules_prompt_builder(self) -> PromptBuilder:
        """Create rules-specific prompt builder"""
        template = """You are a D&D rules expert. Provide accurate rule explanations.

Relevant rules:
{% for document in documents %}
  Source: {{ document.meta.source_file }}
  Rule: {{ document.content }}
  ---
{% endfor %}

Question: {{ query }}

Provide a clear, accurate answer with rule citations:"""
        return PromptBuilder(template=template)
    
    def _setup_pipelines(self):
        """Setup various Haystack pipelines for different use cases"""
        # Core components
        text_embedder = self._create_embedder()
        retriever = self._create_retriever()
        
        # Handle case where document store is not available
        if retriever is None:
            if self.verbose:
                print("⚠️ Document store not available, pipelines disabled")
            self.pipeline = None
            self.scenario_pipeline = None
            self.npc_pipeline = None
            self.rules_pipeline = None
            return
        
        ranker = self._create_ranker()
        
        # General RAG pipeline
        self.pipeline = Pipeline()
        self.pipeline.add_component("text_embedder", text_embedder)
        self.pipeline.add_component("retriever", retriever)
        self.pipeline.add_component("ranker", ranker)
        
        self.pipeline.connect("text_embedder.embedding", "retriever.query_embedding")
        self.pipeline.connect("retriever.documents", "ranker.documents")
        
        if self.has_llm:
            # Add LLM components
            prompt_builder = self._create_general_prompt_builder()
            string_to_chat = StringToChatMessages()
            answer_builder = AnswerBuilder()
            chat_generator = AppleGenAIChatGenerator(
                model="aws:anthropic.claude-sonnet-4-20250514-v1:0"
            )
            
            self.pipeline.add_component("prompt_builder", prompt_builder)
            self.pipeline.add_component("string_to_chat", string_to_chat)
            self.pipeline.add_component("answer_builder", answer_builder)
            self.pipeline.add_component("chat_generator", chat_generator)
            
            self.pipeline.connect("ranker.documents", "prompt_builder.documents")
            self.pipeline.connect("prompt_builder.prompt", "string_to_chat.prompt")
            self.pipeline.connect("string_to_chat.messages", "chat_generator.messages")
            self.pipeline.connect("ranker.documents", "answer_builder.documents")
            self.pipeline.connect("chat_generator.replies", "answer_builder.replies")
        
        # Create specialized pipelines
        self._setup_specialized_pipelines()
        
        if self.verbose:
            mode = "Claude Sonnet 4" if self.has_llm else "Retrieval-only"
            print(f"✓ Haystack pipelines initialized in {mode} mode")
    
    def _setup_specialized_pipelines(self):
        """Setup specialized pipelines for different agent types"""
        if not self.has_llm:
            return
            
        # Creative scenario generation pipeline (no document retrieval)
        self.scenario_pipeline = Pipeline()
        self.scenario_pipeline.add_component("prompt_builder", self._create_creative_scenario_prompt_builder())
        self.scenario_pipeline.add_component("string_to_chat", StringToChatMessages())
        self.scenario_pipeline.add_component("chat_generator", AppleGenAIChatGenerator(
            model="aws:anthropic.claude-sonnet-4-20250514-v1:0"
        ))
        
        # Connect creative scenario pipeline (no retrieval)
        self.scenario_pipeline.connect("prompt_builder.prompt", "string_to_chat.prompt")
        self.scenario_pipeline.connect("string_to_chat.messages", "chat_generator.messages")
        
        # NPC pipeline
        self.npc_pipeline = Pipeline()
        self.npc_pipeline.add_component("text_embedder", self._create_embedder())
        self.npc_pipeline.add_component("retriever", self._create_retriever())
        self.npc_pipeline.add_component("ranker", self._create_ranker())
        self.npc_pipeline.add_component("prompt_builder", self._create_npc_prompt_builder())
        self.npc_pipeline.add_component("string_to_chat", StringToChatMessages())
        self.npc_pipeline.add_component("chat_generator", AppleGenAIChatGenerator(
            model="aws:anthropic.claude-sonnet-4-20250514-v1:0"
        ))
        
        # Connect NPC pipeline
        self.npc_pipeline.connect("text_embedder.embedding", "retriever.query_embedding")
        self.npc_pipeline.connect("retriever.documents", "ranker.documents")
        self.npc_pipeline.connect("ranker.documents", "prompt_builder.documents")
        self.npc_pipeline.connect("prompt_builder.prompt", "string_to_chat.prompt")
        self.npc_pipeline.connect("string_to_chat.messages", "chat_generator.messages")
        
        # Rules pipeline
        self.rules_pipeline = Pipeline()
        self.rules_pipeline.add_component("text_embedder", self._create_embedder())
        self.rules_pipeline.add_component("retriever", self._create_retriever())
        self.rules_pipeline.add_component("ranker", self._create_ranker())
        self.rules_pipeline.add_component("prompt_builder", self._create_rules_prompt_builder())
        self.rules_pipeline.add_component("string_to_chat", StringToChatMessages())
        self.rules_pipeline.add_component("chat_generator", AppleGenAIChatGenerator(
            model="aws:anthropic.claude-sonnet-4-20250514-v1:0"
        ))
        
        # Connect rules pipeline
        self.rules_pipeline.connect("text_embedder.embedding", "retriever.query_embedding")
        self.rules_pipeline.connect("retriever.documents", "ranker.documents")
        self.rules_pipeline.connect("ranker.documents", "prompt_builder.documents")
        self.rules_pipeline.connect("prompt_builder.prompt", "string_to_chat.prompt")
        self.rules_pipeline.connect("string_to_chat.messages", "chat_generator.messages")
    
    def _create_creative_scenario_prompt_builder(self) -> PromptBuilder:
        """Create creative scenario prompt builder for story generation"""
        template = """You are an expert Dungeon Master continuing an ongoing D&D adventure.

Current situation: {{ query }}
Campaign info: {{ campaign_context }}
Game state: {{ game_state }}

Based on the player's choice and current situation, create an engaging continuation of the story. Use your creativity and D&D knowledge to:

1. Describe what happens as a result of the player's choice (2-3 sentences)
2. Advance the story in an interesting direction
3. Present 3-4 numbered options for what the players can do next

Make it engaging, appropriate for D&D, and keep the story moving forward naturally."""
        return PromptBuilder(template=template)
    
    def _handle_query_rag(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle general RAG query"""
        query = message.data.get("query")
        if not query:
            return {"success": False, "error": "No query provided"}
        
        if self.pipeline is None:
            return {
                "success": True,
                "result": {
                    "answer": f"RAG pipeline not available (Qdrant not connected). Query: {query}",
                    "sources": []
                }
            }
        
        try:
            result = self._run_pipeline(self.pipeline, query)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_query_scenario(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle scenario-specific query"""
        query = message.data.get("query")
        campaign_context = message.data.get("campaign_context", "")
        game_state = message.data.get("game_state", "")
        
        if not query:
            return {"success": False, "error": "No query provided"}
        
        try:
            if self.scenario_pipeline:
                result = self._run_scenario_pipeline(query, campaign_context, game_state)
            else:
                result = self._run_pipeline(self.pipeline, query)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_query_npc(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle NPC-specific query"""
        query = message.data.get("query")
        game_state = message.data.get("game_state", "")
        
        if not query:
            return {"success": False, "error": "No query provided"}
        
        try:
            if self.npc_pipeline:
                result = self._run_npc_pipeline(query, game_state)
            else:
                result = self._run_pipeline(self.pipeline, query)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_query_rules(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle rules-specific query"""
        query = message.data.get("query")
        if not query:
            return {"success": False, "error": "No query provided"}
        
        try:
            if self.rules_pipeline:
                result = self._run_pipeline(self.rules_pipeline, query)
            else:
                result = self._run_pipeline(self.pipeline, query)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_get_pipeline_status(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle pipeline status request"""
        return {
            "has_llm": self.has_llm,
            "collection": self.collection_name,
            "pipelines": {
                "general": self.pipeline is not None,
                "scenario": self.scenario_pipeline is not None,
                "npc": self.npc_pipeline is not None,
                "rules": self.rules_pipeline is not None
            }
        }
    
    def _handle_get_collection_info(self, message: AgentMessage) -> Dict[str, Any]:
        """Handle collection info request"""
        try:
            client = QdrantClient(host=self.host, port=self.port)
            collection_info = client.get_collection(self.collection_name)
            
            return {
                "success": True,
                "collection_name": self.collection_name,
                "total_documents": collection_info.points_count,
                "vector_size": collection_info.config.params.vectors.size,
                "distance_metric": collection_info.config.params.vectors.distance.name
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _run_pipeline(self, pipeline: Pipeline, query: str) -> Dict[str, Any]:
        """Run a pipeline with the given query"""
        if pipeline is None:
            return {
                "answer": f"Pipeline not available (Qdrant not connected). Query was: {query}",
                "sources": []
            }
        
        if self.has_llm:
            result = pipeline.run({
                "text_embedder": {"text": query},
                "ranker": {"query": query},
                "prompt_builder": {"query": query},
                "answer_builder": {"query": query}
            })
            
            if "answer_builder" in result and "answers" in result["answer_builder"]:
                answer_obj = result["answer_builder"]["answers"][0]
                answer = answer_obj.data
                documents = answer_obj.documents if hasattr(answer_obj, 'documents') else []
            else:
                answer = "No response generated"
                documents = []
            
            return {
                "answer": answer,
                "sources": self._format_sources(documents)
            }
        else:
            result = pipeline.run({
                "text_embedder": {"text": query},
                "ranker": {"query": query}
            })
            documents = result.get("ranker", {}).get("documents", [])
            
            return {
                "answer": self._create_manual_response(documents, query),
                "sources": self._format_sources(documents)
            }
    
    def _run_scenario_pipeline(self, query: str, campaign_context: str, game_state: str) -> Dict[str, Any]:
        """Run creative scenario-specific pipeline"""
        result = self.scenario_pipeline.run({
            "prompt_builder": {
                "query": query,
                "campaign_context": campaign_context,
                "game_state": game_state
            }
        })
        
        if "chat_generator" in result and "replies" in result["chat_generator"]:
            answer = result["chat_generator"]["replies"][0].text
        else:
            answer = "No scenario generated"
        
        return {"answer": answer}
    
    def _run_npc_pipeline(self, query: str, game_state: str) -> Dict[str, Any]:
        """Run NPC-specific pipeline"""
        result = self.npc_pipeline.run({
            "text_embedder": {"text": query},
            "ranker": {"query": query},
            "prompt_builder": {
                "query": query,
                "game_state": game_state
            }
        })
        
        if "chat_generator" in result and "replies" in result["chat_generator"]:
            answer = result["chat_generator"]["replies"][0].text
        else:
            answer = "No NPC action generated"
        
        return {"answer": answer}
    
    def _format_sources(self, documents: List[Document]) -> List[Dict[str, Any]]:
        """Format source documents"""
        sources = []
        for i, doc in enumerate(documents, 1):
            sources.append({
                "rank": i,
                "source": doc.meta.get("source_file", "Unknown"),
                "tags": doc.meta.get("document_tag", "Unknown"),
                "preview": doc.content[:150] + "..." if len(doc.content) > 150 else doc.content,
                "score": getattr(doc, 'score', 'N/A')
            })
        return sources
    
    def _create_manual_response(self, documents: List[Document], query: str) -> str:
        """Create manual response when no LLM available"""
        if not documents:
            return f"No relevant documents found for: '{query}'"
        
        response = f"Found {len(documents)} relevant documents:\n\n"
        for i, doc in enumerate(documents, 1):
            response += f"{i}. {doc.meta.get('source_file', 'Unknown')}\n"
            response += f"   {doc.content[:200]}{'...' if len(doc.content) > 200 else ''}\n\n"
        
        return response
    
    def process_tick(self):
        """Process Haystack pipeline tick - mostly reactive, no regular processing needed"""
        pass


def get_embeddings_model():
    """Get the embeddings model - for test mocking compatibility"""
    return EMBEDDING_MODEL


def get_llm_generator():
    """Get the LLM generator - for test mocking compatibility"""
    if CLAUDE_AVAILABLE:
        from hwtgenielib.components.generators.chat import AppleGenAIChatGenerator
        return AppleGenAIChatGenerator(model="aws:anthropic.claude-sonnet-4-20250514-v1:0")
    else:
        return None