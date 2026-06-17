/**
 * Static metadata + demo data for the tour.
 *
 * Stage definitions are data-driven: the progress rail, dots, counter, and nav
 * all derive from `TOUR_STAGES`. Demo data is drawn from real archived results
 * (`arena_runs/`, `data/champion_registry.json`, `KEY_FINDINGS.md`) so fallback
 * values are representative rather than invented — every demo block is clearly
 * badged as such in the UI.
 */
import {
  BookOpen,
  GitBranch,
  Cpu,
  Layers,
  FlaskConical,
  TrendingUp,
  Trophy,
  Gamepad2,
} from 'lucide-react';
import type { TourAccent, TourStage } from './tourTypes';

/* ------------------------------------------------------------------ */
/*  Stages                                                             */
/* ------------------------------------------------------------------ */

export const TOUR_STAGES: TourStage[] = [
  { id: 'rules', label: 'Rules', title: 'How Blokus works', icon: BookOpen, accent: 'cyan' },
  { id: 'complexity', label: 'Complexity', title: 'Why it is hard for AI', icon: GitBranch, accent: 'red' },
  { id: 'agents', label: 'Agents', title: 'The agents under test', icon: Cpu, accent: 'blue' },
  { id: 'techniques', label: 'Techniques', title: 'MCTS techniques explored', icon: Layers, accent: 'violet' },
  { id: 'evaluation', label: 'Evaluation', title: 'The evaluation harness', icon: FlaskConical, accent: 'cyan' },
  { id: 'trueskill', label: 'TrueSkill', title: 'Statistical validation', icon: TrendingUp, accent: 'blue' },
  { id: 'champion', label: 'Champion', title: 'Champion progression', icon: Trophy, accent: 'green' },
  { id: 'play', label: 'Play', title: 'Play the champion', icon: Gamepad2, accent: 'violet' },
];

/* ------------------------------------------------------------------ */
/*  Screen 3 — Agents (only agents that exist in the repo)             */
/* ------------------------------------------------------------------ */

export interface AgentCard {
  name: string;
  /** Maps to agents/<file>.py */
  type: string;
  accent: TourAccent;
  strategy: string;
  strengths: string[];
  weaknesses: string[];
  usedFor: string;
}

export const AGENT_CARDS: AgentCard[] = [
  {
    name: 'Random Agent',
    type: 'random_agent.py',
    accent: 'red',
    strategy: 'Picks uniformly at random from all legal moves.',
    strengths: ['Zero compute', 'Unbiased baseline', 'Fully reproducible with a seed'],
    weaknesses: ['No strategy', 'Loses to everything'],
    usedFor: 'The floor of the leaderboard — every other agent must beat it convincingly.',
  },
  {
    name: 'Heuristic Agent',
    type: 'heuristic_agent.py',
    accent: 'cyan',
    strategy: 'Hand-tuned preferences: play large pieces, create new corners, avoid edges early.',
    strengths: ['Instant moves', 'Surprisingly strong baseline', 'Interpretable'],
    weaknesses: ['No lookahead', 'Static — cannot adapt to opponents'],
    usedFor: 'The bar that search has to clear. Early naive MCTS actually lost to it.',
  },
  {
    name: 'MCTS Agent',
    type: 'mcts/mcts_agent.py',
    accent: 'violet',
    strategy: 'Monte Carlo Tree Search: Select → Expand → Simulate → Backpropagate, with a stack of optional enhancements.',
    strengths: ['Anytime search', 'Configurable depth/policy', 'Carries every technique layer'],
    weaknesses: ['Compute-hungry', 'Quality depends on the evaluator and budget'],
    usedFor: 'The research workhorse — the configurable subject of every experiment.',
  },
  {
    name: 'Champion Agent',
    type: 'agents/champion.py + registry',
    accent: 'green',
    strategy: 'The single best MCTS configuration promoted from the registry after validation.',
    strengths: ['Best validated config', 'RAVE + progressive widening + calibrated eval', 'Serves the public demo'],
    weaknesses: ['Only as good as the last gauntlet', 'Promotion gated on evidence'],
    usedFor: 'The opponent you face in "Play the Champion".',
  },
];

/* ------------------------------------------------------------------ */
/*  Screen 4 — Techniques (only techniques implemented in the repo)    */
/* ------------------------------------------------------------------ */

export interface TechniqueCard {
  id: string;
  name: string;
  /** Which MCTS phase / layer it touches. */
  phase: string;
  blurb: string;
  detail: string;
  /** Truthful verdict from KEY_FINDINGS — honest about what helped. */
  verdict: 'win' | 'mixed' | 'baseline';
}

export const TECHNIQUE_CARDS: TechniqueCard[] = [
  {
    id: 'uct',
    name: 'UCB1 / UCT Selection',
    phase: 'Selection',
    blurb: 'Balances exploiting strong moves vs. exploring uncertain ones.',
    detail:
      'The core tree-policy. Each node is scored Q + C·√(ln N / n); the exploration constant C (default 1.414) controls the trade-off. Everything else builds on this.',
    verdict: 'baseline',
  },
  {
    id: 'rave',
    name: 'RAVE',
    phase: 'Selection',
    blurb: 'Shares move value across sibling nodes to converge faster.',
    detail:
      'Rapid Action Value Estimation blends an all-moves-as-first estimate into UCB via β = √(k / (3N + k)). A major win: 50ms RAVE matched 200ms vanilla — ~4× convergence.',
    verdict: 'win',
  },
  {
    id: 'pw',
    name: 'Progressive Widening',
    phase: 'Expansion',
    blurb: 'Limits how many children a node opens as visits grow.',
    detail:
      'With branching up to ~534 moves, opening every child wastes the budget. Widening (allowed children ∝ N^α) constrains the tree and was the first big +win.',
    verdict: 'win',
  },
  {
    id: 'rollout',
    name: 'Rollout Policy',
    phase: 'Simulation',
    blurb: 'How simulated games are played out: random, heuristic, or two-ply.',
    detail:
      'Counter-intuitively, fast random rollouts (cut at depth 5) beat slower heuristic and two-ply playouts in this environment — extra bias hurt more than extra speed helped.',
    verdict: 'win',
  },
  {
    id: 'eval',
    name: 'State Evaluation',
    phase: 'Simulation',
    blurb: 'ML-calibrated feature weights score non-terminal positions.',
    detail:
      'Regression on 13,332 labeled states fixed three miscalibrations (including a sign error). Calibrated weights drove a 76% arena win rate vs. 12% for the defaults — the headline result.',
    verdict: 'win',
  },
  {
    id: 'minimax',
    name: 'Implicit Minimax Backups',
    phase: 'Backpropagation',
    blurb: 'Blends averaged returns with a minimax signal during backup.',
    detail:
      'A tunable α mixes standard averaging with implicit minimax values (Lanctot et al., 2014), sharpening tactical play in the multiplayer backup.',
    verdict: 'mixed',
  },
  {
    id: 'tt',
    name: 'Transposition Tables',
    phase: 'Tree',
    blurb: 'Reuses statistics for positions reached by different move orders.',
    detail:
      'Identical board states reached via different paths share a node, so search effort is not duplicated across transpositions.',
    verdict: 'baseline',
  },
  {
    id: 'opponent',
    name: 'Opponent Modeling',
    phase: 'Policy',
    blurb: 'Tracks blocking, alliances, and king-maker scenarios.',
    detail:
      'Per-opponent blocking rates flag targeting; late-game king-maker detection triggers defensive weight shifts. Activated correctly but cost more than it returned at real budgets.',
    verdict: 'mixed',
  },
  {
    id: 'parallel',
    name: 'Parallel Search',
    phase: 'Systems',
    blurb: 'Root-parallel multiprocessing (real speedup) vs. tree-parallel threads.',
    detail:
      'Root parallelization hit ~3.1× throughput at 4 workers. Tree parallelization with virtual loss is architecturally correct but GIL-limited (<10% WR) — multiprocessing wins in Python.',
    verdict: 'win',
  },
  {
    id: 'adaptive',
    name: 'Adaptive Meta-Control',
    phase: 'Meta',
    blurb: 'Branching-factor-aware exploration C and rollout depth.',
    detail:
      'Adaptive rollout depth (depth ∝ 80 / branching factor) gave 36% WR and 1.6× speedup. Stacking adaptive C on top of RAVE double-counted exploration and cratered to 8% — a useful negative result.',
    verdict: 'mixed',
  },
];

/* ------------------------------------------------------------------ */
/*  Screen 5/6 — Demo leaderboard (fallback for useArenaLeaderboard)   */
/*  Values mirror a representative champion-gauntlet arena summary.    */
/* ------------------------------------------------------------------ */

export interface DemoLeaderboardRow {
  agent_id: string;
  type: string;
  mu: number;
  sigma: number;
  conservative: number;
  rank: number;
  games_played: number;
}

export const DEMO_LEADERBOARD: DemoLeaderboardRow[] = [
  { agent_id: 'champion', type: 'mcts', mu: 50.6, sigma: 7.0, conservative: 29.5, rank: 1, games_played: 60 },
  { agent_id: 'mcts_rave_500ms', type: 'mcts', mu: 41.2, sigma: 6.8, conservative: 20.8, rank: 2, games_played: 60 },
  { agent_id: 'heuristic', type: 'heuristic', mu: 27.4, sigma: 6.5, conservative: 7.9, rank: 3, games_played: 60 },
  { agent_id: 'random', type: 'random', mu: 18.1, sigma: 6.9, conservative: -2.6, rank: 4, games_played: 60 },
];

/** Pairwise win-rate matrix (row beats column), demo values. */
export const DEMO_PAIRWISE: { agents: string[]; winRate: (number | null)[][] } = {
  agents: ['champion', 'mcts', 'heuristic', 'random'],
  winRate: [
    [null, 0.58, 0.74, 0.91],
    [0.42, null, 0.66, 0.85],
    [0.26, 0.34, null, 0.71],
    [0.09, 0.15, 0.29, null],
  ],
};

/* ------------------------------------------------------------------ */
/*  Screen 6 — TrueSkill progression (demo; no time-series API yet)    */
/* ------------------------------------------------------------------ */

export interface ProgressionPoint {
  run: string;
  /** Conservative TrueSkill (μ − 3σ) of the then-best agent. */
  conservative: number;
  mu: number;
}

export const DEMO_PROGRESSION: ProgressionPoint[] = [
  { run: 'L1 baseline', mu: 25.0, conservative: 8.2 },
  { run: 'L1 widening', mu: 31.5, conservative: 14.0 },
  { run: 'L4 eval', mu: 38.0, conservative: 19.5 },
  { run: 'L5 RAVE', mu: 43.1, conservative: 22.7 },
  { run: 'L8 parallel', mu: 47.0, conservative: 26.4 },
  { run: 'Champion v2', mu: 50.6, conservative: 29.5 },
];

/* ------------------------------------------------------------------ */
/*  Screen 7 — Champion progression / overnight runs (demo)           */
/* ------------------------------------------------------------------ */

export interface ChampionTimelineEntry {
  version: string;
  date: string;
  reason: string;
  status: 'promoted' | 'provisional';
}

export const DEMO_CHAMPION_TIMELINE: ChampionTimelineEntry[] = [
  {
    version: 'v1',
    date: '2026-04-29',
    reason: 'Initial champion — challenge config + Layer 9 adaptive rollout depth.',
    status: 'promoted',
  },
  {
    version: 'v2',
    date: '2026-06-17',
    reason: "Best agent from the Layer 1–9 assessment (random rollout + RAVE + calibrated eval).",
    status: 'provisional',
  },
];

export interface OvernightStep {
  label: string;
  detail: string;
}

export const OVERNIGHT_PIPELINE: OvernightStep[] = [
  { label: 'Generate candidates', detail: 'Vary one knob at a time from the current champion config.' },
  { label: 'Run overnight tournaments', detail: 'Seeded 4-player round-robins, every agent in every seat.' },
  { label: 'Aggregate results', detail: 'TrueSkill (μ, σ), win rates, score stats, pairwise records.' },
  { label: 'Compare to baseline', detail: 'Conservative rating + seat-bias-corrected significance tests.' },
  { label: 'Promote only on evidence', detail: 'A candidate becomes champion only if it clears the gauntlet.' },
];
