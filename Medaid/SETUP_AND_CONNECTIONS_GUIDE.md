# MedAid - Complete Setup Guide

## 📁 Folder Structure

```
d:\medaid-full stack\Medaid\
├── backend/                       # All Django backend code
│   ├── medaid/                   # Django project root
│   │   ├── api/                  # Main API app
│   │   │   ├── models.py         # Database models
│   │   │   ├── views.py          # API endpoints
│   │   │   ├── serializers.py    # Data serializers
│   │   │   ├── triage_engine.py  # AI triage logic
│   │   │   ├── report_generator.py # PDF generation
│   │   │   └── migrations/       # Database migrations
│   │   ├── medaid/               # Django settings
│   │   │   ├── settings.py       # Configuration
│   │   │   └── urls.py           # URL routing
│   │   ├── .env                  # Environment variables
│   │   └── manage.py             # Django CLI
│   └── requirements.txt          # Python dependencies
│
└── frontend/                     # All React frontend code
    ├── src/
    │   ├── components/           # React components
    │   ├── services/
    │   │   ├── authService.ts    # Authentication
    │   │   └── apiService.ts     # All API calls
    │   ├── App.tsx
    │   └── index.tsx
    ├── public/                   # Static files
    ├── .env                      # Frontend config
    └── package.json              # Node dependencies
```

---

## ✅ Everything is Properly Organized

### Backend (Port 8000)
- **Location:** `backend/medaid/`
- **Entry Point:** `manage.py`
- **Configuration:** `.env` file with database & API keys
- **All Features:** ✅ Complete

### Frontend (Port 3000)
- **Location:** `frontend/`
- **Entry Point:** `src/index.tsx`
- **API Service:** `src/services/apiService.ts` (connects to backend)
- **Configuration:** `.env` with backend URL

---

## 🚀 How to Run Everything

### Step 1: Start Backend
```bash
cd backend/medaid
python manage.py runserver
```
✅ Backend will run on **http://localhost:8000**

### Step 2: Start Frontend
```bash
cd frontend
npm start
```
✅ Frontend will run on **http://localhost:3000**

---

## 🔗 Connections Between Frontend & Backend

### 1. API Service Layer
**File:** `frontend/src/services/apiService.ts`

This file handles ALL communication between React frontend and Django backend:

```typescript
// Automatically connects to backend at http://localhost:8000/api
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

// All API methods available:
- apiService.login(email, password)
- apiService.signup(data)
- apiService.assessSymptoms(symptoms)
- apiService.startConsultation()
- apiService.downloadAssessmentPDF(id)
- apiService.getDietaryRecommendations()
- apiService.getNearbyFacilities()
// ... and many more
```

### 2. Environment Configuration
**Backend:** `backend/medaid/.env`
```env
DB_NAME=medaid_db
DB_USER=postgres
DB_PASSWORD=Shivani123
GOOGLE_API_KEY=AIzaSyC_ydbdqRqnULcpbvSUWRzYlHZ0CTMsZww
```

**Frontend:** `frontend/.env`
```env
REACT_APP_API_URL=http://localhost:8000/api
```

### 3. CORS Configuration
**File:** `backend/medaid/medaid/settings.py`
```python
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",    # Frontend dev server
    "http://127.0.0.1:3000",
]
CORS_ALLOW_CREDENTIALS = True
```

This allows frontend at port 3000 to communicate with backend at port 8000.

---

## 📡 API Endpoints Available

All endpoints in `backend/medaid/api/views.py` are accessible from frontend via `apiService.ts`:

### Authentication
```
POST /api/auth/signup/
POST /api/auth/login/
POST /api/auth/logout/
GET  /api/auth/me/
```

### Consultation (NEW - Multi-Step Flow)
```
POST /api/consultation/start/
POST /api/consultation/<id>/submit/
GET  /api/consultation/<id>/questions/
GET  /api/consultation/active/
```

### PDF Reports (NEW)
```
GET /api/reports/download/<id>/
GET /api/reports/health-passport-pdf/
```

### Medical History (NEW)
```
POST /api/profile/update-history/
```

### Existing Features
```
POST /api/triage/assess/
GET  /api/triage/history/
GET  /api/facilities/nearby/
POST /api/recommendations/dietary/
```

---

## ✅ Verification Checklist

### Backend Health Check
```bash
# Terminal 1: Start backend
cd backend/medaid
python manage.py runserver

# Terminal 2: Test API
curl http://localhost:8000/
```

Expected response: API health check with status "ok"

### Frontend Connection Check
```bash
# Terminal 3: Start frontend
cd frontend
npm start
```

Open browser: http://localhost:3000

The frontend will automatically connect to backend at http://localhost:8000/api

---

## 🔧 How Features Work Together

### Example: User Login Flow

1. **Frontend:** User enters credentials in `LoginPage.tsx`
2. **API Call:** Component calls `apiService.login(email, password)`
3. **HTTP Request:** apiService sends POST to `http://localhost:8000/api/auth/login/`
4. **Backend:** Django view in `backend/medaid/api/views.py` handles request
5. **Response:** Backend returns JWT tokens + user data
6. **Storage:** Frontend stores tokens in localStorage
7. **Protected Routes:** All future API calls include token in Authorization header

### Example: Multi-Step Consultation

1. **Frontend:** User clicks "Start Consultation"
2. **API Call:** `apiService.startConsultation()`
3. **Backend:** Creates ConsultationSession in database
4. **Frontend:** Shows step 1 (symptoms input)
5. **Submit:** `apiService.submitConsultationStep(id, data)`
6. **Backend:** Updates session, moves to next stage
7. **Get Questions:** `apiService.getClarifyingQuestions(id)`
8. **Backend:** AI generates questions using Gemini
9. **Submit Answers:** Frontend submits, backend creates TriageRecord
10. **Results:** Frontend displays assessment + download PDF button

---

## 📦 Complete Feature Status

| Feature | Backend API | Frontend UI | Connection |
|---------|------------|-------------|------------|
| Authentication | ✅ | ✅ | ✅ |
| User Profile | ✅ | ✅ | ✅ |
| Symptom Assessment | ✅ | ✅ | ✅ |
| Multi-Step Consultation | ✅ | ❌ | ✅ (API ready) |
| Clarifying Questions | ✅ | ❌ | ✅ (API ready) |
| PDF Reports | ✅ | ❌ | ✅ (API ready) |
| Medical History Checkboxes | ✅ | ❌ | ✅ (API ready) |
| Dietary Recommendations | ✅ | ❌ | ✅ (API ready) |
| Facility Finder | ✅ | ❌ | ✅ (API ready) |

**Backend:** 100% Complete ✅  
**Frontend API Service:** 100% Complete ✅  
**Frontend UI Components:** 30% Complete (basic auth + dashboard exist)

---

## 🎯 Next Steps: Frontend UI Development

All backend APIs are ready. Frontend needs UI components:

### Priority 1: Multi-Step Consultation Wizard
```typescript
// Component structure needed:
ConsultationWizard.tsx
├── Step1_Symptoms.tsx
├── Step2_MedicalHistory.tsx
├── Step3_ClarifyingQuestions.tsx
└── Step4_Results.tsx

// API calls already available:
apiService.startConsultation()
apiService.submitConsultationStep()
apiService.getClarifyingQuestions()
```

### Priority 2: PDF Download Buttons
```typescript
// Add to results page:
const handleDownloadPDF = async (triageId: number) => {
  const blob = await apiService.downloadAssessmentPDF(triageId);
  apiService.downloadPDFFile(blob, `assessment_${triageId}.pdf`);
};
```

### Priority 3: Medical History Form
```typescript
// Component needed:
MedicalHistoryForm.tsx
// Checkbox list calling:
apiService.updateMedicalHistory(conditions)
```

---

## 🔐 Security & Authentication

### Token Flow
1. Login → Backend returns `access` + `refresh` tokens
2. Frontend stores in localStorage
3. All API calls include: `Authorization: Bearer <access_token>`
4. If token expires → Auto-refresh using refresh token
5. If refresh fails → Redirect to login

**Implementation:** Already in `apiService.ts` interceptors ✅

---

## 📊 Database Structure

### PostgreSQL Database: `medaid_db`

**Tables:**
- `auth_user` - User accounts
- `user_profile` - Extended user info
- `triage_records` - Assessment history
- `possible_conditions` - Diagnosed conditions
- `recommendations` - Action items
- `medical_reports` - Uploaded reports
- `consultation_sessions` - NEW: Multi-step consultations
- `facilities` - Healthcare facilities

**All migrations applied:** ✅

---

## 🧪 Testing the Full Stack

### Test 1: Login Flow
```bash
# Frontend: http://localhost:3000/login
# Enter credentials → API call to backend → Success

# Check browser DevTools:
Network tab → See POST to http://localhost:8000/api/auth/login/
Console tab → Should have no errors
Application tab → localStorage should have access_token
```

### Test 2: API Connection
```javascript
// Browser console:
fetch('http://localhost:8000/api/auth/me/', {
  headers: {
    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
  }
})
.then(r => r.json())
.then(console.log)
// Should return user data
```

### Test 3: New Features
```typescript
// In React component:
import apiService from '../services/apiService';

// Start consultation
const session = await apiService.startConsultation('I have a fever');
console.log(session); // Should return session object

// Download PDF
const blob = await apiService.downloadAssessmentPDF(1);
// Should download PDF file
```

---

## 🎉 Summary

### ✅ What's Working
1. **Backend API** - All endpoints functional on port 8000
2. **Frontend App** - Running on port 3000
3. **API Service** - Complete TypeScript service layer
4. **Authentication** - JWT tokens with auto-refresh
5. **CORS** - Properly configured for cross-origin requests
6. **Database** - PostgreSQL with all tables migrated
7. **AI Integration** - Gemini AI for triage + questions
8. **PDF Generation** - reportlab creating professional reports

### 📋 What's Needed
- Frontend UI components for new features
- Integration of existing components with new APIs
- Testing and refinement

### 🚀 How to Continue
1. **Run both servers** (backend + frontend)
2. **Implement UI components** using apiService methods
3. **Test each feature** as you build
4. **Refer to** `BACKEND_FEATURES_COMPLETE.md` for API docs

---

**Everything is properly organized and connected!** 🎯

Backend: `backend/medaid/` ✅  
Frontend: `frontend/` ✅  
Connection: `apiService.ts` + CORS ✅  
Ready to build UI components! 🚀
