import numpy as np
from datetime import datetime, timedelta
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
        # Throttle state (126-day rolling window)
        self.equity_history = []            # daily equity snapshots for rolling peak calc
        self.rolling_window = 126           # trading days (~6 months)
        self.lowest_since_throttle = None   # trough equity during throttle=0 for recovery detection
        # Darwinian Rolling Weights state
        self.darwin_window = 63            # trading days for trailing PF computation
        self.strategy_trades = {}           # {strategy_name: [(close_time, pnl), ...]}
        self._fed_trade_count = 0           # how many closed_trades entries have been fed

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
            self.equity_history.append(current_balance)
            if len(self.equity_history) > self.rolling_window * 2:
                self.equity_history = self.equity_history[-(self.rolling_window * 2):]
        self.current_balance = current_balance
        self.peak_balance = peak_balance

    def feed_trades(self, closed_trades):
        """
        Feed newly closed trades from the engine to the allocator for
        63-day trailing Profit Factor computation (Darwinian Weights).
        Returns updated fed_trade_count.
        """
        for i in range(self._fed_trade_count, len(closed_trades)):
            t = closed_trades[i]
            sname = t.get('strategy', '')
            if not sname:
                continue
            if sname not in self.strategy_trades:
                self.strategy_trades[sname] = []
            self.strategy_trades[sname].append((t['close_time'], t['profit']))
        self._fed_trade_count = len(closed_trades)
        return self._fed_trade_count

    def _darwin_multiplier(self, strategy_name):
        """
        Compute rolling 63-trading-day Profit Factor multiplier.
        Multiplier caps at 1.5 (boost) and floors at 0.1 (survival).
        Strategies with <3 trades in the window get 1.0 (neutral).
        """
        trades = self.strategy_trades.get(strategy_name, [])
        if len(trades) < 5:
            return 1.0
        latest_time = trades[-1][0]
        cutoff = latest_time - timedelta(days=self.darwin_window)
        window_trades = [pnl for t, pnl in trades if t >= cutoff]
        if len(window_trades) < 3:
            return 1.0
        wins = [p for p in window_trades if p > 0]
        losses = [abs(p) for p in window_trades if p <= 0]
        if not losses or sum(losses) == 0:
            return 1.5
        pf = sum(wins) / sum(losses)
        if pf > 1.5:    return 1.5
        elif pf >= 1.0: return 1.0
        elif pf >= 0.8: return 0.5
        else:           return 0.1

    def _dd_to_throttle(self, dd):
        if dd < 0.02:
            return 1.0
        elif dd < 0.04:
            return 0.5
        elif dd < 0.06:
            return 0.25
        elif dd < 0.10:
            return 0.1
        else:
            return 0.0

    def throttle_multiplier(self):
        if len(self.equity_history) < 2:
            return 1.0
        current = self.equity_history[-1]
        # Rolling peak (126-day window) — short memory enables fast recovery
        window = self.equity_history[-self.rolling_window:] if len(self.equity_history) > self.rolling_window else self.equity_history
        peak = max(window)
        if peak <= 0:
            return 1.0
        dd = (peak - current) / peak
        throttle = self._dd_to_throttle(dd)
        if throttle == 0.0:
            if self.lowest_since_throttle is None or current < self.lowest_since_throttle:
                self.lowest_since_throttle = current
            if self.lowest_since_throttle is not None and self.lowest_since_throttle > 0:
                recovery = (current - self.lowest_since_throttle) / self.lowest_since_throttle
                if recovery >= 0.02:
                    throttle = 0.25
                    self.lowest_since_throttle = None
        else:
            self.lowest_since_throttle = None
        return throttle

    ZERO_STRATS = {
        'Smart_Swing_Bias', 'PriceAction_SR', 'SuperTrend_EMA',
        'Volatility_Squeeze', 'Liquidity_Sweep_Breakout',
        'NY_Session_Reversal', 'Bollinger Mean Reversion',
        'AVWAP_Confluence',
    }

    def get_weights_for_context(self, context):
        if context == MarketContext.AMBIGUOUS:
            weights = dict(self.AMBIGUOUS_WEIGHTS)
        else:
            weights = dict(self.WEIGHT_TABLES.get(context, {}))
        for s in self.ZERO_STRATS:
            weights[s] = 0.0
        return weights

    def allocate_weights(self, current_context, signal_strategy_names):
        raw_weights = self.get_weights_for_context(current_context)
        active_weights = {s: w for s, w in raw_weights.items() if s in signal_strategy_names and w > 0}
        if not active_weights:
            return {}
        total = sum(active_weights.values())
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

        # Phase 1: Collect all candidates with their requested risk
        candidates = []
        used_symbol_directions = set()
        for sig_key, sig in signals_by_strategy.items():
            if sig is None or sig.get('direction', 0) == 0:
                continue
            if len(candidates) >= self.MAX_TRADES_PER_DAY:
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

            requested = base_weight * discount

            candidates.append({
                'sig_key': sig_key,
                'sig': sig,
                'requested_risk': requested,
            })

        if not candidates:
            return []

        # Phase 2: Proportional scaling — each candidate gets a fair slice
        total_requested = sum(c['requested_risk'] for c in candidates)
        if total_requested > self.max_daily_risk:
            scaling = self.max_daily_risk / total_requested
        else:
            scaling = 1.0

        # Phase 3: Apply scaled risk to each signal
        approved = []
        for c in candidates:
            allocated = c['requested_risk'] * scaling
            if allocated <= 0:
                continue

            cap = min(allocated, 0.03)
            cum = sum(s.get('allocated_risk_pct', 0) for s in approved)
            if cum + cap > self.max_daily_risk:
                cap = max(0, self.max_daily_risk - cum)
            if cap <= 0:
                continue

            self.used_budget += cap
            c['sig']['allocated_risk_pct'] = cap
            approved.append(c['sig'])
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
                'sl_price': sig.get('sl_price'),
                'tp_price': sig.get('tp_price'),
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
