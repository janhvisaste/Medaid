import axios, { AxiosInstance } from 'axios';

export const API_BASE_URL = (process.env.REACT_APP_API_URL || 'http://localhost:8001/api').replace(/\/+$/, '');

// Create axios instance with default config
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

let refreshPromise: Promise<{ access: string; refresh?: string }> | null = null;

// Request interceptor to add auth token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor to handle token refresh
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config as (typeof error.config & { _retry?: boolean }) | undefined;

    if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (!refreshToken) throw new Error('Session expired. Please sign in again.');
        if (!refreshPromise) {
          refreshPromise = axios
            .post(`${API_BASE_URL}/auth/token/refresh/`, { refresh: refreshToken })
            .then(response => response.data)
            .finally(() => { refreshPromise = null; });
        }
        const { access, refresh } = await refreshPromise;
        if (!access) throw new Error('Session refresh returned no access token.');
        localStorage.setItem('access_token', access);
        if (refresh) localStorage.setItem('refresh_token', refresh);
        originalRequest.headers = originalRequest.headers || {};
        originalRequest.headers.Authorization = `Bearer ${access}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('user');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

// ====================== TYPES ======================

interface User {
  id: number;
  email: string;
  first_name?: string;
  last_name?: string;
  phone_number?: string;
  role?: 'patient' | 'clinician' | 'admin';
}

interface UserProfile {
  id: number;
  user: User;
  date_of_birth?: string;
  gender?: string;
  city?: string;
  state?: string;
  pincode?: string;
  past_history?: any;
  other_notes?: string;
  institution?: string;
  license_number?: string;
  license_expiry?: string;
  preferred_model?: string;
  created_at?: string;
  updated_at?: string;
}

interface TriageRecord {
  id: number;
  current_symptoms: string;
  risk_level: string;
  risk_probability: number;
  reasoning: string;
  confidence: number;
  possible_conditions?: any[];
  recommendations?: any[];
  created_at: string;
  input_mode?: string;
  model_id?: string;
  model_provider?: string;
  assessment_source?: string;
  degraded?: boolean;
  is_degraded?: boolean;
  model_error?: string;
}

interface AvailableModel {
  id: string;
  name: string;
  context_length?: number;
  pricing?: {
    prompt?: string | null;
    completion?: string | null;
  };
  description?: string;
  is_free?: boolean;
}

interface ConsultationSession {
  id: number;
  user: number;
  user_email: string;
  stage: 'symptoms' | 'history' | 'questions' | 'assessment' | 'completed';
  symptoms?: string;
  medical_history?: any;
  clarifying_questions?: any[];
  triage_id?: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  completed_at?: string;
}

export interface Facility {
  name: string;
  address: string;
  phone?: string;
  maps_url?: string;
  facility_type: string;
  distance_km?: number;
  rating?: number;
  latitude?: number;
  longitude?: number;
}

interface DietaryCard {
  category: string;
  name: string;
  rationale: string;
  nutrient_highlights: { label: string; value: string }[];
  image_url: string;
  image_alt: string;
}

interface DietaryRecommendations {
  id: number;
  summary: string;
  cards: DietaryCard[];
  daily_pattern?: string[];
  next_step?: string;
  model_id: string;
  free_tier: boolean;
  safety_flags: string[];
  safety_notice: string;
  context_used: {
    profile: boolean;
    assessment_history: number;
    report_history: number;
    conversation_turns: number;
    previous_dietary_advice: number;
  };
}

interface AbnormalFinding {
  test_name: string;
  abbreviation?: string;
  value: string;
  unit: string;
  status: string;
  reference_range: string;
  category: string;
  source: string;
  severity?: string;
}

interface ExtractionSummary {
  total_reports: number;
  total_tests: number;
  abnormal_count: number;
  critical_findings: AbnormalFinding[];
  all_abnormals: AbnormalFinding[];
}

interface TestResult {
  test_name: string;
  abbreviation?: string;
  result_value: string;
  result_flag?: string;
  unit: string;
  reference_range: {
    low?: string;
    high?: string;
    text?: string;
  };
  is_abnormal: boolean;
  category?: string;
}

interface ExtractedReport {
  _source_file: string;
  report_metadata?: {
    lab_name?: string;
    report_type?: string;
    report_date?: string;
    patient_id?: string;
    patient_name?: string;
    patient_age?: number;
    patient_gender?: string;
    doctor_name?: string;
    sample_id?: string;
  };
  test_results?: TestResult[];
  abnormal_findings?: string[];
  specimen_type?: string;
  equipment_used?: string;
  notes?: string;
  error?: string;
}

/** A finding whose status was verified arithmetically against reference ranges. */
export interface VerifiedFinding {
  test_name: string;
  value: string;
  status: 'normal' | 'low' | 'high' | 'critical_low' | 'critical_high' | 'unknown';
  explanation?: string;
  possible_causes?: string[];
  action?: string;
  reference_range?: string;
}

/** Doctor-to-patient narrative, generated only from verified findings. */
export interface ReportConsultation {
  headline: string;
  opening: string;
  whats_working_well: string;
  needs_attention: {
    test_name: string;
    plain_meaning: string;
    why_it_matters_for_you: string;
    urgency: 'routine' | 'soon' | 'urgent' | string;
  }[];
  connection_to_your_history: string;
  trend_vs_previous: string;
  next_steps: string[];
  follow_up: string;
  questions_for_your_doctor: string[];
  red_flags: string[];
  closing: string;
}

export interface ReportVerification {
  total: number;
  verified: number;
  normal: number;
  abnormal: number;
  critical: number;
  unverified: number;
  overall_status: 'urgent' | 'attention_needed' | 'reassuring' | 'unclear' | string;
}

interface DetailedReportAnalysis {
  success: boolean;
  // Present instead of the fields below when the report is still being
  // processed (HTTP 202) — callers must check this before reading the rest.
  pending?: boolean;
  message?: string;
  report_id?: number;
  file_name?: string;
  generated_at?: string;
  extraction_summary?: ExtractionSummary;
  extracted_reports?: ExtractedReport[];
  clinical_insights?: string;
  markdown_report?: string;
  consultation?: ReportConsultation | null;
  verification?: ReportVerification | null;
  abnormal_findings?: VerifiedFinding[];
}

// ====================== API SERVICE ======================

class ApiService {
  // ==================== AUTHENTICATION ====================

  async signup(data: {
    email: string;
    password: string;
    confirm_password: string;
    first_name?: string;
    last_name?: string;
  }) {
    const response = await apiClient.post('/auth/signup/', data);
    return response.data;
  }

  async login(email: string, password: string) {
    const response = await apiClient.post('/auth/login/', { email, password });
    const { access, refresh, user } = response.data;

    localStorage.setItem('access_token', access);
    localStorage.setItem('refresh_token', refresh);
    localStorage.setItem('user', JSON.stringify(user));

    return { access, refresh, user };
  }

  async logout() {
    const refreshToken = localStorage.getItem('refresh_token');
    try {
      await apiClient.post('/auth/logout/', { refresh: refreshToken });
    } finally {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      localStorage.removeItem('user');
    }
  }

  async getCurrentUser(): Promise<User> {
    const response = await apiClient.get('/auth/me/');
    return response.data;
  }

  async updateUser(data: {
    first_name?: string;
    last_name?: string;
    phone_number?: string;
  }): Promise<User> {
    const response = await apiClient.patch('/auth/update/', data);
    return response.data;
  }

  // ==================== USER PROFILE ====================

  async getUserProfile(): Promise<UserProfile> {
    const response = await apiClient.get('/profile/');
    return response.data;
  }

  async updateUserProfile(data: Partial<UserProfile>): Promise<UserProfile> {
    const response = await apiClient.patch('/profile/update/', data);
    return response.data;
  }

  async updateMedicalHistory(
    conditions: Array<{
      name: string;
      selected: boolean;
      notes?: string;
    }>,
    other_notes?: string,
  ) {
    const body: Record<string, unknown> = { conditions };
    // Only include other_notes in the payload when explicitly provided
    // (undefined = caller didn't touch the field; null/'' = caller cleared it)
    if (other_notes !== undefined) {
      body.other_notes = other_notes;
    }
    const response = await apiClient.post('/profile/update-history/', body);
    return response.data;
  }

  // ==================== MEDICAL REPORTS ====================

  async getMedicalReports(): Promise<any[]> {
    const response = await apiClient.get('/medical-reports/');
    // Handle both array and paginated response formats
    if (Array.isArray(response.data)) {
      return response.data;
    } else if (response.data?.results && Array.isArray(response.data.results)) {
      return response.data.results;
    }
    return [];
  }

  async getMedicalReportById(id: number): Promise<any> {
    const response = await apiClient.get(`/medical-reports/${id}/`);
    return response.data;
  }

  async uploadMedicalReport(formData: FormData): Promise<any> {
    const response = await apiClient.post('/medical-reports/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  }

  async analyzeMedicalReport(reportId: number): Promise<any> {
    const response = await apiClient.post('/reports/analyze/', { report_id: reportId });
    return response.data;
  }

  async deleteMedicalReport(id: number): Promise<void> {
    await apiClient.delete(`/medical-reports/${id}/`);
  }

  async deleteConversation(id: number): Promise<void> {
    await apiClient.delete(`/chat/conversations/${id}/`);
  }

  /**
   * Delete one of the user's own assessments.
   *
   * Throws with a readable message when the backend refuses (409) because a
   * clinician is still reviewing it — callers should surface that, not swallow it.
   */
  async deleteTriageRecord(id: number): Promise<void> {
    try {
      await apiClient.delete(`/triage/${id}/`);
    } catch (error: any) {
      if (error?.response?.status === 409) {
        throw new Error(
          error.response.data?.error
            || 'This assessment is currently under clinician review and cannot be deleted yet.'
        );
      }
      throw error;
    }
  }

  // ==================== TRIAGE & ASSESSMENT ====================

  async assessSymptoms(data: {
    symptoms?: string;
    current_symptoms?: string;
    input_mode?: string;
    age?: number;
    gender?: string;
    past_history?: any;
    location?: string;
    model_id?: string;
  }): Promise<TriageRecord> {
    const response = await apiClient.post('/triage/assess/', data);
    return response.data;
  }

  async getAvailableModels(): Promise<AvailableModel[]> {
    const response = await apiClient.get('/models/available');
    return response.data.models || [];
  }

  async getTriageHistory(): Promise<TriageRecord[]> {
    const response = await apiClient.get('/triage/history/');
    if (Array.isArray(response.data)) return response.data;
    // Paginated {count, next, previous, results}; fall back to the legacy
    // `history` key for older backends.
    return response.data?.results || response.data?.history || [];
  }

  // ==================== CONSULTATION SESSIONS ====================

  async startConsultation(symptoms?: string, hasReport = false): Promise<{ session: ConsultationSession }> {
    const response = await apiClient.post('/consultation/start/', { symptoms, has_report: hasReport });
    return response.data;
  }

  async submitConsultationStep(sessionId: number, data: any): Promise<{ session: ConsultationSession }> {
    const response = await apiClient.post(`/consultation/${sessionId}/submit/`, data);
    return response.data;
  }

  async getClarifyingQuestions(sessionId: number): Promise<{
    session_id: number;
    questions: Array<{
      question: string;
      type: 'text' | 'yes_no' | 'scale';
    }>;
  }> {
    const response = await apiClient.get(`/consultation/${sessionId}/questions/`);
    return response.data;
  }

  async getActiveConsultation(): Promise<{ session: ConsultationSession } | null> {
    try {
      const response = await apiClient.get('/consultation/active/');
      return response.data;
    } catch (error: any) {
      if (error.response?.status === 404) {
        return null;
      }
      throw error;
    }
  }

  // ==================== FACILITIES ====================

  async getNearbyFacilities(params: {
    latitude?: number;
    longitude?: number;
    location?: string;
    radius?: number;
    risk_level?: string;
  }): Promise<Facility[]> {
    const response = await apiClient.get('/facilities/nearby/', { params });
    const facilities = response.data.facilities || response.data;
    if (!Array.isArray(facilities)) {
      return [];
    }

    return facilities.map((facility: any) => ({
      ...facility,
      latitude: facility.latitude ?? facility.lat,
      longitude: facility.longitude ?? facility.lng,
      distance_km: typeof facility.distance_km === 'number'
        ? facility.distance_km
        : (typeof facility.distance === 'string'
          ? parseFloat(String(facility.distance).replace(' km', ''))
          : undefined),
    }));
  }

  // ==================== DIETARY RECOMMENDATIONS ====================

  async getDietaryRecommendations(data: {
    risk_level?: string;
    possible_conditions?: string[];
    symptoms?: string;
    stated_preferences?: string;
  }): Promise<DietaryRecommendations> {
    const response = await apiClient.post('/recommendations/dietary/', data);
    return response.data;
  }

  // ==================== PDF GENERATION ====================

  async downloadAssessmentPDF(triageId: number): Promise<Blob> {
    const response = await apiClient.get(`/reports/download/${triageId}/`, {
      responseType: 'blob',
    });
    return response.data;
  }

  async downloadHealthPassportPDF(): Promise<Blob> {
    const response = await apiClient.get('/reports/health-passport-pdf/', {
      responseType: 'blob',
    });
    return response.data;
  }

  // Helper method to trigger PDF download
  downloadPDFFile(blob: Blob, filename: string) {
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  }

  // ==================== HEALTH PASSPORT ====================

  async getHealthPassport() {
    const response = await apiClient.get('/health-passport/');
    return response.data;
  }

  // ==================== CLINICIAN DASHBOARD ====================

  async getClinicianStats() {
    const response = await apiClient.get('/clinician/stats/');
    return response.data;
  }

  async getClinicianPatients(filters?: {
    risk_level?: string;
    status?: string;
    search?: string;
    from_date?: string;
    to_date?: string;
  }) {
    const response = await apiClient.get('/clinician/patients/', { params: filters });
    // Paginated {count, next, previous, results}; tolerate a bare array too.
    return Array.isArray(response.data) ? response.data : (response.data?.results ?? []);
  }

  async assignPatient(data: { triage_id: number; priority?: number; notes?: string }) {
    const response = await apiClient.post('/clinician/assign-patient/', data);
    return response.data;
  }

  async updateAssignmentStatus(assignmentId: number, data: { status: string; notes?: string }) {
    const response = await apiClient.patch(`/clinician/assignments/${assignmentId}/status/`, data);
    return response.data;
  }

  async addClinicianNote(data: { assignment_id: number; note: string; is_private?: boolean }) {
    const response = await apiClient.post('/clinician/notes/', data);
    return response.data;
  }

  async getClinicianAlerts(isRead?: boolean) {
    const params = isRead !== undefined ? { is_read: isRead } : {};
    const response = await apiClient.get('/clinician/alerts/', { params });
    // Paginated {count, next, previous, results}; tolerate a bare array too.
    return Array.isArray(response.data) ? response.data : (response.data?.results ?? []);
  }

  async markAlertRead(alertId: number) {
    const response = await apiClient.patch(`/clinician/alerts/${alertId}/mark-read/`);
    return response.data;
  }

  // ==================== DETAILED REPORT ANALYSIS ====================

  async analyzeReportDetailed(reportId: number): Promise<DetailedReportAnalysis> {
    const response = await apiClient.post('/reports/analyze-local/', { report_id: reportId });
    return response.data;
  }

  async downloadReportAnalysis(reportId: number, format: 'json' | 'md' = 'md'): Promise<Blob> {
    const response = await apiClient.get(`/reports/analysis/${reportId}/download/`, {
      params: { format },
      responseType: 'blob',
    });
    return response.data;
  }

  // Helper method to download analysis file
  downloadAnalysisFile(blob: Blob, filename: string) {
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  }
}

export const apiService = new ApiService();
export default apiService;
export type {
  User,
  UserProfile,
  TriageRecord,
  AvailableModel,
  ConsultationSession,
  DietaryRecommendations,
  DetailedReportAnalysis,
  ExtractionSummary,
  ExtractedReport,
  TestResult,
  AbnormalFinding,
};
