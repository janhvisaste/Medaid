import React, { useEffect, useMemo, useState } from 'react';
import { AlertCircle, BrainCircuit, Loader2 } from 'lucide-react';
import apiService from '../../services/apiService';
import type { AvailableModel } from '../../services/apiService';
import { medaidClasses } from '../../styles/medaidTokens';

interface ModelSelectorProps {
  value: string;
  onChange: (modelId: string) => void;
  disabled?: boolean;
}

function formatContext(length?: number) {
  if (!length) return 'context unknown';
  if (length >= 1000000) return `${Math.round(length / 100000) / 10}M ctx`;
  if (length >= 1000) return `${Math.round(length / 1000)}k ctx`;
  return `${length} ctx`;
}

function formatTier(model: AvailableModel) {
  return model.is_free ? 'Free' : 'Paid';
}

function formatPrice(model: AvailableModel) {
  const prompt = model.pricing?.prompt;
  if (prompt === undefined || prompt === null) return null;
  const perMillion = Number(prompt) * 1_000_000;
  if (!Number.isFinite(perMillion) || perMillion <= 0) return null;
  return `$${perMillion.toFixed(2)}/M tokens`;
}

const ModelSelector: React.FC<ModelSelectorProps> = ({ value, onChange, disabled }) => {
  const [models, setModels] = useState<AvailableModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await apiService.getAvailableModels();
        if (mounted) setModels(data);
      } catch {
        if (mounted) setError('Model list unavailable');
      } finally {
        if (mounted) setLoading(false);
      }
    };
    load();
    return () => { mounted = false; };
  }, []);

  const selected = useMemo(() => models.find(model => model.id === value), [models, value]);

  return (
    <div className="flex flex-col gap-1.5 sm:flex-row sm:items-center">
      <label className="inline-flex items-center gap-2 text-xs font-semibold text-[var(--medaid-ink-soft)]">
        <BrainCircuit className="h-4 w-4 text-[var(--medaid-accent)]" />
        AI model
      </label>
      <div className="flex min-w-0 flex-1 items-center gap-2">
        <select
          value={value}
          onChange={event => onChange(event.target.value)}
          disabled={disabled || loading || !!error}
          className={`${medaidClasses.select} min-w-0 py-2 text-xs`}
          aria-label="Select AI model"
        >
          <option value="">Default live model (free)</option>
          {models.map(model => (
            <option key={model.id} value={model.id}>
              {model.name} · {formatTier(model)}{!model.is_free && formatPrice(model) ? ` · ${formatPrice(model)}` : ''} · {formatContext(model.context_length)}
            </option>
          ))}
        </select>
        {loading && <Loader2 className="h-4 w-4 animate-spin text-[var(--medaid-ink-muted)]" />}
        {error && <span className="inline-flex items-center gap-1 text-xs text-[var(--risk-emergency-text)]"><AlertCircle className="h-3.5 w-3.5" />{error}</span>}
      </div>
      {selected && !selected.is_free && (
        // Paid selection must never bill silently: surface an explicit,
        // high-visibility cost warning, not just a low-emphasis "Paid" tag.
        <p className="inline-flex items-center gap-1.5 rounded-control border border-[var(--risk-medium-border)] bg-[var(--risk-medium-soft)] px-2.5 py-1 text-[11px] font-medium text-[var(--risk-medium-text)]">
          <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
          Paid model{formatPrice(selected) ? ` — ${formatPrice(selected)}, billed to your API key` : ' — billed to your API key'}
        </p>
      )}
      {selected && selected.is_free && (
        <p className="text-[11px] text-[var(--medaid-ink-muted)] sm:max-w-xs">
          Free · {formatContext(selected.context_length)}
        </p>
      )}
    </div>
  );
};

export default ModelSelector;
