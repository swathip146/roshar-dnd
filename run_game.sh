#!/bin/bash
# Script to run the D&D game with proper environment setup

cd "$(dirname "$0")"

# Check if virtual environment exists
if [ -d ".venv" ]; then
    echo "✅ Activating virtual environment..."
    source .venv/bin/activate
else
    echo "⚠️ No virtual environment found. Using system Python."
fi

# Check for GEMINI_API_KEY
if [ -z "$GEMINI_API_KEY" ]; then
    echo "⚠️ Warning: GEMINI_API_KEY environment variable not set"
    echo "   The game may not work properly without it."
    echo "   Set it with: export GEMINI_API_KEY=your_api_key_here"
    echo ""
fi

# Run the game
echo "🎲 Starting D&D Game..."
echo ""
python3 haystack_dnd_game.py

