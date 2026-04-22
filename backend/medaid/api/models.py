from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    """Custom User model extending Django's AbstractUser"""
    ROLE_CHOICES = [
        ('patient', 'Patient'),
        ('clinician', 'Clinician'),
        ('admin', 'Admin'),
    ]
    
    # Make username optional since we're using email as USERNAME_FIELD
    username = models.CharField(max_length=150, unique=True, null=True, blank=True)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='patient')
    is_verified = models.BooleanField(default=False)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    specialization = models.CharField(max_length=100, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []  # Empty because we only need email

    class Meta:
        db_table = 'auth_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return self.email


class UserProfile(models.Model):
    """Extended user profile information"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(
        max_length=10,
        choices=[('M', 'Male'), ('F', 'Female'), ('O', 'Other')],
        blank=True
    )
    # Location information
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    pincode = models.CharField(max_length=10, blank=True, null=True)
    
    # Medical information
    preferred_language = models.CharField(max_length=20, default='English')
    past_history = models.JSONField(default=dict, blank=True)  # Stores medical history
    
    # Professional information (for clinicians)
    institution = models.CharField(max_length=255, blank=True, null=True)
    license_number = models.CharField(max_length=50, blank=True, null=True)
    license_expiry = models.DateField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_profile'
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f"Profile of {self.user.email}"


class MedicalReport(models.Model):
    """Medical reports uploaded by users"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='medical_reports')
    file = models.FileField(upload_to='medical_reports/%Y/%m/%d/')
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=50)
    file_size = models.IntegerField(help_text='File size in bytes')
    description = models.TextField(blank=True, null=True)
    
    # Analysis results
    extracted_text = models.TextField(blank=True, null=True)
    structured_data = models.JSONField(default=dict, blank=True)
    
    upload_date = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'medical_reports'
        verbose_name = 'Medical Report'
        verbose_name_plural = 'Medical Reports'
        ordering = ['-upload_date']

    def __str__(self):
        return f"{self.file_name} - {self.user.email}"


class TriageRecord(models.Model):
    """Triage assessment records"""
    RISK_LEVELS = [
        ('emergency', 'Emergency'),
        ('high', 'High Risk'),
        ('medium', 'Medium Risk'),
        ('low', 'Low Risk'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='triage_records')
    
    # Symptoms and input
    current_symptoms = models.TextField()
    input_mode = models.CharField(max_length=20, default='text')  # text, voice, report
    voice_file = models.FileField(upload_to='voice_recordings/%Y/%m/%d/', blank=True, null=True)
    
    # Assessment results
    risk_level = models.CharField(max_length=20, choices=RISK_LEVELS)
    risk_probability = models.FloatField(default=0.0)
    reasoning = models.TextField()
    confidence = models.FloatField(default=0.0)
    
    # AI assessment metadata
    assessment_source = models.CharField(max_length=50, default='ai')  # ai, safety_rule, emergency_rule
    similar_cases = models.JSONField(default=dict, blank=True)
    
    # Related data
    medical_report = models.ForeignKey(MedicalReport, on_delete=models.SET_NULL, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'triage_records'
        verbose_name = 'Triage Record'
        verbose_name_plural = 'Triage Records'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} - {self.risk_level} - {self.created_at.strftime('%Y-%m-%d')}"


class PossibleCondition(models.Model):
    """Possible medical conditions from triage"""
    triage_record = models.ForeignKey(TriageRecord, on_delete=models.CASCADE, related_name='possible_conditions')
    disease_name = models.CharField(max_length=255)
    confidence = models.FloatField()
    category = models.CharField(max_length=100, blank=True)  # gastrointestinal, respiratory, etc.
    
    class Meta:
        db_table = 'possible_conditions'
        ordering = ['-confidence']

    def __str__(self):
        return f"{self.disease_name} ({self.confidence:.0%})"


class MedicalTest(models.Model):
    """Medical test results from uploaded reports"""
    medical_report = models.ForeignKey(MedicalReport, on_delete=models.CASCADE, related_name='tests')
    test_name = models.CharField(max_length=255)
    test_value = models.FloatField()
    test_unit = models.CharField(max_length=50)
    reference_range = models.CharField(max_length=100, blank=True)
    is_abnormal = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'medical_tests'

    def __str__(self):
        return f"{self.test_name}: {self.test_value} {self.test_unit}"


class AbnormalResult(models.Model):
    """Abnormal test results with interpretations"""
    medical_test = models.OneToOneField(MedicalTest, on_delete=models.CASCADE, related_name='abnormal_result')
    status = models.CharField(max_length=20)  # High, Low, Critical
    concern_level = models.CharField(max_length=20)  # High, Moderate, Low
    interpretation = models.TextField()
    
    class Meta:
        db_table = 'abnormal_results'

    def __str__(self):
        return f"{self.medical_test.test_name} - {self.status}"


class Recommendation(models.Model):
    """Recommendations for triage records"""
    RECOMMENDATION_TYPES = [
        ('action', 'Action'),
        ('dietary', 'Dietary'),
        ('lifestyle', 'Lifestyle'),
        ('medication', 'Medication'),
        ('facility', 'Facility Visit'),
    ]
    
    triage_record = models.ForeignKey(TriageRecord, on_delete=models.CASCADE, related_name='recommendations')
    recommendation_type = models.CharField(max_length=20, choices=RECOMMENDATION_TYPES)
    description = models.TextField()
    priority = models.IntegerField(default=1)  # 1=highest
    
    class Meta:
        db_table = 'recommendations'
        ordering = ['priority']

    def __str__(self):
        return f"{self.recommendation_type}: {self.description[:50]}"


class Facility(models.Model):
    """Healthcare facilities for recommendations"""
    name = models.CharField(max_length=255)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    
    phone = models.CharField(max_length=20, blank=True)
    facility_type = models.CharField(max_length=50)  # hospital, clinic, diagnostic center
    
    # Location data
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    
    rating = models.FloatField(null=True, blank=True)
    distance_km = models.FloatField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'facilities'

    def __str__(self):
        return f"{self.name} - {self.city}"


class ConsultationSession(models.Model):
    """Multi-step consultation session management"""
    SESSION_STAGES = [
        ('symptoms', 'Initial Symptoms'),
        ('history', 'Medical History'),
        ('questions', 'Clarifying Questions'),
        ('assessment', 'AI Assessment'),
        ('results', 'Final Results'),
        ('completed', 'Completed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='consultation_sessions')
    stage = models.CharField(max_length=20, choices=SESSION_STAGES, default='symptoms')
    
    # Session data storage (JSON)
    symptoms = models.TextField(blank=True, null=True)
    medical_history = models.JSONField(default=dict, blank=True)
    clarifying_questions = models.JSONField(default=list, blank=True)  # [{"question": "...", "answer": "..."}]
    
    # Assessment results (linked after completion)
    triage_record = models.ForeignKey(TriageRecord, on_delete=models.SET_NULL, null=True, blank=True, related_name='consultation_session')
    
    # Metadata
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'consultation_sessions'
        verbose_name = 'Consultation Session'
        verbose_name_plural = 'Consultation Sessions'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} - {self.stage} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class PatientAssignment(models.Model):
    """Patient assignments to clinicians for monitoring"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('monitoring', 'Under Monitoring'),
        ('resolved', 'Resolved'),
        ('transferred', 'Transferred'),
    ]
    
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='clinician_assignments', limit_choices_to={'role': 'patient'})
    clinician = models.ForeignKey(User, on_delete=models.CASCADE, related_name='patient_assignments', limit_choices_to={'role': 'clinician'})
    triage_record = models.ForeignKey(TriageRecord, on_delete=models.CASCADE, related_name='assignments')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    priority = models.IntegerField(default=1)  # 1=highest (emergency), 5=lowest
    notes = models.TextField(blank=True, null=True)
    
    assigned_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'patient_assignments'
        verbose_name = 'Patient Assignment'
        verbose_name_plural = 'Patient Assignments'
        ordering = ['priority', '-assigned_at']
        unique_together = [['patient', 'triage_record', 'clinician']]
    
    def __str__(self):
        return f"{self.patient.email} → {self.clinician.email} ({self.status})"


class ClinicianNote(models.Model):
    """Notes added by clinicians on patient assessments"""
    assignment = models.ForeignKey(PatientAssignment, on_delete=models.CASCADE, related_name='clinician_notes')
    clinician = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'clinician'})
    note = models.TextField()
    is_private = models.BooleanField(default=False)  # Private notes not visible to patient
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'clinician_notes'
        verbose_name = 'Clinician Note'
        verbose_name_plural = 'Clinician Notes'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Note by {self.clinician.email} at {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class ClinicianAlert(models.Model):
    """Alerts for clinicians on high-risk patients"""
    ALERT_TYPES = [
        ('new_emergency', 'New Emergency Assessment'),
        ('high_risk', 'High Risk Patient'),
        ('deteriorating', 'Patient Condition Deteriorating'),
        ('follow_up', 'Follow-up Required'),
    ]
    
    clinician = models.ForeignKey(User, on_delete=models.CASCADE, related_name='alerts', limit_choices_to={'role': 'clinician'})
    patient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='generated_alerts', limit_choices_to={'role': 'patient'})
    assignment = models.ForeignKey(PatientAssignment, on_delete=models.CASCADE, related_name='alerts', null=True, blank=True)
    
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPES)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    is_actioned = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    actioned_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'clinician_alerts'
        verbose_name = 'Clinician Alert'
        verbose_name_plural = 'Clinician Alerts'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.alert_type} for {self.clinician.email} - {self.patient.email}"


class ChatConversation(models.Model):
    """Persistent chat conversations with context memory"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_conversations')
    title = models.CharField(max_length=255, default='New Conversation')
    is_active = models.BooleanField(default=True)
    
    # Metadata for context management
    total_tokens_used = models.IntegerField(default=0)
    last_activity = models.DateTimeField(auto_now=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'chat_conversations'
        verbose_name = 'Chat Conversation'
        verbose_name_plural = 'Chat Conversations'
        ordering = ['-last_activity']
    
    def __str__(self):
        return f"{self.user.email} - {self.title}"
    
    def get_context_messages(self, max_tokens=3000):
        """Get recent messages within token limit for context"""
        messages = self.messages.all().order_by('-created_at')[:20]  # Last 20 messages
        
        context = []
        tokens_estimate = 0
        
        for msg in reversed(list(messages)):
            # Rough token estimation: ~4 chars per token
            msg_tokens = (len(msg.content) + len(msg.role)) // 4
            
            if tokens_estimate + msg_tokens > max_tokens:
                break
            
            context.append({
                'role': msg.role,
                'content': msg.content
            })
            tokens_estimate += msg_tokens
        
        return context


class ChatMessage(models.Model):
    """Individual messages within a chat conversation"""
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    ]
    
    conversation = models.ForeignKey(ChatConversation, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    
    # Optional metadata
    metadata = models.JSONField(default=dict, blank=True)  # For risk_level, triage_data, etc.
    tokens_used = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'chat_messages'
        verbose_name = 'Chat Message'
        verbose_name_plural = 'Chat Messages'
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.role}: {self.content[:50]}..."
