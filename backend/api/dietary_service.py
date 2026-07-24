"""Context-aware, safety-bounded dietary guidance generation."""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import Any

from django.conf import settings
from django.core.cache import cache

from .llm_providers import ModelProviderError, OpenRouterProvider
from .llm_providers.catalog import get_free_openrouter_models
from .models import ChatMessage, DietaryAdvice, MedicalReport, TriageRecord


logger = logging.getLogger(__name__)


CONTEXT_CHAR_LIMIT = 9000
RELEVANT_CHAT_TERMS = (
    'diet', 'food', 'meal', 'eat', 'allerg', 'vegetarian', 'vegan', 'salt',
    'sugar', 'glucose', 'potassium', 'kidney', 'weight', 'nutrition',
)
SENSITIVE_TERMS = {
    'kidney': 'kidney-related history or results',
    'renal': 'renal-related history or results',
    'diabetes': 'diabetes or glucose-related history',
    'glucose': 'glucose-related history or results',
    'allerg': 'allergy-related history',
    'celiac': 'celiac-related history',
    'eating disorder': 'eating-related clinical history',
    'pregnan': 'pregnancy-related context',
}
FOOD_IMAGE_URLS = {
    'iron': 'https://images.unsplash.com/photo-1547592180-85f173990554?auto=format&fit=crop&w=900&q=85',
    'blood_sugar': 'https://images.unsplash.com/photo-1490474418585-ba9bad8fd0ea?auto=format&fit=crop&w=900&q=85',
    'heart': 'https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=900&q=85',
    'digestive': 'https://images.unsplash.com/photo-1547592180-85f173990554?auto=format&fit=crop&w=900&q=85',
    'general': 'https://images.unsplash.com/photo-1498837167922-ddd27525d352?auto=format&fit=crop&w=900&q=85',
}


class DietaryGenerationError(Exception):
    """A user-safe failure while generating dietary advice."""

    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _compact(value: Any, limit: int = 500) -> str:
    text = ' '.join(str(value or '').split())
    return text if len(text) <= limit else f'{text[:limit - 1]}…'


def _age_from_date(value: date | None) -> int | None:
    if not value:
        return None
    today = date.today()
    return today.year - value.year - ((today.month, today.day) < (value.month, value.day))


def _history_conditions(profile: Any) -> list[dict]:
    history = getattr(profile, 'past_history', {}) or {}
    conditions = history.get('conditions', []) if isinstance(history, dict) else history
    if not isinstance(conditions, list):
        return []
    return [
        {'name': _compact(item.get('name', ''), 120), 'notes': _compact(item.get('notes', ''), 180)}
        if isinstance(item, dict) else {'name': _compact(item, 120), 'notes': ''}
        for item in conditions[:20]
    ]


def _diet_relevant_texts(values: list[str]) -> list[str]:
    return [value for value in values if any(term in value.lower() for term in RELEVANT_CHAT_TERMS)]


def _report_summary(report: MedicalReport) -> dict:
    tests = []
    for test in list(report.tests.all()[:40]):
        name = _compact(getattr(test, 'test_name', ''), 100)
        if not name:
            continue
        name_lower = name.lower()
        if any(term in name_lower for term in ('glucose', 'a1c', 'hba1c', 'cholesterol', 'ldl', 'hdl', 'triglycer', 'hemoglobin', 'haemoglobin', 'iron', 'ferritin', 'potassium', 'creatinine', 'uric', 'albumin', 'sodium')) or getattr(test, 'is_abnormal', False):
            tests.append({
                'name': name,
                'value': getattr(test, 'test_value', None),
                'unit': _compact(getattr(test, 'test_unit', ''), 30),
                'reference_range': _compact(getattr(test, 'reference_range', ''), 60),
                'is_abnormal': bool(getattr(test, 'is_abnormal', False)),
            })
    structured = getattr(report, 'structured_data', {}) or {}
    structured_text = json.dumps(structured, ensure_ascii=False) if structured else ''
    relevant_structured = _diet_relevant_texts([structured_text])
    return {
        'file_name': _compact(getattr(report, 'file_name', ''), 100),
        'uploaded': getattr(report, 'upload_date', None).date().isoformat() if getattr(report, 'upload_date', None) else None,
        'diet_relevant_tests': tests[:15],
        'relevant_extracted_text': _compact(relevant_structured[0], 700) if relevant_structured else '',
    }


def build_dietary_context(user: Any, current_request: dict | None = None) -> dict:
    """Fetch and compact the user's saved context for one dietary generation call."""
    current_request = current_request or {}
    try:
        profile = user.profile
    except Exception:
        profile = None

    profile_data = {
        'age': _age_from_date(getattr(profile, 'date_of_birth', None)) if profile else None,
        'gender': getattr(profile, 'gender', None) if profile else None,
        'dietary_or_medical_history': _history_conditions(profile) if profile else [],
        'saved_preferences': current_request.get('stated_preferences') or (getattr(profile, 'past_history', {}) or {}).get('dietary_preferences', []) if profile else [],
        'other_notes': (getattr(profile, 'other_notes', None) or '').strip() or None if profile else None,
    }

    assessments = []
    for record in TriageRecord.objects.filter(user=user).prefetch_related('possible_conditions', 'recommendations')[:8]:
        conditions = [_compact(getattr(condition, 'disease_name', ''), 100) for condition in record.possible_conditions.all()[:8]]
        recommendations = [_compact(getattr(item, 'description', ''), 180) for item in record.recommendations.all()[:5] if getattr(item, 'recommendation_type', '') in ('dietary', 'lifestyle', 'action')]
        assessments.append({
            'date': record.created_at.date().isoformat() if record.created_at else None,
            'risk_level': record.risk_level,
            'symptoms': _compact(record.current_symptoms, 350),
            'flagged_conditions': [item for item in conditions if item],
            'relevant_recommendations': [item for item in recommendations if item],
        })

    reports = [_report_summary(report) for report in MedicalReport.objects.filter(user=user).prefetch_related('tests')[:5]]

    messages = list(ChatMessage.objects.filter(conversation__user=user).order_by('-created_at')[:40])
    relevant_turns = []
    for message in reversed(messages):
        content = _compact(getattr(message, 'content', ''), 450)
        if content and any(term in content.lower() for term in RELEVANT_CHAT_TERMS):
            relevant_turns.append({'role': getattr(message, 'role', 'user'), 'content': content})
    relevant_turns = relevant_turns[-12:]

    prior_advice = []
    for advice in DietaryAdvice.objects.filter(user=user)[:4]:
        data = getattr(advice, 'response_data', {}) or {}
        prior_advice.append({
            'date': advice.created_at.date().isoformat() if advice.created_at else None,
            'summary': _compact(data.get('summary', ''), 350),
            'recommendations': [_compact(card.get('name', ''), 100) for card in data.get('cards', [])[:6] if isinstance(card, dict)],
        })

    context = {
        'current_request': {
            'symptoms_or_goal': _compact(current_request.get('symptoms') or current_request.get('current_symptoms') or '', 500),
            'stated_preferences': _compact(current_request.get('stated_preferences') or '', 250),
            'assessment_hint': {
                'risk_level': current_request.get('risk_level'),
                'possible_conditions': current_request.get('possible_conditions', [])[:10],
            },
        },
        'profile': profile_data,
        'assessment_history': assessments,
        'report_history': reports,
        'relevant_conversation_turns': relevant_turns,
        'previous_dietary_advice': prior_advice,
    }
    encoded = json.dumps(context, ensure_ascii=False, separators=(',', ':'))
    if len(encoded) <= CONTEXT_CHAR_LIMIT:
        return context
    # Keep the most recent and highest-signal data when older history is large.
    context['relevant_conversation_turns'] = relevant_turns[-6:]
    context['report_history'] = reports[:3]
    context['assessment_history'] = assessments[:5]
    encoded = json.dumps(context, ensure_ascii=False, separators=(',', ':'))
    if len(encoded) > CONTEXT_CHAR_LIMIT:
        context['relevant_conversation_turns'] = []
        context['previous_dietary_advice'] = prior_advice[:2]
    return context


def _safety_flags(context: dict) -> list[str]:
    text = json.dumps(context, ensure_ascii=False).lower()
    return [label for term, label in SENSITIVE_TERMS.items() if term in text]


def _select_free_model() -> str:
    free_models = get_free_openrouter_models()
    if not free_models:
        logger.warning("dietary.free_model_catalog_empty")
        raise DietaryGenerationError('No free dietary model is currently available.')
    ids = {row.get('id') for row in free_models}
    configured = getattr(settings, 'DIETARY_DEFAULT_FREE_MODEL', '')
    if configured and configured in ids:
        return configured
    def score(row: dict) -> tuple:
        context_length = row.get('context_length') or 0
        instruction_signal = any(term in f"{row.get('name', '')} {row.get('description', '')}".lower() for term in ('instruct', 'reason', 'chat'))
        return (not instruction_signal, -context_length, row.get('id') or '')
    return sorted(free_models, key=score)[0]['id']


def _parse_json_response(raw: str) -> dict:
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError) as error:
        logger.warning("dietary.response_json_parse_failed", extra={"response_type": type(raw).__name__})
        raise DietaryGenerationError('The dietary model returned an unreadable response.') from error
    if not isinstance(parsed, dict) or not isinstance(parsed.get('cards'), list):
        logger.warning("dietary.response_schema_invalid")
        raise DietaryGenerationError('The dietary model returned an incomplete response.')
    return parsed


def _remove_restrictive_numbers(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _remove_restrictive_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_remove_restrictive_numbers(item) for item in value]
    if not isinstance(value, str):
        return value
    value = re.sub(r'\b\d[\d,]*(?:\.\d+)?\s*(?:k?cal(?:ories)?|calories)\b', 'an individualized amount', value, flags=re.I)
    value = re.sub(r'\b(?:lose|gain|target|limit|stay under|under)\s+\d[\d,]*(?:\.\d+)?\s*(?:kg|kilograms?|lb|lbs|pounds?)\b', 'follow an individualized health goal', value, flags=re.I)
    value = re.sub(r'\b\d[\d,]*(?:\.\d+)?\s*(?:calories|kcal|kilograms?|kg|pounds?|lbs)\b', 'an individualized amount', value, flags=re.I)
    return value


def _normalise_response(response: dict, safety_flags: list[str], model_id: str) -> dict:
    response = _remove_restrictive_numbers(response)
    cards = []
    for index, card in enumerate(response.get('cards', [])[:8]):
        if not isinstance(card, dict) or not card.get('name') or not card.get('rationale'):
            continue
        category_text = f"{card.get('category', '')} {card.get('name', '')} {card.get('rationale', '')}".lower()
        image_key = 'digestive' if any(term in category_text for term in ('digest', 'gentle', 'stomach')) else (
            'blood_sugar' if any(term in category_text for term in ('glucose', 'sugar', 'diabet')) else (
                'heart' if any(term in category_text for term in ('heart', 'blood pressure', 'sodium', 'lipid')) else (
                    'iron' if any(term in category_text for term in ('iron', 'hemoglobin', 'anaemia', 'anemia')) else 'general')))
        nutrient_highlights = card.get('nutrient_highlights', [])
        if not isinstance(nutrient_highlights, list):
            nutrient_highlights = []
        cards.append({
            'category': _compact(card.get('category', 'A nourishing option'), 60),
            'name': _compact(card['name'], 100),
            'rationale': _compact(card['rationale'], 360),
            'nutrient_highlights': [
                {'label': _compact(item.get('label', ''), 40), 'value': _compact(item.get('value', ''), 60)}
                for item in nutrient_highlights[:4] if isinstance(item, dict) and item.get('label') and item.get('value')
            ],
            'image_url': FOOD_IMAGE_URLS[image_key],
            'image_alt': f"{_compact(card['name'], 100)} food photograph",
        })
    if not cards:
        logger.warning("dietary.response_cards_unusable", extra={"model_id": model_id})
        raise DietaryGenerationError('The dietary model did not return usable recommendations.')

    # summary/daily_pattern/next_step are free-form output outside the
    # structured 'cards' schema - the system prompt names daily_pattern as a
    # key but (unlike cards) never pins its type, so a model occasionally
    # returns a single string instead of a list. The frontend calls
    # .map() on it directly, so an un-coerced string crashes the page.
    raw_daily_pattern = response.get('daily_pattern')
    if isinstance(raw_daily_pattern, list):
        daily_pattern = [_compact(item, 200) for item in raw_daily_pattern if str(item or '').strip()][:6]
    elif isinstance(raw_daily_pattern, str) and raw_daily_pattern.strip():
        daily_pattern = [_compact(raw_daily_pattern, 400)]
    else:
        daily_pattern = []

    response['summary'] = _compact(response.get('summary', ''), 500)
    response['daily_pattern'] = daily_pattern
    response['next_step'] = _compact(response.get('next_step', ''), 300)
    response['cards'] = cards
    response['model_id'] = model_id
    response['free_tier'] = True
    response['safety_flags'] = safety_flags
    response['safety_notice'] = (
        'Because your saved history includes ' + ', '.join(safety_flags) + ', confirm condition-specific restrictions with your doctor or a registered dietitian.'
        if safety_flags else
        'This is general nutrition guidance. Ask a doctor or registered dietitian before making condition-specific changes, especially for allergies or medical restrictions.'
    )
    return response


def generate_dietary_advice(user: Any, current_request: dict | None = None, *, provider: OpenRouterProvider | None = None) -> dict:
    user_id = getattr(user, 'id', None)
    context = build_dietary_context(user, current_request)
    safety_flags = _safety_flags(context)
    model_id = _select_free_model()
    provider = provider or OpenRouterProvider()
    system_prompt = """You are MedAid's dietary guidance assistant. Return JSON only with keys: summary, cards, daily_pattern, and next_step. cards is an array of 3-6 objects with category, name, rationale, and nutrient_highlights (an array of {label,value}). Use the supplied user context deeply: connect each rationale to a real profile, assessment, report, conversation, or prior-advice signal. If context is empty, say so implicitly and give broadly safe, practical options. Provide general nutrition guidance, never diagnosis or a prescriptive medical diet. Never provide calorie targets, weight-loss targets, numeric meal plans, or restrictive numbers. Do not recommend potassium-rich foods or other condition-specific restrictions without a clear clinician/dietitian caveat when the context suggests kidney, glucose, allergy, pregnancy, eating-related, or other sensitive history. Avoid medical certainty. Do not include image URLs; the application supplies approved imagery."""
    messages = [
        {'role': 'system', 'content': system_prompt + '\nDeterministic safety flags for this user: ' + (', '.join(safety_flags) if safety_flags else 'none detected') + '.'},
        {'role': 'user', 'content': 'User context (bounded and retrieved from MedAid records):\n' + json.dumps(context, ensure_ascii=False)},
    ]
    try:
        raw = provider.complete(messages, model_id, getattr(settings, 'DIETARY_MODEL_TEMPERATURE', 0.25))
    except ModelProviderError as error:
        logger.warning("dietary.provider_failed", extra={"user_id": user_id, "model_id": model_id, "status_code": error.status_code, "error_type": type(error).__name__})
        retryable = error.status_code in {400, 404, 408, 429} or (error.status_code is not None and error.status_code >= 500)
        if not retryable or model_id == 'openrouter/free':
            raise DietaryGenerationError('Dietary advice is temporarily unavailable. Please try again shortly.', status_code=error.status_code) from error
        try:
            raw = provider.complete(messages, 'openrouter/free', getattr(settings, 'DIETARY_MODEL_TEMPERATURE', 0.25))
            model_id = 'openrouter/free'
        except ModelProviderError as fallback_error:
            logger.warning("dietary.free_model_fallback_failed", extra={"user_id": user_id, "model_id": 'openrouter/free', "status_code": fallback_error.status_code, "error_type": type(fallback_error).__name__})
            raise DietaryGenerationError('Dietary advice is temporarily unavailable. Please try again shortly.', status_code=fallback_error.status_code) from fallback_error
    response = _normalise_response(_parse_json_response(raw), safety_flags, model_id)
    saved = DietaryAdvice.objects.create(
        user=user,
        request_text=_compact((current_request or {}).get('symptoms') or (current_request or {}).get('current_symptoms') or '', 1000),
        response_data=response,
        context_snapshot=context,
        model_id=model_id,
    )
    response['id'] = saved.id
    response['context_used'] = {
        'profile': bool(context['profile'].get('dietary_or_medical_history') or context['profile'].get('age')),
        'assessment_history': len(context['assessment_history']),
        'report_history': len(context['report_history']),
        'conversation_turns': len(context['relevant_conversation_turns']),
        'previous_dietary_advice': len(context['previous_dietary_advice']),
    }
    logger.info("dietary.generation_completed", extra={"user_id": user_id, "model_id": model_id, "context_assessments": len(context['assessment_history']), "context_reports": len(context['report_history'])})
    return response
