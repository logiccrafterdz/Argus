//+------------------------------------------------------------------+
//|                                           ORB_SessionEA.mq5      |
//|                                  Copyright 2026, Trading Studio |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK. VERSION 1.00 (Standard Gold Design)       |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Trading Studio"
#property link      "https://example.com"
#property version   "1.00"
#property strict

//--- Include necessary libraries
#include <Trade\Trade.mqh>
#include "StructureUtils.mqh"

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
input int      MagicNumber       = 998877;        // Magic Number
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
int            last_traded_day = -1;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   ema_handle = iMA(_Symbol, _Period, Trend_EMA_Period, 0, MODE_EMA, PRICE_CLOSE);
   if(ema_handle == INVALID_HANDLE) return(INIT_FAILED);
   
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
   IndicatorRelease(ema_handle);
   ObjectsDeleteAll(0, "ORB_");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // 1. Time Synchronization
   datetime now = TimeCurrent();
   MqlDateTime struct_now;
   TimeToStruct(now, struct_now);

   // 2. Daily Reset
   if(struct_now.day != last_traded_day && current_state == STATE_TRADED) {
      current_state = STATE_WAIT_START;
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
         range_high = MathMax(range_high, iHigh(_Symbol, _Period, 0));
         range_low  = MathMin(range_low, iLow(_Symbol, _Period, 0));
         
         if(now >= range_end_dt) {
            current_state = STATE_MONITOR_BREAK;
            DrawRangeLines();
            PrintFormat("ORB: Range Built. High: %.5f | Low: %.5f", range_high, range_low);
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
   if(HasOpenPosition()) return;

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
      double sl = NormalizePrice(range_low - _Point, tick_size);
      sl = ValidateStopsLevel(ask, sl);
      double risk_dist = ask - sl;
      if(risk_dist <= 0) return;
      
      double tp = NormalizePrice(ask + (risk_dist * TP_Multiplier), tick_size);
      tp = ValidateStopsLevel(ask, tp);
      
      double lot = CalculateLotSize(risk_dist);
      ExecuteTrade(ORDER_TYPE_BUY, lot, ask, sl, tp, "ORB Session Buy");
      current_state = STATE_TRADED;
      last_traded_day = TimeDay(TimeCurrent());
   }
   // 2. Short Breakout
   else if(last_close < range_low && last_close < ema_buffer[0])
   {
      double sl = NormalizePrice(range_high + _Point, tick_size);
      sl = ValidateStopsLevel(bid, sl);
      double risk_dist = sl - bid;
      if(risk_dist <= 0) return;
      
      double tp = NormalizePrice(bid - (risk_dist * TP_Multiplier), tick_size);
      tp = ValidateStopsLevel(bid, tp);
      
      double lot = CalculateLotSize(risk_dist);
      ExecuteTrade(ORDER_TYPE_SELL, lot, bid, sl, tp, "ORB Session Sell");
      current_state = STATE_TRADED;
      last_traded_day = TimeDay(TimeCurrent());
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
int TimeDay(datetime dt) { MqlDateTime s; TimeToStruct(dt, s); return s.day; }
