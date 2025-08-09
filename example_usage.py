"""
Example usage of the PDF converter
"""
from pdf_converter import main, alternative_pipeline_main, setup_qdrant_store
from pathlib import Path
import os

def example_with_existing_pdf():
    """
    Example using one of the existing PDF files in the project
    """
    print("=== Example: Converting an existing PDF ===")
    
    # Look for available PDF files in the project
    pdf_files = []
    for root, dirs, files in os.walk("."):
        for file in files:
            if file.lower().endswith('.pdf'):
                pdf_files.append(os.path.join(root, file))
    
    if pdf_files:
        print(f"Found {len(pdf_files)} PDF files in the project:")
        for i, pdf in enumerate(pdf_files[:5], 1):  # Show first 5
            print(f"  {i}. {pdf}")
        
        print("\nExample: To convert the first PDF, you would run:")
        print(f"python pdf_converter.py")
        print(f"# Then enter: {pdf_files[0]}")
        print(f"# And enter a tag like: character_sheet")
    else:
        print("No PDF files found in the current directory")
        print("You can use any PDF file by providing its path")

def example_programmatic_usage():
    """
    Example of programmatic usage without user input
    """
    print("\n=== Example: Programmatic Usage ===")
    print("""
# Example code for direct usage:

from pdf_converter import convert_pdf_to_documents, setup_qdrant_store, store_in_qdrant, save_text_output

# Setup
pdf_path = "your_file.pdf"
document_tag = "your_tag"

# Convert PDF
documents = convert_pdf_to_documents(pdf_path, document_tag)

# Setup Qdrant
document_store = setup_qdrant_store()

# Store in vector database
store_in_qdrant(documents, document_store)

# Save text output
save_text_output(documents, "output.txt")
    """)

def check_dependencies():
    """
    Check if required dependencies are installed
    """
    print("\n=== Dependency Check ===")
    
    try:
        import haystack
        print("✓ Haystack installed")
    except ImportError:
        print("✗ Haystack not installed. Run: pip install farm-haystack")
    
    try:
        from haystack_integrations.document_stores.qdrant import QdrantDocumentStore
        print("✓ Qdrant Haystack integration available")
    except ImportError:
        print("✗ Qdrant integration not available. Run: pip install qdrant-haystack")
    
    try:
        from qdrant_client import QdrantClient
        print("✓ Qdrant client available")
    except ImportError:
        print("✗ Qdrant client not installed. Run: pip install qdrant-client")
    
    try:
        from sentence_transformers import SentenceTransformer
        print("✓ SentenceTransformers available")
    except ImportError:
        print("✗ SentenceTransformers not installed. Run: pip install sentence-transformers")

if __name__ == "__main__":
    check_dependencies()
    example_with_existing_pdf()
    example_programmatic_usage()
    
    print("\n=== Instructions ===")
    print("1. Make sure Qdrant is running:")
    print("   docker run -p 6333:6333 qdrant/qdrant")
    print("\n2. Run the converter:")
    print("   python pdf_converter.py")
    print("\n3. Follow the prompts to select your PDF file and tag")