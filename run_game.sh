#!/bin/bash
# Script to run the D&D game with proper environment setup

cd "$(dirname "$0")"

# Virtual environment name
ENV_NAME=".venv"

# Load environment variables from .env file
if [ -f ".env" ]; then
    echo "✅ Loading environment variables from .env..."
    export $(grep -v '^#' .env | xargs)
fi

# Check if conda is available
if command -v conda &> /dev/null; then
    # Check if conda environment exists
    if conda env list | grep -q "^${ENV_NAME} "; then
        echo "✅ Activating conda environment ($ENV_NAME)..."
        # Note: conda activate doesn't work in scripts, use conda run instead
        CONDA_ENV_EXISTS=true
    else
        echo "⚠️  Conda environment '$ENV_NAME' not found."
        echo "   Run ./install_dependencies.sh first to create it."
        exit 1
    fi
else
    # Check if venv exists
    if [ -d "$ENV_NAME" ]; then
        echo "✅ Activating virtual environment ($ENV_NAME)..."
        source "$ENV_NAME/bin/activate"
    else
        echo "⚠️  No virtual environment found at '$ENV_NAME'."
        echo "   Run ./install_dependencies.sh first to create it."
        exit 1
    fi
fi

# Check for GEMINI_API_KEY
if [ -z "$GEMINI_API_KEY" ]; then
    echo "⚠️  Warning: GEMINI_API_KEY environment variable not set"
    echo "   The game may not work properly without it."
    echo "   Add it to .env file: echo 'GEMINI_API_KEY=your_key_here' > .env"
    echo ""
fi

# Run the game
echo "🎲 Starting D&D Game..."
echo ""

if [ "$CONDA_ENV_EXISTS" = true ]; then
    # Use conda run to execute in the conda environment
    conda run -n "$ENV_NAME" --no-capture-output python haystack_dnd_game.py
else
    # Use activated venv
    python3 haystack_dnd_game.py
fi

