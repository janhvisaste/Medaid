import React, { useEffect, useRef, useState } from 'react';
import { Loader2, Trash2, X } from 'lucide-react';

interface ConfirmDeleteButtonProps {
  /** Runs on confirm. Throw to surface an error message to the user. */
  onConfirm: () => Promise<void> | void;
  /** Accessible label, e.g. "Delete conversation 'Chest pain'". */
  label: string;
  /** Text shown on the confirm step. */
  confirmText?: string;
  /** Called with a readable message when onConfirm throws. */
  onError?: (message: string) => void;
  className?: string;
  /** Stop click bubbling — needed when nested inside a clickable row. */
  stopPropagation?: boolean;
}

/**
 * Two-step delete control.
 *
 * Deleting health records is irreversible, so a single click never destroys
 * anything: the first click arms an inline confirmation, and only the second
 * commits. Inline rather than a modal so it stays in context and doesn't trap
 * focus for a low-stakes-looking action that is actually permanent.
 */
const ConfirmDeleteButton: React.FC<ConfirmDeleteButtonProps> = ({
  onConfirm,
  label,
  confirmText = 'Delete?',
  onError,
  className = '',
  stopPropagation = false,
}) => {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const mounted = useRef(true);

  useEffect(() => () => { mounted.current = false; }, []);

  // Move focus onto the confirm action so keyboard users land on the decision.
  useEffect(() => {
    if (confirming) confirmRef.current?.focus();
  }, [confirming]);

  const guard = (event: React.MouseEvent) => {
    if (stopPropagation) event.stopPropagation();
    event.preventDefault();
  };

  const handleConfirm = async (event: React.MouseEvent) => {
    guard(event);
    setBusy(true);
    try {
      await onConfirm();
      // Parent usually unmounts this row on success; guard the state update.
      if (mounted.current) setConfirming(false);
    } catch (error: any) {
      onError?.(error?.message || 'Could not delete this item. Please try again.');
      if (mounted.current) setConfirming(false);
    } finally {
      if (mounted.current) setBusy(false);
    }
  };

  if (!confirming) {
    return (
      <button
        type="button"
        aria-label={label}
        title={label}
        onClick={(event) => { guard(event); setConfirming(true); }}
        className={`rounded-control p-2 text-[var(--medaid-ink-faint)] transition-colors hover:bg-[var(--risk-emergency-soft)] hover:text-[var(--risk-emergency-text)] ${className}`}
      >
        <Trash2 className="h-4 w-4" />
      </button>
    );
  }

  return (
    <span className="inline-flex shrink-0 items-center gap-1" onClick={stopPropagation ? (e) => e.stopPropagation() : undefined}>
      <button
        ref={confirmRef}
        type="button"
        disabled={busy}
        onClick={handleConfirm}
        aria-label={`Confirm: ${label}`}
        className="inline-flex items-center gap-1 rounded-control bg-[var(--risk-emergency-solid)] px-2.5 py-1.5 text-xs font-semibold text-white transition-[filter] hover:brightness-110 disabled:opacity-60"
      >
        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
        {confirmText}
      </button>
      <button
        type="button"
        disabled={busy}
        onClick={(event) => { guard(event); setConfirming(false); }}
        aria-label="Cancel delete"
        className="rounded-control p-1.5 text-[var(--medaid-ink-muted)] transition-colors hover:bg-[var(--medaid-surface-muted)] hover:text-[var(--medaid-ink)] disabled:opacity-60"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </span>
  );
};

export default ConfirmDeleteButton;
