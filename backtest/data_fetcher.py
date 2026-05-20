import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

# --- Configuration ---
SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD"]
TIMEFRAMES = ["M15", "H1", "H4"]
DATE_FROM = datetime(2022, 1, 1)
DATE_TO = datetime(2025, 5, 1)
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def generate_simulated_data(symbol, timeframe):
    print(f"Generating simulated data for {symbol} - {timeframe}...")
    
    # Calculate number of periods
    if timeframe == "M15":
        freq = "15min"
        minutes = 15
    elif timeframe == "H1":
        freq = "1h"
        minutes = 60
    else:
        freq = "4h"
        minutes = 240
        
    dates = pd.date_range(start=DATE_FROM, end=DATE_TO, freq=freq)
    
    # Filter weekends
    dates = dates[dates.dayofweek < 5]
    n = len(dates)
    
    # Generate random walk
    if "JPY" in symbol:
        start_price = 130.0
        volatility = 0.05
    elif "XAU" in symbol:
        start_price = 1900.0
        volatility = 1.5
    else:
        start_price = 1.1000
        volatility = 0.0005
        
    np.random.seed(hash(symbol + timeframe) % 2**32)
    returns = np.random.normal(0, volatility, n)
    closes = start_price + np.cumsum(returns)
    
    # Generate OHLC
    highs = closes + np.abs(np.random.normal(0, volatility/2, n))
    lows = closes - np.abs(np.random.normal(0, volatility/2, n))
    opens = closes - np.random.normal(0, volatility/2, n)
    
    # Fix open/close boundaries relative to high/low
    highs = np.maximum(np.maximum(opens, closes), highs)
    lows = np.minimum(np.minimum(opens, closes), lows)
    
    df = pd.DataFrame({
        'time': dates,
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'tick_volume': np.random.randint(100, 1000, n),
        'spread': np.random.randint(10, 30, n),
        'real_volume': np.random.randint(10, 100, n)
    })
    
    filename = os.path.join(DATA_DIR, f"{symbol}_{timeframe}.csv")
    df.to_csv(filename, index=False)
    print(f"Saved {len(df)} records to {filename}")

if __name__ == "__main__":
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    for symbol in SYMBOLS:
        for tf in TIMEFRAMES:
            generate_simulated_data(symbol, tf)
            
    print("Data generation complete.")
