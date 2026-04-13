//+------------------------------------------------------------------+
//|                                         HiddenDivergenceEA.mq5 |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK. VERSION 1.00 (Momentum Continuation)      |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property version   "1.00"
#property strict

//--- Include necessary libraries
#include <Trade\Trade.mqh>
#include "DivergenceUtils.mqh"

//--- Input parameters
input string   _DivSettings         = "------ Divergence (RSI) ------";
input int      RSI_Period           = 14;            // RSI Period
input int      Swing_Radius         = 3;             // Swing lookaround strength
input int      Lookback_Bars        = 60;            // Max bars to look back for swings
input int      MinDivPips           = 10;            // Min price distance between swings

input string   _BiasSettings        = "------ Trend Bias ------";
input int      EMA_Trend            = 200;           // Trend Baseline
input ENUM_TIMEFRAMES Bias_TF       = PERIOD_D1;     // Bias Timeframe

input string   _RiskSettings        = "------ Risk & Trade ------";
input double   RiskPercent          = 1.0;           // Risk % per trade
input int      TP_Ratio             = 2;             // Risk-Reward
input int      MaxSpread            = 25;            // Max Allowed Spread
input int      MagicNumber          = 100014;        // EA Magic Number

//--- Global variables
CTrade         trade;
int            rsi_handle, ema_handle;
int            vol_precision = 0;
datetime       last_bar_time = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   rsi_handle = iRSI(_Symbol, _Period, RSI_Period, PRICE_CLOSE);
   ema_handle = iMA(_Symbol, Bias_TF, EMA_Trend, 0, MODE_EMA, PRICE_CLOSE);
   
   if(rsi_handle == INVALID_HANDLE || ema_handle == INVALID_HANDLE) return(INIT_FAILED);
   
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
   IndicatorRelease(rsi_handle);
   IndicatorRelease(ema_handle);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Strategy Logic on New Bar
   datetime current_bar_time = iTime(_Symbol, _Period, 0);
   if(current_bar_time == last_bar_time) return;
   last_bar_time = current_bar_time;

   if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > MaxSpread) return;
   if(HasOpenPosition()) return;

   // 1. Check Institutional Bias
   int bias = GetBias();
   if(bias == 0) return;

   // 2. Identify Potential Hidden Divergence
   CheckForHiddenDivergence(bias);
}

//+------------------------------------------------------------------+
//| Bias Logic                                                       |
//+------------------------------------------------------------------+
int GetBias()
{
   double ema[];
   if(CopyBuffer(ema_handle, 0, 0, 1, ema) <= 0) return 0;
   
   MqlRates rates[];
   if(CopyRates(_Symbol, Bias_TF, 0, 1, rates) <= 0) return 0;
   
   if(rates[0].close > ema[0]) return 1;  // Bullish
   if(rates[0].close < ema[0]) return -1; // Bearish
   return 0;
}

//+------------------------------------------------------------------+
//| Divergence Calculation and Entry                                 |
//+------------------------------------------------------------------+
void CheckForHiddenDivergence(int bias)
{
   int s1, s2; // Indices of most recent (s1) and previous (s2) swings

   // --- CASE A: Bullish Bias, Look for Hidden Bullish Div ---
   if(bias == 1) 
   {
      if(CDivergenceUtils::FindSwingLows(Swing_Radius, Lookback_Bars, s1, s2))
      {
         // Confirmed Swing Low within valid window
         if(s1 <= Swing_Radius + 3)
         {
            double p1 = iLow(_Symbol, _Period, s1);
            double p2 = iLow(_Symbol, _Period, s2);
            
            // Distance Filter
            if(MathAbs(p1 - p2) < MinDivPips * _Point * (SymbolInfoInteger(_Symbol, SYMBOL_DIGITS) == 3 || SymbolInfoInteger(_Symbol, SYMBOL_DIGITS) == 5 ? 10 : 1)) return;

            double r1 = CDivergenceUtils::GetRSIAt(rsi_handle, s1);
            double r2 = CDivergenceUtils::GetRSIAt(rsi_handle, s2);
            
            // Hidden Bullish: Price HL (p1 > p2) but RSI LL (r1 < r2)
            if(p1 > p2 && r1 < r2 && r1 != -1)
            {
               ExecuteTrade(ORDER_TYPE_BUY, p1);
            }
         }
      }
   }
   // --- CASE B: Bearish Bias, Look for Hidden Bearish Div ---
   else if(bias == -1)
   {
      if(CDivergenceUtils::FindSwingHighs(Swing_Radius, Lookback_Bars, s1, s2))
      {
         if(s1 <= Swing_Radius + 3)
         {
            double p1 = iHigh(_Symbol, _Period, s1);
            double p2 = iHigh(_Symbol, _Period, s2);
            
            // Distance Filter
            if(MathAbs(p1 - p2) < MinDivPips * _Point * (SymbolInfoInteger(_Symbol, SYMBOL_DIGITS) == 3 || SymbolInfoInteger(_Symbol, SYMBOL_DIGITS) == 5 ? 10 : 1)) return;

            double r1 = CDivergenceUtils::GetRSIAt(rsi_handle, s1);
            double r2 = CDivergenceUtils::GetRSIAt(rsi_handle, s2);
            
            // Hidden Bearish: Price LH (p1 < p2) but RSI HH (r1 > r2)
            if(p1 < p2 && r1 > r2 && r1 != -1)
            {
               ExecuteTrade(ORDER_TYPE_SELL, p1);
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Execution Engine                                                 |
//+------------------------------------------------------------------+
void ExecuteTrade(ENUM_ORDER_TYPE type, double sl_extreme)
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double tick_sz = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   if(type == ORDER_TYPE_BUY) {
      double sl = NormalizePrice(sl_extreme - (2 * _Point), tick_sz);
      sl = ValidateStopsLevel(ask, sl);
      double risk_dist = ask - sl;
      if(risk_dist <= 0) return;
      double tp = NormalizePrice(ask + (risk_dist * TP_Ratio), tick_sz);
      tp = ValidateStopsLevel(ask, tp);
      double lot = CalculateLotSize(risk_dist);
      trade.Buy(lot, _Symbol, ask, sl, tp, "Hidden Div Long");
   }
   else {
      double sl = NormalizePrice(sl_extreme + (2 * _Point), tick_sz);
      sl = ValidateStopsLevel(bid, sl);
      double risk_dist = sl - bid;
      if(risk_dist <= 0) return;
      double tp = NormalizePrice(bid - (risk_dist * TP_Ratio), tick_sz);
      tp = ValidateStopsLevel(bid, tp);
      double lot = CalculateLotSize(risk_dist);
      trade.Sell(lot, _Symbol, bid, sl, tp, "Hidden Div Short");
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

double NormalizePrice(double p, double t) { return MathRound(p / t) * t; }
