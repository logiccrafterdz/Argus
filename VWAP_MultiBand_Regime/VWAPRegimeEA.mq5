//+------------------------------------------------------------------+
//|                                           VWAPRegimeEA.mq5       |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK. VERSION 1.00 (Regime-Aware VWAP)          |
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
#include "VWAPUtils.mqh"

//--- Input parameters
enum ENUM_SL_TYPE {
   SL_FIXED_PIPS,    // Fixed Pips from Entry
   SL_ATR_MULT       // ATR Multiplier (Dynamic)
};

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
input ENUM_SL_TYPE SL_Mode          = SL_ATR_MULT;   // Stop Loss Mode
input double   SL_FixedPips         = 15.0;          // SL Pips (if Fixed)
input double   SL_AtrMultiplier     = 1.5;           // SL ATR Mult (if ATR)
input int      MaxTradesPerDay      = 2;             // Max Trades Per Day
input int      MaxSpread            = 30;            // Max Allowed Spread (Points)
input int      MagicNumber          = 100007;        // EA Magic Number

//--- Global variables
CTrade         trade;
int            atr_handle;
int            vol_precision = 0;
datetime       last_bar_time = 0;
int            trades_today = 0;
datetime       today_reset = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   atr_handle = iATR(_Symbol, _Period, AtrPeriod);
   if(atr_handle == INVALID_HANDLE) return(INIT_FAILED);
   
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


   // Execute logic on New Bar only (conservative mean reversion)
   datetime current_bar_time = iTime(_Symbol, _Period, 0);
   if(current_bar_time == last_bar_time) return;
   last_bar_time = current_bar_time;

   if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > MaxSpread) return;
   if(CArgusCore::HasOpenPosition(_Symbol, MagicNumber)) return;

   // 1. Daily Trade Limit Logic
   datetime current_day = iTime(_Symbol, PERIOD_D1, 0);
   if(current_day > today_reset) {
      today_reset = current_day;
      trades_today = 0;
   }
   if(trades_today >= MaxTradesPerDay) return;

   // 2. Determine Market Regime
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
   
   // Calculate Dynamic SL
   double sl_dist = 0;
   if(SL_Mode == SL_FIXED_PIPS) {
      sl_dist = SL_FixedPips * PipsToPointsMultiplier();
   } else {
      double atr[];
      if(CopyBuffer(atr_handle, 0, 0, 1, atr) > 0) {
         sl_dist = atr[0] * SL_AtrMultiplier;
      }
   }

   if(type == ORDER_TYPE_BUY) {
      double sl = CArgusCore::NormalizePrice(_Symbol, ask - sl_dist, tick_size); 
      sl = CArgusCore::ValidateStopsLevel(_Symbol, ask, sl);
      double risk_dist = ask - sl;
      if(risk_dist <= 0) return;
      
      double tp = CArgusCore::NormalizePrice(_Symbol, target_vwap, tick_size);
      tp = CArgusCore::ValidateStopsLevel(_Symbol, ask, tp);
      
      double lot = CArgusCore::CalculateLotSize(_Symbol, RiskPercent, risk_dist, vol_precision);
      if(SendTrade(ORDER_TYPE_BUY, lot, ask, sl, tp, comment)) trades_today++;
   }
   else {
      double sl = CArgusCore::NormalizePrice(_Symbol, bid + sl_dist, tick_size);
      sl = CArgusCore::ValidateStopsLevel(_Symbol, bid, sl);
      double risk_dist = sl - bid;
      if(risk_dist <= 0) return;
      
      double tp = CArgusCore::NormalizePrice(_Symbol, target_vwap, tick_size);
      tp = CArgusCore::ValidateStopsLevel(_Symbol, bid, tp);
      
      double lot = CArgusCore::CalculateLotSize(_Symbol, RiskPercent, risk_dist, vol_precision);
      if(SendTrade(ORDER_TYPE_SELL, lot, bid, sl, tp, comment)) trades_today++;
   }
}

bool SendTrade(ENUM_ORDER_TYPE type, double lot, double price, double sl, double tp, string comment)
{
   bool s = (type == ORDER_TYPE_BUY) ? trade.Buy(lot, _Symbol, price, sl, tp, comment) : trade.Sell(lot, _Symbol, price, sl, tp, comment);
   if(!s) {
      PrintFormat("Trade Error: %d (%s)", trade.ResultRetcode(), trade.ResultRetcodeDescription());
      return false;
   }
   
   PrintFormat("Trade Success: %s | Lot: %.*f | TP: %.5f", comment, vol_precision, lot, tp);
   return true;
}

//+------------------------------------------------------------------+
//| Utilities                                                        |

double PipsToPointsMultiplier() { int d = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS); return (d == 3 || d == 5) ? 10.0 * _Point : _Point; }

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
   m.name = "VWAP MultiBand Regime";
   m.category = "Mean Reversion";
   m.magic_number = MagicNumber;
   m.regime_mask = REGIME_RANGE;
   m.session_mask = SESSION_ALL;
   m.requires_trend = false;
   m.hates_high_volatility = true;
   m.target_style = "VWAP Mean";
   return m;
}
