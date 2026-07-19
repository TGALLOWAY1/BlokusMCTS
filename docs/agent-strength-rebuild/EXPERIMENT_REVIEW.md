# Experiment Review — Agent-Strength Rescue, EXP-000 … EXP-013

_Written 2026-07-18 (after PR #207 merged; PR #208 open). Purpose: a single
self-contained account of every experiment run under the rescue program — rationale,
setup, results, and conclusions — so an outside reviewer (human or agent) can assess
the work and give concrete guidance on direction. Full per-experiment records with
reproduce commands live in `EXPERIMENT_LOG.md`; decisions in `DECISIONS.md`._

---

## 1. Context and objective

This repo is a 4-player Blokus AI lab: engine (`engine/`), one canonical MCTS agent
(`mcts/mcts_agent.py`, maxⁿ with per-player reward vectors), a seeded arena, and a
(now frozen) nightly training pipeline. Before the rescue, the system had gone **39
generations without a champion promotion** — every nightly candidate lost to the
gen140 champion. The rescue's governing rule: stop asking "did Elo go up?" and
instead find, with controlled experiments and pre-registered decision rules, **where
compute and learning actually convert into strength** — and never ship anything that
hasn't passed its gate.

Ground rules that shaped everything below:

- **Standard Blokus scoring** is the target ruleset (D-002; implemented + tested in
  Phase 2, including the +5 monomino-last bonus).
- **Fixed benchmark protocol** (`rescue_v2`): pinned iteration budgets (never time
  budgets), round-robin seat rotation, fixed seeds, Wilson CIs, TrueSkill, and paired
  sign-flip permutation tests as the primary strength statistic.
- **Pre-registration**: every experiment's hypothesis and decision rule is recorded
  in `EXPERIMENT_LOG.md` at launch, before results exist. §20 of the master prompt
  forbids "default escapes" (more games / more data / more hyperparameters / treating
  lower loss as strength) as responses to a failed gate — a failed gate gets the
  *smallest distinguishing experiment* instead.
- **The champion is untouched** throughout. Nothing below changed any production
  config; all learned components are opt-in.

The foundations were validated before any experiment: engine correctness (property
suite + ~6,000-position reference↔optimized differential checks, zero disagreements),
versioned state/action schemas (`board_state_v1`, `move_v1`), and minimal-search
semantics (a rollout reward-baseline bug — leaf-baseline deltas erasing sibling
immediate-gain differences — was found and fixed here, D-014; this bug alone
plausibly contributed to the historical plateau).

## 2. Baseline (EXP-000)

Snapshot of the frozen system, no new games: champion gen140 at Elo 1388.55
(TrueSkill μ 54.39, σ 5.02), 6,290 cumulative games, 39-generation promotion
drought. All recent candidates *lost* to the champion by 60–117 Elo — the plateau
was real, not a detection-power problem. This motivated diagnosing the
search/evaluation stack rather than iterating the nightly loop harder.

## 3. Chain 1 — Does search scale at all? (EXP-001 → 002 → 003)

**EXP-001 (scaling ladder, 50/150/500 iterations + heuristic anchor, 24 games).**
Hypothesis: with the reward-baseline fix, more iterations → stronger play.
**Result: FAIL — 500 iterations trended *worse* than 50/150.** Mechanistic probe at
branching-factor-325/385 positions: below the branching factor every expanded child
has exactly one visit, so max-visits selection ties and the agent just plays the
move-ordering heuristic's top move; above it, revisits (3–7 visits) follow
single-rollout noise. "Search" was either the ordering heuristic or noise-following.
This also explained the training plateau: nightly budgets (50–250 iters) cannot
express evaluator improvements.

**EXP-002 (same ladder + progressive widening, one variable changed).** PW
(pw_c=2.0, α=0.5) concentrated visits as predicted (best child 23% visit share vs
0.6%; depth 4 vs 2) and **raised absolute strength** — every rung now beat the
anchor at p ≤ 0.0006 (EXP-001's 500-rung was p=0.22). **But the scaling curve stayed
flat** (50 ≈ 150 ≈ 500). Tree shape fixed; remaining suspect: the value signal.

**EXP-003 (same PW ladder, rollouts replaced by pure static-eval leaves).**
Discriminating design: if noise was the blocker, deterministic leaves restore
scaling; if the static evaluator is uninformative, the curve stays flat and the
margin over the anchor should collapse. **Result: decisive outcome B — the entire
+11..+16-point margin over the heuristic anchor vanished** (all comparisons ≈ 0).
The Layer-6 static evaluator's root-Q spread is ~1.3 points on a ~47-point scale —
it contributes nothing beyond the move-ordering prior. Rollouts carried *all* the
value signal, but are too noisy to convert extra visits into strength.

**Chain-1 conclusion (attribution complete):** search mechanics exonerated; PW
necessary but insufficient; **leaf-evaluation quality is the binding ceiling.**

## 4. Chain 2 — A learned value evaluator (EXP-004 → 005 → 006a/b → 007)

**EXP-004 (model training, fresh data).** New manifested dataset
`value_dataset_v1` (17,408 rows / 60 games of standard-scored PW-50 self-play, rich
45-feature `rich_blokus_v1` extraction, game-level split). Ridge vs HistGB vs MLP on
final-score prediction: ridge won on every metric (held-out R² 0.264, pairwise
ordering 0.682); non-linear models added nothing. **Finding: capacity is not the
bottleneck — the 45-feature representation saturates**, at R²≈0.26 and pairwise
≈0.68. (This ~0.68 number recurs throughout.) In-tree probe: ridge leaves give root-Q
spread 4.6–6.3 points vs Layer-6's 1.3 — a real discriminator.

**EXP-005 (ridge as leaf evaluator, PW ladder 50/150/500, 24 games).** **First
positive scaling signal of the whole investigation**: avg rank monotone in budget
(2.12 → 1.83 → 1.75), 10× budget pair +5.71 pts at p=0.054, anchor shut out (0%
first places) with larger margins than the rollout ladder at every rung.

**EXP-006a (direct same-table model-500 vs rollout-500, 20 games).** The clean
equal-budget test: **parity** (+2.40 pts for model leaves, p=0.556). Model leaves
are not stronger *today* — they were adopted (D-016) on scaling + trainability
grounds (deterministic, TT-cacheable, improvable through the loop; rollouts are
none of these).

**EXP-006b (model-leaf ladder 150/500/1500, 12 games).** 150→500 = **+14.08 pts,
p=0.013** — the first conventionally significant budget pair; 1500 ≈ 500. **Knee at
~500 → teacher budget 500 iterations (D-008). Phase 4 gate: PASS** for the
PW+model-leaf configuration.

**EXP-007 (gate C, first loop turn: retrained v2 evaluator vs v1 at equal budget).**
Teacher pipeline (Phase 7) had produced `teacher_dataset_v1`: 1,309 full-state
`teacher_record_v2` records / 18 games at the 500-iteration teacher budget, with
per-child visit counts and Q values, engine-level validated. Training half:
**v2_mixed fixes v1's severe miscalibration on the stronger teacher distribution
(v1 R² = −0.384 on teacher play!) — PASS.** Arena half: vm2 57.5% vs vm1 42.5%
first places, but paired diff only +2.25 pts, p=0.596 — **PARTIAL**. Ordering
quality barely moved (0.658 → 0.678 pairwise): calibration transfers, ordering
doesn't, because ordering is pinned at the **~0.68 feature ceiling**.

**Chain-2 conclusion:** the loop mechanically works (better data → better-calibrated
evaluator → no regression, slight positive trend), but per-generation gains are
capped by the state-feature representation, not by data, model family, or budget.

## 5. Chain 3 — Attack the representation with features (EXP-008 → 009)

**EXP-008 (six new contested/exclusive-territory features, `rich_blokus_v2`).**
Feature-set-controlled comparison on identical splits: 51 vs 45 features =
0.619 vs 0.615 pairwise — **+0.004, nothing.** But the best condition (mixed, 0.678)
was fueled by the 17k feature-only v1 rows that *cannot* receive new features (no
stored states) — representation and state-carrying data volume were confounded.

**EXP-009 (v2 features at state-carrying volume).** Generated `value_dataset_v2`:
7,208 full-state teacher-format records / 100 games at the cheap PW-50 budget
(~2 h). Retrained with feature-set control at ~33k state-carrying rows (6.5× more):
volume_full (51 feats) 0.655 vs volume_45 0.651 — **still +0.004. The feature
block's null result is a genuine representation failure, not data starvation.**
Bonus negative: the bulk corpus *underperforms* value_dataset_v1 as training data
(all volume conditions < mixed_45's 0.678) — its games open with τ=1.0 visit
sampling, making early-state final scores noisier labels. **Volume of the wrong
distribution is negative signal.** Bar (decisively > 0.68) not met; per the
pre-registered rule, pivot to the move-level candidate-scoring evaluator.

## 6. Chain 4 — A learned move policy (EXP-010 → 011 → 012 → 013)

Architecture decision D-017: listwise softmax candidate scorer distilling **teacher
root visit distributions** (the search's own improved policy), consumed via the
agent's existing `policy_prior` slot (PUCT prior + move ordering), replacing the
legacy 4-feature log-linear artifact (top-1 0.53, self-distilled from heuristic
play). Metrics: tie-aware top-1 agreement with the teacher's move (ties in visit
maxima count as correct — a review fix worth ~+0.01) and within-decision pairwise
ordering vs visit counts, on held-out 500-iteration teacher decisions (n=285),
against two baselines: the fixed heuristic and the legacy artifact.

**EXP-010 (listwise linear scorer, 4 vs 10 engineered move features).**
Distillation lifted pairwise (+0.04) but **top-1 did not move** (0.140 trained vs
0.140 heuristic), and the 6 feature extensions added nothing (third strike for
hand-crafted features after EXP-008/009). Decisive attribution: the model scores
**0.165 top-1 on its own 200 training decisions** — train ≈ held-out everywhere. A
linear model over cheap geometric features cannot even *fit* the teacher's choices.
**Capacity-bound.**

**EXP-011 (shape-aware numpy MLP, `move_encoding_v1`).** Encoding: 9×9 six-channel
board patch centered on the placement (own/opponent/off-board/new-piece/own-frontier/
opponent-frontier) + piece one-hot + the 10 scalars = 518 inputs → 64 tanh → 1 logit
per candidate, same listwise objective. Three results:
1. **Capacity confirmed**: 0.930–0.945 top-1 memorizing 200 decisions at adequate
   optimization budget.
2. **Bulk data poisons policy distillation** (controlled pair, data the only
   variable): teacher-only (1,003 decisions) → **0.228 / 0.744**; mixed (6,337) →
   0.151 / 0.637. PW-50 visit distributions are a different, noisier policy — the
   policy-side twin of EXP-009's label-noise finding.
3. **Teacher-only clears the pre-registered bars decisively and seed-robustly**:
   top-1 0.196–0.228 vs 0.140/0.133, pairwise 0.742–0.744 vs 0.591/0.596 across
   three seeds. First Phase 6 candidate past the training gates. Production wiring
   built and tested (`mcts/move_encoding.py`, `mcts/move_policy_mlp.py`, agent
   artifact dispatch, arena `policy_weights_path`; 10 wiring tests).

**EXP-012 (search integration: D-016 agent ± MLP PUCT prior at c=1.5, 2×2
same-table, 500 iters, 20 games).** **NEGATIVE — the prior *hurts*:** prior agents
4 first-places / avg rank 2.80 vs base 16 / 2.00; paired per-game **−20.6 pts,
exact permutation p=0.048.** No-games diagnostic: the MLP prior is 3× sharper than
the heuristic prior (top-move mass 0.227 vs 0.071, normalized entropy 0.817 vs
0.984) — distilled from *completed* 500-iteration visit counts, it over-commits a
*fresh* search and starves exploration (no root Dirichlet noise in this agent).

**EXP-013 (calibration corrective: temperature 3.0 flattens the prior to the
heuristic's entropy while preserving ranking; single variable; same table).**
**NEGATIVE, more decisive: −29.1 pts, p=0.0011** (softprior 4 vs 16 first places).
And a wiring insight that reframes both runs: temperature scales only the PUCT
prior *probabilities*; progressive-widening **move-expansion ordering uses the raw
logit** and is temperature-independent. EXP-012 and EXP-013 therefore ran the
*identical* MLP-driven expansion order and both lost decisively → **the invariant
suspect is the MLP ordering deciding which moves ever enter the tree.** Under PW
(⌈2√N⌉ children), a ranking optimized to predict the teacher's *final* move expands
the exploitation candidate first and never widens to the moves a fresh search needs
to evaluate. "Predict the completed search's choice" is the wrong objective for
"decide what to explore now."

**Chain-4 conclusion:** the policy is a validated *predictor* and a refuted *search
guide* in this integration. Per the pre-registered rule, policy-as-search-guide is
**paused at the gate**. Note the asymmetry: EXP-012/013 tested prior + ordering
together (ordering never isolated) — a policy-as-prior-only test with the default
heuristic ordering has *not* been run.

## 7. Cross-cutting findings

1. **The ~0.68 pairwise-ordering ceiling of the 45-feature state representation is
   the single most-confirmed fact in the program** (EXP-004, 007, 008, 009 —
   different models, data mixes, and volumes all converge on it).
2. **Distribution beats volume, twice.** PW-50 self-play data actively hurt both
   value calibration-transfer (EXP-009) and policy distillation (EXP-011). The only
   data that moved anything was 500-iteration teacher data — of which only 18 games
   / 1,288 decisions exist.
3. **Training metrics do not predict in-search strength.** EXP-011's decisive
   training win became EXP-012/013's decisive in-search loss. Any future learned
   component must pass an arena integration test before any adoption claim.
4. **The gate discipline worked.** Ten of thirteen experiments were negatives or
   partials, each costing hours not weeks, each narrowing the hypothesis space:
   tree shape → value signal → evaluator → representation → data volume → model
   capacity → data distribution → prior calibration → expansion ordering. Zero
   arena compute was spent on unvalidated training claims; the champion was never
   touched.
5. **Infrastructure realities:** the session container restarts roughly daily and
   kills long runs (three arena runs lost mid-flight). Mitigations now standard:
   per-seed processes, pinned seeds (partial runs replay identically), `--resume`
   with config-mismatch guards on the data generator, packed immutable datasets
   (`records.jsonl.gz` + sha256 lineage).

## 8. Current asset state

| Asset | Status |
|---|---|
| Engine + standard scoring + schemas | Validated (Phase 2 PASS); differential-tested |
| Minimal search + maxⁿ semantics | Validated (Phase 3 PASS); reward-baseline bug fixed (D-014) |
| **D-016 experimental baseline**: minimal search + PW(2.0/0.5) + v1 ridge leaves, teacher budget 500 (D-008) | **The strongest validated configuration.** Phase 4 PASS. Not promoted to champion (Phase 9 gate only) |
| v2_mixed value evaluator (teacher-retrained) | Best evaluator artifact; better calibrated than v1, ordering unchanged; not promoted |
| `move_policy_v2` MLP (encoding, policy class, arena wiring, tests) | Committed, correct, **opt-in and unused by defaults** — refuted as a search guide in its current integration |
| Datasets: `value_dataset_v1` (17.4k rows), `teacher_dataset_v1` (1,309 records), `value_dataset_v2` (7,208 records) | Immutable, manifested, sha256-registered, packed |
| Champion gen140 + nightly pipeline | Untouched; frozen since Phase 0 |

## 9. The open decision — candidate paths forward

The learned-evaluator track has hit a confirmed wall on both axes at the current
data scale. Four candidate directions, with the evidence for and against each:

**(a) One more isolation arena: policy as PUCT-prior-only, default heuristic PW
ordering.** For: EXP-012/013 never separated ordering from prior; this closes the
diagnosis for one ~4–6 h run and would tell us whether the trained policy has *any*
safe insertion point. Against: even a positive result yields at most a small gain
given the prior was the weaker suspect.

**(b) Pivot to Phase 9 (champion/league).** For: D-016 + the v2 evaluator is a
complete, validated stack that has never been tested against the gen140 champion;
the dual-registry split (D-009) needs resolving regardless; this is where durable
user-visible progress is available now. Against: leaves the Phase 6/8 learning-loop
question dormant (though documented for clean resumption).

**(c) Retarget the policy objective** (train toward exploration-useful targets —
e.g., soft value/regret over candidates rather than final-move argmax; or use the
policy only for late-position pruning). For: directly addresses the diagnosed
objective mismatch. Against: research-grade uncertainty; still starving at 1,288
teacher decisions.

**(d) Scale 500-iteration teacher data first** (the one confirmed-positive lever;
~14 min/game → 100 games ≈ 24 h of compute across restarts). For: every positive
learning result traced to this data; 10× more supports (b)'s evaluator *and* any
future (c). Against: §20 warns against "more data" as a default escape — it is only
justified *after* an objective/integration design exists that the current data
provably starves.

The author's recommendation on record: **(b)**, with (a) as an optional cheap
close-out first, and (d) folded in only once a consumer for the data is committed.

## 10. Reproducibility

Every experiment: exact reproduce command in `EXPERIMENT_LOG.md`; run records in
`training/reports/experiments/search_scaling/<label>/` (games.jsonl per seed +
report.json); artifacts in `training/artifacts/`; dataset lineage + hashes in
`DATA_LINEAGE.md`; decisions D-001…D-017 in `DECISIONS.md`; per-phase gate verdicts
in `phases/`. Protocol: `BENCHMARK_PROTOCOL.md` (rescue_v2).
