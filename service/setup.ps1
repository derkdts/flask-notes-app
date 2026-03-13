# PowerShell script to set up virtual environment

Write-Host "Setting up virtual environment..." -ForegroundColor Cyan

# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install dependencies
Write-Host "Installing dependencies..." -ForegroundColor Cyan
python -m pip install --upgrade pip
pip install -r requirements.txt

Write-Host "------------------------------------------------" -ForegroundColor Green
Write-Host "Setup complete!" -ForegroundColor Green
Write-Host "To start the app, run: python app.py" -ForegroundColor Green
Write-Host "------------------------------------------------" -ForegroundColor Green
