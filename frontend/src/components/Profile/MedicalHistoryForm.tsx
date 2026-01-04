import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Save, Loader2, Check, AlertCircle } from 'lucide-react';
import apiService from '../../services/apiService';

const MEDICAL_CONDITIONS = [
  { name: 'Diabetes', description: 'Type 1, Type 2, or Gestational' },
  { name: 'Hypertension', description: 'High blood pressure' },
  { name: 'Heart Disease', description: 'Coronary artery disease, heart failure' },
  { name: 'Asthma', description: 'Chronic respiratory condition' },
  { name: 'Thyroid Disorders', description: 'Hypothyroidism, Hyperthyroidism' },
  { name: 'Kidney Disease', description: 'Chronic kidney disease' },
  { name: 'Liver Disease', description: 'Hepatitis, cirrhosis, fatty liver' },
  { name: 'Cancer', description: 'Any type of cancer history' },
  { name: 'Arthritis', description: 'Rheumatoid or osteoarthritis' },
  { name: 'Mental Health Conditions', description: 'Depression, anxiety, etc.' },
  { name: 'Allergies', description: 'Food, drug, or environmental' },
  { name: 'COPD', description: 'Chronic obstructive pulmonary disease' },
  { name: 'Stroke', description: 'Previous stroke or TIA' },
  { name: 'Epilepsy', description: 'Seizure disorder' },
  { name: 'Autoimmune Disorders', description: 'Lupus, MS, etc.' }
];

interface MedicalHistoryFormProps {
  onSave?: () => void;
}

const MedicalHistoryForm: React.FC<MedicalHistoryFormProps> = ({ onSave }) => {
  const [conditions, setConditions] = useState<{[key: string]: { selected: boolean; notes: string }}>({});
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fetching, setFetching] = useState(true);

  useEffect(() => {
    loadExistingHistory();
  }, []);

  const loadExistingHistory = async () => {
    try {
      const profile = await apiService.getUserProfile();
      
      if (profile.past_history && profile.past_history.conditions) {
        const existingConditions: {[key: string]: { selected: boolean; notes: string }} = {};
        
        profile.past_history.conditions.forEach((condition: any) => {
          existingConditions[condition.name] = {
            selected: true,
            notes: condition.notes || ''
          };
        });
        
        setConditions(existingConditions);
      }
    } catch (err) {
      console.error('Failed to load medical history:', err);
    } finally {
      setFetching(false);
    }
  };

  const toggleCondition = (conditionName: string) => {
    setConditions(prev => ({
      ...prev,
      [conditionName]: {
        selected: !prev[conditionName]?.selected,
        notes: prev[conditionName]?.notes || ''
      }
    }));
    setSuccess(false);
    setError(null);
  };

  const updateNotes = (conditionName: string, notes: string) => {
    setConditions(prev => ({
      ...prev,
      [conditionName]: {
        ...prev[conditionName],
        notes
      }
    }));
    setSuccess(false);
  };

  const handleSave = async () => {
    setLoading(true);
    setError(null);
    setSuccess(false);

    try {
      const conditionsArray = MEDICAL_CONDITIONS.map(condition => ({
        name: condition.name,
        selected: conditions[condition.name]?.selected || false,
        notes: conditions[condition.name]?.notes || ''
      }));

      await apiService.updateMedicalHistory(conditionsArray);
      
      setSuccess(true);
      if (onSave) onSave();

      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(false), 3000);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to save medical history');
    } finally {
      setLoading(false);
    }
  };

  const selectedCount = Object.values(conditions).filter(c => c.selected).length;

  if (fetching) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="animate-spin text-blue-600" size={32} />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="bg-white rounded-2xl shadow-xl p-8">
        {/* Header */}
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-gray-900 mb-2">Past Medical History</h2>
          <p className="text-gray-600">
            Select all conditions you have been diagnosed with. This information helps us provide more accurate assessments.
          </p>
          <div className="mt-3 text-sm text-blue-600 font-medium">
            {selectedCount} condition{selectedCount !== 1 ? 's' : ''} selected
          </div>
        </div>

        {/* Success Message */}
        {success && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg flex items-center gap-3"
          >
            <Check className="text-green-600" size={20} />
            <span className="text-green-800 font-medium">Medical history saved successfully!</span>
          </motion.div>
        )}

        {/* Error Message */}
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3"
          >
            <AlertCircle className="text-red-600 flex-shrink-0" size={20} />
            <span className="text-red-800">{error}</span>
          </motion.div>
        )}

        {/* Conditions Grid */}
        <div className="space-y-3 mb-8">
          {MEDICAL_CONDITIONS.map((condition, index) => (
            <motion.div
              key={condition.name}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.03 }}
              className={`border-2 rounded-xl p-5 transition-all ${
                conditions[condition.name]?.selected
                  ? 'border-blue-400 bg-blue-50'
                  : 'border-gray-200 hover:border-gray-300 bg-white'
              }`}
            >
              <label className="flex items-start gap-4 cursor-pointer">
                <input
                  type="checkbox"
                  checked={conditions[condition.name]?.selected || false}
                  onChange={() => toggleCondition(condition.name)}
                  className="mt-1 w-5 h-5 text-blue-600 rounded focus:ring-2 focus:ring-blue-500 cursor-pointer"
                />
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-semibold text-gray-900">{condition.name}</span>
                  </div>
                  <p className="text-sm text-gray-600 mb-3">{condition.description}</p>
                  
                  {conditions[condition.name]?.selected && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                    >
                      <input
                        type="text"
                        placeholder="Add notes (e.g., diagnosis date, severity, medications)..."
                        value={conditions[condition.name]?.notes || ''}
                        onChange={(e) => updateNotes(condition.name, e.target.value)}
                        className="w-full px-4 py-2.5 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        onClick={(e) => e.stopPropagation()}
                      />
                    </motion.div>
                  )}
                </div>
              </label>
            </motion.div>
          ))}
        </div>

        {/* Save Button */}
        <div className="flex justify-end">
          <button
            onClick={handleSave}
            disabled={loading}
            className="px-8 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <>
                <Loader2 className="animate-spin" size={20} />
                Saving...
              </>
            ) : (
              <>
                <Save size={20} />
                Save Medical History
              </>
            )}
          </button>
        </div>

        {/* Info Box */}
        <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <p className="text-sm text-blue-800">
            <strong>Note:</strong> Your medical history is kept confidential and will only be used to provide you with better health assessments and recommendations.
          </p>
        </div>
      </div>
    </div>
  );
};

export default MedicalHistoryForm;
