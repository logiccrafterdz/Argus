import numpy as np
from indicators import MarketContext, detect_market_context

REGIME_TREND = 1
REGIME_RANGE = 2
REGIME_EXPANSION = 4
REGIME_COMPRESSION = 8
REGIME_REVERSAL = 16


class InstitutionalAllocator:
    MAX_PORTFOLIO_RISK = 0.02
    MAX_TRADES_PER_DAY = 50

    WEIGHT_TABLES = {
        MarketContext.ACCUMULATION: {
            'PriceAction_SR': 0.22,
            'Volatility_Squeeze': 0.18,
            'Liquidity_Sweep_Breakout': 0.11,
            'Hidden_Divergence': 0.10,
            'Asian_Range_Fakeout': 0.09,
            'TrendPullback': 0.08,
            'AVWAP_Confluence': 0.05,
            'Smart_Swing_Bias': 0.04,
            'SuperTrend_EMA': 0.03,
            'NY_Session_Reversal': 0.01,
            'Bollinger Mean Reversion': 0.01,
        },
        MarketContext.DISTRIBUTION: {
            'PriceAction_SR': 0.20,
            'Volatility_Squeeze': 0.16,
            'Liquidity_Sweep_Breakout': 0.14,
            'Hidden_Divergence': 0.12,
            'TrendPullback': 0.10,
            'Asian_Range_Fakeout': 0.08,
            'AVWAP_Confluence': 0.05,
            'Smart_Swing_Bias': 0.04,
            'SuperTrend_EMA': 0.03,
            'NY_Session_Reversal': 0.01,
            'Bollinger Mean Reversion': 0.01,
        },
        MarketContext.STOP_HUNT: {
            'PriceAction_SR': 0.22,
            'Liquidity_Sweep_Breakout': 0.16,
            'Hidden_Divergence': 0.14,
            'Volatility_Squeeze': 0.12,
            'TrendPullback': 0.10,
            'Asian_Range_Fakeout': 0.08,
            'AVWAP_Confluence': 0.05,
            'Smart_Swing_Bias': 0.04,
            'SuperTrend_EMA': 0.03,
            'NY_Session_Reversal': 0.01,
            'Bollinger Mean Reversion': 0.01,
        },
        MarketContext.PURE_TREND: {
            'TrendPullback': 0.18,
            'Volatility_Squeeze': 0.16,
            'PriceAction_SR': 0.14,
            'Liquidity_Sweep_Breakout': 0.12,
            'SuperTrend_EMA': 0.10,
            'Smart_Swing_Bias': 0.08,
            'Hidden_Divergence': 0.06,
            'AVWAP_Confluence': 0.06,
            'Asian_Range_Fakeout': 0.04,
            'NY_Session_Reversal': 0.02,
            'Bollinger Mean Reversion': 0.02,
        },
        MarketContext.PURE_RANGE: {
            'PriceAction_SR': 0.22,
            'Volatility_Squeeze': 0.18,
            'Asian_Range_Fakeout': 0.12,
            'Hidden_Divergence': 0.10,
            'Bollinger Mean Reversion': 0.08,
            'Liquidity_Sweep_Breakout': 0.08,
            'TrendPullback': 0.06,
            'AVWAP_Confluence': 0.04,
            'Smart_Swing_Bias': 0.04,
            'SuperTrend_EMA': 0.02,
            'NY_Session_Reversal': 0.02,
        },
    }

    AMBIGUOUS_WEIGHTS = {
        'PriceAction_SR': 0.20,
        'Volatility_Squeeze': 0.16,
        'Liquidity_Sweep_Breakout': 0.12,
        'Hidden_Divergence': 0.10,
        'TrendPullback': 0.10,
        'Asian_Range_Fakeout': 0.08,
        'AVWAP_Confluence': 0.06,
        'Smart_Swing_Bias': 0.05,
        'SuperTrend_EMA': 0.04,
        'Bollinger Mean Reversion': 0.02,
        'NY_Session_Reversal': 0.02,
    }

    def __init__(self, config=None):
        self.max_daily_risk = 0.06          # 6% max cumulative risk per day
        self.daily_risk_budget = 1.0        # 100% allocatable (soft limit, max_daily_risk is hard cap)
        self.used_budget = 0.0
        self.last_date = None
        self.peak_balance = None
        self.current_balance = None
        self.corr_matrix = None
        self.current_context = MarketContext.AMBIGUOUS
        self.skip_no_weights = 0
        self.skip_budget_full = 0
        self.skip_no_strategy = 0
        self.allocate_calls = 0
        self.total_signals_in = 0
        self.total_approved = 0
        # Track per-ticket correlation discount for refund on close
        self._ticket_discount = {}

    def set_corr_matrix(self, corr_matrix):
        self.corr_matrix = corr_matrix

    def refund_budget(self, ticket, allocated_risk_pct, discount_multiplier=1.0):
        """Refund budget when a position closes. Refunds the full allocated risk,
        not just the correlation-discounted portion, to prevent budget erosion."""
        pass  # budget resets daily — no intraday compounding erosion

    def reset_daily(self, current_date, current_balance, peak_balance):
        if self.last_date != current_date:
            self.used_budget = 0.0
            self._ticket_discount.clear()
            self.last_date = current_date
        self.current_balance = current_balance
        self.peak_balance = peak_balance

    def throttle_multiplier(self):
        if self.peak_balance is None or self.current_balance is None:
            return 1.0
        dd_pct = ((self.peak_balance - self.current_balance) / self.peak_balance) * 100
        if dd_pct < 3.0:
            return 1.0
        elif dd_pct < 6.0:
            return 0.5
        elif dd_pct < 10.0:
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
        self.allocate_calls += 1
        self.total_signals_in += len(signals_by_strategy)

        if self.used_budget >= self.daily_risk_budget:
            self.skip_budget_full += 1
            return []

        strategy_names = set()
        for sig_key, sig in signals_by_strategy.items():
            if sig is not None and sig.get('direction', 0) != 0:
                strategy_names.add(sig.get('strategy', ''))
        weight_map = self.allocate_weights(current_context, strategy_names)
        if not weight_map:
            self.skip_no_weights += 1
            return []

        for sig_key, sig in signals_by_strategy.items():
            if sig is not None and sig.get('direction', 0) != 0:
                sname = sig.get('strategy', '')
                if sname not in weight_map:
                    self.skip_no_strategy += 1

        trades_today = 0
        used_symbol_directions = set()
        approved = []
        for sig_key, sig in signals_by_strategy.items():
            if sig is None or sig.get('direction', 0) == 0:
                continue
            if trades_today >= self.MAX_TRADES_PER_DAY:
                break
            strategy_name = sig.get('strategy', '')
            symbol = sig.get('symbol', '')
            direction = sig.get('direction_label', 'BUY')
            base_weight = weight_map.get(strategy_name, 0.0)
            if base_weight <= 0:
                continue

            sd_key = (symbol, direction)
            if sd_key in used_symbol_directions:
                base_weight *= 0.3
            else:
                used_symbol_directions.add(sd_key)

            discount = 1.0
            if corr_matrix is not None and symbol in corr_matrix.index:
                for pos in open_positions:
                    pos_sym = pos.get('symbol', '')
                    if pos_sym in corr_matrix.columns and pos_sym != symbol:
                        c_val = abs(corr_matrix.loc[symbol, pos_sym])
                        if c_val > 0.8 and pos['type'] == direction:
                            discount = min(discount, 0.4)
                        elif c_val > 0.6 and pos['type'] == direction:
                            discount = min(discount, 0.6)

            base_weight *= discount
            risk_used = base_weight

            # Hard cap: max_daily_risk (6%) — prevents blowing up in high-volatility days
            cum_risk = sum(s.get('allocated_risk_pct', 0) for s in approved)
            if cum_risk + risk_used > self.max_daily_risk:
                risk_used = max(0, self.max_daily_risk - cum_risk)
            if risk_used <= 0:
                continue

            self.used_budget += risk_used
            sig['allocated_risk_pct'] = min(risk_used, 0.03)
            approved.append(sig)
            trades_today += 1
            self.total_approved += 1
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
