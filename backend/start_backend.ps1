# MedAid Backend Startup Script
Write-Host "Starting MedAid Backend Server..." -ForegroundColor Green
Set-Location medaid
& ..\..\venv\Scripts\Activate.ps1
python manage.py runserver
