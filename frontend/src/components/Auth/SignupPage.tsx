import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Activity, Eye, EyeOff } from 'lucide-react';
import authService from '../../services/authService';
import { Input } from '../ui/input';
import { Button } from '../ui/button';

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
      };

      await authService.signup(signupData);
      navigate('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Signup failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const authImage = 'https://i.pinimg.com/736x/73/b1/81/73b18143b223d354ba690043ec06d7c5.jpg';
  const inputClassName = 'h-11 bg-white border-slate-300 text-slate-900 placeholder:text-slate-400 focus-visible:ring-slate-300 focus-visible:ring-offset-white';

  return (
    <div className="min-h-screen bg-[#f2f4f8] p-4 md:p-8 flex items-center justify-center">
      <div className="w-full max-w-6xl bg-white border border-slate-200 rounded-[2rem] shadow-sm overflow-hidden grid lg:grid-cols-2">
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

          <h1 className="text-3xl md:text-4xl font-semibold text-slate-900">Welcome to Medaid.</h1>
          <p className="text-slate-500 mt-2 mb-6">Let's help you get started with better care.</p>
          <p className="text-sm text-slate-500 mb-6">
            Already have an account?{' '}
            <Link to="/login" className="text-slate-900 font-medium underline">Log in</Link>
          </p>

          {error && (
            <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-3 text-red-600 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4" autoComplete="off">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">First Name</label>
                <Input type="text" name="first_name" value={formData.first_name} onChange={handleInputChange} placeholder="Enter first name" className={inputClassName} autoComplete="off" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Last Name</label>
                <Input type="text" name="last_name" value={formData.last_name} onChange={handleInputChange} placeholder="Enter last name" className={inputClassName} autoComplete="off" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Phone</label>
                <Input type="tel" name="phone" value={formData.phone} onChange={handleInputChange} placeholder="Enter phone number" className={inputClassName} autoComplete="off" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Email</label>
                <Input type="email" name="email" value={formData.email} onChange={handleInputChange} placeholder="Enter email" className={inputClassName} autoComplete="off" />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="relative">
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Password</label>
                <Input
                  type={showPassword ? 'text' : 'password'}
                  name="password"
                  value={formData.password}
                  onChange={handleInputChange}
                  placeholder="Enter password"
                  className={`${inputClassName} pr-10`}
                  autoComplete="new-password"
                />
                <button type="button" onClick={() => setShowPassword(!showPassword)} className="absolute right-3 top-9 text-slate-400">
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Confirm Password</label>
                <Input
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

            <label className="flex items-center gap-2 text-sm text-slate-600">
              <input type="checkbox" className="rounded border-slate-300" />
              I want to receive Medaid updates and product news
            </label>
            <label className="flex items-center gap-2 text-sm text-slate-600">
              <input type="checkbox" className="rounded border-slate-300" />
              I agree to the Terms & Privacy Policy
            </label>

            <Button disabled={loading} type="submit" className="w-full h-11 bg-slate-900 hover:bg-slate-800 text-white font-semibold rounded-lg">
              {loading ? 'Creating account...' : 'Sign Up'}
            </Button>
          </form>
        </div>

        <motion.div
          initial={{ x: 120 }}
          animate={{ x: 0 }}
          transition={{ type: 'spring', stiffness: 170, damping: 24 }}
          className="relative min-h-[420px] lg:min-h-full"
        >
          <img src={authImage} alt="Medaid signup visual" className="absolute inset-0 w-full h-full object-cover" />
          <div className="absolute inset-0 bg-gradient-to-t from-slate-900/55 via-slate-900/25 to-transparent" />
          <div className="absolute inset-x-0 bottom-0 p-8 md:p-10 text-white">
            <p className="text-sm font-medium text-white/90 mb-3">Create your Medaid account</p>
            <h2 className="text-3xl font-semibold leading-tight max-w-md">Get access to triage clarity and smarter healthcare decisions.</h2>
            <p className="text-sm text-white/80 mt-3">For patients, clinicians, and care teams.</p>
          </div>
        </motion.div>
      </div>
    </div>
  );
};

export default SignupPage;
