#!/bin/bash

# MedAid Full Stack Startup Script
# This script starts both backend and frontend servers

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get the script directory (where this script is located)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo -e "${CYAN}📍 Script directory: ${SCRIPT_DIR}${NC}"

BACKEND_PID=""
FRONTEND_PID=""
SHUTTING_DOWN=false

# Function to cleanup background processes on script exit
cleanup() {
    if [[ "$SHUTTING_DOWN" == true ]]; then
        return
    fi
    SHUTTING_DOWN=true

    echo -e "\n${YELLOW}🛑 Shutting down MedAid servers...${NC}"
    
    # Kill backend process if it exists
    if [[ ! -z "$BACKEND_PID" ]]; then
        echo -e "${YELLOW}⏹️  Stopping backend server (PID: $BACKEND_PID)...${NC}"
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
    
    # Kill frontend process if it exists
    if [[ ! -z "$FRONTEND_PID" ]]; then
        echo -e "${YELLOW}⏹️  Stopping frontend server (PID: $FRONTEND_PID)...${NC}"
        kill "$FRONTEND_PID" 2>/dev/null || true
    fi

    wait "$BACKEND_PID" 2>/dev/null || true
    wait "$FRONTEND_PID" 2>/dev/null || true
    
    echo -e "${GREEN}✅ MedAid servers stopped successfully!${NC}"
}

# Set trap to cleanup on script exit
trap cleanup SIGINT SIGTERM EXIT

echo -e "${CYAN}🏥 Starting MedAid Full Stack Application...${NC}\n"

# Port Cleanup
echo -e "${YELLOW}🧹 Cleaning up ports 3000, 8000, 8001...${NC}"
lsof -ti:3000 | xargs kill -9 2>/dev/null || true
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
lsof -ti:8001 | xargs kill -9 2>/dev/null || true

if ! command -v npm >/dev/null 2>&1; then
    echo -e "${RED}❌ npm is not installed or not in PATH.${NC}"
    exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
    echo -e "${RED}❌ curl is not installed or not in PATH.${NC}"
    exit 1
fi

# Check if virtual environment exists
VENV_PATH="${SCRIPT_DIR}/venv"
if [[ ! -d "$VENV_PATH" ]]; then
    echo -e "${RED}❌ Virtual environment not found at: ${VENV_PATH}${NC}"
    echo -e "${YELLOW}💡 Please create a virtual environment first:${NC}"
    echo -e "${YELLOW}   python -m venv venv${NC}"
    echo -e "${YELLOW}   source venv/bin/activate${NC}"
    echo -e "${YELLOW}   pip install -r backend/requirements.txt${NC}"
    exit 1
fi

if [[ ! -f "${VENV_PATH}/bin/activate" ]]; then
    echo -e "${RED}❌ Virtual environment activation script not found: ${VENV_PATH}/bin/activate${NC}"
    exit 1
fi

BACKEND_DIR="${SCRIPT_DIR}/backend/medaid"
FRONTEND_DIR="${SCRIPT_DIR}/frontend"

if [[ ! -d "$BACKEND_DIR" || ! -f "$BACKEND_DIR/manage.py" ]]; then
    echo -e "${RED}❌ Backend app not found at: ${BACKEND_DIR}${NC}"
    exit 1
fi

if [[ ! -d "$FRONTEND_DIR" || ! -f "$FRONTEND_DIR/package.json" ]]; then
    echo -e "${RED}❌ Frontend app not found at: ${FRONTEND_DIR}${NC}"
    exit 1
fi

# Run Database Migrations
echo -e "${CYAN}🔄 Running Database Migrations...${NC}"
cd "${SCRIPT_DIR}/backend/medaid"
(
    source "${VENV_PATH}/bin/activate"
    python manage.py makemigrations
    python manage.py migrate
)
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Database migrations failed.${NC}"
    exit 1
fi

# Start Backend Server
echo -e "${CYAN}🔧 Starting Backend Server...${NC}"
cd "${SCRIPT_DIR}/backend/medaid"

# Activate virtual environment and start Django server in background
(
    source "${VENV_PATH}/bin/activate"
    echo -e "${GREEN}✅ Virtual environment activated!${NC}"
    echo -e "${YELLOW}📦 Python: $(python --version)${NC}"
    echo -e "${CYAN}🚀 Starting Django server on http://127.0.0.1:8001/...${NC}\n"
    python manage.py runserver 8001 > backend.log 2>&1
) &

BACKEND_PID=$!
echo -e "${GREEN}✅ Backend server started (PID: $BACKEND_PID)${NC}"

# Wait for backend to become reachable
echo -e "${CYAN}⏳ Waiting for backend to become available...${NC}"
BACKEND_READY=false
for _ in {1..30}; do
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo -e "${RED}❌ Backend process died unexpectedly!${NC}"
        cat backend.log
        break
    fi

    if curl --max-time 2 -s -o /dev/null "http://127.0.0.1:8001/"; then
        BACKEND_READY=true
        break
    fi

    sleep 1
done

if [[ "$BACKEND_READY" != true ]]; then
    echo -e "${RED}❌ Backend did not start successfully on http://127.0.0.1:8001.${NC}"
    echo -e "${YELLOW}💡 Check DB/env setup. Current project expects PostgreSQL on localhost:5432.${NC}"
    exit 1
fi

# Start Frontend Server
echo -e "${CYAN}🔧 Starting Frontend Server...${NC}"
cd "$FRONTEND_DIR"

# Check if node_modules exists
if [[ ! -d "node_modules" ]]; then
    echo -e "${YELLOW}📦 Installing frontend dependencies...${NC}"
    npm install
fi

# Start React development server in background
(
    echo -e "${CYAN}🚀 Starting React development server on http://localhost:8000/...${NC}\n"
    PORT=8000 npm start
) &

FRONTEND_PID=$!
echo -e "${GREEN}✅ Frontend server started (PID: $FRONTEND_PID)${NC}\n"

# Wait for frontend to become reachable
echo -e "${CYAN}⏳ Waiting for frontend to become available...${NC}"
FRONTEND_READY=false
for _ in {1..60}; do
    if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
        break
    fi

    if curl --max-time 2 -s -o /dev/null "http://localhost:8000/"; then
        FRONTEND_READY=true
        break
    fi

    sleep 1
done

if [[ "$FRONTEND_READY" != true ]]; then
    echo -e "${RED}❌ Frontend did not start successfully on http://localhost:8000.${NC}"
    exit 1
fi

# Display status and URLs
echo -e "${GREEN}🎉 MedAid servers are now running!${NC}"
echo -e "${BLUE}───────────────────────────────────────${NC}"
echo -e "${CYAN}🌐 Frontend: ${NC}http://localhost:8000"
echo -e "${CYAN}🔧 Backend:  ${NC}http://127.0.0.1:8001"
echo -e "${CYAN}📊 Admin:    ${NC}http://127.0.0.1:8001/admin"
echo -e "${BLUE}───────────────────────────────────────${NC}"
echo -e "${YELLOW}💡 Press Ctrl+C to stop both servers${NC}\n"

# Wait for both processes (this keeps the script running)
while true; do
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo -e "\n${RED}❌ Backend server exited unexpectedly.${NC}"
        exit 1
    fi

    if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
        echo -e "\n${RED}❌ Frontend server exited unexpectedly.${NC}"
        exit 1
    fi

    sleep 2
done