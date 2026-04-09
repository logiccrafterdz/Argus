//+------------------------------------------------------------------+
//|                                                   ORUtils.mqh |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK.                                           |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property strict

class CORUtils
{
public:
   // Detect Range Boundaries
   static bool GetRangeBoundaries(datetime start, datetime end, double &high, double &low)
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

   // Trend Bias Filter (EMA)
   static bool IsTrendAligned(ENUM_ORDER_TYPE type, int ema_handle)
   {
      double ema[];
      if(CopyBuffer(ema_handle, 0, 0, 1, ema) <= 0) return true; // Default to true if indicator fails
      
      double close = iClose(_Symbol, _Period, 1);
      if(type == ORDER_TYPE_BUY) return (close > ema[0]);
      if(type == ORDER_TYPE_SELL) return (close < ema[0]);
      return true;
   }

   // Expansion / Momentum Detector
   static bool IsExpansionCandle(int index, int lookback, double multiplier)
   {
      double cur_range = iHigh(_Symbol, _Period, index) - iLow(_Symbol, _Period, index);
      double cur_body  = MathAbs(iClose(_Symbol, _Period, index) - iOpen(_Symbol, _Period, index));
      
      double sum_range = 0, sum_body = 0;
      for(int i = 1; i <= lookback; i++) {
         sum_range += (iHigh(_Symbol, _Period, index + i) - iLow(_Symbol, _Period, index + i));
         sum_body  += MathAbs(iClose(_Symbol, _Period, index + i) - iOpen(_Symbol, _Period, index + i));
      }
      
      double avg_range = sum_range / (double)lookback;
      double avg_body  = sum_body / (double)lookback;
      
      return (cur_range > avg_range * multiplier && cur_body > avg_body * multiplier);
   }

   static double PipsToPoints()
   {
      int d = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
      return (d == 3 || d == 5) ? 10.0 * _Point : _Point;
   }
};
