//+------------------------------------------------------------------+
//|                                           TrendPullbackEA.mq5    |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK. VERSION 3.10 (Standard Gold Refined)      |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property version   "3.10"
#property strict

//--- Include necessary libraries
#include <Trade\Trade.mqh>
#include "..\Shared\ArgusCore.mqh"
#include "..\Shared\ArgusStructure.mqh"
//--- Input parameters
input int      FastEMA_Period = 50;     // Fast EMA Period (Pullback Zone)
input int      SlowEMA_Period = 200;    // Slow EMA Period (Trend Filter)
input int      MarketStructurePeriod = 30; // Bars to check for HH/HL structure
input int      MaxSpread      = 30;     // Max Allowed Spread (Points)
input double   RiskPercent    = 1.0;    // Risk % per Trade
input int      TP_Multiplier  = 2;      // Risk-Reward Multiplier
input int      MagicNumber    = 100001; // EA Magic Number
input bool     OnlyNewBar     = true;   // Execute on New Bar Only

//--- Global variables
CTrade         trade;
int            fast_ema_handle;
int            slow_ema_handle;
double         fast_ema_buffer[];
double         slow_ema_buffer[];
datetime       last_bar_time = 0;
int            vol_precision = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   fast_ema_handle = iMA(_Symbol, _Period, FastEMA_Period, 0, MODE_EMA, PRICE_CLOSE);
   slow_ema_handle = iMA(_Symbol, _Period, SlowEMA_Period, 0, MODE_EMA, PRICE_CLOSE);
   
   if(fast_ema_handle == INVALID_HANDLE || slow_ema_handle == INVALID_HANDLE)
   {
      Print("Error: Failed to create indicator handles.");
      return(INIT_FAILED);
   }
   
   // Volume Precision
   vol_precision = CArgusCore::GetVolumePrecision(_Symbol);
   
   trade.SetExpertMagicNumber(MagicNumber);
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
   if(OnlyNewBar)
   {
      datetime current_bar_time = iTime(_Symbol, _Period, 0);
      if(current_bar_time == last_bar_time) return;
      last_bar_time = current_bar_time;
   }

   if(BarsCalculated(fast_ema_handle) < SlowEMA_Period || 
      BarsCalculated(slow_ema_handle) < SlowEMA_Period) return;

   if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > MaxSpread) return;
   if(CArgusCore::HasOpenPosition(_Symbol, MagicNumber)) return;

   ArraySetAsSeries(fast_ema_buffer, true);
   ArraySetAsSeries(slow_ema_buffer, true);
   if(CopyBuffer(fast_ema_handle, 0, 0, 4, fast_ema_buffer) < 4 ||
      CopyBuffer(slow_ema_handle, 0, 0, 4, slow_ema_buffer) < 4) return;

   // Market Analysis (2-Bar Logic + HH/HL Structure)
   double bar1_close = iClose(_Symbol, _Period, 1);
   double bar2_high  = iHigh(_Symbol, _Period, 2);
   double bar2_low   = iLow(_Symbol, _Period, 2);

   // A. Strategic Trend Confluence
   bool ema_bias_up = (fast_ema_buffer[1] > slow_ema_buffer[1]) && (slow_ema_buffer[1] > slow_ema_buffer[2]);
   bool ema_bias_dn = (fast_ema_buffer[1] < slow_ema_buffer[1]) && (slow_ema_buffer[1] < slow_ema_buffer[2]);
   
   bool structure_up = CArgusStructure::IsBullishStructure(_Symbol, _Period, MarketStructurePeriod);
   bool structure_dn = CArgusStructure::IsBearishStructure(_Symbol, _Period, MarketStructurePeriod);

   bool is_uptrend = ema_bias_up && structure_up;
   bool is_downtrend = ema_bias_dn && structure_dn;

   // B. Trigger Logic
   bool bull_pullback = is_uptrend && (iLow(_Symbol, _Period, 2) <= fast_ema_buffer[2]);
   bool bear_pullback = is_downtrend && (iHigh(_Symbol, _Period, 2) >= fast_ema_buffer[2]);

   bool bull_trigger = bull_pullback && (bar1_close > bar2_high); 
   bool bear_trigger = bear_pullback && (bar1_close < bar2_low);

   // C. Pricing & Validation
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   if(bull_trigger)
   {
      double sl = CArgusCore::NormalizePrice(_Symbol, iLow(_Symbol, _Period, 1) - CArgusCore::PipsToPriceDelta(_Symbol, 5), tick_size);
      sl = CArgusCore::ValidateStopsLevel(_Symbol, ask, sl);
      
      double risk_dist = ask - sl;
      if(risk_dist <= 0) return;
      
      double tp = CArgusCore::NormalizePrice(_Symbol, ask + (risk_dist * TP_Multiplier), tick_size);
      tp = CArgusCore::ValidateStopsLevel(_Symbol, ask, tp);
      
      double lot = CArgusCore::CalculateLotSize(_Symbol, RiskPercent, risk_dist, vol_precision);
      ExecuteTrade(ORDER_TYPE_BUY, lot, ask, sl, tp, "Gold Pullback Buy");
   }
   else if(bear_trigger)
   {
      double sl = CArgusCore::NormalizePrice(_Symbol, iHigh(_Symbol, _Period, 1) + CArgusCore::PipsToPriceDelta(_Symbol, 5), tick_size);
      sl = CArgusCore::ValidateStopsLevel(_Symbol, bid, sl);
      
      double risk_dist = sl - bid;
      if(risk_dist <= 0) return;
      
      double tp = CArgusCore::NormalizePrice(_Symbol, bid - (risk_dist * TP_Multiplier), tick_size);
      tp = CArgusCore::ValidateStopsLevel(_Symbol, bid, tp);
      
      double lot = CArgusCore::CalculateLotSize(_Symbol, RiskPercent, risk_dist, vol_precision);
      ExecuteTrade(ORDER_TYPE_SELL, lot, bid, sl, tp, "Gold Pullback Sell");
   }
}

//+------------------------------------------------------------------+
//| Execute and Log Result                                           |
//+------------------------------------------------------------------+
void ExecuteTrade(ENUM_ORDER_TYPE type, double lot, double price, double sl, double tp, string comment)
{
   bool success = (type == ORDER_TYPE_BUY) ? trade.Buy(lot, _Symbol, price, sl, tp, comment) : trade.Sell(lot, _Symbol, price, sl, tp, comment);
   
   if(!success)
      PrintFormat("Trade Failed: %s. Code: %d (%s)", comment, trade.ResultRetcode(), trade.ResultRetcodeDescription());
   else
      PrintFormat("Trade Opened: %s. Ticket: %d. Lot: %.*f", comment, trade.ResultOrder(), vol_precision, lot);
}

//+------------------------------------------------------------------+
//| Standard Volume Calculation                                      |

//+------------------------------------------------------------------+
//| Logic for Validating Stops against BOTH Stops and Freeze levels  |

//+------------------------------------------------------------------+
//| Helpers                                                          |

