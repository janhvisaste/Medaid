import React, { useEffect, useRef } from 'react';
import { Hospital, Loader2, MapPin, Navigation, Phone, Search, ShieldAlert, X } from 'lucide-react';
import type { Facility } from '../../services/apiService';
import { medaidClasses } from '../../styles/medaidTokens';
import FacilitiesMap from './FacilitiesMap';

interface FacilityPanelProps {
  open: boolean;
  onClose: () => void;
  facilities?: Facility[];
  loading: boolean;
  /** Drives the emergency fallback when no facilities are found. */
  riskLevel?: string;
  pincode: string;
  onPincodeChange: (value: string) => void;
  onSearch: () => void;
}

/**
 * Slide-in facility finder.
 *
 * Deliberately an overlay rather than a permanent fourth column: a docked panel
 * would compress the chat on every viewport even when the feature is unused.
 * It enters from the right edge, sits in front of the thread, and returns the
 * full-width chat on close.
 */
const FacilityPanel: React.FC<FacilityPanelProps> = ({
  open, onClose, facilities, loading, riskLevel, pincode, onPincodeChange, onSearch,
}) => {
  const closeRef = useRef<HTMLButtonElement>(null);
  const isUrgent = ['emergency', 'high'].includes((riskLevel || '').toLowerCase());

  // Move focus into the panel when it opens, and close on Escape.
  useEffect(() => {
    if (!open) return;
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  const emptyAndUrgent = !loading && facilities && facilities.length === 0 && isUrgent;

  return (
    <>
      {/* Scrim dims the thread so the panel reads as the active surface */}
      <button
        aria-label="Close facility finder"
        onClick={onClose}
        className="fixed inset-0 z-40 bg-[var(--medaid-overlay)] animate-fade-in"
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Nearby care facilities"
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-[var(--medaid-border)] bg-[var(--medaid-surface)] shadow-e3 animate-fade-in"
      >
        <header className="flex shrink-0 items-center justify-between gap-3 border-b border-[var(--medaid-border)] px-5 py-4">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-md bg-brand text-brand-contrast">
              <Hospital className="h-4 w-4" aria-hidden="true" />
            </span>
            <div>
              <p className="font-display text-base font-medium text-[var(--medaid-ink)]">Nearby care</p>
              <p className="text-xs text-[var(--medaid-ink-muted)]">Facilities close to you</p>
            </div>
          </div>
          <button
            ref={closeRef}
            onClick={onClose}
            aria-label="Close facility finder"
            className="rounded-control p-2 text-[var(--medaid-ink-muted)] transition-colors hover:bg-[var(--medaid-surface-muted)] hover:text-[var(--medaid-ink)]"
          >
            <X className="h-5 w-5" />
          </button>
        </header>

        <div className="shrink-0 border-b border-[var(--medaid-border)] px-5 py-3">
          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <MapPin className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--medaid-ink-faint)]" aria-hidden="true" />
              <input
                value={pincode}
                onChange={(event) => onPincodeChange(event.target.value)}
                onKeyDown={(event) => { if (event.key === 'Enter') onSearch(); }}
                placeholder="Pincode"
                aria-label="Search facilities by pincode"
                className={`${medaidClasses.input} pl-9`}
              />
            </div>
            <button onClick={onSearch} disabled={loading} className={`${medaidClasses.buttonPrimary} shrink-0 px-4 py-2.5 disabled:opacity-60`}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />} Search
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {loading && (
            <div className="flex flex-col items-center justify-center gap-3 px-5 py-16 text-center" role="status">
              <Loader2 className="h-6 w-6 animate-spin text-brand" aria-hidden="true" />
              <p className="text-sm text-[var(--medaid-ink-soft)]">Looking for care near you…</p>
            </div>
          )}

          {/* Backend already returns the 108/112 guidance for this case; the panel
              must not show an empty map when the risk is urgent. */}
          {emptyAndUrgent && (
            <div role="alert" className="m-5 rounded-card border border-[var(--risk-emergency-border)] bg-[var(--risk-emergency-soft)] p-4">
              <div className="flex items-start gap-3">
                <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-[var(--risk-emergency-line)]" aria-hidden="true" />
                <div>
                  <p className="text-sm font-bold text-[var(--risk-emergency-text)]">No facilities found nearby</p>
                  <p className="mt-1 text-sm leading-6 text-[var(--risk-emergency-text)]">
                    Don't wait on this search — if your symptoms are severe, call emergency services now.
                  </p>
                  <div className="mt-4 grid gap-2">
                    <a href="tel:112" className="inline-flex min-h-12 items-center justify-center gap-2 rounded-control bg-[var(--risk-emergency-solid)] px-4 text-base font-semibold text-white shadow-e1 transition-[filter] hover:brightness-110">
                      <Phone className="h-5 w-5" aria-hidden="true" /> Call 112
                    </a>
                    <a href="tel:108" className="inline-flex min-h-12 items-center justify-center gap-2 rounded-control border border-current bg-[var(--medaid-surface)] px-4 text-base font-semibold text-[var(--medaid-ink)] transition-colors hover:bg-[var(--medaid-surface-muted)]">
                      <Phone className="h-5 w-5" aria-hidden="true" /> Call 108 (ambulance)
                    </a>
                  </div>
                </div>
              </div>
            </div>
          )}

          {!loading && facilities && facilities.length === 0 && !isUrgent && (
            <div className="px-5 py-16 text-center">
              <MapPin className="mx-auto mb-3 h-10 w-10 text-[var(--medaid-ink-faint)]" aria-hidden="true" />
              <p className="text-sm font-semibold text-[var(--medaid-ink)]">No facilities found</p>
              <p className="mx-auto mt-1 max-w-xs text-sm leading-6 text-[var(--medaid-ink-muted)]">
                Try a different pincode, or widen your search area.
              </p>
            </div>
          )}

          {!loading && !!facilities?.length && (
            <>
              <div className="border-b border-[var(--medaid-border)] p-4">
                <FacilitiesMap facilities={facilities} />
              </div>
              <ul className="divide-y divide-[var(--medaid-border)]">
                {facilities.map((facility, index) => (
                  <li key={index} className="p-4 transition-colors hover:bg-[var(--medaid-surface-muted)]">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-[var(--medaid-ink)]">{facility.name}</p>
                        <p className="mt-0.5 text-xs leading-5 text-[var(--medaid-ink-muted)]">{facility.address}</p>
                      </div>
                      {typeof facility.distance_km === 'number' && (
                        <span className="shrink-0 rounded-pill bg-[var(--medaid-surface-muted)] px-2.5 py-1 text-xs font-semibold tabular-nums text-[var(--medaid-ink-soft)]">
                          {facility.distance_km.toFixed(1)} km
                        </span>
                      )}
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {facility.phone && (
                        <a href={`tel:${facility.phone}`} className={`${medaidClasses.buttonSecondary} px-3 py-1.5 text-xs`}>
                          <Phone className="h-3.5 w-3.5" aria-hidden="true" /> Call
                        </a>
                      )}
                      {facility.maps_url && (
                        <a href={facility.maps_url} target="_blank" rel="noopener noreferrer" className={`${medaidClasses.buttonSecondary} px-3 py-1.5 text-xs`}>
                          <Navigation className="h-3.5 w-3.5" aria-hidden="true" /> Directions
                        </a>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      </aside>
    </>
  );
};

export default FacilityPanel;
