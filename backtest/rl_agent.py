"""
Reinforcement Learning Agent for dynamic TP/SL adjustment.

Uses a contextual bandit approach (no full RL training pipeline):
  - State: volatility regime, trend strength, position duration, recent PnL
  - Action: select from discrete {tp_mult, sl_mult} pairs
  - Reward: risk-adjusted return of the completed trade

The agent learns online via epsilon-greedy exploration with reward tracking.

This is a lightweight stand-in for a full PPO/SAC agent.
It enables adaptive behaviour without the ML infrastructure overhead.
"""

import numpy as np
from collections import defaultdict


class AdaptiveTPSLAgent:
    """
    Contextual bandit for TP/SL multiplier selection.

    Actions are pre-defined (tp_mult, sl_mult) pairs covering
    conservative, moderate, and aggressive profiles.

    Regime context determines which action arm is selected.
    Reward updates shift probability toward better-performing arms.
    """

    ACTIONS = [
        # (tp_mult, sl_mult, label)
        (3.0, 1.0, 'tight'),     # aggressive SL, moderate TP
        (4.0, 1.5, 'balanced'),  # balanced
        (5.0, 1.5, 'moderate'),  # moderate TP
        (6.0, 2.0, 'wide_sl'),   # wide SL
        (8.0, 2.5, 'swing'),     # swing-style
    ]

    def __init__(self, epsilon=0.1, alpha=0.3, window=50):
        self.epsilon = epsilon
        self.alpha = alpha
        self.window = window
        # Q-values: {regime_label: {action_idx: avg_reward}}
        self.q = defaultdict(lambda: np.zeros(len(self.ACTIONS)))
        # Counts: {regime_label: {action_idx: count}}
        self.counts = defaultdict(lambda: np.zeros(len(self.ACTIONS), dtype=int))
        # Rolling context history
        self._context_buffer = []

    def _discretize_regime(self, adx, atr_ratio):
        """Map continuous market state to a discrete regime label."""
        if adx >= 45:
            return 'exhaustion'
        elif adx >= 25:
            if atr_ratio > 1.2:
                return 'trend_expansion'
            return 'trend'
        else:
            if atr_ratio < 0.7:
                return 'range_compression'
            return 'range'

    def get_regime_label(self, adx, atr_ratio):
        return self._discretize_regime(adx, atr_ratio)

    def select_action(self, adx, atr_ratio):
        """Return (tp_mult, sl_mult, action_idx) for current market state."""
        regime = self._discretize_regime(adx, atr_ratio)
        if np.random.random() < self.epsilon:
            idx = np.random.randint(len(self.ACTIONS))
        else:
            idx = int(np.argmax(self.q[regime]))
        tp_mult, sl_mult, _ = self.ACTIONS[idx]
        return tp_mult, sl_mult, idx

    def update(self, adx, atr_ratio, action_idx, trade_return):
        """Update Q-value for the chosen action in the given regime."""
        regime = self._discretize_regime(adx, atr_ratio)
        self.counts[regime][action_idx] += 1
        n = self.counts[regime][action_idx]
        # Incremental update: Q = Q + alpha * (reward - Q)
        current_q = self.q[regime][action_idx]
        # Normalize trade_return to [-1, 1] range for stability
        norm_return = np.tanh(trade_return / 100.0)
        self.q[regime][action_idx] = current_q + self.alpha * (norm_return - current_q)

    def get_action_profile(self, idx):
        """Return human-readable profile name for an action index."""
        if 0 <= idx < len(self.ACTIONS):
            return self.ACTIONS[idx][2]
        return 'unknown'

    def summary(self):
        """Print current Q-table for debugging."""
        lines = []
        for regime, q_vals in sorted(self.q.items()):
            best_idx = int(np.argmax(q_vals))
            best_profile = self.get_action_profile(best_idx)
            counts = self.counts.get(regime, np.zeros(len(self.ACTIONS)))
            lines.append(f"  {regime:20s}: best={best_profile:10s}  Q={q_vals.round(3)}  counts={counts}")
        return '\n'.join(lines)
