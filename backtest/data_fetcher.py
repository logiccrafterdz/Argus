import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import pytz
import os

SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD", "EURJPY", "GBPJPY"]
TIMEFRAMES = {
    "M15": mt5.TIMEFRAME_M15,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4
}
DATE_FROM = datetime(2022, 1, 1, tzinfo=pytz.timezone("Etc/UTC"))
DATE_TO = datetime(2025, 5, 1, tzinfo=pytz.timezone("Etc/UTC"))
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def init_mt5():
    mt5_path = r"C:\Program Files\FBS MetaTrader 5\terminal64.exe"
    if not mt5.initialize(path=mt5_path):
        print(f"initialize() failed, error code = {mt5.last_error()}")
        return False
    print("MetaTrader 5 initialized successfully.")
    return True

def fetch_data(symbol, timeframe_name, mt5_timeframe):
    print(f"Fetching {symbol} - {timeframe_name}...")
    rates = mt5.copy_rates_range(symbol, mt5_timeframe, DATE_FROM, DATE_TO)
    if rates is None:
        print(f"Failed to fetch {symbol} - {timeframe_name}, error: {mt5.last_error()}")
        return
        
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    filename = os.path.join(DATA_DIR, f"{symbol}_{timeframe_name}.csv")
    df.to_csv(filename, index=False)
    print(f"Saved {len(df)} records to {filename}")

if __name__ == "__main__":
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    if not init_mt5():
        print("Failed to start data fetcher.")
        exit(1)
        
    for symbol in SYMBOLS:
        for tf_name, mt5_tf in TIMEFRAMES.items():
            fetch_data(symbol, tf_name, mt5_tf)
            
    mt5.shutdown()
    print("Data fetching complete.")
