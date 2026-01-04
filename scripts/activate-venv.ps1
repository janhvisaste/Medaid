# Activate Virtual Environment
Write-Host "🔧 Activating virtual environment..." -ForegroundColor Cyan
& "D:\medaid-full stack\backend\venv\Scripts\Activate.ps1"

Write-Host "✅ Virtual environment activated!" -ForegroundColor Green
Write-Host "📦 Python: $(python --version)" -ForegroundColor Yellow
Write-Host "📍 Location: $(Get-Location)" -ForegroundColor Yellow
Write-Host ""
Write-Host "You can now run Django commands:" -ForegroundColor Cyan
Write-Host "  cd backend\medaid" -ForegroundColor White
Write-Host "  python manage.py runserver" -ForegroundColor White
Write-Host "  python manage.py migrate" -ForegroundColor White
Write-Host "  python manage.py createsuperuser" -ForegroundColor White
