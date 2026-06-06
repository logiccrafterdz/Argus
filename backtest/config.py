import yaml
import os

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.yaml')

DEFAULT_CONFIG = {
    'backtest': {
        'initial_balance': 100000.0,
        'start_date': None,
        'end_date': None,
    },
    'risk': {
        'risk_percent_per_trade': 1.0,
        'max_daily_dd': 3.0,
        'max_weekly_dd': 8.0,
        'max_monthly_dd': 15.0,
        'max_exposure_per_symbol': 2,
        'correlation_threshold': 0.8,
        'correlation_enabled': True,
        'prop_firm_mode': False,
        'news_filter_enabled': False,
    },
    'execution': {
        'slippage_min': 0.0,
        'slippage_max': 0.3,
        'commission_map': {
            'XAUUSD': 3.50,
            'US30': 0.0,
            'NAS100': 0.0,
        },
        'default_commission': 7.0,
    },
    'spread': {
        'EURUSD': 0.00012,
        'GBPUSD': 0.00014,
        'USDJPY': 0.013,
        'USDCHF': 0.00014,
        'AUDUSD': 0.00013,
        'USDCAD': 0.00016,
        'NZDUSD': 0.00018,
        'XAUUSD': 0.35,
        'US30': 3.0,
        'NAS100': 2.5,
    },
    'contract_size': {
        'XAUUSD': 100,
        'US30': 1.0,
        'NAS100': 1.0,
    },
    'default_contract_size': 100000.0,
    'regime': {
        'method': 'adx',  # 'adx' | 'hmm'
    },
    'sentiment': {
        'enabled': True,
    },
    'meta_labeling': {
        'enabled': True,
    },
    'rl_agent': {
        'enabled': False,
    },
    'kelly': {
        'enabled': True,
    },
    'agent_system': {
        'enabled': False,
    },
    'strategies': {
        'TrendPullback': {
            'fast_ema_period': 50,
            'slow_ema_period': 200,
            'market_structure_period': 30,
            'tp_multiplier': 2.0,
        },
        'Smart_Swing_Bias': {
            'lookback': 40,
        },
        'Liquidity_Sweep_Breakout': {
            'lookback': 50,
        },
        'Liquidity Sweep FVG': {
            'lookback': 50,
            'threshold': 0.00050,
        },
    },
}

def load_config(path=None):
    if path is None:
        path = DEFAULT_CONFIG_PATH
    if os.path.exists(path):
        with open(path, 'r') as f:
            return yaml.safe_load(f)
    return dict(DEFAULT_CONFIG)

def save_config(config, path=None):
    if path is None:
        path = DEFAULT_CONFIG_PATH
    with open(path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

def create_default_config(path=None):
    if path is None:
        path = DEFAULT_CONFIG_PATH
    save_config(DEFAULT_CONFIG, path)
    return DEFAULT_CONFIG
