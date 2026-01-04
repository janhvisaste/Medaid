import React from 'react';
import { motion } from 'framer-motion';
import { 
  Brain, 
  Activity, 
  BarChart3,
  Users,
  Heart,
  Zap,
  TrendingUp,
  Shield,
  Clock,
  FileText,
  AlertTriangle,
  Target,
  ArrowLeft
} from 'lucide-react';

const FeaturesPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-950 text-white relative overflow-hidden">
      {/* Enhanced dark gradient background */}
      <div className="absolute inset-0 bg-gradient-to-br from-slate-950 via-gray-950 to-black"></div>
      <div className="absolute inset-0 bg-gradient-to-t from-purple-950/20 via-transparent to-slate-950/30"></div>
      
      {/* Advanced grid pattern with purple glow */}
      <div className="absolute inset-0 opacity-20" style={{
        backgroundImage: `
          linear-gradient(rgba(147, 51, 234, 0.15) 1px, transparent 1px), 
          linear-gradient(90deg, rgba(147, 51, 234, 0.15) 1px, transparent 1px),
          radial-gradient(circle at 25% 25%, rgba(147, 51, 234, 0.1) 0%, transparent 50%),
          radial-gradient(circle at 75% 75%, rgba(168, 85, 247, 0.08) 0%, transparent 50%)
        `,
        backgroundSize: '60px 60px, 60px 60px, 800px 800px, 600px 600px'
      }}></div>

      {/* Navigation */}
      <nav className="relative z-10 flex items-center justify-between px-8 py-6 max-w-7xl mx-auto border-b border-slate-800/50 backdrop-blur-xl">
        <motion.div 
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.6 }}
          className="flex items-center space-x-3"
        >
          <button 
            onClick={() => window.history.back()}
            className="flex items-center gap-2 text-gray-300 hover:text-purple-400 transition-colors mr-6"
          >
            <ArrowLeft className="w-5 h-5" />
            <span>Back</span>
          </button>
          <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-pink-400 rounded-lg flex items-center justify-center shadow-lg shadow-purple-500/60 border border-purple-400/30 relative">
            <div className="absolute inset-0 bg-gradient-to-br from-purple-500/20 to-pink-400/20 rounded-lg blur-sm"></div>
            <span className="text-xl font-bold text-white relative z-10 drop-shadow-[0_0_8px_rgba(255,255,255,0.8)]">M</span>
          </div>
          <span className="text-2xl font-bold text-white drop-shadow-[0_0_20px_rgba(147,51,234,0.3)]">Medaid</span>
        </motion.div>
      </nav>

      {/* Header Section */}
      <div className="relative z-10 max-w-7xl mx-auto px-8 py-16">
        <div className="text-center mb-16">
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="w-16 h-16 bg-gradient-to-br from-purple-600 to-pink-500 rounded-2xl flex items-center justify-center mx-auto mb-8 shadow-xl shadow-purple-500/50"
          >
            <Brain className="w-8 h-8 text-white drop-shadow-[0_0_12px_rgba(255,255,255,0.8)]" />
          </motion.div>
          
          <motion.h1
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.4 }}
            className="text-5xl md:text-6xl font-bold mb-6 leading-tight"
          >
            Discover the Features That Simplify<br />
            <span className="bg-gradient-to-r from-purple-300 via-pink-400 to-purple-500 text-transparent bg-clip-text drop-shadow-[0_0_30px_rgba(147,51,234,0.6)]">
              and Empower Your Healthcare
            </span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.6 }}
            className="text-xl text-gray-300 mb-12 max-w-4xl mx-auto leading-relaxed"
          >
            Everything you need to manage, track, and optimize your medical practice — all in one intuitive platform
          </motion.p>
        </div>

        {/* Feature Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 mb-16">
          {/* Smart Diagnostics */}
          <motion.div
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.8 }}
            className="bg-slate-900/60 backdrop-blur-xl border border-slate-700/80 rounded-3xl p-8 hover:border-purple-400/60 transition-all duration-500 hover:shadow-xl hover:shadow-purple-500/30 group relative overflow-hidden"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-purple-500/5 to-pink-500/5 rounded-3xl opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
            
            <div className="h-48 bg-gradient-to-br from-purple-600/20 to-pink-600/20 rounded-2xl mb-6 relative overflow-hidden flex items-center justify-center">
              <div className="absolute inset-0 bg-gradient-to-br from-purple-500/10 to-pink-500/10 rounded-2xl"></div>
              <Brain className="w-16 h-16 text-purple-400 relative z-10 drop-shadow-[0_0_20px_rgba(147,51,234,0.8)]" />
              {/* Diagnostic trend visualization */}
              <div className="absolute bottom-4 left-4 right-4">
                <div className="text-xs text-purple-400 mb-1 font-semibold">AI Diagnosis Accuracy</div>
                <div className="flex gap-1 h-8 items-end">
                  {[60, 75, 85, 90, 95, 98].map((height, i) => (
                    <motion.div
                      key={i}
                      className="flex-1 bg-gradient-to-t from-purple-600 to-pink-500 rounded-t opacity-70"
                      style={{ height: `${height}%` }}
                      initial={{ height: 0 }}
                      animate={{ height: `${height}%` }}
                      transition={{ duration: 1, delay: i * 0.1 + 1 }}
                    ></motion.div>
                  ))}
                </div>
              </div>
            </div>

            <div className="relative z-10">
              <h3 className="text-2xl font-bold text-white mb-4 drop-shadow-[0_0_10px_rgba(255,255,255,0.1)]">Smart Diagnostics</h3>
              <p className="text-gray-300 mb-4">
                AI-powered diagnostic assistance and comprehensive patient analysis with real-time insights.
              </p>
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm">
                  <div className="w-2 h-2 bg-purple-400 rounded-full shadow-[0_0_6px_rgba(147,51,234,0.8)]"></div>
                  <span className="text-gray-200">Symptom pattern recognition</span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <div className="w-2 h-2 bg-purple-400 rounded-full shadow-[0_0_6px_rgba(147,51,234,0.8)]"></div>
                  <span className="text-gray-200">Medical history correlation</span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <div className="w-2 h-2 bg-purple-400 rounded-full shadow-[0_0_6px_rgba(147,51,234,0.8)]"></div>
                  <span className="text-gray-200">Treatment recommendations</span>
                </div>
              </div>
            </div>
          </motion.div>

          {/* AI Automation */}
          <motion.div
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 1.0 }}
            className="bg-slate-900/60 backdrop-blur-xl border border-slate-700/80 rounded-3xl p-8 hover:border-purple-400/60 transition-all duration-500 hover:shadow-xl hover:shadow-purple-500/30 group relative overflow-hidden"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-purple-500/5 to-pink-500/5 rounded-3xl opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
            
            <div className="h-48 bg-gradient-to-br from-purple-600/20 to-pink-600/20 rounded-2xl mb-6 relative overflow-hidden flex flex-col justify-center p-4">
              <Zap className="w-12 h-12 text-purple-400 mb-4 drop-shadow-[0_0_15px_rgba(147,51,234,0.8)]" />
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-xs">
                  <Activity className="w-3 h-3 text-purple-400" />
                  <span className="text-purple-300">Workflow Automation</span>
                  <div className="ml-auto w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <FileText className="w-3 h-3 text-purple-400" />
                  <span className="text-purple-300">Document Processing</span>
                  <div className="ml-auto w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                </div>
                <div className="flex items-center gap-2 text-xs">
                  <Shield className="w-3 h-3 text-purple-400" />
                  <span className="text-purple-300">Compliance Monitoring</span>
                  <div className="ml-auto w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                </div>
              </div>
            </div>

            <div className="relative z-10">
              <h3 className="text-2xl font-bold text-white mb-4 drop-shadow-[0_0_10px_rgba(255,255,255,0.1)]">AI Automation</h3>
              <p className="text-gray-300 mb-4">
                Streamline clinical workflows with intelligent automation and reduce manual administrative tasks.
              </p>
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm">
                  <div className="w-2 h-2 bg-purple-400 rounded-full shadow-[0_0_6px_rgba(147,51,234,0.8)]"></div>
                  <span className="text-gray-200">Automated scheduling</span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <div className="w-2 h-2 bg-purple-400 rounded-full shadow-[0_0_6px_rgba(147,51,234,0.8)]"></div>
                  <span className="text-gray-200">Document generation</span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <div className="w-2 h-2 bg-purple-400 rounded-full shadow-[0_0_6px_rgba(147,51,234,0.8)]"></div>
                  <span className="text-gray-200">Billing automation</span>
                </div>
              </div>
            </div>
          </motion.div>

          {/* Real-time Analytics */}
          <motion.div
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 1.2 }}
            className="bg-slate-900/60 backdrop-blur-xl border border-slate-700/80 rounded-3xl p-8 hover:border-purple-400/60 transition-all duration-500 hover:shadow-xl hover:shadow-purple-500/30 group relative overflow-hidden"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-purple-500/5 to-pink-500/5 rounded-3xl opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
            
            <div className="h-48 bg-gradient-to-br from-purple-600/20 to-pink-600/20 rounded-2xl mb-6 relative overflow-hidden p-4">
              <div className="flex items-center justify-between mb-2">
                <BarChart3 className="w-8 h-8 text-purple-400 drop-shadow-[0_0_12px_rgba(147,51,234,0.8)]" />
                <div className="text-xs text-purple-400 font-semibold">↗ Live Metrics</div>
              </div>
              <div className="flex gap-1 h-24 items-end mb-2">
                {[45, 70, 60, 82, 78, 92, 88, 95].map((height, i) => (
                  <motion.div
                    key={i}
                    className="flex-1 bg-gradient-to-t from-purple-600 via-purple-500 to-pink-500 rounded-t shadow-[0_0_6px_rgba(147,51,234,0.4)]"
                    style={{ height: `${height}%` }}
                    initial={{ height: 0 }}
                    animate={{ height: `${height}%` }}
                    transition={{ duration: 1, delay: i * 0.1 + 1.5 }}
                  ></motion.div>
                ))}
              </div>
              <div className="flex justify-between text-xs text-purple-300">
                <span>Patients</span>
                <span>Efficiency</span>
              </div>
            </div>

            <div className="relative z-10">
              <h3 className="text-2xl font-bold text-white mb-4 drop-shadow-[0_0_10px_rgba(255,255,255,0.1)]">Real-time Analytics</h3>
              <p className="text-gray-300 mb-4">
                Monitor practice performance and patient outcomes with comprehensive real-time dashboards.
              </p>
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm">
                  <div className="w-2 h-2 bg-purple-400 rounded-full shadow-[0_0_6px_rgba(147,51,234,0.8)]"></div>
                  <span className="text-gray-200">Performance metrics</span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <div className="w-2 h-2 bg-purple-400 rounded-full shadow-[0_0_6px_rgba(147,51,234,0.8)]"></div>
                  <span className="text-gray-200">Patient flow tracking</span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <div className="w-2 h-2 bg-purple-400 rounded-full shadow-[0_0_6px_rgba(147,51,234,0.8)]"></div>
                  <span className="text-gray-200">Revenue insights</span>
                </div>
              </div>
            </div>
          </motion.div>
        </div>

        {/* Bottom Row - Larger Cards */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Patient Management */}
          <motion.div
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 1.4 }}
            className="bg-slate-900/60 backdrop-blur-xl border border-slate-700/80 rounded-3xl p-8 hover:border-purple-400/60 transition-all duration-500 hover:shadow-xl hover:shadow-purple-500/30 group relative overflow-hidden"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-purple-500/5 to-pink-500/5 rounded-3xl opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
            
            <div className="flex items-start gap-6">
              <div className="flex-shrink-0">
                <div className="w-16 h-16 bg-gradient-to-br from-purple-600/30 to-pink-600/30 rounded-2xl flex items-center justify-center mb-4">
                  <Users className="w-8 h-8 text-purple-400 drop-shadow-[0_0_12px_rgba(147,51,234,0.8)]" />
                </div>
              </div>
              
              <div className="flex-1">
                <h3 className="text-2xl font-bold text-white mb-4 drop-shadow-[0_0_10px_rgba(255,255,255,0.1)]">Patient Management</h3>
                <p className="text-gray-300 mb-6">
                  Comprehensive patient record management with integrated communication and care coordination tools.
                </p>
                
                <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50 mb-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-gray-300">Monthly Appointments</span>
                    <span className="text-lg font-bold text-purple-400">1,247</span>
                  </div>
                  <div className="w-full bg-slate-700 rounded-full h-2">
                    <motion.div 
                      className="bg-gradient-to-r from-purple-500 to-pink-500 h-2 rounded-full"
                      initial={{ width: 0 }}
                      animate={{ width: "78%" }}
                      transition={{ duration: 1.5, delay: 2 }}
                    ></motion.div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-purple-400 drop-shadow-[0_0_10px_rgba(147,51,234,0.6)]">98%</div>
                    <div className="text-xs text-gray-400">Patient Satisfaction</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-purple-400 drop-shadow-[0_0_10px_rgba(147,51,234,0.6)]">24/7</div>
                    <div className="text-xs text-gray-400">Support Available</div>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>

          {/* Clinical Insights */}
          <motion.div
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 1.6 }}
            className="bg-slate-900/60 backdrop-blur-xl border border-slate-700/80 rounded-3xl p-8 hover:border-purple-400/60 transition-all duration-500 hover:shadow-xl hover:shadow-purple-500/30 group relative overflow-hidden"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-purple-500/5 to-pink-500/5 rounded-3xl opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
            
            <div className="flex items-start gap-6">
              <div className="flex-shrink-0">
                <div className="w-16 h-16 bg-gradient-to-br from-purple-600/30 to-pink-600/30 rounded-2xl flex items-center justify-center mb-4">
                  <Target className="w-8 h-8 text-purple-400 drop-shadow-[0_0_12px_rgba(147,51,234,0.8)]" />
                </div>
              </div>
              
              <div className="flex-1">
                <h3 className="text-2xl font-bold text-white mb-4 drop-shadow-[0_0_10px_rgba(255,255,255,0.1)]">Clinical Insights</h3>
                <p className="text-gray-300 mb-6">
                  Advanced predictive analytics and clinical decision support powered by machine learning algorithms.
                </p>

                <div className="space-y-3">
                  <div className="bg-slate-800/40 rounded-lg p-3 border border-slate-700/40">
                    <div className="flex items-center gap-2 mb-1">
                      <AlertTriangle className="w-4 h-4 text-yellow-400" />
                      <span className="text-purple-400 font-semibold text-sm">Risk Alert</span>
                    </div>
                    <div className="text-gray-200 text-xs">High blood pressure pattern detected in 3 patients</div>
                  </div>
                  
                  <div className="bg-slate-800/40 rounded-lg p-3 border border-slate-700/40">
                    <div className="flex items-center gap-2 mb-1">
                      <TrendingUp className="w-4 h-4 text-green-400" />
                      <span className="text-purple-400 font-semibold text-sm">Trend Analysis</span>
                    </div>
                    <div className="text-gray-200 text-xs">Treatment success rate improved by 15% this month</div>
                  </div>
                </div>
                
                <div className="mt-4 flex items-center gap-4">
                  <div className="flex items-center gap-2 text-sm">
                    <Heart className="w-4 h-4 text-purple-400" />
                    <span className="text-gray-200">Predictive modeling</span>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <Clock className="w-4 h-4 text-purple-400" />
                    <span className="text-gray-200">Real-time alerts</span>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
};

export default FeaturesPage;