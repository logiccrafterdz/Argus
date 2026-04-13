//+------------------------------------------------------------------+
//|                                           SR_BreakoutEA.mq5      |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK. VERSION 1.10 (Standard Gold Design)       |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property version   "1.10"
#property strict

//--- Include necessary libraries
#include <Trade\Trade.mqh>
#include "StructureUtils.mqh"

//--- Enums
enum ENUM_STATE {
   STATE_IDLE,
   STATE_WAIT_RETEST
};

enum ENUM_SIGNAL {
   SIGNAL_NONE,
   SIGNAL_BUY,
   SIGNAL_SELL
};

//--- Input parameters
input ENUM_TIMEFRAMES HTF_Timeframe = PERIOD_H4;     // Trend Timeframe
input int      HTF_EMA_Period        = 200;           // HTF Trend Filter Period
input int      SR_Lookback          = 50;            // Bars to look for S/R
input int      SR_Radius            = 10;            // Radius for Swing detection
input int      MaxWaitBars          = 10;            // Max bars to wait for retest
input int      MaxBreakDistancePips = 30;            // Max pips price can go after break
input int      MaxSpread            = 30;            // Max Allowed Spread (Points)
input double   RiskPercent          = 1.0;           // Risk % per Trade
input int      TP_Multiplier        = 2;             // Risk-Reward Multiplier
input int      MagicNumber          = 100002;        // EA Magic Number
input bool     OnlyNewBar           = true;          // Execute on New Bar Only

//--- Global variables
CTrade         trade;
int            htf_ema_handle;
int            vol_precision = 0;
datetime       last_bar_time = 0;

//--- State tracking
ENUM_STATE     current_state = STATE_IDLE;
ENUM_SIGNAL    intended_signal = SIGNAL_NONE;
double         active_level = 0;
double         max_deviation_pips = 0;
int            break_bar_index = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   htf_ema_handle = iMA(_Symbol, HTF_Timeframe, HTF_EMA_Period, 0, MODE_EMA, PRICE_CLOSE);
   
   if(htf_ema_handle == INVALID_HANDLE)
   {
      Print("Error: Failed to create HTF EMA handle.");
      return(INIT_FAILED);
   }
   
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
   IndicatorRelease(htf_ema_handle);
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
   if(HasOpenPosition()) { ResetState(); return; }

   double htf_ema_buffer[];
   ArraySetAsSeries(htf_ema_buffer, true);
   if(CopyBuffer(htf_ema_handle, 0, 0, 2, htf_ema_buffer) < 2) return;
   
   double htf_close = iClose(_Symbol, HTF_Timeframe, 1);
   bool is_bullish_bias = (htf_close > htf_ema_buffer[1]);
   bool is_bearish_bias = (htf_close < htf_ema_buffer[1]);

   if(current_state == STATE_IDLE) {
      IdentifyBreakout(is_bullish_bias, is_bearish_bias);
   }
   else if(current_state == STATE_WAIT_RETEST) {
      MonitorRetest();
   }
}

void IdentifyBreakout(bool bull_bias, bool bear_bias)
{
   if(!bull_bias && !bear_bias) return;
   
   double last_close = iClose(_Symbol, _Period, 1);
   double prev_close = iClose(_Symbol, _Period, 2);

   if(bull_bias) {
      double res = CStructureUtils::GetRecentSwingHigh(SR_Lookback, SR_Radius);
      if(res > 0 && prev_close <= res && last_close > res) {
         current_state = STATE_WAIT_RETEST;
         intended_signal = SIGNAL_BUY;
         active_level = res;
         break_bar_index = 0;
         max_deviation_pips = 0;
         PrintFormat("Breakout Detected: Resistance at %.5f. Waiting for Retest.", active_level);
      }
   }
   else if(bear_bias) {
      double sup = CStructureUtils::GetRecentSwingLow(SR_Lookback, SR_Radius);
      if(sup > 0 && prev_close >= sup && last_close < sup) {
         current_state = STATE_WAIT_RETEST;
         intended_signal = SIGNAL_SELL;
         active_level = sup;
         break_bar_index = 0;
         max_deviation_pips = 0;
         PrintFormat("Breakout Detected: Support at %.5f. Waiting for Retest.", active_level);
      }
   }
}

void MonitorRetest()
{
   break_bar_index++;
   
   if(break_bar_index > MaxWaitBars) {
      Print("Retest timeout: MaxWaitBars reached. Resetting.");
      ResetState();
      return;
   }

   double last_close = iClose(_Symbol, _Period, 1);
   double last_low = iLow(_Symbol, _Period, 1);
   double last_high = iHigh(_Symbol, _Period, 1);
   double prev_high = iHigh(_Symbol, _Period, 2);
   double prev_low = iLow(_Symbol, _Period, 2);
   
   // Track Maximum Deviation since breakout
   double current_deviation = MathAbs(last_close - active_level) / PipsToPriceDelta(1);
   if(current_deviation > max_deviation_pips) max_deviation_pips = current_deviation;

   if(max_deviation_pips > MaxBreakDistancePips) {
      PrintFormat("Price escaped too far (Max: %.1f pips). Level considered 'tired'. Resetting.", max_deviation_pips);
      ResetState();
      return;
   }

   if(intended_signal == SIGNAL_BUY) {
      bool touch = (last_low <= active_level);
      bool confirm = (last_close > prev_high);
      
      if(touch && confirm) {
         OpenPosition(ORDER_TYPE_BUY);
         ResetState();
      }
   }
   else if(intended_signal == SIGNAL_SELL) {
      bool touch = (last_high >= active_level);
      bool confirm = (last_close < prev_low);
      
      if(touch && confirm) {
         OpenPosition(ORDER_TYPE_SELL);
         ResetState();
      }
   }
}

void OpenPosition(ENUM_ORDER_TYPE type)
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double last_high = iHigh(_Symbol, _Period, 1);
   double last_low = iLow(_Symbol, _Period, 1);

   if(type == ORDER_TYPE_BUY) {
      double sl = NormalizePrice(last_low - PipsToPriceDelta(5), tick_size);
      sl = ValidateStopsLevel(ask, sl);
      double risk_dist = ask - sl;
      if(risk_dist <= 0) return;
      
      double tp = NormalizePrice(ask + (risk_dist * TP_Multiplier), tick_size);
      tp = ValidateStopsLevel(ask, tp);
      
      double lot = CalculateLotSize(risk_dist);
      ExecuteTrade(ORDER_TYPE_BUY, lot, ask, sl, tp, "Gold SR Breakout Buy");
   }
   else {
      double sl = NormalizePrice(last_high + PipsToPriceDelta(5), tick_size);
      sl = ValidateStopsLevel(bid, sl);
      double risk_dist = sl - bid;
      if(risk_dist <= 0) return;
      
      double tp = NormalizePrice(bid - (risk_dist * TP_Multiplier), tick_size);
      tp = ValidateStopsLevel(bid, tp);
      
      double lot = CalculateLotSize(risk_dist);
      ExecuteTrade(ORDER_TYPE_SELL, lot, bid, sl, tp, "Gold SR Breakout Sell");
   }
}

void ExecuteTrade(ENUM_ORDER_TYPE type, double lot, double price, double sl, double tp, string comment)
{
   bool s = (type == ORDER_TYPE_BUY) ? trade.Buy(lot, _Symbol, price, sl, tp, comment) : trade.Sell(lot, _Symbol, price, sl, tp, comment);
   
   if(!s) {
      PrintFormat("Trade Error: %d (%s)", trade.ResultRetcode(), trade.ResultRetcodeDescription());
   } else {
      PrintFormat("Trade Execution Success: %s | Ticket: #%d | Lot: %.*f | Price: %.5f", 
                  comment, trade.ResultOrder(), vol_precision, lot, price);
   }
}

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
   if(d < m) {
      double new_target = (t > p) ? p + m + _Point : p - m - _Point;
      Print("Warning: SL/TP adjusted to respect STOPS/FREEZE level limits.");
      return NormalizePrice(new_target, SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE));
   }
   return t;
}

void ResetState() { current_state = STATE_IDLE; intended_signal = SIGNAL_NONE; active_level = 0; break_bar_index = 0; max_deviation_pips = 0; }
bool HasOpenPosition() {
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      if(PositionSelectByTicket(PositionGetTicket(i)) && PositionGetInteger(POSITION_MAGIC) == MagicNumber && PositionGetString(POSITION_SYMBOL) == _Symbol) return true;
   }
   return false;
}
double NormalizePrice(double p, double t) { return MathRound(p / t) * t; }
double PipsToPriceDelta(double p) { int d = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS); return (d == 3 || d == 5) ? p * 10 * _Point : p * _Point; }
