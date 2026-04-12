//+------------------------------------------------------------------+
//|                                                     ADXUtils.mqh |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK.                                           |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property strict

class CADXUtils
{
public:
   // Check if ADX is rising for the last N bars
   static bool IsRising(int handle, int count)
   {
      double adx[];
      if(CopyBuffer(handle, 0, 0, count + 1, adx) <= count) return false;
      
      for(int i = 0; i < count; i++) {
         if(adx[i] <= adx[i+1]) return false; // index 0 is current, i+1 is previous
      }
      return true;
   }

   // Check if ADX is falling for the last N bars (Exhaustion)
   static bool IsFalling(int handle, int count)
   {
      double adx[];
      if(CopyBuffer(handle, 0, 0, count + 1, adx) <= count) return false;
      
      for(int i = 0; i < count; i++) {
         if(adx[i] >= adx[i+1]) return false;
      }
      return true;
   }

   // Calculate 1.5x ATR distance
   static double GetATRDistance(int atr_handle, double multiplier)
   {
      double atr[];
      if(CopyBuffer(atr_handle, 0, 1, 1, atr) <= 0) return 0;
      return atr[0] * multiplier;
   }
};
