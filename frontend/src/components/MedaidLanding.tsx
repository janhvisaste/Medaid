import React, { useRef, useState, useEffect } from 'react';
import { motion, useScroll, useTransform, useSpring } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import {
  Activity,
  ArrowRight,
  Brain,
  ChevronDown,
  FileText,
  HeartPulse,
  Menu,
  Shield,
  Sparkles,
  Stethoscope,
  Syringe,
  Users,
  X,
} from 'lucide-react';
type IconType = React.ElementType;

const MedaidLanding: React.FC = () => {
  const navigate = useNavigate();
  const [activeSection, setActiveSection] = useState('home');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const homeRef = useRef<HTMLDivElement>(null);
  const featuresRef = useRef<HTMLDivElement>(null);
  const aboutRef = useRef<HTMLDivElement>(null);

  // Scroll progress
  const { scrollYProgress } = useScroll({ target: containerRef, offset: ["start start", "end end"] });
  const smoothProgress = useSpring(scrollYProgress, { stiffness: 80, damping: 25 });
  const navBg = useTransform(smoothProgress, [0, 0.05], [0, 1]);

  // Track active section
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id);
          }
        });
      },
      { threshold: 0.35 }
    );
    [homeRef, featuresRef, aboutRef].forEach(ref => {
      if (ref.current) observer.observe(ref.current);
    });
    return () => observer.disconnect();
  }, []);

  const scrollTo = (id: string) => {
    setMobileMenuOpen(false);
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
  };

  const navLinks = [
    { id: 'home', label: 'Home' },
    { id: 'features', label: 'Features' },
    { id: 'about', label: 'About' },
  ];

  const offerings: { icon: IconType; title: string; description: string }[] = [
    { icon: Stethoscope, title: 'Clinical Triage', description: 'AI-assisted symptom intake and urgency scoring to help patients reach care faster.' },
    { icon: FileText, title: 'Medical Report Analysis', description: 'Upload reports and get structured findings, risks, and simplified explanations.' },
    { icon: Brain, title: 'Care Intelligence', description: 'Actionable insights for clinicians and patients based on history and current condition.' },
    { icon: Syringe, title: 'Preventive Guidance', description: 'Personalized health reminders and wellness recommendations for better outcomes.' },
  ];

  const achievements = [
    { title: 'Trusted by growing care teams', detail: 'Adopted by clinics and community health providers for streamlined triage workflows.' },
    { title: 'High patient clarity scores', detail: 'Patients understand results better through plain-language explanations.' },
    { title: 'Faster report turnaround', detail: 'Teams reduce manual review time with AI-assisted extraction and summaries.' },
  ];

  const landingImages = {
    hero: 'https://i.pinimg.com/736x/88/54/b5/8854b516add7ec7b3c25500b50ab29b1.jpg',
    featurePrimary: 'https://i.pinimg.com/736x/e8/01/96/e801962029008e9886b916a49233f753.jpg',
    featureSecondary: 'https://i.pinimg.com/736x/97/3d/53/973d536841b6319f4818bad1ea60b092.jpg',
    recognition: 'https://i.pinimg.com/736x/13/70/fe/1370fe9628ba6a145935e625eba48f83.jpg',
  };

  return (
    <div ref={containerRef} className="min-h-screen bg-[#f7f8fb] text-slate-900">
      <motion.nav
        style={{ backgroundColor: `rgba(247,248,251,${navBg})` }}
        className="fixed top-0 inset-x-0 z-50 border-b border-slate-200/70 backdrop-blur-xl"
      >
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <button onClick={() => scrollTo('home')} className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-white border border-slate-200 flex items-center justify-center shadow-sm">
              <Activity className="w-4 h-4 text-sky-600" />
            </div>
            <span className="text-lg font-bold tracking-tight">Medaid</span>
          </button>

          <div className="hidden md:flex items-center gap-1">
            {navLinks.map(link => (
              <button
                key={link.id}
                onClick={() => scrollTo(link.id)}
                className={`px-4 py-2 text-sm font-medium rounded-lg transition-all duration-300 ${
                  activeSection === link.id
                    ? 'text-slate-900 bg-white shadow-sm border border-slate-200'
                    : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                {link.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/login')}
              className="hidden md:block px-5 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors"
            >
              Sign In
            </button>
            <button
              onClick={() => navigate('/signup')}
              className="hidden md:flex px-5 py-2.5 text-sm font-semibold rounded-xl bg-slate-900 text-white hover:bg-slate-800 transition-colors items-center gap-2"
            >
              Get Started <ArrowRight className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-2 text-slate-500 hover:text-slate-900"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {/* Mobile Menu */}
        {mobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="md:hidden border-t border-slate-200 bg-white/90 backdrop-blur-xl"
          >
            <div className="px-6 py-4 space-y-1">
              {navLinks.map(link => (
                <button
                  key={link.id}
                  onClick={() => scrollTo(link.id)}
                  className={`block w-full text-left px-4 py-3 text-sm font-medium rounded-lg ${
                    activeSection === link.id ? 'text-slate-900 bg-slate-100' : 'text-slate-600'
                  }`}
                >
                  {link.label}
                </button>
              ))}
              <div className="pt-3 flex gap-3">
                <button onClick={() => navigate('/login')} className="flex-1 py-2.5 text-sm font-medium text-slate-700 border border-slate-200 rounded-lg">Sign In</button>
                <button onClick={() => navigate('/signup')} className="flex-1 py-2.5 text-sm font-semibold bg-slate-900 text-white rounded-lg">Get Started</button>
              </div>
            </div>
          </motion.div>
        )}
      </motion.nav>

      <section ref={homeRef} id="home" className="relative pt-28 pb-20 px-6 overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(14,165,233,0.12),transparent_60%)]" />
        <div className="max-w-6xl mx-auto relative z-10">
          <div className="rounded-[2rem] border border-white bg-gradient-to-r from-sky-100/80 to-indigo-100/80 p-10 md:p-14 shadow-sm relative overflow-hidden">
            <div className="absolute -top-10 -right-12 w-52 h-52 rounded-full bg-sky-300/20 blur-2xl" />
            <div className="absolute -bottom-8 -left-8 w-56 h-56 rounded-full bg-indigo-300/20 blur-2xl" />

            <div className="grid lg:grid-cols-[1.2fr_0.8fr] gap-8 items-center">
              <div>
                <div className="inline-flex items-center gap-2 rounded-full bg-white/80 border border-slate-200 px-4 py-1.5 text-xs text-slate-600 mb-6">
                  <Sparkles className="w-3.5 h-3.5 text-sky-600" />
                  AI-powered care coordination for modern clinics
                </div>

                <h1 className="text-4xl md:text-6xl font-semibold tracking-tight leading-[1.05] text-slate-900">
                  Innovative healthcare technology
                  <span className="block text-slate-600">with care for every patient.</span>
                </h1>
                <p className="mt-6 text-slate-600 text-lg max-w-xl">
                  Medaid helps patients and clinicians move faster from symptoms to clarity using triage intelligence, report analysis, and guided next steps.
                </p>

                <div className="mt-8 flex flex-col sm:flex-row gap-3">
                  <button onClick={() => navigate('/signup')} className="px-6 py-3 rounded-full bg-slate-900 text-white text-sm font-semibold hover:bg-slate-800 transition-colors inline-flex items-center justify-center gap-2">
                    Explore Medaid <ArrowRight className="w-4 h-4" />
                  </button>
                  <button onClick={() => scrollTo('features')} className="px-6 py-3 rounded-full border border-slate-300 text-slate-700 text-sm font-medium hover:bg-white transition-colors">
                    See key capabilities
                  </button>
                </div>
              </div>

              <div className="space-y-4">
                <div className="bg-white rounded-3xl border border-slate-200 p-3 shadow-sm">
                  <img
                    src={landingImages.hero}
                    alt="Medaid healthcare innovation visual"
                    className="w-full h-36 object-cover rounded-2xl"
                    loading="lazy"
                  />
                </div>
                <div className="bg-white rounded-3xl border border-slate-200 p-5 shadow-sm">
                  <div className="text-xs text-slate-500 mb-1">Today with Medaid</div>
                  <div className="text-3xl font-semibold">1.5k+</div>
                  <p className="text-sm text-slate-600 mt-1">satisfied patients received faster guidance</p>
                </div>
                <div className="bg-slate-900 text-white rounded-3xl p-5 shadow-sm">
                  <div className="text-xs text-slate-300 mb-2">Clinical confidence</div>
                  <div className="text-2xl font-semibold">99.2% report extraction reliability</div>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-8 grid grid-cols-2 md:grid-cols-4 gap-3">
            {['98 care units', '24/7 monitoring', 'Certified clinicians', 'Biotech-ready workflows'].map((chip) => (
              <div key={chip} className="rounded-full bg-white border border-slate-200 px-4 py-2 text-sm text-slate-700 text-center">
                {chip}
              </div>
            ))}
          </div>
        </div>

        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1 }} className="flex justify-center mt-10">
          <motion.div animate={{ y: [0, 8, 0] }} transition={{ repeat: Infinity, duration: 2 }}>
            <ChevronDown className="w-5 h-5 text-slate-400" />
          </motion.div>
        </motion.div>
      </section>

      <section ref={featuresRef} id="features" className="relative z-10 py-20 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-12">
            <p className="text-sm text-slate-500 uppercase tracking-[0.2em] mb-3">Solutions</p>
            <h2 className="text-4xl md:text-5xl font-semibold leading-tight">Explore our key Medaid services</h2>
            <p className="text-slate-600 mt-4 max-w-2xl mx-auto">Purpose-built tools that improve patient understanding, clinician efficiency, and quality of care.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {offerings.map((item, index) => {
              const Icon = item.icon;
              const cardImage = index % 2 === 0 ? landingImages.featurePrimary : landingImages.featureSecondary;
              return (
                <motion.div
                  key={item.title}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: index * 0.08 }}
                  className="rounded-3xl bg-white border border-slate-200 p-7 shadow-sm hover:shadow-md transition-shadow"
                >
                  <div className="mb-5 h-36 rounded-2xl overflow-hidden border border-slate-200">
                    <img
                      src={cardImage}
                      alt={`${item.title} illustration`}
                      className="w-full h-full object-cover"
                      loading="lazy"
                    />
                  </div>
                  <div className="w-12 h-12 rounded-2xl bg-slate-100 flex items-center justify-center mb-5">
                    <Icon className="w-6 h-6 text-sky-700" />
                  </div>
                  <h3 className="text-2xl font-semibold mb-3">{item.title}</h3>
                  <p className="text-slate-600 leading-relaxed">{item.description}</p>
                </motion.div>
              );
            })}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-8">
            {[
              { icon: Users, text: 'Patient-ready summaries' },
              { icon: Shield, text: 'Secure health records' },
              { icon: HeartPulse, text: 'Outcome-focused workflows' },
            ].map((stat) => {
              const Icon = stat.icon;
              return (
                <div key={stat.text} className="rounded-2xl bg-white border border-slate-200 px-5 py-4 flex items-center gap-3">
                  <Icon className="w-5 h-5 text-slate-500" />
                  <span className="text-slate-700 text-sm font-medium">{stat.text}</span>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      <section ref={aboutRef} id="about" className="relative z-10 py-20 px-6">
        <div className="max-w-6xl mx-auto grid lg:grid-cols-[1.1fr_0.9fr] gap-8 items-start">
          <div>
            <h2 className="text-4xl md:text-5xl font-semibold mb-4">Our awards & recognition</h2>
            <p className="text-slate-600 max-w-lg">Medaid is recognized for improving access to clinical clarity and creating a better care experience for both patients and providers.</p>
            <div className="mt-6 rounded-3xl border border-slate-200 bg-gradient-to-b from-sky-100/60 to-white p-6 shadow-sm">
              <div className="h-64 rounded-2xl border border-white overflow-hidden relative flex items-end p-5">
                <img
                  src={landingImages.recognition}
                  alt="Medaid award and recognition visual"
                  className="absolute inset-0 w-full h-full object-cover"
                  loading="lazy"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-slate-900/35 to-transparent" />
                <button onClick={() => navigate('/signup')} className="rounded-full bg-white border border-slate-200 px-5 py-2 text-sm font-medium hover:bg-slate-50 transition-colors">
                  Learn more
                </button>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            {achievements.map((item, index) => (
              <motion.div
                key={item.title}
                initial={{ opacity: 0, x: 20 }}
                whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.1 }}
                className="rounded-2xl bg-white border border-slate-200 px-5 py-4 shadow-sm"
              >
                <div className="flex items-center justify-between gap-3">
                  <h3 className="font-semibold text-lg">{item.title}</h3>
                  <ArrowRight className="w-4 h-4 text-slate-400" />
                </div>
                <p className="mt-1 text-sm text-slate-600">{item.detail}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <footer className="relative z-10 border-t border-slate-200 py-12 px-6 bg-white/70">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-slate-900 flex items-center justify-center">
              <Activity className="w-3.5 h-3.5 text-white" />
            </div>
            <span className="text-sm font-semibold">Medaid</span>
          </div>
          <div className="flex items-center gap-8 text-xs text-slate-500">
            <button onClick={() => scrollTo('home')} className="hover:text-slate-800 transition-colors">Home</button>
            <button onClick={() => scrollTo('features')} className="hover:text-slate-800 transition-colors">Features</button>
            <button onClick={() => scrollTo('about')} className="hover:text-slate-800 transition-colors">About</button>
            <button onClick={() => navigate('/login')} className="hover:text-slate-800 transition-colors">Sign In</button>
          </div>
          <p className="text-xs text-slate-500">© 2026 Medaid. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
};

export default MedaidLanding;
