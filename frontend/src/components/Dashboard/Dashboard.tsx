import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { useTranslation } from 'react-i18next';
import MedicalHistory from './MedicalHistory';
import PatientReports from '../PatientHistory/PatientReports';
import ReportDetailsView from '../PatientHistory/ReportDetailsView';
import FindSpecialist from '../Specialist/FindSpecialist';

import {
  Search,
  Plus,
  Menu,
  Home,
  FileText,
  User,
  Settings,
  Send,
  Mic,
  Image as ImageIcon,
  Activity,
  Calendar,
  Heart,
  Sparkles,
  MessageSquare,
  Brain,
  MapPin,
  Stethoscope,
  Share2,
  Sun,
  Moon,
  Languages,
  Edit2,
  Trash2,
  LogOut
} from 'lucide-react';
import authService from '../../services/authService';

interface Message {
  id: string;
  text: string;
  sender: 'user' | 'ai';
  timestamp: Date;
}

interface ChatHistory {
  id: string;
  title: string;
  date: string;
  preview: string;
  // keep original ID for API calls if needed, though id above is string
  originalId?: number; 
}

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const [user, setUser] = useState<any>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [showLoginPrompt, setShowLoginPrompt] = useState(false);
  const [showProfileCard, setShowProfileCard] = useState(false);
  const [showProfileSettings, setShowProfileSettings] = useState(false);
  const [showMedicalHistory, setShowMedicalHistory] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showShareModal, setShowShareModal] = useState(false);
  const [activeNavItem, setActiveNavItem] = useState('home');
  const [selectedReportId, setSelectedReportId] = useState<number | null>(null);
  const [chatSearchQuery, setChatSearchQuery] = useState('');
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const savedTheme = localStorage.getItem('medaid_theme');
    return (savedTheme as 'light' | 'dark') || 'dark';
  });
  const [language, setLanguage] = useState(i18n.language || 'english');

  // Profile editing states
  const [editingField, setEditingField] = useState<string | null>(null);
  const [profileData, setProfileData] = useState({
    fullName: '',
    gender: '',
    location: '',
    birthDate: '',
    pastHistory: ''
  });

  const handleLanguageChange = (lang: string) => {
    setLanguage(lang);
    i18n.changeLanguage(lang);
  };

  const handleLogout = async () => {
    try {
      if (authService.isAuthenticated()) {
        await authService.logout();
      }
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      setIsAuthenticated(false);
      setUser(null);
      navigate('/');
    }
  };
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [userLocation, setUserLocation] = useState('');  // User's location for nearby hospitals
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [loading, setLoading] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [isListening, setIsListening] = useState(false);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  // Persistent chat state
  const [chatHistory, setChatHistory] = useState<ChatHistory[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<number | null>(null);
  const [currentConversation, setCurrentConversation] = useState<any>(null);
  // Point to the backend API (currently running on 8001)
  const API_BASE = 'http://127.0.0.1:8001/api';

  useEffect(() => {
    // Check authentication
    const authenticated = authService.isAuthenticated();
    setIsAuthenticated(authenticated);

    if (authenticated) {
      // Load user from local storage first for immediate display
      const localUser = authService.getUser();
      if (localUser) {
        setUser(localUser);
      }
      // Fetch user data from API to get latest
      fetchUserData();
      // Load conversations from database
      loadConversations();
    }
  }, []);

  useEffect(() => {
    // Save theme to localStorage whenever it changes
    localStorage.setItem('medaid_theme', theme);
  }, [theme]);

  const fetchUserData = async () => {
    try {
      const response = await fetch('http://localhost:8001/api/auth/me/', {
        headers: authService.getAuthHeaders(),
      });

      if (response.ok) {
        const data = await response.json();
        setUser(data);
      } else {
        navigate('/login');
      }
    } catch (error) {
      console.error('Error fetching user:', error);
    }
  };

  const loadConversations = async () => {
    try {
      const response = await fetch(`${API_BASE}/chat/conversations/`, {
        headers: authService.getAuthHeaders()
      });
      if (response.ok) {
        const data = await response.json();
        // Handle both single object or array response for robustness
        const conversations = Array.isArray(data.conversations) ? data.conversations : [];
        const formattedChats = conversations.map((conv: any) => ({
          id: conv.id.toString(),
          originalId: conv.id,
          title: conv.title || 'New Chat',
          date: formatDate(conv.last_activity),
          preview: conv.preview_message || 'No messages'
        }));
        setChatHistory(formattedChats);
      }
    } catch (error) {
      console.error('Error loading conversations:', error);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffHours = Math.floor((now.getTime() - date.getTime()) / 3600000);
    if (diffHours < 24) return 'Today';
    if (diffHours < 48) return 'Yesterday';
    return `${Math.floor(diffHours / 24)} days ago`;
  };


  const handleSendMessage = async () => {
    if (!isAuthenticated) {
      setShowLoginPrompt(true);
      return;
    }
    if (!inputMessage.trim() && !uploadedFile) return;

    const currentInput = inputMessage;
    const currentFile = uploadedFile;

    setInputMessage('');
    setUploadedFile(null);
    setLoading(true);

    try {
      let conversationId = activeConversationId;

      // Create conversation if none exists
      if (!conversationId) {
        const convResponse = await fetch(`${API_BASE}/chat/conversations/`, {
          method: 'POST',
          headers: authService.getAuthHeaders()
        });
        if (convResponse.ok) {
          const convData = await convResponse.json();
          conversationId = convData.conversation.id;
          setActiveConversationId(conversationId);
          setCurrentConversation(convData.conversation);
        } else {
          throw new Error('Failed to create conversation');
        }
      }

      // Send message to active conversation
      if (conversationId) {
        let headers = authService.getAuthHeaders() as any;
        let body;

        if (currentFile) {
          const formData = new FormData();
          formData.append('content', currentInput);
          formData.append('file', currentFile);
          body = formData;
          // Remove Content-Type header to let browser set boundary for multipart
          if (headers['Content-Type']) {
            delete headers['Content-Type'];
          }
        } else {
          body = JSON.stringify({ content: currentInput });
        }

        const msgResponse = await fetch(`${API_BASE}/chat/conversations/${conversationId}/messages/`, {
          method: 'POST',
          headers: headers,
          body: body
        });

        if (msgResponse.ok) {
          const msgData = await msgResponse.json();

          // Add both user and assistant messages to display
          setMessages(prev => [...prev,
          {
            id: msgData.user_message.id.toString(),
            text: msgData.user_message.content,
            sender: 'user',
            timestamp: new Date(msgData.user_message.created_at)
          },
          {
            id: msgData.assistant_message.id.toString(),
            text: msgData.assistant_message.content,
            sender: 'ai',
            timestamp: new Date(msgData.assistant_message.created_at)
          }
          ]);

          // Update conversation in sidebar
          await loadConversations();

          // Update current conversation title
          if (msgData.conversation?.title) {
            setCurrentConversation(msgData.conversation);
          }
        } else {
          throw new Error('Failed to send message');
        }
      }
    } catch (error) {
      console.error('Error sending message:', error);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: "Sorry, I encountered an error. Please try again.",
        sender: 'ai',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleNewChat = async () => {
    try {
      const response = await fetch(`${API_BASE}/chat/conversations/`, {
        method: 'POST',
        headers: authService.getAuthHeaders()
      });

      if (response.ok) {
        const data = await response.json();
        setActiveConversationId(data.conversation.id);
        setCurrentConversation(data.conversation);
        setMessages([]);
        await loadConversations();
      }
    } catch (error) {
      console.error('Error creating new chat:', error);
    }
  };

  const handleSelectChat = async (chatId: string) => {
    try {
      const convId = parseInt(chatId);
      setActiveConversationId(convId);

      // Load messages for this conversation
      const response = await fetch(`${API_BASE}/chat/conversations/${convId}/messages/list/`, {
        headers: authService.getAuthHeaders()
      });

      if (response.ok) {
        const data = await response.json();
        const formattedMessages = data.messages.map((msg: any) => ({
          id: msg.id.toString(),
          text: msg.content,
          sender: msg.role === 'user' ? 'user' : 'ai',
          timestamp: new Date(msg.created_at)
        }));
        setMessages(formattedMessages);
        setCurrentConversation(data.conversation);
      }
    } catch (error) {
      console.error('Error loading chat:', error);
    }
  };

  const handleDeleteChat = async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm('Are you sure you want to delete this chat?')) return;

    try {
      const response = await fetch(`${API_BASE}/chat/conversations/${convId}/`, {
        method: 'DELETE',
        headers: authService.getAuthHeaders()
      });
      if (response.ok) {
        setChatHistory(prev => prev.filter(chat => chat.id !== convId));
        if (activeConversationId?.toString() === convId) {
          setActiveConversationId(null);
          setMessages([]);
        }
      }
    } catch (error) {
      console.error('Error deleting chat:', error);
    }
  };

  const handleRenameChat = async (convId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const newTitle = window.prompt('Enter new title:');
    if (!newTitle || !newTitle.trim()) return;

    try {
      const response = await fetch(`${API_BASE}/chat/conversations/${convId}/`, {
        method: 'PATCH',
        headers: authService.getAuthHeaders(),
        body: JSON.stringify({ title: newTitle.trim() })
      });
      if (response.ok) {
        const data = await response.json();
        setChatHistory(prev => prev.map(chat =>
          chat.id === convId ? { ...chat, title: data.conversation.title } : chat
        ));
      }
    } catch (error) {
      console.error('Error renaming chat:', error);
    }
  };

  const handleVoiceInput = () => {
    const SpeechRecognition = (window as any).webkitSpeechRecognition || (window as any).SpeechRecognition;

    if (!SpeechRecognition) {
      alert('Speech recognition is not supported in your browser. Please use Chrome, Edge, or Safari.');
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.lang = language === 'english' ? 'en-US' : language === 'hindi' ? 'hi-IN' : 'mr-IN';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      setIsListening(true);
    };

    recognition.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript;
      setInputMessage(transcript);
      setIsListening(false);
    };

    recognition.onerror = (event: any) => {
      console.error('Speech recognition error:', event.error);
      setIsListening(false);
      alert(`Voice input error: ${event.error}`);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognition.start();
  };

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      // Check file type
      const allowedTypes = ['application/pdf', 'image/jpeg', 'image/png', 'image/jpg'];
      if (!allowedTypes.includes(file.type)) {
        alert('Please upload a PDF or image file (JPEG, PNG)');
        return;
      }

      // Check file size (10MB limit)
      if (file.size > 10 * 1024 * 1024) {
        alert('File size must be less than 10MB');
        return;
      }

      setUploadedFile(file);
      setInputMessage(`📎 ${file.name} - Describe your symptoms or concerns`);
    }
  };

  const quickActions = [
    {
      title: 'Voice Input',
      description: 'Describe your symptoms using voice - supports English, Hindi, and Marathi.',
      icon: Mic,
      color: 'from-blue-500 to-purple-600',
      action: handleVoiceInput
    },
    {
      title: 'Upload Report',
      description: 'Upload medical reports, lab results, or prescriptions for AI analysis.',
      icon: ImageIcon,
      color: 'from-purple-500 to-pink-500',
      action: () => fileInputRef.current?.click()
    },
    {
      title: 'Emergency Detection',
      description: 'Automatically detects emergency keywords and provides urgent care guidance.',
      icon: Activity,
      color: 'from-red-500 to-orange-500'
    }
  ];

  const filteredChatHistory = chatHistory.filter(chat =>
    chat.title.toLowerCase().includes(chatSearchQuery.toLowerCase()) ||
    chat.preview.toLowerCase().includes(chatSearchQuery.toLowerCase())
  );

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good Morning';
    if (hour < 18) return 'Good Afternoon';
    return 'Good Evening';
  };

  return (
    <div className={`flex h-screen ${theme === 'dark' ? 'bg-[#0f0f0f] text-gray-100' : 'bg-gray-50 text-gray-900'} overflow-hidden`}>
      {/* Sidebar */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.div
            initial={{ x: -280 }}
            animate={{ x: 0 }}
            exit={{ x: -280 }}
            transition={{ type: 'spring', damping: 20 }}
            className={`w-[280px] ${theme === 'dark' ? 'bg-[#1a1a1a] border-gray-800/50' : 'bg-white border-gray-200'} border-r flex flex-col`}
          >
            {/* Logo */}
            <div className={`p-5 border-b ${theme === 'dark' ? 'border-gray-800/30' : 'border-gray-200'}`}>
              <div className="flex items-center gap-3">
                <div className={`w-9 h-9 ${theme === 'dark' ? 'bg-white' : 'bg-gradient-to-br from-purple-600 to-blue-600'} rounded-lg flex items-center justify-center`}>
                  <span className={`text-lg font-bold ${theme === 'dark' ? 'text-gray-900' : 'text-white'}`}>M</span>
                </div>
                <h1 className={`text-lg font-semibold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                  Medaid
                </h1>
              </div>
            </div>

            {/* New Chat Button */}
            <div className="px-4 pt-5 pb-3">
              <button
                onClick={handleNewChat}
                className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 rounded-lg py-2.5 text-sm font-semibold flex items-center justify-center gap-2 transition-all shadow-lg shadow-blue-500/20"
              >
                <Plus className="w-4 h-4" />
                New Chat
              </button>
            </div>

            {/* Search Chats */}
            <div className="px-4 pb-3">
              <div className="relative">
                <Search className={`absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 ${theme === 'dark' ? 'text-gray-500' : 'text-gray-400'}`} />
                <input
                  type="text"
                  placeholder="Search chats..."
                  value={chatSearchQuery}
                  onChange={(e) => setChatSearchQuery(e.target.value)}
                  className={`w-full ${theme === 'dark' ? 'bg-[#252525] border-gray-800/50 text-white placeholder:text-gray-500 focus:border-gray-700' : 'bg-gray-100 border-gray-200 text-gray-900 placeholder:text-gray-400 focus:border-gray-300'} border rounded-lg pl-9 pr-4 py-2 text-sm focus:outline-none transition-colors`}
                />
              </div>
            </div>

            {/* Pincode / Location */}
            <div className="px-4 pb-3">
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <MapPin className={`absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 ${theme === 'dark' ? 'text-gray-500' : 'text-gray-400'}`} />
                  <input
                    type="text"
                    placeholder="Enter Pincode..."
                    value={userLocation}
                    onChange={(e) => setUserLocation(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && setActiveNavItem('medication')}
                    className={`w-full ${theme === 'dark' ? 'bg-[#252525] border-gray-800/50 text-white placeholder:text-gray-500 focus:border-gray-700' : 'bg-gray-100 border-gray-200 text-gray-900 placeholder:text-gray-400 focus:border-gray-300'} border rounded-lg pl-9 pr-4 py-2 text-sm focus:outline-none transition-colors`}
                  />
                </div>
                <button
                  onClick={() => setActiveNavItem('medication')}
                  className="bg-blue-600 hover:bg-blue-500 text-white p-2 rounded-lg transition-colors flex items-center justify-center shadow-lg shadow-blue-500/20"
                  title="Find Hospitals"
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Navigation */}
            <nav className="flex-1 px-3 py-2 space-y-0.5 overflow-y-auto">
              <NavItem
                icon={Home}
                label="Home"
                active={activeNavItem === 'home'}
                onClick={() => setActiveNavItem('home')}
                theme={theme}
              />
              <NavItem
                icon={Brain}
                label="Medical History Insights"
                active={activeNavItem === 'insights'}
                onClick={() => setActiveNavItem('insights')}
                theme={theme}
              />
              <NavItem
                icon={Stethoscope}
                label="Health Consultation"
                active={activeNavItem === 'medication'}
                onClick={() => setActiveNavItem('medication')}
                theme={theme}
              />

              {/* Chat History */}
              <div className="pt-4 pb-2">
                <div className="px-3 mb-2 flex items-center justify-between">
                  <h3 className={`text-xs font-medium uppercase tracking-wider ${theme === 'dark' ? 'text-gray-500' : 'text-gray-600'}`}>
                    Previous Chats
                  </h3>
                </div>

                {filteredChatHistory.length > 0 ? (
                  filteredChatHistory.map((chat) => (
                    <div
                      key={chat.id}
                      onClick={() => {
                        handleSelectChat(chat.id);
                      }}
                      className={`w-full px-3 py-2 rounded-lg cursor-pointer transition-colors group text-left relative mb-1 ${activeConversationId?.toString() === chat.id
                          ? (theme === 'dark' ? 'bg-blue-600/20 border-l-2 border-blue-500' : 'bg-blue-100 border-l-2 border-blue-600')
                          : (theme === 'dark' ? 'hover:bg-gray-800/50' : 'hover:bg-gray-100')
                        }`}
                    >
                      <div className="flex items-start gap-2">
                        <MessageSquare className={`w-3.5 h-3.5 mt-0.5 flex-shrink-0 ${theme === 'dark' ? 'text-gray-500' : 'text-gray-500'
                          }`} />
                        <div className="flex-1 min-w-0">
                          <p className={`text-sm font-medium truncate ${theme === 'dark' ? 'text-gray-300 group-hover:text-white' : 'text-gray-700 group-hover:text-gray-900'
                            }`}>
                            {chat.title}
                          </p>
                          <p className={`text-xs truncate ${theme === 'dark' ? 'text-gray-500' : 'text-gray-600'
                            }`}>{chat.preview}</p>
                        </div>
                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            onClick={(e) => {
                              // e.stopPropagation();
                              handleRenameChat(chat.id, e);
                            }}
                            className={`p-1 rounded transition-colors ${theme === 'dark' ? 'hover:bg-white/10' : 'hover:bg-gray-200'}`}
                            title="Rename"
                          >
                            <Edit2 className="w-3 h-3" />
                          </button>
                          <button
                            onClick={(e) => {
                              // e.stopPropagation();
                              handleDeleteChat(chat.id, e);
                            }}
                            className={`p-1 rounded transition-colors ${theme === 'dark' ? 'hover:bg-red-500/20' : 'hover:bg-red-100'}`}
                            title="Delete"
                          >
                            <Trash2 className="w-3 h-3 text-red-500" />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="px-3 py-2 text-xs text-center text-gray-500">
                    No history yet
                  </div>
                )}
              </div>

            </nav>

            {/* Upgrade Card */}
            <div className="px-4 pb-4">
              <div className={`${theme === 'dark' ? 'bg-gradient-to-br from-gray-800/50 to-gray-900/50 border-gray-800/50' : 'bg-gradient-to-br from-blue-50 to-indigo-50 border-blue-100'} border rounded-xl p-4 mb-3`}>
                <div className="flex items-start gap-2 mb-3">
                  <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center flex-shrink-0">
                    <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                  </div>
                  <div>
                    <h4 className={`text-sm font-semibold mb-1 ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>Boost with AI</h4>
                    <p className={`text-xs leading-relaxed ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>
                      AI-powered replies, tag insights, and tools that save hours.
                    </p>
                  </div>
                </div>
                <button className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white rounded-lg py-2.5 text-sm font-medium transition-all">
                  Upgrade to Pro
                </button>
              </div>

              {/* User Profile */}
              <div
                onClick={() => setShowProfileCard(true)}
                className={`flex items-center gap-3 p-2.5 rounded-lg cursor-pointer transition-colors group border ${theme === 'dark' ? 'hover:bg-gray-800/50 border-gray-800/30' : 'hover:bg-gray-100 border-gray-200'}`}
              >
                <div className="w-9 h-9 bg-gradient-to-br from-blue-500 to-purple-500 rounded-full flex items-center justify-center font-semibold text-sm flex-shrink-0">
                  {user?.first_name?.[0] || user?.email?.[0] || 'U'}
                </div>
                <div className="flex-1 min-w-0">
                  <p className={`text-sm font-medium truncate ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                    {user?.first_name || 'User'}
                  </p>
                  <p className={`text-xs truncate ${theme === 'dark' ? 'text-gray-400' : 'text-gray-500'}`}>{user?.email || 'user@example.com'}</p>
                </div>
                <div className="flex flex-col gap-0.5">
                  <div className={`w-1 h-1 rounded-full ${theme === 'dark' ? 'bg-gray-400' : 'bg-gray-500'}`}></div>
                  <div className={`w-1 h-1 rounded-full ${theme === 'dark' ? 'bg-gray-400' : 'bg-gray-500'}`}></div>
                  <div className={`w-1 h-1 rounded-full ${theme === 'dark' ? 'bg-gray-400' : 'bg-gray-500'}`}></div>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Content */}
      {activeNavItem === 'insights' && !selectedReportId ? (
        <PatientReports
          theme={theme}
          onBack={() => setActiveNavItem('home')}
          onViewDetails={(reportId) => setSelectedReportId(reportId)}
        />
      ) : activeNavItem === 'insights' && selectedReportId ? (
        <ReportDetailsView
          reportId={selectedReportId}
          theme={theme}
          onBack={() => setSelectedReportId(null)}
        />
      ) : activeNavItem === 'medication' ? (
        <FindSpecialist
          theme={theme}
          onBack={() => setActiveNavItem('home')}
          user={user}
          location={userLocation}
        />
      ) : (
        <div className="flex-1 flex flex-col">{/* Header */}
          <header className={`h-16 border-b ${theme === 'dark' ? 'border-gray-800 bg-gray-900/50' : 'border-gray-200 bg-white/50'} flex items-center justify-between px-6 backdrop-blur-xl`}>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className={`p-2 ${theme === 'dark' ? 'hover:bg-gray-800' : 'hover:bg-gray-100'} rounded-lg transition-colors`}
              >
                <Menu className={`w-5 h-5 ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`} />
              </button>
              <div className={`flex items-center gap-2 px-3 py-1.5 ${theme === 'dark' ? 'bg-gray-800/50 border-gray-700' : 'bg-blue-50 border-blue-200'} rounded-lg border`}>
                <Sparkles className="w-4 h-4 text-blue-400" />
                <span className={`text-sm font-medium ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>AI Assistant</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowShareModal(true)}
                className={`p-2 ${theme === 'dark' ? 'hover:bg-gray-800' : 'hover:bg-gray-100'} rounded-lg transition-colors`}
                title="Share"
              >
                <Share2 className={`w-5 h-5 ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`} />
              </button>
              <button
                onClick={() => setShowSettings(true)}
                className={`p-2 ${theme === 'dark' ? 'hover:bg-gray-800' : 'hover:bg-gray-100'} rounded-lg transition-colors`}
                title="Settings"
              >
                <Settings className={`w-5 h-5 ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`} />
              </button>
            </div>
          </header>

          {/* Chat Area */}
          <div className="flex-1 overflow-y-auto">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center px-6">
                {/* Welcome Screen */}
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="text-center max-w-2xl"
                >
                  <div className="w-24 h-24 mx-auto mb-6 bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500 rounded-full flex items-center justify-center shadow-2xl">
                    <Heart className="w-12 h-12 text-white" />
                  </div>
                  <h1 className={`text-4xl font-bold mb-3 ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                    {getGreeting()}, {user?.first_name || 'there'}.
                  </h1>
                  <p className={`text-xl mb-12 ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>
                    Can I help you with anything?
                  </p>

                  {/* Quick Actions */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-8 max-w-4xl mx-auto">
                    {quickActions.map((action, index) => (
                      <motion.div
                        key={action.title}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.1 }}
                        onClick={action.action}
                        className={`${theme === 'dark' ? 'bg-gray-800/50 hover:bg-gray-800 border-gray-700 hover:border-gray-600' : 'bg-white hover:bg-gray-50 border-gray-200 hover:border-gray-300'} backdrop-blur-xl border rounded-2xl p-6 cursor-pointer transition-all group aspect-square flex flex-col justify-center items-center text-center`}
                      >
                        <div className={`w-16 h-16 bg-gradient-to-br ${action.color} rounded-2xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform shadow-lg`}>
                          <action.icon className="w-8 h-8 text-white" />
                        </div>
                        <h3 className={`text-lg font-bold mb-2 ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>{action.title}</h3>
                        <p className={`text-sm leading-relaxed ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>{action.description}</p>
                      </motion.div>
                    ))}
                  </div>
                </motion.div>
              </div>
            ) : (
              <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
                {messages.map((message) => (
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
                      className={`max-w-2xl px-4 py-3 rounded-2xl ${message.sender === 'user'
                        ? 'bg-blue-600 text-white'
                        : theme === 'dark' ? 'bg-gray-800 text-gray-100' : 'bg-gray-100 text-gray-900'
                        }`}
                    >
                      {message.sender === 'ai' && message.text.includes('<div') ? (
                        <div
                          className="text-sm leading-relaxed"
                          dangerouslySetInnerHTML={{ __html: message.text }}
                        />
                      ) : (
                        message.text.includes('<div') ? 
                        <div
                          className="text-sm leading-relaxed"
                          dangerouslySetInnerHTML={{ __html: message.text }}
                        /> 
                        :
                        <p className="text-sm leading-relaxed whitespace-pre-line">{message.text}</p>
                      )}
                    </div>
                    {message.sender === 'user' && (
                      <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-500 rounded-full flex items-center justify-center flex-shrink-0 font-semibold text-white">
                        {user?.first_name?.[0] || 'U'}
                      </div>
                    )}
                  </motion.div>
                ))}
                {loading && (
                  <div className="flex gap-4">
                    <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-cyan-400 rounded-xl flex items-center justify-center">
                      <Sparkles className="w-5 h-5 text-white animate-pulse" />
                    </div>
                    <div className={`${theme === 'dark' ? 'bg-gray-800' : 'bg-gray-100'} px-4 py-3 rounded-2xl`}>
                      <div className="flex gap-1">
                        <div className={`w-2 h-2 ${theme === 'dark' ? 'bg-gray-500' : 'bg-gray-400'} rounded-full animate-bounce`} style={{ animationDelay: '0ms' }}></div>
                        <div className={`w-2 h-2 ${theme === 'dark' ? 'bg-gray-500' : 'bg-gray-400'} rounded-full animate-bounce`} style={{ animationDelay: '150ms' }}></div>
                        <div className={`w-2 h-2 ${theme === 'dark' ? 'bg-gray-500' : 'bg-gray-400'} rounded-full animate-bounce`} style={{ animationDelay: '300ms' }}></div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Input Area */}
          <div className={`border-t ${theme === 'dark' ? 'border-gray-800/50 bg-[#0a0a0a]' : 'border-gray-200 bg-white'} p-6`}>
            <div className="max-w-4xl mx-auto">
              {/* Purple Gradient Border Container */}
              <div className="relative p-[2px] rounded-2xl bg-gradient-to-r from-purple-600 via-blue-500 to-purple-600 bg-[length:200%_100%] animate-[shimmer_3s_linear_infinite]">
                <style>{`
                @keyframes shimmer {
                  0% { background-position: 200% 0; }
                  100% { background-position: -200% 0; }
                }
              `}</style>

                <div className={`relative ${theme === 'dark' ? 'bg-[#1a1a1a]' : 'bg-white'} rounded-2xl`}>
                  <div className="flex items-center gap-3 px-4 py-3.5">
                    {/* Left Actions */}
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      className={`p-2 ${theme === 'dark' ? 'hover:bg-gray-800/50' : 'hover:bg-gray-100'} rounded-lg transition-colors flex-shrink-0`}
                      title="Upload medical document"
                    >
                      <Plus className={`w-5 h-5 ${uploadedFile ? 'text-green-400' : theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`} />
                    </button>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".pdf,image/*"
                      onChange={handleFileUpload}
                      className="hidden"
                    />
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      className={`p-2 ${theme === 'dark' ? 'hover:bg-gray-800/50' : 'hover:bg-gray-100'} rounded-lg transition-colors flex-shrink-0`}
                      title="Upload image"
                    >
                      <ImageIcon className={`w-5 h-5 ${uploadedFile ? 'text-green-400' : theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`} />
                    </button>

                    {/* Input */}
                    <input
                      type="text"
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
                      placeholder="Describe your symptoms, upload reports, or ask anything..."
                      className={`flex-1 bg-transparent text-sm ${theme === 'dark' ? 'text-white placeholder:text-gray-500' : 'text-gray-900 placeholder:text-gray-400'} focus:outline-none`}
                    />

                    {/* Right Actions */}
                    <button
                      onClick={handleVoiceInput}
                      className={`p-2 ${isListening ? 'bg-red-500/20 animate-pulse' : theme === 'dark' ? 'hover:bg-gray-800/50' : 'hover:bg-gray-100'} rounded-lg transition-colors flex-shrink-0`}
                      title="Voice input"
                    >
                      <Mic className={`w-5 h-5 ${isListening ? 'text-red-400' : theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`} />
                    </button>
                    <button
                      onClick={handleSendMessage}
                      disabled={!inputMessage.trim() && !uploadedFile}
                      className="p-2 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed flex-shrink-0"
                    >
                      <Send className="w-5 h-5 text-white" />
                    </button>

                    {/* AI Features Button */}
                    <button className={`flex items-center gap-2 px-3 py-2 ${theme === 'dark' ? 'bg-gray-800/50 hover:bg-gray-800' : 'bg-gray-100 hover:bg-gray-200'} rounded-lg transition-colors flex-shrink-0`}>
                      <svg className="w-4 h-4 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                      </svg>
                      <span className={`text-xs font-medium ${theme === 'dark' ? 'text-gray-300' : 'text-gray-700'}`}>AI</span>
                    </button>
                  </div>
                </div>
              </div>

              <div className={`flex items-center justify-center gap-4 mt-4 text-xs ${theme === 'dark' ? 'text-gray-500' : 'text-gray-500'}`}>
                <button className={`${theme === 'dark' ? 'hover:text-gray-400' : 'hover:text-gray-700'} transition-colors`}>About</button>
                <span>•</span>
                <button className={`${theme === 'dark' ? 'hover:text-gray-400' : 'hover:text-gray-700'} transition-colors`}>Privacy</button>
                <span>•</span>
                <button className={`${theme === 'dark' ? 'hover:text-gray-400' : 'hover:text-gray-700'} transition-colors`}>Terms</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Profile Card Modal */}
      <AnimatePresence>
        {showProfileCard && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setShowProfileCard(false)}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4"
          >
            <motion.div
              initial={{ scale: 0.95, y: 20, opacity: 0 }}
              animate={{ scale: 1, y: 0, opacity: 1 }}
              exit={{ scale: 0.95, y: 20, opacity: 0 }}
              transition={{ type: 'spring', damping: 30, stiffness: 300 }}
              onClick={(e) => e.stopPropagation()}
              className={`${theme === 'dark' ? 'bg-gray-900 border-gray-800' : 'bg-white border-gray-200'} rounded-2xl overflow-hidden shadow-2xl max-w-md w-full border`}
            >
              {/* Header with Close Button */}
              <div className="relative bg-gradient-to-br from-blue-600 via-blue-700 to-purple-700 p-6 pb-16">
                <div className="absolute top-4 right-4">
                  <button
                    onClick={() => setShowProfileCard(false)}
                    className="w-8 h-8 bg-white/10 hover:bg-white/20 backdrop-blur-md rounded-lg flex items-center justify-center transition-colors"
                  >
                    <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                {/* Profile Image */}
                <div className="flex justify-center">
                  <div className={`w-24 h-24 bg-gradient-to-br from-blue-400 to-purple-500 rounded-full flex items-center justify-center text-3xl font-bold text-white shadow-xl border-4 ${theme === 'dark' ? 'border-gray-900' : 'border-white'}`}>
                    {user?.first_name?.[0] || user?.email?.[0] || 'U'}
                  </div>
                </div>
              </div>

              {/* Profile Content */}
              <div className="px-6 py-5 -mt-8 relative">
                {/* Name and Status */}
                <div className="text-center mb-6">
                  <h2 className={`text-xl font-bold mb-1 ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                    {user?.first_name && user?.last_name
                      ? `${user.first_name} ${user.last_name}`
                      : user?.first_name || user?.email || 'User'}
                  </h2>
                  <div className="inline-flex items-center gap-2 bg-blue-500/20 px-3 py-1 rounded-full border border-blue-500/30 mt-2">
                    <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                    <span className="text-xs font-medium text-blue-400">Active Patient</span>
                  </div>
                </div>

                {/* Stats */}
                <div className={`grid grid-cols-3 gap-3 mb-6 rounded-xl p-4 border ${theme === 'dark' ? 'bg-gray-800/50 border-gray-700/50' : 'bg-gray-50 border-gray-200'}`}>
                  <div className="text-center">
                    <Activity className="w-4 h-4 text-blue-400 mx-auto mb-1" />
                    <p className={`text-xs mb-0.5 ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>Age</p>
                    <p className={`text-sm font-semibold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>{user?.age || 'N/A'}</p>
                  </div>
                  <div className={`text-center border-l border-r ${theme === 'dark' ? 'border-gray-700/50' : 'border-gray-200'}`}>
                    <Calendar className="w-4 h-4 text-purple-400 mx-auto mb-1" />
                    <p className={`text-xs mb-0.5 ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>Visits</p>
                    <p className={`text-sm font-semibold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>12</p>
                  </div>
                  <div className="text-center">
                    <FileText className="w-4 h-4 text-cyan-400 mx-auto mb-1" />
                    <p className={`text-xs mb-0.5 ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>Records</p>
                    <p className={`text-sm font-semibold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>8</p>
                  </div>
                </div>

                {/* Contact Info */}
                <div className="space-y-3 mb-6">
                  <div className={`flex items-center gap-3 rounded-lg p-3 border ${theme === 'dark' ? 'bg-gray-800/30 border-gray-700/30' : 'bg-gray-50 border-gray-200'}`}>
                    <div className="w-9 h-9 bg-blue-500/10 rounded-lg flex items-center justify-center">
                      <User className="w-4 h-4 text-blue-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className={`text-xs ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>Full Name</p>
                      <p className={`text-sm font-medium truncate ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                        {user?.first_name && user?.last_name
                          ? `${user.first_name} ${user.last_name}`
                          : user?.first_name || 'Not provided'}
                      </p>
                    </div>
                  </div>
                  <div className={`flex items-center gap-3 rounded-lg p-3 border ${theme === 'dark' ? 'bg-gray-800/30 border-gray-700/30' : 'bg-gray-50 border-gray-200'}`}>
                    <div className="w-9 h-9 bg-purple-500/10 rounded-lg flex items-center justify-center">
                      <Activity className="w-4 h-4 text-purple-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className={`text-xs ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>Age</p>
                      <p className={`text-sm font-medium ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>{user?.age || 'Not provided'}</p>
                    </div>
                  </div>
                  <div className={`flex items-center gap-3 rounded-lg p-3 border ${theme === 'dark' ? 'bg-gray-800/30 border-gray-700/30' : 'bg-gray-50 border-gray-200'}`}>
                    <div className="w-9 h-9 bg-cyan-500/10 rounded-lg flex items-center justify-center">
                      <svg className="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                      </svg>
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className={`text-xs ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>Email</p>
                      <p className={`text-sm font-medium truncate ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>{user?.email || 'Not provided'}</p>
                    </div>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="space-y-3">
                  <button
                    onClick={() => {
                      setShowProfileCard(false);
                      setShowProfileSettings(true);
                    }}
                    className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white font-semibold py-3 rounded-xl transition-all duration-200 flex items-center justify-center gap-2 shadow-lg shadow-blue-500/25"
                  >
                    <User className="w-4 h-4" />
                    Edit Profile
                  </button>
                  <button
                    onClick={() => {
                      setShowProfileCard(false);
                      setShowMedicalHistory(true);
                    }}
                    className={`w-full font-semibold py-3 rounded-xl transition-all duration-200 flex items-center justify-center gap-2 border ${theme === 'dark' ? 'bg-gray-800 hover:bg-gray-700 text-white border-gray-700' : 'bg-gray-100 hover:bg-gray-200 text-gray-900 border-gray-200'}`}
                  >
                    <FileText className="w-4 h-4" />
                    Medical History
                  </button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Profile Settings Modal */}
      <AnimatePresence>
        {showProfileSettings && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setShowProfileSettings(false)}
            className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4"
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              transition={{ type: 'spring', damping: 30, stiffness: 300 }}
              onClick={(e) => e.stopPropagation()}
              className={`${theme === 'dark' ? 'bg-gray-900 border-gray-800' : 'bg-white border-gray-200'} rounded-2xl shadow-2xl max-w-3xl w-full border max-h-[90vh] overflow-y-auto`}
            >
              {/* Header */}
              <div className={`sticky top-0 border-b p-6 flex items-center justify-between z-10 ${theme === 'dark' ? 'bg-gray-900 border-gray-800' : 'bg-white border-gray-200'}`}>
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-500 rounded-full flex items-center justify-center text-lg font-bold text-white">
                    {user?.first_name?.[0] || user?.email?.[0] || 'U'}
                  </div>
                  <div>
                    <h2 className={`text-xl font-bold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>Profile Settings</h2>
                    <p className={`text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>Manage your personal information</p>
                  </div>
                </div>
                <button
                  onClick={() => setShowProfileSettings(false)}
                  className={`w-10 h-10 rounded-lg flex items-center justify-center transition-colors ${theme === 'dark' ? 'bg-gray-800 hover:bg-gray-700' : 'bg-gray-100 hover:bg-gray-200'}`}
                >
                  <svg className={`w-5 h-5 ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              {/* Content */}
              <div className="p-6">
                {/* User Profile Section */}
                <div className="mb-8">
                  <h3 className={`text-lg font-semibold mb-6 ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>User Profile</h3>
                  <div className="space-y-4">
                    {/* Name */}
                    <div className={`py-3 border-b ${theme === 'dark' ? 'border-gray-800' : 'border-gray-200'}`}>
                      <div className="flex items-center justify-between mb-2">
                        <label className={`text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>Full Name</label>
                      </div>
                      <div className={`text-xl font-bold mb-1 ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                        {user?.first_name} {user?.last_name}
                      </div>
                    </div>

                    {/* Email */}
                    <div className={`py-3 border-b ${theme === 'dark' ? 'border-gray-800' : 'border-gray-200'}`}>
                      <div className="flex items-center justify-between mb-2">
                        <label className={`text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>Email Address</label>
                      </div>
                      <div className={`text-lg mb-1 ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                        {user?.email}
                      </div>
                    </div>
                    {/* Gender */}
                    <div className={`py-3 border-b ${theme === 'dark' ? 'border-gray-800' : 'border-gray-200'}`}>
                      <div className="flex items-center justify-between mb-2">
                        <label className={`text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>Gender</label>
                        <button
                          onClick={() => setEditingField(editingField === 'gender' ? null : 'gender')}
                          className="text-blue-400 hover:text-blue-300 text-sm font-medium transition-colors"
                        >
                          {editingField === 'gender' ? 'Cancel' : 'Edit'}
                        </button>
                      </div>
                      <select
                        value={profileData.gender}
                        onChange={(e) => setProfileData({ ...profileData, gender: e.target.value })}
                        className={`w-full border rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500 ${theme === 'dark' ? 'bg-gray-800/50 border-gray-700 text-white' : 'bg-white border-gray-300 text-gray-900'}`}
                        disabled={editingField !== 'gender'}
                      >
                        <option value="">Select gender</option>
                        <option value="male">Male</option>
                        <option value="female">Female</option>
                        <option value="other">Other</option>
                      </select>
                    </div>
                    {/* Location */}
                    <div className={`py-3 border-b ${theme === 'dark' ? 'border-gray-800' : 'border-gray-200'}`}>
                      <div className="flex items-center justify-between mb-2">
                        <label className={`text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>Location</label>
                        <button
                          onClick={() => setEditingField(editingField === 'location' ? null : 'location')}
                          className="text-blue-400 hover:text-blue-300 text-sm font-medium transition-colors"
                        >
                          {editingField === 'location' ? 'Cancel' : 'Edit'}
                        </button>
                      </div>
                      <input
                        type="text"
                        value={profileData.location}
                        onChange={(e) => setProfileData({ ...profileData, location: e.target.value })}
                        placeholder="Enter your location"
                        className={`w-full border rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500 ${theme === 'dark' ? 'bg-gray-800/50 border-gray-700 text-white placeholder:text-gray-500' : 'bg-white border-gray-300 text-gray-900 placeholder:text-gray-400'}`}
                        disabled={editingField !== 'location'}
                      />
                    </div>
                    {/* Birth Date */}
                    <div className={`py-3 border-b ${theme === 'dark' ? 'border-gray-800' : 'border-gray-200'}`}>
                      <div className="flex items-center justify-between mb-2">
                        <label className={`text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>Birth Date</label>
                        <button
                          onClick={() => setEditingField(editingField === 'birthDate' ? null : 'birthDate')}
                          className="text-blue-400 hover:text-blue-300 text-sm font-medium transition-colors"
                        >
                          {editingField === 'birthDate' ? 'Cancel' : 'Edit'}
                        </button>
                      </div>
                      <input
                        type="date"
                        value={profileData.birthDate}
                        onChange={(e) => setProfileData({ ...profileData, birthDate: e.target.value })}
                        className={`w-full border rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500 ${theme === 'dark' ? 'bg-gray-800/50 border-gray-700 text-white' : 'bg-white border-gray-300 text-gray-900'}`}
                        disabled={editingField !== 'birthDate'}
                      />
                    </div>
                    {/* Past History */}
                    <div className={`py-3 border-b ${theme === 'dark' ? 'border-gray-800' : 'border-gray-200'}`}>
                      <div className="flex items-center justify-between mb-2">
                        <label className={`text-sm ${theme === 'dark' ? 'text-gray-400' : 'text-gray-600'}`}>Past History</label>
                        <button
                          onClick={() => setEditingField(editingField === 'pastHistory' ? null : 'pastHistory')}
                          className="text-blue-400 hover:text-blue-300 text-sm font-medium transition-colors"
                        >
                          {editingField === 'pastHistory' ? 'Cancel' : 'Edit'}
                        </button>
                      </div>
                      <textarea
                        value={profileData.pastHistory}
                        onChange={(e) => setProfileData({ ...profileData, pastHistory: e.target.value })}
                        placeholder="Tell us about your medical history (allergies, previous conditions, etc.)"
                        rows={4}
                        className={`w-full border rounded-lg px-4 py-2 focus:outline-none focus:border-blue-500 resize-none ${theme === 'dark' ? 'bg-gray-800/50 border-gray-700 text-white placeholder:text-gray-500' : 'bg-white border-gray-300 text-gray-900 placeholder:text-gray-400'}`}
                        disabled={editingField !== 'pastHistory'}
                      />
                    </div>
                  </div>
                </div>

                {/* Save Button */}
                <button className="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white font-semibold py-3 rounded-xl transition-all duration-200">
                  Save Changes
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Login Overlay - Shows when user tries to interact without authentication */}
      {showLoginPrompt && !isAuthenticated && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          onClick={() => setShowLoginPrompt(false)}
          className="absolute inset-0 bg-gray-950/80 backdrop-blur-md flex items-center justify-center z-50"
        >
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ delay: 0.1 }}
            onClick={(e) => e.stopPropagation()}
            className="bg-gray-900 border border-gray-800 rounded-2xl p-8 max-w-md w-full mx-4 shadow-2xl"
          >
            <div className="text-center">
              <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-cyan-400 rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-lg shadow-blue-500/50">
                <Sparkles className="w-8 h-8 text-white" />
              </div>
              <h2 className="text-2xl font-bold mb-3 bg-gradient-to-r from-blue-400 to-cyan-400 text-transparent bg-clip-text">
                Welcome to Medaid AI
              </h2>
              <p className="text-gray-400 mb-6">
                Sign in to access your AI healthcare assistant and unlock powerful features
              </p>
              <div className="flex flex-col gap-3">
                <button
                  onClick={() => navigate('/login')}
                  className="w-full bg-blue-600 hover:bg-blue-500 text-white font-medium py-3 rounded-xl transition-colors"
                >
                  Sign In
                </button>
                <button
                  onClick={() => navigate('/signup')}
                  className="w-full bg-gray-800 hover:bg-gray-700 text-white font-medium py-3 rounded-xl transition-colors border border-gray-700"
                >
                  Create Account
                </button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}

      {/* Medical History Modal */}
      <MedicalHistory
        isOpen={showMedicalHistory}
        onClose={() => setShowMedicalHistory(false)}
      />

      {/* Settings Modal */}
      <AnimatePresence>
        {showSettings && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
              onClick={() => setShowSettings(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-md"
              onClick={(e) => e.stopPropagation()}
            >
              <div className={`${theme === 'dark' ? 'bg-gradient-to-br from-[#1a1f3a] via-[#1a1f3a] to-[#0f1525] border-blue-500/20' : 'bg-white border-gray-200'} rounded-3xl border p-6 shadow-2xl`}>
                {/* Header */}
                <div className="flex items-center justify-between mb-6">
                  <h3 className={`text-xl font-semibold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>Appearance</h3>
                  <button
                    onClick={() => setShowSettings(false)}
                    className={`w-8 h-8 rounded-lg flex items-center justify-center transition-colors ${theme === 'dark' ? 'bg-white/5 hover:bg-white/10' : 'bg-gray-100 hover:bg-gray-200'}`}
                  >
                    <svg className={`w-4 h-4 ${theme === 'dark' ? 'text-white' : 'text-gray-700'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                {/* Theme Toggle */}
                <div className="mb-6">
                  <label className={`block text-sm font-medium mb-3 ${theme === 'dark' ? 'text-gray-300' : 'text-gray-600'}`}>Theme Mode</label>
                  <button
                    onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
                    className={`w-full rounded-2xl p-1 relative overflow-hidden group ${theme === 'dark' ? 'bg-gradient-to-r from-[#e8d4b8] via-[#f5e6d3] to-[#e8d4b8]' : 'bg-gradient-to-r from-blue-100 via-indigo-100 to-blue-100 border border-blue-200'}`}
                  >
                    <div className="absolute inset-0 bg-gradient-to-r from-yellow-400/20 to-orange-400/20 opacity-0 group-hover:opacity-100 transition-opacity"></div>
                    <div className={`relative flex items-center justify-between px-6 py-4 rounded-xl ${theme === 'dark' ? 'bg-gradient-to-br from-[#2a1f3a]/95 to-[#1a1525]/95' : 'bg-white'}`}>
                      <span className={`font-semibold text-lg ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>{theme === 'dark' ? 'Dark Mode' : 'Light Mode'}</span>
                      <div className="relative flex items-center gap-2">
                        {theme === 'dark' ? (
                          <Moon className="w-8 h-8 text-yellow-200" fill="currentColor" />
                        ) : (
                          <Sun className="w-8 h-8 text-yellow-400" />
                        )}
                        <div className={`relative w-14 h-7 rounded-full transition-colors ${theme === 'dark' ? 'bg-blue-600' : 'bg-yellow-400'}`}>
                          <div className={`absolute top-0.5 w-6 h-6 bg-white rounded-full shadow-lg transition-all ${theme === 'dark' ? 'right-0.5' : 'left-0.5'}`}></div>
                        </div>
                      </div>
                    </div>
                  </button>
                </div>

                {/* Language Selector */}
                <div>
                  <label className={`block text-sm font-medium mb-3 ${theme === 'dark' ? 'text-gray-300' : 'text-gray-600'}`}>
                    <Languages className="w-4 h-4 inline mr-2" />
                    Language
                  </label>
                  <select
                    value={language}
                    onChange={(e) => handleLanguageChange(e.target.value)}
                    className={`w-full rounded-xl px-4 py-3 focus:outline-none transition-colors ${theme === 'dark' ? 'bg-[#1a1f3a] border border-blue-500/20 text-white focus:border-blue-500/50' : 'bg-gray-50 border border-gray-300 text-gray-900 focus:border-blue-400'}`}
                  >
                    <option value="english">English</option>
                    <option value="hindi">हिन्दी (Hindi)</option>
                    <option value="marathi">मराठी (Marathi)</option>
                  </select>
                </div>

                {/* Logout Button */}
                <div className={`mt-6 pt-6 border-t ${theme === 'dark' ? 'border-white/10' : 'border-gray-200'}`}>
                  <button
                    onClick={handleLogout}
                    className="w-full bg-red-500/10 hover:bg-red-500/20 text-red-500 rounded-xl px-4 py-3 flex items-center justify-center gap-2 transition-colors group"
                  >
                    <LogOut className="w-5 h-5 group-hover:scale-110 transition-transform" />
                    <span className="font-semibold">Logout</span>
                  </button>
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* Share Modal */}
      <AnimatePresence>
        {showShareModal && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
              onClick={() => setShowShareModal(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-md"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="bg-white rounded-3xl p-8 shadow-2xl relative">
                {/* Icon */}
                <div className="absolute -top-10 left-1/2 -translate-x-1/2 w-20 h-20 bg-white rounded-full flex items-center justify-center shadow-xl">
                  <Share2 className="w-8 h-8 text-gray-700" />
                </div>

                {/* Close Button */}
                <button
                  onClick={() => setShowShareModal(false)}
                  className="absolute top-6 right-6 w-8 h-8 bg-gray-100 hover:bg-gray-200 rounded-lg flex items-center justify-center transition-colors"
                >
                  <svg className="w-4 h-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>

                {/* Content */}
                <div className="mt-8">
                  <h2 className="text-2xl font-bold text-gray-900 text-center mb-2">Share with Friends</h2>
                  <p className="text-gray-600 text-center mb-6">
                    Trading is more effective when<br />you connect with friends!
                  </p>

                  {/* Share Link */}
                  <div className="mb-6">
                    <label className="block text-sm font-semibold text-gray-900 mb-2">Share you link</label>
                    <div className="flex items-center gap-2 bg-gray-50 rounded-xl px-4 py-3 border border-gray-200">
                      <input
                        type="text"
                        value="https://medaid.healthcare"
                        readOnly
                        className="flex-1 bg-transparent text-gray-700 text-sm focus:outline-none"
                      />
                      <button className="p-2 hover:bg-gray-200 rounded-lg transition-colors">
                        <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                        </svg>
                      </button>
                    </div>
                  </div>

                  {/* Social Share */}
                  <div>
                    <label className="block text-sm font-semibold text-gray-900 mb-3">Share to</label>
                    <div className="flex items-center justify-center gap-6">
                      <button className="flex flex-col items-center gap-2 group">
                        <div className="w-14 h-14 bg-blue-600 rounded-full flex items-center justify-center group-hover:scale-110 transition-transform">
                          <svg className="w-7 h-7 text-white" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
                          </svg>
                        </div>
                        <span className="text-xs text-gray-600">Facebook</span>
                      </button>

                      <button className="flex flex-col items-center gap-2 group">
                        <div className="w-14 h-14 bg-black rounded-full flex items-center justify-center group-hover:scale-110 transition-transform">
                          <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
                          </svg>
                        </div>
                        <span className="text-xs text-gray-600">X</span>
                      </button>

                      <button className="flex flex-col items-center gap-2 group">
                        <div className="w-14 h-14 bg-green-500 rounded-full flex items-center justify-center group-hover:scale-110 transition-transform">
                          <svg className="w-7 h-7 text-white" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z" />
                          </svg>
                        </div>
                        <span className="text-xs text-gray-600">Whatsapp</span>
                      </button>

                      <button className="flex flex-col items-center gap-2 group">
                        <div className="w-14 h-14 bg-blue-400 rounded-full flex items-center justify-center group-hover:scale-110 transition-transform">
                          <svg className="w-7 h-7 text-white" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
                          </svg>
                        </div>
                        <span className="text-xs text-gray-600">Telegram</span>
                      </button>

                      <button className="flex flex-col items-center gap-2 group">
                        <div className="w-14 h-14 bg-blue-700 rounded-full flex items-center justify-center group-hover:scale-110 transition-transform">
                          <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
                          </svg>
                        </div>
                        <span className="text-xs text-gray-600">LinkedIn</span>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
};

interface NavItemProps {
  icon: React.ElementType;
  label: string;
  active?: boolean;
  onClick?: () => void;
  theme: 'light' | 'dark';
}

const NavItem: React.FC<NavItemProps> = ({ icon: Icon, label, active, onClick, theme }) => {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all relative group ${active
        ? theme === 'dark'
          ? 'bg-gradient-to-r from-blue-600/20 to-purple-600/20 text-white'
          : 'bg-gradient-to-r from-blue-100 to-purple-100 text-gray-900'
        : theme === 'dark'
          ? 'text-gray-400 hover:text-white hover:bg-gray-800/30'
          : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
        }`}
    >
      {active && (
        <div className={`absolute inset-0 ${theme === 'dark' ? 'bg-gradient-to-r from-blue-600/10 to-purple-600/10' : 'bg-gradient-to-r from-blue-200/50 to-purple-200/50'} rounded-lg blur-xl`}></div>
      )}
      <Icon className="w-5 h-5 relative z-10" />
      <span className="text-sm font-medium relative z-10">{label}</span>
      {active && (
        <div className="absolute right-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-gradient-to-b from-blue-500 to-purple-600 rounded-l-full"></div>
      )}
    </button>
  );
};

export default Dashboard;
