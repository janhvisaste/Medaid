from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import FileExtensionValidator
from django.db import transaction
from django.urls import reverse
from .models import (
    User, UserProfile, MedicalReport, ConsultationSession,
    PatientAssignment, ClinicianNote, ClinicianAlert, TriageRecord,
    ChatConversation, ChatMessage
)
from .llm_providers.catalog import is_allowed_openrouter_model


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'phone_number', 'role', 'profile_picture', 'specialization', 'bio', 'is_verified', 'created_at']
        read_only_fields = ['id', 'created_at', 'is_verified']


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for UserProfile model"""
    user = UserSerializer(read_only=True)
    other_notes = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        max_length=2000,
        error_messages={'max_length': 'Notes must be 2000 characters or fewer. Please shorten your text.'},
    )

    class Meta:
        model = UserProfile
        fields = [
            'id', 'user', 'date_of_birth', 'gender', 'city', 'state', 'pincode',
            'institution', 'license_number', 'license_expiry',
            'preferred_model', 'past_history', 'other_notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_preferred_model(self, value):
        if value in ("", None):
            return None
        if not is_allowed_openrouter_model(value):
            raise serializers.ValidationError("Selected model is not available.")
        return value

    def validate_other_notes(self, value):
        """Normalize empty string to None so DB stays clean."""
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return value.strip()


class SignupSerializer(serializers.ModelSerializer):
    """Serializer for user signup"""
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)
    phone_number = serializers.CharField(required=False, allow_blank=True, max_length=20)

    class Meta:
        model = User
        fields = ['email', 'password', 'confirm_password', 'first_name', 'last_name', 'phone_number']

    def validate(self, data):
        data['email'] = data['email'].strip().lower()
        if data['password'] != data.pop('confirm_password'):
            raise serializers.ValidationError({'password': 'Passwords do not match.'})
        try:
            validate_password(data['password'])
        except DjangoValidationError as error:
            raise serializers.ValidationError({'password': list(error.messages)})
        return data

    def create(self, validated_data):
        with transaction.atomic():
            user = User.objects.create_user(
                username=validated_data['email'],
                email=validated_data['email'],
                password=validated_data['password'],
                first_name=validated_data.get('first_name', ''),
                last_name=validated_data.get('last_name', ''),
                phone_number=validated_data.get('phone_number', ''),
            )
            UserProfile.objects.create(user=user)
            return user


class LoginSerializer(serializers.Serializer):
    """Serializer for user login"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, data):
        email = data.get('email')
        password = data.get('password')

        if email and password:
            # Primary: use Django's authenticate (respects USERNAME_FIELD).
            user = authenticate(username=email, password=password)
            # Fallback: some deployments or backends may not map username=>email
            # as expected. Try a case-insensitive email lookup and manual
            # password check to be robust to backing-store differences.
            if not user:
                try:
                    candidate = User.objects.filter(email__iexact=email).first()
                    if candidate and candidate.check_password(password):
                        user = candidate
                except Exception:
                    # Fall through to error below
                    user = None

            if not user:
                # Well-formed request but the credentials don't match an
                # account. Per REST convention this is 401 Unauthorized, not a
                # 400 Bad Request. AuthenticationFailed maps to HTTP 401.
                msg = 'Unable to log in with provided credentials.'
                raise AuthenticationFailed(msg, code='authorization')
        else:
            msg = 'Must include "email" and "password".'
            raise serializers.ValidationError(msg, code='authorization')

        data['user'] = user
        return data


class AuthResponseSerializer(serializers.Serializer):
    """Serializer for auth response with tokens"""
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSerializer()


class LogoutSerializer(serializers.Serializer):
    """Serializer for logout"""
    refresh = serializers.CharField()

    def validate_refresh(self, value):
        try:
            RefreshToken(value)
        except Exception:
            raise serializers.ValidationError("Invalid token")
        return value


class MedicalReportSerializer(serializers.ModelSerializer):
    """Serializer for Medical Reports"""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_first_name = serializers.CharField(source='user.first_name', read_only=True)
    user_last_name = serializers.CharField(source='user.last_name', read_only=True)
    file_url = serializers.SerializerMethodField()
    file = serializers.FileField(
        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'png', 'jpg', 'jpeg'])]
    )

    class Meta:
        model = MedicalReport
        fields = ['id', 'user', 'user_email', 'user_first_name', 'user_last_name', 'file', 'file_url', 'file_name', 'file_type', 'file_size', 'description', 'status', 'extracted_text', 'structured_data', 'insights_text', 'ocr_path', 'upload_date', 'updated_at']
        read_only_fields = ['id', 'user', 'upload_date', 'updated_at', 'file_name', 'file_type', 'file_size', 'status', 'insights_text', 'ocr_path']

    def get_file_url(self, obj):
        # Always route through the as_attachment=True download action rather
        # than exposing the raw MEDIA URL, so an uploaded file (e.g. a
        # crafted .svg/.html-like upload) is never served inline where a
        # browser could execute it.
        if not obj.file:
            return None
        request = self.context.get('request')
        path = reverse('medical-report-download', kwargs={'pk': obj.pk})
        return request.build_absolute_uri(path) if request else path


class ConsultationSessionSerializer(serializers.ModelSerializer):
    """Serializer for ConsultationSession model"""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    triage_id = serializers.IntegerField(source='triage_record.id', read_only=True, allow_null=True)
    
    class Meta:
        model = ConsultationSession
        fields = [
            'id', 'user', 'user_email', 'stage', 'symptoms', 
            'medical_history', 'clarifying_questions', 'triage_id',
            'is_active', 'created_at', 'updated_at', 'completed_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at', 'completed_at']


class TriageRecordSerializer(serializers.ModelSerializer):
    """Serializer for TriageRecord model"""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    patient_name = serializers.SerializerMethodField()
    possible_conditions = serializers.SerializerMethodField()
    recommendations = serializers.SerializerMethodField()

    class Meta:
        model = TriageRecord
        fields = [
            'id', 'user', 'user_email', 'patient_name', 'current_symptoms',
            'risk_level', 'risk_probability', 'reasoning', 'confidence',
            'possible_conditions', 'recommendations', 'requires_human_review',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']

    def get_patient_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.email

    def get_possible_conditions(self, obj):
        # Return list of strings: "Disease Name (XX%)"
        conditions = obj.possible_conditions.all()
        return [f"{c.disease_name} {int(c.confidence*100)}%" if c.confidence else c.disease_name for c in conditions]

    def get_recommendations(self, obj):
        return [r.description for r in obj.recommendations.filter(recommendation_type='action').order_by('priority')]


class PatientAssignmentSerializer(serializers.ModelSerializer):
    """Serializer for PatientAssignment model"""
    patient_email = serializers.EmailField(source='patient.email', read_only=True)
    patient_name = serializers.SerializerMethodField()
    clinician_email = serializers.EmailField(source='clinician.email', read_only=True)
    clinician_name = serializers.SerializerMethodField()
    triage_details = TriageRecordSerializer(source='triage_record', read_only=True)
    
    class Meta:
        model = PatientAssignment
        fields = [
            'id', 'patient', 'patient_email', 'patient_name',
            'clinician', 'clinician_email', 'clinician_name',
            'triage_record', 'triage_details', 'status', 'priority',
            'notes', 'assigned_at', 'updated_at', 'resolved_at'
        ]
        read_only_fields = ['id', 'assigned_at', 'updated_at']
    
    def get_patient_name(self, obj):
        return f"{obj.patient.first_name} {obj.patient.last_name}".strip() or obj.patient.email
    
    def get_clinician_name(self, obj):
        return f"{obj.clinician.first_name} {obj.clinician.last_name}".strip() or obj.clinician.email


class ClinicianNoteSerializer(serializers.ModelSerializer):
    """Serializer for ClinicianNote model"""
    clinician_email = serializers.EmailField(source='clinician.email', read_only=True)
    clinician_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ClinicianNote
        fields = [
            'id', 'assignment', 'clinician', 'clinician_email', 'clinician_name',
            'note', 'is_private', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'clinician', 'created_at', 'updated_at']
    
    def get_clinician_name(self, obj):
        return f"{obj.clinician.first_name} {obj.clinician.last_name}".strip() or obj.clinician.email


# Severity implied by an alert_type, used only when an alert has no linked
# assignment to read a real triage risk_level from.
ALERT_TYPE_RISK_FALLBACK = {
    'new_emergency': 'emergency',
    'high_risk': 'high',
    'deteriorating': 'high',
    'follow_up': 'medium',
}


class ClinicianAlertSerializer(serializers.ModelSerializer):
    """Serializer for ClinicianAlert model"""
    patient_email = serializers.EmailField(source='patient.email', read_only=True)
    patient_name = serializers.SerializerMethodField()
    risk_level = serializers.SerializerMethodField()

    class Meta:
        model = ClinicianAlert
        fields = [
            'id', 'clinician', 'patient', 'patient_email', 'patient_name',
            'assignment', 'alert_type', 'risk_level', 'message', 'is_read',
            'is_actioned', 'created_at', 'read_at', 'actioned_at'
        ]
        read_only_fields = ['id', 'clinician', 'patient', 'created_at']

    def get_patient_name(self, obj):
        return f"{obj.patient.first_name} {obj.patient.last_name}".strip() or obj.patient.email

    def get_risk_level(self, obj):
        """Clinical risk tier behind this alert.

        The alert queue is triaged by patient risk, not by alert category, so
        prefer the risk_level of the TriageRecord that raised the alert.
        `assignment` is nullable, so fall back to the severity implied by
        alert_type rather than returning nothing.
        """
        assignment = obj.assignment
        if assignment is not None and assignment.triage_record is not None:
            return assignment.triage_record.risk_level
        # An alert_type missing from the map is a coding gap, not a low-risk
        # patient. Floor it to 'high' so a type added to ALERT_TYPES without
        # updating this map surfaces at the TOP of the clinician queue rather
        # than silently sinking to the bottom as 'neutral'.
        return ALERT_TYPE_RISK_FALLBACK.get(obj.alert_type, 'high')


class ClinicianStatsSerializer(serializers.Serializer):
    """Serializer for clinician dashboard statistics"""
    total_patients = serializers.IntegerField()
    active_patients = serializers.IntegerField()
    emergency_patients = serializers.IntegerField()
    high_risk_patients = serializers.IntegerField()
    todays_assessments = serializers.IntegerField()
    pending_alerts = serializers.IntegerField()


class ChatMessageSerializer(serializers.ModelSerializer):
    """Serializer for ChatMessage model"""
    
    class Meta:
        model = ChatMessage
        fields = ['id', 'conversation', 'role', 'content', 'metadata', 'tokens_used', 'created_at']
        read_only_fields = ['id', 'created_at']


class ChatConversationSerializer(serializers.ModelSerializer):
    """Serializer for ChatConversation model"""
    messages = ChatMessageSerializer(many=True, read_only=True)
    message_count = serializers.SerializerMethodField()
    preview_message = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatConversation
        fields = [
            'id', 'user', 'title', 'is_active', 'total_tokens_used',
            'last_activity', 'created_at', 'updated_at',
            'messages', 'message_count', 'preview_message'
        ]
        read_only_fields = ['id', 'user', 'last_activity', 'created_at', 'updated_at']
    
    def get_message_count(self, obj):
        return obj.messages.count()
    
    def get_preview_message(self, obj):
        """Get a preview of the last message"""
        last_message = obj.messages.order_by('-created_at').first()
        if last_message:
            preview = last_message.content[:60]
            return f"{preview}..." if len(last_message.content) > 60 else preview
        return "No messages yet"


class ChatConversationListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing conversations (without full messages)"""
    message_count = serializers.SerializerMethodField()
    preview_message = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatConversation
        fields = [
            'id', 'title', 'is_active', 'total_tokens_used',
            'last_activity', 'created_at', 'message_count', 'preview_message'
        ]
        read_only_fields = ['id', 'last_activity', 'created_at']
    
    def get_message_count(self, obj):
        return obj.messages.count()
    
    def get_preview_message(self, obj):
        """Get a preview of the last message"""
        last_message = obj.messages.order_by('-created_at').first()
        if last_message:
            preview = last_message.content[:60]
            return f"{preview}..." if len(last_message.content) > 60 else preview
        return "No messages yet"
