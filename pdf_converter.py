"""
PDF to Document Converter using Haystack PyPDFToDocument and Qdrant Vector Storage
"""
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from haystack import Document, Pipeline
from haystack.components.converters import PyPDFToDocument
from haystack.components.preprocessors import DocumentSplitter
from haystack.components.writers import DocumentWriter
from haystack.components.embedders import SentenceTransformersDocumentEmbedder
from haystack_integrations.document_stores.qdrant import QdrantDocumentStore
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams


def setup_qdrant_store(collection_name: str = "dnd_documents", 
                      embedding_dim: int = 384,
                      host: str = "localhost",
                      port: int = 6333) -> QdrantDocumentStore:
    """
    Set up Qdrant vector store for document storage
    
    Args:
        collection_name: Name of the Qdrant collection
        embedding_dim: Dimension of the embedding vectors
        host: Qdrant host
        port: Qdrant port
        
    Returns:
        QdrantDocumentStore instance
    """
    try:
        # Initialize Qdrant client
        client = QdrantClient(host=host, port=port)
        
        # Check if collection exists, create if not
        collections = client.get_collections()
        collection_names = [col.name for col in collections.collections]
        
        if collection_name not in collection_names:
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=embedding_dim, distance=Distance.COSINE)
            )
            print(f"Created new Qdrant collection: {collection_name}")
        else:
            print(f"Using existing Qdrant collection: {collection_name}")
        
        # Initialize document store
        document_store = QdrantDocumentStore(
            host=host,
            port=port,
            index=collection_name,
            embedding_dim=embedding_dim
        )
        
        return document_store
        
    except Exception as e:
        print(f"Error setting up Qdrant store: {e}")
        print("Make sure Qdrant is running locally on localhost:6333")
        print("You can start it with: docker run -p 6333:6333 qdrant/qdrant")
        raise


def get_user_input() -> tuple[str, str]:
    """
    Get user input for PDF file path and document tag
    
    Returns:
        Tuple of (file_path, document_tag)
    """
    print("=== PDF to Document Converter ===")
    print("This tool converts PDF files to documents and stores them in Qdrant vector database")
    print()
    
    # Get file path
    while True:
        file_path = input("Enter the path to your PDF file: ").strip()
        if not file_path:
            print("Please enter a valid file path.")
            continue
            
        # Handle relative paths
        if not os.path.isabs(file_path):
            file_path = os.path.join(os.getcwd(), file_path)
            
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            print("Please check the path and try again.")
            continue
            
        if not file_path.lower().endswith('.pdf'):
            print("Please provide a PDF file (.pdf extension required).")
            continue
            
        break
    
    # Get document tag for metadata
    document_tag = input("Enter a tag for this document (e.g., 'character_sheet', 'rules', 'lore'): ").strip()
    if not document_tag:
        document_tag = "general"
    
    return file_path, document_tag


def convert_pdf_to_documents(pdf_path: str, document_tag: str, 
                           chunk_size: int = 800, 
                           chunk_overlap: int = 100) -> List[Document]:
    """
    Convert PDF to Haystack documents with chunking
    
    Args:
        pdf_path: Path to PDF file
        document_tag: Tag to add as metadata
        chunk_size: Size of text chunks
        chunk_overlap: Overlap between chunks
        
    Returns:
        List of Haystack Document objects
    """
    #print(f"Converting PDF: {pdf_path}")
    
    # Initialize PDF converter
    converter = PyPDFToDocument()
    
    # Convert PDF to documents
    result = converter.run(sources=[Path(pdf_path)])
    documents = result["documents"]
    
    #print(f"Extracted {len(documents)} pages from PDF")
    
    # Initialize document splitter for chunking
    splitter = DocumentSplitter(
        split_by="word",
        split_length=chunk_size,
        split_overlap=chunk_overlap
    )
    
    # Split documents into chunks
    split_result = splitter.run(documents=documents)
    chunked_documents = split_result["documents"]
    
    #print(f"Split into {len(chunked_documents)} chunks")
    
    # Add metadata to all documents
    for doc in chunked_documents:
        if doc.meta is None:
            doc.meta = {}
        doc.meta.update({
            "source_file": os.path.basename(pdf_path),
            "document_tag": document_tag,
            "file_type": "pdf"
        })
    
    return chunked_documents


def save_text_output(documents: List[Document], output_path: str):
    """
    Save document content to a text file
    
    Args:
        documents: List of Document objects
        output_path: Path for output text file
    """
    print(f"Saving text output to: {output_path}")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("=== PDF Document Conversion Output ===\n\n")
        
        for i, doc in enumerate(documents, 1):
            f.write(f"--- Chunk {i} ---\n")
            f.write(f"Content: {doc.content}\n")
            
            if doc.meta:
                f.write(f"Metadata: {doc.meta}\n")
            
            f.write("\n" + "="*50 + "\n\n")
    
    print(f"Text output saved successfully to {output_path}")


def store_in_qdrant(documents: List[Document], document_store: QdrantDocumentStore):
    """
    Store documents in Qdrant vector database with embeddings
    
    Args:
        documents: List of Document objects
        document_store: QdrantDocumentStore instance
    """
    print("Generating embeddings and storing in Qdrant...")
    
    # Initialize embedder
    embedder = SentenceTransformersDocumentEmbedder(
        model="sentence-transformers/all-MiniLM-L6-v2",
        progress_bar=True
    )
    
    # Warm up the embedder (load the model)
    print("Loading embedding model...")
    embedder.warm_up()
    
    # Generate embeddings
    embedded_result = embedder.run(documents=documents)
    embedded_documents = embedded_result["documents"]
    
    # Initialize document writer
    writer = DocumentWriter(document_store=document_store)
    
    # Write documents to store
    writer.run(documents=embedded_documents)
    
    print(f"Successfully stored {len(embedded_documents)} documents in Qdrant")


def create_processing_pipeline(document_store: QdrantDocumentStore) -> Pipeline:
    """
    Create a processing pipeline for PDF conversion and storage
    
    Args:
        document_store: QdrantDocumentStore instance
        
    Returns:
        Configured Pipeline
    """
    # Initialize components
    converter = PyPDFToDocument()
    splitter = DocumentSplitter(
        split_by="word",
        split_length=800,
        split_overlap=100
    )
    embedder = SentenceTransformersDocumentEmbedder(
        model="sentence-transformers/all-MiniLM-L6-v2"
    )
    
    # Warm up the embedder (load the model)
    print("Loading embedding model for pipeline...")
    embedder.warm_up()
    
    writer = DocumentWriter(document_store=document_store)
    
    # Create pipeline
    pipeline = Pipeline()
    pipeline.add_component("converter", converter)
    pipeline.add_component("splitter", splitter)
    pipeline.add_component("embedder", embedder)
    pipeline.add_component("writer", writer)
    
    # Connect components
    pipeline.connect("converter", "splitter")
    pipeline.connect("splitter", "embedder")
    pipeline.connect("embedder", "writer")
    
    return pipeline


def process_pdf_with_pipeline(pdf_path: str, document_tag: str, 
                            document_store: QdrantDocumentStore) -> List[Document]:
    """
    Process PDF using the pipeline approach
    
    Args:
        pdf_path: Path to PDF file
        document_tag: Tag for metadata
        document_store: QdrantDocumentStore instance
        
    Returns:
        List of processed documents
    """
    print("Processing PDF with pipeline...")
    
    # Create pipeline
    pipeline = create_processing_pipeline(document_store)
    
    # Run pipeline
    result = pipeline.run({
        "converter": {"sources": [Path(pdf_path)]}
    })
    
    # Add metadata to documents
    documents = result["writer"]["documents_written"]
    for doc in documents:
        if doc.meta is None:
            doc.meta = {}
        doc.meta.update({
            "source_file": os.path.basename(pdf_path),
            "document_tag": document_tag,
            "file_type": "pdf"
        })
    
    print(f"Pipeline processed {len(documents)} documents")
    return documents


def main():
    """
    Main function to orchestrate the PDF conversion process
    """
    try:
        # Get user input
        pdf_path, document_tag = get_user_input()
        
        # Setup Qdrant document store
        print("\nSetting up Qdrant vector store...")
        document_store = setup_qdrant_store()
        
        # Convert PDF to documents
        print("\nConverting PDF to documents...")
        documents = convert_pdf_to_documents(pdf_path, document_tag)
        
        # Generate output text file path
        pdf_name = Path(pdf_path).stem
        output_text_path = f"{pdf_name}_{document_tag}_output.txt"
        
        # Save text output
        print("\nSaving text output...")
        save_text_output(documents, output_text_path)
        
        # Store in Qdrant
        print("\nStoring documents in Qdrant...")
        store_in_qdrant(documents, document_store)
        
        print("\n=== Conversion Complete ===")
        print(f"✓ PDF converted: {pdf_path}")
        print(f"✓ Documents created: {len(documents)}")
        print(f"✓ Text output saved: {output_text_path}")
        print(f"✓ Documents stored in Qdrant with tag: {document_tag}")
        
        return documents, document_store
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        return None, None
    except Exception as e:
        print(f"\nError during processing: {e}")
        raise


def alternative_pipeline_main():
    """
    Alternative main function using the pipeline approach
    """
    try:
        # Get user input
        pdf_path, document_tag = get_user_input()
        
        # Setup Qdrant document store
        print("\nSetting up Qdrant vector store...")
        document_store = setup_qdrant_store()
        
        # Process with pipeline
        print("\nProcessing PDF with pipeline...")
        documents = process_pdf_with_pipeline(pdf_path, document_tag, document_store)
        
        # Generate output text file path
        pdf_name = Path(pdf_path).stem
        output_text_path = f"{pdf_name}_{document_tag}_pipeline_output.txt"
        
        # Save text output
        print("\nSaving text output...")
        save_text_output(documents, output_text_path)
        
        print("\n=== Pipeline Processing Complete ===")
        print(f"✓ PDF processed: {pdf_path}")
        print(f"✓ Documents created: {len(documents)}")
        print(f"✓ Text output saved: {output_text_path}")
        print(f"✓ Documents stored in Qdrant with tag: {document_tag}")
        
        return documents, document_store
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        return None, None
    except Exception as e:
        print(f"\nError during processing: {e}")
        raise


if __name__ == "__main__":
    # You can choose which approach to use:
    # main()  # Step-by-step approach
    alternative_pipeline_main()  # Pipeline approach