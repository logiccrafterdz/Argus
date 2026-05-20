import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import pytz
import os

# --- Configuration ---
SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]
TIMEFRAMES = {
    "M15": mt5.TIMEFRAME_M15,
    "H1":  mt5.TIMEFRAME_H1,
    "H4":  mt5.TIMEFRAME_H4
}
# Timezone setup - MT5 uses UTC/broker time. We will use UTC to standardise.
timezone = pytz.timezone("Etc/UTC")
DATE_FROM = datetime(2022, 1, 1, tzinfo=timezone)
DATE_TO = datetime(2025, 5, 1, tzinfo=timezone) # Or datetime.now() if before May 2025
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def init_mt5():
    if not mt5.initialize():
        print(f"initialize() failed, error code = {mt5.last_error()}")
        return False
    print("MetaTrader 5 initialized successfully.")
    return True

def fetch_data(symbol, timeframe_name, timeframe_code):
    print(f"Fetching {symbol} - {timeframe_name}...")
    
    # Check if symbol exists
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"Symbol {symbol} not found.")
        return False
    
    if not symbol_info.visible:
        print(f"Symbol {symbol} is not visible, trying to switch on")
        if not mt5.symbol_select(symbol, True):
            print(f"symbol_select({symbol}) failed")
            return False

    # Request historical data
    rates = mt5.copy_rates_range(symbol, timeframe_code, DATE_FROM, DATE_TO)
    
    if rates is None or len(rates) == 0:
        print(f"No data retrieved for {symbol} - {timeframe_name}. Error: {mt5.last_error()}")
        return False

    # Convert to DataFrame
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # Save to CSV
    filename = os.path.join(DATA_DIR, f"{symbol}_{timeframe_name}.csv")
    df.to_csv(filename, index=False)
    print(f"Saved {len(df)} records to {filename}")
    return True

if __name__ == "__main__":
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    if init_mt5():
        for symbol in SYMBOLS:
            for tf_name, tf_code in TIMEFRAMES.items():
                fetch_data(symbol, tf_name, tf_code)
        
        mt5.shutdown()
        print("Data fetching complete.")
    else:
        print("Failed to start data fetcher.")
