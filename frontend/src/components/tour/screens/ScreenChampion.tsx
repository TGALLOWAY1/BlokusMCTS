import React from 'react';
import { Moon, ArrowDown, Crown, BadgeCheck, FlaskConical } from 'lucide-react';
import { ScreenShell } from '../components/ScreenShell';
import { SourceBadge } from '../components/SourceBadge';
import { useTourChampion } from '../tourMetrics';
import { DEMO_CHAMPION_TIMELINE, OVERNIGHT_PIPELINE } from '../tourData';
import type { ScreenProps } from './types';

export const ScreenChampion: React.FC<ScreenProps> = ({ stage, stepLabel }) => {
  const champ = useTourChampion();
  const meta = champ.champion;

  return (
    <ScreenShell
      stage={stage}
      stepLabel={stepLabel}
      intro="Improving the agent is a loop, not a moment. Candidates are generated, run through overnight tournaments, and a new champion is promoted only when the evidence clears the bar."
    >
      <div className="grid gap-5 lg:grid-cols-5">
        {/* overnight pipeline */}
        <div className="lg:col-span-3">
          <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold uppercase tracking-widest text-gray-400">
            <Moon size={15} className="text-neon-violet" /> The overnight loop
          </h3>
          <ol className="space-y-2">
            {OVERNIGHT_PIPELINE.map((s, i) => (
              <li key={s.label}>
                <div className="rounded-xl border border-charcoal-700 bg-charcoal-800/50 p-3">
                  <div className="flex items-center gap-2">
                    <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-neon-violet/15 font-mono text-xs font-bold text-neon-violet">
                      {i + 1}
                    </span>
                    <span className="text-sm font-bold text-white">{s.label}</span>
                  </div>
                  <p className="mt-1 pl-8 text-sm text-gray-400">{s.detail}</p>
                </div>
                {i < OVERNIGHT_PIPELINE.length - 1 && (
                  <div className="flex justify-center py-0.5 text-charcoal-600">
                    <ArrowDown size={14} />
                  </div>
                )}
              </li>
            ))}
          </ol>
        </div>

        {/* champion + timeline */}
        <div className="lg:col-span-2 space-y-4">
          <div className="rounded-2xl border border-neon-green/30 bg-charcoal-800/60 p-4">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-widest text-gray-300">
                <Crown size={15} className="text-neon-green" /> Current champion
              </h3>
              <SourceBadge source={champ.source} />
            </div>
            {meta && (
              <dl className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <dt className="text-[10px] uppercase tracking-widest text-gray-500">Version</dt>
                  <dd className="font-mono text-white">{meta.version}</dd>
                </div>
                <div>
                  <dt className="text-[10px] uppercase tracking-widest text-gray-500">TrueSkill μ</dt>
                  <dd className="font-mono text-neon-cyan">
                    {meta.trueSkill != null ? meta.trueSkill.toFixed(1) : '—'}
                  </dd>
                </div>
                <div className="col-span-2">
                  <dt className="text-[10px] uppercase tracking-widest text-gray-500">Notes</dt>
                  <dd className="text-xs leading-relaxed text-gray-400">{meta.notes ?? '—'}</dd>
                </div>
              </dl>
            )}
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-sm font-semibold uppercase tracking-widest text-gray-400">
                Promotion history
              </h3>
              <SourceBadge source="demo" />
            </div>
            <ol className="relative space-y-3 border-l border-charcoal-700 pl-4">
              {DEMO_CHAMPION_TIMELINE.map((e) => (
                <li key={e.version} className="relative">
                  <span className="absolute -left-[21px] top-1 inline-flex h-3 w-3 items-center justify-center rounded-full border border-charcoal-900 bg-neon-green" />
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm font-bold text-white">{e.version}</span>
                    <span className="text-[11px] text-gray-500">{e.date}</span>
                    <span
                      className={`inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider ${
                        e.status === 'promoted'
                          ? 'border-neon-green/40 bg-neon-green/10 text-neon-green'
                          : 'border-neon-violet/40 bg-neon-violet/10 text-neon-violet'
                      }`}
                    >
                      {e.status === 'promoted' ? <BadgeCheck size={10} /> : <FlaskConical size={10} />}
                      {e.status}
                    </span>
                  </div>
                  <p className="mt-0.5 text-xs leading-relaxed text-gray-400">{e.reason}</p>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </div>
    </ScreenShell>
  );
};
