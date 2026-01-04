import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Eye, EyeOff, Github } from 'lucide-react';
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

  return (
    <div className="min-h-screen flex">
      {/* Left Side - Branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-purple-600 via-purple-700 to-indigo-900 p-12 flex-col justify-between relative overflow-hidden">
        {/* Gradient Overlay */}
        <div className="absolute inset-0 bg-gradient-to-br from-purple-500/50 via-purple-600/50 to-indigo-800/50"></div>

        <div className="relative z-10">
          <div className="flex items-center gap-2 text-white mb-16">
            <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center">
              <span className="text-purple-700 font-bold text-lg">M</span>
            </div>
            <span className="text-xl font-semibold">Medaid</span>
          </div>

          <div className="max-w-md">
            <h1 className="text-5xl font-bold text-white mb-8 leading-tight">
              Welcome Back
            </h1>
            <p className="text-purple-100 text-lg mb-12">
              Sign in to access your AI-powered healthcare dashboard and continue transforming patient care.
            </p>

            <div className="space-y-4">
              <div className="flex items-center gap-4 bg-white/10 backdrop-blur-sm rounded-2xl p-4 border border-white/20">
                <div className="w-10 h-10 bg-white rounded-full flex items-center justify-center flex-shrink-0">
                  <svg className="w-5 h-5 text-purple-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <span className="text-white font-medium">Secure & encrypted connection</span>
              </div>

              <div className="flex items-center gap-4 bg-white/5 backdrop-blur-sm rounded-2xl p-4 border border-white/10">
                <div className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center flex-shrink-0">
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                  </svg>
                </div>
                <span className="text-purple-200">HIPAA compliant platform</span>
              </div>

              <div className="flex items-center gap-4 bg-white/5 backdrop-blur-sm rounded-2xl p-4 border border-white/10">
                <div className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center flex-shrink-0">
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                <span className="text-purple-200">AI-powered insights</span>
              </div>
            </div>
          </div>
        </div>

        {/* Decorative circles */}
        <div className="absolute -bottom-20 -right-20 w-96 h-96 bg-purple-500/20 rounded-full blur-3xl"></div>
        <div className="absolute top-1/4 -left-20 w-72 h-72 bg-indigo-500/20 rounded-full blur-3xl"></div>
      </div>

      {/* Right Side - Form */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8 bg-black">
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.6 }}
          className="w-full max-w-md"
        >
          <div className="mb-8">
            <h2 className="text-3xl font-bold text-white mb-2">Log In Account</h2>
            <p className="text-gray-400 text-sm">Enter your credentials to access your account.</p>
          </div>

          {/* Social Login Buttons */}
          <div className="grid grid-cols-2 gap-4 mb-6">
            <button
              onClick={() => {
                setLoading(true);
                setError('');
                setTimeout(() => {
                  setLoading(false);
                  setError('Google login is unavailable in this prototype. Please use email/password.');
                }, 1000);
              }}
              disabled={loading}
              type="button"
              className="flex items-center justify-center gap-2 bg-gray-900 hover:bg-gray-800 border border-gray-800 rounded-xl py-3 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
              </svg>
              <span className="text-white text-sm font-medium">Google</span>
            </button>

            <button
              onClick={() => {
                setLoading(true);
                setError('');
                setTimeout(() => {
                  setLoading(false);
                  setError('Github login is unavailable in this prototype. Please use email/password.');
                }, 1000);
              }}
              disabled={loading}
              type="button"
              className="flex items-center justify-center gap-2 bg-gray-900 hover:bg-gray-800 border border-gray-800 rounded-xl py-3 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Github className="w-5 h-5 text-white" />
              <span className="text-white text-sm font-medium">Github</span>
            </button>
          </div>

          <div className="relative mb-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-800"></div>
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-2 bg-black text-gray-500">Or</span>
            </div>
          </div>

          {/* Error message */}
          {error && (
            <div className="mb-4 bg-red-500/10 border border-red-500/50 rounded-lg p-3 text-red-400 text-sm">
              {error}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Email field */}
            <div>
              <label className="block text-sm text-gray-400 mb-2">Email</label>
              <Input
                type="email"
                name="email"
                value={formData.email}
                onChange={handleInputChange}
                placeholder="eg. johnfrans@gmail.com"
                className="bg-gray-900 border-gray-800 text-white placeholder:text-gray-600"
              />
            </div>

            {/* Password field */}
            <div>
              <label className="block text-sm text-gray-400 mb-2">Password</label>
              <div className="relative">
                <Input
                  type={showPassword ? 'text' : 'password'}
                  name="password"
                  value={formData.password}
                  onChange={handleInputChange}
                  placeholder="Enter your password"
                  className="bg-gray-900 border-gray-800 text-white placeholder:text-gray-600 pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-2.5 text-gray-500 hover:text-gray-400 transition-colors"
                >
                  {showPassword ? (
                    <EyeOff className="w-5 h-5" />
                  ) : (
                    <Eye className="w-5 h-5" />
                  )}
                </button>
              </div>
            </div>

            {/* Remember me */}
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <input
                  type="checkbox"
                  id="remember"
                  className="w-4 h-4 rounded bg-gray-900 border-gray-700 text-blue-600 focus:ring-blue-500 cursor-pointer"
                />
                <label htmlFor="remember" className="ml-2 text-sm text-gray-400 cursor-pointer">
                  Remember me
                </label>
              </div>
              <Link to="/forgot-password" className="text-sm text-gray-400 hover:text-white transition-colors">
                Forgot password?
              </Link>
            </div>

            {/* Submit button */}
            <Button
              disabled={loading}
              type="submit"
              className="w-full h-11 bg-white hover:bg-gray-100 text-black font-semibold"
            >
              {loading ? 'Signing in...' : 'Log In'}
            </Button>

            {/* Signup link */}
            <div className="text-center">
              <p className="text-gray-400 text-sm">
                Don't have an account?{' '}
                <Link to="/signup" className="text-white hover:text-gray-300 font-semibold transition-colors underline">
                  Sign up
                </Link>
              </p>
            </div>
          </form>
        </motion.div>
      </div>
    </div>
  );
};

export default LoginPage;
