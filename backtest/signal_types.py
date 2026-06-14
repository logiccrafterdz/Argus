from enum import Enum
from dataclasses import dataclass

class StrategyType(Enum):
    TREND_MOMENTUM = "trend_momentum"
    MEAN_REVERSION = "mean_reversion"
    STOP_HUNT = "stop_hunt"

STRATEGY_TYPE_PARAMS = {
    StrategyType.TREND_MOMENTUM: {
        'sl_atr': 2.0,
    },
    StrategyType.MEAN_REVERSION: {
        'sl_atr': 1.0,
        'tp_atr': 2.0,
    },
    StrategyType.STOP_HUNT: {
        'sl_atr': 0.5,
        'tp_atr': 2.0,
    },
}


@dataclass
class Signal:
    direction: int
    conviction: float
