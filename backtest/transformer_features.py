"""
Transformer-based feature extraction for price prediction.

Generates structured time-series features suitable for:
  - Temporal Fusion Transformer (TFT)
  - LightGBM/XGBoost with time-series features
  - Any downstream ML model

Feature groups:
  1. Price-derived: returns, log returns, rolling volatility
  2. Technical: EMA cross, RSI, MACD, BB width
  3. Cross-asset: correlations, relative strength
  4. Temporal: time-of-day, day-of-week, session

Designed to output a flat DataFrame suitable for any ML pipeline.
Does NOT depend on deep learning frameworks — features are
framework-agnostic and can be fed into PyTorch, TensorFlow, sklearn, etc.
"""

import numpy as np
import pandas as pd
from indicators import EMA, SMA, ATR


def compute_features(df, prefix=''):
    """
    Compute full feature set from OHLC DataFrame.

    Returns a DataFrame with the same index as df and columns:
      {prefix}ret_1, {prefix}ret_5, {prefix}ret_20,
      {prefix}vol_5, {prefix}vol_20,
      {prefix}ema_9, {prefix}ema_21, {prefix}ema_50,
      {prefix}rsi_14, {prefix}bb_width, {prefix}atr_14,
      {prefix}adx_14, {prefix}macd, {prefix}macd_signal,
      {prefix}hour, {prefix}day_of_week,
      {prefix}session_asia, {prefix}session_london, {prefix}session_ny
    """
    close = df['close']
    high = df['high']
    low = df['low']
    vol = df.get('volume', pd.Series(1.0, index=df.index))

    features = pd.DataFrame(index=df.index)

    # Returns
    features[f'{prefix}ret_1'] = close.pct_change(1)
    features[f'{prefix}ret_5'] = close.pct_change(5)
    features[f'{prefix}ret_20'] = close.pct_change(20)

    # Rolling volatility
    features[f'{prefix}vol_5'] = close.pct_change().rolling(5).std()
    features[f'{prefix}vol_20'] = close.pct_change().rolling(20).std()

    # EMAs
    features[f'{prefix}ema_9'] = EMA(close, 9)
    features[f'{prefix}ema_21'] = EMA(close, 21)
    features[f'{prefix}ema_50'] = EMA(close, 50)

    # RSI
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    features[f'{prefix}rsi_14'] = 100 - (100 / (1 + rs))

    # Bollinger Band width
    sma20 = SMA(close, 20)
    std20 = close.rolling(20).std()
    features[f'{prefix}bb_width'] = 2 * std20 / sma20.replace(0, np.nan)

    # ATR
    features[f'{prefix}atr_14'] = ATR(df, 14)

    # ADX (simplified)
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    atr_ = tr.rolling(14).mean()
    up = high.diff()
    down = -low.diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0)
    minus_dm = np.where((down > up) & (down > 0), down, 0)
    plus_di = 100 * SMA(pd.Series(plus_dm, index=df.index), 14) / atr_.replace(0, np.nan)
    minus_di = 100 * SMA(pd.Series(minus_dm, index=df.index), 14) / atr_.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    features[f'{prefix}adx_14'] = SMA(dx, 14)

    # MACD
    macd = EMA(close, 12) - EMA(close, 26)
    features[f'{prefix}macd'] = macd
    features[f'{prefix}macd_signal'] = EMA(macd, 9)

    # Temporal features
    if hasattr(df.index, 'hour'):
        features[f'{prefix}hour'] = df.index.hour
        features[f'{prefix}day_of_week'] = df.index.dayofweek
        asia = ((df.index.hour >= 0) & (df.index.hour < 8)).astype(int)
        london = ((df.index.hour >= 8) & (df.index.hour < 16)).astype(int)
        ny = ((df.index.hour >= 13) & (df.index.hour < 22)).astype(int)
        features[f'{prefix}session_asia'] = asia
        features[f'{prefix}session_london'] = london
        features[f'{prefix}session_ny'] = ny

    # Volume change
    features[f'{prefix}vol_change'] = vol.pct_change()

    # Fill NaN
    features = features.fillna(method='bfill').fillna(0)
    return features


def compute_cross_asset_features(symbol_data_dict, target_symbol, lookback=50):
    """
    Compute cross-asset features for a target symbol relative to all others.
    Returns correlation and relative strength features.
    """
    closes = {}
    for sym, data in symbol_data_dict.items():
        for tf in ('H1', 'M15', 'H4'):
            if tf in data:
                closes[sym] = data[tf]['close']
                break

    if target_symbol not in closes or len(closes) < 2:
        return pd.DataFrame()

    target_close = closes[target_symbol]
    rows = []
    for sym, close_series in closes.items():
        if sym == target_symbol:
            continue
        aligned = pd.concat([target_close, close_series], axis=1, join='inner')
        aligned.columns = ['target', sym]
        corr = aligned['target'].corr(aligned[sym])
        rel_strength = (aligned['target'].iloc[-1] / aligned['target'].iloc[-lookback] - 1) - \
                       (aligned[sym].iloc[-1] / aligned[sym].iloc[-lookback] - 1)
        rows.append({'symbol': sym, 'correlation': corr, 'relative_strength': rel_strength})

    return pd.DataFrame(rows)
