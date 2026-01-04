import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Users,
  Activity,
  AlertTriangle,
  TrendingUp,
  Filter,
  Search,
  Calendar,
  Download,
  Eye,
  Loader2,
  AlertCircle,
  CheckCircle
} from 'lucide-react';
import apiService from '../../services/apiService';

interface ClinicianStats {
  total_patients: number;
  active_patients: number;
  emergency_patients: number;
  high_risk_patients: number;
  todays_assessments: number;
  pending_alerts: number;
}

interface PatientAssignment {
  id: number;
  patient_name: string;
  patient_email: string;
  status: string;
  priority: number;
  assigned_at: string;
  triage_details: {
    risk_level: string;
    current_symptoms: string;
    created_at: string;
  };
}

const ClinicianDashboard: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'emergency' | 'high' | 'medium' | 'low'>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('active');
  
  const [stats, setStats] = useState<ClinicianStats>({
    total_patients: 0,
    active_patients: 0,
    emergency_patients: 0,
    high_risk_patients: 0,
    todays_assessments: 0,
    pending_alerts: 0
  });

  const [patients, setPatients] = useState<PatientAssignment[]>([]);

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    fetchPatients();
  }, [filter, statusFilter, searchTerm]);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const statsData = await apiService.getClinicianStats();
      setStats(statsData);
    } catch (err: any) {
      console.error('Error fetching clinician stats:', err);
      setError(err.response?.data?.error || 'Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  const fetchPatients = async () => {
    try {
      const filters: any = {};
      if (filter !== 'all') {
        filters.risk_level = filter;
      }
      if (statusFilter) {
        filters.status = statusFilter;
      }
      if (searchTerm) {
        filters.search = searchTerm;
      }
      
      const patientsData = await apiService.getClinicianPatients(filters);
      setPatients(patientsData);
    } catch (err) {
      console.error('Error fetching patients:', err);
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

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="animate-spin text-blue-600" size={48} />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">Clinician Dashboard</h1>
          <p className="text-gray-600">Real-time patient monitoring and triage management</p>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border-2 border-red-200 rounded-xl flex items-start gap-3">
            <AlertCircle className="text-red-600 flex-shrink-0 mt-0.5" size={20} />
            <div>
              <p className="text-red-900 font-medium">Error</p>
              <p className="text-red-800 text-sm mt-1">{error}</p>
            </div>
          </div>
        )}

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-white rounded-2xl shadow-lg p-6 border-2 border-gray-200"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
                <Users className="text-blue-600" size={24} />
              </div>
              <span className="text-3xl font-bold text-gray-900">{stats.total_patients}</span>
            </div>
            <p className="text-gray-600 font-medium">Total Patients</p>
            <p className="text-sm text-gray-500 mt-1">All time</p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="bg-white rounded-2xl shadow-lg p-6 border-2 border-red-200"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-red-100 rounded-xl flex items-center justify-center">
                <AlertTriangle className="text-red-600" size={24} />
              </div>
              <span className="text-3xl font-bold text-red-600">{stats.emergency_patients}</span>
            </div>
            <p className="text-gray-600 font-medium">Emergency Cases</p>
            <p className="text-sm text-red-600 mt-1">Requires immediate attention</p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="bg-white rounded-2xl shadow-lg p-6 border-2 border-orange-200"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-orange-100 rounded-xl flex items-center justify-center">
                <Activity className="text-orange-600" size={24} />
              </div>
              <span className="text-3xl font-bold text-orange-600">{stats.high_risk_patients}</span>
            </div>
            <p className="text-gray-600 font-medium">High Risk</p>
            <p className="text-sm text-orange-600 mt-1">Review within 24 hours</p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="bg-white rounded-2xl shadow-lg p-6 border-2 border-green-200"
          >
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center">
                <TrendingUp className="text-green-600" size={24} />
              </div>
              <span className="text-3xl font-bold text-green-600">{stats.todays_assessments}</span>
            </div>
            <p className="text-gray-600 font-medium">Today's Assessments</p>
            <p className="text-sm text-gray-500 mt-1">Last 24 hours</p>
          </motion.div>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-2xl shadow-lg p-6 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={20} />
              <input
                type="text"
                placeholder="Search patients..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            {/* Risk Filter */}
            <div className="relative">
              <Filter className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={20} />
              <select
                value={filter}
                onChange={(e) => setFilter(e.target.value as any)}
                className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent appearance-none"
              >
                <option value="all">All Risk Levels</option>
                <option value="emergency">Emergency</option>
                <option value="high">High Risk</option>
                <option value="medium">Medium Risk</option>
                <option value="low">Low Risk</option>
              </select>
            </div>

            {/* Date Filter */}
            <div className="relative">
              <Calendar className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={20} />
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent appearance-none"
              >
                <option value="">All Status</option>
                <option value="active">Active</option>
                <option value="monitoring">Under Monitoring</option>
                <option value="resolved">Resolved</option>
                <option value="transferred">Transferred</option>
              </select>
            </div>
          </div>
        </div>

        {/* Patient List */}
        <div className="bg-white rounded-2xl shadow-lg p-6">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">Patient Queue</h2>
          
          {patients.length === 0 ? (
            <div className="text-center py-12">
              <Users className="mx-auto text-gray-400 mb-4" size={64} />
              <p className="text-gray-600 text-lg mb-2">No patients assigned yet</p>
              <p className="text-gray-500 text-sm">
                Patient assignments will appear here once patients complete their assessments.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {patients.map((patient) => (
                <motion.div
                  key={patient.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="border-2 border-gray-200 rounded-xl p-4 hover:border-blue-300 transition-all"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <h3 className="text-lg font-semibold text-gray-900">{patient.patient_name}</h3>
                        <span className={`px-3 py-1 rounded-full text-xs font-medium border ${getRiskColor(patient.triage_details.risk_level)}`}>
                          {patient.triage_details.risk_level.toUpperCase()}
                        </span>
                        <span className="px-3 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800 border border-blue-300">
                          {patient.status}
                        </span>
                      </div>
                      <p className="text-gray-600 text-sm mb-2">{patient.patient_email}</p>
                      <p className="text-gray-700 text-sm mb-2">
                        <strong>Symptoms:</strong> {patient.triage_details.current_symptoms}
                      </p>
                      <p className="text-gray-500 text-xs">
                        Assessed: {new Date(patient.triage_details.created_at).toLocaleString()}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <button className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
                        <Eye size={20} className="text-gray-600" />
                      </button>
                      <button className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
                        <Download size={20} className="text-gray-600" />
                      </button>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </div>

        {/* Action Items - Only show if no patients */}
        {patients.length === 0 && (
          <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-gradient-to-br from-purple-50 to-pink-50 rounded-2xl p-6 border-2 border-purple-200">
              <h3 className="text-xl font-bold text-gray-900 mb-3">Getting Started</h3>
              <ul className="space-y-2 text-gray-700">
                <li>• Ensure your account has clinician role permissions</li>
                <li>• Patients with emergency/high risk will be auto-assigned</li>
                <li>• Use filters to find specific patients quickly</li>
                <li>• Download PDFs for detailed patient reports</li>
                <li>• Add notes to track patient progress</li>
              </ul>
            </div>

            <div className="bg-gradient-to-br from-blue-50 to-cyan-50 rounded-2xl p-6 border-2 border-blue-200">
              <h3 className="text-xl font-bold text-gray-900 mb-3">Features Available</h3>
              <ul className="space-y-2 text-gray-700">
                <li className="flex items-center gap-2">
                  <CheckCircle className="text-green-600 flex-shrink-0" size={16} />
                  <span>View all patient assessments by risk level</span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="text-green-600 flex-shrink-0" size={16} />
                  <span>Filter and search patients</span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="text-green-600 flex-shrink-0" size={16} />
                  <span>Review detailed medical history</span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="text-green-600 flex-shrink-0" size={16} />
                  <span>Real-time dashboard statistics</span>
                </li>
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ClinicianDashboard;
