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

   // Detect Higher Timeframe Bias
   // Returns: 1 (Bullish), -1 (Bearish), 0 (Neutral)
   static int GetHTFBias(ENUM_TIMEFRAMES htf, int ema_200_handle, int ema_50_handle)
   {
      double ema200[], ema50[], close[];
      if(CopyBuffer(ema_200_handle, 0, 0, 1, ema200) <= 0) return 0;
      if(CopyBuffer(ema_50_handle, 0, 0, 1, ema50) <= 0) return 0;
      
      MqlRates rates[];
      if(CopyRates(_Symbol, htf, 0, 1, rates) <= 0) return 0;
      
      bool trend_up = (rates[0].close > ema200[0] && ema50[0] > ema200[0]);
      bool trend_dn = (rates[0].close < ema200[0] && ema50[0] < ema200[0]);
      
      if(trend_up) return 1;
      if(trend_dn) return -1;
      return 0;
   }

   // Find the most recent Swing Leg
   static bool FindLatestSwingLeg(int lookback, int radius, double &leg_high, double &leg_low, int &h_idx, int &l_idx)
   {
      leg_high = 0; leg_low = 0;
      h_idx = -1; l_idx = -1;

      for(int i = 2; i < lookback; i++) {
         if(h_idx == -1 && IsSwingHigh(i, radius)) h_idx = i;
         if(l_idx == -1 && IsSwingLow(i, radius)) l_idx = i;
         if(h_idx != -1 && l_idx != -1) break;
      }

      if(h_idx != -1 && l_idx != -1) {
         leg_high = iHigh(_Symbol, _Period, h_idx);
         leg_low  = iLow(_Symbol, _Period, l_idx);
         return true;
      }
      return false;
   }

   static double PipsToPoints()
   {
      int d = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
      return (d == 3 || d == 5) ? 10.0 * _Point : _Point;
   }
};
