"""
Composite scoring engine for Argus backtest evaluation.
Maps strategy/portfolio raw metrics to a 0-100 score.

Sub-scores (weighted):
  profitability (30%) — PF, expectancy, net profit
  risk (25%) — max DD, DD duration, recovery factor
  consistency (20%) — monthly return stability, win rate volatility
  robustness (15%) — trade count sufficiency, regime adaptability
  OOS stability (10%) — PF train/test gap, DD train/test gap
"""
import json, os, sys, math
from collections import OrderedDict

RESULTS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "docs", "data", "results.json"
)
EVIDENCE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "references", "evidence_memory.json"
)

def sigmoid(x, midpoint=1.0, steepness=4.0):
    return 100 / (1 + math.exp(-steepness * (x - midpoint)))

def cap_score(v, lo=0, hi=100):
    return max(lo, min(hi, v))


class StrategyScorer:
    WEIGHTS = {
        "profitability": 0.30,
        "risk": 0.25,
        "consistency": 0.20,
        "robustness": 0.15,
        "oos_stability": 0.10,
    }

    @staticmethod
    def profitability_score(s: dict) -> float:
        pf = s.get("profit_factor", 0) or 0
        np_val = s.get("net_profit", 0) or 0
        trades = s.get("total_trades", 0) or 1
        expectancy = np_val / trades
        pf_score = cap_score(sigmoid(pf, midpoint=1.2, steepness=3.0))
        exp_score = cap_score(sigmoid(expectancy / 50, midpoint=0.5, steepness=2.0))
        np_score = cap_score(sigmoid(np_val / 5000, midpoint=1.0, steepness=2.0))
        return 0.4 * pf_score + 0.35 * exp_score + 0.25 * np_score

    @staticmethod
    def risk_score(s: dict, port: dict = None) -> float:
        dd = abs(s.get("max_drawdown", port.get("max_drawdown", 10) if port else 10))
        dd_dur = s.get("max_dd_duration", port.get("max_dd_duration", 100) if port else 100)
        recv = s.get("recovery_factor", port.get("recovery_factor", 1) if port else 1)
        dd_score = cap_score(sigmoid(20 - dd, midpoint=10, steepness=0.3))
        dur_score = cap_score(sigmoid(200 - dd_dur, midpoint=100, steepness=0.02))
        recv_score = cap_score(sigmoid(recv, midpoint=2.0, steepness=1.5))
        return 0.4 * dd_score + 0.3 * dur_score + 0.3 * recv_score

    @staticmethod
    def consistency_score(s: dict, monthly_returns: dict = None) -> float:
        wr = s.get("win_rate", 0) or 0
        wr_score = cap_score(sigmoid(wr, midpoint=35, steepness=0.08))
        if monthly_returns:
            vals = list(monthly_returns.values())
            if len(vals) > 1:
                mean_m = sum(vals) / len(vals)
                var_m = sum((v - mean_m) ** 2 for v in vals) / len(vals)
                std_m = math.sqrt(var_m)
                stability_score = cap_score(sigmoid(5 - std_m, midpoint=2, steepness=1.0))
            else:
                stability_score = 50
        else:
            stability_score = 50
        return 0.5 * wr_score + 0.5 * stability_score

    @staticmethod
    def robustness_score(s: dict) -> float:
        trades = s.get("total_trades", 0) or 0
        cat = s.get("category", "Unknown")
        min_trades = {"Divergence": 20, "Institutional": 30, "Breakout": 30, "Mean Reversion": 40}.get(cat, 20)
        trade_score = cap_score(100 * (1 - math.exp(-trades / min_trades)))
        return trade_score

    @staticmethod
    def oos_stability_score(train_metrics: dict = None, test_metrics: dict = None) -> float:
        if not train_metrics or not test_metrics:
            return 50
        pf_train = train_metrics.get("profit_factor", 1) or 1
        pf_test = test_metrics.get("profit_factor", 1) or 1
        dd_train = abs(train_metrics.get("max_drawdown", 5) or 5)
        dd_test = abs(test_metrics.get("max_drawdown", 5) or 5)
        pf_gap = abs(pf_train - pf_test)
        pf_stability = cap_score(sigmoid(1 - pf_gap, midpoint=0.5, steepness=4.0))
        dd_increase = max(0, dd_test - dd_train)
        dd_stability = cap_score(sigmoid(10 - dd_increase, midpoint=3, steepness=0.5))
        return 0.5 * pf_stability + 0.5 * dd_stability

    @classmethod
    def score(cls, s: dict, port: dict = None, monthly: dict = None,
              train: dict = None, test: dict = None) -> dict:
        scores = {
            "profitability": cls.profitability_score(s),
            "risk": cls.risk_score(s, port),
            "consistency": cls.consistency_score(s, monthly),
            "robustness": cls.robustness_score(s),
            "oos_stability": cls.oos_stability_score(train, test),
        }
        composite = sum(scores[k] * cls.WEIGHTS[k] for k in scores)
        return {
            "composite": round(composite, 1),
            "sub_scores": {k: round(v, 1) for k, v in scores.items()},
            "weights": cls.WEIGHTS,
            "grade": "A" if composite >= 80 else "B" if composite >= 60 else "C" if composite >= 40 else "D" if composite >= 20 else "F",
        }


class PortfolioScorer:
    WEIGHTS = {
        "profitability": 0.35,
        "risk": 0.30,
        "consistency": 0.25,
        "robustness": 0.10,
    }

    @classmethod
    def score(cls, p: dict) -> dict:
        s = StrategyScorer()
        scores = {
            "profitability": s.profitability_score(p),
            "risk": s.risk_score(p, p),
            "consistency": s.consistency_score(p, p.get("monthly_returns")),
            "robustness": s.robustness_score(p),
        }
        composite = sum(scores[k] * cls.WEIGHTS[k] for k in scores)
        return {
            "composite": round(composite, 1),
            "sub_scores": {k: round(v, 1) for k, v in scores.items()},
            "weights": cls.WEIGHTS,
            "grade": "A" if composite >= 80 else "B" if composite >= 60 else "C" if composite >= 40 else "D" if composite >= 20 else "F",
        }


def load_results(path=None):
    path = path or RESULTS_PATH
    if not os.path.exists(path):
        print(f"Results not found: {path}")
        return None
    with open(path) as f:
        return json.load(f)


def load_evidence():
    if not os.path.exists(EVIDENCE_PATH):
        return {"runs": [], "observations": [], "experiments": []}
    with open(EVIDENCE_PATH) as f:
        return json.load(f)


def score_all_strategies(data, train=None, test=None):
    port = data.get("portfolio", {})
    monthly = port.get("monthly_returns", {})
    results = []
    for s in data.get("strategies", []):
        tr = train.get(s["name"]) if train else None
        te = test.get(s["name"]) if test else None
        sc = StrategyScorer.score(s, port, monthly, tr, te)
        results.append({**s, "score": sc})
    results.sort(key=lambda x: x["score"]["composite"], reverse=True)
    return results


def main():
    data = load_results()
    if not data:
        return 1

    print("=" * 55)
    print("  ARGUS COMPOSITE SCORING ENGINE")
    print("=" * 55)

    port = data["portfolio"]
    ps = PortfolioScorer.score(port)
    print(f"\nPORTFOLIO SCORE: {ps['composite']:.1f}/100  Grade: {ps['grade']}")
    print(f"  PF={port.get('profit_factor',0):.2f}  Return={port.get('total_return',0):.1f}%  DD={port.get('max_drawdown',0):.1f}%  Trades={port.get('total_trades',0)}")
    for k, v in ps["sub_scores"].items():
        print(f"  {k}: {v:.1f}")

    print(f"\n{'STRATEGY':<30} {'SCORE':>6} {'GRADE':>6} {'PF':>7} {'PnL':>10} {'Trades':>7}")
    print("-" * 70)
    scored = score_all_strategies(data)
    for s in scored:
        sc = s["score"]
        print(f"{s['name']:<30} {sc['composite']:>6.1f} {sc['grade']:>6} {s['profit_factor']:>7.2f} ${s['net_profit']:>+8,.0f} {s['total_trades']:>7}")

    print()
    best = scored[0]
    worst = scored[-1]
    print(f"Best strategy: {best['name']} (Score: {best['score']['composite']:.1f}, PF: {best['profit_factor']:.2f})")
    print(f"Worst strategy: {worst['name']} (Score: {worst['score']['composite']:.1f}, PF: {worst['profit_factor']:.2f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
