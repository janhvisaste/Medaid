import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Activity, Check, Copy, FileText, Loader2, MapPin, Mic, Paperclip, Plus,
  Search, Send, Sparkles, Stethoscope, X,
} from 'lucide-react';
import authService from '../../services/authService';
import apiService from '../../services/apiService';
import type { Facility } from '../../services/apiService';
import { medaidClasses } from '../../styles/medaidTokens';
import { Skeleton } from '../ui/Skeleton';
import ModelSelector from '../ui/ModelSelector';
import ConfirmDeleteButton from '../ui/ConfirmDeleteButton';
import AssessmentCard from '../Results/AssessmentCard';
import FacilityPanel from '../Consultation/FacilityPanel';

interface Message {
  id: string;
  text: string;
  sender: 'user' | 'ai';
  timestamp?: string;
  isDegraded?: boolean;
  // Structured assessment fields, present when this AI turn completed a full
  // triage assessment (chat and the guided flow share one pipeline now).
  riskLevel?: string;
  confidence?: number;
  possibleConditions?: any[];
  recommendations?: string[];
  whenToSeekCare?: string;
  requiresHumanReview?: boolean;
  reasoning?: string;
  triageId?: number;
}
interface ChatSummary { id: number; title: string; preview: string; date: string; }

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8001/api';

// A considered loading sequence — an assessment can take 1–5s and the person
// waiting is often anxious, so we narrate progress instead of showing a bare
// spinner. Purely informational text (safe to change under reduced-motion).
const THINKING_STEPS = [
  'Reading your description…',
  'Checking for urgent signs…',
  'Weighing possible causes…',
  'Preparing your guidance…',
];

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversations, setConversations] = useState<ChatSummary[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [input, setInput] = useState('');
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [thinking, setThinking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [selectedModelId, setSelectedModelId] = useState('');
  const [listening, setListening] = useState(false);
  const [pincode, setPincode] = useState('');
  const [facilitiesByMessage, setFacilitiesByMessage] = useState<Record<string, Facility[]>>({});
  const [loadingFacilitiesId, setLoadingFacilitiesId] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [thinkingStep, setThinkingStep] = useState(0);
  // Which message opened the slide-in facility finder (null = closed).
  const [facilityPanelFor, setFacilityPanelFor] = useState<Message | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  // The conversation list is a fixed column on desktop and a drawer on mobile,
  // where there is no room for a permanent third pane.
  const [historyOpen, setHistoryOpen] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const recognitionRef = useRef<any>(null);

  // Web Speech API is Chrome/Safari-prefixed and absent in some browsers; when
  // unsupported we hide the mic entirely rather than showing a dead control.
  const voiceSupported =
    typeof window !== 'undefined' &&
    ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window);

  const headers = () => authService.getAuthHeaders();

  const resizeTextarea = () => {
    const node = textareaRef.current;
    if (!node) return;
    node.style.height = 'auto';
    node.style.height = `${Math.min(node.scrollHeight, 160)}px`;
  };

  const loadConversations = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE}/chat/conversations/`, { headers: headers() });
      if (!response.ok) throw new Error('Unable to load conversations');
      const data = await response.json();
      const list = Array.isArray(data.conversations) ? data.conversations : [];
      setConversations(list.map((conversation: any) => ({
        id: conversation.id,
        title: conversation.title || 'New conversation',
        preview: conversation.preview_message || 'No messages yet',
        date: conversation.last_activity ? new Date(conversation.last_activity).toLocaleDateString() : '',
      })));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load conversations');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadConversations(); }, [loadConversations]);
  useEffect(() => { resizeTextarea(); }, [input]);

  // Advance the narrated loading copy while the assistant is working.
  useEffect(() => {
    if (!thinking) { setThinkingStep(0); return; }
    const id = setInterval(() => setThinkingStep(step => (step + 1) % THINKING_STEPS.length), 1600);
    return () => clearInterval(id);
  }, [thinking]);

  // Prefill the facility-search pincode from the profile so a high/emergency
  // assessment card can offer nearby care without asking the user to retype it.
  useEffect(() => {
    apiService.getUserProfile().then(profile => {
      if (profile.pincode) setPincode(profile.pincode);
    }).catch(() => {});
  }, []);

  // Dictate into the message box using the browser's Web Speech API. Final
  // transcripts are appended to whatever is already typed; a second tap stops.
  const toggleVoiceInput = useCallback(() => {
    if (!voiceSupported) return;
    if (listening) {
      recognitionRef.current?.stop();
      return;
    }
    const SpeechRecognitionCtor =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition = new SpeechRecognitionCtor();
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.continuous = false;
    recognition.onresult = (event: any) => {
      const transcript = Array.from(event.results)
        .map((result: any) => result[0]?.transcript ?? '')
        .join(' ')
        .trim();
      if (transcript) {
        setInput((prev) => (prev ? `${prev} ${transcript}` : transcript));
      }
    };
    recognition.onerror = (event: any) => {
      // 'no-speech'/'aborted' are benign (user paused or tapped stop).
      if (event.error !== 'no-speech' && event.error !== 'aborted') {
        setError('Voice input failed. Please try again or type your message.');
      }
      setListening(false);
    };
    recognition.onend = () => setListening(false);
    recognitionRef.current = recognition;
    try {
      recognition.start();
      setListening(true);
    } catch {
      setListening(false);
    }
  }, [listening, voiceSupported]);

  // Stop an in-flight recognition session if the user navigates away.
  useEffect(() => () => recognitionRef.current?.stop?.(), []);

  // Pulls the structured-assessment fields chat_send_message now attaches to
  // an assistant message's metadata (same contract for both the regular and
  // emergency-short-circuit paths) into the shape the chat UI renders.
  const assessmentFieldsFromMetadata = (metadata: any) => metadata?.risk_level ? {
    riskLevel: metadata.risk_level,
    confidence: metadata.confidence,
    possibleConditions: metadata.possible_conditions,
    recommendations: metadata.recommendations,
    whenToSeekCare: metadata.when_to_seek_care,
    requiresHumanReview: !!metadata.requires_human_review,
    reasoning: metadata.reasoning,
    triageId: metadata.triage_id ?? undefined,
  } : {};

  const createConversation = async () => {
    const response = await fetch(`${API_BASE}/chat/conversations/`, { method: 'POST', headers: headers() });
    if (!response.ok) throw new Error('Unable to start a conversation');
    const data = await response.json();
    const id = data.conversation.id as number;
    setActiveId(id);
    setMessages([]);
    await loadConversations();
    return id;
  };

  const removeConversation = async (id: number) => {
    await apiService.deleteConversation(id);
    // Clear the reading pane if the open conversation was the one removed.
    if (activeId === id) {
      setActiveId(null);
      setMessages([]);
    }
    await loadConversations();
  };

  const selectConversation = async (id: number) => {
    try {
      setError(null);
      setActiveId(id);
      const response = await fetch(`${API_BASE}/chat/conversations/${id}/messages/list/`, { headers: headers() });
      if (!response.ok) throw new Error('Unable to open this conversation');
      const data = await response.json();
      setMessages((data.messages || []).map((message: any) => ({
        id: String(message.id),
        text: message.content,
        sender: message.role === 'user' ? 'user' : 'ai',
        timestamp: message.created_at,
        isDegraded: !!message.metadata?.is_degraded,
        ...assessmentFieldsFromMetadata(message.metadata),
      })));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to open this conversation');
    }
  };

  const handleSend = async () => {
    if ((!input.trim() && !file) || thinking) return;
    const text = input.trim();
    const selectedFile = file;
    setInput('');
    setFile(null);
    setError(null);
    setThinking(true);
    setMessages(previous => [...previous, { id: `local-${Date.now()}`, text: selectedFile ? `${text}\n\nAttached: ${selectedFile.name}` : text, sender: 'user' }]);
    try {
      const conversationId = activeId || await createConversation();
      const body = selectedFile ? (() => { const form = new FormData(); form.append('content', text); form.append('file', selectedFile); if (selectedModelId) form.append('model_id', selectedModelId); return form; })() : JSON.stringify({ content: text, ...(selectedModelId ? { model_id: selectedModelId } : {}) });
      const requestHeaders: HeadersInit = selectedFile ? { Authorization: `Bearer ${authService.getToken() || ''}` } : headers();
      const response = await fetch(`${API_BASE}/chat/conversations/${conversationId}/messages/`, { method: 'POST', headers: requestHeaders, body });
      if (!response.ok) throw new Error('The assistant could not respond. Please try again.');
      const data = await response.json();
      setMessages(previous => [
        ...previous.filter(message => !message.id.startsWith('local-')),
        { id: String(data.user_message.id), text: data.user_message.content, sender: 'user', timestamp: data.user_message.created_at },
        {
          id: String(data.assistant_message.id), text: data.assistant_message.content, sender: 'ai',
          timestamp: data.assistant_message.created_at, isDegraded: !!data.assistant_message.metadata?.is_degraded,
          ...assessmentFieldsFromMetadata(data.assistant_message.metadata),
        },
      ]);
      await loadConversations();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The assistant could not respond');
    } finally {
      setThinking(false);
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); handleSend(); }
  };

  // Copy the assistant's reply — the one contextual action that needs no
  // backend support. Regenerate/bookmark would require endpoints that don't
  // exist yet, so they are deliberately absent rather than faked.
  const copyMessage = async (message: Message) => {
    try {
      await navigator.clipboard.writeText(message.text);
      setCopiedId(message.id);
      setTimeout(() => setCopiedId(current => (current === message.id ? null : current)), 2000);
    } catch {
      setError('Could not copy to clipboard.');
    }
  };

  const openFacilityPanel = (message: Message) => {
    setFacilityPanelFor(message);
    if (!facilitiesByMessage[message.id]) findCareFor(message);
  };

  const findCareFor = async (message: Message) => {
    if (!message.riskLevel) return;
    setLoadingFacilitiesId(message.id);
    try {
      const results = await apiService.getNearbyFacilities({
        location: pincode || undefined,
        risk_level: message.riskLevel,
        radius: 10,
      });
      setFacilitiesByMessage(previous => ({ ...previous, [message.id]: results }));
    } catch {
      setFacilitiesByMessage(previous => ({ ...previous, [message.id]: [] }));
    } finally {
      setLoadingFacilitiesId(null);
    }
  };

  const downloadReport = async (message: Message) => {
    if (!message.triageId) return;
    setDownloadingId(message.id);
    try {
      const blob = await apiService.downloadAssessmentPDF(message.triageId);
      apiService.downloadPDFFile(blob, `assessment_${message.triageId}.pdf`);
    } catch {
      setError('Report generation failed. Please try again.');
    } finally {
      setDownloadingId(null);
    }
  };

  const filteredConversations = conversations.filter(conversation => `${conversation.title} ${conversation.preview}`.toLowerCase().includes(search.toLowerCase()));

  if (loading) return <div className="mx-auto grid max-w-7xl gap-6 px-4 py-8 md:grid-cols-[280px_1fr] md:px-6"><div className="space-y-3"><Skeleton className="h-11" /><Skeleton className="h-9" /><Skeleton className="h-9" /><Skeleton className="h-9" /></div><div className="space-y-4"><Skeleton className="h-36" /><Skeleton className="h-[420px]" /></div></div>;

  return (
    // Fixed workspace frame: the sidebar and chat header/composer stay put and
    // only the message thread scrolls, so orientation is never lost.
    <div className="flex h-full min-h-0 gap-4 overflow-hidden p-4 md:gap-5 md:p-5">
      {historyOpen && (
        <button aria-label="Close conversations" onClick={() => setHistoryOpen(false)} className="fixed inset-0 z-40 bg-[var(--medaid-overlay)] md:hidden" />
      )}
      <aside className={`${medaidClasses.compactCard} flex w-72 shrink-0 flex-col p-3 max-md:fixed max-md:inset-y-0 max-md:left-0 max-md:z-50 max-md:rounded-none max-md:transition-transform max-md:duration-200 ${historyOpen ? 'max-md:translate-x-0' : 'max-md:-translate-x-full'}`}>
        <button onClick={() => { createConversation().catch(err => setError(err.message)); setHistoryOpen(false); }} className={`mb-3 w-full px-4 py-3 ${medaidClasses.buttonPrimary}`}><Plus className="h-4 w-4" /> New conversation</button>
        <div className="relative mb-4"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--medaid-ink-faint)]" /><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search conversations" className={`${medaidClasses.input} pl-9`} /></div>
        <div className="mb-2 flex items-center gap-2 px-2 text-xs font-semibold uppercase tracking-[0.16em] text-[var(--medaid-ink-muted)]"><Stethoscope className="h-3.5 w-3.5" /> Recent consultations</div>
        <div className="min-h-0 flex-1 space-y-1 overflow-y-auto">
          {filteredConversations.length === 0 ? <p className="px-2 py-4 text-sm text-[var(--medaid-ink-muted)]">Your conversations will appear here.</p> : filteredConversations.map(conversation => (
            // Row is a flex container, not a button — the delete control is
            // itself a button and must not be nested inside another one.
            <div key={conversation.id} className={`group flex items-center gap-1 rounded-card pr-1 transition-colors ${activeId === conversation.id ? 'bg-[var(--medaid-accent-soft)]' : 'hover:bg-[var(--medaid-surface-muted)]'}`}>
              <button onClick={() => { selectConversation(conversation.id); setHistoryOpen(false); }} className="min-w-0 flex-1 rounded-card px-3 py-2.5 text-left">
                <p className="truncate text-sm font-semibold text-[var(--medaid-ink)]">{conversation.title}</p>
                <p className="mt-1 truncate text-xs text-[var(--medaid-ink-muted)]">{conversation.preview}</p>
              </button>
              <ConfirmDeleteButton
                label={`Delete conversation: ${conversation.title}`}
                onConfirm={() => removeConversation(conversation.id)}
                onError={setError}
                className="opacity-0 transition-opacity focus-visible:opacity-100 group-hover:opacity-100"
              />
            </div>
          ))}
        </div>
        <div className="mt-4 hidden border-t border-[var(--medaid-border)] pt-3 md:block"><p className="px-2 text-xs leading-5 text-[var(--medaid-ink-muted)]">Your conversations are private and can be reviewed with your care team.</p></div>
      </aside>

      <section className={`${medaidClasses.card} flex min-w-0 flex-1 flex-col overflow-hidden`}>
        {/* Fixed chat header */}
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-[var(--medaid-border)] px-5 py-3.5">
          <div className="flex min-w-0 items-center gap-2.5">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-brand text-brand-contrast"><Activity className="h-4 w-4" aria-hidden="true" /></span>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-[var(--medaid-ink)]">AI health assistant</p>
              <p className="mt-0.5 truncate text-xs text-[var(--medaid-ink-muted)]">Preliminary guidance, not a diagnosis</p>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <span className="hidden items-center gap-1.5 rounded-pill bg-[var(--medaid-surface-muted)] px-2.5 py-1 text-xs font-medium text-[var(--medaid-ink-soft)] sm:inline-flex">
              <span className="h-1.5 w-1.5 rounded-pill bg-brand" aria-hidden="true" /> Ready
            </span>
            <button onClick={() => setHistoryOpen(true)} aria-label="Show conversations" title="Conversations" className={`${medaidClasses.buttonGhost} p-2 md:hidden`}><Stethoscope className="h-4 w-4" /></button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-5 md:p-8" role="log" aria-live="polite" aria-label="Conversation with the AI health assistant">
            {error && <div role="alert" className="mb-4 flex items-start justify-between gap-3 rounded-md border border-[var(--risk-emergency-border)] bg-[var(--risk-emergency-soft)] px-4 py-3 text-sm text-[var(--risk-emergency-text)]"><span>{error}</span><button onClick={() => setError(null)} aria-label="Dismiss error"><X className="h-4 w-4" /></button></div>}
            {messages.length === 0 ? <div className="mx-auto flex max-w-2xl flex-col items-center justify-center py-10 text-center"><div className="mb-5 flex h-14 w-14 items-center justify-center rounded-card bg-brand-100 text-brand-700 dark:bg-[var(--medaid-accent-soft)] dark:text-[var(--medaid-accent-strong)]"><Activity className="h-7 w-7" /></div><h3 className="font-display text-2xl font-medium text-[var(--medaid-ink)] md:text-3xl">How can Medaid help today?</h3><p className="mt-2 max-w-md text-sm leading-6 text-[var(--medaid-ink-soft)]">A clear description helps the assistant ask better questions and prepare a useful summary for your clinician.</p><p className="mt-3 inline-flex items-center gap-1.5 rounded-pill bg-[var(--medaid-surface-muted)] px-3 py-1.5 text-xs text-[var(--medaid-ink-muted)]"><Sparkles className="h-3.5 w-3.5 text-brand" aria-hidden="true" /> MedAid may ask a few short follow-up questions — answering them leads to a safer, more accurate assessment.</p><div className="mt-7 grid w-full gap-3 sm:grid-cols-3"><button onClick={() => textareaRef.current?.focus()} className={`${medaidClasses.compactCardHover} p-4 text-left`}><Activity className="mb-3 h-5 w-5 text-brand" /><p className="text-sm font-semibold text-[var(--medaid-ink)]">Describe symptoms</p><p className="mt-1 text-xs text-[var(--medaid-ink-muted)]">Get a guided assessment</p></button><button onClick={() => navigate('/medical-history-insights')} className={`${medaidClasses.compactCardHover} p-4 text-left`}><FileText className="mb-3 h-5 w-5 text-brand" /><p className="text-sm font-semibold text-[var(--medaid-ink)]">Review a report</p><p className="mt-1 text-xs text-[var(--medaid-ink-muted)]">See extracted findings</p></button><button onClick={() => fileRef.current?.click()} className={`${medaidClasses.compactCardHover} p-4 text-left`}><MapPin className="mb-3 h-5 w-5 text-brand" /><p className="text-sm font-semibold text-[var(--medaid-ink)]">Attach a report</p><p className="mt-1 text-xs text-[var(--medaid-ink-muted)]">Analyzed alongside your message</p></button></div></div> :<div className="mx-auto max-w-3xl space-y-5">{messages.map(message => {
              const isUser = message.sender === 'user';
              // A completed assessment renders as a structured card. The raw
              // reply text behind it is the same content in numbered-prose form
              // (model name, reasoning, causes, steps) — showing both doubled
              // the height of the turn and read as debug output.
              const isAssessment = !isUser && !!message.riskLevel;
              return (
                <div key={message.id} className={`flex animate-fade-in gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
                  {!isUser && (
                    <span className="mt-1 hidden h-8 w-8 shrink-0 items-center justify-center rounded-md bg-brand text-brand-contrast sm:flex" aria-hidden="true">
                      <Activity className="h-4 w-4" />
                    </span>
                  )}
                  <div className={isUser ? 'max-w-[85%]' : 'min-w-0 max-w-[92%] flex-1'}>
                    {isAssessment ? (
                      <AssessmentCard
                        message={message}
                        downloading={downloadingId === message.id}
                        onFindCare={() => openFacilityPanel(message)}
                        onDownload={() => downloadReport(message)}
                      />
                    ) : (
                      <div className={`rounded-card px-4 py-3 text-sm leading-7 ${isUser ? 'bg-brand text-brand-contrast' : 'border border-[var(--medaid-border)] bg-[var(--medaid-surface-muted)] text-[var(--medaid-ink-soft)]'}`}>
                        {/* Degraded turns reuse the message card so they read as part of
                            the conversation, not an unrelated system error. */}
                        {message.isDegraded && <div className="mb-2 flex items-start gap-2 rounded-md border border-[var(--risk-medium-border)] bg-[var(--risk-medium-soft)] px-3 py-2 text-xs font-medium text-[var(--risk-medium-text)]"><Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0" />A full AI analysis couldn't be completed. This is general safety guidance, not a diagnosis — please consult a healthcare professional.</div>}
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.text}</ReactMarkdown>
                      </div>
                    )}

                    {/* Quiet metadata + contextual actions, sitting under the
                        message rather than in a global toolbar. Risk and
                        confidence live in the card itself for an assessment. */}
                    {!isUser && (
                      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 px-1">
                        {message.timestamp && (
                          <span className="text-[11px] tabular-nums text-[var(--medaid-ink-faint)]">
                            {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        )}
                        <button
                          onClick={() => copyMessage(message)}
                          aria-label="Copy this reply"
                          title="Copy"
                          className="ml-auto inline-flex items-center gap-1 rounded-control px-1.5 py-1 text-[11px] text-[var(--medaid-ink-faint)] transition-colors hover:bg-[var(--medaid-surface-muted)] hover:text-[var(--medaid-ink-soft)]"
                        >
                          {copiedId === message.id ? <><Check className="h-3.5 w-3.5" /> Copied</> : <><Copy className="h-3.5 w-3.5" /> Copy</>}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {thinking && (
              <div className="flex animate-fade-in items-center gap-3" role="status" aria-live="polite">
                <div className="inline-flex items-center gap-2.5 rounded-card border border-[var(--medaid-border)] bg-[var(--medaid-surface-muted)] px-4 py-3">
                  <span className="flex gap-1" aria-hidden="true"><span className="h-2 w-2 animate-bounce rounded-pill bg-brand" /><span className="h-2 w-2 animate-bounce rounded-pill bg-brand [animation-delay:150ms]" /><span className="h-2 w-2 animate-bounce rounded-pill bg-brand [animation-delay:300ms]" /></span>
                  <span className="text-sm text-[var(--medaid-ink-soft)]">{THINKING_STEPS[thinkingStep]}</span>
                </div>
              </div>
            )}
            </div>}
        </div>

        {/* Fixed composer. Controls live inside the input container so the field
            reads as one self-contained object rather than a toolbar plus a box. */}
        <div className="shrink-0 border-t border-[var(--medaid-border)] p-4 md:px-5">
          <div className="mx-auto max-w-3xl">
            <div className="mb-3"><ModelSelector value={selectedModelId} onChange={setSelectedModelId} disabled={thinking} /></div>
            <div className="rounded-panel border border-[var(--medaid-border-strong)] bg-[var(--medaid-surface)] p-2 shadow-e1 transition-colors focus-within:border-brand focus-within:ring-2 focus-within:ring-[var(--medaid-focus)]">
              <textarea
                ref={textareaRef} value={input} onChange={event => setInput(event.target.value)}
                onKeyDown={handleKeyDown} rows={1} maxLength={4000}
                placeholder="Describe your symptoms…"
                className="max-h-40 min-h-11 w-full resize-none bg-transparent px-3 py-2 text-sm leading-6 text-[var(--medaid-ink)] outline-none placeholder:text-[var(--medaid-ink-faint)]"
                aria-label="Describe your symptoms"
              />
              {file && (
                <div className="mx-2 mb-2 flex items-center justify-between rounded-md bg-[var(--medaid-surface-muted)] px-3 py-2 text-xs text-[var(--medaid-ink-soft)]">
                  <span className="flex min-w-0 items-center gap-2"><Paperclip className="h-3.5 w-3.5 shrink-0" /><span className="truncate">{file.name}</span></span>
                  <button onClick={() => setFile(null)} aria-label="Remove attached file"><X className="h-3.5 w-3.5" /></button>
                </div>
              )}
              <div className="flex items-center justify-between gap-2 px-2 pb-1">
                <div className="flex min-w-0 items-center gap-1">
                  <input ref={fileRef} type="file" accept=".pdf,image/*" className="hidden" onChange={event => setFile(event.target.files?.[0] || null)} />
                  <button onClick={() => fileRef.current?.click()} className="rounded-control p-2 text-[var(--medaid-ink-muted)] transition-colors hover:bg-[var(--medaid-surface-muted)] hover:text-[var(--medaid-ink)]" aria-label="Attach medical report" title="Attach a report"><Paperclip className="h-4 w-4" /></button>
                  {voiceSupported && (
                    <button type="button" onClick={toggleVoiceInput} aria-pressed={listening} aria-label={listening ? 'Stop voice input' : 'Start voice input'} title={listening ? 'Stop recording' : 'Dictate'}
                      className={`rounded-control p-2 transition-colors ${listening ? 'bg-[var(--risk-emergency-soft)] text-[var(--risk-emergency-text)]' : 'text-[var(--medaid-ink-muted)] hover:bg-[var(--medaid-surface-muted)] hover:text-[var(--medaid-ink)]'}`}>
                      <Mic className={`h-4 w-4 ${listening ? 'animate-pulse' : ''}`} />
                    </button>
                  )}
                  {listening
                    ? <span className="inline-flex items-center gap-1.5 text-xs font-medium text-[var(--risk-emergency-text)]"><span className="h-1.5 w-1.5 animate-pulse rounded-pill bg-[var(--risk-emergency-line)]" aria-hidden="true" />Recording…</span>
                    : <span className="hidden truncate text-xs text-[var(--medaid-ink-faint)] sm:inline">Enter to send · Shift+Enter for a new line</span>}
                </div>
                <button disabled={(!input.trim() && !file) || thinking} onClick={handleSend} className="flex h-9 w-9 shrink-0 items-center justify-center rounded-control bg-brand text-brand-contrast transition-colors hover:bg-brand-hover disabled:cursor-not-allowed disabled:opacity-40" aria-label="Send message">
                  {thinking ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                </button>
              </div>
            </div>
            <p className="mt-2 text-center text-[11px] text-[var(--medaid-ink-faint)]">For emergencies, call local emergency services immediately.</p>
          </div>
        </div>
      </section>

      <FacilityPanel
        open={!!facilityPanelFor}
        onClose={() => setFacilityPanelFor(null)}
        facilities={facilityPanelFor ? facilitiesByMessage[facilityPanelFor.id] : undefined}
        loading={!!facilityPanelFor && loadingFacilitiesId === facilityPanelFor.id}
        riskLevel={facilityPanelFor?.riskLevel}
        pincode={pincode}
        onPincodeChange={setPincode}
        onSearch={() => facilityPanelFor && findCareFor(facilityPanelFor)}
      />
    </div>
  );
};

export default Dashboard;
