from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from .models import (
    User, UserProfile, MedicalReport, ConsultationSession,
    PatientAssignment, ClinicianNote, ClinicianAlert, TriageRecord,
    ChatConversation, ChatMessage
)


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'phone_number', 'role', 'profile_picture', 'specialization', 'bio', 'is_verified', 'created_at']
        read_only_fields = ['id', 'created_at', 'is_verified']


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for UserProfile model"""
    user = UserSerializer(read_only=True)

    class Meta:
        model = UserProfile
        fields = ['id', 'user', 'date_of_birth', 'gender', 'city', 'state', 'pincode', 'institution', 'license_number', 'license_expiry', 'preferred_language', 'past_history', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class SignupSerializer(serializers.ModelSerializer):
    """Serializer for user signup"""
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['email', 'password', 'confirm_password', 'first_name', 'last_name']

    def validate(self, data):
        if data['password'] != data.pop('confirm_password'):
            raise serializers.ValidationError({'password': 'Passwords do not match.'})
        return data

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        # Create user profile
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
            user = authenticate(username=email, password=password)
            if not user:
                msg = 'Unable to log in with provided credentials.'
                raise serializers.ValidationError(msg, code='authorization')
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

    class Meta:
        model = MedicalReport
        fields = ['id', 'user', 'user_email', 'user_first_name', 'user_last_name', 'file', 'file_url', 'file_name', 'file_type', 'file_size', 'description', 'extracted_text', 'structured_data', 'upload_date', 'updated_at']
        read_only_fields = ['id', 'user', 'upload_date', 'updated_at', 'file_name', 'file_type', 'file_size']

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        elif obj.file:
            return obj.file.url
        return None


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
            'possible_conditions', 'recommendations',
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


class ClinicianAlertSerializer(serializers.ModelSerializer):
    """Serializer for ClinicianAlert model"""
    patient_email = serializers.EmailField(source='patient.email', read_only=True)
    patient_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ClinicianAlert
        fields = [
            'id', 'clinician', 'patient', 'patient_email', 'patient_name',
            'assignment', 'alert_type', 'message', 'is_read', 'is_actioned',
            'created_at', 'read_at', 'actioned_at'
        ]
        read_only_fields = ['id', 'clinician', 'patient', 'created_at']
    
    def get_patient_name(self, obj):
        return f"{obj.patient.first_name} {obj.patient.last_name}".strip() or obj.patient.email


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
