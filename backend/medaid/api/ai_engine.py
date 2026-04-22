# ai_engine.py - AI Triage Engine for MedAid
import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import re
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv

load_dotenv()

# Medical validation rules
MEDICAL_CONSISTENCY_RULES = {
    "gastrointestinal": ["stomach", "abdominal", "digestive", "vomit", "nausea", "diarrhea", "constipation", "indigestion"],
    "respiratory": ["breath", "cough", "wheeze", "lungs", "asthma", "pneumonia", "bronchitis", "laryngo"],
    "cardiac": ["chest", "heart", "cardiac", "angina", "pressure", "palpitation"],
    "neurological": ["head", "brain", "migraine", "seizure", "dizzy", "vertigo", "confusion"],
    "musculoskeletal": ["pain", "ache", "joint", "muscle", "bone", "arthritis", "sprain"],
    "systemic": ["fever", "chills", "sweat", "weakness", "fatigue", "body pain", "ache"]
}

# Critical rules for high-risk detection
CRITICAL_RULES = [
    {
        "symptoms": ["chest pain", "chest discomfort", "pressure chest", "seene mein dard", "heart pain"],
        "history": ["heart disease", "myocardial infarction", "angina", "cardiac", "coronary"],
        "override_risk": "emergency",
        "reason": "Chest pain is a serious symptom. Given your history, this requires immediate hospital care."
    },
    {
        "symptoms": ["shortness of breath", "difficulty breathing", "wheezing", "cannot breathe", "saans ki problem", "breathless"],
        "history": ["asthma", "copd", "emphysema", "respiratory"],
        "override_risk": "high",
        "reason": "Difficulty breathing is unsafe. You need to see a doctor immediately."
    },
    {
        "symptoms": ["severe headache", "worst headache", "thunderclap headache", "head feels like exploding"],
        "history": ["hypertension", "high blood pressure", "aneurysm", "stroke"],
        "override_risk": "high",
        "reason": "A very severe headache can be dangerous with your history. Please go to the hospital."
    },
    {
        "symptoms": ["uncontrolled bleeding", "heavy bleeding", "bleeding won't stop", "khoon beh raha hai"],
        "history": [],
        "override_risk": "emergency",
        "reason": "Heavy bleeding that doesn't stop is an emergency."
    },
    {
        "symptoms": ["fainting", "lost consciousness", "passed out", "behosh", "blackout"],
        "history": [],
        "override_risk": "emergency",
        "reason": "Losing consciousness is very serious. Go to the hospital now."
    },
]

# Low-risk rules (Strictly filtered)
LOW_RISK_RULES = [
    {
        "symptoms": ["stomach pain", "stomach ache", "pet dard", "abdominal pain"],
        "absence_of": ["fever", "vomit", "vomiting", "blood", "bleeding", "severe", "sharp", "unbearable", "pregnancy"],
        "override_risk": "low",
        "reason": "Mild stomach pain without fever or vomiting is usually due to gas or indigestion.",
        "possible_diseases": ["Indigestion/Gas (Acidity)", "Mild Food Reaction", "Constipation"]
    },
    {
        "symptoms": ["headache", "sir dard"],
        "absence_of": ["severe", "worst", "thunderclap", "vomit", "vomiting", "vision", "confusion", "numbness", "fever", "body pain", "stiff neck"],
        "override_risk": "low",
        "reason": "A standalone headache without fever or other symptoms is often due to stress, lack of sleep, or dehydration.",
        "possible_diseases": ["Tension Headache (Stress)", "Dehydration (Lack of water)", "Eye Strain", "Lack of Sleep"]
    },
    {
        "symptoms": ["cough", "khansi"],
        "absence_of": ["fever", "breath", "shortness", "chest pain", "blood", "wheezing", " > 2 weeks"],
        "override_risk": "low",
        "reason": "A dry cough without fever or breathing trouble is often due to dust, pollution, or mild allergy.",
        "possible_diseases": ["Dust Allergy", "Throat Irritation", "Mild Cold"]
    },
    {
        "symptoms": ["cold", "runny nose", "nasal congestion", "zukam"],
        "absence_of": ["fever", "chest pain", "breath", "severe", "yellow mucus", "green mucus"],
        "override_risk": "low",
        "reason": "A common cold with just a runny nose usually goes away on its own with rest.",
        "possible_diseases": ["Common Cold", "Seasonal Allergy"]
    }
]

# Symptom keyword mapping for multilingual support
SYMPTOM_KEYWORD_MAP = {
    'dizziness': ['dizzy', 'lightheaded', 'vertigo', 'spinning', 'balance_problem', 'chakkar'],
    'fever': ['fever', 'high_temperature', 'chills', 'bukhar', 'taap', 'garamn'],
    'headache': ['headache', 'head_pain', 'sir_dard', 'sir_mein_dard', 'maatha'],
    'stomach_pain': ['abdominal_pain', 'stomach_ache', 'pet_dard', 'pet_mein_dard', 'pet_dukhnav'],
    'breathing_problem': ['dyspnea', 'shortness_of_breath', 'chest_tightness', 'saans_ki_problem', 'dum'],
    'weakness': ['fatigue', 'weakness', 'tired', 'kamjori', 'thakan'],
    'loose_motion': ['diarrhea', 'loose_stools', 'dast'],
    'vomiting': ['nausea', 'vomiting', 'throwing_up', 'ulti'],
    'body_pain': ['body_ache', 'muscle_pain', 'joint_pain', 'badan_dard', 'haath_pair_dard', 'body_pain'],
    'cough': ['cough', 'dry_cough', 'productive_cough', 'khansi'],
}


class AITriageEngine:
    """AI-powered medical triage system using Google Gemini"""
    
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY_CHAT") or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY_DOCS")
        if not self.api_key:
            raise ValueError("No Gemini API key found in environment variables")
        
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=self.api_key,
            temperature=0.3
        )
        
        self.prompt_template = PromptTemplate(
            input_variables=["user_symptoms", "user_history", "user_age", "user_sex", "current_date"],
            template="""
You are "Seva", a compassionate and practical Medical Assistant for rural communities.
Your goal is to provide accurate, simple, and helpful health advice.

CRITICAL CONTEXT:
1. The user may be from a rural area. Avoid complex medical jargon. Use simple, direct language.
2. Logic Check: "Headache + Fever + Body Pain" is NOT "Eye Strain". It is likely a Viral Fever, Flu, or localized infection (Dengue/Malaria depending on region).
3. If symptoms suggest an infection (Fever, Chills, Body Pain), the risk is usually MEDIUM (needs doctor visit), not LOW (home rest only).
4. Be practical. Recommendations should include home remedies (drinking water, rest, sponging for fever) and when to see a doctor.

User Information:
- Current Symptoms: {user_symptoms}
- Past Medical History: {user_history}
- Age: {user_age}
- Sex: {user_sex}
- Assessment Date: {current_date}

Please provide your assessment in the following JSON format:
{{
    "risk_level": "emergency/high/medium/low",
    "reasoning": "Simple explanation in plain English. Ex: 'Since you have fever and body pain along with headache, this could be a viral fever.'",
    "possible_diseases": ["Condition 1", "Condition 2", "Condition 3"],
    "confidence": 0.85,
    "recommended_actions": ["Action 1", "Action 2", "Action 3"]
}}

Provide ONLY the JSON output, no additional text.
"""
        )
    
    def check_critical_rules(self, symptoms: str, history: str) -> Optional[Dict]:
        """Check if symptoms match critical emergency rules"""
        symptoms_lower = symptoms.lower()
        history_lower = history.lower()
        
        for rule in CRITICAL_RULES:
            symptom_match = any(s in symptoms_lower for s in rule["symptoms"])
            
            if symptom_match:
                if rule["history"]:
                    history_match = any(h in history_lower for h in rule["history"])
                    if history_match:
                        return {
                            "risk_level": rule["override_risk"],
                            "reasoning": rule["reason"],
                            "confidence": 0.95,
                            "source": "critical_rule",
                            "possible_diseases": ["Emergency Condition - Requires Immediate Attention"]
                        }
                else:
                    return {
                        "risk_level": rule["override_risk"],
                        "reasoning": rule["reason"],
                        "confidence": 0.95,
                        "source": "critical_rule",
                        "possible_diseases": ["Emergency Condition - Requires Immediate Attention"]
                    }
        
        return None
    
    def check_low_risk_rules(self, symptoms: str) -> Optional[Dict]:
        """Check if symptoms match low-risk patterns"""
        symptoms_lower = symptoms.lower()
        
        for rule in LOW_RISK_RULES:
            symptom_match = any(s in symptoms_lower for s in rule["symptoms"])
            absence_match = not any(a in symptoms_lower for a in rule["absence_of"])
            
            if symptom_match and absence_match:
                return {
                    "risk_level": rule["override_risk"],
                    "reasoning": rule["reason"],
                    "confidence": 0.8,
                    "source": "low_risk_rule",
                    "possible_diseases": rule["possible_diseases"]
                }
        
        return None
    
    def normalize_symptoms(self, symptoms: str) -> str:
        """Normalize symptoms using keyword mapping"""
        symptoms_lower = symptoms.lower()
        normalized = symptoms_lower
        
        for key, synonyms in SYMPTOM_KEYWORD_MAP.items():
            for synonym in synonyms:
                if synonym in normalized:
                    normalized = normalized.replace(synonym, key)
        
        return normalized
    
    def assess_patient(self, 
                      symptoms: str, 
                      age: int, 
                      sex: str,
                      past_history: str = "") -> Dict:
        """
        Main triage assessment function
        
        Returns dict with:
            - risk_level: emergency/high/medium/low
            - reasoning: detailed explanation
            - possible_diseases: list of conditions
            - confidence: float 0-1
            - recommended_actions: list of recommendations
            - assessment_source: critical_rule/low_risk_rule/ai
        """
        
        # Check critical rules first
        critical_result = self.check_critical_rules(symptoms, past_history)
        if critical_result:
            return {
                **critical_result,
                "assessment_source": "critical_rule",
                "recommended_actions": [
                    "Seek immediate emergency medical attention",
                    "Call emergency services or visit ER immediately",
                    "Do not delay treatment"
                ]
            }
        
        # Check low-risk rules
        low_risk_result = self.check_low_risk_rules(symptoms)
        if low_risk_result:
            return {
                **low_risk_result,
                "assessment_source": "low_risk_rule",
                "recommended_actions": [
                    "Rest and stay hydrated",
                    "Monitor symptoms for any worsening",
                    "Consider over-the-counter remedies",
                    "Visit a clinic if symptoms persist beyond 2-3 days"
                ]
            }
        
        # Use AI assessment for complex cases
        try:
            normalized_symptoms = self.normalize_symptoms(symptoms)
            
            prompt = self.prompt_template.format(
                user_symptoms=normalized_symptoms,
                user_history=past_history if past_history else "None reported",
                user_age=age,
                user_sex=sex,
                current_date=datetime.now().strftime("%Y-%m-%d")
            )
            
            response = self.llm.invoke(prompt)
            
            # Parse JSON response
            content = response.content.strip()
            
            # Clean up JSON if wrapped in markdown code blocks
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            
            content = content.strip()
            
            result = json.loads(content)
            result["assessment_source"] = "ai"
            
            return result
            
        except json.JSONDecodeError as e:
            # Fallback if JSON parsing fails
            return {
                "risk_level": "medium",
                "reasoning": "Unable to parse AI response. Please consult a healthcare provider for proper assessment.",
                "possible_diseases": ["Assessment Needed"],
                "confidence": 0.5,
                "assessment_source": "fallback",
                "recommended_actions": [
                    "Consult a healthcare provider for proper assessment",
                    "Monitor your symptoms closely",
                    "Seek immediate care if symptoms worsen"
                ]
            }
        except Exception as e:
            # General fallback
            return {
                "risk_level": "medium",
                "reasoning": f"Error during assessment: {str(e)}. Please consult a healthcare provider.",
                "possible_diseases": ["Assessment Needed"],
                "confidence": 0.5,
                "assessment_source": "error",
                "recommended_actions": [
                    "Consult a healthcare provider",
                    "Monitor symptoms",
                    "Seek care if symptoms worsen"
                ]
            }


# Helper function for standalone use
def run_triage_assessment(symptoms: str, age: int, sex: str, past_history: str = "") -> Dict:
    """
    Standalone function to run triage assessment
    """
    engine = AITriageEngine()
    return engine.assess_patient(symptoms, age, sex, past_history)
