//+------------------------------------------------------------------+
//|                                                    VWAPUtils.mqh |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK.                                           |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property strict

//+------------------------------------------------------------------+
//| Market Structure and VWAP Statistics Utility                     |
//+------------------------------------------------------------------+
class CVWAPUtils
{
public:
   // Calculate VWAP for a specific anchor period
   static double GetVWAP(ENUM_TIMEFRAMES anchor_period, int bar_index, double& std_dev)
   {
      datetime bar_time = iTime(_Symbol, _Period, bar_index);
      datetime anchor_start = 0;
      
      // Determine the start time of the anchor period
      if(anchor_period == PERIOD_D1)       anchor_start = iTime(_Symbol, PERIOD_D1, iBarShift(_Symbol, PERIOD_D1, bar_time));
      else if(anchor_period == PERIOD_W1)  anchor_start = iTime(_Symbol, PERIOD_W1, iBarShift(_Symbol, PERIOD_W1, bar_time));
      else if(anchor_period == PERIOD_MN1) anchor_start = iTime(_Symbol, PERIOD_MN1, iBarShift(_Symbol, PERIOD_MN1, bar_time));
      else anchor_start = iTime(_Symbol, PERIOD_D1, iBarShift(_Symbol, PERIOD_D1, bar_time)); // Default to Daily

      int start_idx = iBarShift(_Symbol, _Period, anchor_start);
      if(start_idx < bar_index) return 0;

      double sum_pv = 0;
      double sum_v = 0;
      double sum_sq_diff = 0;

      // 1st Pass: Calculate VWAP
      for(int i = start_idx; i >= bar_index; i--)
      {
         double price = (iHigh(_Symbol, _Period, i) + iLow(_Symbol, _Period, i) + iClose(_Symbol, _Period, i)) / 3.0;
         long vol = iTickVolume(_Symbol, _Period, i);
         
         sum_pv += (price * vol);
         sum_v += vol;
      }

      if(sum_v == 0) return 0;
      double vwap = sum_pv / sum_v;

      // 2nd Pass: Calculate Standard Deviation (Bands)
      for(int i = start_idx; i >= bar_index; i--)
      {
         double price = (iHigh(_Symbol, _Period, i) + iLow(_Symbol, _Period, i) + iClose(_Symbol, _Period, i)) / 3.0;
         long vol = iTickVolume(_Symbol, _Period, i);
         sum_sq_diff += vol * MathPow(price - vwap, 2);
      }

      std_dev = MathSqrt(sum_sq_diff / sum_v);
      return vwap;
   }

   // Detect if the market is Balanced (range) or Trending (expansion)
   // Uses ATR Ratio: Current ATR / SMA of ATR
   static bool IsBalancedRegime(int atr_handle, double low_vol_threshold)
   {
      double atr_buffer[];
      ArraySetAsSeries(atr_buffer, true);
      
      if(CopyBuffer(atr_handle, 0, 0, 100, atr_buffer) < 100) return true; // Default to balanced if not enough data

      double current_atr = atr_buffer[0];
      double sum_atr = 0;
      for(int i = 0; i < 100; i++) sum_atr += atr_buffer[i];
      double avg_atr = sum_atr / 100.0;

      if(avg_atr == 0) return true;
      
      double ratio = current_atr / avg_atr;
      return (ratio < low_vol_threshold);
   }

   // Utility to check confluence between two levels
   static bool IsConfluence(double level1, double level2, double threshold_pips)
   {
      if(level1 <= 0 || level2 <= 0) return false;
      double dist = MathAbs(level1 - level2);
      return (dist <= threshold_pips * PipsToPoints());
   }

private:
   static double PipsToPoints()
   {
      int d = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
      return (d == 3 || d == 5) ? 10.0 * _Point : _Point;
   }
};
