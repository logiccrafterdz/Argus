//+------------------------------------------------------------------+
//|                                     AVWAP_Confluence_EA.mq5 |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK. VERSION 1.00 (Institutional VWAP Engine)  |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property version   "1.00"
#property strict

#include <Trade\Trade.mqh>
#include "AVWAPUtils.mqh"

//--- States
enum ENUM_EA_STATE {
   STATE_IDLE,
   STATE_WATCH_TOUCH,
   STATE_CONFIRM_BOUNCE
};

//--- Input parameters
input string   _Anchor_Settings     = "------ Anchor Points ------";
input ENUM_ANCHOR_MODE AnchorMode   = ANCHOR_SESSION; // Anchor Mode
input int      SessionAnchorHour    = 8;              // Session Anchor (Server Hour)
input int      SwingLookback        = 50;             // Swing Lookback

input string   _Confluence_Settings = "------ HTF & Signal ------";
input ENUM_TIMEFRAMES HTF_Period    = PERIOD_H1;      // HTF Trend Period
input int      EMA_Trend_Period     = 50;             // Trend EMA Period
input double   BounceATRMin         = 0.5;            // Min Bounce Size (ATR Ratio)
input int      MaxTradesPerSession  = 2;              // Max Session Trades

input string   _Meta_Settings       = "------ Risk & Meta ------";
input double   RiskPercent          = 1.0;            // Risk % per trade
input double   RR_Target            = 2.0;            // Reward:Risk Ratio
input double   SL_ATR_Buffer        = 0.2;            // SL buffer (ATR ratio)
input int      MaxSpread            = 15;             // Institutional Spread
input int      MagicNumber          = 100020;        // EA Magic Number

//--- Global variables
CTrade         trade;
int            ema_h, atr_h;
datetime       anchor_time = 0;
double         current_avwap = 0;
ENUM_EA_STATE  current_state = STATE_IDLE;
ENUM_ORDER_TYPE bias = ORDER_TYPE_BUY;
datetime       last_bar_time = 0;
int            bounce_bar_count = 0;
int            trades_today = 0;
int            last_day = 0;
int            vol_precision = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   ema_h = iMA(_Symbol, HTF_Period, EMA_Trend_Period, 0, MODE_EMA, PRICE_CLOSE);
   atr_h = iATR(_Symbol, _Period, 14);
   
   if(ema_h == INVALID_HANDLE || atr_h == INVALID_HANDLE) return(INIT_FAILED);
   
   double step_vol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   vol_precision = (int)MathMax(0, MathCeil(MathLog10(1.0 / step_vol)));
   
   trade.SetExpertMagicNumber(MagicNumber);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   // Reset trades count on new day
   MqlDateTime dt;
   TimeCurrent(dt);
   if(dt.day != last_day) {
      trades_today = 0;
      last_day = dt.day;
      anchor_time = 0; // Force recalculate anchor on new day
   }

   datetime current_bar_time = iTime(_Symbol, _Period, 0);
   bool is_new_bar = (current_bar_time != last_bar_time);
   last_bar_time = current_bar_time;

   if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > MaxSpread) return;
   if(trades_today >= MaxTradesPerSession) return;
   if(HasOpenPosition()) return;

   // 1. Update Core Data
   if(is_new_bar) {
      if(AnchorMode == ANCHOR_SWING || anchor_time == 0) 
         anchor_time = CAVWAPUtils::GetAnchorTime(AnchorMode, SessionAnchorHour, SwingLookback);
      DrawAVWAPLine();
   }
      
   current_avwap = CAVWAPUtils::CalculateAVWAP(anchor_time);

   // 2. HTF Bias Check
   double ema[];
   if(CopyBuffer(ema_h, 0, 0, 1, ema) <= 0) return;
   double htf_close = iClose(_Symbol, HTF_Period, 0);
   
   if(htf_close > ema[0]) bias = ORDER_TYPE_BUY; 
   else if(htf_close < ema[0]) bias = ORDER_TYPE_SELL;
   else return;

   // 3. Signal Logic
   switch(current_state)
   {
      case STATE_IDLE:
         if(!is_new_bar) break;
         
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         
         if(bias == ORDER_TYPE_BUY && ask > current_avwap) current_state = STATE_WATCH_TOUCH;
         if(bias == ORDER_TYPE_SELL && bid < current_avwap) current_state = STATE_WATCH_TOUCH;
         break;

      case STATE_WATCH_TOUCH:
         // Bias Reversal Protection
         if((bias == ORDER_TYPE_BUY && SymbolInfoDouble(_Symbol, SYMBOL_ASK) < current_avwap) ||
            (bias == ORDER_TYPE_SELL && SymbolInfoDouble(_Symbol, SYMBOL_BID) > current_avwap))
         {
            current_state = STATE_IDLE;
            break;
         }
         if(is_new_bar) DetectTouch();
         break;

      case STATE_CONFIRM_BOUNCE:
         if(is_new_bar) HandleBounceConfirmation();
         break;
   }
}

//+------------------------------------------------------------------+
//| Step 1: Detect touch on the AVWAP line                           |
//+------------------------------------------------------------------+
void DetectTouch()
{
   double low1 = iLow(_Symbol, _Period, 1);
   double high1 = iHigh(_Symbol, _Period, 1);
   
   if(bias == ORDER_TYPE_BUY) {
      if(low1 <= current_avwap) {
         current_state = STATE_CONFIRM_BOUNCE;
         bounce_bar_count = 0;
      }
   } else {
      if(high1 >= current_avwap) {
         current_state = STATE_CONFIRM_BOUNCE;
         bounce_bar_count = 0;
      }
   }
}

//+------------------------------------------------------------------+
//| Step 2: Confirmation of rejection close                          |
//+------------------------------------------------------------------+
void HandleBounceConfirmation()
{
   bounce_bar_count++;
   if(bounce_bar_count > 5) {
      current_state = STATE_IDLE;
      Print("AVWAP Reset: Bounce Expired (5 bars)");
      return;
   }

   double close1 = iClose(_Symbol, _Period, 1);
   double low1 = iLow(_Symbol, _Period, 1);
   double high1 = iHigh(_Symbol, _Period, 1);
   double atr[];
   if(CopyBuffer(atr_h, 0, 0, 1, atr) <= 0) return;
   
   double min_bounce = atr[0] * BounceATRMin;
   double tick_sz = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   if(bias == ORDER_TYPE_BUY) {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      if(close1 > current_avwap && CAVWAPUtils::IsBounceConfirmed(1, current_avwap, min_bounce)) {
         double sl = NormalizePrice(low1 - (SL_ATR_Buffer * atr[0]), tick_sz);
         sl = ValidateStopsLevel(ask, sl);
         double risk = ask - sl;
         if(risk <= 0) return;
         
         double tp = NormalizePrice(ask + (risk * RR_Target), tick_sz);
         double lot = CalculateLotSize(risk);
         
         if(trade.Buy(lot, _Symbol, ask, sl, tp, "AVWAP Bounce Buy")) {
            trades_today++;
            current_state = STATE_IDLE;
            return;
         }
      }
   } else {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      if(close1 < current_avwap && CAVWAPUtils::IsBounceConfirmed(1, current_avwap, min_bounce)) {
         double sl = NormalizePrice(high1 + (SL_ATR_Buffer * atr[0]), tick_sz);
         sl = ValidateStopsLevel(bid, sl);
         double risk = sl - bid;
         if(risk <= 0) return;
         
         double tp = NormalizePrice(bid - (risk * RR_Target), tick_sz);
         double lot = CalculateLotSize(risk);
         
         if(trade.Sell(lot, _Symbol, bid, sl, tp, "AVWAP Bounce Sell")) {
            trades_today++;
            current_state = STATE_IDLE;
            return;
         }
      }
   }
   
   // Failure reset: If price breaks significantly through VWAP without bouncing, back to IDLE
   if(bias == ORDER_TYPE_BUY && close1 < current_avwap - atr[0]) current_state = STATE_IDLE;
   if(bias == ORDER_TYPE_SELL && close1 > current_avwap + atr[0]) current_state = STATE_IDLE;
}

//+------------------------------------------------------------------+
//| Utilities & Graphics                                            |
//+------------------------------------------------------------------+
void DrawAVWAPLine() {
   ObjectDelete(0, "AVWAP_Line");
   ObjectCreate(0, "AVWAP_Line", OBJ_HLINE, 0, 0, current_avwap);
   ObjectSetInteger(0, "AVWAP_Line", OBJPROP_COLOR, clrCyan);
   ObjectSetInteger(0, "AVWAP_Line", OBJPROP_WIDTH, 2);
   ObjectSetInteger(0, "AVWAP_Line", OBJPROP_STYLE, STYLE_DASH);
}

double CalculateLotSize(double distance) 
{
   if(distance <= 0) return 0;

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double risk_amount = balance * (RiskPercent / 100.0);
   
   double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_size  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   
   if(tick_value <= 0) return 0;
   
   double lot = risk_amount / (distance / tick_size * tick_value);
   
   double min_vol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double max_vol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step_vol = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   
   lot = MathFloor(lot / step_vol) * step_vol;
   return NormalizeDouble(MathMax(min_vol, MathMin(max_vol, lot)), vol_precision);
}

double ValidateStopsLevel(double p, double t) {
   int s = (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL), f = (int)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_FREEZE_LEVEL);
   double m = MathMax(s, f) * _Point, d = MathAbs(p - t);
   if(d < m) return (t > p) ? p + m + _Point : p - m - _Point;
   return t;
}

bool HasOpenPosition() {
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      if(PositionSelectByTicket(PositionGetTicket(i)) && PositionGetInteger(POSITION_MAGIC) == MagicNumber && PositionGetString(POSITION_SYMBOL) == _Symbol) return true;
   }
   return false;
}

double NormalizePrice(double p, double t) { return MathRound(p / t) * t; }
void OnDeinit(const int reason) { ObjectDelete(0, "AVWAP_Line"); IndicatorRelease(ema_h); IndicatorRelease(atr_h); }
