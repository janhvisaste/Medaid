"""Shared emergency-detection logic.

This module is the single source of truth for rule-based emergency detection.
It must be used by every symptom-entry path (direct triage, the consultation
wizard, chat, and the AI triage engine itself) so a patient gets the same
emergency routing decision no matter which entry point they used.
"""

import re
from typing import Dict, List, Optional

EMERGENCY_KEYWORDS = [
    # Airway / breathing / consciousness
    "not breathing", "unconscious", "severe chest pain", "heavy bleeding",
    "sudden weakness", "slurred speech", "seizure", "severe burn",
    "blue lips", "very drowsy", "faint", "loss of consciousness",
    "can't breathe", "cannot breathe", "chest pain", "difficulty breathing",
    "severe bleeding", "uncontrolled bleeding", "passed out", "behosh",

    # Stroke signs
    "facial drooping", "face drooping", "drooping face",
    "one-sided weakness", "one sided weakness", "sudden confusion",

    # Cardiac
    "heart attack",

    # Allergic / anaphylaxis
    "anaphylaxis", "severe allergic reaction", "throat closing up",

    # Toxicology / self-harm
    "overdose", "suicidal", "suicide", "want to die", "kill myself",
    "poisoning", "poisoned",

    # GI / internal bleeding
    "vomiting blood", "coughing blood", "coughing up blood", "vomiting up blood",

    # Neurological
    "sudden numbness", "sudden paralysis", "can't move my", "cannot move my",

    # Abdominal
    "severe abdominal pain",

    # Pediatric
    "infant high fever", "baby high fever", "infant won't wake", "baby won't wake",

    # Pregnancy
    "pregnant and bleeding", "bleeding during pregnancy",
    "severe pregnancy pain", "pregnancy emergency",
]

NEGATION_TERMS = [
    "no", "not", "denies", "denying", "without", "negative for",
    "ruled out", "ruling out", "rule out", "no history of",
]

# How many characters immediately before a keyword match to scan for a
# negation term. Simple character-window heuristic, not a full NLP parse.
NEGATION_WINDOW_CHARS = 25

_NEGATION_PATTERNS = [re.compile(r"\b" + re.escape(term) + r"\b") for term in NEGATION_TERMS]

# Answers to a yes/no follow-up often echo the symptom back BEFORE the
# negation ("chest pain: no", "chest pain no,") rather than before it
# ("no chest pain") - especially when the assistant's own question named the
# symptom first. Deliberately narrow: the negation word must sit immediately
# after the keyword (only punctuation/whitespace between) and be immediately
# followed by punctuation or end-of-string. This catches direct answers
# without risking a real emergency where "no" modifies something else later
# in the sentence, e.g. "chest pain, no relief for two hours" must still
# trigger - "no" there is followed by "relief", not punctuation/end.
_FORWARD_NEGATION_TERMS = ["no", "not", "none", "negative", "nil"]
_FORWARD_NEGATION_PATTERN = re.compile(
    r"^[\s:;,\-–—]*(?:" + "|".join(_FORWARD_NEGATION_TERMS) + r")\b\s*(?:[,.;!?]|$)"
)


def _is_negated(lowered_text: str, keyword_index: int, keyword_len: int) -> bool:
    window_start = max(0, keyword_index - NEGATION_WINDOW_CHARS)
    backward_window = lowered_text[window_start:keyword_index]
    if any(pattern.search(backward_window) for pattern in _NEGATION_PATTERNS):
        return True

    forward_window = lowered_text[keyword_index + keyword_len:keyword_index + keyword_len + NEGATION_WINDOW_CHARS]
    return bool(_FORWARD_NEGATION_PATTERN.match(forward_window))


def contains_emergency_keyword(text: Optional[str]) -> bool:
    """Return True if text contains a non-negated emergency keyword."""
    if not text:
        return False
    lowered = text.lower()
    for keyword in EMERGENCY_KEYWORDS:
        search_from = 0
        while True:
            idx = lowered.find(keyword, search_from)
            if idx == -1:
                break
            if not _is_negated(lowered, idx, len(keyword)):
                return True
            search_from = idx + len(keyword)
    return False


EMERGENCY_REASONING = (
    "Critical emergency keywords detected in symptoms. Immediate medical attention required."
)

EMERGENCY_RECOMMENDATIONS = [
    "🚨 CALL EMERGENCY SERVICES IMMEDIATELY (108/112)",
    "Do NOT drive yourself - call ambulance",
    "Stay calm and await professional help",
    "If available, have someone stay with you",
    "Go to nearest Emergency Room immediately",
]

EMERGENCY_DISCLAIMER = (
    "⚠️ EMERGENCY: This is a medical emergency. Call emergency services (108/112) "
    "immediately. Do not delay seeking professional medical care."
)


def get_emergency_services_by_pincode(pincode: Optional[str]) -> Dict:
    """Return basic emergency contact info and example hospitals for a pincode prefix."""
    services = {
        "pincode": pincode,
        "emergency_numbers": {
            "ambulance": "108",
            "police": "100",
            "fire": "101",
            "women_helpline": "1091",
            "child_helpline": "1098",
            "national_emergency": "112",
        },
        "instructions": [
            "Call 108 for medical emergencies",
            "Call 112 for any emergency (integrated number)",
            "Keep your location ready when calling",
            "Stay on the line until help arrives",
        ],
    }

    pincode_prefix = pincode[:3] if pincode and len(pincode) >= 3 else ""

    city_hospitals = {
        "400": {
            "city": "Mumbai",
            "hospitals": [
                {"name": "KEM Hospital", "phone": "022-24107000", "address": "Acharya Donde Marg, Parel"},
                {"name": "Lilavati Hospital", "phone": "022-26567891", "address": "Bandra West"},
                {"name": "Hinduja Hospital", "phone": "022-44458888", "address": "Mahim"},
            ],
        },
        "110": {
            "city": "Delhi",
            "hospitals": [
                {"name": "AIIMS", "phone": "011-26588500", "address": "Ansari Nagar"},
                {"name": "Safdarjung Hospital", "phone": "011-26165060", "address": "Ring Road"},
                {"name": "Apollo Hospital", "phone": "011-26825858", "address": "Sarita Vihar"},
            ],
        },
        "560": {
            "city": "Bangalore",
            "hospitals": [
                {"name": "Victoria Hospital", "phone": "080-26700301", "address": "Fort Area"},
                {"name": "Manipal Hospital", "phone": "080-25023456", "address": "HAL Airport Road"},
                {"name": "Apollo Hospital", "phone": "080-26304050", "address": "Bannerghatta Road"},
            ],
        },
        "600": {
            "city": "Chennai",
            "hospitals": [
                {"name": "Apollo Hospital", "phone": "044-28296000", "address": "Greams Road"},
                {"name": "Fortis Malar", "phone": "044-42895555", "address": "Adyar"},
                {"name": "SIMS Hospital", "phone": "044-42855555", "address": "Vadapalani"},
            ],
        },
        "700": {
            "city": "Kolkata",
            "hospitals": [
                {"name": "SSKM Hospital", "phone": "033-22441000", "address": "College Street"},
                {"name": "Apollo Gleneagles", "phone": "033-23203040", "address": "EM Bypass"},
                {"name": "Fortis Hospital", "phone": "033-66283000", "address": "Anandapur"},
            ],
        },
    }

    if pincode_prefix in city_hospitals:
        services["city_info"] = city_hospitals[pincode_prefix]
    else:
        services["city_info"] = {
            "city": "Your Location",
            "message": "Call 108 for nearest hospital or search 'emergency hospital near me'",
        }

    return services


def build_emergency_assessment(symptoms_text: str, pincode: Optional[str] = None) -> Dict:
    """Build a structured emergency assessment dict.

    Shape matches what TriageEngineV2.assess() normally returns, so callers
    can treat a rule-triggered emergency and an AI assessment interchangeably.
    """
    emergency_services = get_emergency_services_by_pincode(pincode) if pincode else None

    recommendations: List[str] = list(EMERGENCY_RECOMMENDATIONS)
    if emergency_services and "city_info" in emergency_services:
        city_info = emergency_services["city_info"]
        if "hospitals" in city_info:
            recommendations.append(
                f"📍 Nearest hospitals in {city_info['city']} available - check response"
            )

    return {
        # An emergency is a real, high-confidence rule result - never degraded.
        "is_degraded": False,
        "risk_level": "emergency",
        "risk_probability": 1.0,
        "confidence": 1.0,
        "reasoning": EMERGENCY_REASONING,
        "possible_conditions": [
            {
                "disease": "Emergency Medical Condition",
                "confidence": 1.0,
                "supporting_evidence": ["Emergency keyword detected in symptoms"],
            }
        ],
        "reassurance": [],
        "ruled_out_conditions": [],
        "recommendations": recommendations,
        "follow_up_questions": [],
        "when_to_seek_care": "IMMEDIATELY - This is a medical emergency",
        "disclaimer": EMERGENCY_DISCLAIMER,
        "assessment_source": "emergency_rule",
        "requires_human_review": True,
        "emergency_services": emergency_services,
        # Same calibration/ontology contract as the AI path. Confidence here
        # is 1.0 because it comes from a deterministic keyword rule, not a
        # model estimate - so it is never capped.
        "reported_confidence": 1.0,
        "confidence_ceiling": 1.0,
        "confidence_was_capped": False,
        "input_specificity": "not_assessed",
        "input_specificity_score": 0,
        "input_word_count": 0,
        "short_input_cap_applied": False,
        "had_clarifying_round": False,
        "missing_detail": [],
        "confidence_explanation": (
            "This is a rule-based emergency match on your description, not an AI "
            "estimate. Seek emergency care now."
        ),
        "unrecognized_condition_count": 0,
        "has_unrecognized_conditions": False,
        "review_reasons": ["emergency_keyword_present"],
    }


def create_emergency_triage_record(
    *,
    user,
    symptoms_text: str,
    input_mode: str = "text",
    pincode: Optional[str] = None,
    medical_report_id: Optional[int] = None,
):
    """Persist a rule-detected emergency as a TriageRecord (+ children).

    Returns (triage_record, assessment_dict). All child rows are created
    atomically so a partial write can never leave an emergency record without
    its conditions/recommendations.
    """
    from django.db import transaction

    from ..models import PossibleCondition, Recommendation, TriageRecord
    from .clinician_alerts import create_alert_for_triage_record

    assessment = build_emergency_assessment(symptoms_text, pincode)

    with transaction.atomic():
        triage_record = TriageRecord.objects.create(
            user=user,
            current_symptoms=symptoms_text,
            input_mode=input_mode,
            risk_level="emergency",
            risk_probability=assessment["risk_probability"],
            reasoning=assessment["reasoning"],
            confidence=assessment["confidence"],
            assessment_source="emergency_rule",
            requires_human_review=True,
            medical_report_id=medical_report_id,
        )

        for condition in assessment["possible_conditions"]:
            PossibleCondition.objects.create(
                triage_record=triage_record,
                disease_name=condition["disease"],
                confidence=condition["confidence"],
            )

        for idx, rec in enumerate(assessment["recommendations"]):
            Recommendation.objects.create(
                triage_record=triage_record,
                recommendation_type="emergency",
                description=rec,
                priority=idx + 1,
            )

        create_alert_for_triage_record(triage_record)

    return triage_record, assessment
