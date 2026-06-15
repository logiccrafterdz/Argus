import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from indicators import ATR
from signal_types import StrategyType

class BaseStrategy:
    def __init__(self, name, category, regime_mask, session_mask, strategy_type=StrategyType.TREND_MOMENTUM):
        self.name = name
        self.category = category
        self.regime_mask = regime_mask
        self.session_mask = session_mask
        self.strategy_type = strategy_type
        self.atr_period = 14

    def _add_atr_col(self, df):
        df['atr'] = ATR(df, self.atr_period)

    def _atr_buf(self, df, idx, mult=0.5):
        return df['atr'].iloc[idx] * mult

    def prepare_data(self, df):
        pass

    def generate_signals(self, df):
        pass

    def check_regime(self, current_regime):
        if self.regime_mask == 31:
            return True
        return (current_regime & self.regime_mask) != 0

    def check_session(self, current_session):
        if self.session_mask == 7:
            return True
        if current_session == 0:
            return False
        return (current_session & self.session_mask) != 0
