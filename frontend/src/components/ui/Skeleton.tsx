import React from 'react';

export const Skeleton: React.FC<{ className?: string }> = ({ className = '' }) => (
  <div aria-hidden="true" className={`animate-pulse rounded-card bg-[var(--medaid-surface-muted)] ${className}`} />
);

export const PageSkeleton: React.FC = () => (
  <div className="mx-auto max-w-7xl space-y-5 px-4 py-8 md:px-6">
    <Skeleton className="h-32 w-full" />
    <div className="grid gap-4 md:grid-cols-3"><Skeleton className="h-28" /><Skeleton className="h-28" /><Skeleton className="h-28" /></div>
    <Skeleton className="h-72 w-full" />
  </div>
);
