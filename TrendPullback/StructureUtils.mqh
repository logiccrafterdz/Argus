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
   // Detect if a bar is a Swing High (shorter period)
   static bool IsSwingHigh(int index, int left_bars, int right_bars)
   {
      double high = iHigh(_Symbol, _Period, index);
      for(int i = 1; i <= left_bars; i++)
         if(iHigh(_Symbol, _Period, index + i) > high) return false;
      for(int i = 1; i <= right_bars; i++)
         if(iHigh(_Symbol, _Period, index - i) >= high) return false;
      return true;
   }

   // Detect if a bar is a Swing Low (shorter period)
   static bool IsSwingLow(int index, int left_bars, int right_bars)
   {
      double low = iLow(_Symbol, _Period, index);
      for(int i = 1; i <= left_bars; i++)
         if(iLow(_Symbol, _Period, index + i) < low) return false;
      for(int i = 1; i <= right_bars; i++)
         if(iLow(_Symbol, _Period, index - i) <= low) return false;
      return true;
   }

   // Identify Trend based on Highs/Lows
   static int GetTrendBias(int bars_to_check)
   {
      double last_hh = 0, last_hl = 0, last_lh = 0, last_ll = 0;
      int hh_count = 0, ll_count = 0;

      // Logic for simplistic trend detection
      // 1 = Bullish, -1 = Bearish, 0 = Neutral
      // In a real system, we would store these points.
      return 0; // Placeholder for now, simple EMA usually suffices for the first version
   }
};
