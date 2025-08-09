"""
Batch PDF to Document Converter with Hierarchical Folder-based Tagging
Combines PDF processing with Qdrant Vector Storage
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


def clear_qdrant_collection(collection_name: str, host: str = "localhost", port: int = 6333):
    """Clear all documents from a Qdrant collection"""
    client = QdrantClient(host=host, port=port)
    
    # Check if collection exists
    collections = client.get_collections()
    collection_names = [col.name for col in collections.collections]
    
    if collection_name in collection_names:
        # Delete the collection
        client.delete_collection(collection_name)
        print(f"Cleared Qdrant collection: {collection_name}")
    else:
        print(f"Collection {collection_name} does not exist")


def setup_qdrant_store(collection_name: str = "dnd_documents",
                      embedding_dim: int = 384,
                      host: str = "localhost",
                      port: int = 6333,
                      clear_existing: bool = False) -> QdrantDocumentStore:
    """Set up Qdrant vector store for document storage"""
    # Initialize Qdrant client
    client = QdrantClient(host=host, port=port)
    
    # Check if collection exists
    collections = client.get_collections()
    collection_names = [col.name for col in collections.collections]
    
    # Clear existing collection if requested
    if clear_existing and collection_name in collection_names:
        client.delete_collection(collection_name)
        print(f"Cleared existing collection: {collection_name}")
        collection_names.remove(collection_name)
    
    # Create collection if it doesn't exist
    if collection_name not in collection_names:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=embedding_dim, distance=Distance.COSINE)
        )
        print(f"Created Qdrant collection: {collection_name}")
    
    # Initialize document store
    document_store = QdrantDocumentStore(
        host=host,
        port=port,
        index=collection_name,
        embedding_dim=embedding_dim
    )
    
    return document_store


def convert_pdf_to_documents(pdf_path: str, folder_tags: List[str],
                           chunk_size: int = 800,
                           chunk_overlap: int = 100) -> List[Document]:
    """Convert PDF to Haystack documents with chunking"""
    # Initialize PDF converter
    converter = PyPDFToDocument()
    
    # Convert PDF to documents
    result = converter.run(sources=[Path(pdf_path)])
    documents = result["documents"]
    
    # Initialize document splitter for chunking
    splitter = DocumentSplitter(
        split_by="word",
        split_length=chunk_size,
        split_overlap=chunk_overlap
    )
    
    # Split documents into chunks
    split_result = splitter.run(documents=documents)
    chunked_documents = split_result["documents"]
    
    # Add metadata to all documents
    for doc in chunked_documents:
        if doc.meta is None:
            doc.meta = {}
        doc.meta.update({
            "source_file": os.path.basename(pdf_path),
            "folder_tags": folder_tags,
            "document_tag": "/".join(folder_tags) if folder_tags else "root",
            "file_type": "pdf"
        })
    
    return chunked_documents


def save_text_output(documents: List[Document], output_path: str):
    """Save document content to a text file"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("=== PDF Document Conversion Output ===\n\n")
        
        for i, doc in enumerate(documents, 1):
            f.write(f"--- Chunk {i} ---\n")
            f.write(f"Content: {doc.content}\n")
            
            if doc.meta:
                f.write(f"Metadata: {doc.meta}\n")
            
            f.write("\n" + "="*50 + "\n\n")


def store_in_qdrant(documents: List[Document], document_store: QdrantDocumentStore):
    """Store documents in Qdrant vector database with embeddings"""
    # Initialize embedder
    embedder = SentenceTransformersDocumentEmbedder(
        model="sentence-transformers/all-MiniLM-L6-v2",
        progress_bar=False
    )
    
    # Warm up the embedder (load the model)
    embedder.warm_up()
    
    # Generate embeddings
    embedded_result = embedder.run(documents=documents)
    embedded_documents = embedded_result["documents"]
    
    # Initialize document writer
    writer = DocumentWriter(document_store=document_store)
    
    # Write documents to store
    writer.run(documents=embedded_documents)


def find_all_pdfs(root_folder):
    """Recursively find all PDF files in a folder and its subfolders"""
    pdf_files = []
    root_path = Path(root_folder)
    
    for pdf_file in root_path.rglob("*.pdf"):
        # Get all parent folder names from root to immediate parent
        relative_path = pdf_file.relative_to(root_path)
        folder_tags = list(relative_path.parent.parts) if relative_path.parent != Path('.') else []
        pdf_files.append((str(pdf_file), folder_tags))
    
    return pdf_files


def get_user_inputs():
    """Get user inputs for batch processing"""
    print("=== Batch PDF Processing ===")
    print("This tool processes all PDFs in a folder and its subfolders")
    print("Each PDF will be tagged with all its parent folder names")
    print()
    
    # Get root folder
    while True:
        root_folder = input("Enter the root folder path containing PDFs: ").strip()
        if not root_folder:
            print("Please enter a valid folder path.")
            continue
            
        # Handle relative paths
        if not os.path.isabs(root_folder):
            root_folder = os.path.join(os.getcwd(), root_folder)
            
        if not os.path.exists(root_folder):
            print(f"Folder not found: {root_folder}")
            print("Please check the path and try again.")
            continue
            
        if not os.path.isdir(root_folder):
            print("Please provide a directory path.")
            continue
            
        break
    
    # Ask about Qdrant usage
    while True:
        use_qdrant = input("Use Qdrant vector storage? (y/n, default: y): ").strip().lower()
        if use_qdrant in ['', 'y', 'yes']:
            use_qdrant = True
            break
        elif use_qdrant in ['n', 'no']:
            use_qdrant = False
            break
        else:
            print("Please enter 'y' for yes or 'n' for no.")
    
    # Get collection name and clear option if using Qdrant
    collection_name = "dnd_documents"
    clear_existing = False
    if use_qdrant:
        collection_input = input("Qdrant collection name (default: dnd_documents): ").strip()
        if collection_input:
            collection_name = collection_input
        
        # Ask about clearing existing data
        while True:
            clear_input = input("Clear existing documents in collection? (y/n, default: n): ").strip().lower()
            if clear_input in ['', 'n', 'no']:
                clear_existing = False
                break
            elif clear_input in ['y', 'yes']:
                clear_existing = True
                break
            else:
                print("Please enter 'y' for yes or 'n' for no.")
    
    return root_folder, use_qdrant, collection_name, clear_existing


def process_all_pdfs(root_folder, use_qdrant=True, collection_name="dnd_documents", clear_existing=False):
    """Process all PDFs in a folder and its subfolders"""
    # Find all PDF files
    pdf_files = find_all_pdfs(root_folder)
    
    if not pdf_files:
        print(f"No PDF files found in {root_folder}")
        return
    
    print(f"Found {len(pdf_files)} PDF files to process")
    
    # Try to setup Qdrant if requested
    document_store = None
    if use_qdrant:
        try:
            print("Setting up Qdrant vector store...")
            document_store = setup_qdrant_store(collection_name=collection_name, clear_existing=clear_existing)
            print("✓ Qdrant connection successful")
        except Exception as e:
            print(f"⚠️  Qdrant connection failed: {e}")
            print("Continuing without vector storage - only text files will be generated")
            print("To enable vector storage, start Qdrant with: docker run -p 6333:6333 qdrant/qdrant")
            document_store = None
    
    all_documents = []
    successful_count = 0
    
    # Process each PDF
    for i, (pdf_path, folder_tags) in enumerate(pdf_files, 1):
        tag_display = "/".join(folder_tags) if folder_tags else "root"
        print(f"[{i}/{len(pdf_files)}] Processing: {os.path.basename(pdf_path)} (tags: {tag_display})")
        
        try:
            # Convert PDF to documents
            documents = convert_pdf_to_documents(pdf_path, folder_tags)
            all_documents.extend(documents)
            
            # Store in vector database if available
            if document_store:
                store_in_qdrant(documents, document_store)
            
            successful_count += 1
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            continue
    
    # Save combined text output
    if all_documents:
        output_filename = f"batch_output_{successful_count}_pdfs.txt"
        # print(f"Saving combined text output...")
        # save_text_output(all_documents, output_filename)
        
        print(f"\n=== Processing Complete ===")
        print(f"✓ Successfully processed: {successful_count}/{len(pdf_files)} PDFs")
        print(f"✓ Total document chunks: {len(all_documents)}")
        # print(f"✓ Text output saved: {output_filename}")
        if document_store:
            print(f"✓ Documents stored in Qdrant collection: {collection_name}")
        else:
            print(f"⚠️  Vector storage skipped (Qdrant not available)")
    else:
        print("No documents were processed successfully.")


def main():
    """Main function to orchestrate the batch PDF processing"""
    try:
        # Get user inputs
        root_folder, use_qdrant, collection_name, clear_existing = get_user_inputs()
        
        print(f"\nStarting batch processing...")
        print(f"Root folder: {root_folder}")
        print(f"Vector storage: {'Enabled' if use_qdrant else 'Disabled'}")
        if use_qdrant:
            print(f"Collection: {collection_name}")
            print(f"Clear existing: {'Yes' if clear_existing else 'No'}")
        print()
        
        # Process all PDFs
        process_all_pdfs(root_folder, use_qdrant, collection_name, clear_existing)
        
        print("\nBatch processing completed!")
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
    except Exception as e:
        print(f"\nError during processing: {e}")
        raise


if __name__ == "__main__":
    main()