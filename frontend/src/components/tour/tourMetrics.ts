/**
 * Adapter layer between the live data hooks and the tour screens.
 *
 * Each adapter returns a `{ source: 'live' | 'demo', ... }` view model so screens
 * can render an honest badge. Nothing here blocks on the network: if a hook is
 * still loading, errored, or returns nothing, the adapter falls back to the
 * representative demo data in `tourData.ts`.
 */
import { useArenaLeaderboard } from '../../hooks/useArenaLeaderboard';
import { useChampion } from '../../hooks/useChampion';
import type { ChampionMetadata } from '../../utils/championConfig';
import { championIsPlayable } from '../../utils/championConfig';
import { DEMO_LEADERBOARD, type DemoLeaderboardRow } from './tourData';

export type MetricSource = 'live' | 'demo';

export interface LeaderboardView {
  source: MetricSource;
  isLoading: boolean;
  runId: string | null;
  rows: DemoLeaderboardRow[];
}

/**
 * Latest arena leaderboard, or representative demo rows when no run is
 * reachable (e.g. the static deploy build with no `/api`).
 */
export function useTourLeaderboard(): LeaderboardView {
  const { isLoading, agents, runId } = useArenaLeaderboard();

  if (!isLoading && agents.length > 0) {
    return {
      source: 'live',
      isLoading: false,
      runId,
      rows: agents.map((a) => ({
        agent_id: a.agent_id,
        type: a.type,
        mu: a.mu,
        sigma: a.sigma,
        conservative: a.conservative,
        rank: a.rank,
        games_played: a.games_played,
      })),
    };
  }

  return {
    source: 'demo',
    isLoading,
    runId: null,
    rows: DEMO_LEADERBOARD,
  };
}

export interface ChampionView {
  source: MetricSource;
  isLoading: boolean;
  /** Whether a live champion is actually playable right now. */
  playable: boolean;
  champion: ChampionMetadata | null;
  /** Friendly message when no live champion is available. */
  note: string | null;
}

/**
 * Champion metadata from the registry-backed endpoint, with a demo-friendly
 * fallback describing the registry's current provisional champion.
 */
export function useTourChampion(): ChampionView {
  const { isLoading, available, champion, error } = useChampion();

  if (!isLoading && available && champion) {
    return {
      source: 'live',
      isLoading: false,
      playable: championIsPlayable(champion),
      champion,
      note: null,
    };
  }

  return {
    source: 'demo',
    isLoading,
    playable: false,
    champion: {
      name: 'champion',
      version: 'v2',
      validationDate: null,
      totalGamesPlayed: null,
      winRate: null,
      trueSkill: 50.6,
      trueSkillConservative: 29.5,
      notes:
        'Provisional champion from the Layer 1–9 assessment: random rollout (cut at depth 5), ' +
        'RAVE (k=1000), progressive widening, and ML-calibrated evaluation weights.',
      agentConfig: null,
    },
    note: error,
  };
}
