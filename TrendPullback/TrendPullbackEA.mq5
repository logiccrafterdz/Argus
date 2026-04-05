//+------------------------------------------------------------------+
//|                                           TrendPullbackEA.mq5    |
//|                                  Copyright 2026, Trading Studio |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK. VERSION 2.00 (Production Optimized)        |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Trading Studio"
#property link      "https://example.com"
#property version   "2.00"
#property strict

//--- Include necessary libraries
#include <Trade\Trade.mqh>
#include "StructureUtils.mqh"

//--- Input parameters
input int      FastEMA_Period = 50;     // Fast EMA Period (Pullback Zone)
input int      SlowEMA_Period = 200;    // Slow EMA Period (Trend Filter)
input int      MaxSpread      = 30;     // Max Allowed Spread (Points)
input double   RiskPercent    = 1.0;    // Risk % per Trade
input int      TP_Multiplier  = 2;      // Risk-Reward Multiplier
input int      MagicNumber    = 123456; // EA Magic Number
input bool     OnlyNewBar     = true;   // Execute on New Bar Only

//--- Global variables
CTrade         trade;
int            fast_ema_handle;
int            slow_ema_handle;
double         fast_ema_buffer[];
double         slow_ema_buffer[];
datetime       last_bar_time = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   fast_ema_handle = iMA(_Symbol, _Period, FastEMA_Period, 0, MODE_EMA, PRICE_CLOSE);
   slow_ema_handle = iMA(_Symbol, _Period, SlowEMA_Period, 0, MODE_EMA, PRICE_CLOSE);
   
   if(fast_ema_handle == INVALID_HANDLE || slow_ema_handle == INVALID_HANDLE)
   {
      Print("Error: Failed to create indicator handles.");
      return(INIT_FAILED);
   }
   
   trade.SetExpertMagicNumber(MagicNumber);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(fast_ema_handle);
   IndicatorRelease(slow_ema_handle);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // 1. New Bar Filter
   if(OnlyNewBar)
   {
      datetime current_bar_time = iTime(_Symbol, _Period, 0);
      if(current_bar_time == last_bar_time) return;
      last_bar_time = current_bar_time;
   }

   // 2. Spread Filter
   if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > MaxSpread) return;

   // 3. Position Filter (Symbol + Magic)
   if(HasOpenPosition()) return;

   // 4. Indicator Buffers
   ArraySetAsSeries(fast_ema_buffer, true);
   ArraySetAsSeries(slow_ema_buffer, true);
   
   if(CopyBuffer(fast_ema_handle, 0, 0, 3, fast_ema_buffer) < 3 ||
      CopyBuffer(slow_ema_handle, 0, 0, 3, slow_ema_buffer) < 3) return;

   // 5. Market Analysis
   double last_close = iClose(_Symbol, _Period, 1);
   double prev_close = iClose(_Symbol, _Period, 2);
   double last_high = iHigh(_Symbol, _Period, 1);
   double last_low = iLow(_Symbol, _Period, 1);
   double prev_high = iHigh(_Symbol, _Period, 2);
   double prev_low = iLow(_Symbol, _Period, 2);

   // A. Advanced Trend Filter (Relationship + Slope)
   bool is_uptrend = (fast_ema_buffer[1] > slow_ema_buffer[1]) && (slow_ema_buffer[1] > slow_ema_buffer[2]);
   bool is_downtrend = (fast_ema_buffer[1] < slow_ema_buffer[1]) && (slow_ema_buffer[1] < slow_ema_buffer[2]);

   // B. Pullback Detection (Touch EMA 50)
   bool bull_pullback = is_uptrend && (iLow(_Symbol, _Period, 1) <= fast_ema_buffer[1]);
   bool bear_pullback = is_downtrend && (iHigh(_Symbol, _Period, 1) >= fast_ema_buffer[1]);

   // C. Entry Trigger (Momentum Resumption: Break of Prev Candle)
   // We check if the current completed candle (index 1) broke the momentum after touching EMA50
   bool bull_trigger = bull_pullback && (last_close > prev_high); 
   bool bear_trigger = bear_pullback && (last_close < prev_low);

   // 6. Execution
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   if(bull_trigger)
   {
      double sl = last_low - (PipsToPoints(5)); // 5 pips below local low
      double risk_dist = ask - sl;
      if(risk_dist <= 0) return;
      
      double tp = ask + (risk_dist * TP_Multiplier);
      double lot = CalculateLotSize(risk_dist);
      
      if(lot > 0) trade.Buy(lot, _Symbol, ask, sl, tp, "TP Pullback V2 Buy");
   }
   else if(bear_trigger)
   {
      double sl = last_high + (PipsToPoints(5)); // 5 pips above local high
      double risk_dist = sl - bid;
      if(risk_dist <= 0) return;
      
      double tp = bid - (risk_dist * TP_Multiplier);
      double lot = CalculateLotSize(risk_dist);
      
      if(lot > 0) trade.Sell(lot, _Symbol, bid, sl, tp, "TP Pullback V2 Sell");
   }
}

//+------------------------------------------------------------------+
//| Proper Lot Size Calculation with Symbol Volume Step              |
//+------------------------------------------------------------------+
double CalculateLotSize(double risk_dist_points)
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double risk_amount = balance * (RiskPercent / 100.0);
   
   double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   
   if(risk_dist_points <= 0 || tick_value <= 0) return 0;
   
   // Calculate ideal lot
   double lot = risk_amount / (risk_dist_points / tick_size * tick_value);
   
   // Volume constraints
   double min_vol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_vol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step_vol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   
   // Round to nearest step
   lot = MathFloor(lot / step_vol) * step_vol;
   
   // Clamp
   lot = MathMax(min_vol, MathMin(max_vol, lot));
   
   return NormalizeDouble(lot, 2);
}

//+------------------------------------------------------------------+
//| Check for open positions by Magic and Symbol                     |
//+------------------------------------------------------------------+
bool HasOpenPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
      {
         if(PositionGetInteger(POSITION_MAGIC) == MagicNumber && 
            PositionGetString(POSITION_SYMBOL) == _Symbol) return true;
      }
   }
   return false;
}

//+------------------------------------------------------------------+
//| convert pips to points (Detects 4/5 digits)                      |
//+------------------------------------------------------------------+
double PipsToPoints(double pips)
{
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   if(digits == 3 || digits == 5) return pips * 10 * _Point;
   return pips * _Point;
}
