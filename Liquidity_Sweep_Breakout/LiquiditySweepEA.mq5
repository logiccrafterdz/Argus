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
#include "StructureUtils.mqh"

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
input int      MagicNumber          = 662244;        // EA Magic Number

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
   IndicatorRelease(ema_handle);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Only execute logic on New Bar
   datetime current_bar_time = iTime(_Symbol, _Period, 0);
   if(current_bar_time == last_bar_time) return;
   last_bar_time = current_bar_time;

   if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > MaxSpread) return;
   if(HasOpenPosition()) {
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
   double eqh = CStructureUtils::GetLiquidityHigh(LookbackBars, SwingRadius, EqualThresholdPips);
   double eql = CStructureUtils::GetLiquidityLow(LookbackBars, SwingRadius, EqualThresholdPips);

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
         confirmed = CStructureUtils::IsBearishMSB(LookbackBars, SwingRadius);
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
         confirmed = CStructureUtils::IsBullishMSB(LookbackBars, SwingRadius);
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
      double sl = NormalizePrice(sl_extreme - (5 * _Point), tick_size);
      sl = ValidateStopsLevel(ask, sl);
      double risk_dist = ask - sl;
      if(risk_dist <= 0) return;
      
      double tp = NormalizePrice(ask + (risk_dist * FixedRR), tick_size);
      tp = ValidateStopsLevel(ask, tp);
      
      double lot = CalculateLotSize(risk_dist);
      if(trade.Buy(lot, _Symbol, ask, sl, tp, "LS Sweep Buy")) {
         Print("Trade Success: LS Sweep Buy at ", ask);
      }
   }
   else {
      double sl = NormalizePrice(sl_extreme + (5 * _Point), tick_size);
      sl = ValidateStopsLevel(bid, sl);
      double risk_dist = sl - bid;
      if(risk_dist <= 0) return;
      
      double tp = NormalizePrice(bid - (risk_dist * FixedRR), tick_size);
      tp = ValidateStopsLevel(bid, tp);
      
      double lot = CalculateLotSize(risk_dist);
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

double CalculateLotSize(double risk_dist) {
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double risk_amount = balance * (RiskPercent / 100.0);
   double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(risk_dist <= 0 || tick_value <= 0) return 0;
   double lot = risk_amount / (risk_dist / tick_size * tick_value);
   double min_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   lot = MathFloor(lot / step_lot) * step_lot;
   return NormalizeDouble(MathMax(min_lot, MathMin(max_lot, lot)), vol_precision);
}

double ValidateStopsLevel(double price, double target) {
   int stops_level = (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   int freeze_level = (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   double min_dist = MathMax(stops_level, freeze_level) * _Point;
   double actual_dist = MathAbs(price - target);
   if(actual_dist < min_dist) return (target > price) ? price + min_dist + _Point : price - min_dist - _Point;
   return target;
}

bool HasOpenPosition() {
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      if(PositionSelectByTicket(PositionGetTicket(i)) && PositionGetInteger(POSITION_MAGIC) == MagicNumber && PositionGetString(POSITION_SYMBOL) == _Symbol) return true;
   }
   return false;
}

double NormalizePrice(double p, double t) { return MathRound(p / t) * t; }
