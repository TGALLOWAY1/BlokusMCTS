import React from 'react';
import { GitBranch, Users, Brain, Shield } from 'lucide-react';
import { ScreenShell } from '../components/ScreenShell';
import type { ScreenProps } from './types';

/** A tiny fan-out tree: one root explodes into many futures, each into more. */
const BranchFan: React.FC = () => {
  const root: [number, number] = [10, 12];
  const mid = Array.from({ length: 6 }, (_, i) => [30 + i * 28, 60] as [number, number]);
  const leaves = mid.flatMap(([mx]) =>
    Array.from({ length: 4 }, (_, j) => [mx - 12 + j * 8, 108] as [number, number]),
  );
  return (
    <svg viewBox="0 0 180 120" className="h-auto w-full" role="img" aria-label="Search tree fanning out from one move into hundreds of futures">
      {mid.map(([mx, my], i) => (
        <line key={`r${i}`} x1={root[0]} y1={root[1]} x2={mx} y2={my} stroke="#3E3E42" strokeWidth={0.6} />
      ))}
      {mid.map(([mx, my], i) =>
        leaves
          .filter((_, j) => Math.floor(j / 4) === i)
          .map(([lx, ly], k) => (
            <line key={`m${i}-${k}`} x1={mx} y1={my} x2={lx} y2={ly} stroke="#2c2c2e" strokeWidth={0.4} />
          )),
      )}
      {leaves.map(([lx, ly], i) => (
        <circle key={`l${i}`} cx={lx} cy={ly} r={1.4} fill="#8B5CF6" opacity={0.7} />
      ))}
      {mid.map(([mx, my], i) => (
        <circle key={`mm${i}`} cx={mx} cy={my} r={2.4} fill="#00F0FF" />
      ))}
      <circle cx={root[0]} cy={root[1]} r={3.4} fill="#FF4D4D" />
    </svg>
  );
};

const CARDS = [
  {
    icon: <GitBranch size={18} />,
    accent: 'text-neon-red',
    title: 'Huge branching factor',
    body: 'Up to ~534 legal moves at the peak (around turn 17). A fixed search budget gets spread thin across hundreds of children.',
  },
  {
    icon: <Users size={18} />,
    accent: 'text-neon-blue',
    title: 'Four-player, non-stationary',
    body: 'Three opponents, not one. There is no clean minimax: incentives shift and king-making changes who you should fight.',
  },
  {
    icon: <Brain size={18} />,
    accent: 'text-neon-cyan',
    title: 'Long-horizon spatial planning',
    body: 'A piece placed now opens or closes corners forty moves later. Mobility is the currency, and it compounds.',
  },
  {
    icon: <Shield size={18} />,
    accent: 'text-neon-violet',
    title: 'Blocking & territory',
    body: 'Denying an opponent a corner can be worth more than your own placement. Depth is expensive, so where you spend it matters.',
  },
];

export const ScreenComplexity: React.FC<ScreenProps> = ({ stage, stepLabel }) => (
  <ScreenShell
    stage={stage}
    stepLabel={stepLabel}
    intro="Two-player chess-style search assumes one opponent and stable incentives. Four-player Blokus breaks every one of those assumptions — which is exactly what makes it a good search laboratory."
  >
    <div className="grid gap-6 lg:grid-cols-5">
      <div className="lg:col-span-2">
        <div className="rounded-2xl border border-charcoal-700 bg-charcoal-800/60 p-4">
          <BranchFan />
          <div className="mt-3 grid grid-cols-3 gap-2 text-center">
            <div>
              <div className="text-lg font-bold text-neon-red">534</div>
              <div className="text-[10px] uppercase tracking-widest text-gray-500">peak moves</div>
            </div>
            <div>
              <div className="text-lg font-bold text-neon-blue">3</div>
              <div className="text-[10px] uppercase tracking-widest text-gray-500">opponents</div>
            </div>
            <div>
              <div className="text-lg font-bold text-neon-violet">~84</div>
              <div className="text-[10px] uppercase tracking-widest text-gray-500">moves/game</div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:col-span-3">
        {CARDS.map((c, i) => (
          <div key={i} className="rounded-xl border border-charcoal-700 bg-charcoal-800/40 p-4">
            <span className={c.accent}>{c.icon}</span>
            <h3 className="mt-2 text-base font-bold text-white">{c.title}</h3>
            <p className="mt-1 text-sm leading-relaxed text-gray-400">{c.body}</p>
          </div>
        ))}
      </div>
    </div>
  </ScreenShell>
);
