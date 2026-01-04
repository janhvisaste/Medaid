import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  FileText,
  Calendar,
  User,
  Activity,
  Download,
  Eye,
  Search,
  ChevronLeft
} from 'lucide-react';
import authService from '../../services/authService';

interface MedicalReport {
  id: number;
  file_name: string;
  upload_date: string;
  structured_data: {
    patient_name?: string;
    patient_age?: number;
    patient_dob?: string;
    diagnosis?: string;
    triage_level?: string;
  };
  extracted_text: string;
  user: {
    first_name: string;
    last_name: string;
    email: string;
  };
}

interface PatientReportsProps {
  theme: 'light' | 'dark';
  onBack: () => void;
  onViewDetails: (reportId: number) => void;
}

const PatientReports: React.FC<PatientReportsProps> = ({ theme, onBack, onViewDetails }) => {
  const [reports, setReports] = useState<MedicalReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterTriage, setFilterTriage] = useState<string>('all');

  useEffect(() => {
    fetchReports();
  }, []);

  const fetchReports = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/api/medical-reports/', {
        headers: authService.getAuthHeaders(),
      });

      if (response.ok) {
        const data = await response.json();
        // Ensure data is always an array
        setReports(Array.isArray(data) ? data : []);
      } else {
        console.error('Failed to fetch reports');
        setReports([]);
      }
    } catch (error) {
      console.error('Error fetching reports:', error);
      setReports([]);
    } finally {
      setLoading(false);
    }
  };

  const getTriageBadge = (triage?: string) => {
    const triageLevel = triage?.toLowerCase() || 'non-urgent';
    
    const styles = {
      emergency: 'bg-red-100 text-red-700 border-red-300',
      urgent: 'bg-orange-100 text-orange-700 border-orange-300',
      'non-urgent': 'bg-green-100 text-green-700 border-green-300',
      'home remedies': 'bg-blue-100 text-blue-700 border-blue-300'
    };

    const emojis = {
      emergency: '🚨',
      urgent: '⚠️',
      'non-urgent': '✅',
      'home remedies': '🏠'
    };

    return (
      <span className={`px-3 py-1 rounded-full text-xs font-semibold border ${styles[triageLevel as keyof typeof styles] || styles['non-urgent']}`}>
        {emojis[triageLevel as keyof typeof emojis] || '✅'} {triageLevel.charAt(0).toUpperCase() + triageLevel.slice(1)}
      </span>
    );
  };

  const filteredReports = reports.filter(report => {
    const matchesSearch = 
      report.file_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      report.structured_data?.patient_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      report.structured_data?.diagnosis?.toLowerCase().includes(searchQuery.toLowerCase());
    
    const matchesFilter = filterTriage === 'all' || 
      report.structured_data?.triage_level?.toLowerCase() === filterTriage.toLowerCase();
    
    return matchesSearch && matchesFilter;
  });

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { 
      year: 'numeric', 
      month: 'short', 
      day: 'numeric' 
    });
  };

  if (loading) {
    return (
      <div className={`flex-1 flex items-center justify-center ${theme === 'dark' ? 'bg-[#0f0f0f]' : 'bg-gray-50'}`}>
        <div className="text-center">
          <Activity className="w-12 h-12 text-purple-500 animate-spin mx-auto mb-4" />
          <p className={`${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>Loading medical reports...</p>
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
                Medical History Insights
              </h1>
              <p className={`text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>
                View and analyze uploaded medical reports
              </p>
            </div>
          </div>
          
          {/* Search and Filter */}
          <div className="flex items-center gap-3">
            <div className={`relative flex items-center ${theme === 'dark' ? 'bg-gray-800' : 'bg-gray-100'} rounded-lg px-3 py-2`}>
              <Search className={`w-4 h-4 ${theme === 'dark' ? 'text-gray-400' : 'text-gray-500'} mr-2`} />
              <input
                type="text"
                placeholder="Search reports..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className={`bg-transparent ${theme === 'dark' ? 'text-white placeholder:text-gray-500' : 'text-gray-900 placeholder:text-gray-400'} focus:outline-none text-sm w-64`}
              />
            </div>
            
            <select
              value={filterTriage}
              onChange={(e) => setFilterTriage(e.target.value)}
              className={`${theme === 'dark' ? 'bg-gray-800 text-white border-gray-700' : 'bg-white text-gray-900 border-gray-300'} border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-purple-500`}
            >
              <option value="all">All Triage Levels</option>
              <option value="emergency">Emergency</option>
              <option value="urgent">Urgent</option>
              <option value="non-urgent">Non-Urgent</option>
              <option value="home remedies">Home Remedies</option>
            </select>
          </div>
        </div>
      </div>

      {/* Reports Table */}
      <div className="flex-1 overflow-y-auto p-6">
        {filteredReports.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full">
            <FileText className={`w-16 h-16 ${theme === 'dark' ? 'text-gray-700' : 'text-gray-300'} mb-4`} />
            <h3 className={`text-xl font-semibold ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'} mb-2`}>
              No medical reports found
            </h3>
            <p className={`${theme === 'dark' ? 'text-gray-500' : 'text-gray-500'}`}>
              Upload medical reports from the dashboard to see them here
            </p>
          </div>
        ) : (
          <div className={`${theme === 'dark' ? 'bg-[#1a1a1a]' : 'bg-white'} rounded-xl border ${theme === 'dark' ? 'border-gray-800' : 'border-gray-200'} overflow-hidden`}>
            <table className="w-full">
              <thead className={`${theme === 'dark' ? 'bg-gray-800/50' : 'bg-gray-50'}`}>
                <tr>
                  <th className={`px-6 py-4 text-left text-xs font-semibold ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'} uppercase tracking-wider`}>
                    No. / RM
                  </th>
                  <th className={`px-6 py-4 text-left text-xs font-semibold ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'} uppercase tracking-wider`}>
                    Patient Name
                  </th>
                  <th className={`px-6 py-4 text-left text-xs font-semibold ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'} uppercase tracking-wider`}>
                    Age
                  </th>
                  <th className={`px-6 py-4 text-left text-xs font-semibold ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'} uppercase tracking-wider`}>
                    Date of Birth
                  </th>
                  <th className={`px-6 py-4 text-left text-xs font-semibold ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'} uppercase tracking-wider`}>
                    Diagnosis
                  </th>
                  <th className={`px-6 py-4 text-left text-xs font-semibold ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'} uppercase tracking-wider`}>
                    Triage
                  </th>
                  <th className={`px-6 py-4 text-left text-xs font-semibold ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'} uppercase tracking-wider`}>
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className={`divide-y ${theme === 'dark' ? 'divide-gray-800' : 'divide-gray-200'}`}>
                {filteredReports.map((report, index) => (
                  <motion.tr
                    key={report.id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.05 }}
                    className={`${theme === 'dark' ? 'hover:bg-gray-800/30' : 'hover:bg-gray-50'} transition-colors`}
                  >
                    <td className={`px-6 py-4 whitespace-nowrap text-sm font-medium ${theme === 'dark' ? 'text-gray-300' : 'text-gray-900'}`}>
                      R{String(report.id).padStart(5, '0')}
                    </td>
                    <td className={`px-6 py-4 whitespace-nowrap`}>
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center">
                          <User className="w-5 h-5 text-white" />
                        </div>
                        <div>
                          <div className={`text-sm font-medium ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                            {report.structured_data?.patient_name || `${report.user.first_name} ${report.user.last_name}`}
                          </div>
                          <div className={`text-xs ${theme === 'dark' ? 'text-gray-500' : 'text-gray-500'}`}>
                            {report.user.email}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className={`px-6 py-4 whitespace-nowrap text-sm ${theme === 'dark' ? 'text-gray-300' : 'text-gray-700'}`}>
                      {report.structured_data?.patient_age ? `${report.structured_data.patient_age} yo` : 'N/A'}
                    </td>
                    <td className={`px-6 py-4 whitespace-nowrap text-sm ${theme === 'dark' ? 'text-gray-300' : 'text-gray-700'}`}>
                      <div className="flex items-center gap-2">
                        <Calendar className="w-4 h-4 text-gray-400" />
                        {report.structured_data?.patient_dob || formatDate(report.upload_date)}
                      </div>
                    </td>
                    <td className={`px-6 py-4`}>
                      <button
                        onClick={() => onViewDetails(report.id)}
                        className="text-sm text-blue-500 hover:text-blue-400 font-medium underline flex items-center gap-1"
                      >
                        <Eye className="w-4 h-4" />
                        {report.structured_data?.diagnosis || 'View Full Report'}
                      </button>
                    </td>
                    <td className={`px-6 py-4 whitespace-nowrap`}>
                      {getTriageBadge(report.structured_data?.triage_level)}
                    </td>
                    <td className={`px-6 py-4 whitespace-nowrap text-sm`}>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => onViewDetails(report.id)}
                          className={`p-2 ${theme === 'dark' ? 'hover:bg-gray-700' : 'hover:bg-gray-100'} rounded-lg transition-colors`}
                          title="View Details"
                        >
                          <Eye className={`w-4 h-4 ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`} />
                        </button>
                        <a
                          href={`http://127.0.0.1:8000/api/medical-reports/${report.id}/download/`}
                          download
                          className={`p-2 ${theme === 'dark' ? 'hover:bg-gray-700' : 'hover:bg-gray-100'} rounded-lg transition-colors`}
                          title="Download Report"
                        >
                          <Download className={`w-4 h-4 ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`} />
                        </a>
                      </div>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Footer Stats */}
      <div className={`${theme === 'dark' ? 'bg-[#1a1a1a] border-gray-800' : 'bg-white border-gray-200'} border-t px-6 py-4`}>
        <div className="flex items-center justify-between">
          <div className={`text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>
            Showing {filteredReports.length} of {reports.length} reports
          </div>
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-red-500"></div>
              <span className={`text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>
                Emergency: {reports.filter(r => r.structured_data?.triage_level?.toLowerCase() === 'emergency').length}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-orange-500"></div>
              <span className={`text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>
                Urgent: {reports.filter(r => r.structured_data?.triage_level?.toLowerCase() === 'urgent').length}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-green-500"></div>
              <span className={`text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>
                Non-Urgent: {reports.filter(r => r.structured_data?.triage_level?.toLowerCase() === 'non-urgent').length}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PatientReports;
