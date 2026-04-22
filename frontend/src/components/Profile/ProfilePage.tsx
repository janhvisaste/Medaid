import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Save, Loader2, User as UserIcon, Mail, Phone, MapPin, Calendar, Check, AlertCircle, Upload, FileText } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import apiService from '../../services/apiService';
import MedicalHistoryForm from './MedicalHistoryForm';

interface ProfileFormData {
  first_name: string;
  last_name: string;
  email: string;
  phone_number: string;
  date_of_birth: string;
  gender: string;
  city: string;
  state: string;
  pincode: string;
}

const ProfilePage: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'personal' | 'medical'>('personal');
  
  const [formData, setFormData] = useState<ProfileFormData>({
    first_name: '',
    last_name: '',
    email: '',
    phone_number: '',
    date_of_birth: '',
    gender: '',
    city: '',
    state: '',
    pincode: ''
  });

  useEffect(() => {
    loadProfileData();
  }, []);

  const loadProfileData = async () => {
    try {
      setLoading(true);
      const [user, profile] = await Promise.all([
        apiService.getCurrentUser(),
        apiService.getUserProfile()
      ]);

      setFormData({
        first_name: user.first_name || '',
        last_name: user.last_name || '',
        email: user.email || '',
        phone_number: user.phone_number || '',
        date_of_birth: profile.date_of_birth || '',
        gender: profile.gender || '',
        city: profile.city || '',
        state: profile.state || '',
        pincode: profile.pincode || ''
      });
    } catch (err: any) {
      setError('Failed to load profile data');
      console.error('Profile load error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    setSuccess(false);
    setError(null);
  };

  const handleSaveChanges = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSuccess(false);

    try {
      // Update user basic info
      await apiService.updateUser({
        first_name: formData.first_name,
        last_name: formData.last_name,
        phone_number: formData.phone_number
      });

      // Update profile info
      await apiService.updateUserProfile({
        date_of_birth: formData.date_of_birth,
        gender: formData.gender,
        city: formData.city,
        state: formData.state,
        pincode: formData.pincode
      });

      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to save changes');
      console.error('Save error:', err);
    } finally {
      setSaving(false);
    }
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
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <button
            onClick={() => navigate('/dashboard')}
            className="text-purple-300 hover:text-white mb-4 transition-colors"
          >
            ← Back to Dashboard
          </button>
          <h1 className="text-4xl font-bold text-white mb-2">Profile Settings</h1>
          <p className="text-purple-200">Manage your personal information and medical history</p>
        </motion.div>

        {/* Tabs */}
        <div className="flex gap-4 mb-6">
          <button
            onClick={() => setActiveTab('personal')}
            className={`px-6 py-3 rounded-lg font-medium transition-all ${
              activeTab === 'personal'
                ? 'bg-purple-600 text-white shadow-lg'
                : 'bg-gray-800/50 text-gray-300 hover:bg-gray-800'
            }`}
          >
            <UserIcon className="w-4 h-4 inline mr-2" />
            Personal Information
          </button>
          <button
            onClick={() => setActiveTab('medical')}
            className={`px-6 py-3 rounded-lg font-medium transition-all ${
              activeTab === 'medical'
                ? 'bg-purple-600 text-white shadow-lg'
                : 'bg-gray-800/50 text-gray-300 hover:bg-gray-800'
            }`}
          >
            <FileText className="w-4 h-4 inline mr-2" />
            Medical History
          </button>
        </div>

        {/* Personal Information Tab */}
        {activeTab === 'personal' && (
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            className="bg-gray-800/50 backdrop-blur-lg rounded-2xl shadow-2xl p-8 border border-gray-700"
          >
            <form onSubmit={handleSaveChanges} className="space-y-6">
              {/* Status Messages */}
              {success && (
                <div className="bg-green-500/20 border border-green-500 rounded-lg p-4 flex items-center gap-3">
                  <Check className="w-5 h-5 text-green-400" />
                  <span className="text-green-300 font-medium">Profile updated successfully!</span>
                </div>
              )}

              {error && (
                <div className="bg-red-500/20 border border-red-500 rounded-lg p-4 flex items-center gap-3">
                  <AlertCircle className="w-5 h-5 text-red-400" />
                  <span className="text-red-300">{error}</span>
                </div>
              )}

              {/* Name Fields */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    <UserIcon className="w-4 h-4 inline mr-2" />
                    First Name
                  </label>
                  <input
                    type="text"
                    name="first_name"
                    value={formData.first_name}
                    onChange={handleInputChange}
                    className="w-full px-4 py-3 bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
                    placeholder="Enter first name"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    <UserIcon className="w-4 h-4 inline mr-2" />
                    Last Name
                  </label>
                  <input
                    type="text"
                    name="last_name"
                    value={formData.last_name}
                    onChange={handleInputChange}
                    className="w-full px-4 py-3 bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
                    placeholder="Enter last name"
                  />
                </div>
              </div>

              {/* Contact Fields */}
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  <Mail className="w-4 h-4 inline mr-2" />
                  Email Address
                </label>
                <input
                  type="email"
                  name="email"
                  value={formData.email}
                  disabled
                  className="w-full px-4 py-3 bg-gray-900/50 border border-gray-600 rounded-lg text-gray-400 cursor-not-allowed"
                  placeholder="Email address (cannot be changed)"
                />
                <p className="text-sm text-gray-400 mt-1">Email cannot be changed for security reasons</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  <Phone className="w-4 h-4 inline mr-2" />
                  Phone Number
                </label>
                <input
                  type="tel"
                  name="phone_number"
                  value={formData.phone_number}
                  onChange={handleInputChange}
                  className="w-full px-4 py-3 bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
                  placeholder="Enter phone number"
                />
              </div>

              {/* Personal Details */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    <Calendar className="w-4 h-4 inline mr-2" />
                    Date of Birth
                  </label>
                  <input
                    type="date"
                    name="date_of_birth"
                    value={formData.date_of_birth}
                    onChange={handleInputChange}
                    className="w-full px-4 py-3 bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Gender
                  </label>
                  <select
                    name="gender"
                    value={formData.gender}
                    onChange={handleInputChange}
                    className="w-full px-4 py-3 bg-gray-900 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
                  >
                    <option value="">Select gender</option>
                    <option value="M">Male</option>
                    <option value="F">Female</option>
                    <option value="O">Other</option>
                  </select>
                </div>
              </div>

              {/* Location Fields */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="md:col-span-1">
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    <MapPin className="w-4 h-4 inline mr-2" />
                    City
                  </label>
                  <input
                    type="text"
                    name="city"
                    value={formData.city}
                    onChange={handleInputChange}
                    className="w-full px-4 py-3 bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
                    placeholder="City"
                  />
                </div>

                <div className="md:col-span-1">
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    State
                  </label>
                  <input
                    type="text"
                    name="state"
                    value={formData.state}
                    onChange={handleInputChange}
                    className="w-full px-4 py-3 bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
                    placeholder="State"
                  />
                </div>

                <div className="md:col-span-1">
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Pincode
                  </label>
                  <input
                    type="text"
                    name="pincode"
                    value={formData.pincode}
                    onChange={handleInputChange}
                    className="w-full px-4 py-3 bg-gray-900 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
                    placeholder="Pincode"
                  />
                </div>
              </div>

              {/* Save Button */}
              <div className="flex justify-end pt-4">
                <button
                  type="submit"
                  disabled={saving}
                  className="flex items-center gap-2 px-8 py-3 bg-gradient-to-r from-purple-600 to-blue-600 text-white font-medium rounded-lg hover:from-purple-700 hover:to-blue-700 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 focus:ring-offset-gray-900 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg hover:shadow-xl"
                >
                  {saving ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    <>
                      <Save className="w-5 h-5" />
                      Save Changes
                    </>
                  )}
                </button>
              </div>
            </form>

            {/* Link to Medical Documents */}
            <div className="mt-8 pt-8 border-t border-gray-700">
              <button
                onClick={() => navigate('/medical-history-insights')}
                className="flex items-center gap-3 text-purple-300 hover:text-white transition-colors"
              >
                <Upload className="w-5 h-5" />
                <div className="text-left">
                  <div className="font-medium">View Medical Documents</div>
                  <div className="text-sm text-gray-400">Access all your uploaded medical reports and documents</div>
                </div>
              </button>
            </div>
          </motion.div>
        )}

        {/* Medical History Tab */}
        {activeTab === 'medical' && (
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
          >
            <MedicalHistoryForm onSave={() => setSuccess(true)} />
          </motion.div>
        )}
      </div>
    </div>
  );
};

export default ProfilePage;
