"""
URL configuration for medaid project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from api import views

# Create router for viewsets
router = DefaultRouter()
router.register(r'users', views.UserViewSet)
router.register(r'medical-reports', views.MedicalReportViewSet, basename='medical-report')

urlpatterns = [
    path('', views.health_check, name='health_check'),
    path('admin/', admin.site.urls),
    path('api/', include([
        # Authentication endpoints
        path('auth/signup/', views.signup, name='signup'),
        path('auth/login/', views.login, name='login'),
        path('auth/logout/', views.logout, name='logout'),
        path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
        
        # User endpoints
        path('auth/me/', views.get_current_user, name='current_user'),
        path('auth/update/', views.update_user, name='update_user'),
        path('profile/', views.get_user_profile, name='get_profile'),
        path('profile/update/', views.update_user_profile, name='update_profile'),
        path('profile/update-history/', views.update_medical_history, name='update_medical_history'),
        
        # Triage & AI Assessment endpoints
        path('triage/assess/', views.assess_symptoms, name='assess_symptoms'),
        path('triage/history/', views.get_triage_history, name='triage_history'),
        path('triage/analyze-report/', views.analyze_report_local_pipeline, name='triage_analyze_report'),
        path('reports/analyze/', views.analyze_medical_report, name='analyze_report'),
        path('reports/analyze-detailed/', views.analyze_report_detailed, name='analyze_report_detailed'),
        path('reports/analyze-local/', views.analyze_report_local_pipeline, name='analyze_report_local'),
        path('reports/analysis/<int:report_id>/download/', views.download_report_analysis, name='download_report_analysis'),
        path('health-passport/', views.get_health_passport, name='health_passport'),
        
        # Facility & Recommendations endpoints
        path('facilities/nearby/', views.get_nearby_facilities_view, name='nearby_facilities'),
        path('recommendations/dietary/', views.get_dietary_recommendations_view, name='dietary_recommendations'),
        
        # Consultation Session endpoints
        path('consultation/start/', views.start_consultation, name='start_consultation'),
        path('consultation/<int:session_id>/submit/', views.submit_consultation_step, name='submit_consultation_step'),
        path('consultation/<int:session_id>/questions/', views.get_clarifying_questions, name='get_clarifying_questions'),
        path('consultation/active/', views.get_active_consultation, name='get_active_consultation'),
        
        # PDF Download endpoints
        path('reports/download/<int:triage_id>/', views.download_assessment_pdf, name='download_assessment_pdf'),
        path('reports/health-passport-pdf/', views.download_health_passport_pdf, name='download_health_passport_pdf'),
        
        # Clinician Dashboard endpoints
        path('clinician/stats/', views.clinician_stats, name='clinician_stats'),
        path('clinician/patients/', views.clinician_patients, name='clinician_patients'),
        path('clinician/assign-patient/', views.assign_patient, name='assign_patient'),
        path('clinician/assignments/<int:assignment_id>/status/', views.update_assignment_status, name='update_assignment_status'),
        path('clinician/notes/', views.add_clinician_note, name='add_clinician_note'),
        path('clinician/alerts/', views.clinician_alerts, name='clinician_alerts'),
        path('clinician/alerts/<int:alert_id>/mark-read/', views.mark_alert_read, name='mark_alert_read'),
        
        # Persistent Chat endpoints
        path('chat/conversations/', views.chat_conversations_list, name='chat_conversations_list'),
        path('chat/conversations/<int:conversation_id>/', views.chat_conversation_detail, name='chat_conversation_detail'),
        path('chat/conversations/<int:conversation_id>/messages/', views.chat_send_message, name='chat_send_message'),
        path('chat/conversations/<int:conversation_id>/messages/list/', views.chat_get_messages, name='chat_get_messages'),
        
        # Router URLs
        path('', include(router.urls)),
    ])),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

