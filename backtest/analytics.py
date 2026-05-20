import pandas as pd
import numpy as np

def calculate_metrics(trades, equity_curve, initial_balance):
    if not trades:
        return {}
        
    df = pd.DataFrame(trades)
    df_eq = pd.DataFrame(equity_curve)
    
    # Basic metrics
    total_trades = len(df)
    winning_trades = df[df['profit'] > 0]
    losing_trades = df[df['profit'] <= 0]
    
    win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0
    gross_profit = winning_trades['profit'].sum()
    gross_loss = abs(losing_trades['profit'].sum())
    
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    net_profit = df['profit'].sum()
    total_return = (net_profit / initial_balance) * 100
    
    avg_win = winning_trades['profit'].mean() if not winning_trades.empty else 0
    avg_loss = losing_trades['profit'].mean() if not losing_trades.empty else 0
    
    # Drawdown
    df_eq['peak'] = df_eq['equity'].cummax()
    df_eq['drawdown'] = (df_eq['equity'] - df_eq['peak']) / df_eq['peak'] * 100
    max_dd = df_eq['drawdown'].min()
    
    # Sharpe Ratio (assuming daily data in equity_curve and 4.5% risk free rate)
    df_eq['daily_return'] = df_eq['equity'].pct_change()
    mean_daily_return = df_eq['daily_return'].mean()
    std_daily_return = df_eq['daily_return'].std()
    
    annual_rf_rate = 0.045
    daily_rf_rate = (1 + annual_rf_rate) ** (1/252) - 1
    
    if std_daily_return > 0:
        sharpe_ratio = np.sqrt(252) * (mean_daily_return - daily_rf_rate) / std_daily_return
    else:
        sharpe_ratio = 0
        
    # Calmar Ratio
    annual_return = mean_daily_return * 252
    calmar_ratio = annual_return / abs(max_dd/100) if max_dd < 0 else float('inf')
    
    metrics = {
        'total_return': round(total_return, 2),
        'net_profit': round(net_profit, 2),
        'total_trades': total_trades,
        'win_rate': round(win_rate, 2),
        'profit_factor': round(profit_factor, 2),
        'max_drawdown': round(max_dd, 2),
        'sharpe_ratio': round(sharpe_ratio, 2),
        'calmar_ratio': round(calmar_ratio, 2),
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
    }
    
    return metrics
