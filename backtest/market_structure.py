import numpy as np

def get_swing_highs(df, radius=2):
    """Returns a boolean series where True indicates a swing high"""
    highs = df['high'].values
    n = len(highs)
    is_swing = np.zeros(n, dtype=bool)
    
    for i in range(radius, n - radius):
        window = highs[i-radius : i+radius+1]
        if highs[i] == np.max(window) and sum(window == highs[i]) == 1:
            is_swing[i] = True
            
    return is_swing

def get_swing_lows(df, radius=2):
    """Returns a boolean series where True indicates a swing low"""
    lows = df['low'].values
    n = len(lows)
    is_swing = np.zeros(n, dtype=bool)
    
    for i in range(radius, n - radius):
        window = lows[i-radius : i+radius+1]
        if lows[i] == np.min(window) and sum(window == lows[i]) == 1:
            is_swing[i] = True
            
    return is_swing

def get_recent_swing(df, is_swing_series, index, lookback, price_col):
    """Finds the most recent swing high/low before the current index within lookback."""
    start_idx = max(0, index - lookback)
    for i in range(index - 1, start_idx - 1, -1):
        if is_swing_series[i]:
            return df[price_col].iloc[i]
    return np.nan

def precompute_swings(df, radius=2):
    """Precompute swing high and low arrays for the entire dataframe.
    Call once per backtest run to avoid recomputing on every index.
    Returns (swing_highs, swing_lows) as numpy boolean arrays.
    """
    swing_highs = get_swing_highs(df, radius)
    swing_lows = get_swing_lows(df, radius)
    return swing_highs, swing_lows

def is_bullish_structure(df, index, lookback=30, radius=2, swing_lows=None):
    # Higher highs and higher lows
    if swing_lows is None:
        is_low = get_swing_lows(df, radius)
    else:
        is_low = swing_lows
    start_idx = max(0, index - lookback)
    
    lows = []
    for i in range(index - 1, start_idx - 1, -1):
        if is_low[i]:
            lows.append(df['low'].iloc[i])
            if len(lows) == 2:
                break
    
    if len(lows) == 2:
        return lows[0] > lows[1] # Last low > Previous low
    return False

def is_bearish_structure(df, index, lookback=30, radius=2, swing_highs=None):
    # Lower highs and lower lows
    if swing_highs is None:
        is_high = get_swing_highs(df, radius)
    else:
        is_high = swing_highs
    start_idx = max(0, index - lookback)
    
    highs = []
    for i in range(index - 1, start_idx - 1, -1):
        if is_high[i]:
            highs.append(df['high'].iloc[i])
            if len(highs) == 2:
                break
                
    if len(highs) == 2:
        return highs[0] < highs[1] # Last high < Previous high
    return False

def get_liquidity_pools(df, index, lookback=50, radius=2, threshold_points=0.00050, swing_highs=None, swing_lows=None):
    if swing_highs is None:
        is_high = get_swing_highs(df, radius)
    else:
        is_high = swing_highs
    if swing_lows is None:
        is_low = get_swing_lows(df, radius)
    else:
        is_low = swing_lows
    
    start_idx = max(0, index - lookback)
    
    swings_h = [(i, df['high'].iloc[i]) for i in range(start_idx, index) if is_high[i]]
    swings_l = [(i, df['low'].iloc[i]) for i in range(start_idx, index) if is_low[i]]
    
    liq_high = np.nan
    liq_low = np.nan
    
    # EQH
    for i, h1 in enumerate(swings_h):
        matches = 0
        max_h = h1[1]
        for j, h2 in enumerate(swings_h):
            if i != j and abs(h1[1] - h2[1]) <= threshold_points:
                matches += 1
                max_h = max(max_h, h2[1])
        if matches >= 1:
            liq_high = max_h
            break
            
    # EQL
    for i, l1 in enumerate(swings_l):
        matches = 0
        min_l = l1[1]
        for j, l2 in enumerate(swings_l):
            if i != j and abs(l1[1] - l2[1]) <= threshold_points:
                matches += 1
                min_l = min(min_l, l2[1])
        if matches >= 1:
            liq_low = min_l
            break
            
    return liq_high, liq_low
