import React from 'react';
import { AlertCircle, AlertTriangle, CheckCircle2, CircleAlert } from 'lucide-react';
import { medaidClasses, riskStyles, type MedaidRisk } from '../../styles/medaidTokens';

interface RiskBadgeProps { risk: string; compact?: boolean; }

const icons = { emergency: CircleAlert, high: AlertTriangle, medium: AlertCircle, low: CheckCircle2, neutral: AlertCircle } as const;

const RiskBadge: React.FC<RiskBadgeProps> = ({ risk, compact = false }) => {
  const normalized = (risk || 'neutral').toLowerCase() as MedaidRisk;
  const meta = riskStyles[normalized] || riskStyles.neutral;
  const Icon = icons[normalized] || icons.neutral;
  return <span className={`${medaidClasses.statusBadge} ${meta.className} ${compact ? 'px-2 py-0.5 text-[11px]' : ''}`}><Icon className="h-3.5 w-3.5" aria-hidden="true" />{meta.label}</span>;
};

export default RiskBadge;
