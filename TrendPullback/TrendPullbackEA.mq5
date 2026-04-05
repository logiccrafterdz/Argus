//+------------------------------------------------------------------+
//|                                           TrendPullbackEA.mq5    |
//|                                  Copyright 2026, Trading Studio |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK.                                           |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Trading Studio"
#property link      "https://example.com"
#property version   "1.00"
#property strict

//--- Include necessary libraries
#include <Trade\Trade.mqh>
#include "StructureUtils.mqh"

//--- Input parameters
input int      FastEMA_Period = 50;     // Fast EMA Period (Pullback Zone)
input int      SlowEMA_Period = 200;    // Slow EMA Period (Trend Filter)
input double   RiskPercent    = 1.0;    // Risk % per Trade
input int      TP_Multiplier  = 2;      // Risk-Reward Multiplier
input int      MagicNumber    = 123456; // EA Magic Number

//--- Global variables
CTrade         trade;
int            fast_ema_handle;
int            slow_ema_handle;
double         fast_ema_buffer[];
double         slow_ema_buffer[];

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   // Initialize EMA handles
   fast_ema_handle = iMA(_Symbol, _Period, FastEMA_Period, 0, MODE_EMA, PRICE_CLOSE);
   slow_ema_handle = iMA(_Symbol, _Period, SlowEMA_Period, 0, MODE_EMA, PRICE_CLOSE);
   
   if(fast_ema_handle == INVALID_HANDLE || slow_ema_handle == INVALID_HANDLE)
   {
      Print("Error: Failed to create indicator handles.");
      return(INIT_FAILED);
   }
   
   // Set trade parameters
   trade.SetExpertMagicNumber(MagicNumber);
   
   // Success
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(fast_ema_handle);
   IndicatorRelease(slow_ema_handle);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Check if we have an open position with this magic number
   if(PositionsTotal() > 0)
   {
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong ticket = PositionGetTicket(i);
         if(PositionSelectByTicket(ticket))
         {
            if(PositionGetInteger(POSITION_MAGIC) == MagicNumber) return; // Wait for exit
         }
      }
   }

   // Copy indicator data
   ArraySetAsSeries(fast_ema_buffer, true);
   ArraySetAsSeries(slow_ema_buffer, true);
   
   if(CopyBuffer(fast_ema_handle, 0, 0, 3, fast_ema_buffer) < 3 ||
      CopyBuffer(slow_ema_handle, 0, 0, 3, slow_ema_buffer) < 3) return;

   // Current Price
   double last_close = iClose(_Symbol, _Period, 1);
   double last_open = iOpen(_Symbol, _Period, 1);
   double current_bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double current_ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   // 1. Identify Trend (EMA 200 Filter)
   bool is_uptrend = (last_close > slow_ema_buffer[1]);
   bool is_downtrend = (last_close < slow_ema_buffer[1]);
   
   // 2. Identify Pullback (Touching Fast EMA)
   bool bull_pullback = is_uptrend && (iLow(_Symbol, _Period, 1) <= fast_ema_buffer[1] && last_close > fast_ema_buffer[1]);
   bool bear_pullback = is_downtrend && (iHigh(_Symbol, _Period, 1) >= fast_ema_buffer[1] && last_close < fast_ema_buffer[1]);

   // 3. Price Action Confirmation (Simple Engulfing/Rejection)
   bool bull_trigger = bull_pullback && (last_close > last_open); // Bullish candle
   bool bear_trigger = bear_pullback && (last_close < last_open); // Bearish candle

   // 4. Trade Execution
   if(bull_trigger)
   {
      double sl = iLow(_Symbol, _Period, 1) - 50 * _Point; // 5 pips below low
      double risk_dist = current_ask - sl;
      double tp = current_ask + (risk_dist * TP_Multiplier);
      
      double lot_size = CalculateLotSize(risk_dist);
      trade.Buy(lot_size, _Symbol, current_ask, sl, tp, "Trend Pullback Buy");
   }
   else if(bear_trigger)
   {
      double sl = iHigh(_Symbol, _Period, 1) + 50 * _Point; // 5 pips above high
      double risk_dist = sl - current_bid;
      double tp = current_bid - (risk_dist * TP_Multiplier);
      
      double lot_size = CalculateLotSize(risk_dist);
      trade.Sell(lot_size, _Symbol, current_bid, sl, tp, "Trend Pullback Sell");
   }
}

//+------------------------------------------------------------------+
//| Calculate Lot Size based on Risk %                               |
//+------------------------------------------------------------------+
double CalculateLotSize(double risk_dist_points)
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double risk_amount = balance * (RiskPercent / 100.0);
   double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   
   if(risk_dist_points <= 0 || tick_value <= 0) return 0.01;
   
   double lot = risk_amount / (risk_dist_points / tick_size * tick_value);
   double min_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   
   return NormalizeDouble(MathMax(min_lot, MathMin(max_lot, lot)), 2);
}
