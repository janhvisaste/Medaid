import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { FileText, Calendar, Download, Eye, Loader2, Upload, AlertCircle, File, Image as ImageIcon } from 'lucide-react';
import apiService from '../../services/apiService';

interface MedicalDocument {
  id: number;
  file_name: string;
  file_type: string;
  file_size: number;
  upload_date: string;
  description?: string;
  file: string;
  extracted_text?: string;
}

const MedicalHistoryInsights: React.FC = () => {
  const navigate = useNavigate();
  const [documents, setDocuments] = useState<MedicalDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploadingFile, setUploadingFile] = useState(false);

  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    try {
      setLoading(true);
      console.log('MedicalHistoryInsights - Loading documents...');
      const reports = await apiService.getMedicalReports();
      console.log('MedicalHistoryInsights - Received reports:', reports);
      setDocuments(Array.isArray(reports) ? reports : []);
    } catch (err: any) {
      setError('Failed to load medical documents');
      console.error('Load documents error:', err);
      setDocuments([]);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('description', 'Medical report uploaded from profile');

    try {
      setUploadingFile(true);
      await apiService.uploadMedicalReport(formData);
      await loadDocuments(); // Reload documents after upload
    } catch (err: any) {
      setError('Failed to upload document');
      console.error('Upload error:', err);
    } finally {
      setUploadingFile(false);
    }
  };

  const handleViewDocument = (documentId: number) => {
    navigate(`/medical-document/${documentId}`);
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
  };

  const formatDate = (dateString: string): string => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  const getFileIcon = (fileType: string) => {
    if (fileType.includes('image')) {
      return <ImageIcon className="w-8 h-8 text-blue-400" />;
    }
    if (fileType.includes('pdf')) {
      return <FileText className="w-8 h-8 text-red-400" />;
    }
    return <File className="w-8 h-8 text-gray-400" />;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900 to-gray-900 flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-purple-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900 to-gray-900 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <button
            onClick={() => navigate('/profile')}
            className="text-purple-300 hover:text-white mb-4 transition-colors"
          >
            ← Back to Profile
          </button>
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold text-white mb-2">Medical History Insights</h1>
              <p className="text-purple-200">View and analyze your medical documents and reports</p>
            </div>
            <label className="cursor-pointer">
              <input
                type="file"
                accept=".pdf,.jpg,.jpeg,.png"
                onChange={handleFileUpload}
                className="hidden"
                disabled={uploadingFile}
              />
              <div className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white font-medium rounded-lg hover:from-purple-700 hover:to-blue-700 transition-all shadow-lg hover:shadow-xl">
                {uploadingFile ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Uploading...
                  </>
                ) : (
                  <>
                    <Upload className="w-5 h-5" />
                    Upload Document
                  </>
                )}
              </div>
            </label>
          </div>
        </motion.div>

        {/* Error Message */}
        {error && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mb-6 bg-red-500/20 border border-red-500 rounded-lg p-4 flex items-center gap-3"
          >
            <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
            <span className="text-red-300">{error}</span>
          </motion.div>
        )}

        {/* Documents Grid */}
        {documents.length === 0 ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-gray-800/50 backdrop-blur-lg rounded-2xl shadow-2xl p-12 border border-gray-700 text-center"
          >
            <FileText className="w-16 h-16 text-gray-600 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-white mb-2">No Documents Yet</h3>
            <p className="text-gray-400 mb-6">Upload your first medical report to get started</p>
            <label className="cursor-pointer inline-block">
              <input
                type="file"
                accept=".pdf,.jpg,.jpeg,.png"
                onChange={handleFileUpload}
                className="hidden"
              />
              <div className="px-6 py-3 bg-purple-600 text-white font-medium rounded-lg hover:bg-purple-700 transition-colors">
                <Upload className="w-5 h-5 inline mr-2" />
                Upload Your First Document
              </div>
            </label>
          </motion.div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {documents.map((doc, index) => (
              <motion.div
                key={doc.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
                className="bg-gray-800/50 backdrop-blur-lg rounded-xl shadow-xl border border-gray-700 overflow-hidden hover:border-purple-500 transition-all duration-300 group cursor-pointer"
                onClick={() => handleViewDocument(doc.id)}
              >
                {/* Document Icon Header */}
                <div className="bg-gradient-to-br from-gray-800 to-gray-900 p-6 flex items-center justify-center border-b border-gray-700 group-hover:from-purple-900 group-hover:to-blue-900 transition-all duration-300">
                  {getFileIcon(doc.file_type)}
                </div>

                {/* Document Info */}
                <div className="p-6">
                  <h3 className="text-lg font-semibold text-white mb-2 truncate group-hover:text-purple-300 transition-colors">
                    {doc.file_name}
                  </h3>
                  
                  {doc.description && (
                    <p className="text-sm text-gray-400 mb-4 line-clamp-2">
                      {doc.description}
                    </p>
                  )}

                  <div className="space-y-2 text-sm text-gray-400">
                    <div className="flex items-center gap-2">
                      <Calendar className="w-4 h-4" />
                      <span>{formatDate(doc.upload_date)}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <File className="w-4 h-4" />
                      <span>{formatFileSize(doc.file_size)}</span>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="mt-6 flex gap-3">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleViewDocument(doc.id);
                      }}
                      className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors text-sm font-medium"
                    >
                      <Eye className="w-4 h-4" />
                      View Details
                    </button>
                    <a
                      href={doc.file}
                      download
                      onClick={(e) => e.stopPropagation()}
                      className="flex items-center justify-center px-4 py-2 bg-gray-700 text-white rounded-lg hover:bg-gray-600 transition-colors"
                    >
                      <Download className="w-4 h-4" />
                    </a>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        )}

        {/* Summary Stats */}
        {documents.length > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5 }}
            className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-6"
          >
            <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl p-6 border border-gray-700">
              <div className="text-3xl font-bold text-purple-400 mb-2">{documents.length}</div>
              <div className="text-gray-300">Total Documents</div>
            </div>
            <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl p-6 border border-gray-700">
              <div className="text-3xl font-bold text-blue-400 mb-2">
                {documents.filter(d => d.file_type.includes('pdf')).length}
              </div>
              <div className="text-gray-300">PDF Reports</div>
            </div>
            <div className="bg-gray-800/50 backdrop-blur-lg rounded-xl p-6 border border-gray-700">
              <div className="text-3xl font-bold text-green-400 mb-2">
                {documents.filter(d => d.file_type.includes('image')).length}
              </div>
              <div className="text-gray-300">Images/Scans</div>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
};

export default MedicalHistoryInsights;
