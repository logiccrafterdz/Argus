//+------------------------------------------------------------------+
//|                                             NYReversalEA.mq5     |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK. VERSION 1.00 (NY Killzone Design)         |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property version   "1.00"
#property strict

//--- Include necessary libraries
#include <Trade\Trade.mqh>
#include "StructureUtils.mqh"

//--- Enums
enum ENUM_NY_STATE {
   STATE_WAIT_LONDON_END,
   STATE_ANALYZE_EXPANSION,
   STATE_MONITOR_NY_REVERSAL,
   STATE_TRADED_FOR_DAY
};

//--- Input parameters
input string   _SessionTimes        = "------ Session Windows ------";
input string   LondonStart          = "08:00";       // London Start
input string   LondonEnd            = "12:00";       // London End (Analyze time)
input string   NY_Start             = "13:00";       // NY Monitoring Start
input string   NY_End               = "15:30";       // NY Monitoring End

input string   _SetupFilters        = "------ Setup Filters ------";
input double   MinExpansionAtrMult  = 1.5;           // London Range > X * ATR
input double   MinSweepPips         = 1.0;           // Min pierce of London High/Low
input bool     RequireMSB           = true;          // Require Market Structure Break

input string   _RiskSettings        = "------ Risk & Trade ------";
input double   RiskPercent          = 1.0;           // Risk % per trade
input int      MaxSpread            = 30;            // Max Allowed Spread
input int      MagicNumber          = 776655;        // Magic Number

//--- Global variables
CTrade         trade;
int            atr_handle;
int            vol_precision = 0;
datetime       last_bar_time = 0;

// State management
ENUM_NY_STATE  current_state = STATE_WAIT_LONDON_END;
int            last_sync_day = -1;
double         london_high = 0, london_low = 0;
datetime       ld_start_dt, ld_end_dt, ny_start_dt, ny_end_dt;
bool           expansion_found = false;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   atr_handle = iATR(_Symbol, _Period, 14);
   if(atr_handle == INVALID_HANDLE) return(INIT_FAILED);
   
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
   IndicatorRelease(atr_handle);
   ObjectsDeleteAll(0, "NYR_");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   datetime now = TimeCurrent();
   MqlDateTime dt;
   TimeToStruct(now, dt);

   // 1. Daily Sync
   if(dt.day != last_sync_day) {
      ResetDailyState();
      last_sync_day = dt.day;
      UpdateSessionTimes(dt);
      Print("NYR: New day reset. Windows updated.");
   }

   // 2. New Bar Logic
   datetime current_bar_time = iTime(_Symbol, _Period, 0);
   if(current_bar_time == last_bar_time) return;
   last_bar_time = current_bar_time;

   if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > MaxSpread) return;

   // 3. State Logic
   ManageStates(now);
}

//+------------------------------------------------------------------+
//| State Controller                                                 |
//+------------------------------------------------------------------+
void ManageStates(datetime now)
{
   switch(current_state)
   {
      case STATE_WAIT_LONDON_END:
         if(now >= ld_end_dt) {
            if(CStructureUtils::GetSessionRange(ld_start_dt, ld_end_dt, london_high, london_low)) {
               current_state = STATE_ANALYZE_EXPANSION;
               DrawLondonRange();
            }
         }
         break;

      case STATE_ANALYZE_EXPANSION:
         if(CheckLondonExpansion()) {
            current_state = STATE_MONITOR_NY_REVERSAL;
            PrintFormat("NYR: Expansion Confirmed (%.1f pips). Monitoring NY Killzone...", (london_high - london_low)/CStructureUtils::PipsToPoints());
         } else {
            Print("NYR: London move too small. Skipping today.");
            current_state = STATE_TRADED_FOR_DAY;
         }
         break;

      case STATE_MONITOR_NY_REVERSAL:
         if(now >= ny_end_dt) current_state = STATE_TRADED_FOR_DAY;
         else CheckForReversalEntry();
         break;

      case STATE_TRADED_FOR_DAY:
         break;
   }
}

//+------------------------------------------------------------------+
//| Expansion Filter                                                 |
//+------------------------------------------------------------------+
bool CheckLondonExpansion()
{
   double atr[];
   if(CopyBuffer(atr_handle, 0, 0, 1, atr) <= 0) return false;
   
   double range = london_high - london_low;
   double min_range = atr[0] * MinExpansionAtrMult;
   
   return (range >= min_range);
}

//+------------------------------------------------------------------+
//| Entry Search (NY Killzone)                                       |
//+------------------------------------------------------------------+
void CheckForReversalEntry()
{
   if(HasOpenPosition()) return;

   double h1 = iHigh(_Symbol, _Period, 1);
   double l1 = iLow(_Symbol, _Period, 1);
   double c1 = iClose(_Symbol, _Period, 1);
   double sweep_lvl = MinSweepPips * CStructureUtils::PipsToPoints();

   // -- SELL REVERSAL (London was up, NY sweeps high) --
   if(h1 > london_high + sweep_lvl && c1 < london_high)
   {
      bool msb = RequireMSB ? CStructureUtils::IsStructureBreak(ORDER_TYPE_SELL, 20, 5) : true;
      if(msb) ExecuteTrade(ORDER_TYPE_SELL, h1);
   }

   // -- BUY REVERSAL (London was down, NY sweeps low) --
   else if(l1 < london_low - sweep_lvl && c1 > london_low)
   {
      bool msb = RequireMSB ? CStructureUtils::IsStructureBreak(ORDER_TYPE_BUY, 20, 5) : true;
      if(msb) ExecuteTrade(ORDER_TYPE_BUY, l1);
   }
}

//+------------------------------------------------------------------+
//| Execution and Targets                                            |
//+------------------------------------------------------------------+
void ExecuteTrade(ENUM_ORDER_TYPE type, double stop_high_low)
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double tick_sz = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   double tp_target = (london_high + london_low) / 2.0; // Primary Target: London Midpoint

   if(type == ORDER_TYPE_BUY) {
      double sl = stop_high_low - (2 * _Point);
      double risk_dist = ask - sl;
      if(risk_dist <= 0) return;
      
      double tp = NormalizePrice(tp_target, tick_sz);
      if(tp <= ask) tp = ask + (risk_dist * 2.0); // Fallback to 1:2 RR if mid is too close

      double lot = CalculateLotSize(risk_dist);
      if(trade.Buy(lot, _Symbol, ask, sl, tp, "NY Reversal Long")) {
         current_state = STATE_TRADED_FOR_DAY;
      }
   }
   else {
      double sl = stop_high_low + (2 * _Point);
      double risk_dist = sl - bid;
      if(risk_dist <= 0) return;
      
      double tp = NormalizePrice(tp_target, tick_sz);
      if(tp >= bid) tp = bid - (risk_dist * 2.0);

      double lot = CalculateLotSize(risk_dist);
      if(trade.Sell(lot, _Symbol, bid, sl, tp, "NY Reversal Short")) {
         current_state = STATE_TRADED_FOR_DAY;
      }
   }
}

//+------------------------------------------------------------------+
//| Helpers                                                          |
//+------------------------------------------------------------------+
void ResetDailyState() {
   current_state = STATE_WAIT_LONDON_END;
   london_high = 0; london_low = 0;
   expansion_found = false;
   ObjectsDeleteAll(0, "NYR_");
}

void UpdateSessionTimes(MqlDateTime &d) {
   string s = StringFormat("%04d.%02d.%02d ", d.year, d.mon, d.day);
   ld_start_dt = StringToTime(s + LondonStart);
   ld_end_dt   = StringToTime(s + LondonEnd);
   ny_start_dt = StringToTime(s + NY_Start);
   ny_end_dt   = StringToTime(s + NY_End);
}

void DrawLondonRange() {
   ObjectCreate(0, "NYR_Range", OBJ_RECTANGLE, 0, ld_start_dt, london_high, ld_end_dt, london_low);
   ObjectSetInteger(0, "NYR_Range", OBJPROP_COLOR, clrMediumSlateBlue);
   ObjectSetInteger(0, "NYR_Range", OBJPROP_FILL, true);
   ObjectSetInteger(0, "NYR_Range", OBJPROP_BACK, true);
}

double CalculateLotSize(double d) {
   double b = AccountInfoDouble(ACCOUNT_BALANCE), r = b * (RiskPercent / 100.0);
   double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE), ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(d <= 0 || tv <= 0) return 0;
   double l = r / (d / ts * tv), min = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN), max = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX), st = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   l = MathFloor(l / st) * st;
   return NormalizeDouble(MathMax(min, MathMin(max, l)), vol_precision);
}

bool HasOpenPosition() {
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      if(PositionSelectByTicket(PositionGetTicket(i)) && PositionGetInteger(POSITION_MAGIC) == MagicNumber && PositionGetString(POSITION_SYMBOL) == _Symbol) return true;
   }
   return false;
}

double NormalizePrice(double p, double t) { return MathRound(p / t) * t; }
