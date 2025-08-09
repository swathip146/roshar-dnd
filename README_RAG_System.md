# D&D RAG System Documentation

This system provides a complete Retrieval-Augmented Generation (RAG) solution for D&D documents using Qdrant vector database and Claude Sonnet 4.

## System Components

### 1. `batch_pdf_processor.py`
Processes PDF documents and stores them in Qdrant vector database with hierarchical folder-based tagging.

**Features:**
- Recursive PDF discovery in folders/subfolders
- Hierarchical tagging (all parent folder names)
- Qdrant vector storage with embeddings
- Option to clear existing collections
- Interactive user input

**Usage:**
```bash
python batch_pdf_processor.py
```

### 2. `rag_agent.py`
RAG agent that answers questions using the stored documents.

**Features:**
- Semantic document retrieval from Qdrant
- Claude Sonnet 4 for intelligent answer generation
- Fallback retrieval-only mode (no Claude needed)
- Interactive chat interface
- Source document citations

**Usage:**
```bash
python rag_agent.py
```

### 3. `example_rag_usage.py`
Demonstrates programmatic usage of the RAG agent.

**Usage:**
```bash
python example_rag_usage.py
```

## Setup Instructions

### 1. Prerequisites
```bash
pip install haystack-ai qdrant-client sentence-transformers hwtgenielib
```

### 2. Start Qdrant
```bash
docker run -p 6333:6333 qdrant/qdrant
```

### 3. Setup Claude Access
The system uses Claude Sonnet 4 through Apple's GenAI framework via `hwtgenielib`.
Make sure you have proper access configured for Claude models.

Without Claude access, the system works in retrieval-only mode.

### 4. Process Documents
```bash
python batch_pdf_processor.py
```
- Enter folder path containing PDFs
- Choose Qdrant options
- Wait for processing to complete

### 5. Query Documents
```bash
python rag_agent.py
```
- Enter collection name
- Ask questions interactively

## Document Structure Example

For a file structure like:
```
docs/
├── rules/
│   └── SRD_CC_v5.2.1.pdf
└── character_sheets_examples/
    ├── Dragonborn Sorcerer 1.pdf
    └── Human Fighter 1.pdf
```

Documents will be tagged as:
- `SRD_CC_v5.2.1.pdf`: `folder_tags: ["rules"]`, `document_tag: "rules"`
- `Dragonborn Sorcerer 1.pdf`: `folder_tags: ["character_sheets_examples"]`, `document_tag: "character_sheets_examples"`

## RAG Agent Usage

### Interactive Mode
```bash
python rag_agent.py
```

Sample questions:
- "What are the different character classes?"
- "How does combat work in D&D?"
- "What equipment does a fighter start with?"

### Programmatic Usage
```python
from rag_agent import RAGAgent

# Initialize agent
agent = RAGAgent(collection_name="dnd_documents")

# Query
result = agent.query("What are the spellcasting rules?")

# Access answer
print(result["answer"])

# Access sources
for source in result["source_documents"]:
    print(f"Source: {source['source_file']}")
```

## System Architecture

```
1. PDF Documents
   ↓
2. batch_pdf_processor.py
   ├── Extract text chunks
   ├── Generate embeddings
   └── Store in Qdrant
   ↓
3. Qdrant Vector Database
   ├── Document chunks
   ├── Embeddings
   └── Metadata (tags, sources)
   ↓
4. rag_agent.py
   ├── Query embedding
   ├── Semantic search
   ├── Retrieve relevant chunks
   └── Generate answer with Claude Sonnet 4
   ↓
5. User Answer + Sources
```

## Configuration Options

### RAGAgent Parameters
```python
agent = RAGAgent(
    collection_name="dnd_documents",  # Qdrant collection
    host="localhost",                 # Qdrant host
    port=6333,                       # Qdrant port
    top_k=5                          # Documents to retrieve
)
```

### Batch Processor Options
- Root folder path
- Qdrant collection name
- Clear existing documents (y/n)
- Vector storage enable/disable

## Troubleshooting

### Common Issues

1. **Qdrant Connection Failed**
   ```
   Error: Connection refused
   ```
   **Solution:** Start Qdrant with `docker run -p 6333:6333 qdrant/qdrant`

2. **Collection Not Found**
   ```
   Collection 'dnd_documents' not found
   ```
   **Solution:** Run `batch_pdf_processor.py` first to create and populate the collection

3. **No Claude Responses**
   ```
   Only document retrieval will be available
   ```
   **Solution:** Ensure `hwtgenielib` is installed and Claude access is configured, or use retrieval-only mode

4. **Embedding Model Loading**
   ```
   The embedding model has not been loaded
   ```
   **Solution:** The system automatically calls `warm_up()` - wait for model download

### Performance Tips

1. **Large Document Collections**
   - Increase `top_k` for more comprehensive retrieval
   - Use more specific queries for better results

2. **Slow Responses**
   - Reduce `top_k` parameter
   - Consider using faster embedding models

3. **Memory Usage**
   - Process documents in smaller batches
   - Clear collections periodically

## Example Queries

### Character Creation
- "How do I create a character?"
- "What races are available?"
- "What classes can I choose?"

### Combat Rules
- "How does initiative work?"
- "What is armor class?"
- "How do I calculate damage?"

### Spellcasting
- "How do spell slots work?"
- "What are cantrips?"
- "How do I prepare spells?"

### Equipment
- "What weapons can a fighter use?"
- "How much does leather armor cost?"
- "What's in a starting equipment pack?"

## API Reference

### RAGAgent Methods

#### `__init__(collection_name, host, port, top_k)`
Initialize the RAG agent with Qdrant connection parameters.

#### `query(question)`
Query the system and get an answer with sources.

**Returns:**
```python
{
    "question": str,
    "answer": str,
    "retrieved_documents": List[Document],
    "source_documents": List[Dict]
}
```

#### `get_collection_info()`
Get information about the current Qdrant collection.

**Returns:**
```python
{
    "collection_name": str,
    "total_documents": int,
    "vector_size": int,
    "distance_metric": str
}
```

## Advanced Usage

### Custom Prompts
Modify the RAG prompt in `rag_agent.py` to customize answer generation:

```python
rag_prompt = """
Your custom prompt template here...
Context: {% for doc in documents %}{{ doc.content }}{% endfor %}
Question: {{ question }}
Answer:
"""
```

### Document Filtering
Filter documents by tags before querying:

```python
# This would require extending the retriever component
# to support metadata filtering
```

### Multiple Collections
Query different collections for different document types:

```python
rules_agent = RAGAgent(collection_name="rules")
lore_agent = RAGAgent(collection_name="lore")
```

## Support

For issues or questions:
1. Check troubleshooting section
2. Verify all prerequisites are installed
3. Ensure Qdrant is running
4. Check document processing completed successfully