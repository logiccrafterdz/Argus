//+------------------------------------------------------------------+
//|                                     BollingerMeanReversionEA.mq5 |
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
enum ENUM_BB_STATE {
   STATE_IDLE,
   STATE_OUTSIDE_UPPER,
   STATE_OUTSIDE_LOWER
};

//--- Input parameters
input int      BB_Period      = 20;            // Bollinger Bands Period
input double   BB_Deviation   = 2.0;           // Bollinger Bands Deviation
input bool     UseRSIFilter   = true;          // Enable RSI Confirmation
input int      RSI_Period     = 14;            // RSI Period
input double   RSI_Overbought = 70.0;          // RSI Overbought Level
input double   RSI_Oversold   = 30.0;          // RSI Oversold Level
input bool     UseTrendFilter = false;         // Enable EMA Trend Filter
input int      Trend_EMA_Period = 200;         // Trend Filter Period
input int      MaxBarsOutside = 15;            // Max candles allowed outside band
input int      MaxSpread      = 30;            // Max Allowed Spread (Points)
input double   RiskPercent    = 1.0;           // Risk % per Trade
input int      MagicNumber    = 887766;        // Magic Number
input bool     OnlyNewBar     = true;          // Execute on New Bar Only

//--- Global variables
CTrade         trade;
int            bb_handle;
int            rsi_handle;
int            ema_handle;
int            vol_precision = 0;
datetime       last_bar_time = 0;

//--- State tracking
ENUM_BB_STATE  current_state = STATE_IDLE;
double         limit_price = 0; 
int            bars_since_outside = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   bb_handle = iBands(_Symbol, _Period, BB_Period, 0, BB_Deviation, PRICE_CLOSE);
   rsi_handle = iRSI(_Symbol, _Period, RSI_Period, PRICE_CLOSE);
   ema_handle = iMA(_Symbol, _Period, Trend_EMA_Period, 0, MODE_EMA, PRICE_CLOSE);
   
   if(bb_handle == INVALID_HANDLE || rsi_handle == INVALID_HANDLE || ema_handle == INVALID_HANDLE)
   {
      Print("Error: Failed to create indicator handles.");
      return(INIT_FAILED);
   }
   
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
   IndicatorRelease(bb_handle);
   IndicatorRelease(rsi_handle);
   IndicatorRelease(ema_handle);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   if(OnlyNewBar) {
      datetime current_bar_time = iTime(_Symbol, _Period, 0);
      if(current_bar_time == last_bar_time) return;
      last_bar_time = current_bar_time;
   }

   if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > MaxSpread) return;
   if(HasOpenPosition()) { current_state = STATE_IDLE; return; }

   double bb_mid[], bb_up[], bb_low[], rsi[];
   ArraySetAsSeries(bb_mid, true);
   ArraySetAsSeries(bb_up, true);
   ArraySetAsSeries(bb_low, true);
   ArraySetAsSeries(rsi, true);

   if(CopyBuffer(bb_handle, 0, 0, 2, bb_mid) < 2 ||
      CopyBuffer(bb_handle, 1, 0, 2, bb_up) < 2 ||
      CopyBuffer(bb_handle, 2, 0, 2, bb_low) < 2 ||
      CopyBuffer(rsi_handle, 0, 0, 2, rsi) < 2) return;

   double close1 = iClose(_Symbol, _Period, 1);
   double high1  = iHigh(_Symbol, _Period, 1);
   double low1   = iLow(_Symbol, _Period, 1);

   //--- State Machine Logic
   switch(current_state)
   {
      case STATE_IDLE:
         if(high1 > bb_up[1]) { 
            current_state = STATE_OUTSIDE_UPPER; 
            limit_price = high1;
            bars_since_outside = 0;
         }
         else if(low1 < bb_low[1]) { 
            current_state = STATE_OUTSIDE_LOWER; 
            limit_price = low1;
            bars_since_outside = 0;
         }
         break;

      case STATE_OUTSIDE_UPPER:
         bars_since_outside++;
         if(bars_since_outside > MaxBarsOutside) { current_state = STATE_IDLE; return; }
         
         limit_price = MathMax(limit_price, high1);
         // Confirmation: Close inside BB + Optional RSI + Optional Trend
         if(close1 < bb_up[1]) {
            bool rsi_ok = !UseRSIFilter || (rsi[1] > RSI_Overbought);
            bool trend_ok = true;
            if(UseTrendFilter) {
               double ema_buffer[];
               if(CopyBuffer(ema_handle, 0, 0, 1, ema_buffer) > 0) trend_ok = (close1 < ema_buffer[0]);
            }

            if(rsi_ok && trend_ok) {
               OpenPosition(ORDER_TYPE_SELL, bb_mid[1], limit_price);
            }
            current_state = STATE_IDLE;
         }
         break;

      case STATE_OUTSIDE_LOWER:
         bars_since_outside++;
         if(bars_since_outside > MaxBarsOutside) { current_state = STATE_IDLE; return; }

         limit_price = MathMin(limit_price, low1);
         // Confirmation: Close inside BB + Optional RSI + Optional Trend
         if(close1 > bb_low[1]) {
            bool rsi_ok = !UseRSIFilter || (rsi[1] < RSI_Oversold);
            bool trend_ok = true;
            if(UseTrendFilter) {
               double ema_buffer[];
               if(CopyBuffer(ema_handle, 0, 0, 1, ema_buffer) > 0) trend_ok = (close1 > ema_buffer[0]);
            }

            if(rsi_ok && trend_ok) {
               OpenPosition(ORDER_TYPE_BUY, bb_mid[1], limit_price);
            }
            current_state = STATE_IDLE;
         }
         break;
   }
}

void OpenPosition(ENUM_ORDER_TYPE type, double target_mean, double extreme_price)
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   if(type == ORDER_TYPE_BUY) {
      double sl = NormalizePrice(extreme_price - _Point, tick_size);
      sl = ValidateStopsLevel(ask, sl);
      double tp = NormalizePrice(target_mean, tick_size);
      tp = ValidateStopsLevel(ask, tp);
      
      double risk_dist = ask - sl;
      if(risk_dist <= 0) return;
      
      double lot = CalculateLotSize(risk_dist);
      ExecuteTrade(ORDER_TYPE_BUY, lot, ask, sl, tp, "BB Mean Reversion Buy");
   }
   else {
      double sl = NormalizePrice(extreme_price + _Point, tick_size);
      sl = ValidateStopsLevel(bid, sl);
      double tp = NormalizePrice(target_mean, tick_size);
      tp = ValidateStopsLevel(bid, tp);
      
      double risk_dist = sl - bid;
      if(risk_dist <= 0) return;
      
      double lot = CalculateLotSize(risk_dist);
      ExecuteTrade(ORDER_TYPE_SELL, lot, bid, sl, tp, "BB Mean Reversion Sell");
   }
}

void ExecuteTrade(ENUM_ORDER_TYPE type, double lot, double price, double sl, double tp, string comment)
{
   bool s = (type == ORDER_TYPE_BUY) ? trade.Buy(lot, _Symbol, price, sl, tp, comment) : trade.Sell(lot, _Symbol, price, sl, tp, comment);
   
   if(!s) {
      PrintFormat("Trade Error: %d (%s)", trade.ResultRetcode(), trade.ResultRetcodeDescription());
   } else {
      PrintFormat("Trade Success: %s | Ticket: #%d | Lot: %.*f | TP: %.5f", 
                  comment, trade.ResultOrder(), vol_precision, lot, tp);
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
