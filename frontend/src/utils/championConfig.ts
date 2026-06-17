import {
  CHAMPION_DEFAULT_BUDGET_MS,
  CHAMPION_MAX_BUDGET_MS,
  CHAMPION_MIN_BUDGET_MS,
  CHAMPION_PROFILE,
} from '../constants/gameConstants';

/**
 * Browser-ready agent spec returned by GET /api/champion under `agentConfig`.
 * Resolved server-side from the champion registry so the in-browser (Pyodide)
 * worker can rebuild the exact validated agent.
 */
export interface ChampionAgentSpec {
  type: string; // 'mcts' | 'random' | 'heuristic'
  thinkingTimeMs: number | null;
  mcts?: Record<string, unknown>;
}

/** Metadata + browser config served by GET /api/champion. */
export interface ChampionMetadata {
  name: string;
  version: string;
  validationDate: string | null;
  totalGamesPlayed: number | null;
  winRate: number | null;
  trueSkill: number | null;
  trueSkillConservative?: number | null;
  thinkingTimeMs?: number | null;
  gauntletRunPath?: string | null;
  notes?: string;
  agentConfig?: ChampionAgentSpec | null;
}

const PLAYER_COLORS_ORDER = ['RED', 'BLUE', 'GREEN', 'YELLOW'] as const;
export type PlayerColor = (typeof PLAYER_COLORS_ORDER)[number];

const clampBudget = (raw: number | null | undefined): number => {
  const value = Number(raw);
  if (!Number.isFinite(value) || value <= 0) return CHAMPION_DEFAULT_BUDGET_MS;
  return Math.max(CHAMPION_MIN_BUDGET_MS, Math.min(CHAMPION_MAX_BUDGET_MS, Math.round(value)));
};

export interface BuildChampionGameConfigOptions {
  /** Seat the human plays (default RED). */
  humanPlayer?: PlayerColor;
  /** Override the champion per-move budget (ms). */
  budgetMs?: number;
  /** Scoring rule set; defaults to standard Blokus for public play. */
  scoringMode?: 'standard' | 'house';
}

export interface GameConfigSeat {
  player: PlayerColor;
  agent_type: 'human' | 'mcts';
  agent_config: Record<string, unknown>;
}

export interface ChampionGameConfig {
  players: GameConfigSeat[];
  auto_start: boolean;
  scoring_mode: 'standard' | 'house';
}

/**
 * Build a 4-player game config: the human plus three registry-backed champion
 * opponents. The champion's resolved browser spec is forwarded verbatim under
 * each AI seat's `agent_config.champion`, so the worker rebuilds the exact
 * validated agent. No champion config path is hardcoded here.
 */
export function buildChampionGameConfig(
  champion: ChampionMetadata,
  options: BuildChampionGameConfigOptions = {},
): ChampionGameConfig {
  const humanPlayer = options.humanPlayer ?? 'RED';
  const scoringMode = options.scoringMode ?? 'standard';
  const budgetMs = clampBudget(options.budgetMs ?? champion.agentConfig?.thinkingTimeMs);

  const aiSeat = (player: PlayerColor): GameConfigSeat => ({
    player,
    agent_type: 'mcts',
    agent_config: {
      profile: CHAMPION_PROFILE,
      time_budget_ms: budgetMs,
      // Forwarded registry-resolved spec used by the Pyodide worker.
      champion: champion.agentConfig ?? null,
    },
  });

  const players: GameConfigSeat[] = PLAYER_COLORS_ORDER.map((color) =>
    color === humanPlayer
      ? { player: color, agent_type: 'human', agent_config: {} }
      : aiSeat(color),
  );

  return {
    players,
    auto_start: true,
    scoring_mode: scoringMode,
  };
}

/** True when the API returned a champion that can actually be played in-browser. */
export function championIsPlayable(champion: ChampionMetadata | null): boolean {
  return Boolean(champion?.agentConfig);
}
