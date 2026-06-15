import numpy as np
from indicators import MarketContext, detect_market_context

REGIME_TREND = 1
REGIME_RANGE = 2
REGIME_EXPANSION = 4
REGIME_COMPRESSION = 8
REGIME_REVERSAL = 16


class InstitutionalAllocator:
    MAX_PORTFOLIO_RISK = 0.02

    WEIGHT_TABLES = {
        MarketContext.ACCUMULATION: {
            'Bollinger Mean Reversion': 0.55,
            'Asian_Range_Fakeout': 0.30,
            'PriceAction_SR': 0.15,
        },
        MarketContext.DISTRIBUTION: {
            'AVWAP_Confluence': 0.45,
            'TrendPullback': 0.30,
            'Liquidity_Sweep_Breakout': 0.25,
        },
        MarketContext.STOP_HUNT: {
            'NY_Session_Reversal': 0.35,
            'Hidden_Divergence': 0.35,
            'ICT_Killzone_Macro': 0.20,
            'Smart_Swing_Bias': 0.10,
        },
        MarketContext.PURE_TREND: {
            'AVWAP_Confluence': 0.35,
            'TrendPullback': 0.25,
            'Smart_Swing_Bias': 0.20,
            'Hidden_Divergence': 0.10,
            'SuperTrend_EMA': 0.10,
        },
        MarketContext.PURE_RANGE: {
            'Bollinger Mean Reversion': 0.40,
            'Asian_Range_Fakeout': 0.25,
            'PriceAction_SR': 0.20,
            'Volatility_Squeeze': 0.15,
        },
    }

    AMBIGUOUS_WEIGHTS = {
        'Bollinger Mean Reversion': 0.25,
        'AVWAP_Confluence': 0.25,
        'Asian_Range_Fakeout': 0.20,
        'Hidden_Divergence': 0.20,
        'TrendPullback': 0.10,
    }

    def __init__(self, config=None):
        self.daily_risk_budget = 0.6
        self.used_budget = 0.0
        self.last_date = None
        self.peak_balance = None
        self.current_balance = None
        self.corr_matrix = None
        self.current_context = MarketContext.AMBIGUOUS

    def set_corr_matrix(self, corr_matrix):
        self.corr_matrix = corr_matrix

    def reset_daily(self, current_date, current_balance, peak_balance):
        if self.last_date != current_date:
            self.used_budget = 0.0
            self.last_date = current_date
        self.current_balance = current_balance
        self.peak_balance = peak_balance

    def throttle_multiplier(self):
        if self.peak_balance is None or self.current_balance is None:
            return 1.0
        dd_pct = ((self.peak_balance - self.current_balance) / self.peak_balance) * 100
        if dd_pct < 2.0:
            return 1.0
        elif dd_pct < 4.0:
            return 0.5
        elif dd_pct < 6.0:
            return 0.25
        else:
            return 0.0

    def get_weights_for_context(self, context):
        if context == MarketContext.AMBIGUOUS:
            return dict(self.AMBIGUOUS_WEIGHTS)
        return dict(self.WEIGHT_TABLES.get(context, {}))

    def allocate_weights(self, current_context, signal_strategy_names):
        raw_weights = self.get_weights_for_context(current_context)
        active_weights = {s: w for s, w in raw_weights.items() if s in signal_strategy_names}
        if not active_weights:
            return {}
        total = sum(active_weights.values())
        if total <= 0:
            return {}
        normalized = {}
        for s, w in active_weights.items():
            normalized[s] = (w / total) * self.MAX_PORTFOLIO_RISK
        return normalized

    def allocate(self, signals_by_strategy, current_context, corr_matrix, open_positions, equity):
        self.current_context = current_context
        strategy_names = set()
        for sig_key, sig in signals_by_strategy.items():
            if sig is not None and sig.get('direction', 0) != 0:
                strategy_names.add(sig.get('strategy', ''))
        weight_map = self.allocate_weights(current_context, strategy_names)
        if not weight_map:
            total_signals = len(signals_by_strategy)
            if total_signals > 0:
                equal_risk = self.MAX_PORTFOLIO_RISK / max(total_signals, 1)
                for k in signals_by_strategy:
                    weight_map[k] = equal_risk
            else:
                return []

        used_symbol_directions = set()
        approved = []
        for sig_key, sig in signals_by_strategy.items():
            if sig is None or sig.get('direction', 0) == 0:
                continue
            strategy_name = sig.get('strategy', '')
            symbol = sig.get('symbol', '')
            direction = sig.get('direction_label', 'BUY')
            base_weight = weight_map.get(strategy_name, 0.0)

            sd_key = (symbol, direction)
            symbol_count = sum(1 for k, s in signals_by_strategy.items()
                               if s and s.get('symbol') == symbol and s.get('direction_label') == direction
                               and s.get('direction', 0) != 0)

            if sd_key in used_symbol_directions:
                base_weight *= 0.4
            else:
                used_symbol_directions.add(sd_key)

            if corr_matrix is not None and symbol in corr_matrix.index:
                for pos in open_positions:
                    pos_sym = pos.get('symbol', '')
                    if pos_sym in corr_matrix.columns and pos_sym != symbol:
                        c_val = abs(corr_matrix.loc[symbol, pos_sym])
                        if c_val > 0.8 and pos['type'] == direction:
                            base_weight *= 0.5
                        elif c_val > 0.6 and pos['type'] == direction:
                            base_weight *= 0.75

            sig['allocated_risk_pct'] = min(base_weight, 0.05)
            approved.append(sig)
        return approved

    def filter(self, raw_signals, open_positions=None, current_regime=None):
        if not raw_signals:
            return []
        corr_matrix = self.corr_matrix
        if open_positions is None:
            open_positions = []
        context = detect_market_context(current_regime) if current_regime is not None else self.current_context
        self.current_context = context
        signals_by_strategy = {}
        for sig in raw_signals:
            key = f"{sig['strategy']}_{sig['symbol']}_{sig['order_type']}"
            signals_by_strategy[key] = {
                'symbol': sig['symbol'],
                'direction': 1 if sig['order_type'] == 'BUY' else -1,
                'direction_label': sig['order_type'],
                'entry_price': sig['entry_price'],
                'atr_value': sig['atr_value'],
                'conviction': sig['conviction'],
                'sl_price': sig['sl_price'],
                'tp_price': sig['tp_price'],
                'strategy': sig['strategy'],
                'strategy_type': sig['strategy_type'],
                'allocated_risk_pct': 0.2,
            }
        approved = self.allocate(signals_by_strategy, context, corr_matrix, open_positions, 100000.0)
        result = []
        for item in approved:
            result.append({
                'symbol': item['symbol'],
                'strategy': item['strategy'],
                'strategy_type': item['strategy_type'],
                'order_type': item['direction_label'],
                'entry_price': item['entry_price'],
                'atr_value': item['atr_value'],
                'conviction': item.get('conviction', 0.5),
                'sl_price': item.get('sl_price'),
                'tp_price': item.get('tp_price'),
                'allocated_risk_pct': item.get('allocated_risk_pct', 0.2),
            })
        return result
