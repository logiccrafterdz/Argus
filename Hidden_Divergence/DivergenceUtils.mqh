//+------------------------------------------------------------------+
//|                                           DivergenceUtils.mqh |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK.                                           |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property strict

class CDivergenceUtils
{
public:
   // Find indices of last two swing lows
   static bool FindSwingLows(int radius, int lookback, int &s1, int &s2)
   {
      s1 = -1; s2 = -1;
      int found = 0;
      for(int i = radius + 1; i < lookback; i++) {
         if(IsSwingLow(i, radius)) {
            if(found == 0) { s1 = i; found++; }
            else { s2 = i; return true; }
         }
      }
      return false;
   }

   // Find indices of last two swing highs
   static bool FindSwingHighs(int radius, int lookback, int &s1, int &s2)
   {
      s1 = -1; s2 = -1;
      int found = 0;
      for(int i = radius + 1; i < lookback; i++) {
         if(IsSwingHigh(i, radius)) {
            if(found == 0) { s1 = i; found++; }
            else { s2 = i; return true; }
         }
      }
      return false;
   }

   // Helper: Is index i a swing high?
   static bool IsSwingHigh(int i, int r) {
      double h = iHigh(_Symbol, _Period, i);
      for(int j = 1; j <= r; j++) {
         if(iHigh(_Symbol, _Period, i+j) > h || iHigh(_Symbol, _Period, i-j) >= h) return false;
      }
      return true;
   }

   // Helper: Is index i a swing low?
   static bool IsSwingLow(int i, int r) {
      double l = iLow(_Symbol, _Period, i);
      for(int j = 1; j <= r; j++) {
         if(iLow(_Symbol, _Period, i+j) < l || iLow(_Symbol, _Period, i-j) <= l) return false;
      }
      return true;
   }

   // RSI Buffer Helper
   static double GetRSIAt(int handle, int index) {
      double rsi[];
      if(CopyBuffer(handle, 0, index, 1, rsi) > 0) return rsi[0];
      return -1;
   }
};
