import React, { useEffect, useState } from 'react';
import { AlertCircle, Calendar, CheckCircle2, Download, FileText, Loader2 } from 'lucide-react';
import apiService from '../../services/apiService';
import type { TriageRecord } from '../../services/apiService';
import RiskBadge from '../ui/RiskBadge';
import { medaidClasses } from '../../styles/medaidTokens';
import { Skeleton } from '../ui/Skeleton';
import ConfirmDeleteButton from '../ui/ConfirmDeleteButton';

// Timeline node colour per risk level — lets severity and recurrence read
// straight down the rail without reading each badge.
const RISK_LINE: Record<string, string> = {
  emergency: 'var(--risk-emergency-line)',
  high: 'var(--risk-high-line)',
  medium: 'var(--risk-medium-line)',
  low: 'var(--risk-low-line)',
  neutral: 'var(--risk-neutral-line)',
};
const riskLine = (level?: string) => RISK_LINE[(level || 'neutral').toLowerCase()] || RISK_LINE.neutral;

interface PDFDownloadButtonProps { triageId?: number; type?: 'assessment' | 'passport'; variant?: 'primary' | 'secondary'; className?: string; }

const PDFDownloadButton: React.FC<PDFDownloadButtonProps> = ({ triageId, type = 'assessment', variant = 'primary', className = '' }) => {
  const [loading, setLoading] = useState(false); const [success, setSuccess] = useState(false); const [error, setError] = useState<string | null>(null);
  const download = async () => { setLoading(true); setError(null); try { const blob = type === 'passport' ? await apiService.downloadHealthPassportPDF() : triageId ? await apiService.downloadAssessmentPDF(triageId) : (() => { throw new Error('Assessment id is missing'); })(); apiService.downloadPDFFile(blob, type === 'passport' ? 'medaid-health-passport.pdf' : `assessment-${triageId}.pdf`); setSuccess(true); setTimeout(() => setSuccess(false), 3000); } catch (err: any) { setError(err.response?.data?.error || err.message || 'Unable to generate report.'); } finally { setLoading(false); } };
  return <div className={className}><button onClick={download} disabled={loading} className={`px-4 py-2.5 ${variant === 'primary' ? medaidClasses.buttonPrimary : medaidClasses.buttonSecondary} disabled:cursor-not-allowed disabled:opacity-50`}>{loading ? <><Loader2 className="h-4 w-4 animate-spin" />Generating…</> : success ? <><CheckCircle2 className="h-4 w-4" />Downloaded</> : <><Download className="h-4 w-4" />Download PDF</>}</button>{error && <p role="alert" className="mt-2 text-xs text-[var(--risk-emergency-text)]">{error}</p>}</div>;
};

const AssessmentHistory: React.FC = () => {
  const [assessments, setAssessments] = useState<TriageRecord[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState<string | null>(null);
  // Separate from `error`, which replaces the whole view on a load failure. A
  // refused delete must not blank out the timeline the user is looking at.
  const [actionError, setActionError] = useState<string | null>(null);
  const load = async () => { try { setLoading(true); setError(null); setAssessments(await apiService.getTriageHistory()); } catch { setError('Unable to load assessment history.'); } finally { setLoading(false); } };
  // Rethrows so ConfirmDeleteButton can surface the backend's refusal message
  // when an assessment is still under clinician review.
  const remove = async (id: number) => { await apiService.deleteTriageRecord(id); setAssessments(previous => previous.filter(a => a.id !== id)); };
  useEffect(() => { load(); }, []);
  if (loading) return <div className="space-y-4"><Skeleton className="h-28" /><Skeleton className="h-36" /><Skeleton className="h-36" /></div>;
  if (error) return <div role="alert" className="flex items-center justify-between rounded-md border border-[var(--risk-emergency-border)] bg-[var(--risk-emergency-soft)] px-4 py-3 text-sm text-[var(--risk-emergency-text)]"><span className="flex items-center gap-2"><AlertCircle className="h-4 w-4" />{error}</span><button onClick={load} className="font-semibold underline">Retry</button></div>;
  if (!assessments.length) return <div className={`${medaidClasses.card} px-6 py-16 text-center`}><FileText className="mx-auto mb-4 h-12 w-12 text-[var(--medaid-ink-faint)]" /><p className="font-semibold text-[var(--medaid-ink)]">No assessments yet</p><p className={`mt-2 ${medaidClasses.bodySmall}`}>Start a consultation to create your first report.</p></div>;
  return (
    <div className="space-y-6">
      {actionError && (
        <div role="alert" className="flex items-start justify-between gap-3 rounded-md border border-[var(--risk-emergency-border)] bg-[var(--risk-emergency-soft)] px-4 py-3 text-sm text-[var(--risk-emergency-text)]">
          <span className="flex items-center gap-2"><AlertCircle className="h-4 w-4 shrink-0" />{actionError}</span>
          <button onClick={() => setActionError(null)} className="font-semibold underline">Dismiss</button>
        </div>
      )}
      <div className={`${medaidClasses.heroPanel} flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between`}>
        <div>
          <p className="font-display text-lg font-medium text-[var(--medaid-ink)]">Complete health passport</p>
          <p className={medaidClasses.bodySmall}>Download your assessments and medical history together.</p>
        </div>
        <PDFDownloadButton type="passport" variant="secondary" />
      </div>

      {/* Chronological timeline — newest first. The rail + coloured node make a
          run of high-risk assessments (a worsening trajectory) obvious. */}
      <ol className="relative ml-1">
        {assessments.map((assessment, index) => (
          <li key={assessment.id} className="relative pb-5 pl-8 last:pb-0">
            {index !== assessments.length - 1 && (
              <span aria-hidden="true" className="absolute left-[6px] top-3 h-full w-px bg-[var(--medaid-border)]" />
            )}
            <span
              aria-hidden="true"
              style={{ background: riskLine(assessment.risk_level) }}
              className="absolute left-0 top-1.5 h-3.5 w-3.5 rounded-pill border-2 border-[var(--medaid-surface)] shadow-e1"
            />
            <article className={`${medaidClasses.compactCardHover} p-5`}>
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-3">
                    <RiskBadge risk={assessment.risk_level} />
                    <span className="flex items-center gap-1.5 text-xs text-[var(--medaid-ink-muted)]">
                      <Calendar className="h-3.5 w-3.5" />{new Date(assessment.created_at).toLocaleString()}
                    </span>
                  </div>
                  <p className="mt-3 line-clamp-2 text-sm leading-6 text-[var(--medaid-ink-soft)]">{assessment.current_symptoms}</p>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <PDFDownloadButton triageId={assessment.id} variant="secondary" />
                  <ConfirmDeleteButton
                    label={`Delete assessment from ${new Date(assessment.created_at).toLocaleDateString()}`}
                    onConfirm={() => remove(assessment.id)}
                    onError={setActionError}
                  />
                </div>
              </div>
              <div className="mt-4 grid gap-3 border-t border-[var(--medaid-border)] pt-4 sm:grid-cols-3">
                <div><p className={medaidClasses.mutedSmall}>Confidence</p><p className="mt-1 font-semibold tabular-nums text-[var(--medaid-ink)]">{Math.round((assessment.confidence || 0) * 100)}%</p></div>
                <div><p className={medaidClasses.mutedSmall}>Risk probability</p><p className="mt-1 font-semibold tabular-nums text-[var(--medaid-ink)]">{Math.round((assessment.risk_probability || 0) * 100)}%</p></div>
                <div><p className={medaidClasses.mutedSmall}>Input mode</p><p className="mt-1 font-semibold capitalize text-[var(--medaid-ink)]">{assessment.input_mode || 'text'}</p></div>
              </div>
            </article>
          </li>
        ))}
      </ol>
    </div>
  );
};

export { PDFDownloadButton, AssessmentHistory };
export default PDFDownloadButton;
