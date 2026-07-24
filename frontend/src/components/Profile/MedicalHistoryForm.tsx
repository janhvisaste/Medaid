import React, { useState, useEffect } from 'react';
import {
  AlertCircle, Bone, Brain, Check, Cloud, Dna, Droplet, Droplets, FileText,
  FlaskConical, Flower2, Gauge, HeartPulse, Loader2, Ribbon, Save, ShieldCheck,
  Stethoscope, Waves, Wind, Zap,
} from 'lucide-react';
import apiService from '../../services/apiService';
import { medaidClasses } from '../../styles/medaidTokens';
import { Skeleton } from '../ui/Skeleton';

const MEDICAL_CONDITIONS = [
  { name: 'Diabetes', description: 'Type 1, Type 2, or Gestational' },
  { name: 'Hypertension', description: 'High blood pressure' },
  { name: 'Heart Disease', description: 'Coronary artery disease, heart failure' },
  { name: 'Thyroid Disorders', description: 'Hypothyroidism, Hyperthyroidism' },
  { name: 'Kidney Disease', description: 'Chronic kidney disease' },
  { name: 'Liver Disease', description: 'Hepatitis, cirrhosis, fatty liver' },
  { name: 'Asthma', description: 'Chronic respiratory condition' },
  { name: 'COPD', description: 'Chronic obstructive pulmonary disease' },
  { name: 'Stroke', description: 'Previous stroke or TIA' },
  { name: 'Epilepsy', description: 'Seizure disorder' },
  { name: 'Cancer', description: 'Any type of cancer history' },
  { name: 'Arthritis', description: 'Rheumatoid or osteoarthritis' },
  { name: 'Mental Health Conditions', description: 'Depression, anxiety, etc.' },
  { name: 'Allergies', description: 'Food, drug, or environmental' },
  { name: 'Autoimmune Disorders', description: 'Lupus, MS, etc.' },
];

// Grouped for scannability — a flat wall of 15 tiles reads worse than a few
// short, clearly labelled clusters. Order mirrors MEDICAL_CONDITIONS above.
const CONDITION_GROUPS: { label: string; items: string[] }[] = [
  { label: 'Metabolic & heart', items: ['Diabetes', 'Hypertension', 'Heart Disease', 'Thyroid Disorders', 'Kidney Disease', 'Liver Disease'] },
  { label: 'Respiratory & neurological', items: ['Asthma', 'COPD', 'Stroke', 'Epilepsy'] },
  { label: 'Other conditions', items: ['Cancer', 'Arthritis', 'Mental Health Conditions', 'Allergies', 'Autoimmune Disorders'] },
];

const CONDITION_BY_NAME = Object.fromEntries(MEDICAL_CONDITIONS.map(c => [c.name, c]));

// One recognizable icon per condition (falls back to a stethoscope).
const CONDITION_ICON: Record<string, React.ElementType> = {
  'Diabetes': Droplet,
  'Hypertension': Gauge,
  'Heart Disease': HeartPulse,
  'Thyroid Disorders': Gauge,
  'Kidney Disease': Droplets,
  'Liver Disease': FlaskConical,
  'Asthma': Wind,
  'COPD': Cloud,
  'Stroke': Zap,
  'Epilepsy': Waves,
  'Cancer': Ribbon,
  'Arthritis': Bone,
  'Mental Health Conditions': Brain,
  'Allergies': Flower2,
  'Autoimmune Disorders': Dna,
};

const OTHER_NOTES_MAX = 2000;

interface MedicalHistoryFormProps {
  onSave?: () => void;
}

const MedicalHistoryForm: React.FC<MedicalHistoryFormProps> = ({ onSave }) => {
  const [conditions, setConditions] = useState<{[key: string]: { selected: boolean; notes: string }}>({});
  const [otherNotes, setOtherNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fetching, setFetching] = useState(true);

  useEffect(() => {
    loadExistingHistory();
  }, []);

  const loadExistingHistory = async () => {
    try {
      const profile = await apiService.getUserProfile();

      if (profile.past_history && profile.past_history.conditions) {
        const existingConditions: {[key: string]: { selected: boolean; notes: string }} = {};

        profile.past_history.conditions.forEach((condition: any) => {
          existingConditions[condition.name] = {
            selected: true,
            notes: condition.notes || ''
          };
        });

        setConditions(existingConditions);
      }

      // Load saved other_notes (stored as top-level field on UserProfile)
      if (profile.other_notes) {
        setOtherNotes(profile.other_notes);
      }
    } catch {
      // Silently continue — form still usable without pre-population
    } finally {
      setFetching(false);
    }
  };

  const toggleCondition = (conditionName: string) => {
    setConditions(prev => ({
      ...prev,
      [conditionName]: {
        selected: !prev[conditionName]?.selected,
        notes: prev[conditionName]?.notes || ''
      }
    }));
    setSuccess(false);
    setError(null);
  };

  const updateNotes = (conditionName: string, notes: string) => {
    setConditions(prev => ({
      ...prev,
      [conditionName]: {
        ...prev[conditionName],
        notes
      }
    }));
    setSuccess(false);
  };

  const handleOtherNotesChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setOtherNotes(e.target.value);
    setSuccess(false);
    setError(null);
  };

  const otherNotesOverLimit = otherNotes.length > OTHER_NOTES_MAX;

  const handleSave = async () => {
    if (otherNotesOverLimit) {
      setError(`Notes must be ${OTHER_NOTES_MAX} characters or fewer. Please shorten your text.`);
      return;
    }

    setLoading(true);
    setError(null);
    setSuccess(false);

    try {
      const conditionsArray = MEDICAL_CONDITIONS.map(condition => ({
        name: condition.name,
        selected: conditions[condition.name]?.selected || false,
        notes: conditions[condition.name]?.notes || ''
      }));

      await apiService.updateMedicalHistory(conditionsArray, otherNotes);

      setSuccess(true);
      if (onSave) onSave();

      // Clear success message after 3 seconds
      setTimeout(() => setSuccess(false), 3000);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to save medical history');
    } finally {
      setLoading(false);
    }
  };

  const totalCount = MEDICAL_CONDITIONS.length;
  const selectedCount = Object.values(conditions).filter(c => c.selected).length;

  // Circular progress ring geometry — a calmer, more designed feedback signal
  // than a plain "N selected" pill.
  const RING_RADIUS = 21;
  const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS;
  const ringProgress = totalCount ? selectedCount / totalCount : 0;

  if (fetching) {
    return (
      <div className={`${medaidClasses.card} overflow-hidden`}>
        <div className="grid gap-6 p-6 md:p-8 lg:grid-cols-[1.55fr_1fr]">
          <div className="space-y-4">
            <Skeleton className="h-8 w-2/3" />
            <Skeleton className="h-4 w-full max-w-md" />
            <div className="grid gap-2.5 pt-2 sm:grid-cols-2">
              {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-16" />)}
            </div>
          </div>
          <Skeleton className="h-72" />
        </div>
      </div>
    );
  }

  return (
    <div className={`${medaidClasses.card} animate-fade-in overflow-hidden`}>
      <div className="grid lg:grid-cols-[1.55fr_1fr]">
        {/* Conditions — grouped icon + title + description tiles; selected tiles highlight */}
        <div className="p-6 md:p-8">
          <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
            <div className="flex items-start gap-4">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md bg-brand text-brand-contrast shadow-e1">
                <Stethoscope className="h-5 w-5" aria-hidden="true" />
              </div>
              <div>
                <p className={medaidClasses.eyebrow}>Health profile</p>
                <h2 className="mt-1 font-display text-2xl font-medium text-[var(--medaid-ink)]">Past medical history</h2>
                <p className="mt-1.5 max-w-md text-sm leading-6 text-[var(--medaid-ink-soft)]">
                  Select every condition you've been diagnosed with — it helps us assess you more accurately.
                </p>
              </div>
            </div>

            <div className="relative flex h-16 w-16 shrink-0 items-center justify-center" role="img" aria-label={`${selectedCount} of ${totalCount} conditions selected`}>
              <svg viewBox="0 0 48 48" className="h-16 w-16 -rotate-90" aria-hidden="true">
                <circle cx="24" cy="24" r={RING_RADIUS} fill="none" stroke="var(--medaid-border)" strokeWidth="4" />
                <circle
                  cx="24" cy="24" r={RING_RADIUS} fill="none"
                  stroke="var(--brand)" strokeWidth="4" strokeLinecap="round"
                  strokeDasharray={RING_CIRCUMFERENCE}
                  strokeDashoffset={RING_CIRCUMFERENCE * (1 - ringProgress)}
                  className="transition-[stroke-dashoffset] duration-500 ease-standard"
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-base font-bold tabular-nums leading-none text-[var(--medaid-ink)]">{selectedCount}</span>
                <span className="mt-0.5 text-[10px] leading-none text-[var(--medaid-ink-muted)]">of {totalCount}</span>
              </div>
            </div>
          </div>

          {success && (
            <div role="status" className="mb-4 flex animate-fade-in items-center gap-3 rounded-md border border-[var(--risk-low-border)] bg-[var(--risk-low-soft)] p-3 text-sm text-[var(--risk-low-text)]">
              <Check size={18} className="shrink-0" /> <span className="font-medium">Medical history saved.</span>
            </div>
          )}
          {error && (
            <div role="alert" className="mb-4 flex animate-fade-in items-start gap-3 rounded-md border border-[var(--risk-emergency-border)] bg-[var(--risk-emergency-soft)] p-3 text-sm text-[var(--risk-emergency-text)]">
              <AlertCircle size={18} className="shrink-0" /> <span>{error}</span>
            </div>
          )}

          <div className="space-y-6">
            {CONDITION_GROUPS.map((group) => (
              <div key={group.label}>
                <p className={`${medaidClasses.eyebrow} mb-2.5`}>{group.label}</p>
                <div className="grid gap-2.5 sm:grid-cols-2">
                  {group.items.map((name, index) => {
                    const condition = CONDITION_BY_NAME[name];
                    const selected = conditions[name]?.selected || false;
                    const Icon = CONDITION_ICON[name] || Stethoscope;
                    const isLastOdd = index === group.items.length - 1 && group.items.length % 2 === 1;
                    return (
                      <div
                        key={name}
                        className={`relative rounded-card border p-3 transition-colors ${isLastOdd ? 'sm:col-span-2' : ''} ${
                          selected
                            ? 'border-brand bg-brand-50 shadow-e1 dark:bg-[var(--medaid-accent-soft)]'
                            : 'border-transparent hover:bg-[var(--medaid-surface-muted)]'
                        }`}
                      >
                        {selected && (
                          <span aria-hidden="true" className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-brand text-brand-contrast shadow-e1">
                            <Check className="h-3 w-3" strokeWidth={3} />
                          </span>
                        )}
                        <button
                          type="button"
                          onClick={() => toggleCondition(name)}
                          aria-pressed={selected}
                          className="flex w-full items-start gap-3 rounded-md text-left"
                        >
                          <span className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-md transition-colors ${
                            selected ? 'bg-brand text-brand-contrast' : 'bg-[var(--medaid-surface-muted)] text-[var(--medaid-ink-muted)]'
                          }`}>
                            <Icon className="h-4 w-4" aria-hidden="true" />
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="block text-sm font-semibold text-[var(--medaid-ink)]">{name}</span>
                            <span className="mt-0.5 block text-xs leading-5 text-[var(--medaid-ink-muted)]">{condition.description}</span>
                          </span>
                        </button>
                        {selected && (
                          <input
                            type="text"
                            placeholder="Notes — diagnosis date, severity, medications…"
                            value={conditions[name]?.notes || ''}
                            onChange={(e) => updateNotes(name, e.target.value)}
                            className={`${medaidClasses.input} animate-fade-in mt-2.5 py-2 text-sm`}
                          />
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right panel — additional free-text context + privacy note */}
        <aside className="border-t border-[var(--medaid-border)] bg-[var(--medaid-surface-muted)]/50 p-6 md:p-8 lg:border-l lg:border-t-0">
          <div className="flex h-11 w-11 items-center justify-center rounded-md bg-[var(--medaid-surface)] text-brand shadow-e1">
            <FileText className="h-5 w-5" aria-hidden="true" />
          </div>
          <p className={`${medaidClasses.eyebrow} mt-4`}>Additional notes</p>
          <p className="mt-1.5 text-sm leading-6 text-[var(--medaid-ink-soft)]">
            Allergies, past surgeries, family history, or ongoing medications not covered on the left.
          </p>
          <textarea
            id="other-notes"
            value={otherNotes}
            onChange={handleOtherNotesChange}
            placeholder="E.g. Penicillin allergy. Father had a heart attack at 55. Appendix removed in 2018. Currently taking metformin 500 mg twice daily."
            rows={8}
            maxLength={OTHER_NOTES_MAX + 1}   /* +1 so the browser doesn't silently truncate; we validate client-side */
            className={`mt-4 w-full resize-y rounded-card border px-4 py-3 text-sm leading-relaxed transition-colors focus:outline-none focus:ring-2 ${
              otherNotesOverLimit
                ? 'border-[var(--risk-emergency-line)] bg-[var(--risk-emergency-soft)] focus:ring-[var(--risk-emergency-border)]'
                : 'border-[var(--medaid-border)] bg-[var(--medaid-surface)] focus:border-brand focus:ring-[var(--medaid-focus)]'
            } text-[var(--medaid-ink)] placeholder:text-[var(--medaid-ink-faint)]`}
          />
          <div className={`mt-1.5 flex justify-end text-xs font-medium ${
            otherNotesOverLimit
              ? 'text-[var(--risk-emergency-text)]'
              : otherNotes.length > OTHER_NOTES_MAX * 0.85
              ? 'text-[var(--risk-medium-text)]'
              : 'text-[var(--medaid-ink-muted)]'
          }`}>
            {otherNotes.length.toLocaleString()} / {OTHER_NOTES_MAX.toLocaleString()}
          </div>
          <div className="mt-4 flex items-start gap-2.5 rounded-md border border-[var(--medaid-border)] bg-[var(--medaid-surface)] p-3 text-xs leading-5 text-[var(--medaid-ink-muted)]">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-brand" aria-hidden="true" />
            Kept confidential and used only to personalise your health assessments and report analysis.
          </div>
        </aside>
      </div>

      {/* Bottom action bar */}
      <div className="flex flex-col gap-3 border-t border-[var(--medaid-border)] px-6 py-4 sm:flex-row sm:items-center sm:justify-between md:px-8">
        <p className="text-sm text-[var(--medaid-ink-muted)]">
          <span className="font-semibold text-[var(--medaid-ink-soft)]">{selectedCount} condition{selectedCount !== 1 ? 's' : ''}</span> selected — changes aren't saved until you save.
        </p>
        <button
          onClick={handleSave}
          disabled={loading || otherNotesOverLimit}
          className={`px-6 py-2.5 ${medaidClasses.buttonPrimary} disabled:cursor-not-allowed disabled:opacity-50`}
        >
          {loading ? (
            <>
              <Loader2 className="animate-spin" size={18} />
              Saving…
            </>
          ) : (
            <>
              <Save size={18} />
              Save medical history
            </>
          )}
        </button>
      </div>
    </div>
  );
};

export default MedicalHistoryForm;
