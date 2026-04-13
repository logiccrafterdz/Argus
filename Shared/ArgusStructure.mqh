//+------------------------------------------------------------------+
//|                                                ArgusStructure.mqh|
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK.                                           |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property strict

#ifndef ARGUS_STRUCTURE_MQH
#define ARGUS_STRUCTURE_MQH

#include "ArgusCore.mqh"

//+------------------------------------------------------------------+
//| Class for Market Structure and Liquidity Analysis                |
//+------------------------------------------------------------------+
class CArgusStructure
{
public:
   //+------------------------------------------------------------------+
   //| Swing Detection                                                  |
   //+------------------------------------------------------------------+
   static bool IsSwingHigh(string symbol, ENUM_TIMEFRAMES period, int index, int radius)
   {
      double high = iHigh(symbol, period, index);
      for(int i = 1; i <= radius; i++) {
         if(iHigh(symbol, period, index + i) > high || iHigh(symbol, period, index - i) >= high) return false;
      }
      return true;
   }

   static bool IsSwingLow(string symbol, ENUM_TIMEFRAMES period, int index, int radius)
   {
      double low = iLow(symbol, period, index);
      for(int i = 1; i <= radius; i++) {
         if(iLow(symbol, period, index + i) < low || iLow(symbol, period, index - i) <= low) return false;
      }
      return true;
   }

   //+------------------------------------------------------------------+
   //| Macro Structure Detection (Higher Highs / Lower Lows)            |
   //+------------------------------------------------------------------+
   static bool IsBullishStructure(string symbol, ENUM_TIMEFRAMES period, int bars_to_check)
   {
      double last_low = iLow(symbol, period, 1);
      double prev_low = 0;
      int found = 0;
      
      for(int i = 2; i < bars_to_check; i++) {
         if(iLow(symbol, period, i) < iLow(symbol, period, i-1) && 
            iLow(symbol, period, i) < iLow(symbol, period, i+1)) {
            prev_low = iLow(symbol, period, i);
            found++;
            break;
         }
      }
      return (found > 0 && last_low > prev_low);
   }

   static bool IsBearishStructure(string symbol, ENUM_TIMEFRAMES period, int bars_to_check)
   {
      double last_high = iHigh(symbol, period, 1);
      double prev_high = 0;
      int found = 0;
      
      for(int i = 2; i < bars_to_check; i++) {
         if(iHigh(symbol, period, i) > iHigh(symbol, period, i-1) && 
            iHigh(symbol, period, i) > iHigh(symbol, period, i+1)) {
            prev_high = iHigh(symbol, period, i);
            found++;
            break;
         }
      }
      return (found > 0 && last_high < prev_high);
   }

   //+------------------------------------------------------------------+
   //| Liquidity Pool Detection (EQH / EQL)                             |
   //+------------------------------------------------------------------+
   static double GetLiquidityHigh(string symbol, ENUM_TIMEFRAMES period, int lookback, int radius, double threshold_pips)
   {
      double points = CArgusCore::PipsToPriceDelta(symbol, threshold_pips);
      double swings[];
      int count = 0;

      for(int i = 2; i < lookback; i++) {
         if(IsSwingHigh(symbol, period, i, radius)) {
            ArrayResize(swings, count + 1);
            swings[count] = iHigh(symbol, period, i);
            count++;
         }
      }

      if(count < 2) return 0;

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
         if(matches >= 1) return max_h; 
      }
      return 0;
   }

   static double GetLiquidityLow(string symbol, ENUM_TIMEFRAMES period, int lookback, int radius, double threshold_pips)
   {
      double points = CArgusCore::PipsToPriceDelta(symbol, threshold_pips);
      double swings[];
      int count = 0;

      for(int i = 2; i < lookback; i++) {
         if(IsSwingLow(symbol, period, i, radius)) {
            ArrayResize(swings, count + 1);
            swings[count] = iLow(symbol, period, i);
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

   //+------------------------------------------------------------------+
   //| Market Structure Break (MSB) Detection                           |
   //+------------------------------------------------------------------+
   static bool IsStructureBreak(string symbol, ENUM_TIMEFRAMES period, ENUM_ORDER_TYPE type, int lookback, int radius)
   {
      double last_close = iClose(symbol, period, 1);
      if(type == ORDER_TYPE_BUY) {
         for(int i = 2; i < lookback; i++) {
            if(IsSwingHigh(symbol, period, i, radius)) {
               if(last_close > iHigh(symbol, period, i)) return true;
               break;
            }
         }
      } else {
         for(int i = 2; i < lookback; i++) {
            if(IsSwingLow(symbol, period, i, radius)) {
               if(last_close < iLow(symbol, period, i)) return true;
               break;
            }
         }
      }
      return false;
   }

   static bool IsBearishMSB(string symbol, ENUM_TIMEFRAMES period, int bars_to_check, int radius)
   {
      return IsStructureBreak(symbol, period, ORDER_TYPE_SELL, bars_to_check, radius);
   }

   static bool IsBullishMSB(string symbol, ENUM_TIMEFRAMES period, int bars_to_check, int radius)
   {
      return IsStructureBreak(symbol, period, ORDER_TYPE_BUY, bars_to_check, radius);
   }

   //+------------------------------------------------------------------+
   //| Multi-Timeframe Bias and Swing Legs                              |
   //+------------------------------------------------------------------+
   static int GetHTFBias(string symbol, ENUM_TIMEFRAMES htf, int ema_200_handle, int ema_50_handle)
   {
      double ema200[], ema50[];
      if(CopyBuffer(ema_200_handle, 0, 0, 1, ema200) <= 0) return 0;
      if(CopyBuffer(ema_50_handle, 0, 0, 1, ema50) <= 0) return 0;
      
      MqlRates rates[];
      if(CopyRates(symbol, htf, 0, 1, rates) <= 0) return 0;
      
      bool trend_up = (rates[0].close > ema200[0] && ema50[0] > ema200[0]);
      bool trend_dn = (rates[0].close < ema200[0] && ema50[0] < ema200[0]);
      
      if(trend_up) return 1;
      if(trend_dn) return -1;
      return 0;
   }

   static bool FindLatestSwingLeg(string symbol, ENUM_TIMEFRAMES period, int lookback, int radius, double &leg_high, double &leg_low, int &h_idx, int &l_idx)
   {
      leg_high = 0; leg_low = 0;
      h_idx = -1; l_idx = -1;

      for(int i = 2; i < lookback; i++) {
         if(h_idx == -1 && IsSwingHigh(symbol, period, i, radius)) h_idx = i;
         if(l_idx == -1 && IsSwingLow(symbol, period, i, radius)) l_idx = i;
         if(h_idx != -1 && l_idx != -1) break;
      }

      if(h_idx != -1 && l_idx != -1) {
         leg_high = iHigh(symbol, period, h_idx);
         leg_low  = iLow(symbol, period, l_idx);
         return true;
      }
      return false;
   }

   //+------------------------------------------------------------------+
   //| Session Range                                                    |
   //+------------------------------------------------------------------+
   static bool GetSessionRange(string symbol, ENUM_TIMEFRAMES period, datetime start, datetime end, double &high, double &low)
   {
      int s_idx = iBarShift(symbol, period, start, false);
      int e_idx = iBarShift(symbol, period, end, false);
      if(s_idx < 0 || e_idx < 0 || s_idx <= e_idx) return false;

      int count = s_idx - e_idx + 1;
      int h_idx = iHighest(symbol, period, MODE_HIGH, count, e_idx);
      int l_idx = iLowest(symbol, period, MODE_LOW, count, e_idx);

      if(h_idx < 0 || l_idx < 0) return false;
      high = iHigh(symbol, period, h_idx);
      low  = iLow(symbol, period, l_idx);
      return true;
   }

   static double PipsToPoints(string symbol)
   {
      int d = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
      return (d == 3 || d == 5) ? 10.0 * SymbolInfoDouble(symbol, SYMBOL_POINT) : SymbolInfoDouble(symbol, SYMBOL_POINT);
   }
};

#endif
