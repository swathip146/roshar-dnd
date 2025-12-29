#!/bin/bash
# D&D System Dependencies Installation Script
# Based on DEPENDENCIES_INSTALLATION_GUIDE.md

# Don't exit on error immediately - we want to handle Python detection gracefully
set +e

echo "🎲 Setting up Roshar D&D System Dependencies..."
echo "============================================================"

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if virtual environment exists and is valid
if [ ! -d ".venv" ]; then
    echo "⚠️ Virtual environment not found. Creating one..."
    python3 -m venv .venv
    echo "✅ Virtual environment created"
elif [ -e ".venv/bin/python" ]; then
    # Check if the Python symlink target exists
    PYTHON_TARGET=$(readlink -f .venv/bin/python 2>/dev/null || readlink .venv/bin/python 2>/dev/null)
    if [ -n "$PYTHON_TARGET" ] && [ ! -f "$PYTHON_TARGET" ]; then
        echo "⚠️ Virtual environment Python symlink is broken (target missing)"
        echo "   Recreating virtual environment..."
        rm -rf .venv
        python3 -m venv .venv
        echo "✅ Virtual environment recreated"
    fi
fi

# Determine Python executable
# Priority 1: If venv is activated, use that Python (most reliable)
if [ -n "$VIRTUAL_ENV" ]; then
    PYTHON="$(command -v python 2>/dev/null || command -v python3 2>/dev/null)"
    if [ -n "$PYTHON" ] && [ -x "$PYTHON" ]; then
        echo "✅ Using Python from activated virtual environment: $PYTHON"
    else
        PYTHON=""
    fi
fi

# Priority 2: Try venv/bin/python (even if symlink target missing, might work)
if [ -z "$PYTHON" ]; then
    if [ -e ".venv/bin/python" ]; then
        PYTHON=".venv/bin/python"
    elif [ -e ".venv/bin/python3" ]; then
        PYTHON=".venv/bin/python3"
    fi
fi

# Priority 3: System python3
if [ -z "$PYTHON" ]; then
    PYTHON="$(command -v python3 2>/dev/null)"
    if [ -n "$PYTHON" ]; then
        echo "⚠️ Using system python3: $PYTHON"
    fi
fi

# Verify we found a Python
if [ -z "$PYTHON" ] || [ ! -x "$PYTHON" ]; then
    echo "❌ Could not find a working Python executable"
    echo "   Checked:"
    [ -n "$VIRTUAL_ENV" ] && echo "   - Activated venv: $VIRTUAL_ENV"
    echo "   - .venv/bin/python"
    echo "   - .venv/bin/python3"
    echo "   - system python3"
    echo ""
    echo "💡 Try activating your venv first: source .venv/bin/activate"
    exit 1
fi

# Re-enable exit on error for rest of script
set -e

echo "📦 Using Python: $PYTHON"
echo "   Version: $($PYTHON --version)"

# Upgrade pip
echo ""
echo "⬆️ Upgrading pip..."
$PYTHON -m pip install --upgrade pip --quiet

# Install core dependencies
echo ""
echo "📦 Installing core dependencies..."
echo "   This may take several minutes..."

echo "   → Installing haystack-ai..."
$PYTHON -m pip install haystack-ai

echo "   → Installing qdrant-haystack..."
$PYTHON -m pip install qdrant-haystack

echo "   → Installing google-generativeai..."
$PYTHON -m pip install google-generativeai

echo "   → Installing sentence-transformers..."
$PYTHON -m pip install "sentence-transformers>=4.1.0"

# Verify installation
echo ""
echo "✅ Verifying installation..."
$PYTHON -c "
import sys
print(f'Python: {sys.version}')
print(f'Virtual env: {sys.prefix}')

try:
    import haystack
    print(f'✅ Haystack: {haystack.__version__}')
except ImportError as e:
    print(f'❌ Haystack: {e}')
    sys.exit(1)

try:
    import google.generativeai
    print('✅ Google Generative AI: Available')
except ImportError as e:
    print(f'❌ Google Generative AI: {e}')
    sys.exit(1)

try:
    import sentence_transformers
    print('✅ Sentence Transformers: Available')
except ImportError as e:
    print(f'❌ Sentence Transformers: {e}')
    sys.exit(1)

try:
    from haystack_integrations.document_stores.qdrant import QdrantDocumentStore
    print('✅ Qdrant Haystack: Available')
except ImportError as e:
    print(f'❌ Qdrant Haystack: {e}')
    print('   Trying to install qdrant-haystack...')
    import subprocess
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'qdrant-haystack'])
    # Try again
    try:
        from haystack_integrations.document_stores.qdrant import QdrantDocumentStore
        print('✅ Qdrant Haystack: Now available after installation')
    except ImportError as e2:
        print(f'❌ Qdrant Haystack: Still failed after install - {e2}')
        sys.exit(1)

print('')
print('🎉 All packages installed successfully!')
"

echo ""
echo "============================================================"
echo "🎉 Installation complete!"
echo ""
echo "⚠️ Don't forget to set your GEMINI_API_KEY environment variable:"
echo "   export GEMINI_API_KEY='your_api_key_here'"
echo ""
echo "🚀 To run the game:"
echo "   source .venv/bin/activate"
echo "   python3 haystack_dnd_game.py"
echo ""

