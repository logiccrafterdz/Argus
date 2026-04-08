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
   // Detect Swing High
   static bool IsSwingHigh(int index, int radius)
   {
      double high = iHigh(_Symbol, _Period, index);
      for(int i = 1; i <= radius; i++) {
         if(iHigh(_Symbol, _Period, index + i) > high || iHigh(_Symbol, _Period, index - i) >= high) return false;
      }
      return true;
   }

   // Detect Swing Low
   static bool IsSwingLow(int index, int radius)
   {
      double low = iLow(_Symbol, _Period, index);
      for(int i = 1; i <= radius; i++) {
         if(iLow(_Symbol, _Period, index + i) < low || iLow(_Symbol, _Period, index - i) <= low) return false;
      }
      return true;
   }

   // Detect Break of Minor Structure (M15 or current TF)
   // type: 0 = Buy (Break above High), 1 = Sell (Break below Low)
   static bool IsStructureBreak(ENUM_ORDER_TYPE type, int lookback, int radius)
   {
      double last_close = iClose(_Symbol, _Period, 1);
      if(type == ORDER_TYPE_BUY) {
         for(int i = 2; i < lookback; i++) {
            if(IsSwingHigh(i, radius)) {
               if(last_close > iHigh(_Symbol, _Period, i)) return true;
               break; // Only check most recent
            }
         }
      }
      else {
         for(int i = 2; i < lookback; i++) {
            if(IsSwingLow(i, radius)) {
               if(last_close < iLow(_Symbol, _Period, i)) return true;
               break;
            }
         }
      }
      return false;
   }

   // Detect High/Low in a specific session window
   static bool GetSessionRange(datetime start, datetime end, double &high, double &low)
   {
      int start_idx = iBarShift(_Symbol, _Period, start, false);
      int end_idx   = iBarShift(_Symbol, _Period, end, false);
      
      if(start_idx < 0 || end_idx < 0 || start_idx <= end_idx) return false;

      int count = start_idx - end_idx + 1;
      int h_idx = iHighest(_Symbol, _Period, MODE_HIGH, count, end_idx);
      int l_idx = iLowest(_Symbol, _Period, MODE_LOW, count, end_idx);

      if(h_idx < 0 || l_idx < 0) return false;

      high = iHigh(_Symbol, _Period, h_idx);
      low  = iLow(_Symbol, _Period, l_idx);
      return true;
   }

   static double PipsToPoints()
   {
      int d = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
      return (d == 3 || d == 5) ? 10.0 * _Point : _Point;
   }
};
