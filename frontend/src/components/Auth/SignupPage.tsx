import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Activity, Eye, EyeOff, HeartPulse, ShieldCheck } from 'lucide-react';
import authService from '../../services/authService';
import { Input } from '../ui/input';
import { Button } from '../ui/button';
import { medaidClasses } from '../../styles/medaidTokens';

const SignupPage: React.FC = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    phone: '',
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [showPassword, setShowPassword] = useState(false);
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    setError('');
  };

  const validateForm = (): boolean => {
    if (!formData.first_name || !formData.last_name) {
      setError('First and Last name are required');
      return false;
    }
    if (!formData.email) {
      setError('Email is required');
      return false;
    }
    if (!formData.password) {
      setError('Password is required');
      return false;
    }
    if (formData.password.length < 8) {
      setError('Password must be at least 8 characters');
      return false;
    }
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(formData.email)) {
      setError('Invalid email format');
      return false;
    }
    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return false;
    }
    if (!acceptedTerms) {
      setError('Please agree to the Terms & Privacy Policy');
      return false;
    }
    return true;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

    setLoading(true);
    try {
      const signupData = {
        email: formData.email,
        password: formData.password,
        confirm_password: formData.password,
        first_name: formData.first_name,
        last_name: formData.last_name,
        phone_number: formData.phone,
      };

      const result = await authService.signup(signupData);
      navigate(result.user?.role === 'clinician' ? '/clinician' : '/dashboard');
    } catch (err: any) {
      setError(err.message || 'Signup failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const inputClassName = `${medaidClasses.input} h-11`;
  const labelClassName = 'mb-1.5 block text-sm font-medium text-[var(--medaid-ink-soft)]';

  return (
    <div className={`${medaidClasses.page} flex min-h-screen items-center justify-center p-4 md:p-8`}>
      <div className="grid w-full max-w-5xl overflow-hidden rounded-panel border border-[var(--medaid-border)] bg-[var(--medaid-surface)] shadow-e2 lg:grid-cols-2">
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

          <h1 className="font-display text-3xl font-medium tracking-tight text-[var(--medaid-ink)] md:text-4xl">Welcome to Medaid.</h1>
          <p className="mb-6 mt-2 text-[var(--medaid-ink-muted)]">Let's help you get started with better care.</p>
          <p className="mb-6 text-sm text-[var(--medaid-ink-muted)]">
            Already have an account?{' '}
            <Link to="/login" className="font-medium text-[var(--medaid-accent-strong)] underline">Log in</Link>
          </p>

          {error && (
            <div role="alert" className="mb-4 rounded-md border border-[var(--risk-emergency-border)] bg-[var(--risk-emergency-soft)] p-3 text-sm text-[var(--risk-emergency-text)]">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4" autoComplete="off">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="su-first" className={labelClassName}>First name</label>
                <Input id="su-first" type="text" name="first_name" value={formData.first_name} onChange={handleInputChange} placeholder="Enter first name" className={inputClassName} autoComplete="off" />
              </div>
              <div>
                <label htmlFor="su-last" className={labelClassName}>Last name</label>
                <Input id="su-last" type="text" name="last_name" value={formData.last_name} onChange={handleInputChange} placeholder="Enter last name" className={inputClassName} autoComplete="off" />
              </div>
              <div>
                <label htmlFor="su-phone" className={labelClassName}>Phone</label>
                <Input id="su-phone" type="tel" name="phone" value={formData.phone} onChange={handleInputChange} placeholder="Enter phone number" className={inputClassName} autoComplete="off" />
              </div>
              <div>
                <label htmlFor="su-email" className={labelClassName}>Email</label>
                <Input id="su-email" type="email" name="email" value={formData.email} onChange={handleInputChange} placeholder="Enter email" className={inputClassName} autoComplete="off" />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="relative">
                <label htmlFor="su-password" className={labelClassName}>Password</label>
                <Input
                  id="su-password"
                  type={showPassword ? 'text' : 'password'}
                  name="password"
                  value={formData.password}
                  onChange={handleInputChange}
                  placeholder="Enter password"
                  className={`${inputClassName} pr-10`}
                  autoComplete="new-password"
                />
                <button type="button" onClick={() => setShowPassword(!showPassword)} aria-label={showPassword ? 'Hide password' : 'Show password'} className="absolute right-3 top-9 text-[var(--medaid-ink-faint)] transition-colors hover:text-[var(--medaid-ink-soft)]">
                  {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                </button>
              </div>
              <div>
                <label htmlFor="su-confirm" className={labelClassName}>Confirm password</label>
                <Input
                  id="su-confirm"
                  type={showPassword ? 'text' : 'password'}
                  name="confirmPassword"
                  value={formData.confirmPassword}
                  onChange={handleInputChange}
                  placeholder="Re-enter password"
                  className={inputClassName}
                  autoComplete="new-password"
                />
              </div>
            </div>

            <label className="flex items-center gap-2 text-sm text-[var(--medaid-ink-soft)]">
              <input type="checkbox" className="rounded border-[var(--medaid-border-strong)] text-brand focus-visible:ring-2 focus-visible:ring-[var(--medaid-focus)]" />
              I want to receive Medaid updates and product news
            </label>
            <label className="flex items-center gap-2 text-sm text-[var(--medaid-ink-soft)]">
              <input type="checkbox" checked={acceptedTerms} onChange={event => setAcceptedTerms(event.target.checked)} className="rounded border-[var(--medaid-border-strong)] text-brand focus-visible:ring-2 focus-visible:ring-[var(--medaid-focus)]" />
              I agree to the Terms &amp; Privacy Policy
            </label>

            <Button disabled={loading} type="submit" className="h-11 w-full font-semibold">
              {loading ? 'Creating account…' : 'Sign up'}
            </Button>
          </form>
        </div>

        {/* Calm, branded trust panel — no stock imagery */}
        <aside className="relative hidden animate-fade-in overflow-hidden bg-gradient-to-br from-brand-700 via-brand-800 to-brand-900 lg:block">
          <div aria-hidden="true" className="pointer-events-none absolute -left-16 -top-16 h-56 w-56 rounded-full bg-white/10 blur-2xl" />
          <div aria-hidden="true" className="pointer-events-none absolute -bottom-20 -right-10 h-56 w-56 rounded-full bg-black/10 blur-2xl" />
          <div className="relative flex h-full flex-col justify-between p-10 text-white">
            <div className="flex items-center gap-2">
              <span className="flex h-9 w-9 items-center justify-center rounded-md bg-white/15"><Activity className="h-4 w-4" /></span>
              <span className="text-lg font-semibold tracking-tight">Medaid</span>
            </div>
            <div>
              <h2 className="font-display text-3xl font-medium leading-tight">Triage clarity and smarter healthcare decisions.</h2>
              <p className="mt-3 max-w-sm text-sm leading-6 text-white/80">Built for patients, clinicians, and care teams — thoughtful guidance you can act on.</p>
            </div>
            <ul className="space-y-2.5 text-sm text-white/85">
              <li className="flex items-center gap-2.5"><ShieldCheck className="h-4 w-4 shrink-0" /> Encrypted and private from the first step.</li>
              <li className="flex items-center gap-2.5"><HeartPulse className="h-4 w-4 shrink-0" /> Understand what your symptoms may mean — calmly.</li>
            </ul>
          </div>
        </aside>
      </div>
    </div>
  );
};

export default SignupPage;
