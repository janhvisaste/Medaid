# clinical_nlp_engine.py
import os
import json
import fasttext
import spacy
import medspacy
from typing import List, Dict, Optional
from openai import OpenAI
from datetime import datetime

# ---------------------------
# INITIALIZATION
# ---------------------------

FASTTEXT_MODEL_PATH = "lid.176.bin"
LANG_MODEL = fasttext.load_model(FASTTEXT_MODEL_PATH)

nlp = spacy.load("en_core_web_sm")
medspacy.load(nlp)

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------------------------
# DATA MODELS
# ---------------------------

class Symptom:
    def __init__(
        self,
        name: str,
        severity: Optional[str] = None,
        duration_days: Optional[int] = None,
        onset: Optional[str] = None,
        trend: Optional[str] = None,
        negated: bool = False,
    ):
        self.name = name
        self.severity = severity
        self.duration_days = duration_days
        self.onset = onset
        self.trend = trend
        self.negated = negated

    def to_dict(self):
        return self.__dict__


# ---------------------------
# LANGUAGE DETECTION
# ---------------------------

def detect_language(text: str) -> str:
    label, confidence = LANG_MODEL.predict(text)
    return label[0].replace("__label__", "")


# ---------------------------
# SYMPTOM EXTRACTION (spaCy + GPT)
# ---------------------------

def extract_symptom_entities(text: str) -> List[str]:
    """
    spaCy + medspaCy entity extraction with negation awareness
    """
    doc = nlp(text)
    symptoms = []

    for ent in doc.ents:
        if ent.label_.lower() in ["problem", "symptom", "disease"]:
            symptoms.append(ent.text.lower())

    # fallback: noun chunks
    if not symptoms:
        symptoms = [chunk.text.lower() for chunk in doc.noun_chunks]

    return list(set(symptoms))


def enrich_symptoms_with_gpt(raw_text: str, entities: List[str]) -> List[Symptom]:
    """
    GPT extracts severity, duration, onset, trend
    """
    prompt = f"""
You are a medical NLP engine.
Extract structured symptom data in STRICT JSON.

Symptoms detected: {entities}
Text: "{raw_text}"

Return JSON array with:
- name
- severity (mild/moderate/severe/unknown)
- duration_days (int or null)
- onset (sudden/gradual/unknown)
- trend (improving/worsening/static/unknown)
- negated (true/false)

JSON ONLY.
"""

    response = openai_client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    data = json.loads(response.choices[0].message.content)

    return [Symptom(**item) for item in data]


# ---------------------------
# TEMPORAL + RISK SCORING ENGINE
# ---------------------------

RISK_WEIGHTS = {
    "fever": 2,
    "body pain": 1,
    "headache": 1,
    "chest pain": 5,
    "shortness of breath": 4,
}

def compute_risk_score(
    symptoms: List[Symptom], age: int, sex: str
) -> int:
    score = 0

    for s in symptoms:
        if s.negated:
            continue

        score += RISK_WEIGHTS.get(s.name, 0)

        if s.duration_days and s.duration_days >= 3:
            score += 1

        if s.trend == "worsening":
            score += 2

        if s.severity == "severe":
            score += 2

    if age >= 60:
        score += 2

    if sex.lower() == "female":
        score += 1

    return score


def map_score_to_risk(score: int) -> str:
    if score >= 9:
        return "emergency"
    if score >= 6:
        return "high"
    if score >= 3:
        return "medium"
    return "low"


# ---------------------------
# FOLLOW-UP QUESTION ENGINE
# ---------------------------

def generate_follow_up_questions(symptoms: List[Symptom]) -> List[str]:
    incomplete = [
        s.name for s in symptoms if not s.severity or not s.duration_days
    ]

    if not incomplete:
        return []

    prompt = f"""
You are a medical triage nurse.
Ask MAX 2 follow-up questions to reduce uncertainty.

Incomplete symptoms: {incomplete}

Return JSON array of questions.
"""

    response = openai_client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )

    return json.loads(response.choices[0].message.content)


# ---------------------------
# MAIN PIPELINE FUNCTION
# ---------------------------

def structured_symptom_pipeline(
    text: str, age: int, sex: str
) -> Dict:
    language = detect_language(text)
    entities = extract_symptom_entities(text)
    symptoms = enrich_symptoms_with_gpt(text, entities)

    risk_score = compute_risk_score(symptoms, age, sex)
    risk_level = map_score_to_risk(risk_score)

    followups = []
    if risk_level in ["medium", "high"]:
        followups = generate_follow_up_questions(symptoms)

    confidence = min(0.95, 0.4 + (risk_score * 0.05))
    if followups:
        confidence *= 0.8

    return {
        "language": language,
        "symptoms": [s.to_dict() for s in symptoms],
        "risk_score": risk_score,
        "risk_level": risk_level,
        "confidence": round(confidence, 2),
        "follow_up_questions": followups,
    }
