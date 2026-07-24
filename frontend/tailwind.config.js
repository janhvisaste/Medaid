// tailwind.config.js
/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ['class', '[data-theme="dark"]'],
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      // Type pairing — Public Sans is the default (body / UI / data); the serif
      // display face is opt-in via `font-display` for headings only.
      fontFamily: {
        sans: ['"Public Sans"', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'sans-serif'],
        display: ['Newsreader', 'Georgia', '"Times New Roman"', 'serif'],
      },
      // Additive display sizes (Tailwind's default numeric scale stays intact).
      fontSize: {
        'display-sm': ['1.5rem', { lineHeight: '2rem', letterSpacing: '-0.01em' }],
        'display-md': ['2rem', { lineHeight: '2.5rem', letterSpacing: '-0.015em' }],
        'display-lg': ['2.5rem', { lineHeight: '3rem', letterSpacing: '-0.02em' }],
        'display-xl': ['3.25rem', { lineHeight: '3.5rem', letterSpacing: '-0.02em' }],
      },
      // Semantic colours resolve to CSS variables so light/dark theming lives
      // in one place (index.css). brand-* = chrome; risk-* = triage semantics.
      colors: {
        brand: {
          DEFAULT: 'var(--brand)',
          hover: 'var(--brand-hover)',
          contrast: 'var(--brand-contrast)',
          50: 'var(--brand-50)', 100: 'var(--brand-100)', 200: 'var(--brand-200)',
          300: 'var(--brand-300)', 400: 'var(--brand-400)', 500: 'var(--brand-500)',
          600: 'var(--brand-600)', 700: 'var(--brand-700)', 800: 'var(--brand-800)',
          900: 'var(--brand-900)',
        },
        risk: {
          'emergency': 'var(--risk-emergency-solid)',
          'emergency-soft': 'var(--risk-emergency-soft)',
          'emergency-text': 'var(--risk-emergency-text)',
          'emergency-line': 'var(--risk-emergency-line)',
          'high': 'var(--risk-high-solid)',
          'high-soft': 'var(--risk-high-soft)',
          'high-text': 'var(--risk-high-text)',
          'high-line': 'var(--risk-high-line)',
          'medium': 'var(--risk-medium-solid)',
          'medium-soft': 'var(--risk-medium-soft)',
          'medium-text': 'var(--risk-medium-text)',
          'medium-line': 'var(--risk-medium-line)',
          'low': 'var(--risk-low-solid)',
          'low-soft': 'var(--risk-low-soft)',
          'low-text': 'var(--risk-low-text)',
          'low-line': 'var(--risk-low-line)',
        },
      },
      borderRadius: {
        control: 'var(--radius-sm)', // 6px — buttons / inputs
        card: 'var(--radius-lg)',    // 12px — cards
        panel: 'var(--radius-xl)',   // 16px — large panels
      },
      boxShadow: {
        e1: 'var(--elev-1)',
        e2: 'var(--elev-2)',
        e3: 'var(--elev-3)',
      },
      transitionTimingFunction: {
        standard: 'var(--ease-standard)',
        emphasized: 'var(--ease-emphasized)',
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
