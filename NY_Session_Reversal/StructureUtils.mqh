//+------------------------------------------------------------------+
//|                                              StructureUtils.mqh |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK.                                           |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property strict

class CStructureUtils
{
public:
   // Detect Swing logic
   static bool IsSwingHigh(int index, int radius)
   {
      double h = iHigh(_Symbol, _Period, index);
      for(int i = 1; i <= radius; i++) {
         if(iHigh(_Symbol, _Period, index + i) > h || iHigh(_Symbol, _Period, index - i) >= h) return false;
      }
      return true;
   }

   static bool IsSwingLow(int index, int radius)
   {
      double l = iLow(_Symbol, _Period, index);
      for(int i = 1; i <= radius; i++) {
         if(iLow(_Symbol, _Period, index + i) < l || iLow(_Symbol, _Period, index - i) <= l) return false;
      }
      return true;
   }

   // Detect Session Range
   static bool GetSessionRange(datetime start, datetime end, double &high, double &low)
   {
      int s_idx = iBarShift(_Symbol, _Period, start, false);
      int e_idx = iBarShift(_Symbol, _Period, end, false);
      if(s_idx < 0 || e_idx < 0 || s_idx <= e_idx) return false;

      int count = s_idx - e_idx + 1;
      int h_idx = iHighest(_Symbol, _Period, MODE_HIGH, count, e_idx);
      int l_idx = iLowest(_Symbol, _Period, MODE_LOW, count, e_idx);

      if(h_idx < 0 || l_idx < 0) return false;
      high = iHigh(_Symbol, _Period, h_idx);
      low  = iLow(_Symbol, _Period, l_idx);
      return true;
   }

   // Detect Structure Break (MSB)
   static bool IsStructureBreak(ENUM_ORDER_TYPE type, int lookback, int radius)
   {
      double last_close = iClose(_Symbol, _Period, 1);
      if(type == ORDER_TYPE_BUY) { // Bullish Break
         for(int i = 2; i < lookback; i++) {
            if(IsSwingHigh(i, radius)) {
               if(last_close > iHigh(_Symbol, _Period, i)) return true;
               break;
            }
         }
      } else { // Bearish Break
         for(int i = 2; i < lookback; i++) {
            if(IsSwingLow(i, radius)) {
               if(last_close < iLow(_Symbol, _Period, i)) return true;
               break;
            }
         }
      }
      return false;
   }

   static double PipsToPoints()
   {
      int d = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
      return (d == 3 || d == 5) ? 10.0 * _Point : _Point;
   }
};
