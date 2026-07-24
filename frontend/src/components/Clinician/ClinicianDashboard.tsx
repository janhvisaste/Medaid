import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  Bell,
  Calendar,
  Check,
  CheckCircle,
  Download,
  Eye,
  Filter,
  RefreshCw,
  Search,
  TrendingUp,
  Users,
} from 'lucide-react';
import apiService from '../../services/apiService';
import { medaidClasses, riskStyles } from '../../styles/medaidTokens';
import RiskBadge from '../ui/RiskBadge';
import { Skeleton } from '../ui/Skeleton';

interface ClinicianStats {
  total_patients: number;
  active_patients: number;
  emergency_patients: number;
  high_risk_patients: number;
  todays_assessments: number;
  pending_alerts: number;
}

interface PatientAssignment {
  id: number;
  patient_name: string;
  patient_email: string;
  status: string;
  priority: number;
  assigned_at: string;
  triage_details: {
    risk_level: string;
    current_symptoms: string;
    created_at: string;
    confidence?: number;
    reasoning?: string;
    possible_conditions?: string[];
    recommendations?: string[];
    requires_human_review?: boolean;
  };
}

interface ClinicianAlertItem {
  id: number;
  patient_name: string;
  patient_email: string;
  alert_type: string;
  risk_level: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

// Alerts are triaged by clinical severity first, recency second. An unknown
// tier sorts FIRST, not last: it means the backend sent something this map
// doesn't cover, and an unclassifiable alert is a thing to look at, not a
// thing to bury. Mirrors the 'high' floor in ClinicianAlertSerializer.
const RISK_ORDER: Record<string, number> = { emergency: 0, high: 1, medium: 2, low: 3, neutral: 4 };

// Left-border accent colour per risk level, so a row's severity reads at a
// glance in the queue without parsing the badge text.
const RISK_LINE: Record<string, string> = {
  emergency: 'var(--risk-emergency-line)',
  high: 'var(--risk-high-line)',
  medium: 'var(--risk-medium-line)',
  low: 'var(--risk-low-line)',
  neutral: 'var(--risk-neutral-line)',
};
const riskLine = (level?: string) => RISK_LINE[(level || 'neutral').toLowerCase()] || RISK_LINE.neutral;

const ALERT_REFRESH_MS = 45000;

const statCards = [
  {
    key: 'total_patients',
    label: 'Total Patients',
    detail: 'All time',
    icon: Users,
    accent: 'text-brand bg-brand-100 dark:bg-[var(--medaid-accent-soft)]',
  },
  {
    key: 'emergency_patients',
    label: 'Emergency Cases',
    detail: 'Immediate review',
    icon: AlertTriangle,
    accent: 'text-[var(--risk-emergency-text)] bg-[var(--risk-emergency-soft)]',
  },
  {
    key: 'high_risk_patients',
    label: 'High Risk',
    detail: 'Review within 24 hours',
    icon: Activity,
    accent: 'text-[var(--risk-high-text)] bg-[var(--risk-high-soft)]',
  },
  {
    key: 'todays_assessments',
    label: "Today's Assessments",
    detail: 'Last 24 hours',
    icon: TrendingUp,
    accent: 'text-[var(--medaid-ink-soft)] bg-[var(--medaid-surface-muted)]',
  },
] as const;

function getStatusLabel(status: string) {
  return status ? status.replace(/_/g, ' ') : 'Unassigned';
}

// Confidence arrives as a 0-1 float. Render it as a percentage, or null when
// the assessment carried no confidence so we can omit the chip entirely.
function formatConfidence(confidence?: number): string | null {
  if (typeof confidence !== 'number' || Number.isNaN(confidence)) return null;
  return `${Math.round(confidence * 100)}%`;
}

const ClinicianDashboard: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'emergency' | 'high' | 'medium' | 'low'>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('active');
  const [stats, setStats] = useState<ClinicianStats>({
    total_patients: 0,
    active_patients: 0,
    emergency_patients: 0,
    high_risk_patients: 0,
    todays_assessments: 0,
    pending_alerts: 0,
  });
  const [patients, setPatients] = useState<PatientAssignment[]>([]);
  const [alerts, setAlerts] = useState<ClinicianAlertItem[]>([]);
  const [alertsError, setAlertsError] = useState<string | null>(null);
  const [alertsRefreshing, setAlertsRefreshing] = useState(false);
  const [dismissing, setDismissing] = useState<number[]>([]);

  const fetchAlerts = useCallback(async () => {
    setAlertsRefreshing(true);
    try {
      const data = await apiService.getClinicianAlerts(false);
      setAlerts(Array.isArray(data) ? data : []);
      setAlertsError(null);
    } catch (err: any) {
      // Surface the failure. An alert queue that silently renders empty is
      // indistinguishable from "no patients need attention".
      setAlertsError(err.response?.data?.error || 'Could not load alerts. Retrying automatically.');
    } finally {
      setAlertsRefreshing(false);
    }
  }, []);

  const dismissAlert = useCallback(async (alertId: number) => {
    const previous = alerts;
    // Optimistic: drop it immediately, restore if the write fails.
    setAlerts((current) => current.filter((alert) => alert.id !== alertId));
    setDismissing((current) => [...current, alertId]);
    try {
      await apiService.markAlertRead(alertId);
    } catch (err: any) {
      setAlerts(previous);
      setAlertsError(err.response?.data?.error || 'Could not acknowledge that alert. It has been restored.');
    } finally {
      setDismissing((current) => current.filter((id) => id !== alertId));
    }
  }, [alerts]);

  const sortedAlerts = useMemo(
    () =>
      [...alerts].sort((a, b) => {
        const severity = (RISK_ORDER[a.risk_level] ?? -1) - (RISK_ORDER[b.risk_level] ?? -1);
        if (severity !== 0) return severity;
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      }),
    [alerts],
  );

  const fetchPatients = useCallback(async () => {
    try {
      const filters: any = {};
      if (filter !== 'all') {
        filters.risk_level = filter;
      }
      if (statusFilter) {
        filters.status = statusFilter;
      }
      if (searchTerm) {
        filters.search = searchTerm;
      }

      const patientsData = await apiService.getClinicianPatients(filters);
      setPatients(patientsData);
    } catch {
    }
  }, [filter, searchTerm, statusFilter]);

  const fetchStats = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const statsData = await apiService.getClinicianStats();
      setStats(statsData);
    } catch (err: any) {
      setError(err.response?.data?.error || 'Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  useEffect(() => {
    if (!loading) {
      fetchPatients();
    }
  }, [fetchPatients, loading]);

  // Poll the alert queue so a new emergency surfaces without a manual reload.
  useEffect(() => {
    fetchAlerts();
    const timer = setInterval(fetchAlerts, ALERT_REFRESH_MS);
    return () => clearInterval(timer);
  }, [fetchAlerts]);

  const visiblePatients = useMemo(() => patients.slice(0, 60), [patients]);

  if (loading) return <div className="mx-auto max-w-7xl space-y-5 px-4 py-8 md:px-6"><Skeleton className="h-36" /><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"><Skeleton className="h-28" /><Skeleton className="h-28" /><Skeleton className="h-28" /><Skeleton className="h-28" /></div><Skeleton className="h-96" /></div>;

  return (
    <div className={medaidClasses.page}>
      <div className={medaidClasses.dashboardContainer}>
        <header className={`${medaidClasses.restrainedHeroPanel} mb-6 p-6 md:p-8`}>
          <div className="pointer-events-none absolute -top-16 -right-14 h-44 w-44 rounded-full bg-brand-200/30 blur-2xl dark:bg-brand-900/40" />
          <div className="relative z-10 flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <div className={`${medaidClasses.badge} mb-4`}>
                <Activity className="h-3.5 w-3.5 text-brand" />
                Live clinical queue
              </div>
              <h1 className={medaidClasses.dashboardTitle}>Clinician Dashboard</h1>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--medaid-ink-soft)] md:text-base">
                Scan active triage assignments, prioritize urgent patients, and keep assessment follow-up moving.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-3 sm:flex">
              <div className={`${medaidClasses.compactCard} px-4 py-3`}>
                <p className={medaidClasses.mutedSmall}>Active patients</p>
                <p className="mt-1 text-2xl font-semibold text-[var(--medaid-ink)]">{stats.active_patients}</p>
              </div>
              <div className={`${medaidClasses.compactCard} px-4 py-3`}>
                <p className={medaidClasses.mutedSmall}>Pending alerts</p>
                <p className="mt-1 text-2xl font-semibold text-[var(--medaid-ink)]">{stats.pending_alerts}</p>
              </div>
            </div>
          </div>
        </header>

        {error && (
          <div role="alert" className="mb-6 rounded-card border border-[var(--risk-emergency-border)] bg-[var(--risk-emergency-soft)] px-4 py-3 text-[var(--risk-emergency-text)] shadow-e1">
            <div className="flex items-start gap-3">
              <AlertCircle className="mt-0.5 h-5 w-5 flex-shrink-0" />
              <div>
                <p className="text-sm font-semibold">Dashboard data issue</p>
                <p className="mt-1 text-sm">{error}</p>
              </div>
            </div>
          </div>
        )}

        <section className={`${medaidClasses.compactCard} mb-5 p-5`} aria-labelledby="alerts-heading">
          <div className="mb-4 flex items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <Bell className="h-5 w-5 text-[var(--risk-emergency-line)]" />
              <h2 id="alerts-heading" className="text-base font-semibold text-[var(--medaid-ink)]">
                Unacknowledged alerts
              </h2>
              {sortedAlerts.length > 0 && (
                <span className={`${medaidClasses.statusBadge} ${riskStyles.emergency.className}`}>
                  {sortedAlerts.length}
                </span>
              )}
            </div>
            <button
              onClick={fetchAlerts}
              disabled={alertsRefreshing}
              className={`p-2 ${medaidClasses.buttonGhost}`}
              aria-label="Refresh alerts"
            >
              <RefreshCw size={16} className={alertsRefreshing ? 'animate-spin' : ''} />
            </button>
          </div>

          {alertsError && (
            <div role="alert" className="mb-3 rounded-md border border-[var(--risk-emergency-border)] bg-[var(--risk-emergency-soft)] px-3 py-2 text-sm text-[var(--risk-emergency-text)]">
              {alertsError}
            </div>
          )}

          {sortedAlerts.length === 0 && !alertsError ? (
            <p className={medaidClasses.bodySmall}>No unacknowledged alerts.</p>
          ) : (
            <ul className="space-y-2">
              {sortedAlerts.map((alert) => {
                const urgent = ['emergency', 'high'].includes((alert.risk_level || '').toLowerCase());
                return (
                <li
                  key={alert.id}
                  style={{ borderLeftColor: riskLine(alert.risk_level) }}
                  className={`flex flex-col gap-3 rounded-card border border-l-4 border-[var(--medaid-border)] p-4 sm:flex-row sm:items-center sm:justify-between ${urgent ? riskStyles[(alert.risk_level.toLowerCase() as 'emergency')]?.softBgClassName ?? 'bg-[var(--medaid-surface-muted)]' : 'bg-[var(--medaid-surface-muted)]'}`}
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <RiskBadge risk={alert.risk_level} compact />
                      <span className="text-sm font-semibold text-[var(--medaid-ink)]">
                        {alert.patient_name}
                      </span>
                      <span className="text-xs text-[var(--medaid-ink-muted)]">{alert.patient_email}</span>
                    </div>
                    <p className="mt-1 text-sm leading-6 text-[var(--medaid-ink-soft)]">{alert.message}</p>
                    <p className="mt-1 text-xs text-[var(--medaid-ink-faint)]">
                      {new Date(alert.created_at).toLocaleString()}
                    </p>
                  </div>
                  <button
                    onClick={() => dismissAlert(alert.id)}
                    disabled={dismissing.includes(alert.id)}
                    className={`${medaidClasses.buttonSecondary} shrink-0 px-4 py-2 text-sm`}
                  >
                    <Check className="h-4 w-4" /> Acknowledge
                  </button>
                </li>
                );
              })}
            </ul>
          )}
        </section>

        <section className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {statCards.map((card, index) => {
            const Icon = card.icon;
            const value = stats[card.key];
            return (
              <div
                key={card.key}
                style={{ animationDelay: `${index * 60}ms` }}
                className={`${medaidClasses.compactCardHover} animate-fade-in p-5`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className={`flex h-11 w-11 items-center justify-center rounded-md ${card.accent}`}>
                    <Icon size={22} />
                  </div>
                  <p className="text-3xl font-semibold tracking-tight text-[var(--medaid-ink)] tabular-nums">{value}</p>
                </div>
                <p className="mt-4 text-sm font-semibold text-[var(--medaid-ink)]">{card.label}</p>
                <p className="mt-1 text-xs text-[var(--medaid-ink-muted)]">{card.detail}</p>
              </div>
            );
          })}
        </section>

        <section className={`${medaidClasses.compactCard} mb-5 p-4`}>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-[1.4fr_1fr_1fr]">
            <label className="relative block">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--medaid-ink-muted)]" />
              <input
                type="text"
                placeholder="Search patients..."
                value={searchTerm}
                onChange={(event) => setSearchTerm(event.target.value)}
                className={`${medaidClasses.input} pl-10`}
              />
            </label>

            <label className="relative block">
              <Filter className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--medaid-ink-muted)]" />
              <select
                value={filter}
                onChange={(event) => setFilter(event.target.value as any)}
                className={`${medaidClasses.select} pl-10`}
              >
                <option value="all">All risk levels</option>
                <option value="emergency">Emergency</option>
                <option value="high">High risk</option>
                <option value="medium">Medium risk</option>
                <option value="low">Low risk</option>
              </select>
            </label>

            <label className="relative block">
              <Calendar className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--medaid-ink-muted)]" />
              <select
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value)}
                className={`${medaidClasses.select} pl-10`}
              >
                <option value="">All status</option>
                <option value="active">Active</option>
                <option value="monitoring">Under monitoring</option>
                <option value="resolved">Resolved</option>
                <option value="transferred">Transferred</option>
              </select>
            </label>
          </div>
        </section>

        <section className={`${medaidClasses.card} overflow-hidden`}>
          <div className="flex flex-col gap-3 border-b border-[var(--medaid-border)] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-[var(--medaid-ink)]">Patient Queue</h2>
              <p className="mt-1 text-sm text-[var(--medaid-ink-muted)]">{visiblePatients.length} visible assignments</p>
            </div>
            <button className={`px-4 py-2 ${medaidClasses.buttonSecondary}`}>
              <Download className="h-4 w-4" />
              Export
            </button>
          </div>

          {visiblePatients.length === 0 ? (
            <div className="px-6 py-12 text-center">
              <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-md bg-[var(--medaid-surface-muted)]">
                <Users className="text-[var(--medaid-ink-muted)]" size={28} />
              </div>
              <p className="text-base font-semibold text-[var(--medaid-ink)]">No patients assigned yet</p>
              <p className="mx-auto mt-2 max-w-md text-sm text-[var(--medaid-ink-muted)]">
                Patient assignments will appear here once patients complete triage assessments.
              </p>
            </div>
          ) : (
            <>
            <div className="space-y-3 p-4 md:hidden">
              {visiblePatients.map((patient) => (
                <article key={patient.id} style={{ borderLeftColor: riskLine(patient.triage_details.risk_level) }} className={`${medaidClasses.compactCard} border-l-4 p-4`}>
                  <div className="flex items-start justify-between gap-3"><div><p className="text-sm font-semibold text-[var(--medaid-ink)]">{patient.patient_name}</p><p className="mt-1 text-xs text-[var(--medaid-ink-muted)]">{patient.patient_email}</p></div><div className="flex flex-col items-end gap-1"><RiskBadge risk={patient.triage_details.risk_level} compact />{patient.triage_details.requires_human_review && <span className="inline-flex items-center gap-1 rounded-pill bg-[var(--risk-medium-soft)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[var(--risk-medium-text)]"><AlertTriangle className="h-3 w-3" /> Review</span>}</div></div>
                  <p className="mt-3 text-sm leading-6 text-[var(--medaid-ink-soft)]">{patient.triage_details.current_symptoms}</p>
                  {(patient.triage_details.possible_conditions?.length ?? 0) > 0 && <div className="mt-2 flex flex-wrap gap-1.5">{patient.triage_details.possible_conditions!.slice(0, 4).map((condition, index) => <span key={index} className="rounded-full border border-[var(--medaid-border)] bg-[var(--medaid-surface-muted)] px-2 py-0.5 text-[11px] font-medium text-[var(--medaid-ink-soft)]">{condition}</span>)}</div>}
                  {patient.triage_details.reasoning && <p className="mt-2 line-clamp-3 text-xs leading-5 text-[var(--medaid-ink-muted)]">{patient.triage_details.reasoning}</p>}
                  <div className="mt-3 flex items-center justify-between text-xs text-[var(--medaid-ink-muted)]"><span>{new Date(patient.triage_details.created_at).toLocaleDateString()}</span><div className="flex items-center gap-2">{formatConfidence(patient.triage_details.confidence) && <span className="font-medium text-[var(--medaid-ink-soft)]">Confidence {formatConfidence(patient.triage_details.confidence)}</span>}<span className={`${medaidClasses.statusBadge} ${riskStyles.neutral.className}`}>{getStatusLabel(patient.status)}</span></div></div>
                </article>
              ))}
            </div>
            <div className="hidden overflow-x-auto md:block">
              <table className="min-w-full divide-y divide-[var(--medaid-border)] text-left">
                <thead className="bg-[var(--medaid-surface-muted)]">
                  <tr>
                    <th className="px-5 py-3 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--medaid-ink-muted)]">Patient</th>
                    <th className="px-5 py-3 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--medaid-ink-muted)]">Risk</th>
                    <th className="px-5 py-3 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--medaid-ink-muted)]">Assessment</th>
                    <th className="px-5 py-3 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--medaid-ink-muted)]">Confidence</th>
                    <th className="px-5 py-3 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--medaid-ink-muted)]">Assessed</th>
                    <th className="px-5 py-3 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--medaid-ink-muted)]">Status</th>
                    <th className="px-5 py-3 text-right text-xs font-semibold uppercase tracking-[0.12em] text-[var(--medaid-ink-muted)]">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--medaid-border)] bg-[var(--medaid-surface)]">
                  {visiblePatients.map((patient) => {
                    return (
                      <tr key={patient.id} style={{ boxShadow: `inset 4px 0 0 0 ${riskLine(patient.triage_details.risk_level)}` }} className="transition-colors hover:bg-[var(--medaid-surface-muted)]">
                        <td className="whitespace-nowrap px-5 py-4">
                          <p className="text-sm font-semibold text-[var(--medaid-ink)]">{patient.patient_name}</p>
                          <p className="mt-1 text-xs text-[var(--medaid-ink-muted)]">{patient.patient_email}</p>
                        </td>
                        <td className="whitespace-nowrap px-5 py-4">
                          <div className="flex flex-col items-start gap-1.5">
                            <RiskBadge risk={patient.triage_details.risk_level} compact />
                            {patient.triage_details.requires_human_review && (
                              <span className="inline-flex items-center gap-1 rounded-pill bg-[var(--risk-medium-soft)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[var(--risk-medium-text)]">
                                <AlertTriangle className="h-3 w-3" /> Review
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="max-w-sm px-5 py-4">
                          <p className="line-clamp-2 text-sm leading-6 text-[var(--medaid-ink-soft)]">
                            {patient.triage_details.current_symptoms}
                          </p>
                          {(patient.triage_details.possible_conditions?.length ?? 0) > 0 && (
                            <div className="mt-1.5 flex flex-wrap gap-1.5">
                              {patient.triage_details.possible_conditions!.slice(0, 3).map((condition, index) => (
                                <span key={index} className="rounded-full border border-[var(--medaid-border)] bg-[var(--medaid-surface-muted)] px-2 py-0.5 text-[11px] font-medium text-[var(--medaid-ink-soft)]">
                                  {condition}
                                </span>
                              ))}
                            </div>
                          )}
                          {patient.triage_details.reasoning && (
                            <p className="mt-1.5 line-clamp-2 text-xs leading-5 text-[var(--medaid-ink-muted)]">
                              {patient.triage_details.reasoning}
                            </p>
                          )}
                        </td>
                        <td className="whitespace-nowrap px-5 py-4 text-sm text-[var(--medaid-ink-soft)]">
                          {formatConfidence(patient.triage_details.confidence) ?? '—'}
                        </td>
                        <td className="whitespace-nowrap px-5 py-4 text-sm text-[var(--medaid-ink-soft)]">
                          {new Date(patient.triage_details.created_at).toLocaleString()}
                        </td>
                        <td className="whitespace-nowrap px-5 py-4">
                          <span className={`${medaidClasses.statusBadge} ${riskStyles.neutral.className}`}>
                            <span className={`h-1.5 w-1.5 rounded-full ${riskStyles.neutral.dotClassName}`} />
                            {getStatusLabel(patient.status)}
                          </span>
                        </td>
                        <td className="whitespace-nowrap px-5 py-4 text-right">
                          <div className="inline-flex items-center gap-1">
                            <button className={`p-2 ${medaidClasses.buttonGhost}`} aria-label={`View ${patient.patient_name}`}>
                              <Eye size={18} />
                            </button>
                            <button className={`p-2 ${medaidClasses.buttonGhost}`} aria-label={`Download ${patient.patient_name}`}>
                              <Download size={18} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            </>
          )}
        </section>

        {visiblePatients.length === 0 && (
          <section className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className={`${medaidClasses.compactCard} p-5`}>
              <h3 className="text-base font-semibold text-[var(--medaid-ink)]">Getting started</h3>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-[var(--medaid-ink-soft)]">
                <li>Ensure your account has clinician role permissions.</li>
                <li>Patients with emergency or high risk assessments will be prioritized.</li>
                <li>Use filters to focus the queue during shift handoffs.</li>
              </ul>
            </div>

            <div className={`${medaidClasses.compactCard} p-5`}>
              <h3 className="text-base font-semibold text-[var(--medaid-ink)]">Available workflow</h3>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-[var(--medaid-ink-soft)]">
                {['View assessments by risk level', 'Filter and search patients', 'Download detailed patient reports'].map((item) => (
                  <li key={item} className="flex items-center gap-2">
                    <CheckCircle className="h-4 w-4 flex-shrink-0 text-brand" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          </section>
        )}
      </div>
    </div>
  );
};

export default ClinicianDashboard;
