---
name: backtest-learning-loop
description: >
  Drives the Argus iterative learning loop. After every backtest run,
  invoke argus_learn.py to score, detect regressions, and generate
  hypotheses. Update skills/references/ when promoting a change.
---

# Backtest Learning Loop (v2)

## Quick Start
```bash
# 1. Run backtest
python backtest/run_backtest.py

# 2. Score + analyze
python skills/scripts/argus_learn.py --hypothesis

# 3. Register run in evidence memory
python skills/scripts/argus_learn.py --run

# 4. Optimize a strategy (if hypothesis generated)
python backtest/optimize.py StrategyName --params key=val

# 5. Run single-strategy to verify
python backtest/run_single.py --strategy StrategyName
```

## The Loop (5 Phases)

### Phase 1: Run Backtest
- `python backtest/run_backtest.py` — generates results.json + run_manifest.json
- Results saved to `docs/data/results.json` with portfolio + per-strategy metrics

### Phase 2: Score & Analyze
- `python skills/scripts/scoring.py` — composite 0-100 score per strategy and portfolio
- `python skills/scripts/argus_learn.py --hypothesis` — detect regressions + generate hypotheses
- Key signals:
  - Strategy turned from profitable to unprofitable (regression)
  - PF dropped >0.2 from previous run
  - Portfolio DD exceeded 10%

### Phase 3: Generate Hypothesis
For each underperformer, argus_learn.py generates:
- **Issue classification**: low_profit_factor, too_few_trades, high_drawdown
- **Hypothesis**: root cause analysis based on strategy type and data
- **Experiment command**: ready-to-run optimize.py command

### Phase 4: Run Experiment
- Run single-strategy optimization first: `python backtest/run_single.py`
- Then optimize: `python backtest/optimize.py ClassName --params key=val`
- Verify with portfolio: `python backtest/run_backtest.py`
- Run OOS: `python backtest/run_oos.py`
- **Promotion gates**: PF > 1.05, DD not increased, >=50 trades, OOS stable

### Phase 5: Encode Learning
- `python skills/scripts/argus_learn.py --run` — registers in evidence_memory.json
- Update `skills/references/results-history.md` with run details
- Update relevant strategy skill in `skills/strategy-*/SKILL.md`
- Add rejected experiments to `skills/references/rejected/` as "don't repeat"

## Evidence Hierarchy
```
skills/references/evidence_memory.json    — structured run database (machine-readable)
skills/references/results-history.md     — human-readable run log
skills/references/parameter-tuning-log.md — parameter change log
skills/strategy-*/SKILL.md               — per-strategy living playbooks
```

## Promotion Gates (MUST all pass)
1. Single-strategy PF > 1.05 (was < 1.0 before change)
2. Portfolio PF not decreased by > 0.05
3. Portfolio max DD not increased by > 2%
4. >= 50 trades for the modified strategy
5. OOS test: PF gap train/test <= 0.3, DD not double in test

## Key Principles
1. **One change at a time** — batch only after individual validation
2. **Record WHY** in the hypothesis, not just WHAT changed
3. **Skills evolve** — update existing skills, don't create new ones
4. **Failure is data** — log rejected experiments in evidence_memory.json
5. **Prefer ATR-based params** over fixed values for cross-symbol robustness
