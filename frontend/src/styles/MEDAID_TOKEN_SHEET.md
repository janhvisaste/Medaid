# Medaid Landing Token Sheet

Source of truth: `frontend/src/components/MedaidLanding.tsx` and `frontend/src/index.css`.

## Phase 0 - Literal Landing Tokens

### Color

| Purpose | Literal value | Tailwind/CSS source |
| --- | --- | --- |
| Page background | `#f7f8fb` | `bg-[#f7f8fb]`, `rgba(247,248,251,alpha)` |
| Surface | `#ffffff` | `bg-white`, `bg-white/70`, `bg-white/80`, `bg-white/90` |
| Primary text | `#0f172a` | `text-slate-900`, `bg-slate-900` |
| Primary hover panel | `#1e293b` | `hover:bg-slate-800` |
| Secondary text | `#475569` | `text-slate-600`, `text-slate-700` |
| Muted text | `#64748b` | `text-slate-500` |
| Faint icon text | `#94a3b8` | `text-slate-400` |
| Border | `#e2e8f0` | `border-slate-200`, `border-slate-200/70` |
| Strong border | `#cbd5e1` | `border-slate-300` |
| Accent | `#0284c7` | `text-sky-600` |
| Strong accent | `#0369a1` | `text-sky-700` |
| Accent wash | `#e0f2fe` | `from-sky-100`, `bg-sky-100` |
| Secondary wash | `#e0e7ff` | `to-indigo-100` |
| Accent glow | `rgba(14,165,233,0.12)` | radial hero background |
| Hero orb | `rgba(125,211,252,0.20)` | `bg-sky-300/20` |
| Secondary orb | `rgba(165,180,252,0.20)` | `bg-indigo-300/20` |
| Image overlay | `rgba(15,23,42,0.35)` | `from-slate-900/35` |

Clinical status colors are a dashboard extension because the landing page does not define Low/Medium/High/Emergency states. They stay in the same subdued wash/border vocabulary: `red-100/800/200`, `orange-100/800/200`, `amber-100/800/200`, and `sky-100/800/200`.

### Typography

| Use | Literal source |
| --- | --- |
| Body family | `Inter`, then system fallbacks from `index.css` |
| Imported but unused on landing | `Cormorant Garamond`, `Cinzel`, `Poppins` |
| Logo | `text-lg font-bold tracking-tight` |
| Hero H1 | `text-4xl md:text-6xl font-semibold tracking-tight leading-[1.05]` |
| Section H2 | `text-4xl md:text-5xl font-semibold leading-tight` |
| Card title | `text-2xl font-semibold`, compact cards `text-lg font-semibold` |
| Body large | `text-lg text-slate-600` |
| Body | `text-sm`, `text-slate-600`, `leading-relaxed` |
| Eyebrow | `text-sm uppercase tracking-[0.2em]` |
| Fine print | `text-xs text-slate-500` |

### Spacing And Layout

| Pattern | Literal value/classes |
| --- | --- |
| Landing container | `max-w-6xl mx-auto px-6` |
| Dashboard container extension | `max-w-7xl mx-auto px-4 sm:px-6 py-6` |
| Nav height | `h-16` |
| Hero section | `pt-28 pb-20 px-6` |
| General sections | `py-20 px-6` |
| Hero panel padding | `p-10 md:p-14` |
| Card padding | `p-7`, compact `px-5 py-4`, metric `p-5` |
| Grid gaps | `gap-3`, `gap-4`, `gap-5`, `gap-8` |
| Card image height | `h-36`, recognition image `h-64` |

### Component Style

| Component | Landing treatment |
| --- | --- |
| Primary CTA | `rounded-full bg-slate-900 text-white text-sm font-semibold hover:bg-slate-800` |
| Secondary CTA | `rounded-full border border-slate-300 text-slate-700 hover:bg-white` |
| Nav pill | `rounded-lg px-4 py-2 text-sm font-medium`; active state `bg-white shadow-sm border border-slate-200` |
| Card | `bg-white border border-slate-200 shadow-sm`, `rounded-3xl` or `rounded-2xl` |
| Hover card | `hover:shadow-md transition-shadow` |
| Badge/chip | `rounded-full bg-white/80 border border-slate-200 px-4 py-1.5 text-xs text-slate-600` |
| Inputs/selects | Not present on landing; dashboard uses landing card/control radius, slate borders, sky focus ring |

### Signature Visual Element

Restrained sky/indigo medical-tech wash: `bg-gradient-to-r from-sky-100/80 to-indigo-100/80`, radial sky glow, and soft blurred sky/indigo circles. Dashboard may reuse this only in header/chrome, not table bodies.

## Phase 1 - Clinician Dashboard Audit Before Refit

- Page background used `from-blue-50 via-white to-purple-50`, which does not map to the landing page's `#f7f8fb` plus sky/indigo wash.
- Cards used `rounded-2xl shadow-lg border-2`, while landing cards use `rounded-3xl` or `rounded-2xl`, one-pixel `border-slate-200`, and `shadow-sm`.
- Text used `text-gray-*` and bold dashboard headings; landing uses slate tokens and `font-semibold tracking-tight` for large headings.
- Inputs/selects used default gray borders and blue focus rings; landing has no form controls, so controls should inherit slate border, white surface, rounded landing radii, and sky accent focus.
- Status pills used separate red/orange/yellow/green systems with heavier borders. Landing has no status system, so dashboard needs a small clinical extension that keeps subdued fills, readable text, and explicit labels/dots.
- Patient rows used thick bordered cards with blue hover borders; landing uses subtle surface separation and soft shadow hover.
- Empty-state helper panels used purple/pink and blue/cyan gradients that are not in the landing palette.

## Shared Source

Reusable runtime tokens live in `frontend/src/styles/medaidTokens.ts`.
