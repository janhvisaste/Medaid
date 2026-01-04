# 🏥 MedAid - AI-Powered Medical Triage System

A complete full-stack medical triage and patient monitoring system with AI-powered symptom assessment, clinician dashboard, and comprehensive health tracking.

## ✨ Features

### For Patients
- 🔍 **AI-Powered Symptom Assessment** - Intelligent triage using Google Gemini AI
- 📝 **Multi-Step Consultation** - Guided symptom collection with clarifying questions
- 📋 **Medical History Management** - Track 15+ medical conditions with notes
- 📄 **PDF Reports** - Download detailed assessment reports and health passport
- 🥗 **Dietary Recommendations** - Personalized nutrition advice based on conditions
- 🏥 **Facility Finder** - Locate nearby healthcare facilities
- 📊 **Assessment History** - View all past consultations and results

### For Clinicians
- 👥 **Patient Dashboard** - Real-time monitoring of assigned patients
- 🚨 **Priority Management** - Track emergency, high-risk, and medium-risk patients
- 🔍 **Advanced Filters** - Search and filter patients by risk level, status, date
- 📝 **Clinical Notes** - Add private notes to patient records
- 🔔 **Alert System** - Get notified about critical cases
- 📈 **Statistics** - View dashboard metrics and patient counts

## 🛠️ Tech Stack

### Backend
- **Framework:** Django 5.2.4 with Django REST Framework
- **Database:** PostgreSQL
- **Authentication:** JWT with SimpleJWT
- **AI:** Google Gemini API via `google-genai`
- **PDF Generation:** ReportLab
- **CORS:** django-cors-headers

### Frontend
- **Framework:** React 19.1.1 with TypeScript
- **Styling:** Tailwind CSS
- **Animations:** Framer Motion
- **HTTP Client:** Axios
- **Icons:** Lucide React
- **Routing:** React Router v7

## 📁 Project Structure

```
Medaid/
├── backend/                    # Django backend
│   └── medaid/
│       ├── api/               # API app
│       │   ├── models.py      # Database models
│       │   ├── views.py       # API endpoints
│       │   ├── serializers.py # DRF serializers
│       │   ├── triage_engine.py # AI triage logic
│       │   └── report_generator.py # PDF generation
│       └── medaid/            # Django settings
│           ├── settings.py
│           └── urls.py
├── frontend/                   # React frontend
│   └── src/
│       ├── components/        # UI components
│       │   ├── Auth/         # Login/Signup
│       │   ├── Consultation/ # Assessment wizard
│       │   ├── Clinician/    # Clinician dashboard
│       │   ├── Profile/      # Medical history
│       │   ├── Reports/      # PDF downloads
│       │   └── Results/      # Dietary advice
│       ├── services/
│       │   └── apiService.ts # API integration
│       └── App.tsx
└── Documentation/
    ├── README.md             # This file
    ├── QUICK_START.md        # Quick setup guide
    ├── SETUP_INSTRUCTIONS.md # Detailed setup
    ├── BACKEND_FEATURES_COMPLETE.md
    ├── FRONTEND_IMPLEMENTATION_COMPLETE.md
    ├── CLINICIAN_BACKEND_COMPLETE.md
    └── SETUP_AND_CONNECTIONS_GUIDE.md
```

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 16+
- PostgreSQL
- Google Gemini API key

### 1. Clone and Setup

```bash
git clone <repository-url>
cd Medaid
```

### 2. Backend Setup

```bash
cd backend/medaid

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
echo "DB_NAME=medaid_db
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
GOOGLE_API_KEY=your_gemini_api_key" > .env

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start server
python manage.py runserver
```

Backend runs at: **http://localhost:8000**

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Create .env file
echo "REACT_APP_API_URL=http://localhost:8000/api" > .env

# Start development server
npm start
```

Frontend runs at: **http://localhost:3000**

## 📖 Documentation

- **[QUICK_START.md](QUICK_START.md)** - Quick setup guide
- **[SETUP_INSTRUCTIONS.md](SETUP_INSTRUCTIONS.md)** - Detailed installation steps
- **[BACKEND_FEATURES_COMPLETE.md](BACKEND_FEATURES_COMPLETE.md)** - Backend API reference
- **[FRONTEND_IMPLEMENTATION_COMPLETE.md](FRONTEND_IMPLEMENTATION_COMPLETE.md)** - Frontend components guide
- **[CLINICIAN_BACKEND_COMPLETE.md](CLINICIAN_BACKEND_COMPLETE.md)** - Clinician features documentation
- **[SETUP_AND_CONNECTIONS_GUIDE.md](SETUP_AND_CONNECTIONS_GUIDE.md)** - Integration guide

## 🔐 Authentication

The system uses JWT authentication:
- Access tokens expire in 60 minutes
- Refresh tokens expire in 7 days
- Automatic token refresh on frontend

**Default roles:**
- `patient` - Standard users
- `clinician` - Healthcare providers
- `admin` - System administrators

## 📡 API Endpoints

### Patient Endpoints
- `POST /api/auth/signup/` - User registration
- `POST /api/auth/login/` - User login
- `POST /api/triage/assess/` - Symptom assessment
- `GET /api/triage/history/` - Assessment history
- `POST /api/consultation/start/` - Start consultation
- `GET /api/profile/` - Get user profile
- `PATCH /api/profile/update-history/` - Update medical history
- `GET /api/recommendations/dietary/` - Get dietary advice
- `GET /api/facilities/nearby/` - Find facilities
- `GET /api/reports/download/<id>/` - Download PDF

### Clinician Endpoints
- `GET /api/clinician/stats/` - Dashboard statistics
- `GET /api/clinician/patients/` - Patient list with filters
- `POST /api/clinician/assign-patient/` - Assign patient
- `PATCH /api/clinician/assignments/<id>/status/` - Update status
- `POST /api/clinician/notes/` - Add clinical note
- `GET /api/clinician/alerts/` - Get alerts

## 🗄️ Database Models

### Core Models
- `User` - Custom user with role field
- `UserProfile` - Extended user information
- `TriageRecord` - Assessment results
- `ConsultationSession` - Multi-step consultation data
- `MedicalReport` - Uploaded medical documents

### Clinician Models
- `PatientAssignment` - Clinician-patient relationships
- `ClinicianNote` - Clinical notes on patients
- `ClinicianAlert` - Alert notifications

### Additional Models
- `Facility` - Healthcare facilities
- `Recommendation` - Patient recommendations
- `PossibleCondition` - AI-detected conditions

## 🎨 Frontend Components

### Main Components
- `ConsultationWizard` - 4-step assessment flow
- `MedicalHistoryForm` - Checkbox-based history input
- `DietaryAdvice` - Condition-specific dietary guidance
- `PDFDownload` - Report download functionality
- `ClinicianDashboard` - Patient monitoring interface
- `Navigation` - Responsive navigation bar

## 🧪 Testing

### Backend
```bash
cd backend/medaid
python manage.py test
```

### Frontend
```bash
cd frontend
npm test
```

## 📦 Deployment

See [SETUP_INSTRUCTIONS.md](SETUP_INSTRUCTIONS.md) for production deployment guide.

**Production checklist:**
- [ ] Set `DEBUG=False` in Django settings
- [ ] Configure production `SECRET_KEY`
- [ ] Setup Gunicorn/Nginx
- [ ] Configure SSL certificates
- [ ] Setup production database
- [ ] Build frontend: `npm run build`
- [ ] Configure CORS for production domain

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/AmazingFeature`
3. Commit changes: `git commit -m 'Add AmazingFeature'`
4. Push to branch: `git push origin feature/AmazingFeature`
5. Open Pull Request

## 📝 License

This project is licensed under the MIT License.

## 👥 Team

- **Backend Development** - Django REST API, AI Integration, Database Design
- **Frontend Development** - React UI, Component Architecture, API Integration
- **AI/ML** - Triage Engine, Symptom Analysis, Recommendation System

## 📞 Support

For issues and questions:
- Create an issue in the repository
- Check existing documentation
- Review API endpoint documentation

## 🎉 Status

**Current Version:** 1.0.0  
**Status:** ✅ Production Ready

**Completed Features:**
- ✅ User authentication system
- ✅ AI-powered triage engine
- ✅ Multi-step consultation flow
- ✅ Medical history management
- ✅ PDF report generation
- ✅ Dietary recommendations
- ✅ Facility finder
- ✅ Clinician dashboard
- ✅ Patient monitoring system
- ✅ Real-time statistics

---

**Built with ❤️ for better healthcare accessibility**