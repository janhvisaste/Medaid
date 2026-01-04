import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Menu, Home, FileText, Clock, User, Send, Mic, Upload,
  Heart, Sparkles, Sun, Moon, LogOut, X
} from 'lucide-react';
import authService from '../../services/authService';

interface Message {
  id: string;
  text: string;
  html?: string;
  sender: 'user' | 'ai';
  timestamp: Date;
  riskLevel?: 'emergency' | 'high' | 'medium' | 'low';
  triageData?: any;
}

const NewDashboard: React.FC = () => {
  const navigate = useNavigate();
  const [user, setUser] = useState<any>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [theme, setTheme] = useState<'light' | 'dark'>('dark');
  const [activeSection, setActiveSection] = useState('home');
  
  // Input modes
  const [inputMode, setInputMode] = useState<'text' | 'voice' | 'document'>('text');
  const [isRecording, setIsRecording] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Profile editing (for future use)
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [profileData, setProfileData] = useState({
    first_name: '',
    last_name: '',
    email: '',
    phone: '',
    city: '',
    state: '',
    past_history: ''
  });

  // Keep profileData in sync with user
  useEffect(() => {
    if (user) {
      setProfileData({
        first_name: user.first_name || '',
        last_name: user.last_name || '',
        email: user.email || '',
        phone: user.phone || '',
        city: user.city || '',
        state: user.state || '',
        past_history: user.past_history || ''
      });
    }
  }, [user]);

  useEffect(() => {
    checkAuthStatus();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const checkAuthStatus = async () => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      navigate('/login');
      return;
    }

    try {
      const response = await fetch('http://127.0.0.1:8000/api/auth/me/', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      const userData = await response.json();
      setUser(userData);
      setProfileData({
        first_name: userData.first_name || '',
        last_name: userData.last_name || '',
        email: userData.email || '',
        phone: userData.phone || '',
        city: userData.city || '',
        state: userData.state || '',
        past_history: userData.past_history || ''
      });
    } catch (error) {
      console.error('Auth error:', error);
      navigate('/login');
    }
  };

  const getRiskColor = (risk?: string) => {
    if (!risk) return 'bg-gray-600';
    switch (risk) {
      case 'emergency': return 'bg-red-600';
      case 'high': return 'bg-orange-600';
      case 'medium': return 'bg-yellow-600';
      case 'low': return 'bg-green-600';
      default: return 'bg-gray-600';
    }
  };

  const detectEmergency = (text: string): boolean => {
    const emergencyKeywords = [
      'severe chest pain', 'chest pain', 'heart attack',
      'difficulty breathing', 'can\'t breathe', 'shortness of breath',
      'unconscious', 'passed out', 'fainted',
      'heavy bleeding', 'bleeding heavily', 'blood loss',
      'stroke', 'seizure', 'convulsion',
      'severe head injury', 'head trauma',
      'poisoning', 'overdose'
    ];
    
    const lowerText = text.toLowerCase();
    return emergencyKeywords.some(keyword => lowerText.includes(keyword));
  };

  const handleSendMessage = async () => {
    if (!inputMessage.trim() && !uploadedFile) return;

    const isEmergency = detectEmergency(inputMessage);
    
    const userMessage: Message = {
      id: Date.now().toString(),
      text: inputMessage,
      sender: 'user',
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    const currentInput = inputMessage;
    const currentFile = uploadedFile;
    setInputMessage('');
    setUploadedFile(null);
    setLoading(true);

    try {
      const token = localStorage.getItem('access_token');
      
      // Handle document upload first if present
      if (currentFile && inputMode === 'document') {
        const formData = new FormData();
        formData.append('file', currentFile);
        
        const reportResponse = await fetch('http://127.0.0.1:8000/api/reports/analyze/', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
          },
          body: formData
        });

        if (reportResponse.ok) {
          const reportData = await reportResponse.json();
          
          // Add medical report to history context
          const reportSummary = `Medical Report Analysis: ${reportData.summary || 'Report analyzed'}`;
          
          // Now send symptoms with report context
          const triageResponse = await fetch('http://127.0.0.1:8000/api/triage/assess/', {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({
              current_symptoms: currentInput || reportSummary,
              input_mode: 'document',
              medical_report_id: reportData.report_id
            })
          });

          const triageData = await triageResponse.json();
          displayTriageResults(triageData, reportData);
        }
      } else {
        // Regular symptom assessment
        const response = await fetch('http://127.0.0.1:8000/api/triage/assess/', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            current_symptoms: currentInput,
            input_mode: inputMode,
            force_emergency: isEmergency
          })
        });

        if (!response.ok) {
          throw new Error('Failed to get assessment');
        }

        const data = await response.json();
        displayTriageResults(data);
      }
    } catch (error) {
      console.error('Error:', error);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: "I apologize, but I'm having trouble processing your request. Please ensure your Google Gemini API key is configured in the backend .env file.",
        sender: 'ai',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const displayTriageResults = (data: any, reportData?: any) => {
    const riskLevel = data.risk_level;
    const isEmergency = riskLevel === 'emergency';
    
    let htmlContent = `
      <div class="space-y-4">
        <!-- Risk Badge -->
        <div class="${getRiskColor(riskLevel)} text-white px-6 py-4 rounded-xl">
          <div class="flex items-center gap-3 mb-2">
            ${isEmergency ? 
              '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>' :
              '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>'
            }
            <h3 class="text-2xl font-bold uppercase">${riskLevel} Risk Assessment</h3>
          </div>
          <p class="text-white/90 text-sm">Confidence: ${(data.confidence * 100).toFixed(0)}%</p>
        </div>

        ${isEmergency ? `
          <div class="bg-red-900/30 border-2 border-red-500 rounded-xl p-4">
            <h4 class="text-red-400 font-bold text-lg mb-2">⚠️ EMERGENCY DETECTED</h4>
            <p class="text-red-200">This appears to be a medical emergency. Please:</p>
            <ul class="mt-2 space-y-1 text-red-200">
              <li>• Call emergency services (911) immediately</li>
              <li>• Do not wait for further assessment</li>
              <li>• Seek immediate medical attention</li>
            </ul>
          </div>
        ` : ''}

        <!-- Reasoning -->
        <div class="bg-slate-700/50 rounded-xl p-4">
          <h4 class="text-white font-semibold mb-2">Analysis</h4>
          <p class="text-slate-200 leading-relaxed">${data.reasoning}</p>
        </div>

        ${reportData ? `
          <div class="bg-blue-900/30 border border-blue-500/30 rounded-xl p-4">
            <h4 class="text-blue-300 font-semibold mb-2">📄 Medical Report Analysis</h4>
            <p class="text-slate-200 text-sm">${reportData.summary || 'Report analyzed successfully'}</p>
            ${reportData.abnormal_results && reportData.abnormal_results.length > 0 ? `
              <div class="mt-2">
                <p class="text-orange-300 text-sm font-medium">Abnormal Results Found:</p>
                <ul class="mt-1 space-y-1">
                  ${reportData.abnormal_results.map((result: any) => `
                    <li class="text-slate-300 text-sm">• ${result.test_name}: ${result.concern_level}</li>
                  `).join('')}
                </ul>
              </div>
            ` : ''}
          </div>
        ` : ''}

        <!-- Possible Conditions -->
        ${data.possible_conditions && data.possible_conditions.length > 0 ? `
          <div class="bg-slate-700/50 rounded-xl p-4">
            <h4 class="text-white font-semibold mb-3">Possible Conditions</h4>
            <div class="grid grid-cols-2 gap-2">
              ${data.possible_conditions.slice(0, 4).map((condition: string, idx: number) => `
                <div class="bg-slate-600/50 rounded-lg p-3 text-center">
                  <p class="text-slate-200 text-sm font-medium">${condition}</p>
                </div>
              `).join('')}
            </div>
          </div>
        ` : ''}

        <!-- Recommendations -->
        ${data.recommendations && data.recommendations.length > 0 ? `
          <div class="bg-slate-700/50 rounded-xl p-4">
            <h4 class="text-white font-semibold mb-3">Recommendations</h4>
            <div class="space-y-2">
              ${data.recommendations.map((rec: string) => `
                <div class="flex items-start gap-2">
                  <svg class="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                  </svg>
                  <p class="text-slate-200 text-sm">${rec}</p>
                </div>
              `).join('')}
            </div>
          </div>
        ` : ''}

        <!-- Facility Recommendations -->
        <div class="bg-slate-700/50 rounded-xl p-4">
          <h4 class="text-white font-semibold mb-3">Next Steps</h4>
          <ul class="space-y-2 text-slate-200 text-sm">
            <li class="flex items-start gap-2">
              <span class="text-slate-400">•</span>
              <span>${isEmergency ? 'Seek immediate emergency care' : 'Monitor your symptoms at home'}</span>
            </li>
            <li class="flex items-start gap-2">
              <span class="text-slate-400">•</span>
              <span>Consult healthcare provider if symptoms worsen</span>
            </li>
            <li class="flex items-start gap-2">
              <span class="text-slate-400">•</span>
              <span>Keep this assessment for your medical records</span>
            </li>
          </ul>
        </div>

        <!-- Share Options -->
        <div class="flex gap-2">
          <button class="flex-1 bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
            📥 Download PDF
          </button>
          <button class="flex-1 bg-green-600 hover:bg-green-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
            💬 Share via WhatsApp
          </button>
          <button class="flex-1 bg-slate-600 hover:bg-slate-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
            ✉️ Email Results
          </button>
        </div>
      </div>
    `;

    const aiMessage: Message = {
      id: (Date.now() + 1).toString(),
      text: data.reasoning,
      html: htmlContent,
      sender: 'ai',
      timestamp: new Date(),
      riskLevel: riskLevel,
      triageData: data
    };

    setMessages(prev => [...prev, aiMessage]);
  };

  const handleVoiceInput = () => {
    if (!isRecording) {
      // Start recording
      if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRecognition = (window as any).webkitSpeechRecognition || (window as any).SpeechRecognition;
        const recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-US';

        recognition.onstart = () => {
          setIsRecording(true);
        };

        recognition.onresult = (event: any) => {
          const transcript = event.results[0][0].transcript;
          setInputMessage(transcript);
          setIsRecording(false);
        };

        recognition.onerror = () => {
          setIsRecording(false);
        };

        recognition.onend = () => {
          setIsRecording(false);
        };

        recognition.start();
      } else {
        alert('Speech recognition is not supported in your browser. Please use Chrome or Edge.');
      }
    }
  };

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setUploadedFile(file);
      setInputMode('document');
      setInputMessage(`Uploaded: ${file.name}`);
    }
  };

  const handleLogout = async () => {
    await authService.logout();
    navigate('/');
  };



  return (
    <div className={`h-screen flex ${theme === 'dark' ? 'bg-slate-900' : 'bg-gray-50'}`}>
      {/* Sidebar */}
      <div className={`${sidebarOpen ? 'w-64' : 'w-0'} transition-all duration-300 ${theme === 'dark' ? 'bg-slate-800 border-slate-700' : 'bg-white border-gray-200'} border-r overflow-hidden`}>
        <div className="h-full flex flex-col">
          {/* Logo */}
          <div className="p-4 border-b border-slate-700">
            <div className="flex items-center gap-2">
              <Heart className="w-8 h-8 text-blue-500" />
              <h1 className="text-xl font-bold text-white">MEDAID</h1>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex-1 p-4 space-y-2">
            <button
              onClick={() => setActiveSection('home')}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                activeSection === 'home' 
                  ? 'bg-blue-600 text-white' 
                  : 'text-slate-300 hover:bg-slate-700'
              }`}
            >
              <Home className="w-5 h-5" />
              <span>Home</span>
            </button>
            
            <button
              onClick={() => setActiveSection('history')}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                activeSection === 'history' 
                  ? 'bg-blue-600 text-white' 
                  : 'text-slate-300 hover:bg-slate-700'
              }`}
            >
              <Clock className="w-5 h-5" />
              <span>History</span>
            </button>

            <button
              onClick={() => setActiveSection('profile')}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                activeSection === 'profile' 
                  ? 'bg-blue-600 text-white' 
                  : 'text-slate-300 hover:bg-slate-700'
              }`}
            >
              <User className="w-5 h-5" />
              <span>Profile</span>
            </button>
          </nav>

          {/* User Info */}
          <div className="p-4 border-t border-slate-700">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 bg-blue-600 rounded-full flex items-center justify-center text-white font-bold">
                {user?.first_name?.[0] || 'U'}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-white font-medium truncate">{user?.first_name} {user?.last_name}</p>
                <p className="text-slate-400 text-sm truncate">{user?.email}</p>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg transition-colors"
            >
              <LogOut className="w-4 h-4" />
              <span>Logout</span>
            </button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className={`h-16 ${theme === 'dark' ? 'bg-slate-800 border-slate-700' : 'bg-white border-gray-200'} border-b flex items-center justify-between px-6`}>
          <div className="flex items-center gap-4">
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-2 hover:bg-slate-700 rounded-lg transition-colors"
            >
              <Menu className="w-5 h-5 text-white" />
            </button>
            <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-600 rounded-lg">
              <Sparkles className="w-4 h-4 text-white" />
              <span className="text-sm font-medium text-white">AI Health Assistant</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
              className="p-2 hover:bg-slate-700 rounded-lg transition-colors"
            >
              {theme === 'dark' ? (
                <Sun className="w-5 h-5 text-white" />
              ) : (
                <Moon className="w-5 h-5 text-slate-900" />
              )}
            </button>
          </div>
        </header>

        {/* Chat Area */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-4xl mx-auto space-y-6">
            {messages.length === 0 ? (
              <div className="text-center py-12">
                <div className="w-24 h-24 mx-auto mb-6 bg-gradient-to-br from-blue-500 to-purple-500 rounded-full flex items-center justify-center">
                  <Heart className="w-12 h-12 text-white" />
                </div>
                <h2 className="text-3xl font-bold text-white mb-2">
                  Hello, {user?.first_name}!
                </h2>
                <p className="text-slate-400 text-lg">
                  How can I help you with your health today?
                </p>
              </div>
            ) : (
              messages.map((message) => (
                <motion.div
                  key={message.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`flex gap-4 ${message.sender === 'user' ? 'justify-end' : ''}`}
                >
                  {message.sender === 'ai' && (
                    <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-cyan-400 rounded-xl flex items-center justify-center flex-shrink-0">
                      <Sparkles className="w-5 h-5 text-white" />
                    </div>
                  )}
                  <div
                    className={`max-w-3xl rounded-2xl ${
                      message.sender === 'user'
                        ? 'bg-blue-600 text-white px-6 py-4'
                        : 'bg-slate-800 text-slate-100 px-6 py-4'
                    }`}
                  >
                    {message.html ? (
                      <div dangerouslySetInnerHTML={{ __html: message.html }} />
                    ) : (
                      <p className="text-sm leading-relaxed whitespace-pre-line">{message.text}</p>
                    )}
                  </div>
                  {message.sender === 'user' && (
                    <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-500 rounded-full flex items-center justify-center flex-shrink-0 text-white font-bold">
                      {user?.first_name?.[0] || 'U'}
                    </div>
                  )}
                </motion.div>
              ))
            )}

            {loading && (
              <div className="flex gap-4">
                <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-cyan-400 rounded-xl flex items-center justify-center">
                  <Sparkles className="w-5 h-5 text-white animate-pulse" />
                </div>
                <div className="bg-slate-800 px-6 py-4 rounded-2xl">
                  <div className="flex gap-2">
                    <div className="w-2 h-2 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                    <div className="w-2 h-2 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                    <div className="w-2 h-2 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Input Area */}
        <div className={`${theme === 'dark' ? 'bg-slate-800 border-slate-700' : 'bg-white border-gray-200'} border-t p-6`}>
          <div className="max-w-4xl mx-auto">
            {/* Input Mode Selector */}
            <div className="flex gap-2 mb-4">
              <button
                onClick={() => setInputMode('text')}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                  inputMode === 'text'
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                }`}
              >
                <FileText className="w-4 h-4" />
                <span className="text-sm font-medium">Text</span>
              </button>
              <button
                onClick={() => setInputMode('voice')}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                  inputMode === 'voice'
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                }`}
              >
                <Mic className="w-4 h-4" />
                <span className="text-sm font-medium">Voice</span>
              </button>
              <button
                onClick={() => {
                  setInputMode('document');
                  fileInputRef.current?.click();
                }}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                  inputMode === 'document'
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                }`}
              >
                <Upload className="w-4 h-4" />
                <span className="text-sm font-medium">Document</span>
              </button>
            </div>

            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,image/*"
              onChange={handleFileUpload}
              className="hidden"
            />

            {/* Input Box */}
            <div className="relative">
              <div className="bg-slate-700 rounded-2xl p-1">
                <div className="flex items-end gap-3 px-4 py-3">
                  <textarea
                    value={inputMessage}
                    onChange={(e) => setInputMessage(e.target.value)}
                    onKeyPress={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleSendMessage();
                      }
                    }}
                    placeholder="Describe your symptoms in your own words..."
                    className="flex-1 bg-transparent text-white placeholder-slate-400 outline-none resize-none max-h-32"
                    rows={1}
                  />
                  
                  {inputMode === 'voice' && (
                    <button
                      onClick={handleVoiceInput}
                      className={`p-3 rounded-xl transition-all ${
                        isRecording 
                          ? 'bg-red-600 animate-pulse' 
                          : 'bg-blue-600 hover:bg-blue-500'
                      }`}
                    >
                      <Mic className="w-5 h-5 text-white" />
                    </button>
                  )}
                  
                  <button
                    onClick={handleSendMessage}
                    disabled={!inputMessage.trim() && !uploadedFile}
                    className="p-3 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-600 disabled:cursor-not-allowed rounded-xl transition-colors"
                  >
                    <Send className="w-5 h-5 text-white" />
                  </button>
                </div>
              </div>
            </div>

            {uploadedFile && (
              <div className="mt-2 flex items-center gap-2 px-4 py-2 bg-blue-600/20 border border-blue-500/30 rounded-lg">
                <FileText className="w-4 h-4 text-blue-400" />
                <span className="text-sm text-blue-300">{uploadedFile.name}</span>
                <button
                  onClick={() => {
                    setUploadedFile(null);
                    setInputMode('text');
                  }}
                  className="ml-auto p-1 hover:bg-blue-500/20 rounded"
                >
                  <X className="w-4 h-4 text-blue-400" />
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default NewDashboard;
