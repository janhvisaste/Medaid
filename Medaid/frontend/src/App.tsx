import React from 'react';
import { Routes, Route } from 'react-router-dom';
import MedaidLanding from './components/MedaidLanding';
import FeaturesPage from './components/FeaturesPage';
import SignupPage from './components/Auth/SignupPage';
import LoginPage from './components/Auth/LoginPage';
import Dashboard from './components/Dashboard/Dashboard';
import ConsultationWizard from './components/Consultation/ConsultationWizard';
import MedicalHistoryForm from './components/Profile/MedicalHistoryForm';
import DietaryAdvice from './components/Results/DietaryAdvice';
import { AssessmentHistory } from './components/Reports/PDFDownload';
import ClinicianDashboard from './components/Clinician/ClinicianDashboard';
import Layout from './components/Layout/Layout';
import ProtectedRoute from './components/ProtectedRoute';

const App: React.FC = () => {
  return (
    <Routes>
      {/* Public Routes */}
      <Route path="/" element={<MedaidLanding />} />
      <Route path="/features" element={<FeaturesPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/login" element={<LoginPage />} />
      
      {/* Protected Routes with Layout */}
      <Route 
        path="/dashboard" 
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        } 
      />
      <Route 
        path="/consultation" 
        element={
          <ProtectedRoute>
            <Layout>
              <ConsultationWizard />
            </Layout>
          </ProtectedRoute>
        } 
      />
      <Route 
        path="/medical-history" 
        element={
          <ProtectedRoute>
            <Layout>
              <div className="max-w-7xl mx-auto px-4">
                <MedicalHistoryForm />
              </div>
            </Layout>
          </ProtectedRoute>
        } 
      />
      <Route 
        path="/dietary-advice" 
        element={
          <ProtectedRoute>
            <Layout>
              <div className="max-w-7xl mx-auto px-4">
                <DietaryAdvice />
              </div>
            </Layout>
          </ProtectedRoute>
        } 
      />
      <Route 
        path="/assessments" 
        element={
          <ProtectedRoute>
            <Layout>
              <div className="max-w-7xl mx-auto px-4">
                <h1 className="text-4xl font-bold text-gray-900 mb-8">Assessment History & Reports</h1>
                <AssessmentHistory />
              </div>
            </Layout>
          </ProtectedRoute>
        } 
      />
      <Route 
        path="/clinician" 
        element={
          <ProtectedRoute>
            <ClinicianDashboard />
          </ProtectedRoute>
        } 
      />
    </Routes>
  );
};

export default App;