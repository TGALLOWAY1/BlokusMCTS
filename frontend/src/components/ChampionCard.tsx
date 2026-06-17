import React from 'react';
import { type ChampionState } from '../hooks/useChampion';
import { championIsPlayable } from '../utils/championConfig';

const fmtPct = (v: number | null | undefined): string =>
  v === null || v === undefined ? '—' : `${(v * 100).toFixed(1)}%`;

const fmtNum = (v: number | null | undefined): string =>
  v === null || v === undefined ? '—' : v.toFixed(1);

const fmtDate = (v: string | null | undefined): string => {
  if (!v) return '—';
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? String(v) : d.toLocaleDateString();
};

interface ChampionCardProps {
  state: ChampionState;
  isCreating: boolean;
  onPlay: () => void;
}

/**
 * "Play the Champion" entry point for the public demo. Shows validation metadata
 * for the registry-backed champion and a Start button. Degrades gracefully when
 * no validated champion exists or the backend is unreachable.
 */
export const ChampionCard: React.FC<ChampionCardProps> = ({ state, isCreating, onPlay }) => {
  const { isLoading, available, error, champion } = state;
  const playable = available && championIsPlayable(champion);

  return (
    <div className="rounded-lg border border-neon-green/40 bg-neon-green/5 p-4 text-left">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-lg" aria-hidden>🏆</span>
        <span className="text-sm font-bold text-neon-green">Play the Champion</span>
      </div>

      {isLoading ? (
        <div className="text-xs text-gray-400 py-3">Loading champion…</div>
      ) : !available ? (
        <div className="text-xs text-gray-400 py-2">
          <p className="mb-2">
            No validated champion is available yet. Promote one with the gauntlet
            (<code className="text-gray-300">scripts/champion_gauntlet.py --promote</code>) to
            unlock this mode.
          </p>
          {error && <p className="text-gray-500 italic">{error}</p>}
        </div>
      ) : (
        <>
          <div className="flex items-baseline gap-2 mb-2">
            <span className="text-sm font-semibold text-gray-100 truncate">{champion?.name}</span>
            <span className="text-[10px] font-mono text-gray-500">{champion?.version}</span>
          </div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs mb-3">
            <Metric label="Win rate" value={fmtPct(champion?.winRate)} />
            <Metric label="TrueSkill μ" value={fmtNum(champion?.trueSkill)} />
            <Metric
              label="Validation games"
              value={champion?.totalGamesPlayed != null ? String(champion.totalGamesPlayed) : '—'}
            />
            <Metric label="Validated" value={fmtDate(champion?.validationDate)} />
          </div>
          {!playable && (
            <p className="text-[11px] text-yellow-400 mb-2">
              Champion metadata loaded, but its play config could not be resolved.
            </p>
          )}
          <button
            onClick={onPlay}
            disabled={isCreating || !playable}
            className={`w-full py-3 px-4 rounded-lg font-medium transition-colors duration-200 flex items-center justify-between ${
              isCreating || !playable
                ? 'bg-charcoal-700 text-gray-500 cursor-not-allowed'
                : 'bg-neon-green text-black hover:bg-neon-green/80'
            }`}
          >
            <span>{isCreating ? 'Starting…' : 'Play the Champion'}</span>
            <span className="text-xs opacity-70">You (Red) vs the validated champion</span>
          </button>
        </>
      )}
    </div>
  );
};

const Metric: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="flex flex-col">
    <span className="text-[10px] uppercase tracking-wider text-gray-500">{label}</span>
    <span className="text-gray-200 font-semibold tabular-nums">{value}</span>
  </div>
);
