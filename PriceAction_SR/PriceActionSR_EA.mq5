//+------------------------------------------------------------------+
//|                                           PriceActionSR_EA.mq5   |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK. VERSION 1.00 (Standard Gold Design)       |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property version   "1.00"
#property strict

//--- Include necessary libraries
#include <Trade\Trade.mqh>
#include "StructureUtils.mqh"

//--- Input parameters
input int      SR_Lookback          = 50;            // Bars to look for S/R levels
input int      SR_Radius            = 10;            // Radius for Swing detection
input double   MaxSR_DistancePips   = 5.0;           // Rejection Proximity Zone (Pips)
input bool     UseTrendFilter       = true;          // Filter by EMA 200
input int      Trend_EMA_Period     = 200;           // Trend Filter Period
input int      MaxSpread            = 30;            // Max Allowed Spread (Points)
input double   RiskPercent          = 1.0;           // Risk % per Trade
input double   FixedRR              = 2.0;           // Target Risk-Reward Ratio
input int      MagicNumber          = 100005;        // EA Magic Number
input bool     OnlyNewBar           = true;          // Execution on New Bar Only

//--- Global variables
CTrade         trade;
int            ema_handle;
int            vol_precision = 0;
datetime       last_bar_time = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   ema_handle = iMA(_Symbol, _Period, Trend_EMA_Period, 0, MODE_EMA, PRICE_CLOSE);
   if(ema_handle == INVALID_HANDLE) return(INIT_FAILED);
   
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
   IndicatorRelease(ema_handle);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   if(OnlyNewBar) {
      datetime current_bar_time = iTime(_Symbol, _Period, 0);
      if(current_bar_time == last_bar_time) return;
      last_bar_time = current_bar_time;
   }

   if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > MaxSpread) return;
   if(HasOpenPosition()) return;

   // 1. Scan for recent S/R levels
   double near_res = CStructureUtils::GetRecentSwingHigh(SR_Lookback, SR_Radius);
   double near_sup = CStructureUtils::GetRecentSwingLow(SR_Lookback, SR_Radius);

   // 2. Trend Bias
   bool trend_up = true, trend_dn = true;
   if(UseTrendFilter) {
      double ema_buffer[];
      ArraySetAsSeries(ema_buffer, true);
      if(CopyBuffer(ema_handle, 0, 0, 1, ema_buffer) > 0) {
         trend_up = (iClose(_Symbol, _Period, 1) > ema_buffer[0]);
         trend_dn = (iClose(_Symbol, _Period, 1) < ema_buffer[0]);
      }
   }

   // 3. Pattern Detection (Bar 1 is the completed pattern)
   double body1  = MathAbs(iOpen(_Symbol, _Period, 1) - iClose(_Symbol, _Period, 1));
   double range1 = iHigh(_Symbol, _Period, 1) - iLow(_Symbol, _Period, 1);
   if(range1 < 1.0 * _Point) return; // Ignore tiny noise bars

   bool is_bullish_pin = IsPinBar(1, true);
   bool is_bearish_pin = IsPinBar(1, false);
   bool is_bullish_eng = IsEngulfing(1, true);
   bool is_bearish_eng = IsEngulfing(1, false);

   // 4. Signal Logic with Proximity Check
   double last_high = iHigh(_Symbol, _Period, 1);
   double last_low  = iLow(_Symbol, _Period, 1);
   double dist_points = MaxSR_DistancePips * PipsToPointsMultiplier();

   // -- BULLISH SIGNALS --
   if(near_sup > 0 && trend_up) {
      bool near_support = (last_low <= near_sup + dist_points);
      if(near_support && (is_bullish_pin || is_bullish_eng)) {
         string reason = is_bullish_pin ? "Bullish Pin Bar" : "Bullish Engulfing";
         ExecuteRejectionTrade(ORDER_TYPE_BUY, last_low, reason);
      }
   }

   // -- BEARISH SIGNALS --
   if(near_res > 0 && trend_dn) {
      bool near_resistance = (last_high >= near_res - dist_points);
      if(near_resistance && (is_bearish_pin || is_bearish_eng)) {
         string reason = is_bearish_pin ? "Bearish Pin Bar" : "Bearish Engulfing";
         ExecuteRejectionTrade(ORDER_TYPE_SELL, last_high, reason);
      }
   }
}

//+------------------------------------------------------------------+
//| Pattern Detectors                                                |
//+------------------------------------------------------------------+
bool IsPinBar(int idx, bool bullish)
{
   double open  = iOpen(_Symbol, _Period, idx);
   double close = iClose(_Symbol, _Period, idx);
   double high  = iHigh(_Symbol, _Period, idx);
   double low   = iLow(_Symbol, _Period, idx);
   double body  = MathAbs(open - close);
   double range = high - low;
   if(range <= 0) return false;

   double upper_wick = high - MathMax(open, close);
   double lower_wick = MathMin(open, close) - low;

   if(bullish) {
      // Long lower wick, small body in upper half, body size check
      return (lower_wick >= body * 2.5 && close > (low + range * 0.5) && body <= range * 0.33);
   } else {
      // Long upper wick, small body in lower half, body size check
      return (upper_wick >= body * 2.5 && close < (low + range * 0.5) && body <= range * 0.33);
   }
}

bool IsEngulfing(int idx, bool bullish)
{
   double o0 = iOpen(_Symbol, _Period, idx);
   double c0 = iClose(_Symbol, _Period, idx);
   double o1 = iOpen(_Symbol, _Period, idx + 1);
   double c1 = iClose(_Symbol, _Period, idx + 1);

   if(bullish) {
      return (c1 < o1 && c0 > o0 && c0 > o1 && o0 < c1);
   } else {
      return (c1 > o1 && c0 < o0 && c0 < o1 && o0 > c1);
   }
}

//+------------------------------------------------------------------+
//| Trade Execution                                                  |
//+------------------------------------------------------------------+
void ExecuteRejectionTrade(ENUM_ORDER_TYPE type, double extreme, string reason)
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   if(type == ORDER_TYPE_BUY) {
      double sl = NormalizePrice(extreme - _Point, tick_size);
      sl = ValidateStopsLevel(ask, sl);
      double risk_dist = ask - sl;
      if(risk_dist <= 0) return;
      
      double tp = NormalizePrice(ask + (risk_dist * FixedRR), tick_size);
      tp = ValidateStopsLevel(ask, tp);
      
      double lot = CalculateLotSize(risk_dist);
      SendTrade(ORDER_TYPE_BUY, lot, ask, sl, tp, "PA Rejection: " + reason);
   }
   else {
      double sl = NormalizePrice(extreme + _Point, tick_size);
      sl = ValidateStopsLevel(bid, sl);
      double risk_dist = sl - bid;
      if(risk_dist <= 0) return;
      
      double tp = NormalizePrice(bid - (risk_dist * FixedRR), tick_size);
      tp = ValidateStopsLevel(bid, tp);
      
      double lot = CalculateLotSize(risk_dist);
      SendTrade(ORDER_TYPE_SELL, lot, bid, sl, tp, "PA Rejection: " + reason);
   }
}

void SendTrade(ENUM_ORDER_TYPE type, double lot, double price, double sl, double tp, string comment)
{
   bool s = (type == ORDER_TYPE_BUY) ? trade.Buy(lot, _Symbol, price, sl, tp, comment) : trade.Sell(lot, _Symbol, price, sl, tp, comment);
   if(!s) PrintFormat("Trade Error: %d (%s)", trade.ResultRetcode(), trade.ResultRetcodeDescription());
   else PrintFormat("Trade Success: %s | Ticket: #%d | Lot: %.*f", comment, trade.ResultOrder(), vol_precision, lot);
}

//+------------------------------------------------------------------+
//| Utilities                                                        |
//+------------------------------------------------------------------+
double CalculateLotSize(double d) {
   double b = AccountInfoDouble(ACCOUNT_BALANCE), r = b * (RiskPercent / 100.0);
   double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE), ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(d <= 0 || tv <= 0) return 0;
   double l = r / (d / ts * tv), min = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN), max = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX), st = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   l = MathFloor(l / st) * st;
   return NormalizeDouble(MathMax(min, MathMin(max, l)), vol_precision);
}

double ValidateStopsLevel(double p, double t) {
   int s = (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL), f = (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   double m = MathMax(s, f) * _Point, d = MathAbs(p - t);
   if(d < m) return (t > p) ? p + m + _Point : p - m - _Point;
   return t;
}

bool HasOpenPosition() {
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      if(PositionSelectByTicket(PositionGetTicket(i)) && PositionGetInteger(POSITION_MAGIC) == MagicNumber && PositionGetString(POSITION_SYMBOL) == _Symbol) return true;
   }
   return false;
}

double NormalizePrice(double p, double t) { return MathRound(p / t) * t; }
double PipsToPointsMultiplier() { int d = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS); return (d == 3 || d == 5) ? 10.0 * _Point : _Point; }
