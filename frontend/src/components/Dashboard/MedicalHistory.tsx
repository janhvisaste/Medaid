import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, FileText, Download, Eye, Upload, Calendar, File, AlertCircle } from 'lucide-react';
import axios from 'axios';
import authService from '../../services/authService';

interface MedicalReport {
  id: number;
  file_name: string;
  file_type: string;
  file_size: number;
  file_url: string;
  description: string;
  upload_date: string;
}

interface MedicalHistoryProps {
  isOpen: boolean;
  onClose: () => void;
}

const MedicalHistory: React.FC<MedicalHistoryProps> = ({ isOpen, onClose }) => {
  const [reports, setReports] = useState<MedicalReport[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [description, setDescription] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [debugMode, setDebugMode] = useState(false);

  // Test backend connectivity
  const testConnectivity = async () => {
    try {
      const token = authService.getToken();
      const rawToken = localStorage.getItem('access_token');
      
      console.log('=== Debug Info ===');
      console.log('authService.isAuthenticated():', authService.isAuthenticated());
      console.log('authService.getToken():', token ? `${token.substring(0, 30)}...` : 'NULL');
      console.log('Raw localStorage access_token:', rawToken ? `${rawToken.substring(0, 30)}...` : 'NULL');
      
      if (!authService.isAuthenticated()) {
        setError('No authentication token found. Please log out and log in again.');
        return;
      }

      const response = await axios.get('http://127.0.0.1:8000/', {
        timeout: 5000,
      });
      console.log('Backend health check:', response.data);
      setSuccess(`Backend is accessible! Token: ${token ? 'Present' : 'Missing'}`);
      
      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(null), 3000);
      
    } catch (error: any) {
      console.error('Connectivity test failed:', error);
      
      if (error.code === 'NETWORK_ERROR' || error.message.includes('Network Error')) {
        setError('Cannot reach backend server. Is it running on http://127.0.0.1:8000?');
      } else {
        setError(`Connectivity test failed: ${error.message}`);
      }
    }
  };

  useEffect(() => {
    if (isOpen) {
      // Clear any previous messages when modal opens
      setError(null);
      setSuccess(null);
      
      fetchReports();
    }
  }, [isOpen]);

  const fetchReports = async () => {
    setLoading(true);
    setError(null);
    try {
      if (!authService.isAuthenticated()) {
        throw new Error('No authentication token found');
      }

      const response = await axios.get('http://127.0.0.1:8001/api/medical-reports/', {
        headers: {
          'Authorization': `Bearer ${authService.getToken()}`,
        },
      });
      // Log and validate response structure  
      console.log('API Response:', response.data);
      console.log('Is Array:', Array.isArray(response.data));
      
      // Ensure response.data is always an array
      const reportsData = Array.isArray(response.data) ? response.data : [];
      setReports(reportsData);
    } catch (error: any) {
      console.error('Failed to fetch medical reports:', error);
      if (error.response) {
        setError(`Failed to fetch reports: ${error.response.data?.detail || error.response.statusText}`);
      } else {
        setError('Failed to fetch reports. Please check your connection.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      
      // Clear previous messages
      setError(null);
      setSuccess(null);
      
      // Validate file size (10MB limit)
      const maxSize = 10 * 1024 * 1024;
      if (file.size > maxSize) {
        setError('File size must be less than 10MB');
        return;
      }

      // Validate file type
      const allowedTypes = ['application/pdf', 'image/jpeg', 'image/png', 'image/jpg', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
      if (!allowedTypes.includes(file.type)) {
        setError('File type not supported. Please upload PDF, JPG, PNG, DOC, or DOCX files.');
        return;
      }

      setSelectedFile(file);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setError('Please select a file to upload');
      return;
    }

    // Validate file size (10MB limit)
    const maxSize = 10 * 1024 * 1024;
    if (selectedFile.size > maxSize) {
      setError('File size must be less than 10MB');
      return;
    }

    // Validate file type
    const allowedTypes = ['application/pdf', 'image/jpeg', 'image/png', 'image/jpg', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
    if (!allowedTypes.includes(selectedFile.type)) {
      setError('File type not supported. Please upload PDF, JPG, PNG, DOC, or DOCX files.');
      return;
    }

    setUploading(true);
    setError(null);
    setSuccess(null);

    try {
      if (!authService.isAuthenticated()) {
        throw new Error('No authentication token found. Please log in again.');
      }

      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('description', description);

      console.log('Uploading file:', selectedFile.name, 'Size:', selectedFile.size, 'Type:', selectedFile.type);
      console.log('API URL:', 'http://127.0.0.1:8001/api/medical-reports/');
      console.log('Token exists:', authService.isAuthenticated());

      const response = await axios.post('http://127.0.0.1:8001/api/medical-reports/', formData, {
        headers: {
          'Authorization': `Bearer ${authService.getToken()}`,
          'Content-Type': 'multipart/form-data',
        },
        timeout: 30000, // 30 second timeout
      });

      console.log('Upload successful:', response.data);
      setSelectedFile(null);
      setDescription('');
      setSuccess('Document uploaded successfully!');
      fetchReports();

      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(null), 3000);

    } catch (error: any) {
      console.error('Failed to upload file:', error);
      
      if (error.response) {
        console.error('Response error:', error.response.status, error.response.data);
        if (error.response.status === 401) {
          setError('Authentication failed. Please log in again.');
        } else if (error.response.status === 413) {
          setError('File too large. Please select a smaller file.');
        } else if (error.response.status === 415) {
          setError('File type not supported.');
        } else {
          setError(`Upload failed: ${error.response.data?.detail || error.response.data?.error || error.response.statusText}`);
        }
      } else if (error.code === 'NETWORK_ERROR' || error.message.includes('Network Error')) {
        setError('Network error. Please check your connection and try again.');
      } else if (error.code === 'ECONNABORTED' || error.message.includes('timeout')) {
        setError('Upload timed out. Please try again with a smaller file.');
      } else {
        setError(`Upload failed: ${error.message}`);
      }
    } finally {
      setUploading(false);
    }
  };

  const handleViewReport = (fileUrl: string) => {
    window.open(fileUrl, '_blank');
  };

  const handleDownload = async (reportId: number, fileName: string) => {
    try {
      const response = await axios.get(
        `http://127.0.0.1:8001/api/medical-reports/${reportId}/download/`,
        {
          headers: {
            'Authorization': `Bearer ${authService.getToken()}`,
          },
          responseType: 'blob',
        }
      );

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', fileName);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      console.error('Failed to download file:', error);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
            onClick={onClose}
          />

          {/* Glass Card Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
          >
            <div
              className="relative w-full max-w-4xl max-h-[85vh] overflow-hidden"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Glass morphism card */}
              <div className="bg-gradient-to-br from-gray-900/90 via-gray-800/90 to-gray-900/90 backdrop-blur-2xl border border-gray-700/50 rounded-3xl shadow-2xl shadow-blue-500/20">
                {/* Header with gradient */}
                <div className="relative bg-gradient-to-r from-blue-600/20 via-purple-600/20 to-blue-600/20 border-b border-gray-700/50 px-8 py-6">
                  <div className="absolute inset-0 bg-gradient-to-r from-blue-500/10 to-purple-500/10 blur-xl"></div>
                  
                  <div className="relative flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center">
                        <FileText className="w-6 h-6 text-white" />
                      </div>
                      <div>
                        <h2 className="text-2xl font-bold text-white">Medical History</h2>
                        <p className="text-sm text-gray-400">View and manage your medical documents</p>
                      </div>
                    </div>
                    
                    <button
                      onClick={onClose}
                      className="w-10 h-10 bg-white/10 hover:bg-white/20 backdrop-blur-md rounded-xl flex items-center justify-center transition-colors"
                    >
                      <X className="w-5 h-5 text-white" />
                    </button>
                  </div>
                </div>

                {/* Content */}
                <div className="p-8 overflow-y-auto max-h-[calc(85vh-140px)]">
                  {/* Upload Section */}
                  <div className="mb-8 bg-gradient-to-br from-gray-800/50 to-gray-900/50 border border-gray-700/50 rounded-2xl p-6 backdrop-blur-xl">
                    {/* Debug Mode Toggle */}
                    <div className="mb-4 flex justify-between items-center">
                      <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                        <Upload className="w-5 h-5 text-blue-400" />
                        Upload New Document
                      </h3>
                      <button
                        onClick={() => setDebugMode(!debugMode)}
                        className="text-xs px-3 py-1 bg-gray-700/50 hover:bg-gray-600/50 rounded text-gray-300 transition-colors"
                      >
                        {debugMode ? 'Hide Debug' : 'Show Debug'}
                      </button>
                    </div>

                    {/* Debug Section */}
                    {debugMode && (
                      <div className="mb-4 p-3 bg-gray-900/50 border border-gray-600/50 rounded-lg">
                        <h4 className="text-sm font-semibold text-gray-300 mb-2 flex items-center gap-2">
                          <AlertCircle className="w-4 h-4" />
                          Debug Information
                        </h4>
                        <div className="text-xs text-gray-400 space-y-1">
                          <div>Backend URL: http://127.0.0.1:8001/api/medical-reports/</div>
                          <div>authService.isAuthenticated(): {authService.isAuthenticated() ? '✅ Yes' : '❌ No'}</div>
                          <div>localStorage access_token: {localStorage.getItem('access_token') ? '✅ Present' : '❌ Missing'}</div>
                          <div>Token preview: {authService.getToken() ? `${authService.getToken()?.substring(0, 20)}...` : 'None'}</div>
                        </div>
                        <button
                          onClick={testConnectivity}
                          className="mt-2 px-3 py-1 bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/30 text-blue-400 rounded text-xs transition-colors"
                        >
                          Test Backend Connection
                        </button>
                      </div>
                    )}
                    
                    {/* Error Message */}
                    {error && (
                      <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
                        {error}
                      </div>
                    )}
                    
                    {/* Success Message */}
                    {success && (
                      <div className="mb-4 p-3 bg-green-500/10 border border-green-500/30 rounded-lg text-green-400 text-sm">
                        {success}
                      </div>
                    )}
                    
                    <div className="space-y-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-300 mb-2">
                          Select File
                        </label>
                        <div className="mb-2 text-xs text-gray-500">
                          Supported formats: PDF, JPG, PNG, DOC, DOCX (Max: 10MB)
                        </div>
                        <input
                          type="file"
                          onChange={handleFileSelect}
                          accept=".pdf,.jpg,.jpeg,.png,.doc,.docx"
                          className="block w-full text-sm text-gray-300 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-blue-600 file:text-white hover:file:bg-blue-500 file:cursor-pointer"
                        />
                      </div>
                      
                      {selectedFile && !error && (
                        <>
                          {/* Selected File Info */}
                          <div className="p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                            <div className="flex items-center gap-2 text-blue-400 text-sm">
                              <FileText className="w-4 h-4" />
                              <span className="font-medium">{selectedFile.name}</span>
                              <span className="text-blue-300">({formatFileSize(selectedFile.size)})</span>
                            </div>
                          </div>
                          
                          <div>
                            <label className="block text-sm font-medium text-gray-300 mb-2">
                              Description (Optional)
                            </label>
                            <textarea
                              value={description}
                              onChange={(e) => setDescription(e.target.value)}
                              placeholder="Add a note about this document..."
                              className="w-full bg-gray-800/50 border border-gray-700 rounded-lg px-4 py-2 text-white placeholder:text-gray-500 focus:outline-none focus:border-blue-500/50 resize-none"
                              rows={2}
                            />
                          </div>
                          
                          <button
                            onClick={handleUpload}
                            disabled={uploading}
                            className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 disabled:from-gray-600 disabled:to-gray-700 disabled:cursor-not-allowed text-white font-semibold py-3 rounded-xl transition-all duration-200 flex items-center justify-center gap-2"
                          >
                            {uploading ? (
                              <>
                                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                                Uploading...
                              </>
                            ) : (
                              <>
                                <Upload className="w-5 h-5" />
                                Upload Document
                              </>
                            )}
                          </button>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Reports List */}
                  <div>
                    <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                      <FileText className="w-5 h-5 text-purple-400" />
                      Your Documents ({Array.isArray(reports) ? reports.length : 0})
                    </h3>
                    
                    {loading ? (
                      <div className="flex items-center justify-center py-12">
                        <div className="w-8 h-8 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin"></div>
                      </div>
                    ) : reports.length === 0 ? (
                      <div className="text-center py-12">
                        <File className="w-16 h-16 text-gray-600 mx-auto mb-4" />
                        <p className="text-gray-400">No documents uploaded yet</p>
                        <p className="text-sm text-gray-500 mt-1">Upload your first medical document above</p>
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 gap-4">
                        {(Array.isArray(reports) ? reports : []).map((report) => (
                          <motion.div
                            key={report.id}
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="bg-gradient-to-br from-gray-800/40 to-gray-900/40 border border-gray-700/30 rounded-xl p-5 backdrop-blur-xl hover:border-gray-600/50 transition-all group"
                          >
                            <div className="flex items-start gap-4">
                              <div className="w-12 h-12 bg-gradient-to-br from-blue-500/20 to-purple-500/20 border border-blue-500/30 rounded-lg flex items-center justify-center flex-shrink-0">
                                <FileText className="w-6 h-6 text-blue-400" />
                              </div>
                              
                              <div className="flex-1 min-w-0">
                                <h4 className="text-base font-semibold text-white truncate mb-1">
                                  {report.file_name}
                                </h4>
                                {report.description && (
                                  <p className="text-sm text-gray-400 mb-2">{report.description}</p>
                                )}
                                <div className="flex items-center gap-4 text-xs text-gray-500">
                                  <span className="flex items-center gap-1">
                                    <Calendar className="w-3.5 h-3.5" />
                                    {formatDate(report.upload_date)}
                                  </span>
                                  <span>{formatFileSize(report.file_size)}</span>
                                  <span className="uppercase">{report.file_type.split('/')[1]}</span>
                                </div>
                              </div>
                              
                              <div className="flex items-center gap-2 flex-shrink-0">
                                <button
                                  onClick={() => handleViewReport(report.file_url)}
                                  className="p-2 bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/30 text-blue-400 rounded-lg transition-colors"
                                  title="View"
                                >
                                  <Eye className="w-4 h-4" />
                                </button>
                                <button
                                  onClick={() => handleDownload(report.id, report.file_name)}
                                  className="p-2 bg-purple-600/20 hover:bg-purple-600/30 border border-purple-500/30 text-purple-400 rounded-lg transition-colors"
                                  title="Download"
                                >
                                  <Download className="w-4 h-4" />
                                </button>
                              </div>
                            </div>
                          </motion.div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

export default MedicalHistory;
