import pandas as pd
import numpy as np

def EMA(series, period):
    return series.ewm(span=period, adjust=False).mean()

def SMA(series, period):
    return series.rolling(window=period).mean()

def ATR(df, period=14):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    return true_range.ewm(alpha=1/period, adjust=False).mean() # Wilder's RMA (matches MT5)

def ADX(df, period=14):
    up = df['high'] - df['high'].shift()
    down = df['low'].shift() - df['low']
    
    pos_dm = np.where((up > down) & (up > 0), up, 0.0)
    neg_dm = np.where((down > up) & (down > 0), down, 0.0)
    
    tr = ATR(df, 1) # True range of 1 period
    
    pos_dm_smooth = pd.Series(pos_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean()
    neg_dm_smooth = pd.Series(neg_dm, index=df.index).ewm(alpha=1/period, adjust=False).mean()
    tr_smooth = tr.ewm(alpha=1/period, adjust=False).mean()
    
    plus_di = 100 * (pos_dm_smooth / tr_smooth)
    minus_di = 100 * (neg_dm_smooth / tr_smooth)
    
    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.ewm(alpha=1/period, adjust=False).mean()
    
    return adx, plus_di, minus_di

def BollingerBands(series, period=20, std_dev=2):
    sma = SMA(series, period)
    std = series.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, sma, lower

def RSI(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def MarketRegime(df):
    """
    Returns a series mapping to the Argus Market Regime bitmask:
    REGIME_TREND = 1
    REGIME_RANGE = 2
    REGIME_EXPANSION = 4
    REGIME_COMPRESSION = 8
    REGIME_REVERSAL = 16
    """
    adx, _, _ = ADX(df, 14)
    atr = ATR(df, 14)
    atr_sma = SMA(atr, 20)
    
    atr_ratio = atr / atr_sma.replace(0, np.nan)
    atr_ratio = atr_ratio.fillna(1.0)
    
    is_trend = adx > 25.0
    is_exhaustion = adx >= 45.0
    is_expand = atr_ratio > 1.3
    is_compression = atr_ratio < 0.7
    
    regime = np.zeros(len(df), dtype=int)
    
    # 1: Trend, 2: Range, 16: Reversal
    regime = np.where(is_exhaustion, regime | 16, regime)
    regime = np.where(~is_exhaustion & is_trend, regime | 1, regime)
    regime = np.where(~is_exhaustion & ~is_trend, regime | 2, regime)
    
    # 4: Expansion, 8: Compression
    regime = np.where(is_expand, regime | 4, regime)
    regime = np.where(~is_expand & is_compression, regime | 8, regime)
    
    return pd.Series(regime, index=df.index)
def SuperTrend(df, period=10, multiplier=3):
    atr = ATR(df, period)
    hl2 = (df['high'] + df['low']) / 2
    final_upperband = hl2 + (multiplier * atr)
    final_lowerband = hl2 - (multiplier * atr)
    
    supertrend = pd.Series(0.0, index=df.index)
    direction = pd.Series(1, index=df.index)
    
    for i in range(1, len(df.index)):
        if df['close'].iloc[i] > final_upperband.iloc[i-1]:
            direction.iloc[i] = 1
        elif df['close'].iloc[i] < final_lowerband.iloc[i-1]:
            direction.iloc[i] = -1
        else:
            direction.iloc[i] = direction.iloc[i-1]
            if direction.iloc[i] == 1 and final_lowerband.iloc[i] < final_lowerband.iloc[i-1]:
                final_lowerband.iloc[i] = final_lowerband.iloc[i-1]
            if direction.iloc[i] == -1 and final_upperband.iloc[i] > final_upperband.iloc[i-1]:
                final_upperband.iloc[i] = final_upperband.iloc[i-1]
                
        if direction.iloc[i] == 1:
            supertrend.iloc[i] = final_lowerband.iloc[i]
        else:
            supertrend.iloc[i] = final_upperband.iloc[i]
            
    return supertrend, direction

def DonchianChannels(df, period=20):
    upper = df['high'].rolling(window=period).max()
    lower = df['low'].rolling(window=period).min()
    middle = (upper + lower) / 2
    return upper, middle, lower

def VWAP(df):
    v = df['tick_volume']
    tp = (df['high'] + df['low'] + df['close']) / 3
    # Daily VWAP typically resets each day
    if isinstance(df.index, pd.DatetimeIndex):
        df['date'] = df.index.date
    else:
        df['date'] = df['time'].apply(lambda x: x.date())
    vwap = (tp * v).groupby(df['date']).cumsum() / v.groupby(df['date']).cumsum()
    return vwap

def KeltnerChannels(df, period=20, atr_period=10, multiplier=2):
    ema = EMA(df['close'], period)
    atr = ATR(df, atr_period)
    upper = ema + (multiplier * atr)
    lower = ema - (multiplier * atr)
    return upper, ema, lower
