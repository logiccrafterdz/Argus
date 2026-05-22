import unittest
import pandas as pd
import numpy as np
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backtest'))
from engine import BacktestEngine

class TestBacktestEngine(unittest.TestCase):
    def setUp(self):
        self.engine = BacktestEngine(initial_balance=100000.0)

    def test_initial_state(self):
        self.assertEqual(self.engine.balance, 100000.0)
        self.assertEqual(self.engine.equity, 100000.0)
        self.assertEqual(len(self.engine.open_positions), 0)
        self.assertEqual(len(self.engine.closed_trades), 0)
        self.assertEqual(len(self.engine.equity_curve), 0)

    def test_contract_size_forex(self):
        self.assertEqual(self.engine.contract_size('EURUSD'), 100000.0)
        self.assertEqual(self.engine.contract_size('GBPUSD'), 100000.0)
        self.assertEqual(self.engine.contract_size('USDJPY'), 100000.0)

    def test_contract_size_gold(self):
        self.assertEqual(self.engine.contract_size('XAUUSD'), 100)

    def test_contract_size_indices(self):
        self.assertEqual(self.engine.contract_size('US30'), 1.0)
        self.assertEqual(self.engine.contract_size('NAS100'), 1.0)

    def test_position_value(self):
        self.assertEqual(self.engine.position_value('EURUSD', 1.0), 100000.0)
        self.assertEqual(self.engine.position_value('XAUUSD', 1.0), 100)
        self.assertEqual(self.engine.position_value('US30', 1.0), 1.0)

    def test_execute_trade_buy(self):
        result = self.engine.execute_trade(
            symbol='EURUSD',
            strategy_name='TestStrat',
            order_type='BUY',
            lot_size=0.1,
            entry_price=1.10000,
            sl=1.09800,
            tp=1.10400,
            comment='Test Buy'
        )
        self.assertTrue(result)
        self.assertEqual(len(self.engine.open_positions), 1)
        pos = self.engine.open_positions[0]
        self.assertEqual(pos['symbol'], 'EURUSD')
        self.assertEqual(pos['strategy'], 'TestStrat')
        self.assertEqual(pos['type'], 'BUY')
        self.assertEqual(pos['lot_size'], 0.1)
        self.assertEqual(pos['remaining_lots'], 0.1)

    def test_execute_trade_sell(self):
        result = self.engine.execute_trade(
            symbol='EURUSD',
            strategy_name='TestStrat',
            order_type='SELL',
            lot_size=0.1,
            entry_price=1.10000,
            sl=1.10200,
            tp=1.09600,
            comment='Test Sell'
        )
        self.assertTrue(result)

    def test_close_position_buy_profit(self):
        self.engine.execute_trade('EURUSD', 'Test', 'BUY', 0.1, 1.10000, 1.09800, 1.10400, '')
        pos = self.engine.open_positions[0]
        self.engine.close_position(pos, 1.10400, pd.Timestamp('2024-01-01'), 'TP')
        self.assertEqual(len(self.engine.open_positions), 0)
        self.assertEqual(len(self.engine.closed_trades), 1)
        trade = self.engine.closed_trades[0]
        # Profit uses actual entry_price (adjusted by spread) not the raw input
        actual_entry = pos['entry_price']
        expected_profit = (1.10400 - actual_entry) * 0.1 * 100000 - 0.70
        self.assertAlmostEqual(trade['profit'], expected_profit, places=1)

    def test_close_position_buy_loss(self):
        self.engine.execute_trade('EURUSD', 'Test', 'BUY', 0.1, 1.10000, 1.09800, 1.10400, '')
        pos = self.engine.open_positions[0]
        self.engine.close_position(pos, 1.09800, pd.Timestamp('2024-01-01'), 'SL')
        trade = self.engine.closed_trades[0]
        actual_entry = pos['entry_price']
        expected_profit = (1.09800 - actual_entry) * 0.1 * 100000 - 0.70
        self.assertAlmostEqual(trade['profit'], expected_profit, places=1)

    def test_close_position_gold(self):
        self.engine.execute_trade('XAUUSD', 'Test', 'BUY', 0.1, 1900.00, 1898.00, 1904.00, '')
        pos = self.engine.open_positions[0]
        self.engine.close_position(pos, 1904.00, pd.Timestamp('2024-01-01'), 'TP')
        trade = self.engine.closed_trades[0]
        actual_entry = pos['entry_price']
        expected_profit = (1904.00 - actual_entry) * 0.1 * 100 - 0.35
        self.assertAlmostEqual(trade['profit'], expected_profit, places=1)

    def test_emergency_close_all(self):
        self.engine.execute_trade('EURUSD', 'Test', 'BUY', 0.1, 1.10000, 1.09800, 1.10400, '')
        self.engine.execute_trade('GBPUSD', 'Test', 'SELL', 0.1, 1.25000, 1.25200, 1.24600, '')
        self.engine.emergency_close_all({'EURUSD': 1.10100, 'GBPUSD': 1.25100})
        self.assertEqual(len(self.engine.open_positions), 0)
        self.assertEqual(len(self.engine.closed_trades), 2)

    def test_calculate_equity(self):
        self.engine.execute_trade('EURUSD', 'Test', 'BUY', 0.1, 1.10000, 1.09800, 1.10400, '')
        pos = self.engine.open_positions[0]
        equity = self.engine.calculate_equity({'EURUSD': 1.10200})
        actual_entry = pos['entry_price']
        expected_unrealized = (1.10200 - actual_entry) * 0.1 * 100000
        self.assertAlmostEqual(equity, 100000.0 + expected_unrealized, delta=1)

    def test_update_equity_curve(self):
        self.engine.current_time = pd.Timestamp('2024-01-01')
        self.engine.update(pd.Timestamp('2024-01-01'), {'EURUSD': 1.10000}, {'EURUSD': 1.10100}, {'EURUSD': 1.09900})
        self.assertEqual(len(self.engine.equity_curve), 1)
        self.assertEqual(self.engine.equity_curve[0]['balance'], 100000.0)
        self.assertEqual(self.engine.equity_curve[0]['equity'], 100000.0)

if __name__ == '__main__':
    unittest.main()
