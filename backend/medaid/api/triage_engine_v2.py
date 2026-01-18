"""
V2 Triage Engine with Multi-Stage Reasoning
Provides detailed disease predictions with probabilities, reasoning, and recommendations
"""

import os
import json
from typing import Dict, List, Any
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)


class TriageEngineV2:
    """
    V2 Triage Engine with detailed disease predictions and probabilities
    """
    
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-1.5-flash')
    
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
        try:
            # Build comprehensive prompt
            prompt = self._build_assessment_prompt(symptoms_text, user_data, report_summary, location)
            
            # Get AI assessment
            response = self.model.generate_content(prompt)
            result_text = response.text
            
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
        
        prompt = f"""You are an expert medical AI assistant. Analyze the following patient case and provide a detailed triage assessment.

**Patient Information:**
- Age: {user_data.get('age', 'Unknown')}
- Gender: {user_data.get('gender', 'Unknown')}
- Past Medical History: {', '.join(user_data.get('past_history', [])) if user_data.get('past_history') else 'None reported'}

**Current Symptoms:**
{symptoms}

**Medical Report Summary:**
{report if report else 'No medical report provided'}

**Location:**
{location if location else 'Not specified'}

**CRITICAL INSTRUCTIONS:**
You MUST provide a comprehensive medical triage assessment in JSON format. 

**IMPORTANT RULES:**
1. **DO NOT use generic disease names** like "Medical Condition Requiring Evaluation" or "Unknown Condition"
2. **ALWAYS provide SPECIFIC disease names** based on the symptoms (e.g., "Appendicitis", "Gastroenteritis", "Viral Infection", "Food Poisoning")
3. **List at least 3-5 specific possible conditions** with different confidence scores
4. **Each condition MUST have a realistic confidence score** between 0.15 and 0.40 (15% to 40%)
5. **Provide specific supporting evidence** for each condition
6. **Rule out at least 2 conditions** and explain why

**Required JSON Structure:**
{{
    "risk_level": "emergency|high|medium|low",
    "risk_probability": 0.0-1.0,
    "confidence": 0.0-1.0,
    "reasoning": "Detailed clinical reasoning explaining the assessment, referencing specific symptoms and their significance",
    "possible_conditions": [
        {{
            "disease": "SPECIFIC DISEASE NAME (e.g., Appendicitis, NOT 'Medical Condition')",
            "confidence": 0.15-0.40,
            "supporting_evidence": [
                "Specific symptom or finding 1",
                "Specific symptom or finding 2",
                "Clinical reasoning for this diagnosis"
            ]
        }},
        {{
            "disease": "ANOTHER SPECIFIC DISEASE NAME",
            "confidence": 0.15-0.40,
            "supporting_evidence": ["Evidence 1", "Evidence 2"]
        }},
        {{
            "disease": "THIRD SPECIFIC DISEASE NAME",
            "confidence": 0.10-0.30,
            "supporting_evidence": ["Evidence 1", "Evidence 2"]
        }}
    ],
    "ruled_out_conditions": [
        {{
            "condition": "Specific condition name",
            "reason": "Detailed explanation of why this was ruled out"
        }},
        {{
            "condition": "Another condition name",
            "reason": "Why this doesn't match the presentation"
        }}
    ],
    "recommendations": [
        "Specific, actionable recommendation 1",
        "Specific, actionable recommendation 2",
        "Specific, actionable recommendation 3"
    ],
    "follow_up_questions": [
        "Specific question to clarify symptoms 1",
        "Specific question to clarify symptoms 2"
    ],
    "when_to_seek_care": "Specific timeframe or triggers (e.g., 'If symptoms worsen within 24 hours' or 'Seek immediate care if...')",
    "disclaimer": "Appropriate medical disclaimer based on risk level"
}}

**Example of GOOD response for stomach pain:**
{{
    "possible_conditions": [
        {{"disease": "Appendicitis", "confidence": 0.30}},
        {{"disease": "Gastroenteritis", "confidence": 0.25}},
        {{"disease": "Food Poisoning", "confidence": 0.20}},
        {{"disease": "Stomach Ulcer", "confidence": 0.15}}
    ]
}}

**Example of BAD response (DO NOT DO THIS):**
{{
    "possible_conditions": [
        {{"disease": "Medical Condition Requiring Evaluation", "confidence": 0.60}}
    ]
}}

**Remember:**
- Be SPECIFIC with disease names
- Provide MULTIPLE conditions (3-5)
- Use REALISTIC confidence scores (15-40% each)
- Include detailed supporting evidence
- Rule out at least 2 conditions

Return ONLY the JSON object, no additional text."""

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
        
        # Ensure all required fields exist
        structured = {
            'risk_level': assessment.get('risk_level', 'medium').lower(),
            'risk_probability': float(assessment.get('risk_probability', 0.6)),
            'confidence': float(assessment.get('confidence', 0.7)),
            'reasoning': assessment.get('reasoning', f'Based on the symptoms: {symptoms}, medical evaluation is recommended.'),
            'possible_conditions': [],
            'ruled_out_conditions': assessment.get('ruled_out_conditions', []),
            'recommendations': assessment.get('recommendations', [
                'Consult a healthcare provider',
                'Monitor your symptoms',
                'Rest and stay hydrated'
            ]),
            'follow_up_questions': assessment.get('follow_up_questions', []),
            'when_to_seek_care': assessment.get('when_to_seek_care', 'If symptoms worsen or persist for more than 48 hours'),
            'disclaimer': assessment.get('disclaimer', self._get_default_disclaimer(assessment.get('risk_level', 'medium')))
        }
        
        # Structure possible conditions
        conditions = assessment.get('possible_conditions', [])
        for condition in conditions:
            if isinstance(condition, dict):
                structured['possible_conditions'].append({
                    'disease': condition.get('disease', 'Unknown Condition'),
                    'confidence': float(condition.get('confidence', 0.5)),
                    'supporting_evidence': condition.get('supporting_evidence', [])
                })
            elif isinstance(condition, str):
                # Simple string condition
                structured['possible_conditions'].append({
                    'disease': condition,
                    'confidence': 0.5,
                    'supporting_evidence': []
                })
        
        # Ensure at least one condition
        if not structured['possible_conditions']:
            structured['possible_conditions'].append({
                'disease': 'Medical Condition Requiring Evaluation',
                'confidence': 0.6,
                'supporting_evidence': ['Symptoms require professional assessment']
            })
        
        return structured
    
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
        """Fallback response when AI fails"""
        return {
            'risk_level': 'medium',
            'risk_probability': 0.6,
            'confidence': 0.5,
            'reasoning': f'Based on your symptoms ({symptoms}), we recommend consulting a healthcare provider for proper evaluation.',
            'possible_conditions': [
                {
                    'disease': 'Medical Condition Requiring Evaluation',
                    'confidence': 0.6,
                    'supporting_evidence': ['Symptoms require professional assessment']
                }
            ],
            'ruled_out_conditions': [],
            'recommendations': [
                'Consult a healthcare provider within 24-48 hours',
                'Monitor your symptoms closely',
                'Rest and stay hydrated',
                'Avoid self-medication without medical advice'
            ],
            'follow_up_questions': [],
            'when_to_seek_care': 'If symptoms worsen or persist for more than 48 hours',
            'disclaimer': self._get_default_disclaimer('medium')
        }


# Singleton instance
_triage_engine_v2 = None

def get_triage_engine_v2():
    """Get singleton instance of V2 triage engine"""
    global _triage_engine_v2
    if _triage_engine_v2 is None:
        _triage_engine_v2 = TriageEngineV2()
    return _triage_engine_v2
