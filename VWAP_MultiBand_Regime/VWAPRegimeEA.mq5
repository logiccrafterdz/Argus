//+------------------------------------------------------------------+
//|                                           VWAPRegimeEA.mq5       |
//|                                  Copyright 2026, Trading Studio |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK. VERSION 1.00 (Regime-Aware VWAP)          |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Trading Studio"
#property link      "https://example.com"
#property version   "1.00"
#property strict

//--- Include necessary libraries
#include <Trade\Trade.mqh>
#include "VWAPUtils.mqh"

//--- Input parameters
input string   _RegimeSettings      = "------ Regime Settings ------";
input double   AtrRatioThreshold    = 0.8;           // Balanced < x | Trending > y
input int      AtrPeriod            = 14;            // ATR base period

input string   _VWAPSettings        = "------ VWAP & Bands ------";
input double   BandMult             = 2.0;           // Standard Deviation Multiplier
input double   ConfDistPips         = 5.0;           // Multi-VWAP Confluence Dist (Pips)
input bool     UseWeeklyVWAP        = true;          // Use Weekly VWAP for confluence
input bool     UseMonthlyVWAP       = true;          // Use Monthly VWAP for confluence

input string   _RiskSettings        = "------ Risk Settings ------";
input double   RiskPercent          = 1.0;           // Risk % per trade
input int      MaxSpread            = 30;            // Max Allowed Spread (Points)
input int      MagicNumber          = 554433;        // Magic Number

//--- Global variables
CTrade         trade;
int            atr_handle;
int            vol_precision = 0;
datetime       last_bar_time = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   atr_handle = iATR(_Symbol, _Period, AtrPeriod);
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
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Execute logic on New Bar only (conservative mean reversion)
   datetime current_bar_time = iTime(_Symbol, _Period, 0);
   if(current_bar_time == last_bar_time) return;
   last_bar_time = current_bar_time;

   if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > MaxSpread) return;
   if(HasOpenPosition()) return;

   // 1. Determine Market Regime
   bool balanced = CVWAPUtils::IsBalancedRegime(atr_handle, AtrRatioThreshold);
   if(!balanced) {
      // Commenting out for cleaner logs, but we could add a "Trending - Skipping" print here
      return; 
   }

   // 2. Calculate Daily VWAP and Bands
   double d_std_dev = 0;
   double d_vwap = CVWAPUtils::GetVWAP(PERIOD_D1, 1, d_std_dev);
   if(d_vwap <= 0) return;

   double upper_band = d_vwap + (d_std_dev * BandMult);
   double lower_band = d_vwap - (d_std_dev * BandMult);

   // 3. Multi-VWAP Confluence Check
   double w_std = 0, m_std = 0;
   double w_vwap = UseWeeklyVWAP ? CVWAPUtils::GetVWAP(PERIOD_W1, 1, w_std) : 0;
   double m_vwap = UseMonthlyVWAP ? CVWAPUtils::GetVWAP(PERIOD_MN1, 1, m_std) : 0;

   // 4. Signal Logic
   double h1 = iHigh(_Symbol, _Period, 1);
   double l1 = iLow(_Symbol, _Period, 1);
   double c1 = iClose(_Symbol, _Period, 1);

   // -- SELL SIGNAL (Price reached upper band in balanced regime) --
   if(h1 >= upper_band && c1 < upper_band)
   {
      bool conf = (w_vwap > 0 && CVWAPUtils::IsConfluence(h1, w_vwap, ConfDistPips)) ||
                  (m_vwap > 0 && CVWAPUtils::IsConfluence(h1, m_vwap, ConfDistPips));
      
      string msg = conf ? "VWAP Rejection (Multi-VWAP Confluence)" : "VWAP Band Rejection";
      ExecuteVWAPTrade(ORDER_TYPE_SELL, upper_band, d_vwap, msg);
   }

   // -- BUY SIGNAL (Price reached lower band in balanced regime) --
   else if(l1 <= lower_band && c1 > lower_band)
   {
      bool conf = (w_vwap > 0 && CVWAPUtils::IsConfluence(l1, w_vwap, ConfDistPips)) ||
                  (m_vwap > 0 && CVWAPUtils::IsConfluence(l1, m_vwap, ConfDistPips));
      
      string msg = conf ? "VWAP Rejection (Multi-VWAP Confluence)" : "VWAP Band Rejection";
      ExecuteVWAPTrade(ORDER_TYPE_BUY, lower_band, d_vwap, msg);
   }
}

//+------------------------------------------------------------------+
//| Trade Execution Logic                                            |
//+------------------------------------------------------------------+
void ExecuteVWAPTrade(ENUM_ORDER_TYPE type, double entry_extreme, double target_vwap, string comment)
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   if(type == ORDER_TYPE_BUY) {
      double sl = NormalizePrice(entry_extreme - (10 * _Point), tick_size); 
      sl = ValidateStopsLevel(ask, sl);
      double risk_dist = ask - sl;
      if(risk_dist <= 0) return;
      
      double tp = NormalizePrice(target_vwap, tick_size);
      tp = ValidateStopsLevel(ask, tp);
      
      double lot = CalculateLotSize(risk_dist);
      SendTrade(ORDER_TYPE_BUY, lot, ask, sl, tp, comment);
   }
   else {
      double sl = NormalizePrice(entry_extreme + (10 * _Point), tick_size);
      sl = ValidateStopsLevel(bid, sl);
      double risk_dist = sl - bid;
      if(risk_dist <= 0) return;
      
      double tp = NormalizePrice(target_vwap, tick_size);
      tp = ValidateStopsLevel(bid, tp);
      
      double lot = CalculateLotSize(risk_dist);
      SendTrade(ORDER_TYPE_SELL, lot, bid, sl, tp, comment);
   }
}

void SendTrade(ENUM_ORDER_TYPE type, double lot, double price, double sl, double tp, string comment)
{
   bool s = (type == ORDER_TYPE_BUY) ? trade.Buy(lot, _Symbol, price, sl, tp, comment) : trade.Sell(lot, _Symbol, price, sl, tp, comment);
   if(!s) PrintFormat("Trade Error: %d (%s)", trade.ResultRetcode(), trade.ResultRetcodeDescription());
   else PrintFormat("Trade Success: %s | Lot: %.*f | TP: %.5f", comment, vol_precision, lot, tp);
}

//+------------------------------------------------------------------+
//| Utilities                                                        |
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
