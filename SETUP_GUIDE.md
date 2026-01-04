# 🚀 MedAid - Complete Setup Guide

## Project Structure Overview

The project has been cleaned and organized with the following structure:

```
medaid-full stack/
├── backend/              # Django backend with Python virtual environment
├── frontend/             # React frontend
└── scripts/              # Utility scripts for quick startup
```

## 📋 Prerequisites

Before starting, ensure you have:
- **Python 3.10+** installed
- **Node.js 16+** and npm installed
- **PostgreSQL** database server running
- **Google Gemini API key** (get from https://makersuite.google.com/app/apikey)

## 🔧 Initial Setup (First Time Only)

### Step 1: Database Setup

1. Install and start PostgreSQL
2. Create the database:

```sql
CREATE DATABASE medaid_db;
CREATE USER postgres WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE medaid_db TO postgres;
```

### Step 2: Backend Configuration

1. Navigate to backend:
```bash
cd backend/medaid
```

2. Create `.env` file with your configuration:
```env
DB_NAME=medaid_db
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
GOOGLE_API_KEY=your_gemini_api_key_here
SECRET_KEY=your-secret-key-here
DEBUG=True
```

3. Activate virtual environment and install dependencies:

**Windows:**
```powershell
..\venv\Scripts\activate
pip install -r requirements.txt
```

**Linux/Mac:**
```bash
source ../venv/bin/activate
pip install -r requirements.txt
```

4. Run database migrations:
```bash
python manage.py migrate
```

5. Create a superuser account:
```bash
python manage.py createsuperuser
```

### Step 3: Frontend Configuration

1. Navigate to frontend:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Create `.env` file:
```env
REACT_APP_API_URL=http://localhost:8000/api
```

## 🚀 Running the Application

### Option 1: Using Convenience Scripts (Recommended for Windows)

**Terminal 1 - Backend:**
```powershell
.\scripts\start-backend.ps1
```

**Terminal 2 - Frontend:**
```powershell
.\scripts\start-frontend.ps1
```

### Option 2: Manual Start

**Terminal 1 - Backend:**
```bash
cd backend/medaid
# Activate venv first
python manage.py runserver
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm start
```

## 🌐 Access the Application

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **Django Admin:** http://localhost:8000/admin

## 👤 Test Accounts

After running migrations, you can create test accounts:

### Create Clinician Account:
```bash
python manage.py shell
```
```python
from django.contrib.auth.models import User
from api.models import Profile

# Create clinician user
user = User.objects.create_user(
    username='dr.smith',
    email='drsmith@medaid.com',
    password='test123',
    first_name='John',
    last_name='Smith'
)

# Set as clinician
profile = Profile.objects.get(user=user)
profile.is_clinician = True
profile.save()
```

### Create Patient Account:
Use the signup form at http://localhost:3000/signup

## 🔧 Common Commands

### Backend Commands

```bash
# Activate virtual environment
cd backend
.\venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start development server
python manage.py runserver

# Access Django shell
python manage.py shell

# Run tests
python manage.py test
```

### Frontend Commands

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm start

# Build for production
npm run build

# Run tests
npm test
```

## 🐛 Troubleshooting

### Backend Issues

**Problem:** `ModuleNotFoundError: No module named 'xyz'`
- **Solution:** Ensure virtual environment is activated and run `pip install -r requirements.txt`

**Problem:** Database connection errors
- **Solution:** Check PostgreSQL is running and credentials in `.env` are correct

**Problem:** `SECRET_KEY` not set
- **Solution:** Add `SECRET_KEY=your-random-secret-key` to backend `.env` file

### Frontend Issues

**Problem:** `Cannot find module` errors
- **Solution:** Delete `node_modules` and `package-lock.json`, then run `npm install`

**Problem:** API connection refused
- **Solution:** Ensure backend is running on port 8000

**Problem:** CORS errors
- **Solution:** Verify `REACT_APP_API_URL` in frontend `.env` matches backend URL

## 📦 Dependencies

### Backend (Python)
- Django 4.2.27
- djangorestframework 3.16.1
- djangorestframework-simplejwt 5.5.1
- django-cors-headers 4.3.1
- google-genai 1.56.0
- psycopg2-binary 2.9.9
- fpdf2 2.8.5
- And more... (see requirements.txt)

### Frontend (Node.js)
- React 19.1.1
- React Router 7.9.4
- TypeScript
- Tailwind CSS
- Framer Motion 12.23.22
- Axios 1.13.2
- Lucide React 0.544.0
- And more... (see package.json)

## 🔐 Security Notes

- Never commit `.env` files to version control
- Change default passwords in production
- Use strong `SECRET_KEY` in production
- Enable HTTPS in production
- Set `DEBUG=False` in production

## 📚 Additional Documentation

For more detailed information, refer to:
- Main README.md
- Backend API documentation: `/api/docs/` (when server is running)
- Frontend component documentation in source files

## 🤝 Support

If you encounter issues:
1. Check this guide first
2. Review error messages carefully
3. Ensure all prerequisites are installed
4. Verify environment variables are set correctly
5. Check that both backend and frontend are running

---
**Happy Coding! 🎉**
