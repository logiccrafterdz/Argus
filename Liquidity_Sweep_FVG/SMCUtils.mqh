//+------------------------------------------------------------------+
//|                                                     SMCUtils.mqh |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK.                                           |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property strict

class CSMCUtils
{
public:
   // Detect Bullish Fair Value Gap (3-Candle Sequence)
   // i = start of gap (candle 1), i+1 = displacement (candle 2), i+2 = end of gap (candle 3)
   static bool IsBullishFVG(int i, double &top, double &bottom)
   {
      double h_start = iHigh(_Symbol, _Period, i + 2); // Candle 3 High
      double l_end   = iLow(_Symbol, _Period, i);     // Candle 1 Low
      
      if(l_end > h_start + 2 * _Point) {
         top = l_end;
         bottom = h_start;
         return true;
      }
      return false;
   }

   // Detect Bearish Fair Value Gap
   static bool IsBearishFVG(int i, double &top, double &bottom)
   {
      double l_start = iLow(_Symbol, _Period, i + 2);  // Candle 3 Low
      double h_end   = iHigh(_Symbol, _Period, i);      // Candle 1 High
      
      if(h_end < l_start - 2 * _Point) {
         top = l_start;
         bottom = h_end;
         return true;
      }
      return false;
   }

   // Identify Liquidity Pools (Short-term High/Low)
   static void GetLiquidityPools(int lookback, double &high, double &low)
   {
      int h_idx = iHighest(_Symbol, _Period, MODE_HIGH, lookback, 1);
      int l_idx = iLowest(_Symbol, _Period, MODE_LOW, lookback, 1);
      
      high = iHigh(_Symbol, _Period, h_idx);
      low = iLow(_Symbol, _Period, l_idx);
   }

   // Check for displacement (Using middle candle of sequence)
   static bool IsDisplacement(int i, int atr_h)
   {
      double body = MathAbs(iOpen(_Symbol, _Period, i) - iClose(_Symbol, _Period, i));
      double atr[];
      if(CopyBuffer(atr_h, 0, 0, 1, atr) <= 0) return false;
      
      return (body > atr[0] * 1.5); 
   }
};
