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
#include "..\Shared\ArgusCore.mqh"
#include "..\Shared\ArgusStructure.mqh"
#include "..\Shared\ArgusManifest.mqh"
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
input bool     CloseOnSessionEnd    = false;         // Close trades at session end

input string   _SMC_Settings        = "------ SMC Logic ------";
input int      SweepLookback        = 20;            // Candles to find Liq Pools
input double   SweepBufferATR       = 0.1;           // 0.1 x ATR for breach
input double   MinFVGSizeATR        = 0.2;           // Minimum gap size (ATR)
input double   EntryRetracePercent  = 50.0;          // 0 = Start of FVG, 50 = Mid

input string   _Risk_Settings        = "------ Risk & Trade ------";
input double   RiskPercent          = 1.0;           // Risk % per trade
input double   RR_Target            = 2.5;           // Reward:Risk Goal
input int      MaxSpread            = 15;            // Institutional Spread
input int      MagicNumber          = 100019;        // EA Magic Number

//--- Global variables
CTrade         trade;
int            ema_h, atr_h;
double         liq_high = 0, liq_low = 0;
double         fvg_top = 0, fvg_bottom = 0, sweep_extreme = 0;
ENUM_SMC_STATE current_state = SMC_IDLE;
ENUM_ORDER_TYPE pending_type = ORDER_TYPE_BUY;
datetime       last_bar_time = 0;
int            fvg_bar_count = 0;
int            vol_precision = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   ema_h = iMA(_Symbol, HTF_Period, EMA_Trend_Period, 0, MODE_EMA, PRICE_CLOSE);
   atr_h = iATR(_Symbol, _Period, 14);
   
   if(ema_h == INVALID_HANDLE || atr_h == INVALID_HANDLE) return(INIT_FAILED);
   
   vol_precision = CArgusCore::GetVolumePrecision(_Symbol);
   
   trade.SetExpertMagicNumber(MagicNumber);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   if(CArgusCore::IsHalted()) return;

   // --- V2.0 Regime Filter ---
   StrategyManifest m = GetManifest();
   int current_regime = (int)GlobalVariableGet("Argus_Regime");
   if(current_regime > 0 && !CManifestUtils::IsRegimeMatch(current_regime, m.regime_mask)) return;


   // 1. Session Filter
   MqlDateTime dt;
   TimeCurrent(dt);
   if(dt.hour < StartHour || dt.hour >= EndHour) {
      if(CloseOnSessionEnd && CArgusCore::HasOpenPosition(_Symbol, MagicNumber)) CloseAllPositions();
      if(current_state != SMC_IDLE) ResetState("Out of session");
      return;
   }

   datetime current_bar_time = iTime(_Symbol, _Period, 0);
   bool is_new_bar = (current_bar_time != last_bar_time);
   if(is_new_bar) last_bar_time = current_bar_time;

   if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > MaxSpread) return;
   if(CArgusCore::HasOpenPosition(_Symbol, MagicNumber)) return;

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
         if(is_new_bar) DetectFVG();
         break;

      case SMC_WAIT_ENTRY:
         HandleEntryLogic(is_new_bar);
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
   double atr[];
   if(CopyBuffer(atr_h, 0, 0, 1, atr) <= 0) return;

   double top, bottom;
   bool found = false;
   double min_fvg = atr[0] * MinFVGSizeATR;

   // FVG logic: Check index 1 (gap end), displacement is index 2
   if(pending_type == ORDER_TYPE_BUY) {
      if(CSMCUtils::IsBullishFVG(1, top, bottom) && CSMCUtils::IsDisplacement(2, atr_h) && (top - bottom) >= min_fvg) {
         fvg_top = top; fvg_bottom = bottom;
         found = true;
      }
   } else {
      if(CSMCUtils::IsBearishFVG(1, top, bottom) && CSMCUtils::IsDisplacement(2, atr_h) && (top - bottom) >= min_fvg) {
         fvg_top = top; fvg_bottom = bottom;
         found = true;
      }
   }

   if(found) {
      DrawFVG();
      fvg_bar_count = 0;
      current_state = SMC_WAIT_ENTRY;
   }
   
   // Adaptive Reset: If price moves 1.5x ATR from sweep extreme, reset
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(MathAbs(bid - sweep_extreme) > 1.5 * atr[0]) ResetState("Adaptive Reset");
}

//+------------------------------------------------------------------+
//| Step 3: Handle Entry into the Gap                                |
//+------------------------------------------------------------------+
void HandleEntryLogic(bool is_new_bar)
{
   if(is_new_bar) {
      fvg_bar_count++;
      if(fvg_bar_count > 10) {
         ResetState("FVG Expired (10 bars)");
         return;
      }
   }

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double tick_sz = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   double atr[];
   if(CopyBuffer(atr_h, 0, 0, 1, atr) <= 0) return;

   // Entry level calculation inside FVG
   double entry_level = (pending_type == ORDER_TYPE_BUY) ? 
                        (fvg_bottom + (fvg_top - fvg_bottom) * (EntryRetracePercent / 100.0)) :
                        (fvg_top - (fvg_top - fvg_bottom) * (EntryRetracePercent / 100.0));

   // Entry logic
   if(pending_type == ORDER_TYPE_BUY) {
      if(ask <= entry_level && ask >= fvg_bottom) {
         double sl = CArgusCore::NormalizePrice(_Symbol, sweep_extreme - (0.2 * atr[0]), tick_sz);
         sl = CArgusCore::ValidateStopsLevel(_Symbol, ask, sl);
         double risk = ask - sl;
         if(risk <= 0) return;
         double tp = CArgusCore::NormalizePrice(_Symbol, ask + (risk * RR_Target), tick_sz);
         
         double lot = CArgusCore::CalculateLotSize(_Symbol, RiskPercent, risk, vol_precision);
         trade.Buy(lot, _Symbol, ask, sl, tp, "SMC Sweep+FVG Buy");
         ResetState("Order Executed");
      }
   } else {
      if(bid >= entry_level && bid <= fvg_top) {
         double sl = CArgusCore::NormalizePrice(_Symbol, sweep_extreme + (0.2 * atr[0]), tick_sz);
         sl = CArgusCore::ValidateStopsLevel(_Symbol, bid, sl);
         double risk = sl - bid;
         if(risk <= 0) return;
         double tp = CArgusCore::NormalizePrice(_Symbol, bid - (risk * RR_Target), tick_sz);
         
         double lot = CArgusCore::CalculateLotSize(_Symbol, RiskPercent, risk, vol_precision);
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

void CloseAllPositions()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket) && PositionGetInteger(POSITION_MAGIC) == MagicNumber && PositionGetString(POSITION_SYMBOL) == _Symbol) {
         trade.PositionClose(ticket, -1);
      }
   }
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
   datetime t1 = iTime(_Symbol, _Period, 3);
   datetime t2 = TimeCurrent() + 7200; // Extend forward
   ObjectCreate(0, "SMC_FVG", OBJ_RECTANGLE, 0, t1, fvg_top, t2, fvg_bottom);
   ObjectSetInteger(0, "SMC_FVG", OBJPROP_COLOR, (pending_type == ORDER_TYPE_BUY) ? clrLightBlue : clrLightPink);
   ObjectSetInteger(0, "SMC_FVG", OBJPROP_FILL, true);
   ObjectSetInteger(0, "SMC_FVG", OBJPROP_BACK, true);
}

void OnDeinit(const int reason) { ObjectDelete(0, "SMC_LiqHigh"); ObjectDelete(0, "SMC_LiqLow"); ObjectDelete(0, "SMC_FVG"); IndicatorRelease(ema_h); IndicatorRelease(atr_h); }
//+------------------------------------------------------------------+
//| Trade Analytics Event                                            |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction& trans, const MqlTradeRequest& request, const MqlTradeResult& result)
{
   if(trans.type == TRADE_TRANSACTION_DEAL_ADD) {
      if(HistoryDealSelect(trans.deal)) {
         if(HistoryDealGetInteger(DEAL_MAGIC) == MagicNumber && HistoryDealGetInteger(DEAL_ENTRY) == DEAL_ENTRY_IN) {
            double sl = 0, tp = 0;
            if(PositionSelectByTicket(trans.position)) {
               sl = PositionGetDouble(POSITION_SL);
               tp = PositionGetDouble(POSITION_TP);
            }
            CArgusCore::LogTradeData(_Symbol, MagicNumber, (ENUM_ORDER_TYPE)HistoryDealGetInteger(DEAL_TYPE), HistoryDealGetDouble(DEAL_VOLUME), HistoryDealGetDouble(DEAL_PRICE), sl, tp, HistoryDealGetString(DEAL_COMMENT), trans.order);
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Strategy Manifest Identity                                       |
//+------------------------------------------------------------------+
StrategyManifest GetManifest()
{
   StrategyManifest m;
   m.name = "Liquidity Sweep FVG";
   m.category = "SMC";
   m.magic_number = MagicNumber;
   m.regime_mask = REGIME_TREND | REGIME_REVERSAL;
   m.session_mask = SESSION_LONDON | SESSION_NY;
   m.requires_trend = true;
   m.hates_high_volatility = false;
   m.target_style = "Structural Limits";
   return m;
}
