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
    return true_range.rolling(window=period).mean() # Simplified ATR using SMA instead of Wilder's RMA for speed, close enough to MT5

def ADX(df, period=14):
    up = df['high'] - df['high'].shift()
    down = df['low'].shift() - df['low']
    
    pos_dm = np.where((up > down) & (up > 0), up, 0.0)
    neg_dm = np.where((down > up) & (down > 0), down, 0.0)
    
    tr = ATR(df, 1) # True range of 1 period
    
    pos_dm_smooth = pd.Series(pos_dm).ewm(alpha=1/period, adjust=False).mean()
    neg_dm_smooth = pd.Series(neg_dm).ewm(alpha=1/period, adjust=False).mean()
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
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
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
    
    regime = pd.Series(0, index=df.index)
    
    # 1: Trend, 2: Range, 16: Reversal
    regime = np.where(is_exhaustion, regime | 16, regime)
    regime = np.where(~is_exhaustion & is_trend, regime | 1, regime)
    regime = np.where(~is_exhaustion & ~is_trend, regime | 2, regime)
    
    # 4: Expansion, 8: Compression
    regime = np.where(is_expand, regime | 4, regime)
    regime = np.where(~is_expand & is_compression, regime | 8, regime)
    
    return regime
