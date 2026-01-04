import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  TrendingUp,
  TrendingDown,
  ChevronLeft,
  Download,
  Share2,
  Printer,
  Calendar,
  User,
  Stethoscope,
  Brain,
  Clock
} from 'lucide-react';
import authService from '../../services/authService';

interface ReportDetails {
  id: number;
  file_name: string;
  upload_date: string;
  extracted_text: string;
  structured_data: {
    patient_name?: string;
    patient_age?: number;
    patient_dob?: string;
    diagnosis?: string;
    triage_level?: string;
    parameters?: any;
    abnormal_results?: Array<{
      parameter: string;
      value: string;
      normal_range: string;
      status: string;
      recommendation: string;
    }>;
  };
  ai_analysis?: {
    summary: string;
    risk_assessment: string;
    key_findings: string[];
    recommendations: string[];
    follow_up: string;
  };
}

interface ReportDetailsViewProps {
  reportId: number;
  theme: 'light' | 'dark';
  onBack: () => void;
}

const ReportDetailsView: React.FC<ReportDetailsViewProps> = ({ reportId, theme, onBack }) => {
  const [report, setReport] = useState<ReportDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);

  useEffect(() => {
    fetchReportDetails();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reportId]);

  const fetchReportDetails = async () => {
    try {
      const response = await fetch(`http://127.0.0.1:8000/api/medical-reports/${reportId}/`, {
        headers: authService.getAuthHeaders(),
      });

      if (response.ok) {
        const data = await response.json();
        setReport(data);
        
        // If no AI analysis exists, request one
        if (!data.ai_analysis) {
          await requestAIAnalysis(data);
        }
      } else {
        console.error('Failed to fetch report details');
      }
    } catch (error) {
      console.error('Error fetching report details:', error);
    } finally {
      setLoading(false);
    }
  };

  const requestAIAnalysis = async (reportData: ReportDetails) => {
    setAnalyzing(true);
    try {
      // Send extracted text and structured data to LLM for elaborate analysis
      const response = await fetch('http://127.0.0.1:8000/api/triage/analyze-report/', {
        method: 'POST',
        headers: authService.getAuthHeaders(),
        body: JSON.stringify({
          report_id: reportId,
          extracted_text: reportData.extracted_text,
          structured_data: reportData.structured_data
        })
      });

      if (response.ok) {
        const aiAnalysis = await response.json();
        setReport(prev => prev ? { ...prev, ai_analysis: aiAnalysis } : null);
      }
    } catch (error) {
      console.error('Error requesting AI analysis:', error);
    } finally {
      setAnalyzing(false);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status.toLowerCase()) {
      case 'high':
        return <TrendingUp className="w-5 h-5 text-red-500" />;
      case 'low':
        return <TrendingDown className="w-5 h-5 text-blue-500" />;
      case 'critical':
        return <AlertTriangle className="w-5 h-5 text-red-600" />;
      default:
        return <CheckCircle className="w-5 h-5 text-green-500" />;
    }
  };

  const getTriageBadge = (triage?: string) => {
    const triageLevel = triage?.toLowerCase() || 'non-urgent';
    
    const styles = {
      emergency: 'bg-red-600 text-white',
      urgent: 'bg-orange-500 text-white',
      'non-urgent': 'bg-green-500 text-white',
      'home remedies': 'bg-blue-500 text-white'
    };

    return (
      <span className={`px-4 py-2 rounded-full text-sm font-bold ${styles[triageLevel as keyof typeof styles] || styles['non-urgent']}`}>
        {triageLevel.charAt(0).toUpperCase() + triageLevel.slice(1)}
      </span>
    );
  };

  if (loading) {
    return (
      <div className={`flex-1 flex items-center justify-center ${theme === 'dark' ? 'bg-[#0f0f0f]' : 'bg-gray-50'}`}>
        <div className="text-center">
          <Activity className="w-12 h-12 text-purple-500 animate-spin mx-auto mb-4" />
          <p className={`${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>Loading report details...</p>
        </div>
      </div>
    );
  }

  if (!report) {
    return (
      <div className={`flex-1 flex items-center justify-center ${theme === 'dark' ? 'bg-[#0f0f0f]' : 'bg-gray-50'}`}>
        <div className="text-center">
          <AlertTriangle className="w-12 h-12 text-red-500 mx-auto mb-4" />
          <p className={`${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>Report not found</p>
          <button
            onClick={onBack}
            className="mt-4 px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex-1 ${theme === 'dark' ? 'bg-[#0f0f0f]' : 'bg-gray-50'} overflow-hidden flex flex-col`}>
      {/* Header */}
      <div className={`${theme === 'dark' ? 'bg-[#1a1a1a] border-gray-800' : 'bg-white border-gray-200'} border-b px-6 py-4`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={onBack}
              className={`p-2 ${theme === 'dark' ? 'hover:bg-gray-800' : 'hover:bg-gray-100'} rounded-lg transition-colors`}
            >
              <ChevronLeft className={`w-5 h-5 ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`} />
            </button>
            <div>
              <h1 className={`text-2xl font-bold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                Detailed Report Analysis
              </h1>
              <p className={`text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>
                {report.file_name}
              </p>
            </div>
          </div>
          
          {/* Action Buttons */}
          <div className="flex items-center gap-3">
            <button className={`p-2 ${theme === 'dark' ? 'hover:bg-gray-800' : 'hover:bg-gray-100'} rounded-lg transition-colors`}>
              <Download className={`w-5 h-5 ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`} />
            </button>
            <button className={`p-2 ${theme === 'dark' ? 'hover:bg-gray-800' : 'hover:bg-gray-100'} rounded-lg transition-colors`}>
              <Share2 className={`w-5 h-5 ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`} />
            </button>
            <button className={`p-2 ${theme === 'dark' ? 'hover:bg-gray-800' : 'hover:bg-gray-100'} rounded-lg transition-colors`}>
              <Printer className={`w-5 h-5 ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`} />
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-6xl mx-auto space-y-6">
          {/* Patient Info Card */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className={`${theme === 'dark' ? 'bg-[#1a1a1a] border-gray-800' : 'bg-white border-gray-200'} border rounded-xl p-6`}
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className={`text-lg font-semibold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                Patient Information
              </h2>
              {getTriageBadge(report.structured_data?.triage_level)}
            </div>
            
            <div className="grid grid-cols-3 gap-6">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <User className={`w-4 h-4 ${theme === 'dark' ? 'text-gray-400' : 'text-gray-500'}`} />
                  <span className={`text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>Patient Name</span>
                </div>
                <p className={`text-base font-medium ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                  {report.structured_data?.patient_name || 'N/A'}
                </p>
              </div>
              
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Calendar className={`w-4 h-4 ${theme === 'dark' ? 'text-gray-400' : 'text-gray-500'}`} />
                  <span className={`text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>Age / DOB</span>
                </div>
                <p className={`text-base font-medium ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                  {report.structured_data?.patient_age ? `${report.structured_data.patient_age} years` : 'N/A'}
                  {report.structured_data?.patient_dob && (
                    <span className={`text-sm ${theme === 'dark' ? 'text-gray-500' : 'text-gray-600'} ml-2`}>
                      ({report.structured_data.patient_dob})
                    </span>
                  )}
                </p>
              </div>
              
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <Clock className={`w-4 h-4 ${theme === 'dark' ? 'text-gray-400' : 'text-gray-500'}`} />
                  <span className={`text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>Upload Date</span>
                </div>
                <p className={`text-base font-medium ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                  {new Date(report.upload_date).toLocaleDateString('en-US', { 
                    year: 'numeric', 
                    month: 'long', 
                    day: 'numeric' 
                  })}
                </p>
              </div>
            </div>
          </motion.div>

          {/* Diagnosis Card */}
          {report.structured_data?.diagnosis && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className={`${theme === 'dark' ? 'bg-gradient-to-br from-purple-900/20 to-blue-900/20 border-purple-800/30' : 'bg-gradient-to-br from-purple-50 to-blue-50 border-purple-200'} border rounded-xl p-6`}
            >
              <div className="flex items-start gap-4">
                <div className="p-3 bg-purple-600 rounded-lg">
                  <Stethoscope className="w-6 h-6 text-white" />
                </div>
                <div className="flex-1">
                  <h3 className={`text-lg font-semibold mb-2 ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                    Primary Diagnosis
                  </h3>
                  <p className={`text-base ${theme === 'dark' ? 'text-gray-300' : 'text-gray-700'}`}>
                    {report.structured_data.diagnosis}
                  </p>
                </div>
              </div>
            </motion.div>
          )}

          {/* Abnormal Results */}
          {report.structured_data?.abnormal_results && report.structured_data.abnormal_results.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className={`${theme === 'dark' ? 'bg-[#1a1a1a] border-gray-800' : 'bg-white border-gray-200'} border rounded-xl p-6`}
            >
              <h2 className={`text-lg font-semibold mb-4 ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                Abnormal Test Results
              </h2>
              
              <div className="space-y-4">
                {report.structured_data.abnormal_results.map((result, index) => (
                  <div
                    key={index}
                    className={`${theme === 'dark' ? 'bg-gray-800/50' : 'bg-gray-50'} rounded-lg p-4`}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-3">
                        {getStatusIcon(result.status)}
                        <div>
                          <h4 className={`font-semibold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                            {result.parameter}
                          </h4>
                          <p className={`text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>
                            Normal Range: {result.normal_range}
                          </p>
                        </div>
                      </div>
                      <span className={`text-lg font-bold ${
                        result.status.toLowerCase() === 'high' ? 'text-red-500' :
                        result.status.toLowerCase() === 'low' ? 'text-blue-500' :
                        'text-orange-500'
                      }`}>
                        {result.value}
                      </span>
                    </div>
                    {result.recommendation && (
                      <p className={`text-sm ${theme === 'dark' ? 'text-gray-300' : 'text-gray-700'} mt-2`}>
                        <strong>Recommendation:</strong> {result.recommendation}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </motion.div>
          )}

          {/* AI Analysis */}
          {analyzing ? (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className={`${theme === 'dark' ? 'bg-[#1a1a1a] border-gray-800' : 'bg-white border-gray-200'} border rounded-xl p-8`}
            >
              <div className="text-center">
                <Brain className="w-12 h-12 text-purple-500 animate-pulse mx-auto mb-4" />
                <p className={`${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>
                  AI is analyzing your report for detailed insights...
                </p>
              </div>
            </motion.div>
          ) : report.ai_analysis && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className={`${theme === 'dark' ? 'bg-[#1a1a1a] border-gray-800' : 'bg-white border-gray-200'} border rounded-xl p-6`}
            >
              <div className="flex items-center gap-3 mb-6">
                <div className="p-3 bg-gradient-to-br from-purple-600 to-blue-600 rounded-lg">
                  <Brain className="w-6 h-6 text-white" />
                </div>
                <h2 className={`text-lg font-semibold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                  AI-Powered Analysis
                </h2>
              </div>
              
              <div className="space-y-6">
                {report.ai_analysis.summary && (
                  <div>
                    <h3 className={`text-base font-semibold mb-2 ${theme === 'dark' ? 'text-gray-300' : 'text-gray-800'}`}>
                      Summary
                    </h3>
                    <p className={`${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'} leading-relaxed`}>
                      {report.ai_analysis.summary}
                    </p>
                  </div>
                )}
                
                {report.ai_analysis.key_findings && report.ai_analysis.key_findings.length > 0 && (
                  <div>
                    <h3 className={`text-base font-semibold mb-3 ${theme === 'dark' ? 'text-gray-300' : 'text-gray-800'}`}>
                      Key Findings
                    </h3>
                    <ul className="space-y-2">
                      {report.ai_analysis.key_findings.map((finding, index) => (
                        <li key={index} className="flex items-start gap-2">
                          <CheckCircle className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
                          <span className={`${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>{finding}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                
                {report.ai_analysis.recommendations && report.ai_analysis.recommendations.length > 0 && (
                  <div>
                    <h3 className={`text-base font-semibold mb-3 ${theme === 'dark' ? 'text-gray-300' : 'text-gray-800'}`}>
                      Recommendations
                    </h3>
                    <ul className="space-y-2">
                      {report.ai_analysis.recommendations.map((rec, index) => (
                        <li key={index} className="flex items-start gap-2">
                          <span className="text-purple-500 font-bold flex-shrink-0">{index + 1}.</span>
                          <span className={`${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>{rec}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </motion.div>
          )}

          {/* Raw Report Text (Collapsible) */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className={`${theme === 'dark' ? 'bg-[#1a1a1a] border-gray-800' : 'bg-white border-gray-200'} border rounded-xl p-6`}
          >
            <details>
              <summary className={`cursor-pointer text-lg font-semibold ${theme === 'dark' ? 'text-white' : 'text-gray-900'} mb-4`}>
                View Raw Report Text
              </summary>
              <pre className={`${theme === 'dark' ? 'bg-gray-900 text-gray-300' : 'bg-gray-50 text-gray-800'} p-4 rounded-lg text-sm overflow-x-auto whitespace-pre-wrap`}>
                {report.extracted_text}
              </pre>
            </details>
          </motion.div>
        </div>
      </div>
    </div>
  );
};

export default ReportDetailsView;
