#!/bin/bash

# Script to run MCP Inspector for Gemini PDF MCP Server
# Usage: ./run_inspector.sh

set -e

echo "=========================================="
echo "MCP Inspector - Gemini PDF Server"
echo "=========================================="

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found!"
    echo "Creating .env from env.example..."
    cp env.example .env
    echo "❗ Please edit .env and add your GEMINI_API_KEY"
    exit 1
fi

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Check if MCP Inspector is installed
if ! command -v npx &> /dev/null; then
    echo "❌ Error: npx not found. Please install Node.js first."
    echo "Visit: https://nodejs.org/"
    exit 1
fi

# Run MCP Inspector
echo ""
echo "🚀 Starting MCP Inspector..."
echo "=========================================="
echo ""

npx @modelcontextprotocol/inspector python main.py

# Deactivate venv on exit
deactivate


