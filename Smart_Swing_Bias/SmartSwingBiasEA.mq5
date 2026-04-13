//+------------------------------------------------------------------+
//|                                           SmartSwingBiasEA.mq5 |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK. VERSION 1.00 (SMC/ICT Inspired)          |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property version   "1.00"
#property strict

//--- Include necessary libraries
#include <Trade\Trade.mqh>
#include "..\Shared\ArgusCore.mqh"
#include "..\Shared\ArgusStructure.mqh"
//--- Input parameters
input string   _HTF_Settings        = "------ HTF Bias (D1) ------";
input ENUM_TIMEFRAMES HTF_Period    = PERIOD_D1;     // High Timeframe
input int      HTF_EMA_Slow         = 200;           // Trend Baseline
input int      HTF_EMA_Fast         = 50;            // Trend Momentum

input string   _LTF_Settings        = "------ LTF Setup (Live) ------";
input int      Swing_Radius         = 3;             // Radius for swing detection
input int      MinLegRangePips      = 30;            // Min range of valid swing leg
input double   Discount_Start       = 0.5;           // Entry Zone Start (0.5 = 50%)
input double   Discount_End         = 0.75;          // Entry Zone End

input string   _Risk_Settings        = "------ Risk & Trade ------";
input double   RiskPercent          = 1.0;           // Risk % per trade
input int      MaxTradesPerDay      = 1;             // Daily Trade Limit
input int      TP_Ratio             = 2;             // Fixed RR Target
input int      MaxSpread            = 25;            // Max Allowed Spread
input int      MagicNumber          = 100012;        // EA Magic Number

//--- Global variables
CTrade         trade;
int            ema_slow_htf, ema_fast_htf;
int            vol_precision = 0;
datetime       last_bar_time = 0;
int            trades_today = 0;
int            last_sync_day = -1;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   ema_slow_htf = iMA(_Symbol, HTF_Period, HTF_EMA_Slow, 0, MODE_EMA, PRICE_CLOSE);
   ema_fast_htf = iMA(_Symbol, HTF_Period, HTF_EMA_Fast, 0, MODE_EMA, PRICE_CLOSE);
   
   if(ema_slow_htf == INVALID_HANDLE || ema_fast_htf == INVALID_HANDLE) return(INIT_FAILED);
   
   vol_precision = CArgusCore::GetVolumePrecision(_Symbol);
   
   trade.SetExpertMagicNumber(MagicNumber);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(ema_slow_htf);
   IndicatorRelease(ema_fast_htf);
   ObjectsDeleteAll(0, "SSB_");
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   if(CArgusCore::IsHalted()) return;

   datetime now = TimeCurrent();
   MqlDateTime dt;
   TimeToStruct(now, dt);
   
   // Daily Reset
   if(dt.day != last_sync_day) {
      trades_today = 0;
      last_sync_day = dt.day;
   }

   // Check on New Bar
   datetime current_bar_time = iTime(_Symbol, _Period, 0);
   if(current_bar_time == last_bar_time) return;
   last_bar_time = current_bar_time;

   if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > MaxSpread) return;
   if(CArgusCore::HasOpenPosition(_Symbol, MagicNumber) || trades_today >= MaxTradesPerDay) return;

   // 1. Check HTF Bias
   int bias = CArgusStructure::GetHTFBias(_Symbol, HTF_Period, ema_slow_htf, ema_fast_htf);
   if(bias == 0) return;

   // 2. Identify Current Swing Leg
   double leg_h, leg_l;
   int h_idx, l_idx;
   if(!CArgusStructure::FindLatestSwingLeg(_Symbol, _Period, 300, Swing_Radius, leg_h, leg_l, h_idx, l_idx)) return;

   // Leg Range Filter
   double leg_pips = (leg_h - leg_l) / CArgusStructure::PipsToPoints(_Symbol);
   if(leg_pips < MinLegRangePips) return;

   // 3. Check for Entry Opportunity
   ProcessSignals(bias, leg_h, leg_l, h_idx, l_idx);
}

//+------------------------------------------------------------------+
//| Processing Signals in Discount/Premium Zones                    |
//+------------------------------------------------------------------+
void ProcessSignals(int bias, double high, double low, int h_idx, int l_idx)
{
   double range = high - low;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   
   // --- BULLISH BIAS: Buy in DISCOUNT ---
   if(bias == 1 && h_idx < l_idx) // We identified a leg where high is more recent (uptrend pull)
   {
      // Zone 0.5 - 0.75 (from top)
      double zone_top    = low + (range * (1.0 - Discount_Start));
      double zone_bottom = low + (range * (1.0 - Discount_End));
      
      DrawZoneBox(zone_top, zone_bottom);
      
      // Entry: Ask price is in discount AND we see a bullish rejection
      if(ask <= zone_top && ask >= zone_bottom)
      {
         if(IsRejectionCandle(ORDER_TYPE_BUY)) ExecuteTrade(ORDER_TYPE_BUY, low);
      }
   }
   
   // --- BEARISH BIAS: Sell in PREMIUM ---
   else if(bias == -1 && l_idx < h_idx) // Low is more recent (downtrend pull)
   {
      double zone_bottom = low + (range * Discount_Start);
      double zone_top    = low + (range * Discount_End);
      
      DrawZoneBox(zone_top, zone_bottom);
      
      if(bid >= zone_bottom && bid <= zone_top)
      {
         if(IsRejectionCandle(ORDER_TYPE_SELL)) ExecuteTrade(ORDER_TYPE_SELL, high);
      }
   }
}

//+------------------------------------------------------------------+
//| Confirmation: Rejection Candle Logic                             |
//+------------------------------------------------------------------+
bool IsRejectionCandle(ENUM_ORDER_TYPE type)
{
   double o1 = iOpen(_Symbol, _Period, 1);
   double c1 = iClose(_Symbol, _Period, 1);
   double l1 = iLow(_Symbol, _Period, 1);
   double h1 = iHigh(_Symbol, _Period, 1);
   
   if(type == ORDER_TYPE_BUY) {
      // Bullish Engulfing or long lower wick
      return (c1 > o1 && (c1 - l1) > (h1 - c1) * 2); 
   } else {
      // Bearish reversal
      return (c1 < o1 && (h1 - c1) > (c1 - l1) * 2);
   }
}

//+------------------------------------------------------------------+
//| Trade Execution                                                  |
//+------------------------------------------------------------------+
void ExecuteTrade(ENUM_ORDER_TYPE type, double sl_price)
{
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double tick_sz = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   if(type == ORDER_TYPE_BUY) {
      double sl = CArgusCore::NormalizePrice(_Symbol, sl_price - (2 * _Point), tick_sz);
      sl = CArgusCore::ValidateStopsLevel(_Symbol, ask, sl);
      double risk_dist = ask - sl;
      if(risk_dist <= 0) return;
      
      double tp = CArgusCore::NormalizePrice(_Symbol, ask + (risk_dist * TP_Ratio), tick_sz);
      tp = CArgusCore::ValidateStopsLevel(_Symbol, ask, tp);
      
      double lot = CArgusCore::CalculateLotSize(_Symbol, RiskPercent, risk_dist, vol_precision);
      if(trade.Buy(lot, _Symbol, ask, sl, tp, "SmartSwing Long")) trades_today++;
   }
   else {
      double sl = CArgusCore::NormalizePrice(_Symbol, sl_price + (2 * _Point), tick_sz);
      sl = CArgusCore::ValidateStopsLevel(_Symbol, bid, sl);
      double risk_dist = sl - bid;
      if(risk_dist <= 0) return;
      
      double tp = CArgusCore::NormalizePrice(_Symbol, bid - (risk_dist * TP_Ratio), tick_sz);
      tp = CArgusCore::ValidateStopsLevel(_Symbol, bid, tp);
      
      double lot = CArgusCore::CalculateLotSize(_Symbol, RiskPercent, risk_dist, vol_precision);
      if(trade.Sell(lot, _Symbol, bid, sl, tp, "SmartSwing Short")) trades_today++;
   }
}

//+------------------------------------------------------------------+
//| Utilities                                                        |
//+------------------------------------------------------------------+
void DrawZoneBox(double top, double bottom) {
   string name = "SSB_Zone";
   if(ObjectFind(0, name) < 0) {
      ObjectCreate(0, name, OBJ_RECTANGLE, 0, iTime(_Symbol, _Period, 20), top, iTime(_Symbol, _Period, 0), bottom);
      ObjectSetInteger(0, name, OBJPROP_COLOR, clrRoyalBlue);
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
      ObjectSetInteger(0, name, OBJPROP_FILL, true);
   } else {
      ObjectSetDouble(0, name, OBJPROP_PRICE, 0, top);
      ObjectSetDouble(0, name, OBJPROP_PRICE, 1, bottom);
      ObjectSetInteger(0, name, OBJPROP_TIME, 1, iTime(_Symbol, _Period, 0));
   }
}


//+------------------------------------------------------------------+
//| Trade Analytics Event                                            |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction& trans, const MqlTradeRequest& request, const MqlTradeResult& result)
{
   if(trans.type == TRADE_TRANSACTION_DEAL_ADD) {
      if(HistoryDealSelect(trans.deal)) {
         if(HistoryDealGetInteger(DEAL_MAGIC) == MagicNumber && HistoryDealGetInteger(DEAL_ENTRY) == DEAL_ENTRY_IN) {
            CArgusCore::LogTradeData(_Symbol, MagicNumber, (ENUM_ORDER_TYPE)HistoryDealGetInteger(DEAL_TYPE), HistoryDealGetDouble(DEAL_VOLUME), HistoryDealGetDouble(DEAL_PRICE), HistoryDealGetDouble(DEAL_SL), HistoryDealGetDouble(DEAL_TP), HistoryDealGetString(DEAL_COMMENT), trans.order);
         }
      }
   }
}
