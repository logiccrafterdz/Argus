"""
Sentiment Analysis Integration for Argus.

Provides:
  - FearGreedIndex: proxy VIX/fear-greed from market data (no external API needed)
  - NewsSentiment: keyword-based news sentiment for economic events
  - SentimentFilter: combines signals to flag whether a trade direction aligns with sentiment

Designed to run without external APIs — all inputs derived from OHLC data or
the existing economic calendar integration.
"""

import numpy as np
import pandas as pd
from datetime import datetime


class FearGreedIndex:
    """
    Computes a fear-greed proxy from market data without external API.

    Components (normalized 0-100, then averaged):
      1. VIX proxy:  (1yr rolling high - current close) / range  → 100 = low VIX = greed
      2. Put/Call proxy: volume ratio of down-days to up-days
      3. Price momentum: (close / 50d SMA - 1) normalized
      4. Volatility ratio: current ATR / 20d avg ATR

    Score: 0 = extreme fear, 100 = extreme greed
    """

    def __init__(self, lookback=365):
        self.lookback = lookback

    def compute(self, df):
        """Return pd.Series of fear-greed index (0-100) aligned to df.index."""
        close = df['close']
        high = df['high']
        low = df['low']

        # 1. Market volatility proxy (inverse: low vol = greed)
        rolling_high = close.rolling(self.lookback).max()
        rolling_low = close.rolling(self.lookback).min()
        vol_range = (rolling_high - rolling_low).replace(0, np.nan)
        vix_proxy = 100 * (1 - (rolling_high - close) / vol_range)
        vix_proxy = vix_proxy.fillna(50).clip(0, 100)

        # 2. Momentum: distance from 50d SMA (normalized to 0-100)
        sma50 = close.rolling(50).mean()
        momentum = (close / sma50 - 1).replace(0, np.nan)
        mom_std = momentum.rolling(50).std(ddof=1) + 1e-10
        momentum_norm = ((momentum / mom_std) * 10 + 50).clip(0, 100)

        # 3. Volatility ratio: low relative vol = greed
        if 'atr' in df.columns:
            atr = df['atr']
        else:
            tr = pd.concat([
                high - low,
                (high - close.shift()).abs(),
                (low - close.shift()).abs()
            ], axis=1).max(axis=1)
            atr = tr.rolling(14).mean()
        atr_sma = atr.rolling(20).mean().replace(0, np.nan)
        vol_ratio = (atr_sma / atr).replace(0, np.nan) * 50
        vol_ratio = vol_ratio.fillna(50).clip(0, 100)

        # Average components
        fear_greed = (vix_proxy * 0.4 + momentum_norm * 0.35 + vol_ratio * 0.25)
        fear_greed = fear_greed.clip(0, 100)
        return fear_greed

    def classify(self, value):
        """Classify a single fear-greed value into a label."""
        if value >= 75: return "EXTREME_GREED"
        if value >= 60: return "GREED"
        if value >= 40: return "NEUTRAL"
        if value >= 25: return "FEAR"
        return "EXTREME_FEAR"


class MacroEventSentiment:
    """
    Assigns directional bias to scheduled macro events.
    Maps economic calendar events to likely market impact.

    Rules-based: rate hikes → bearish for FX pairs,
    strong data → bullish for currency, etc.
    """

    EVENT_SENTIMENT = {
        'CPI': {'impact': 0.8, 'direction': 'bearish_if_high'},  # high CPI = bearish bonds/bullish USD
        'NFP': {'impact': 0.9, 'direction': 'bearish_if_high'},
        'FOMC': {'impact': 1.0, 'direction': 'hawkish_if_hike'},
        'GDP': {'impact': 0.7, 'direction': 'bullish_if_high'},
        'PMI': {'impact': 0.6, 'direction': 'bullish_if_high'},
        'Retail Sales': {'impact': 0.6, 'direction': 'bullish_if_high'},
    }

    def get_event_bias(self, event_name, actual, forecast):
        """
        Return directional bias: 1 = bullish, -1 = bearish, 0 = neutral.
        actual/forecast as floats.
        """
        meta = self.EVENT_SENTIMENT.get(event_name)
        if not meta:
            return 0
        diff = actual - forecast
        if abs(diff) < 0.1:
            return 0
        if meta['direction'] == 'bullish_if_high':
            return 1 if diff > 0 else -1
        elif meta['direction'] == 'bearish_if_high':
            return -1 if diff > 0 else 1
        elif meta['direction'] == 'hawkish_if_hike':
            return -1 if diff > 0 else 1  # hawkish = bearish for risk
        return 0


class NewsKeywordSentiment:
    """
    Lightweight keyword-based sentiment for news headlines.
    Suitable as a drop-in until FinGPT or an LLM-based system is integrated.
    """

    POSITIVE_KW = [
        'beat earnings', 'outperform', 'upgrade', 'bullish', 'positive outlook',
        'rate cut', 'stimulus', 'expansion', 'growth', 'recovery',
        'breakthrough', 'partnership', 'buyback', 'dividend increase'
    ]
    NEGATIVE_KW = [
        'miss earnings', 'downgrade', 'downturn', 'recession', 'inflation spike',
        'rate hike', 'slowdown', 'default', 'bankruptcy', 'sanctions',
        'selloff', 'crash', 'volatility spike', 'uncertainty', 'downgrade'
    ]

    def score_headline(self, headline):
        """Return sentiment score: -1 (bearish) to +1 (bullish)."""
        headline_lower = headline.lower()
        pos_count = sum(1 for kw in self.POSITIVE_KW if kw in headline_lower)
        neg_count = sum(1 for kw in self.NEGATIVE_KW if kw in headline_lower)
        total = pos_count + neg_count
        if total == 0:
            return 0
        return (pos_count - neg_count) / total


class SentimentFilter:
    """
    Combines fear-greed, event, and news sentiment into a single
    signal filter. Returns whether a trade direction is supported
    by current sentiment.
    """

    def __init__(self):
        self.fear_greed = FearGreedIndex()
        self.macro = MacroEventSentiment()
        self.news = NewsKeywordSentiment()
        self._fg_series = None

    def feed_prices(self, df):
        """Pre-compute fear-greed from price data."""
        self._fg_series = self.fear_greed.compute(df)

    def get_sentiment_score(self, timestamp, symbol='EURUSD'):
        """
        Aggregate sentiment score: -1 (bearish) to +1 (bullish).
        Uses fear-greed index as primary, with room for news/macro overlay.
        """
        fg_score = 0
        if self._fg_series is not None and timestamp in self._fg_series.index:
            fg_val = self._fg_series.loc[timestamp]
            fg_score = (fg_val - 50) / 50  # -1 to +1

        return fg_score

    def should_trade(self, direction, timestamp, symbol='EURUSD'):
        """
        Return True if sentiment supports the trade direction.
        direction: 'BUY' or 'SELL'.
        """
        score = self.get_sentiment_score(timestamp, symbol)
        if direction == 'BUY' and score < -0.3:
            return False
        if direction == 'SELL' and score > 0.3:
            return False
        return True
