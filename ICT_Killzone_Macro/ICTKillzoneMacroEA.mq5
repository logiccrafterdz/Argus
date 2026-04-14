//+------------------------------------------------------------------+
//|                                         ICTKillzoneMacroEA.mq5 |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK. VERSION 1.00 (Institutional Sweep Engine) |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property version   "1.00"
#property strict

//--- Include necessary libraries
#include <Trade\Trade.mqh>
#include "..\Shared\ArgusCore.mqh"
#include "..\Shared\ArgusStructure.mqh"
#include "..\Shared\ArgusManifest.mqh"
#include "ICTUtils.mqh"

//--- States
enum ENUM_EA_STATE {
   STATE_IDLE,
   STATE_CALC_REF,
   STATE_WATCH_SWEEP,
   STATE_IN_TRADE
};

//--- Input parameters
input string   _KZ_Settings         = "------ Killzone & Macro ------";
input string   KillzoneStart        = "08:00";       // Start Time (Broker)
input string   KillzoneEnd          = "10:00";       // End Time (Broker)
input int      RefLookbackHours     = 4;            // Hours for High/Low Ref

input string   _Signal_Settings     = "------ Sweep Logic ------";
input double   SweepBufferPips      = 5.0;          // Buffer to confirm Sweep

input string   _Risk_Settings        = "------ Risk & Trade ------";
input double   RiskPercent          = 1.0;           // Risk % per trade
input bool     UseTP2               = true;          // Exit half at Mid, half at End
input bool     ForceCloseAtEnd      = true;          // Close all at KillzoneEnd
input int      MaxSpread            = 20;            // Max Allowed Spread
input int      MagicNumber          = 100017;        // EA Magic Number

//--- Global variables
CTrade         trade;
ENUM_EA_STATE  current_state = STATE_IDLE;
double         liq_high = 0, liq_low = 0;
bool           sweep_buy_triggered = false, sweep_sell_triggered = false;
bool           trade_taken_today = false;
int            vol_precision = 0;
datetime       last_calc_date = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
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

   datetime now = TimeCurrent();
   MqlDateTime dt;
   TimeToStruct(now, dt);
   int now_min = dt.hour * 60 + dt.min;
   
   int kz_start = CICTUtils::ParseTime(KillzoneStart);
   int kz_end = CICTUtils::ParseTime(KillzoneEnd);
   int calc_start = kz_start - 15;
   if(calc_start < 0) calc_start += 1440;

   // 1. Force Close at End
   if(ForceCloseAtEnd && now_min >= kz_end && (now_min < kz_start || kz_start > kz_end)) {
      if(CArgusCore::HasOpenPosition(_Symbol, MagicNumber)) {
         CloseAllPositions();
         current_state = STATE_IDLE;
         return;
      }
   }

   // 2. State Machine Logic
   switch(current_state)
   {
      case STATE_IDLE:
         if(now_min >= calc_start && now_min < kz_start && last_calc_date != iTime(_Symbol, PERIOD_D1, 0)) {
            current_state = STATE_CALC_REF;
         }
         break;

      case STATE_CALC_REF:
         if(CICTUtils::GetReferenceRange(RefLookbackHours, liq_high, liq_low)) {
            DrawRefLevels();
            last_calc_date = iTime(_Symbol, PERIOD_D1, 0);
            current_state = STATE_WATCH_SWEEP;
            sweep_buy_triggered = false;
            sweep_sell_triggered = false;
            trade_taken_today = false;
         }
         break;

      case STATE_WATCH_SWEEP:
         if(now_min >= kz_end) {
            current_state = STATE_IDLE;
            return;
         }
         
         if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > MaxSpread) return;
         if(trade_taken_today) return;
         if(CArgusCore::HasOpenPosition(_Symbol, MagicNumber)) {
            current_state = STATE_IN_TRADE;
            return;
         }

         HandleSweepDetection();
         break;

      case STATE_IN_TRADE:
         if(!CArgusCore::HasOpenPosition(_Symbol, MagicNumber)) {
            current_state = (now_min < kz_end) ? STATE_WATCH_SWEEP : STATE_IDLE;
         }
         break;
   }
}

//+------------------------------------------------------------------+
//| Detect Sweep + Rejection                                         |
//+------------------------------------------------------------------+
void HandleSweepDetection()
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double buffer = SweepBufferPips * CICTUtils::PipsToPoints();
   
   double close1 = iClose(_Symbol, _Period, 1);
   double low1 = iLow(_Symbol, _Period, 1);
   double high1 = iHigh(_Symbol, _Period, 1);

   // --- BULLISH SWEEP (BUY) ---
   // Logic: Price went BELOW liq_low - buffer, but Close[1] is ABOVE liq_low
   if(low1 < liq_low - buffer && close1 > liq_low && !sweep_buy_triggered)
   {
      ExecuteTrade(ORDER_TYPE_BUY, low1);
      sweep_buy_triggered = true;
   }
   
   // --- BEARISH SWEEP (SELL) ---
   // Logic: Price went ABOVE liq_high + buffer, but Close[1] is BELOW liq_high
   if(high1 > liq_high + buffer && close1 < liq_high && !sweep_sell_triggered)
   {
      ExecuteTrade(ORDER_TYPE_SELL, high1);
      sweep_sell_triggered = true;
   }
}

//+------------------------------------------------------------------+
//| Trading Logic                                                    |
//+------------------------------------------------------------------+
void ExecuteTrade(ENUM_ORDER_TYPE type, double stop_ref)
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double tick_sz = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double mid = (liq_high + liq_low) / 2.0;

   // Base lot calculation
   double risk_amt = (type == ORDER_TYPE_BUY) ? (ask - (stop_ref - 2 * _Point)) : ((stop_ref + 2 * _Point) - bid);
   double base_lot = CArgusCore::CalculateLotSize(_Symbol, RiskPercent, MathMax(risk_amt, 10 * _Point), vol_precision);
   if(base_lot <= 0) return;

   double min_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double step_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   if(type == ORDER_TYPE_BUY) {
      double sl = CArgusCore::NormalizePrice(_Symbol, stop_ref - (2 * _Point), tick_sz);
      sl = CArgusCore::ValidateStopsLevel(_Symbol, ask, sl);
      double tp1 = CArgusCore::NormalizePrice(_Symbol, mid, tick_sz);
      double tp2 = CArgusCore::NormalizePrice(_Symbol, liq_high, tick_sz);
      
      if(UseTP2) {
         double lot1 = NormalizeDouble(MathMax(min_lot, MathFloor((base_lot/2.0)/step_lot)*step_lot), vol_precision);
         double lot2 = NormalizeDouble(MathMax(min_lot, MathFloor((base_lot/2.0)/step_lot)*step_lot), vol_precision);
         trade.Buy(lot1, _Symbol, ask, sl, tp1, "ICT Macro Buy TP1");
         trade.Buy(lot2, _Symbol, ask, sl, tp2, "ICT Macro Buy TP2");
      } else {
         trade.Buy(base_lot, _Symbol, ask, sl, tp1, "ICT Macro Buy Full");
      }
   }
   else {
      double sl = CArgusCore::NormalizePrice(_Symbol, stop_ref + (2 * _Point), tick_sz);
      sl = CArgusCore::ValidateStopsLevel(_Symbol, bid, sl);
      double tp1 = CArgusCore::NormalizePrice(_Symbol, mid, tick_sz);
      double tp2 = CArgusCore::NormalizePrice(_Symbol, liq_low, tick_sz);
      
      if(UseTP2) {
         double lot1 = NormalizeDouble(MathMax(min_lot, MathFloor((base_lot/2.0)/step_lot)*step_lot), vol_precision);
         double lot2 = NormalizeDouble(MathMax(min_lot, MathFloor((base_lot/2.0)/step_lot)*step_lot), vol_precision);
         trade.Sell(lot1, _Symbol, bid, sl, tp1, "ICT Macro Sell TP1");
         trade.Sell(lot2, _Symbol, bid, sl, tp2, "ICT Macro Sell TP2");
      } else {
         trade.Sell(base_lot, _Symbol, bid, sl, tp1, "ICT Macro Sell Full");
      }
   }
   trade_taken_today = true;
   current_state = STATE_IN_TRADE;
}

//+------------------------------------------------------------------+
//| UI & Utilities                                                   |
//+------------------------------------------------------------------+
void DrawRefLevels()
{
   ObjectDelete(0, "ICT_RefHigh");
   ObjectDelete(0, "ICT_RefLow");
   ObjectCreate(0, "ICT_RefHigh", OBJ_HLINE, 0, 0, liq_high);
   ObjectCreate(0, "ICT_RefLow", OBJ_HLINE, 0, 0, liq_low);
   ObjectSetInteger(0, "ICT_RefHigh", OBJPROP_COLOR, clrRed);
   ObjectSetInteger(0, "ICT_RefLow", OBJPROP_COLOR, clrGreen);
   ObjectSetInteger(0, "ICT_RefHigh", OBJPROP_STYLE, STYLE_DOT);
   ObjectSetInteger(0, "ICT_RefLow", OBJPROP_STYLE, STYLE_DOT);
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

bool PositionSelectByMagic(long magic) {
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if(PositionSelectByTicket(t) && PositionGetInteger(POSITION_MAGIC) == magic && PositionGetString(POSITION_SYMBOL) == _Symbol) return true;
   }
   return false;
}

void OnDeinit(const int reason) { ObjectDelete(0, "ICT_RefHigh"); ObjectDelete(0, "ICT_RefLow"); }

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
   m.name = "ICT Killzone Macro";
   m.category = "Liquidity Hunting";
   m.magic_number = MagicNumber;
   m.regime_mask = REGIME_EXPANSION | REGIME_REVERSAL;
   m.session_mask = SESSION_LONDON | SESSION_NY;
   m.requires_trend = false;
   m.hates_high_volatility = false;
   m.target_style = "Mid Range / Extremes";
   return m;
}
