import os
from pathlib import Path
from pdf_converter import convert_pdf_to_documents, setup_qdrant_store, store_in_qdrant, save_text_output

def find_all_pdfs(root_folder):
    """
    Recursively find all PDF files in a folder and its subfolders
    
    Args:
        root_folder: Root directory to search for PDFs
        
    Returns:
        List of tuples (pdf_path, folder_tag)
    """
    pdf_files = []
    root_path = Path(root_folder)
    
    for pdf_file in root_path.rglob("*.pdf"):
        # Get the immediate parent folder name as the tag
        folder_tag = pdf_file.parent.name
        pdf_files.append((str(pdf_file), folder_tag))
    
    return pdf_files

def process_all_pdfs(root_folder, use_qdrant=True):
    """
    Process all PDFs in a folder and its subfolders
    
    Args:
        root_folder: Root directory containing PDFs
        use_qdrant: Whether to try using Qdrant for vector storage
    """
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
            document_store = setup_qdrant_store()
            print("✓ Qdrant connection successful")
        except Exception as e:
            print(f"⚠️  Qdrant connection failed: {e}")
            print("Continuing without vector storage - only text files will be generated")
            print("To enable vector storage, start Qdrant with: docker run -p 6333:6333 qdrant/qdrant")
            document_store = None
    
    all_documents = []
    
    # Process each PDF
    for i, (pdf_path, folder_tag) in enumerate(pdf_files, 1):
        # print(f"\n[{i}/{len(pdf_files)}] Processing: {os.path.basename(pdf_path)}")
        # print(f"Folder tag: {folder_tag}")
        
        try:
            # Convert PDF to documents
            documents = convert_pdf_to_documents(pdf_path, folder_tag)
            all_documents.extend(documents)
            
            # Store in vector database if available
            if document_store:
                store_in_qdrant(documents, document_store)
                print(f"✓ Stored {len(documents)} chunks in Qdrant")
            else:
                print(f"✓ Processed {len(documents)} chunks (Qdrant not available)")
            
        except Exception as e:
            print(f"✗ Error processing {os.path.basename(pdf_path)}: {e}")
            continue
    
    # Save combined text output
    if all_documents:
        output_filename = f"combined_output_{len(pdf_files)}_pdfs.txt"
        save_text_output(all_documents, output_filename)
        print(f"\n=== Processing Complete ===")
        print(f"✓ Total documents processed: {len(all_documents)}")
        print(f"✓ Combined text output saved: {output_filename}")
        if document_store:
            print(f"✓ Documents stored in Qdrant vector database")
        else:
            print(f"⚠️  Vector storage skipped (Qdrant not available)")
    else:
        print("No documents were processed successfully.")

# Main execution
if __name__ == "__main__":
    # Specify the root folder containing PDFs
    root_folder = "docs"  # Change this to your desired folder
    
    print("=== Batch PDF Processing ===")
    print(f"Processing all PDFs in folder: {root_folder}")
    print("Note: If Qdrant is not running, only text files will be generated")
    print("To start Qdrant: docker run -p 6333:6333 qdrant/qdrant")
    print()
    
    process_all_pdfs(root_folder, use_qdrant=True)
