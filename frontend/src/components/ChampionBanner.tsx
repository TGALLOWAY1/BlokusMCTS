import React from 'react';
import { useGameStore } from '../store/gameStore';

const fmtPct = (v: number | null | undefined): string =>
  v === null || v === undefined ? '—' : `${(v * 100).toFixed(1)}%`;

const fmtNum = (v: number | null | undefined, digits = 1): string =>
  v === null || v === undefined ? '—' : v.toFixed(digits);

const fmtDate = (v: string | null | undefined): string => {
  if (!v) return '—';
  const d = new Date(v);
  return Number.isNaN(d.getTime()) ? String(v) : d.toLocaleDateString();
};

interface StatProps {
  label: string;
  value: string;
  title?: string;
}

const Stat: React.FC<StatProps> = ({ label, value, title }) => (
  <div className="flex flex-col" title={title}>
    <span className="text-[10px] uppercase tracking-wider text-gray-500">{label}</span>
    <span className="text-sm font-semibold text-gray-100 tabular-nums">{value}</span>
  </div>
);

/**
 * Public "Play the Champion" banner. Renders champion validation metadata
 * (name, validation date, win rate, TrueSkill, total games), the active scoring
 * mode, and a live "thinking" indicator while the champion searches.
 *
 * Only renders when the current game was started against the registry-backed
 * champion (i.e. `championMeta` is set in the store).
 */
export const ChampionBanner: React.FC = () => {
  const champion = useGameStore((s) => s.championMeta);
  const gameState = useGameStore((s) => s.gameState);
  const isAdvancing = useGameStore((s) => s.isAdvancingTurn);

  if (!champion) return null;

  const currentPlayer = gameState?.current_player;
  const players = gameState?.players;
  const currentIsChampion =
    !!players && players.find((p) => p.player === currentPlayer)?.agent_type !== 'human';
  const thinking = currentIsChampion && isAdvancing && !gameState?.game_over;

  const scoringMode = gameState?.scoring_mode ?? 'standard';
  const stats = gameState?.mcts_stats;

  return (
    <div className="w-full mb-3 rounded-lg border border-neon-green/40 bg-neon-green/5 px-4 py-3">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-lg" aria-hidden>🏆</span>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-neon-green truncate">
                {champion.name}
              </span>
              <span className="text-[10px] text-gray-500 font-mono">{champion.version}</span>
            </div>
            <div className="text-[11px] text-gray-400">Validated Blokus champion</div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
          <Stat label="Win rate" value={fmtPct(champion.winRate)} title="Gauntlet average win rate" />
          <Stat label="TrueSkill μ" value={fmtNum(champion.trueSkill)} title="TrueSkill rating (mu)" />
          <Stat
            label="Games"
            value={champion.totalGamesPlayed != null ? String(champion.totalGamesPlayed) : '—'}
            title="Total validation games played"
          />
          <Stat label="Validated" value={fmtDate(champion.validationDate)} />
        </div>

        <div className="flex items-center gap-2 ml-auto">
          <span
            className="text-[10px] uppercase tracking-wider px-2 py-1 rounded border border-charcoal-600 text-gray-300"
            title="Scoring rule set in effect for this game"
          >
            {scoringMode === 'house' ? 'House scoring' : 'Standard scoring'}
          </span>
          {thinking ? (
            <span className="flex items-center gap-1.5 text-xs text-neon-green">
              <span className="inline-block w-2 h-2 rounded-full bg-neon-green animate-pulse" />
              Champion thinking…
            </span>
          ) : null}
        </div>
      </div>

      {/* Lightweight diagnostics from the champion's most recent search. */}
      {stats && (stats.iterations_run || stats.nodesEvaluated || stats.timeSpentMs) ? (
        <div className="mt-2 pt-2 border-t border-neon-green/15 flex flex-wrap gap-x-5 gap-y-1 text-[11px] text-gray-400">
          {stats.timeSpentMs != null && (
            <span title="Wall-clock time the champion searched on its last move">
              ⏱ {(stats.timeSpentMs / 1000).toFixed(2)}s
            </span>
          )}
          {(stats.iterations_run ?? stats.nodesEvaluated) != null && (
            <span title="MCTS simulations run on the last move">
              🔁 {(stats.iterations_run ?? stats.nodesEvaluated)!.toLocaleString()} sims
            </span>
          )}
          {stats.maxDepthReached != null && stats.maxDepthReached > 0 && (
            <span title="Maximum search-tree depth reached">▽ depth {stats.maxDepthReached}</span>
          )}
          {typeof stats.budgetTier === 'string' && (
            <span title="Adaptive search budget tier">tier: {stats.budgetTier}</span>
          )}
        </div>
      ) : null}
    </div>
  );
};
