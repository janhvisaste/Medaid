import React, { useState, useRef } from 'react';
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
  Loader2,
  Upload,
  MapPin,
  ChevronDown,
  ChevronUp,
  Hospital,
  ShieldCheck,
  ShieldAlert
} from 'lucide-react';
import apiService from '../../services/apiService';
import type { ConsultationSession, Facility } from '../../services/apiService';
import FacilitiesMap from './FacilitiesMap';

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

  // Step 0: Consultation Room Inputs
  const [symptoms, setSymptoms] = useState('');
  const [pincode, setPincode] = useState('411046'); // Default from image
  const [city, setCity] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Step 1: Medical History
  const [selectedConditions, setSelectedConditions] = useState<{ [key: string]: { selected: boolean; notes: string } }>({});

  // Step 2: Clarifying Questions
  const [questions, setQuestions] = useState<Question[]>([]);

  // Step 3: Results
  const [assessment, setAssessment] = useState<any>(null);
  const [showJson, setShowJson] = useState(false);
  const [nearbyFacilities, setNearbyFacilities] = useState<Facility[]>([]);
  const [loadingFacilities, setLoadingFacilities] = useState(false);

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const steps = [
    { title: 'Consultation', icon: FileText },
    { title: 'History', icon: ClipboardCheck },
    { title: 'Clarify', icon: MessageCircle },
    { title: 'Results', icon: Activity }
  ];

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setSelectedFile(e.dataTransfer.files[0]);
    }
  };

  const startAnalysis = async () => {
    if (!symptoms.trim() && !selectedFile) {
      setError('Please describe your symptoms or upload a report');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      let reportId = null;

      // 1. Upload file if exists
      if (selectedFile) {
        try {
          const formData = new FormData();
          formData.append('file', selectedFile);
          formData.append('description', 'Consultation Upload');
          
          const reportResult = await apiService.uploadMedicalReport(formData);
          // Start analysis on the report to get structured data
          const analysisResult = await apiService.analyzeMedicalReport(reportResult.id);
          reportId = reportResult.id;

          // Pre-fill symptoms if analysis extracted text and user left it blank
          if (!symptoms && analysisResult.extracted_text) {
            setSymptoms(analysisResult.extracted_text.substring(0, 500) + '...');
          }
        } catch (uploadErr) {
          console.error("File upload failed", uploadErr);
          setError("Failed to upload file. Continuing with text symptoms only.");
        }
      }

      // 2. Start Consultation Session
      // We pass report_id, pincode as context in a way the backend hopefully understands or we handle it later

      const result = await apiService.startConsultation(symptoms);
      setSession(result.session);

      // Store location/report info in local state for later usage if needed, 
      // or ideally we would pass it to the backend. 
      // For now, let's assume valid session started.

      // If we have report info that needs to be part of history context:
      // We will inject this into the next step's payload or a separate update if needed.
      // For now, we proceed to Medical History.

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
          .map(([name, value]) => ({ name, notes: value.notes })),
        // Add the consultation context here
        pincode: pincode,
        city: city,
        has_file: !!selectedFile
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
        const history = await apiService.getTriageHistory();
        const latestAssessment = history.find(t => t.id === finalResult.session.triage_id);
        setAssessment(latestAssessment);

        // Fetch nearby facilities immediately
        if (latestAssessment) {
          fetchFacilities(latestAssessment.risk_level);
        }
      }

      setCurrentStep(3);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to submit answers');
    } finally {
      setLoading(false);
    }
  };

  const fetchFacilities = async (riskLevel: string) => {
    setLoadingFacilities(true);
    try {
      // Use the pincode entered earlier or default
      const loc = pincode || 'Pune';
      const facilities = await apiService.getNearbyFacilities({
        location: loc,
        risk_level: riskLevel,
        radius: 10
      });
      setNearbyFacilities(facilities);
    } catch (e) {
      console.error("Failed to fetch facilities", e);
    } finally {
      setLoadingFacilities(false);
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
    switch (risk?.toLowerCase()) {
      case 'emergency': return 'bg-red-500 text-white';
      case 'high': return 'bg-orange-500 text-white';
      case 'medium': return 'bg-yellow-500 text-white';
      case 'low': return 'bg-green-600 text-white';
      default: return 'bg-gray-500 text-white';
    }
  };

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const getRiskBadgeColor = (risk: string) => {
    switch (risk?.toLowerCase()) {
      case 'emergency': return 'bg-red-100 text-red-800 border-red-200';
      case 'high': return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'medium': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'low': return 'bg-green-100 text-green-800 border-green-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
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
      [condition]: { ...prev[condition], notes }
    }));
  };

  const updateAnswer = (index: number, answer: string) => {
    setQuestions(prev => prev.map((q, i) => i === index ? { ...q, answer } : q));
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-3">
              <Activity className="text-blue-600" />
              Medical Assessment Agent
            </h1>
            <p className="text-gray-500 mt-1">AI-powered triage and health analysis</p>
          </div>
          {currentStep > 0 && session && (
            <button
              onClick={() => {
                setCurrentStep(0);
                setSession(null);
                setSymptoms('');
                setAssessment(null);
                setError(null);
              }}
              className="text-sm text-gray-500 hover:text-gray-700 underline"
            >
              Start Over
            </button>
          )}
        </div>

        {/* Consultation Room (Step 0) - Dark Theme Card */}
        {currentStep === 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-slate-900 rounded-2xl shadow-xl overflow-hidden text-white border border-slate-700"
          >
            <div className="p-8">
              <h2 className="text-2xl font-bold mb-2">Consultation Room</h2>
              <p className="text-slate-400 mb-8">Provide current symptoms (text). Optionally upload a medical report.</p>

              <div className="space-y-6">
                {/* Symptoms Input */}
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    Describe current symptoms (required if no report)
                  </label>
                  <textarea
                    value={symptoms}
                    onChange={(e) => setSymptoms(e.target.value)}
                    rows={4}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg p-4 text-white placeholder-slate-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                    placeholder="e.g. stomach pain, unable to eat anything..."
                  />
                </div>

                {/* File Upload */}
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    Upload medical report (PDF / image) — optional
                  </label>
                  <div
                    className="border-2 border-dashed border-slate-700 bg-slate-800/50 rounded-lg p-8 flex flex-col items-center justify-center cursor-pointer hover:bg-slate-800 transition-colors"
                    onDragOver={handleDragOver}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                  >
                    <input
                      type="file"
                      ref={fileInputRef}
                      className="hidden"
                      onChange={handleFileChange}
                      accept=".pdf,.png,.jpg,.jpeg"
                    />

                    {selectedFile ? (
                      <div className="flex items-center gap-3 text-green-400 bg-green-900/20 px-4 py-2 rounded-full">
                        <FileText size={20} />
                        <span className="font-medium">{selectedFile.name}</span>
                      </div>
                    ) : (
                      <>
                        <div className="bg-slate-700 p-3 rounded-full mb-3">
                          <Upload className="text-slate-300" size={24} />
                        </div>
                        <p className="text-slate-300 font-medium">Drag and drop file here</p>
                        <p className="text-slate-500 text-sm mt-1">Limit 200MB per file • PDF, PNG, JPG, JPEG</p>
                        <button className="mt-4 px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-md text-sm font-medium transition-colors">
                          Browse files
                        </button>
                      </>
                    )}
                  </div>
                </div>

                {/* City / Pincode */}
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">
                    City / Pincode (for recommendations)
                  </label>
                  <input
                    type="text"
                    value={pincode}
                    onChange={(e) => setPincode(e.target.value)}
                    placeholder="Enter pincode or city name"
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-white placeholder-slate-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                </div>

                {/* Action Button */}
                <div className="pt-4">
                  <button
                    onClick={startAnalysis}
                    disabled={loading}
                    className="w-full md:w-auto bg-blue-600 hover:bg-blue-500 text-white font-semibold py-3 px-8 rounded-lg transition-colors flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {loading ? (
                      <>
                        <Loader2 className="animate-spin" size={20} />
                        Running assessment...
                      </>
                    ) : (
                      <>
                        Analyze Now
                        <ArrowRight size={20} />
                      </>
                    )}
                  </button>
                  {error && (
                    <p className="mt-3 text-red-400 text-sm flex items-center gap-2">
                      <AlertCircle size={16} />
                      {error}
                    </p>
                  )}
                </div>
              </div>
            </div>

            {/* Status Bar */}
            <div className="bg-slate-950 px-8 py-4 border-t border-slate-800">
              <div className="flex items-center gap-2 text-sm text-slate-400">
                <div className={`w-2 h-2 rounded-full ${loading ? 'bg-blue-500 animate-pulse' : 'bg-green-500'}`}></div>
                {loading ? 'Processing data...' : 'System ready'}
              </div>
            </div>
          </motion.div>
        )}

        {/* Steps 1 & 2 (History / Questions) - Kept mostly same but cleaner */}
        {(currentStep === 1 || currentStep === 2) && (
          <motion.div
            key={currentStep}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            className="bg-white rounded-2xl shadow-xl p-8 border border-gray-200"
          >
            {currentStep === 1 && (
              <div className="space-y-6">
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center text-blue-600">
                    <ClipboardCheck size={20} />
                  </div>
                  <div>
                    <h2 className="text-2xl font-bold text-gray-900">Medical History</h2>
                    <p className="text-gray-500">Select any pre-existing conditions</p>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {MEDICAL_CONDITIONS.map((condition) => (
                    <div key={condition}
                      className={`border rounded-lg p-4 transition-all cursor-pointer ${selectedConditions[condition]?.selected
                        ? 'border-blue-500 bg-blue-50 shadow-sm'
                        : 'border-gray-200 hover:border-blue-300'
                        }`}
                      onClick={() => toggleCondition(condition)}
                    >
                      <label className="flex items-start gap-3 cursor-pointer pointer-events-none">
                        <input
                          type="checkbox"
                          checked={selectedConditions[condition]?.selected || false}
                          readOnly
                          className="mt-1 w-5 h-5 text-blue-600 rounded focus:ring-blue-500"
                        />
                        <div className="flex-1">
                          <span className={`font-medium ${selectedConditions[condition]?.selected ? 'text-blue-900' : 'text-gray-900'}`}>{condition}</span>
                          {selectedConditions[condition]?.selected && (
                            <input
                              type="text"
                              placeholder="Add notes..."
                              value={selectedConditions[condition]?.notes || ''}
                              onChange={(e) => updateNotes(condition, e.target.value)}
                              className="mt-2 w-full px-2 py-1 text-sm border-b border-blue-200 bg-transparent focus:border-blue-500 focus:outline-none pointer-events-auto"
                              onClick={(e) => e.stopPropagation()}
                            />
                          )}
                        </div>
                      </label>
                    </div>
                  ))}
                </div>

                <div className="flex gap-4 pt-4">
                  <button onClick={() => setCurrentStep(0)} className="px-6 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 font-medium">Back</button>
                  <button
                    onClick={handleSubmitHistory}
                    disabled={loading}
                    className="flex-1 bg-blue-600 hover:bg-blue-700 text-white py-3 rounded-lg font-medium flex items-center justify-center gap-2"
                  >
                    {loading ? <Loader2 className="animate-spin" /> : <>Continue <ArrowRight size={20} /></>}
                  </button>
                </div>
              </div>
            )}

            {currentStep === 2 && (
              <div className="space-y-6">
                <div className="flex items-center gap-3 mb-6">
                  <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center text-blue-600">
                    <MessageCircle size={20} />
                  </div>
                  <div>
                    <h2 className="text-2xl font-bold text-gray-900">Clarifying Questions</h2>
                    <p className="text-gray-500">Help us refine the assessment</p>
                  </div>
                </div>

                <div className="space-y-6">
                  {questions.map((question, index) => (
                    <div key={index} className="bg-gray-50 rounded-xl p-6 border border-gray-100">
                      <label className="block text-lg font-medium text-gray-900 mb-3">
                        {index + 1}. {question.question}
                      </label>

                      {question.type === 'text' ? (
                        <textarea
                          value={question.answer || ''}
                          onChange={(e) => updateAnswer(index, e.target.value)}
                          rows={2}
                          className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                          placeholder="Type your answer here..."
                        />
                      ) : question.type === 'yes_no' ? (
                        <div className="flex gap-3 max-w-xs">
                          <button
                            onClick={() => updateAnswer(index, 'Yes')}
                            className={`flex-1 py-2 rounded-lg font-medium border ${question.answer === 'Yes'
                              ? 'bg-blue-600 text-white border-blue-600'
                              : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                              }`}
                          >
                            Yes
                          </button>
                          <button
                            onClick={() => updateAnswer(index, 'No')}
                            className={`flex-1 py-2 rounded-lg font-medium border ${question.answer === 'No'
                              ? 'bg-blue-600 text-white border-blue-600'
                              : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                              }`}
                          >
                            No
                          </button>
                        </div>
                      ) : (
                        <div className="space-y-2">
                          <input
                            type="range"
                            min="1"
                            max="10"
                            value={question.answer || '5'}
                            onChange={(e) => updateAnswer(index, e.target.value)}
                            className="w-full"
                          />
                          <div className="flex justify-between text-sm text-gray-600">
                            <span>Mild (1)</span>
                            <span className="font-bold text-blue-600">{question.answer || '5'}</span>
                            <span>Severe (10)</span>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>

                <div className="flex gap-4 pt-4">
                  <button onClick={() => setCurrentStep(1)} className="px-6 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 font-medium">Back</button>
                  <button
                    onClick={handleSubmitQuestions}
                    disabled={loading}
                    className="flex-1 bg-blue-600 hover:bg-blue-700 text-white py-3 rounded-lg font-medium flex items-center justify-center gap-2"
                  >
                    {loading ? <Loader2 className="animate-spin" /> : <>Get Results <ArrowRight size={20} /></>}
                  </button>
                </div>
              </div>
            )}
          </motion.div>
        )}

        {/* Results (Step 3) - Dark Theme Replicated within Layout */}
        {currentStep === 3 && assessment && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="space-y-6"
          >
            {/* JSON View (Collapsible) */}
            <div className="bg-slate-950 rounded-lg overflow-hidden border border-slate-800">
              <button
                onClick={() => setShowJson(!showJson)}
                className="w-full px-4 py-2 bg-slate-900 text-slate-400 text-xs font-mono flex items-center justify-between hover:text-white transition-colors"
              >
                <span>{showJson ? 'Hide' : 'Show'} raw response JSON</span>
                {showJson ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </button>
              {showJson && (
                <pre className="p-4 text-xs font-mono text-green-400 overflow-x-auto max-h-60 custom-scrollbar">
                  {JSON.stringify({
                    risk: assessment.risk_level,
                    probability: assessment.confidence,
                    conditions: assessment.possible_conditions,
                    reasoning: assessment.reasoning
                  }, null, 2)}
                </pre>
              )}
            </div>

            {/* Main Results Card */}
            <div className={`rounded-xl overflow-hidden shadow-lg text-white ${getRiskColor(assessment.risk_level)}`}>
              <div className="p-8">
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-3xl font-bold mb-2 flex items-center gap-3">
                      {assessment.risk_level === 'low' && <ShieldCheck size={32} />}
                      {assessment.risk_level !== 'low' && <ShieldAlert size={32} />}
                      {assessment.risk_level.charAt(0).toUpperCase() + assessment.risk_level.slice(1)} Risk Assessment
                    </h2>
                    <p className="text-white/80 text-lg">
                      {assessment.risk_level === 'low'
                        ? 'Your symptoms match mostly mild cases that can typically be managed with self-care.'
                        : 'Your symptoms suggest a potential condition that may require professional medical attention.'}
                    </p>
                  </div>
                  <div className="hidden md:block bg-white/20 backdrop-blur-md rounded-lg p-4 text-center min-w-[120px]">
                    <div className="text-3xl font-bold">{(assessment.confidence * 100).toFixed(0)}%</div>
                    <div className="text-sm opacity-80">Confidence</div>
                  </div>
                </div>
              </div>

              {assessment.risk_level === 'low' && (
                <div className="bg-white/10 px-8 py-4 backdrop-blur-sm border-t border-white/10">
                  <div className="flex items-center gap-2 font-medium">
                    <Check className="bg-white text-green-600 rounded-full p-0.5" size={20} />
                    Self-care recommended - Continue monitoring symptoms.
                  </div>
                </div>
              )}
            </div>

            {/* Results Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Detailed Analysis */}
              <div className="bg-white rounded-xl shadow-lg border border-gray-100 p-6">
                <h3 className="text-lg font-bold text-gray-900 mb-4 flex items-center gap-2">
                  <Activity className="text-blue-600" size={20} />
                  Detailed Analysis
                </h3>
                <div className="space-y-4">
                  <div className="bg-gray-50 rounded-lg p-4">
                    <p className="text-sm text-gray-500 mb-1">Medical Reasoning</p>
                    <p className="text-gray-800 leading-relaxed text-sm">
                      {assessment.reasoning}
                    </p>
                  </div>

                  <div>
                    <p className="text-sm text-gray-500 mb-2">Likely Conditions</p>
                    <div className="flex flex-wrap gap-2">
                      {assessment.possible_conditions?.map((idx: any, i: number) => (
                        <span key={i} className="px-3 py-1 bg-slate-800 text-white text-sm rounded-full shadow-sm">
                          {typeof idx === 'string' ? idx : idx.disease_name}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div>
                    <p className="text-sm text-gray-500 mb-2">Recommendations</p>
                    <ul className="space-y-2">
                      {assessment.recommendations?.slice(0, 4).map((rec: any, i: number) => (
                        <li key={i} className="flex items-start gap-3">
                          <div className="mt-1 min-w-[6px] h-1.5 rounded-full bg-blue-500"></div>
                          <span className="text-sm text-gray-700">{typeof rec === 'string' ? rec : rec.description}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>

              {/* Nearby Facilities */}
              <div className="bg-slate-900 rounded-xl shadow-lg border border-slate-800 p-6 text-white min-h-[400px]">
                <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                  <Hospital className="text-blue-400" size={20} />
                  Nearby Facilities
                </h3>

                <div className="flex items-center gap-2 mb-4 text-xs text-slate-400 bg-slate-800 p-2 rounded">
                  <MapPin size={12} />
                  <span>Finding aid near: <span className="text-white font-medium">{pincode || 'Pune'}</span></span>
                </div>

                {loadingFacilities ? (
                  <div className="flex items-center justify-center h-40">
                    <Loader2 className="animate-spin text-blue-500" />
                  </div>
                ) : nearbyFacilities.length > 0 ? (
                  <div className="space-y-4">
                    <FacilitiesMap facilities={nearbyFacilities} />
                    <div className="space-y-4 max-h-[300px] overflow-y-auto custom-scrollbar pr-2">
                    {nearbyFacilities.map((facility, i) => (
                      <div key={i} className="bg-slate-800 rounded-lg p-3 hover:bg-slate-700 transition-colors border border-slate-700">
                        <div className="font-semibold text-blue-200">{facility.name}</div>
                        <div className="text-xs text-slate-400 mt-1">{facility.address}</div>
                        <div className="flex items-center justify-between mt-3 text-xs">
                          <span className="bg-slate-900 px-2 py-1 rounded text-slate-300">
                            {facility.distance_km ? `${facility.distance_km.toFixed(1)} km` : 'Near you'}
                          </span>
                        </div>
                      </div>
                    ))}
                    </div>
                  </div>
                ) : (
                  <div className="text-center text-slate-500 py-10">
                    <Hospital className="mx-auto mb-2 opacity-20" size={32} />
                    <p>No facilities found nearby.</p>
                  </div>
                )}
              </div>
            </div>

            {/* Actions Footer */}
            <div className="flex flex-col md:flex-row gap-4 mt-8">
              <button
                onClick={handleDownloadPDF}
                disabled={loading}
                className="flex-1 bg-green-600 text-white py-3 rounded-lg font-medium hover:bg-green-700 transition-colors flex items-center justify-center gap-2"
              >
                <Download size={20} />
                Download Health Summary
              </button>
              <div className="flex gap-2 flex-1">
                <button
                  onClick={() => { }}
                  className="flex-1 bg-white border border-gray-300 text-gray-700 py-3 rounded-lg font-medium hover:bg-gray-50 flex items-center justify-center gap-2"
                >
                  Share via WhatsApp
                </button>
                <button
                  onClick={() => {
                    setCurrentStep(0);
                    setSession(null);
                    setSymptoms('');
                    setAssessment(null);
                  }}
                  className="flex-1 bg-blue-600 text-white py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors flex items-center justify-center gap-2"
                >
                  New Assessment
                </button>
              </div>
            </div>
          </motion.div>
        )}

      </div>
    </div>
  );
};

export default ConsultationWizard;
