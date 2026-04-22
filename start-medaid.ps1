# MedAid Full Stack Startup Script
# This script starts both backend and frontend servers

# Set error action preference
$ErrorActionPreference = "Stop"

# Get the script directory (where this script is located)
$ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "📍 Script directory: $ScriptPath" -ForegroundColor Cyan

# Global variables for process management
$BackendProcess = $null
$FrontendProcess = $null

# Function to cleanup background processes on script exit
function Cleanup {
    Write-Host "`n🛑 Shutting down MedAid servers..." -ForegroundColor Yellow
    
    # Stop backend process if it exists
    if ($BackendProcess -and !$BackendProcess.HasExited) {
        Write-Host "⏹️  Stopping backend server (PID: $($BackendProcess.Id))..." -ForegroundColor Yellow
        $BackendProcess.Kill()
        $BackendProcess.WaitForExit(5000)  # Wait up to 5 seconds
    }
    
    # Stop frontend process if it exists  
    if ($FrontendProcess -and !$FrontendProcess.HasExited) {
        Write-Host "⏹️  Stopping frontend server (PID: $($FrontendProcess.Id))..." -ForegroundColor Yellow
        $FrontendProcess.Kill()
        $FrontendProcess.WaitForExit(5000)  # Wait up to 5 seconds
    }
    
    Write-Host "✅ MedAid servers stopped successfully!" -ForegroundColor Green
}

# Register cleanup function for Ctrl+C
$null = Register-EngineEvent PowerShell.Exiting -Action { Cleanup } 

try {
    Write-Host "🏥 Starting MedAid Full Stack Application...`n" -ForegroundColor Cyan

    # Check if virtual environment exists
    $VenvPath = Join-Path $ScriptPath "venv"
    if (!(Test-Path $VenvPath)) {
        Write-Host "❌ Virtual environment not found at: $VenvPath" -ForegroundColor Red
        Write-Host "💡 Please create a virtual environment first:" -ForegroundColor Yellow
        Write-Host "   python -m venv venv" -ForegroundColor Yellow
        Write-Host "   .\venv\Scripts\Activate.ps1" -ForegroundColor Yellow
        Write-Host "   pip install -r backend\requirements.txt" -ForegroundColor Yellow
        exit 1
    }

    # Start Backend Server
    Write-Host "🔧 Starting Backend Server..." -ForegroundColor Cyan
    $BackendPath = Join-Path $ScriptPath "backend\medaid"
    
    # Create backend startup script
    $BackendScript = @"
& '$VenvPath\Scripts\Activate.ps1'
Write-Host '✅ Virtual environment activated!' -ForegroundColor Green
Write-Host '📦 Python: ' -NoNewline -ForegroundColor Yellow
python --version
Write-Host '🚀 Starting Django server on http://127.0.0.1:8000/...' -ForegroundColor Cyan
Set-Location '$BackendPath'
python manage.py runserver
"@

    # Start backend in new PowerShell window
    $BackendProcess = Start-Process -FilePath "powershell" -ArgumentList "-Command", $BackendScript -PassThru -WindowStyle Normal
    Write-Host "✅ Backend server started (PID: $($BackendProcess.Id))" -ForegroundColor Green

    # Wait a moment for backend to initialize
    Start-Sleep -Seconds 3

    # Start Frontend Server
    Write-Host "🔧 Starting Frontend Server..." -ForegroundColor Cyan
    $FrontendPath = Join-Path $ScriptPath "frontend"
    
    # Check if node_modules exists
    $NodeModulesPath = Join-Path $FrontendPath "node_modules"
    if (!(Test-Path $NodeModulesPath)) {
        Write-Host "📦 Installing frontend dependencies..." -ForegroundColor Yellow
        Set-Location $FrontendPath
        npm install
    }

    # Create frontend startup script
    $FrontendScript = @"
Write-Host '🚀 Starting React development server on http://localhost:3000/...' -ForegroundColor Cyan
Set-Location '$FrontendPath'
npm start
"@

    # Start frontend in new PowerShell window
    $FrontendProcess = Start-Process -FilePath "powershell" -ArgumentList "-Command", $FrontendScript -PassThru -WindowStyle Normal
    Write-Host "✅ Frontend server started (PID: $($FrontendProcess.Id))" -ForegroundColor Green

    # Display status and URLs
    Write-Host "`n🎉 MedAid servers are now running!" -ForegroundColor Green
    Write-Host "───────────────────────────────────────" -ForegroundColor Blue
    Write-Host "🌐 Frontend: " -NoNewline -ForegroundColor Cyan
    Write-Host "http://localhost:3000"
    Write-Host "🔧 Backend:  " -NoNewline -ForegroundColor Cyan  
    Write-Host "http://127.0.0.1:8000"
    Write-Host "📊 Admin:    " -NoNewline -ForegroundColor Cyan
    Write-Host "http://127.0.0.1:8000/admin"
    Write-Host "───────────────────────────────────────" -ForegroundColor Blue
    Write-Host "💡 Press Ctrl+C to stop both servers`n" -ForegroundColor Yellow

    # Wait for user input to keep script alive
    Write-Host "⏸️  Press any key to stop all servers..." -ForegroundColor Yellow
    $null = Read-Host

} catch {
    Write-Host "❌ An error occurred: $($_.Exception.Message)" -ForegroundColor Red
} finally {
    # Cleanup is called automatically via the registered event
    Cleanup
}