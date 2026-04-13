//+------------------------------------------------------------------+
//|                                           ORB_SessionEA.mq5      |
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
#include "..\Shared\ArgusCore.mqh"
#include "..\Shared\ArgusStructure.mqh"
//--- Enums
enum ENUM_ORB_STATE {
   STATE_WAIT_START,
   STATE_BUILD_RANGE,
   STATE_MONITOR_BREAK,
   STATE_TRADED
};

//--- Input parameters
input string   SessionStart      = "09:00";       // Session Start Time (HH:MM Broker)
input int      RangeDuration     = 30;            // Range Duration (Minutes)
input string   SessionEnd        = "11:30";       // End monitoring breakout (HH:MM)
input int      Trend_EMA_Period  = 200;           // Trend Filter (Current TF)
input int      MaxSpread         = 30;            // Max Allowed Spread (Points)
input double   RiskPercent       = 1.0;           // Risk % per Trade
input int      TP_Multiplier     = 2;             // Risk-Reward Ratio
input int      MagicNumber       = 100003;        // EA Magic Number
input bool     OnlyNewBar        = true;          // Execution on New Bar

//--- Global variables
CTrade         trade;
int            ema_handle;
int            vol_precision = 0;
datetime       last_bar_time = 0;

//--- ORB variables
ENUM_ORB_STATE current_state = STATE_WAIT_START;
double         range_high = 0;
double         range_low = 0;
datetime       range_start_dt = 0;
datetime       range_end_dt = 0;
datetime       session_finish_dt = 0;
int            last_sync_day = -1;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   ema_handle = iMA(_Symbol, _Period, Trend_EMA_Period, 0, MODE_EMA, PRICE_CLOSE);
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
   ObjectsDeleteAll(0, "ORB_");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   if(CArgusCore::IsHalted()) return;

   // 1. Time Synchronization
   datetime now = TimeCurrent();
   MqlDateTime struct_now;
   TimeToStruct(now, struct_now);

   // 2. Daily Sync & Cycle Reset
   if(struct_now.day != last_sync_day) {
      current_state = STATE_WAIT_START;
      last_sync_day = struct_now.day;
      ObjectsDeleteAll(0, "ORB_");
      Print("ORB: New day detected, system reset.");
   }

   if(OnlyNewBar) {
      datetime current_bar_time = iTime(_Symbol, _Period, 0);
      if(current_bar_time == last_bar_time) return;
      last_bar_time = current_bar_time;
   }

   // 3. Update Session Windows
   UpdateSessionTimes(now, struct_now);

   // 4. State Management
   ManageStates(now);
}

//+------------------------------------------------------------------+
//| Logic for managing ORB States                                    |
//+------------------------------------------------------------------+
void ManageStates(datetime now)
{
   switch(current_state)
   {
      case STATE_WAIT_START:
         if(now >= range_start_dt && now < range_end_dt) {
            current_state = STATE_BUILD_RANGE;
            range_high = -1;
            range_low = 999999;
            Print("ORB: Started building range.");
         }
         break;

      case STATE_BUILD_RANGE:
         if(now >= range_end_dt) {
            // High-precision Range Calculation using completed bars
            int bars_in_range = iBarShift(_Symbol, _Period, range_start_dt) - iBarShift(_Symbol, _Period, range_end_dt);
            if(bars_in_range > 0) {
               int high_idx = iHighest(_Symbol, _Period, MODE_HIGH, bars_in_range, iBarShift(_Symbol, _Period, range_end_dt));
               int low_idx  = iLowest(_Symbol, _Period, MODE_LOW, bars_in_range, iBarShift(_Symbol, _Period, range_end_dt));
               range_high = iHigh(_Symbol, _Period, high_idx);
               range_low  = iLow(_Symbol, _Period, low_idx);
               
               current_state = STATE_MONITOR_BREAK;
               DrawRangeLines();
               PrintFormat("ORB: Range Built. High: %.5f | Low: %.5f", range_high, range_low);
            }
            else {
               Print("Error: Failed to build ORB range. No bars found in the specified window. Check TimeZone/Data.");
               current_state = STATE_TRADED; // Stop for today to avoid errors
            }
         }
         break;

      case STATE_MONITOR_BREAK:
         if(now >= session_finish_dt) {
            current_state = STATE_TRADED;
            Print("ORB: Session finished without breakout.");
            return;
         }
         CheckBreakout();
         break;

      case STATE_TRADED:
         // Wait for next day reset
         break;
   }
}

//+------------------------------------------------------------------+
//| Breakout Detection and Execution                                 |
//+------------------------------------------------------------------+
void CheckBreakout()
{
   if(CArgusCore::HasOpenPosition(_Symbol, MagicNumber)) return;

   // Confirmation Logic
   double last_close = iClose(_Symbol, _Period, 1);
   double ema_buffer[];
   ArraySetAsSeries(ema_buffer, true);
   if(CopyBuffer(ema_handle, 0, 0, 1, ema_buffer) < 1) return;

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   // Spread & Bias Check
   if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > MaxSpread) return;

   // 1. Long Breakout
   if(last_close > range_high && last_close > ema_buffer[0])
   {
      double sl = CArgusCore::NormalizePrice(_Symbol, range_low - _Point, tick_size);
      sl = CArgusCore::ValidateStopsLevel(_Symbol, ask, sl);
      double risk_dist = ask - sl;
      if(risk_dist <= 0) return;
      
      double tp = CArgusCore::NormalizePrice(_Symbol, ask + (risk_dist * TP_Multiplier), tick_size);
      tp = CArgusCore::ValidateStopsLevel(_Symbol, ask, tp);
      
      double lot = CArgusCore::CalculateLotSize(_Symbol, RiskPercent, risk_dist, vol_precision);
      ExecuteTrade(ORDER_TYPE_BUY, lot, ask, sl, tp, "ORB Session Buy");
      current_state = STATE_TRADED;
   }
   // 2. Short Breakout
   else if(last_close < range_low && last_close < ema_buffer[0])
   {
      double sl = CArgusCore::NormalizePrice(_Symbol, range_high + _Point, tick_size);
      sl = CArgusCore::ValidateStopsLevel(_Symbol, bid, sl);
      double risk_dist = sl - bid;
      if(risk_dist <= 0) return;
      
      double tp = CArgusCore::NormalizePrice(_Symbol, bid - (risk_dist * TP_Multiplier), tick_size);
      tp = CArgusCore::ValidateStopsLevel(_Symbol, bid, tp);
      
      double lot = CArgusCore::CalculateLotSize(_Symbol, RiskPercent, risk_dist, vol_precision);
      ExecuteTrade(ORDER_TYPE_SELL, lot, bid, sl, tp, "ORB Session Sell");
      current_state = STATE_TRADED;
   }
}

//+------------------------------------------------------------------+
//| Time Utilities                                                   |
//+------------------------------------------------------------------+
void UpdateSessionTimes(datetime now, MqlDateTime &s)
{
   string date_str = StringFormat("%04d.%02d.%02d ", s.year, s.mon, s.day);
   range_start_dt = StringToTime(date_str + SessionStart);
   range_end_dt = range_start_dt + (RangeDuration * 60);
   session_finish_dt = StringToTime(date_str + SessionEnd);
}

void DrawRangeLines()
{
   ObjectsDeleteAll(0, "ORB_");
   ObjectCreate(0, "ORB_High", OBJ_HLINE, 0, 0, range_high);
   ObjectSetInteger(0, "ORB_High", OBJPROP_COLOR, clrDodgerBlue);
   ObjectSetInteger(0, "ORB_High", OBJPROP_STYLE, STYLE_DOT);
   
   ObjectCreate(0, "ORB_Low", OBJ_HLINE, 0, 0, range_low);
   ObjectSetInteger(0, "ORB_Low", OBJPROP_COLOR, clrOrangeRed);
   ObjectSetInteger(0, "ORB_Low", OBJPROP_STYLE, STYLE_DOT);
}

//+------------------------------------------------------------------+
//| Trade Execution & Logging                                        |
//+------------------------------------------------------------------+
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

//+------------------------------------------------------------------+

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
