import React, { useCallback, useEffect, useState } from 'react';
import {
  Activity, AlertCircle, AlertTriangle, ArrowLeft, CheckCircle2, ClipboardList,
  Download, FileText, HelpCircle, Loader2, ShieldAlert, Sparkles, Stethoscope, TrendingUp,
} from 'lucide-react';
import { useNavigate, useParams } from 'react-router-dom';
import apiService from '../../services/apiService';
import type { DetailedReportAnalysis, VerifiedFinding } from '../../services/apiService';
import { medaidClasses } from '../../styles/medaidTokens';
import { Skeleton } from '../ui/Skeleton';

// Verified status → presentation. Colour is always paired with a text label.
const STATUS_META: Record<string, { label: string; cls: string; line: string }> = {
  critical_low: { label: 'Critically low', cls: 'bg-[var(--risk-emergency-soft)] text-[var(--risk-emergency-text)] border-[var(--risk-emergency-border)]', line: 'var(--risk-emergency-line)' },
  critical_high: { label: 'Critically high', cls: 'bg-[var(--risk-emergency-soft)] text-[var(--risk-emergency-text)] border-[var(--risk-emergency-border)]', line: 'var(--risk-emergency-line)' },
  low: { label: 'Low', cls: 'bg-[var(--risk-high-soft)] text-[var(--risk-high-text)] border-[var(--risk-high-border)]', line: 'var(--risk-high-line)' },
  high: { label: 'High', cls: 'bg-[var(--risk-high-soft)] text-[var(--risk-high-text)] border-[var(--risk-high-border)]', line: 'var(--risk-high-line)' },
  normal: { label: 'Normal', cls: 'bg-[var(--risk-low-soft)] text-[var(--risk-low-text)] border-[var(--risk-low-border)]', line: 'var(--risk-low-line)' },
  unknown: { label: 'Not verified', cls: 'bg-[var(--risk-neutral-soft)] text-[var(--risk-neutral-text)] border-[var(--risk-neutral-border)]', line: 'var(--risk-neutral-line)' },
};

const OVERALL_META: Record<string, { title: string; tone: string; Icon: React.ElementType }> = {
  urgent: { title: 'Needs prompt medical attention', tone: 'bg-[var(--risk-emergency-soft)] text-[var(--risk-emergency-text)] border-[var(--risk-emergency-border)]', Icon: ShieldAlert },
  attention_needed: { title: 'Some results need follow-up', tone: 'bg-[var(--risk-high-soft)] text-[var(--risk-high-text)] border-[var(--risk-high-border)]', Icon: AlertTriangle },
  reassuring: { title: 'Everything checked looks normal', tone: 'bg-[var(--risk-low-soft)] text-[var(--risk-low-text)] border-[var(--risk-low-border)]', Icon: CheckCircle2 },
  unclear: { title: 'This report could not be fully interpreted', tone: 'bg-[var(--risk-neutral-soft)] text-[var(--risk-neutral-text)] border-[var(--risk-neutral-border)]', Icon: HelpCircle },
};

const URGENCY_LABEL: Record<string, string> = {
  urgent: 'See a doctor urgently',
  soon: 'Follow up soon',
  routine: 'Routine follow-up',
};

const StatusPill: React.FC<{ status: string }> = ({ status }) => {
  const meta = STATUS_META[status] || STATUS_META.unknown;
  return (
    <span className={`inline-flex shrink-0 items-center gap-1.5 rounded-pill border px-2.5 py-0.5 text-xs font-semibold ${meta.cls}`}>
      {meta.label}
    </span>
  );
};

const Section: React.FC<{ title: string; icon: React.ElementType; children: React.ReactNode }> = ({ title, icon: Icon, children }) => (
  <div>
    <div className="mb-2.5 flex items-center gap-2">
      <Icon className="h-4 w-4 text-brand" aria-hidden="true" />
      <h4 className="text-sm font-semibold text-[var(--medaid-ink)]">{title}</h4>
    </div>
    {children}
  </div>
);

const MedicalDocumentDetail: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const [document, setDocument] = useState<any>(null);
  const [analysis, setAnalysis] = useState<DetailedReportAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      setDocument(await apiService.getMedicalReportById(Number(id)));
    } catch {
      setError('Unable to load this medical document.');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const analyze = async () => {
    if (!id) return;
    setAnalyzing(true);
    setError(null);
    try {
      const result = await apiService.analyzeReportDetailed(Number(id));
      // A 202-shaped "still processing" response resolves through axios like
      // any other success — it must be checked explicitly rather than stored
      // as a finished analysis, or the UI silently renders an empty result.
      if (result.pending || result.success === false) {
        setError(result.message || 'This report is still being processed. Please try again in a moment.');
        return;
      }
      setAnalysis(result);
      // Analysis runs OCR and persists the extracted text server-side. Without
      // refetching, the "Extracted information" panel keeps showing the stale
      // pre-analysis value and claims no text exists while results are on screen.
      try {
        setDocument(await apiService.getMedicalReportById(Number(id)));
      } catch {
        /* keeping the analysis on screen matters more than refreshing the panel */
      }
    } catch {
      setError('Detailed analysis is unavailable right now.');
    } finally {
      setAnalyzing(false);
    }
  };

  if (loading) return <div className="mx-auto max-w-5xl space-y-4 px-4 py-8 md:px-6"><Skeleton className="h-24" /><Skeleton className="h-64" /><Skeleton className="h-48" /></div>;
  if (!document) return <div className="mx-auto max-w-5xl px-4 py-12 text-sm text-[var(--risk-emergency-text)]">{error || 'Document not found.'}</div>;

  const consultation = analysis?.consultation;
  const verification = analysis?.verification;
  const findings: VerifiedFinding[] = analysis?.abnormal_findings || [];
  const overall = verification?.overall_status || 'unclear';
  const overallMeta = OVERALL_META[overall] || OVERALL_META.unclear;

  return (
    <div className="mx-auto max-w-5xl space-y-5 px-4 py-8 md:px-6">
      <button onClick={() => navigate('/medical-history-insights')} className={`${medaidClasses.buttonGhost} px-2 py-2`}>
        <ArrowLeft className="mr-2 inline h-4 w-4" />Back to reports
      </button>

      {error && (
        <div role="alert" className="flex items-center justify-between rounded-md border border-[var(--risk-emergency-border)] bg-[var(--risk-emergency-soft)] px-4 py-3 text-sm text-[var(--risk-emergency-text)]">
          <span className="flex items-center gap-2"><AlertCircle className="h-4 w-4" />{error}</span>
          <button onClick={load} className="font-semibold underline">Retry</button>
        </div>
      )}

      <header className={`${medaidClasses.heroPanel} p-6 md:p-8`}>
        <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-md bg-[var(--medaid-surface)]/80 text-brand"><FileText className="h-5 w-5" /></div>
            <h2 className={medaidClasses.dashboardTitle}>{document.file_name}</h2>
            <p className={`mt-2 ${medaidClasses.bodySmall}`}>{document.upload_date ? new Date(document.upload_date).toLocaleString() : 'Uploaded document'}</p>
          </div>
          {document.file && <a href={document.file} download className={`px-4 py-2.5 ${medaidClasses.buttonSecondary}`}><Download className="h-4 w-4" />Download file</a>}
        </div>
      </header>

      <section className={`${medaidClasses.card} p-6`}>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="font-display text-lg font-medium text-[var(--medaid-ink)]">Your results explained</h3>
            <p className={medaidClasses.bodySmall}>Values are checked against clinical reference ranges, then explained in plain language.</p>
          </div>
          <button onClick={analyze} disabled={analyzing} className={`shrink-0 px-4 py-2.5 ${medaidClasses.buttonPrimary}`}>
            {analyzing ? <><Loader2 className="h-4 w-4 animate-spin" />Analyzing…</> : <><Sparkles className="h-4 w-4" />{analysis ? 'Re-analyze' : 'Analyze report'}</>}
          </button>
        </div>

        {analysis && (
          <div className="mt-6 space-y-6 border-t border-[var(--medaid-border)] pt-6">
            {/* Headline verdict */}
            <div role="status" className={`flex items-start gap-3 rounded-card border p-4 ${overallMeta.tone}`}>
              <overallMeta.Icon className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
              <div className="min-w-0">
                <p className="text-sm font-bold">{overallMeta.title}</p>
                {consultation?.headline && <p className="mt-1 text-sm leading-6">{consultation.headline}</p>}
                {verification && (
                  <p className="mt-2 text-xs opacity-90 tabular-nums">
                    {verification.normal} normal · {verification.abnormal} outside range · {verification.critical} critical
                    {verification.unverified > 0 && ` · ${verification.unverified} not verified`}
                  </p>
                )}
              </div>
            </div>

            {consultation?.opening && (
              <p className="text-sm leading-7 text-[var(--medaid-ink-soft)]">{consultation.opening}</p>
            )}

            {consultation?.whats_working_well && (
              <Section title="What's working well" icon={CheckCircle2}>
                <p className="text-sm leading-7 text-[var(--medaid-ink-soft)]">{consultation.whats_working_well}</p>
              </Section>
            )}

            {/* Verified findings needing attention */}
            {findings.length > 0 && (
              <Section title="What needs attention" icon={AlertTriangle}>
                <ul className="space-y-3">
                  {findings.map((finding, index) => {
                    const meta = STATUS_META[finding.status] || STATUS_META.unknown;
                    const note = consultation?.needs_attention?.find(n => n.test_name === finding.test_name);
                    return (
                      <li key={index} style={{ borderLeftColor: meta.line }} className="rounded-card border border-l-4 border-[var(--medaid-border)] bg-[var(--medaid-surface-muted)]/50 p-4">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="text-sm font-semibold text-[var(--medaid-ink)]">{finding.test_name}</span>
                          <div className="flex items-center gap-2">
                            <span className="tabular-nums text-sm text-[var(--medaid-ink-soft)]">{finding.value}</span>
                            <StatusPill status={finding.status} />
                          </div>
                        </div>
                        {finding.reference_range && (
                          <p className="mt-1 text-xs tabular-nums text-[var(--medaid-ink-muted)]">Normal range: {finding.reference_range}</p>
                        )}
                        {note?.plain_meaning && <p className="mt-2 text-sm leading-6 text-[var(--medaid-ink-soft)]">{note.plain_meaning}</p>}
                        {note?.why_it_matters_for_you
                          ? <p className="mt-1.5 text-sm leading-6 text-[var(--medaid-ink)]">{note.why_it_matters_for_you}</p>
                          : finding.explanation && <p className="mt-2 text-sm leading-6 text-[var(--medaid-ink-soft)]">{finding.explanation}</p>}
                        {!!finding.possible_causes?.length && (
                          <div className="mt-3 flex flex-wrap gap-1.5">
                            {finding.possible_causes.slice(0, 5).map((cause, i) => (
                              <span key={i} className="rounded-pill border border-[var(--medaid-border)] bg-[var(--medaid-surface)] px-2.5 py-0.5 text-[11px] text-[var(--medaid-ink-muted)]">{cause}</span>
                            ))}
                          </div>
                        )}
                        {note?.urgency && (
                          <p className="mt-3 text-xs font-semibold text-[var(--medaid-ink-soft)]">{URGENCY_LABEL[note.urgency] || note.urgency}</p>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </Section>
            )}

            {consultation?.connection_to_your_history && (
              <Section title="How this relates to your history" icon={Stethoscope}>
                <p className="text-sm leading-7 text-[var(--medaid-ink-soft)]">{consultation.connection_to_your_history}</p>
              </Section>
            )}

            {consultation?.trend_vs_previous && (
              <Section title="Compared with your previous reports" icon={TrendingUp}>
                <p className="text-sm leading-7 text-[var(--medaid-ink-soft)]">{consultation.trend_vs_previous}</p>
              </Section>
            )}

            {!!consultation?.next_steps?.length && (
              <Section title="What to do next" icon={ClipboardList}>
                <ul className="space-y-1.5">
                  {consultation.next_steps.map((step, i) => (
                    <li key={i} className="flex gap-2 text-sm leading-6 text-[var(--medaid-ink-soft)]">
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-brand" aria-hidden="true" />{step}
                    </li>
                  ))}
                </ul>
                {consultation.follow_up && (
                  <p className="mt-3 rounded-md border border-[var(--medaid-border)] bg-[var(--medaid-surface-muted)] px-3 py-2 text-sm text-[var(--medaid-ink)]">
                    <span className="font-semibold">Follow-up: </span>{consultation.follow_up}
                  </p>
                )}
              </Section>
            )}

            {!!consultation?.questions_for_your_doctor?.length && (
              <Section title="Questions to ask your doctor" icon={HelpCircle}>
                <ul className="space-y-1.5">
                  {consultation.questions_for_your_doctor.map((q, i) => (
                    <li key={i} className="flex gap-2 text-sm leading-6 text-[var(--medaid-ink-soft)]">
                      <span aria-hidden="true" className="text-brand">•</span>{q}
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            {!!consultation?.red_flags?.length && (
              <div role="alert" className="rounded-card border border-[var(--risk-emergency-border)] bg-[var(--risk-emergency-soft)] p-4">
                <div className="mb-2 flex items-center gap-2">
                  <ShieldAlert className="h-4 w-4 text-[var(--risk-emergency-line)]" aria-hidden="true" />
                  <h4 className="text-sm font-bold text-[var(--risk-emergency-text)]">Seek care immediately if you notice</h4>
                </div>
                <ul className="space-y-1">
                  {consultation.red_flags.map((flag, i) => (
                    <li key={i} className="text-sm leading-6 text-[var(--risk-emergency-text)]">• {flag}</li>
                  ))}
                </ul>
              </div>
            )}

            {consultation?.closing && (
              <p className="text-sm leading-7 text-[var(--medaid-ink-soft)]">{consultation.closing}</p>
            )}

            {/* Fallback: verification succeeded but the narrative call didn't */}
            {!consultation && analysis.clinical_insights && (
              <p className="whitespace-pre-wrap text-sm leading-7 text-[var(--medaid-ink-soft)]">{analysis.clinical_insights}</p>
            )}

            <p className="border-t border-[var(--medaid-border)] pt-4 text-xs leading-5 text-[var(--medaid-ink-muted)]">
              This explanation is informational and not a diagnosis. Statuses are calculated against standard
              reference ranges; tests without reference data on file are marked “Not verified”. Always confirm with your doctor.
            </p>
          </div>
        )}
      </section>

      <section className={`${medaidClasses.card} p-6`}>
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold text-[var(--medaid-ink)]">Extracted information</h3>
            <p className={medaidClasses.mutedSmall}>The raw text read from your report.</p>
          </div>
          <Activity className="h-5 w-5 text-[var(--medaid-accent)]" />
        </div>
        {document.extracted_text
          ? <p className="max-h-64 overflow-y-auto whitespace-pre-wrap text-sm leading-7 text-[var(--medaid-ink-soft)]">{document.extracted_text}</p>
          : <p className={medaidClasses.bodySmall}>No extracted text is available for this file.</p>}
      </section>
    </div>
  );
};

export default MedicalDocumentDetail;
