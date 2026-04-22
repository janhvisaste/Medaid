@echo off
REM MedAid Full Stack Startup Script (Simple Batch Version)
REM This script starts both backend and frontend servers

echo 🏥 Starting MedAid Full Stack Application...
echo.

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"
echo 📍 Script directory: %SCRIPT_DIR%

REM Check if virtual environment exists
if not exist "%SCRIPT_DIR%venv" (
    echo ❌ Virtual environment not found!
    echo 💡 Please create a virtual environment first:
    echo    python -m venv venv
    echo    venv\Scripts\activate.bat
    echo    pip install -r backend\requirements.txt
    pause
    exit /b 1
)

echo 🔧 Starting Backend Server...
REM Start backend in a new window
start "MedAid Backend" cmd /k "cd /d "%SCRIPT_DIR%backend\medaid" && "%SCRIPT_DIR%venv\Scripts\activate.bat" && echo ✅ Virtual environment activated! && python --version && echo 🚀 Starting Django server on http://127.0.0.1:8000/... && python manage.py runserver"

echo ✅ Backend server window opened!

REM Wait a moment for backend to initialize
timeout /t 3 /nobreak >nul

echo 🔧 Starting Frontend Server...
REM Start frontend in a new window  
start "MedAid Frontend" cmd /k "cd /d "%SCRIPT_DIR%frontend" && echo 🚀 Starting React development server on http://localhost:3000/... && npm start"

echo ✅ Frontend server window opened!

echo.
echo 🎉 MedAid servers are now running!
echo ───────────────────────────────────────
echo 🌐 Frontend: http://localhost:3000
echo 🔧 Backend:  http://127.0.0.1:8000  
echo 📊 Admin:    http://127.0.0.1:8000/admin
echo ───────────────────────────────────────
echo 💡 Close the terminal windows to stop the servers
echo.
pause