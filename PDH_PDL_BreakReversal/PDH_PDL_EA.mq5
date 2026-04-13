//+------------------------------------------------------------------+
//|                                                   PDH_PDL_EA.mq5 |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK. VERSION 1.00 (Institutional Regime Sniper)|
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property version   "1.00"
#property strict

//--- Include necessary libraries
#include <Trade\Trade.mqh>
#include "PDHUtils.mqh"

//--- Enums
enum ENUM_STRATEGY_MODE { MODE_BOTH, MODE_BREAKOUT, MODE_REVERSAL };
enum ENUM_TRADE_STATE { STATE_WATCHING, STATE_PULLBACK, STATE_RETEST };

//--- Input parameters
input string   _Regime_Settings     = "------ Regime Filter ------";
input ENUM_STRATEGY_MODE StrategyStep = MODE_BOTH;    // Entry Filter
input bool     UseATRRegime         = true;          // Auto-Switch Mode
input double   ATR_ExpansionRatio   = 1.2;           // Ratio to trigger Breakout Mode

input string   _Logic_Settings      = "------ Logic Params ------";
input int      BreakConfirmPips     = 5;             // Pips for valid Breakout
input int      PullbackBufferPips   = 10;            // Pips zone for retest
input int      MinRejectionPips     = 10;            // Min size for rejection

input string   _Risk_Settings        = "------ Risk & Trade ------";
input double   RiskPercent          = 1.0;           // Risk % per trade
input double   RR_Target            = 2.0;           // Reward:Risk Goal
input int      MaxSpread            = 20;            // Max Allowed Spread
input int      MagicNumber          = 556677;        // Magic Number

//--- Global variables
CTrade         trade;
int            atr_h;
double         pdh = 0, pdl = 0;
ENUM_TRADE_STATE current_state = STATE_WATCHING;
ENUM_STRATEGY_MODE current_regime = MODE_REVERSAL;
datetime       last_bar_time = 0;
datetime       last_day_time = 0;
int            vol_precision = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   atr_h = iATR(_Symbol, PERIOD_D1, 14);
   if(atr_h == INVALID_HANDLE) return(INIT_FAILED);
   
   double step_vol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   vol_precision = (int)MathMax(0, MathCeil(MathLog10(1.0 / step_vol)));
   
   trade.SetExpertMagicNumber(MagicNumber);
   
   // Pre-calc levels
   pdh = CPDHUtils::GetPDH();
   pdl = CPDHUtils::GetPDL();
   
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // 1. New Day/Bar Check
   datetime current_bar_time = iTime(_Symbol, _Period, 0);
   if(current_bar_time == last_bar_time) return;
   last_bar_time = current_bar_time;

   // Update Daily Levels if day changed
   datetime current_day = iTime(_Symbol, PERIOD_D1, 0);
   if(current_day != last_day_time) {
      last_day_time = current_day;
      pdh = CPDHUtils::GetPDH();
      pdl = CPDHUtils::GetPDL();
      DrawPDH_PDL();
      current_state = STATE_WATCHING;
   }

   if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > MaxSpread) return;
   if(HasOpenPosition()) return;

   // 2. Regime Detection
   double ratio = CPDHUtils::GetATRRatio(atr_h, 14);
   if(UseATRRegime) {
      current_regime = (ratio > ATR_ExpansionRatio) ? MODE_BREAKOUT : MODE_REVERSAL;
   } else {
      if(StrategyStep == MODE_BOTH) {
         HandleBreakoutLogic();
         HandleReversalLogic();
         return;
      }
      current_regime = StrategyStep;
   }

   // 3. Signal Logic
   if(current_regime == MODE_BREAKOUT) HandleBreakoutLogic();
   else HandleReversalLogic();
}

//+------------------------------------------------------------------+
//| Handle Reversal Logic (Balance Day)                              |
//+------------------------------------------------------------------+
void HandleReversalLogic()
{
   double close1 = iClose(_Symbol, _Period, 1);
   double high1 = iHigh(_Symbol, _Period, 1);
   double low1 = iLow(_Symbol, _Period, 1);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   // Sell at PDH Reversal
   if(high1 > pdh && close1 < pdh && CPDHUtils::IsRejection(ORDER_TYPE_SELL, 1))
   {
      ExecuteTrade(ORDER_TYPE_SELL, high1);
   }
   // Buy at PDL Reversal
   else if(low1 < pdl && close1 > pdl && CPDHUtils::IsRejection(ORDER_TYPE_BUY, 1))
   {
      ExecuteTrade(ORDER_TYPE_BUY, low1);
   }
}

//+------------------------------------------------------------------+
//| Handle Breakout Logic (Expansion Day)                            |
//+------------------------------------------------------------------+
void HandleBreakoutLogic()
{
   double close1 = iClose(_Symbol, _Period, 1);
   double low1 = iLow(_Symbol, _Period, 1);
   double high1 = iHigh(_Symbol, _Period, 1);
   double buffer = PullbackBufferPips * _Point * (SymbolInfoInteger(_Symbol, SYMBOL_DIGITS) == 5 ? 10 : 1);

   // Simple Breakout + Retest Logic (Aggregated for v1)
   // Logic: Price is back at level (Retest) after a breakout (confirmed by previous candles)
   
   // LONG Retest of PDH
   if(low1 < pdh + buffer && low1 > pdh - buffer && close1 > pdh && CPDHUtils::IsRejection(ORDER_TYPE_BUY, 1))
   {
      // Check if price was significantly above PDH recently (Breakout confirmed)
      int h_idx = iHighest(_Symbol, _Period, MODE_HIGH, 10, 2);
      if(iHigh(_Symbol, _Period, h_idx) > pdh + (BreakConfirmPips * _Point * (SymbolInfoInteger(_Symbol, SYMBOL_DIGITS) == 5 ? 10 : 1))) {
         ExecuteTrade(ORDER_TYPE_BUY, low1);
      }
   }
   // SHORT Retest of PDL
   else if(high1 > pdl - buffer && high1 < pdl + buffer && close1 < pdl && CPDHUtils::IsRejection(ORDER_TYPE_SELL, 1))
   {
      int l_idx = iLowest(_Symbol, _Period, MODE_LOW, 10, 2);
      if(iLow(_Symbol, _Period, l_idx) < pdl - (BreakConfirmPips * _Point * (SymbolInfoInteger(_Symbol, SYMBOL_DIGITS) == 5 ? 10 : 1))) {
         ExecuteTrade(ORDER_TYPE_SELL, high1);
      }
   }
}

//+------------------------------------------------------------------+
//| Execution Engine                                                 |
//+------------------------------------------------------------------+
void ExecuteTrade(ENUM_ORDER_TYPE type, double sl_ref)
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double tick_sz = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   if(type == ORDER_TYPE_BUY) {
      double sl = NormalizePrice(sl_ref - (2 * _Point), tick_sz);
      sl = ValidateStopsLevel(ask, sl);
      double risk = ask - sl;
      if(risk <= 0) return;
      double tp = NormalizePrice(ask + (risk * RR_Target), tick_sz);
      
      double lot = CalculateLotSize(risk);
      trade.Buy(lot, _Symbol, ask, sl, tp, "PDH/PDL Entry");
   }
   else {
      double sl = NormalizePrice(sl_ref + (2 * _Point), tick_sz);
      sl = ValidateStopsLevel(bid, sl);
      double risk = sl - bid;
      if(risk <= 0) return;
      double tp = NormalizePrice(bid - (risk * RR_Target), tick_sz);
      
      double lot = CalculateLotSize(risk);
      trade.Sell(lot, _Symbol, bid, sl, tp, "PDH/PDL Entry");
   }
}

//+------------------------------------------------------------------+
//| Utilities                                                        |
//+------------------------------------------------------------------+
void DrawPDH_PDL() {
   ObjectDelete(0, "Argus_PDH");
   ObjectDelete(0, "Argus_PDL");
   ObjectCreate(0, "Argus_PDH", OBJ_HLINE, 0, 0, pdh);
   ObjectCreate(0, "Argus_PDL", OBJ_HLINE, 0, 0, pdl);
   ObjectSetInteger(0, "Argus_PDH", OBJPROP_COLOR, clrDodgerBlue);
   ObjectSetInteger(0, "Argus_PDL", OBJPROP_COLOR, clrOrangeRed);
   ObjectSetInteger(0, "Argus_PDH", OBJPROP_STYLE, STYLE_DASH);
   ObjectSetInteger(0, "Argus_PDL", OBJPROP_STYLE, STYLE_DASH);
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
void OnDeinit(const int reason) { ObjectDelete(0, "Argus_PDH"); ObjectDelete(0, "Argus_PDL"); }
