//+------------------------------------------------------------------+
//|                                              StructureUtils.mqh |
//|                                  Copyright 2026, Trading Studio |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK.                                           |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Trading Studio"
#property link      "https://example.com"
#property strict

//+------------------------------------------------------------------+
//| Class for Market Structure Analysis                             |
//+------------------------------------------------------------------+
class CStructureUtils
{
public:
   // Detect if current structure is Bullish (Higher Highs and Higher Lows)
   static bool IsBullishStructure(int bars_to_check)
   {
      double last_low = iLow(_Symbol, _Period, 1);
      double prev_low = 0;
      int found = 0;
      
      // Look for the last prominent low
      for(int i = 2; i < bars_to_check; i++) {
         if(iLow(_Symbol, _Period, i) < iLow(_Symbol, _Period, i-1) && 
            iLow(_Symbol, _Period, i) < iLow(_Symbol, _Period, i+1)) {
            prev_low = iLow(_Symbol, _Period, i);
            found++;
            break;
         }
      }
      
      // If we found a previous swing low, and current price/low is above it
      return (found > 0 && last_low > prev_low);
   }

   // Detect if current structure is Bearish (Lower Lows and Lower Highs)
   static bool IsBearishStructure(int bars_to_check)
   {
      double last_high = iHigh(_Symbol, _Period, 1);
      double prev_high = 0;
      int found = 0;
      
      for(int i = 2; i < bars_to_check; i++) {
         if(iHigh(_Symbol, _Period, i) > iHigh(_Symbol, _Period, i-1) && 
            iHigh(_Symbol, _Period, i) > iHigh(_Symbol, _Period, i+1)) {
            prev_high = iHigh(_Symbol, _Period, i);
            found++;
            break;
         }
      }
      
      return (found > 0 && last_high < prev_high);
   }

   // Higher High detection
   static bool IsSwingHigh(int index, int radius)
   {
      double high = iHigh(_Symbol, _Period, index);
      for(int i = 1; i <= radius; i++) {
         if(iHigh(_Symbol, _Period, index + i) > high || iHigh(_Symbol, _Period, index - i) >= high) return false;
      }
      return true;
   }

   // Lower Low detection
   static bool IsSwingLow(int index, int radius)
   {
      double low = iLow(_Symbol, _Period, index);
      for(int i = 1; i <= radius; i++) {
         if(iLow(_Symbol, _Period, index + i) < low || iLow(_Symbol, _Period, index - i) <= low) return false;
      }
      return true;
   }
};
