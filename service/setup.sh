#!/bin/bash

# Exit on error
set -e

echo "Setting up virtual environment..."

# Check if python3 is installed
if ! command -v python3 &> /dev/null
then
    echo "python3 could not be found. Please install Python."
    exit 1
fi

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# Note: This script runs in a subshell, so it won't activate venv for the current shell.
# But we can install dependencies inside.
source venv/Scripts/activate 2>/dev/null || source venv/bin/activate

echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "------------------------------------------------"
echo "Setup complete!"
echo "To activate the environment, run:"
echo "source venv/Scripts/activate (Git Bash/Windows)"
echo "or"
echo "source venv/bin/activate (Linux/macOS)"
echo "Then start the app with: python app.py"
echo "------------------------------------------------"
