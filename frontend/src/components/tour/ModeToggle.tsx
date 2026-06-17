import React from 'react';
import { Footprints, LayoutGrid } from 'lucide-react';
import type { TourMode } from './tourTypes';

/** Segmented Guided / Overview switch. */
export const ModeToggle: React.FC<{
  mode: TourMode;
  onChange: (mode: TourMode) => void;
}> = ({ mode, onChange }) => {
  const opts: Array<{ value: TourMode; label: string; icon: React.ReactNode }> = [
    { value: 'guided', label: 'Guided', icon: <Footprints size={13} /> },
    { value: 'overview', label: 'Overview', icon: <LayoutGrid size={13} /> },
  ];
  return (
    <div
      role="radiogroup"
      aria-label="Tour mode"
      className="inline-flex rounded-full border border-charcoal-600 bg-charcoal-800/80 p-0.5"
    >
      {opts.map((o) => {
        const active = mode === o.value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(o.value)}
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold transition-colors ${
              active
                ? 'bg-neon-blue/15 text-neon-blue'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            {o.icon}
            {o.label}
          </button>
        );
      })}
    </div>
  );
};
