//+------------------------------------------------------------------+
//|                                           SR_BreakoutEA.mq5      |
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
#include "..\Shared\ArgusManifest.mqh"
//--- Enums
enum ENUM_STATE {
   STATE_IDLE,
   STATE_WAIT_RETEST
};

enum ENUM_SIGNAL {
   SIGNAL_NONE,
   SIGNAL_BUY,
   SIGNAL_SELL
};

//--- Input parameters
input ENUM_TIMEFRAMES HTF_Timeframe = PERIOD_H4;     // Trend Timeframe
input int      HTF_EMA_Period        = 200;           // HTF Trend Filter Period
input int      SR_Lookback          = 50;            // Bars to look for S/R
input int      SR_Radius            = 10;            // Radius for Swing detection
input int      MaxWaitBars          = 10;            // Max bars to wait for retest
input int      MaxBreakDistancePips = 30;            // Max pips price can go after break
input int      MaxSpread            = 30;            // Max Allowed Spread (Points)
input double   RiskPercent          = 1.0;           // Risk % per Trade
input int      TP_Multiplier        = 2;             // Risk-Reward Multiplier
input int      MagicNumber          = 100002;        // EA Magic Number
input bool     OnlyNewBar           = true;          // Execute on New Bar Only

//--- Global variables
CTrade         trade;
int            htf_ema_handle;
int            vol_precision = 0;
datetime       last_bar_time = 0;

//--- State tracking
ENUM_STATE     current_state = STATE_IDLE;
ENUM_SIGNAL    intended_signal = SIGNAL_NONE;
double         active_level = 0;
double         max_deviation_pips = 0;
int            break_bar_index = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   htf_ema_handle = iMA(_Symbol, HTF_Timeframe, HTF_EMA_Period, 0, MODE_EMA, PRICE_CLOSE);
   
   if(htf_ema_handle == INVALID_HANDLE)
   {
      Print("Error: Failed to create HTF EMA handle.");
      return(INIT_FAILED);
   }
   
   vol_precision = CArgusCore::GetVolumePrecision(_Symbol);
   
   trade.SetExpertMagicNumber(MagicNumber);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(htf_ema_handle);
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


   if(OnlyNewBar) {
      datetime current_bar_time = iTime(_Symbol, _Period, 0);
      if(current_bar_time == last_bar_time) return;
      last_bar_time = current_bar_time;
   }

   if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > MaxSpread) return;
   if(CArgusCore::HasOpenPosition(_Symbol, MagicNumber)) { ResetState(); return; }

   double htf_ema_buffer[];
   ArraySetAsSeries(htf_ema_buffer, true);
   if(CopyBuffer(htf_ema_handle, 0, 0, 2, htf_ema_buffer) < 2) return;
   
   double htf_close = iClose(_Symbol, HTF_Timeframe, 1);
   bool is_bullish_bias = (htf_close > htf_ema_buffer[1]);
   bool is_bearish_bias = (htf_close < htf_ema_buffer[1]);

   if(current_state == STATE_IDLE) {
      IdentifyBreakout(is_bullish_bias, is_bearish_bias);
   }
   else if(current_state == STATE_WAIT_RETEST) {
      MonitorRetest();
   }
}

void IdentifyBreakout(bool bull_bias, bool bear_bias)
{
   if(!bull_bias && !bear_bias) return;
   
   double last_close = iClose(_Symbol, _Period, 1);
   double prev_close = iClose(_Symbol, _Period, 2);

   if(bull_bias) {
      double res = CStructureUtils::GetRecentSwingHigh(SR_Lookback, SR_Radius);
      if(res > 0 && prev_close <= res && last_close > res) {
         current_state = STATE_WAIT_RETEST;
         intended_signal = SIGNAL_BUY;
         active_level = res;
         break_bar_index = 0;
         max_deviation_pips = 0;
         PrintFormat("Breakout Detected: Resistance at %.5f. Waiting for Retest.", active_level);
      }
   }
   else if(bear_bias) {
      double sup = CStructureUtils::GetRecentSwingLow(SR_Lookback, SR_Radius);
      if(sup > 0 && prev_close >= sup && last_close < sup) {
         current_state = STATE_WAIT_RETEST;
         intended_signal = SIGNAL_SELL;
         active_level = sup;
         break_bar_index = 0;
         max_deviation_pips = 0;
         PrintFormat("Breakout Detected: Support at %.5f. Waiting for Retest.", active_level);
      }
   }
}

void MonitorRetest()
{
   break_bar_index++;
   
   if(break_bar_index > MaxWaitBars) {
      Print("Retest timeout: MaxWaitBars reached. Resetting.");
      ResetState();
      return;
   }

   double last_close = iClose(_Symbol, _Period, 1);
   double last_low = iLow(_Symbol, _Period, 1);
   double last_high = iHigh(_Symbol, _Period, 1);
   double prev_high = iHigh(_Symbol, _Period, 2);
   double prev_low = iLow(_Symbol, _Period, 2);
   
   // Track Maximum Deviation since breakout
   double current_deviation = MathAbs(last_close - active_level) / CArgusCore::PipsToPriceDelta(_Symbol, 1);
   if(current_deviation > max_deviation_pips) max_deviation_pips = current_deviation;

   if(max_deviation_pips > MaxBreakDistancePips) {
      PrintFormat("Price escaped too far (Max: %.1f pips). Level considered 'tired'. Resetting.", max_deviation_pips);
      ResetState();
      return;
   }

   if(intended_signal == SIGNAL_BUY) {
      bool touch = (last_low <= active_level);
      bool confirm = (last_close > prev_high);
      
      if(touch && confirm) {
         OpenPosition(ORDER_TYPE_BUY);
         ResetState();
      }
   }
   else if(intended_signal == SIGNAL_SELL) {
      bool touch = (last_high >= active_level);
      bool confirm = (last_close < prev_low);
      
      if(touch && confirm) {
         OpenPosition(ORDER_TYPE_SELL);
         ResetState();
      }
   }
}

void OpenPosition(ENUM_ORDER_TYPE type)
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double last_high = iHigh(_Symbol, _Period, 1);
   double last_low = iLow(_Symbol, _Period, 1);

   if(type == ORDER_TYPE_BUY) {
      double sl = CArgusCore::NormalizePrice(_Symbol, last_low - CArgusCore::PipsToPriceDelta(_Symbol, 5), tick_size);
      sl = CArgusCore::ValidateStopsLevel(_Symbol, ask, sl);
      double risk_dist = ask - sl;
      if(risk_dist <= 0) return;
      
      double tp = CArgusCore::NormalizePrice(_Symbol, ask + (risk_dist * TP_Multiplier), tick_size);
      tp = CArgusCore::ValidateStopsLevel(_Symbol, ask, tp);
      
      double lot = CArgusCore::CalculateLotSize(_Symbol, RiskPercent, risk_dist, vol_precision);
      ExecuteTrade(ORDER_TYPE_BUY, lot, ask, sl, tp, "Gold SR Breakout Buy");
   }
   else {
      double sl = CArgusCore::NormalizePrice(_Symbol, last_high + CArgusCore::PipsToPriceDelta(_Symbol, 5), tick_size);
      sl = CArgusCore::ValidateStopsLevel(_Symbol, bid, sl);
      double risk_dist = sl - bid;
      if(risk_dist <= 0) return;
      
      double tp = CArgusCore::NormalizePrice(_Symbol, bid - (risk_dist * TP_Multiplier), tick_size);
      tp = CArgusCore::ValidateStopsLevel(_Symbol, bid, tp);
      
      double lot = CArgusCore::CalculateLotSize(_Symbol, RiskPercent, risk_dist, vol_precision);
      ExecuteTrade(ORDER_TYPE_SELL, lot, bid, sl, tp, "Gold SR Breakout Sell");
   }
}

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

void ResetState() { current_state = STATE_IDLE; intended_signal = SIGNAL_NONE; active_level = 0; break_bar_index = 0; max_deviation_pips = 0; }


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
   m.name = "SR Breakout Retest";
   m.category = "Breakout";
   m.magic_number = MagicNumber;
   m.regime_mask = REGIME_EXPANSION | REGIME_TREND;
   m.session_mask = SESSION_ALL;
   m.requires_trend = false;
   m.hates_high_volatility = false;
   m.target_style = "Next SR Level";
   return m;
}
