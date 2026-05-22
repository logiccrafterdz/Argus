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
        
        spread_cfg = self.config.get('spread', {})
        self.spread_map = {
            'EURUSD': spread_cfg.get('EURUSD', 0.00012),
            'GBPUSD': spread_cfg.get('GBPUSD', 0.00014),
            'USDJPY': spread_cfg.get('USDJPY', 0.013),
            'USDCHF': spread_cfg.get('USDCHF', 0.00014),
            'AUDUSD': spread_cfg.get('AUDUSD', 0.00013),
            'USDCAD': spread_cfg.get('USDCAD', 0.00016),
            'NZDUSD': spread_cfg.get('NZDUSD', 0.00018),
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
        }
        self.default_commission = self.config.get('execution', {}).get('default_commission', 7.0)
        
        slippage_cfg = self.config.get('execution', {})
        self.slippage_min = slippage_cfg.get('slippage_min', 0.0)
        self.slippage_max = slippage_cfg.get('slippage_max', 0.3)
        self.current_time = None
        self.ticket_counter = 1
        self.is_bankrupt = False
        self.bankruptcy_threshold = initial_balance * 0.05
        self.peak_balance = initial_balance
        self.max_drawdown_pct = self.config.get('risk', {}).get('max_drawdown_pct', 50.0)
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
        t_size = self.tick_size(symbol)
        t_value = self.tick_value(symbol)
        risk_ticks = risk_distance / t_size
        risk_per_lot = risk_ticks * t_value
        if risk_per_lot <= 0:
            return 0.0
        lot = risk_amount / risk_per_lot
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
                if pos['type'] == 'BUY':
                    profit = (current_price - pos['entry_price']) * lots * cs
                else:
                    profit = (pos['entry_price'] - current_price) * lots * cs
                equity += profit
        return equity

    def execute_trade(self, symbol, strategy_name, order_type, lot_size, entry_price, sl, tp, comment):
        if self.is_bankrupt or self.risk_manager.is_halted:
            return False
            
        if not self.risk_manager.check_exposure(symbol, order_type, self.open_positions):
            return False
            
        # Simplified correlation check could be added here
        
        # Realistic per-symbol spread model (in price units)
        # Based on typical FBS MT5 average spreads
        spread = self.spread_map.get(symbol, self.default_spread)
        
        # Dynamic slippage: random 0-30% of spread (simulates real execution variance)
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
            
        pos = {
            'ticket': self.ticket_counter,
            'symbol': symbol,
            'strategy': strategy_name,
            'type': order_type,
            'lot_size': lot_size,
            'entry_price': entry_price,
            'sl': sl,
            'tp': tp,
            'entry_time': self.current_time,
            'comment': comment,
            'highest_profit': 0.0,
            'breakeven_triggered': False,
            'partial_closed': False,
            'remaining_lots': lot_size
        }
        self.open_positions.append(pos)
        self.ticket_counter += 1
        return True

    def close_position(self, pos, close_price, close_time, reason):
        lots_to_close = pos['remaining_lots']
        cs = self.contract_size(pos['symbol'])
        if pos['type'] == 'BUY':
            profit = (close_price - pos['entry_price']) * lots_to_close * cs
        else:
            profit = (pos['entry_price'] - close_price) * lots_to_close * cs
            
        # Realistic per-symbol commission
        # Forex: $7/lot round turn, Gold: $3.50/lot, Indices: $0 (built into spread)
        commission_per_lot = self.commission_map.get(pos['symbol'], self.default_commission)
        commission = -commission_per_lot * lots_to_close
        profit += commission
        
        self.balance += profit
        self.closed_trades.append({
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
            'reason': reason
        })
        pos['remaining_lots'] -= lots_to_close
        if pos['remaining_lots'] <= 0.001:
            self.open_positions.remove(pos)

        if self.balance < self.bankruptcy_threshold and not self.is_bankrupt:
            self.is_bankrupt = True
            self.logger.warning(f"BANKRUPT at {close_time}: balance={self.balance:.2f} < threshold={self.bankruptcy_threshold:.2f}")

    def close_position_partial(self, pos, close_price, close_time, reason, lots_to_close):
        cs = self.contract_size(pos['symbol'])
        if pos['type'] == 'BUY':
            profit = (close_price - pos['entry_price']) * lots_to_close * cs
        else:
            profit = (pos['entry_price'] - close_price) * lots_to_close * cs
            
        commission = -self.commission_map.get(pos['symbol'], self.default_commission) * lots_to_close
        profit += commission
        
        self.balance += profit
        self.closed_trades.append({
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
            'reason': reason
        })
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
        self.equity = self.calculate_equity(current_prices)
        self.peak_balance = max(self.peak_balance, self.balance)
        dd_from_peak = ((self.peak_balance - self.balance) / self.peak_balance) * 100
        if dd_from_peak >= self.max_drawdown_pct and not self.is_bankrupt:
            self.is_bankrupt = True
            self.logger.warning(f"MAX DRAWDOWN at {current_time}: peak={self.peak_balance:.2f}, balance={self.balance:.2f}, dd={dd_from_peak:.1f}%")
        
        if self.risk_manager.update(current_time, self.equity):
            self.emergency_close_all(current_prices)
            
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
            
            # Break-Even Logic: Move SL to entry when profit >= 1R
            if not pos['breakeven_triggered']:
                risk_distance = abs(pos['entry_price'] - pos['sl'])
                if pos['type'] == 'BUY':
                    be_threshold = pos['entry_price'] + risk_distance
                    if high >= be_threshold:
                        pos['sl'] = pos['entry_price']
                        pos['breakeven_triggered'] = True
                else:
                    be_threshold = pos['entry_price'] - risk_distance
                    if low <= be_threshold:
                        pos['sl'] = pos['entry_price']
                        pos['breakeven_triggered'] = True
            
            # Partial Close Logic: Close 50% at 1.5R
            if not pos['partial_closed']:
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
            
            if pos['type'] == 'BUY':
                if low <= pos['sl']:
                    self.close_position(pos, pos['sl'], current_time, "SL")
                elif high >= pos['tp']:
                    self.close_position(pos, pos['tp'], current_time, "TP")
            else:
                if high >= pos['sl']:
                    self.close_position(pos, pos['sl'], current_time, "SL")
                elif low <= pos['tp']:
                    self.close_position(pos, pos['tp'], current_time, "TP")
                    
        # Log equity daily
        if len(self.equity_curve) == 0 or self.equity_curve[-1]['date'] != current_time.date():
            self.equity_curve.append({
                'date': current_time.date(),
                'equity': self.equity,
                'balance': self.balance
            })
