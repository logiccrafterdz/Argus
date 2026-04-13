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
   // Detect Bullish Fair Value Gap
   static bool IsBullishFVG(int i, double &top, double &bottom)
   {
      double h2 = iHigh(_Symbol, _Period, i + 2);
      double l0 = iLow(_Symbol, _Period, i);
      
      if(l0 > h2 + 2 * _Point) {
         top = l0;
         bottom = h2;
         return true;
      }
      return false;
   }

   // Detect Bearish Fair Value Gap
   static bool IsBearishFVG(int i, double &top, double &bottom)
   {
      double l2 = iLow(_Symbol, _Period, i + 2);
      double h0 = iHigh(_Symbol, _Period, i);
      
      if(h0 < l2 - 2 * _Point) {
         top = l2;
         bottom = h0;
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

   // Check for displacement (Strong impulsive candle)
   static bool IsDisplacement(int i, int atr_h)
   {
      double body = MathAbs(iOpen(_Symbol, _Period, i) - iClose(_Symbol, _Period, i));
      double atr[];
      if(CopyBuffer(atr_h, 0, i, 1, atr) <= 0) return false;
      
      return (body > atr[0] * 1.5); // Body must be 1.5x larger than average volatility
   }
};
