import pandas as pd
import numpy as np
from datetime import timedelta

class RiskManager:
    def __init__(self, initial_balance):
        self.initial_balance = initial_balance
        self.daily_high_water_mark = initial_balance
        self.weekly_high_water_mark = initial_balance
        self.monthly_high_water_mark = initial_balance
        
        self.max_daily_dd = 3.0
        self.max_weekly_dd = 8.0
        self.max_monthly_dd = 15.0
        
        self.is_halted = False
        self.last_date = None
        self.last_week = None
        self.last_month = None

    def update(self, current_time, equity):
        # Reset HWMs on new day/week/month
        date = current_time.date()
        week = current_time.isocalendar()[1]
        month = current_time.month
        
        if self.last_date != date:
            self.last_date = date
            self.daily_high_water_mark = equity
            self.is_halted = False # Reset halt on new day
            
        if self.last_week != week:
            self.last_week = week
            self.weekly_high_water_mark = equity
            
        if self.last_month != month:
            self.last_month = month
            self.monthly_high_water_mark = equity
            
        # Update HWMs
        self.daily_high_water_mark = max(self.daily_high_water_mark, equity)
        self.weekly_high_water_mark = max(self.weekly_high_water_mark, equity)
        self.monthly_high_water_mark = max(self.monthly_high_water_mark, equity)
        
        # Check DD
        daily_dd = ((self.daily_high_water_mark - equity) / self.daily_high_water_mark) * 100
        weekly_dd = ((self.weekly_high_water_mark - equity) / self.weekly_high_water_mark) * 100
        monthly_dd = ((self.monthly_high_water_mark - equity) / self.monthly_high_water_mark) * 100
        
        if not self.is_halted:
            if daily_dd >= self.max_daily_dd or weekly_dd >= self.max_weekly_dd or monthly_dd >= self.max_monthly_dd:
                self.is_halted = True
                return True # Trigger Emergency Close
        return False
        
    def check_exposure(self, symbol, order_type, open_positions, max_exposure=2):
        net_exposure = 0
        for pos in open_positions:
            if pos['symbol'] == symbol:
                if pos['type'] == 'BUY':
                    net_exposure += 1
                elif pos['type'] == 'SELL':
                    net_exposure -= 1
                    
        if order_type == 'BUY' and net_exposure >= max_exposure:
            return False
        if order_type == 'SELL' and net_exposure <= -max_exposure:
            return False
        return True

    def calculate_lot_size(self, symbol, risk_percent, risk_dist_points, equity, tick_value=1.0, tick_size=0.00001):
        if risk_dist_points <= 0:
            return 0.0
            
        risk_amount = equity * (risk_percent / 100.0)
        lot = risk_amount / ((risk_dist_points / tick_size) * tick_value)
        
        # simplified limits
        min_vol = 0.01
        max_vol = 100.0
        step_vol = 0.01
        
        lot = np.floor(lot / step_vol) * step_vol
        lot = max(min_vol, min(max_vol, lot))
        return lot
    def check_correlation(self, symbol, open_positions, correlation_matrix, threshold=0.8):
        # Prevent taking a trade if it is highly correlated with a currently open position
        if correlation_matrix is None or symbol not in correlation_matrix:
            return True
        for pos in open_positions:
            open_symbol = pos['symbol']
            if open_symbol in correlation_matrix.columns:
                corr = correlation_matrix.loc[symbol, open_symbol]
                # If correlation is > threshold, and we are taking the same direction trade, reject
                if corr > threshold:
                    return False
        return True
