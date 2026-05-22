import pandas as pd
import numpy as np
from datetime import timedelta, time

class RiskManager:
    def __init__(self, initial_balance, prop_firm_mode=False):
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
        
        # Prop Firm Mode
        self.prop_firm_mode = prop_firm_mode
        self.news_blocked = False
        self.news_windows = [
            (time(8, 30), time(9, 0)),   # US Early News
            (time(10, 0), time(10, 30)),  # US Mid News
            (time(13, 30), time(14, 0)),  # US Afternoon News
            (time(14, 0), time(14, 30)),  # FOMC / NFP Window
        ]
        self.weekend_closure_enabled = prop_firm_mode

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
    def check_correlation(self, symbol, order_type, open_positions, correlation_matrix, threshold=0.8):
        if correlation_matrix is None or symbol not in correlation_matrix:
            return True
        for pos in open_positions:
            open_symbol = pos['symbol']
            if open_symbol in correlation_matrix.columns:
                corr = correlation_matrix.loc[symbol, open_symbol]
                if abs(corr) > threshold:
                    # Same direction: high positive corr = double exposure -> reject
                    # Opposite direction: high negative corr = effective double exposure -> reject
                    if order_type == pos['type'] and corr > threshold:
                        return False
                    if order_type != pos['type'] and corr < -threshold:
                        return False
        return True

    def is_news_blocked(self, current_time):
        if not self.prop_firm_mode:
            return False
        current_hour_min = current_time.time()
        for start, end in self.news_windows:
            if start <= current_hour_min <= end:
                return True
        return False

    def is_weekend_closure(self, current_time):
        if not self.weekend_closure_enabled:
            return False
        day = current_time.weekday()
        hour = current_time.hour
        if day == 4 and hour >= 20:
            return True
        if day >= 5:
            return True
        return False

    def should_close_weekend_positions(self, current_time, open_positions):
        if not self.weekend_closure_enabled:
            return []
        if current_time.weekday() == 4 and current_time.hour >= 20:
            return list(open_positions)
        return []
