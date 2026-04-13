//+------------------------------------------------------------------+
//|                                                    ArgusCore.mqh |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK.                                           |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property strict

//+------------------------------------------------------------------+
//| Class for Core Operations (Risk, Validation, Helpers)            |
//+------------------------------------------------------------------+
class CArgusCore
{
public:
   //+------------------------------------------------------------------+
   //| Standard Volume Calculation                                      |
   //+------------------------------------------------------------------+
   static double CalculateLotSize(string symbol, double risk_percent, double risk_dist_points, int vol_precision)
   {
      double balance = AccountInfoDouble(ACCOUNT_BALANCE);
      double risk_amount = balance * (risk_percent / 100.0);
      double tick_value = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
      double tick_size = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
      
      if(risk_dist_points <= 0 || tick_value <= 0) return 0;
      
      double lot = risk_amount / (risk_dist_points / tick_size * tick_value);
      double min_vol = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
      double max_vol = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
      double step_vol = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
      
      lot = MathFloor(lot / step_vol) * step_vol;
      lot = MathMax(min_vol, MathMin(max_vol, lot));
      return NormalizeDouble(lot, vol_precision);
   }

   //+------------------------------------------------------------------+
   //| Logic for Validating Stops against BOTH Stops and Freeze levels  |
   //+------------------------------------------------------------------+
   static double ValidateStopsLevel(string symbol, double price, double target)
   {
      int stops_level = (int)SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL);
      int freeze_level = (int)SymbolInfoInteger(symbol, SYMBOL_TRADE_FREEZE_LEVEL);
      int max_level = MathMax(stops_level, freeze_level);
      
      double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
      double min_dist = max_level * point;
      double actual_dist = MathAbs(price - target);
      
      if(actual_dist < min_dist)
      {
         double new_target = (target > price) ? price + min_dist + point : price - min_dist - point;
         PrintFormat("Warning: SL/TP too close to price (MaxLevel: %d). Adjusted to respect Broker limits. RR Impact possible.", max_level);
         return NormalizePrice(symbol, new_target, SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE));
      }
      return target;
   }

   //+------------------------------------------------------------------+
   //| Check if an EA has open positions                                |
   //+------------------------------------------------------------------+
   static bool HasOpenPosition(string symbol, int magic_number)
   {
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong ticket = PositionGetTicket(i);
         if(PositionSelectByTicket(ticket) && PositionGetInteger(POSITION_MAGIC) == magic_number && PositionGetString(POSITION_SYMBOL) == symbol) return true;
      }
      return false;
   }

   //+------------------------------------------------------------------+
   //| Helpers                                                          |
   //+------------------------------------------------------------------+
   static double NormalizePrice(string symbol, double price, double tick_size) 
   { 
      return MathRound(price / tick_size) * tick_size; 
   }

   static double PipsToPriceDelta(string symbol, double pips)
   {
      int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
      double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
      return (digits == 3 || digits == 5) ? pips * 10 * point : pips * point;
   }
   
   static int GetVolumePrecision(string symbol)
   {
       double step_vol = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
       return (int)MathMax(0, MathCeil(MathLog10(1.0 / step_vol)));
   }
};
