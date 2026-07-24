"""
V2 Triage Engine with Multi-Stage Reasoning
Provides detailed disease predictions with probabilities, reasoning, and recommendations

Provider strategy: the caller's selected provider is tried first (OpenRouter
when an allow-listed model_id is supplied, otherwise the default Gemini
provider). If it raises ModelProviderError, the engine makes exactly one
cross-provider failover attempt against the other configured provider before
returning a degraded response. Failover to OpenRouter requires
settings.TRIAGE_FALLBACK_OPENROUTER_MODEL to be set.

Safety nets, in order: an emergency-keyword short-circuit runs before any LLM
call; after parsing, the model's own risk tier is floored to 'high' if
emergency keywords are present in the symptom text.
"""

import os
import json
import logging
from typing import Dict, List, Any
from django.conf import settings
from dotenv import load_dotenv

from .assessment_quality import calibrate_confidence, validate_conditions
from .llm_providers import GeminiProvider, ModelProviderError, OpenRouterProvider
from .llm_providers.base import provider_log_context, provider_request_context
from .llm_providers.catalog import is_allowed_openrouter_model, resolve_fallback_openrouter_model
from .safety.emergency_check import build_emergency_assessment, contains_emergency_keyword

load_dotenv()

# Configure Gemini
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
logger = logging.getLogger(__name__)

if not GOOGLE_API_KEY:
    logger.warning("triage.default_provider_unconfigured", extra={"provider": "gemini"})


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
    
    def __init__(self, default_provider=None, openrouter_provider=None):
        self.default_provider = default_provider or GeminiProvider(api_key=GOOGLE_API_KEY)
        self.openrouter_provider = openrouter_provider or OpenRouterProvider()
        self.default_model = getattr(settings, "DEFAULT_TRIAGE_MODEL", "google/gemini-2.5-flash")
        self.temperature = getattr(settings, "TRIAGE_MODEL_TEMPERATURE", 0.4)
        self.client = self.default_provider if getattr(self.default_provider, "is_available", False) else None
    
    def assess(
        self,
        symptoms_text: str,
        user_data: Dict,
        report_summary: str = "",
        location: str = "",
        model_id: str = None,
        *,
        request_id: str | None = None,
        user_id: int | None = None,
        had_clarifying_round: bool = False,
        skip_emergency_recheck: bool = False,
    ) -> Dict:
        """
        Perform comprehensive triage assessment

        Args:
            symptoms_text: Patient's symptom description
            user_data: Dict with age, gender, past_history
            report_summary: Optional medical report summary
            location: Optional location for facility recommendations
            had_clarifying_round: True when the patient has already answered
                follow-up questions. Lifts the short-input confidence cap,
                since they were given a chance to elaborate.
            skip_emergency_recheck: True when the caller already ran
                contains_emergency_keyword() on the patient's raw, single-turn
                message before merging in anything AI-authored (a clarifying
                question's own wording, or prior chat turns). Callers that
                build symptoms_text by prepending/appending assistant text -
                e.g. "Q: Are you experiencing chest pain? A: No" - must set
                this, because the keyword scan below can't tell who said
                "chest pain": a clarifying question routinely NAMES the
                symptom it's asking about, so re-scanning the merged text
                here would trigger on the assistant's own question wording
                regardless of how the patient answered it.

        Returns:
            Dict with risk_level, reasoning, possible_conditions (with probabilities), recommendations
        """
        # STEP 3: Normalize at triage entry (SECOND SAFETY NET)
        symptoms_text = symptoms_text or ""
        report_summary = report_summary or ""
        location = location or ""
        log_context = {"request_id": request_id, "user_id": user_id}

        # IMMEDIATE EMERGENCY CHECK - safety net for any caller that invokes
        # this engine directly without its own emergency short-circuit. Must
        # run before any LLM call. Skipped only when the caller has already
        # verified the raw patient message (see skip_emergency_recheck above).
        if not skip_emergency_recheck and contains_emergency_keyword(symptoms_text):
            logger.warning("triage.emergency_keyword_detected_in_engine", extra=log_context)
            emergency_assessment = build_emergency_assessment(symptoms_text)
            emergency_assessment['model_id'] = None
            emergency_assessment['model_provider'] = None
            emergency_assessment['degraded'] = False
            return emergency_assessment

        try:
            # Build comprehensive prompt
            prompt = self._build_assessment_prompt(symptoms_text, user_data, report_summary, location)

            selected_model = self._resolve_model_id(model_id)
            if not selected_model and not self.client:
                raise RuntimeError("Gemini client not initialized (missing GOOGLE_API_KEY)")

            messages = [{"role": "user", "content": prompt}]

            # Primary provider first, then a single cross-provider failover
            # attempt against the other configured provider.
            attempts = self._build_provider_attempts(selected_model)
            primary_model, primary_provider_name = attempts[0][1], attempts[0][2]

            result_text = None
            model_to_call = None
            provider_name = None
            used_fallback = False
            last_error = None

            for index, (provider, candidate_model, candidate_provider_name) in enumerate(attempts):
                is_last_attempt = index == len(attempts) - 1
                try:
                    with provider_request_context(**log_context):
                        result_text = provider.complete(messages, candidate_model, self.temperature)
                except ModelProviderError as error:
                    last_error = error
                    logger.warning(
                        "triage.provider_failed",
                        extra={
                            **log_context,
                            "model_id": candidate_model,
                            "provider": candidate_provider_name,
                            "status_code": error.status_code,
                            "error_type": type(error).__name__,
                            "will_failover": not is_last_attempt,
                        },
                    )
                    continue

                model_to_call = candidate_model
                provider_name = candidate_provider_name
                used_fallback = index > 0
                last_error = None
                logger.info(
                    "triage.provider_completed",
                    extra={
                        **log_context,
                        "model_id": model_to_call,
                        "provider": provider_name,
                        "used_fallback_provider": used_fallback,
                    },
                )
                break

            if last_error is not None:
                # Every configured provider failed.
                logger.error(
                    "triage.all_providers_failed",
                    extra={**log_context, "attempts": len(attempts), "status_code": last_error.status_code},
                )
                if selected_model:
                    return self._get_model_error_response(symptoms_text, last_error, selected_model, **log_context)
                return self._get_degraded_fallback_response(
                    symptoms_text,
                    last_error.user_message,
                    primary_model,
                    primary_provider_name,
                    last_error.status_code,
                    **log_context,
                )

            # Extract JSON from response. A provider that returned no text at
            # all is treated the same as unreadable output (degraded), not as
            # a crash.
            assessment = self._extract_json(result_text or "", request_id=request_id, user_id=user_id)
            if not assessment:
                return self._get_degraded_fallback_response(
                    symptoms_text,
                    "We couldn't complete a full AI analysis because the model returned an unreadable response. Here's general guidance while you try again.",
                    model_to_call,
                    provider_name,
                    **log_context,
                )

            # Validate and structure response
            structured_assessment = self._structure_assessment(
                assessment, symptoms_text, had_clarifying_round=had_clarifying_round
            )
            structured_assessment['model_id'] = model_to_call
            structured_assessment['model_provider'] = provider_name
            structured_assessment['used_fallback_provider'] = used_fallback

            return structured_assessment
            
        except Exception as e:
            logger.exception("triage.assessment_failed", extra={**log_context, "model_id": model_id or self.default_model, "error_type": type(e).__name__})
            return self._get_degraded_fallback_response(
                symptoms_text,
                "We couldn't complete a full AI analysis because the model request failed. Here's general guidance while you try again.",
                model_id or self.default_model,
                'openrouter' if self._resolve_model_id(model_id) else 'gemini',
                **log_context,
            )

    def _resolve_model_id(self, model_id: str | None = None) -> str | None:
        """Return an allow-listed OpenRouter model id, or None for the default Gemini path."""
        model_id = (model_id or "").strip()
        return model_id if is_allowed_openrouter_model(model_id) else None

    def _build_provider_attempts(self, selected_model: str | None) -> List[tuple]:
        """Ordered [(provider, model_id, provider_name)] to try for one assessment.

        The first entry is the provider the caller actually selected. A second
        entry, when present, is the cross-provider failover target so a single
        provider outage doesn't degrade every assessment (see Fix 8). Failover
        is only offered when the other provider is actually configured.
        """
        attempts: List[tuple] = []

        if selected_model:
            attempts.append((self.openrouter_provider, selected_model, "openrouter"))
            if getattr(self.default_provider, "is_available", False):
                attempts.append((self.default_provider, self.default_model, "gemini"))
            return attempts

        attempts.append((self.default_provider, self.default_model, "gemini"))
        # Resolved live from OpenRouter's free-model catalog (hourly cache),
        # falling back to the configured default only if that lookup fails.
        fallback_model = resolve_fallback_openrouter_model()
        if fallback_model and getattr(self.openrouter_provider, "is_available", False):
            attempts.append((self.openrouter_provider, fallback_model, "openrouter"))
        return attempts
    
    def _complete_with_failover(self, messages: List[Dict], selected_model: str | None, log_context: Dict) -> str:
        """Run one completion across the provider attempt chain.

        Raises the last ModelProviderError if every configured provider fails.
        """
        attempts = self._build_provider_attempts(selected_model)
        last_error = None

        for index, (provider, candidate_model, candidate_provider_name) in enumerate(attempts):
            try:
                with provider_request_context(**log_context):
                    return provider.complete(messages, candidate_model, self.temperature)
            except ModelProviderError as error:
                last_error = error
                logger.warning(
                    "triage.provider_failed",
                    extra={
                        **log_context,
                        "model_id": candidate_model,
                        "provider": candidate_provider_name,
                        "status_code": error.status_code,
                        "error_type": type(error).__name__,
                        "will_failover": index < len(attempts) - 1,
                    },
                )

        raise last_error or ModelProviderError("No provider configured")

    def _extract_json_list(self, text: str) -> List:
        """Extract a JSON array from a model response, or [] if unparseable."""
        if not text:
            return []
        candidates = []

        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            candidates.append(text[start:end])
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            candidates.append(text[start:end])

        start, end = text.find("["), text.rfind("]") + 1
        if start != -1 and end > start:
            candidates.append(text[start:end])
        candidates.append(text)

        for candidate in candidates:
            try:
                parsed = json.loads(candidate.strip())
            except Exception:
                continue
            if isinstance(parsed, list):
                return parsed
            # Some models wrap the array, e.g. {"questions": [...]}.
            if isinstance(parsed, dict):
                for value in parsed.values():
                    if isinstance(value, list):
                        return value
        return []

    def generate_clarifying_questions(
        self,
        symptoms_text: str,
        user_data: Dict | None = None,
        *,
        model_id: str | None = None,
        max_questions: int = 3,
        request_id: str | None = None,
        user_id: int | None = None,
    ) -> List[Dict]:
        """Generate targeted follow-up questions for a vague symptom report.

        Returns a list of {"question": str, "type": "text"|"yes_no"|"scale"}.
        Falls back to a curated clinical default set if the model is
        unavailable or returns something unusable - the consultation must
        never dead-end because question generation failed.
        """
        symptoms_text = (symptoms_text or "").strip()
        user_data = user_data or {}
        log_context = {"request_id": request_id, "user_id": user_id}

        if not symptoms_text:
            return self._default_clarifying_questions(max_questions)

        # Emergencies are not a time to ask questions - the caller should be
        # routing to emergency care, not collecting more history.
        if contains_emergency_keyword(symptoms_text):
            logger.warning("triage.clarifying_questions_skipped_emergency", extra=log_context)
            return []

        prompt = self._build_clarifying_questions_prompt(symptoms_text, user_data, max_questions)
        selected_model = self._resolve_model_id(model_id)

        try:
            result_text = self._complete_with_failover(
                [{"role": "user", "content": prompt}], selected_model, log_context
            )
        except ModelProviderError as error:
            logger.warning(
                "triage.clarifying_questions_provider_failed",
                extra={**log_context, "status_code": error.status_code},
            )
            return self._default_clarifying_questions(max_questions)
        except Exception as error:
            logger.exception(
                "triage.clarifying_questions_failed",
                extra={**log_context, "error_type": type(error).__name__},
            )
            return self._default_clarifying_questions(max_questions)

        questions = self._validate_clarifying_questions(self._extract_json_list(result_text), max_questions)
        if not questions:
            logger.warning("triage.clarifying_questions_unusable_response", extra=log_context)
            return self._default_clarifying_questions(max_questions)

        return questions

    def _build_clarifying_questions_prompt(self, symptoms: str, user_data: Dict, max_questions: int) -> str:
        age = user_data.get('age', 'Unknown')
        gender = user_data.get('gender', 'Unknown')

        raw_history = user_data.get('past_history', [])
        if isinstance(raw_history, dict):
            raw_history = raw_history.get('conditions', [])
        if raw_history:
            history_str = ', '.join(
                c.get('name', str(c)) if isinstance(c, dict) else str(c)
                for c in raw_history
            )
        else:
            history_str = 'None'

        return f"""You are a triage nurse taking a history. Respond with ONLY a valid JSON array.

**Patient:** Age {age}, {gender}
**Known history:** {history_str}
**Reported symptoms:** {symptoms}

Ask up to {max_questions} follow-up questions that would most reduce diagnostic
uncertainty for THIS specific presentation. Prioritise, in order:
1. Onset and duration, if not already stated
2. Severity or progression (getting better/worse)
3. Red-flag associated symptoms that would change urgency for this complaint
4. Aggravating or relieving factors

Rules:
- Ask ONLY about information not already provided in the reported symptoms.
- Each question must be specific to this presentation, not generic boilerplate.
- Use "yes_no" for red-flag screening, "scale" for severity, "text" otherwise.
- Plain language a patient can answer without medical training.
- Do NOT diagnose, reassure, or give advice - questions only.

Return ONLY a JSON array of this exact shape:
[{{"question": "...", "type": "text|yes_no|scale"}}]"""

    def _validate_clarifying_questions(self, raw_questions: List, max_questions: int) -> List[Dict]:
        """Keep only well-formed, non-duplicate questions."""
        allowed_types = {'text', 'yes_no', 'scale'}
        validated: List[Dict] = []
        seen = set()

        for item in raw_questions:
            if isinstance(item, dict):
                question = item.get('question') or item.get('text') or ''
                question_type = item.get('type') or 'text'
            elif isinstance(item, str):
                question, question_type = item, 'text'
            else:
                continue

            question = str(question).strip()
            if not question:
                continue

            key = question.lower()
            if key in seen:
                continue
            seen.add(key)

            question_type = str(question_type).strip().lower().replace('-', '_').replace(' ', '_')
            if question_type in {'yesno', 'boolean', 'bool'}:
                question_type = 'yes_no'
            if question_type not in allowed_types:
                question_type = 'text'

            validated.append({'question': question, 'type': question_type})
            if len(validated) >= max_questions:
                break

        return validated

    def _default_clarifying_questions(self, max_questions: int = 3) -> List[Dict]:
        """Curated fallback set covering the highest-yield triage history gaps."""
        return [
            {'question': 'How long have you had these symptoms?', 'type': 'text'},
            {'question': 'How severe are your symptoms right now?', 'type': 'scale'},
            {'question': 'Are your symptoms getting worse?', 'type': 'yes_no'},
        ][:max_questions]

    def _build_assessment_prompt(self, symptoms: str, user_data: Dict, report: str, location: str) -> str:
        """Build comprehensive assessment prompt"""

        raw_history = user_data.get('past_history', [])
        if raw_history:
            history_str = ', '.join(
                c.get('name', str(c)) if isinstance(c, dict) else str(c)
                for c in raw_history
            )
        else:
            history_str = 'None'
        other_notes = (user_data.get('other_notes') or '').strip()
        other_notes_line = f"\n**Additional info from patient:** {other_notes}" if other_notes else ''

        # Prior assessments for this same patient, so the model can spot
        # recurrence and escalation instead of assessing every episode cold.
        prior_text = (user_data.get('prior_assessments_text') or '').strip()
        prior_block = (
            f"\n\n**Previous assessments for this patient (most recent first):**\n{prior_text}\n"
            "Consider whether the current symptoms are a recurrence, a continuation, or an "
            "escalation of the above. Repeated or worsening presentations of the same complaint "
            "warrant a higher level of concern than a first presentation."
            if prior_text else ''
        )

        # Uploaded medical report findings and location were previously
        # accepted by this method and then dropped on the floor.
        report_text = (report or '').strip()
        report_block = f"\n\n**Findings from the patient's uploaded medical report:**\n{report_text}" if report_text else ''

        location_text = (location or '').strip()
        location_block = f"\n**Patient location:** {location_text}" if location_text else ''

        prompt = f"""
Analyze this medical case and respond with ONLY valid JSON:

**Patient:** Age {user_data.get('age', 'Unknown')}, {user_data.get('gender', 'Unknown')}
**History:** {history_str}{other_notes_line}{location_block}
**Symptoms:** {symptoms}{report_block}{prior_block}

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

Confidence rules (important):
- "confidence" must reflect how much the SYMPTOM DESCRIPTION actually supports a
  conclusion, not how familiar the condition is to you.
- Lower it substantially when the description is brief or vague, or when duration,
  severity, or location are missing. A one-line report like "I feel bad" cannot
  support a confidence above 0.3 no matter how plausible your differential is.
- Only use confidence above 0.7 when duration, severity, AND specific location or
  associated symptoms are all present.
- State explicitly in "reasoning" what key information is missing and how that
  limits the assessment. Do not present an under-specified case as a confident one.

Return ONLY the JSON object."""

        return prompt

    
    def _extract_json(self, text: str, *, request_id: str | None = None, user_id: int | None = None) -> Dict:
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
            logger.warning("triage.response_json_parse_failed", extra={"request_id": request_id, "user_id": user_id, "error_type": type(e).__name__})
            # Try parsing the whole text
            try:
                return json.loads(text)
            except:
                return {}
    
    def _structure_assessment(self, assessment: Dict, symptoms: str, *, had_clarifying_round: bool = False) -> Dict:
        """Structure and validate assessment"""
        
        # Ensure all required fields exist with LOWER default risk values (FIX 3)
        structured = {
            'is_degraded': False,
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
                    logger.info("triage.generic_condition_filtered", extra={**provider_log_context(), "condition": disease_name})
                    continue  # Skip generic conditions
                
                structured['possible_conditions'].append({
                    'disease': disease_name,
                    'confidence': safe_float(condition.get('confidence'), 0.5),
                    'supporting_evidence': condition.get('supporting_evidence', [])
                })
            elif isinstance(condition, str):
                # Check if it's a generic name
                if any(generic in condition.lower() for generic in generic_names):
                    logger.info("triage.generic_condition_filtered", extra={**provider_log_context(), "condition": condition})
                    continue  # Skip generic conditions
                
                # Simple string condition
                structured['possible_conditions'].append({
                    'disease': condition,
                    'confidence': 0.5,
                    'supporting_evidence': []
                })
        
        # If no valid conditions after filtering, provide symptom-based suggestions
        if not structured['possible_conditions']:
            logger.warning("triage.conditions_degraded_to_keyword_guidance", extra=provider_log_context())
            structured['possible_conditions'] = self._generate_symptom_based_conditions(symptoms)

        # ONTOLOGY CHECK: annotate any condition name we cannot recognise, so a
        # hallucinated name never reaches a patient looking like a diagnosis.
        validation = validate_conditions(structured['possible_conditions'])
        structured['possible_conditions'] = validation['conditions']
        structured['unrecognized_condition_count'] = validation['unrecognized_count']
        structured['has_unrecognized_conditions'] = validation['any_unrecognized']
        structured['non_curated_condition_count'] = validation['non_curated_count']
        structured['icd10_matched_condition_count'] = validation['icd10_matched_count']

        # CONFIDENCE CALIBRATION: cap the model's self-reported confidence at
        # what the patient's input can actually support, and surface why.
        calibration = calibrate_confidence(
            structured['confidence'], symptoms, had_clarifying_round=had_clarifying_round
        )
        structured.update(calibration)

        # SAFETY NET: never let the model's own risk tier undercut a
        # rule-based emergency keyword check on the original symptoms text,
        # regardless of which provider answered. Also flag low-confidence
        # assessments for clinician follow-up.
        structured['requires_human_review'] = False
        review_reasons = []

        risk_order = {'low': 0, 'medium': 1, 'high': 2, 'emergency': 3}
        if contains_emergency_keyword(symptoms) and risk_order.get(structured['risk_level'], 0) < risk_order['high']:
            logger.warning(
                "triage.risk_level_floored_to_high",
                extra={**provider_log_context(), "llm_risk_level": structured['risk_level']},
            )
            structured['risk_level'] = 'high'
            structured['requires_human_review'] = True
            review_reasons.append('emergency_keyword_present')
            structured['disclaimer'] = self._get_default_disclaimer('high')

        if structured['confidence'] < 0.3:
            structured['requires_human_review'] = True
            review_reasons.append('low_confidence')

        if validation['all_unrecognized']:
            # Every name the model returned is unrecognisable - the output as a
            # whole cannot be trusted, so route it to a human.
            logger.warning(
                "triage.all_conditions_unrecognized",
                extra={**provider_log_context(), "condition_count": len(validation['conditions'])},
            )
            structured['requires_human_review'] = True
            review_reasons.append('unrecognized_conditions')
        elif validation['none_authoritative']:
            # Nothing resolved against the curated list OR ICD-10-CM's ~46k
            # codes. Names that merely *look* medical are not enough to let a
            # whole differential through unreviewed.
            logger.warning(
                "triage.no_authoritative_condition_match",
                extra={**provider_log_context(), "condition_count": len(validation['conditions'])},
            )
            structured['requires_human_review'] = True
            review_reasons.append('no_authoritative_condition_match')

        structured['authoritative_condition_count'] = validation['authoritative_count']
        structured['review_reasons'] = review_reasons
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
        """Fallback response when AI fails.

        Risk defaults to 'medium' (not 'low') because a failed/unreadable
        assessment is an unknown, not a reassurance - it must not look like
        a normal low-risk result to the patient or the clinician dashboard.
        requires_human_review flags it for clinician follow-up regardless of
        risk tier (see safety.clinician_alerts.create_alert_for_triage_record).
        """
        # STEP 4: Fix fallback reasoning (IMPORTANT)
        symptoms = symptoms or "the information provided"

        return {
            'risk_level': 'medium',
            'risk_probability': 0.5,
            'confidence': 0.4,
            # App-wide programmatic flag: a degraded response is NOT a real
            # assessment. Same field name/shape as the rate-limited 429 body,
            # so every client checks one flag. requires_human_review stays for
            # the clinician-alert path; is_degraded is what the patient UI keys
            # its banner on.
            'is_degraded': True,
            'requires_human_review': True,
            'reasoning': f'Based on your symptoms ({symptoms}), a full AI assessment could not be completed. Treat this as unconfirmed and consult a healthcare provider.',
            # No differential. A degraded response previously returned a
            # fabricated list (Self-limiting viral illness, etc.) that rendered
            # identically to a real result (Phase 1 finding). A patient who
            # could not be assessed must not be shown invented conditions.
            'possible_conditions': [],
            'reassurance': [],
            'ruled_out_conditions': [],
            'recommendations': [
                'This assessment is incomplete - do not treat it as reassurance',
                'Consult a healthcare provider, especially if symptoms are severe or worsening',
                'Try again or select another AI model for a full assessment'
            ],
            'follow_up_questions': [],
            'when_to_seek_care': 'Promptly - this assessment could not be fully completed, so err on the side of caution',
            'disclaimer': self._get_default_disclaimer('medium'),
            # Keep the calibration/ontology contract stable across every path
            # so clients never have to special-case a missing field.
            'reported_confidence': 0.4,
            'confidence_ceiling': 0.0,
            'confidence_was_capped': False,
            'input_specificity': 'not_assessed',
            'input_specificity_score': 0,
            'input_word_count': 0,
            'short_input_cap_applied': False,
            'had_clarifying_round': False,
            'missing_detail': [],
            'confidence_explanation': (
                'No AI assessment was completed, so this confidence reflects generic '
                'fallback guidance rather than an analysis of your symptoms.'
            ),
            'unrecognized_condition_count': 0,
            'has_unrecognized_conditions': False,
            'review_reasons': ['degraded_assessment'],
        }

    def _get_degraded_fallback_response(
        self,
        symptoms: str,
        user_message: str,
        model_id: str | None = None,
        model_provider: str | None = None,
        status_code: int | None = None,
        request_id: str | None = None,
        user_id: int | None = None,
    ) -> Dict:
        logger.warning(
            "triage.degraded_fallback",
            extra={
                "request_id": request_id,
                "user_id": user_id,
                "model_id": model_id,
                "provider": model_provider,
                "status_code": status_code,
                "fallback_cause": user_message,
            },
        )
        response = self._get_fallback_response(symptoms)
        response.update({
            'degraded': True,
            'assessment_source': 'llm_fallback',
            'model_id': model_id,
            'model_provider': model_provider,
            'model_error': user_message,
            'model_error_status': status_code,
        })
        response['reasoning'] = (
            f"{user_message} This is general safety guidance, not a complete AI assessment for your specific case."
        )
        response['recommendations'] = [
            'Try again or select another AI model',
            'Use this only as general safety guidance',
            'Consult a healthcare provider if symptoms persist, worsen, or feel urgent'
        ]
        response['disclaimer'] = (
            "DEGRADED RESPONSE: A full AI analysis could not be completed. "
            "This general guidance is not a diagnosis and should not replace professional medical advice."
        )
        return response

    def _get_model_error_response(
        self,
        symptoms: str,
        error: ModelProviderError,
        model_id: str,
        *,
        request_id: str | None = None,
        user_id: int | None = None,
    ) -> Dict:
        return self._get_degraded_fallback_response(
            symptoms,
            error.user_message,
            model_id,
            'openrouter',
            error.status_code,
            request_id=request_id,
            user_id=user_id,
        )


# Singleton instance
_triage_engine_v2 = None

def get_triage_engine_v2():
    """Get singleton instance of V2 triage engine"""
    global _triage_engine_v2
    if _triage_engine_v2 is None:
        _triage_engine_v2 = TriageEngineV2()
    return _triage_engine_v2
