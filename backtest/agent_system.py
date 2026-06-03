"""
Multi-Agent Architecture for ARGUS.

Agents:
  - MacroAgent:   analyses economic data, central bank policy, geopol risk
  - TechAgent:    runs strategy signals, classifies technical setup
  - SentimentAgent: market sentiment (fear-greed, news, positioning)
  - RiskAgent:    position sizing, exposure limits, correlation check
  - ExecutorAgent: final trade assembly + execution

Communication:
  agents produce signals (dicts) consumed by the next agent in the pipeline.
  Final output is a vetted trade order ready for execution.

Flow:
  MacroAgent ──→ TechAgent ──→ SentimentAgent ──→ RiskAgent ──→ ExecutorAgent
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Optional, List, Dict


@dataclass
class SignalVote:
    agent: str
    symbol: str
    direction: Optional[str]  # 'BUY', 'SELL', or None = neutral
    confidence: float         # 0.0 to 1.0
    tp_mult: float = 4.0
    sl_mult: float = 1.5
    reason: str = ''


@dataclass
class TradeOrder:
    symbol: str
    direction: str
    lots: float
    entry_price: float
    tp: float
    sl: float
    strategy: str
    confidence: float
    reason: str = ''


class MacroAgent:
    """Analyses macro environment and sets directional bias per symbol."""

    def __init__(self):
        self.bias = {}  # symbol -> 'BULLISH'/'BEARISH'/'NEUTRAL'

    def analyze(self, fear_greed: float, regime: dict, rates_outlook: str = 'NEUTRAL'):
        """
        Set macro bias based on:
          - fear-greed index (extreme readings = reversal likelihood)
          - HMM regime (trend = persist, reversal = fade)
          - rates outlook (hawkish = bearish risk)
        """
        self.bias = {}
        for sym in ['EURUSD', 'GBPUSD', 'USDJPY', 'XAUUSD', 'US30', 'NAS100']:
            score = 0
            fear_greed_weight = 0.0
            if fear_greed >= 80:
                fear_greed_weight = 1.0  # extreme greed → bearish reversal
            elif fear_greed <= 20:
                fear_greed_weight = -1.0  # extreme fear → bullish reversal
            else:
                fear_greed_weight = (fear_greed - 50) / 50

            score += fear_greed_weight * 0.3

            regime_label = regime.get(sym, {}).get('regime', 'RANGE')
            if regime_label in ('TREND', 'TREND_EXPANSION'):
                score += 0.2 * (1 if fear_greed > 50 else -1)
            elif regime_label == 'REVERSAL':
                score += -0.3 * (1 if fear_greed > 50 else -1)

            if rates_outlook == 'HAWKISH':
                if sym in ('EURUSD', 'GBPUSD', 'XAUUSD'):
                    score -= 0.2
                elif sym == 'USDJPY':
                    score += 0.2
            elif rates_outlook == 'DOVISH':
                if sym in ('EURUSD', 'GBPUSD', 'XAUUSD'):
                    score += 0.2
                elif sym == 'USDJPY':
                    score -= 0.2

            if score > 0.15:
                self.bias[sym] = 'BULLISH'
            elif score < -0.15:
                self.bias[sym] = 'BEARISH'
            else:
                self.bias[sym] = 'NEUTRAL'

    def vote(self, symbol: str, direction: str) -> SignalVote:
        """Check if a trade direction aligns with macro view."""
        bias = self.bias.get(symbol, 'NEUTRAL')
        if bias == 'NEUTRAL':
            return SignalVote('macro', symbol, direction, 0.6, reason='macro neutral')
        aligned = (direction == 'BUY' and bias == 'BULLISH') or \
                  (direction == 'SELL' and bias == 'BEARISH')
        if aligned:
            return SignalVote('macro', symbol, direction, 0.8, reason=f'macro aligned ({bias})')
        return SignalVote('macro', symbol, None, 0.2, reason=f'macro opposed ({bias})')


class TechAgent:
    """Evaluates strategy signals and produces technical votes."""

    def __init__(self):
        self.regime = {}
        self.meta_filters = {}

    def set_meta_filters(self, meta_filters):
        self.meta_filters = meta_filters or {}

    def vote(self, symbol: str, direction: str, strategy: str,
             adx: float, atr_ratio: float) -> SignalVote:
        confidence = 0.5
        reasons = []

        # Regime alignment
        if adx >= 25 and atr_ratio > 1.0:
            confidence += 0.15
            reasons.append('trend_expansion')
        elif adx < 25 and atr_ratio < 0.7:
            confidence -= 0.1
            reasons.append('range_compression')

        mf = self.meta_filters.get(strategy) if isinstance(self.meta_filters, dict) else None
        if mf:
            features = {'adx': adx, 'atr_ratio': atr_ratio, 'spread': 0}
            meta_prob = mf.predict_proba(features)
            if meta_prob > 0.6:
                confidence += 0.15
                reasons.append(f'meta:{meta_prob:.2f}')
            elif meta_prob < 0.35:
                confidence -= 0.2
                reasons.append(f'meta_reject:{meta_prob:.2f}')

        return SignalVote('tech', symbol, direction,
                          min(confidence, 1.0),
                          reason=' | '.join(reasons) if reasons else 'base')


class SentimentAgent:
    """Market sentiment overlay — filters trades against sentiment."""

    def __init__(self, sentiment_filter=None):
        self.sentiment = sentiment_filter

    def vote(self, symbol: str, direction: str, timestamp) -> SignalVote:
        if self.sentiment:
            allowed = self.sentiment.should_trade(direction, timestamp, symbol)
            if not allowed:
                return SignalVote('sentiment', symbol, None, 0.1,
                                  reason='sentiment_opposed')
        return SignalVote('sentiment', symbol, direction, 0.7,
                          reason='sentiment_neutral')


class RiskAgent:
    """Final risk check — position sizing, exposure limits, correlation."""

    def __init__(self, engine=None):
        self.engine = engine
        self.max_correlation = 0.8
        self.max_net_exposure = 2.0

    def vote(self, symbol: str, direction: str, lots: float,
             open_positions: list) -> SignalVote:
        reasons = []
        confidence = 0.7

        # Net exposure check
        net = 0
        for p in open_positions:
            if p['symbol'] == symbol:
                net += p['remaining_lots'] if p['type'] == direction else -p['remaining_lots']
        if abs(net + lots) > self.max_net_exposure:
            confidence = max(0, confidence - 0.4)
            reasons.append(f'exposure:{net:.2f}')

        # Correlation check
        if self.engine and hasattr(self.engine, 'risk_manager'):
            if not self.engine.risk_manager.check_exposure(symbol, direction, open_positions):
                confidence = max(0, confidence - 0.5)
                reasons.append('correlation_block')

        return SignalVote('risk', symbol, direction,
                          min(confidence, 1.0),
                          reason=' | '.join(reasons) if reasons else 'pass')


class ExecutorAgent:
    """Final assembly — converts votes into a trade order."""

    def __init__(self, engine, kelly_agent=None, tp_sl_agent=None):
        self.engine = engine
        self.kelly = kelly_agent
        self.tp_sl_agent = tp_sl_agent

    def execute(self, votes: List[SignalVote], symbol: str, entry_price: float,
                adx: float, atr_ratio: float, strategy: str,
                risk_dist: Optional[float] = None) -> Optional[TradeOrder]:
        # Aggregate votes
        buy_votes = [v for v in votes if v.direction == 'BUY']
        sell_votes = [v for v in votes if v.direction == 'SELL']
        neutral_votes = [v for v in votes if v.direction is None]

        if not buy_votes and not sell_votes:
            return None

        # Prefer the side with more confidence
        avg_buy_conf = np.mean([v.confidence for v in buy_votes]) if buy_votes else 0
        avg_sell_conf = np.mean([v.confidence for v in sell_votes]) if sell_votes else 0

        if avg_buy_conf < 0.3 and avg_sell_conf < 0.3:
            return None

        if avg_buy_conf >= avg_sell_conf:
            direction = 'BUY'
            confidence = avg_buy_conf
        else:
            direction = 'SELL'
            confidence = avg_sell_conf

        # Position sizing via engine
        if risk_dist is None or risk_dist <= 0:
            risk_dist = entry_price * 0.002
        lots = self.engine.calculate_lot_size(symbol, 0.2, risk_dist, self.engine.equity)

        # TP/SL via RL agent if available
        tp_mult = 4.0
        sl_mult = 1.5
        if self.tp_sl_agent:
            tp_mult, sl_mult, _ = self.tp_sl_agent.select_action(adx, atr_ratio)

        if direction == 'BUY':
            sl = entry_price - risk_dist * sl_mult
            tp = entry_price + risk_dist * tp_mult
        else:
            sl = entry_price + risk_dist * sl_mult
            tp = entry_price - risk_dist * tp_mult

        return TradeOrder(
            symbol=symbol, direction=direction, lots=lots,
            entry_price=entry_price, tp=tp, sl=sl,
            strategy=strategy, confidence=confidence,
            reason=' | '.join(f'{v.agent}:{v.confidence:.2f}' for v in votes)
        )


class AgentSystem:
    """
    Orchestrates the full agent pipeline.

    Usage:
        system = AgentSystem(engine)
        system.macro.analyze(fear_greed, regime)
        order = system.process(symbol, direction, strategy, entry_price, adx, atr, timestamp)
    """

    def __init__(self, engine, meta_filters=None, sentiment_filter=None):
        self.macro = MacroAgent()
        self.tech = TechAgent()
        self.sentiment = SentimentAgent(sentiment_filter)
        self.risk = RiskAgent(engine)
        self.executor = ExecutorAgent(engine, tp_sl_agent=None)

        if meta_filters:
            self.tech.set_meta_filters(meta_filters)

    def process(self, symbol: str, direction: str, strategy: str,
                entry_price: float, adx: float, atr_ratio: float,
                timestamp, open_positions: list, lots: float = 0,
                risk_dist: Optional[float] = None) -> Optional[TradeOrder]:
        votes = [
            self.macro.vote(symbol, direction),
            self.tech.vote(symbol, direction, strategy, adx, atr_ratio),
            self.sentiment.vote(symbol, direction, timestamp),
            self.risk.vote(symbol, direction, lots, open_positions),
        ]
        return self.executor.execute(votes, symbol, entry_price,
                                     adx, atr_ratio, strategy,
                                     risk_dist=risk_dist)
