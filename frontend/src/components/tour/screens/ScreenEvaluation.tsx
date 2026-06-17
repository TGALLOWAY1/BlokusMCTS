import React from 'react';
import { Settings2, Dices, Swords, BarChart3, ArrowRight, Database, RotateCw, FileCode } from 'lucide-react';
import { ScreenShell } from '../components/ScreenShell';
import { SourceBadge } from '../components/SourceBadge';
import { DEMO_PAIRWISE } from '../tourData';
import type { ScreenProps } from './types';

const PIPELINE = [
  { icon: <Settings2 size={16} />, label: 'Reproducible config', sub: 'JSON arena spec' },
  { icon: <Dices size={16} />, label: 'Seeded games', sub: 'fixed RNG seeds' },
  { icon: <Swords size={16} />, label: 'Round-robin', sub: 'every seat rotated' },
  { icon: <BarChart3 size={16} />, label: 'Aggregate', sub: 'wins · scores · pairwise' },
];

const pct = (v: number | null) => (v === null ? '—' : `${Math.round(v * 100)}%`);
const cellTone = (v: number | null) =>
  v === null
    ? 'text-gray-600'
    : v >= 0.6
      ? 'text-neon-green'
      : v >= 0.4
        ? 'text-gray-200'
        : 'text-neon-red';

export const ScreenEvaluation: React.FC<ScreenProps> = ({ stage, stepLabel }) => (
  <ScreenShell
    stage={stage}
    stepLabel={stepLabel}
    intro="Strength is measured, not asserted. Agents meet in seeded arena tournaments and every game is reproducible from a JSON config — so a result can always be replayed and attributed to one change."
  >
    <div className="space-y-5">
      {/* pipeline */}
      <div className="flex flex-wrap items-stretch gap-2">
        {PIPELINE.map((p, i) => (
          <React.Fragment key={p.label}>
            <div className="flex-1 rounded-xl border border-charcoal-700 bg-charcoal-800/50 p-3">
              <span className="text-neon-cyan">{p.icon}</span>
              <div className="mt-1 text-sm font-bold text-white">{p.label}</div>
              <div className="text-[11px] text-gray-500">{p.sub}</div>
            </div>
            {i < PIPELINE.length - 1 && (
              <div className="hidden items-center text-charcoal-600 sm:flex">
                <ArrowRight size={16} />
              </div>
            )}
          </React.Fragment>
        ))}
      </div>

      <div className="grid gap-5 lg:grid-cols-5">
        {/* pairwise matrix */}
        <div className="lg:col-span-3">
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-sm font-semibold uppercase tracking-widest text-gray-400">
              Pairwise win rate (row beats column)
            </h3>
            <SourceBadge source="demo" />
          </div>
          <div className="overflow-x-auto rounded-xl border border-charcoal-700 bg-charcoal-800/50">
            <table className="w-full text-center text-xs">
              <thead className="text-[10px] uppercase tracking-widest text-gray-500">
                <tr>
                  <th className="px-3 py-2 text-left">vs →</th>
                  {DEMO_PAIRWISE.agents.map((a) => (
                    <th key={a} className="px-3 py-2 font-mono">{a}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-charcoal-700">
                {DEMO_PAIRWISE.agents.map((row, ri) => (
                  <tr key={row}>
                    <td className="px-3 py-2 text-left font-mono text-gray-300">{row}</td>
                    {DEMO_PAIRWISE.winRate[ri].map((v, ci) => (
                      <td key={ci} className={`px-3 py-2 font-semibold ${cellTone(v)}`}>
                        {pct(v)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* reproducibility */}
        <div className="lg:col-span-2">
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-widest text-gray-400">
            Why it is trustworthy
          </h3>
          <ul className="space-y-2 text-sm">
            <li className="flex items-start gap-2 rounded-lg border border-charcoal-700 bg-charcoal-800/40 p-3">
              <Dices size={15} className="mt-0.5 shrink-0 text-neon-cyan" />
              <span className="text-gray-300"><b className="text-white">Fixed seeds</b> — same seed, same game. Differences come from the algorithm, not luck.</span>
            </li>
            <li className="flex items-start gap-2 rounded-lg border border-charcoal-700 bg-charcoal-800/40 p-3">
              <RotateCw size={15} className="mt-0.5 shrink-0 text-neon-blue" />
              <span className="text-gray-300"><b className="text-white">Seat rotation</b> — every agent plays every seat to cancel positional bias.</span>
            </li>
            <li className="flex items-start gap-2 rounded-lg border border-charcoal-700 bg-charcoal-800/40 p-3">
              <FileCode size={15} className="mt-0.5 shrink-0 text-neon-violet" />
              <span className="text-gray-300"><b className="text-white">Replayable</b> — runs land in <code className="text-gray-400">arena_runs/*/summary.json</code> for re-analysis.</span>
            </li>
            <li className="flex items-start gap-2 rounded-lg border border-charcoal-700 bg-charcoal-800/40 p-3">
              <Database size={15} className="mt-0.5 shrink-0 text-neon-green" />
              <span className="text-gray-300"><b className="text-white">Score stats</b> — win rates, margins, and per-seat scores, not a single headline number.</span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  </ScreenShell>
);
