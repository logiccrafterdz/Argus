//+------------------------------------------------------------------+
//|                                       OpeningRangeHybridEA.mq5 |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK. VERSION 1.00 (Hybrid Momentum Design)     |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property version   "1.00"
#property strict

//--- Include necessary libraries
#include <Trade\Trade.mqh>
#include "..\Shared\ArgusCore.mqh"
#include "..\Shared\ArgusStructure.mqh"
#include "ORUtils.mqh"

//--- Enums
enum ENUM_ORB_STATE {
   STATE_WAITING_OR,
   STATE_BUILDING_OR,
   STATE_MONITORING_ORB,
   STATE_TRADED_OR_EXPIRED
};

//--- Input parameters
input string   _OR_Settings         = "------ Opening Range ------";
input string   OR_Start             = "08:00";       // Start Time (Broker)
input int      OR_DurationMins      = 30;            // Duration (Minutes)
input int      MonitoringMins       = 120;           // Monitor Duration (Mins)

input string   _Hybrid_Logic        = "------ Hybrid & Failure ------";
input bool     UseBiasFilter        = true;          // Use EMA 200 filter
input double   ExpansionMult        = 1.2;           // Breakout Momentum factor
input bool     AllowFailureTrade    = true;          // Enable False Breakout logic
input bool     UseBiasForFailure    = false;         // Apply bias filter to failure trades

input string   _Risk_Trade          = "------ Risk & Trade ------";
input double   RiskPercent          = 1.0;           // Risk % per trade
input int      TP_Ratio             = 2;             // Risk-Reward
input int      MaxTradesPerDay      = 1;             // Max Trades allowed daily
input int      MaxSpread            = 30;            // Max Allowed Spread
input int      MagicNumber          = 100011;        // EA Magic Number

//--- Global variables
CTrade         trade;
int            ema_handle;
int            vol_precision = 0;
datetime       last_bar_time = 0;

// Internal Tracking
ENUM_ORB_STATE current_state = STATE_WAITING_OR;
double         or_high = 0, or_low = 0;
datetime       or_start_dt, or_end_dt, monitor_end_dt;
int            last_sync_day = -1;
int            trades_today = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   ema_handle = iMA(_Symbol, _Period, 200, 0, MODE_EMA, PRICE_CLOSE);
   if(ema_handle == INVALID_HANDLE) return(INIT_FAILED);
   
   vol_precision = CArgusCore::GetVolumePrecision(_Symbol);
   
   trade.SetExpertMagicNumber(MagicNumber);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(ema_handle);
   ObjectsDeleteAll(0, "ORH_");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   datetime now = TimeCurrent();
   MqlDateTime dt;
   TimeToStruct(now, dt);

   // 1. Daily Reset
   if(dt.day != last_sync_day) {
      ResetDailyState();
      last_sync_day = dt.day;
      UpdateSessionWindows(dt);
   }

   // 2. New Bar Execution
   datetime current_bar_time = iTime(_Symbol, _Period, 0);
   if(current_bar_time == last_bar_time) return;
   last_bar_time = current_bar_time;

   if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > MaxSpread) return;

   // 3. State Controller
   ManageStrategy(now);
}

//+------------------------------------------------------------------+
//| Strategy State Management                                        |
//+------------------------------------------------------------------+
void ManageStrategy(datetime now)
{
   switch(current_state)
   {
      case STATE_WAITING_OR:
         if(now >= or_start_dt) current_state = STATE_BUILDING_OR;
         break;

      case STATE_BUILDING_OR:
         if(now >= or_end_dt) {
            if(CORUtils::GetRangeBoundaries(or_start_dt, or_end_dt, or_high, or_low)) {
               DrawOpeningBox();
               current_state = STATE_MONITORING_ORB;
               PrintFormat("ORH: Range Built. H: %.5f | L: %.5f", or_high, or_low);
            }
         }
         break;

      case STATE_MONITORING_ORB:
         if(now >= monitor_end_dt) {
            current_state = STATE_TRADED_OR_EXPIRED;
         } else {
            CheckForSignals();
         }
         break;

      case STATE_TRADED_OR_EXPIRED:
         break;
   }
}

//+------------------------------------------------------------------+
//| Signal Detection: Breakout & Failure                             |
//+------------------------------------------------------------------+
void CheckForSignals()
{
   if(CArgusCore::HasOpenPosition(_Symbol, MagicNumber) || trades_today >= MaxTradesPerDay) return;

   double h1 = iHigh(_Symbol, _Period, 1);
   double l1 = iLow(_Symbol, _Period, 1);
   double c1 = iClose(_Symbol, _Period, 1);
   double o1 = iOpen(_Symbol, _Period, 1);

   // --- A. BREAKOUT LOGIC (Trend Aligned + Expansion) ---
   bool expansion = CORUtils::IsExpansionCandle(1, 20, ExpansionMult);
   
   // Long Breakout
   if(c1 > or_high && o1 <= or_high && expansion) {
      if(!UseBiasFilter || CORUtils::IsTrendAligned(ORDER_TYPE_BUY, ema_handle)) {
         ExecuteTrade(ORDER_TYPE_BUY, or_low, "ORH Breakout Long");
         return;
      }
   }
   // Short Breakout
   if(c1 < or_low && o1 >= or_low && expansion) {
      if(!UseBiasFilter || CORUtils::IsTrendAligned(ORDER_TYPE_SELL, ema_handle)) {
         ExecuteTrade(ORDER_TYPE_SELL, or_high, "ORH Breakout Short");
         return;
      }
   }

   // --- B. FAILURE LOGIC (Sweep and close back) ---
   if(AllowFailureTrade) {
      // Fakeout High (Short opportunity)
      if(h1 > or_high && c1 < or_high) {
         if(!UseBiasForFailure || CORUtils::IsTrendAligned(ORDER_TYPE_SELL, ema_handle)) {
            ExecuteTrade(ORDER_TYPE_SELL, h1, "ORH Failure Short");
            return;
         }
      }
      // Fakeout Low (Long opportunity)
      if(l1 < or_low && c1 > or_low) {
         if(!UseBiasForFailure || CORUtils::IsTrendAligned(ORDER_TYPE_BUY, ema_handle)) {
            ExecuteTrade(ORDER_TYPE_BUY, l1, "ORH Failure Long");
            return;
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Execution Engine                                                 |
//+------------------------------------------------------------------+
void ExecuteTrade(ENUM_ORDER_TYPE type, double sl_extreme, string comment)
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double tick_sz = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   if(type == ORDER_TYPE_BUY) {
      double sl = CArgusCore::NormalizePrice(_Symbol, sl_extreme - (2 * _Point), tick_sz);
      sl = CArgusCore::ValidateStopsLevel(_Symbol, ask, sl);
      double risk_dist = ask - sl;
      if(risk_dist <= 0) return;
      
      double tp = CArgusCore::NormalizePrice(_Symbol, ask + (risk_dist * TP_Ratio), tick_sz);
      tp = CArgusCore::ValidateStopsLevel(_Symbol, ask, tp);
      
      double lot = CArgusCore::CalculateLotSize(_Symbol, RiskPercent, risk_dist, vol_precision);
      if(trade.Buy(lot, _Symbol, ask, sl, tp, comment)) {
         trades_today++;
         current_state = STATE_TRADED_OR_EXPIRED;
      }
   }
   else {
      double sl = CArgusCore::NormalizePrice(_Symbol, sl_extreme + (2 * _Point), tick_sz);
      sl = CArgusCore::ValidateStopsLevel(_Symbol, bid, sl);
      double risk_dist = sl - bid;
      if(risk_dist <= 0) return;
      
      double tp = CArgusCore::NormalizePrice(_Symbol, bid - (risk_dist * TP_Ratio), tick_sz);
      tp = CArgusCore::ValidateStopsLevel(_Symbol, bid, tp);
      
      double lot = CArgusCore::CalculateLotSize(_Symbol, RiskPercent, risk_dist, vol_precision);
      if(trade.Sell(lot, _Symbol, bid, sl, tp, comment)) {
         trades_today++;
         current_state = STATE_TRADED_OR_EXPIRED;
      }
   }
}

//+------------------------------------------------------------------+
//| Helpers                                                          |
//+------------------------------------------------------------------+
void ResetDailyState() {
   current_state = STATE_WAITING_OR;
   or_high = 0; or_low = 0;
   trades_today = 0;
   ObjectsDeleteAll(0, "ORH_");
}

void UpdateSessionWindows(MqlDateTime &dt) {
   string d = StringFormat("%04d.%02d.%02d ", dt.year, dt.mon, dt.day);
   or_start_dt    = StringToTime(d + OR_Start);
   or_end_dt      = or_start_dt + (OR_DurationMins * 60);
   monitor_end_dt = or_end_dt + (MonitoringMins * 60);
}

void DrawOpeningBox() {
   ObjectCreate(0, "ORH_Box", OBJ_RECTANGLE, 0, or_start_dt, or_high, or_end_dt, or_low);
   ObjectSetInteger(0, "ORH_Box", OBJPROP_COLOR, clrDarkOrange);
   ObjectSetInteger(0, "ORH_Box", OBJPROP_FILL, true);
   ObjectSetInteger(0, "ORH_Box", OBJPROP_BACK, true);
}

