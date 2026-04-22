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

EMERGENCY_KEYWORDS = [
    "not breathing", "unconscious", "severe chest pain", "heavy bleeding",
    "sudden weakness", "slurred speech", "seizure", "severe burn",
    "blue lips", "very drowsy", "faint", "loss of consciousness",
    "can't breathe", "cannot breathe", "chest pain", "difficulty breathing",
    "severe bleeding", "uncontrolled bleeding", "passed out", "behosh"
]


def contains_emergency_keyword(text):
    """Return True if text contains any emergency keyword."""
    if not text:
        return False
    lowered = text.lower()
    for keyword in EMERGENCY_KEYWORDS:
        if keyword in lowered:
            return True
    return False


def get_emergency_services_by_pincode(pincode):
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
from .triage_engine import get_triage_engine
from .hospital_finder import get_hospital_finder
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
        
        # Run V2 triage assessment with all context
        triage_engine_v2 = get_triage_engine_v2()
        assessment = triage_engine_v2.assess(symptoms_text, user_data, report_summary, location_str)
        
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
                print(f"Error finding nearby hospitals: {e}")
        
        # Save triage record
        triage_record = TriageRecord.objects.create(
            user=user,
            current_symptoms=symptoms_text,
            input_mode=input_mode,
            risk_level=assessment['risk_level'],
            risk_probability=assessment.get('risk_probability', 0.0),
            reasoning=assessment['reasoning'],
            confidence=assessment.get('confidence', 0.0),
            assessment_source='ai_v2',
            medical_report_id=report_id if report_id else None
        )
        
        # Save possible conditions with confidence scores
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
        
        # Save recommendations
        for idx, rec in enumerate(assessment.get('recommendations', [])):
            Recommendation.objects.create(
                triage_record=triage_record,
                recommendation_type='action',
                description=rec,
                priority=idx + 1
            )
        
        # Build comprehensive response
        response_data = {
            'triage_id': triage_record.id,
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
            'created_at': triage_record.created_at
        }
        
        return Response(response_data, status=status.HTTP_201_CREATED)
        
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
        result = processor.extract_and_analyze(file_bytes, file_name=uploaded_file.name)
        
        if not result.get('success'):
            return Response(
                {'error': result.get('error', 'Failed to process report')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get LLM summary using local T5 model (no external API)
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
        medical_reports = MedicalReport.objects.filter(user=user).order_by('-upload_date')
        
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
    Get dietary recommendations
    """
    risk_level = request.data.get('risk_level', 'medium')
    possible_conditions = request.data.get('possible_conditions', [])
    
    from .facility_recommendations import get_dietary_recommendations
    
    recs = get_dietary_recommendations(risk_level, possible_conditions)
    return Response({'recommendations': recs}, status=status.HTTP_200_OK)


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
    uploaded_file = request.FILES.get('file')

    if not user_message_content and not uploaded_file:
        return Response(
            {'error': 'Message content or file is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        chat_service = get_chat_service()
        
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
            tokens_used=tokens_est
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
                    'type': 'file_upload', 
                    'report_id': report.id,
                    'file_url': report.file.url if report.file else ''
                }
                user_message.save()

        # If this is the first user message, generate a title
        if conversation.messages.filter(role='user').count() == 1:
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
        try:
            profile = request.user.profile
            user_data = {
                'age': profile.date_of_birth,
                'gender': profile.gender,
                'past_history': profile.past_history.get('conditions', []) if profile.past_history else []
            }
        except:
            user_data = None
        
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

        if file_analysis_text and analysis_result and analysis_result.get('success'):
            ai_response = {
                'content': analysis_result.get('markdown_report'),
                'tokens_used': 0
            }
        else:
            ai_response = chat_service.generate_ai_response(
                full_content_for_ai,
                context_for_ai,
                user_data
            )
        
        # 5. Save Assistant Message
        assistant_message = ChatMessage.objects.create(
            conversation=conversation,
            role='assistant',
            content=ai_response['content'],
            tokens_used=ai_response['tokens_used']
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
                'id': conversation.id,
                'title': conversation.title,
                'total_tokens_used': conversation.total_tokens_used
            },
            'suggest_new_chat': suggest_new_chat
        }, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        print(f"Error sending message: {e}")
        import traceback
        traceback.print_exc()
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
    
    messages = conversation.messages.all().order_by('created_at')
    serializer = ChatMessageSerializer(messages, many=True)
    
    return Response({
        'messages': serializer.data,
        'conversation': {
            'id': conversation.id,
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
                    return _format_detailed_pipeline_response(pipeline_result, report_id, report.file_name)
            
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
            
            return _format_detailed_pipeline_response(pipeline_result, report_id, report.file_name)
            
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
            
            return _format_detailed_pipeline_response(pipeline_result, None, uploaded_file.name)
        else:
            return Response(
                {'error': 'Either report_id or file must be provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
    except Exception as e:
        print(f"Error in detailed report analysis: {e}")
        import traceback
        traceback.print_exc()
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


def _format_detailed_pipeline_response(pipeline_result: dict, report_id, file_name: str) -> Response:
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
        if 'CRITICAL' in st:
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
        print(f"Error downloading analysis: {e}")
        import traceback
        traceback.print_exc()
        return Response(
            {'error': f'Error: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============= LOCAL MEDICAL PIPELINE ANALYSIS =============

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def analyze_report_local_pipeline(request):
    """
    Analyze medical report using local ML pipeline (LayoutLMv3 + OCR + Knowledge Base + T5).
    
    This endpoint uses a fully local pipeline without external API calls:
    1. Preprocessing - resize, denoise, deskew, normalize
    2. OCR/Extraction - LayoutLMv3 or pytesseract
    3. Normalization - alias resolution, unit normalization
    4. Rule Engine - compare against reference ranges
    5. Knowledge Base - retrieve structured explanations
    6. Simplification - T5-small for patient-friendly language
    7. Report Assembly - structured JSON output
    
    Request body (JSON):
    {
        "report_id": 123,
        "extracted_text": "...",  // optional pre-extracted text
        "structured_data": {...}  // optional pre-extracted structured data
    }
    
    Returns:
        {
            "summary": "Overall analysis summary",
            "risk_assessment": "Risk level assessment",
            "key_findings": ["finding1", "finding2", ...],
            "recommendations": ["rec1", "rec2", ...],
            "follow_up": "Follow-up recommendations",
            "detailed_findings": [...],  // Full findings list
            "text_report": "..."  // Full text report
        }
    """
    try:
        from .medical_pipeline import analyze_medical_report_local, analyze_extracted_values
        
        report_id = request.data.get('report_id')
        extracted_text = request.data.get('extracted_text', '')
        structured_data = request.data.get('structured_data', {})
        
        # Get user gender for reference ranges
        user = request.user
        gender = getattr(user, 'gender', 'male') or 'male'
        gender = gender.lower() if gender else 'male'
        
        # If we have pre-extracted structured data with test values, use that
        if structured_data and isinstance(structured_data, dict):
            # Check if structured_data has test results we can analyze
            test_values = {}
            units = {}
            
            # Try to extract test values from various possible formats
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
            
            # Also check for abnormal_results format
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
            
            # If we found test values, analyze them directly
            if test_values:
                pipeline_result = analyze_extracted_values(test_values, units=units, gender=gender)
                return _format_pipeline_response(pipeline_result)
        
        # Otherwise, if we have a report_id, load and analyze the file
        if report_id:
            try:
                report = MedicalReport.objects.get(id=report_id, user=request.user)
            except MedicalReport.DoesNotExist:
                return Response(
                    {'error': 'Medical report not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Read file bytes
            report.file.seek(0)
            file_bytes = report.file.read()
            
            # Determine file type
            file_type = 'pdf' if 'pdf' in report.file_type.lower() else 'image'
            
            # Run the local pipeline
            pipeline_result = analyze_medical_report_local(
                file_bytes=file_bytes,
                file_type=file_type,
                gender=gender,
                mode='ocr'  # Use OCR mode for faster processing
            )
            
            # Save analysis to report
            if pipeline_result.get('success'):
                report.structured_data = report.structured_data or {}
                report.structured_data['pipeline_analysis'] = {
                    'summary': pipeline_result.get('summary', {}),
                    'findings_count': len(pipeline_result.get('findings', [])),
                    'analyzed_at': timezone.now().isoformat()
                }
                report.save()
            
            return _format_pipeline_response(pipeline_result)
        
        # If neither structured_data nor report_id, return error
        return Response(
            {'error': 'Either report_id or structured_data with test values must be provided'},
            status=status.HTTP_400_BAD_REQUEST
        )
        
    except Exception as e:
        print(f"Error in local pipeline analysis: {e}")
        import traceback
        traceback.print_exc()
        return Response(
            {'error': f'Error analyzing report: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
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
