//+------------------------------------------------------------------+
//|                                            DonchianUtils.mqh |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK.                                           |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property strict

class CDonchianUtils
{
public:
   // Calculate Upper Band (Highest High in the last N bars, shifted by 1)
   static double GetUpper(int period, int shift)
   {
      int idx = iHighest(_Symbol, _Period, MODE_HIGH, period, shift);
      if(idx < 0) return 0;
      return iHigh(_Symbol, _Period, idx);
   }

   // Calculate Lower Band (Lowest Low in the last N bars, shifted by 1)
   static double GetLower(int period, int shift)
   {
      int idx = iLowest(_Symbol, _Period, MODE_LOW, period, shift);
      if(idx < 0) return 0;
      return iLow(_Symbol, _Period, idx);
   }

   // Middle Line
   static double GetMiddle(int period, int shift)
   {
      double u = GetUpper(period, shift);
      double l = GetLower(period, shift);
      return (u + l) / 2.0;
   }
};
