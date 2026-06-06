from datetime import datetime, timedelta

class NewsFilter:
    """
    Macro/News Events Filter.
    Simulates high-impact news events (like NFP and FOMC) during backtesting
    to prevent the system from entering trades right before massive slippage events.
    """
    def __init__(self, hours_before=1, hours_after=2):
        self.hours_before = hours_before
        self.hours_after = hours_after
        
        self.fomc_months = [1, 3, 5, 6, 7, 9, 11, 12]
        
    def _is_nfp_time(self, dt: datetime) -> bool:
        """NFP is typically the first Friday of the month at 13:30 GMT."""
        if dt.weekday() == 4 and 1 <= dt.day <= 7:
            event_time = dt.replace(hour=13, minute=30, second=0, microsecond=0)
            start_block = event_time - timedelta(hours=self.hours_before)
            end_block = event_time + timedelta(hours=self.hours_after)
            if start_block <= dt <= end_block:
                return True
        return False
        
    def _is_fomc_time(self, dt: datetime) -> bool:
        """FOMC is typically the 3rd Wednesday of specific months at 19:00 GMT."""
        if dt.month in self.fomc_months and dt.weekday() == 2 and 15 <= dt.day <= 21:
            event_time = dt.replace(hour=19, minute=0, second=0, microsecond=0)
            start_block = event_time - timedelta(hours=self.hours_before)
            end_block = event_time + timedelta(hours=self.hours_after)
            if start_block <= dt <= end_block:
                return True
        return False

    def should_trade(self, symbol: str, current_time: datetime) -> bool:
        """
        Returns False if a high-impact news event is currently blocking trading
        for the given symbol.
        """
        # Only apply USD news to USD-pegged or highly correlated instruments
        is_usd_related = 'USD' in symbol or symbol in ['XAUUSD', 'US30', 'NAS100']
        
        if is_usd_related:
            if self._is_nfp_time(current_time) or self._is_fomc_time(current_time):
                return False
                
        return True
