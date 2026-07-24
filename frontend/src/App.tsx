import React from 'react';
import { MotionConfig } from 'framer-motion';
import { Navigate, Route, Routes } from 'react-router-dom';
import MedaidLanding from './components/MedaidLanding';
import SignupPage from './components/Auth/SignupPage';
import LoginPage from './components/Auth/LoginPage';
import Dashboard from './components/Dashboard/Dashboard';
import MedicalHistoryPage from './components/Profile/MedicalHistoryPage';
import ProfilePage from './components/Profile/ProfilePage';
import MedicalHistoryInsights from './components/PatientHistory/MedicalHistoryInsights';
import MedicalDocumentDetail from './components/PatientHistory/MedicalDocumentDetail';
import DietaryAdvice from './components/Results/DietaryAdvice';
import { AssessmentHistory } from './components/Reports/PDFDownload';
import ClinicianDashboard from './components/Clinician/ClinicianDashboard';
import AppShell from './components/Layout/AppShell';
import { ThemeProvider } from './components/Layout/ThemeProvider';
import ProtectedRoute from './components/ProtectedRoute';

const ProtectedShell: React.FC<{ children: React.ReactNode; role?: 'clinician' | 'patient' }> = ({ children, role }) => (
  <ProtectedRoute requiredRole={role}>
    <AppShell>{children}</AppShell>
  </ProtectedRoute>
);

const App: React.FC = () => (
  <ThemeProvider>
    {/* reducedMotion="user" makes all framer-motion animations honour the
        OS prefers-reduced-motion setting, matching the CSS-level guard. */}
    <MotionConfig reducedMotion="user">
    <Routes>
      <Route path="/" element={<MedaidLanding />} />
      <Route path="/features" element={<Navigate to="/#features" replace />} />
      <Route path="/about" element={<Navigate to="/#about" replace />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/login" element={<LoginPage />} />

      <Route path="/dashboard" element={<ProtectedShell><Dashboard /></ProtectedShell>} />
      {/* Guided consultation was merged into the AI workspace chat - old links redirect there. */}
      <Route path="/consultation" element={<Navigate to="/dashboard" replace />} />
      <Route path="/medical-history" element={<ProtectedShell><MedicalHistoryPage /></ProtectedShell>} />
      <Route path="/profile" element={<ProtectedShell><ProfilePage /></ProtectedShell>} />
      <Route path="/medical-history-insights" element={<ProtectedShell><MedicalHistoryInsights /></ProtectedShell>} />
      <Route path="/medical-document/:id" element={<ProtectedShell><MedicalDocumentDetail /></ProtectedShell>} />
      <Route path="/dietary-advice" element={<ProtectedShell><DietaryAdvice /></ProtectedShell>} />
      <Route path="/assessments" element={<ProtectedShell><div className="mx-auto max-w-7xl px-4 py-8 md:px-6"><h2 className="mb-6 text-3xl font-semibold tracking-tight text-[var(--medaid-ink)]">Assessment history & reports</h2><AssessmentHistory /></div></ProtectedShell>} />
      <Route path="/clinician" element={<ProtectedShell role="clinician"><ClinicianDashboard /></ProtectedShell>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </MotionConfig>
  </ThemeProvider>
);

export default App;
