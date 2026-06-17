import { describe, it, expect } from 'vitest';
import {
  buildChampionGameConfig,
  championIsPlayable,
  type ChampionMetadata,
} from '../championConfig';

const champion: ChampionMetadata = {
  name: 'demo_champ',
  version: 'v2',
  validationDate: '2026-06-17',
  totalGamesPlayed: 200,
  winRate: 0.51,
  trueSkill: 28.3,
  thinkingTimeMs: 800,
  agentConfig: {
    type: 'mcts',
    thinkingTimeMs: 800,
    mcts: { rollout_policy: 'random', iterations: 400 },
  },
};

const aiSeats = (cfg: ReturnType<typeof buildChampionGameConfig>) =>
  cfg.players.filter((p) => p.agent_type === 'mcts');
const humanSeats = (cfg: ReturnType<typeof buildChampionGameConfig>) =>
  cfg.players.filter((p) => p.agent_type === 'human');

describe('buildChampionGameConfig', () => {
  it('builds 1 human + 3 champion seats forwarding the resolved spec', () => {
    const cfg = buildChampionGameConfig(champion);
    expect(cfg.players).toHaveLength(4);

    const human = humanSeats(cfg);
    const ai = aiSeats(cfg);
    expect(human).toHaveLength(1);
    expect(human[0].player).toBe('RED');
    expect(ai).toHaveLength(3);

    for (const seat of ai) {
      expect(seat.agent_config.profile).toBe('champion');
      // The exact registry-resolved spec is forwarded for the worker to rebuild.
      expect(seat.agent_config.champion).toEqual(champion.agentConfig);
      expect(seat.agent_config.time_budget_ms).toBe(800);
    }
  });

  it('defaults to standard scoring for public play', () => {
    const cfg = buildChampionGameConfig(champion);
    expect(cfg.scoring_mode).toBe('standard');
    expect(cfg.auto_start).toBe(true);
  });

  it('clamps the champion budget into the responsive demo range', () => {
    const slow = buildChampionGameConfig(champion, { budgetMs: 999999 });
    expect(aiSeats(slow)[0].agent_config.time_budget_ms).toBe(4000);

    const fast = buildChampionGameConfig(champion, { budgetMs: 1 });
    expect(aiSeats(fast)[0].agent_config.time_budget_ms).toBe(200);
  });

  it('honors a custom human seat', () => {
    const cfg = buildChampionGameConfig(champion, { humanPlayer: 'BLUE' });
    expect(humanSeats(cfg)[0].player).toBe('BLUE');
  });
});

describe('championIsPlayable', () => {
  it('is true only when an agentConfig is present', () => {
    expect(championIsPlayable(champion)).toBe(true);
    expect(championIsPlayable({ ...champion, agentConfig: null })).toBe(false);
    expect(championIsPlayable(null)).toBe(false);
  });
});
