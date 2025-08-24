"""
Batch PDF and Text Document to Vector Database Converter
Combines PDF and text processing with Qdrant Vector Storage
"""

# Set tokenizers parallelism to avoid fork warnings - MUST be set before any imports
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from pathlib import Path
from typing import List, Optional, Dict, Any
from haystack import Document, Pipeline
from haystack.components.converters import PyPDFToDocument, TextFileToDocument
from haystack.components.preprocessors import DocumentSplitter
from haystack.components.writers import DocumentWriter
from haystack.components.embedders import SentenceTransformersDocumentEmbedder
from haystack_integrations.document_stores.qdrant import QdrantDocumentStore


def clear_qdrant_collection(collection_name: str, storage_path: str = "./qdrant_storage"):
    """Clear all documents from a local Qdrant collection"""
    import shutil
    
    # For local storage, we can remove the collection directory
    collection_path = Path(storage_path) / collection_name
    
    if collection_path.exists():
        shutil.rmtree(collection_path)
        print(f"Cleared local Qdrant collection: {collection_name}")
    else:
        print(f"Collection {collection_name} does not exist at {storage_path}")


def setup_qdrant_store(collection_name: str = "dnd_documents",
                      embedding_dim: int = 384,
                      storage_path: str = "./qdrant_storage",
                      clear_existing: bool = False) -> QdrantDocumentStore:
    """Set up local Qdrant vector store for document storage"""
    
    # Clear existing collection if requested
    if clear_existing:
        clear_qdrant_collection(collection_name, storage_path)
        print(f"Cleared existing collection: {collection_name}")
    
    # Initialize local document store - it will create the collection automatically
    document_store = QdrantDocumentStore(
        path=storage_path,
        index=collection_name,
        embedding_dim=embedding_dim
    )
    
    print(f"Initialized local Qdrant collection: {collection_name}")
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


def convert_text_to_documents(text_path: str, folder_tags: List[str],
                             chunk_size: int = 800,
                             chunk_overlap: int = 100) -> List[Document]:
    """Convert text file to Haystack documents with chunking"""
    # Initialize text file converter
    converter = TextFileToDocument()
    
    # Convert text file to documents
    result = converter.run(sources=[Path(text_path)])
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
    file_extension = Path(text_path).suffix.lower()
    for doc in chunked_documents:
        if doc.meta is None:
            doc.meta = {}
        doc.meta.update({
            "source_file": os.path.basename(text_path),
            "folder_tags": folder_tags,
            "document_tag": "/".join(folder_tags) if folder_tags else "root",
            "file_type": "text",
            "file_extension": file_extension
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


def find_all_documents(root_folder, file_types=None):
    """Recursively find all document files in a folder and its subfolders"""
    if file_types is None:
        file_types = ["*.pdf", "*.txt", "*.md"]
    
    document_files = []
    root_path = Path(root_folder)
    
    for file_pattern in file_types:
        for doc_file in root_path.rglob(file_pattern):
            # Get all parent folder names from root to immediate parent
            relative_path = doc_file.relative_to(root_path)
            folder_tags = list(relative_path.parent.parts) if relative_path.parent != Path('.') else []
            file_extension = doc_file.suffix.lower()
            document_files.append((str(doc_file), folder_tags, file_extension))
    
    return document_files


def find_all_pdfs(root_folder):
    """Recursively find all PDF files in a folder and its subfolders (legacy function)"""
    pdf_files = []
    document_files = find_all_documents(root_folder, ["*.pdf"])
    
    # Convert to old format for backward compatibility
    for doc_file, folder_tags, _ in document_files:
        pdf_files.append((doc_file, folder_tags))
    
    return pdf_files


def get_user_inputs():
    """Get user inputs for batch processing"""
    print("=== Batch Document Processing ===")
    print("This tool processes all documents (PDFs, TXT, MD files) in a folder and its subfolders")
    print("Each document will be tagged with all its parent folder names")
    print("Supported file types: .pdf, .txt, .md")
    print()
    
    # Get root folder
    while True:
        root_folder = input("Enter the root folder path containing documents: ").strip()
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


def process_all_documents(root_folder, use_qdrant=True, collection_name="dnd_documents", clear_existing=False):
    """Process all document files (PDFs, TXT, MD) in a folder and its subfolders"""
    # Find all document files
    document_files = find_all_documents(root_folder)
    
    if not document_files:
        print(f"No document files found in {root_folder}")
        return
    
    # Count files by type
    file_counts = {}
    for _, _, file_ext in document_files:
        file_counts[file_ext] = file_counts.get(file_ext, 0) + 1
    
    print(f"Found {len(document_files)} document files to process:")
    for ext, count in sorted(file_counts.items()):
        print(f"  - {ext.upper()} files: {count}")
    
    # Try to setup Qdrant if requested
    document_store = None
    if use_qdrant:
        try:
            print("Setting up local Qdrant vector store...")
            document_store = setup_qdrant_store(collection_name=collection_name, clear_existing=clear_existing)
            print("✓ Local Qdrant storage initialized")
        except Exception as e:
            print(f"⚠️  Local Qdrant storage initialization failed: {e}")
            print("Continuing without vector storage - only text files will be generated")
            print("Check that the storage path is accessible and has write permissions")
            document_store = None
    
    all_documents = []
    successful_count = 0
    
    # Process each document file
    for i, (doc_path, folder_tags, file_ext) in enumerate(document_files, 1):
        tag_display = "/".join(folder_tags) if folder_tags else "root"
        print(f"[{i}/{len(document_files)}] Processing: {os.path.basename(doc_path)} (tags: {tag_display})")
        
        try:
            # Convert document to Haystack documents based on file type
            if file_ext == ".pdf":
                documents = convert_pdf_to_documents(doc_path, folder_tags)
            elif file_ext in [".txt", ".md"]:
                documents = convert_text_to_documents(doc_path, folder_tags)
            else:
                print(f"  ⚠️  Unsupported file type: {file_ext}")
                continue
                
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
        output_filename = f"batch_output_{successful_count}_documents.txt"
        # print(f"Saving combined text output...")
        # save_text_output(all_documents, output_filename)
        
        print(f"\n=== Processing Complete ===")
        print(f"✓ Successfully processed: {successful_count}/{len(document_files)} document files")
        print(f"✓ Total document chunks: {len(all_documents)}")
        # print(f"✓ Text output saved: {output_filename}")
        if document_store:
            print(f"✓ Documents stored in local Qdrant collection: {collection_name}")
        else:
            print(f"⚠️  Vector storage skipped (local Qdrant not available)")
    else:
        print("No documents were processed successfully.")


def process_all_pdfs(root_folder, use_qdrant=True, collection_name="dnd_documents", clear_existing=False):
    """Legacy function for backward compatibility - now processes all document types"""
    return process_all_documents(root_folder, use_qdrant, collection_name, clear_existing)


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
        
        # Process all documents
        process_all_documents(root_folder, use_qdrant, collection_name, clear_existing)
        
        print("\nBatch processing completed!")
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
    except Exception as e:
        print(f"\nError during processing: {e}")
        raise


if __name__ == "__main__":
    main()