class BaseStrategy:
    def __init__(self, name, category, regime_mask, session_mask):
        self.name = name
        self.category = category
        self.regime_mask = regime_mask
        self.session_mask = session_mask

    def prepare_data(self, df):
        """Pre-calculate indicators for the entire dataframe"""
        pass

    def generate_signals(self, df):
        """
        Returns a list of signals or updates the dataframe with 'signal' column.
        Signal format:
        1 for BUY, -1 for SELL, 0 for neutral
        Needs to also return sl and tp prices.
        """
        pass

    def check_regime(self, current_regime):
        if self.regime_mask == 31: # REGIME_ALL
            return True
        return (current_regime & self.regime_mask) != 0
        
    def check_session(self, current_session):
        if self.session_mask == 7: # SESSION_ALL
            return True
        if current_session == 0:
            return False
        return (current_session & self.session_mask) != 0
