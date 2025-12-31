#!/bin/bash
# Script to run the 3-round game test

# Change to script directory
cd "$(dirname "$0")"

# Disable HuggingFace connection issues by using offline mode
export TRANSFORMERS_OFFLINE=0
export HF_HUB_OFFLINE=0

# Load .env file
if [ -f .env ]; then
    export $(cat .env | xargs)
fi

# Run the test
python3 test_game_3_rounds.py
