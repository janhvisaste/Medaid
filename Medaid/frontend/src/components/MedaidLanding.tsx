import React from 'react';
import { motion } from 'framer-motion';
import { Link, useNavigate } from 'react-router-dom';

import { 
  Heart, 
  Users,
  CheckCircle,
  TrendingUp,
  BarChart3,
  MessageSquare,
  ArrowRight,
  Play,
  Brain
} from 'lucide-react';

const MedaidLanding: React.FC = () => {
  const navigate = useNavigate();

  const handleGetStarted = () => {
    navigate('/dashboard');
  };

  return (
    <div className="min-h-screen bg-gray-950 text-white relative overflow-hidden">
      {/* Sophisticated dark gradient background */}
      <div className="absolute inset-0 bg-gradient-to-br from-slate-950 via-gray-950 to-black"></div>
      <div className="absolute inset-0 bg-gradient-to-t from-blue-950/20 via-transparent to-slate-950/30"></div>
      
      {/* Advanced grid pattern with electric blue glow */}
      <div className="absolute inset-0 opacity-20" style={{
        backgroundImage: `
          linear-gradient(rgba(59, 130, 246, 0.15) 1px, transparent 1px), 
          linear-gradient(90deg, rgba(59, 130, 246, 0.15) 1px, transparent 1px),
          radial-gradient(circle at 25% 25%, rgba(59, 130, 246, 0.1) 0%, transparent 50%),
          radial-gradient(circle at 75% 75%, rgba(34, 211, 238, 0.08) 0%, transparent 50%)
        `,
        backgroundSize: '60px 60px, 60px 60px, 800px 800px, 600px 600px'
      }}></div>
      
      {/* Ambient lighting effects */}
      <div className="absolute top-0 left-1/4 w-96 h-96 bg-blue-600/10 rounded-full blur-3xl"></div>
      <div className="absolute bottom-0 right-1/4 w-80 h-80 bg-cyan-500/8 rounded-full blur-3xl"></div>

      {/* Navigation */}
      <nav className="relative z-10 flex items-center justify-between px-8 py-6 max-w-7xl mx-auto border-b border-slate-800/50 backdrop-blur-xl">
        <motion.div 
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.6 }}
          className="flex items-center space-x-3"
        >
            {/* Enhanced logo with electric glow */}
          <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-cyan-400 rounded-lg flex items-center justify-center shadow-lg shadow-blue-500/60 border border-blue-400/30 relative">
            <div className="absolute inset-0 bg-gradient-to-br from-blue-500/20 to-cyan-400/20 rounded-lg blur-sm"></div>
            <span className="text-xl font-bold text-white relative z-10 drop-shadow-[0_0_8px_rgba(255,255,255,0.8)]">M</span>
          </div>
          <span className="text-2xl font-bold text-white drop-shadow-[0_0_20px_rgba(59,130,246,0.3)]">Medaid</span>
        </motion.div>

        <motion.div 
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="hidden md:flex space-x-12 text-sm font-medium"
        >
          <Link to="/features" className="text-gray-300 hover:text-blue-400 transition-all duration-300 hover:drop-shadow-[0_0_8px_rgba(59,130,246,0.6)] relative">Features</Link>
          <a href="#pricing" className="text-gray-300 hover:text-blue-400 transition-all duration-300 hover:drop-shadow-[0_0_8px_rgba(59,130,246,0.6)] relative">Pricing</a>
          <a href="#resources" className="text-gray-300 hover:text-blue-400 transition-all duration-300 hover:drop-shadow-[0_0_8px_rgba(59,130,246,0.6)] relative">Resources</a>
          <a href="#about" className="text-gray-300 hover:text-blue-400 transition-all duration-300 hover:drop-shadow-[0_0_8px_rgba(59,130,246,0.6)] relative">About</a>
        </motion.div>

        <motion.button
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.6, delay: 0.4 }}
          onClick={handleGetStarted}
          className="bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-500 hover:to-blue-600 px-6 py-2.5 rounded-lg transition-all duration-300 text-sm font-semibold shadow-lg shadow-blue-600/60 hover:shadow-blue-500/80 border border-blue-500/30 hover:border-blue-400/50 relative group"
        >
          <div className="absolute inset-0 bg-gradient-to-r from-blue-500/20 to-blue-400/20 rounded-lg blur-sm group-hover:blur-md transition-all duration-300"></div>
          <span className="relative z-10 drop-shadow-[0_0_4px_rgba(255,255,255,0.3)]">Get started</span>
        </motion.button>
      </nav>

      {/* Hero Section */}
      <div className="relative z-10 max-w-7xl mx-auto px-8 py-20 pb-28">
        {/* Multiple layered glowing effects */}
        <div className="absolute top-16 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-blue-600/15 rounded-full blur-3xl"></div>
        <div className="absolute top-24 left-1/2 -translate-x-1/2 w-96 h-96 bg-cyan-500/10 rounded-full blur-2xl"></div>
        <div className="absolute top-32 left-1/2 -translate-x-1/2 w-64 h-64 bg-blue-400/20 rounded-full blur-xl"></div>
        
        <div className="text-center mb-20 relative">
          <motion.h1
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.3 }}
            className="text-5xl md:text-6xl lg:text-8xl font-bold mb-8 leading-tight tracking-tight"
          >
            <span className="text-white drop-shadow-[0_0_20px_rgba(255,255,255,0.1)]">Your AI assistant for</span><br />
            <span className="bg-gradient-to-r from-cyan-300 via-blue-400 to-blue-500 text-transparent bg-clip-text relative">
              <span className="absolute inset-0 bg-gradient-to-r from-cyan-400 via-blue-400 to-blue-500 text-transparent bg-clip-text blur-sm">smarter healthcare.</span>
              <span className="relative drop-shadow-[0_0_40px_rgba(59,130,246,0.8)]">smarter healthcare.</span>
            </span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.5 }}
            className="text-xl md:text-2xl text-gray-300 mb-16 max-w-4xl mx-auto leading-relaxed font-light"
          >
            Harness the power of AI to streamline medical workflows, enhance patient
            care, and boost your healthcare team's efficiency — all in one intelligent
            platform.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.7 }}
            className="flex flex-col sm:flex-row items-center justify-center gap-6"
          >
            <button onClick={handleGetStarted} className="bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 px-10 py-5 rounded-xl text-lg font-semibold transition-all transform hover:scale-105 flex items-center gap-3 shadow-xl shadow-blue-600/60 hover:shadow-blue-500/80 border border-blue-400/30 hover:border-blue-300/50 relative group">
              <div className="absolute inset-0 bg-gradient-to-r from-blue-500/30 to-cyan-500/30 rounded-xl blur-lg group-hover:blur-xl transition-all duration-300"></div>
              <span className="relative z-10 drop-shadow-[0_0_8px_rgba(255,255,255,0.4)]">Get started</span>
              <ArrowRight className="w-5 h-5 relative z-10 drop-shadow-[0_0_8px_rgba(255,255,255,0.4)]" />
            </button>
            <button className="flex items-center gap-3 px-10 py-5 rounded-xl text-lg font-semibold bg-slate-900/60 border border-slate-700/80 hover:bg-slate-800/60 hover:border-blue-500/50 transition-all backdrop-blur-sm relative group">
              <div className="absolute inset-0 bg-gradient-to-r from-slate-800/20 to-slate-700/20 rounded-xl blur-sm group-hover:blur-md transition-all duration-300"></div>
              <Play className="w-5 h-5 text-blue-400 relative z-10 drop-shadow-[0_0_8px_rgba(59,130,246,0.6)]" />
              <span className="relative z-10 text-gray-200">See it in Action</span>
            </button>
          </motion.div>
        </div>

        {/* Feature Cards Grid - Enhanced with Electric Glow */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 mt-24">
          {/* Smart Diagnostics Card */}
          <motion.div
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.9 }}
            className="bg-slate-900/60 backdrop-blur-xl border border-slate-700/80 rounded-3xl p-8 hover:border-blue-400/60 transition-all duration-500 hover:shadow-2xl hover:shadow-blue-500/30 group relative overflow-hidden"
          >
            {/* Subtle inner glow */}
            <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-cyan-500/5 rounded-3xl opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
            <div className="flex items-start justify-between mb-6 relative z-10">
              <h3 className="text-2xl font-bold text-white drop-shadow-[0_0_10px_rgba(255,255,255,0.1)]">Smart Diagnostics</h3>
              <Brain className="w-7 h-7 text-blue-400 group-hover:drop-shadow-[0_0_15px_rgba(59,130,246,0.9)] transition-all duration-500 group-hover:text-blue-300" />
            </div>
            <p className="text-base text-gray-300 mb-6 relative z-10 leading-relaxed">
              AI-powered diagnostic assistance and patient record analysis.
            </p>
            <div className="space-y-3 text-sm relative z-10">
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-blue-400 shadow-[0_0_8px_rgba(59,130,246,0.9)] group-hover:shadow-[0_0_12px_rgba(59,130,246,1)] transition-all duration-300"></div>
                <span className="text-gray-200 font-medium">AI symptom analysis</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-blue-400 shadow-[0_0_8px_rgba(59,130,246,0.9)] group-hover:shadow-[0_0_12px_rgba(59,130,246,1)] transition-all duration-300"></div>
                <span className="text-gray-200 font-medium">Medical history insights</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-blue-400 shadow-[0_0_8px_rgba(59,130,246,0.9)] group-hover:shadow-[0_0_12px_rgba(59,130,246,1)] transition-all duration-300"></div>
                <span className="text-gray-200 font-medium">Treatment recommendations</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-blue-400 shadow-[0_0_8px_rgba(59,130,246,0.9)] group-hover:shadow-[0_0_12px_rgba(59,130,246,1)] transition-all duration-300"></div>
                <span className="text-gray-200 font-medium">Risk assessment</span>
              </div>
            </div>
          </motion.div>

          {/* Patient Care Card */}
          <motion.div
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 1.0 }}
            className="bg-slate-900/60 backdrop-blur-xl border border-slate-700/80 rounded-3xl p-8 hover:border-cyan-400/60 transition-all duration-500 hover:shadow-2xl hover:shadow-cyan-500/30 group relative overflow-hidden"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/5 to-blue-500/5 rounded-3xl opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
            <div className="flex items-start justify-between mb-6 relative z-10">
              <h3 className="text-2xl font-bold text-white drop-shadow-[0_0_10px_rgba(255,255,255,0.1)]">Patient Care</h3>
              <Heart className="w-7 h-7 text-cyan-400 group-hover:drop-shadow-[0_0_15px_rgba(34,211,238,0.9)] transition-all duration-500 group-hover:text-cyan-300" />
            </div>
            <p className="text-base text-gray-300 mb-6 relative z-10 leading-relaxed">
              Comprehensive patient management and care coordination.
            </p>
            <div className="space-y-3 text-sm relative z-10">
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.9)] group-hover:shadow-[0_0_12px_rgba(34,211,238,1)] transition-all duration-300"></div>
                <span className="text-gray-200 font-medium">Patient monitoring</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.9)] group-hover:shadow-[0_0_12px_rgba(34,211,238,1)] transition-all duration-300"></div>
                <span className="text-gray-200 font-medium">Care plan management</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.9)] group-hover:shadow-[0_0_12px_rgba(34,211,238,1)] transition-all duration-300"></div>
                <span className="text-gray-200 font-medium">Medication tracking</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-cyan-400 shadow-[0_0_8px_rgba(34,211,238,0.9)] group-hover:shadow-[0_0_12px_rgba(34,211,238,1)] transition-all duration-300"></div>
                <span className="text-gray-200 font-medium">Appointment scheduling</span>
              </div>
            </div>
          </motion.div>

          {/* Health Analytics Card */}
          <motion.div
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 1.1 }}
            className="bg-slate-900/60 backdrop-blur-xl border border-slate-700/80 rounded-3xl p-8 hover:border-blue-400/60 transition-all duration-500 hover:shadow-2xl hover:shadow-blue-500/30 group relative overflow-hidden"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 to-purple-500/5 rounded-3xl opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
            <div className="flex items-start justify-between mb-6 relative z-10">
              <h3 className="text-2xl font-bold text-white drop-shadow-[0_0_10px_rgba(255,255,255,0.1)]">Health Analytics</h3>
              <BarChart3 className="w-7 h-7 text-blue-400 group-hover:drop-shadow-[0_0_15px_rgba(59,130,246,0.9)] transition-all duration-500 group-hover:text-blue-300" />
            </div>
            <p className="text-base text-gray-300 mb-6 relative z-10 leading-relaxed">
              Advanced analytics and reporting for better healthcare outcomes.
            </p>
            <div className="space-y-3 text-sm relative z-10">
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-blue-400 shadow-[0_0_8px_rgba(59,130,246,0.9)] group-hover:shadow-[0_0_12px_rgba(59,130,246,1)] transition-all duration-300"></div>
                <span className="text-gray-200 font-medium">Performance metrics</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-blue-400 shadow-[0_0_8px_rgba(59,130,246,0.9)] group-hover:shadow-[0_0_12px_rgba(59,130,246,1)] transition-all duration-300"></div>
                <span className="text-gray-200 font-medium">Outcome tracking</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-blue-400 shadow-[0_0_8px_rgba(59,130,246,0.9)] group-hover:shadow-[0_0_12px_rgba(59,130,246,1)] transition-all duration-300"></div>
                <span className="text-gray-200 font-medium">Predictive analytics</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 rounded-full bg-blue-400 shadow-[0_0_8px_rgba(59,130,246,0.9)] group-hover:shadow-[0_0_12px_rgba(59,130,246,1)] transition-all duration-300"></div>
                <span className="text-gray-200 font-medium">Custom reports</span>
              </div>
            </div>
          </motion.div>
        </div>
      </div>

        {/* Features Section with Advanced Central Diagram */}
      <div className="relative py-24 mt-16 border-t border-slate-800/50 bg-gradient-to-b from-slate-950/50 to-gray-950">
        <div className="max-w-7xl mx-auto px-8">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            viewport={{ once: true }}
            className="text-center mb-20"
          >
            <h2 className="text-5xl md:text-6xl font-bold mb-6 text-white tracking-tight">
              Revolutionize Your <span className="bg-gradient-to-r from-cyan-300 via-blue-400 to-blue-500 text-transparent bg-clip-text drop-shadow-[0_0_30px_rgba(59,130,246,0.6)]">Healthcare Practice</span>
            </h2>
            <p className="text-xl text-gray-300 max-w-4xl mx-auto leading-relaxed">
              Streamline operations, enhance patient outcomes, and embrace the future of medicine with
              AI-driven insights and intelligent automation.
            </p>
          </motion.div>

{/* Central Image Section */}
<div className="relative w-full flex items-center justify-center pt-4 pb-20 md:pb-28">
  <motion.img
    src="/images/centralImage.png"
    alt="MedAid AI Healthcare Platform"
    initial={{ opacity: 0, scale: 0.9 }}
    animate={{ opacity: 1, scale: 1 }}
    transition={{ duration: 1 }}
    className="w-[150vw] max-w-[1200px] object-contain"
  />
</div>

          {/* Enhanced Medical Insights Dashboard */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            viewport={{ once: true }}
            className="bg-slate-900/60 backdrop-blur-xl border border-slate-700/80 rounded-3xl p-10 mb-16 shadow-2xl shadow-blue-500/20 relative overflow-hidden"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 via-cyan-500/5 to-purple-500/5 rounded-3xl"></div>
            <h3 className="text-3xl font-bold mb-8 flex items-center gap-4 text-white relative z-10">
              <BarChart3 className="w-8 h-8 text-cyan-400 drop-shadow-[0_0_15px_rgba(34,211,238,0.8)]" />
              <span className="drop-shadow-[0_0_10px_rgba(255,255,255,0.1)]">Medical Insights Dashboard</span>
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-8 relative z-10">
              <div className="text-center bg-slate-800/30 rounded-2xl p-6 border border-slate-700/50">
                <div className="text-5xl font-bold text-blue-400 mb-3 drop-shadow-[0_0_15px_rgba(59,130,246,0.8)]">98%</div>
                <div className="text-sm text-gray-300 mb-2 font-medium">Diagnostic Accuracy</div>
                <CheckCircle className="w-6 h-6 text-blue-400 mx-auto drop-shadow-[0_0_10px_rgba(59,130,246,0.8)]" />
              </div>
              <div className="text-center bg-slate-800/30 rounded-2xl p-6 border border-slate-700/50">
                <div className="text-5xl font-bold text-green-400 mb-3 drop-shadow-[0_0_15px_rgba(34,197,94,0.8)]">45%</div>
                <div className="text-sm text-gray-300 mb-2 font-medium">Faster Treatment</div>
                <TrendingUp className="w-6 h-6 text-green-400 mx-auto drop-shadow-[0_0_10px_rgba(34,197,94,0.8)]" />
              </div>
              <div className="text-center bg-slate-800/30 rounded-2xl p-6 border border-slate-700/50">
                <div className="text-5xl font-bold text-cyan-400 mb-3 drop-shadow-[0_0_15px_rgba(34,211,238,0.8)]">10k+</div>
                <div className="text-sm text-gray-300 mb-2 font-medium">Patients Served</div>
                <Users className="w-6 h-6 text-cyan-400 mx-auto drop-shadow-[0_0_10px_rgba(34,211,238,0.8)]" />
              </div>
              <div className="text-center bg-slate-800/30 rounded-2xl p-6 border border-slate-700/50">
                <div className="text-5xl font-bold text-purple-400 mb-3 drop-shadow-[0_0_15px_rgba(168,85,247,0.8)]">24/7</div>
                <div className="text-sm text-gray-300 mb-2 font-medium">AI Support</div>
                <MessageSquare className="w-6 h-6 text-purple-400 mx-auto drop-shadow-[0_0_10px_rgba(168,85,247,0.8)]" />
              </div>
            </div>
          </motion.div>
        </div>
      </div>

      {/* Enhanced CTA Section */}
      <div className="relative py-24 bg-gradient-to-b from-gray-950 to-black border-t border-slate-800/50">
        <div className="absolute inset-0 bg-gradient-to-r from-blue-950/20 via-transparent to-cyan-950/20"></div>
        <div className="max-w-5xl mx-auto px-8 text-center relative z-10">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            viewport={{ once: true }}
          >
            <h2 className="text-5xl md:text-6xl font-bold mb-8 text-white tracking-tight">
              Ready to Transform 
              <span className="bg-gradient-to-r from-cyan-300 via-blue-400 to-blue-500 text-transparent bg-clip-text drop-shadow-[0_0_30px_rgba(59,130,246,0.6)]"> Healthcare?</span>
            </h2>
            <p className="text-xl text-gray-300 mb-12 max-w-3xl mx-auto leading-relaxed">
              Join thousands of healthcare professionals already using Medaid to deliver
              better patient care with the power of artificial intelligence.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-6">
              <button className="bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-400 hover:to-blue-400 text-white px-10 py-5 rounded-xl text-lg font-semibold transition-all transform hover:scale-105 flex items-center gap-3 shadow-xl shadow-blue-500/60 border border-blue-400/30 relative group">
                <div className="absolute inset-0 bg-gradient-to-r from-cyan-400/20 to-blue-400/20 rounded-xl blur-lg group-hover:blur-xl transition-all duration-300"></div>
                <span className="relative z-10 drop-shadow-[0_0_8px_rgba(255,255,255,0.4)]">Start Free Trial</span>
                <ArrowRight className="w-5 h-5 relative z-10 drop-shadow-[0_0_8px_rgba(255,255,255,0.4)]" />
              </button>
              <button className="bg-slate-900/60 hover:bg-slate-800/60 border border-slate-700 hover:border-blue-500/50 px-10 py-5 rounded-xl text-lg font-semibold transition-all backdrop-blur-sm relative group">
                <div className="absolute inset-0 bg-gradient-to-r from-slate-800/20 to-slate-700/20 rounded-xl blur-sm group-hover:blur-md transition-all duration-300"></div>
                <span className="relative z-10 text-gray-200">Schedule Demo</span>
              </button>
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
};

export default MedaidLanding;
