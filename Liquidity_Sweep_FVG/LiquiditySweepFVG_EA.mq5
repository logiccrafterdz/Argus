//+------------------------------------------------------------------+
//|                                        LiquiditySweepFVG_EA.mq5 |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK. VERSION 1.10 (Refined SMC Engine)         |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property version   "1.10"
#property strict

//--- Include necessary libraries
#include <Trade\Trade.mqh>
#include "SMCUtils.mqh"

//--- States
enum ENUM_SMC_STATE {
   SMC_IDLE,
   SMC_WAIT_SWEEP,
   SMC_WAIT_FVG,
   SMC_WAIT_ENTRY
};

//--- Input parameters
input string   _Regime_Settings     = "------ HTF Bias & Session ------";
input ENUM_TIMEFRAMES HTF_Period    = PERIOD_H1;     // Higher Timeframe
input int      EMA_Trend_Period     = 50;            // Trend EMA
input int      StartHour            = 8;             // London Start (Server)
input int      EndHour              = 18;            // NY Close (Server)

input string   _SMC_Settings        = "------ SMC Logic ------";
input int      SweepLookback        = 20;            // Candles to find Liq Pools
input double   SweepBufferATR       = 0.1;           // 0.1 x ATR for breach
input double   MinFVGSizeATR        = 0.2;           // Minimum gap size (ATR)
input double   EntryRetracePercent  = 50.0;          // 0 = Start of FVG, 50 = Mid

input string   _Risk_Settings        = "------ Risk & Trade ------";
input double   RiskPercent          = 1.0;           // Risk % per trade
input double   RR_Target            = 2.5;           // Reward:Risk Goal
input int      MaxSpread            = 15;            // Institutional Spread
input int      MagicNumber          = 991122;        // Magic Number

//--- Global variables
CTrade         trade;
int            ema_h, atr_h;
double         liq_high = 0, liq_low = 0;
double         fvg_top = 0, fvg_bottom = 0, sweep_extreme = 0;
ENUM_SMC_STATE current_state = SMC_IDLE;
ENUM_ORDER_TYPE pending_type = ORDER_TYPE_BUY;
datetime       last_bar_time = 0;
int            vol_precision = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   ema_h = iMA(_Symbol, HTF_Period, EMA_Trend_Period, 0, MODE_EMA, PRICE_CLOSE);
   atr_h = iATR(_Symbol, _Period, 14);
   
   if(ema_h == INVALID_HANDLE || atr_h == INVALID_HANDLE) return(INIT_FAILED);
   
   double step_vol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   vol_precision = (int)MathMax(0, MathCeil(MathLog10(1.0 / step_vol)));
   
   trade.SetExpertMagicNumber(MagicNumber);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // 1. Session Filter
   MqlDateTime dt;
   TimeCurrent(dt);
   if(dt.hour < StartHour || dt.hour >= EndHour) {
      if(current_state != SMC_IDLE) ResetState("Out of session");
      return;
   }

   datetime current_bar_time = iTime(_Symbol, _Period, 0);
   bool is_new_bar = (current_bar_time != last_bar_time);
   last_bar_time = current_bar_time;

   if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > MaxSpread) return;
   if(HasOpenPosition()) return;

   // 2. HTF Bias Check (H1 Trend)
   double ema[];
   if(CopyBuffer(ema_h, 0, 0, 1, ema) <= 0) return;
   double htf_close = iClose(_Symbol, HTF_Period, 0);
   bool bullish_bias = (htf_close > ema[0]);

   // 3. State Machine Logic
   switch(current_state)
   {
      case SMC_IDLE:
         CSMCUtils::GetLiquidityPools(SweepLookback, liq_high, liq_low);
         DrawLiquidityLines();
         current_state = SMC_WAIT_SWEEP;
         break;

      case SMC_WAIT_SWEEP:
         if(is_new_bar) {
            CSMCUtils::GetLiquidityPools(SweepLookback, liq_high, liq_low);
            DrawLiquidityLines();
         }
         DetectSweep(bullish_bias);
         break;

      case SMC_WAIT_FVG:
         DetectFVG();
         break;

      case SMC_WAIT_ENTRY:
         HandleEntryLogic();
         break;
   }
}

//+------------------------------------------------------------------+
//| Step 1: Detect Liquidity Sweep                                   |
//+------------------------------------------------------------------+
void DetectSweep(bool bullish_bias)
{
   double high1 = iHigh(_Symbol, _Period, 1);
   double low1 = iLow(_Symbol, _Period, 1);
   double close1 = iClose(_Symbol, _Period, 1);
   
   double atr[];
   if(CopyBuffer(atr_h, 0, 0, 1, atr) <= 0) return;
   double buffer = atr[0] * SweepBufferATR;

   // Bullish Setup Logic: Sweep LOW then shift UP
   if(bullish_bias && low1 < liq_low - buffer && close1 > liq_low) {
      sweep_extreme = low1;
      pending_type = ORDER_TYPE_BUY;
      current_state = SMC_WAIT_FVG;
   }
   // Bearish Setup Logic: Sweep HIGH then shift DOWN
   else if(!bullish_bias && high1 > liq_high + buffer && close1 < liq_high) {
      sweep_extreme = high1;
      pending_type = ORDER_TYPE_SELL;
      current_state = SMC_WAIT_FVG;
   }
}

//+------------------------------------------------------------------+
//| Step 2: Detect FVG Displacement                                  |
//+------------------------------------------------------------------+
void DetectFVG()
{
   double top, bottom;
   bool found = false;

   // FVG logic: Check index 1 (gap fill candle)
   if(pending_type == ORDER_TYPE_BUY) {
      if(CSMCUtils::IsBullishFVG(1, top, bottom) && CSMCUtils::IsDisplacement(1, atr_h)) {
         fvg_top = top; fvg_bottom = bottom;
         found = true;
      }
   } else {
      if(CSMCUtils::IsBearishFVG(1, top, bottom) && CSMCUtils::IsDisplacement(1, atr_h)) {
         fvg_top = top; fvg_bottom = bottom;
         found = true;
      }
   }

   if(found) {
      DrawFVG();
      current_state = SMC_WAIT_ENTRY;
   }
   
   // Adaptive Reset: If price moves 1.5x ATR from sweep extreme, reset
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double atr[];
   if(CopyBuffer(atr_h, 0, 0, 1, atr) > 0) {
      if(MathAbs(bid - sweep_extreme) > 1.5 * atr[0]) ResetState("Adaptive Reset");
   }
}

//+------------------------------------------------------------------+
//| Step 3: Handle Entry into the Gap                                |
//+------------------------------------------------------------------+
void HandleEntryLogic()
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double tick_sz = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   double atr[];
   if(CopyBuffer(atr_h, 0, 0, 1, atr) <= 0) return;

   // Entry logic
   if(pending_type == ORDER_TYPE_BUY) {
      if(ask <= fvg_top && ask >= fvg_bottom) {
         double sl = NormalizePrice(sweep_extreme - (0.2 * atr[0]), tick_sz);
         sl = ValidateStopsLevel(ask, sl);
         double risk = ask - sl;
         if(risk <= 0) return;
         double tp = NormalizePrice(ask + (risk * RR_Target), tick_sz);
         
         double lot = CalculateLotSize(risk);
         trade.Buy(lot, _Symbol, ask, sl, tp, "SMC Sweep+FVG Buy");
         ResetState("Order Executed");
      }
   } else {
      if(bid >= fvg_bottom && bid <= fvg_top) {
         double sl = NormalizePrice(sweep_extreme + (0.2 * atr[0]), tick_sz);
         sl = ValidateStopsLevel(bid, sl);
         double risk = sl - bid;
         if(risk <= 0) return;
         double tp = NormalizePrice(bid - (risk * RR_Target), tick_sz);
         
         double lot = CalculateLotSize(risk);
         trade.Sell(lot, _Symbol, bid, sl, tp, "SMC Sweep+FVG Sell");
         ResetState("Order Executed");
      }
   }
}

//+------------------------------------------------------------------+
//| Utilities & UI                                                   |
//+------------------------------------------------------------------+
void ResetState(string reason) {
   current_state = SMC_IDLE;
   ObjectDelete(0, "SMC_FVG");
   Print("SMC Reset: ", reason);
}

void DrawLiquidityLines() {
   ObjectDelete(0, "SMC_LiqHigh");
   ObjectDelete(0, "SMC_LiqLow");
   ObjectCreate(0, "SMC_LiqHigh", OBJ_HLINE, 0, 0, liq_high);
   ObjectCreate(0, "SMC_LiqLow", OBJ_HLINE, 0, 0, liq_low);
   ObjectSetInteger(0, "SMC_LiqHigh", OBJPROP_COLOR, clrRed);
   ObjectSetInteger(0, "SMC_LiqLow", OBJPROP_COLOR, clrGreen);
   ObjectSetInteger(0, "SMC_LiqHigh", OBJPROP_STYLE, STYLE_DOT);
   ObjectSetInteger(0, "SMC_LiqLow", OBJPROP_STYLE, STYLE_DOT);
}

void DrawFVG() {
   ObjectDelete(0, "SMC_FVG");
   datetime t1 = iTime(_Symbol, _Period, 4);
   datetime t2 = TimeCurrent() + 7200; // Extend forward
   ObjectCreate(0, "SMC_FVG", OBJ_RECTANGLE, 0, t1, fvg_top, t2, fvg_bottom);
   ObjectSetInteger(0, "SMC_FVG", OBJPROP_COLOR, (pending_type == ORDER_TYPE_BUY) ? clrLightBlue : clrLightPink);
   ObjectSetInteger(0, "SMC_FVG", OBJPROP_FILL, true);
   ObjectSetInteger(0, "SMC_FVG", OBJPROP_BACK, true);
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
   double tick_sz = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double m = MathMax(s, f) * tick_sz, d = MathAbs(p - t);
   if(d < m) return (t > p) ? p + m + tick_sz : p - m - tick_sz;
   return t;
}

bool HasOpenPosition() {
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      if(PositionSelectByTicket(PositionGetTicket(i)) && PositionGetInteger(POSITION_MAGIC) == MagicNumber && PositionGetString(POSITION_SYMBOL) == _Symbol) return true;
   }
   return false;
}

double NormalizePrice(double p, double t) { return MathRound(p / t) * t; }
void OnDeinit(const int reason) { ObjectDelete(0, "SMC_LiqHigh"); ObjectDelete(0, "SMC_LiqLow"); ObjectDelete(0, "SMC_FVG"); }