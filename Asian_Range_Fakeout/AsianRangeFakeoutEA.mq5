//+------------------------------------------------------------------+
//|                                       AsianRangeFakeoutEA.mq5    |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK. VERSION 1.00 (London Killzone Design)     |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property version   "1.00"
#property strict

//--- Include necessary libraries
#include <Trade\Trade.mqh>
#include "..\Shared\ArgusCore.mqh"
#include "..\Shared\ArgusStructure.mqh"
//--- Enums
enum ENUM_STRATEGY_STATE {
   STATE_WAITING_ASIA,
   STATE_BUILDING_ASIA,
   STATE_WAITING_LONDON,
   STATE_MONITORING_FAKEOUT,
   STATE_WAITING_CONFIRMATION,
   STATE_TRADED_OR_EXPIRED
};

enum ENUM_CONFIRM_TYPE {
   CONFIRM_CLOSE_IN,    // Aggressive: Close back inside range
   CONFIRM_STRUCTURE    // Conservative: Shift in Market Structure (MSB)
};

//--- Input parameters
input string   _AsianSettings       = "------ Asian Session ------";
input string   AsianStart           = "00:00";       // Start Time (Broker)
input int      AsianDurationMins    = 360;           // Duration (Minutes)
input double   MinAsiaRangePips     = 10.0;          // Min Range Width (Pips)
input double   MaxAsiaRangePips     = 60.0;          // Max Range Width (Pips)

input string   _LondonSettings      = "------ London Killzone ------";
input string   LondonStart          = "08:00";       // Start Monitoring (Broker)
input int      LondonDurationMins   = 180;           // Duration (Minutes)
input double   MinFakeoutPips       = 2.0;           // Min pierce distance (Pips)
input ENUM_CONFIRM_TYPE ConfirmMode = CONFIRM_STRUCTURE; // Confirmation Style

input string   _RiskSettings        = "------ Risk & Filter ------";
input bool     UseTrendFilter       = true;          // Use EMA 200 filter
input int      Trend_EMA            = 200;           // Trend Period
input double   RiskPercent          = 1.0;           // Risk % per trade
input int      TP_Ratio             = 2;             // Fixed Risk-Reward
input int      MaxSpread            = 30;            // Max Allowed Spread (Points)
input int      MagicNumber          = 100008;        // EA Magic Number

//--- Global variables
CTrade         trade;
int            ema_handle;
int            vol_precision = 0;
datetime       last_bar_time = 0;

// Strategy Tracking
ENUM_STRATEGY_STATE current_state = STATE_WAITING_ASIA;
double         asia_high = 0;
double         asia_low = 0;
datetime       asia_start_dt, asia_end_dt;
datetime       london_start_dt, london_end_dt;
int            last_sync_day = -1;

// Setup details
bool           potential_short = false;
bool           potential_long = false;
double         fakeout_extreme = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   ema_handle = iMA(_Symbol, _Period, Trend_EMA, 0, MODE_EMA, PRICE_CLOSE);
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
   ObjectsDeleteAll(0, "ARF_");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   datetime now = TimeCurrent();
   MqlDateTime dt;
   TimeToStruct(now, dt);

   // 1. Daily Sync & Cycle Reset
   if(dt.day != last_sync_day) {
      ResetStrategy();
      last_sync_day = dt.day;
      UpdateSessionWindows(dt);
      Print("ARF: New day detected. Windows updated.");
   }

   // 2. Execution on New Bar Only
   datetime current_bar_time = iTime(_Symbol, _Period, 0);
   if(current_bar_time == last_bar_time) return;
   last_bar_time = current_bar_time;

   if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > MaxSpread) return;

   // 3. State Management
   ManageStrategy(now);
}

//+------------------------------------------------------------------+
//| Strategy State Management                                        |
//+------------------------------------------------------------------+
void ManageStrategy(datetime now)
{
   switch(current_state)
   {
      case STATE_WAITING_ASIA:
         if(now >= asia_start_dt) current_state = STATE_BUILDING_ASIA;
         break;

      case STATE_BUILDING_ASIA:
         if(now >= asia_end_dt) {
            if(CArgusStructure::GetSessionRange(_Symbol, _Period, asia_start_dt, asia_end_dt, asia_high, asia_low)) {
               double range_pips = (asia_high - asia_low) / CArgusStructure::PipsToPoints(_Symbol);
               
               if(range_pips < MinAsiaRangePips || range_pips > MaxAsiaRangePips) {
                  PrintFormat("ARF: Range invalidated (Width: %.1f pips). Skipping today.", range_pips);
                  current_state = STATE_TRADED_OR_EXPIRED;
                  return;
               }

               DrawRangeBox();
               current_state = STATE_WAITING_LONDON;
               PrintFormat("ARF: Asian Range Built. H: %.5f | L: %.5f | Width: %.1f", asia_high, asia_low, range_pips);
            }
         }
         break;

      case STATE_WAITING_LONDON:
         if(now >= london_start_dt) current_state = STATE_MONITORING_FAKEOUT;
         if(now >= london_end_dt) current_state = STATE_TRADED_OR_EXPIRED;
         break;

      case STATE_MONITORING_FAKEOUT:
         if(now >= london_end_dt) current_state = STATE_TRADED_OR_EXPIRED;
         else CheckForFakeout();
         break;

      case STATE_WAITING_CONFIRMATION:
         if(now >= london_end_dt) current_state = STATE_TRADED_OR_EXPIRED;
         else CheckConfirmation();
         break;

      case STATE_TRADED_OR_EXPIRED:
         // Wait for next day reset
         break;
   }
}

//+------------------------------------------------------------------+
//| Step 1: Detect Fakeout (Price breaches range then closes back)   |
//+------------------------------------------------------------------+
void CheckForFakeout()
{
   if(CArgusCore::HasOpenPosition(_Symbol, MagicNumber)) return;

   double h1 = iHigh(_Symbol, _Period, 1);
   double l1 = iLow(_Symbol, _Period, 1);
   double c1 = iClose(_Symbol, _Period, 1);
   double pips = MinFakeoutPips * CArgusStructure::PipsToPoints(_Symbol);

   // -- Potential SHORT (Fakeout to the upside) --
   if(h1 > asia_high + pips && c1 <= asia_high) {
      potential_short = true;
      potential_long = false;
      fakeout_extreme = h1;
      current_state = STATE_WAITING_CONFIRMATION;
      Print("ARF: Potential Short Fakeout detected. Waiting for confirmation.");
   }
   
   // -- Potential LONG (Fakeout to the downside) --
   else if(l1 < asia_low - pips && c1 >= asia_low) {
      potential_long = true;
      potential_short = false;
      fakeout_extreme = l1;
      current_state = STATE_WAITING_CONFIRMATION;
      Print("ARF: Potential Long Fakeout detected. Waiting for confirmation.");
   }
}

//+------------------------------------------------------------------+
//| Step 2: Confirm Entry (Aggressive vs Conservative)              |
//+------------------------------------------------------------------+
void CheckConfirmation()
{
   if(CArgusCore::HasOpenPosition(_Symbol, MagicNumber)) return;

   // Trend Filter
   bool trend_up = true, trend_dn = true;
   if(UseTrendFilter) {
      double ema[];
      ArraySetAsSeries(ema, true);
      if(CopyBuffer(ema_handle, 0, 0, 1, ema) > 0) {
         trend_up = (iClose(_Symbol, _Period, 1) > ema[0]);
         trend_dn = (iClose(_Symbol, _Period, 1) < ema[0]);
      }
   }

   if(potential_short && trend_dn) {
      bool confirmed = (ConfirmMode == CONFIRM_CLOSE_IN); // Already closed in
      if(ConfirmMode == CONFIRM_STRUCTURE) confirmed = CArgusStructure::IsStructureBreak(_Symbol, _Period, ORDER_TYPE_SELL, 20, 5);
      
      if(confirmed) ExecuteTrade(ORDER_TYPE_SELL, fakeout_extreme);
   }
   else if(potential_long && trend_up) {
      bool confirmed = (ConfirmMode == CONFIRM_CLOSE_IN);
      if(ConfirmMode == CONFIRM_STRUCTURE) confirmed = CArgusStructure::IsStructureBreak(_Symbol, _Period, ORDER_TYPE_BUY, 20, 5);
      
      if(confirmed) ExecuteTrade(ORDER_TYPE_BUY, fakeout_extreme);
   }
}

//+------------------------------------------------------------------+
//| Trade Execution                                                  |
//+------------------------------------------------------------------+
void ExecuteTrade(ENUM_ORDER_TYPE type, double extreme)
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   if(type == ORDER_TYPE_BUY) {
      double sl = CArgusCore::NormalizePrice(_Symbol, extreme - (2 * _Point), tick_size);
      sl = CArgusCore::ValidateStopsLevel(_Symbol, ask, sl);
      double risk_dist = ask - sl;
      if(risk_dist <= 0) return;
      
      double tp = CArgusCore::NormalizePrice(_Symbol, ask + (risk_dist * TP_Ratio), tick_size);
      tp = CArgusCore::ValidateStopsLevel(_Symbol, ask, tp);
      
      double lot = CArgusCore::CalculateLotSize(_Symbol, RiskPercent, risk_dist, vol_precision);
      if(trade.Buy(lot, _Symbol, ask, sl, tp, "ARF London Long")) current_state = STATE_TRADED_OR_EXPIRED;
   }
   else {
      double sl = CArgusCore::NormalizePrice(_Symbol, extreme + (2 * _Point), tick_size);
      sl = CArgusCore::ValidateStopsLevel(_Symbol, bid, sl);
      double risk_dist = sl - bid;
      if(risk_dist <= 0) return;
      
      double tp = CArgusCore::NormalizePrice(_Symbol, bid - (risk_dist * TP_Ratio), tick_size);
      tp = CArgusCore::ValidateStopsLevel(_Symbol, bid, tp);
      
      double lot = CArgusCore::CalculateLotSize(_Symbol, RiskPercent, risk_dist, vol_precision);
      if(trade.Sell(lot, _Symbol, bid, sl, tp, "ARF London Short")) current_state = STATE_TRADED_OR_EXPIRED;
   }
}

//+------------------------------------------------------------------+
//| Helper Utilities                                                 |
//+------------------------------------------------------------------+
void ResetStrategy()
{
   current_state = STATE_WAITING_ASIA;
   asia_high = 0; asia_low = 0;
   potential_short = false; potential_long = false;
   ObjectsDeleteAll(0, "ARF_");
}

void UpdateSessionWindows(MqlDateTime &dt)
{
   string d = StringFormat("%04d.%02d.%02d ", dt.year, dt.mon, dt.day);
   asia_start_dt = StringToTime(d + AsianStart);
   asia_end_dt   = asia_start_dt + (AsianDurationMins * 60);
   london_start_dt = StringToTime(d + LondonStart);
   london_end_dt   = london_start_dt + (LondonDurationMins * 60);
}

void DrawRangeBox()
{
   string name = "ARF_Box_" + TimeToString(asia_start_dt);
   ObjectCreate(0, name, OBJ_RECTANGLE, 0, asia_start_dt, asia_high, asia_end_dt, asia_low);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clrDodgerBlue);
   ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_SOLID);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, name, OBJPROP_FILL, true);
   ObjectSetInteger(0, name, OBJPROP_BACK, true);
}

