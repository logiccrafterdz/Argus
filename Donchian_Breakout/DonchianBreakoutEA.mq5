//+------------------------------------------------------------------+
//|                                         DonchianBreakoutEA.mq5 |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK. VERSION 1.00 (Momentum Breakout Sniper)   |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property version   "1.00"
#property strict

//--- Include necessary libraries
#include <Trade\Trade.mqh>
#include "DonchianUtils.mqh"

//--- Input parameters
input string   _DC_Settings         = "------ Donchian Channel ------";
input int      Donchian_Period      = 20;            // Lookback Period

input string   _Filter_Settings     = "------ Filters ------";
input int      EMA_Fast             = 50;            // Fast Trend
input int      EMA_Slow             = 200;           // Slow Trend
input int      ADX_MinStrength      = 20;            // Min Volatility Filter
input bool     RequireRisingADX     = true;          // Must be accelerating

input string   _Risk_Settings        = "------ Risk & Trade ------";
input double   RiskPercent          = 1.0;           // Risk % per trade
input double   ATR_Multiplier       = 1.5;           // SL (if not using Channel)
input int      MaxSpread            = 30;            // Max Allowed Spread
input int      MagicNumber          = 991122;        // Magic Number

//--- Global variables
CTrade         trade;
int            ema_fast_h, ema_slow_h, adx_h, atr_h;
int            vol_precision = 0;
datetime       last_bar_time = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   ema_fast_h = iMA(_Symbol, _Period, EMA_Fast, 0, MODE_EMA, PRICE_CLOSE);
   ema_slow_h = iMA(_Symbol, _Period, EMA_Slow, 0, MODE_EMA, PRICE_CLOSE);
   adx_h      = iADX(_Symbol, _Period, 14);
   atr_h      = iATR(_Symbol, _Period, 14);
   
   if(ema_fast_h == INVALID_HANDLE || ema_slow_h == INVALID_HANDLE || adx_h == INVALID_HANDLE || atr_h == INVALID_HANDLE) 
      return(INIT_FAILED);
   
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
   IndicatorRelease(ema_fast_h);
   IndicatorRelease(ema_slow_h);
   IndicatorRelease(adx_h);
   IndicatorRelease(atr_h);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Trailing Logic (follows the opposite Donchian band)
   if(PositionSelectByMagic(MagicNumber)) {
      HandleTrailingStop();
   }

   // Signal Check on New Bar
   datetime current_bar_time = iTime(_Symbol, _Period, 0);
   if(current_bar_time == last_bar_time) return;
   last_bar_time = current_bar_time;

   if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > MaxSpread) return;
   if(HasOpenPosition()) return;

   // 1. Regime Filter: ADX Strength
   double adx[];
   if(CopyBuffer(adx_h, 0, 1, 1, adx) <= 0) return;
   if(adx[0] < ADX_MinStrength) return;

   // Rising ADX Filter
   if(RequireRisingADX) {
      double adx_prev[];
      if(CopyBuffer(adx_h, 0, 2, 1, adx_prev) > 0) {
         if(adx[0] <= adx_prev[0]) return;
      }
   }

   // 2. Trend Filter: Faster/Slower EMA
   double ema50[], ema200[];
   if(CopyBuffer(ema_fast_h, 0, 1, 1, ema50) <= 0) return;
   if(CopyBuffer(ema_slow_h, 0, 1, 1, ema200) <= 0) return;
   
   double close1 = iClose(_Symbol, _Period, 1);
   
   // Donchian Levels (calculated from shift 2 to check breakout of completed bar 1)
   double upper_zone = CDonchianUtils::GetUpper(Donchian_Period, 2);
   double lower_zone = CDonchianUtils::GetLower(Donchian_Period, 2);

   // --- LONG SIGNAL ---
   if(close1 > upper_zone && close1 > ema50[0] && close1 > ema200[0])
   {
      double sl_price = CDonchianUtils::GetLower(Donchian_Period, 1);
      ExecuteTrade(ORDER_TYPE_BUY, sl_price);
   }
   // --- SHORT SIGNAL ---
   else if(close1 < lower_zone && close1 < ema50[0] && close1 < ema200[0])
   {
      double sl_price = CDonchianUtils::GetUpper(Donchian_Period, 1);
      ExecuteTrade(ORDER_TYPE_SELL, sl_price);
   }
}

//+------------------------------------------------------------------+
//| Trailing Stop: Turtles follow the opposite band                  |
//+------------------------------------------------------------------+
void HandleTrailingStop()
{
   if(!PositionSelectByMagic(MagicNumber)) return;
   
   ulong ticket = PositionGetInteger(POSITION_TICKET);
   double current_sl = PositionGetDouble(POSITION_SL);
   ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
   
   if(type == POSITION_TYPE_BUY) {
      double new_sl = CDonchianUtils::GetLower(Donchian_Period, 1);
      if(new_sl > current_sl + _Point) {
         trade.PositionModify(ticket, NormalizePrice(new_sl, _Point), 0);
      }
   }
   else if(type == POSITION_TYPE_SELL) {
      double new_sl = CDonchianUtils::GetUpper(Donchian_Period, 1);
      if(new_sl < current_sl - _Point) {
         trade.PositionModify(ticket, NormalizePrice(new_sl, _Point), 0);
      }
   }
}

//+------------------------------------------------------------------+
//| Execution Engine                                                 |
//+------------------------------------------------------------------+
void ExecuteTrade(ENUM_ORDER_TYPE type, double sl_ref)
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double tick_sz = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   if(type == ORDER_TYPE_BUY) {
      double sl = NormalizePrice(sl_ref - (2 * _Point), tick_sz);
      sl = ValidateStopsLevel(ask, sl);
      double risk_dist = ask - sl;
      if(risk_dist <= 0) return;
      
      double tp = NormalizePrice(ask + (risk_dist * 2.5), tick_sz);
      // Removed ValidateStopsLevel for TP (usually far enough)
      
      double lot = CalculateLotSize(risk_dist);
      trade.Buy(lot, _Symbol, ask, sl, tp, "Donchian Breakout Long");
   }
   else {
      double sl = NormalizePrice(sl_ref + (2 * _Point), tick_sz);
      sl = ValidateStopsLevel(bid, sl);
      double risk_dist = sl - bid;
      if(risk_dist <= 0) return;
      
      double tp = NormalizePrice(bid - (risk_dist * 2.5), tick_sz);
      // Removed ValidateStopsLevel for TP
      
      double lot = CalculateLotSize(risk_dist);
      trade.Sell(lot, _Symbol, bid, sl, tp, "Donchian Breakout Short");
   }
}

//+------------------------------------------------------------------+
//| Support Utilities                                                |
//+------------------------------------------------------------------+
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

bool PositionSelectByMagic(long magic) {
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if(PositionSelectByTicket(t) && PositionGetInteger(POSITION_MAGIC) == magic && PositionGetString(POSITION_SYMBOL) == _Symbol) return true;
   }
   return false;
}

double NormalizePrice(double p, double t) { return MathRound(p / t) * t; }
