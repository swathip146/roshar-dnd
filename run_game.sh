#!/bin/bash
# Script to run the D&D game via uv (see run_game_conda.sh for the Conda/venv path)

set -e
cd "$(dirname "$0")"

# Load environment variables from .env file. Same loader as before; note it breaks on
# values containing spaces or '#' — quote your .env values if that ever applies.
if [ -f ".env" ]; then
    echo "✅ Loading environment variables from .env..."
    export $(grep -v '^#' .env | xargs)
fi

if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed. Run ./install_dependencies.sh first, or use"
    echo "   ./run_game_conda.sh if you're on the Conda/venv path."
    exit 1
fi

if [ -z "$GEMINI_API_KEY" ]; then
    echo "⚠️  Warning: GEMINI_API_KEY environment variable not set"
    echo "   The game may not work properly without it."
    echo "   Add it to .env file: echo 'GEMINI_API_KEY=your_key_here' > .env"
    echo ""
fi

echo "🎲 Starting D&D Game..."
echo ""

# `uv run` resolves against uv.lock and runs inside .venv/ without needing it
# activated — no `conda activate` / `source .../activate` step.
uv run python haystack_dnd_game.py
