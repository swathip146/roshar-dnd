#!/usr/bin/env python3
"""
Simple Haystack document store setup - Stage 2 Week 5-6
Provides basic RAG capabilities for campaign context
"""
from haystack_integrations.document_stores.qdrant import QdrantDocumentStore
from haystack.components.embedders import SentenceTransformersTextEmbedder
from haystack import Document, Pipeline
from haystack.components.retrievers import QdrantEmbeddingRetriever
from pathlib import Path
from typing import List, Dict, Any, Optional
import os

class SimpleDocumentStore:
    """Basic Haystack document store setup"""
    
    def __init__(self, collection_name: str = "simple_dnd"):
        """Initialize the document store"""
        self.collection_name = collection_name
        
        # Initialize Qdrant document store
        self.document_store = QdrantDocumentStore(
            path="qdrant_storage",
            index=collection_name,
            embedding_dim=384,
            recreate_index=False
        )
        
        # Initialize embedder
        self.embedder = SentenceTransformersTextEmbedder()
        
        # Initialize retriever
        self.retriever = QdrantEmbeddingRetriever(
            document_store=self.document_store,
            top_k=5
        )
        
        # Build retrieval pipeline
        self.retrieval_pipeline = self._build_retrieval_pipeline()
        
        print(f"🗄️ Document store initialized: {collection_name}")
    
    def _build_retrieval_pipeline(self) -> Pipeline:
        """Build Haystack retrieval pipeline"""
        pipeline = Pipeline()
        
        # Add components
        pipeline.add_component("embedder", self.embedder)
        pipeline.add_component("retriever", self.retriever)
        
        # Connect components
        pipeline.connect("embedder.embedding", "retriever.query_embedding")
        
        return pipeline
    
    def load_basic_content(self):
        """Load minimal D&D content from available sources"""
        docs = []
        
        # Try to load from existing campaign directories
        campaign_sources = [
            "data/campaigns",
            "resources/current_campaign", 
            "docs/campaigns"
        ]
        
        for source_dir in campaign_sources:
            if Path(source_dir).exists():
                docs.extend(self._load_from_directory(source_dir))
        
        # If no campaigns found, create sample content
        if not docs:
            docs = self._create_sample_content()
        
        # Write documents to store
        if docs:
            # Embed documents
            embedded_docs = []
            for doc in docs:
                embedding = self.embedder.run(text=doc.content)["embedding"]
                doc.embedding = embedding
                embedded_docs.append(doc)
            
            self.document_store.write_documents(embedded_docs)
            print(f"📚 Loaded {len(embedded_docs)} documents into store")
        else:
            print("⚠️ No documents loaded - RAG will use fallback responses")
    
    def _load_from_directory(self, directory: str) -> List[Document]:
        """Load documents from a directory"""
        docs = []
        dir_path = Path(directory)
        
        # Load text files
        for file_path in dir_path.glob("*.md"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    docs.append(Document(
                        content=content,
                        meta={
                            "source": str(file_path),
                            "filename": file_path.name,
                            "type": "campaign"
                        }
                    ))
            except Exception as e:
                print(f"⚠️ Failed to load {file_path}: {e}")
        
        # Also load .txt files
        for file_path in dir_path.glob("*.txt"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    docs.append(Document(
                        content=content,
                        meta={
                            "source": str(file_path),
                            "filename": file_path.name,
                            "type": "campaign"
                        }
                    ))
            except Exception as e:
                print(f"⚠️ Failed to load {file_path}: {e}")
        
        return docs
    
    def _create_sample_content(self) -> List[Document]:
        """Create sample D&D content for testing"""
        sample_docs = [
            Document(
                content="""
                The Forgotten Realms Campaign
                
                Welcome to Faerûn, a land of magic and intrigue. Ancient kingdoms rise and fall, 
                while heroes venture forth to face legendary monsters and uncover lost treasures.
                
                Key Locations:
                - Waterdeep: The City of Splendors, a major trading hub
                - Neverwinter: A city rebuilding from past disasters
                - Baldur's Gate: A rough frontier city with opportunities
                - Candlekeep: The great library fortress
                
                Notable NPCs:
                - Elminster: The legendary wizard
                - Drizzt Do'Urden: Famous drow ranger
                - Minsc: Beloved ranger with his hamster Boo
                """,
                meta={"type": "campaign", "name": "Forgotten Realms"}
            ),
            
            Document(
                content="""
                Tavern: The Prancing Pony
                
                A cozy tavern popular with travelers and locals alike. The common room is warm 
                and welcoming, with a large fireplace and sturdy wooden tables. 
                
                NPCs:
                - Barliman: The friendly innkeeper, always ready with local news
                - Nob: The tavern's helper, eager to assist guests
                - Local merchants and farmers frequent the establishment
                
                Rumors:
                - Strange lights seen in the nearby forest
                - Missing caravan last seen heading north
                - Ancient ruins discovered by shepherds
                """,
                meta={"type": "location", "name": "Prancing Pony"}
            ),
            
            Document(
                content="""
                Forest Encounters
                
                The Whispering Woods are ancient and mysterious. Tall oaks and elms create a 
                canopy that filters sunlight into dancing patterns on the forest floor.
                
                Possible Encounters:
                - Wolves: Usually travel in packs of 4-6
                - Bandits: Desperate outlaws seeking easy marks  
                - Fey Creatures: Sprites and pixies, mischievous but not evil
                - Ancient Grove: Sacred circle with magical properties
                - Lost Ruins: Remnants of a forgotten civilization
                
                Environmental Features:
                - Hidden paths known only to locals
                - Stream with crystal clear water
                - Abandoned woodcutter's hut
                """,
                meta={"type": "encounter", "location": "forest"}
            )
        ]
        
        return sample_docs
    
    def simple_search(self, query: str, top_k: int = 3) -> List[str]:
        """Basic document search - returns content strings"""
        try:
            # Run the retrieval pipeline
            result = self.retrieval_pipeline.run({
                "embedder": {"text": query}
            })
            
            documents = result.get("retriever", {}).get("documents", [])
            return [doc.content for doc in documents[:top_k]]
            
        except Exception as e:
            print(f"⚠️ Search failed: {e}")
            return []
    
    def search_with_metadata(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Enhanced search that returns documents with metadata"""
        try:
            result = self.retrieval_pipeline.run({
                "embedder": {"text": query}
            })
            
            documents = result.get("retriever", {}).get("documents", [])
            
            results = []
            for doc in documents[:top_k]:
                results.append({
                    "content": doc.content,
                    "metadata": doc.meta,
                    "score": getattr(doc, 'score', 0.0)
                })
            
            return results
            
        except Exception as e:
            print(f"⚠️ Enhanced search failed: {e}")
            return []
    
    def add_campaign_content(self, content: str, metadata: Dict[str, Any]) -> bool:
        """Add new campaign content to the store"""
        try:
            doc = Document(content=content, meta=metadata)
            
            # Embed the document
            embedding = self.embedder.run(text=content)["embedding"]
            doc.embedding = embedding
            
            # Write to store
            self.document_store.write_documents([doc])
            
            print(f"📝 Added new content: {metadata.get('name', 'Unnamed')}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to add content: {e}")
            return False
    
    def list_campaigns(self) -> List[Dict[str, Any]]:
        """List available campaigns in the document store"""
        try:
            # Get all documents
            all_docs = self.document_store.get_all_documents()
            
            campaigns = []
            seen_campaigns = set()
            
            for doc in all_docs:
                if doc.meta.get("type") == "campaign":
                    name = doc.meta.get("name", "Unknown Campaign")
                    if name not in seen_campaigns:
                        campaigns.append({
                            "name": name,
                            "type": doc.meta.get("type", "unknown"),
                            "source": doc.meta.get("source", "unknown")
                        })
                        seen_campaigns.add(name)
            
            return campaigns
            
        except Exception as e:
            print(f"⚠️ Failed to list campaigns: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get document store statistics"""
        try:
            doc_count = self.document_store.count_documents()
            campaigns = self.list_campaigns()
            
            return {
                "total_documents": doc_count,
                "campaigns": len(campaigns),
                "collection_name": self.collection_name,
                "available_campaigns": [c["name"] for c in campaigns]
            }
            
        except Exception as e:
            print(f"⚠️ Failed to get stats: {e}")
            return {"error": str(e)}