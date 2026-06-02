import json
import time
import threading
import logging
from typing import Optional, Callable

logger = logging.getLogger('bridge')


class BridgeServer:
    """
    ZeroMQ bridge server that receives market data from MT5,
    runs AI inference, and sends signals back.

    Protocol (JSON messages):
      -> MT5:  {"type":"tick","symbol":"EURUSD","bid":1.05,"ask":1.0501,"time":1234567890}
      <- PY:   {"type":"signal","symbol":"EURUSD","action":"BUY","lots":0.1,"tp":1.06,"sl":1.04}
      -> MT5:  {"type":"order_result","ticket":123,"symbol":"EURUSD","profit":12.5}
      <- PY:   {"type":"regime","symbol":"EURUSD","regime":"TREND","confidence":0.85}

    Architecture:
        MT5 (MQL5)  --ZeroMQ PUB-->  Python (this server)
        MT5 (MQL5)  <--ZeroMQ SUB--  Python (this server)

    Two ports:
        PULL_PORT (5559): receive data from MT5
        PUB_PORT  (5560): send signals to MT5
    """

    def __init__(self, pull_port=5559, pub_port=5560):
        self.pull_port = pull_port
        self.pub_port = pub_port
        self.running = False
        self._thread = None
        self._context = None
        self._pull_sock = None
        self._pub_sock = None
        self.on_tick: Optional[Callable] = None
        self.on_order: Optional[Callable] = None
        self._regime_cache = {}
        self._signal_cache = {}

    def start(self, on_tick=None, on_order=None):
        import zmq
        self.on_tick = on_tick
        self.on_order = on_order
        self._context = zmq.Context()
        self._pull_sock = self._context.socket(zmq.PULL)
        self._pull_sock.bind(f"tcp://*:{self.pull_port}")
        self._pub_sock = self._context.socket(zmq.PUB)
        self._pub_sock.bind(f"tcp://*:{self.pub_port}")
        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(f"Bridge server started on PULL:{self.pull_port} PUB:{self.pub_port}")

    def stop(self):
        self.running = False
        if self._pull_sock:
            self._pull_sock.close()
        if self._pub_sock:
            self._pub_sock.close()
        if self._context:
            self._context.term()

    def send_signal(self, symbol, action, lots, tp, sl, reason=""):
        msg = json.dumps({
            "type": "signal",
            "symbol": symbol,
            "action": action,
            "lots": lots,
            "tp": tp,
            "sl": sl,
            "reason": reason,
            "time": time.time()
        })
        if self._pub_sock:
            self._pub_sock.send_string(msg)

    def send_regime(self, symbol, regime, confidence):
        msg = json.dumps({
            "type": "regime",
            "symbol": symbol,
            "regime": regime,
            "confidence": confidence,
            "time": time.time()
        })
        if self._pub_sock:
            self._pub_sock.send_string(msg)

    def _run(self):
        while self.running:
            try:
                msg = self._pull_sock.recv_string(flags=zmq.NOBLOCK)
                data = json.loads(msg)
                msg_type = data.get("type")
                if msg_type == "tick" and self.on_tick:
                    self.on_tick(data)
                elif msg_type == "order_result" and self.on_order:
                    self.on_order(data)
            except zmq.Again:
                time.sleep(0.001)
            except Exception as e:
                logger.error(f"Bridge error: {e}")


class BridgeClient:
    """
    Simulated bridge client for backtesting.
    Records tick/order data during backtest for later playback
    or real-time simulation.
    """

    def __init__(self):
        self.ticks = []
        self.orders = []
        self.signals = []

    def record_tick(self, symbol, bid, ask, time_val):
        self.ticks.append({
            "type": "tick",
            "symbol": symbol,
            "bid": bid,
            "ask": ask,
            "time": time_val
        })

    def record_order(self, ticket, symbol, profit):
        self.orders.append({
            "type": "order_result",
            "ticket": ticket,
            "symbol": symbol,
            "profit": profit
        })

    def record_signal(self, symbol, action, lots, tp, sl, reason=""):
        self.signals.append({
            "type": "signal",
            "symbol": symbol,
            "action": action,
            "lots": lots,
            "tp": tp,
            "sl": sl,
            "reason": reason
        })

    def replay_ticks(self, handler):
        """Replay recorded ticks through a handler function."""
        for t in self.ticks:
            handler(t)

    def to_dict(self):
        return {
            "ticks": self.ticks,
            "orders": self.orders,
            "signals": self.signals
        }
