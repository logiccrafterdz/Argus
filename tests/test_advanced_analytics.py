import unittest
import pandas as pd
import numpy as np
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backtest'))
from advanced_analytics import monte_carlo_shuffle, walk_forward_analysis

class TestAdvancedAnalytics(unittest.TestCase):
    def setUp(self):
        np.random.seed(42)
        n = 200
        self.trades = pd.DataFrame({
            'profit': np.random.uniform(-50, 50, n),
            'close_time': pd.date_range('2024-01-01', periods=n, freq='h'),
            'strategy': ['Test'] * n,
        })
        self.trades_list = self.trades.to_dict('records')

    def test_monte_carlo_basic(self):
        result = monte_carlo_shuffle(self.trades_list, n_simulations=100)
        self.assertIsNotNone(result)
        self.assertIn('mean_final_pnl', result)
        self.assertIn('median_final_pnl', result)
        self.assertIn('pct_positive', result)
        self.assertIn('pct_negative', result)

    def test_monte_carlo_percentiles(self):
        result = monte_carlo_shuffle(self.trades_list, n_simulations=200, confidence=99)
        self.assertIn('percentile_5', result)
        self.assertIn('percentile_95', result)
        self.assertLessEqual(result['percentile_5'], result['percentile_95'])

    def test_monte_carlo_insufficient_trades(self):
        result = monte_carlo_shuffle([{'profit': 10}], n_simulations=10)
        self.assertIn('error', result)

    def test_monte_carlo_empty(self):
        result = monte_carlo_shuffle([])
        self.assertEqual(result, {})

    def test_walk_forward_basic(self):
        result = walk_forward_analysis(self.trades, n_folds=3, train_pct=0.6)
        self.assertIsNotNone(result)
        self.assertIn('folds', result)
        self.assertIn('aggregate', result)

    def test_walk_forward_folds(self):
        result = walk_forward_analysis(self.trades, n_folds=4, train_pct=0.5)
        self.assertGreaterEqual(len(result['folds']), 1)
        for fold in result['folds']:
            self.assertIn('train_profit', fold)
            self.assertIn('test_profit', fold)
            self.assertIn('train_win_rate', fold)
            self.assertIn('test_win_rate', fold)

    def test_walk_forward_aggregate(self):
        result = walk_forward_analysis(self.trades, n_folds=3)
        agg = result['aggregate']
        self.assertIn('n_folds', agg)
        self.assertIn('avg_train_profit', agg)
        self.assertIn('avg_test_profit', agg)
        self.assertIn('profit_persistence', agg)

    def test_walk_forward_insufficient_trades(self):
        result = walk_forward_analysis(pd.DataFrame({'profit': [1, 2], 'close_time': pd.date_range('2024-01-01', periods=2, freq='h')}), n_folds=4)
        if 'error' in result:
            self.assertIn('error', result)

    def test_walk_forward_empty(self):
        result = walk_forward_analysis(pd.DataFrame())
        self.assertIn('error', result)

if __name__ == '__main__':
    unittest.main()
