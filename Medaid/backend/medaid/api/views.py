from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import authenticate
from django.db import IntegrityError
from django.http import HttpResponse
from django.utils import timezone
import json

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
from .triage_engine import get_triage_engine, contains_emergency_keyword, get_emergency_services_by_pincode
from .report_processor import get_report_processor, summarize_medical_report_with_llm
from .facility_recommendations import get_nearby_facilities, get_dietary_recommendations
from .report_generator import generate_assessment_pdf, generate_health_passport_pdf


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    API health check endpoint - returns API status and available endpoints
    """
    return Response({
        'status': 'ok',
        'message': 'MedAid API is running',
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
            user = serializer.save()
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
    if serializer.is_valid():
        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)
        
        response_data = {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserSerializer(user).data
        }
        return Response(response_data, status=status.HTTP_200_OK)
    
    return Response(serializer.errors, status=status.HTTP_401_UNAUTHORIZED)


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
    Update user's past medical history with structured conditions
    Body: {
        "conditions": [
            {"name": "Diabetes", "selected": true, "notes": "Type 2"},
            {"name": "Hypertension", "selected": true},
            {"name": "Heart Disease", "selected": false}
        ]
    }
    """
    try:
        profile = request.user.profile
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)
    
    conditions = request.data.get('conditions', [])
    
    # Build structured past_history
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
    
    profile.past_history = past_history
    profile.save()
    
    return Response({
        'message': 'Medical history updated successfully',
        'past_history': past_history
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_current_user(request):
    """
    Get current authenticated user
    """
    serializer = UserSerializer(request.user)
    return Response(serializer.data, status=status.HTTP_200_OK)


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for User management
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Users can only see their own profile
        return User.objects.filter(id=self.request.user.id)

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

    def get_queryset(self):
        # Users can only see their own medical reports
        return MedicalReport.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Automatically set the user to the current authenticated user
        file = self.request.FILES.get('file')
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
        
        user = request.user
        symptoms_text = request.data.get('current_symptoms', '')
        input_mode = request.data.get('input_mode', 'text')
        report_id = request.data.get('medical_report_id')
        location = request.data.get('location', '')
        pincode = request.data.get('pincode', '')
        
        if not symptoms_text:
            return Response(
                {'error': 'Symptoms description is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # IMMEDIATE EMERGENCY CHECK
        if contains_emergency_keyword(symptoms_text):
            # Get emergency services if pincode provided
            emergency_services = None
            if pincode:
                emergency_services = get_emergency_services_by_pincode(pincode)
            
            # Create emergency triage record
            triage_record = TriageRecord.objects.create(
                user=user,
                current_symptoms=symptoms_text,
                input_mode=input_mode,
                risk_level='emergency',
                risk_probability=1.0,
                reasoning='Critical emergency keywords detected in symptoms. Immediate medical attention required.',
                confidence=1.0,
                assessment_source='emergency_rule',
                medical_report_id=report_id if report_id else None
            )
            
            # Save condition
            PossibleCondition.objects.create(
                triage_record=triage_record,
                disease_name='Emergency Medical Condition',
                confidence=1.0
            )
            
            # Save emergency recommendations
            emergency_recs = [
                '🚨 CALL EMERGENCY SERVICES IMMEDIATELY (108/112)',
                'Do NOT drive yourself - call ambulance',
                'Stay calm and await professional help',
                'If available, have someone stay with you',
                'Go to nearest Emergency Room immediately'
            ]
            
            # Add location-specific recommendations if available
            if emergency_services and 'city_info' in emergency_services:
                city_info = emergency_services['city_info']
                if 'hospitals' in city_info:
                    emergency_recs.append(f"📍 Nearest hospitals in {city_info['city']} available - check response")
            
            for idx, rec in enumerate(emergency_recs):
                Recommendation.objects.create(
                    triage_record=triage_record,
                    recommendation_type='emergency',
                    description=rec,
                    priority=idx + 1
                )
            
            response_data = {
                'triage_id': triage_record.id,
                'risk_level': 'emergency',
                'reasoning': 'Critical emergency keywords detected in symptoms. Immediate medical attention required.',
                'confidence': 1.0,
                'possible_conditions': ['Emergency Medical Condition'],
                'recommendations': emergency_recs,
                'immediate_actions': [
                    'Call 108 or 112 now',
                    'Alert family members',
                    'Prepare for hospital visit'
                ],
                'when_to_seek_care': 'IMMEDIATELY - This is a medical emergency',
                'triage_level': 'emergency',
                'created_at': triage_record.created_at
            }
            
            # Add emergency services info if available
            if emergency_services:
                response_data['emergency_services'] = emergency_services
            
            return Response(response_data, status=status.HTTP_201_CREATED)
        
        # Continue with normal triage for non-emergency cases
        
        # Get user profile data
        profile = UserProfile.objects.filter(user=user).first()
        age = None
        gender = 'unknown'
        past_history = []
        
        if profile:
            if profile.date_of_birth:
                from datetime import date
                today = date.today()
                age = today.year - profile.date_of_birth.year - (
                    (today.month, today.day) < (profile.date_of_birth.month, profile.date_of_birth.day)
                )
            gender = profile.gender or 'unknown'
            past_history = profile.past_history.get('conditions', []) if profile.past_history else []
        
        # Prepare user data for triage
        user_data = {
            'age': age or 'Adult',
            'gender': gender,
            'past_history': past_history
        }
        
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
                print(f"Error getting report summary: {e}")
        
        # Build location string
        location_str = ""
        if location and pincode:
            location_str = f"{location}, Pincode: {pincode}"
        elif location:
            location_str = location
        elif pincode:
            location_str = f"Pincode: {pincode}"
        
        # Run triage assessment with all context
        triage_engine = get_triage_engine()
        assessment = triage_engine.assess(symptoms_text, user_data, report_summary, location_str)
        
        # Save triage record
        triage_record = TriageRecord.objects.create(
            user=user,
            current_symptoms=symptoms_text,
            input_mode=input_mode,
            risk_level=assessment['risk_level'],
            risk_probability=assessment.get('confidence', 0.0),
            reasoning=assessment['reasoning'],
            confidence=assessment.get('confidence', 0.0),
            assessment_source=assessment.get('source', 'ai'),
            medical_report_id=report_id if report_id else None
        )
        
        # Save possible conditions
        for condition in assessment.get('possible_conditions', []):
            PossibleCondition.objects.create(
                triage_record=triage_record,
                disease_name=condition,
                confidence=assessment.get('confidence', 0.0)
            )
        
        # Save recommendations
        for idx, rec in enumerate(assessment.get('recommendations', [])):
            Recommendation.objects.create(
                triage_record=triage_record,
                recommendation_type='action',
                description=rec,
                priority=idx + 1
            )
        
        return Response({
            'triage_id': triage_record.id,
            'risk_level': assessment['risk_level'],
            'reasoning': assessment['reasoning'],
            'confidence': assessment.get('confidence', 0.0),
            'possible_conditions': assessment.get('possible_conditions', []),
            'recommendations': assessment.get('recommendations', []),
            'created_at': triage_record.created_at
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        print(f"Error in triage assessment: {e}")
        import traceback
        traceback.print_exc()
        return Response(
            {'error': f'Error processing assessment: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_triage_history(request):
    """Get user's triage history"""
    try:
        records = TriageRecord.objects.filter(user=request.user).order_by('-created_at')
        
        history = []
        for record in records:
            conditions = PossibleCondition.objects.filter(triage_record=record)
            recommendations = Recommendation.objects.filter(triage_record=record)
            
            history.append({
                'id': record.id,
                'date': record.created_at,
                'symptoms': record.current_symptoms,
                'risk_level': record.risk_level,
                'reasoning': record.reasoning,
                'confidence': record.confidence,
                'possible_conditions': [c.disease_name for c in conditions],
                'recommendations': [r.description for r in recommendations]
            })
        
        return Response({'history': history}, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': f'Error retrieving history: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def analyze_medical_report(request):
    """
    Analyze uploaded medical report (PDF/Image)
    
    Expects multipart/form-data with 'file' field
    """
    try:
        if 'file' not in request.FILES:
            return Response(
                {'error': 'No file uploaded'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        uploaded_file = request.FILES['file']
        file_type = uploaded_file.content_type
        
        # Determine file type
        if 'pdf' in file_type:
            file_type_str = 'pdf'
        elif 'image' in file_type:
            file_type_str = 'image'
        else:
            return Response(
                {'error': 'Unsupported file type. Please upload PDF or image'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get user gender for context
        profile = UserProfile.objects.filter(user=request.user).first()
        gender = profile.gender if profile else 'unknown'
        age = None
        if profile and profile.date_of_birth:
            from datetime import date
            today = date.today()
            age = today.year - profile.date_of_birth.year
        
        # Read file bytes
        file_bytes = uploaded_file.read()
        
        # Process report
        processor = get_report_processor()
        result = processor.process_report(file_bytes, file_type_str, gender, age)
        
        if not result.get('success'):
            return Response(
                {'error': result.get('error', 'Failed to process report')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get LLM summary of the medical report
        extracted_text = result.get('extracted_text', '')
        llm_summary = None
        if extracted_text:
            llm_summary = summarize_medical_report_with_llm(extracted_text)
        
        # Save medical report with LLM summary
        uploaded_file.seek(0)  # Reset file pointer
        structured_data = result.get('structured_data', {})
        
        # Add LLM summary to structured data if available
        if llm_summary and llm_summary.get('success'):
            structured_data['llm_summary'] = llm_summary.get('summary', '')
            structured_data['llm_key_findings'] = llm_summary.get('key_findings', [])
            structured_data['llm_abnormalities'] = llm_summary.get('abnormalities', [])
            structured_data['llm_risk_indicators'] = llm_summary.get('risk_indicators', [])
            structured_data['llm_suggested_focus'] = llm_summary.get('suggested_focus', '')
        
        medical_report = MedicalReport.objects.create(
            user=request.user,
            file=uploaded_file,
            file_name=uploaded_file.name,
            file_type=file_type,
            file_size=uploaded_file.size,
            extracted_text=extracted_text,
            structured_data=structured_data
        )
        
        # Save medical tests and abnormal results
        for param, value in result.get('structured_data', {}).items():
            interpretation = result.get('interpretations', {}).get(param, {})
            
            test = MedicalTest.objects.create(
                medical_report=medical_report,
                test_name=param.replace('_', ' ').title(),
                test_value=value,
                test_unit=interpretation.get('unit', ''),
                reference_range=f"{interpretation.get('normal_range', ['', ''])[0]} - {interpretation.get('normal_range', ['', ''])[1]}",
                is_abnormal=interpretation.get('status') != 'Normal'
            )
            
            # Create abnormal result if needed
            if interpretation.get('status') != 'Normal':
                AbnormalResult.objects.create(
                    medical_test=test,
                    status=interpretation.get('status', 'Unknown'),
                    concern_level=interpretation.get('concern_level', 'Low'),
                    interpretation=interpretation.get('interpretation', '')
                )
        
        # Prepare response with LLM summary if available
        response_data = {
            'report_id': medical_report.id,
            'success': True,
            'extracted_text': result.get('extracted_text', '')[:500],  # Truncate for response
            'structured_data': structured_data,
            'interpretations': result.get('interpretations', {}),
            'abnormal_results': result.get('abnormal_results', []),
            'summary': result.get('summary', '')
        }
        
        # Add LLM summary to response if successful
        if llm_summary and llm_summary.get('success'):
            response_data['llm_summary'] = {
                'clinical_summary': llm_summary.get('summary', ''),
                'key_findings': llm_summary.get('key_findings', []),
                'abnormalities': llm_summary.get('abnormalities', []),
                'risk_indicators': llm_summary.get('risk_indicators', []),
                'suggested_focus': llm_summary.get('suggested_focus', ''),
                'patient_category': llm_summary.get('patient_category', 'adult')
            }
        
        return Response(response_data, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        print(f"Error analyzing report: {e}")
        import traceback
        traceback.print_exc()
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
        
        # Get triage records
        triage_records = TriageRecord.objects.filter(user=user).order_by('-created_at')[:10]
        triage_history = []
        for record in triage_records:
            conditions = PossibleCondition.objects.filter(triage_record=record)
            triage_history.append({
                'date': record.created_at,
                'symptoms': record.current_symptoms,
                'risk_level': record.risk_level,
                'conditions': [c.disease_name for c in conditions]
            })
        
        # Get medical reports
        reports = MedicalReport.objects.filter(user=user).order_by('-upload_date')[:10]
        reports_data = []
        for report in reports:
            tests = MedicalTest.objects.filter(medical_report=report)
            abnormal = AbnormalResult.objects.filter(medical_test__medical_report=report)
            
            reports_data.append({
                'id': report.id,
                'date': report.upload_date,
                'file_name': report.file_name,
                'tests_count': tests.count(),
                'abnormal_count': abnormal.count()
            })
        
        # Past history
        past_history = profile.past_history if profile else {}
        
        return Response({
            'profile': {
                'name': f"{user.first_name} {user.last_name}",
                'email': user.email,
                'age': None,  # Calculate from DOB if available
                'gender': profile.gender if profile else None,
                'past_history': past_history
            },
            'triage_history': triage_history,
            'medical_reports': reports_data,
            'total_consultations': triage_records.count()
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': f'Error retrieving health passport: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_nearby_facilities_view(request):
    """
    Get nearby medical facilities based on location and risk level
    Query params:
        - location: City name, pincode, or "lat,lng"
        - risk_level: emergency/high/medium/low (optional)
        - radius: Search radius in km (optional, default 10)
    """
    location = request.GET.get('location')
    if not location:
        return Response(
            {'error': 'Location parameter is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    risk_level = request.GET.get('risk_level', 'medium')
    try:
        radius = float(request.GET.get('radius', 10))
    except ValueError:
        radius = 10
    
    try:
        facilities = get_nearby_facilities(location, risk_level, radius)
        return Response({
            'location': location,
            'risk_level': risk_level,
            'radius_km': radius,
            'facilities': facilities,
            'count': len(facilities)
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': f'Error fetching facilities: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_dietary_recommendations_view(request):
    """
    Get dietary recommendations based on risk level and conditions
    Body: {
        "risk_level": "high",
        "possible_conditions": ["diabetes", "hypertension"]
    }
    """
    risk_level = request.data.get('risk_level', 'medium')
    possible_conditions = request.data.get('possible_conditions', [])
    
    try:
        recommendations = get_dietary_recommendations(risk_level, possible_conditions)
        return Response({
            'risk_level': risk_level,
            'conditions': possible_conditions,
            'dietary_recommendations': recommendations
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': f'Error generating recommendations: {str(e)}'},
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
        
        # Create new session
        session = ConsultationSession.objects.create(
            user=request.user,
            stage='symptoms',
            symptoms=request.data.get('symptoms', ''),
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
            session.symptoms = request.data.get('symptoms', session.symptoms)
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
            triage_engine = get_triage_engine()
            
            user_data = {
                'age': getattr(request.user.profile, 'date_of_birth', None),
                'gender': getattr(request.user.profile, 'gender', 'unknown'),
                'past_history': session.medical_history
            }
            
            assessment = triage_engine.assess_with_clarifications(
                symptoms_text=session.symptoms,
                user_data=user_data,
                clarifications=session.clarifying_questions
            )
            
            # Create triage record
            triage_record = TriageRecord.objects.create(
                user=request.user,
                current_symptoms=session.symptoms,
                input_mode='consultation',
                risk_level=assessment['risk_level'],
                risk_probability=assessment['confidence'],
                reasoning=assessment['reasoning'],
                confidence=assessment['confidence'],
                assessment_source='ai'
            )
            
            # Add possible conditions
            for condition_name in assessment.get('possible_conditions', []):
                PossibleCondition.objects.create(
                    triage_record=triage_record,
                    disease_name=condition_name,
                    confidence=assessment['confidence']
                )
            
            # Add recommendations
            for idx, rec in enumerate(assessment.get('recommendations', []), 1):
                Recommendation.objects.create(
                    triage_record=triage_record,
                    recommendation_type='action',
                    description=rec,
                    priority=idx
                )
            
            # Link triage record to session
            session.triage_record = triage_record
            session.stage = 'completed'
            session.is_active = False
            from django.utils import timezone
            session.completed_at = timezone.now()
        
        session.save()
        
        serializer = ConsultationSessionSerializer(session)
        return Response({
            'message': f'Stage {stage} completed',
            'session': serializer.data
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        print(f"Error submitting consultation step: {e}")
        import traceback
        traceback.print_exc()
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
        
        # Generate questions using triage engine
        triage_engine = get_triage_engine()
        
        user_data = {
            'age': getattr(request.user.profile, 'date_of_birth', None),
            'gender': getattr(request.user.profile, 'gender', 'unknown'),
            'past_history': session.medical_history
        }
        
        questions = triage_engine.generate_clarifying_questions(
            symptoms_text=session.symptoms,
            user_data=user_data
        )
        
        return Response({
            'session_id': session_id,
            'questions': questions
        }, status=status.HTTP_200_OK)
    
    except Exception as e:
        print(f"Error generating clarifying questions: {e}")
        import traceback
        traceback.print_exc()
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
        print(f"Error generating PDF: {e}")
        import traceback
        traceback.print_exc()
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
        medical_reports = MedicalReport.objects.filter(user=user).order_by('-uploaded_at')
        
        # Generate PDF
        pdf_content = generate_health_passport_pdf(user, user_profile, triage_records, medical_reports)
        
        # Create response
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="medaid_health_passport_{user.id}.pdf"'
        
        return response
        
    except Exception as e:
        print(f"Error generating health passport PDF: {e}")
        import traceback
        traceback.print_exc()
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
        
        serializer = PatientAssignmentSerializer(assignments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
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
        alerts = ClinicianAlert.objects.filter(clinician=user)
        
        # Filter by read status
        is_read = request.query_params.get('is_read', None)
        if is_read is not None:
            is_read_bool = is_read.lower() == 'true'
            alerts = alerts.filter(is_read=is_read_bool)
        
        alerts = alerts.order_by('-created_at')
        
        serializer = ClinicianAlertSerializer(alerts, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
        
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
