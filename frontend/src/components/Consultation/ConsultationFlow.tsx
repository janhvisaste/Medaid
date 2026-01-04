// ConsultationFlow.tsx - AI Medical Triage Consultation Component
import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  MessageSquare, Mic, Upload, CheckCircle,
  XCircle, Send, Loader,
  Heart, Stethoscope, ChevronDown, ChevronUp,
  Share2, Download, Mail, Clock, User
} from 'lucide-react';
import axios from 'axios';

interface TriageResult {
  triage_id: number;
  risk_level: 'low' | 'medium' | 'high' | 'emergency';
  risk_probability?: number;
  reasoning: string;
  confidence: number;
  possible_conditions: Array<{
    name: string;
    probability?: number;
  }> | string[];
  recommendations: Array<{
    type: string;
    text: string;
    priority?: string;
  }> | string[];
  created_at: string;
  detailed_analysis?: string;
  warning_signs?: string[];
  home_care?: string[];
}

type InputMode = 'text' | 'voice' | 'report';

const ConsultationFlow: React.FC = () => {
  const [step, setStep] = useState<'input' | 'processing' | 'results'>('input');
  const [inputMode, setInputMode] = useState<InputMode>('text');
  const [symptoms, setSymptoms] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [triageResult, setTriageResult] = useState<TriageResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedSection, setExpandedSection] = useState<string | null>('analysis');

  const getRiskColor = (risk: string) => {
    switch (risk) {
      case 'emergency':
        return 'bg-red-600 border-red-700';
      case 'high':
        return 'bg-orange-600 border-orange-700';
      case 'medium':
        return 'bg-yellow-600 border-yellow-700';
      case 'low':
        return 'bg-green-600 border-green-700';
      default:
        return 'bg-gray-600 border-gray-700';
    }
  };

  const handleSubmitSymptoms = async () => {
    if (!symptoms.trim()) {
      setError('Please describe your symptoms');
      return;
    }

    setIsLoading(true);
    setError(null);
    setStep('processing');

    try {
      const token = localStorage.getItem('access_token');
      const response = await axios.post(
        'http://127.0.0.1:8000/api/triage/assess/',
        {
          current_symptoms: symptoms,
          input_mode: inputMode
        },
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        }
      );

      setTriageResult(response.data);
      setStep('results');
    } catch (err: any) {
      console.error('Triage assessment error:', err);
      setError(err.response?.data?.error || 'Failed to assess symptoms. Please try again.');
      setStep('input');
    } finally {
      setIsLoading(false);
    }
  };

  const handleVoiceRecording = () => {
    // TODO: Implement Web Speech API
    setIsRecording(!isRecording);
    alert('Voice recording will be implemented with Web Speech API');
  };

  const handleNewConsultation = () => {
    setStep('input');
    setSymptoms('');
    setTriageResult(null);
    setError(null);
    setInputMode('text');
    setExpandedSection('analysis');
  };

  const handleDownloadPDF = () => {
    // Generate PDF summary
    alert('PDF download will be implemented');
  };

  const handleShareEmail = () => {
    if (!triageResult) return;
    const subject = encodeURIComponent('My Health Assessment Results');
    const body = encodeURIComponent(`Risk Level: ${triageResult.risk_level.toUpperCase()}\n\n${triageResult.reasoning}`);
    window.open(`mailto:?subject=${subject}&body=${body}`);
  };

  const handleShareWhatsApp = () => {
    if (!triageResult) return;
    const text = encodeURIComponent(`Health Assessment: ${triageResult.risk_level.toUpperCase()} Risk\n\n${triageResult.reasoning}`);
    window.open(`https://wa.me/?text=${text}`, '_blank');
  };

  const toggleSection = (section: string) => {
    setExpandedSection(expandedSection === section ? null : section);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 p-6">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-8"
        >
          <div className="inline-flex items-center gap-3 mb-4">
            <Stethoscope className="w-10 h-10 text-blue-600" />
            <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
              AI Health Triage
            </h1>
          </div>
          <p className="text-gray-600">Get instant medical risk assessment powered by AI</p>
        </motion.div>

        <AnimatePresence mode="wait">
          {/* Input Step */}
          {step === 'input' && (
            <motion.div
              key="input"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-white rounded-2xl shadow-xl p-8"
            >
              {/* Input Mode Selection */}
              <div className="mb-6">
                <label className="block text-sm font-semibold text-gray-700 mb-3">
                  How would you like to describe your symptoms?
                </label>
                <div className="grid grid-cols-3 gap-4">
                  <button
                    onClick={() => setInputMode('text')}
                    className={`p-4 rounded-xl border-2 transition-all ${inputMode === 'text'
                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                        : 'border-gray-200 hover:border-gray-300'
                      }`}
                  >
                    <MessageSquare className="w-6 h-6 mx-auto mb-2" />
                    <span className="text-sm font-medium">Text</span>
                  </button>
                  <button
                    onClick={() => setInputMode('voice')}
                    className={`p-4 rounded-xl border-2 transition-all ${inputMode === 'voice'
                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                        : 'border-gray-200 hover:border-gray-300'
                      }`}
                  >
                    <Mic className="w-6 h-6 mx-auto mb-2" />
                    <span className="text-sm font-medium">Voice</span>
                  </button>
                  <button
                    onClick={() => setInputMode('report')}
                    className={`p-4 rounded-xl border-2 transition-all ${inputMode === 'report'
                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                        : 'border-gray-200 hover:border-gray-300'
                      }`}
                  >
                    <Upload className="w-6 h-6 mx-auto mb-2" />
                    <span className="text-sm font-medium">Report</span>
                  </button>
                </div>
              </div>

              {/* Text Input */}
              {inputMode === 'text' && (
                <div className="mb-6">
                  <label className="block text-sm font-semibold text-gray-700 mb-3">
                    Describe your symptoms
                  </label>
                  <textarea
                    value={symptoms}
                    onChange={(e) => setSymptoms(e.target.value)}
                    placeholder="E.g., I have fever, body pain, and headache for 2 days..."
                    className="w-full h-40 px-4 py-3 border-2 border-gray-200 rounded-xl focus:border-blue-500 focus:outline-none resize-none"
                  />
                  <p className="text-sm text-gray-500 mt-2">
                    Tip: Include duration, severity, and any other relevant details
                  </p>
                </div>
              )}

              {/* Voice Input */}
              {inputMode === 'voice' && (
                <div className="mb-6">
                  <div className="flex flex-col items-center justify-center py-12 border-2 border-dashed border-gray-300 rounded-xl">
                    <button
                      onClick={handleVoiceRecording}
                      className={`w-20 h-20 rounded-full flex items-center justify-center transition-all ${isRecording
                          ? 'bg-red-500 hover:bg-red-600 animate-pulse'
                          : 'bg-blue-500 hover:bg-blue-600'
                        }`}
                    >
                      <Mic className="w-10 h-10 text-white" />
                    </button>
                    <p className="mt-4 text-gray-600 font-medium">
                      {isRecording ? 'Recording... Tap to stop' : 'Tap to start recording'}
                    </p>
                    {symptoms && (
                      <div className="mt-4 px-4 py-2 bg-gray-100 rounded-lg">
                        <p className="text-sm text-gray-700">{symptoms}</p>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Report Upload */}
              {inputMode === 'report' && (
                <div className="mb-6">
                  <div className="flex flex-col items-center justify-center py-12 border-2 border-dashed border-gray-300 rounded-xl hover:border-blue-400 transition-colors cursor-pointer">
                    <Upload className="w-16 h-16 text-gray-400 mb-4" />
                    <p className="text-gray-600 font-medium mb-2">
                      Upload Medical Report
                    </p>
                    <p className="text-sm text-gray-500">
                      PDF or Image (JPG, PNG)
                    </p>
                    <input
                      type="file"
                      accept=".pdf,image/*"
                      className="hidden"
                      onChange={(e) => {
                        if (e.target.files?.[0]) {
                          setSymptoms(`Uploaded: ${e.target.files[0].name}`);
                        }
                      }}
                    />
                  </div>
                </div>
              )}

              {/* Error Display */}
              {error && (
                <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl flex items-center gap-3">
                  <XCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
                  <p className="text-sm text-red-700">{error}</p>
                </div>
              )}

              {/* Submit Button */}
              <button
                onClick={handleSubmitSymptoms}
                disabled={!symptoms.trim() || isLoading}
                className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 disabled:from-gray-400 disabled:to-gray-400 text-white font-semibold py-4 rounded-xl transition-all flex items-center justify-center gap-2 shadow-lg"
              >
                {isLoading ? (
                  <>
                    <Loader className="w-5 h-5 animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  <>
                    <Send className="w-5 h-5" />
                    Get AI Assessment
                  </>
                )}
              </button>
            </motion.div>
          )}

          {/* Processing Step */}
          {step === 'processing' && (
            <motion.div
              key="processing"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="bg-white rounded-2xl shadow-xl p-12 text-center"
            >
              <div className="flex flex-col items-center">
                <div className="relative">
                  <div className="w-24 h-24 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
                  <Heart className="w-10 h-10 text-blue-600 absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2" />
                </div>
                <h3 className="text-2xl font-bold text-gray-800 mt-6 mb-2">
                  Analyzing Your Symptoms
                </h3>
                <p className="text-gray-600">
                  Our AI is assessing your health condition...
                </p>
              </div>
            </motion.div>
          )}

          {/* Results Step */}
          {step === 'results' && triageResult && (
            <motion.div
              key="results"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="max-w-4xl mx-auto space-y-6"
            >
              {/* Header */}
              <div className="bg-gradient-to-r from-slate-800 to-slate-900 rounded-2xl shadow-2xl p-8 text-white">
                <h1 className="text-3xl font-bold mb-2">Your Health Assessment Results</h1>
                <div className="flex items-center gap-4 text-sm text-slate-300">
                  <div className="flex items-center gap-2">
                    <Clock className="w-4 h-4" />
                    <span>{new Date(triageResult.created_at).toLocaleString()}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <User className="w-4 h-4" />
                    <span>ID: {triageResult.triage_id}</span>
                  </div>
                </div>
              </div>

              {/* Risk Level Badge */}
              <div className={`${getRiskColor(triageResult.risk_level)} rounded-2xl shadow-xl p-6 text-white`}>
                <div className="flex items-center gap-4">
                  <CheckCircle className="w-8 h-8" />
                  <div className="flex-1">
                    <h2 className="text-2xl font-bold capitalize mb-1">
                      {triageResult.risk_level} risk — {triageResult.risk_probability || (triageResult.confidence * 100).toFixed(0)}% probability
                    </h2>
                    <p className="text-white/90 text-sm">
                      {triageResult.reasoning.split('.')[0]}.
                    </p>
                  </div>
                </div>
              </div>

              {/* Possible Conditions with Probabilities */}
              {triageResult.possible_conditions && triageResult.possible_conditions.length > 0 && (
                <div className="bg-slate-800 rounded-2xl shadow-xl p-6 text-white">
                  <h3 className="text-lg font-semibold mb-4">Likely Culprits</h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {triageResult.possible_conditions.slice(0, 4).map((condition, index) => {
                      const conditionName = typeof condition === 'string' ? condition : ((condition as any).disease_name || (condition as any).name);
                      const probability = typeof condition === 'object' && condition.probability
                        ? condition.probability
                        : Math.max(30, 50 - index * 5);

                      return (
                        <div key={index} className="bg-slate-700 rounded-xl p-4 text-center">
                          <div className="text-sm font-medium mb-1">{conditionName.split(' ').slice(0, 2).join(' ')}</div>
                          <div className="text-2xl font-bold">{probability}%</div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Recommendations Section */}
              <div className="bg-slate-800 rounded-2xl shadow-xl p-6 text-white">
                <h3 className="text-lg font-semibold mb-4">Recommendations</h3>
                <div className="space-y-3">
                  {triageResult.recommendations.map((rec, index) => {
                    const recText = typeof rec === 'string' ? rec : rec.text;
                    const recType = typeof rec === 'object' && rec.type ? rec.type : 'action';

                    return (
                      <div key={index} className="flex items-start gap-3">
                        <CheckCircle className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
                        <p className="text-slate-200 leading-relaxed">
                          {recType === 'action' && <strong className="text-white">Self-care recommended</strong>}
                          {recType === 'dietary' && <strong className="text-white">Dietary advice</strong>}
                          {recType === 'lifestyle' && <strong className="text-white">Lifestyle change</strong>}
                          {recType !== 'action' && recType !== 'dietary' && recType !== 'lifestyle' && ' - '}
                          {recText}
                        </p>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Suggested Facilities/Actions */}
              <div className="bg-slate-800 rounded-2xl shadow-xl p-6 text-white">
                <h3 className="text-lg font-semibold mb-4">Suggested Facilities/Actions:</h3>
                <ul className="space-y-2 text-slate-200">
                  <li className="flex items-start gap-2">
                    <span className="text-slate-400">•</span>
                    <span>Monitor symptoms at home</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-slate-400">•</span>
                    <span>Consult local healthcare provider if symptoms worsen</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-slate-400">•</span>
                    <span>Maintain hydration and rest</span>
                  </li>
                </ul>
              </div>

              {/* Expandable Detailed Analysis */}
              <div className="bg-slate-800 rounded-2xl shadow-xl overflow-hidden">
                <button
                  onClick={() => toggleSection('analysis')}
                  className="w-full px-6 py-4 flex items-center justify-between text-white hover:bg-slate-700 transition-colors"
                >
                  <h3 className="text-lg font-semibold">View Detailed Analysis</h3>
                  {expandedSection === 'analysis' ? (
                    <ChevronUp className="w-5 h-5" />
                  ) : (
                    <ChevronDown className="w-5 h-5" />
                  )}
                </button>

                <AnimatePresence>
                  {expandedSection === 'analysis' && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="border-t border-slate-700"
                    >
                      <div className="p-6 space-y-4 text-slate-200">
                        <div>
                          <h4 className="font-semibold text-white mb-2">Ideal Likely Condition:</h4>
                          <p className="leading-relaxed">
                            {triageResult.possible_conditions.length > 0
                              ? (typeof triageResult.possible_conditions[0] === 'string'
                                ? triageResult.possible_conditions[0]
                                : triageResult.possible_conditions[0].name)
                              : 'General viral infection or minor condition'}
                          </p>
                        </div>

                        <div>
                          <h4 className="font-semibold text-white mb-2">Medical Reasoning:</h4>
                          <p className="leading-relaxed">{triageResult.reasoning}</p>
                        </div>

                        <div>
                          <h4 className="font-semibold text-white mb-2">Confidence Level:</h4>
                          <div className="flex items-center gap-4">
                            <div className="flex-1 bg-slate-700 rounded-full h-3 overflow-hidden">
                              <div
                                className="bg-green-500 h-full rounded-full transition-all duration-500"
                                style={{ width: `${(triageResult.confidence * 100)}%` }}
                              />
                            </div>
                            <span className="font-semibold">{(triageResult.confidence * 100).toFixed(0)}%</span>
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* Health Summary Section */}
              <div className="bg-slate-800 rounded-2xl shadow-xl p-6 text-white">
                <h3 className="text-lg font-semibold mb-4">Your Health Summary</h3>
                <p className="text-slate-300 mb-6">
                  Download a complete summary of this consultation for your records or to share with a doctor.
                </p>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <button
                    onClick={handleDownloadPDF}
                    className="flex items-center justify-center gap-2 bg-slate-700 hover:bg-slate-600 px-6 py-3 rounded-xl transition-colors"
                  >
                    <Download className="w-5 h-5" />
                    <span>Download PDF Health Summary</span>
                  </button>

                  <button
                    onClick={handleShareWhatsApp}
                    className="flex items-center justify-center gap-2 bg-green-600 hover:bg-green-500 px-6 py-3 rounded-xl transition-colors"
                  >
                    <Share2 className="w-5 h-5" />
                    <span>Share via WhatsApp</span>
                  </button>

                  <button
                    onClick={handleShareEmail}
                    className="flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-500 px-6 py-3 rounded-xl transition-colors"
                  >
                    <Mail className="w-5 h-5" />
                    <span>Share via Email</span>
                  </button>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-4 pb-8">
                <button
                  onClick={handleNewConsultation}
                  className="flex-1 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white font-semibold py-4 rounded-xl transition-all shadow-lg"
                >
                  Start New Health Assessment
                </button>
                <button
                  onClick={() => window.history.back()}
                  className="px-8 bg-slate-700 hover:bg-slate-600 text-white font-semibold py-4 rounded-xl transition-all"
                >
                  Logout
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};

export default ConsultationFlow;
