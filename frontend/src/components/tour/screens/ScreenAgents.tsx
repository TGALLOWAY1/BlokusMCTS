import React from 'react';
import { Check, X, MapPin } from 'lucide-react';
import { ScreenShell } from '../components/ScreenShell';
import { AGENT_CARDS } from '../tourData';
import { ACCENTS } from '../components/accents';
import type { ScreenProps } from './types';

export const ScreenAgents: React.FC<ScreenProps> = ({ stage, stepLabel }) => (
  <ScreenShell
    stage={stage}
    stepLabel={stepLabel}
    intro="This is an evaluation laboratory, not just a game UI. Every agent below exists in the codebase and competes in the same seeded tournaments."
  >
    <div className="grid gap-3 sm:grid-cols-2">
      {AGENT_CARDS.map((a) => {
        const accent = ACCENTS[a.accent];
        return (
          <article
            key={a.name}
            className={`flex flex-col rounded-xl border bg-charcoal-800/50 p-4 ${accent.borderSoft}`}
          >
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-white">{a.name}</h3>
              <code className={`rounded bg-charcoal-900/70 px-2 py-0.5 text-[10px] ${accent.text}`}>
                {a.type}
              </code>
            </div>
            <p className="mt-2 text-sm leading-relaxed text-gray-400">{a.strategy}</p>
            <div className="mt-3 grid gap-2 text-xs">
              <ul className="space-y-1">
                {a.strengths.map((s, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-gray-300">
                    <Check size={13} className="mt-0.5 shrink-0 text-neon-green" /> {s}
                  </li>
                ))}
              </ul>
              <ul className="space-y-1">
                {a.weaknesses.map((w, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-gray-400">
                    <X size={13} className="mt-0.5 shrink-0 text-neon-red" /> {w}
                  </li>
                ))}
              </ul>
            </div>
            <div className="mt-3 flex items-start gap-1.5 border-t border-charcoal-700 pt-3 text-xs text-gray-400">
              <MapPin size={13} className={`mt-0.5 shrink-0 ${accent.text}`} />
              <span>{a.usedFor}</span>
            </div>
          </article>
        );
      })}
    </div>
  </ScreenShell>
);
