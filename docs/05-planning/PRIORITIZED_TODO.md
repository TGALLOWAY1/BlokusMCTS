# Prioritized TODO

> Ranked from [Backlog](BACKLOG.md). Last audited: 2026-05-28.
> Ready-to-run prompts for the top items: [Next Agent Tasks](NEXT_AGENT_TASKS.md).

| # | Task | Score | Category | Why now |
|---|---|---|---|---|
| 1 | Add MCTS-core unit tests (`tests/test_mcts_core.py`) | +7 | Quality | Untested heart of the project |
| 2 | Fix editable install / packaging (`pyproject.toml`) | +6 | DX | README quickstart is broken |
| 3 | Add CI workflow | +6 | Infra | Nothing enforces tests/lint/types |
| 4 | Combined best-of-all-layers tournament | +5 | Research | Natural headline experiment |
| 5 | Retire RL-era residue (name, `/training*`) | +4 | Clarity | Misleads readers/agents |
| 6 | Engine/browser mirror sync guard | +4 | Correctness | Prevents browser/arena divergence |
| 7 | Multi-seed 100+ game validation | +3 | Validity | Strengthen statistical claims |
| 8 | Expanded evaluator features (center_proximity) | +3 | Research | #1 RF feature has zero weight |
| 9 | Track `last_move` in GameManager | +2 | Feature | The one code TODO |
| 10 | Structured API error codes | +2 | API | Better client UX |
| 11 | Reduce learned-evaluator inference cost | +1 | Research (deferred) | Only with distillation |
| 12 | TD-UCT learning | +1 | Research (deferred) | Large, uncertain payoff |

**Suggested order:** do 1–3 together (tests + packaging + CI form a quality
foundation), then 4 (the headline experiment), then 5–6 (cleanup/correctness),
then research items 7–8.

Historical/experiment-level TODOs (Layers 0–10) are in the root
[`TODO.md`](../../TODO.md); most are marked done. The live operational plan is
[`docs/overnight_training_roadmap_2026-05-14.md`](../overnight_training_roadmap_2026-05-14.md).
