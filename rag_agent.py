"""
RAG (Retrieval-Augmented Generation) Agent
Answers user queries using documents stored in Qdrant vector database
"""
import os
from typing import List, Dict, Any, Optional
from haystack import Document, Pipeline
from haystack.components.retrievers import QdrantEmbeddingRetriever
from haystack.components.embedders import SentenceTransformersTextEmbedder
from haystack.components.generators import OpenAIGenerator
from haystack.components.builders import PromptBuilder
from haystack_integrations.document_stores.qdrant import QdrantDocumentStore
from qdrant_client import QdrantClient
import warnings
warnings.filterwarnings("ignore")


class RAGAgent:
    """RAG Agent for answering queries using Qdrant vector database"""
    
    def __init__(self, collection_name: str = "dnd_documents", 
                 host: str = "localhost", 
                 port: int = 6333,
                 top_k: int = 5):
        """
        Initialize RAG Agent
        
        Args:
            collection_name: Qdrant collection name
            host: Qdrant host
            port: Qdrant port
            top_k: Number of documents to retrieve
        """
        self.collection_name = collection_name
        self.host = host
        self.port = port
        self.top_k = top_k
        self.document_store = None
        self.pipeline = None
        
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
                embedding_dim=384  # sentence-transformers/all-MiniLM-L6-v2 dimension
            )
            
            print(f"✓ Connected to Qdrant collection: {self.collection_name}")
            
        except Exception as e:
            print(f"✗ Failed to connect to Qdrant: {e}")
            print("Make sure Qdrant is running: docker run -p 6333:6333 qdrant/qdrant")
            raise
    
    def _setup_pipeline(self):
        """Setup RAG pipeline with retriever and generator"""
        # Check for OpenAI API key
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            print("⚠️  OpenAI API key not found. Set OPENAI_API_KEY environment variable for LLM responses.")
            print("Only document retrieval will be available.")
            self._setup_retrieval_only_pipeline()
            return
        
        # RAG prompt template
        rag_prompt = """
You are a helpful D&D (Dungeons & Dragons) assistant. Answer the user's question based on the provided context documents.

Context Documents:
{% for doc in documents %}
---
Source: {{ doc.meta.source_file }} (Tags: {{ doc.meta.document_tag }})
Content: {{ doc.content }}
---
{% endfor %}

Question: {{ question }}

Instructions:
- Answer based primarily on the provided context
- If the context doesn't contain enough information, say so clearly
- Cite which document(s) you're referencing when possible
- Be specific and detailed in your responses
- If asked about rules, provide exact text when available

Answer:
"""
        
        # Initialize components
        text_embedder = SentenceTransformersTextEmbedder(
            model="sentence-transformers/all-MiniLM-L6-v2"
        )
        
        retriever = QdrantEmbeddingRetriever(
            document_store=self.document_store,
            top_k=self.top_k
        )
        
        prompt_builder = PromptBuilder(template=rag_prompt)
        
        generator = OpenAIGenerator(
            model="gpt-3.5-turbo",
            api_key=openai_api_key
        )
        
        # Warm up embedder
        text_embedder.warm_up()
        
        # Create pipeline
        self.pipeline = Pipeline()
        self.pipeline.add_component("text_embedder", text_embedder)
        self.pipeline.add_component("retriever", retriever)
        self.pipeline.add_component("prompt_builder", prompt_builder)
        self.pipeline.add_component("generator", generator)
        
        # Connect components
        self.pipeline.connect("text_embedder.embedding", "retriever.query_embedding")
        self.pipeline.connect("retriever.documents", "prompt_builder.documents")
        self.pipeline.connect("prompt_builder.prompt", "generator.prompt")
        
        print("✓ RAG pipeline initialized with OpenAI GPT-3.5-turbo")
    
    def _setup_retrieval_only_pipeline(self):
        """Setup pipeline for document retrieval only"""
        text_embedder = SentenceTransformersTextEmbedder(
            model="sentence-transformers/all-MiniLM-L6-v2"
        )
        
        retriever = QdrantEmbeddingRetriever(
            document_store=self.document_store,
            top_k=self.top_k
        )
        
        # Warm up embedder
        text_embedder.warm_up()
        
        # Create simple retrieval pipeline
        self.pipeline = Pipeline()
        self.pipeline.add_component("text_embedder", text_embedder)
        self.pipeline.add_component("retriever", retriever)
        
        self.pipeline.connect("text_embedder.embedding", "retriever.query_embedding")
        
        print("✓ Retrieval-only pipeline initialized (no LLM)")
    
    def query(self, question: str) -> Dict[str, Any]:
        """
        Answer a question using RAG
        
        Args:
            question: User's question
            
        Returns:
            Dictionary with answer and retrieved documents
        """
        if not self.pipeline:
            return {"error": "Pipeline not initialized"}
        
        try:
            # Run pipeline
            if "generator" in self.pipeline.graph.nodes:
                # Full RAG pipeline
                result = self.pipeline.run({
                    "text_embedder": {"text": question},
                    "prompt_builder": {"question": question}
                })
                
                return {
                    "question": question,
                    "answer": result["generator"]["replies"][0],
                    "retrieved_documents": result["retriever"]["documents"],
                    "source_documents": self._format_sources(result["retriever"]["documents"])
                }
            else:
                # Retrieval only
                result = self.pipeline.run({
                    "text_embedder": {"text": question}
                })
                
                documents = result["retriever"]["documents"]
                
                return {
                    "question": question,
                    "answer": "Document retrieval completed. OpenAI API key required for generated answers.",
                    "retrieved_documents": documents,
                    "source_documents": self._format_sources(documents),
                    "manual_answer": self._create_manual_response(documents, question)
                }
                
        except Exception as e:
            return {"error": f"Query failed: {e}"}
    
    def _format_sources(self, documents: List[Document]) -> List[Dict[str, Any]]:
        """Format source documents for display"""
        sources = []
        for i, doc in enumerate(documents, 1):
            sources.append({
                "rank": i,
                "source_file": doc.meta.get("source_file", "Unknown"),
                "document_tag": doc.meta.get("document_tag", "Unknown"),
                "folder_tags": doc.meta.get("folder_tags", []),
                "content_preview": doc.content[:200] + "..." if len(doc.content) > 200 else doc.content,
                "relevance_score": getattr(doc, 'score', 'N/A')
            })
        return sources
    
    def _create_manual_response(self, documents: List[Document], question: str) -> str:
        """Create a manual response when no LLM is available"""
        if not documents:
            return f"No relevant documents found for: '{question}'"
        
        response = f"Found {len(documents)} relevant documents for: '{question}'\n\n"
        
        for i, doc in enumerate(documents, 1):
            response += f"Document {i}:\n"
            response += f"Source: {doc.meta.get('source_file', 'Unknown')}\n"
            response += f"Tags: {doc.meta.get('document_tag', 'Unknown')}\n"
            response += f"Content: {doc.content[:300]}{'...' if len(doc.content) > 300 else ''}\n"
            response += "-" * 50 + "\n\n"
        
        return response
    
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


def interactive_chat():
    """Interactive chat interface for the RAG agent"""
    print("=== D&D RAG Agent ===")
    print("Ask questions about your D&D documents!")
    print("Type 'quit', 'exit', or 'q' to stop")
    print("Type 'info' to see collection information")
    print("Type 'help' for commands")
    print()
    
    # Get collection name
    collection_name = input("Enter Qdrant collection name (default: dnd_documents): ").strip()
    if not collection_name:
        collection_name = "dnd_documents"
    
    try:
        # Initialize RAG agent
        agent = RAGAgent(collection_name=collection_name)
        
        # Show collection info
        info = agent.get_collection_info()
        if "error" not in info:
            print(f"Collection: {info['collection_name']} ({info['total_documents']} documents)")
        print()
        
        while True:
            question = input("Question: ").strip()
            
            if question.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break
            
            if question.lower() == 'info':
                info = agent.get_collection_info()
                if "error" in info:
                    print(f"Error: {info['error']}")
                else:
                    print(f"Collection: {info['collection_name']}")
                    print(f"Documents: {info['total_documents']}")
                    print(f"Vector size: {info['vector_size']}")
                    print(f"Distance: {info['distance_metric']}")
                print()
                continue
            
            if question.lower() == 'help':
                print("Commands:")
                print("  info  - Show collection information")
                print("  help  - Show this help")
                print("  quit  - Exit the program")
                print("  q     - Exit the program")
                print()
                continue
            
            if not question:
                print("Please enter a question.")
                continue
            
            print("\nSearching...")
            result = agent.query(question)
            
            if "error" in result:
                print(f"Error: {result['error']}")
                print()
                continue
            
            print("\n" + "="*60)
            print("ANSWER:")
            print("="*60)
            
            if "manual_answer" in result:
                print(result["manual_answer"])
            else:
                print(result["answer"])
            
            print("\n" + "="*60)
            print("SOURCES:")
            print("="*60)
            
            sources = result["source_documents"]
            if sources:
                for source in sources:
                    print(f"{source['rank']}. {source['source_file']} (Tags: {source['document_tag']})")
                    print(f"   Preview: {source['content_preview']}")
                    print()
            else:
                print("No sources found.")
            
            print("-" * 60 + "\n")
    
    except Exception as e:
        print(f"Failed to initialize RAG agent: {e}")


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