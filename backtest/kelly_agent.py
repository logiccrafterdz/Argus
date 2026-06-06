import numpy as np
from collections import deque

class KellyAgent:
    """
    Advanced Position Sizing Agent using the Fractional Kelly Criterion.
    
    Dynamically adjusts the risk percentage per trade based on the recent 
    statistical edge (Win Rate and Reward/Risk ratio) of each strategy.
    """
    def __init__(self, kelly_fraction=0.1, min_risk=0.001, max_risk=0.005, window=100):
        self.kelly_fraction = kelly_fraction
        self.min_risk = min_risk
        self.max_risk = max_risk
        self.window = window
        self.history = {} # strategy_name -> deque of profits
        
    def update(self, strategy, profit):
        """Update the rolling history with the latest closed trade's profit."""
        if strategy not in self.history:
            self.history[strategy] = deque(maxlen=self.window)
        self.history[strategy].append(profit)
        
    def get_risk_percent(self, strategy, base_confidence=1.0):
        """
        Calculate the recommended risk percentage for the next trade.
        Returns a float representing the risk decimal (e.g., 0.01 for 1%).
        """
        if strategy not in self.history or len(self.history[strategy]) < 10:
            # Not enough data, use a conservative default (e.g., 2 * min_risk = 0.5%)
            return np.clip(self.min_risk * 2 * base_confidence, self.min_risk, self.max_risk)
            
        trades = list(self.history[strategy])
        wins = [t for t in trades if t > 0]
        losses = [t for t in trades if t <= 0]
        
        W = len(wins) / len(trades)
        
        if len(wins) == 0 or len(losses) == 0:
            # If 100% win rate or 100% loss rate, default to conservative
            return np.clip(self.min_risk * 2 * base_confidence, self.min_risk, self.max_risk)
            
        avg_win = np.mean(wins)
        avg_loss = abs(np.mean(losses))
        
        R = min(avg_win / avg_loss if avg_loss > 0 else 1.0, 5.0)
        
        # Standard Kelly Formula: K = W - ((1 - W) / R)
        if R == 0:
            kelly_pct = 0.0
        else:
            kelly_pct = W - ((1 - W) / R)
            
        if kelly_pct <= 0:
            # If the strategy currently has negative expectancy, minimize risk
            return self.min_risk
            
        # Apply Fractional Kelly to reduce volatility
        fractional_kelly = kelly_pct * self.kelly_fraction
        
        # Scale by the technical/macro confidence of the current setup
        scaled_kelly = fractional_kelly * base_confidence
        
        # Clip to absolute bounds to protect the account
        final_risk = np.clip(scaled_kelly, self.min_risk, self.max_risk)
        
        return float(final_risk)
