import axios, { AxiosInstance } from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8001/api';

// Create axios instance with default config
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

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
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (refreshToken) {
          const response = await axios.post(`${API_BASE_URL}/auth/token/refresh/`, {
            refresh: refreshToken,
          });

          const { access } = response.data;
          localStorage.setItem('access_token', access);

          originalRequest.headers.Authorization = `Bearer ${access}`;
          return apiClient(originalRequest);
        }
      } catch (refreshError) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
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
  institution?: string;
  license_number?: string;
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

interface DietaryRecommendations {
  risk_level: string;
  conditions: string[];
  dietary_recommendations: {
    general: string[];
    [key: string]: string[];
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

interface DetailedReportAnalysis {
  success: boolean;
  report_id?: number;
  file_name: string;
  generated_at: string;
  extraction_summary: ExtractionSummary;
  extracted_reports: ExtractedReport[];
  clinical_insights: string;
  markdown_report: string;
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

    return { access, refresh, user };
  }

  async logout() {
    const refreshToken = localStorage.getItem('refresh_token');
    try {
      await apiClient.post('/auth/logout/', { refresh: refreshToken });
    } finally {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
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

  async updateMedicalHistory(conditions: Array<{
    name: string;
    selected: boolean;
    notes?: string;
  }>) {
    const response = await apiClient.post('/profile/update-history/', { conditions });
    return response.data;
  }

  // ==================== MEDICAL REPORTS ====================

  async getMedicalReports(): Promise<any[]> {
    const response = await apiClient.get('/medical-reports/');
    console.log('apiService.getMedicalReports - Response:', response.data);
    
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

  // ==================== TRIAGE & ASSESSMENT ====================

  async assessSymptoms(data: {
    symptoms: string;
    age?: number;
    gender?: string;
    past_history?: any;
    location?: string;
  }): Promise<TriageRecord> {
    const response = await apiClient.post('/triage/assess/', data);
    return response.data;
  }

  async getTriageHistory(): Promise<TriageRecord[]> {
    const response = await apiClient.get('/triage/history/');
    return response.data;
  }

  // ==================== CONSULTATION SESSIONS ====================

  async startConsultation(symptoms?: string): Promise<{ session: ConsultationSession }> {
    const response = await apiClient.post('/consultation/start/', { symptoms });
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
    risk_level: string;
    possible_conditions: string[];
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
    return response.data;
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
    return response.data;
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
  ConsultationSession,
  DietaryRecommendations,
  DetailedReportAnalysis,
  ExtractionSummary,
  ExtractedReport,
  TestResult,
  AbnormalFinding,
};
