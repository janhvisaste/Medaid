import React, { useRef, useState, useEffect } from 'react';
import { motion } from 'framer-motion';
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
import { medaidClasses } from '../styles/medaidTokens';
type IconType = React.ElementType;

const MedaidLanding: React.FC = () => {
  const navigate = useNavigate();
  const [activeSection, setActiveSection] = useState('home');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const homeRef = useRef<HTMLDivElement>(null);
  const featuresRef = useRef<HTMLDivElement>(null);
  const aboutRef = useRef<HTMLDivElement>(null);

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
    <div ref={containerRef} className={medaidClasses.page}>
      <nav className={medaidClasses.nav}>
        <div className={`${medaidClasses.landingContainer} h-16 flex items-center justify-between`}>
          <button onClick={() => scrollTo('home')} className="flex items-center gap-2.5">
            <div className={`w-9 h-9 ${medaidClasses.brandMark}`}>
              <Activity className="w-4 h-4 text-brand" />
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
                    ? 'text-[var(--medaid-ink)] bg-[var(--medaid-surface)] shadow-e1 border border-[var(--medaid-border)]'
                    : 'text-[var(--medaid-ink-muted)] hover:text-[var(--medaid-ink)]'
                }`}
              >
                {link.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/login')}
              className="hidden md:block px-5 py-2 text-sm font-medium text-[var(--medaid-ink-soft)] hover:text-[var(--medaid-ink)] transition-colors"
            >
              Sign In
            </button>
            <button
              onClick={() => navigate('/signup')}
              className={`hidden md:flex px-5 py-2.5 ${medaidClasses.buttonPrimary}`}
            >
              Get Started <ArrowRight className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-2 text-[var(--medaid-ink-muted)] hover:text-[var(--medaid-ink)]"
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
            className="md:hidden border-t border-[var(--medaid-border)] bg-[var(--medaid-surface)]/90 backdrop-blur-xl"
          >
            <div className="px-6 py-4 space-y-1">
              {navLinks.map(link => (
                <button
                  key={link.id}
                  onClick={() => scrollTo(link.id)}
                  className={`block w-full text-left px-4 py-3 text-sm font-medium rounded-lg ${
                    activeSection === link.id ? 'text-[var(--medaid-ink)] bg-[var(--medaid-surface-muted)]' : 'text-[var(--medaid-ink-soft)]'
                  }`}
                >
                  {link.label}
                </button>
              ))}
              <div className="pt-3 flex gap-3">
                <button onClick={() => navigate('/login')} className="flex-1 rounded-lg border border-[var(--medaid-border)] py-2.5 text-sm font-medium text-[var(--medaid-ink-soft)]">Sign In</button>
                <button onClick={() => navigate('/signup')} className="flex-1 rounded-control bg-brand py-2.5 text-sm font-semibold text-brand-contrast">Get Started</button>
              </div>
            </div>
          </motion.div>
        )}
      </nav>

      <section ref={homeRef} id="home" className="relative pt-28 pb-20 px-6 overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(15,118,110,0.12),transparent_60%)]" />
        <div className={`${medaidClasses.landingContainer} relative z-10`}>
          <div className={`${medaidClasses.heroPanel} p-10 md:p-14`}>
            <div className="pointer-events-none absolute -top-10 -right-12 w-52 h-52 rounded-pill bg-brand-200/30 blur-2xl dark:bg-brand-900/40" />
            <div className="pointer-events-none absolute -bottom-8 -left-8 w-56 h-56 rounded-pill bg-brand-100/40 blur-2xl dark:bg-brand-800/30" />

            <div className="grid lg:grid-cols-[1.2fr_0.8fr] gap-8 items-center">
              <div>
                <div className={`${medaidClasses.badge} mb-6`}>
                  <Sparkles className="w-3.5 h-3.5 text-brand" />
                  AI-powered care coordination for modern clinics
                </div>

                <h1 className={medaidClasses.h1}>
                  Innovative healthcare technology
                  <span className="block text-[var(--medaid-ink-soft)]">with care for every patient.</span>
                </h1>
                <p className="mt-6 max-w-xl text-lg text-[var(--medaid-ink-soft)]">
                  Medaid helps patients and clinicians move faster from symptoms to clarity using triage intelligence, report analysis, and guided next steps.
                </p>

                <div className="mt-8 flex flex-col sm:flex-row gap-3">
                  <button onClick={() => navigate('/signup')} className={`px-6 py-3 ${medaidClasses.buttonPrimary}`}>
                    Explore Medaid <ArrowRight className="w-4 h-4" />
                  </button>
                  <button onClick={() => scrollTo('features')} className={`px-6 py-3 ${medaidClasses.buttonSecondary}`}>
                    See key capabilities
                  </button>
                </div>
              </div>

              <div className="space-y-4">
                <div className={`${medaidClasses.card} p-3`}>
                  <img
                    src={landingImages.hero}
                    alt="Medaid healthcare innovation visual"
                    className="w-full h-36 object-cover rounded-card"
                    loading="lazy"
                  />
                </div>
                <div className={`${medaidClasses.card} p-5`}>
                  <div className="mb-1 text-xs text-[var(--medaid-ink-muted)]">Today with Medaid</div>
                  <div className="text-3xl font-semibold">1.5k+</div>
                  <p className="mt-1 text-sm text-[var(--medaid-ink-soft)]">satisfied patients received faster guidance</p>
                </div>
                <div className="bg-brand text-brand-contrast rounded-card p-5 shadow-e1">
                  <div className="text-xs opacity-80 mb-2">Clinical confidence</div>
                  <div className="text-2xl font-semibold">99.2% report extraction reliability</div>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-8 grid grid-cols-2 md:grid-cols-4 gap-3">
            {['98 care units', '24/7 monitoring', 'Certified clinicians', 'Biotech-ready workflows'].map((chip) => (
              <div key={chip} className="rounded-pill border border-[var(--medaid-border)] bg-[var(--medaid-surface)] px-4 py-2 text-center text-sm text-[var(--medaid-ink-soft)]">
                {chip}
              </div>
            ))}
          </div>
        </div>

        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1 }} className="flex justify-center mt-10">
          <motion.div animate={{ y: [0, 8, 0] }} transition={{ repeat: Infinity, duration: 2 }}>
            <ChevronDown className="h-5 w-5 text-[var(--medaid-ink-muted)]" />
          </motion.div>
        </motion.div>
      </section>

      <section ref={featuresRef} id="features" className="relative z-10 py-20 px-6">
        <div className={medaidClasses.landingContainer}>
          <div className="text-center mb-12">
            <p className="mb-3 text-sm uppercase tracking-[0.2em] text-[var(--medaid-ink-muted)]">Solutions</p>
            <h2 className="font-display text-4xl md:text-5xl font-medium leading-tight">Explore our key Medaid services</h2>
            <p className="mx-auto mt-4 max-w-2xl text-[var(--medaid-ink-soft)]">Purpose-built tools that improve patient understanding, clinician efficiency, and quality of care.</p>
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
                  className={`${medaidClasses.card} p-7 hover:shadow-e2 transition-shadow`}
                >
                  <div className="mb-5 h-36 overflow-hidden rounded-card border border-[var(--medaid-border)]">
                    <img
                      src={cardImage}
                      alt={`${item.title} illustration`}
                      className="w-full h-full object-cover"
                      loading="lazy"
                    />
                  </div>
                  <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-card bg-[var(--medaid-surface-muted)]">
                    <Icon className="h-6 w-6 text-[var(--medaid-accent)]" />
                  </div>
                  <h3 className="text-2xl font-semibold mb-3">{item.title}</h3>
                  <p className="leading-relaxed text-[var(--medaid-ink-soft)]">{item.description}</p>
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
                <div key={stat.text} className="flex items-center gap-3 rounded-card border border-[var(--medaid-border)] bg-[var(--medaid-surface)] px-5 py-4">
                  <Icon className="h-5 w-5 text-[var(--medaid-ink-muted)]" />
                  <span className="text-sm font-medium text-[var(--medaid-ink-soft)]">{stat.text}</span>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      <section ref={aboutRef} id="about" className="relative z-10 py-20 px-6">
        <div className={`${medaidClasses.landingContainer} grid lg:grid-cols-[1.1fr_0.9fr] gap-8 items-start`}>
          <div>
            <h2 className="font-display text-4xl md:text-5xl font-medium mb-4">Our awards &amp; recognition</h2>
            <p className="max-w-lg text-[var(--medaid-ink-soft)]">Medaid is recognized for improving access to clinical clarity and creating a better care experience for both patients and providers.</p>
            <div className="mt-6 rounded-card border border-[var(--medaid-border)] bg-[var(--medaid-surface)] p-6 shadow-e1">
              <div className="h-64 rounded-card border border-white overflow-hidden relative flex items-end p-5">
                <img
                  src={landingImages.recognition}
                  alt="Medaid award and recognition visual"
                  className="absolute inset-0 w-full h-full object-cover"
                  loading="lazy"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-slate-900/35 to-transparent" />
                <button onClick={() => navigate('/signup')} className="rounded-pill border border-[var(--medaid-border)] bg-[var(--medaid-surface)] px-5 py-2 text-sm font-medium text-[var(--medaid-ink)] transition-colors hover:bg-[var(--medaid-surface-muted)]">
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
              className={`${medaidClasses.compactCard} px-5 py-4`}
              >
                <div className="flex items-center justify-between gap-3">
                  <h3 className="font-semibold text-lg">{item.title}</h3>
                  <ArrowRight className="h-4 w-4 text-[var(--medaid-ink-muted)]" />
                </div>
                <p className="mt-1 text-sm text-[var(--medaid-ink-soft)]">{item.detail}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <footer className="relative z-10 border-t border-[var(--medaid-border)] bg-[var(--medaid-surface)]/70 px-6 py-12">
        <div className={`${medaidClasses.landingContainer} flex flex-col md:flex-row items-center justify-between gap-6`}>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-brand flex items-center justify-center">
              <Activity className="w-3.5 h-3.5 text-brand-contrast" />
            </div>
            <span className="text-sm font-semibold">Medaid</span>
          </div>
          <div className="flex items-center gap-8 text-xs text-[var(--medaid-ink-muted)]">
            <button onClick={() => scrollTo('home')} className="transition-colors hover:text-[var(--medaid-ink)]">Home</button>
            <button onClick={() => scrollTo('features')} className="transition-colors hover:text-[var(--medaid-ink)]">Features</button>
            <button onClick={() => scrollTo('about')} className="transition-colors hover:text-[var(--medaid-ink)]">About</button>
            <button onClick={() => navigate('/login')} className="transition-colors hover:text-[var(--medaid-ink)]">Sign In</button>
          </div>
          <p className="text-xs text-[var(--medaid-ink-muted)]">© 2026 Medaid. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
};

export default MedaidLanding;
