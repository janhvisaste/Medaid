from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import authenticate
from django.db import IntegrityError
from django.db.models import QuerySet
from django.http import HttpResponse
from django.utils import timezone
from django.conf import settings
from typing import Any, cast
import json

from .patient_context import build_patient_history_context
from .llm_quota import (
    LLMQuotaExceeded,
    _cache_release,
    _cache_reserve,
    check_llm_quota,
    note_global_usage,
)
from .safety.clinician_alerts import create_alert_for_triage_record
from .safety.critical_findings import (
    content_key_for,
    escalate_critical_findings,
    is_critical_status,
    select_critical_findings,
)
from .safety.emergency_check import (
    contains_emergency_keyword,
    create_emergency_triage_record,
    get_emergency_services_by_pincode,
)


from .models import (
    User, UserProfile, MedicalReport, TriageRecord, 
    PossibleCondition, MedicalTest, AbnormalResult, Recommendation,
    ConsultationSession, PatientAssignment, ClinicianNote, ClinicianAlert
)
from .serializers import (
    UserSerializer,
    UserProfileSerializer,
    SignupSerializer,
    LoginSerializer,
    AuthResponseSerializer,
    LogoutSerializer,
    MedicalReportSerializer,
    ConsultationSessionSerializer,
    PatientAssignmentSerializer,
    ClinicianNoteSerializer,
    ClinicianAlertSerializer,
    ClinicianStatsSerializer,
    TriageRecordSerializer
)
from .triage_engine_v2 import get_triage_engine_v2
from .assessment_quality import should_request_clarification
from .hospital_finder import get_hospital_finder
from .report_processor import get_report_processor
from django.db import transaction
from .facility_recommendations import get_nearby_facilities
from .report_generator import generate_assessment_pdf, generate_health_passport_pdf
from .llm_providers.catalog import get_available_model_catalog, is_allowed_openrouter_model
from django.db import connections
from django.core.cache import cache
from .dietary_service import DietaryGenerationError, generate_dietary_advice
import logging
import uuid


logger = logging.getLogger(__name__)


def _paginate_queryset(request, queryset):
    """Apply DRF's configured PAGE_SIZE to a function-based view.

    Generic views and viewsets pick up REST_FRAMEWORK['PAGE_SIZE'] for free;
    plain @api_view functions do not, so they must opt in explicitly. Returns
    (paginator, page) - call ``paginator.get_paginated_response(data)`` to emit
    the standard {count, next, previous, results} envelope.
    """
    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(queryset, request)
    return paginator, page


def _persist_triage_assessment(*, user, symptoms_text, input_mode, assessment, medical_report_id=None):
    """Persist a completed TriageEngineV2 assessment as a TriageRecord + children.

    Shared by every entry point that runs a real structured assessment
    (direct triage, and now chat) so an assessment is recorded exactly once,
    the same way, regardless of which UI produced it. All child rows are
    created atomically so a partial failure can never leave a TriageRecord
    committed without its conditions/recommendations/alert.
    """
    with transaction.atomic():
        triage_record = TriageRecord.objects.create(
            user=user,
            current_symptoms=symptoms_text,
            input_mode=input_mode,
            risk_level=assessment['risk_level'],
            risk_probability=assessment.get('risk_probability', 0.0),
            reasoning=assessment['reasoning'],
            confidence=assessment.get('confidence', 0.0),
            assessment_source=assessment.get('assessment_source') or 'ai_v2',
            requires_human_review=bool(assessment.get('requires_human_review')),
            medical_report_id=medical_report_id,
            similar_cases={
                'model_id': assessment.get('model_id'),
                'model_provider': assessment.get('model_provider'),
                'degraded': bool(assessment.get('degraded')),
                'is_degraded': bool(assessment.get('is_degraded')),
                'model_error': assessment.get('model_error'),
            }
        )

        for condition in assessment.get('possible_conditions', []):
            if isinstance(condition, dict):
                PossibleCondition.objects.create(
                    triage_record=triage_record,
                    disease_name=condition.get('disease', 'Unknown'),
                    confidence=condition.get('confidence', 0.0)
                )
            else:
                PossibleCondition.objects.create(
                    triage_record=triage_record,
                    disease_name=str(condition),
                    confidence=assessment.get('confidence', 0.0)
                )

        for idx, rec in enumerate(assessment.get('recommendations', [])):
            Recommendation.objects.create(
                triage_record=triage_record,
                recommendation_type='action',
                description=rec,
                priority=idx + 1
            )

        # Notify a clinician for high/emergency AI assessments too, not
        # just the rule-based emergency short-circuit.
        create_alert_for_triage_record(triage_record)

    return triage_record


def _rate_limited_response(limit, feature):
    """Build a 429 for a non-triage LLM feature hitting a quota ceiling.

    Deliberately distinct from every success (2xx) and from the degraded-AI
    case (201/503): the 429 status plus the explicit `rate_limited` flag tell
    the client this was a usage limit, not a real result.
    """
    scope_label = 'your account' if limit.scope == 'user' else 'the shared free-tier'
    detail = (
        f"You've reached {scope_label} {feature} usage limit. "
        f"Please wait about {limit.retry_after} seconds and try again."
    )
    return Response(
        {
            'rate_limited': True,
            'quota_scope': limit.scope,
            'retry_after': limit.retry_after,
            'detail': detail,
        },
        status=status.HTTP_429_TOO_MANY_REQUESTS,
        headers={'Retry-After': str(limit.retry_after)},
    )


def _rate_limited_triage_response(limit):
    """Build a 429 for triage hitting a quota ceiling.

    Emergency screening has already run and returned before this point, so a
    genuine emergency is never rate-limited. For a non-emergency, this carries
    the SAFE degraded semantics (requires_human_review, safe guidance, no
    fabricated differential) so a patient still gets a safe next step - but the
    429 status and the explicit rate_limited flag make it unmistakably a usage
    limit, NOT an AI assessment. No possible_conditions are returned: a
    rate-limited user must never see a fabricated differential that reads like
    a real result.
    """
    scope_label = 'your account' if limit.scope == 'user' else 'the shared free-tier'
    detail = (
        f"You've reached {scope_label} AI triage usage limit. Please wait about "
        f"{limit.retry_after} seconds and try again. This is a usage limit, not a "
        "medical assessment - no AI analysis was performed on your symptoms."
    )
    body = {
        'rate_limited': True,
        'quota_scope': limit.scope,
        'retry_after': limit.retry_after,
        'detail': detail,
        # Safe degraded semantics preserved, but clearly not an assessment.
        # is_degraded is included ahead of the general degraded-flag work so
        # this path already carries the programmatic flag a client checks.
        'is_degraded': True,
        'degraded': True,
        'requires_human_review': True,
        'assessment_source': 'rate_limited',
        'risk_level': 'medium',
        'possible_conditions': [],
        'reasoning': detail,
        'recommendations': [
            'This request was rate-limited; no AI assessment was produced.',
            'Wait a moment and try again.',
            'If your symptoms are severe or worsening, seek medical care now - '
            'do not wait for the limit to reset.',
        ],
        'when_to_seek_care': (
            'If symptoms are severe or worsening, seek care immediately regardless of this limit.'
        ),
        'disclaimer': (
            'RATE-LIMITED: usage limit reached. This is not a diagnosis or an AI assessment.'
        ),
    }
    return Response(
        body,
        status=status.HTTP_429_TOO_MANY_REQUESTS,
        headers={'Retry-After': str(limit.retry_after)},
    )


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    API health check endpoint - returns API status and available endpoints
    """
    # Basic DB connectivity check
    db_ok = False
    try:
        with connections['default'].cursor() as cursor:
            cursor.execute('SELECT 1')
            db_ok = True
    except Exception:
        db_ok = False

    return Response({
        'status': 'ok' if db_ok else 'degraded',
        'message': 'MedAid API is running',
        'db': 'ok' if db_ok else 'unavailable',
        'version': '1.0.0',
        'endpoints': {
            'authentication': {
                'signup': '/api/auth/signup/',
                'login': '/api/auth/login/',
                'logout': '/api/auth/logout/',
                'refresh_token': '/api/auth/token/refresh/',
                'current_user': '/api/auth/me/'
            },
            'profile': {
                'get_profile': '/api/profile/',
                'update_profile': '/api/profile/update/'
            },
            'medical_reports': {
                'list_create': '/api/medical-reports/',
                'detail': '/api/medical-reports/{id}/'
            },
            'admin': '/admin/'
        }
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def signup(request):
    """
    User signup endpoint
    """
    serializer = SignupSerializer(data=request.data)
    if serializer.is_valid():
        try:
            user = cast(User, serializer.save())
            # Generate tokens
            refresh = RefreshToken.for_user(user)
            
            response_data = {
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': UserSerializer(user).data
            }
            return Response(response_data, status=status.HTTP_201_CREATED)
        except IntegrityError:
            return Response(
                {'email': 'Email already exists.'},
                status=status.HTTP_400_BAD_REQUEST
            )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """
    User login endpoint
    """
    serializer = LoginSerializer(data=request.data)
    # raise_exception=True propagates the serializer's errors directly:
    # malformed input -> 400, credential mismatch -> 401 (AuthenticationFailed).
    serializer.is_valid(raise_exception=True)
    validated_data = cast(dict[str, Any], serializer.validated_data)
    user = cast(User, validated_data['user'])
    # Older/admin-created accounts may predate automatic profile creation.
    # Ensure the protected profile-dependent workflows can start safely.
    UserProfile.objects.get_or_create(user=user)
    refresh = RefreshToken.for_user(user)

    response_data = {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': UserSerializer(user).data
    }
    return Response(response_data, status=status.HTTP_200_OK)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """
    User logout endpoint
    """
    try:
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {'detail': 'Refresh token is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        token = RefreshToken(refresh_token)
        token.blacklist()
        
        return Response(
            {'detail': 'Successfully logged out.'},
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response(
            {'detail': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_profile(request):
    """
    Get current user's profile
    """
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)
    
    serializer = UserProfileSerializer(profile)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_user_profile(request):
    """
    Update current user's profile
    """
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)
    
    serializer = UserProfileSerializer(profile, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_medical_history(request):
    """
    Update user's past medical history with structured conditions and optional
    free-text notes.

    Body: {
        "conditions": [
            {"name": "Diabetes", "selected": true, "notes": "Type 2"},
            {"name": "Hypertension", "selected": true},
            {"name": "Heart Disease", "selected": false}
        ],
        "other_notes": "Penicillin allergy. Father had a heart attack at 55."  // optional
    }
    """
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)

    conditions = request.data.get('conditions', [])
    other_notes_raw = request.data.get('other_notes', None)

    # Validate other_notes length — reject, never silently truncate
    OTHER_NOTES_MAX = 2000
    if other_notes_raw is not None:
        if not isinstance(other_notes_raw, str):
            return Response(
                {'error': 'other_notes must be a string.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(other_notes_raw) > OTHER_NOTES_MAX:
            return Response(
                {'error': f'Notes must be {OTHER_NOTES_MAX} characters or fewer (received {len(other_notes_raw)}).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

    # Normalise: strip whitespace; store None when blank
    other_notes = other_notes_raw.strip() if other_notes_raw and other_notes_raw.strip() else None

    # Build structured past_history (conditions only — other_notes lives at top-level)
    past_history = {
        'conditions': [],
        'updated_at': str(timezone.now())
    }

    for condition in conditions:
        if condition.get('selected', False):
            past_history['conditions'].append({
                'name': condition.get('name'),
                'notes': condition.get('notes', '')
            })

    update_fields = ['past_history', 'updated_at']
    profile.past_history = past_history
    if other_notes_raw is not None:
        # Only overwrite other_notes if the caller explicitly sent the field
        profile.other_notes = other_notes
        update_fields.append('other_notes')
    profile.save(update_fields=update_fields)

    return Response({
        'message': 'Medical history updated successfully',
        'past_history': past_history,
        'other_notes': profile.other_notes,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_current_user(request):
    """
    Get current authenticated user
    """
    serializer = UserSerializer(request.user)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def available_models(request):
    """Return the curated OpenRouter model catalog without exposing API keys."""
    return Response({'models': get_available_model_catalog()}, status=status.HTTP_200_OK)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_user(request):
    """
    Update current user's basic information (name, phone)
    """
    user = request.user
    
    # Update allowed fields
    if 'first_name' in request.data:
        user.first_name = request.data['first_name']
    if 'last_name' in request.data:
        user.last_name = request.data['last_name']
    if 'phone_number' in request.data:
        user.phone_number = request.data['phone_number']
    
    user.save()
    serializer = UserSerializer(user)
    return Response(serializer.data, status=status.HTTP_200_OK)


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for User management
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):  # type: ignore[override]
        # Users can only see their own profile
        return User.objects.filter(pk=getattr(self.request.user, 'pk', None))

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)


class MedicalReportViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Medical Report management
    """
    serializer_class = MedicalReportSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):  # type: ignore[override]
        # Users can only see their own medical reports
        return MedicalReport.objects.filter(user=getattr(self.request.user, 'pk', None))

    MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10MB

    def perform_create(self, serializer):
        # Automatically set the user to the current authenticated user
        file = self.request.FILES.get('file')
        if file and file.size > self.MAX_UPLOAD_SIZE_BYTES:
            max_mb = self.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
            raise ValidationError({'file': f'File too large. Maximum upload size is {max_mb}MB.'})
        serializer.save(
            user=self.request.user,
            file_name=file.name if file else '',
            file_type=file.content_type if file else '',
            file_size=file.size if file else 0
        )

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download a specific medical report"""
        report = self.get_object()
        from django.http import FileResponse
        return FileResponse(report.file.open('rb'), as_attachment=True, filename=report.file_name)


# ============= TRIAGE & AI ASSESSMENT =============

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assess_symptoms(request):
    """
    AI-powered triage assessment
    
    Request body:
    {
        "current_symptoms": "I have fever and body pain",
        "input_mode": "text",  // text, voice, report
        "medical_report_id": null,  // optional
        "location": "Mumbai",  // optional
        "pincode": "400001"  // optional
    }
    """
    try:
        from datetime import datetime
        request_id = request.headers.get('X-Request-ID') or uuid.uuid4().hex
        user = request.user
        symptoms_text = request.data.get('current_symptoms', '')
        input_mode = request.data.get('input_mode', 'text')
        report_id = request.data.get('medical_report_id')
        location = request.data.get('location', '')
        pincode = request.data.get('pincode', '')
        model_id = request.data.get('model_id')
        # Optional clarifying-question round. When the patient has answered a
        # follow-up (clarifying_answers present) we fold those answers into the
        # symptom text and lift the short-input confidence cap. skip_clarification
        # lets a caller opt out of the two-step flow entirely.
        clarifying_answers = request.data.get('clarifying_answers') or []
        skip_clarification = bool(request.data.get('skip_clarification'))
        had_clarifying_round = bool(clarifying_answers)
        
        # Save pincode to user profile
        if pincode and hasattr(user, 'profile'):
            user.profile.pincode = pincode
            user.profile.save()
        
        if not symptoms_text:
            return Response(
                {'error': 'Symptoms description is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # IMMEDIATE EMERGENCY CHECK
        if contains_emergency_keyword(symptoms_text):
            triage_record, assessment = create_emergency_triage_record(
                user=user,
                symptoms_text=symptoms_text,
                input_mode=input_mode,
                pincode=pincode or None,
                medical_report_id=report_id if report_id else None,
            )

            response_data = {
                'triage_id': triage_record.pk,
                'risk_level': 'emergency',
                'reasoning': assessment['reasoning'],
                'confidence': assessment['confidence'],
                'possible_conditions': ['Emergency Medical Condition'],
                'recommendations': assessment['recommendations'],
                'immediate_actions': [
                    'Call 108 or 112 now',
                    'Alert family members',
                    'Prepare for hospital visit'
                ],
                'when_to_seek_care': assessment['when_to_seek_care'],
                'triage_level': 'emergency',
                'created_at': triage_record.created_at
            }

            # Add emergency services info if available
            if assessment.get('emergency_services'):
                response_data['emergency_services'] = assessment['emergency_services']

            return Response(response_data, status=status.HTTP_201_CREATED)
        
        # Continue with normal triage for non-emergency cases
        
        # Get user profile data
        profile = UserProfile.objects.filter(user=user).first()
        age = None
        gender = 'unknown'
        past_history = []
        other_notes = None

        if profile:
            age = profile.calculate_age()
            gender = profile.gender or 'unknown'
            past_history = profile.past_history.get('conditions', []) if profile.past_history else []
            other_notes = profile.other_notes or None
            if is_allowed_openrouter_model(model_id):
                profile.preferred_model = model_id
                profile.save(update_fields=['preferred_model', 'updated_at'])

        # Prepare user data for triage, including this patient's prior
        # assessments so recurrence/escalation is visible to the model.
        user_data = {
            'age': age or 'Adult',
            'gender': gender,
            'past_history': past_history,
            'other_notes': other_notes,
            **build_patient_history_context(user),
        }

        # Vagueness gate: if the report is too thin to assess confidently and
        # no clarifying round has happened yet, ask a follow-up first instead of
        # returning a low-confidence assessment. Reuses the shared trigger and
        # the V2 engine's question generator - no bespoke heuristic here. A
        # medical report supplies its own detail, so only gate plain-text input.
        if (
            not skip_clarification
            and not had_clarifying_round
            and not report_id
            and should_request_clarification(symptoms_text)
        ):
            questions = get_triage_engine_v2().generate_clarifying_questions(
                symptoms_text=symptoms_text,
                user_data=user_data,
                model_id=model_id,
                request_id=request_id,
                user_id=user.pk,
            )
            # No questions => emergency text or the generator was unavailable;
            # fall through and assess rather than dead-end the patient.
            if questions:
                return Response({
                    'needs_clarification': True,
                    'clarifying_questions': questions,
                    'current_symptoms': symptoms_text,
                    'message': (
                        'A few quick questions will make this assessment more '
                        'accurate. Answer them and resubmit with clarifying_answers.'
                    ),
                }, status=status.HTTP_200_OK)

        # Once the patient has answered, fold their responses into the symptom
        # text the model sees so the extra detail actually informs the result.
        if had_clarifying_round:
            answer_lines = []
            for item in clarifying_answers:
                if isinstance(item, dict):
                    question = str(item.get('question', '')).strip()
                    answer = str(item.get('answer', '')).strip()
                    if answer:
                        answer_lines.append(f"Q: {question}\nA: {answer}" if question else answer)
            if answer_lines:
                symptoms_text = symptoms_text + "\n\nFollow-up answers:\n" + "\n".join(answer_lines)

        # Get medical report summary if report_id provided
        report_summary = ""
        if report_id:
            try:
                report = MedicalReport.objects.filter(id=report_id, user=user).first()
                if report and report.structured_data:
                    # Check if LLM summary available (preferred)
                    if 'llm_summary' in report.structured_data:
                        report_summary = report.structured_data['llm_summary']
                        # Add key findings if available
                        if 'llm_key_findings' in report.structured_data:
                            findings = report.structured_data['llm_key_findings']
                            if findings:
                                report_summary += " Key findings: " + ", ".join(findings[:5])
                    else:
                        # Fallback to structured test data
                        tests = []
                        for key, value in report.structured_data.items():
                            if not key.startswith('llm_'):  # Skip LLM fields
                                tests.append(f"{key}: {value}")
                        report_summary = "; ".join(tests[:10])  # Limit to first 10 tests
            except Exception as e:
                logger.warning("triage.report_summary_failed", extra={"request_id": request_id, "user_id": user.pk, "error_type": type(e).__name__})
        
        # Build location string
        location_str = ""
        if location and pincode:
            location_str = f"{location}, Pincode: {pincode}"
        elif location:
            location_str = location
        elif pincode:
            location_str = f"Pincode: {pincode}"
        
        # Quota gate for the LLM call ONLY. The emergency short-circuit above
        # has already returned for emergencies, so screening is never gated.
        # On breach, return a distinct 429 carrying safe degraded guidance -
        # never an error that skips safety, and never a silent success.
        try:
            check_llm_quota('triage', user.pk)
        except LLMQuotaExceeded as limit:
            return _rate_limited_triage_response(limit)

        # Run V2 triage assessment with all context
        triage_engine_v2 = get_triage_engine_v2()
        assessment = triage_engine_v2.assess(
            symptoms_text,
            user_data,
            report_summary,
            location_str,
            model_id=model_id,
            request_id=request_id,
            user_id=user.pk,
            had_clarifying_round=had_clarifying_round,
            # The raw current_symptoms was already checked via
            # contains_emergency_keyword() above, before any clarifying-answer
            # merge. That merge appends "Q: <question>\nA: <answer>" - and a
            # clarifying question routinely names the symptom it's asking
            # about (e.g. "Are you experiencing chest pain?"), so re-scanning
            # the merged text here would trigger on the question's own
            # wording regardless of how the patient answered it.
            skip_emergency_recheck=True,
        )

        if assessment.get('model_error') and not assessment.get('degraded'):
            return Response(
                {
                    'error': assessment['model_error'],
                    'model_id': assessment.get('model_id'),
                    'assessment': assessment,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Find nearby hospitals if location provided
        nearby_hospitals = []
        if location or pincode:
            try:
                hospital_finder = get_hospital_finder()
                # Prefer a valid 6-digit pincode for more precise geocoding.
                cleaned_pincode = str(pincode or '').strip()
                search_location = cleaned_pincode if cleaned_pincode.isdigit() and len(cleaned_pincode) == 6 else (location or pincode)
                hospitals = hospital_finder.find_nearby_hospitals(
                    location=search_location,
                    risk_level=assessment['risk_level'],
                    radius=5000,
                    max_results=5
                )
                
                # Convert to dict format
                for hospital in hospitals:
                    nearby_hospitals.append({
                        'name': hospital.name,
                        'address': hospital.address,
                        'distance': hospital.distance,
                        'rating': hospital.rating,
                        'phone': hospital.phone,
                        'is_open': hospital.is_open,
                        'maps_url': hospital.get_google_maps_url()
                    })
            except Exception as e:
                logger.warning("triage.nearby_hospitals_failed", extra={"request_id": request_id, "user_id": user.pk, "error_type": type(e).__name__})
        
        triage_record = _persist_triage_assessment(
            user=user,
            symptoms_text=symptoms_text,
            input_mode=input_mode,
            assessment=assessment,
            medical_report_id=report_id if report_id else None,
        )

        # Build comprehensive response
        response_data = {
            'triage_id': triage_record.pk,
            'risk_level': assessment['risk_level'],
            'risk_probability': assessment.get('risk_probability', 0.0),
            'reasoning': assessment['reasoning'],
            'confidence': assessment.get('confidence', 0.0),
            'possible_conditions': assessment.get('possible_conditions', []),
            'ruled_out_conditions': assessment.get('ruled_out_conditions', []),
            'recommendations': assessment.get('recommendations', []),
            'follow_up_questions': assessment.get('follow_up_questions', []),
            'when_to_seek_care': assessment.get('when_to_seek_care', ''),
            'disclaimer': assessment.get('disclaimer', ''),
            'nearby_hospitals': nearby_hospitals,
            'model_id': assessment.get('model_id'),
            'model_provider': assessment.get('model_provider'),
            'degraded': bool(assessment.get('degraded')),
            'is_degraded': bool(assessment.get('is_degraded')),
            'assessment_source': assessment.get('assessment_source') or 'ai_v2',
            # Confidence calibration + condition-name checks, surfaced so the
            # UI can explain an uncertain result instead of showing a bare number.
            'reported_confidence': assessment.get('reported_confidence'),
            'confidence_was_capped': bool(assessment.get('confidence_was_capped')),
            'confidence_explanation': assessment.get('confidence_explanation', ''),
            'input_specificity': assessment.get('input_specificity'),
            'input_word_count': assessment.get('input_word_count'),
            'short_input_cap_applied': bool(assessment.get('short_input_cap_applied')),
            'missing_detail': assessment.get('missing_detail', []),
            'has_unrecognized_conditions': bool(assessment.get('has_unrecognized_conditions')),
            'unrecognized_condition_count': assessment.get('unrecognized_condition_count', 0),
            'requires_human_review': bool(assessment.get('requires_human_review')),
            'review_reasons': assessment.get('review_reasons', []),
            'used_prior_assessments': len(user_data.get('prior_assessments', [])),
            'created_at': triage_record.created_at
        }
        
        return Response(response_data, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.exception("triage.request_failed", extra={"request_id": locals().get('request_id'), "user_id": getattr(request.user, 'id', None), "error_type": type(e).__name__})
        return Response(
            {'error': f'Error processing assessment: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_triage_history(request):
    """Get user's triage history"""
    try:
        # Prefetch children so the loop below reads them from memory instead of
        # firing 2 queries per record, matching the clinician list view's
        # already-optimized pattern.
        records = (
            TriageRecord.objects.filter(user=request.user)
            .order_by('-created_at')
            .prefetch_related('possible_conditions', 'recommendations')
        )

        # Explicit pagination: FBVs don't inherit DRF's PAGE_SIZE.
        paginator, page = _paginate_queryset(request, records)

        history = []
        for record in page:
            conditions = record.possible_conditions.all()
            recommendations = record.recommendations.all()

            history.append({
                'id': record.pk,
                'date': record.created_at,
                'created_at': record.created_at,
                'symptoms': record.current_symptoms,
                'current_symptoms': record.current_symptoms,
                'risk_level': record.risk_level,
                'risk_probability': record.risk_probability,
                'reasoning': record.reasoning,
                'confidence': record.confidence,
                'possible_conditions': [c.disease_name for c in conditions],
                'recommendations': [r.description for r in recommendations],
                'assessment_source': record.assessment_source,
                'model_id': (record.similar_cases or {}).get('model_id'),
                'model_provider': (record.similar_cases or {}).get('model_provider'),
                'degraded': bool((record.similar_cases or {}).get('degraded')),
                # Older records only stored 'degraded'; fall back to it so
                # historical degraded assessments still surface the flag.
                'is_degraded': bool(
                    (record.similar_cases or {}).get('is_degraded')
                    or (record.similar_cases or {}).get('degraded')
                ),
                'model_error': (record.similar_cases or {}).get('model_error'),
            })

        # Standard {count, next, previous, results} envelope. The frontend
        # unwraps `results`, falling back to the legacy `history` key.
        return paginator.get_paginated_response(history)

    except Exception as e:
        return Response(
            {'error': f'Error retrieving history: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_triage_record(request, triage_id):
    """
    Delete one of the caller's own assessments.

    Guarded on purpose. PatientAssignment.triage_record cascades, and
    ClinicianAlert cascades off that in turn — so deleting an assessment that a
    clinician is still reviewing would silently remove it from their queue and
    take any unacknowledged high-risk alert with it. A patient must not be able
    to erase a clinician's pending work, so an assessment under active review is
    refused (409) with an explanation rather than deleted.

    Once the assignment is resolved or transferred, deletion is allowed.
    """
    try:
        record = TriageRecord.objects.get(id=triage_id, user=request.user)
    except TriageRecord.DoesNotExist:
        return Response({'error': 'Assessment not found.'}, status=status.HTTP_404_NOT_FOUND)

    active_assignments = record.assignments.exclude(status__in=['resolved', 'transferred'])
    if active_assignments.exists():
        return Response(
            {
                'error': 'This assessment is currently under clinician review and cannot be deleted yet.',
                'reason': 'under_clinician_review',
            },
            status=status.HTTP_409_CONFLICT,
        )

    record.delete()
    return Response({'message': 'Assessment deleted.'}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def analyze_medical_report(request):
    """
    Analyze uploaded medical report (PDF/Image) using the OCR + LLM pipeline.

    Accepts either an existing user-owned `report_id` or a multipart `file`.
    Runs synchronously: OCR extraction → LLM structuring → persist → respond.
    """
    import logging as _logging
    _logger = _logging.getLogger(__name__)

    try:
        report_id = request.data.get('report_id')
        existing_report = None
        uploaded_file = request.FILES.get('file')
        if report_id:
            existing_report = MedicalReport.objects.filter(id=report_id, user=request.user).first()
            if not existing_report:
                return Response({'error': 'Medical report not found.'}, status=status.HTTP_404_NOT_FOUND)
            existing_report.file.open('rb')
            file_bytes = existing_report.file.read()
            existing_report.file.close()
            file_type = existing_report.file_type or ''
            file_name = existing_report.file_name or existing_report.file.name
            file_size = existing_report.file_size
        elif uploaded_file:
            file_type = uploaded_file.content_type or ''
            file_name = uploaded_file.name
            file_size = uploaded_file.size
            file_bytes = uploaded_file.read()
        else:
            return Response({'error': 'No file uploaded or report_id provided.'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate file type
        file_type_lower = file_type.lower()
        if not ('pdf' in file_type_lower or 'image' in file_type_lower):
            # Try to infer from file name
            name_lower = (file_name or '').lower()
            if not any(name_lower.endswith(ext) for ext in ('.pdf', '.jpg', '.jpeg', '.png', '.webp', '.tiff', '.bmp')):
                return Response(
                    {'error': 'Unsupported file type. Please upload a PDF or image file.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Get user context for insight generation
        profile = UserProfile.objects.filter(user=request.user).first()
        gender = profile.gender if profile else 'Unknown'
        age = profile.calculate_age() if profile else None

        past_history = []
        if profile and profile.past_history:
            past_history = profile.past_history.get('conditions', [])

        user_context = {
            'age': age or 'Unknown',
            'gender': gender,
            'past_history': past_history,
        }

        # Quota gate for the report-insight LLM call (Gemini), before the
        # OCR + insight pipeline runs.
        try:
            check_llm_quota('report_insight', request.user.pk)
        except LLMQuotaExceeded as limit:
            return _rate_limited_response(limit, 'report analysis')

        # Run the OCR + LLM pipeline
        processor = get_report_processor()
        result = processor.extract_and_analyze(
            file_bytes=file_bytes,
            file_name=file_name,
            content_type=file_type,
            user_context=user_context,
            request_id=f"view-{request.user.pk}",
            user_id=request.user.pk,
        )

        if not result.get('success'):
            return Response(
                {'error': result.get('error', 'Failed to process report')},
                status=status.HTTP_400_BAD_REQUEST
            )

        extracted_text = result.get('extracted_text', '')
        structured_data = result.get('structured_data', {})
        insights_text = result.get('insights_text', '')
        ocr_path = result.get('ocr_path', 'unknown')

        # Persist results
        with transaction.atomic():
            if existing_report:
                medical_report = existing_report
                medical_report.file_type = file_type
                medical_report.file_size = file_size
                medical_report.extracted_text = extracted_text
                medical_report.structured_data = structured_data
                medical_report.insights_text = insights_text
                medical_report.ocr_path = ocr_path
                medical_report.status = 'completed'
                medical_report.save(update_fields=[
                    'file_type', 'file_size', 'extracted_text', 'structured_data',
                    'insights_text', 'ocr_path', 'status', 'updated_at',
                ])
                cast(Any, medical_report).tests.all().delete()
            else:
                # Reset file pointer for saving
                uploaded_file.seek(0)
                medical_report = MedicalReport.objects.create(
                    user=request.user,
                    file=uploaded_file,
                    file_name=file_name,
                    file_type=file_type,
                    file_size=file_size,
                    extracted_text=extracted_text,
                    structured_data=structured_data,
                    insights_text=insights_text,
                    ocr_path=ocr_path,
                    status='completed',
                )

            # Create MedicalTest and AbnormalResult rows from structured insights
            tests = structured_data.get('tests', [])
            for test_data in tests:
                if not isinstance(test_data, dict):
                    continue

                test_name = test_data.get('test_name', '')
                value_str = test_data.get('value', '')
                unit = test_data.get('unit', '')
                reference_range = test_data.get('reference_range', 'Not specified')
                test_status = test_data.get('status', 'unknown')
                is_abnormal = test_status not in ('normal', 'unknown')

                try:
                    test_value = float(value_str.replace(',', '').strip())
                except (ValueError, TypeError, AttributeError):
                    test_value = 0.0

                test = MedicalTest.objects.create(
                    medical_report=medical_report,
                    test_name=test_name,
                    test_value=test_value,
                    test_unit=unit,
                    reference_range=reference_range,
                    is_abnormal=is_abnormal,
                )

                if is_abnormal:
                    abnormal_findings = structured_data.get('abnormal_findings', [])
                    interpretation = ''
                    for finding in abnormal_findings:
                        if finding.get('test_name', '').lower() == test_name.lower():
                            interpretation = finding.get('explanation', '')
                            break

                    concern_level = 'Low'
                    if test_status == 'critical':
                        concern_level = 'High'
                    elif test_status in ('high', 'low'):
                        concern_level = 'Moderate'

                    AbnormalResult.objects.create(
                        medical_test=test,
                        status=test_status.capitalize(),
                        concern_level=concern_level,
                        interpretation=interpretation,
                    )

            # Critical values must reach a clinician, not just the patient's
            # screen. Alert-only: no TriageRecord is fabricated from an upload.
            escalate_critical_findings(
                user=request.user,
                report_id=medical_report.pk,
                file_name=medical_report.file_name,
                critical_findings=select_critical_findings(tests),
            )

        # Build response
        response_data = {
            'report_id': medical_report.pk,
            'success': True,
            'status': 'completed',
            'ocr_path': ocr_path,
            'extracted_text': extracted_text[:500],
            'structured_data': structured_data,
            'insights_text': insights_text,
            'summary': structured_data.get('summary', ''),
            'abnormal_findings': structured_data.get('abnormal_findings', []),
            'degraded': structured_data.get('degraded', False),
        }

        return Response(response_data, status=status.HTTP_201_CREATED)

    except Exception as e:
        _logger.exception("analyze_medical_report.failed")
        return Response(
            {'error': f'Error analyzing report: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_health_passport(request):
    """
    Get comprehensive health passport with all medical history
    """
    try:
        user = request.user
        profile = UserProfile.objects.filter(user=user).first()
        
        # Get triage records with prefetch to avoid N+1 when reading possible
        # conditions. Explicitly paginated (FBVs don't inherit DRF's PAGE_SIZE)
        # so the passport pages through consultations instead of a fixed slice.
        triage_records = (
            TriageRecord.objects.filter(user=user)
            .order_by('-created_at')
            .prefetch_related('possible_conditions')
        )
        paginator, page = _paginate_queryset(request, triage_records)
        triage_history = []
        for record in page:
            # Use the prefetched related set to avoid extra queries
            conditions = list(cast(Any, record).possible_conditions.all())
            triage_history.append({
                'date': record.created_at,
                'symptoms': record.current_symptoms,
                'risk_level': record.risk_level,
                'conditions': [c.disease_name for c in conditions]
            })

        # Get medical reports and prefetch tests and their abnormal_result to avoid N+1
        reports = (
            MedicalReport.objects.filter(user=user)
            .order_by('-upload_date')
            .prefetch_related('tests__abnormal_result')[:10]
        )
        reports_data = []
        for report in reports:
            # Use prefetched tests list and compute counts in-memory to avoid extra DB COUNT queries
            tests_list = list(cast(Any, report).tests.all())
            tests_count = len(tests_list)
            abnormal_count = sum(1 for t in tests_list if getattr(t, 'abnormal_result', None) is not None)

            reports_data.append({
                'id': report.pk,
                'date': report.upload_date,
                'file_name': report.file_name,
                'tests_count': tests_count,
                'abnormal_count': abnormal_count
            })
        
        # Past history
        past_history = profile.past_history if profile else {}

        # True consultation total. The paginator already counted the full
        # (unpaginated) triage set, so reuse it rather than firing a second
        # COUNT - len(triage_history) would only reflect the current page.
        total_consultations = paginator.page.paginator.count

        return Response({
            'profile': {
                'name': f"{user.first_name} {user.last_name}",
                'email': user.email,
                'age': profile.calculate_age() if profile else None,
                'gender': profile.gender if profile else None,
                'past_history': past_history
            },
            'triage_history': triage_history,
            # Pagination cursor for triage_history (the passport is a composite
            # payload, so the standard results-envelope can't wrap it directly).
            'triage_history_pagination': {
                'count': paginator.page.paginator.count,
                'next': paginator.get_next_link(),
                'previous': paginator.get_previous_link(),
            },
            'medical_reports': reports_data,
            'total_consultations': total_consultations
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': f'Error retrieving health passport: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ====================== CONSULTATION SESSION ENDPOINTS ======================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_consultation(request):
    """
    Start a new multi-step consultation session
    Body: {
        "symptoms": "Initial symptom description" (optional)
    }
    """
    try:
        # Deactivate any existing active sessions
        ConsultationSession.objects.filter(user=request.user, is_active=True).update(is_active=False)
        
        initial_symptoms = str(request.data.get('symptoms') or '').strip()
        has_report = bool(request.data.get('has_report'))

        # IMMEDIATE EMERGENCY CHECK - the wizard UI submits the patient's
        # symptom text here, not in submit_consultation_step's 'symptoms'
        # stage, so this is the real first point emergency text can appear.
        if contains_emergency_keyword(initial_symptoms):
            profile = UserProfile.objects.filter(user=request.user).first()
            pincode = profile.pincode if profile else None

            triage_record, assessment = create_emergency_triage_record(
                user=request.user,
                symptoms_text=initial_symptoms,
                input_mode='consultation',
                pincode=pincode,
            )

            session = ConsultationSession.objects.create(
                user=request.user,
                stage='completed',
                symptoms=initial_symptoms,
                triage_record=triage_record,
                is_active=False,
                completed_at=timezone.now(),
            )

            serializer = ConsultationSessionSerializer(session)
            return Response({
                'message': 'Emergency detected',
                'session': serializer.data,
                'risk_level': 'emergency',
                'triage_id': triage_record.pk,
                'reasoning': assessment['reasoning'],
                'recommendations': assessment['recommendations'],
                'when_to_seek_care': assessment['when_to_seek_care'],
            }, status=status.HTTP_201_CREATED)

        # The consultation UI submits symptoms before it renders the history step.
        # Mark that stage as complete when the initial request already contains
        # symptoms or an uploaded report, otherwise the next history submission
        # is incorrectly interpreted as another symptoms submission.
        session = ConsultationSession.objects.create(
            user=request.user,
            stage='history' if initial_symptoms or has_report else 'symptoms',
            symptoms=initial_symptoms,
            is_active=True
        )
        
        serializer = ConsultationSessionSerializer(session)
        return Response({
            'message': 'Consultation session started',
            'session': serializer.data
        }, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        return Response(
            {'error': f'Error starting consultation: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_consultation_step(request, session_id):
    """
    Submit data for current consultation step and progress to next stage
    Body varies by stage:
    - symptoms: {"symptoms": "text"}
    - history: {"medical_history": {...}}
    - questions: {"answers": [{"question": "...", "answer": "..."}]}
    """
    try:
        session = ConsultationSession.objects.filter(
            id=session_id,
            user=request.user,
            is_active=True
        ).first()
        
        if not session:
            return Response(
                {'error': 'Active consultation session not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        stage = session.stage
        
        # Handle symptoms stage
        if stage == 'symptoms':
            submitted_symptoms = request.data.get('symptoms', session.symptoms) or ''

            # IMMEDIATE EMERGENCY CHECK - must run before any LLM call, on the
            # raw text the patient just submitted.
            if contains_emergency_keyword(submitted_symptoms):
                pincode = None
                if session.medical_history:
                    pincode = session.medical_history.get('pincode')

                triage_record, assessment = create_emergency_triage_record(
                    user=request.user,
                    symptoms_text=submitted_symptoms,
                    input_mode='consultation',
                    pincode=pincode,
                )

                session.symptoms = submitted_symptoms
                session.triage_record = triage_record
                session.stage = 'completed'
                session.is_active = False
                session.completed_at = timezone.now()
                session.save()

                serializer = ConsultationSessionSerializer(session)
                return Response({
                    'message': 'Emergency detected',
                    'session': serializer.data,
                    'risk_level': 'emergency',
                    'triage_id': triage_record.pk,
                    'reasoning': assessment['reasoning'],
                    'recommendations': assessment['recommendations'],
                    'when_to_seek_care': assessment['when_to_seek_care'],
                }, status=status.HTTP_201_CREATED)

            session.symptoms = submitted_symptoms
            session.stage = 'history'
        
        # Handle history stage
        elif stage == 'history':
            session.medical_history = request.data.get('medical_history', {})
            session.stage = 'questions'
        
        # Handle questions stage - answers provided, move to assessment
        elif stage == 'questions':
            answers = request.data.get('answers', [])
            session.clarifying_questions = answers
            session.stage = 'assessment'
        
        # Handle assessment stage - generate final assessment
        elif stage == 'assessment':
            # Run AI assessment with all collected data
            triage_engine = get_triage_engine_v2()
            model_id = (request.data.get('model_id') or '').strip()
            if model_id and not is_allowed_openrouter_model(model_id):
                return Response(
                    {'error': 'Selected model is not available'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            consultation_profile = UserProfile.objects.filter(user=request.user).first()
            user_data = {
                'age': (consultation_profile.calculate_age() if consultation_profile else None) or 'Adult',
                'gender': (consultation_profile.gender if consultation_profile else None) or 'unknown',
                'past_history': session.medical_history,
                **build_patient_history_context(request.user),
            }

            # A clarifying round counts only if the patient actually answered
            # something - an empty or skipped round must not lift the
            # short-input confidence cap.
            answered_clarifications = [
                item for item in (session.clarifying_questions or [])
                if str(item.get('answer', '')).strip()
            ]
            had_clarifying_round = bool(answered_clarifications)

            clarifications_text = "\n".join(
                f"{item.get('question', 'Question')}: {item.get('answer', '')}"
                for item in answered_clarifications
            )
            full_symptoms = session.symptoms or ''
            if clarifications_text:
                full_symptoms = f"{full_symptoms}\n\nClarifying answers:\n{clarifications_text}"

            # Same triage counter as /triage/assess/: the consultation flow is
            # a second full-assessment path, so it must not be an ungated
            # bypass of the triage quota. The emergency check earlier in this
            # view has already returned for emergencies, so screening is never
            # gated.
            try:
                check_llm_quota('triage', request.user.pk)
            except LLMQuotaExceeded as limit:
                return _rate_limited_triage_response(limit)

            request_id = request.headers.get('X-Request-ID') or uuid.uuid4().hex
            assessment = triage_engine.assess(
                symptoms_text=full_symptoms,
                user_data=user_data,
                report_summary="",
                location="",
                model_id=model_id or '',
                request_id=request_id,
                user_id=request.user.pk,
                had_clarifying_round=had_clarifying_round,
                # session.symptoms was already checked via contains_emergency_keyword()
                # when it was first submitted (start_consultation / the 'symptoms'
                # stage above). full_symptoms appends "<question>: <answer>" for
                # each clarifying answer - and a clarifying question routinely
                # names the symptom it's asking about, so re-scanning the merged
                # text here would trigger on the question's own wording.
                skip_emergency_recheck=True,
            )

            # Create triage record + all child rows atomically - a failure
            # partway through must never leave a TriageRecord committed
            # without its conditions/recommendations/alert.
            with transaction.atomic():
                triage_record = TriageRecord.objects.create(
                    user=request.user,
                    current_symptoms=session.symptoms,
                    input_mode='consultation',
                    risk_level=assessment['risk_level'],
                    risk_probability=assessment['confidence'],
                    reasoning=assessment['reasoning'],
                    confidence=assessment['confidence'],
                    assessment_source=assessment.get('assessment_source') or 'ai_v2',
                    requires_human_review=bool(assessment.get('requires_human_review')),
                    similar_cases={
                        'model_id': assessment.get('model_id'),
                        'model_provider': assessment.get('model_provider'),
                        'degraded': bool(assessment.get('degraded')),
                        'is_degraded': bool(assessment.get('is_degraded')),
                        'model_error': assessment.get('model_error'),
                    }
                )

                # Add possible conditions
                for condition in assessment.get('possible_conditions', []):
                    if isinstance(condition, dict):
                        condition_name = condition.get('disease') or condition.get('name') or 'Unknown'
                        confidence = condition.get('confidence', assessment['confidence'])
                    else:
                        condition_name = str(condition)
                        confidence = assessment['confidence']
                    PossibleCondition.objects.create(
                        triage_record=triage_record,
                        disease_name=condition_name,
                        confidence=confidence
                    )

                # Add recommendations
                for idx, rec in enumerate(assessment.get('recommendations', []), 1):
                    Recommendation.objects.create(
                        triage_record=triage_record,
                        recommendation_type='action',
                        description=rec,
                        priority=idx
                    )

                # Notify a clinician for high/emergency AI assessments too,
                # not just the rule-based emergency short-circuit.
                create_alert_for_triage_record(triage_record)

            # Link triage record to session
            session.triage_record = triage_record
            session.stage = 'completed'
            session.is_active = False
            session.completed_at = timezone.now()
        
        session.save()
        
        serializer = ConsultationSessionSerializer(session)
        return Response({
            'message': f'Stage {stage} completed',
            'session': serializer.data
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.exception("triage.consultation_step_failed", extra={"request_id": locals().get('request_id'), "user_id": getattr(request.user, 'id', None), "session_id": session_id, "error_type": type(e).__name__})
        return Response(
            {'error': f'Error processing consultation step: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_clarifying_questions(request, session_id):
    """
    Generate clarifying questions based on symptoms and medical history
    Returns: List of questions to ask the user
    """
    try:
        session = ConsultationSession.objects.filter(
            id=session_id,
            user=request.user,
            is_active=True
        ).first()
        
        if not session:
            return Response(
                {'error': 'Active consultation session not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if session.stage != 'questions':
            return Response(
                {'error': f'Cannot generate questions at stage: {session.stage}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate questions using the V2 engine so question generation gets
        # the same provider failover and validation as assessment does.
        triage_engine = get_triage_engine_v2()

        questions_profile = UserProfile.objects.filter(user=request.user).first()
        user_data = {
            'age': (questions_profile.calculate_age() if questions_profile else None) or 'Adult',
            'gender': (questions_profile.gender if questions_profile else None) or 'unknown',
            'past_history': session.medical_history
        }

        questions = triage_engine.generate_clarifying_questions(
            symptoms_text=session.symptoms or '',
            user_data=user_data,
            request_id=request.headers.get('X-Request-ID') or uuid.uuid4().hex,
            user_id=request.user.pk,
        )
        
        return Response({
            'session_id': session_id,
            'questions': questions
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        logger.exception("triage.clarifying_questions_failed", extra={"user_id": getattr(request.user, 'id', None), "session_id": session_id, "error_type": type(e).__name__})
        return Response(
            {'error': f'Error generating questions: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_active_consultation(request):
    """Get the currently active consultation session for the user"""
    try:
        session = ConsultationSession.objects.filter(
            user=request.user,
            is_active=True
        ).first()
        
        if not session:
            return Response(
                {'message': 'No active consultation session'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = ConsultationSessionSerializer(session)
        return Response({
            'session': serializer.data
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response(
            {'error': f'Error retrieving consultation: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ====================== PDF GENERATION ENDPOINTS ======================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_assessment_pdf(request, triage_id):
    """
    Generate and download PDF report for a specific triage assessment
    URL: /api/reports/download/<triage_id>/
    """
    try:
        # Get triage record
        triage_record = TriageRecord.objects.filter(
            id=triage_id,
            user=request.user
        ).first()
        
        if not triage_record:
            return Response(
                {'error': 'Assessment not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get user profile
        user_profile = UserProfile.objects.filter(user=request.user).first()
        
        # Generate PDF
        pdf_content = generate_assessment_pdf(triage_record, request.user, user_profile)
        
        # Create response
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="medaid_assessment_{triage_id}.pdf"'
        
        return response
        
    except Exception as e:
        logger.exception(
            "reports.assessment_pdf_failed",
            extra={
                "user_id": getattr(request.user, 'id', None),
                "triage_id": triage_id,
                "error_type": type(e).__name__,
            },
        )
        return Response(
            {'error': f'Error generating PDF: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_health_passport_pdf(request):
    """
    Generate and download comprehensive health passport PDF
    URL: /api/reports/health-passport-pdf/
    """
    try:
        user = request.user
        user_profile = UserProfile.objects.filter(user=user).first()
        
        # Get all triage records
        triage_records = TriageRecord.objects.filter(user=user).order_by('-created_at')
        
        # Get all medical reports
        medical_reports = MedicalReport.objects.filter(user=user).order_by('-upload_date')
        
        # Generate PDF
        pdf_content = generate_health_passport_pdf(user, user_profile, triage_records, medical_reports)
        
        # Create response
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="medaid_health_passport_{user.id}.pdf"'
        
        return response
        
    except Exception as e:
        logger.exception(
            "reports.health_passport_pdf_failed",
            extra={
                "user_id": getattr(request.user, 'id', None),
                "error_type": type(e).__name__,
            },
        )
        return Response(
            {'error': f'Error generating PDF: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================================
# CLINICIAN DASHBOARD VIEWS
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def clinician_stats(request):
    """
    Get dashboard statistics for clinicians
    URL: /api/clinician/stats/
    """
    user = request.user
    
    # Check if user is a clinician
    if user.role != 'clinician':
        return Response(
            {'error': 'Only clinicians can access this endpoint'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        # Get all assignments for this clinician
        assignments = PatientAssignment.objects.filter(clinician=user)
        
        # Calculate statistics
        total_patients = assignments.values('patient').distinct().count()
        active_patients = assignments.filter(status='active').values('patient').distinct().count()
        
        # Emergency and high-risk patients
        emergency_assignments = assignments.filter(
            triage_record__risk_level='emergency',
            status__in=['active', 'monitoring']
        )
        high_risk_assignments = assignments.filter(
            triage_record__risk_level='high',
            status__in=['active', 'monitoring']
        )
        
        emergency_patients = emergency_assignments.count()
        high_risk_patients = high_risk_assignments.count()
        
        # Today's assessments
        from datetime import datetime, timedelta
        today = timezone.now().date()
        todays_assessments = assignments.filter(
            assigned_at__date=today
        ).count()
        
        # Pending alerts
        pending_alerts = ClinicianAlert.objects.filter(
            clinician=user,
            is_read=False
        ).count()
        
        stats = {
            'total_patients': total_patients,
            'active_patients': active_patients,
            'emergency_patients': emergency_patients,
            'high_risk_patients': high_risk_patients,
            'todays_assessments': todays_assessments,
            'pending_alerts': pending_alerts
        }
        
        serializer = ClinicianStatsSerializer(stats)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': f'Error fetching stats: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def clinician_patients(request):
    """
    Get list of patients assigned to clinician with filters
    URL: /api/clinician/patients/?risk_level=emergency&status=active&search=john
    """
    user = request.user
    
    # Check if user is a clinician
    if user.role != 'clinician':
        return Response(
            {'error': 'Only clinicians can access this endpoint'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        # Get all assignments for this clinician
        assignments = PatientAssignment.objects.filter(clinician=user).select_related(
            'patient', 'triage_record', 'clinician'
        ).prefetch_related('clinician_notes')
        
        # Apply filters
        risk_level = request.query_params.get('risk_level', None)
        if risk_level:
            assignments = assignments.filter(triage_record__risk_level=risk_level)
        
        assignment_status = request.query_params.get('status', None)
        if assignment_status:
            assignments = assignments.filter(status=assignment_status)
        
        # Search filter (patient name or email)
        search = request.query_params.get('search', None)
        if search:
            from django.db.models import Q
            assignments = assignments.filter(
                Q(patient__first_name__icontains=search) |
                Q(patient__last_name__icontains=search) |
                Q(patient__email__icontains=search)
            )
        
        # Date filter
        from_date = request.query_params.get('from_date', None)
        to_date = request.query_params.get('to_date', None)
        if from_date:
            assignments = assignments.filter(assigned_at__date__gte=from_date)
        if to_date:
            assignments = assignments.filter(assigned_at__date__lte=to_date)
        
        # Order by priority and date
        assignments = assignments.order_by('priority', '-assigned_at')

        # Explicit pagination: FBVs don't inherit DRF's PAGE_SIZE.
        paginator, page = _paginate_queryset(request, assignments)
        serializer = PatientAssignmentSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    except Exception as e:
        return Response(
            {'error': f'Error fetching patients: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assign_patient(request):
    """
    Assign a patient to current clinician (auto-assignment based on triage)
    URL: /api/clinician/assign-patient/
    Body: {"triage_id": 123, "priority": 1, "notes": "..."}
    """
    user = request.user
    
    # Check if user is a clinician
    if user.role != 'clinician':
        return Response(
            {'error': 'Only clinicians can assign patients'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        triage_id = request.data.get('triage_id')
        priority = request.data.get('priority', 1)
        notes = request.data.get('notes', '')
        
        if not triage_id:
            return Response(
                {'error': 'triage_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get triage record
        try:
            triage = TriageRecord.objects.get(id=triage_id)
        except TriageRecord.DoesNotExist:
            return Response(
                {'error': 'Triage record not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if already assigned
        existing = PatientAssignment.objects.filter(
            patient=triage.user,
            triage_record=triage,
            clinician=user
        ).first()
        
        if existing:
            return Response(
                {'message': 'Patient already assigned', 'assignment': PatientAssignmentSerializer(existing).data},
                status=status.HTTP_200_OK
            )
        
        # Create assignment
        assignment = PatientAssignment.objects.create(
            patient=triage.user,
            clinician=user,
            triage_record=triage,
            priority=priority,
            notes=notes,
            status='active'
        )
        
        serializer = PatientAssignmentSerializer(assignment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response(
            {'error': f'Error assigning patient: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_assignment_status(request, assignment_id):
    """
    Update patient assignment status
    URL: /api/clinician/assignments/<id>/status/
    Body: {"status": "resolved", "notes": "..."}
    """
    user = request.user
    
    if user.role != 'clinician':
        return Response(
            {'error': 'Only clinicians can update assignments'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        assignment = PatientAssignment.objects.get(id=assignment_id, clinician=user)
        
        new_status = request.data.get('status')
        notes = request.data.get('notes')
        
        if new_status:
            assignment.status = new_status
            if new_status == 'resolved':
                assignment.resolved_at = timezone.now()
        
        if notes:
            assignment.notes = notes
        
        assignment.save()
        
        serializer = PatientAssignmentSerializer(assignment)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    except PatientAssignment.DoesNotExist:
        return Response(
            {'error': 'Assignment not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': f'Error updating assignment: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_clinician_note(request):
    """
    Add a note to a patient assignment
    URL: /api/clinician/notes/
    Body: {"assignment_id": 123, "note": "...", "is_private": false}
    """
    user = request.user
    
    if user.role != 'clinician':
        return Response(
            {'error': 'Only clinicians can add notes'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        assignment_id = request.data.get('assignment_id')
        note = request.data.get('note')
        is_private = request.data.get('is_private', False)
        
        if not assignment_id or not note:
            return Response(
                {'error': 'assignment_id and note are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify assignment belongs to this clinician
        assignment = PatientAssignment.objects.get(id=assignment_id, clinician=user)
        
        # Create note
        clinician_note = ClinicianNote.objects.create(
            assignment=assignment,
            clinician=user,
            note=note,
            is_private=is_private
        )
        
        serializer = ClinicianNoteSerializer(clinician_note)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
        
    except PatientAssignment.DoesNotExist:
        return Response(
            {'error': 'Assignment not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': f'Error adding note: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def clinician_alerts(request):
    """
    Get alerts for clinician
    URL: /api/clinician/alerts/?is_read=false
    """
    user = request.user
    
    if user.role != 'clinician':
        return Response(
            {'error': 'Only clinicians can access alerts'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        # select_related covers the patient name/email columns and the
        # assignment -> triage_record hop the serializer's risk_level uses,
        # keeping the list a fixed number of queries.
        alerts = ClinicianAlert.objects.filter(clinician=user).select_related(
            'patient', 'assignment__triage_record'
        )

        # Filter by read status
        is_read = request.query_params.get('is_read', None)
        if is_read is not None:
            is_read_bool = is_read.lower() == 'true'
            alerts = alerts.filter(is_read=is_read_bool)
        
        alerts = alerts.order_by('-created_at')

        # Explicit pagination: FBVs don't inherit DRF's PAGE_SIZE.
        paginator, page = _paginate_queryset(request, alerts)
        serializer = ClinicianAlertSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    except Exception as e:
        return Response(
            {'error': f'Error fetching alerts: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def mark_alert_read(request, alert_id):
    """
    Mark alert as read
    URL: /api/clinician/alerts/<id>/mark-read/
    """
    user = request.user
    
    if user.role != 'clinician':
        return Response(
            {'error': 'Only clinicians can mark alerts'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        alert = ClinicianAlert.objects.get(id=alert_id, clinician=user)
        alert.is_read = True
        alert.read_at = timezone.now()
        alert.save()
        
        serializer = ClinicianAlertSerializer(alert)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    except ClinicianAlert.DoesNotExist:
        return Response(
            {'error': 'Alert not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        return Response(
            {'error': f'Error marking alert: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_nearby_facilities_view(request):
    """
    Get nearby facilities based on location
    """
    location = request.query_params.get('location', '')
    risk_level = request.query_params.get('risk_level', 'medium')
    
    # Use facility_recommendations.py
    from .facility_recommendations import get_nearby_facilities
    
    facilities = get_nearby_facilities(location, risk_level=risk_level)
    
    return Response({'facilities': facilities}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_dietary_recommendations_view(request):
    """
    Generate persisted, context-aware dietary guidance on the free tier.
    """
    payload = dict(request.data)
    allowed_risks = {'low', 'medium', 'high', 'emergency'}
    risk_level = payload.get('risk_level')
    if risk_level is not None and str(risk_level).lower() not in allowed_risks:
        return Response({'error': 'risk_level must be one of low, medium, high, or emergency.'}, status=status.HTTP_400_BAD_REQUEST)
    if 'possible_conditions' in payload and not isinstance(payload.get('possible_conditions'), list):
        return Response({'error': 'possible_conditions must be a list.'}, status=status.HTTP_400_BAD_REQUEST)
    if len(payload.get('possible_conditions', [])) > 25:
        return Response({'error': 'possible_conditions may include at most 25 items.'}, status=status.HTTP_400_BAD_REQUEST)
    for text_field in ('symptoms', 'current_symptoms', 'stated_preferences'):
        value = payload.get(text_field)
        if value is not None and not isinstance(value, str):
            return Response({'error': f'{text_field} must be text.'}, status=status.HTTP_400_BAD_REQUEST)
        if isinstance(value, str) and len(value) > 2000:
            return Response({'error': f'{text_field} is too long.'}, status=status.HTTP_400_BAD_REQUEST)

    minute_key = f"dietary:global:rpm:{timezone.now().strftime('%Y%m%d%H%M')}"
    day_key = f"dietary:global:day:{timezone.now().strftime('%Y%m%d')}"
    active_global_key = 'dietary:global:active'
    rpm_limit = max(1, getattr(settings, 'DIETARY_GLOBAL_RPM_LIMIT', 18))
    daily_limit = max(1, getattr(settings, 'DIETARY_GLOBAL_DAILY_LIMIT', 45))
    active_limit = max(1, getattr(settings, 'DIETARY_GLOBAL_ACTIVE_LIMIT', 2))

    active_timeout = getattr(settings, 'DIETARY_ACTIVE_REQUEST_SECONDS', 120)
    minute_timeout = 90
    day_timeout = 60 * 60 * 26

    # Reserve a global concurrency slot atomically. Incrementing first and
    # then comparing means concurrent requests can never all read an
    # under-limit value and admit themselves past the cap.
    if _cache_reserve(active_global_key, active_timeout) > active_limit:
        _cache_release(active_global_key, active_timeout)
        return Response(
            {'error': 'Dietary advice is temporarily busy because the shared free-model queue is full. Please try again shortly.', 'retry_after': 15},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={'Retry-After': '15'},
        )

    # The global slot is now held and must be released on every exit path.
    slot_released = False
    try:
        # Reserve against the per-minute and per-day quotas the same way,
        # handing back any reservation that turns out to exceed its limit.
        if _cache_reserve(minute_key, minute_timeout) > rpm_limit:
            _cache_release(minute_key, minute_timeout)
            return Response(
                {'error': 'The shared free-model dietary quota is temporarily exhausted. Please try again later.', 'retry_after': 60},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={'Retry-After': '60'},
            )

        if _cache_reserve(day_key, day_timeout) > daily_limit:
            _cache_release(day_key, day_timeout)
            _cache_release(minute_key, minute_timeout)
            return Response(
                {'error': 'The shared free-model dietary quota is temporarily exhausted. Please try again later.', 'retry_after': 3600},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={'Retry-After': '3600'},
            )

        active_key = f'dietary:active:{request.user.pk}'
        last_key = f'dietary:last:{request.user.pk}'
        now = timezone.now().timestamp()
        throttle_seconds = getattr(settings, 'DIETARY_THROTTLE_SECONDS', 15)
        last_request = cache.get(last_key)
        if last_request and throttle_seconds > 0 and now - float(last_request) < throttle_seconds:
            retry_after = max(1, int(throttle_seconds - (now - float(last_request))))
            return Response(
                {'error': 'Dietary advice is already being prepared or was requested recently. Please try again shortly.', 'retry_after': retry_after},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={'Retry-After': str(retry_after)},
            )
        # cache.add is atomic, so this doubles as the per-user concurrency gate.
        if not cache.add(active_key, '1', timeout=active_timeout):
            return Response(
                {'error': 'Dietary advice is already being prepared. Please wait a moment.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={'Retry-After': '10'},
            )

        try:
            response = generate_dietary_advice(request.user, payload)
            cache.set(last_key, now, timeout=max(throttle_seconds, 1))
            return Response(response, status=status.HTTP_200_OK)
        except DietaryGenerationError as error:
            response_status = status.HTTP_429_TOO_MANY_REQUESTS if error.status_code == 429 else status.HTTP_503_SERVICE_UNAVAILABLE
            return Response(
                {'error': str(error), 'retry_after': 60 if response_status == status.HTTP_429_TOO_MANY_REQUESTS else 30},
                status=response_status,
                headers={'Retry-After': '60' if response_status == status.HTTP_429_TOO_MANY_REQUESTS else '30'},
            )
        finally:
            cache.delete(active_key)
            _cache_release(active_global_key, active_timeout)
            slot_released = True
    finally:
        if not slot_released:
            _cache_release(active_global_key, active_timeout)


# ============= PERSISTENT CHAT CONVERSATIONS =============

from .models import ChatConversation, ChatMessage
from .chat_service import get_chat_service
from .medical_report_analyzer import get_medical_report_analyzer
from .serializers import ChatConversationSerializer, ChatConversationListSerializer, ChatMessageSerializer



@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def chat_conversations_list(request):
    """
    GET: List all conversations for the current user
    POST: Create a new conversation
    
    URL: /api/chat/conversations/
    """
    if request.method == 'GET':
        conversations = ChatConversation.objects.filter(user=request.user)
        serializer = ChatConversationListSerializer(conversations, many=True)
        return Response({
            'conversations': serializer.data
        }, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        # Create new conversation
        first_message = request.data.get('first_message', '')
        
        conversation = ChatConversation.objects.create(
            user=request.user,
            title='New Conversation',  # Will be updated after first message
            is_active=True
        )
        
        serializer = ChatConversationSerializer(conversation)
        return Response({
            'conversation': serializer.data
        }, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def chat_conversation_detail(request, conversation_id):
    """
    GET: Get a specific conversation with all messages
    PATCH: Update conversation (title, is_active)
    DELETE: Delete a conversation
    
    URL: /api/chat/conversations/<id>/
    """
    try:
        conversation = ChatConversation.objects.get(id=conversation_id, user=request.user)
    except ChatConversation.DoesNotExist:
        return Response(
            {'error': 'Conversation not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if request.method == 'GET':
        serializer = ChatConversationSerializer(conversation)
        return Response({
            'conversation': serializer.data
        }, status=status.HTTP_200_OK)
    
    elif request.method == 'PATCH':
        # Update conversation (e.g., rename)
        if 'title' in request.data:
            conversation.title = request.data['title']
        if 'is_active' in request.data:
            conversation.is_active = request.data['is_active']
        
        conversation.save()
        serializer = ChatConversationSerializer(conversation)
        return Response({
            'conversation': serializer.data
        }, status=status.HTTP_200_OK)
    
    elif request.method == 'DELETE':
        conversation.delete()
        return Response(
            {'message': 'Conversation deleted successfully'},
            status=status.HTTP_200_OK
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def chat_send_message(request, conversation_id):
    """
    Send a message in a conversation and get AI response.
    Supports file uploads for medical reports.
    
    URL: /api/chat/conversations/<id>/messages/
    Body: multipart/form-data or JSON
    - content: "user message text"
    - file: (optional) file attachment
    """
    try:
        conversation = ChatConversation.objects.get(id=conversation_id, user=request.user)
    except ChatConversation.DoesNotExist:
        return Response(
            {'error': 'Conversation not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    user_message_content = request.data.get('content', '').strip()
    model_id = (request.data.get('model_id') or '').strip()
    uploaded_file = request.FILES.get('file')

    if not user_message_content and not uploaded_file:
        return Response(
            {'error': 'Message content or file is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # IMMEDIATE EMERGENCY CHECK - must run before any file analysis or LLM call.
    if contains_emergency_keyword(user_message_content):
        chat_service = get_chat_service()
        profile = UserProfile.objects.filter(user=request.user).first()
        pincode = profile.pincode if profile else None

        triage_record, assessment = create_emergency_triage_record(
            user=request.user,
            symptoms_text=user_message_content,
            input_mode='chat',
            pincode=pincode,
        )

        user_message = ChatMessage.objects.create(
            conversation=conversation,
            role='user',
            content=user_message_content,
            tokens_used=chat_service.estimate_tokens(user_message_content),
        )

        emergency_text = (
            "🚨 EMERGENCY 🚨 " + assessment['reasoning'] + "\n\n"
            "Recommendations:\n" + "\n".join(f"• {rec}" for rec in assessment['recommendations']) +
            f"\n\nWhen to seek care:\n{assessment['when_to_seek_care']}\n\n" + assessment['disclaimer']
        )
        assistant_message = ChatMessage.objects.create(
            conversation=conversation,
            role='assistant',
            content=emergency_text,
            tokens_used=chat_service.estimate_tokens(emergency_text),
            metadata={
                'assessment_source': 'emergency_rule',
                'risk_level': 'emergency',
                'triage_id': triage_record.pk,
                # Same structured-field contract as the regular assessment
                # path below, so the frontend renders both with one component.
                'risk_probability': assessment.get('risk_probability'),
                'confidence': assessment.get('confidence'),
                'reasoning': assessment.get('reasoning'),
                'possible_conditions': assessment.get('possible_conditions'),
                'recommendations': assessment.get('recommendations'),
                'when_to_seek_care': assessment.get('when_to_seek_care'),
                'requires_human_review': bool(assessment.get('requires_human_review')),
            }
        )

        conversation.total_tokens_used += (user_message.tokens_used + assistant_message.tokens_used)
        conversation.save()

        return Response({
            'user_message': ChatMessageSerializer(user_message).data,
            'assistant_message': ChatMessageSerializer(assistant_message).data,
            'conversation': {
                'id': conversation.pk,
                'title': conversation.title,
                'total_tokens_used': conversation.total_tokens_used,
            },
            'suggest_new_chat': False,
            'risk_level': 'emergency',
            'triage_id': triage_record.pk,
        }, status=status.HTTP_201_CREATED)

    try:
        chat_service = get_chat_service()
        selected_model_id = None
        if model_id:
            if not is_allowed_openrouter_model(model_id):
                return Response(
                    {'error': 'Selected model is not available'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            selected_model_id = model_id
            profile = UserProfile.objects.filter(user=request.user).first()
            if profile:
                profile.preferred_model = selected_model_id
                profile.save(update_fields=['preferred_model', 'updated_at'])

        # Quota gate for the chat LLM turn. The emergency short-circuit above
        # has already returned for emergencies, so screening is never gated.
        try:
            check_llm_quota('chat', request.user.pk)
        except LLMQuotaExceeded as limit:
            return _rate_limited_response(limit, 'chat')

        # 1. Handle File Upload if present
        file_analysis_text = ""
        report = None
        analysis_result = None
        
        if uploaded_file:
            # Create MedicalReport
            report = MedicalReport.objects.create(
                user=request.user,
                file=uploaded_file,
                file_name=uploaded_file.name,
                file_type=uploaded_file.content_type,
                file_size=uploaded_file.size
            )
            
            # Analyze using Gemini
            analyzer = get_medical_report_analyzer()
            
            file_content = uploaded_file.read()
            # Reset file pointer for any subsequent reads
            if hasattr(uploaded_file, 'seek'):
                uploaded_file.seek(0)
            
            analysis_result = analyzer.analyze_report(
                file_bytes=file_content,
                file_type=uploaded_file.content_type,
                file_name=uploaded_file.name
            )
            
            if analysis_result.get('success'):
                # Save analysis to report
                report.extracted_text = analysis_result.get('markdown_report', '')
                report.structured_data = analysis_result.get('json_data', {})
                report.description = analysis_result.get('clinical_insights', '')
                report.save()
                
                # Prepare text to inject into chat context
                file_analysis_text = (
                    f"\\n\\n[System: User uploaded a medical report named '{uploaded_file.name}'. "
                    f"Analysis content: {analysis_result.get('clinical_insights', 'No insights found.')}]"
                )
                
                if not user_message_content:
                    user_message_content = f"Uploaded medical report: {uploaded_file.name}"
            else:
                file_analysis_text = f"\\n\\n[System: User uploaded file '{uploaded_file.name}' but analysis failed: {analysis_result.get('error')}]"
                if not user_message_content:
                     user_message_content = f"Uploaded file: {uploaded_file.name} (Analysis failed)"

        # 2. Save User Message
        try:
            tokens_est = chat_service.estimate_tokens(user_message_content + file_analysis_text)
        except:
            tokens_est = len(user_message_content) // 4

        user_message = ChatMessage.objects.create(
            conversation=conversation,
            role='user',
            content=user_message_content,
            tokens_used=tokens_est,
            metadata={'model_id': selected_model_id} if selected_model_id else {}
        )
        
        # Link report to message metadata if exists
        if report:
            # Ensure metadata field exists on model. If not, this might fail or be ignored.
            # Assuming metadata field exists based on previous thought process, but if not, 
            # we should skip or use another way.
            # However, I didn't add the field because migrations failed/I skipped migrations.
            # Wait! I skipped adding `file` field. Did I check `metadata`?
            # I read `ChatMessage` model and it had `metadata = models.JSONField(...)`.
            # So `metadata` exists!
            if hasattr(user_message, 'metadata'):
                user_message.metadata = {
                    **(user_message.metadata or {}),
                    'type': 'file_upload', 
                    'report_id': report.pk,
                    'file_url': report.file.url if report.file else '',
                }
                user_message.save()

        # If this is the first user message, generate a title
        if ChatMessage.objects.filter(conversation=conversation, role='user').count() == 1:
            # Title generation is a second (small) Gemini call. Count it against
            # the chat GLOBAL quota so it isn't a quota-free loophole, but give
            # it no per-user gate of its own and never let it block the turn
            # (the message itself was already gated above).
            note_global_usage('chat')
            generated_title = chat_service.generate_chat_title(user_message_content)
            conversation.title = generated_title
            conversation.save()
        
        # 3. Build Context
        context_messages = conversation.get_context_messages()
        
        # Inject analysis into context manually for this turn
        if file_analysis_text:
             # Find the most recent user message (which corresponds to what we just saved)
             # context_messages from `get_context_messages` returns messages in chronological order (oldest -> newest)
             # So the last message should be the user message.
             if context_messages and context_messages[-1]['role'] == 'user':
                 context_messages[-1]['content'] += file_analysis_text
        
        # Get user profile data for context
        chat_profile = UserProfile.objects.filter(user=request.user).first()
        history_context = build_patient_history_context(request.user)
        if chat_profile:
            user_data = {
                'age': chat_profile.calculate_age() or 'Adult',
                'gender': chat_profile.gender or 'unknown',
                'past_history': chat_profile.past_history.get('conditions', []) if chat_profile.past_history else [],
                **history_context,
            }
        else:
            user_data = dict(history_context)

        # Vagueness gate: if this is a plain-text symptom message too thin to
        # answer confidently, ask a clarifying follow-up before scoring off a
        # single line. Uses the shared trigger and the V2 question generator -
        # same logic as /triage/assess/ and the consultation wizard. We ask at
        # most once per exchange: if our previous turn already asked, the user
        # is now answering, so proceed to a real response. Skip when a report
        # was uploaded (it supplies its own detail).
        prior_assistant = (
            ChatMessage.objects.filter(conversation=conversation, role='assistant')
            .order_by('-created_at')
            .first()
        )
        already_asked_clarification = bool(
            prior_assistant and (prior_assistant.metadata or {}).get('clarification_requested')
        )
        if (
            not uploaded_file
            and not already_asked_clarification
            and should_request_clarification(user_message_content)
        ):
            clarifying_questions = get_triage_engine_v2().generate_clarifying_questions(
                symptoms_text=user_message_content,
                user_data=user_data,
                model_id=selected_model_id,
                request_id=request.headers.get('X-Request-ID') or uuid.uuid4().hex,
                user_id=request.user.pk,
            )
            if clarifying_questions:
                clarify_lines = [
                    'Before I can give you useful guidance, a few quick questions:'
                ]
                for index, question in enumerate(clarifying_questions, start=1):
                    clarify_lines.append(f"{index}. {question.get('question', '')}")
                clarify_text = "\n".join(clarify_lines)

                assistant_message = ChatMessage.objects.create(
                    conversation=conversation,
                    role='assistant',
                    content=clarify_text,
                    tokens_used=chat_service.estimate_tokens(clarify_text),
                    metadata={
                        'clarification_requested': True,
                        'clarifying_questions': clarifying_questions,
                        'assessment_source': 'clarifying_questions',
                    },
                )
                conversation.total_tokens_used += (
                    user_message.tokens_used + assistant_message.tokens_used
                )
                conversation.save()

                return Response({
                    'user_message': ChatMessageSerializer(user_message).data,
                    'assistant_message': ChatMessageSerializer(assistant_message).data,
                    'conversation': {
                        'id': conversation.pk,
                        'title': conversation.title,
                        'total_tokens_used': conversation.total_tokens_used,
                    },
                    'suggest_new_chat': False,
                    'needs_clarification': True,
                }, status=status.HTTP_201_CREATED)

        # 4. Generate AI Response
        # We pass modified content as the user message for AI generation
        # NOTE: generate_ai_response typically takes `user_message` string and `context`.
        # If we pass `user_message_content` as is, the AI won't see the file analysis unless it's in context.
        # But we updated `context_messages` above.
        # Wait, `get_context_messages` returns a list of dicts.
        # `generate_ai_response` usually takes the *current* message as string, and *history* as list.
        # If history includes the current message, we might double it?
        # Let's check `generate_ai_response` again.
        # It takes `context_messages` and appends `user_message` to it.
        # "context_text += ... for msg in context_messages ... context_text += f'Patient: {user_message}'"
        # So `context_messages` should be the HISTORY (excluding current).
        # But `get_context_messages` includes the current message because we saved it first!
        # So we should exclude the last message from `context_messages` when passing to `generate_ai_response`, and pass the full content as `user_message`.
        
        full_content_for_ai = user_message_content + file_analysis_text
        context_for_ai = context_messages[:-1] if context_messages else []

        ai_response = chat_service.generate_ai_response(
            full_content_for_ai,
            context_for_ai,
            user_data,
            model_id=selected_model_id,
        )

        # generate_ai_response already runs a full TriageEngineV2.assess() call
        # under the hood - a risk_level in the result means that completed
        # (the exception-fallback path returns no risk_level at all). Persist
        # it as a TriageRecord, exactly like /triage/assess/ does, so a chat
        # turn shows up in Assessment history and can generate a PDF too:
        # chat and the guided assessment flow are one pipeline now, not two.
        triage_id = None
        if ai_response.get('risk_level'):
            triage_record = _persist_triage_assessment(
                user=request.user,
                symptoms_text=full_content_for_ai,
                input_mode='chat',
                assessment=ai_response,
                medical_report_id=report.pk if report else None,
            )
            triage_id = triage_record.pk

        # 5. Save Assistant Message
        assistant_message = ChatMessage.objects.create(
            conversation=conversation,
            role='assistant',
            content=ai_response['content'],
            tokens_used=ai_response['tokens_used'],
            metadata={
                'model_id': ai_response.get('model_id') or selected_model_id,
                'model_provider': ai_response.get('model_provider'),
                'degraded': bool(ai_response.get('degraded')),
                'is_degraded': bool(ai_response.get('is_degraded') or ai_response.get('degraded')),
                'assessment_source': ai_response.get('assessment_source'),
                # Structured fields for the frontend's assessment card - same
                # contract as /triage/assess/, so one rendering path covers both.
                'triage_id': triage_id,
                'risk_level': ai_response.get('risk_level'),
                'risk_probability': ai_response.get('risk_probability'),
                'confidence': ai_response.get('confidence'),
                # The clinical prose, so the card can offer it behind a
                # disclosure instead of parsing it back out of `content`.
                'reasoning': ai_response.get('reasoning'),
                'possible_conditions': ai_response.get('possible_conditions'),
                'recommendations': ai_response.get('recommendations'),
                'when_to_seek_care': ai_response.get('when_to_seek_care'),
                'requires_human_review': bool(ai_response.get('requires_human_review')),
            }
        )
        
        # Update conversation token count
        conversation.total_tokens_used += (user_message.tokens_used + assistant_message.tokens_used)
        conversation.save()
        
        # Check if we should suggest a new chat
        suggest_new_chat = chat_service.should_suggest_new_chat(conversation.total_tokens_used)
        
        return Response({
            'user_message': ChatMessageSerializer(user_message).data,
            'assistant_message': ChatMessageSerializer(assistant_message).data,
            'conversation': {
                'id': conversation.pk,
                'title': conversation.title,
                'total_tokens_used': conversation.total_tokens_used
            },
            'suggest_new_chat': suggest_new_chat
        }, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        logger.exception(
            "chat.send_message_failed",
            extra={
                "user_id": getattr(request.user, 'id', None),
                "conversation_id": conversation_id,
                "error_type": type(e).__name__,
            },
        )
        return Response(
            {'error': f'Error processing message: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def chat_get_messages(request, conversation_id):
    """
    Get all messages in a conversation
    
    URL: /api/chat/conversations/<id>/messages/
    """
    try:
        conversation = ChatConversation.objects.get(id=conversation_id, user=request.user)
    except ChatConversation.DoesNotExist:
        return Response(
            {'error': 'Conversation not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    messages = ChatMessage.objects.filter(conversation=conversation).order_by('created_at')
    serializer = ChatMessageSerializer(messages, many=True)
    
    return Response({
        'messages': serializer.data,
        'conversation': {
            'id': conversation.pk,
            'title': conversation.title,
            'total_tokens_used': conversation.total_tokens_used
        }
    }, status=status.HTTP_200_OK)


# ============= DETAILED MEDICAL REPORT ANALYSIS (local T5 + pipeline) =============

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def analyze_report_detailed(request):
    """
    Generate detailed clinical insights from a medical report using
    local ML pipeline (OCR + Knowledge Base + T5).
    No external API calls.
    
    Request body (JSON):
    {
        "report_id": 123  // ID of the uploaded medical report
    }
    
    OR multipart/form-data with 'file' field for direct analysis without saving
    
    Returns:
        Comprehensive clinical analysis including:
        - Extracted test results
        - Abnormal findings
        - Clinical insights (T5 + Knowledge Base)
        - Follow-up recommendations
    """
    try:
        from .medical_pipeline import analyze_medical_report_local, analyze_extracted_values
        
        report_id = request.data.get('report_id')
        
        # Get user gender for reference ranges
        user = request.user
        gender = getattr(user, 'gender', 'male') or 'male'
        gender = gender.lower() if gender else 'male'
        
        if report_id:
            # Analyze an existing report
            try:
                report = MedicalReport.objects.get(id=report_id, user=request.user)
            except MedicalReport.DoesNotExist:
                return Response(
                    {'error': 'Medical report not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # If report has structured data with test values, use that first
            if report.structured_data and isinstance(report.structured_data, dict):
                test_values, units = _extract_test_values_from_structured(report.structured_data)
                if test_values:
                    pipeline_result = analyze_extracted_values(test_values, units=units, gender=gender)
                    # Save analysis
                    report.structured_data['detailed_analysis'] = {
                        'generated_at': timezone.now().isoformat(),
                        'summary': pipeline_result.get('summary', {}),
                        'findings_count': len(pipeline_result.get('findings', []))
                    }
                    report.save()
                    return _format_detailed_pipeline_response(pipeline_result, report_id, report.file_name, user=request.user)
            
            # Otherwise use file bytes with OCR pipeline
            report.file.seek(0)
            file_bytes = report.file.read()
            file_type = 'pdf' if 'pdf' in report.file_type.lower() else 'image'
            
            pipeline_result = analyze_medical_report_local(
                file_bytes=file_bytes,
                file_type=file_type,
                gender=gender,
                mode='ocr'
            )
            
            # Save analysis
            if pipeline_result.get('success'):
                report.structured_data = report.structured_data or {}
                report.structured_data['detailed_analysis'] = {
                    'generated_at': timezone.now().isoformat(),
                    'summary': pipeline_result.get('summary', {}),
                    'findings_count': len(pipeline_result.get('findings', []))
                }
                report.save()
            
            return _format_detailed_pipeline_response(pipeline_result, report_id, report.file_name, user=request.user)
            
        elif 'file' in request.FILES:
            # Analyze uploaded file directly
            uploaded_file = request.FILES['file']
            file_bytes = uploaded_file.read()
            file_type = 'pdf' if 'pdf' in uploaded_file.content_type.lower() else 'image'
            
            pipeline_result = analyze_medical_report_local(
                file_bytes=file_bytes,
                file_type=file_type,
                gender=gender,
                mode='ocr'
            )
            
            return _format_detailed_pipeline_response(
                pipeline_result, None, uploaded_file.name,
                user=request.user, content_key=content_key_for(file_bytes),
            )
        else:
            return Response(
                {'error': 'Either report_id or file must be provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
    except Exception as e:
        logger.exception(
            "reports.detailed_analysis_failed",
            extra={
                "user_id": getattr(request.user, 'id', None),
                "error_type": type(e).__name__,
            },
        )
        return Response(
            {'error': f'Error analyzing report: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def _extract_test_values_from_structured(structured_data: dict):
    """Extract test values and units from structured_data dict."""
    test_values = {}
    units = {}
    
    if 'parameters' in structured_data:
        for param in structured_data.get('parameters', []):
            if isinstance(param, dict):
                name = param.get('name') or param.get('test') or param.get('parameter')
                value = param.get('value')
                unit = param.get('unit', '')
                if name and value:
                    try:
                        test_values[name] = float(str(value).replace(',', ''))
                        if unit:
                            units[name] = unit
                    except (ValueError, TypeError):
                        pass
    
    if 'abnormal_results' in structured_data:
        for result in structured_data.get('abnormal_results', []):
            if isinstance(result, dict):
                name = result.get('parameter') or result.get('name')
                value = result.get('value')
                if name and value:
                    try:
                        test_values[name] = float(str(value).replace(',', ''))
                    except (ValueError, TypeError):
                        pass
    
    # Also check for direct test_name:value mappings
    for key, value in structured_data.items():
        if key.startswith('llm_') or key in ('parameters', 'abnormal_results', 'detailed_analysis', 'pipeline_analysis'):
            continue
        if isinstance(value, (int, float)):
            test_values[key] = float(value)
    
    return test_values, units


def _format_detailed_pipeline_response(pipeline_result: dict, report_id, file_name: str, user=None, content_key=None) -> Response:
    """
    Format local pipeline result for the detailed analysis endpoint.
    Compatible with frontend expectations.
    """
    if not pipeline_result.get('success'):
        return Response(
            {'error': pipeline_result.get('error', 'Analysis failed')},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    summary_data = pipeline_result.get('summary', {})
    findings = pipeline_result.get('findings', [])
    text_report = pipeline_result.get('text_report', '')
    narrative_insights = (
        pipeline_result.get('clinical_insights')
        or pipeline_result.get('markdown_report')
        or text_report
        or ""
    )
    
    # Build extraction summary
    extraction_summary = {
        'total_tests': summary_data.get('total_tests', 0),
        'abnormal_count': summary_data.get('abnormal', 0),
        'normal_count': summary_data.get('normal', 0),
        'critical_findings': [],
        'all_abnormals': []
    }
    
    for f in findings:
        st = f.get('status', 'UNKNOWN')
        if is_critical_status(st):
            extraction_summary['critical_findings'].append({
                'test': f.get('test_name', ''),
                'value': f.get('value'),
                'unit': f.get('unit', ''),
                'status': st
            })
        if st not in ('NORMAL', 'UNKNOWN'):
            extraction_summary['all_abnormals'].append({
                'test': f.get('test_name', ''),
                'value': f.get('value'),
                'unit': f.get('unit', ''),
                'status': st,
                'explanation': f.get('explanation', {}).get('simple', '')
            })

    # Critical values must reach a clinician, not just the patient's screen.
    # `user` is optional so the formatter stays callable from any context;
    # when absent no escalation happens.
    if user is not None:
        escalate_critical_findings(
            user=user,
            report_id=report_id,
            file_name=file_name,
            critical_findings=extraction_summary['critical_findings'],
            content_key=content_key,
        )


    # Build clinical insights from structured findings; fallback to direct model narrative
    insights_parts = []
    total = summary_data.get('total_tests', 0)
    abnormal = summary_data.get('abnormal', 0)
    critical = summary_data.get('critical_flags', 0)

    if total == 0 and not findings and narrative_insights.strip():
        clinical_insights = narrative_insights
        return Response({
            'success': True,
            'report_id': report_id,
            'file_name': file_name,
            'generated_at': timezone.now().isoformat(),
            'extraction_summary': extraction_summary,
            'extracted_reports': findings,
            'clinical_insights': clinical_insights,
            'markdown_report': narrative_insights,
            'summary': 'Analysis complete. Narrative insights generated from the uploaded report.',
            'risk_assessment': 'Review insights and consult doctor for final diagnosis.',
            'key_findings': ['Detailed AI explanation generated from report content.'],
            'recommendations': ['Please review the detailed insights and consult your healthcare provider.'],
            'follow_up': 'Consult your doctor for medical decisions based on this report.'
        }, status=status.HTTP_200_OK)
    
    insights_parts.append(f"## Summary\nAnalyzed {total} test parameters. "
                          f"{abnormal} abnormal value(s) found.")
    if critical > 0:
        insights_parts.append(f"\n**⚠️ {critical} CRITICAL value(s) detected — immediate medical attention recommended.**")
    
    insights_parts.append("\n## Findings")
    for f in findings:
        st = f.get('status', 'UNKNOWN')
        if st in ('NORMAL', 'UNKNOWN'):
            continue
        name = f.get('test_name', '')
        val = f.get('value', '')
        unit = f.get('unit', '')
        icon = f.get('status_icon', '')
        explanation = f.get('explanation', {})
        simple = explanation.get('simplified') or explanation.get('simple', '')
        
        insights_parts.append(f"\n### {icon} {name}: {val} {unit} ({st})")
        if simple:
            insights_parts.append(f"{simple}")
        causes = explanation.get('possible_causes', [])
        if causes:
            insights_parts.append(f"\n**Possible causes:** {', '.join(causes[:4])}")
        action = explanation.get('action', '')
        if action:
            insights_parts.append(f"\n**Recommended action:** {action}")
    
    # Note normal values
    normal_count = summary_data.get('normal', 0)
    if normal_count > 0:
        insights_parts.append(f"\n## Normal Values\n✅ {normal_count} test(s) within normal reference ranges.")
    
    clinical_insights = "\n".join(insights_parts)
    
    return Response({
        'success': True,
        'report_id': report_id,
        'file_name': file_name,
        'generated_at': timezone.now().isoformat(),
        'extraction_summary': extraction_summary,
        'extracted_reports': findings,
        'clinical_insights': clinical_insights,
        'markdown_report': text_report,
        # Also include frontend-compatible format
        'summary': f"Analysis complete. {total} tests: {abnormal} abnormal, {total - abnormal} normal." + 
                   (f" ⚠️ {critical} critical." if critical else ""),
        'risk_assessment': (
            "HIGH - Critical values detected." if critical > 0
            else "MODERATE - Abnormal values found." if abnormal > 0
            else "MINIMAL - All normal."
        ),
        'key_findings': [
            f"{f.get('status_icon','')} {f.get('test_name','')}: {f.get('value','')} {f.get('unit','')} ({f.get('status','')})"
            for f in findings if f.get('status') not in ('NORMAL', 'UNKNOWN')
        ][:10],
        'recommendations': list({
            f.get('explanation', {}).get('action', '')
            for f in findings
            if f.get('status') not in ('NORMAL', 'UNKNOWN') and f.get('explanation', {}).get('action')
        })[:5] or ["Maintain healthy lifestyle and regular check-ups."],
        'follow_up': (
            "Immediate medical consultation required." if critical > 0
            else "Schedule follow-up with your doctor." if abnormal > 0
            else "Continue routine monitoring."
        )
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_report_analysis(request, report_id):
    """
    Download detailed analysis as JSON or Markdown file.
    Uses local pipeline (T5 + KB) — no external API calls.
    
    Query params:
        - format: 'json' or 'md' (default: 'md')
    
    Returns:
        File download with analysis data
    """
    try:
        from .medical_pipeline import analyze_medical_report_local, analyze_extracted_values
        
        report = MedicalReport.objects.get(id=report_id, user=request.user)
        
        output_format = request.GET.get('format', 'md').lower()
        
        # Check if analysis already exists in structured_data
        if report.structured_data and 'detailed_analysis' in report.structured_data:
            analysis = report.structured_data['detailed_analysis']
            
            if output_format == 'json':
                content = json.dumps({
                    'report_name': report.file_name,
                    'analysis': analysis
                }, indent=2)
                content_type = 'application/json'
                filename = f"{report.file_name.rsplit('.', 1)[0]}_analysis.json"
            else:
                content = f"# Medical Report Analysis\n\n"
                content += f"**Report:** {report.file_name}\n\n"
                content += f"**Generated:** {analysis.get('generated_at', 'N/A')}\n\n"
                content += "---\n\n"
                content += f"**Tests:** {analysis.get('summary', {}).get('total_tests', 'N/A')}\n"
                content += f"**Abnormal:** {analysis.get('summary', {}).get('abnormal', 'N/A')}\n\n"
                content_type = 'text/markdown'
                filename = f"{report.file_name.rsplit('.', 1)[0]}_analysis.md"
        else:
            # Run analysis using local pipeline
            user = request.user
            gender = getattr(user, 'gender', 'male') or 'male'
            gender = gender.lower() if gender else 'male'
            
            # Try structured data first
            pipeline_result = None
            if report.structured_data and isinstance(report.structured_data, dict):
                test_values, units = _extract_test_values_from_structured(report.structured_data)
                if test_values:
                    pipeline_result = analyze_extracted_values(test_values, units=units, gender=gender)
            
            # Fall back to file-based analysis
            if not pipeline_result or not pipeline_result.get('success'):
                report.file.seek(0)
                file_bytes = report.file.read()
                file_type = 'pdf' if 'pdf' in report.file_type.lower() else 'image'
                pipeline_result = analyze_medical_report_local(
                    file_bytes=file_bytes,
                    file_type=file_type,
                    gender=gender,
                    mode='ocr'
                )
            
            if not pipeline_result.get('success'):
                return Response(
                    {'error': pipeline_result.get('error', 'Analysis failed')},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if output_format == 'json':
                content = json.dumps(pipeline_result, indent=2, default=str)
                content_type = 'application/json'
                filename = f"{report.file_name.rsplit('.', 1)[0]}_analysis.json"
            else:
                content = pipeline_result.get('text_report', 'No report generated.')
                content_type = 'text/markdown'
                filename = f"{report.file_name.rsplit('.', 1)[0]}_analysis.md"
            
            # Save analysis for future use
            report.structured_data = report.structured_data or {}
            report.structured_data['detailed_analysis'] = {
                'generated_at': timezone.now().isoformat(),
                'summary': pipeline_result.get('summary', {}),
                'findings_count': len(pipeline_result.get('findings', []))
            }
            report.save()
        
        response = HttpResponse(content, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
        
    except MedicalReport.DoesNotExist:
        return Response(
            {'error': 'Report not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.exception(
            "reports.analysis_download_failed",
            extra={
                "user_id": getattr(request.user, 'id', None),
                "report_id": report_id,
                "error_type": type(e).__name__,
            },
        )
        return Response(
            {'error': f'Error: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============= LOCAL MEDICAL PIPELINE ANALYSIS =============

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def analyze_report_local_pipeline(request):
    """
    Analyze a medical report combined with the user's full health history.

    The "Analyze report" button in MedicalDocumentDetail calls this endpoint.

    Flow:
      1. Load the MedicalReport by report_id.
      2. If status is pending/processing → return 202 (still processing).
      3. If report already has extracted_text → reuse it (skip re-OCR).
      4. If not → run 3-tier OCR (Apple Vision → Tesseract → NVIDIA).
      5. Assemble patient context: profile, past triage records, prior reports.
      6. Call generate_combined_report_insights() → Gemini with labeled sections.
      7. Persist updated extracted_text + insights back to report.
      8. Return in DetailedReportAnalysis shape.

    Request body: { "report_id": <int> }
    """
    import logging as _logging
    _logger = _logging.getLogger(__name__)

    from .report_insight_engine import build_report_insight_context, generate_combined_report_insights
    from .medical_report_analyzer import extract_text

    report_id = request.data.get('report_id')
    if not report_id:
        return Response(
            {'error': 'report_id is required.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        report = MedicalReport.objects.get(id=report_id, user=request.user)
    except MedicalReport.DoesNotExist:
        return Response({'error': 'Medical report not found.'}, status=status.HTTP_404_NOT_FOUND)

    # 'processing' means another request/worker is actively handling this exact
    # report right now — defer to it. 'pending' just means "not analyzed yet",
    # which is the normal starting state for every upload and is exactly what
    # this endpoint is about to do synchronously below (steps 1-3), so it must
    # NOT be treated as a blocking state — doing so left every fresh upload
    # permanently stuck, since nothing else ever moves status off 'pending'.
    if report.status == 'processing':
        return Response(
            {
                'success': False,
                'pending': True,
                'message': 'This report is still being processed. Please try again in a moment.',
            },
            status=status.HTTP_202_ACCEPTED,
        )

    # Quota gate for the report-insight LLM call (Gemini). Placed after the
    # report is loaded and the still-processing check, before OCR + insight
    # generation, so a rate-limited caller does no LLM work.
    try:
        check_llm_quota('report_insight', request.user.pk)
    except LLMQuotaExceeded as limit:
        return _rate_limited_response(limit, 'report analysis')

    # --- Step 1: Get OCR text (reuse cached or re-run) ---
    extracted_text = (report.extracted_text or '').strip()
    ocr_path = report.ocr_path or 'cached'

    if not extracted_text:
        # No cached text — run OCR now
        try:
            report.file.seek(0)
            file_bytes = report.file.read()
        except Exception as e:
            _logger.error("analyze_report_local.file_read_failed", extra={'report_id': report_id, 'error': str(e)})
            return Response(
                {'error': 'Could not read the report file. It may have been deleted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ocr_result = extract_text(
            file_bytes,
            report.file_type or 'application/pdf',
            file_name=report.file_name,
        )
        if ocr_result.get('success'):
            extracted_text = ocr_result.get('text', '')
            ocr_path = ocr_result.get('ocr_path', 'unknown')
        else:
            _logger.warning(
                "analyze_report_local.ocr_failed",
                extra={'report_id': report_id, 'error': ocr_result.get('error')},
            )
            # Proceed with empty text — generate_combined_report_insights handles this gracefully

    # --- Step 2: Build combined context (report + patient history) ---
    try:
        ctx = build_report_insight_context(request.user, report)
    except Exception:
        _logger.exception("analyze_report_local.context_build_failed", extra={'report_id': report_id})
        ctx = {
            'report_data': {
                'file_name': report.file_name or 'Report',
                'extracted_text': extracted_text,
                'tests': [],
                'abnormal_findings': [],
            },
            'user_context': {'age': 'Unknown', 'gender': 'Unknown', 'past_history': []},
        }

    # Merge freshly-extracted text into report_data (may be newer than cached)
    ctx['report_data']['extracted_text'] = extracted_text or ctx['report_data'].get('extracted_text', '')

    # --- Step 3: Generate combined insights ---
    insights = generate_combined_report_insights(
        report_data=ctx['report_data'],
        user_context=ctx['user_context'],
        request_id=f"analyze-{report_id}",
        user_id=request.user.pk,
    )

    # --- Step 4: Persist results back to report ---
    try:
        sd = report.structured_data or {}
        if insights.get('tests'):
            sd['tests'] = insights['tests']
        if insights.get('abnormal_findings'):
            sd['abnormal_findings'] = insights['abnormal_findings']
        sd['degraded'] = insights.get('degraded', False)

        update_fields = ['structured_data', 'updated_at']
        report.structured_data = sd

        if extracted_text and not report.extracted_text:
            report.extracted_text = extracted_text
            update_fields.append('extracted_text')
        if ocr_path and ocr_path != 'cached':
            report.ocr_path = ocr_path
            update_fields.append('ocr_path')

        narrative = insights.get('summary', '')
        what_it_means = insights.get('what_this_may_mean', '')
        if narrative or what_it_means:
            report.insights_text = f"{narrative}\n\n{what_it_means}".strip()
            update_fields.append('insights_text')

        if report.status != 'completed':
            report.status = 'completed'
            update_fields.append('status')

        report.save(update_fields=update_fields)
    except Exception:
        _logger.exception("analyze_report_local.persist_failed", extra={'report_id': report_id})
        # Non-fatal — still return the insights

    # --- Step 5: Format response in DetailedReportAnalysis shape ---
    tests = insights.get('tests', [])
    abnormal = insights.get('abnormal_findings', [])
    summary_text = insights.get('summary', '')
    what_it_means = insights.get('what_this_may_mean', '')
    consult_note = insights.get('consult_note', '')

    # Build the clinical_insights narrative
    parts = [summary_text]
    if what_it_means:
        parts.append(what_it_means)
    if consult_note:
        parts.append(consult_note)
    clinical_insights = '\n\n'.join(p for p in parts if p)

    if insights.get('degraded') and insights.get('raw_ocr_text'):
        clinical_insights = (
            clinical_insights
            + '\n\n---\n**Raw extracted text:**\n'
            + insights['raw_ocr_text'][:2000]
        )

    extraction_summary = {
        'total_tests': len(tests),
        'abnormal_count': len(abnormal),
        'total_reports': 1,
        'critical_findings': select_critical_findings(abnormal),
        'all_abnormals': abnormal,
    }

    # Critical values must reach a clinician, not just the patient's screen.
    escalate_critical_findings(
        user=request.user,
        report_id=report_id,
        file_name=report.file_name,
        critical_findings=extraction_summary['critical_findings'],
    )

    return Response(
        {
            'success': True,
            'report_id': report_id,
            'file_name': report.file_name,
            'generated_at': timezone.now().isoformat(),
            'extraction_summary': extraction_summary,
            'extracted_reports': tests,
            'clinical_insights': clinical_insights,
            'markdown_report': clinical_insights,
            'summary': summary_text,
            'degraded': insights.get('degraded', False),
            'ocr_path': ocr_path,
            # Doctor-voice consultation built only from arithmetically verified
            # findings, plus the verification tally behind it.
            'consultation': insights.get('consultation'),
            'verification': insights.get('verification'),
            'abnormal_findings': abnormal,
        },
        status=status.HTTP_200_OK,
    )




def _format_pipeline_response(pipeline_result: dict) -> Response:
    """
    Format pipeline result to match frontend expected format.
    
    Frontend expects:
    {
        "summary": string,
        "risk_assessment": string,
        "key_findings": string[],
        "recommendations": string[],
        "follow_up": string
    }
    """
    if not pipeline_result.get('success'):
        return Response({
            'summary': 'Analysis could not be completed.',
            'risk_assessment': 'Unable to assess',
            'key_findings': [pipeline_result.get('error', 'Unknown error occurred')],
            'recommendations': ['Please try uploading a clearer image or consult your doctor directly.'],
            'follow_up': 'Consult your healthcare provider for proper interpretation.'
        }, status=status.HTTP_200_OK)
    
    summary_data = pipeline_result.get('summary', {})
    findings = pipeline_result.get('findings', [])
    narrative_insights = (
        pipeline_result.get('clinical_insights')
        or pipeline_result.get('markdown_report')
        or pipeline_result.get('text_report')
        or ""
    )
    
    # Build summary text
    total = summary_data.get('total_tests', 0)
    abnormal = summary_data.get('abnormal', 0)
    normal = summary_data.get('normal', 0)
    critical = summary_data.get('critical_flags', 0)
    
    if total == 0 and narrative_insights.strip():
        first_line = narrative_insights.strip().splitlines()[0]
        summary_text = first_line[:300] if first_line else "Analysis completed with narrative insights."
    elif total == 0:
        summary_text = "Analysis completed, but no structured test table was detected."
    else:
        summary_text = f"Analysis complete. Found {total} test parameters: {abnormal} abnormal, {normal} normal."
        if critical > 0:
            summary_text += f" ⚠️ {critical} critical value(s) detected requiring immediate attention."
    
    # Build risk assessment
    if critical > 0:
        risk_assessment = "HIGH - Critical values detected. Immediate medical consultation recommended."
    elif abnormal > total * 0.5:
        risk_assessment = "MODERATE - Multiple abnormal values. Medical follow-up recommended."
    elif abnormal > 0:
        risk_assessment = "LOW - Some values outside normal range. Monitor and discuss with doctor if concerned."
    else:
        risk_assessment = "MINIMAL - All values within normal range."
    
    # Build key findings (abnormal values with explanations)
    key_findings = []
    for finding in findings:
        status_val = finding.get('status', 'UNKNOWN')
        if status_val not in ('NORMAL', 'UNKNOWN'):
            test_name = finding.get('test_name', finding.get('canonical_name', 'Unknown test'))
            value = finding.get('value', '')
            unit = finding.get('unit', '')
            icon = finding.get('status_icon', '')
            explanation = finding.get('explanation', {})
            simple_text = explanation.get('simplified') or explanation.get('simple', '')
            
            finding_text = f"{icon} {test_name}: {value} {unit} ({status_val})"
            if simple_text:
                finding_text += f" - {simple_text[:200]}"
            key_findings.append(finding_text)
    
    # If no abnormal findings, mention normal results
    if not key_findings:
        if total > 0:
            key_findings = ["✅ All analyzed parameters are within normal reference ranges."]
        elif narrative_insights.strip():
            key_findings = ["Detailed AI narrative insights were generated from the uploaded report."]
        else:
            key_findings = ["No structured test values were extracted from this report."]
    
    # Build recommendations
    recommendations = []
    seen_actions = set()
    for finding in findings:
        status_val = finding.get('status', 'UNKNOWN')
        if status_val not in ('NORMAL', 'UNKNOWN'):
            action = finding.get('explanation', {}).get('action', '')
            if action and action not in seen_actions:
                recommendations.append(action)
                seen_actions.add(action)
    
    # Add general recommendations
    if critical > 0:
        recommendations.insert(0, "⚠️ URGENT: Seek immediate medical attention for critical values.")
    
    if not recommendations:
        recommendations = ["Maintain a healthy lifestyle and schedule regular check-ups."]
    
    # Build follow-up text
    if critical > 0:
        follow_up = "Immediate medical consultation required. Contact your healthcare provider today."
    elif abnormal > 0:
        follow_up = "Schedule a follow-up appointment with your doctor to discuss these results and any lifestyle modifications."
    else:
        follow_up = "No immediate follow-up required. Continue regular health monitoring and annual check-ups."
    
    return Response({
        'summary': summary_text,
        'risk_assessment': risk_assessment,
        'key_findings': key_findings[:10],  # Limit to top 10 findings
        'recommendations': recommendations[:5],  # Limit to top 5 recommendations
        'follow_up': follow_up,
        'detailed_findings': findings,  # Include full findings for detailed view
        'text_report': pipeline_result.get('text_report', '')
    }, status=status.HTTP_200_OK)
