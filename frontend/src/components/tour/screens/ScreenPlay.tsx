import React from 'react';
import { Link } from 'react-router-dom';
import { Gamepad2, Crown, Info, BarChart3 } from 'lucide-react';
import { ScreenShell } from '../components/ScreenShell';
import { SourceBadge } from '../components/SourceBadge';
import { useTourChampion } from '../tourMetrics';
import type { ScreenProps } from './types';

export const ScreenPlay: React.FC<ScreenProps> = ({ stage, stepLabel, onComplete }) => {
  const champ = useTourChampion();
  const meta = champ.champion;

  return (
    <ScreenShell
      stage={stage}
      stepLabel={stepLabel}
      intro="That is the whole pipeline: teach the game, study the search, evaluate rigorously, and promote a validated champion. Now play it yourself — three champion opponents, right in your browser."
    >
      <div className="grid gap-5 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <div className="rounded-2xl border border-neon-violet/30 bg-gradient-to-b from-charcoal-800/80 to-charcoal-900 p-6">
            <div className="flex items-center gap-2">
              <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-neon-green/15 text-neon-green">
                <Crown size={20} />
              </span>
              <div>
                <div className="text-xs uppercase tracking-widest text-gray-500">The opponent</div>
                <div className="text-lg font-bold text-white">
                  Champion {meta?.version ?? ''}
                </div>
              </div>
              <span className="ml-auto">
                <SourceBadge source={champ.source} />
              </span>
            </div>

            <p className="mt-4 text-sm leading-relaxed text-gray-300">
              The champion runs entirely in-browser via Pyodide — no server search required.
              You take one seat; the validated MCTS agent takes the other three.
            </p>

            <div className="mt-5 flex flex-wrap gap-3">
              <Link
                to="/play"
                onClick={onComplete}
                className="inline-flex items-center gap-2 rounded-full border border-neon-green bg-neon-green/15 px-6 py-3 text-sm font-bold text-neon-green transition-transform hover:scale-105 active:scale-95"
              >
                <Gamepad2 size={16} /> Play the Champion
              </Link>
              <Link
                to="/story"
                onClick={onComplete}
                className="inline-flex items-center gap-2 rounded-full border border-charcoal-600 px-6 py-3 text-sm font-semibold text-gray-300 transition-colors hover:border-neon-blue hover:text-neon-blue"
              >
                <BarChart3 size={16} /> Read the full story
              </Link>
            </div>
          </div>
        </div>

        <div className="lg:col-span-2 space-y-3">
          <div className="rounded-xl border border-charcoal-700 bg-charcoal-800/50 p-4">
            <h3 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-widest text-gray-400">
              <Info size={14} className="text-neon-cyan" /> Good to know
            </h3>
            <ul className="mt-2 space-y-2 text-sm text-gray-400">
              <li>· Standard Blokus scoring — squares placed, bonuses for finishing.</li>
              <li>· The champion thinks within a snappy per-move budget so play stays responsive.</li>
              <li>· It is anytime search: more time would mean stronger play.</li>
            </ul>
          </div>
          {champ.source === 'demo' && champ.note && (
            <p className="rounded-lg border border-charcoal-700 bg-charcoal-800/40 p-3 text-xs text-gray-500">
              Live champion service not reachable from the tour right now ({champ.note}).
              The Play page resolves the champion from the registry when you open it.
            </p>
          )}
        </div>
      </div>
    </ScreenShell>
  );
};
