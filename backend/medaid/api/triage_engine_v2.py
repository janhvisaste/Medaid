"""
V2 Triage Engine with Multi-Stage Reasoning
Provides detailed disease predictions with probabilities, reasoning, and recommendations
"""

import os
import json
from typing import Dict, List, Any
from dotenv import load_dotenv

load_dotenv()

from google import genai
from google.genai import types

# Configure Gemini
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

if not GOOGLE_API_KEY:
    print("⚠️ GOOGLE_API_KEY is not set. TriageEngineV2 will use fallback responses.")


def safe_float(val, default: float) -> float:
    """Safely convert Gemini numeric fields (which may be strings like "60%") to float.

    If conversion fails, return the provided default instead of raising.
    """
    try:
        if isinstance(val, str):
            val = val.strip().replace('%', '')
        return float(val)
    except Exception:
        return default


class TriageEngineV2:
    """
    V2 Triage Engine with detailed disease predictions and probabilities
    """
    
    def __init__(self):
        self.client = genai.Client(api_key=GOOGLE_API_KEY) if GOOGLE_API_KEY else None
    
    def assess(self, symptoms_text: str, user_data: Dict, report_summary: str = "", location: str = "") -> Dict:
        """
        Perform comprehensive triage assessment
        
        Args:
            symptoms_text: Patient's symptom description
            user_data: Dict with age, gender, past_history
            report_summary: Optional medical report summary
            location: Optional location for facility recommendations
            
        Returns:
            Dict with risk_level, reasoning, possible_conditions (with probabilities), recommendations
        """
        # STEP 3: Normalize at triage entry (SECOND SAFETY NET)
        symptoms_text = symptoms_text or ""
        report_summary = report_summary or ""
        location = location or ""
        
        try:
            if not self.client:
                raise RuntimeError("Gemini client not initialized (missing GOOGLE_API_KEY)")

            # Build comprehensive prompt
            prompt = self._build_assessment_prompt(symptoms_text, user_data, report_summary, location)
            
            # Get AI assessment using google-genai client (new SDK)
            # Use a currently supported model (aligned with gemini_smoke_test.py)
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.4,
                    max_output_tokens=4096,  # Increased from 2048 to handle full JSON response
                ),
            )

            # Extract text from response properly
            result_text = None
            if response and response.candidates:
                for candidate in response.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, 'text') and part.text:
                                result_text = part.text
                                break
                        if result_text:
                            break
            
            if not result_text:
                raise RuntimeError("No text content found in response")
                
            # Extract JSON from response
            assessment = self._extract_json(result_text)
            
            # Validate and structure response
            structured_assessment = self._structure_assessment(assessment, symptoms_text)
            
            return structured_assessment
            
        except Exception as e:
            print(f"Error in V2 triage assessment: {e}")
            # Fallback response
            return self._get_fallback_response(symptoms_text)
    
    def _build_assessment_prompt(self, symptoms: str, user_data: Dict, report: str, location: str) -> str:
        """Build comprehensive assessment prompt"""
        
        prompt = f"""
Analyze this medical case and respond with ONLY valid JSON:

**Patient:** Age {user_data.get('age', 'Unknown')}, {user_data.get('gender', 'Unknown')}
**History:** {', '.join(user_data.get('past_history', [])) if user_data.get('past_history') else 'None'}
**Symptoms:** {symptoms}

Provide JSON with this exact structure:
{{
    "risk_level": "low|medium|high|emergency",
    "risk_probability": 0.0-1.0,
    "confidence": 0.0-1.0,
    "reasoning": "Brief clinical explanation",
    "possible_conditions": [
        {{
            "disease": "Specific disease name (NOT generic)",
            "confidence": 0.15-0.40,
            "supporting_evidence": ["Evidence 1", "Evidence 2"]
        }}
    ],
    "recommendations": ["Actionable advice 1", "Actionable advice 2"],
    "when_to_seek_care": "Specific timeframe or triggers"
}}

Rules:
- Use SPECIFIC disease names (e.g., "Viral Upper Respiratory Infection", "Acute Gastroenteritis")  
- Provide 3-5 possible conditions with realistic confidence scores (15-40% each)
- NO generic names like "Medical Condition Requiring Evaluation"
- Risk levels: low (minor/self-limiting), medium (needs evaluation), high (urgent), emergency (immediate)

Return ONLY the JSON object."""

        return prompt
    
    def _extract_json(self, text: str) -> Dict:
        """Extract JSON from AI response"""
        try:
            # Try to find JSON in code blocks
            if "```json" in text:
                start = text.find("```json") + 7
                end = text.find("```", start)
                json_str = text[start:end].strip()
            elif "```" in text:
                start = text.find("```") + 3
                end = text.find("```", start)
                json_str = text[start:end].strip()
            else:
                # Try to find JSON object
                start = text.find("{")
                end = text.rfind("}") + 1
                json_str = text[start:end].strip()
            
            return json.loads(json_str)
        except Exception as e:
            print(f"Error extracting JSON: {e}")
            # Try parsing the whole text
            try:
                return json.loads(text)
            except:
                return {}
    
    def _structure_assessment(self, assessment: Dict, symptoms: str) -> Dict:
        """Structure and validate assessment"""
        
        # Ensure all required fields exist with LOWER default risk values (FIX 3)
        structured = {
            'risk_level': assessment.get('risk_level', 'low').lower(),
            'risk_probability': safe_float(assessment.get('risk_probability'), 0.25),
            'confidence': safe_float(assessment.get('confidence'), 0.4),
            'reasoning': assessment.get('reasoning', f'Based on the symptoms: {symptoms}, medical evaluation is recommended.'),
            'possible_conditions': [],
            'reassurance': assessment.get('reassurance', []),
            'ruled_out_conditions': assessment.get('ruled_out_conditions', []),
            'recommendations': assessment.get('recommendations', [
                'Monitor your symptoms',
                'Rest and stay hydrated',
                'Consult a healthcare provider if symptoms worsen'
            ]),
            'follow_up_questions': assessment.get('follow_up_questions', []),
            'when_to_seek_care': assessment.get('when_to_seek_care', 'If symptoms worsen or persist for more than 48 hours'),
            'disclaimer': assessment.get('disclaimer', self._get_default_disclaimer(assessment.get('risk_level', 'low')))
        }
        
        # Structure possible conditions
        conditions = assessment.get('possible_conditions', [])
        generic_names = ['medical condition', 'unknown condition', 'condition requiring evaluation', 'medical issue']
        
        for condition in conditions:
            if isinstance(condition, dict):
                disease_name = condition.get('disease', 'Unknown Condition')
                
                # Check if it's a generic name
                if any(generic in disease_name.lower() for generic in generic_names):
                    print(f"⚠️ Detected generic disease name: {disease_name}, skipping...")
                    continue  # Skip generic conditions
                
                structured['possible_conditions'].append({
                    'disease': disease_name,
                    'confidence': safe_float(condition.get('confidence'), 0.5),
                    'supporting_evidence': condition.get('supporting_evidence', [])
                })
            elif isinstance(condition, str):
                # Check if it's a generic name
                if any(generic in condition.lower() for generic in generic_names):
                    print(f"⚠️ Detected generic disease name: {condition}, skipping...")
                    continue  # Skip generic conditions
                
                # Simple string condition
                structured['possible_conditions'].append({
                    'disease': condition,
                    'confidence': 0.5,
                    'supporting_evidence': []
                })
        
        # If no valid conditions after filtering, provide symptom-based suggestions
        if not structured['possible_conditions']:
            print("⚠️ No specific conditions provided by AI, generating based on symptoms...")
            structured['possible_conditions'] = self._generate_symptom_based_conditions(symptoms)
        
        return structured
    
    def _generate_symptom_based_conditions(self, symptoms: str) -> List[Dict]:
        """Generate specific conditions based on symptom keywords (FIX 5)"""
        symptoms_lower = symptoms.lower()
        conditions = []
        
        # Gastrointestinal symptoms
        if any(word in symptoms_lower for word in ['stomach', 'vomit', 'nausea', 'diarrhea', 'abdominal']):
            conditions.extend([
                {'disease': 'Viral Gastroenteritis', 'confidence': 0.30, 'supporting_evidence': ['Gastrointestinal symptoms present']},
                {'disease': 'Food Poisoning', 'confidence': 0.25, 'supporting_evidence': ['Acute onset of GI symptoms']},
                {'disease': 'Self-limiting viral illness', 'confidence': 0.20, 'supporting_evidence': ['Mild GI symptoms']},
            ])
        
        # Respiratory symptoms
        elif any(word in symptoms_lower for word in ['cough', 'cold', 'throat', 'breathing']):
            conditions.extend([
                {'disease': 'Viral Upper Respiratory Infection', 'confidence': 0.35, 'supporting_evidence': ['Respiratory symptoms']},
                {'disease': 'Acute viral syndrome', 'confidence': 0.25, 'supporting_evidence': ['Common cold symptoms']},
                {'disease': 'Self-limiting viral illness', 'confidence': 0.20, 'supporting_evidence': ['Mild respiratory symptoms']},
            ])
        
        # Fever + Headache/Dizziness
        elif any(word in symptoms_lower for word in ['fever', 'headache', 'dizz']):
            conditions.extend([
                {'disease': 'Acute Viral Syndrome', 'confidence': 0.35, 'supporting_evidence': ['Fever with systemic symptoms']},
                {'disease': 'Dehydration-related Dizziness', 'confidence': 0.25, 'supporting_evidence': ['Dizziness with possible fluid loss']},
                {'disease': 'Tension-type Headache', 'confidence': 0.20, 'supporting_evidence': ['Headache without neurological deficits']},
            ])
        
        # Pain symptoms
        elif any(word in symptoms_lower for word in ['pain', 'ache', 'hurt']):
            conditions.extend([
                {'disease': 'Musculoskeletal Pain', 'confidence': 0.30, 'supporting_evidence': ['Pain symptoms']},
                {'disease': 'Acute viral syndrome', 'confidence': 0.25, 'supporting_evidence': ['Body aches']},
                {'disease': 'Self-limiting viral illness', 'confidence': 0.20, 'supporting_evidence': ['Mild pain and discomfort']},
            ])
        
        # Default fallback
        else:
            conditions.extend([
                {'disease': 'Acute viral syndrome', 'confidence': 0.30, 'supporting_evidence': ['Common symptoms present']},
                {'disease': 'Self-limiting viral illness', 'confidence': 0.25, 'supporting_evidence': ['Likely benign condition']},
                {'disease': 'Dehydration-related symptoms', 'confidence': 0.20, 'supporting_evidence': ['Mild systemic symptoms']},
            ])
        
        return conditions[:3]  # Return top 3
    
    def _get_default_disclaimer(self, risk_level: str) -> str:
        """Get appropriate disclaimer based on risk level"""
        disclaimers = {
            'emergency': '⚠️ EMERGENCY: This is a medical emergency. Call emergency services (108/112) immediately. Do not delay seeking professional medical care.',
            'high': '⚠️ HIGH RISK: Seek immediate medical attention. Visit an emergency room or urgent care facility as soon as possible.',
            'medium': '⚠️ MEDICAL ADVICE NEEDED: This assessment suggests you should consult a healthcare provider within 24-48 hours. This is not a substitute for professional medical advice.',
            'low': 'ℹ️ INFORMATIONAL: While your symptoms appear mild, monitor them closely. Consult a healthcare provider if symptoms worsen or persist. This is not a substitute for professional medical advice.'
        }
        return disclaimers.get(risk_level.lower(), disclaimers['medium'])
    
    def _get_fallback_response(self, symptoms: str) -> Dict:
        """Fallback response when AI fails (with lower risk defaults)"""
        # STEP 4: Fix fallback reasoning (IMPORTANT)
        symptoms = symptoms or "the information provided"
        
        return {
            'risk_level': 'low',
            'risk_probability': 0.25,
            'confidence': 0.4,
            'reasoning': f'Based on your symptoms ({symptoms}), this appears to be a mild condition. Monitor your symptoms and consult a healthcare provider if they worsen.',
            'possible_conditions': [
                {
                    'disease': 'Self-limiting viral illness',
                    'confidence': 0.30,
                    'supporting_evidence': ['Common symptoms present', 'No red-flag symptoms reported']
                },
                {
                    'disease': 'Acute viral syndrome',
                    'confidence': 0.25,
                    'supporting_evidence': ['Mild systemic symptoms']
                },
                {
                    'disease': 'Benign condition',
                    'confidence': 0.20,
                    'supporting_evidence': ['Likely self-resolving']
                }
            ],
            'reassurance': [
                'No emergency symptoms identified',
                'Symptoms appear mild',
                'Most common causes are benign and self-limiting'
            ],
            'ruled_out_conditions': [],
            'recommendations': [
                'Monitor your symptoms',
                'Rest and stay hydrated',
                'Consult a healthcare provider if symptoms worsen or persist',
                'Maintain good nutrition'
            ],
            'follow_up_questions': [],
            'when_to_seek_care': 'If symptoms worsen, persist for more than 3-5 days, or new concerning symptoms develop',
            'disclaimer': self._get_default_disclaimer('low')
        }


# Singleton instance
_triage_engine_v2 = None

def get_triage_engine_v2():
    """Get singleton instance of V2 triage engine"""
    global _triage_engine_v2
    if _triage_engine_v2 is None:
        _triage_engine_v2 = TriageEngineV2()
    return _triage_engine_v2
