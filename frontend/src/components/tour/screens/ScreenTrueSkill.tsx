import React from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import { Info } from 'lucide-react';
import { ScreenShell } from '../components/ScreenShell';
import { SourceBadge } from '../components/SourceBadge';
import { useTourLeaderboard } from '../tourMetrics';
import { DEMO_PROGRESSION } from '../tourData';
import type { ScreenProps } from './types';

/** Horizontal μ ± 3σ confidence bar for one agent, scaled to a shared domain. */
const CIBar: React.FC<{
  mu: number;
  sigma: number;
  domain: [number, number];
}> = ({ mu, sigma, domain }) => {
  const [lo, hi] = domain;
  const span = hi - lo || 1;
  const toPct = (v: number) => ((v - lo) / span) * 100;
  const left = toPct(mu - 3 * sigma);
  const right = toPct(mu + 3 * sigma);
  const center = toPct(mu);
  return (
    <div className="relative h-3 w-full rounded-full bg-charcoal-900/70">
      <div
        className="absolute top-1/2 h-1 -translate-y-1/2 rounded-full bg-neon-blue/40"
        style={{ left: `${left}%`, width: `${Math.max(right - left, 1)}%` }}
      />
      <div
        className="absolute top-1/2 h-3 w-1 -translate-x-1/2 -translate-y-1/2 rounded-full bg-neon-cyan"
        style={{ left: `${center}%` }}
      />
    </div>
  );
};

export const ScreenTrueSkill: React.FC<ScreenProps> = ({ stage, stepLabel }) => {
  const lb = useTourLeaderboard();

  const mus = lb.rows.flatMap((r) => [r.mu - 3 * r.sigma, r.mu + 3 * r.sigma]);
  const domain: [number, number] = [
    Math.floor(Math.min(...mus, 0) - 2),
    Math.ceil(Math.max(...mus) + 2),
  ];

  return (
    <ScreenShell
      stage={stage}
      stepLabel={stepLabel}
      intro="A single win is noise. Agents are ranked with TrueSkill — a Bayesian rating built for multiplayer games — so we reward agents that are both strong and consistent across many seeded games."
    >
      <div className="space-y-5">
        <div className="rounded-xl border border-neon-blue/30 bg-charcoal-800/60 p-3 text-sm text-gray-300">
          <span className="inline-flex items-center gap-1.5 font-semibold text-neon-blue">
            <Info size={14} /> Conservative rating = μ − 3σ
          </span>{' '}
          — an agent only ranks high if its skill estimate (μ) is large <em>and</em> its
          uncertainty (σ) is small. Native 4-player ratings, no pairwise decomposition.
        </div>

        <div className="grid gap-5 lg:grid-cols-5">
          {/* leaderboard with CI bars */}
          <div className="lg:col-span-3">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-sm font-semibold uppercase tracking-widest text-gray-400">
                TrueSkill leaderboard
              </h3>
              <SourceBadge source={lb.source} />
            </div>
            <div className="space-y-2">
              {lb.rows.map((r) => (
                <div
                  key={r.agent_id}
                  className="rounded-xl border border-charcoal-700 bg-charcoal-800/50 p-3"
                >
                  <div className="flex items-center justify-between text-sm">
                    <span className="flex items-center gap-2 font-semibold text-white">
                      <span className="font-mono text-xs text-gray-500">#{r.rank}</span>
                      {r.agent_id}
                      <span className="rounded bg-charcoal-900/70 px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-gray-500">
                        {r.type}
                      </span>
                    </span>
                    <span className="font-mono text-xs text-gray-400">
                      μ {r.mu.toFixed(1)} · σ {r.sigma.toFixed(1)} ·{' '}
                      <span className="text-neon-cyan">{r.conservative.toFixed(1)}</span>
                    </span>
                  </div>
                  <div className="mt-2">
                    <CIBar mu={r.mu} sigma={r.sigma} domain={domain} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* progression chart */}
          <div className="lg:col-span-2">
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-sm font-semibold uppercase tracking-widest text-gray-400">
                Rating progression
              </h3>
              <SourceBadge source="demo" />
            </div>
            <div className="rounded-xl border border-charcoal-700 bg-charcoal-800/50 p-2">
              <ResponsiveContainer width="100%" height={210}>
                <LineChart data={DEMO_PROGRESSION} margin={{ top: 8, right: 8, bottom: 4, left: -18 }}>
                  <CartesianGrid stroke="#333333" strokeDasharray="3 3" />
                  <XAxis
                    dataKey="run"
                    tick={{ fill: '#9ca3af', fontSize: 9 }}
                    interval={0}
                    angle={-25}
                    textAnchor="end"
                    height={48}
                  />
                  <YAxis tick={{ fill: '#9ca3af', fontSize: 10 }} />
                  <Tooltip
                    contentStyle={{
                      background: '#252526',
                      border: '1px solid #333333',
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                    labelStyle={{ color: '#e5e7eb' }}
                  />
                  <Line type="monotone" dataKey="conservative" stroke="#22D3EE" strokeWidth={2} dot={{ r: 3 }} name="μ − 3σ" />
                  <Line type="monotone" dataKey="mu" stroke="#8B5CF6" strokeWidth={1.5} strokeDasharray="4 3" dot={false} name="μ" />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <p className="mt-2 text-[11px] text-gray-500">
              Conservative rating climbs as each validated layer is added. A per-run
              time-series API is a documented TODO; this trace uses representative values.
            </p>
          </div>
        </div>
      </div>
    </ScreenShell>
  );
};
