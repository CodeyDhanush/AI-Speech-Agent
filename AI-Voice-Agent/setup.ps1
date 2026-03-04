# ═════════════════════════════════════════════════════════════════════════════
# Enterprise Voice AI Gateway — Setup Script (Windows)
# ═════════════════════════════════════════════════════════════════════════════

Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  Enterprise Voice AI Gateway - Setup                          ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Check Python
Write-Host "✓ Checking Python installation..." -ForegroundColor Green
$python = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Python not found! Please install Python 3.9+" -ForegroundColor Red
    exit 1
}
Write-Host "  Found: $python" -ForegroundColor Green
Write-Host ""

# Create venv
if (-not (Test-Path "venv")) {
    Write-Host "✓ Creating virtual environment..." -ForegroundColor Green
    python -m venv venv
} else {
    Write-Host "✓ Virtual environment exists" -ForegroundColor Green
}
Write-Host ""

# Activate venv
Write-Host "✓ Activating virtual environment..." -ForegroundColor Green
& ".\venv\Scripts\Activate.ps1"
Write-Host ""

# Install requirements
Write-Host "✓ Installing dependencies..." -ForegroundColor Green
pip install -r requirements.txt --quiet
Write-Host ""

# Check FFmpeg
$ffmpeg = ffmpeg -version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ FFmpeg found" -ForegroundColor Green
} else {
    Write-Host "⚠ FFmpeg not found (optional, needed for audio)" -ForegroundColor Yellow
    Write-Host "  Download: https://ffmpeg.org/download.html" -ForegroundColor Yellow
}
Write-Host ""

# Check .env
if (-not (Test-Path ".env")) {
    Write-Host "✓ Creating .env file..." -ForegroundColor Green
    Copy-Item ".env.example" ".env"
    Write-Host "  IMPORTANT: Edit .env with your credentials:" -ForegroundColor Yellow
    Write-Host "  - TWILIO_ACCOUNT_SID" -ForegroundColor Yellow
    Write-Host "  - TWILIO_AUTH_TOKEN" -ForegroundColor Yellow
    Write-Host "  - OPENAI_API_KEY" -ForegroundColor Yellow
} else {
    Write-Host "✓ .env file exists" -ForegroundColor Green
}
Write-Host ""

# Seed database
Write-Host "✓ Initializing database..." -ForegroundColor Green
python seed_demo_data.py
Write-Host ""

Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║  ✓ Setup Complete!                                           ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Green
Write-Host "  1. Edit .env with your Twilio & OpenAI credentials" -ForegroundColor Green
Write-Host "  2. Run: python main.py" -ForegroundColor Green
Write-Host "  3. Open: http://localhost:8000" -ForegroundColor Green
Write-Host ""
Write-Host "Documentation:" -ForegroundColor Cyan
Write-Host "  - API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "  - README: README.md" -ForegroundColor Cyan
Write-Host ""
