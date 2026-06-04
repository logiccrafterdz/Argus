import pandas as pd
import numpy as np
from risk_manager import RiskManager
from log_setup import get_logger

class BacktestEngine:
    def __init__(self, initial_balance=100000.0, config=None):
        self.config = config or {}
        self.logger = get_logger('engine')
        
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.equity = initial_balance
        
        self.open_positions = []
        self.closed_trades = []
        self.equity_curve = []
        
        self.risk_manager = RiskManager(initial_balance)
        self.disable_breakeven_strategies = set()  # strategy names that skip breakeven/partial close
        
        spread_cfg = self.config.get('spread', {})
        self.spread_map = {
            'EURUSD': spread_cfg.get('EURUSD', 0.00012),
            'GBPUSD': spread_cfg.get('GBPUSD', 0.00014),
            'USDJPY': spread_cfg.get('USDJPY', 0.013),
            'USDCHF': spread_cfg.get('USDCHF', 0.00014),
            'AUDUSD': spread_cfg.get('AUDUSD', 0.00013),
            'USDCAD': spread_cfg.get('USDCAD', 0.00016),
            'NZDUSD': spread_cfg.get('NZDUSD', 0.00018),
            'EURJPY': spread_cfg.get('EURJPY', 0.015),
            'GBPJPY': spread_cfg.get('GBPJPY', 0.020),
            'XAUUSD': spread_cfg.get('XAUUSD', 0.35),
            'US30': spread_cfg.get('US30', 3.0),
            'NAS100': spread_cfg.get('NAS100', 2.5),
        }
        self.default_spread = 0.00015
        
        cs_cfg = self.config.get('contract_size', {})
        self.contract_size_map = {
            'XAUUSD': cs_cfg.get('XAUUSD', 100),
            'US30': cs_cfg.get('US30', 1.0),
            'NAS100': cs_cfg.get('NAS100', 1.0),
            'EURJPY': cs_cfg.get('EURJPY', 100000.0),
            'GBPJPY': cs_cfg.get('GBPJPY', 100000.0),
        }
        self.default_contract_size = self.config.get('default_contract_size', 100000.0)
        
        tick_cfg = self.config.get('tick_size', {})
        self.tick_size_map = {
            'EURUSD': tick_cfg.get('EURUSD', 0.00001),
            'GBPUSD': tick_cfg.get('GBPUSD', 0.00001),
            'USDJPY': tick_cfg.get('USDJPY', 0.001),
            'USDCHF': tick_cfg.get('USDCHF', 0.00001),
            'AUDUSD': tick_cfg.get('AUDUSD', 0.00001),
            'USDCAD': tick_cfg.get('USDCAD', 0.00001),
            'NZDUSD': tick_cfg.get('NZDUSD', 0.00001),
            'EURJPY': tick_cfg.get('EURJPY', 0.001),
            'GBPJPY': tick_cfg.get('GBPJPY', 0.001),
            'XAUUSD': tick_cfg.get('XAUUSD', 0.01),
            'US30': tick_cfg.get('US30', 1.0),
            'NAS100': tick_cfg.get('NAS100', 1.0),
        }
        
        pip_cfg = self.config.get('pip_size', {})
        self.pip_size_map = {
            'EURUSD': pip_cfg.get('EURUSD', 0.0001),
            'GBPUSD': pip_cfg.get('GBPUSD', 0.0001),
            'USDJPY': pip_cfg.get('USDJPY', 0.01),
            'USDCHF': pip_cfg.get('USDCHF', 0.0001),
            'AUDUSD': pip_cfg.get('AUDUSD', 0.0001),
            'USDCAD': pip_cfg.get('USDCAD', 0.0001),
            'NZDUSD': pip_cfg.get('NZDUSD', 0.0001),
            'EURJPY': pip_cfg.get('EURJPY', 0.01),
            'GBPJPY': pip_cfg.get('GBPJPY', 0.01),
            'XAUUSD': pip_cfg.get('XAUUSD', 0.01),
            'US30': pip_cfg.get('US30', 1.0),
            'NAS100': pip_cfg.get('NAS100', 1.0),
        }
        
        tv_cfg = self.config.get('tick_value', {})
        self.tick_value_map = {
            'EURUSD': tv_cfg.get('EURUSD', 1.0),
            'GBPUSD': tv_cfg.get('GBPUSD', 1.0),
            'AUDUSD': tv_cfg.get('AUDUSD', 1.0),
            'NZDUSD': tv_cfg.get('NZDUSD', 1.0),
            'XAUUSD': tv_cfg.get('XAUUSD', 1.0),
            'US30': tv_cfg.get('US30', 1.0),
            'NAS100': tv_cfg.get('NAS100', 1.0),
        }
        
        comm_cfg = self.config.get('execution', {}).get('commission_map', {})
        self.commission_map = {
            'XAUUSD': comm_cfg.get('XAUUSD', 3.50),
            'US30': comm_cfg.get('US30', 0.0),
            'NAS100': comm_cfg.get('NAS100', 0.0),
            'EURJPY': comm_cfg.get('EURJPY', 3.50),
            'GBPJPY': comm_cfg.get('GBPJPY', 3.50),
        }
        self.default_commission = self.config.get('execution', {}).get('default_commission', 7.0)

        # ATR-based slippage model: keyed by symbol, expected as Series/array aligned to bar index
        self.atr_map = {}
        self.bar_index = 0

        # Swap/rollover costs per lot per day (long, short) keyed by symbol
        swap_cfg = self.config.get('swap', {})
        self.swap_map = {
            'EURUSD': swap_cfg.get('EURUSD', (-1.5, -0.5)),
            'GBPUSD': swap_cfg.get('GBPUSD', (-2.0, -0.8)),
            'USDJPY': swap_cfg.get('USDJPY', (1.2, -2.5)),
            'USDCHF': swap_cfg.get('USDCHF', (-0.8, -1.2)),
            'AUDUSD': swap_cfg.get('AUDUSD', (-0.5, -1.5)),
            'USDCAD': swap_cfg.get('USDCAD', (-1.0, -1.0)),
            'NZDUSD': swap_cfg.get('NZDUSD', (-0.3, -1.8)),
            'EURJPY': swap_cfg.get('EURJPY', (-1.8, -0.3)),
            'GBPJPY': swap_cfg.get('GBPJPY', (-2.5, 0.5)),
            'XAUUSD': swap_cfg.get('XAUUSD', (-4.0, -2.0)),
            'US30': swap_cfg.get('US30', (-1.0, -1.0)),
            'NAS100': swap_cfg.get('NAS100', (-1.5, -1.5)),
        }
        self.default_swap = swap_cfg.get('default', (-1.0, -1.0))
        self.last_swap_date = None
        
        slippage_cfg = self.config.get('execution', {})
        self.slippage_min = slippage_cfg.get('slippage_min', 0.0)
        self.slippage_max = slippage_cfg.get('slippage_max', 0.3)
        self.current_time = None
        self.ticket_counter = 1
        self.is_bankrupt = False
        self.bankruptcy_threshold = initial_balance * 0.05
        self.peak_balance = initial_balance
        self.max_drawdown_pct = self.config.get('risk', {}).get('max_drawdown_pct', 50.0)
        self.current_prices = {}

        # Half-Kelly position sizing: per-strategy rolling stats
        self.strategy_trades = {}  # strategy_name -> list of profit values
        self.kelly_window = 50    # rolling window for Kelly calculation
        self.kelly_enabled = self.config.get('kelly', {}).get('enabled', True)
        self.kelly_base_risk = self.config.get('kelly', {}).get('base_risk_pct', 0.2)
        self.kelly_cap = self.config.get('kelly', {}).get('max_risk_pct', 0.5)  # half-kelly max

    def get_usd_multiplier(self, symbol):
        if symbol.endswith('USD') or symbol in ['US30', 'NAS100']:
            return 1.0
        if symbol.endswith('JPY'):
            if 'USDJPY' in self.current_prices:
                return 1.0 / self.current_prices['USDJPY']
            return 1.0 / 135.0
        if symbol.endswith('CAD'):
            if 'USDCAD' in self.current_prices:
                return 1.0 / self.current_prices['USDCAD']
            return 1.0 / 1.35
        if symbol.endswith('CHF'):
            if 'USDCHF' in self.current_prices:
                return 1.0 / self.current_prices['USDCHF']
            return 1.0 / 0.90
        return 1.0

    def contract_size(self, symbol):
        return self.contract_size_map.get(symbol, 100000.0)
    
    def tick_size(self, symbol):
        return self.tick_size_map.get(symbol, 0.00001)
    
    def pip_size(self, symbol):
        return self.pip_size_map.get(symbol, 0.0001)
    
    def tick_value(self, symbol):
        return self.tick_value_map.get(symbol, 1.0)
    
    def calculate_lot_size(self, symbol, risk_percent, risk_distance, equity):
        if risk_distance <= 0:
            return 0.0
        risk_amount = equity * (risk_percent / 100.0)
        multiplier = self.get_usd_multiplier(symbol)
        
        risk_per_lot_usd = risk_distance * self.contract_size(symbol) * multiplier
        
        if risk_per_lot_usd <= 0:
            return 0.0
        lot = risk_amount / risk_per_lot_usd
        
        # Max 3x leverage cap per trade approximation
        max_position_value_usd = equity * 3.0
        if multiplier > 0:
            # position value roughly = lot * contract_size * (price * multiplier if cross, else price)
            # For simplicity, cap lot size at (max_val / contract_size)
            lot = min(lot, max_position_value_usd / self.contract_size(symbol))
            
        min_vol = 0.01
        max_vol = 100.0
        step_vol = 0.01
        lot = np.floor(lot / step_vol) * step_vol
        lot = max(min_vol, min(max_vol, lot))
        return lot
    
    def position_value(self, symbol, lots):
        return lots * self.contract_size(symbol)
    
    def calculate_equity(self, current_prices):
        equity = self.balance
        for pos in self.open_positions:
            symbol = pos['symbol']
            if symbol in current_prices:
                current_price = current_prices[symbol]
                lots = pos['remaining_lots']
                cs = self.contract_size(symbol)
                multiplier = self.get_usd_multiplier(symbol)
                if pos['type'] == 'BUY':
                    profit = (current_price - pos['entry_price']) * lots * cs * multiplier
                else:
                    profit = (pos['entry_price'] - current_price) * lots * cs * multiplier
                equity += profit
        return equity

    def get_kelly_multiplier(self, strategy_name):
        """Return Half-Kelly risk multiplier for the given strategy. 1.0 = no adjustment."""
        if not self.kelly_enabled:
            return 1.0
        trades = self.strategy_trades.get(strategy_name)
        if not trades or len(trades) < 10:
            return 1.0  # insufficient data
        window = trades[-self.kelly_window:]
        wins = [p for p in window if p > 0]
        losses = [p for p in window if p < 0]
        if not wins or not losses:
            return 1.0
        win_rate = len(wins) / len(window)
        avg_win = sum(wins) / len(wins)
        avg_loss = abs(sum(losses) / len(losses))
        if avg_loss == 0:
            return 1.0
        b = avg_win / avg_loss
        # Kelly %: f = (p * b - q) / b
        q = 1.0 - win_rate
        kelly = (win_rate * b - q) / b
        half_kelly = kelly / 2.0
        # convert to multiplier over base_risk:
        # base_risk = self.kelly_base_risk (0.2% = 0.002 of equity)
        # half_kelly = optimal fraction of equity (~0.02 = 2% when WR~35%, R:R~3)
        # = half_kelly / base_risk → 0.02/0.002 = 10x → clipped to 2.5
        # For weak edge (WR~22%, R:R~1.5): kelly~0.015 → half_kelly~0.0075 → 0.0075/0.002=3.75→2.5
        # For marginal edge (WR~20%, R:R~1.2): kelly~0.003 → half_kelly~0.0015 → 0.0015/0.002=0.75
        base_risk = self.kelly_base_risk / 100.0  # e.g. 0.2 → 0.002
        multiplier = half_kelly / base_risk if base_risk > 0 else 1.0
        return max(0.25, min(2.5, multiplier))

    def record_trade_result(self, profit, strategy_name):
        if strategy_name not in self.strategy_trades:
            self.strategy_trades[strategy_name] = []
        self.strategy_trades[strategy_name].append(profit)
        # Keep only last 200 trades to bound memory
        if len(self.strategy_trades[strategy_name]) > 200:
            self.strategy_trades[strategy_name] = self.strategy_trades[strategy_name][-200:]

    def execute_trade(self, symbol, strategy_name, order_type, lot_size, entry_price, sl, tp, comment):
        if self.is_bankrupt or self.risk_manager.is_halted:
            return False
            
        if not self.risk_manager.check_exposure(symbol, order_type, self.open_positions):
            return False
            
        # Simplified correlation check could be added here
        
        # Realistic per-symbol spread model (in price units)
        # Based on typical FBS MT5 average spreads
        spread = self.spread_map.get(symbol, self.default_spread)

        # ATR-based slippage: 5% of ATR with exponential distribution (heavy-tail)
        atr = self.atr_map.get(symbol)
        if atr is not None:
            idx = min(self.bar_index, len(atr) - 1)
            slippage = atr[idx] * 0.05 * np.random.exponential(1.0)
        else:
            # Fallback: random 0-30% of spread
            slippage = spread * np.random.uniform(self.slippage_min or 0, self.slippage_max or 0.3)

        total_cost = spread + slippage
        if order_type == 'BUY':
            entry_price += total_cost
        else:
            entry_price -= total_cost

        # Validate TP direction: ensure TP is on the profit side of entry
        if tp is not None:
            if order_type == 'BUY' and tp <= entry_price:
                self.logger.debug(f"Reject {symbol} {strategy_name} BUY: tp={tp:.5f} <= entry={entry_price:.5f}")
                return False
            if order_type == 'SELL' and tp >= entry_price:
                self.logger.debug(f"Reject {symbol} {strategy_name} SELL: tp={tp:.5f} >= entry={entry_price:.5f}")
                return False

        # Validate SL direction: ensure SL is on the risk side of entry
        if sl is not None:
            if order_type == 'BUY' and sl >= entry_price:
                self.logger.debug(f"Reject {symbol} {strategy_name} BUY: sl={sl:.5f} >= entry={entry_price:.5f}")
                return False
            if order_type == 'SELL' and sl <= entry_price:
                self.logger.debug(f"Reject {symbol} {strategy_name} SELL: sl={sl:.5f} <= entry={entry_price:.5f}")
                return False

        # Half-Kelly dynamic position sizing
        kelly_mult = self.get_kelly_multiplier(strategy_name)
        adjusted_lot = lot_size * kelly_mult
        # Re-apply step rounding after Kelly adjustment
        step_vol = 0.01
        adjusted_lot = np.floor(adjusted_lot / step_vol) * step_vol
        adjusted_lot = max(0.01, min(100.0, adjusted_lot))

        pos = {
            'ticket': self.ticket_counter,
            'symbol': symbol,
            'strategy': strategy_name,
            'type': order_type,
            'lot_size': adjusted_lot,
            'entry_price': entry_price,
            'sl': sl,
            'tp': tp,
            'entry_time': self.current_time,
            'comment': f"{comment} | kelly:{kelly_mult:.2f}x",
            'highest_profit': 0.0,
            'breakeven_triggered': False,
            'partial_closed': False,
            'remaining_lots': adjusted_lot,
            'swap_cost': 0.0,
            'last_swap_day': None
        }
        self.open_positions.append(pos)
        self.ticket_counter += 1
        return True

    def close_position(self, pos, close_price, close_time, reason):
        lots_to_close = pos['remaining_lots']
        cs = self.contract_size(pos['symbol'])
        multiplier = self.get_usd_multiplier(pos['symbol'])
        if pos['type'] == 'BUY':
            profit = (close_price - pos['entry_price']) * lots_to_close * cs * multiplier
        else:
            profit = (pos['entry_price'] - close_price) * lots_to_close * cs * multiplier
            
        # Realistic per-symbol commission
        # Forex: $7/lot round turn, Gold: $3.50/lot, Indices: $0 (built into spread)
        commission_per_lot = self.commission_map.get(pos['symbol'], self.default_commission)
        commission = -commission_per_lot * lots_to_close
        profit += commission

        # Include accumulated swap/rollover costs
        total_swap = pos['swap_cost'] * (lots_to_close / pos['lot_size'])
        profit += total_swap

        self.balance += profit
        self.record_trade_result(profit, pos['strategy'])
        trade_record = {
            'ticket': pos['ticket'],
            'symbol': pos['symbol'],
            'strategy': pos['strategy'],
            'type': pos['type'],
            'lot_size': lots_to_close,
            'entry_time': pos['entry_time'],
            'close_time': close_time,
            'entry_price': pos['entry_price'],
            'close_price': close_price,
            'profit': profit,
            'reason': reason,
            'swap_cost': round(total_swap, 2)
        }
        if 'rl_action' in pos:
            trade_record['rl_action'] = pos['rl_action']
        if 'meta_features' in pos:
            trade_record['meta_features'] = pos['meta_features']
        self.closed_trades.append(trade_record)
        pos['remaining_lots'] -= lots_to_close
        if pos['remaining_lots'] <= 0.001:
            self.open_positions.remove(pos)

        if self.balance < self.bankruptcy_threshold and not self.is_bankrupt:
            self.is_bankrupt = True
            self.logger.warning(f"BANKRUPT at {close_time}: balance={self.balance:.2f} < threshold={self.bankruptcy_threshold:.2f}")

    def close_position_partial(self, pos, close_price, close_time, reason, lots_to_close):
        cs = self.contract_size(pos['symbol'])
        multiplier = self.get_usd_multiplier(pos['symbol'])
        if pos['type'] == 'BUY':
            profit = (close_price - pos['entry_price']) * lots_to_close * cs * multiplier
        else:
            profit = (pos['entry_price'] - close_price) * lots_to_close * cs * multiplier
            
        commission = -self.commission_map.get(pos['symbol'], self.default_commission) * lots_to_close
        profit += commission

        # Include proportional swap
        total_swap = pos['swap_cost'] * (lots_to_close / pos['lot_size'])
        profit += total_swap

        self.balance += profit
        self.record_trade_result(profit, pos['strategy'])
        trade_record = {
            'ticket': pos['ticket'],
            'symbol': pos['symbol'],
            'strategy': pos['strategy'],
            'type': pos['type'],
            'lot_size': lots_to_close,
            'entry_time': pos['entry_time'],
            'close_time': close_time,
            'entry_price': pos['entry_price'],
            'close_price': close_price,
            'profit': profit,
            'reason': reason,
            'swap_cost': round(total_swap, 2)
        }
        if 'rl_action' in pos:
            trade_record['rl_action'] = pos['rl_action']
        if 'meta_features' in pos:
            trade_record['meta_features'] = pos['meta_features']
        self.closed_trades.append(trade_record)
        pos['remaining_lots'] -= lots_to_close

        if self.balance < self.bankruptcy_threshold and not self.is_bankrupt:
            self.is_bankrupt = True
            self.logger.warning(f"BANKRUPT at {close_time}: balance={self.balance:.2f}")

    def emergency_close_all(self, current_prices, reason="Circuit Breaker"):
        for pos in list(self.open_positions):
            symbol = pos['symbol']
            if symbol in current_prices:
                self.close_position(pos, current_prices[symbol], self.current_time, reason)

    def update(self, current_time, current_prices, current_highs, current_lows):
        self.current_time = current_time
        self.bar_index += 1
        self.equity = self.calculate_equity(current_prices)
        self.peak_balance = max(self.peak_balance, self.balance)
        dd_from_peak = ((self.peak_balance - self.balance) / self.peak_balance) * 100
        if dd_from_peak >= self.max_drawdown_pct and not self.is_bankrupt:
            self.is_bankrupt = True
            self.logger.warning(f"MAX DRAWDOWN at {current_time}: peak={self.peak_balance:.2f}, balance={self.balance:.2f}, dd={dd_from_peak:.1f}%")
        
        if self.risk_manager.update(current_time, self.equity):
            self.emergency_close_all(current_prices)

        # Daily swap/rollover charge: apply once per day at first bar of new date
        current_date = current_time.date()
        if self.last_swap_date is None or current_date > self.last_swap_date:
            self.last_swap_date = current_date
            # Wednesday = triple swap (3x) — MT5 standard for FX/CFD
            swap_multiplier = 3 if current_time.weekday() == 2 else 1
            for pos in self.open_positions:
                swap_rates = self.swap_map.get(pos['symbol'], self.default_swap)
                rate = swap_rates[0] if pos['type'] == 'BUY' else swap_rates[1]
                swap = rate * pos['remaining_lots'] * swap_multiplier
                pos['swap_cost'] += swap
                self.balance += swap
            
        # Manage open positions (SL/TP)
        for pos in list(self.open_positions):
            symbol = pos['symbol']
            if symbol not in current_prices: continue
            
            high = current_highs[symbol]
            low = current_lows[symbol]
            
            # Track highest profit for breakeven
            if pos['type'] == 'BUY':
                unrealized = (high - pos['entry_price']) * pos['remaining_lots'] * self.contract_size(symbol)
            else:
                unrealized = (pos['entry_price'] - low) * pos['remaining_lots'] * self.contract_size(symbol)
            pos['highest_profit'] = max(pos['highest_profit'], unrealized)
            
            # Break-Even Logic: Move SL to entry when profit >= 1R (skip for configured strategies)
            if pos['strategy'] not in self.disable_breakeven_strategies and not pos['breakeven_triggered']:
                risk_distance = abs(pos['entry_price'] - pos['sl'])
                spread = self.spread_map.get(symbol, self.default_spread)
                if pos['type'] == 'BUY':
                    be_threshold = pos['entry_price'] + risk_distance
                    if high >= be_threshold:
                        pos['sl'] = pos['entry_price'] + spread
                        pos['breakeven_triggered'] = True
                else:
                    be_threshold = pos['entry_price'] - risk_distance
                    if low <= be_threshold:
                        pos['sl'] = pos['entry_price'] - spread
                        pos['breakeven_triggered'] = True
            
            # Partial Close Logic: Close 50% at 1.5R (skip for configured strategies)
            if pos['strategy'] not in self.disable_breakeven_strategies and not pos['partial_closed']:
                risk_distance = abs(pos['entry_price'] - pos['sl'])
                if pos['type'] == 'BUY':
                    partial_target = pos['entry_price'] + risk_distance * 1.5
                    if high >= partial_target:
                        half_lots = pos['remaining_lots'] * 0.5
                        self.close_position_partial(pos, partial_target, current_time, "Partial TP 1.5R", half_lots)
                        pos['partial_closed'] = True
                else:
                    partial_target = pos['entry_price'] - risk_distance * 1.5
                    if low <= partial_target:
                        half_lots = pos['remaining_lots'] * 0.5
                        self.close_position_partial(pos, partial_target, current_time, "Partial TP 1.5R", half_lots)
                        pos['partial_closed'] = True
            
            # Check both SL and TP on the same bar; resolve order fairly using entry price as heuristic
            if pos['type'] == 'BUY':
                hit_sl = low <= pos['sl']
                hit_tp = high >= pos['tp']
                if hit_sl and hit_tp:
                    # If low dipped below entry, SL likely hit first (price went down before reversal)
                    if low <= pos['entry_price']:
                        self.close_position(pos, pos['sl'], current_time, "SL")
                    else:
                        self.close_position(pos, pos['tp'], current_time, "TP")
                elif hit_sl:
                    self.close_position(pos, pos['sl'], current_time, "SL")
                elif hit_tp:
                    self.close_position(pos, pos['tp'], current_time, "TP")
            else:
                hit_sl = high >= pos['sl']
                hit_tp = low <= pos['tp']
                if hit_sl and hit_tp:
                    # If high broke above entry, SL likely hit first (price went up before reversal)
                    if high >= pos['entry_price']:
                        self.close_position(pos, pos['sl'], current_time, "SL")
                    else:
                        self.close_position(pos, pos['tp'], current_time, "TP")
                elif hit_sl:
                    self.close_position(pos, pos['sl'], current_time, "SL")
                elif hit_tp:
                    self.close_position(pos, pos['tp'], current_time, "TP")
                    
        # Log equity daily
        if len(self.equity_curve) == 0 or self.equity_curve[-1]['date'] != current_time.date():
            self.equity_curve.append({
                'date': current_time.date(),
                'equity': self.equity,
                'balance': self.balance
            })
