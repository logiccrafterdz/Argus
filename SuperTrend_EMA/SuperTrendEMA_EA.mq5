//+------------------------------------------------------------------+
//|                                           SuperTrendEMA_EA.mq5 |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK. VERSION 1.00 (Volatility Adaptive Sniper) |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property version   "1.00"
#property strict

//--- Include necessary libraries
#include <Trade\Trade.mqh>
#include "..\Shared\ArgusCore.mqh"
#include "..\Shared\ArgusStructure.mqh"
#include "SuperTrendUtils.mqh"

//--- Input parameters
input string   _ST_Settings         = "------ SuperTrend ------";
input int      ST_Period            = 10;            // ATR Period
input double   ST_Multiplier        = 3.0;           // ATR Multiplier
input int      ST_Warmup            = 50;            // Bars for state warmup

input string   _EMA_Settings        = "------ EMA Confluence ------";
input int      EMA_Trend            = 200;           // Trend Filter

input string   _Chop_Settings       = "------ Regime Logic ------";
input bool     UseChopFilter        = true;          // Enable ATR Filter
input double   ATR_ThresholdMult    = 0.8;           // ATR > SMA(ATR)*X

input string   _Risk_Settings        = "------ Risk & Trade ------";
input double   RiskPercent          = 1.0;           // Risk % per trade
input bool     UseTrailing          = true;          // Trail SL with ST Line
input int      MagicNumber          = 100013;        // EA Magic Number

//--- Global variables
CTrade         trade;
int            ema_handle, atr_handle;
int            vol_precision = 0;
datetime       last_bar_time = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   ema_handle = iMA(_Symbol, _Period, EMA_Trend, 0, MODE_EMA, PRICE_CLOSE);
   atr_handle = iATR(_Symbol, _Period, ST_Period);
   
   if(ema_handle == INVALID_HANDLE || atr_handle == INVALID_HANDLE) return(INIT_FAILED);
   
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
   IndicatorRelease(atr_handle);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   if(CArgusCore::IsHalted()) return;

   // Manage Trailing Stop on every tick (if active)
   if(UseTrailing && PositionSelectByMagic(MagicNumber)) {
      HandleTrailingStop();
   }

   // Strategy Logic on New Bar
   datetime current_bar_time = iTime(_Symbol, _Period, 0);
   if(current_bar_time == last_bar_time) return;
   last_bar_time = current_bar_time;

   if(CArgusCore::HasOpenPosition(_Symbol, MagicNumber)) return;

   // 1. Check EMA Bias
   double ema[];
   if(CopyBuffer(ema_handle, 0, 1, 1, ema) <= 0) return;
   double close1 = iClose(_Symbol, _Period, 1);
   bool bias_long = (close1 > ema[0]);
   bool bias_short = (close1 < ema[0]);

   // 2. Identify SuperTrend State & Flip
   double st_val1, st_val2;
   int trend1 = GetSuperTrendState(1, st_val1);
   int trend2 = GetSuperTrendState(2, st_val2);

   // 3. Volatility Filter
   if(UseChopFilter && !CSuperTrendUtils::IsVolatilityHealthy(ST_Period, ATR_ThresholdMult)) return;

   // 4. Signal Detection
   // Long: Flip from Red to Green while above EMA 200
   if(trend2 == -1 && trend1 == 1 && bias_long) {
      ExecuteTrade(ORDER_TYPE_BUY, st_val1);
   }
   // Short: Flip from Green to Red while below EMA 200
   else if(trend2 == 1 && trend1 == -1 && bias_short) {
      ExecuteTrade(ORDER_TYPE_SELL, st_val1);
   }
}

//+------------------------------------------------------------------+
//| Recursive SuperTrend Calculation for state detection             |
//+------------------------------------------------------------------+
int GetSuperTrendState(int bar_idx, double &value)
{
   double upper = 0, lower = 0;
   int trend = 0;
   
   // Initialize state from a safe lookback
   int start_idx = bar_idx + ST_Warmup; 
   for(int i = start_idx; i >= bar_idx; i--) {
      trend = CSuperTrendUtils::Calculate(i, ST_Period, ST_Multiplier, value, upper, lower, trend);
   }
   return trend;
}

//+------------------------------------------------------------------+
//| Trailing Stop Logic                                              |
//+------------------------------------------------------------------+
void HandleTrailingStop()
{
   if(!PositionSelectByMagic(MagicNumber)) return;
   
   double st_val;
   int trend = GetSuperTrendState(1, st_val);
   long ticket = PositionGetInteger(POSITION_TICKET);
   double current_sl = PositionGetDouble(POSITION_SL);
   ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

   if(type == POSITION_TYPE_BUY && trend == 1) {
      if(st_val > current_sl + _Point) {
         trade.PositionModify(ticket, CArgusCore::NormalizePrice(_Symbol, st_val, _Point), 0);
      }
   }
   else if(type == POSITION_TYPE_SELL && trend == -1) {
      if(st_val < current_sl - _Point) {
         trade.PositionModify(ticket, CArgusCore::NormalizePrice(_Symbol, st_val, _Point), 0);
      }
   }
}

//+------------------------------------------------------------------+
//| Execution Engine                                                 |
//+------------------------------------------------------------------+
void ExecuteTrade(ENUM_ORDER_TYPE type, double sl_start)
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double tick_sz = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   if(type == ORDER_TYPE_BUY) {
      double sl = CArgusCore::NormalizePrice(_Symbol, sl_start - (5 * _Point), tick_sz);
      sl = CArgusCore::ValidateStopsLevel(_Symbol, ask, sl);
      double risk_dist = ask - sl;
      if(risk_dist <= 0) return;
      double lot = CArgusCore::CalculateLotSize(_Symbol, RiskPercent, risk_dist, vol_precision);
      trade.Buy(lot, _Symbol, ask, sl, 0, "SuperTrend Breakout Long");
   }
   else {
      double sl = CArgusCore::NormalizePrice(_Symbol, sl_start + (5 * _Point), tick_sz);
      sl = CArgusCore::ValidateStopsLevel(_Symbol, bid, sl);
      double risk_dist = sl - bid;
      if(risk_dist <= 0) return;
      double lot = CArgusCore::CalculateLotSize(_Symbol, RiskPercent, risk_dist, vol_precision);
      trade.Sell(lot, _Symbol, bid, sl, 0, "SuperTrend Breakout Short");
   }
}

//+------------------------------------------------------------------+
//| Support Utilities                                                |

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
