//+------------------------------------------------------------------+
//|                                           LiquiditySweepEA.mq5   |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK. VERSION 1.00 (Sniper Liquidity Design)    |
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
//--- Enums
enum ENUM_CONFIRMATION_TYPE {
   CONFIRM_CANDLE_BREAK, // Close beyond Sweep Candle High/Low
   CONFIRM_MSB           // Market Structure Break (Higher/Lower Close)
};

//--- Input parameters
input string   _StrategySettings    = "------ Strategy Settings ------";
input int      LookbackBars         = 100;           // Bars to scan for liquidity
input int      SwingRadius          = 5;             // Radius for swing detection
input double   EqualThresholdPips   = 3.0;           // Max pips between EQH/EQL
input ENUM_CONFIRMATION_TYPE ConfType = CONFIRM_CANDLE_BREAK; // Confirmation Mode
input bool     UseTrendFilter       = true;          // Filter by EMA 200
input int      TrendEMA             = 200;           // Trend Filter Period

input string   _RiskSettings        = "------ Risk Settings ------";
input double   RiskPercent          = 1.0;           // Risk % per trade
input double   FixedRR              = 2.0;           // Reward:Risk Ratio
input int      MaxSpread            = 30;            // Max allowed spread (Points)
input int      MagicNumber          = 100006;        // EA Magic Number

//--- Global variables
CTrade         trade;
int            ema_handle;
int            vol_precision = 0;
datetime       last_bar_time = 0;

// Pending state tracking
bool           pending_buy = false;
bool           pending_sell = false;
double         sweep_high = 0;
double         sweep_low = 0;
datetime       sweep_bar_time = 0;
double         liquidity_level = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   ema_handle = iMA(_Symbol, _Period, TrendEMA, 0, MODE_EMA, PRICE_CLOSE);
   if(ema_handle == INVALID_HANDLE) return(INIT_FAILED);
   
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
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   if(CArgusCore::IsHalted()) return;

   // Only execute logic on New Bar
   datetime current_bar_time = iTime(_Symbol, _Period, 0);
   if(current_bar_time == last_bar_time) return;
   last_bar_time = current_bar_time;

   if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > MaxSpread) return;
   if(CArgusCore::HasOpenPosition(_Symbol, MagicNumber)) {
      ResetPending();
      return;
   }

   // 1. Check for valid Sweep Pattern (Bar 1 is the completed sweep candidate)
   CheckForSweeps();

   // 2. Check for Confirmation to Enter
   CheckForConfirmation();
}

//+------------------------------------------------------------------+
//| Detect Sweep patterns                                            |
//+------------------------------------------------------------------+
void CheckForSweeps()
{
   // If we already have a pending setup, dont look for new sweeps until it expires or confirms
   if(pending_buy || pending_sell) return;

   // Scan for current Liquidity Zones
   double eqh = CArgusStructure::GetLiquidityHigh(_Symbol, _Period, LookbackBars, SwingRadius, EqualThresholdPips);
   double eql = CArgusStructure::GetLiquidityLow(_Symbol, _Period, LookbackBars, SwingRadius, EqualThresholdPips);

   double h1 = iHigh(_Symbol, _Period, 1);
   double l1 = iLow(_Symbol, _Period, 1);
   double c1 = iClose(_Symbol, _Period, 1);

   // Trend Filter
   bool trend_up = true, trend_dn = true;
   if(UseTrendFilter) {
      double ema[];
      ArraySetAsSeries(ema, true);
      if(CopyBuffer(ema_handle, 0, 0, 1, ema) > 0) {
         trend_up = (c1 > ema[0]);
         trend_dn = (c1 < ema[0]);
      }
   }

   // SELL SWEEP: High pierced EQH, but close is below EQH (index 1 is the sweep candle)
   if(eqh > 0 && h1 > eqh && c1 < eqh && trend_dn) {
      pending_sell = true;
      sweep_high = h1;
      sweep_low = l1;
      sweep_bar_time = iTime(_Symbol, _Period, 1);
      liquidity_level = eqh;
      Print("Strategy 6: High Liquidity Sweep detected (Candle 1). Waiting for confirmation...");
   }

   // BUY SWEEP: Low pierced EQL, but close is above EQL
   else if(eql > 0 && l1 < eql && c1 > eql && trend_up) {
      pending_buy = true;
      sweep_low = l1;
      sweep_high = h1;
      sweep_bar_time = iTime(_Symbol, _Period, 1);
      liquidity_level = eql;
      Print("Strategy 6: Low Liquidity Sweep detected (Candle 1). Waiting for confirmation...");
   }
}

//+------------------------------------------------------------------+
//| Check for breakout / MSB confirmation                            |
//+------------------------------------------------------------------+
void CheckForConfirmation()
{
   double c1 = iClose(_Symbol, _Period, 1);

   // -- SELL CONFIRMATION --
   if(pending_sell) {
      // Check if we are still on the sweep candle bar
      if(iTime(_Symbol, _Period, 1) == sweep_bar_time) {
         return; 
      }

      bool confirmed = false;
      if(ConfType == CONFIRM_CANDLE_BREAK) {
         confirmed = (c1 < sweep_low); 
      } else {
         confirmed = CArgusStructure::IsBearishMSB(_Symbol, _Period, LookbackBars, SwingRadius);
      }

      if(confirmed) {
         ExecuteTrade(ORDER_TYPE_SELL, sweep_high);
         ResetPending();
      }
      
      if(c1 > sweep_high) {
         PrintFormat("Strategy 6: Sweep Failed (Price broke high %.5f). Resetting.", sweep_high);
         ResetPending();
      }
   }

   // -- BUY CONFIRMATION --
   if(pending_buy) {
      if(iTime(_Symbol, _Period, 1) == sweep_bar_time) return;

      bool confirmed = false;
      if(ConfType == CONFIRM_CANDLE_BREAK) {
         confirmed = (c1 > sweep_high);
      } else {
         confirmed = CArgusStructure::IsBullishMSB(_Symbol, _Period, LookbackBars, SwingRadius);
      }

      if(confirmed) {
         ExecuteTrade(ORDER_TYPE_BUY, sweep_low);
         ResetPending();
      }

      if(c1 < sweep_low) {
         PrintFormat("Strategy 6: Sweep Failed (Price broke low %.5f). Resetting.", sweep_low);
         ResetPending();
      }
   }
}

//+------------------------------------------------------------------+
//| Trade Execution logic                                             |
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
      
      double tp = CArgusCore::NormalizePrice(_Symbol, ask + (risk_dist * FixedRR), tick_size);
      tp = CArgusCore::ValidateStopsLevel(_Symbol, ask, tp);
      
      double lot = CArgusCore::CalculateLotSize(_Symbol, RiskPercent, risk_dist, vol_precision);
      if(trade.Buy(lot, _Symbol, ask, sl, tp, "LS Sweep Buy")) {
         Print("Trade Success: LS Sweep Buy at ", ask);
      }
   }
   else {
      double sl = CArgusCore::NormalizePrice(_Symbol, sl_extreme + (5 * _Point), tick_size);
      sl = CArgusCore::ValidateStopsLevel(_Symbol, bid, sl);
      double risk_dist = sl - bid;
      if(risk_dist <= 0) return;
      
      double tp = CArgusCore::NormalizePrice(_Symbol, bid - (risk_dist * FixedRR), tick_size);
      tp = CArgusCore::ValidateStopsLevel(_Symbol, bid, tp);
      
      double lot = CArgusCore::CalculateLotSize(_Symbol, RiskPercent, risk_dist, vol_precision);
      if(trade.Sell(lot, _Symbol, bid, sl, tp, "LS Sweep Sell")) {
         Print("Trade Success: LS Sweep Sell at ", bid);
      }
   }
}

//+------------------------------------------------------------------+
//| Helper Utilities                                                 |
//+------------------------------------------------------------------+
void ResetPending() {
   pending_buy = false;
   pending_sell = false;
   sweep_high = 0;
   sweep_low = 0;
   sweep_bar_time = 0;
   liquidity_level = 0;
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
   m.name = "Liquidity Sweep Breakout";
   m.category = "Liquidity Hunting";
   m.magic_number = MagicNumber;
   m.regime_mask = REGIME_ALL;
   m.session_mask = SESSION_LONDON | SESSION_NY;
   m.requires_trend = false;
   m.hates_high_volatility = false;
   m.target_style = "Fixed RR";
   return m;
}
