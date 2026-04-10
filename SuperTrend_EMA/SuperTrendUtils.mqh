//+------------------------------------------------------------------+
//|                                           SuperTrendUtils.mqh |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK.                                           |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property strict

class CSuperTrendUtils
{
public:
   // Calculate SuperTrend state for a specific bar
   // Returns: 1 (Bullish), -1 (Bearish)
   static int Calculate(int index, int atr_period, double multiplier, double &st_value, double &prev_upper, double &prev_lower, int &prev_trend)
   {
      double atr[];
      int handle = iATR(_Symbol, _Period, atr_period);
      if(CopyBuffer(handle, 0, index, 1, atr) <= 0) return 0;
      
      double mid = (iHigh(_Symbol, _Period, index) + iLow(_Symbol, _Period, index)) / 2.0;
      double basic_upper = mid + multiplier * atr[0];
      double basic_lower = mid - multiplier * atr[0];
      
      double high_p = iHigh(_Symbol, _Period, index + 1);
      double low_p  = iLow(_Symbol, _Period, index + 1);
      double close_p = iClose(_Symbol, _Period, index + 1);
      double close_c = iClose(_Symbol, _Period, index);

      // Trailing Upper Band
      double upper = (basic_upper < prev_upper || close_p > prev_upper) ? basic_upper : prev_upper;
      // Trailing Lower Band
      double lower = (basic_lower > prev_lower || close_p < prev_lower) ? basic_lower : prev_lower;
      
      int trend = prev_trend;
      if(close_c > upper) trend = 1;
      else if(close_c < lower) trend = -1;
      
      st_value = (trend == 1) ? lower : upper;
      
      // Update variables for next call (recursive state)
      prev_upper = upper;
      prev_lower = lower;
      prev_trend = trend;
      
      return trend;
   }

   // Simply verify if ATR is above a certain threshold (Chop Filter)
   static bool IsVolatilityHealthy(int atr_period, double threshold_mult)
   {
      double atr[], atr_sma[];
      int h_atr = iATR(_Symbol, _Period, atr_period);
      int h_sma = iMA(_Symbol, _Period, 50, 0, MODE_SMA, h_atr);
      
      if(CopyBuffer(h_atr, 0, 0, 1, atr) <= 0) return true;
      if(CopyBuffer(h_sma, 0, 0, 1, atr_sma) <= 0) return true;
      
      return (atr[0] > atr_sma[0] * threshold_mult);
   }
};
