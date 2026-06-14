import numpy as np

REGIME_TREND = 1
REGIME_RANGE = 2
REGIME_EXPANSION = 4
REGIME_COMPRESSION = 8
REGIME_REVERSAL = 16

REGIME_ALLOCATION = {
    REGIME_TREND: {
        'trend_momentum': 0.80,
        'mean_reversion': 0.10,
        'stop_hunt': 0.10,
    },
    REGIME_RANGE: {
        'trend_momentum': 0.10,
        'mean_reversion': 0.80,
        'stop_hunt': 0.10,
    },
    REGIME_EXPANSION: {
        'trend_momentum': 0.70,
        'mean_reversion': 0.10,
        'stop_hunt': 0.20,
    },
    REGIME_COMPRESSION: {
        'trend_momentum': 0.10,
        'mean_reversion': 0.70,
        'stop_hunt': 0.20,
    },
    REGIME_REVERSAL: {
        'trend_momentum': 0.40,
        'mean_reversion': 0.10,
        'stop_hunt': 0.50,
    },
}


class CentralAllocator:
    def __init__(self, daily_risk_budget=0.6):
        self.daily_risk_budget = daily_risk_budget
        self.used_budget = 0.0
        self.last_date = None
        self.peak_balance = None
        self.current_balance = None

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

    def regime_allocation(self, current_regime, strategy_type):
        if current_regime == 31:
            return 0.25
        reg_allocs = REGIME_ALLOCATION.get(current_regime)
        if reg_allocs is None:
            return 0.25
        return reg_allocs.get(strategy_type, 0.25)

    def symbol_budget(self, symbol, direction, open_positions, corr_matrix):
        if not open_positions or corr_matrix is None or symbol not in corr_matrix.index:
            return 1.0
        deduction = 1.0
        for pos in open_positions:
            pos_sym = pos.get('symbol', '')
            if pos_sym not in corr_matrix.columns:
                continue
            if pos_sym == symbol:
                deduction *= 0.4
            else:
                c_val = abs(corr_matrix.loc[symbol, pos_sym])
                if c_val > 0.8 and pos['type'] == direction:
                    deduction *= 0.5
                elif c_val > 0.6 and pos['type'] == direction:
                    deduction *= 0.75
        return max(deduction, 0.2)

    def allocate(self, signals_by_strategy, current_regime, corr_matrix, open_positions, equity):
        approved = []
        # Track virtual positions already approved in this bar (sequential ordering matches old system)
        virtual_positions = list(open_positions)
        for sig_key, sig in signals_by_strategy.items():
            if sig is None or sig.get('direction', 0) == 0:
                continue

            symbol = sig.get('symbol', '')
            direction = sig.get('direction_label', 'BUY')

            # Binary correlation block: same symbol + same direction, or strongly correlated (>0.8) same direction
            blocked = False
            for pos in virtual_positions:
                if pos.get('symbol', '') == symbol and pos['type'] == direction:
                    blocked = True
                    break
                pos_sym = pos.get('symbol', '')
                if pos_sym and pos_sym in corr_matrix.columns and symbol in corr_matrix.index:
                    c_val = abs(corr_matrix.loc[symbol, pos_sym])
                    if c_val > 0.8 and pos['type'] == direction:
                        blocked = True
                        break
            if blocked:
                continue

            sig['allocated_risk_pct'] = 0.2
            approved.append(sig)
            # Add virtual position so subsequent signals in this bar see it (sequential ordering)
            virtual_positions.append({'symbol': symbol, 'type': direction})
        return approved
