import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useNavigate, useParams } from 'react-router-dom';
import { 
  FileText, Download, Loader2, AlertCircle, 
  Activity, TrendingUp, AlertTriangle, CheckCircle,
  FileWarning, Pill, TestTube, HeartPulse
} from 'lucide-react';
import apiService from '../../services/apiService';
import authService from '../../services/authService';
import { analyzeDocument } from '../../services/documentAnalyzer';

interface MedicalDocument {
  id: number;
  file_name: string;
  file_type: string;
  file_size: number;
  upload_date: string;
  description?: string;
  file: string;
  file_url?: string;
  extracted_text?: string;
}

interface DocumentAnalysis {
  summary: string;
  keyFindings: string[];
  abnormalValues: Array<{
    parameter: string;
    value: string;
    normalRange: string;
    status: 'high' | 'low' | 'critical';
  }>;
  recommendations: string[];
  riskLevel: 'low' | 'medium' | 'high' | 'critical';
}

const MedicalDocumentDetail: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [document, setDocument] = useState<MedicalDocument | null>(null);
  const [analysis, setAnalysis] = useState<DocumentAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  useEffect(() => {
    loadDocumentDetails();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // Cleanup blob URL when component unmounts
  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const fetchFilePreview = async (docId: number) => {
    try {
      setPreviewLoading(true);
      setPreviewError(null);
      
      const token = authService.getToken();
      const response = await fetch(`http://127.0.0.1:8001/api/medical-reports/${docId}/download/`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        setPreviewUrl(url);
      } else {
        setPreviewError('Failed to load file preview');
      }
    } catch (error) {
      console.error('Error fetching file preview:', error);
      setPreviewError('Error loading preview');
    } finally {
      setPreviewLoading(false);
    }
  };

  const loadDocumentDetails = async () => {
    try {
      setLoading(true);
      const doc = await apiService.getMedicalReportById(Number(id));
      setDocument(doc);
      
      // Fetch file preview
      fetchFilePreview(doc.id);
      
      // Auto-analyze the document
      if (doc.extracted_text || doc.file) {
        analyzeDocumentContent(doc);
      }
    } catch (err: any) {
      setError('Failed to load document details');
      console.error('Load document error:', err);
    } finally {
      setLoading(false);
    }
  };

  const analyzeDocumentContent = async (doc: MedicalDocument) => {
    try {
      setAnalyzing(true);
      // Call the AI analyzer function
      const result = await analyzeDocument(doc);
      setAnalysis(result);
    } catch (err: any) {
      console.error('Analysis error:', err);
      // Set default analysis if AI fails
      setAnalysis({
        summary: 'Document uploaded successfully. Detailed AI analysis will be available soon.',
        keyFindings: ['Document received and stored securely'],
        abnormalValues: [],
        recommendations: ['Consult with your healthcare provider to discuss these results'],
        riskLevel: 'low'
      });
    } finally {
      setAnalyzing(false);
    }
  };

  const getRiskColor = (level: string) => {
    switch (level) {
      case 'critical': return 'text-red-500 bg-red-500/20 border-red-500';
      case 'high': return 'text-orange-500 bg-orange-500/20 border-orange-500';
      case 'medium': return 'text-yellow-500 bg-yellow-500/20 border-yellow-500';
      default: return 'text-green-500 bg-green-500/20 border-green-500';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'critical': return 'text-red-400 bg-red-500/20';
      case 'high': return 'text-orange-400 bg-orange-500/20';
      case 'low': return 'text-blue-400 bg-blue-500/20';
      default: return 'text-gray-400 bg-gray-500/20';
    }
  };

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900 to-gray-900 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-purple-400 animate-spin" />
      </div>
    );
  }

  if (error || !document) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900 to-gray-900 flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-16 h-16 text-red-400 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-white mb-2">Document Not Found</h2>
          <p className="text-gray-400 mb-6">{error || 'The requested document could not be found'}</p>
          <button
            onClick={() => navigate('/medical-history-insights')}
            className="px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
          >
            Back to Documents
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900 to-gray-900 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <button
            onClick={() => navigate('/medical-history-insights')}
            className="text-purple-300 hover:text-white mb-4 transition-colors"
          >
            ← Back to Medical Documents
          </button>
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-3xl font-bold text-white mb-2">{document.file_name}</h1>
              <p className="text-purple-200">Uploaded on {formatDate(document.upload_date)}</p>
            </div>
            <a
              href={document.file}
              download
              className="flex items-center gap-2 px-6 py-3 bg-gray-700 text-white rounded-lg hover:bg-gray-600 transition-colors"
            >
              <Download className="w-5 h-5" />
              Download
            </a>
          </div>
        </motion.div>

        {/* Document Info Card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-gray-800/50 backdrop-blur-lg rounded-2xl shadow-2xl p-6 border border-gray-700 mb-8"
        >
          <div className="flex items-center gap-4 mb-4">
            <FileText className="w-8 h-8 text-purple-400" />
            <div>
              <h2 className="text-xl font-semibold text-white">Document Information</h2>
              <p className="text-gray-400 text-sm">Basic details about this medical document</p>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
            <div className="bg-gray-900/50 p-4 rounded-lg">
              <div className="text-gray-400 mb-1">File Type</div>
              <div className="text-white font-medium">{document.file_type}</div>
            </div>
            <div className="bg-gray-900/50 p-4 rounded-lg">
              <div className="text-gray-400 mb-1">File Size</div>
              <div className="text-white font-medium">
                {(document.file_size / 1024).toFixed(2)} KB
              </div>
            </div>
            {document.description && (
              <div className="bg-gray-900/50 p-4 rounded-lg md:col-span-2">
                <div className="text-gray-400 mb-1">Description</div>
                <div className="text-white">{document.description}</div>
              </div>
            )}
          </div>
        </motion.div>

        {/* Document Preview */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 }}
          className="bg-gray-800/50 backdrop-blur-lg rounded-2xl shadow-2xl p-6 border border-gray-700 mb-8"
        >
          <div className="flex items-center gap-4 mb-4">
            <FileText className="w-8 h-8 text-blue-400" />
            <div>
              <h2 className="text-xl font-semibold text-white">Document Preview</h2>
              <p className="text-gray-400 text-sm">View your uploaded document</p>
            </div>
          </div>
          
          <div className="bg-gray-900/50 rounded-lg overflow-hidden min-h-[200px]">
            {previewLoading ? (
              <div className="flex flex-col items-center justify-center py-16">
                <Loader2 className="w-8 h-8 text-purple-500 animate-spin mb-4" />
                <p className="text-gray-400">Loading preview...</p>
              </div>
            ) : previewError ? (
              <div className="flex flex-col items-center justify-center py-16">
                <FileText className="w-16 h-16 text-gray-600 mb-4" />
                <p className="text-gray-400 mb-4">{previewError}</p>
                <button
                  onClick={() => document && fetchFilePreview(document.id)}
                  className="px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
                >
                  Retry Loading Preview
                </button>
              </div>
            ) : previewUrl ? (
              document.file_type?.includes('image') || document.file_name?.toLowerCase().match(/\.(jpg|jpeg|png|gif|webp)$/) ? (
                <div className="flex justify-center p-4">
                  <img 
                    src={previewUrl} 
                    alt={document.file_name}
                    className="max-w-full max-h-[600px] object-contain rounded-lg"
                  />
                </div>
              ) : document.file_type?.includes('pdf') || document.file_name?.toLowerCase().endsWith('.pdf') ? (
                <div className="relative">
                  <iframe
                    src={previewUrl}
                    className="w-full h-[600px] rounded-lg"
                    title={document.file_name}
                  />
                </div>
              ) : (
                <div className="text-center py-8">
                  <FileText className="w-16 h-16 text-gray-600 mx-auto mb-4" />
                  <p className="text-gray-400 mb-4">Preview not available for this file type</p>
                  <a
                    href={previewUrl}
                    download={document.file_name}
                    className="inline-flex items-center gap-2 px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
                  >
                    <Download className="w-5 h-5" />
                    Download to View
                  </a>
                </div>
              )
            ) : (
              <div className="flex flex-col items-center justify-center py-16">
                <FileText className="w-16 h-16 text-gray-600 mb-4" />
                <p className="text-gray-400">No preview available</p>
              </div>
            )}
          </div>
        </motion.div>

        {/* AI Analysis Section */}
        {analyzing ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="bg-gray-800/50 backdrop-blur-lg rounded-2xl shadow-2xl p-8 border border-gray-700 text-center"
          >
            <Loader2 className="w-12 h-12 text-purple-400 animate-spin mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-white mb-2">Analyzing Document...</h3>
            <p className="text-gray-400">Our AI is processing your medical document</p>
          </motion.div>
        ) : analysis && (
          <div className="space-y-8">
            {/* Risk Level Badge */}
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className={`inline-flex items-center gap-2 px-6 py-3 rounded-full border ${getRiskColor(analysis.riskLevel)}`}
            >
              <Activity className="w-5 h-5" />
              <span className="font-semibold capitalize">Risk Level: {analysis.riskLevel}</span>
            </motion.div>

            {/* Summary */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="bg-gray-800/50 backdrop-blur-lg rounded-2xl shadow-2xl p-6 border border-gray-700"
            >
              <div className="flex items-center gap-3 mb-4">
                <HeartPulse className="w-6 h-6 text-purple-400" />
                <h2 className="text-2xl font-semibold text-white">AI Analysis Summary</h2>
              </div>
              <p className="text-gray-300 leading-relaxed">{analysis.summary}</p>
            </motion.div>

            {/* Key Findings */}
            {analysis.keyFindings.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="bg-gray-800/50 backdrop-blur-lg rounded-2xl shadow-2xl p-6 border border-gray-700"
              >
                <div className="flex items-center gap-3 mb-4">
                  <TrendingUp className="w-6 h-6 text-blue-400" />
                  <h2 className="text-2xl font-semibold text-white">Key Findings</h2>
                </div>
                <ul className="space-y-3">
                  {analysis.keyFindings.map((finding, index) => (
                    <li key={index} className="flex items-start gap-3 text-gray-300">
                      <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
                      <span>{finding}</span>
                    </li>
                  ))}
                </ul>
              </motion.div>
            )}

            {/* Abnormal Values */}
            {analysis.abnormalValues.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
                className="bg-gray-800/50 backdrop-blur-lg rounded-2xl shadow-2xl p-6 border border-gray-700"
              >
                <div className="flex items-center gap-3 mb-4">
                  <TestTube className="w-6 h-6 text-orange-400" />
                  <h2 className="text-2xl font-semibold text-white">Abnormal Values Detected</h2>
                </div>
                <div className="space-y-4">
                  {analysis.abnormalValues.map((value, index) => (
                    <div
                      key={index}
                      className={`p-4 rounded-lg border ${getStatusColor(value.status)}`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="font-semibold text-white">{value.parameter}</h3>
                        <span className={`px-3 py-1 rounded-full text-xs font-medium uppercase ${getStatusColor(value.status)}`}>
                          {value.status}
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <div className="text-gray-400">Your Value</div>
                          <div className="text-white font-medium">{value.value}</div>
                        </div>
                        <div>
                          <div className="text-gray-400">Normal Range</div>
                          <div className="text-white font-medium">{value.normalRange}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}

            {/* Recommendations */}
            {analysis.recommendations.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 }}
                className="bg-gray-800/50 backdrop-blur-lg rounded-2xl shadow-2xl p-6 border border-gray-700"
              >
                <div className="flex items-center gap-3 mb-4">
                  <Pill className="w-6 h-6 text-green-400" />
                  <h2 className="text-2xl font-semibold text-white">Recommendations</h2>
                </div>
                <ul className="space-y-3">
                  {analysis.recommendations.map((rec, index) => (
                    <li key={index} className="flex items-start gap-3 text-gray-300">
                      <FileWarning className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
                      <span>{rec}</span>
                    </li>
                  ))}
                </ul>
              </motion.div>
            )}

            {/* Important Notice */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.5 }}
              className="bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-6"
            >
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-6 h-6 text-yellow-400 flex-shrink-0" />
                <div>
                  <h3 className="text-yellow-300 font-semibold mb-2">Important Notice</h3>
                  <p className="text-yellow-200/80 text-sm">
                    This AI analysis is for informational purposes only and should not replace professional medical advice. 
                    Always consult with your healthcare provider to discuss these results and get personalized recommendations.
                  </p>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </div>
    </div>
  );
};

export default MedicalDocumentDetail;
