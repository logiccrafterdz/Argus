---
name: backtest-learning-loop
description: >
  Guides the iterative learning loop for this project: run backtest → analyze
  results → create/update skills → apply improvements → repeat. Use this
  skill whenever starting a new iteration of backtesting or after reviewing
  backtest results to encode what was learned.
---

# Backtest Learning Loop

## When to Use This Skill

- At the start of every new backtest cycle
- After reviewing backtest results to encode lessons learned
- When deciding what to improve next in the strategy portfolio
- Before making changes to strategy parameters or risk rules

## The Loop (4 Phases)

### Phase 1: Run Backtest

Execute `python backtest/run_backtest.py` to get fresh results.

### Phase 2: Analyze Results

Read `docs/data/results.json` and extract:
- **Portfolio-level**: net_profit, max_drawdown, win_rate, profit_factor, monthly_returns, drawdown_curve
- **Per-strategy**: trades, net_profit, win_rate, profit_factor, max_drawdown (from backtest_run.log or strategy detail output)
- **Key observations**:
  - Which strategies lost the most?
  - Which strategies won?
  - When did the drawdown start? What market regime was active?
  - Is there a correlation between losing strategies?

### Phase 3: Encode Learnings (this is critical)

For each finding:

1. **Create or update a skill** in `skills/` that captures what was learned
2. **Record the result** in `skills/references/results-history.md` with date, commit hash, and key metrics
3. **Document parameter changes** in `skills/references/parameter-tuning-log.md`

Skills must be:
- **Actionable**: they should guide what to do next, not just describe what happened
- **Specific**: include exact parameter values, thresholds, and conditions
- **Evolving**: update existing skills rather than creating new ones for the same topic

### Phase 4: Apply Improvements

Based on the skills:

1. Modify strategy parameters in `backtest/strategies/*.py`
2. Modify risk/portfolio logic in `backtest/engine.py` or `backtest/risk_manager.py`
3. Update config values in `backtest/config.py` if needed
4. Run unit tests: `python -m pytest tests/ -v`
5. Commit changes before running the next backtest

## History of Learnings (Updated Each Cycle)

See `skills/references/results-history.md` for the full backtest log.
See `skills/references/parameter-tuning-log.md` for all parameter changes.

## Key Principles

1. **One change at a time** when possible, or batch similar changes with clear reasoning
2. **Record WHY** a change was made, not just WHAT changed
3. **Skills evolve** — update them as you learn more
4. **If something doesn't work**, document why and try a different approach
5. **Portfolio-level fixes first** — if all strategies lose during the same period, the problem is systemic, not per-strategy
6. **Prefer ATR-based parameters** over fixed values for robustness across symbols
