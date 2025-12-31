#!/bin/bash
# D&D System Dependencies Installation Script
# Installs all dependencies from requirements.txt using Conda/Anaconda

# Don't exit on error immediately - we want to handle detection gracefully
set +e

echo "🎲 Setting up Roshar D&D System Dependencies..."
echo "============================================================"

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Virtual environment name
ENV_NAME="dndenv"

# Check if conda is available
if command -v conda &> /dev/null; then
    echo "✅ Conda detected - using conda for environment management"
    USE_CONDA=true
else
    echo "⚠️  Conda not found - falling back to venv"
    USE_CONDA=false
fi

# Create or verify environment
if [ "$USE_CONDA" = true ]; then
    # Conda environment management
    if conda env list | grep -q "^${ENV_NAME} "; then
        echo "✅ Conda environment '$ENV_NAME' already exists"
    else
        echo "⚠️  Conda environment not found. Creating '$ENV_NAME'..."
        conda create -n "$ENV_NAME" python=3.12 -y
        echo "✅ Conda environment '$ENV_NAME' created"
    fi

    # Determine Python executable from conda
    PYTHON=$(conda run -n "$ENV_NAME" which python)
    if [ -z "$PYTHON" ] || [ ! -x "$PYTHON" ]; then
        echo "❌ Could not find Python in conda environment '$ENV_NAME'"
        exit 1
    fi
else
    # Traditional venv management
    if [ ! -d "$ENV_NAME" ]; then
        echo "⚠️  Virtual environment not found. Creating '$ENV_NAME'..."
        python3 -m venv "$ENV_NAME"
        echo "✅ Virtual environment '$ENV_NAME' created"
    elif [ -e "$ENV_NAME/bin/python" ]; then
        # Check if the Python symlink target exists
        PYTHON_TARGET=$(readlink -f "$ENV_NAME/bin/python" 2>/dev/null || readlink "$ENV_NAME/bin/python" 2>/dev/null)
        if [ -n "$PYTHON_TARGET" ] && [ ! -f "$PYTHON_TARGET" ]; then
            echo "⚠️  Virtual environment Python symlink is broken (target missing)"
            echo "   Recreating virtual environment..."
            rm -rf "$ENV_NAME"
            python3 -m venv "$ENV_NAME"
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

    # Priority 2: Try venv/bin/python
    if [ -z "$PYTHON" ]; then
        if [ -e "$ENV_NAME/bin/python" ]; then
            PYTHON="$ENV_NAME/bin/python"
        elif [ -e "$ENV_NAME/bin/python3" ]; then
            PYTHON="$ENV_NAME/bin/python3"
        fi
    fi

    # Priority 3: System python3
    if [ -z "$PYTHON" ]; then
        PYTHON="$(command -v python3 2>/dev/null)"
        if [ -n "$PYTHON" ]; then
            echo "⚠️  Using system python3: $PYTHON"
        fi
    fi

    # Verify we found a Python
    if [ -z "$PYTHON" ] || [ ! -x "$PYTHON" ]; then
        echo "❌ Could not find a working Python executable"
        echo "   Checked:"
        [ -n "$VIRTUAL_ENV" ] && echo "   - Activated venv: $VIRTUAL_ENV"
        echo "   - $ENV_NAME/bin/python"
        echo "   - $ENV_NAME/bin/python3"
        echo "   - system python3"
        echo ""
        echo "💡 Try activating your venv first: source $ENV_NAME/bin/activate"
        exit 1
    fi
fi

# Re-enable exit on error for rest of script
set -e

echo "📦 Using Python: $PYTHON"
echo "   Version: $($PYTHON --version)"
if [ "$USE_CONDA" = true ]; then
    echo "   Environment Manager: Conda"
else
    echo "   Environment Manager: venv"
fi

# Upgrade pip
echo ""
echo "⬆️  Upgrading pip..."
if [ "$USE_CONDA" = true ]; then
    conda run -n "$ENV_NAME" python -m pip install --upgrade pip --quiet
else
    $PYTHON -m pip install --upgrade pip --quiet
fi

# Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    echo "❌ requirements.txt not found in $SCRIPT_DIR"
    exit 1
fi

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
echo "   This may take several minutes (downloading models: BGE large ~1.34GB, BGE reranker ~2.24GB)..."
echo ""

if [ "$USE_CONDA" = true ]; then
    # Try to install common packages via conda first (faster and better compatibility)
    echo "   → Installing conda packages (where available)..."
    conda install -n "$ENV_NAME" -c conda-forge -y \
        numpy pandas pyarrow pillow pyyaml pytest beautifulsoup4 2>/dev/null || true

    # Install remaining packages via pip in conda environment
    echo ""
    echo "   → Installing remaining packages via pip..."
    conda run -n "$ENV_NAME" pip install -r requirements.txt
else
    # Standard pip installation in venv
    $PYTHON -m pip install -r requirements.txt
fi

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
    import pandas
    print(f'✅ Pandas: {pandas.__version__}')
except ImportError as e:
    print(f'⚠️  Pandas: {e}')

try:
    import PIL
    print('✅ Pillow (PIL): Available')
except ImportError as e:
    print(f'⚠️  Pillow: {e}')

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
echo "📝 Next steps:"
echo ""
echo "1️⃣  Set your GEMINI_API_KEY in .env file:"
echo "   echo 'GEMINI_API_KEY=your_api_key_here' > .env"
echo ""
if [ "$USE_CONDA" = true ]; then
    echo "2️⃣  Activate the conda environment:"
    echo "   conda activate $ENV_NAME"
else
    echo "2️⃣  Activate the virtual environment:"
    echo "   source $ENV_NAME/bin/activate"
fi
echo ""
echo "3️⃣  Run the game:"
echo "   python3 haystack_dnd_game.py"
echo ""
echo "📦 Installed packages:"
echo "   - Haystack Framework (haystack-ai, qdrant-haystack)"
echo "   - Google Gemini AI (google-generativeai)"
echo "   - Embeddings (sentence-transformers with BGE models)"
echo "   - Vector DB (qdrant-client)"
echo "   - Document Processing (docling, pandas, pyarrow, pillow)"
echo "   - And more... (see requirements.txt)"
echo ""
if [ "$USE_CONDA" = true ]; then
    echo "🔧 Environment Manager: Conda ($ENV_NAME)"
    echo "   To activate: conda activate $ENV_NAME"
    echo "   To deactivate: conda deactivate"
    echo "   To list envs: conda env list"
else
    echo "🔧 Environment Manager: venv ($ENV_NAME)"
    echo "   To activate: source $ENV_NAME/bin/activate"
    echo "   To deactivate: deactivate"
fi
echo ""
echo "🤖 Models that will be downloaded on first use:"
echo "   - BAAI/bge-large-en-v1.5 (~1.34GB)"
echo "   - BAAI/bge-reranker-v2-m3 (~2.24GB)"
echo ""

