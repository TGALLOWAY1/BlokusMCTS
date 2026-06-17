import React, { useState } from 'react';
import { CheckCircle2, AlertTriangle, CircleDot } from 'lucide-react';
import { ScreenShell } from '../components/ScreenShell';
import { TECHNIQUE_CARDS, type TechniqueCard } from '../tourData';
import type { ScreenProps } from './types';

const verdictMeta: Record<TechniqueCard['verdict'], { label: string; cls: string; icon: React.ReactNode }> = {
  win: { label: 'Win', cls: 'text-neon-green border-neon-green/40 bg-neon-green/10', icon: <CheckCircle2 size={11} /> },
  mixed: { label: 'Mixed', cls: 'text-neon-violet border-neon-violet/40 bg-neon-violet/10', icon: <AlertTriangle size={11} /> },
  baseline: { label: 'Core', cls: 'text-neon-cyan border-neon-cyan/40 bg-neon-cyan/10', icon: <CircleDot size={11} /> },
};

export const ScreenTechniques: React.FC<ScreenProps> = ({ stage, stepLabel }) => {
  const [selected, setSelected] = useState<string>(TECHNIQUE_CARDS[0].id);
  const active = TECHNIQUE_CARDS.find((t) => t.id === selected) ?? TECHNIQUE_CARDS[0];
  const v = verdictMeta[active.verdict];

  return (
    <ScreenShell
      stage={stage}
      stepLabel={stepLabel}
      intro="MCTS is a skeleton — Select, Expand, Simulate, Backpropagate — with many optional enhancements. These are the techniques actually implemented here, with honest verdicts on what helped."
    >
      <div className="grid gap-4 lg:grid-cols-5">
        {/* technique selector */}
        <div className="lg:col-span-2">
          <div className="flex flex-wrap gap-2 lg:flex-col">
            {TECHNIQUE_CARDS.map((t) => {
              const tv = verdictMeta[t.verdict];
              const isActive = t.id === selected;
              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setSelected(t.id)}
                  aria-pressed={isActive}
                  className={`flex w-full items-center justify-between gap-2 rounded-lg border px-3 py-2 text-left text-sm font-semibold transition-colors ${
                    isActive
                      ? 'border-neon-blue bg-neon-blue/10 text-white'
                      : 'border-charcoal-700 bg-charcoal-800/40 text-gray-300 hover:border-charcoal-500'
                  }`}
                >
                  <span className="truncate">{t.name}</span>
                  <span className={`inline-flex shrink-0 items-center gap-1 rounded-full border px-1.5 py-0.5 text-[9px] uppercase tracking-wider ${tv.cls}`}>
                    {tv.icon}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* detail panel */}
        <div className="lg:col-span-3">
          <div className="h-full rounded-2xl border border-charcoal-700 bg-charcoal-800/60 p-5">
            <div className="flex items-center justify-between gap-3">
              <span className="text-[11px] font-bold uppercase tracking-widest text-gray-500">
                {active.phase}
              </span>
              <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-widest ${v.cls}`}>
                {v.icon} {v.label}
              </span>
            </div>
            <h3 className="mt-2 text-xl font-bold text-white">{active.name}</h3>
            <p className="mt-1 text-sm font-semibold text-gray-200">{active.blurb}</p>
            <p className="mt-3 text-sm leading-relaxed text-gray-400">{active.detail}</p>
          </div>
        </div>
      </div>
    </ScreenShell>
  );
};
