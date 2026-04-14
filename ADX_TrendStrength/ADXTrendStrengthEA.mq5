//+------------------------------------------------------------------+
//|                                         ADXTrendStrengthEA.mq5 |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK. VERSION 1.00 (Regime Filter Based)        |
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
#include "ADXUtils.mqh"

//--- Input parameters
input string   _ADX_Settings        = "------ ADX Regime ------";
input int      ADX_Period           = 14;            // ADX Period
input double   ADX_Threshold        = 25.0;          // Min Strength to enter
input bool     RequireRisingADX     = true;          // Must be accelerating

input string   _Direction_Settings = "------ Direction ------";
input int      EMA_Trend            = 200;           // Trend Baseline
input int      DI_Filter_Period     = 14;            // DMI Period

input string   _Risk_Settings        = "------ Risk & Trade ------";
input double   RiskPercent          = 1.0;           // Risk % per trade
input double   ATR_Multiplier       = 1.5;           // Stop Loss ATR Multiplier
input double   RR_Target            = 2.5;           // Fixed RR Goal
input bool     UseExhaustionExit    = true;          // Exit if Trend Fades
input int      MaxSpread            = 30;            // Max Allowed Spread
input int      MagicNumber          = 100015;        // EA Magic Number

//--- Global variables
CTrade         trade;
int            adx_handle, ema_handle, atr_handle;
int            vol_precision = 0;
datetime       last_bar_time = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   adx_handle = iADX(_Symbol, _Period, ADX_Period);
   ema_handle = iMA(_Symbol, _Period, EMA_Trend, 0, MODE_EMA, PRICE_CLOSE);
   atr_handle = iATR(_Symbol, _Period, 14);
   
   if(adx_handle == INVALID_HANDLE || ema_handle == INVALID_HANDLE || atr_handle == INVALID_HANDLE) 
      return(INIT_FAILED);
   
   vol_precision = CArgusCore::GetVolumePrecision(_Symbol);
   
   trade.SetExpertMagicNumber(MagicNumber);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(adx_handle);
   IndicatorRelease(ema_handle);
   IndicatorRelease(atr_handle);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   if(CArgusCore::IsHalted()) return;

   // 1. Manage Active Trades (Exhaustion Logic)
   if(UseExhaustionExit && PositionSelectByMagic(MagicNumber)) {
      if(CADXUtils::IsFalling(adx_handle, 2)) {
         for(int i = PositionsTotal() - 1; i >= 0; i--) {
            ulong ticket = PositionGetTicket(i);
            if(PositionSelectByTicket(ticket) && PositionGetInteger(POSITION_MAGIC) == MagicNumber && PositionGetString(POSITION_SYMBOL) == _Symbol) {
               trade.PositionClose(ticket, -1);
            }
         }
      }
   }

   // 2. Signal Check on New Bar
   datetime current_bar_time = iTime(_Symbol, _Period, 0);
   if(current_bar_time == last_bar_time) return;
   last_bar_time = current_bar_time;

   if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > MaxSpread) return;
   if(CArgusCore::HasOpenPosition(_Symbol, MagicNumber)) return;

   // 3. Regime Check: ADX Strength
   double adx_main[];
   if(CopyBuffer(adx_handle, 0, 1, 1, adx_main) <= 0) return;
   
   if(adx_main[0] < ADX_Threshold) return; // Trend too weak
   if(RequireRisingADX && !CADXUtils::IsRising(adx_handle, 1)) return; // Fading momentum

   // 4. Direction Check: DMI + EMA
   double plus_di[], minus_di[], ema[];
   if(CopyBuffer(adx_handle, 1, 1, 1, plus_di) <= 0) return;
   if(CopyBuffer(adx_handle, 2, 1, 1, minus_di) <= 0) return;
   if(CopyBuffer(ema_handle, 0, 1, 1, ema) <= 0) return;
   
   double close1 = iClose(_Symbol, _Period, 1);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   // Buy Setup
   if(close1 > ema[0] && plus_di[0] > minus_di[0])
   {
      ExecuteTrade(ORDER_TYPE_BUY);
   }
   // Sell Setup
   else if(close1 < ema[0] && minus_di[0] > plus_di[0])
   {
      ExecuteTrade(ORDER_TYPE_SELL);
   }
}

//+------------------------------------------------------------------+
//| Execution Engine                                                 |
//+------------------------------------------------------------------+
void ExecuteTrade(ENUM_ORDER_TYPE type)
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double tick_sz = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   double sl_dist = CADXUtils::GetATRDistance(atr_handle, ATR_Multiplier);
   if(sl_dist <= 0) return;

   if(type == ORDER_TYPE_BUY) {
      double sl = CArgusCore::NormalizePrice(_Symbol, ask - sl_dist, tick_sz);
      sl = CArgusCore::ValidateStopsLevel(_Symbol, ask, sl);
      double risk_dist = ask - sl;
      if(risk_dist <= 0) return;
      
      double tp = CArgusCore::NormalizePrice(_Symbol, ask + (risk_dist * RR_Target), tick_sz);
      tp = CArgusCore::ValidateStopsLevel(_Symbol, ask, tp);
      
      double lot = CArgusCore::CalculateLotSize(_Symbol, RiskPercent, risk_dist, vol_precision);
      trade.Buy(lot, _Symbol, ask, sl, tp, "ADX Strong Trend Long");
   }
   else {
      double sl = CArgusCore::NormalizePrice(_Symbol, bid + sl_dist, tick_sz);
      sl = CArgusCore::ValidateStopsLevel(_Symbol, bid, sl);
      double risk_dist = sl - bid;
      if(risk_dist <= 0) return;
      
      double tp = CArgusCore::NormalizePrice(_Symbol, bid - (risk_dist * RR_Target), tick_sz);
      tp = CArgusCore::ValidateStopsLevel(_Symbol, bid, tp);
      
      double lot = CArgusCore::CalculateLotSize(_Symbol, RiskPercent, risk_dist, vol_precision);
      trade.Sell(lot, _Symbol, bid, sl, tp, "ADX Strong Trend Short");
   }
}

//+------------------------------------------------------------------+
//| Utilities                                                        |

bool PositionSelectByMagic(long magic) {
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong t = PositionGetTicket(i);
      if(PositionSelectByTicket(t) && PositionGetInteger(POSITION_MAGIC) == magic && PositionGetString(POSITION_SYMBOL) == _Symbol) return true;
   }
   return false;
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
   m.name = "ADX TrendStrength";
   m.category = "Trend Following";
   m.magic_number = MagicNumber;
   m.regime_mask = REGIME_TREND | REGIME_EXPANSION;
   m.session_mask = SESSION_ALL;
   m.requires_trend = true;
   m.hates_high_volatility = false;
   m.target_style = "Fixed RR";
   return m;
}
