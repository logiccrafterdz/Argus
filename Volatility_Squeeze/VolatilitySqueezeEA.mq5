//+------------------------------------------------------------------+
//|                                         VolatilitySqueezeEA.mq5 |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK. VERSION 1.00 (TTM-Expansion Sniper)       |
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
#include "VolatilityUtils.mqh"

//--- Input parameters
input string   _SqueezeSettings     = "------ Squeeze Engine ------";
input int      Squeeze_Period       = 20;            // Base Period (BB & KC)
input double   BB_StdDev            = 2.0;           // Bollinger StdDev
input double   KC_AtrMultiplier     = 1.5;           // Keltner ATR Mult
input int      MinSqueezeBars       = 5;             // Min bars to be in squeeze

input string   _ExpansionSettings   = "------ Expansion Trigger ------";
input double   ExpansionMult        = 1.5;           // Range/Body expansion factor
input int      Trend_EMA            = 100;           // Trend Filter Period

input string   _RiskSettings        = "------ Risk & Trade ------";
input double   RiskPercent          = 1.0;           // Risk % per trade
input int      TP_Ratio             = 2;             // Risk-Reward Ratio
input int      MaxSpread            = 30;            // Max Allowed Spread
input int      MagicNumber          = 100010;        // EA Magic Number

//--- Global variables
CTrade         trade;
int            bb_handle, ema_handle, atr_handle, trend_ema_handle;
int            vol_precision = 0;
datetime       last_bar_time = 0;

// Squeeze Tracking
bool           is_squeezed = false;
int            squeeze_counter = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   bb_handle = iBands(_Symbol, _Period, Squeeze_Period, 0, BB_StdDev, PRICE_CLOSE);
   ema_handle = iMA(_Symbol, _Period, Squeeze_Period, 0, MODE_EMA, PRICE_CLOSE);
   atr_handle = iATR(_Symbol, _Period, Squeeze_Period);
   trend_ema_handle = iMA(_Symbol, _Period, Trend_EMA, 0, MODE_EMA, PRICE_CLOSE);
   
   if(bb_handle == INVALID_HANDLE || ema_handle == INVALID_HANDLE || 
      atr_handle == INVALID_HANDLE || trend_ema_handle == INVALID_HANDLE) return(INIT_FAILED);
   
   vol_precision = CArgusCore::GetVolumePrecision(_Symbol);
   
   trade.SetExpertMagicNumber(MagicNumber);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(bb_handle);
   IndicatorRelease(ema_handle);
   IndicatorRelease(atr_handle);
   IndicatorRelease(trend_ema_handle);
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


   // Execute on New Bar
   datetime current_bar_time = iTime(_Symbol, _Period, 0);
   if(current_bar_time == last_bar_time) return;
   last_bar_time = current_bar_time;

   if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > MaxSpread) return;
   if(CArgusCore::HasOpenPosition(_Symbol, MagicNumber)) return;

   // 1. Monitor Squeeze State (on bar 1)
   UpdateSqueezeState();

   // 2. Detect Breakout from Squeeze
   if(is_squeezed) CheckForBreakout();
}

//+------------------------------------------------------------------+
//| Monitor TTM Squeeze state                                        |
//+------------------------------------------------------------------+
void UpdateSqueezeState()
{
   double bb_u[], bb_l[], kc_u, kc_l;
   if(CopyBuffer(bb_handle, 1, 1, 1, bb_u) <= 0) return;
   if(CopyBuffer(bb_handle, 2, 1, 1, bb_l) <= 0) return;
   if(!CVolatilityUtils::GetKeltnerBands(ema_handle, atr_handle, KC_AtrMultiplier, kc_u, kc_l)) return;

   // TTM Logic: BB inside KC
   if(bb_u[0] < kc_u && bb_l[0] > kc_l) {
      squeeze_counter++;
   } else {
      squeeze_counter = 0;
   }

   is_squeezed = (squeeze_counter >= MinSqueezeBars);
}

//+------------------------------------------------------------------+
//| Breakout and Expansion logic                                     |
//+------------------------------------------------------------------+
void CheckForBreakout()
{
   double c1 = iClose(_Symbol, _Period, 1);
   double o1 = iOpen(_Symbol, _Period, 1);
   double bb_u[], bb_l[];
   if(CopyBuffer(bb_handle, 1, 1, 1, bb_u) <= 0) return;
   if(CopyBuffer(bb_handle, 2, 1, 1, bb_l) <= 0) return;

   // Verify Expansion Momentum (using Utility)
   if(!CVolatilityUtils::IsExpansionCandle(1, Squeeze_Period, ExpansionMult)) return;

   // Trend Filter
   double trend_ema[];
   if(CopyBuffer(trend_ema_handle, 0, 1, 1, trend_ema) <= 0) return;
   bool trend_up = (c1 > trend_ema[0]);
   bool trend_dn = (c1 < trend_ema[0]);

   // Long Breakout
   if(c1 > bb_u[0] && o1 <= bb_u[0] && trend_up) {
      ExecuteTrade(ORDER_TYPE_BUY, iLow(_Symbol, _Period, 1));
   }
   // Short Breakout
   else if(c1 < bb_l[0] && o1 >= bb_l[0] && trend_dn) {
      ExecuteTrade(ORDER_TYPE_SELL, iHigh(_Symbol, _Period, 1));
   }
}

//+------------------------------------------------------------------+
//| Trade Execution                                                  |
//+------------------------------------------------------------------+
void ExecuteTrade(ENUM_ORDER_TYPE type, double sl_extreme)
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   if(type == ORDER_TYPE_BUY) {
      double sl = CArgusCore::NormalizePrice(_Symbol, sl_extreme - (5 * _Point), tick_size);
      sl = CArgusCore::ValidateStopsLevel(_Symbol, ask, sl);
      double risk_dist = ask - sl;
      if(risk_dist <= 0) return;
      
      double tp = CArgusCore::NormalizePrice(_Symbol, ask + (risk_dist * TP_Ratio), tick_size);
      tp = CArgusCore::ValidateStopsLevel(_Symbol, ask, tp);
      
      double lot = CArgusCore::CalculateLotSize(_Symbol, RiskPercent, risk_dist, vol_precision);
      if(trade.Buy(lot, _Symbol, ask, sl, tp, "Squeeze Breakout Long")) {
         squeeze_counter = 0;
         is_squeezed = false;
         Print("Breakout Success: Long confirmed with expansion. Resetting Squeeze.");
      }
   }
   else {
      double sl = CArgusCore::NormalizePrice(_Symbol, sl_extreme + (5 * _Point), tick_size);
      sl = CArgusCore::ValidateStopsLevel(_Symbol, bid, sl);
      double risk_dist = sl - bid;
      if(risk_dist <= 0) return;
      
      double tp = CArgusCore::NormalizePrice(_Symbol, bid - (risk_dist * TP_Ratio), tick_size);
      tp = CArgusCore::ValidateStopsLevel(_Symbol, bid, tp);
      
      double lot = CArgusCore::CalculateLotSize(_Symbol, RiskPercent, risk_dist, vol_precision);
      if(trade.Sell(lot, _Symbol, bid, sl, tp, "Squeeze Breakout Short")) {
         squeeze_counter = 0;
         is_squeezed = false;
         Print("Breakout Success: Short confirmed with expansion. Resetting Squeeze.");
      }
   }
}

//+------------------------------------------------------------------+
//| Support Utilities                                                |


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
   m.name = "Volatility Squeeze";
   m.category = "Breakout";
   m.magic_number = MagicNumber;
   m.regime_mask = REGIME_COMPRESSION;
   m.session_mask = SESSION_ALL;
   m.requires_trend = true;
   m.hates_high_volatility = false;
   m.target_style = "Measured Move";
   return m;
}
