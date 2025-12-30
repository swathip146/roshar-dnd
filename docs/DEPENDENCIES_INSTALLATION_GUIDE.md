# D&D System Dependencies Installation Guide

This guide documents all the libraries and dependencies needed to run the Roshar D&D system with Gemini integration.

## System Requirements

- **Python**: 3.12+ (tested with Python 3.12.11)
- **Operating System**: macOS (tested on macOS 14+), Linux, Windows
- **Memory**: Minimum 4GB RAM (8GB+ recommended for embeddings)

## Environment Setup

### 1. Virtual Environment

Create and activate a Python virtual environment:

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate

# On Windows:
.venv\Scripts\activate
```

### 2. Core Dependencies

Install these packages in your virtual environment:

```bash
# Core Haystack AI framework
.venv/bin/python -m pip install haystack-ai

# Qdrant document store integration
.venv/bin/python -m pip install qdrant-haystack

# Google Generative AI (Gemini) support
.venv/bin/python -m pip install google-generativeai

# Sentence transformers for document embeddings
.venv/bin/python -m pip install "sentence-transformers>=4.1.0"
```

## Package Details

### Essential Packages

| Package | Version | Purpose |
|---------|---------|---------|
| `haystack-ai` | 2.17.1+ | Main AI framework for agents and pipelines |
| `qdrant-haystack` | 9.2.0+ | Vector database integration for RAG |
| `google-generativeai` | Latest | Gemini API integration |
| `sentence-transformers` | 4.1.0+ | Document embeddings for semantic search |

### Automatically Installed Dependencies

These are installed automatically with the core packages:

| Package | Purpose |
|---------|---------|
| `numpy` | Numerical computing |
| `pandas` | Data manipulation |
| `requests` | HTTP requests |
| `pydantic` | Data validation |
| `tqdm` | Progress bars |
| `tenacity` | Retry logic |
| `networkx` | Graph operations |
| `openai` | OpenAI API support (fallback) |
| `grpcio` | gRPC communication |
| `protobuf` | Protocol buffers |
| `h2`, `httpx`, `httpcore` | HTTP/2 support |

## Environment Variables

### Required

```bash
# Gemini API Key (required for AI functionality)
export GEMINI_API_KEY="your_actual_gemini_api_key_here"
```

### Optional Configuration

```bash
# Model selection (defaults to gemini-2.5-flash)
export SCENARIO_GENERATOR_MODEL="gemini-2.5-flash"
export RAG_RETRIEVER_MODEL="gemini-2.5-flash"
export NPC_CONTROLLER_MODEL="gemini-2.5-flash"
export MAIN_INTERFACE_MODEL="gemini-2.5-flash"

# Temperature settings (optional)
export SCENARIO_GENERATOR_TEMPERATURE="0.8"
export RAG_RETRIEVER_TEMPERATURE="0.3"
export NPC_CONTROLLER_TEMPERATURE="0.9"
export MAIN_INTERFACE_TEMPERATURE="0.5"

# Token limits (optional)
export SCENARIO_GENERATOR_MAX_TOKENS="3000"
export RAG_RETRIEVER_MAX_TOKENS="1500"
export NPC_CONTROLLER_MAX_TOKENS="2000"
export MAIN_INTERFACE_MAX_TOKENS="1000"
```

## Installation Script

You can run this complete installation script:

```bash
#!/bin/bash
# Complete D&D System Installation

echo "🎲 Setting up Roshar D&D System..."

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# Upgrade pip
.venv/bin/python -m pip install --upgrade pip

# Install core dependencies
echo "📦 Installing core dependencies..."
.venv/bin/python -m pip install haystack-ai
.venv/bin/python -m pip install qdrant-haystack
.venv/bin/python -m pip install google-generativeai
.venv/bin/python -m pip install "sentence-transformers>=4.1.0"

# Verify installation
echo "✅ Verifying installation..."
python -c "
import haystack
from haystack_integrations.document_stores.qdrant import QdrantDocumentStore
import google.generativeai as genai
import sentence_transformers
print('✅ All packages imported successfully!')
"

echo "🎉 Installation complete!"
echo "Don't forget to set your GEMINI_API_KEY environment variable:"
echo "export GEMINI_API_KEY='your_api_key_here'"
```

## Troubleshooting

### Common Issues

1. **"ModuleNotFoundError: No module named 'haystack'"**
   - Solution: Use the virtual environment's Python: `.venv/bin/python`
   - Ensure packages are installed in the venv, not system Python

2. **"GEMINI_API_KEY environment variable not set"**
   - Solution: `export GEMINI_API_KEY="your_key"`
   - Check with: `echo $GEMINI_API_KEY`

3. **"Interface agent not available"**
   - Usually means missing `google-generativeai` package
   - Install: `.venv/bin/python -m pip install google-generativeai`

4. **"sentence_transformers import error"**
   - Install: `.venv/bin/python -m pip install "sentence-transformers>=4.1.0"`
   - Note: This package is large (~1GB) and may take time to download

5. **Virtual environment pip issues**
   - Use: `.venv/bin/python -m pip` instead of just `pip`
   - This ensures installation in the correct environment

### Version Conflicts

If you encounter version conflicts:

```bash
# Start fresh
rm -rf .venv
python -m venv .venv
source .venv/bin/activate
# Follow installation steps above
```

## Verification

After installation, run this verification script:

```bash
python -c "
import os
import sys
print(f'Python: {sys.version}')
print(f'Virtual env: {sys.prefix}')
print(f'Gemini key set: {\"Yes\" if os.getenv(\"GEMINI_API_KEY\") else \"No\"}')

try:
    import haystack
    print(f'✅ Haystack: {haystack.__version__}')
except ImportError as e:
    print(f'❌ Haystack: {e}')

try:
    import google.generativeai
    print('✅ Google Generative AI: Available')
except ImportError as e:
    print(f'❌ Google Generative AI: {e}')

try:
    import sentence_transformers
    print('✅ Sentence Transformers: Available') 
except ImportError as e:
    print(f'❌ Sentence Transformers: {e}')

try:
    from haystack_integrations.document_stores.qdrant import QdrantDocumentStore
    print('✅ Qdrant Haystack: Available')
except ImportError as e:
    print(f'❌ Qdrant Haystack: {e}')
"
```

## Running the Game

Once everything is installed:

```bash
# Make sure virtual environment is activated
source .venv/bin/activate

# Set your API key
export GEMINI_API_KEY="your_key_here"

# Run the game with Gemini configuration
python start_with_gemini.py

# Or run the standard game
python haystack_dnd_game.py
```

## Notes

- **Installation Size**: Total download size is approximately 2-3GB due to ML models
- **First Run**: Initial model downloads may take 5-10 minutes
- **API Costs**: Gemini API usage will incur costs based on token usage
- **Performance**: Embeddings require significant memory for large document collections

---

*Last updated: $(date)*
*Tested with Python 3.12.11 on macOS*