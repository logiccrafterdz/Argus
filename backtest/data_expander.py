import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import pytz
import os

SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD", "EURJPY", "GBPJPY"]
TIMEFRAMES = {"H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4}
DATE_FROM = datetime(2018, 1, 1, tzinfo=pytz.timezone("Etc/UTC"))
DATE_TO = datetime(2022, 1, 1, tzinfo=pytz.timezone("Etc/UTC"))
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def init_mt5():
    mt5_path = r"C:\Program Files\FBS MetaTrader 5\terminal64.exe"
    if not mt5.initialize(path=mt5_path):
        print(f"initialize() failed, error code = {mt5.last_error()}")
        return False
    print("MetaTrader 5 initialized.")
    return True

def expand_data(symbol, tf_name, mt5_tf):
    print(f"\nFetching {symbol} {tf_name} from 2018...")
    rates = mt5.copy_rates_range(symbol, mt5_tf, DATE_FROM, DATE_TO)
    if rates is None or len(rates) == 0:
        print(f"  No data for {symbol} {tf_name}")
        return

    new_df = pd.DataFrame(rates)
    new_df['time'] = pd.to_datetime(new_df['time'], unit='s')

    filepath = os.path.join(DATA_DIR, f"{symbol}_{tf_name}.csv")
    if os.path.exists(filepath):
        existing = pd.read_csv(filepath, parse_dates=['time'])
        before = len(existing)
        combined = pd.concat([new_df, existing], ignore_index=True)
        combined.drop_duplicates(subset='time', keep='last', inplace=True)
        combined.sort_values('time', inplace=True)
        combined.reset_index(drop=True, inplace=True)
        added = len(combined) - before
        print(f"  Existing had {before} rows, added {added} new, total {len(combined)}")
    else:
        combined = new_df
        print(f"  New file: {len(combined)} rows")
    combined.to_csv(filepath, index=False)
    print(f"  Saved {symbol}_{tf_name}.csv")

if __name__ == "__main__":
    if not init_mt5():
        exit(1)
    for symbol in SYMBOLS:
        for tf_name, mt5_tf in TIMEFRAMES.items():
            expand_data(symbol, tf_name, mt5_tf)
    mt5.shutdown()
    print("\nDone. Data expanded to 2018.")
