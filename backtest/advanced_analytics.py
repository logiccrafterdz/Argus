import pandas as pd
import numpy as np
from log_setup import get_logger

def monte_carlo_shuffle(trades, n_simulations=1000, confidence=95):
    """
    Monte Carlo simulation by shuffling trade order.
    Tests if strategy performance is robust or luck-dependent.
    
    Returns: dict with percentiles of equity curves
    """
    logger = get_logger('analytics')
    if not trades:
        return {}
    
    df = pd.DataFrame(trades)
    profits = df['profit'].values
    
    if len(profits) < 10:
        return {'error': 'Not enough trades for Monte Carlo'}
    
    # Pre-compute cumulative sums of shuffled trades
    np.random.seed(42)
    final_equities = []
    
    for sim in range(n_simulations):
        shuffled = np.random.permutation(profits)
        final_equity = np.sum(shuffled)
        final_equities.append(final_equity)
    
    final_equities = np.array(final_equities)
    
    pct_lower = (100 - confidence) / 2
    pct_upper = 100 - pct_lower
    
    result = {
        'n_simulations': n_simulations,
        'confidence_level': confidence,
        'mean_final_pnl': round(float(np.mean(final_equities)), 2),
        'median_final_pnl': round(float(np.median(final_equities)), 2),
        'std_final_pnl': round(float(np.std(final_equities)), 2),
        'percentile_5': round(float(np.percentile(final_equities, 5)), 2),
        'percentile_25': round(float(np.percentile(final_equities, 25)), 2),
        'percentile_50': round(float(np.percentile(final_equities, 50)), 2),
        'percentile_75': round(float(np.percentile(final_equities, 75)), 2),
        'percentile_95': round(float(np.percentile(final_equities, 95)), 2),
        'pct_positive': round(float(np.mean(final_equities > 0) * 100), 1),
        'pct_negative': round(float(np.mean(final_equities < 0) * 100), 1),
    }
    
    logger.info(f"Monte Carlo ({n_simulations} sims, {confidence}% conf): "
                f"median={result['median_final_pnl']:.2f}, "
                f"pct_positive={result['pct_positive']:.1f}%")
    return result


def walk_forward_analysis(df_trades, n_folds=4, train_pct=0.6):
    """
    Walk-Forward Analysis: split data into folds, train on first part, test on second.
    Measures strategy robustness across different market regimes.
    
    Returns: dict with fold-by-fold and aggregate results
    """
    logger = get_logger('analytics')
    if df_trades.empty or len(df_trades) < 100:
        return {'error': 'Not enough trades for walk-forward analysis'}
    
    df = df_trades.copy()
    df = df.sort_values('close_time').reset_index(drop=True)
    n = len(df)
    
    fold_size = n // n_folds
    results = []
    
    for fold in range(n_folds - 1):
        train_end = int((fold + 1) * fold_size * (train_pct / (1 - train_pct))) + fold * (fold_size - int(fold_size * (train_pct / (1 - train_pct))))
        # Simpler approach: train = first train_pct, test = next portion
        actual_train_end = int((fold + 1) * fold_size * train_pct)
        test_start = int((fold + 1) * fold_size * train_pct)
        test_end = (fold + 1) * fold_size + fold_size // 2
        
        if test_end > n:
            test_end = n
        if test_start >= n or test_start >= test_end:
            continue
        
        train_df = df.iloc[actual_train_end - fold_size:actual_train_end] if fold > 0 else df.iloc[:actual_train_end]
        test_df = df.iloc[test_start:test_end]
        
        if len(train_df) < 10 or len(test_df) < 5:
            continue
        
        train_profit = train_df['profit'].sum()
        test_profit = test_df['profit'].sum()
        train_win = len(train_df[train_df['profit'] > 0]) / len(train_df) * 100 if len(train_df) > 0 else 0
        test_win = len(test_df[test_df['profit'] > 0]) / len(test_df) * 100 if len(test_df) > 0 else 0
        
        results.append({
            'fold': fold + 1,
            'train_trades': len(train_df),
            'test_trades': len(test_df),
            'train_profit': round(train_profit, 2),
            'test_profit': round(test_profit, 2),
            'train_win_rate': round(train_win, 2),
            'test_win_rate': round(test_win, 2),
            'train_profit_per_trade': round(train_profit / len(train_df), 2) if len(train_df) > 0 else 0,
            'test_profit_per_trade': round(test_profit / len(test_df), 2) if len(test_df) > 0 else 0,
        })
    
    if not results:
        return {'error': 'Could not create valid folds'}
    
    agg = {
        'n_folds': len(results),
        'avg_train_profit': round(np.mean([r['train_profit'] for r in results]), 2),
        'avg_test_profit': round(np.mean([r['test_profit'] for r in results]), 2),
        'avg_train_win_rate': round(np.mean([r['train_win_rate'] for r in results]), 2),
        'avg_test_win_rate': round(np.mean([r['test_win_rate'] for r in results]), 2),
        'profit_persistence': round(np.mean([1 for r in results if (r['train_profit'] > 0) == (r['test_profit'] > 0)]) * 100, 1),
        'sharpe_ratio_train': round(np.mean([r['train_profit_per_trade'] for r in results]) / max(np.std([r['train_profit_per_trade'] for r in results]), 0.01), 2),
    }
    
    logger.info(f"Walk-Forward ({n_folds} folds): "
                f"avg_train={agg['avg_train_profit']:.2f}, "
                f"avg_test={agg['avg_test_profit']:.2f}, "
                f"persistence={agg['profit_persistence']:.1f}%")
    
    return {'folds': results, 'aggregate': agg}
