# Activate Virtual Environment and Start Backend
Write-Host "🔧 Activating virtual environment..." -ForegroundColor Cyan
& "D:\medaid-full stack\backend\venv\Scripts\Activate.ps1"

Write-Host "✅ Virtual environment activated!" -ForegroundColor Green
Write-Host "📦 Python: $(python --version)" -ForegroundColor Yellow
Write-Host ""
Write-Host "🚀 Starting Django server..." -ForegroundColor Cyan
cd "D:\medaid-full stack\backend\medaid"
python manage.py runserver
