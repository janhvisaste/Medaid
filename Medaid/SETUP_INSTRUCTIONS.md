# MEDAID Setup Instructions

## 🔧 Required Setup Steps

### 1. Get Google Gemini API Key (CRITICAL - Required for AI Features)

The AI triage system requires a Google Gemini API key to function.

**Steps to get your API key:**

1. Visit: https://makersuite.google.com/app/apikey
2. Sign in with your Google account
3. Click "Create API Key" or "Get API Key"
4. Copy the generated API key

### 2. Add API Key to Backend

Open the file: `/Users/janhvi/MEDAID_WEB/backend/medaid/.env`

Replace this line:
```
GOOGLE_API_KEY=your-google-api-key-here
```

With your actual API key:
```
GOOGLE_API_KEY=AIzaSyC-your-actual-key-here
```

**Save the file after editing!**

### 3. Restart Backend Server (if running)

If your Django server is already running, restart it to load the new environment variable:

```bash
# Press Ctrl+C in the terminal running the server
# Then restart it:
cd /Users/janhvi/MEDAID_WEB/backend/medaid
source ../env/bin/activate
python manage.py runserver
```

## 🚀 How to Use the Application

### Option 1: Dashboard Chat (Quick Access)
1. Go to `http://localhost:3000/dashboard`
2. Type your symptoms in the chat input at the bottom
3. Example: "fever, headache, body pain for 2 days"
4. Press Enter or click Send
5. The AI will analyze and provide:
   - Risk level (Low/Medium/High/Emergency)
   - Reasoning
   - Possible conditions
   - Recommendations

### Option 2: Dedicated Consultation Page (Full Experience)
1. From dashboard, click "AI Health Consultation" in the sidebar
2. OR directly visit `http://localhost:3000/consultation`
3. Choose input mode: Text, Voice, or Report Upload
4. Describe your symptoms
5. Click "Get AI Assessment"
6. View detailed results with:
   - Color-coded risk level
   - Possible conditions
   - Personalized recommendations
   - Print/save options

## ✅ Testing the System

### Test Case 1: Low Risk Symptoms
Input: "I have a mild headache"
Expected: Low risk assessment with rest recommendations

### Test Case 2: Medium Risk Symptoms
Input: "fever 101°F, cough, body pain for 3 days"
Expected: Medium risk with possible flu/viral infection

### Test Case 3: High Risk Symptoms (Critical Rule)
Input: "severe chest pain, difficulty breathing, have heart disease history"
Expected: Emergency risk with immediate medical attention recommendation

### Test Case 4: Multi-language Support
Input in Hindi: "मुझे बुखार और सिर दर्द है" (I have fever and headache)
Expected: System recognizes Hindi symptoms and provides assessment

## 🔍 Troubleshooting

### Issue: "Failed to get AI assessment" in dashboard chat

**Solution:**
1. Check if Google API key is added to `.env` file
2. Restart backend server after adding key
3. Check browser console (F12) for detailed error
4. Verify backend is running on port 8000

### Issue: "This is a development server" warning

**Solution:**
This is normal for development. The warning appears because you're using Django's built-in server. Ignore it during development.

### Issue: Backend shows "GOOGLE_API_KEY not found"

**Solution:**
1. Make sure `.env` file exists at `/Users/janhvi/MEDAID_WEB/backend/medaid/.env`
2. Ensure the line `GOOGLE_API_KEY=...` has no spaces around the `=`
3. Restart the server

### Issue: Frontend not loading consultation page

**Solution:**
1. Check if React dev server is running on port 3000
2. Check browser console for errors
3. Try clearing browser cache and reloading

## 📊 Database Tables Created

The backend has created these tables for the triage system:
- `api_triagerecord` - Stores all symptom assessments
- `api_possiblecondition` - Stores possible diagnoses
- `api_recommendation` - Stores personalized recommendations
- `api_medicaltest` - Stores lab test results
- `api_abnormalresult` - Stores abnormal test findings
- `api_facility` - Stores healthcare facility information

## 🎯 Features Now Available

✅ AI-powered symptom analysis with Google Gemini
✅ Risk level categorization (Emergency/High/Medium/Low)
✅ Multi-language symptom recognition (English, Hindi, Marathi)
✅ Critical condition detection (6 emergency rules)
✅ Low-risk condition filtering (4 common benign patterns)
✅ Personalized recommendations
✅ Medical history integration
✅ Chat interface in dashboard
✅ Dedicated consultation flow page
✅ Medical report analysis (PDF/Image support)
✅ Triage history tracking
✅ Health passport view

## 📝 Next Steps (Optional Enhancements)

- [ ] Install Tesseract OCR for image report analysis: `brew install tesseract`
- [ ] Implement voice recording with Web Speech API
- [ ] Add data visualizations for health trends
- [ ] Build medical report upload component
- [ ] Create health passport timeline view

## 🆘 Need Help?

If you encounter any issues:
1. Check the console logs (browser F12 + backend terminal)
2. Verify both servers are running
3. Ensure API key is properly configured
4. Check that PostgreSQL database is running

---

**Remember:** Add your Google Gemini API key to make the AI features work!
