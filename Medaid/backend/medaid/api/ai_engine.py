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
    "musculoskeletal": ["pain", "ache", "joint", "muscle", "bone", "arthritis", "sprain"]
}

# Critical rules for high-risk detection
CRITICAL_RULES = [
    {
        "symptoms": ["chest pain", "chest discomfort", "pressure chest", "seene mein dard"],
        "history": ["heart disease", "myocardial infarction", "angina", "cardiac", "coronary"],
        "override_risk": "emergency",
        "reason": "Chest pain with a history of heart disease requires immediate emergency evaluation."
    },
    {
        "symptoms": ["shortness of breath", "difficulty breathing", "wheezing", "cannot breathe", "saans ki problem"],
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
        "symptoms": ["uncontrolled bleeding", "heavy bleeding", "bleeding won't stop", "khoon beh raha hai"],
        "history": [],
        "override_risk": "emergency",
        "reason": "Uncontrolled bleeding requires immediate emergency medical attention."
    },
    {
        "symptoms": ["fainting", "lost consciousness", "passed out", "behosh"],
        "history": [],
        "override_risk": "emergency",
        "reason": "Loss of consciousness requires urgent emergency medical evaluation."
    },
    {
        "symptoms": ["severe burns", "major injury", "accident", "trauma"],
        "history": [],
        "override_risk": "emergency",
        "reason": "Major trauma or severe burns require immediate emergency care."
    },
]

# Low-risk rules
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
    },
    {
        "symptoms": ["cold", "runny nose", "nasal congestion", "zukam"],
        "absence_of": ["fever", "chest pain", "breath", "severe"],
        "override_risk": "low",
        "reason": "Common cold symptoms without fever or breathing difficulties typically resolve on their own.",
        "possible_diseases": ["Common Cold", "Viral Rhinitis", "Allergic Rhinitis"]
    }
]

# Symptom keyword mapping for multilingual support
SYMPTOM_KEYWORD_MAP = {
    'dizziness': ['dizzy', 'lightheaded', 'vertigo', 'spinning', 'balance_problem', 'chakkar'],
    'fever': ['fever', 'high_temperature', 'chills', 'bukhar', 'taap'],
    'headache': ['headache', 'head_pain', 'sir_dard', 'sir_mein_dard'],
    'stomach_pain': ['abdominal_pain', 'stomach_ache', 'pet_dard', 'pet_mein_dard'],
    'breathing_problem': ['dyspnea', 'shortness_of_breath', 'chest_tightness', 'saans_ki_problem'],
    'weakness': ['fatigue', 'weakness', 'tired', 'kamjori', 'thakan'],
    'loose_motion': ['diarrhea', 'loose_stools', 'dast'],
    'vomiting': ['nausea', 'vomiting', 'throwing_up', 'ulti'],
    'body_pain': ['body_ache', 'muscle_pain', 'joint_pain', 'badan_dard'],
    'cough': ['cough', 'dry_cough', 'productive_cough', 'khansi'],
}


class AITriageEngine:
    """AI-powered medical triage system using Google Gemini"""
    
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
        
        self.llm = ChatGoogleGenerativeAI(
            model="models/gemini-1.5-flash",
            google_api_key=self.api_key,
            temperature=0.3
        )
        
        self.prompt_template = PromptTemplate(
            input_variables=["user_symptoms", "user_history", "user_age", "user_sex", "current_date"],
            template="""
You are an AI Medical Expert for a Health Triage System. Based on the provided information, give a comprehensive medical assessment.

CRITICAL INSTRUCTIONS:
1. Your medical reasoning MUST directly support and explain the conditions listed in possible_diseases.
2. DO NOT introduce conditions in the reasoning that are not in the possible_diseases list.
3. Focus on the most likely explanations based on symptom patterns.
4. Your response must be medically coherent and consistent.
5. Provide risk level as: "emergency", "high", "medium", or "low"

User Information:
- Current Symptoms: {user_symptoms}
- Past Medical History: {user_history}
- Age: {user_age}
- Sex: {user_sex}
- Assessment Date: {current_date}

Please provide your assessment in the following JSON format:
{{
    "risk_level": "emergency/high/medium/low",
    "reasoning": "Detailed medical reasoning explaining the risk level and possible conditions",
    "possible_diseases": ["Disease 1", "Disease 2", "Disease 3"],
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
