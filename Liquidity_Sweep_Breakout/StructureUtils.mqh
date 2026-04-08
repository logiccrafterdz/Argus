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
//| Class for Market Structure and Liquidity Analysis                |
//+------------------------------------------------------------------+
class CStructureUtils
{
public:
   // Detect if price is a Swing High
   static bool IsSwingHigh(int index, int radius)
   {
      double high = iHigh(_Symbol, _Period, index);
      for(int i = 1; i <= radius; i++) {
         if(iHigh(_Symbol, _Period, index + i) > high || iHigh(_Symbol, _Period, index - i) >= high) return false;
      }
      return true;
   }

   // Detect if price is a Swing Low
   static bool IsSwingLow(int index, int radius)
   {
      double low = iLow(_Symbol, _Period, index);
      for(int i = 1; i <= radius; i++) {
         if(iLow(_Symbol, _Period, index + i) < low || iLow(_Symbol, _Period, index - i) <= low) return false;
      }
      return true;
   }

   // Find Equal Highs (Liquidity Levels)
   // Returns the highest point of the discovered EQH cluster
   static double GetLiquidityHigh(int lookback, int radius, double threshold_pips)
   {
      double points = threshold_pips * PipsToPoints();
      double swings[];
      int count = 0;

      // 1. Collect all swing highs in lookback
      for(int i = 2; i < lookback; i++) {
         if(IsSwingHigh(i, radius)) {
            ArrayResize(swings, count + 1);
            swings[count] = iHigh(_Symbol, _Period, i);
            count++;
         }
      }

      if(count < 2) return 0;

      // 2. Find groups of highs that are close to each other
      for(int i = 0; i < count; i++) {
         int matches = 0;
         double max_h = swings[i];
         for(int j = 0; j < count; j++) {
            if(i == j) continue;
            if(MathAbs(swings[i] - swings[j]) <= points) {
               matches++;
               if(swings[j] > max_h) max_h = swings[j];
            }
         }
         // If we found at least one other high close to this one, it's a liquidity pool
         if(matches >= 1) return max_h; 
      }

      return 0;
   }

   // Find Equal Lows (Liquidity Levels)
   static double GetLiquidityLow(int lookback, int radius, double threshold_pips)
   {
      double points = threshold_pips * PipsToPoints();
      double swings[];
      int count = 0;

      for(int i = 2; i < lookback; i++) {
         if(IsSwingLow(i, radius)) {
            ArrayResize(swings, count + 1);
            swings[count] = iLow(_Symbol, _Period, i);
            count++;
         }
      }

      if(count < 2) return 0;

      for(int i = 0; i < count; i++) {
         int matches = 0;
         double min_l = swings[i];
         for(int j = 0; j < count; j++) {
            if(i == j) continue;
            if(MathAbs(swings[i] - swings[j]) <= points) {
               matches++;
               if(swings[j] < min_l) min_l = swings[j];
            }
         }
         if(matches >= 1) return min_l;
      }

      return 0;
   }

   // Market Structure Break (MSB) detection
   // For Bearish MSB: Close below the last swing low
   static bool IsBearishMSB(int bars_to_check, int radius)
   {
      double last_close = iClose(_Symbol, _Period, 1);
      for(int i = 2; i < bars_to_check; i++) {
         if(IsSwingLow(i, radius)) {
            if(last_close < iLow(_Symbol, _Period, i)) return true;
            break; // Check only the most recent major swing
         }
      }
      return false;
   }

   // For Bullish MSB: Close above the last swing high
   static bool IsBullishMSB(int bars_to_check, int radius)
   {
      double last_close = iClose(_Symbol, _Period, 1);
      for(int i = 2; i < bars_to_check; i++) {
         if(IsSwingHigh(i, radius)) {
            if(last_close > iHigh(_Symbol, _Period, i)) return true;
            break;
         }
      }
      return false;
   }

private:
   static double PipsToPoints()
   {
      int d = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
      return (d == 3 || d == 5) ? 10.0 * _Point : _Point;
   }
};
