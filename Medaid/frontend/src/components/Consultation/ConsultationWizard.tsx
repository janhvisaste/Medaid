import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  ArrowRight, 
  ArrowLeft, 
  Check, 
  AlertCircle,
  FileText,
  ClipboardCheck,
  MessageCircle,
  Activity,
  Download,
  Loader2
} from 'lucide-react';
import apiService from '../../services/apiService';
import type { ConsultationSession } from '../../services/apiService';

interface Question {
  question: string;
  type: 'text' | 'yes_no' | 'scale';
  answer?: string;
}

const MEDICAL_CONDITIONS = [
  'Diabetes',
  'Hypertension',
  'Heart Disease',
  'Asthma',
  'Thyroid Disorders',
  'Kidney Disease',
  'Liver Disease',
  'Cancer',
  'Arthritis',
  'Mental Health Conditions',
  'Allergies',
  'COPD'
];

const ConsultationWizard: React.FC = () => {
  const [currentStep, setCurrentStep] = useState(0);
  const [session, setSession] = useState<ConsultationSession | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Step 1: Symptoms
  const [symptoms, setSymptoms] = useState('');

  // Step 2: Medical History
  const [selectedConditions, setSelectedConditions] = useState<{[key: string]: { selected: boolean; notes: string }}>({});

  // Step 3: Clarifying Questions
  const [questions, setQuestions] = useState<Question[]>([]);

  // Step 4: Results
  const [assessment, setAssessment] = useState<any>(null);

  const steps = [
    { title: 'Symptoms', icon: FileText },
    { title: 'Medical History', icon: ClipboardCheck },
    { title: 'Questions', icon: MessageCircle },
    { title: 'Results', icon: Activity }
  ];

  const handleStartConsultation = async () => {
    if (!symptoms.trim()) {
      setError('Please describe your symptoms');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await apiService.startConsultation(symptoms);
      setSession(result.session);
      setCurrentStep(1);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to start consultation');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitHistory = async () => {
    if (!session) return;

    setLoading(true);
    setError(null);

    try {
      const medicalHistory = {
        conditions: Object.entries(selectedConditions)
          .filter(([_, value]) => value.selected)
          .map(([name, value]) => ({ name, notes: value.notes }))
      };

      const result = await apiService.submitConsultationStep(session.id, { medical_history: medicalHistory });
      setSession(result.session);

      // Get clarifying questions
      const questionsResult = await apiService.getClarifyingQuestions(session.id);
      setQuestions(questionsResult.questions.map(q => ({ ...q, answer: '' })));
      
      setCurrentStep(2);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to submit medical history');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitQuestions = async () => {
    if (!session) return;

    // Validate all questions answered
    const unanswered = questions.filter(q => !q.answer || q.answer.trim() === '');
    if (unanswered.length > 0) {
      setError('Please answer all questions');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const answers = questions.map(q => ({
        question: q.question,
        answer: q.answer
      }));

      const result = await apiService.submitConsultationStep(session.id, { answers });
      setSession(result.session);

      // Final assessment
      const finalResult = await apiService.submitConsultationStep(session.id, {});
      
      if (finalResult.session.triage_id) {
        // Fetch the triage record details
        const history = await apiService.getTriageHistory();
        const latestAssessment = history.find(t => t.id === finalResult.session.triage_id);
        setAssessment(latestAssessment);
      }

      setCurrentStep(3);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to submit answers');
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadPDF = async () => {
    if (!assessment) return;

    setLoading(true);
    try {
      const blob = await apiService.downloadAssessmentPDF(assessment.id);
      apiService.downloadPDFFile(blob, `assessment_${assessment.id}.pdf`);
    } catch (err: any) {
      setError('Failed to download PDF');
    } finally {
      setLoading(false);
    }
  };

  const getRiskColor = (risk: string) => {
    switch (risk) {
      case 'emergency': return 'text-red-600 bg-red-50';
      case 'high': return 'text-orange-600 bg-orange-50';
      case 'medium': return 'text-yellow-600 bg-yellow-50';
      case 'low': return 'text-green-600 bg-green-50';
      default: return 'text-gray-600 bg-gray-50';
    }
  };

  const toggleCondition = (condition: string) => {
    setSelectedConditions(prev => ({
      ...prev,
      [condition]: {
        selected: !prev[condition]?.selected,
        notes: prev[condition]?.notes || ''
      }
    }));
  };

  const updateNotes = (condition: string, notes: string) => {
    setSelectedConditions(prev => ({
      ...prev,
      [condition]: {
        ...prev[condition],
        notes
      }
    }));
  };

  const updateAnswer = (index: number, answer: string) => {
    setQuestions(prev => prev.map((q, i) => i === index ? { ...q, answer } : q));
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 py-12 px-4">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">Health Consultation</h1>
          <p className="text-gray-600">Complete assessment in 4 simple steps</p>
        </div>

        {/* Progress Steps */}
        <div className="mb-12">
          <div className="flex justify-between items-center">
            {steps.map((step, index) => (
              <div key={index} className="flex-1 relative">
                <div className="flex flex-col items-center">
                  <motion.div
                    className={`w-12 h-12 rounded-full flex items-center justify-center ${
                      index <= currentStep
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-200 text-gray-400'
                    }`}
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ delay: index * 0.1 }}
                  >
                    {index < currentStep ? (
                      <Check size={24} />
                    ) : (
                      <step.icon size={24} />
                    )}
                  </motion.div>
                  <span className={`mt-2 text-sm font-medium ${
                    index <= currentStep ? 'text-gray-900' : 'text-gray-400'
                  }`}>
                    {step.title}
                  </span>
                </div>
                {index < steps.length - 1 && (
                  <div className={`absolute top-6 left-1/2 w-full h-0.5 ${
                    index < currentStep ? 'bg-blue-600' : 'bg-gray-200'
                  }`} style={{ transform: 'translateY(-50%)' }} />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Error Message */}
        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3"
            >
              <AlertCircle className="text-red-600 flex-shrink-0" size={20} />
              <p className="text-red-800">{error}</p>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Step Content */}
        <AnimatePresence mode="wait">
          <motion.div
            key={currentStep}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="bg-white rounded-2xl shadow-xl p-8"
          >
            {/* Step 0: Symptoms */}
            {currentStep === 0 && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-2xl font-bold text-gray-900 mb-2">Describe Your Symptoms</h2>
                  <p className="text-gray-600">Tell us what you're experiencing. Be as detailed as possible.</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Symptoms Description *
                  </label>
                  <textarea
                    value={symptoms}
                    onChange={(e) => setSymptoms(e.target.value)}
                    rows={6}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="e.g., I have been experiencing severe headache for the past 3 days, along with mild fever and body aches..."
                  />
                </div>

                <button
                  onClick={handleStartConsultation}
                  disabled={loading || !symptoms.trim()}
                  className="w-full bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? (
                    <>
                      <Loader2 className="animate-spin" size={20} />
                      Starting...
                    </>
                  ) : (
                    <>
                      Continue
                      <ArrowRight size={20} />
                    </>
                  )}
                </button>
              </div>
            )}

            {/* Step 1: Medical History */}
            {currentStep === 1 && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-2xl font-bold text-gray-900 mb-2">Past Medical History</h2>
                  <p className="text-gray-600">Select any conditions you have been diagnosed with.</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {MEDICAL_CONDITIONS.map((condition) => (
                    <div key={condition} className="border border-gray-200 rounded-lg p-4 hover:border-blue-300 transition-colors">
                      <label className="flex items-start gap-3 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={selectedConditions[condition]?.selected || false}
                          onChange={() => toggleCondition(condition)}
                          className="mt-1 w-5 h-5 text-blue-600 rounded focus:ring-2 focus:ring-blue-500"
                        />
                        <div className="flex-1">
                          <span className="font-medium text-gray-900">{condition}</span>
                          {selectedConditions[condition]?.selected && (
                            <input
                              type="text"
                              placeholder="Add notes (optional)"
                              value={selectedConditions[condition]?.notes || ''}
                              onChange={(e) => updateNotes(condition, e.target.value)}
                              className="mt-2 w-full px-3 py-2 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                              onClick={(e) => e.stopPropagation()}
                            />
                          )}
                        </div>
                      </label>
                    </div>
                  ))}
                </div>

                <div className="flex gap-4">
                  <button
                    onClick={() => setCurrentStep(0)}
                    className="flex-1 bg-gray-100 text-gray-700 py-3 rounded-lg font-medium hover:bg-gray-200 transition-colors flex items-center justify-center gap-2"
                  >
                    <ArrowLeft size={20} />
                    Back
                  </button>
                  <button
                    onClick={handleSubmitHistory}
                    disabled={loading}
                    className="flex-1 bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    {loading ? (
                      <>
                        <Loader2 className="animate-spin" size={20} />
                        Processing...
                      </>
                    ) : (
                      <>
                        Continue
                        <ArrowRight size={20} />
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}

            {/* Step 2: Clarifying Questions */}
            {currentStep === 2 && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-2xl font-bold text-gray-900 mb-2">Clarifying Questions</h2>
                  <p className="text-gray-600">Please answer these questions to help us better understand your condition.</p>
                </div>

                <div className="space-y-6">
                  {questions.map((question, index) => (
                    <div key={index} className="border border-gray-200 rounded-lg p-6">
                      <label className="block font-medium text-gray-900 mb-3">
                        {index + 1}. {question.question}
                      </label>

                      {question.type === 'text' && (
                        <textarea
                          value={question.answer || ''}
                          onChange={(e) => updateAnswer(index, e.target.value)}
                          rows={3}
                          className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                          placeholder="Type your answer here..."
                        />
                      )}

                      {question.type === 'yes_no' && (
                        <div className="flex gap-4">
                          <button
                            onClick={() => updateAnswer(index, 'Yes')}
                            className={`flex-1 py-3 rounded-lg font-medium transition-colors ${
                              question.answer === 'Yes'
                                ? 'bg-blue-600 text-white'
                                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                            }`}
                          >
                            Yes
                          </button>
                          <button
                            onClick={() => updateAnswer(index, 'No')}
                            className={`flex-1 py-3 rounded-lg font-medium transition-colors ${
                              question.answer === 'No'
                                ? 'bg-blue-600 text-white'
                                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                            }`}
                          >
                            No
                          </button>
                        </div>
                      )}

                      {question.type === 'scale' && (
                        <div>
                          <input
                            type="range"
                            min="1"
                            max="10"
                            value={question.answer || '5'}
                            onChange={(e) => updateAnswer(index, e.target.value)}
                            className="w-full"
                          />
                          <div className="flex justify-between text-sm text-gray-600 mt-2">
                            <span>1 (Mild)</span>
                            <span className="font-medium text-blue-600">{question.answer || '5'}</span>
                            <span>10 (Severe)</span>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>

                <div className="flex gap-4">
                  <button
                    onClick={() => setCurrentStep(1)}
                    className="flex-1 bg-gray-100 text-gray-700 py-3 rounded-lg font-medium hover:bg-gray-200 transition-colors flex items-center justify-center gap-2"
                  >
                    <ArrowLeft size={20} />
                    Back
                  </button>
                  <button
                    onClick={handleSubmitQuestions}
                    disabled={loading}
                    className="flex-1 bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    {loading ? (
                      <>
                        <Loader2 className="animate-spin" size={20} />
                        Analyzing...
                      </>
                    ) : (
                      <>
                        Get Results
                        <ArrowRight size={20} />
                      </>
                    )}
                  </button>
                </div>
              </div>
            )}

            {/* Step 3: Results */}
            {currentStep === 3 && assessment && (
              <div className="space-y-6">
                <div className="text-center">
                  <h2 className="text-2xl font-bold text-gray-900 mb-2">Assessment Complete</h2>
                  <p className="text-gray-600">Here are your consultation results</p>
                </div>

                {/* Risk Level */}
                <div className={`p-6 rounded-xl ${getRiskColor(assessment.risk_level)} border-2`}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium uppercase tracking-wide">Risk Level</span>
                    <span className="text-2xl font-bold">{assessment.risk_level.toUpperCase()}</span>
                  </div>
                  <div className="text-sm opacity-75">
                    Confidence: {(assessment.confidence * 100).toFixed(0)}%
                  </div>
                </div>

                {/* Reasoning */}
                <div className="border border-gray-200 rounded-xl p-6">
                  <h3 className="font-semibold text-gray-900 mb-3">Assessment Reasoning</h3>
                  <p className="text-gray-700 leading-relaxed">{assessment.reasoning}</p>
                </div>

                {/* Possible Conditions */}
                {assessment.possible_conditions && assessment.possible_conditions.length > 0 && (
                  <div className="border border-gray-200 rounded-xl p-6">
                    <h3 className="font-semibold text-gray-900 mb-3">Possible Conditions</h3>
                    <div className="flex flex-wrap gap-2">
                      {assessment.possible_conditions.map((condition: any, index: number) => (
                        <span
                          key={index}
                          className="px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-sm font-medium"
                        >
                          {typeof condition === 'string' ? condition : condition.disease_name}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Recommendations */}
                {assessment.recommendations && assessment.recommendations.length > 0 && (
                  <div className="border border-gray-200 rounded-xl p-6">
                    <h3 className="font-semibold text-gray-900 mb-3">Recommendations</h3>
                    <ul className="space-y-2">
                      {assessment.recommendations.map((rec: any, index: number) => (
                        <li key={index} className="flex items-start gap-3">
                          <Check className="text-green-600 flex-shrink-0 mt-0.5" size={20} />
                          <span className="text-gray-700">{typeof rec === 'string' ? rec : rec.description}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Actions */}
                <div className="flex gap-4">
                  <button
                    onClick={handleDownloadPDF}
                    disabled={loading}
                    className="flex-1 bg-green-600 text-white py-3 rounded-lg font-medium hover:bg-green-700 transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    {loading ? (
                      <>
                        <Loader2 className="animate-spin" size={20} />
                        Downloading...
                      </>
                    ) : (
                      <>
                        <Download size={20} />
                        Download PDF Report
                      </>
                    )}
                  </button>
                  <button
                    onClick={() => {
                      setCurrentStep(0);
                      setSession(null);
                      setSymptoms('');
                      setSelectedConditions({});
                      setQuestions([]);
                      setAssessment(null);
                      setError(null);
                    }}
                    className="flex-1 bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors"
                  >
                    New Consultation
                  </button>
                </div>
              </div>
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
};

export default ConsultationWizard;
