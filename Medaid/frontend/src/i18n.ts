import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

const resources = {
  english: {
    translation: {
      // Navigation
      "newChat": "New Chat",
      "home": "Home",
      "medicalInsights": "Medical History Insights",
      "medicationTracking": "Medication Tracking",
      "recentChats": "Recent Chats",
      "other": "Other",
      "reports": "Reports",
      "patientMonitoring": "Patient Monitoring",
      
      // Header
      "aiAssistant": "AI Assistant",
      "settings": "Settings",
      "share": "Share",
      
      // Dashboard Cards
      "aiDiagnosis": "AI Diagnosis",
      "aiDiagnosisDesc": "Advanced machine learning for accurate medical diagnosis and treatment recommendations.",
      "healthAnalytics": "Health Analytics",
      "healthAnalyticsDesc": "Advanced analytics and reporting for better healthcare outcomes",
      "patientCare": "Patient Care",
      "patientCareDesc": "Comprehensive patient management and care coordination",
      
      // Welcome
      "greeting": "Good",
      "morning": "Morning",
      "afternoon": "Afternoon",
      "evening": "Evening",
      "welcomeMessage": "How can I assist you today?",
      
      // Settings Modal
      "appearance": "Appearance",
      "darkMode": "Dark Mode",
      "language": "Language",
      "starlit": "Starlit",
      
      // Share Modal
      "shareWithFriends": "Share with Friends",
      "shareDesc": "Trading is more effective when you connect with friends!",
      "shareYourLink": "Share you link",
      "shareTo": "Share to",
      
      // Auth
      "signIn": "Sign In",
      "createAccount": "Create Account",
      "welcomeToMedaid": "Welcome to Medaid AI",
      "signInMessage": "Sign in to access your AI healthcare assistant and unlock powerful features",
      
      // Profile
      "medicalHistory": "Medical History",
      "freePlan": "Free Plan",
      "activePat ient": "Active Patient",
      "age": "Age",
      "visits": "Visits",
      "records": "Records",
      
      // Upgrade
      "boostWithAI": "Boost with AI",
      "boostDesc": "AI-powered replies, tag insights, and tools that save hours.",
      "upgradeToPro": "Upgrade to Pro"
    }
  },
  hindi: {
    translation: {
      // Navigation
      "newChat": "नई चैट",
      "home": "होम",
      "medicalInsights": "मेडिकल हिस्ट्री इनसाइट्स",
      "medicationTracking": "दवा ट्रैकिंग",
      "recentChats": "हाल की चैट",
      "other": "अन्य",
      "reports": "रिपोर्ट",
      "patientMonitoring": "रोगी निगरानी",
      
      // Header
      "aiAssistant": "AI सहायक",
      "settings": "सेटिंग्स",
      "share": "शेयर करें",
      
      // Dashboard Cards
      "aiDiagnosis": "AI निदान",
      "aiDiagnosisDesc": "सटीक चिकित्सा निदान और उपचार सिफारिशों के लिए उन्नत मशीन लर्निंग।",
      "healthAnalytics": "स्वास्थ्य विश्लेषण",
      "healthAnalyticsDesc": "बेहतर स्वास्थ्य परिणामों के लिए उन्नत विश्लेषण और रिपोर्टिंग",
      "patientCare": "रोगी देखभाल",
      "patientCareDesc": "व्यापक रोगी प्रबंधन और देखभाल समन्वय",
      
      // Welcome
      "greeting": "सुप्रभात",
      "morning": "सुबह",
      "afternoon": "दोपहर",
      "evening": "शाम",
      "welcomeMessage": "आज मैं आपकी कैसे सहायता कर सकता हूं?",
      
      // Settings Modal
      "appearance": "दिखावट",
      "darkMode": "डार्क मोड",
      "language": "भाषा",
      "starlit": "स्टारलिट",
      
      // Share Modal
      "shareWithFriends": "दोस्तों के साथ शेयर करें",
      "shareDesc": "जब आप दोस्तों के साथ जुड़ते हैं तो ट्रेडिंग अधिक प्रभावी होती है!",
      "shareYourLink": "अपना लिंक शेयर करें",
      "shareTo": "शेयर करें",
      
      // Auth
      "signIn": "साइन इन करें",
      "createAccount": "खाता बनाएं",
      "welcomeToMedaid": "Medaid AI में आपका स्वागत है",
      "signInMessage": "अपने AI हेल्थकेयर सहायक तक पहुंचने और शक्तिशाली सुविधाओं को अनलॉक करने के लिए साइन इन करें",
      
      // Profile
      "medicalHistory": "मेडिकल हिस्ट्री",
      "freePlan": "फ्री प्लान",
      "activePatient": "सक्रिय रोगी",
      "age": "आयु",
      "visits": "विजिट",
      "records": "रिकॉर्ड",
      
      // Upgrade
      "boostWithAI": "AI के साथ बूस्ट करें",
      "boostDesc": "AI-संचालित उत्तर, टैग इनसाइट्स और उपकरण जो घंटों बचाते हैं।",
      "upgradeToPro": "प्रो में अपग्रेड करें"
    }
  },
  marathi: {
    translation: {
      // Navigation
      "newChat": "नवीन चॅट",
      "home": "होम",
      "medicalInsights": "वैद्यकीय इतिहास अंतर्दृष्टी",
      "medicationTracking": "औषध ट्रॅकिंग",
      "recentChats": "अलीकडील चॅट",
      "other": "इतर",
      "reports": "अहवाल",
      "patientMonitoring": "रुग्ण निरीक्षण",
      
      // Header
      "aiAssistant": "AI सहाय्यक",
      "settings": "सेटिंग्ज",
      "share": "शेअर करा",
      
      // Dashboard Cards
      "aiDiagnosis": "AI निदान",
      "aiDiagnosisDesc": "अचूक वैद्यकीय निदान आणि उपचार शिफारशींसाठी प्रगत मशीन लर्निंग.",
      "healthAnalytics": "आरोग्य विश्लेषण",
      "healthAnalyticsDesc": "चांगल्या आरोग्य परिणामांसाठी प्रगत विश्लेषण आणि अहवाल",
      "patientCare": "रुग्ण काळजी",
      "patientCareDesc": "सर्वसमावेशक रुग्ण व्यवस्थापन आणि काळजी समन्वय",
      
      // Welcome
      "greeting": "शुभ",
      "morning": "सकाळ",
      "afternoon": "दुपार",
      "evening": "संध्याकाळ",
      "welcomeMessage": "आज मी तुम्हाला कशी मदत करू शकतो?",
      
      // Settings Modal
      "appearance": "देखावा",
      "darkMode": "डार्क मोड",
      "language": "भाषा",
      "starlit": "स्टारलिट",
      
      // Share Modal
      "shareWithFriends": "मित्रांसोबत शेअर करा",
      "shareDesc": "जेव्हा तुम्ही मित्रांशी जोडता तेव्हा ट्रेडिंग अधिक प्रभावी होते!",
      "shareYourLink": "तुमची लिंक शेअर करा",
      "shareTo": "शेअर करा",
      
      // Auth
      "signIn": "साइन इन करा",
      "createAccount": "खाते तयार करा",
      "welcomeToMedaid": "Medaid AI मध्ये आपले स्वागत आहे",
      "signInMessage": "तुमच्या AI हेल्थकेअर सहाय्यकामध्ये प्रवेश करण्यासाठी आणि शक्तिशाली वैशिष्ट्ये अनलॉक करण्यासाठी साइन इन करा",
      
      // Profile
      "medicalHistory": "वैद्यकीय इतिहास",
      "freePlan": "फ्री प्लॅन",
      "activePatient": "सक्रिय रुग्ण",
      "age": "वय",
      "visits": "भेटी",
      "records": "रेकॉर्ड",
      
      // Upgrade
      "boostWithAI": "AI सह बूस्ट करा",
      "boostDesc": "AI-संचालित उत्तरे, टॅग अंतर्दृष्टी आणि तास वाचवणारी साधने.",
      "upgradeToPro": "प्रो मध्ये अपग्रेड करा"
    }
  }
};

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: 'english',
    lng: 'english',
    interpolation: {
      escapeValue: false
    }
  });

export default i18n;
