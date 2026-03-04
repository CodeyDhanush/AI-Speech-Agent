#!/bin/bash
# ═════════════════════════════════════════════════════════════════════════════
# Enterprise Voice AI Gateway — Setup Script (Linux/Mac)
# ═════════════════════════════════════════════════════════════════════════════

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  Enterprise Voice AI Gateway - Setup                          ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check Python
echo "✓ Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "✗ Python 3 not found! Please install Python 3.9+"
    exit 1
fi
PYTHON_VERSION=$(python3 --version)
echo "  Found: $PYTHON_VERSION"
echo ""

# Create venv
if [ ! -d "venv" ]; then
    echo "✓ Creating virtual environment..."
    python3 -m venv venv
else
    echo "✓ Virtual environment exists"
fi
echo ""

# Activate venv
echo "✓ Activating virtual environment..."
source venv/bin/activate
echo ""

# Install requirements
echo "✓ Installing dependencies..."
pip install -r requirements.txt --quiet
echo ""

# Check FFmpeg
if command -v ffmpeg &> /dev/null; then
    echo "✓ FFmpeg found"
else
    echo "⚠ FFmpeg not found (optional, needed for audio)"
    echo "  Install: brew install ffmpeg (Mac) or apt install ffmpeg (Linux)"
fi
echo ""

# Check .env
if [ ! -f ".env" ]; then
    echo "✓ Creating .env file..."
    cp .env.example .env
    echo "  IMPORTANT: Edit .env with your credentials:"
    echo "  - TWILIO_ACCOUNT_SID"
    echo "  - TWILIO_AUTH_TOKEN"
    echo "  - OPENAI_API_KEY"
else
    echo "✓ .env file exists"
fi
echo ""

# Seed database
echo "✓ Initializing database..."
python seed_demo_data.py
echo ""

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  ✓ Setup Complete!                                           ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo "  1. Edit .env with your Twilio & OpenAI credentials"
echo "  2. Run: python main.py"
echo "  3. Open: http://localhost:8000"
echo ""
echo "Documentation:"
echo "  - API Docs: http://localhost:8000/docs"
echo "  - README: README.md"
echo ""
