import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  Activity, Apple, FileText, History, Home, Lightbulb, LogOut, Menu, Moon,
  PanelLeftClose, PanelLeftOpen, Settings, ShieldCheck, Sun, UserRound, X,
} from 'lucide-react';
import authService from '../../services/authService';
import { medaidClasses } from '../../styles/medaidTokens';
import { useTheme } from './ThemeProvider';

const patientLinks = [
  { path: '/dashboard', label: 'AI workspace', icon: Home },
  { path: '/assessments', label: 'Assessment history', icon: History },
  { path: '/medical-history', label: 'Medical history', icon: FileText },
  { path: '/medical-history-insights', label: 'Report insights', icon: Lightbulb },
  { path: '/dietary-advice', label: 'Dietary advice', icon: Apple },
];

interface AppShellProps { children: React.ReactNode; }

const AppShell: React.FC<AppShellProps> = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const user = authService.getUser();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);

  const handleLogout = async () => {
    await authService.logout();
    navigate('/login');
  };

  const links = user?.role === 'clinician'
    ? [...patientLinks, { path: '/clinician', label: 'Clinician dashboard', icon: ShieldCheck }]
    : patientLinks;

  const title = links.find(link => location.pathname === link.path)?.label
    || (location.pathname.startsWith('/medical-document') ? 'Report detail' : 'Medaid workspace');

  return (
    // Fixed-height app frame: the sidebar and top bar stay put; only <main>
    // scrolls. Keeps the shell intact on long pages (history, dietary advice).
    <div className="flex h-screen overflow-hidden bg-[var(--medaid-bg)] text-[var(--medaid-ink)]">
      {mobileOpen && (
        <button aria-label="Close navigation" className="fixed inset-0 z-30 bg-[var(--medaid-overlay)] md:hidden" onClick={() => setMobileOpen(false)} />
      )}

      <aside className={`fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-[var(--medaid-border)] bg-[var(--medaid-surface)] transition-transform md:relative md:translate-x-0 ${mobileOpen ? 'translate-x-0' : '-translate-x-full'} ${collapsed ? 'md:w-20' : 'md:w-72'}`}>
        <div className="flex h-16 items-center justify-between border-b border-[var(--medaid-border)] px-4">
          <Link to="/dashboard" className="flex min-w-0 items-center gap-3" onClick={() => setMobileOpen(false)}>
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-brand text-brand-contrast">
              <Activity className="h-4 w-4" />
            </span>
            {!collapsed && <span className="truncate text-lg font-bold tracking-tight text-[var(--medaid-ink)]">Medaid</span>}
          </Link>
          <button className="rounded-lg p-2 text-[var(--medaid-ink-muted)] hover:bg-[var(--medaid-surface-muted)] md:hidden" onClick={() => setMobileOpen(false)} aria-label="Close menu">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-5">
          <Link to="/dashboard" onClick={() => setMobileOpen(false)} className={`mb-5 flex items-center justify-center gap-2 px-4 py-3 ${medaidClasses.buttonPrimary} ${collapsed ? 'md:px-2' : ''}`}>
            <Activity className="h-4 w-4" />
            {!collapsed && 'Start consultation'}
          </Link>
          <nav className="space-y-1" aria-label="Main navigation">
            {links.map(({ path, label, icon: Icon }) => {
              const active = location.pathname === path || (path === '/medical-history-insights' && location.pathname.startsWith('/medical-document'));
              return (
                <Link key={path} to={path} onClick={() => setMobileOpen(false)} title={collapsed ? label : undefined} className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors ${active ? 'bg-[var(--medaid-accent-soft)] text-[var(--medaid-accent-strong)]' : 'text-[var(--medaid-ink-soft)] hover:bg-[var(--medaid-surface-muted)] hover:text-[var(--medaid-ink)]'} ${collapsed ? 'md:justify-center md:px-2' : ''}`}>
                  <Icon className="h-4 w-4 shrink-0" />
                  {!collapsed && label}
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="border-t border-[var(--medaid-border)] p-3">
          <div className={`mb-2 flex items-center gap-3 rounded-xl border border-[var(--medaid-border)] p-2.5 ${collapsed ? 'md:justify-center' : ''}`}>
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--medaid-accent-soft)] text-xs font-bold text-[var(--medaid-accent-strong)]">{(user?.first_name?.[0] || user?.email?.[0] || 'M').toUpperCase()}</span>
            {!collapsed && <div className="min-w-0"><p className="truncate text-sm font-semibold text-[var(--medaid-ink)]">{user?.first_name || 'Medaid member'}</p><p className="truncate text-xs text-[var(--medaid-ink-muted)]">{user?.email || 'Signed in'}</p></div>}
          </div>
          <button onClick={() => setCollapsed(value => !value)} className="hidden w-full items-center justify-center gap-2 rounded-lg px-3 py-2 text-xs text-[var(--medaid-ink-muted)] hover:bg-[var(--medaid-surface-muted)] md:flex" aria-label={collapsed ? 'Expand navigation' : 'Collapse navigation'}>
            {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <><PanelLeftClose className="h-4 w-4" /> Collapse</>}
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="z-20 flex h-16 shrink-0 items-center justify-between border-b border-[var(--medaid-border)] bg-[var(--medaid-surface)]/90 px-4 backdrop-blur-xl md:px-6">
          <div className="flex items-center gap-3">
            <button className="rounded-lg p-2 text-[var(--medaid-ink-muted)] hover:bg-[var(--medaid-surface-muted)] md:hidden" onClick={() => setMobileOpen(true)} aria-label="Open navigation"><Menu className="h-5 w-5" /></button>
            <div><p className="text-xs uppercase tracking-[0.16em] text-[var(--medaid-ink-muted)]">Medaid</p><h1 className="text-sm font-semibold text-[var(--medaid-ink)] md:text-base">{title}</h1></div>
          </div>
          <div className="relative flex items-center gap-1">
            <button onClick={toggleTheme} className="rounded-lg p-2 text-[var(--medaid-ink-muted)] hover:bg-[var(--medaid-surface-muted)]" aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`} title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}>
              {theme === 'dark' ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
            </button>
            <button onClick={() => setAccountOpen(value => !value)} className="flex items-center gap-2 rounded-xl px-2 py-1.5 text-left hover:bg-[var(--medaid-surface-muted)]" aria-expanded={accountOpen}>
              <UserRound className="h-5 w-5 text-[var(--medaid-ink-muted)]" /><span className="hidden text-sm font-medium text-[var(--medaid-ink)] sm:block">Account</span>
            </button>
            {accountOpen && <div className="absolute right-0 top-12 z-50 w-56 rounded-card border border-[var(--medaid-border)] bg-[var(--medaid-surface)] p-2 shadow-e2">
              <Link to="/profile" onClick={() => setAccountOpen(false)} className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-[var(--medaid-ink-soft)] hover:bg-[var(--medaid-surface-muted)]"><UserRound className="h-4 w-4" /> Profile</Link>
              <button onClick={toggleTheme} className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-[var(--medaid-ink-soft)] hover:bg-[var(--medaid-surface-muted)]"><Settings className="h-4 w-4" /> {theme === 'dark' ? 'Use light theme' : 'Use dark theme'}</button>
              {user?.role === 'clinician' && <Link to="/clinician" onClick={() => setAccountOpen(false)} className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-[var(--medaid-ink-soft)] hover:bg-[var(--medaid-surface-muted)]"><ShieldCheck className="h-4 w-4" /> Clinician dashboard</Link>}
              <button onClick={handleLogout} className="flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-sm text-[var(--risk-emergency-text)] hover:bg-[var(--risk-emergency-soft)]"><LogOut className="h-4 w-4" /> Sign out</button>
            </div>}
          </div>
        </header>
        <main className="flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
};

export default AppShell;
