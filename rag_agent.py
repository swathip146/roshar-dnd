"""
RAG (Retrieval-Augmented Generation) Agent
Answers user queries using documents stored in Qdrant vector database with Claude
Integrates with the agent framework for coordinated AI assistance
"""
import os
import time
from typing import List, Dict, Any, Optional

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

# Import agent framework
try:
    from agent_framework import BaseAgent, MessageType, AgentMessage
    AGENT_FRAMEWORK_AVAILABLE = True
except ImportError:
    AGENT_FRAMEWORK_AVAILABLE = False
    # Create dummy base class for backward compatibility
    class BaseAgent:
        def __init__(self, agent_id, agent_type):
            pass
        def process_tick(self):
            pass

# Configuration constants
DEFAULT_TOP_K = 20  # Number of documents to retrieve by default
DEFAULT_RANKER_TOP_K = 5  # Number of documents to keep after ranking
DEFAULT_EMBEDDING_DIM = 384  # sentence-transformers/all-MiniLM-L6-v2 dimension
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
# Claude-specific imports based on Genie.py
try:
    from hwtgenielib import component
    from hwtgenielib.components.generators.chat import AppleGenAIChatGenerator
    from hwtgenielib.components.builders import ChatPromptBuilder
    from hwtgenielib.dataclasses import ChatMessage
    CLAUDE_AVAILABLE = True
except ImportError:
    CLAUDE_AVAILABLE = False
    # Fallback decorator
    def component(cls):
        return cls
from qdrant_client import QdrantClient
import warnings
warnings.filterwarnings("ignore")


# Helper component to convert string prompts to chat messages
@component
class StringToChatMessages:
    """Converts a string prompt into a list of ChatMessage objects."""
    
    @component.output_types(messages=list[ChatMessage])
    def run(self, prompt: str):
        """Run the component."""
        if CLAUDE_AVAILABLE:
            return {"messages": [ChatMessage.from_user(prompt)]}
        else:
            return {"messages": [{"role": "user", "content": prompt}]}


class RAGAgent:
    """RAG Agent for answering queries using Qdrant vector database with Claude"""
    
    def __init__(self, collection_name: str = "dnd_documents",
                 host: str = "localhost",
                 port: int = 6333,
                 top_k: int = DEFAULT_TOP_K,
                 verbose: bool = False):
        """
        Initialize RAG Agent
        
        Args:
            collection_name: Qdrant collection name
            host: Qdrant host
            port: Qdrant port
            top_k: Number of documents to retrieve
            verbose: Enable verbose output
        """
        self.collection_name = collection_name
        self.host = host
        self.port = port
        self.top_k = top_k
        self.verbose = verbose
        self.document_store = None
        self.pipeline = None
        self.has_llm = CLAUDE_AVAILABLE
        
        # Initialize components
        self._setup_document_store()
        self._setup_pipeline()
    
    def _setup_document_store(self):
        """Setup Qdrant document store connection"""
        try:
            # Test connection
            client = QdrantClient(host=self.host, port=self.port)
            collections = client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if self.collection_name not in collection_names:
                raise ValueError(f"Collection '{self.collection_name}' not found. Available collections: {collection_names}")
            
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
                print(f"✗ Failed to connect to Qdrant: {e}")
                print("Make sure Qdrant is running: docker run -p 6333:6333 qdrant/qdrant")
            raise

    def _create_embedder(self) -> SentenceTransformersTextEmbedder:
        """Create and configure text embedder"""
        embedder = SentenceTransformersTextEmbedder(
            model=EMBEDDING_MODEL
        )
        embedder.warm_up()
        return embedder

    def _create_retriever(self) -> QdrantEmbeddingRetriever:
        """Create document retriever"""
        return QdrantEmbeddingRetriever(
            document_store=self.document_store,
            top_k=self.top_k
        )

    def _create_ranker(self) -> SentenceTransformersSimilarityRanker:
        """Create document ranker for improving retrieval quality"""
        ranker = SentenceTransformersSimilarityRanker(
            model="cross-encoder/ms-marco-MiniLM-L-6-v2",
            top_k=DEFAULT_RANKER_TOP_K
        )
        ranker.warm_up()
        return ranker

    def _create_prompt_builder(self) -> PromptBuilder:
        """Create prompt builder with RAG template"""
        rag_prompt = """You are a helpful D&D (Dungeons & Dragons) assistant. Answer the user's question based on the provided context documents.

Your audience is an expert, so be highly specific, direct, and concise. If there are ambiguous terms or acronyms, first define them.
When the retrieved information is directly irrelevant, do not guess. You should output "<REJECT> No relevant information" and summarize the retrieved documents to explain the irrelevance.

Retrieved information (with relevance scores):
{% for document in documents %}
  Source: {{ document.meta.source_file }} (Tags: {{ document.meta.document_tag }})
  Content: {{ document.content }}
  Score: {{ document.score }}
  ---
{% endfor %}

User Query: {{ query }}

Instructions:
- Answer based primarily on the provided context
- If the context doesn't contain enough information, say so clearly
- Cite which document(s) you're referencing when possible
- Be specific and detailed in your responses
- If asked about rules, provide exact text when available

Your Answer:"""
        return PromptBuilder(template=rag_prompt)

    def _create_llm_components(self) -> tuple:
        """Create LLM-related components"""
        if not CLAUDE_AVAILABLE:
            return None, None, None
        
        string_to_chat = StringToChatMessages()
        answer_builder = AnswerBuilder()
        chat_generator = AppleGenAIChatGenerator(
            model="aws:anthropic.claude-sonnet-4-20250514-v1:0"
        )
        return string_to_chat, answer_builder, chat_generator
    
    def _setup_pipeline(self):
        """Setup RAG pipeline with retriever, ranker, and optional Claude generator"""
        # Create core components
        text_embedder = self._create_embedder()
        retriever = self._create_retriever()
        ranker = self._create_ranker()
        
        # Create pipeline
        self.pipeline = Pipeline()
        self.pipeline.add_component("text_embedder", text_embedder)
        self.pipeline.add_component("retriever", retriever)
        self.pipeline.add_component("ranker", ranker)
        
        # Connect retrieval and ranking
        self.pipeline.connect("text_embedder.embedding", "retriever.query_embedding")
        self.pipeline.connect("retriever.documents", "ranker.documents")
        
        # Add LLM components if available
        if self.has_llm:
            prompt_builder = self._create_prompt_builder()
            string_to_chat, answer_builder, chat_generator = self._create_llm_components()
            
            self.pipeline.add_component("prompt_builder", prompt_builder)
            self.pipeline.add_component("string_to_chat", string_to_chat)
            self.pipeline.add_component("answer_builder", answer_builder)
            self.pipeline.add_component("chat_generator", chat_generator)
            
            # Connect LLM pipeline with ranker
            self.pipeline.connect("ranker.documents", "prompt_builder.documents")
            self.pipeline.connect("prompt_builder.prompt", "string_to_chat.prompt")
            self.pipeline.connect("string_to_chat.messages", "chat_generator.messages")
            self.pipeline.connect("ranker.documents", "answer_builder.documents")
            self.pipeline.connect("chat_generator.replies", "answer_builder.replies")
            
            if self.verbose:
                print("✓ RAG pipeline initialized with Claude Sonnet 4 and document ranker")
        else:
            if self.verbose:
                print("⚠️  Claude components not available. Only document retrieval and ranking will be available.")
                print("✓ Retrieval + ranking pipeline initialized (no LLM)")
    
    def query(self, question: str) -> Dict[str, Any]:
        """
        Answer a question using RAG
        
        Args:
            question: User's question
            
        Returns:
            Dictionary with answer and sources
        """
        if not self.pipeline:
            return {"error": "Pipeline not initialized"}
        
        try:
            if self.has_llm:
                # Full RAG pipeline with Claude and ranker
                result = self.pipeline.run({
                    "text_embedder": {"text": question},
                    "ranker": {"query": question},
                    "prompt_builder": {"query": question},
                    "answer_builder": {"query": question}
                })
                
                # Extract response and documents
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
                # Retrieval with ranking only
                result = self.pipeline.run({
                    "text_embedder": {"text": question},
                    "ranker": {"query": question}
                })
                documents = result.get("ranker", {}).get("documents", [])
                
                return {
                    "answer": self._create_manual_response(documents, question),
                    "sources": self._format_sources(documents)
                }
                
        except Exception as e:
            return {"error": f"Query failed: {e}"}
    
    def _format_sources(self, documents: List[Document]) -> List[Dict[str, Any]]:
        """Format source documents for display"""
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
    
    def _create_manual_response(self, documents: List[Document], question: str) -> str:
        """Create a manual response when no LLM is available"""
        if not documents:
            return f"No relevant documents found for: '{question}'"
        
        response = f"Found {len(documents)} relevant documents:\n\n"
        
        for i, doc in enumerate(documents, 1):
            response += f"{i}. {doc.meta.get('source_file', 'Unknown')}\n"
            response += f"   {doc.content[:200]}{'...' if len(doc.content) > 200 else ''}\n\n"
        
        return response
    
    def save_pipeline_diagram(self, filename: str = "rag_pipeline.png") -> bool:
        """
        Save pipeline visualization as PNG file
        
        Args:
            filename: Output filename for the PNG
            
        Returns:
            Boolean indicating success
        """
        if not self.pipeline:
            if self.verbose:
                print("❌ No pipeline to visualize")
            return False
        
        try:
            # Try to draw the pipeline
            self.pipeline.draw(path=filename)
            if self.verbose:
                print(f"✓ Pipeline diagram saved as: {filename}")
            return True
        except Exception as e:
            if self.verbose:
                print(f"❌ Failed to save pipeline diagram: {e}")
                print("💡 Install graphviz: pip install pygraphviz")
            return False

    def get_collection_info(self) -> Dict[str, Any]:
        """Get information about the current collection"""
        try:
            client = QdrantClient(host=self.host, port=self.port)
            collection_info = client.get_collection(self.collection_name)
            
            return {
                "collection_name": self.collection_name,
                "total_documents": collection_info.points_count,
                "vector_size": collection_info.config.params.vectors.size,
                "distance_metric": collection_info.config.params.vectors.distance.name
            }
        except Exception as e:
            return {"error": f"Failed to get collection info: {e}"}


def _print_welcome():
    """Print welcome message"""
    print("=== D&D RAG Agent ===")
    print("Ask questions about your D&D documents!")
    print("\nCommands: 'info', 'help', 'quit'")

def _get_collection_name() -> str:
    """Get collection name from user"""
    collection_name = input("\nEnter Qdrant collection name (default: dnd_documents): ").strip()
    return collection_name if collection_name else "dnd_documents"

def _initialize_agent(collection_name: str) -> RAGAgent:
    """Initialize RAG agent with verbose output"""
    print("Initializing agent...")
    agent = RAGAgent(collection_name=collection_name, verbose=True)
    
    # Show collection info
    info = agent.get_collection_info()
    if "error" not in info:
        print(f"✓ Collection: {info['collection_name']} ({info['total_documents']} documents)")
    
    mode = "Claude Sonnet 4" if CLAUDE_AVAILABLE else "Retrieval-only"
    print(f"✓ Mode: {mode}")
    print()
    
    return agent

def _handle_info_command(agent: RAGAgent):
    """Handle info command"""
    info = agent.get_collection_info()
    if "error" in info:
        print(f"Error: {info['error']}")
    else:
        print(f"Collection: {info['collection_name']}")
        print(f"Documents: {info['total_documents']}")
        print(f"Vector size: {info['vector_size']}")
        print(f"Distance: {info['distance_metric']}")
        print(f"LLM: {'Claude Sonnet 4' if CLAUDE_AVAILABLE else 'None'}")

def _handle_help_command():
    """Handle help command"""
    print("Commands:")
    print("  info     - Show collection information")
    print("  diagram  - Save pipeline diagram as PNG")
    print("  help     - Show this help")
    print("  quit     - Exit the program")
    print("\nExample questions:")
    print("  - What are the different character classes?")
    print("  - How does combat work in D&D?")
    print("  - What equipment does a fighter start with?")

def _display_result(result: Dict[str, Any]):
    """Display query result"""
    if "error" in result:
        print(f"❌ Error: {result['error']}")
        return
    
    print(f"\n{'🤖 ANSWER:' if CLAUDE_AVAILABLE else '📋 INFORMATION:'}")
    print("=" * 50)
    print(result["answer"])
    
    sources = result["sources"]
    if sources:
        # Ask user if they want to see sources
        show_sources = input(f"\nShow {len(sources)} source documents? (y/N): ").strip().lower()
        if show_sources in ['y', 'yes']:
            print(f"\n📚 SOURCES ({len(sources)}):")
            print("=" * 50)
            for source in sources:
                print(f"{source['rank']}. {source['source']}")
                print(f"   {source['preview']}")
    print()

def interactive_chat():
    """Interactive chat interface for the RAG agent"""
    _print_welcome()
    collection_name = _get_collection_name()
    
    try:
        agent = _initialize_agent(collection_name)
        
        while True:
            question = input("Question: ").strip()
            
            if question.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break
            
            if question.lower() == 'info':
                _handle_info_command(agent)
                print()
                continue
            
            if question.lower() == 'diagram':
                success = agent.save_pipeline_diagram()
                if success:
                    print("✓ Pipeline diagram saved as rag_pipeline.png")
                else:
                    print("❌ Failed to save pipeline diagram")
                print()
                continue
            
            if question.lower() == 'help':
                _handle_help_command()
                print()
                continue
            
            if not question:
                print("Please enter a question.")
                continue
            
            result = agent.query(question)
            _display_result(result)
    
    except Exception as e:
        print(f"❌ Failed to initialize RAG agent: {e}")


def main():
    """Main function"""
    try:
        interactive_chat()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()