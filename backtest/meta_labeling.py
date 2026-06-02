import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from indicators import ATR

class MetaLabelingFilter:
    """
    Meta-labeling: trains a classifier to predict whether a strategy signal
    will be profitable (P(profit > 0 | signal, features)).

    Based on López de Prado's meta-labeling framework:
    - Primary model: the strategy itself (generates signals)
    - Secondary model: this classifier (decides whether to take the signal)

    Features used at signal time:
    - ATR ratio (volatility regime)
    - ADX (trend strength)
    - Time of day / day of week (one-hot)
    - Recent strategy win rate (last 10 signals)
    - Spread
    - Session flags
    """

    def __init__(self, strategy_name, window=200, min_samples=30):
        self.strategy_name = strategy_name
        self.window = window
        self.min_samples = min_samples
        self.model = Pipeline([
            ('scaler', StandardScaler()),
            ('clf', LogisticRegression(
                class_weight='balanced',
                C=0.1,
                max_iter=500,
                random_state=42
            ))
        ])
        self.fitted = False
        self._feature_buffer = []
        self._label_buffer = []

    def _extract_signal_features(self, symbol, row, atr_val, adx_val, session, spread):
        """Build feature vector from available data at signal time."""
        features = {
            'atr_ratio': atr_val / (row.get('close', 1) + 1e-10),
            'adx': adx_val,
            'spread': spread,
            'hour': row.name.hour if hasattr(row.name, 'hour') else 0,
            'day_of_week': row.name.dayofweek if hasattr(row.name, 'dayofweek') else 0,
            'session_asia': 1 if session & 1 else 0,
            'session_london': 1 if session & 2 else 0,
            'session_ny': 1 if session & 4 else 0,
            'range_pct': (row['high'] - row['low']) / (row.get('close', 1) + 1e-10),
        }
        return features

    def add_signal(self, features, was_profitable):
        """Record a signal outcome for training."""
        vec = np.array([features[k] for k in sorted(features.keys())])
        self._feature_buffer.append(vec)
        self._label_buffer.append(1 if was_profitable else 0)
        if len(self._feature_buffer) > self.window * 2:
            self._feature_buffer = self._feature_buffer[-self.window:]
            self._label_buffer = self._label_buffer[-self.window:]

    def train(self):
        """Fit classifier on accumulated signal history."""
        if len(self._label_buffer) < self.min_samples:
            return False
        X = np.array(self._feature_buffer[-self.window:])
        y = np.array(self._label_buffer[-self.window:])
        if len(np.unique(y)) < 2:
            return False
        self.model.fit(X, y)
        self.fitted = True
        return True

    def predict_proba(self, features):
        """Return probability that signal will be profitable P(profit > 0)."""
        if not self.fitted:
            return 0.5
        vec = np.array([[features[k] for k in sorted(features.keys())]])
        proba = self.model.predict_proba(vec)[0]
        return proba[1]  # probability of class 1 (profitable)

    def should_trade(self, features, threshold=0.45):
        """Return True if signal passes meta-labeling filter."""
        prob = self.predict_proba(features)
        return prob >= threshold

    def get_feature_importance(self):
        """Return feature coefficients from logistic regression."""
        if not self.fitted:
            return {}
        coef = self.model.named_steps['clf'].coef_[0]
        feature_names = sorted(['atr_ratio', 'adx', 'spread', 'hour',
                                'day_of_week', 'session_asia', 'session_london',
                                'session_ny', 'range_pct'])
        return dict(zip(feature_names, coef))
