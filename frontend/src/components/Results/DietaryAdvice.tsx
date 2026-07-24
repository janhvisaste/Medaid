import React, { useCallback, useEffect, useRef, useState } from 'react';
import { AlertCircle, Apple, ArrowRight, BrainCircuit, Check, CircleGauge, Clock3, Leaf, Loader2, RefreshCw, ShieldCheck, Sparkles } from 'lucide-react';
import apiService, { DietaryRecommendations } from '../../services/apiService';
import { medaidClasses } from '../../styles/medaidTokens';

interface DietaryAdviceProps {
  riskLevel?: string;
  conditions?: string[];
  triageId?: number;
}

// Module-level so the reference is stable across renders. An inline `= []`
// default is a NEW array every time the default is used, which broke
// loadAdvice's useCallback identity and caused an infinite fetch loop (see
// below) - each response triggered a re-render, which triggered a new
// default array, which triggered a new loadAdvice, which re-ran the effect.
const NO_CONDITIONS: string[] = [];

const DietaryAdvice: React.FC<DietaryAdviceProps> = ({ riskLevel = 'medium', conditions = NO_CONDITIONS }) => {
  const [recommendations, setRecommendations] = useState<DietaryRecommendations | null>(null);
  const [loading, setLoading] = useState(true);
  const [slow, setSlow] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Guards against two overlapping calls in flight at once - both React 18
  // StrictMode's intentional double-invoke of mount effects in development,
  // and a real user double-clicking "Try again"/"Refresh". Without this, two
  // identical requests can race: the backend's per-user concurrency guard
  // rejects the second one immediately (fast 429) while the first is still
  // waiting on the real LLM call (slow 200) - and if the fast rejection's
  // state update lands after the slow success, it clobbers good data with an
  // error the user never actually hit.
  const inFlightRef = useRef(false);

  const loadAdvice = useCallback(async () => {
    if (inFlightRef.current) return;
    inFlightRef.current = true;
    setLoading(true);
    setSlow(false);
    setError(null);
    const slowTimer = window.setTimeout(() => setSlow(true), 4500);
    try {
      const response = await apiService.getDietaryRecommendations({ risk_level: riskLevel, possible_conditions: conditions });
      setRecommendations(response);
    } catch (requestError: any) {
      setError(requestError?.response?.data?.error || 'Dietary advice is temporarily unavailable. Please try again shortly.');
    } finally {
      window.clearTimeout(slowTimer);
      setLoading(false);
      inFlightRef.current = false;
    }
  }, [conditions, riskLevel]);

  useEffect(() => { loadAdvice(); }, [loadAdvice]);

  if (loading) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-12 md:px-6">
        <div className="rounded-panel border border-[var(--medaid-border)] bg-[var(--medaid-surface)] p-8 text-center shadow-e1 md:p-16">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-card bg-[var(--medaid-accent-soft)] text-[var(--medaid-accent-strong)]"><Loader2 className="h-8 w-8 animate-spin" /></div>
          <p className="mt-6 text-sm font-semibold uppercase tracking-[0.18em] text-[var(--medaid-accent-strong)]">Preparing your food plan</p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight text-[var(--medaid-ink)]">Connecting the dots in your health history</h1>
          <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-[var(--medaid-ink-muted)]">Medaid is reviewing saved profile details, assessments, report findings, conversations, and previous advice.</p>
          {slow && <p className="mx-auto mt-5 flex max-w-md items-center justify-center gap-2 rounded-md border border-[var(--risk-medium-border)] bg-[var(--risk-medium-soft)] px-4 py-3 text-sm text-[var(--risk-medium-text)]"><Clock3 className="h-4 w-4" />The free-tier model is taking a little longer than usual. Please keep this page open.</p>}
        </div>
      </div>
    );
  }

  if (error || !recommendations) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-12 md:px-6">
        <div role="alert" className="rounded-panel border border-[var(--risk-medium-border)] bg-[var(--risk-medium-soft)] p-8 text-center">
          <AlertCircle className="mx-auto h-10 w-10 text-[var(--risk-medium-line)]" />
          <h1 className="mt-4 font-display text-2xl font-medium text-[var(--medaid-ink)]">We couldn’t prepare dietary guidance</h1>
          <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-[var(--risk-medium-text)]">{error}</p>
          <button onClick={loadAdvice} className={`mt-6 px-5 py-3 ${medaidClasses.buttonPrimary}`}><RefreshCw className="h-4 w-4" />Try again</button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-8 px-4 py-8 md:px-6 md:py-10">
      <header className={`${medaidClasses.restrainedHeroPanel} p-6 md:p-10`}>
        <div className="pointer-events-none absolute -right-16 -top-24 h-64 w-64 rounded-pill bg-brand-200/30 blur-3xl dark:bg-brand-900/40" />
        <div className="relative max-w-3xl">
          <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-[var(--medaid-accent-strong)]"><Sparkles className="h-4 w-4" />Personalized nutrition guidance <span className="rounded-pill bg-[var(--medaid-surface)]/80 px-2.5 py-1 normal-case tracking-normal text-[var(--medaid-ink-soft)]">Free tier</span></div>
          <h1 className="mt-4 font-display text-3xl font-medium tracking-tight text-[var(--medaid-ink)] md:text-5xl">Food that meets you where you are.</h1>
          <p className="mt-4 max-w-2xl text-sm leading-7 text-[var(--medaid-ink-soft)] md:text-base">{recommendations.summary}</p>
          <div className="mt-6 flex flex-wrap gap-2 text-xs text-[var(--medaid-ink-muted)]">
            <span className="inline-flex items-center gap-1.5 rounded-pill border border-[var(--medaid-border)] bg-[var(--medaid-surface)]/80 px-3 py-2"><BrainCircuit className="h-3.5 w-3.5" />{recommendations.context_used.assessment_history} assessment signals</span>
            <span className="inline-flex items-center gap-1.5 rounded-pill border border-[var(--medaid-border)] bg-[var(--medaid-surface)]/80 px-3 py-2"><Leaf className="h-3.5 w-3.5" />{recommendations.context_used.report_history} report sources</span>
            <span className="inline-flex items-center gap-1.5 rounded-pill border border-[var(--medaid-border)] bg-[var(--medaid-surface)]/80 px-3 py-2"><ShieldCheck className="h-3.5 w-3.5" />General guidance, not a prescription</span>
          </div>
        </div>
      </header>

      <section>
        <div className="mb-4 flex items-end justify-between gap-4"><div><p className={medaidClasses.eyebrow}>Built around your context</p><h2 className="mt-1 text-2xl font-semibold text-[var(--medaid-ink)]">A few good places to start</h2></div><button onClick={loadAdvice} className="inline-flex items-center gap-2 rounded-control border border-[var(--medaid-border)] bg-[var(--medaid-surface)] px-3 py-2 text-xs font-semibold text-[var(--medaid-ink-soft)] transition-colors hover:border-brand hover:text-[var(--medaid-ink)]"><RefreshCw className="h-3.5 w-3.5" />Refresh</button></div>
        <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {recommendations.cards.map((card) => <FoodCard key={`${card.category}-${card.name}`} card={card} />)}
        </div>
      </section>

      <div className="grid gap-5 lg:grid-cols-[1.3fr_0.7fr]">
        {Array.isArray(recommendations.daily_pattern) && recommendations.daily_pattern.length ? <section className={`${medaidClasses.card} p-6`}><div className="mb-4 flex items-center gap-3"><CircleGauge className="h-5 w-5 text-[var(--medaid-accent)]" /><div><p className={medaidClasses.eyebrow}>A flexible rhythm</p><h2 className="mt-1 text-xl font-semibold text-[var(--medaid-ink)]">Daily pattern</h2></div></div><ul className="space-y-3">{recommendations.daily_pattern.map((item, index) => <li key={index} className="flex gap-3 text-sm leading-6 text-[var(--medaid-ink-soft)]"><span className="mt-1 flex h-5 w-5 shrink-0 items-center justify-center rounded-pill bg-[var(--medaid-accent-soft)] text-[var(--medaid-accent-strong)]"><Check className="h-3 w-3" /></span>{item}</li>)}</ul></section> : <div />}
        <section className="rounded-card border border-[var(--risk-medium-border)] bg-[var(--risk-medium-soft)] p-6"><div className="flex items-start gap-3"><AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-[var(--risk-medium-line)]" /><div><h2 className="font-semibold text-[var(--medaid-ink)]">A careful next step</h2><p className="mt-2 text-sm leading-6 text-[var(--risk-medium-text)]">{recommendations.safety_notice}</p>{recommendations.next_step && <p className="mt-4 flex items-start gap-2 border-t border-[var(--risk-medium-border)] pt-4 text-sm font-medium leading-6 text-[var(--medaid-ink)]"><ArrowRight className="mt-1 h-4 w-4 shrink-0" />{recommendations.next_step}</p>}</div></div></section>
      </div>
    </div>
  );
};

const FoodCard: React.FC<{ card: DietaryRecommendations['cards'][number] }> = ({ card }) => (
  <article className="group overflow-hidden rounded-card border border-[var(--medaid-border)] bg-[var(--medaid-surface)] shadow-e1 transition-shadow hover:shadow-e2">
    <div className="relative h-44 overflow-hidden bg-[var(--medaid-surface-muted)]"><img src={card.image_url} alt={card.image_alt} loading="lazy" className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105" /><div className="absolute inset-0 bg-gradient-to-t from-slate-950/45 via-transparent to-transparent" /><span className="absolute bottom-3 left-4 rounded-pill bg-white/90 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-800">{card.category}</span></div>
    <div className="p-5"><div className="flex items-start gap-3"><div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-brand-100 text-brand-700 dark:bg-[var(--medaid-accent-soft)] dark:text-[var(--medaid-accent-strong)]"><Apple className="h-5 w-5" /></div><h3 className="pt-1 text-lg font-semibold leading-6 text-[var(--medaid-ink)]">{card.name}</h3></div><p className="mt-4 text-sm leading-6 text-[var(--medaid-ink-soft)]">{card.rationale}</p>{card.nutrient_highlights?.length > 0 && <div className="mt-5 flex flex-wrap gap-2">{card.nutrient_highlights.map((nutrient) => <div key={`${nutrient.label}-${nutrient.value}`} className="flex items-center gap-2 rounded-md bg-[var(--medaid-surface-muted)] px-3 py-2"><span className="h-2 w-2 rounded-pill bg-[var(--medaid-accent)]" /><span className="text-[11px] text-[var(--medaid-ink-muted)]">{nutrient.label}</span><span className="text-xs font-semibold text-[var(--medaid-ink)]">{nutrient.value}</span></div>)}</div>}</div>
  </article>
);

export default DietaryAdvice;
