# backend_processing.py - AI Triage Engine for Django
import os
import re
import json
from datetime import datetime
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

load_dotenv()

LLM_MODEL_NAME = "gemini-2.5-flash"
# Get API keys based on the split configuration
# For document processing, prefer DOCS key but fallback to CHAT or default key
API_KEY = os.getenv("GEMINI_API_KEY_DOCS") or os.getenv("GEMINI_API_KEY_CHAT") or os.getenv("GOOGLE_API_KEY")

# Initialize LLM
if API_KEY:
    # The original code initialized `llm` here. The new instruction removes this
    # direct initialization in favor of `genai.configure` and `vertexai.init`.
    # To maintain functionality for `llm` further down, we re-add its initialization.
    llm = ChatGoogleGenerativeAI(
        model=LLM_MODEL_NAME,
        google_api_key=API_KEY, # Use the resolved API_KEY
        temperature=0.3
    )
    
    # The following lines are added as per the instruction
    import google.generativeai as genai
    import vertexai
    genai.configure(api_key=API_KEY)
    
    # Initialize Vertex AI for OCR
    try:
        vertexai.init(
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        )
    except Exception as e:
        print(f"⚠️ Vertex AI initialization skipped: {str(e)}")
else:
    llm = None # Ensure llm is still None if API_KEY is not found
    print("❌ API Key not found. AI triage will not work.")

# MEDICAL VALIDATION RULES
MEDICAL_CONSISTENCY_RULES = {
    "gastrointestinal": ["stomach", "abdominal", "digestive", "vomit", "nausea", "diarrhea", "constipation", "indigestion"],
    "respiratory": ["breath", "cough", "wheeze", "lungs", "asthma", "pneumonia", "bronchitis", "laryngo"],
    "cardiac": ["chest", "heart", "cardiac", "angina", "pressure", "palpitation"],
    "neurological": ["head", "brain", "migraine", "seizure", "dizzy", "vertigo", "confusion"],
    "musculoskeletal": ["pain", "ache", "joint", "muscle", "bone", "arthritis", "sprain"]
}

# EMERGENCY KEYWORDS - Immediate High Risk
EMERGENCY_KEYWORDS = [
    "chest pain", "heart attack", "myocardial infarction", "severe chest",
    "cannot breathe", "difficulty breathing", "severe breathlessness", "choking",
    "unconscious", "passed out", "fainted", "unresponsive",
    "severe bleeding", "heavy bleeding", "blood loss", "hemorrhage",
    "stroke", "paralysis", "numbness one side", "face drooping",
    "seizure", "convulsion", "fitting",
    "severe burn", "poisoning", "overdose",
    "suicide", "self harm", "wanting to die"
]

# LOW RISK RULES - Common minor conditions
LOW_RISK_RULES = [
    {
        "symptoms": ["stomach pain", "stomach ache", "pet dard", "abdominal pain"],
        "absence_of": ["fever", "vomit", "vomiting", "blood", "bleeding", "severe", "sharp", "unbearable"],
        "override_risk": "low",
        "reason": "Isolated stomach pain without fever, vomiting, or bleeding is often minor indigestion, gas, or a mild stomach bug that can be managed with rest, hydration, and over-the-counter remedies.",
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
    }
]

# HIGH RISK RULES - Critical combinations
CRITICAL_RULES = [
    {
        "symptoms": ["chest pain", "chest discomfort", "pressure chest"],
        "history": ["heart disease", "myocardial infarction", "angina", "cardiac", "coronary"],
        "override_risk": "high",
        "reason": "Chest pain with a history of heart disease requires immediate evaluation."
    },
    {
        "symptoms": ["shortness of breath", "difficulty breathing", "wheezing", "cannot breathe"],
        "history": ["asthma", "copd", "emphysema", "respiratory"],
        "override_risk": "high",
        "reason": "Respiratory distress with a history of lung disease requires immediate evaluation."
    },
    {
        "symptoms": ["severe headache", "worst headache", "thunderclap headache"],
        "history": ["hypertension", "high blood pressure", "aneurysm", "stroke"],
        "override_risk": "high",
        "reason": "A severe headache with a cardiovascular history requires immediate evaluation."
    },
    {
        "symptoms": ["uncontrolled bleeding", "heavy bleeding", "bleeding won't stop"],
        "history": [],
        "override_risk": "high",
        "reason": "Uncontrolled bleeding requires immediate medical attention."
    },
    {
        "symptoms": ["fainting", "lost consciousness", "passed out"],
        "history": [],
        "override_risk": "high",
        "reason": "Loss of consciousness requires urgent medical evaluation."
    }
]

# SYMPTOM MAPPING (multilingual)
SYMPTOM_KEYWORD_MAP = {
    'dizziness': ['dizzy', 'lightheaded', 'vertigo', 'spinning', 'chakkar'],
    'fever': ['fever', 'high temperature', 'chills', 'bukhar', 'taap'],
    'headache': ['headache', 'head pain', 'sir dard'],
    'stomach_pain': ['abdominal pain', 'stomach ache', 'pet dard'],
    'breathing_problem': ['dyspnea', 'shortness of breath', 'chest tightness', 'saans ki problem'],
    'weakness': ['fatigue', 'weakness', 'tired', 'kamjori'],
    'diarrhea': ['diarrhea', 'loose motion', 'loose stools', 'dast'],
    'vomiting': ['nausea', 'vomiting', 'throwing up', 'ulti'],
    'body_pain': ['body ache', 'muscle pain', 'joint pain', 'badan dard'],
    'cough': ['cough', 'dry cough', 'productive cough', 'khansi'],
}


def check_emergency_keywords(symptoms_text):
    """Check if symptoms contain emergency keywords"""
    symptoms_lower = symptoms_text.lower()
    for keyword in EMERGENCY_KEYWORDS:
        if keyword in symptoms_lower:
            return True, keyword
    return False, None


def check_low_risk_rules(symptoms_text):
    """Check if symptoms match low-risk patterns"""
    symptoms_lower = symptoms_text.lower()
    
    for rule in LOW_RISK_RULES:
        symptom_match = any(symptom in symptoms_lower for symptom in rule["symptoms"])
        absence_match = not any(absent in symptoms_lower for absent in rule["absence_of"])
        
        if symptom_match and absence_match:
            return {
                "risk_level": rule["override_risk"],
                "reason": rule["reason"],
                "confidence": 0.8,
                "possible_diseases": rule["possible_diseases"],
                "assessment_source": "low_risk_rule"
            }
    return None


def check_critical_rules(symptoms_text, past_history):
    """Check if symptoms + history match critical patterns"""
    symptoms_lower = symptoms_text.lower()
    history_text = json.dumps(past_history).lower() if past_history else ""
    
    for rule in CRITICAL_RULES:
        symptom_match = any(symptom in symptoms_lower for symptom in rule["symptoms"])
        
        if not rule["history"]:  # No history required
            if symptom_match:
                return {
                    "risk_level": rule["override_risk"],
                    "reason": rule["reason"],
                    "confidence": 0.95,
                    "possible_diseases": ["Emergency Condition"],
                    "assessment_source": "critical_rule"
                }
        else:
            history_match = any(hist in history_text for hist in rule["history"])
            if symptom_match and history_match:
                return {
                    "risk_level": rule["override_risk"],
                    "reason": rule["reason"],
                    "confidence": 0.95,
                    "possible_diseases": ["Emergency Condition"],
                    "assessment_source": "critical_rule"
                }
    return None


def validate_medical_consistency(diseases, reasoning):
    """Validate that medical reasoning matches diagnosed conditions"""
    reasoning_lower = reasoning.lower()
    diseases_lower = " ".join(diseases).lower()
    
    mentioned_conditions = []
    for disease_category, keywords in MEDICAL_CONSISTENCY_RULES.items():
        if any(keyword in reasoning_lower for keyword in keywords):
            mentioned_conditions.append(disease_category)
    
    consistency_issues = []
    for condition in mentioned_conditions:
        if not any(keyword in diseases_lower for keyword in MEDICAL_CONSISTENCY_RULES[condition]):
            consistency_issues.append(f"Reasoning mentions {condition} issues but no {condition} diseases are listed")
    
    if consistency_issues:
        return False, " | ".join(consistency_issues)
    
    return True, "Medical reasoning is consistent with diagnosed conditions"


def normalize_symptoms(symptoms_text):
    """Normalize and extract symptom keywords"""
    symptoms_lower = symptoms_text.lower()
    normalized = []
    
    for symptom, variations in SYMPTOM_KEYWORD_MAP.items():
        for variation in variations:
            if variation in symptoms_lower:
                normalized.append(symptom)
                break
    
    return list(set(normalized))


# LLM PROMPT TEMPLATE
rag_prompt_template = PromptTemplate(
    input_variables=["user_symptoms", "user_history", "user_age", "user_sex", "current_date"],
    template="""
You are an AI Medical Expert for a Health Triage System. Based on the provided information, give a comprehensive medical assessment.

CRITICAL INSTRUCTIONS:
1. Your medical reasoning MUST directly support and explain the conditions listed in possible_diseases.
2. DO NOT introduce conditions in the reasoning that are not in the possible_diseases list.
3. Focus on the most likely explanations based on symptom patterns.
4. Your response must be medically coherent and consistent.
5. Consider the patient's age and sex in your assessment.

User Information:
- Current Symptoms: {user_symptoms}
- Past Medical History: {user_history}
- Age: {user_age}
- Sex: {user_sex}
- Assessment Date: {current_date}

Provide your assessment as a JSON object with these exact keys:
- "risk_level": Must be exactly one of ["low", "medium", "high", "emergency"]
- "reason": Detailed medical reasoning (2-3 sentences explaining your assessment)
- "possible_diseases": Array of 3-5 disease names in simple terms
- "confidence": Number between 0.0 and 1.0

Example response:
{{"risk_level": "medium", "reason": "The combination of fever and body pain suggests a viral infection. Given the patient's age and symptoms, monitoring is recommended.", "possible_diseases": ["Viral Fever", "Flu", "Common Cold"], "confidence": 0.8}}

Your response must be ONLY the JSON object, no other text.
"""
)

# Create LLM Chain
if llm:
    rag_chain = LLMChain(llm=llm, prompt=rag_prompt_template)
else:
    rag_chain = None


def run_ai_triage(symptoms_text, past_history=None, age=None, gender=None):
    """
    Main triage function - analyzes symptoms and returns assessment
    """
    # Step 1: Check for emergencies
    is_emergency, emergency_keyword = check_emergency_keywords(symptoms_text)
    if is_emergency:
        return {
            "risk_level": "emergency",
            "risk_probability": 0.95,
            "reason": f"EMERGENCY: Detected critical symptom '{emergency_keyword}'. Seek immediate medical attention.",
            "confidence": 0.95,
            "possible_diseases": ["Emergency Condition - Immediate Care Required"],
            "assessment_source": "emergency_rule",
            "similar_cases": {}
        }
    
    # Step 2: Check critical rules (high-risk with history)
    critical_result = check_critical_rules(symptoms_text, past_history)
    if critical_result:
        return {
            "risk_level": critical_result["risk_level"],
            "risk_probability": critical_result["confidence"],
            "reason": critical_result["reason"],
            "confidence": critical_result["confidence"],
            "possible_diseases": critical_result["possible_diseases"],
            "assessment_source": critical_result["assessment_source"],
            "similar_cases": {}
        }
    
    # Step 3: Check low-risk rules
    low_risk_result = check_low_risk_rules(symptoms_text)
    if low_risk_result:
        return {
            "risk_level": low_risk_result["risk_level"],
            "risk_probability": low_risk_result["confidence"],
            "reason": low_risk_result["reason"],
            "confidence": low_risk_result["confidence"],
            "possible_diseases": low_risk_result["possible_diseases"],
            "assessment_source": low_risk_result["assessment_source"],
            "similar_cases": {}
        }
    
    # Step 4: Use AI/LLM for complex cases
    if not rag_chain:
        return {
            "risk_level": "medium",
            "risk_probability": 0.5,
            "reason": "AI triage unavailable. Please consult a healthcare provider for proper assessment.",
            "confidence": 0.5,
            "possible_diseases": ["Unknown - Requires Medical Evaluation"],
            "assessment_source": "fallback",
            "similar_cases": {}
        }
    
    try:
        # Prepare inputs for LLM
        history_text = json.dumps(past_history) if past_history else "No past history provided"
        
        # Call LLM
        response = rag_chain.run(
            user_symptoms=symptoms_text,
            user_history=history_text,
            user_age=age or "Not provided",
            user_sex=gender or "Not provided",
            current_date=datetime.now().strftime("%Y-%m-%d")
        )
        
        # Parse JSON response
        response_clean = response.strip()
        if response_clean.startswith("```json"):
            response_clean = response_clean[7:]
        if response_clean.endswith("```"):
            response_clean = response_clean[:-3]
        response_clean = response_clean.strip()
        
        result = json.loads(response_clean)
        
        # Validate consistency
        is_valid, message = validate_medical_consistency(
            result.get("possible_diseases", []),
            result.get("reason", "")
        )
        
        if not is_valid:
            print(f"⚠️ Consistency warning: {message}")
        
        return {
            "risk_level": result.get("risk_level", "medium"),
            "risk_probability": result.get("confidence", 0.7),
            "reason": result.get("reason", "Assessment completed"),
            "confidence": result.get("confidence", 0.7),
            "possible_diseases": result.get("possible_diseases", []),
            "assessment_source": "ai",
            "similar_cases": {},
            "validation_message": message
        }
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
        print(f"Raw response: {response}")
        return {
            "risk_level": "medium",
            "risk_probability": 0.5,
            "reason": "Unable to parse AI response. Please consult a healthcare provider.",
            "confidence": 0.5,
            "possible_diseases": ["Assessment Error"],
            "assessment_source": "error",
            "similar_cases": {}
        }
    except Exception as e:
        print(f"❌ Triage error: {e}")
        return {
            "risk_level": "medium",
            "risk_probability": 0.5,
            "reason": f"Error during assessment: {str(e)}. Please consult a healthcare provider.",
            "confidence": 0.5,
            "possible_diseases": ["Assessment Error"],
            "assessment_source": "error",
            "similar_cases": {}
        }


def generate_recommendations(risk_level, possible_diseases):
    """Generate action recommendations based on risk level"""
    recommendations = []
    
    if risk_level == "emergency":
        recommendations = [
            "🚨 CALL EMERGENCY SERVICES (112/108) IMMEDIATELY",
            "Do not wait - seek immediate medical attention",
            "Go to the nearest emergency room",
            "Have someone stay with the patient",
        ]
    elif risk_level == "high":
        recommendations = [
            "Seek medical attention within 24 hours",
            "Visit a hospital or clinic today",
            "Monitor symptoms closely",
            "Keep emergency contacts ready",
        ]
    elif risk_level == "medium":
        recommendations = [
            "Schedule an appointment with a doctor within 2-3 days",
            "Monitor symptoms - seek immediate care if worsening",
            "Rest and stay hydrated",
            "Take over-the-counter medications if appropriate",
        ]
    else:  # low
        recommendations = [
            "Rest and self-care recommended",
            "Stay hydrated and maintain good nutrition",
            "Monitor symptoms - consult doctor if not improving in 3-5 days",
            "Use home remedies appropriate for the condition",
        ]
    
    return recommendations
