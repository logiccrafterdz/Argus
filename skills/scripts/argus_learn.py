"""
Argus Learning Loop Orchestrator.
Usage:
    python skills/scripts/argus_learn.py              # analyze + score + suggest
    python skills/scripts/argus_learn.py --run         # register current results as new run
    python skills/scripts/argus_learn.py --hypothesis  # generate hypotheses for worst strategies
"""
import json, os, sys, math, subprocess
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from scoring import StrategyScorer, PortfolioScorer, load_results, load_evidence, score_all_strategies

RESULTS_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "data", "results.json")
EVIDENCE_PATH = os.path.join(os.path.dirname(__file__), "..", "references", "evidence_memory.json")
MANIFEST_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "data", "run_manifest.json")


def get_git_commit():
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=os.path.join(os.path.dirname(__file__), "..", ".."))
        return r.stdout.strip() if r.returncode == 0 else "unknown"
    except:
        return "unknown"


def get_git_diff():
    try:
        r = subprocess.run(["git", "diff", "--stat"], capture_output=True, text=True, cwd=os.path.join(os.path.dirname(__file__), "..", ".."))
        return r.stdout.strip()[:500] if r.returncode == 0 else ""
    except:
        return ""


def register_run():
    data = load_results()
    if not data:
        print("No results to register. Run backtest first.")
        return

    evidence = load_evidence()
    commit = get_git_commit()
    diff = get_git_diff()

    run_entry = {
        "run_id": len(evidence.get("runs", [])) + 1,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "commit": commit,
        "config_hash": "auto",
        "changes": diff[:300],
        "n_strategies": len(data.get("strategies", [])),
        "portfolio": data.get("portfolio", {}),
        "strategies": data.get("strategies", []),
    }

    evidence.setdefault("runs", []).append(run_entry)

    os.makedirs(os.path.dirname(EVIDENCE_PATH), exist_ok=True)
    with open(EVIDENCE_PATH, "w") as f:
        json.dump(evidence, f, indent=2)
    print(f"Run {run_entry['run_id']} registered: {run_entry['date']} @ {commit}")
    return run_entry


def detect_regressions(current, previous):
    if not previous:
        return []
    regressions = []
    prev_strats = {s["name"]: s for s in previous.get("strategies", [])}
    for s in current.get("strategies", []):
        ps = prev_strats.get(s["name"])
        if ps and ps.get("net_profit", 0) > 0 and s.get("net_profit", 0) < 0:
            regressions.append({
                "strategy": s["name"],
                "was": ps["net_profit"],
                "now": s["net_profit"],
                "delta": s["net_profit"] - ps["net_profit"]
            })
    return regressions


def generate_hypotheses(strategies):
    hypotheses = []
    for s in strategies:
        if s.get("profit_factor", 1) >= 1.0:
            continue
        name = s["name"]
        pf = s.get("profit_factor", 0)
        trades = s.get("total_trades", 0)
        net = s.get("net_profit", 0)

        if pf < 0.8 and trades >= 30:
            h = {"strategy": name, "issue": "low_profit_factor", "hypothesis": "", "experiment": ""}
            if "Donchian" in name:
                h["hypothesis"] = "Donchian_Breakout suffers from trend-fading in ranging markets. EMA filter may be too slow."
                h["experiment"] = "python backtest/optimize.py DonchianBreakout --params period=10 ema_period=20"
            elif "ADX" in name:
                h["hypothesis"] = "ADX_TrendStrength has too few trades (27). ADX threshold may be too high for H4 data."
                h["experiment"] = "python backtest/optimize.py ADXTrendStrength --params adx_threshold=18 min_slope=2"
            else:
                h["hypothesis"] = f"{name} underperforms with PF {pf}. Needs parameter sweep."
                h["experiment"] = f"python backtest/optimize.py {name.replace('_', '')} --params sl_atr=1.0 tp_atr=2.0"
            hypotheses.append(h)

        if trades < 20 and net <= 0:
            h = {"strategy": name, "issue": "too_few_trades", "hypothesis": "", "experiment": ""}
            if "ADX" in name:
                h["hypothesis"] = "ADX_TrendStrength generates too few signals. Lower ADX threshold or use lower timeframe."
                h["experiment"] = "python backtest/optimize.py ADXTrendStrength --params adx_threshold=15 adx_period=10"
            else:
                h["hypothesis"] = f"{name} has only {trades} trades. Relax entry conditions."
                h["experiment"] = f"python backtest/optimize.py {name.replace('_', '')} --params lookback=10 buffer=0.3"
            hypotheses.append(h)

    return hypotheses


def show_summary(data):
    port = data.get("portfolio", {})
    print(f"Portfolio: PF {port.get('profit_factor',0):.2f} | Return {port.get('total_return',0):+.1f}% | DD {port.get('max_drawdown',0):.1f}% | {port.get('total_trades',0)} trades")
    scored = score_all_strategies(data)
    print(f"{'Strategy':<28} {'Score':>6} {'Grade':>6} {'PF':>6} {'Net PnL':>10}")
    print("-" * 58)
    for s in scored:
        sc = s["score"]
        pnl = s.get("net_profit", 0)
        print(f"{s['name']:<28} {sc['composite']:>6.1f} {sc['grade']:>6} {s['profit_factor']:>6.2f} ${pnl:>+8,.0f}")


def main():
    data = load_results()
    if not data:
        return 1

    if len(sys.argv) > 1 and sys.argv[1] == "--run":
        register_run()
        return 0

    evidence = load_evidence()
    prev_run = evidence.get("runs", [])[-1] if evidence.get("runs") else {}

    show_summary(data)
    print()

    port = data.get("portfolio", {})
    pscore = PortfolioScorer.score(port)
    print(f"Portfolio Score: {pscore['composite']:.1f}/100 ({pscore['grade']})")

    regressions = detect_regressions(data, prev_run)
    if regressions:
        print(f"\n[!] {len(regressions)} regression(s) detected:")
        for r in regressions:
            print(f"   {r['strategy']}: ${r['was']:+,.0f} -> ${r['now']:+,.0f} (delta ${r['delta']:+,.0f})")
    else:
        print("\n[OK] No regressions detected")

    if len(sys.argv) > 1 and sys.argv[1] == "--hypothesis":
        print(f"\n{'='*50}\n  HYPOTHESES\n{'='*50}")
        hyps = generate_hypotheses(data.get("strategies", []))
        for h in hyps:
            print(f"\n[{h['strategy']}] {h['issue']}")
            print(f"  Hypothesis: {h['hypothesis']}")
            print(f"  Experiment: {h['experiment']}")

    return 0


if __name__ == "__main__":
    main()
