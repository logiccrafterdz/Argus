//+------------------------------------------------------------------+
//|                                           TrendPullbackEA.mq5    |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK. VERSION 3.10 (Standard Gold Refined)      |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property version   "3.10"
#property strict

//--- Include necessary libraries
#include <Trade\Trade.mqh>
#include "StructureUtils.mqh"

//--- Input parameters
input int      FastEMA_Period = 50;     // Fast EMA Period (Pullback Zone)
input int      SlowEMA_Period = 200;    // Slow EMA Period (Trend Filter)
input int      MarketStructurePeriod = 30; // Bars to check for HH/HL structure
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
   
   // Volume Precision
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
   if(OnlyNewBar)
   {
      datetime current_bar_time = iTime(_Symbol, _Period, 0);
      if(current_bar_time == last_bar_time) return;
      last_bar_time = current_bar_time;
   }

   if(BarsCalculated(fast_ema_handle) < SlowEMA_Period || 
      BarsCalculated(slow_ema_handle) < SlowEMA_Period) return;

   if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > MaxSpread) return;
   if(HasOpenPosition()) return;

   ArraySetAsSeries(fast_ema_buffer, true);
   ArraySetAsSeries(slow_ema_buffer, true);
   if(CopyBuffer(fast_ema_handle, 0, 0, 4, fast_ema_buffer) < 4 ||
      CopyBuffer(slow_ema_handle, 0, 0, 4, slow_ema_buffer) < 4) return;

   // Market Analysis (2-Bar Logic + HH/HL Structure)
   double bar1_close = iClose(_Symbol, _Period, 1);
   double bar2_high  = iHigh(_Symbol, _Period, 2);
   double bar2_low   = iLow(_Symbol, _Period, 2);

   // A. Strategic Trend Confluence
   bool ema_bias_up = (fast_ema_buffer[1] > slow_ema_buffer[1]) && (slow_ema_buffer[1] > slow_ema_buffer[2]);
   bool ema_bias_dn = (fast_ema_buffer[1] < slow_ema_buffer[1]) && (slow_ema_buffer[1] < slow_ema_buffer[2]);
   
   bool structure_up = CStructureUtils::IsBullishStructure(MarketStructurePeriod);
   bool structure_dn = CStructureUtils::IsBearishStructure(MarketStructurePeriod);

   bool is_uptrend = ema_bias_up && structure_up;
   bool is_downtrend = ema_bias_dn && structure_dn;

   // B. Trigger Logic
   bool bull_pullback = is_uptrend && (iLow(_Symbol, _Period, 2) <= fast_ema_buffer[2]);
   bool bear_pullback = is_downtrend && (iHigh(_Symbol, _Period, 2) >= fast_ema_buffer[2]);

   bool bull_trigger = bull_pullback && (bar1_close > bar2_high); 
   bool bear_trigger = bear_pullback && (bar1_close < bar2_low);

   // C. Pricing & Validation
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   if(bull_trigger)
   {
      double sl = NormalizePrice(iLow(_Symbol, _Period, 1) - PipsToPriceDelta(5), tick_size);
      sl = ValidateStopsLevel(ask, sl);
      
      double risk_dist = ask - sl;
      if(risk_dist <= 0) return;
      
      double tp = NormalizePrice(ask + (risk_dist * TP_Multiplier), tick_size);
      tp = ValidateStopsLevel(ask, tp);
      
      double lot = CalculateLotSize(risk_dist);
      ExecuteTrade(ORDER_TYPE_BUY, lot, ask, sl, tp, "Gold Pullback Buy");
   }
   else if(bear_trigger)
   {
      double sl = NormalizePrice(iHigh(_Symbol, _Period, 1) + PipsToPriceDelta(5), tick_size);
      sl = ValidateStopsLevel(bid, sl);
      
      double risk_dist = sl - bid;
      if(risk_dist <= 0) return;
      
      double tp = NormalizePrice(bid - (risk_dist * TP_Multiplier), tick_size);
      tp = ValidateStopsLevel(bid, tp);
      
      double lot = CalculateLotSize(risk_dist);
      ExecuteTrade(ORDER_TYPE_SELL, lot, bid, sl, tp, "Gold Pullback Sell");
   }
}

//+------------------------------------------------------------------+
//| Execute and Log Result                                           |
//+------------------------------------------------------------------+
void ExecuteTrade(ENUM_ORDER_TYPE type, double lot, double price, double sl, double tp, string comment)
{
   bool success = (type == ORDER_TYPE_BUY) ? trade.Buy(lot, _Symbol, price, sl, tp, comment) : trade.Sell(lot, _Symbol, price, sl, tp, comment);
   
   if(!success)
      PrintFormat("Trade Failed: %s. Code: %d (%s)", comment, trade.ResultRetcode(), trade.ResultRetcodeDescription());
   else
      PrintFormat("Trade Opened: %s. Ticket: %d. Lot: %.*f", comment, trade.ResultOrder(), vol_precision, lot);
}

//+------------------------------------------------------------------+
//| Standard Volume Calculation                                      |
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
//| Logic for Validating Stops against BOTH Stops and Freeze levels  |
//+------------------------------------------------------------------+
double ValidateStopsLevel(double price, double target)
{
   int stops_level = (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   int freeze_level = (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   int max_level = MathMax(stops_level, freeze_level);
   
   double min_dist = max_level * _Point;
   double actual_dist = MathAbs(price - target);
   
   if(actual_dist < min_dist)
   {
      double new_target = (target > price) ? price + min_dist + _Point : price - min_dist - _Point;
      PrintFormat("Warning: SL/TP too close to price (MaxLevel: %d). Adjusted to respect Broker limits. RR Impact possible.", max_level);
      return NormalizePrice(new_target, SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE));
   }
   return target;
}

//+------------------------------------------------------------------+
//| Helpers                                                          |
//+------------------------------------------------------------------+
double NormalizePrice(double price, double tick_size) { return MathRound(price / tick_size) * tick_size; }

bool HasOpenPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket) && PositionGetInteger(POSITION_MAGIC) == MagicNumber && PositionGetString(POSITION_SYMBOL) == _Symbol) return true;
   }
   return false;
}

double PipsToPriceDelta(double pips)
{
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   return (digits == 3 || digits == 5) ? pips * 10 * _Point : pips * _Point;
}
