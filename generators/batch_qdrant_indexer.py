"""
Batch PDF and Text Document to Vector Database Converter
Combines PDF and text processing with Qdrant Vector Storage
"""

# Set tokenizers parallelism to avoid fork warnings - MUST be set before any imports
import os
import re
import sys
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Add parent directory to path so we can import from generators package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import centralized logging configuration
from config.logging_config import get_logger

# Initialize logger using centralized config (logs to file + console)
logger = get_logger(__name__)

from pathlib import Path
from typing import List, Optional, Dict, Any
from haystack import Document, Pipeline
from haystack.components.preprocessors import DocumentSplitter
from haystack.components.writers import DocumentWriter
from haystack.components.embedders import SentenceTransformersDocumentEmbedder
from haystack_integrations.document_stores.qdrant import QdrantDocumentStore

# Import Docling converters (new implementation)
from generators.batch_docling_config import BatchDoclingConfig, load_batch_config
from generators.docling_converter import (
    convert_pdf_to_documents_docling,
    convert_text_to_documents_docling,
    convert_image_to_documents_docling
)


def clear_qdrant_collection(collection_name: str, storage_path: str = "./qdrant_storage"):
    """
    Delete a local Qdrant collection's data.

    Plan 0.18: this used to check `<storage_path>/<collection_name>`, but local
    Qdrant actually stores collections under `<storage_path>/collection/<name>`.
    The path never existed, so the function logged "does not exist" and silently
    no-opped — a "clear existing: y" re-index appended to the old data instead of
    replacing it (observed: 3,062 stale + 4,221 new = 7,283 chunks).
    """
    import shutil

    candidates = [
        Path(storage_path) / "collection" / collection_name,  # real layout
        Path(storage_path) / collection_name,                 # legacy guess
    ]

    removed = False
    for path in candidates:
        if path.exists():
            shutil.rmtree(path)
            logger.info(f"Cleared local Qdrant collection at {path}")
            removed = True

    if not removed:
        logger.info(f"Collection {collection_name} not present under {storage_path}")
    return removed


def setup_qdrant_store(collection_name: str = "dnd_documents",
                      embedding_dim: int = 1024,
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
    
    logger.info(f"Initialized local Qdrant collection: {collection_name}")
    return document_store


# Old PDF converter removed - now using convert_pdf_to_documents_docling() from docling_converter module


# Old text converter removed - now using convert_text_to_documents_docling() from docling_converter module


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


def clean_wiki_markup(text: str) -> str:
    """
    Plan 0.13: strip MediaWiki markup from Coppermind-sourced lore.

    resources/lore/*.txt are Coppermind wiki chapter summaries full of
    [[links]], {{templates}}, == headings == and [[File:...]] embeds. Embedding
    that markup pollutes the vectors and wastes retrieval tokens on syntax.
    """
    if not text:
        return text

    # [[File:...]] / [[Image:...]] embeds — drop entirely
    text = re.sub(r"\[\[(?:File|Image):[^\]]*\]\]", " ", text, flags=re.IGNORECASE)
    # [[target|label]] -> label ; [[target]] -> target
    text = re.sub(r"\[\[([^\]|]*)\|([^\]]*)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]*)\]\]", r"\1", text)
    # {{templates}} (incl. {{anchor|...}}, {{update|sa5}}) — drop
    text = re.sub(r"\{\{[^}]*\}\}", " ", text)
    # == Heading == -> Heading (keep the words; they carry meaning)
    text = re.sub(r"^\s*=+\s*(.*?)\s*=+\s*$", r"\1", text, flags=re.MULTILINE)
    # Bold/italic quote markup
    text = re.sub(r"'{2,}", "", text)
    # Leftover HTML-ish wrappers
    text = re.sub(r"</?div[^>]*>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"__TOC__", " ", text)
    # Collapse whitespace introduced by the removals
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_markdown_structurally(text: str, max_words: int) -> List[str]:
    """
    Structure-aware markdown splitter (plan 0.12, revised).

    Haystack's DocumentSplitter(split_by="word") is structure-BLIND: it counts
    words and cuts, ignoring headings, tables and even word boundaries. Measured
    on the Radiant's Handbook it produced 1,041 chunks of which:
        812 (78%) started mid-word   ("ustbringer", "gedancer")
          0 ( 0%) started at a heading
         92       had a table header severed from its rows
    That is why the surge mechanics tables were unusable for retrieval.

    This mirrors the cascade used in pkg-wiki-cli
    (narrator/generator.py: _split_child_by_h2 -> _split_child_by_paragraphs ->
    _hard_split_by_words): prefer semantic boundaries, and only fall back to
    counting words when no structure exists.

    Order of preference:
      1. markdown headings (## / ###) — keeps a section with its own title
      2. paragraph breaks
      3. word count, walking back to a line boundary

    Markdown tables are kept intact: a header row severed from its data rows
    embeds to noise, and the Handbook's mechanics live in tables.
    """
    def _emit(block: str) -> List[str]:
        """Split one block that is already below the heading level."""
        if len(block.split()) <= max_words:
            return [block]

        # Paragraph split
        paras = [p for p in re.split(r"\n\s*\n", block) if p.strip()]
        if len(paras) > 1:
            out, buf = [], []
            for para in paras:
                candidate = buf + [para]
                if sum(len(p.split()) for p in candidate) > max_words and buf:
                    out.append("\n\n".join(buf))
                    buf = [para]
                else:
                    buf = candidate
            if buf:
                out.append("\n\n".join(buf))
            # Recurse in case a single paragraph is still oversized
            return [piece for p in out for piece in (
                [p] if len(p.split()) <= max_words else _hard_split(p, max_words)
            )]

        return _hard_split(block, max_words)

    def _hard_split(block: str, limit: int) -> List[str]:
        """Last resort: split on LINE boundaries, never mid-word."""
        lines, out, buf, count = block.split("\n"), [], [], 0
        for line in lines:
            words = len(line.split())
            if count + words > limit and buf:
                out.append("\n".join(buf))
                buf, count = [line], words
            else:
                buf.append(line)
                count += words
        if buf:
            out.append("\n".join(buf))
        return out or [block]

    if not text.strip():
        return []

    # 1. Split on headings, keeping the heading with its section.
    sections = [s for s in re.split(r"(?m)(?=^#{1,3} )", text) if s.strip()]

    chunks: List[str] = []
    for section in sections:
        # Keep contiguous table blocks whole rather than splitting them.
        table_blocks = re.split(r"(?m)((?:^\|.*\|\s*$\n?)+)", section)
        for block in table_blocks:
            if not block or not block.strip():
                continue
            if block.lstrip().startswith("|"):
                # A table: emit whole, even if it exceeds the word target.
                chunks.append(block.strip())
            else:
                chunks.extend(c for c in _emit(block.strip()) if c.strip())

    return chunks


def store_in_qdrant(documents: List[Document], document_store: QdrantDocumentStore,
                    split_length: int = 200, split_overlap: int = 30):
    """
    Split, embed and write documents to Qdrant.

    Plan 0.12: DocumentSplitter was imported at module scope and NEVER USED, so
    Docling output went straight to the embedder (chunks up to 34,586 chars).
    Wiring it up bounded the sizes, but split_by="word" is structure-blind — see
    _split_markdown_structurally() for the measured damage. We now use the
    structure-aware splitter and keep Haystack's only as a safety net.

    split_length is a parameter because the two collections want different chunk
    sizes (plan D1): small precise chunks for the DM's `dnd_documents`, large
    arc-sized chunks for `dnd_reference`.
    """
    # Plan 0.13: clean wiki markup before splitting so chunk boundaries and
    # embeddings are computed on prose, not syntax.
    split_docs: List[Document] = []
    for doc in documents:
        content = clean_wiki_markup(doc.content or "")
        if not content.strip():
            continue
        for piece in _split_markdown_structurally(content, split_length):
            if piece.strip():
                split_docs.append(Document(content=piece, meta=dict(doc.meta or {})))

    if not split_docs:
        logger.warning("No non-empty documents to store after cleaning/splitting")
        return

    lengths = [len(d.content) for d in split_docs]
    starts_at_heading = sum(1 for d in split_docs if d.content.lstrip().startswith("#"))
    logger.info(
        f"✂️  Split {len(documents)} document(s) -> {len(split_docs)} chunks "
        f"(max {max(lengths)} chars, median {sorted(lengths)[len(lengths)//2]}, "
        f"{100 * starts_at_heading // len(split_docs)}% start at a heading)"
    )

    # Initialize embedder with BGE large model (1024-dim embeddings)
    embedder = SentenceTransformersDocumentEmbedder(
        model="BAAI/bge-large-en-v1.5",
        progress_bar=False
    )
    embedder.warm_up()

    embedded_documents = embedder.run(documents=split_docs)["documents"]
    DocumentWriter(document_store=document_store).run(documents=embedded_documents)


def find_all_documents(root_folder, file_types=None):
    """Recursively find all document files in a folder and its subfolders"""
    if file_types is None:
        # Support PDFs, text files, markdown files, and image files
        file_types = [
            "*.pdf",
            "*.txt",
            "*.md",
            "*.png",
            "*.jpg",
            "*.jpeg",
            "*.gif",
            "*.bmp",
            "*.tiff",
            "*.webp"
        ]
    
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


def save_documents_to_parsed_data(
    documents: List[Document],
    source_file: str,
    session_timestamp: str,
    parsed_data_dir: str = "./parsed_data"
) -> None:
    """
    Save extracted documents to parsed_data directory with organized structure.

    Matches the directory structure used by enhanced parser system:
    parsed_data/{file_stem}_{timestamp}/
        ├── markdown/       # Markdown content files
        ├── metadata/       # JSON metadata files
        ├── image_files/    # Already extracted by docling_converter
        └── tables/         # Already extracted by docling_table_utils

    Args:
        documents: List of Haystack documents to save
        source_file: Original source file path
        session_timestamp: Timestamp for this processing session (YYYYMMDD_HHMMSS)
        parsed_data_dir: Base directory for parsed data
    """
    import json
    from collections import defaultdict

    # Get source file stem
    file_stem = Path(source_file).stem

    # Create session folder
    session_folder = Path(parsed_data_dir) / f"{file_stem}_{session_timestamp}"
    markdown_dir = session_folder / "markdown"
    metadata_dir = session_folder / "metadata"

    # Create directories
    markdown_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    # Track document type counters
    type_counters = defaultdict(int)

    for doc in documents:
        # Determine document type (fixed: use 'content_type' to match actual metadata)
        doc_type = doc.meta.get('content_type', 'text')
        type_counters[doc_type] += 1
        index = type_counters[doc_type]

        # Generate filename based on document type
        page_number = doc.meta.get('page_number')
        if page_number is not None and doc_type == 'text':
            markdown_filename = f"{doc_type}_{index:03d}_page{page_number}.md"
        elif doc_type == 'table':
            table_idx = doc.meta.get('table_index', index)
            markdown_filename = f"{doc_type}_{index:03d}_idx{table_idx}.md"
        elif doc_type == 'image':
            # Extract source file stem and image index for caption naming
            source_file = doc.meta.get('source_file', 'unknown')
            # Remove extension if present (e.g., "file.pdf" → "file")
            source_stem = Path(source_file).stem if '.' in source_file else source_file
            image_idx = doc.meta.get('image_index', index)
            # Use pattern: {source_stem}_image_{idx}_caption.md
            markdown_filename = f"{source_stem}_image_{image_idx}_caption.md"
        else:
            markdown_filename = f"{doc_type}_{index:03d}.md"

        # Save markdown content
        markdown_path = markdown_dir / markdown_filename
        with open(markdown_path, 'w', encoding='utf-8') as f:
            f.write(doc.content)

        # Save metadata JSON
        metadata_filename = markdown_filename.replace('.md', '_metadata.json')
        metadata_path = metadata_dir / metadata_filename
        with open(metadata_path, 'w', encoding='utf-8') as f:
            # Use default=str to handle any non-serializable types
            json.dump(doc.meta, f, indent=2, default=str)

        logger.debug(f"  ✓ Saved {doc_type} document: {markdown_filename}")


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


def process_all_documents(root_folder, use_qdrant=True, collection_name="dnd_documents", clear_existing=False, config_path=None):
    """Process all document files (PDFs, TXT, MD) in a folder and its subfolders"""

    # Load Docling configuration
    config = load_batch_config(config_path)
    logger.info(f"Loaded Docling config: OCR={config.do_ocr}, Tables={config.do_table_structure}, Images={config.generate_picture_images}")

    # Generate session timestamp once for this batch run
    from datetime import datetime
    session_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger.info(f"Session timestamp: {session_timestamp}")

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

    # Define supported image extensions
    IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp'}

    # Process each document file
    for i, (doc_path, folder_tags, file_ext) in enumerate(document_files, 1):
        tag_display = "/".join(folder_tags) if folder_tags else "root"
        print(f"[{i}/{len(document_files)}] Processing: {os.path.basename(doc_path)} (tags: {tag_display})")

        try:
            # Convert document to Haystack documents based on file type
            if file_ext == ".pdf":
                documents = convert_pdf_to_documents_docling(doc_path, folder_tags, config, session_timestamp)
            elif file_ext in [".txt", ".md"]:
                documents = convert_text_to_documents_docling(doc_path, folder_tags, config, session_timestamp)
            elif file_ext in IMAGE_EXTENSIONS:
                # Handle standalone image files
                documents = convert_image_to_documents_docling(doc_path, folder_tags, config, session_timestamp)
            else:
                print(f"  ⚠️  Unsupported file type: {file_ext}")
                continue

            # Save documents to parsed_data directory
            if config and config.save_parsed_artifacts:
                try:
                    save_documents_to_parsed_data(
                        documents=documents,
                        source_file=doc_path,
                        session_timestamp=session_timestamp,
                        parsed_data_dir=config.parsed_data_dir
                    )
                except Exception as e:
                    print(f"  ⚠️  Failed to save parsed artifacts: {e}")

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


def process_all_pdfs(root_folder, use_qdrant=True, collection_name="dnd_documents", clear_existing=False, config_path=None):
    """Legacy function for backward compatibility - now processes all document types"""
    return process_all_documents(root_folder, use_qdrant, collection_name, clear_existing, config_path)


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