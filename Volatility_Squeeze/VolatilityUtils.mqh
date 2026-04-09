//+------------------------------------------------------------------+
//|                                           VolatilityUtils.mqh |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK.                                           |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property strict

class CVolatilityUtils
{
public:
   // Calculate Keltner Channels
   static bool GetKeltnerBands(int ema_handle, int atr_handle, double multiplier, double &upper, double &lower)
   {
      double ema[], atr[];
      if(CopyBuffer(ema_handle, 0, 0, 1, ema) <= 0) return false;
      if(CopyBuffer(atr_handle, 0, 0, 1, atr) <= 0) return false;

      upper = ema[0] + (multiplier * atr[0]);
      lower = ema[0] - (multiplier * atr[0]);
      return true;
   }

   // Detect an Expansion Candle (Momentum)
   static bool IsExpansionCandle(int index, int avg_period, double multiplier)
   {
      double current_range = iHigh(_Symbol, _Period, index) - iLow(_Symbol, _Period, index);
      double current_body  = MathAbs(iClose(_Symbol, _Period, index) - iOpen(_Symbol, _Period, index));
      
      double sum_range = 0, sum_body = 0;
      for(int i = 1; i <= avg_period; i++) {
         sum_range += (iHigh(_Symbol, _Period, index + i) - iLow(_Symbol, _Period, index + i));
         sum_body  += MathAbs(iClose(_Symbol, _Period, index + i) - iOpen(_Symbol, _Period, index + i));
      }
      
      double avg_range = sum_range / (double)avg_period;
      double avg_body  = sum_body / (double)avg_period;
      
      if(avg_range == 0 || avg_body == 0) return false;
      
      // Both range and body must show expansion
      return (current_range > avg_range * multiplier && current_body > avg_body * multiplier);
   }

   // Standard Pip to Point conversion
   static double PipsToPoints()
   {
      int d = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
      return (d == 3 || d == 5) ? 10.0 * _Point : _Point;
   }
};
