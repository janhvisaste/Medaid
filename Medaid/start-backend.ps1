# Activate Virtual Environment and Start Backend
Write-Host "🔧 Activating full-stack virtual environment..." -ForegroundColor Cyan
& "D:\medaid-full stack\full-stack\Scripts\Activate.ps1"

Write-Host "✅ Virtual environment activated!" -ForegroundColor Green
Write-Host "📦 Python: $(python --version)" -ForegroundColor Yellow
Write-Host ""
Write-Host "🚀 Starting Django server..." -ForegroundColor Cyan
cd "D:\medaid-full stack\Medaid\backend\medaid"
python manage.py runserver
