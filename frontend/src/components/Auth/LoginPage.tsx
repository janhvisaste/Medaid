import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Activity, Eye, EyeOff } from 'lucide-react';
import authService from '../../services/authService';
import { Input } from '../ui/input';
import { Button } from '../ui/button';

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
      await authService.login(formData);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Login failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  const authImage = 'https://i.pinimg.com/736x/39/43/a9/3943a9201b27271b2e99900b63b7a82f.jpg';
  const inputClassName = 'h-11 bg-white border-slate-300 text-slate-900 placeholder:text-slate-400 focus-visible:ring-slate-300 focus-visible:ring-offset-white';

  return (
    <div className="min-h-screen bg-[#f2f4f8] p-4 md:p-8 flex items-center justify-center">
      <div className="w-full max-w-6xl bg-white border border-slate-200 rounded-[2rem] shadow-sm overflow-hidden grid lg:grid-cols-2">
        <motion.div
          initial={{ x: -120 }}
          animate={{ x: 0 }}
          transition={{ type: 'spring', stiffness: 170, damping: 24 }}
          className="relative min-h-[420px] lg:min-h-full"
        >
          <img src={authImage} alt="Medaid login visual" className="absolute inset-0 w-full h-full object-cover" />
          <div className="absolute inset-0 bg-gradient-to-t from-slate-900/55 via-slate-900/25 to-transparent" />
          <div className="absolute inset-x-0 bottom-0 p-8 md:p-10 text-white">
            <p className="text-sm font-medium text-white/90 mb-3">Welcome back to Medaid</p>
            <h2 className="text-3xl font-semibold leading-tight max-w-md">Continue your workflow with secure clinical intelligence.</h2>
            <p className="text-sm text-white/80 mt-3">Report review • Triage support • Care coordination</p>
          </div>
        </motion.div>

        <div className="p-8 md:p-12">
          <button
            onClick={() => navigate('/')}
            className="inline-flex items-center gap-2 text-slate-700 mb-8"
          >
            <span className="w-8 h-8 rounded-lg bg-slate-900 text-white flex items-center justify-center">
              <Activity className="w-4 h-4" />
            </span>
            <span className="font-semibold">Medaid</span>
          </button>

          <h1 className="text-3xl md:text-4xl font-semibold text-slate-900">Welcome back.</h1>
          <p className="text-slate-500 mt-2 mb-6">Sign in to continue with your Medaid workspace.</p>
          <p className="text-sm text-slate-500 mb-6">
            New to Medaid?{' '}
            <Link to="/signup" className="text-slate-900 font-medium underline">Create account</Link>
          </p>

          {error && (
            <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-3 text-red-600 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4" autoComplete="off">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Email</label>
              <Input
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
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Password</label>
              <Input
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
                className="absolute right-3 top-9 text-slate-400"
              >
                {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            </div>

            <div className="flex items-center justify-between text-sm">
              <label className="flex items-center gap-2 text-slate-600">
                <input type="checkbox" className="rounded border-slate-300" />
                Remember me
              </label>
              <span className="text-slate-400">Forgot password</span>
            </div>

            <Button
              disabled={loading}
              type="submit"
              className="w-full h-11 bg-slate-900 hover:bg-slate-800 text-white font-semibold rounded-lg"
            >
              {loading ? 'Signing in...' : 'Log In'}
            </Button>

            <button
              type="button"
              className="w-full h-11 rounded-lg border border-dashed border-slate-300 text-slate-600 hover:text-slate-900 hover:border-slate-500 hover:bg-slate-50 transition-all text-sm"
              onClick={() => {
                setFormData({
                  email: 'test@medaid.com',
                  password: 'Test1234!'
                });
              }}
            >
              Fill Demo Credentials
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
