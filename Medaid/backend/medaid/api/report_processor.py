# report_processor.py - Medical Report Analysis Module
import re
import json
import os
from typing import Dict, List, Tuple, Optional
from PIL import Image
import io
from dotenv import load_dotenv

load_dotenv()

try:
    from google import genai
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    if GOOGLE_API_KEY:
        client = genai.Client(api_key=GOOGLE_API_KEY)
        GEMINI_AVAILABLE = True
    else:
        GEMINI_AVAILABLE = False
        print("⚠️  GOOGLE_API_KEY not found. LLM report summarization unavailable.")
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️  google-genai not installed. Install with: pip install google-genai")

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    print("⚠️  PyMuPDF not installed. Install with: pip install PyMuPDF")

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False
    print("⚠️  pytesseract not installed. Install with: pip install pytesseract")

def summarize_medical_report_with_llm(extracted_text: str) -> Dict:
    """
    Use Google Gemini to summarize medical report in clinical terms
    
    Args:
        extracted_text: Raw text extracted from medical report
    
    Returns:
        Dict with summary, key_findings, abnormalities, and clinical notes
    """
    if not GEMINI_AVAILABLE or not extracted_text:
        return {
            "success": False,
            "error": "LLM not available or no text provided",
            "summary": extracted_text[:500] if extracted_text else ""
        }
    
    try:
        prompt = f"""
Analyze this medical report and provide a clinical summary in JSON format.

MEDICAL REPORT TEXT:
{extracted_text[:3000]}  

Provide a JSON response with:
{{
    "summary": "Brief 2-3 sentence clinical summary",
    "key_findings": ["finding 1", "finding 2", ...],
    "abnormalities": ["abnormality 1 with value", ...],
    "risk_indicators": ["any concerning patterns"],
    "suggested_focus": "What healthcare provider should prioritize",
    "patient_category": "adult/pediatric/geriatric"
}}

Focus on:
- Test results outside normal ranges
- Critical values requiring immediate attention
- Patterns suggesting specific conditions
- Overall health risk assessment

Respond ONLY with valid JSON, no other text.
"""
        
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt
        )
        
        # Extract JSON from response
        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        # Try to extract JSON
        start = response_text.find("{")
        end = response_text.rfind("}")
        if start != -1 and end != -1:
            response_text = response_text[start:end+1]
        
        result = json.loads(response_text)
        result["success"] = True
        return result
        
    except Exception as e:
        print(f"Error in LLM summarization: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
            "summary": f"Medical report analysis. {extracted_text[:300]}...",
            "key_findings": [],
            "abnormalities": [],
            "risk_indicators": [],
            "suggested_focus": "Manual review recommended"
        }

# Medical Parameter Normal Ranges
NORMAL_RANGES = {
    'hemoglobin': {
        'male': (13.5, 17.5),
        'female': (12.0, 15.5),
        'unit': 'g/dL',
        'interpretation': {
            'low': 'Low hemoglobin may indicate anemia, blood loss, or nutritional deficiency',
            'high': 'High hemoglobin may indicate dehydration, smoking, or polycythemia'
        }
    },
    'wbc_count': {
        'normal': (4000, 11000),
        'unit': '/μL',
        'interpretation': {
            'low': 'Low WBC count may indicate bone marrow problems, immune system disorders, or certain infections',
            'high': 'High WBC count may indicate infection, inflammation, or immune response'
        }
    },
    'rbc_count': {
        'male': (4.5, 5.5),
        'female': (4.0, 5.0),
        'unit': 'million/μL',
        'interpretation': {
            'low': 'Low RBC count may indicate anemia or blood loss',
            'high': 'High RBC count may indicate dehydration or lung disease'
        }
    },
    'platelet_count': {
        'normal': (150000, 450000),
        'unit': '/μL',
        'interpretation': {
            'low': 'Low platelet count increases bleeding risk',
            'high': 'High platelet count may increase clotting risk'
        }
    },
    'glucose_fasting': {
        'normal': (70, 100),
        'prediabetic': (100, 125),
        'diabetic': (126, 999),
        'unit': 'mg/dL',
        'interpretation': {
            'low': 'Low blood sugar (hypoglycemia) requires immediate attention',
            'high': 'High fasting glucose may indicate diabetes or prediabetes'
        }
    },
    'glucose_random': {
        'normal': (70, 140),
        'unit': 'mg/dL',
        'interpretation': {
            'low': 'Low blood sugar requires immediate attention',
            'high': 'High random glucose may indicate diabetes'
        }
    },
    'hba1c': {
        'normal': (0, 5.7),
        'prediabetic': (5.7, 6.4),
        'diabetic': (6.5, 15.0),
        'unit': '%',
        'interpretation': {
            'high': 'High HbA1c indicates poor blood sugar control over past 2-3 months'
        }
    },
    'creatinine': {
        'male': (0.9, 1.3),
        'female': (0.6, 1.1),
        'unit': 'mg/dL',
        'interpretation': {
            'low': 'Low creatinine may indicate muscle loss',
            'high': 'High creatinine may indicate kidney dysfunction'
        }
    },
    'urea': {
        'normal': (7, 20),
        'unit': 'mg/dL',
        'interpretation': {
            'high': 'High urea may indicate kidney problems or dehydration'
        }
    },
    'blood_pressure_systolic': {
        'normal': (90, 120),
        'elevated': (120, 129),
        'high': (130, 180),
        'unit': 'mmHg',
        'interpretation': {
            'low': 'Low blood pressure may cause dizziness and fainting',
            'high': 'High blood pressure increases risk of heart disease and stroke'
        }
    },
    'blood_pressure_diastolic': {
        'normal': (60, 80),
        'elevated': (80, 89),
        'high': (90, 120),
        'unit': 'mmHg',
        'interpretation': {
            'low': 'Low diastolic pressure may indicate cardiovascular issues',
            'high': 'High diastolic pressure increases cardiovascular risk'
        }
    },
    'cholesterol_total': {
        'normal': (0, 200),
        'borderline': (200, 239),
        'high': (240, 600),
        'unit': 'mg/dL',
        'interpretation': {
            'high': 'High cholesterol increases risk of heart disease'
        }
    },
    'ldl': {
        'optimal': (0, 100),
        'near_optimal': (100, 129),
        'borderline': (130, 159),
        'high': (160, 500),
        'unit': 'mg/dL',
        'interpretation': {
            'high': 'High LDL (bad cholesterol) increases heart disease risk'
        }
    },
    'hdl': {
        'low': (0, 40),
        'normal': (40, 60),
        'high': (60, 100),
        'unit': 'mg/dL',
        'interpretation': {
            'low': 'Low HDL (good cholesterol) increases heart disease risk',
            'high': 'High HDL is protective against heart disease'
        }
    },
    'triglycerides': {
        'normal': (0, 150),
        'borderline': (150, 199),
        'high': (200, 499),
        'very_high': (500, 2000),
        'unit': 'mg/dL',
        'interpretation': {
            'high': 'High triglycerides increase risk of heart disease and pancreatitis'
        }
    },
    'alt_sgpt': {
        'normal': (7, 56),
        'unit': 'U/L',
        'interpretation': {
            'high': 'Elevated ALT may indicate liver damage or disease'
        }
    },
    'ast_sgot': {
        'normal': (10, 40),
        'unit': 'U/L',
        'interpretation': {
            'high': 'Elevated AST may indicate liver or heart damage'
        }
    },
    'bilirubin_total': {
        'normal': (0.1, 1.2),
        'unit': 'mg/dL',
        'interpretation': {
            'high': 'High bilirubin may indicate liver disease or bile duct obstruction'
        }
    },
    'tsh': {
        'normal': (0.4, 4.0),
        'unit': 'mIU/L',
        'interpretation': {
            'low': 'Low TSH may indicate hyperthyroidism (overactive thyroid)',
            'high': 'High TSH may indicate hypothyroidism (underactive thyroid)'
        }
    },
    'vitamin_d': {
        'deficient': (0, 20),
        'insufficient': (20, 30),
        'sufficient': (30, 100),
        'unit': 'ng/mL',
        'interpretation': {
            'low': 'Low vitamin D affects bone health and immune function'
        }
    },
    'vitamin_b12': {
        'deficient': (0, 200),
        'normal': (200, 900),
        'unit': 'pg/mL',
        'interpretation': {
            'low': 'Low B12 can cause anemia and neurological problems'
        }
    }
}

# Keywords for Extraction
MEDICAL_KEYWORDS = {
    'hemoglobin': ['hemoglobin', 'hb', 'haemoglobin', 'hgb'],
    'wbc_count': ['wbc', 'white blood cell', 'leucocyte', 'leukocyte', 'tlc'],
    'rbc_count': ['rbc', 'red blood cell', 'erythrocyte'],
    'platelet_count': ['platelet', 'thrombocyte', 'plt'],
    'glucose_fasting': ['glucose fasting', 'fbs', 'fasting blood sugar', 'fasting glucose', 'fbg'],
    'glucose_random': ['glucose random', 'rbs', 'random blood sugar', 'blood glucose', 'rbg'],
    'hba1c': ['hba1c', 'glycated hemoglobin', 'glycohemoglobin', 'a1c'],
    'creatinine': ['creatinine', 'serum creatinine', 'creat'],
    'urea': ['urea', 'blood urea', 'bun'],
    'blood_pressure_systolic': ['bp systolic', 'systolic bp', 'sbp', 'systolic'],
    'blood_pressure_diastolic': ['bp diastolic', 'diastolic bp', 'dbp', 'diastolic'],
    'cholesterol_total': ['total cholesterol', 'cholesterol total', 'tc', 'serum cholesterol'],
    'ldl': ['ldl', 'ldl cholesterol', 'low density lipoprotein'],
    'hdl': ['hdl', 'hdl cholesterol', 'high density lipoprotein'],
    'triglycerides': ['triglycerides', 'tg', 'serum triglycerides'],
    'alt_sgpt': ['alt', 'sgpt', 'alanine aminotransferase'],
    'ast_sgot': ['ast', 'sgot', 'aspartate aminotransferase'],
    'bilirubin_total': ['bilirubin total', 'total bilirubin', 't bili'],
    'tsh': ['tsh', 'thyroid stimulating hormone', 'thyrotropin'],
    'vitamin_d': ['vitamin d', 'vit d', '25-oh vitamin d', 'calcidiol'],
    'vitamin_b12': ['vitamin b12', 'vit b12', 'cobalamin', 'b 12']
}


class ReportProcessor:
    """Medical Report Analysis and Interpretation"""
    
    def __init__(self):
        self.normal_ranges = NORMAL_RANGES
        self.keywords = MEDICAL_KEYWORDS
    
    def extract_text_from_pdf(self, file_bytes: bytes) -> str:
        """Extract text from PDF file"""
        if not PYMUPDF_AVAILABLE:
            return "PDF processing not available. Please install PyMuPDF."
        
        try:
            pdf_document = fitz.open(stream=file_bytes, filetype="pdf")
            text = ""
            for page_num in range(pdf_document.page_count):
                page = pdf_document[page_num]
                text += page.get_text()
            pdf_document.close()
            return text
        except Exception as e:
            print(f"Error reading PDF: {e}")
            return f"Error: {str(e)}"
    
    def extract_text_from_image(self, file_bytes: bytes) -> str:
        """Extract text from image using OCR"""
        if not PYTESSERACT_AVAILABLE:
            return "OCR not available. Please install pytesseract."
        
        try:
            image = Image.open(io.BytesIO(file_bytes))
            text = pytesseract.image_to_string(image)
            return text
        except Exception as e:
            print(f"Error processing image: {e}")
            return f"Error: {str(e)}"
    
    def extract_medical_values(self, text: str) -> Dict[str, float]:
        """Extract medical parameter values from text"""
        structured_data = {}
        
        # Clean and normalize text
        text = text.lower().replace('\n', ' ')
        
        for param, keywords in self.keywords.items():
            for keyword in keywords:
                # Patterns to match parameter name followed by value
                patterns = [
                    rf'{keyword}\s*:?\s*(\d+\.?\d*)',  # Basic: keyword: 123
                    rf'{keyword}\s*[-=:]\s*(\d+\.?\d*)',  # With separator
                    rf'(\d+\.?\d*)\s*{keyword}',  # Value before keyword
                    rf'{keyword}.*?(\d+\.?\d*)',  # Keyword with some text then value
                ]
                
                for pattern in patterns:
                    matches = re.findall(pattern, text, re.IGNORECASE)
                    if matches:
                        try:
                            value = float(matches[0])
                            structured_data[param] = value
                            break
                        except (ValueError, IndexError):
                            continue
                
                if param in structured_data:
                    break
        
        return structured_data
    
    def interpret_values(self, structured_data: Dict[str, float], 
                        patient_sex: str = 'unknown', 
                        patient_age: int = None) -> Dict:
        """Interpret medical values against normal ranges"""
        interpretations = {}
        abnormal_results = []
        
        for param, value in structured_data.items():
            if param not in self.normal_ranges:
                continue
            
            range_info = self.normal_ranges[param]
            
            # Get appropriate range based on sex
            if patient_sex.lower() in ['male', 'female', 'm', 'f']:
                sex_key = 'male' if patient_sex.lower() in ['male', 'm'] else 'female'
                if sex_key in range_info:
                    normal_range = range_info[sex_key]
                elif 'normal' in range_info:
                    normal_range = range_info['normal']
                else:
                    normal_range = list(range_info.values())[0] if isinstance(list(range_info.values())[0], tuple) else (0, 999999)
            elif 'normal' in range_info:
                normal_range = range_info['normal']
            else:
                # Use first available range
                for key, val in range_info.items():
                    if isinstance(val, tuple):
                        normal_range = val
                        break
            
            unit = range_info.get('unit', '')
            
            # Determine status
            status = 'Normal'
            concern_level = 'None'
            interpretation_text = f"{param.replace('_', ' ').title()}: {value} {unit} is within normal range"
            
            if value < normal_range[0]:
                status = 'Low'
                concern_level = self._get_concern_level(param, 'low', value, normal_range[0])
                interpretation_text = range_info.get('interpretation', {}).get('low', f'Low {param}')
                abnormal_results.append({
                    'test': param.replace('_', ' ').title(),
                    'value': value,
                    'unit': unit,
                    'status': status,
                    'concern_level': concern_level,
                    'interpretation': interpretation_text
                })
            
            elif value > normal_range[1]:
                status = 'High'
                concern_level = self._get_concern_level(param, 'high', value, normal_range[1])
                interpretation_text = range_info.get('interpretation', {}).get('high', f'High {param}')
                abnormal_results.append({
                    'test': param.replace('_', ' ').title(),
                    'value': value,
                    'unit': unit,
                    'status': status,
                    'concern_level': concern_level,
                    'interpretation': interpretation_text
                })
            
            interpretations[param] = {
                'value': value,
                'unit': unit,
                'status': status,
                'concern_level': concern_level,
                'normal_range': normal_range,
                'interpretation': interpretation_text
            }
        
        return {
            'interpretations': interpretations,
            'abnormal_results': abnormal_results,
            'summary': self._generate_summary(abnormal_results)
        }
    
    def _get_concern_level(self, param: str, status: str, value: float, threshold: float) -> str:
        """Determine concern level based on how far value is from normal"""
        deviation_percent = abs((value - threshold) / threshold * 100)
        
        # Critical parameters
        critical_params = ['glucose_fasting', 'glucose_random', 'creatinine', 'blood_pressure_systolic']
        
        if param in critical_params:
            if deviation_percent > 50:
                return 'High'
            elif deviation_percent > 20:
                return 'Moderate'
            else:
                return 'Low'
        else:
            if deviation_percent > 100:
                return 'High'
            elif deviation_percent > 30:
                return 'Moderate'
            else:
                return 'Low'
    
    def _generate_summary(self, abnormal_results: List[Dict]) -> str:
        """Generate overall summary of abnormal results"""
        if not abnormal_results:
            return "All test results are within normal ranges."
        
        high_concern = [r for r in abnormal_results if r['concern_level'] == 'High']
        moderate_concern = [r for r in abnormal_results if r['concern_level'] == 'Moderate']
        low_concern = [r for r in abnormal_results if r['concern_level'] == 'Low']
        
        summary_parts = []
        
        if high_concern:
            summary_parts.append(f"{len(high_concern)} test(s) with high concern requiring immediate medical attention")
        if moderate_concern:
            summary_parts.append(f"{len(moderate_concern)} test(s) with moderate concern requiring follow-up")
        if low_concern:
            summary_parts.append(f"{len(low_concern)} test(s) slightly outside normal range")
        
        return ". ".join(summary_parts) + "."
    
    def process_report(self, file_bytes: bytes, file_type: str, 
                      patient_sex: str = 'unknown', patient_age: int = None) -> Dict:
        """
        Main method to process medical report
        
        Args:
            file_bytes: File content as bytes
            file_type: 'pdf' or 'image'
            patient_sex: Patient's sex for context
            patient_age: Patient's age for context
        
        Returns:
            Dict with extracted_text, structured_data, interpretations
        """
        # Extract text
        if file_type.lower() == 'pdf':
            extracted_text = self.extract_text_from_pdf(file_bytes)
        else:
            extracted_text = self.extract_text_from_image(file_bytes)
        
        if not extracted_text or extracted_text.startswith("Error"):
            return {
                'success': False,
                'error': 'Could not extract text from report',
                'extracted_text': extracted_text
            }
        
        # Extract medical values
        structured_data = self.extract_medical_values(extracted_text)
        
        if not structured_data:
            return {
                'success': False,
                'error': 'No medical parameters found in report',
                'extracted_text': extracted_text,
                'structured_data': {}
            }
        
        # Interpret values
        interpretation_result = self.interpret_values(structured_data, patient_sex, patient_age)
        
        return {
            'success': True,
            'extracted_text': extracted_text,
            'structured_data': structured_data,
            'interpretations': interpretation_result['interpretations'],
            'abnormal_results': interpretation_result['abnormal_results'],
            'summary': interpretation_result['summary']
        }


# Global instance
_report_processor = None

def get_report_processor():
    """Get singleton instance of report processor"""
    global _report_processor
    if _report_processor is None:
        _report_processor = ReportProcessor()
    return _report_processor
