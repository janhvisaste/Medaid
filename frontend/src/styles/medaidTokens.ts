// ─────────────────────────────────────────────────────────────────────────
// MedAid design tokens.
//
// The runtime source of truth for colour/theming is index.css (CSS variables,
// light + dark). This module mirrors those tokens for documentation and
// exposes the composed utility-class strings (`medaidClasses`) and the risk
// style map (`riskStyles`) that components consume. Both reference the same
// CSS variables, so risk colours are defined in exactly one place.
// ─────────────────────────────────────────────────────────────────────────

export const medaidTokens = {
  // 4px spacing base — use these steps, not arbitrary values.
  space: { 1: '4px', 2: '8px', 3: '12px', 4: '16px', 6: '24px', 8: '32px', 12: '48px', 16: '64px' },
  color: {
    page: '#f6f8f9',
    surface: '#ffffff',
    surfaceMuted: '#f1f5f9',
    ink: '#0f172a',
    inkSoft: '#475569',
    inkMuted: '#64748b',
    inkFaint: '#94a3b8',
    border: '#e2e8f0',
    borderStrong: '#cbd5e1',
    // Brand: MedAid teal — chrome only, never a risk hue.
    brand: '#0f766e',
    brandHover: '#115e59',
    brandSoft: '#d7f2ee',
    // Risk semantics (light-mode reference values; dark variants in index.css).
    // Each soft pairing meets WCAG AA; each solid carries white at ≥ 4.5:1.
    status: {
      emergency: { solid: '#b91c1c', soft: '#fef2f2', text: '#991b1b', border: '#fecaca', line: '#dc2626' },
      high: { solid: '#c2410c', soft: '#fff7ed', text: '#9a3412', border: '#fed7aa', line: '#ea580c' },
      medium: { solid: '#b45309', soft: '#fffbeb', text: '#92400e', border: '#fde68a', line: '#d97706' },
      low: { solid: '#15803d', soft: '#f0fdf4', text: '#166534', border: '#bbf7d0', line: '#16a34a' },
      neutral: { solid: '#475569', soft: '#f1f5f9', text: '#334155', border: '#e2e8f0', line: '#64748b' },
    },
  },
  font: {
    display: "'Newsreader', Georgia, 'Times New Roman', serif",
    body: "'Public Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
    // Type scale: 12 / 14 / 16 / 18 / 24 / 32 / 40 / 52
    scale: { xs: '12px', sm: '14px', base: '16px', lg: '18px', xl: '24px', '2xl': '32px', '3xl': '40px', '4xl': '52px' },
    weights: { normal: 400, medium: 500, semibold: 600, bold: 700 },
  },
  radius: {
    xs: '4px',
    control: '6px', // buttons / inputs
    md: '8px',
    card: '12px',
    panel: '16px',
    pill: '9999px', // chips / badges / avatars only
  },
  elevation: {
    e1: 'shadow-e1',
    e2: 'shadow-e2',
    e3: 'shadow-e3',
  },
  motion: { fast: '120ms', base: '200ms', slow: '320ms', ease: 'cubic-bezier(0.2, 0, 0, 1)' },
  layout: {
    landingContainer: 'max-w-6xl mx-auto px-6',
    dashboardContainer: 'max-w-7xl mx-auto px-4 sm:px-6 py-6',
    sectionPadding: 'py-20 px-6',
  },
} as const;

export type MedaidTheme = 'light' | 'dark';

// Retained for reference; the live theme engine is index.css `:root` blocks.
export const medaidThemeVariables = {
  light: {
    '--medaid-bg': '#f6f8f9',
    '--medaid-surface': '#ffffff',
    '--medaid-surface-muted': '#f1f5f9',
    '--medaid-ink': '#0f172a',
    '--brand': '#0f766e',
  },
  dark: {
    '--medaid-bg': '#0b1220',
    '--medaid-surface': '#131c2e',
    '--medaid-surface-muted': '#1c2740',
    '--medaid-ink': '#f8fafc',
    '--brand': '#2dd4bf',
  },
} as const;

export const medaidClasses = {
  page: 'min-h-screen bg-[var(--medaid-bg)] text-[var(--medaid-ink)]',
  landingContainer: 'max-w-6xl mx-auto px-6',
  dashboardContainer: 'max-w-7xl mx-auto px-4 sm:px-6 py-6',
  nav: 'fixed top-0 inset-x-0 z-50 border-b border-[var(--medaid-border)] bg-[var(--medaid-surface)]/90 backdrop-blur-xl',
  brandMark: 'rounded-md bg-[var(--medaid-surface)] border border-[var(--medaid-border)] flex items-center justify-center shadow-e1',
  // Restrained brand-tinted hero — no purple/indigo AI-gradient trope.
  heroPanel: 'rounded-panel border border-[var(--medaid-border)] bg-gradient-to-br from-[var(--brand-50)] via-[var(--medaid-surface)] to-[var(--medaid-surface)] dark:from-[var(--medaid-surface-muted)] dark:via-[var(--medaid-surface)] dark:to-[var(--medaid-surface)] shadow-e1 relative overflow-hidden',
  restrainedHeroPanel: 'rounded-panel border border-[var(--medaid-border)] bg-gradient-to-br from-[var(--brand-50)] to-[var(--medaid-surface)] dark:from-[var(--medaid-surface-muted)] dark:to-[var(--medaid-surface)] shadow-e1 relative overflow-hidden',
  card: 'rounded-card bg-[var(--medaid-surface)] border border-[var(--medaid-border)] shadow-e1',
  compactCard: 'rounded-card bg-[var(--medaid-surface)] border border-[var(--medaid-border)] shadow-e1',
  compactCardHover: 'rounded-card bg-[var(--medaid-surface)] border border-[var(--medaid-border)] shadow-e1 hover:shadow-e2 hover:border-[var(--medaid-border-strong)] transition-[box-shadow,border-color] duration-200 ease-standard',
  // Primary CTA now carries the brand colour (was near-black slate).
  buttonPrimary: 'rounded-control bg-brand text-brand-contrast text-sm font-semibold hover:bg-brand-hover transition-colors duration-150 ease-standard inline-flex items-center justify-center gap-2',
  buttonSecondary: 'rounded-control border border-[var(--medaid-border-strong)] text-[var(--medaid-ink-soft)] text-sm font-medium hover:bg-[var(--medaid-surface-muted)] transition-colors duration-150 ease-standard inline-flex items-center justify-center gap-2',
  buttonGhost: 'rounded-md text-[var(--medaid-ink-muted)] hover:text-[var(--medaid-ink)] hover:bg-[var(--medaid-surface-muted)] transition-colors duration-150 ease-standard',
  input: 'w-full rounded-control border border-[var(--medaid-border)] bg-[var(--medaid-surface)] px-4 py-2.5 text-sm text-[var(--medaid-ink)] placeholder:text-[var(--medaid-ink-faint)] focus:border-brand focus:outline-none focus:ring-2 focus:ring-[var(--medaid-focus)] transition-colors duration-150',
  select: 'w-full rounded-control border border-[var(--medaid-border)] bg-[var(--medaid-surface)] px-4 py-2.5 text-sm text-[var(--medaid-ink)] focus:border-brand focus:outline-none focus:ring-2 focus:ring-[var(--medaid-focus)] appearance-none transition-colors duration-150',
  badge: 'inline-flex items-center gap-2 rounded-pill bg-[var(--medaid-surface)]/80 border border-[var(--medaid-border)] px-4 py-1.5 text-xs text-[var(--medaid-ink-soft)]',
  statusBadge: 'inline-flex items-center gap-1.5 rounded-pill border px-2.5 py-1 text-xs font-semibold',
  eyebrow: 'text-sm text-[var(--medaid-ink-muted)] uppercase tracking-[0.2em]',
  // Headings use the serif display face — the intentional half of the pairing.
  h1: 'font-display text-4xl md:text-6xl font-medium tracking-tight leading-[1.05] text-[var(--medaid-ink)]',
  h2: 'font-display text-4xl md:text-5xl font-medium leading-tight text-[var(--medaid-ink)]',
  dashboardTitle: 'font-display text-3xl md:text-4xl font-medium tracking-tight leading-tight text-[var(--medaid-ink)]',
  body: 'text-[var(--medaid-ink-soft)]',
  bodySmall: 'text-sm text-[var(--medaid-ink-soft)]',
  mutedSmall: 'text-xs text-[var(--medaid-ink-muted)]',
} as const;

export type MedaidRisk = 'emergency' | 'high' | 'medium' | 'low' | 'neutral';

export interface RiskStyle {
  label: string;
  /** Soft badge treatment: soft bg + AA text + border. */
  className: string;
  /** Solid/high-emphasis treatment: filled bg + white text. */
  solidClassName: string;
  /** Dot / left-border accent colour. */
  dotClassName: string;
  /** Just the accent line colour (for progress bars, left borders). */
  lineClassName: string;
  /** Soft background only (for tinted surfaces). */
  softBgClassName: string;
}

// Single source of truth: every value points at the index.css CSS variables,
// so light/dark are handled centrally and can never drift from the tokens.
export const riskStyles: Record<MedaidRisk, RiskStyle> = {
  emergency: {
    label: 'Emergency',
    className: 'bg-[var(--risk-emergency-soft)] text-[var(--risk-emergency-text)] border-[var(--risk-emergency-border)]',
    solidClassName: 'bg-[var(--risk-emergency-solid)] text-[var(--risk-emergency-on-solid,#fff)]',
    dotClassName: 'bg-[var(--risk-emergency-line)]',
    lineClassName: 'bg-[var(--risk-emergency-line)]',
    softBgClassName: 'bg-[var(--risk-emergency-soft)]',
  },
  high: {
    label: 'High',
    className: 'bg-[var(--risk-high-soft)] text-[var(--risk-high-text)] border-[var(--risk-high-border)]',
    solidClassName: 'bg-[var(--risk-high-solid)] text-[var(--risk-high-on-solid,#fff)]',
    dotClassName: 'bg-[var(--risk-high-line)]',
    lineClassName: 'bg-[var(--risk-high-line)]',
    softBgClassName: 'bg-[var(--risk-high-soft)]',
  },
  medium: {
    label: 'Medium',
    className: 'bg-[var(--risk-medium-soft)] text-[var(--risk-medium-text)] border-[var(--risk-medium-border)]',
    solidClassName: 'bg-[var(--risk-medium-solid)] text-[var(--risk-medium-on-solid,#fff)]',
    dotClassName: 'bg-[var(--risk-medium-line)]',
    lineClassName: 'bg-[var(--risk-medium-line)]',
    softBgClassName: 'bg-[var(--risk-medium-soft)]',
  },
  low: {
    label: 'Low',
    className: 'bg-[var(--risk-low-soft)] text-[var(--risk-low-text)] border-[var(--risk-low-border)]',
    solidClassName: 'bg-[var(--risk-low-solid)] text-[var(--risk-low-on-solid,#fff)]',
    dotClassName: 'bg-[var(--risk-low-line)]',
    lineClassName: 'bg-[var(--risk-low-line)]',
    softBgClassName: 'bg-[var(--risk-low-soft)]',
  },
  neutral: {
    label: 'Neutral',
    className: 'bg-[var(--risk-neutral-soft)] text-[var(--risk-neutral-text)] border-[var(--risk-neutral-border)]',
    solidClassName: 'bg-[var(--risk-neutral-solid)] text-[var(--risk-neutral-on-solid,#fff)]',
    dotClassName: 'bg-[var(--risk-neutral-line)]',
    lineClassName: 'bg-[var(--risk-neutral-line)]',
    softBgClassName: 'bg-[var(--risk-neutral-soft)]',
  },
};
