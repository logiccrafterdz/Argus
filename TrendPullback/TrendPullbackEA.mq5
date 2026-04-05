//+------------------------------------------------------------------+
//|                                           TrendPullbackEA.mq5    |
//|                                  Copyright 2026, Trading Studio |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK. VERSION 3.00 (Production Elite)           |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Trading Studio"
#property link      "https://example.com"
#property version   "3.00"
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
int            vol_precision = 0;

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
   
   // Calculate Volume Precision dynamically
   double step_vol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   vol_precision = (int)MathMax(0, MathCeil(MathLog10(1.0 / step_vol)));
   
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

   // 2. Data Readiness Check
   if(BarsCalculated(fast_ema_handle) < SlowEMA_Period || 
      BarsCalculated(slow_ema_handle) < SlowEMA_Period) return;

   // 3. Operational Filters
   if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > MaxSpread) return;
   if(HasOpenPosition()) return;

   // 4. Update Indicators
   ArraySetAsSeries(fast_ema_buffer, true);
   ArraySetAsSeries(slow_ema_buffer, true);
   
   if(CopyBuffer(fast_ema_handle, 0, 0, 4, fast_ema_buffer) < 4 ||
      CopyBuffer(slow_ema_handle, 0, 0, 4, slow_ema_buffer) < 4) return;

   // 5. Market Analysis (2-Bar Logic)
   // Bar 0: Current (Incomplete)
   // Bar 1: Previous (Confirmation)
   // Bar 2: Pullback (Touch)
   // Bar 3: Pre-Pullback (Reference)

   double bar1_close = iClose(_Symbol, _Period, 1);
   double bar2_high  = iHigh(_Symbol, _Period, 2);
   double bar2_low   = iLow(_Symbol, _Period, 2);
   double bar2_open  = iOpen(_Symbol, _Period, 2);

   // A. Elite Trend Filter
   bool is_uptrend = (fast_ema_buffer[1] > slow_ema_buffer[1]) && (slow_ema_buffer[1] > slow_ema_buffer[2]);
   bool is_downtrend = (fast_ema_buffer[1] < slow_ema_buffer[1]) && (slow_ema_buffer[1] < slow_ema_buffer[2]);

   // B. 2-Phase Trigger (Bar 2 touches EMA50, Bar 1 breaks Bar 2)
   bool bull_pullback = is_uptrend && (iLow(_Symbol, _Period, 2) <= fast_ema_buffer[2]);
   bool bear_pullback = is_downtrend && (iHigh(_Symbol, _Period, 2) >= fast_ema_buffer[2]);

   bool bull_trigger = bull_pullback && (bar1_close > bar2_high); 
   bool bear_trigger = bear_pullback && (bar1_close < bar2_low);

   // 6. Execution Parameters
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   if(bull_trigger)
   {
      double sl = iLow(_Symbol, _Period, 1) - PipsToPriceDelta(5); // SL below confirmation candle
      sl = ValidateStopsLevel(ask, sl, true);
      
      double risk_dist = ask - sl;
      if(risk_dist <= 0) return;
      
      double tp = ask + (risk_dist * TP_Multiplier);
      tp = ValidateStopsLevel(ask, tp, false);
      
      double lot = CalculateLotSize(risk_dist);
      ExecuteTrade(ORDER_TYPE_BUY, lot, ask, sl, tp, "Elite Pullback Buy");
   }
   else if(bear_trigger)
   {
      double sl = iHigh(_Symbol, _Period, 1) + PipsToPriceDelta(5);
      sl = ValidateStopsLevel(bid, sl, true);
      
      double risk_dist = sl - bid;
      if(risk_dist <= 0) return;
      
      double tp = bid - (risk_dist * TP_Multiplier);
      tp = ValidateStopsLevel(bid, tp, false);
      
      double lot = CalculateLotSize(risk_dist);
      ExecuteTrade(ORDER_TYPE_SELL, lot, bid, sl, tp, "Elite Pullback Sell");
   }
}

//+------------------------------------------------------------------+
//| Execute and Log Result                                           |
//+------------------------------------------------------------------+
void ExecuteTrade(ENUM_ORDER_TYPE type, double lot, double price, double sl, double tp, string comment)
{
   bool success = false;
   if(type == ORDER_TYPE_BUY) success = trade.Buy(lot, _Symbol, price, sl, tp, comment);
   else success = trade.Sell(lot, _Symbol, price, sl, tp, comment);
   
   if(!success)
      PrintFormat("Trade Failed: %s. Error: %d (%s)", comment, trade.ResultRetcode(), trade.ResultRetcodeDescription());
   else
      PrintFormat("Trade Opened: %s. Ticket: %d", comment, trade.ResultOrder());
}

//+------------------------------------------------------------------+
//| Robust Lot Size Calculation                                      |
//+------------------------------------------------------------------+
double CalculateLotSize(double risk_dist_points)
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double risk_amount = balance * (RiskPercent / 100.0);
   double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   
   if(risk_dist_points <= 0 || tick_value <= 0) return 0;
   
   double lot = risk_amount / (risk_dist_points / tick_size * tick_value);
   
   double min_vol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_vol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step_vol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   
   lot = MathFloor(lot / step_vol) * step_vol;
   lot = MathMax(min_vol, MathMin(max_vol, lot));
   
   return NormalizeDouble(lot, vol_precision);
}

//+------------------------------------------------------------------+
//| Validate SL/TP against Broker Stops Level                        |
//+------------------------------------------------------------------+
double ValidateStopsLevel(double price, double target, bool is_sl)
{
   int stops_level = (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   if(stops_level == 0) return target; // No restriction
   
   double min_dist = stops_level * _Point;
   double actual_dist = MathAbs(price - target);
   
   if(actual_dist < min_dist)
   {
      // Shift target to exactly the minimum distance
      if(target > price) return price + min_dist + _Point; // Move further up
      else return price - min_dist - _Point; // Move further down
   }
   return target;
}

//+------------------------------------------------------------------+
//| Helpers                                                          |
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

double PipsToPriceDelta(double pips)
{
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   if(digits == 3 || digits == 5) return pips * 10 * _Point;
   return pips * _Point;
}
