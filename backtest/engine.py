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
                if pos['type'] == 'BUY':
                    profit = (current_price - pos['entry_price']) * pos['lot_size'] * 100000 # simplified pnl
                else:
                    profit = (pos['entry_price'] - current_price) * pos['lot_size'] * 100000
                equity += profit
        return equity

    def execute_trade(self, symbol, strategy_name, order_type, lot_size, entry_price, sl, tp, comment):
        if self.risk_manager.is_halted:
            return False
            
        if not self.risk_manager.check_exposure(symbol, order_type, self.open_positions):
            return False
            
        # Simplified correlation check could be added here
        
        # Apply spread and slippage (simplified)
        spread = 0.00015 if "JPY" not in symbol else 0.015
        if order_type == 'BUY':
            entry_price += spread
        else:
            entry_price -= spread
            
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
            'highest_profit': 0.0
        }
        self.open_positions.append(pos)
        self.ticket_counter += 1
        return True

    def close_position(self, pos, close_price, close_time, reason):
        if pos['type'] == 'BUY':
            profit = (close_price - pos['entry_price']) * pos['lot_size'] * 100000
        else:
            profit = (pos['entry_price'] - close_price) * pos['lot_size'] * 100000
            
        # Apply commission
        commission = -7.0 * pos['lot_size']
        profit += commission
        
        self.balance += profit
        self.closed_trades.append({
            'ticket': pos['ticket'],
            'symbol': pos['symbol'],
            'strategy': pos['strategy'],
            'type': pos['type'],
            'lot_size': pos['lot_size'],
            'entry_time': pos['entry_time'],
            'close_time': close_time,
            'entry_price': pos['entry_price'],
            'close_price': close_price,
            'profit': profit,
            'reason': reason
        })
        self.open_positions.remove(pos)

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
