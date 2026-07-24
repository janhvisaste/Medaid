import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Activity, Eye, EyeOff, Lock, ShieldCheck, Stethoscope } from 'lucide-react';
import authService from '../../services/authService';
import { Input } from '../ui/input';
import { Button } from '../ui/button';
import { medaidClasses } from '../../styles/medaidTokens';

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    email: '',
    password: '',
  });
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    setError('');
  };

  const validateForm = (): boolean => {
    if (!formData.email) {
      setError('Email is required');
      return false;
    }
    if (!formData.password) {
      setError('Password is required');
      return false;
    }
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(formData.email)) {
      setError('Invalid email format');
      return false;
    }
    return true;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

    setLoading(true);
    try {
      const result = await authService.login(formData);
      navigate(result.user?.role === 'clinician' ? '/clinician' : '/dashboard');
    } catch (err: any) {
      setError(err.message || 'Login failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  const inputClassName = `${medaidClasses.input} h-11`;

  return (
    <div className={`${medaidClasses.page} flex min-h-screen items-center justify-center p-4 md:p-8`}>
      <div className="grid w-full max-w-5xl overflow-hidden rounded-panel border border-[var(--medaid-border)] bg-[var(--medaid-surface)] shadow-e2 lg:grid-cols-2">
        {/* Calm, branded trust panel — no stock imagery, first impression signals a healthcare product */}
        <aside className="relative hidden animate-fade-in overflow-hidden bg-gradient-to-br from-brand-700 via-brand-800 to-brand-900 lg:block">
          <div aria-hidden="true" className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full bg-white/10 blur-2xl" />
          <div aria-hidden="true" className="pointer-events-none absolute -bottom-20 -left-10 h-56 w-56 rounded-full bg-black/10 blur-2xl" />
          <div className="relative flex h-full flex-col justify-between p-10 text-white">
            <div className="flex items-center gap-2">
              <span className="flex h-9 w-9 items-center justify-center rounded-md bg-white/15"><Activity className="h-4 w-4" /></span>
              <span className="text-lg font-semibold tracking-tight">Medaid</span>
            </div>
            <div>
              <h2 className="font-display text-3xl font-medium leading-tight">Welcome back to calmer, clearer care decisions.</h2>
              <p className="mt-3 max-w-sm text-sm leading-6 text-white/80">Report review · Triage support · Care coordination — all in one secure workspace.</p>
            </div>
            <ul className="space-y-2.5 text-sm text-white/85">
              <li className="flex items-center gap-2.5"><ShieldCheck className="h-4 w-4 shrink-0" /> Private by design — your records stay yours.</li>
              <li className="flex items-center gap-2.5"><Stethoscope className="h-4 w-4 shrink-0" /> Preliminary guidance, reviewed with your care team.</li>
            </ul>
          </div>
        </aside>

        <div className="p-8 md:p-12">
          <button
            onClick={() => navigate('/')}
            className="mb-8 inline-flex items-center gap-2 text-[var(--medaid-ink-soft)] transition-colors hover:text-[var(--medaid-ink)]"
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-md bg-brand text-brand-contrast">
              <Activity className="h-4 w-4" />
            </span>
            <span className="font-semibold">Medaid</span>
          </button>

          <h1 className="font-display text-3xl font-medium tracking-tight text-[var(--medaid-ink)] md:text-4xl">Welcome back.</h1>
          <p className="mb-6 mt-2 text-[var(--medaid-ink-muted)]">Sign in to continue with your Medaid workspace.</p>
          <p className="mb-6 text-sm text-[var(--medaid-ink-muted)]">
            New to Medaid?{' '}
            <Link to="/signup" className="font-medium text-[var(--medaid-accent-strong)] underline">Create account</Link>
          </p>

          {error && (
            <div role="alert" className="mb-4 rounded-md border border-[var(--risk-emergency-border)] bg-[var(--risk-emergency-soft)] p-3 text-sm text-[var(--risk-emergency-text)]">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4" autoComplete="off">
            <div>
              <label htmlFor="login-email" className="mb-1.5 block text-sm font-medium text-[var(--medaid-ink-soft)]">Email</label>
              <Input
                id="login-email"
                type="email"
                name="email"
                value={formData.email}
                onChange={handleInputChange}
                placeholder="Enter your email"
                className={inputClassName}
                autoComplete="off"
              />
            </div>

            <div className="relative">
              <label htmlFor="login-password" className="mb-1.5 block text-sm font-medium text-[var(--medaid-ink-soft)]">Password</label>
              <Input
                id="login-password"
                type={showPassword ? 'text' : 'password'}
                name="password"
                value={formData.password}
                onChange={handleInputChange}
                placeholder="Enter your password"
                className={`${inputClassName} pr-10`}
                autoComplete="current-password"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                className="absolute right-3 top-9 text-[var(--medaid-ink-faint)] transition-colors hover:text-[var(--medaid-ink-soft)]"
              >
                {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
              </button>
            </div>

            <div className="flex items-center justify-between text-sm">
              <label className="flex items-center gap-2 text-[var(--medaid-ink-soft)]">
                <input type="checkbox" className="rounded border-[var(--medaid-border-strong)] text-brand focus-visible:ring-2 focus-visible:ring-[var(--medaid-focus)]" />
                Remember me
              </label>
              <span className="text-[var(--medaid-ink-faint)]">Forgot password</span>
            </div>

            <Button disabled={loading} type="submit" className="h-11 w-full font-semibold">
              {loading ? 'Signing in…' : 'Log in'}
            </Button>

            <button
              type="button"
              className="flex h-11 w-full items-center justify-center gap-2 rounded-control border border-dashed border-[var(--medaid-border-strong)] text-sm text-[var(--medaid-ink-muted)] transition-colors hover:border-brand hover:bg-[var(--medaid-surface-muted)] hover:text-[var(--medaid-ink)]"
              onClick={() => {
                setFormData({
                  email: 'test@medaid.com',
                  password: 'Test1234!'
                });
              }}
            >
              <Lock className="h-3.5 w-3.5" /> Fill demo credentials
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
