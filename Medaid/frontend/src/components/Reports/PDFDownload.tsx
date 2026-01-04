import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Download, 
  FileText, 
  Calendar,
  AlertCircle,
  Loader2,
  CheckCircle,
  User
} from 'lucide-react';
import apiService from '../../services/apiService';
import type { TriageRecord } from '../../services/apiService';

interface PDFDownloadButtonProps {
  triageId?: number;
  type?: 'assessment' | 'passport';
  variant?: 'primary' | 'secondary';
  className?: string;
}

const PDFDownloadButton: React.FC<PDFDownloadButtonProps> = ({ 
  triageId,
  type = 'assessment',
  variant = 'primary',
  className = ''
}) => {
  const [downloading, setDownloading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDownload = async () => {
    setDownloading(true);
    setError(null);
    setSuccess(false);

    try {
      let blob: Blob;
      let filename: string;

      if (type === 'passport') {
        blob = await apiService.downloadHealthPassportPDF();
        filename = `health_passport_${new Date().toISOString().split('T')[0]}.pdf`;
      } else if (triageId) {
        blob = await apiService.downloadAssessmentPDF(triageId);
        filename = `assessment_${triageId}_${new Date().toISOString().split('T')[0]}.pdf`;
      } else {
        throw new Error('Triage ID required for assessment PDF');
      }

      apiService.downloadPDFFile(blob, filename);
      setSuccess(true);

      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(false), 3000);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to download PDF');
      setTimeout(() => setError(null), 5000);
    } finally {
      setDownloading(false);
    }
  };

  const buttonClasses = variant === 'primary'
    ? 'bg-blue-600 text-white hover:bg-blue-700'
    : 'bg-gray-100 text-gray-700 hover:bg-gray-200';

  return (
    <div className={className}>
      <button
        onClick={handleDownload}
        disabled={downloading}
        className={`px-6 py-3 rounded-lg font-medium transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed ${buttonClasses}`}
      >
        {downloading ? (
          <>
            <Loader2 className="animate-spin" size={20} />
            Downloading...
          </>
        ) : success ? (
          <>
            <CheckCircle size={20} />
            Downloaded!
          </>
        ) : (
          <>
            <Download size={20} />
            Download PDF
          </>
        )}
      </button>

      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="mt-2 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2"
          >
            <AlertCircle className="text-red-600 flex-shrink-0 mt-0.5" size={16} />
            <p className="text-sm text-red-800">{error}</p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

const AssessmentHistory: React.FC = () => {
  const [assessments, setAssessments] = useState<TriageRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadAssessments();
  }, []);

  const loadAssessments = async () => {
    try {
      const data = await apiService.getTriageHistory();
      setAssessments(data);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to load assessments');
    } finally {
      setLoading(false);
    }
  };

  const getRiskColor = (risk: string) => {
    switch (risk) {
      case 'emergency': return 'bg-red-100 text-red-800 border-red-300';
      case 'high': return 'bg-orange-100 text-orange-800 border-orange-300';
      case 'medium': return 'bg-yellow-100 text-yellow-800 border-yellow-300';
      case 'low': return 'bg-green-100 text-green-800 border-green-300';
      default: return 'bg-gray-100 text-gray-800 border-gray-300';
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { 
      year: 'numeric', 
      month: 'short', 
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="animate-spin text-blue-600" size={32} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
        <AlertCircle className="text-red-600 flex-shrink-0" size={20} />
        <div>
          <p className="text-red-800 font-medium">Error loading assessments</p>
          <p className="text-red-700 text-sm mt-1">{error}</p>
        </div>
      </div>
    );
  }

  if (assessments.length === 0) {
    return (
      <div className="text-center py-12">
        <FileText className="mx-auto text-gray-400 mb-4" size={48} />
        <p className="text-gray-600">No assessments yet. Start a consultation to get your first assessment!</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Health Passport Download */}
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-2xl p-6 text-white">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-2xl font-bold mb-2">Complete Health Passport</h3>
            <p className="text-blue-100">Download your comprehensive medical history and all assessments</p>
          </div>
          <PDFDownloadButton type="passport" variant="secondary" className="ml-4" />
        </div>
      </div>

      {/* Individual Assessments */}
      <div className="grid gap-4">
        {assessments.map((assessment, index) => (
          <motion.div
            key={assessment.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
            className="bg-white rounded-xl shadow-md p-6 hover:shadow-lg transition-shadow border border-gray-200"
          >
            <div className="flex items-start justify-between mb-4">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <span className={`px-3 py-1 rounded-full text-sm font-semibold border-2 ${getRiskColor(assessment.risk_level)}`}>
                    {assessment.risk_level.toUpperCase()}
                  </span>
                  <div className="flex items-center gap-2 text-sm text-gray-600">
                    <Calendar size={16} />
                    <span>{formatDate(assessment.created_at)}</span>
                  </div>
                </div>
                <p className="text-gray-700 leading-relaxed line-clamp-2">
                  {assessment.current_symptoms}
                </p>
              </div>
              <PDFDownloadButton 
                triageId={assessment.id} 
                variant="secondary"
                className="ml-4"
              />
            </div>

            {/* Assessment Details */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4 pt-4 border-t border-gray-200">
              <div>
                <p className="text-sm text-gray-600 mb-1">Confidence</p>
                <p className="font-semibold text-gray-900">{(assessment.confidence * 100).toFixed(0)}%</p>
              </div>
              <div>
                <p className="text-sm text-gray-600 mb-1">Risk Probability</p>
                <p className="font-semibold text-gray-900">{(assessment.risk_probability * 100).toFixed(0)}%</p>
              </div>
              <div>
                <p className="text-sm text-gray-600 mb-1">Input Mode</p>
                <p className="font-semibold text-gray-900 capitalize">{assessment.input_mode || 'text'}</p>
              </div>
            </div>

            {/* Possible Conditions */}
            {assessment.possible_conditions && assessment.possible_conditions.length > 0 && (
              <div className="mt-4">
                <p className="text-sm text-gray-600 mb-2">Possible Conditions:</p>
                <div className="flex flex-wrap gap-2">
                  {assessment.possible_conditions.map((condition: any, idx: number) => (
                    <span
                      key={idx}
                      className="px-3 py-1 bg-purple-50 text-purple-700 rounded-full text-sm font-medium"
                    >
                      {typeof condition === 'string' ? condition : condition.disease_name}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        ))}
      </div>
    </div>
  );
};

export { PDFDownloadButton, AssessmentHistory };
export default PDFDownloadButton;
