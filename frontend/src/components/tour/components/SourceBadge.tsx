import React from 'react';
import { Database, FlaskConical } from 'lucide-react';
import type { MetricSource } from '../tourMetrics';

/**
 * Honest live-vs-demo indicator. Screens render this next to any metric so the
 * viewer always knows whether they are looking at real arena/registry data or
 * representative fallback values.
 */
export const SourceBadge: React.FC<{ source: MetricSource; label?: string }> = ({
  source,
  label,
}) => {
  if (source === 'live') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-neon-green/40 bg-neon-green/10 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-widest text-neon-green">
        <Database size={10} /> {label ?? 'Live data'}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-neon-violet/40 bg-neon-violet/10 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-widest text-neon-violet">
      <FlaskConical size={10} /> {label ?? 'Demo data'}
    </span>
  );
};
