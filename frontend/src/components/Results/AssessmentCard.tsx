import React, { useState } from 'react';
import {
  Check, ChevronDown, CircleAlert, Download, Hospital, Loader2, Phone,
  ShieldAlert, Sparkles,
} from 'lucide-react';
import { medaidClasses, riskStyles, type MedaidRisk } from '../../styles/medaidTokens';
import RiskBadge from '../ui/RiskBadge';

/** The assessment fields a completed triage turn carries. */
export interface AssessmentMessage {
  id: string;
  text: string;
  riskLevel?: string;
  confidence?: number;
  possibleConditions?: any[];
  recommendations?: string[];
  whenToSeekCare?: string;
  requiresHumanReview?: boolean;
  reasoning?: string;
  isDegraded?: boolean;
  triageId?: number;
}

interface AssessmentCardProps {
  message: AssessmentMessage;
  downloading: boolean;
  onFindCare: () => void;
  onDownload: () => void;
}

/** Steps shown before the "show more" toggle — enough to act on now. */
const VISIBLE_STEPS = 3;

// Assessments are stored as a formatted numbered block ("1. Assessment: …")
// alongside their structured metadata. Turns saved before `reasoning` was added
// to that metadata only have the text, so recover the prose from it.
// Deliberately not /m: `$` must mean end of input, or the lazy group would
// stop at the first line break and clip a multi-paragraph assessment.
const REASONING_SECTION = /(?:^|\n)[ \t]*1\.\s*Assessment:\s*([\s\S]*?)(?=\n[ \t]*\d+\.\s|$)/;

export const extractReasoning = (text: string): string =>
  (text.match(REASONING_SECTION)?.[1] ?? '').trim();

/** Splits prose into its opening sentence and whatever follows it. */
const splitFirstSentence = (text: string): [string, string] => {
  const trimmed = (text || '').trim();
  if (!trimmed) return ['', ''];
  const match = trimmed.match(/^[\s\S]*?[.!?](?=\s|$)/);
  if (!match) return [trimmed, ''];
  return [match[0].trim(), trimmed.slice(match[0].length).trim()];
};

const AssessmentCard: React.FC<AssessmentCardProps> = ({ message, downloading, onFindCare, onDownload }) => {
  const [conditionsOpen, setConditionsOpen] = useState(false);
  const [stepsOpen, setStepsOpen] = useState(false);
  const [reasoningOpen, setReasoningOpen] = useState(false);

  const risk = (message.riskLevel || 'neutral').toLowerCase() as MedaidRisk;
  const meta = riskStyles[risk] || riskStyles.neutral;
  const isEmergency = risk === 'emergency';
  const isUrgent = isEmergency || risk === 'high';

  const ranked = [...(message.possibleConditions || [])]
    .map((condition: any) => typeof condition === 'string'
      ? { disease: condition, confidence: null as number | null }
      : { disease: condition.disease, confidence: typeof condition.confidence === 'number' ? condition.confidence : null })
    .sort((a, b) => (b.confidence ?? 0) - (a.confidence ?? 0));
  const [top, ...otherConditions] = ranked;
  const topPct = top?.confidence != null ? Math.round(top.confidence * 100) : null;

  const reasoning = (message.reasoning || extractReasoning(message.text)).trim();

  // The default view is one sentence: the leading condition plus the opening
  // line of the care guidance. Everything longer lives behind a disclosure.
  const [careLead, careRest] = splitFirstSentence(message.whenToSeekCare || '');
  const summaryLead = top?.disease
    ? `Likely ${top.disease}`
    : splitFirstSentence(reasoning)[0] || `${meta.label} risk assessment`;

  const steps = message.recommendations || [];
  const visibleSteps = stepsOpen ? steps : steps.slice(0, VISIBLE_STEPS);
  const hiddenStepCount = steps.length - visibleSteps.length;

  const chip = 'inline-flex items-center gap-1.5 rounded-pill border border-[var(--medaid-border)] bg-[var(--medaid-surface-muted)] px-2.5 py-1 text-xs text-[var(--medaid-ink-soft)]';
  const disclosure = 'inline-flex items-center gap-1.5 rounded-control text-xs font-medium text-[var(--medaid-ink-muted)] transition-colors hover:text-[var(--medaid-ink)]';

  return (
    <div className={`${medaidClasses.card} overflow-hidden`}>
      <div className="space-y-4 p-4 md:p-5">
        {message.isDegraded && (
          <div className="flex items-start gap-2 rounded-md border border-[var(--risk-medium-border)] bg-[var(--risk-medium-soft)] px-3 py-2 text-xs font-medium text-[var(--risk-medium-text)]">
            <Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            A full AI analysis couldn't be completed. This is general safety guidance, not a diagnosis — please consult a healthcare professional.
          </div>
        )}

        {/* 1. Risk badge + the one-line takeaway */}
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <RiskBadge risk={message.riskLevel || 'neutral'} compact />
            {typeof message.confidence === 'number' && (
              <span className="text-xs font-medium text-[var(--medaid-ink-muted)]">
                <span className="tabular-nums">{Math.round(message.confidence * 100)}%</span> confidence
              </span>
            )}
            {message.requiresHumanReview && (
              <span className="inline-flex items-center gap-1 rounded-pill bg-[var(--risk-medium-soft)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[var(--risk-medium-text)]">
                <ShieldAlert className="h-3 w-3" aria-hidden="true" /> Flagged for review
              </span>
            )}
          </div>
          <p className="mt-2 text-[15px] font-semibold leading-6 text-[var(--medaid-ink)]">
            {summaryLead}
            {careLead && <span className="font-normal text-[var(--medaid-ink-soft)]"> — {careLead}</span>}
          </p>
          {/* The leading condition is named in the sentence above, so the bar
              carries only what the sentence can't: how strong the match is. */}
          {top && topPct != null && (
            <div className="mt-2 flex items-center gap-2.5">
              <div className="h-1.5 w-full max-w-[220px] overflow-hidden rounded-pill bg-[var(--medaid-surface-muted)]" role="img" aria-label={`${top.disease}: ${topPct}% match`}>
                <div className="h-full rounded-pill bg-brand transition-[width] duration-500 ease-standard" style={{ width: `${Math.max(topPct, 3)}%` }} />
              </div>
              <span className="shrink-0 text-xs tabular-nums text-[var(--medaid-ink-muted)]">{topPct}% match</span>
            </div>
          )}
        </div>

        {/* 2. Urgent action panel — the most important surface in the product */}
        {isUrgent && (
          <div role="alert" className={`rounded-card border p-4 ${meta.className} ${isEmergency ? 'animate-emergency-pulse' : ''}`}>
            <div className="flex items-start gap-3">
              <CircleAlert className="mt-0.5 h-6 w-6 shrink-0" aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <p className="text-base font-bold">{isEmergency ? 'Emergency — seek care immediately' : 'Urgent — medical attention recommended'}</p>
                {/* The opening line of the care guidance already sits in the
                    summary above; the rest stays visible here rather than
                    collapsing, because an urgent turn must hide nothing. */}
                {careRest && <p className="mt-1 text-sm leading-6 opacity-90">{careRest}</p>}
                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  {isEmergency && (
                    <a href="tel:112" className="inline-flex min-h-12 items-center justify-center gap-2 rounded-control bg-[var(--risk-emergency-solid)] px-4 text-base font-semibold text-white shadow-e1 transition-[filter,transform] duration-150 hover:brightness-110 active:scale-[0.99]">
                      <Phone className="h-5 w-5" aria-hidden="true" /> Call emergency services (112)
                    </a>
                  )}
                  <button onClick={() => onFindCare()} className="inline-flex min-h-12 items-center justify-center gap-2 rounded-control border border-current bg-[var(--medaid-surface)] px-4 text-base font-semibold text-[var(--medaid-ink)] transition-colors duration-150 hover:bg-[var(--medaid-surface-muted)]">
                    <Hospital className="h-5 w-5" aria-hidden="true" /> Find nearest facility
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 3. The rest of the differential — one line of chips, on request */}
        {otherConditions.length > 0 && (
          <div>
            <button onClick={() => setConditionsOpen(open => !open)} aria-expanded={conditionsOpen} className={disclosure}>
              <ChevronDown className={`h-3.5 w-3.5 transition-transform duration-200 ${conditionsOpen ? 'rotate-180' : ''}`} aria-hidden="true" />
              {conditionsOpen
                ? 'Hide other possibilities'
                : `Show ${otherConditions.length} more possibilit${otherConditions.length === 1 ? 'y' : 'ies'}`}
            </button>
            {conditionsOpen && (
              <ul className="mt-2 flex flex-wrap gap-1.5">
                {otherConditions.map((condition, index) => {
                  const pct = condition.confidence != null ? Math.round(condition.confidence * 100) : null;
                  return (
                    <li key={index} className={chip}>
                      {condition.disease}
                      {pct != null && <span className="tabular-nums text-[var(--medaid-ink-muted)]">{pct}%</span>}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        )}

        {/* 4. What to do now — the lower-priority tail collapses */}
        {steps.length > 0 && (
          <div>
            <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--medaid-ink-muted)]">Next steps</p>
            <ul className="space-y-1.5">
              {visibleSteps.map((step, index) => (
                <li key={index} className="flex gap-2 text-sm leading-6 text-[var(--medaid-ink-soft)]">
                  <Check className="mt-1 h-4 w-4 shrink-0 text-brand" aria-hidden="true" /> {step}
                </li>
              ))}
            </ul>
            {steps.length > VISIBLE_STEPS && (
              <button onClick={() => setStepsOpen(open => !open)} aria-expanded={stepsOpen} className={`${disclosure} mt-2`}>
                <ChevronDown className={`h-3.5 w-3.5 transition-transform duration-200 ${stepsOpen ? 'rotate-180' : ''}`} aria-hidden="true" />
                {stepsOpen ? 'Show fewer steps' : `Show ${hiddenStepCount} more step${hiddenStepCount === 1 ? '' : 's'}`}
              </button>
            )}
          </div>
        )}

        {/* Non-urgent care lookup — urgent risks get the button in the panel above */}
        {!isUrgent && risk === 'medium' && (
          <button onClick={() => onFindCare()} className={`${medaidClasses.buttonSecondary} px-3 py-1.5 text-xs`}>
            <Hospital className="h-3.5 w-3.5" /> Find care nearby
          </button>
        )}

        {/* The clinician-grade detail: available, never in the way */}
        {(reasoning || (!isUrgent && careRest)) && (
          <div className="border-t border-[var(--medaid-border)] pt-3">
            <button onClick={() => setReasoningOpen(open => !open)} aria-expanded={reasoningOpen} className={disclosure}>
              <ChevronDown className={`h-3.5 w-3.5 transition-transform duration-200 ${reasoningOpen ? 'rotate-180' : ''}`} aria-hidden="true" />
              {reasoningOpen ? 'Hide full clinical reasoning' : 'View full clinical reasoning'}
            </button>
            {reasoningOpen && (
              <div className="mt-2 space-y-3 rounded-md bg-[var(--medaid-surface-muted)] px-3 py-2.5 text-sm leading-6 text-[var(--medaid-ink-soft)]">
                {reasoning && <p className="whitespace-pre-line">{reasoning}</p>}
                {!isUrgent && careRest && (
                  <p><span className="font-semibold text-[var(--medaid-ink)]">When to seek care: </span>{careRest}</p>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* 5. The report is the conclusion of the assessment — always in reach */}
      <div className="flex flex-col gap-3 border-t border-[var(--medaid-border)] bg-[var(--medaid-surface-muted)]/50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between md:px-5">
        <p className="text-xs leading-5 text-[var(--medaid-ink-muted)]">
          AI-generated guidance, not a diagnosis. Share the report with your doctor.
        </p>
        {!!message.triageId && (
          <button
            onClick={() => onDownload()}
            disabled={downloading}
            className={`shrink-0 px-4 py-2 ${medaidClasses.buttonPrimary} disabled:opacity-60`}
          >
            {downloading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />} Download report
          </button>
        )}
      </div>
    </div>
  );
};

export default AssessmentCard;
