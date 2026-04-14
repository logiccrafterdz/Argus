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
#include "..\Shared\ArgusCore.mqh"
#include "..\Shared\ArgusStructure.mqh"
#include "..\Shared\ArgusManifest.mqh"
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
input bool     UseBiasFilter        = true;          // Only reverse AGAINST HTF trend
input int      HTF_EMA_Period       = 200;           // HTF Trend (EMA 200)

input string   _RiskSettings        = "------ Risk & Trade ------";
input double   RiskPercent          = 1.0;           // Risk % per trade
input int      MaxSpread            = 30;            // Max Allowed Spread
input int      MagicNumber          = 100009;        // EA Magic Number

//--- Global variables
CTrade         trade;
int            atr_handle;
int            ema_handle; // HTF trend filter
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

   ema_handle = iMA(_Symbol, _Period, HTF_EMA_Period, 0, MODE_EMA, PRICE_CLOSE);
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
   IndicatorRelease(atr_handle);
   IndicatorRelease(ema_handle);
   ObjectsDeleteAll(0, "NYR_");
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
            if(CArgusStructure::GetSessionRange(_Symbol, _Period, ld_start_dt, ld_end_dt, london_high, london_low)) {
               current_state = STATE_ANALYZE_EXPANSION;
               DrawLondonRange();
            }
         }
         break;

      case STATE_ANALYZE_EXPANSION:
         if(CheckLondonExpansion()) {
            current_state = STATE_MONITOR_NY_REVERSAL;
            PrintFormat("NYR: Expansion Confirmed (%.1f pips). Monitoring NY Killzone...", (london_high - london_low)/CArgusStructure::PipsToPoints(_Symbol));
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
   if(CArgusCore::HasOpenPosition(_Symbol, MagicNumber)) return;

   double h1 = iHigh(_Symbol, _Period, 1);
   double l1 = iLow(_Symbol, _Period, 1);
   double c1 = iClose(_Symbol, _Period, 1);
   double sweep_lvl = MinSweepPips * CArgusStructure::PipsToPoints(_Symbol);

   // -- Bias Check --
   bool bias_ok_sell = true;
   bool bias_ok_buy = true;
   if(UseBiasFilter) {
      double ema[];
      ArraySetAsSeries(ema, true);
      if(CopyBuffer(ema_handle, 0, 0, 1, ema) > 0) {
         // To REVERSE, we want the London move to have gone TOO FAR against the trend or 
         // we are playing a mean reversion back to the EMA.
         // Common logic: Reversal works best if London moved far from EMA or is rejected by a trend line.
         // Here we'll use a simple: Only Sell if Price is arguably overextended (above EMA)
         bias_ok_sell = (c1 > ema[0]); 
         bias_ok_buy  = (c1 < ema[0]);
      }
   }

   // -- SELL REVERSAL (London was up, NY sweeps high) --
   if(h1 > london_high + sweep_lvl && c1 < london_high && bias_ok_sell)
   {
      bool msb = RequireMSB ? CArgusStructure::IsStructureBreak(_Symbol, _Period, ORDER_TYPE_SELL, 20, 5) : true;
      if(msb) ExecuteTrade(ORDER_TYPE_SELL, h1);
   }

   // -- BUY REVERSAL (London was down, NY sweeps low) --
   else if(l1 < london_low - sweep_lvl && c1 > london_low && bias_ok_buy)
   {
      bool msb = RequireMSB ? CArgusStructure::IsStructureBreak(_Symbol, _Period, ORDER_TYPE_BUY, 20, 5) : true;
      if(msb) ExecuteTrade(ORDER_TYPE_BUY, l1);
   }
}

//+------------------------------------------------------------------+
//| Execution and Targets                                            |
//+------------------------------------------------------------------+
void ExecuteTrade(ENUM_ORDER_TYPE type, double extreme)
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   double tp_target = (london_high + london_low) / 2.0; // Primary Target: London Midpoint

   if(type == ORDER_TYPE_BUY) {
      double sl = CArgusCore::NormalizePrice(_Symbol, extreme - (2 * _Point), tick_size);
      sl = CArgusCore::ValidateStopsLevel(_Symbol, ask, sl);
      double risk_dist = ask - sl;
      if(risk_dist <= 0) return;
      
      double tp = CArgusCore::NormalizePrice(_Symbol, tp_target, tick_size);
      tp = CArgusCore::ValidateStopsLevel(_Symbol, ask, tp);
      if(tp <= ask) tp = CArgusCore::NormalizePrice(_Symbol, ask + (risk_dist * 2.0), tick_size); // Fallback to 1:2 RR
      
      double lot = CArgusCore::CalculateLotSize(_Symbol, RiskPercent, risk_dist, vol_precision);
      if(trade.Buy(lot, _Symbol, ask, sl, tp, "NY Reversal Long")) {
         current_state = STATE_TRADED_FOR_DAY;
      }
   }
   else {
      double sl = CArgusCore::NormalizePrice(_Symbol, extreme + (2 * _Point), tick_size);
      sl = CArgusCore::ValidateStopsLevel(_Symbol, bid, sl);
      double risk_dist = sl - bid;
      if(risk_dist <= 0) return;
      
      double tp = CArgusCore::NormalizePrice(_Symbol, tp_target, tick_size);
      tp = CArgusCore::ValidateStopsLevel(_Symbol, bid, tp);
      if(tp >= bid) tp = CArgusCore::NormalizePrice(_Symbol, bid - (risk_dist * 2.0), tick_size); 

      double lot = CArgusCore::CalculateLotSize(_Symbol, RiskPercent, risk_dist, vol_precision);
      if(trade.Sell(lot, _Symbol, bid, sl, tp, "NY Reversal Short")) {
         current_state = STATE_TRADED_FOR_DAY;
      }
   }
}

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
   m.name = "NY Session Reversal";
   m.category = "Reversal";
   m.magic_number = MagicNumber;
   m.regime_mask = REGIME_REVERSAL;
   m.session_mask = SESSION_NY;
   m.requires_trend = false;
   m.hates_high_volatility = false;
   m.target_style = "50% London Retracement";
   return m;
}
