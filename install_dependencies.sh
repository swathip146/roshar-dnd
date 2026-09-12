#!/bin/bash
# D&D System Dependencies Installation Script
# Installs all dependencies from pyproject.toml using uv (https://docs.astral.sh/uv/)
#
# Prior versions of this script drove Conda or a plain venv directly. That path still
# works (see install_dependencies_conda.sh) but is no longer the default: uv resolves
# and installs from a single lockfile (uv.lock), so every machine gets the exact same
# versions, and `uv sync` is a single idempotent command instead of the ~150-line
# conda/venv detection dance this script used to need.
set -e

echo "🎲 Setting up Roshar D&D System Dependencies (uv)..."
echo "============================================================"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed."
    echo ""
    echo "   Install it with:"
    echo "     curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "   or:"
    echo "     brew install uv"
    echo ""
    echo "   If you'd rather not install uv, use the Conda/venv path instead:"
    echo "     ./install_dependencies_conda.sh"
    exit 1
fi

echo "✅ uv detected: $(uv --version)"
echo ""

# Pin the interpreter. `uv sync` creates .venv/ on first run and reuses it after.
echo "🐍 Pinning Python 3.12..."
uv python pin 3.12

echo ""
echo "📦 Resolving and installing dependencies (uv sync)..."
echo "   This may take a while the first time (downloads torch, transformers, etc.)."
echo "   Includes the dev group (pytest + plugins) — this is a dev checkout, not a"
echo "   deployed package, so there is no separate 'prod install' path."
echo ""
uv sync

echo ""
echo "✅ Verifying installation..."
uv run python -c "
import sys
print(f'Python: {sys.version}')

try:
    import haystack
    print(f'✅ Haystack: {haystack.__version__}')
except ImportError as e:
    print(f'❌ Haystack: {e}')
    sys.exit(1)

try:
    import google.genai
    print('✅ Google Gen AI SDK: Available')
except ImportError as e:
    print(f'❌ Google Gen AI SDK: {e}')
    sys.exit(1)

try:
    import sentence_transformers
    print(f'✅ Sentence Transformers: {sentence_transformers.__version__}')
except ImportError as e:
    print(f'❌ Sentence Transformers: {e}')
    sys.exit(1)

try:
    import docling
    print('✅ Docling: Available')
except ImportError as e:
    print(f'⚠️  Docling: {e} (optional for document processing)')

try:
    from haystack.components.embedders import SentenceTransformersTextEmbedder
    print('✅ Haystack SentenceTransformers embedder: Available')
except ImportError as e:
    # Verified 2026-09-11: an unpinned haystack-ai resolves to a 3.x release on this
    # project's package index that removed this embedder entirely (ImportError, not a
    # deprecation warning). pyproject.toml pins haystack-ai<3.0 for exactly this reason
    # — if this still fails, something re-widened that constraint.
    print(f'❌ Haystack SentenceTransformers embedder: {e}')
    print('   Check the haystack-ai version pin in pyproject.toml (<3.0).')
    sys.exit(1)

try:
    import d20
    print('✅ d20 (Avrae dice parser): Available')
except ImportError as e:
    print(f'❌ d20: {e}')
    sys.exit(1)

try:
    from haystack_integrations.document_stores.qdrant import QdrantDocumentStore
    print('✅ Qdrant Haystack: Available')
except ImportError as e:
    print(f'❌ Qdrant Haystack: {e}')
    sys.exit(1)

print('')
print('🎉 All packages installed successfully!')
"

echo ""
echo "============================================================"
echo "🎉 Installation complete!"
echo ""
echo "📝 Next steps:"
echo ""
echo "1️⃣  Set your GEMINI_API_KEY in .env file:"
echo "   echo 'GEMINI_API_KEY=your_api_key_here' > .env"
echo ""
echo "2️⃣  Run the game:"
echo "   ./run_game.sh"
echo "   (or directly: uv run python haystack_dnd_game.py)"
echo ""
echo "3️⃣  Run the tests:"
echo "   uv run pytest tests/ -q"
echo ""
echo "📦 Dependency source of truth: pyproject.toml + uv.lock"
echo "   Add a dependency:    uv add <package>"
echo "   Add a dev-only tool: uv add --dev <package>"
echo "   No 'activate' step needed — every command runs through 'uv run ...'"
echo ""
echo "🤖 Models that will be downloaded on first use:"
echo "   - BAAI/bge-large-en-v1.5 (~1.34GB)"
echo "   - BAAI/bge-reranker-v2-m3 (~2.24GB)"
echo ""
