# triage_engine.py - AI-Powered Medical Triage System
import os
import json
import re
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    print("⚠️  LangChain not installed. Install with: pip install langchain langchain-google-genai")

load_dotenv()

# Medical Validation Rules
MEDICAL_CONSISTENCY_RULES = {
    "gastrointestinal": ["stomach", "abdominal", "digestive", "vomit", "nausea", "diarrhea", "constipation", "indigestion"],
    "respiratory": ["breath", "cough", "wheeze", "lungs", "asthma", "pneumonia", "bronchitis"],
    "cardiac": ["chest", "heart", "cardiac", "angina", "pressure", "palpitation"],
    "neurological": ["head", "brain", "migraine", "seizure", "dizzy", "vertigo", "confusion"],
    "musculoskeletal": ["pain", "ache", "joint", "muscle", "bone", "arthritis", "sprain"]
}

# Emergency keywords for immediate override
EMERGENCY_KEYWORDS = [
    "not breathing", "unconscious", "severe chest pain", "heavy bleeding",
    "sudden weakness", "slurred speech", "seizure", "severe burn",
    "blue lips", "very drowsy", "faint", "loss of consciousness", 
    "can't breathe", "cannot breathe", "chest pain", "difficulty breathing",
    "severe bleeding", "uncontrolled bleeding", "passed out", "behosh"
]

def contains_emergency_keyword(text: str) -> bool:
    """Check if text contains any emergency keywords"""
    if not text:
        return False
    t = text.lower()
    for kw in EMERGENCY_KEYWORDS:
        if kw in t:
            return True
    return False

def get_emergency_services_by_pincode(pincode: str) -> Dict:
    """
    Get emergency services based on pincode/location
    
    Args:
        pincode: User's pincode or location
    
    Returns:
        Dict with emergency services information
    """
    # Base emergency services (India)
    services = {
        "pincode": pincode,
        "emergency_numbers": {
            "ambulance": "108",
            "police": "100",
            "fire": "101",
            "women_helpline": "1091",
            "child_helpline": "1098",
            "national_emergency": "112"
        },
        "instructions": [
            "Call 108 for medical emergencies",
            "Call 112 for any emergency (integrated number)",
            "Keep your location ready when calling",
            "Stay on the line until help arrives"
        ]
    }
    
    # TODO: Integrate with Google Places API or hospital database
    # For now, providing general guidance based on major Indian cities
    pincode_prefix = pincode[:3] if pincode and len(pincode) >= 3 else ""
    
    city_hospitals = {
        "400": {  # Mumbai
            "city": "Mumbai",
            "hospitals": [
                {"name": "KEM Hospital", "phone": "022-24107000", "address": "Acharya Donde Marg, Parel"},
                {"name": "Lilavati Hospital", "phone": "022-26567891", "address": "Bandra West"},
                {"name": "Hinduja Hospital", "phone": "022-44458888", "address": "Mahim"}
            ]
        },
        "110": {  # Delhi
            "city": "Delhi",
            "hospitals": [
                {"name": "AIIMS", "phone": "011-26588500", "address": "Ansari Nagar"},
                {"name": "Safdarjung Hospital", "phone": "011-26165060", "address": "Ring Road"},
                {"name": "Apollo Hospital", "phone": "011-26825858", "address": "Sarita Vihar"}
            ]
        },
        "560": {  # Bangalore
            "city": "Bangalore",
            "hospitals": [
                {"name": "Victoria Hospital", "phone": "080-26700301", "address": "Fort Area"},
                {"name": "Manipal Hospital", "phone": "080-25023456", "address": "HAL Airport Road"},
                {"name": "Apollo Hospital", "phone": "080-26304050", "address": "Bannerghatta Road"}
            ]
        },
        "600": {  # Chennai
            "city": "Chennai",
            "hospitals": [
                {"name": "Apollo Hospital", "phone": "044-28296000", "address": "Greams Road"},
                {"name": "Fortis Malar", "phone": "044-42895555", "address": "Adyar"},
                {"name": "SIMS Hospital", "phone": "044-42855555", "address": "Vadapalani"}
            ]
        },
        "700": {  # Kolkata
            "city": "Kolkata",
            "hospitals": [
                {"name": "SSKM Hospital", "phone": "033-22441000", "address": "College Street"},
                {"name": "Apollo Gleneagles", "phone": "033-23203040", "address": "EM Bypass"},
                {"name": "Fortis Hospital", "phone": "033-66283000", "address": "Anandapur"}
            ]
        }
    }
    
    if pincode_prefix in city_hospitals:
        services["city_info"] = city_hospitals[pincode_prefix]
    else:
        services["city_info"] = {
            "city": "Your Location",
            "message": "Call 108 for nearest hospital or search 'emergency hospital near me'"
        }
    
    return services

# Critical High-Risk Rules
CRITICAL_RULES = [
    {
        "symptoms": ["chest pain", "chest discomfort", "pressure chest", "seene me dard", "severe chest pain"],
        "history": ["heart disease", "myocardial infarction", "angina", "cardiac", "coronary"],
        "override_risk": "emergency",
        "reason": "Chest pain with a history of heart disease requires immediate evaluation to rule out acute cardiac event."
    },
    {
        "symptoms": ["shortness of breath", "difficulty breathing", "wheezing", "cannot breathe", "saans ki problem"],
        "history": ["asthma", "copd", "emphysema", "respiratory"],
        "override_risk": "emergency",
        "reason": "Respiratory distress with a history of lung disease requires immediate evaluation."
    },
    {
        "symptoms": ["severe headache", "worst headache", "thunderclap headache"],
        "history": ["hypertension", "high blood pressure", "aneurysm", "stroke"],
        "override_risk": "emergency",
        "reason": "Severe headache with cardiovascular history may indicate stroke or hemorrhage - requires immediate evaluation."
    },
    {
        "symptoms": ["uncontrolled bleeding", "heavy bleeding", "bleeding won't stop", "blood"],
        "history": [],
        "override_risk": "emergency",
        "reason": "Uncontrolled bleeding requires immediate medical attention."
    },
    {
        "symptoms": ["fainting", "lost consciousness", "passed out", "behosh"],
        "history": [],
        "override_risk": "emergency",
        "reason": "Loss of consciousness requires urgent medical evaluation."
    },
    {
        "symptoms": ["seizure", "convulsion", "fits", "dora"],
        "history": [],
        "override_risk": "high",
        "reason": "Seizure activity requires immediate medical assessment."
    }
]

# Low-Risk Rules (Common benign conditions)
LOW_RISK_RULES = [
    {
        "symptoms": ["stomach pain", "stomach ache", "pet dard", "abdominal pain"],
        "absence_of": ["fever", "vomit", "vomiting", "blood", "bleeding", "severe", "sharp", "unbearable"],
        "override_risk": "low",
        "reason": "Isolated stomach pain without fever, vomiting, or bleeding is often minor indigestion, gas, or mild gastritis that can be managed with rest and over-the-counter remedies.",
        "possible_diseases": ["Indigestion", "Gas", "Mild Gastritis", "Abdominal Muscle Strain"]
    },
    {
        "symptoms": ["headache", "sir dard"],
        "absence_of": ["severe", "worst", "thunderclap", "vomit", "vomiting", "vision", "confusion", "numbness"],
        "override_risk": "low",
        "reason": "Common headache without severe, neurological, or vomiting symptoms is often tension-related or due to dehydration, fatigue, or stress.",
        "possible_diseases": ["Tension Headache", "Dehydration", "Eye Strain", "Stress"]
    },
    {
        "symptoms": ["cough", "khansi"],
        "absence_of": ["fever", "breath", "shortness", "chest pain", "blood", "wheezing"],
        "override_risk": "low",
        "reason": "Isolated cough without fever or breathing difficulties is often a mild respiratory irritation, post-nasal drip, or the tail end of a cold.",
        "possible_diseases": ["Common Cold", "Post-Nasal Drip", "Allergic Cough", "Throat Irritation"]
    },
    {
        "symptoms": ["runny nose", "nasal congestion", "sore throat", "nakta"],
        "absence_of": ["fever", "difficulty breathing", "severe", "chest pain"],
        "override_risk": "low",
        "reason": "Upper respiratory symptoms without fever or breathing issues typically indicate a common cold or mild viral infection.",
        "possible_diseases": ["Common Cold", "Viral Upper Respiratory Infection", "Allergic Rhinitis"]
    }
]

# Symptom Mapping (English, Hindi, Marathi)
SYMPTOM_KEYWORD_MAP = {
    # Fever
    'fever': ['fever', 'high_temperature', 'chills'],
    'bukhar': ['fever', 'high_temperature', 'chills'],
    'taap': ['fever', 'high_temperature', 'chills'],
    
    # Pain
    'headache': ['headache', 'head_pain'],
    'sir_dard': ['headache', 'head_pain'],
    'dokyache_dukh': ['headache', 'head_pain'],
    
    'stomach_pain': ['abdominal_pain', 'stomach_ache'],
    'pet_dard': ['abdominal_pain', 'stomach_ache'],
    'potache_dukh': ['abdominal_pain', 'stomach_ache'],
    
    'chest_pain': ['chest_pain', 'chest_discomfort'],
    'seene_me_dard': ['chest_pain', 'chest_discomfort'],
    
    'body_pain': ['body_ache', 'muscle_pain', 'joint_pain'],
    'badan_dard': ['body_ache', 'muscle_pain', 'joint_pain'],
    'angache_dukh': ['body_ache', 'muscle_pain'],
    
    # Respiratory
    'cough': ['cough', 'dry_cough', 'productive_cough'],
    'khansi': ['cough', 'dry_cough', 'productive_cough'],
    'khokla': ['cough', 'dry_cough'],
    
    'breathing_problem': ['dyspnea', 'shortness_of_breath', 'chest_tightness'],
    'saans_ki_problem': ['dyspnea', 'shortness_of_breath', 'chest_tightness'],
    'shwaas_ghenyat_taklif': ['dyspnea', 'shortness_of_breath'],
    
    # Digestive
    'vomiting': ['nausea', 'vomiting', 'throwing_up'],
    'ulti': ['nausea', 'vomiting', 'throwing_up'],
    'vant': ['nausea', 'vomiting'],
    
    'loose_motion': ['diarrhea', 'loose_stools'],
    'dast': ['diarrhea', 'loose_stools'],
    'julaab': ['diarrhea', 'loose_stools'],
    
    # General
    'dizziness': ['dizzy', 'lightheaded', 'vertigo', 'spinning'],
    'chakkar': ['dizzy', 'lightheaded', 'vertigo'],
    'dongarvarte': ['dizzy', 'vertigo'],
    
    'weakness': ['fatigue', 'weakness', 'tired'],
    'kamjori': ['fatigue', 'weakness', 'tired'],
    'akamtpana': ['fatigue', 'weakness'],
}

class TriageEngine:
    """AI-Powered Medical Triage Assessment Engine"""
    
    def __init__(self):
        self.llm = None
        self._initialize_llm()
    
    def _initialize_llm(self):
        """Initialize Google Gemini LLM"""
        if not LANGCHAIN_AVAILABLE:
            print("⚠️  LangChain not available. Triage engine will use rule-based system only.")
            return
        
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            print("⚠️  GOOGLE_API_KEY not found in environment variables.")
            return
        
        try:
            self.llm = ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                google_api_key=google_api_key,
                temperature=0.3  # Lower for more consistent, focused responses
            )
            print("✅ Triage Engine initialized with Google Gemini AI")
            
        except Exception as e:
            print(f"❌ Error initializing LLM: {e}")
            self.llm = None
    
    def extract_symptoms(self, symptoms_text: str, past_history: List[str] = None) -> List[str]:
        """Extract and normalize symptoms from text"""
        all_symptoms = []
        
        if symptoms_text:
            text_lower = symptoms_text.lower()
            
            # Map user terms to medical codes
            for user_term, medical_codes in SYMPTOM_KEYWORD_MAP.items():
                if user_term in text_lower:
                    all_symptoms.extend(medical_codes)
            
            # Extract basic symptom keywords
            basic_keywords = re.findall(
                r'\b(?:pain|fever|headache|nausea|cough|weakness|fatigue|dizzy|vomit|ache|cold|flu|bleeding|breath|shortness|diarrhea|vomiting)\b',
                text_lower
            )
            all_symptoms.extend(basic_keywords)
        
        # Add condition-related symptoms from history
        if past_history:
            condition_symptoms = {
                'Diabetes': ['glucose_high', 'frequent_urination', 'excessive_thirst'],
                'Hypertension': ['high_blood_pressure', 'headache'],
                'Asthma': ['breathing_difficulty', 'wheezing', 'cough'],
                'Heart Disease': ['chest_pain', 'shortness_of_breath'],
                'Anemia': ['fatigue', 'weakness', 'pale_skin'],
            }
            for condition in past_history:
                if condition in condition_symptoms:
                    all_symptoms.extend(condition_symptoms[condition])
        
        return list(set(all_symptoms))
    
    def check_critical_rules(self, symptoms_text: str, past_history: List[str]) -> Optional[Dict]:
        """Check if case triggers critical high-risk rules"""
        symptoms_lower = symptoms_text.lower()
        history_lower = " ".join(past_history).lower() if past_history else ""
        
        for rule in CRITICAL_RULES:
            symptom_match = any(symptom in symptoms_lower for symptom in rule["symptoms"])
            
            if rule["history"]:
                history_match = any(hist in history_lower for hist in rule["history"])
                if symptom_match and history_match:
                    return {
                        "risk_level": rule["override_risk"],
                        "reasoning": rule["reason"],
                        "confidence": 1.0,
                        "possible_conditions": ["Critical Condition", "Emergency", "Requires Immediate Care"],
                        "source": "critical_rule"
                    }
            elif symptom_match:
                return {
                    "risk_level": rule["override_risk"],
                    "reasoning": rule["reason"],
                    "confidence": 1.0,
                    "possible_conditions": ["Critical Condition", "Emergency", "Requires Immediate Care"],
                    "source": "critical_rule"
                }
        
        return None
    
    def check_low_risk_rules(self, symptoms_text: str) -> Optional[Dict]:
        """Check if symptoms match common low-risk conditions"""
        symptoms_lower = symptoms_text.lower()
        
        for rule in LOW_RISK_RULES:
            # Check if main symptom is present
            symptom_match = any(symptom in symptoms_lower for symptom in rule["symptoms"])
            
            # Check that NO high-risk symptoms are present
            absence_match = not any(absent in symptoms_lower for absent in rule["absence_of"])
            
            if symptom_match and absence_match:
                return {
                    "risk_level": rule["override_risk"],
                    "reasoning": rule["reason"],
                    "confidence": 0.8,
                    "possible_conditions": rule["possible_diseases"],
                    "source": "low_risk_rule"
                }
        
        return None
    
    def assess_with_ai(self, symptoms_text: str, user_data: Dict, report_summary: str = "", location: str = "") -> Dict:
        """Perform AI-based triage assessment using Google Gemini"""
        if not self.llm:
            print("⚠️  LLM not available, using fallback assessment")
            return self.fallback_assessment(symptoms_text, user_data)
        
        try:
            # Build the prompt
            prompt = f"""You are a clinical triage assistant. You must respond with ONLY a valid JSON object and nothing else.

CRITICAL INSTRUCTIONS:
1. Your entire response must be a single valid JSON object
2. Do not wrap the JSON in markdown code blocks (no ```json)
3. Do not add any text before or after the JSON
4. Provide PERSONALIZED assessment for THIS SPECIFIC patient
5. Consider patient's age, sex, and medical history in your analysis
6. Vary your assessment based on the specific symptoms provided
7. Different symptoms should result in different conditions and risk levels

The JSON object must have exactly these keys:
- "possible_conditions": an array of objects, each with "disease" (string) and "confidence" (number between 0 and 1)
- "risk_level": one of these exact strings: "low", "medium", "high", "emergency"
- "risk_proba": a number between 0 and 1
- "reason": a string with a specific explanation tailored to THESE symptoms
- "recommendations": an array of strings (specific actionable recommendations for THESE symptoms)

PATIENT PROFILE:
- Age: {user_data.get('age', 'Adult')} years
- Sex: {user_data.get('gender', 'Not specified')}
- Past Medical History: {", ".join(user_data.get('past_history', [])) or "No significant past medical history"}
- Assessment Time: {datetime.now().strftime("%Y-%m-%d %H:%M")}
- Location: {location or "Location not specified"}

SYMPTOMS: {symptoms_text or "Patient reporting general discomfort"}

REPORT SUMMARY: {report_summary or "No medical report provided"}

Respond ONLY with the JSON object. Provide a SPECIFIC assessment based on the symptoms described above.
"""
            
            # Get AI response using invoke
            response = self.llm.invoke(prompt)
            
            # Extract content from response
            if hasattr(response, 'content'):
                response_text = response.content
            elif hasattr(response, 'text'):
                response_text = response.text
            else:
                response_text = str(response)
            
            # Parse JSON response
            response_clean = response_text.strip()
            if response_clean.startswith("```json"):
                response_clean = response_clean[7:]
            if response_clean.startswith("```"):
                response_clean = response_clean[3:]
            if response_clean.endswith("```"):
                response_clean = response_clean[:-3]
            
            result = json.loads(response_clean.strip())
            
            # Normalize the response format
            normalized_result = {
                "risk_level": result.get("risk_level", "medium").lower(),
                "reasoning": result.get("reason", "AI assessment completed"),
                "confidence": result.get("risk_proba", 0.7),
                "possible_conditions": [],
                "recommendations": result.get("recommendations", []),
                "source": "ai"
            }
            
            # Extract condition names from possible_conditions
            conditions = result.get("possible_conditions", [])
            if conditions:
                if isinstance(conditions[0], dict):
                    normalized_result["possible_conditions"] = [c.get("disease", "Unknown") for c in conditions]
                else:
                    normalized_result["possible_conditions"] = conditions
            
            return normalized_result
            
        except Exception as e:
            print(f"❌ Error in AI assessment: {e}")
            import traceback
            traceback.print_exc()
            return self.fallback_assessment(symptoms_text, user_data)
    
    def fallback_assessment(self, symptoms_text: str, user_data: Dict) -> Dict:
        """Fallback assessment when AI is unavailable"""
        symptoms_lower = symptoms_text.lower()
        
        # Emergency keywords
        emergency_keywords = ['chest pain', 'difficulty breathing', 'severe bleeding', 'fainting', 
                             'severe headache', 'unconscious', 'seizure', 'stroke']
        
        # High-risk keywords
        high_risk_keywords = ['high fever', 'persistent vomiting', 'severe pain', 'confusion', 
                             'rapid heartbeat', 'severe weakness']
        
        # Check for emergency
        if any(keyword in symptoms_lower for keyword in emergency_keywords):
            return {
                "risk_level": "emergency",
                "reasoning": "Critical symptoms detected that require immediate emergency medical attention.",
                "confidence": 0.85,
                "possible_conditions": ["Emergency Medical Condition", "Acute Critical Illness"],
                "recommendations": ["Call emergency services immediately", "Do not delay seeking care", 
                                   "Go to nearest emergency room"],
                "source": "fallback"
            }
        
        # Check for high risk
        if any(keyword in symptoms_lower for keyword in high_risk_keywords):
            return {
                "risk_level": "high",
                "reasoning": "Symptoms suggest a condition that requires prompt medical evaluation within hours.",
                "confidence": 0.75,
                "possible_conditions": ["Acute Illness", "Severe Infection", "Medical Emergency"],
                "recommendations": ["Seek medical care within 2-4 hours", "Visit urgent care or ER", 
                                   "Do not wait for symptoms to worsen"],
                "source": "fallback"
            }
        
        # Check for moderate risk
        moderate_keywords = ['fever', 'pain', 'vomiting', 'dizziness', 'cough', 'weakness']
        if any(keyword in symptoms_lower for keyword in moderate_keywords):
            return {
                "risk_level": "medium",
                "reasoning": "Symptoms suggest a medical condition that requires evaluation within 24-48 hours.",
                "confidence": 0.70,
                "possible_conditions": ["Viral Infection", "Bacterial Infection", "Common Illness"],
                "recommendations": ["Consult doctor within 24-48 hours", "Monitor symptoms", 
                                   "Rest and hydration", "Seek immediate care if symptoms worsen"],
                "source": "fallback"
            }
        
        # Default to low risk
        return {
            "risk_level": "low",
            "reasoning": "No significant concerning symptoms reported. Continue monitoring your health.",
            "confidence": 0.65,
            "possible_conditions": ["General Health Maintenance", "No Specific Condition"],
            "recommendations": ["Monitor your health", "Maintain regular checkups", 
                               "Contact doctor if symptoms develop"],
            "source": "fallback"
        }
    
    def assess(self, symptoms_text: str, user_data: Dict, report_summary: str = "", location: str = "") -> Dict:
        """
        Main triage assessment method
        
        Args:
            symptoms_text: Patient's description of symptoms
            user_data: Dict containing age, gender, past_history
            report_summary: Optional medical report summary from LLM
            location: Optional location/pincode for emergency services
        
        Returns:
            Dict with risk_level, reasoning, possible_conditions, confidence, recommendations
        """
        past_history = user_data.get('past_history', [])
        
        # Step 1: Check critical high-risk rules
        critical_result = self.check_critical_rules(symptoms_text, past_history)
        if critical_result:
            critical_result['recommendations'] = [
                "SEEK EMERGENCY MEDICAL CARE IMMEDIATELY",
                "Call emergency services or go to nearest ER",
                "Do not delay - this could be life-threatening"
            ]
            return critical_result
        
        # Step 2: Check low-risk rules
        low_risk_result = self.check_low_risk_rules(symptoms_text)
        if low_risk_result:
            low_risk_result['recommendations'] = [
                "Rest and monitor symptoms",
                "Stay hydrated",
                "Use over-the-counter remedies as needed",
                "Consult doctor if symptoms persist beyond 3-5 days"
            ]
            return low_risk_result
        
        # Step 3: Use AI assessment with report and location context
        return self.assess_with_ai(symptoms_text, user_data, report_summary, location)
    
    def generate_clarifying_questions(self, symptoms_text: str, user_data: Dict) -> List[Dict]:
        """
        Generate 2-3 targeted clarifying questions based on initial symptoms
        
        Args:
            symptoms_text: Patient's initial symptom description
            user_data: User profile data including age, gender, past history
        
        Returns:
            List of question dictionaries with question text and expected answer type
        """
        if not self.llm:
            # Fallback questions if AI unavailable
            return [
                {"question": "How long have you been experiencing these symptoms?", "type": "text"},
                {"question": "Have you taken any medications for this?", "type": "yes_no"},
                {"question": "On a scale of 1-10, how would you rate your discomfort?", "type": "scale"}
            ]
        
        age = user_data.get('age', 'unknown')
        gender = user_data.get('gender', 'unknown')
        past_history = user_data.get('past_history', {})
        
        prompt = f"""You are a medical AI assistant. A patient has reported the following symptoms:

SYMPTOMS: {symptoms_text}

PATIENT INFO:
- Age: {age}
- Gender: {gender}
- Past Medical History: {past_history}

Generate exactly 3 targeted clarifying questions to better understand the patient's condition. 
Focus on:
1. Symptom duration/progression
2. Severity and impact on daily activities
3. Associated symptoms or relevant medical history

Return your response as a JSON array with this exact format:
[
  {{"question": "Question text here?", "type": "text"}},
  {{"question": "Question text here?", "type": "yes_no"}},
  {{"question": "Question text here?", "type": "scale"}}
]

Only return the JSON array, nothing else."""

        try:
            response = self.llm.invoke(prompt)
            
            # Extract content
            if hasattr(response, 'content'):
                content = response.content
            else:
                content = str(response)
            
            # Parse JSON
            content = content.strip()
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            
            questions = json.loads(content)
            
            # Validate format
            if isinstance(questions, list) and len(questions) > 0:
                return questions[:3]  # Max 3 questions
            
            # Fallback if parsing failed
            return [
                {"question": "How long have you been experiencing these symptoms?", "type": "text"},
                {"question": "Have you taken any medications for this?", "type": "yes_no"},
                {"question": "On a scale of 1-10, how would you rate your discomfort?", "type": "scale"}
            ]
            
        except Exception as e:
            print(f"❌ Error generating clarifying questions: {e}")
            import traceback
            traceback.print_exc()
            return [
                {"question": "How long have you been experiencing these symptoms?", "type": "text"},
                {"question": "Have you taken any medications for this?", "type": "yes_no"},
                {"question": "On a scale of 1-10, how would you rate your discomfort?", "type": "scale"}
            ]
    
    def assess_with_clarifications(self, symptoms_text: str, user_data: Dict, 
                                   clarifications: List[Dict], report_summary: str = "", 
                                   location: str = "") -> Dict:
        """
        Enhanced assessment incorporating clarifying question responses
        
        Args:
            symptoms_text: Original symptom description
            user_data: User profile data
            clarifications: List of {"question": "...", "answer": "..."} pairs
            report_summary: Optional medical report summary
            location: Optional location for emergency services
        
        Returns:
            Complete assessment dictionary
        """
        # Build enhanced context with clarifications
        clarification_text = "\n".join([
            f"Q: {c['question']}\nA: {c['answer']}"
            for c in clarifications if c.get('answer')
        ])
        
        enhanced_symptoms = f"{symptoms_text}\n\nADDITIONAL INFORMATION:\n{clarification_text}"
        
        # Use standard assessment with enhanced context
        return self.assess_with_ai(enhanced_symptoms, user_data, report_summary, location)


# Global instance
_triage_engine = None

def get_triage_engine():
    """Get singleton instance of triage engine"""
    global _triage_engine
    if _triage_engine is None:
        _triage_engine = TriageEngine()
    return _triage_engine
