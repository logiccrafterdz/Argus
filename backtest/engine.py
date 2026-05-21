import pandas as pd
import numpy as np
from risk_manager import RiskManager

class BacktestEngine:
    def __init__(self, initial_balance=100000.0):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.equity = initial_balance
        
        self.open_positions = []
        self.closed_trades = []
        self.equity_curve = []
        
        self.risk_manager = RiskManager(initial_balance)
        self.current_time = None
        
        self.ticket_counter = 1

    def calculate_equity(self, current_prices):
        equity = self.balance
        for pos in self.open_positions:
            symbol = pos['symbol']
            if symbol in current_prices:
                current_price = current_prices[symbol]
                lots = pos['remaining_lots']
                if pos['type'] == 'BUY':
                    profit = (current_price - pos['entry_price']) * lots * 100000
                else:
                    profit = (pos['entry_price'] - current_price) * lots * 100000
                equity += profit
        return equity

    def execute_trade(self, symbol, strategy_name, order_type, lot_size, entry_price, sl, tp, comment):
        if self.risk_manager.is_halted:
            return False
            
        if not self.risk_manager.check_exposure(symbol, order_type, self.open_positions):
            return False
            
        # Simplified correlation check could be added here
        
        # Realistic per-symbol spread model (in price units)
        # Based on typical FBS MT5 average spreads
        spread_map = {
            'EURUSD': 0.00012, 'GBPUSD': 0.00014, 'USDJPY': 0.013,
            'USDCHF': 0.00014, 'AUDUSD': 0.00013, 'USDCAD': 0.00016,
            'NZDUSD': 0.00018, 'XAUUSD': 0.35,   # Gold: 35 cents
            'US30': 3.0,       # Dow Jones: 3 points
            'NAS100': 2.5,     # Nasdaq: 2.5 points
        }
        spread = spread_map.get(symbol, 0.00015)
        
        # Dynamic slippage: random 0-30% of spread (simulates real execution variance)
        slippage = spread * np.random.uniform(0, 0.3)
        
        total_cost = spread + slippage
        if order_type == 'BUY':
            entry_price += total_cost
        else:
            entry_price -= total_cost
            
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
        if pos['type'] == 'BUY':
            profit = (close_price - pos['entry_price']) * lots_to_close * 100000
        else:
            profit = (pos['entry_price'] - close_price) * lots_to_close * 100000
            
        # Realistic per-symbol commission
        # Forex: $7/lot round turn, Gold: $3.50/lot, Indices: $0 (built into spread)
        commission_map = {
            'XAUUSD': 3.50,
            'US30': 0.0,
            'NAS100': 0.0,
        }
        commission_per_lot = commission_map.get(symbol, 7.0)
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

    def close_position_partial(self, pos, close_price, close_time, reason, lots_to_close):
        if pos['type'] == 'BUY':
            profit = (close_price - pos['entry_price']) * lots_to_close * 100000
        else:
            profit = (pos['entry_price'] - close_price) * lots_to_close * 100000
            
        commission_map = {'XAUUSD': 3.50, 'US30': 0.0, 'NAS100': 0.0}
        commission = -commission_map.get(pos['symbol'], 7.0) * lots_to_close
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

    def emergency_close_all(self, current_prices):
        for pos in list(self.open_positions):
            symbol = pos['symbol']
            if symbol in current_prices:
                self.close_position(pos, current_prices[symbol], self.current_time, "Circuit Breaker")

    def update(self, current_time, current_prices, current_highs, current_lows):
        self.current_time = current_time
        self.equity = self.calculate_equity(current_prices)
        
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
                unrealized = (high - pos['entry_price']) * pos['lot_size'] * 100000
            else:
                unrealized = (pos['entry_price'] - low) * pos['lot_size'] * 100000
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
