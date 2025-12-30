#!/bin/bash

# Script to create a fresh git repository without history
# This solves the problem of sensitive data in git history

set -e  # Exit on error

echo "=========================================="
echo "Creating Fresh Repository (No History)"
echo "=========================================="
echo ""

# Get the current directory name
CURRENT_DIR=$(basename "$(pwd)")
PARENT_DIR=$(dirname "$(pwd)")

# Step 1: Remove the old .git directory
echo "Step 1: Removing old git history..."
if [ -d ".git" ]; then
    rm -rf .git
    echo "✓ Removed .git directory"
else
    echo "✓ No .git directory found"
fi

# Step 2: Initialize a fresh git repository
echo ""
echo "Step 2: Initializing fresh git repository..."
git init
echo "✓ Fresh git repository initialized"

# Step 3: Add all files
echo ""
echo "Step 3: Adding all files..."
git add .
echo "✓ All files added"

# Step 4: Create initial commit
echo ""
echo "Step 4: Creating initial commit..."
git commit -m "Initial commit - fresh repository without history"
echo "✓ Initial commit created"

# Step 5: Display next steps
echo ""
echo "=========================================="
echo "✓ Fresh repository created successfully!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Go to GitHub and create a NEW repository (do NOT initialize with README)"
echo "2. Copy the repository URL (e.g., https://github.com/username/new-repo-name.git)"
echo "3. Run the following commands:"
echo ""
echo "   git remote add origin <YOUR_NEW_REPO_URL>"
echo "   git branch -M main"
echo "   git push -u origin main"
echo ""
echo "4. After verifying the new repo works, delete the old repository:"
echo "   https://github.com/swathip146/roshar-dnd"
echo ""
echo "⚠️  IMPORTANT: Make sure your .gitignore is properly configured"
echo "   to exclude sensitive files before pushing!"
echo ""

