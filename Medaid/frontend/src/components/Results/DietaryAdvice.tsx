import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { 
  Apple, 
  Salad, 
  Coffee,
  Droplet,
  AlertCircle,
  CheckCircle,
  XCircle,
  Loader2
} from 'lucide-react';
import apiService from '../../services/apiService';
import type { DietaryRecommendations } from '../../services/apiService';

interface DietaryAdviceProps {
  riskLevel?: string;
  conditions?: string[];
  triageId?: number;
}

const DietaryAdvice: React.FC<DietaryAdviceProps> = ({ 
  riskLevel = 'medium', 
  conditions = [],
  triageId
}) => {
  const [recommendations, setRecommendations] = useState<DietaryRecommendations | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchRecommendations();
  }, [riskLevel, conditions]);

  const fetchRecommendations = async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await apiService.getDietaryRecommendations({
        risk_level: riskLevel,
        possible_conditions: conditions
      });
      setRecommendations(data);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to load dietary recommendations');
    } finally {
      setLoading(false);
    }
  };

  const getRiskColor = (risk: string) => {
    switch (risk.toLowerCase()) {
      case 'emergency': return 'bg-red-50 border-red-300 text-red-800';
      case 'high': return 'bg-orange-50 border-orange-300 text-orange-800';
      case 'medium': return 'bg-yellow-50 border-yellow-300 text-yellow-800';
      case 'low': return 'bg-green-50 border-green-300 text-green-800';
      default: return 'bg-gray-50 border-gray-300 text-gray-800';
    }
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
          <p className="text-red-800 font-medium">Error loading recommendations</p>
          <p className="text-red-700 text-sm mt-1">{error}</p>
        </div>
      </div>
    );
  }

  if (!recommendations) return null;

  const allRecommendations = recommendations.dietary_recommendations;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="text-center">
        <div className="flex items-center justify-center gap-3 mb-3">
          <Apple className="text-green-600" size={32} />
          <h2 className="text-3xl font-bold text-gray-900">Dietary Recommendations</h2>
        </div>
        <p className="text-gray-600">Personalized nutrition advice based on your health assessment</p>
      </div>

      {/* Risk Level Badge */}
      <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full border-2 ${getRiskColor(recommendations.risk_level)}`}>
        <span className="font-semibold">Risk Level:</span>
        <span className="uppercase font-bold">{recommendations.risk_level}</span>
      </div>

      {/* General Recommendations */}
      {allRecommendations.general && allRecommendations.general.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-gradient-to-br from-blue-50 to-cyan-50 rounded-2xl p-6 border-2 border-blue-200"
        >
          <div className="flex items-center gap-3 mb-4">
            <Salad className="text-blue-600" size={24} />
            <h3 className="text-xl font-bold text-gray-900">General Guidelines</h3>
          </div>
          <ul className="space-y-3">
            {allRecommendations.general.map((item: string, index: number) => (
              <motion.li
                key={index}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.1 }}
                className="flex items-start gap-3"
              >
                <CheckCircle className="text-green-600 flex-shrink-0 mt-0.5" size={20} />
                <span className="text-gray-700 leading-relaxed">{item}</span>
              </motion.li>
            ))}
          </ul>
        </motion.div>
      )}

      {/* Condition-Specific Recommendations */}
      {Object.entries(allRecommendations)
        .filter(([key]) => key !== 'general')
        .map(([condition, items], sectionIndex) => (
          <motion.div
            key={condition}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: (sectionIndex + 1) * 0.15 }}
            className="bg-white rounded-2xl p-6 border-2 border-gray-200 shadow-sm hover:shadow-md transition-shadow"
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-purple-100 flex items-center justify-center">
                <Apple className="text-purple-600" size={20} />
              </div>
              <div>
                <h3 className="text-xl font-bold text-gray-900 capitalize">
                  {condition.replace(/_/g, ' ')}
                </h3>
                <p className="text-sm text-gray-600">Specific dietary guidance</p>
              </div>
            </div>

            {Array.isArray(items) && items.length > 0 ? (
              <ul className="space-y-3">
                {items.map((item: string, index: number) => (
                  <motion.li
                    key={index}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: (sectionIndex + 1) * 0.15 + index * 0.05 }}
                    className="flex items-start gap-3 p-3 rounded-lg hover:bg-purple-50 transition-colors"
                  >
                    <CheckCircle className="text-purple-600 flex-shrink-0 mt-0.5" size={18} />
                    <span className="text-gray-700">{item}</span>
                  </motion.li>
                ))}
              </ul>
            ) : (
              <p className="text-gray-500 italic">No specific recommendations available</p>
            )}
          </motion.div>
        ))}

      {/* Hydration Reminder */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
        className="bg-gradient-to-r from-cyan-50 to-blue-50 rounded-2xl p-6 border-2 border-cyan-200"
      >
        <div className="flex items-center gap-3 mb-3">
          <Droplet className="text-cyan-600" size={24} />
          <h3 className="text-xl font-bold text-gray-900">Hydration</h3>
        </div>
        <p className="text-gray-700">
          Stay well-hydrated by drinking at least 8-10 glasses of water daily. Proper hydration supports overall health and helps your body function optimally.
        </p>
      </motion.div>

      {/* Important Notice */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
        className="bg-amber-50 border-2 border-amber-300 rounded-xl p-5"
      >
        <div className="flex items-start gap-3">
          <AlertCircle className="text-amber-600 flex-shrink-0 mt-0.5" size={20} />
          <div>
            <h4 className="font-semibold text-amber-900 mb-1">Important Notice</h4>
            <p className="text-amber-800 text-sm leading-relaxed">
              These dietary recommendations are general guidelines based on your health assessment. 
              Always consult with a healthcare professional or registered dietitian before making 
              significant changes to your diet, especially if you have existing medical conditions 
              or are taking medications.
            </p>
          </div>
        </div>
      </motion.div>

      {/* Foods to Avoid (if high/emergency risk) */}
      {(recommendations.risk_level === 'high' || recommendations.risk_level === 'emergency') && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7 }}
          className="bg-red-50 rounded-2xl p-6 border-2 border-red-200"
        >
          <div className="flex items-center gap-3 mb-4">
            <XCircle className="text-red-600" size={24} />
            <h3 className="text-xl font-bold text-gray-900">Foods to Limit or Avoid</h3>
          </div>
          <ul className="space-y-2 text-gray-700">
            <li className="flex items-start gap-3">
              <XCircle className="text-red-500 flex-shrink-0 mt-0.5" size={18} />
              <span>Processed and high-sodium foods</span>
            </li>
            <li className="flex items-start gap-3">
              <XCircle className="text-red-500 flex-shrink-0 mt-0.5" size={18} />
              <span>Excessive sugar and refined carbohydrates</span>
            </li>
            <li className="flex items-start gap-3">
              <XCircle className="text-red-500 flex-shrink-0 mt-0.5" size={18} />
              <span>Saturated and trans fats</span>
            </li>
            <li className="flex items-start gap-3">
              <XCircle className="text-red-500 flex-shrink-0 mt-0.5" size={18} />
              <span>Alcohol and caffeinated beverages</span>
            </li>
          </ul>
        </motion.div>
      )}

      {/* Quick Tips */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.8 }}
        className="bg-gradient-to-br from-green-50 to-emerald-50 rounded-2xl p-6 border-2 border-green-200"
      >
        <div className="flex items-center gap-3 mb-4">
          <Coffee className="text-green-600" size={24} />
          <h3 className="text-xl font-bold text-gray-900">Quick Tips</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="bg-white rounded-lg p-4">
            <p className="font-medium text-gray-900 mb-1">🍽️ Meal Planning</p>
            <p className="text-sm text-gray-600">Plan your meals in advance to maintain consistency</p>
          </div>
          <div className="bg-white rounded-lg p-4">
            <p className="font-medium text-gray-900 mb-1">⏰ Regular Timing</p>
            <p className="text-sm text-gray-600">Eat meals at consistent times each day</p>
          </div>
          <div className="bg-white rounded-lg p-4">
            <p className="font-medium text-gray-900 mb-1">🥗 Portion Control</p>
            <p className="text-sm text-gray-600">Use smaller plates to manage portion sizes</p>
          </div>
          <div className="bg-white rounded-lg p-4">
            <p className="font-medium text-gray-900 mb-1">📝 Food Journal</p>
            <p className="text-sm text-gray-600">Track what you eat to identify patterns</p>
          </div>
        </div>
      </motion.div>
    </div>
  );
};

export default DietaryAdvice;
