//+------------------------------------------------------------------+
//|                                                     ICTUtils.mqh |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK.                                           |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property strict

class CICTUtils
{
public:
   // Check if current time is within a specific window (relative to broker time)
   static bool IsInRange(string start_str, string end_str)
   {
      datetime now = TimeCurrent();
      MqlDateTime dt;
      TimeToStruct(now, dt);
      
      int now_min = dt.hour * 60 + dt.min;
      int start_min = ParseTime(start_str);
      int end_min = ParseTime(end_str);
      
      if(start_min < end_min) return (now_min >= start_min && now_min < end_min);
      else return (now_min >= start_min || now_min < end_min); // Overnight window
   }

   // Capture High/Low for a specific lookback period (in hours)
   static bool GetReferenceRange(int hours, double &high, double &low)
   {
      int bars = hours * 3600 / PeriodSeconds(); // Accurate bars calculation
      if(bars <= 0) return false;
      
      int h_idx = iHighest(_Symbol, _Period, MODE_HIGH, bars, 1);
      int l_idx = iLowest(_Symbol, _Period, MODE_LOW, bars, 1);
      
      if(h_idx < 0 || l_idx < 0) return false;
      
      high = iHigh(_Symbol, _Period, h_idx);
      low = iLow(_Symbol, _Period, l_idx);
      return true;
   }

   // Helper: HH:MM to minutes
   static int ParseTime(string time_str)
   {
      string parts[];
      if(StringSplit(time_str, ':', parts) != 2) return 0;
      return (int)StringToInteger(parts[0]) * 60 + (int)StringToInteger(parts[1]);
   }

   // Helper: Calculate pips to points conversion
   static double PipsToPoints() {
      return (SymbolInfoInteger(_Symbol, SYMBOL_DIGITS) == 3 || SymbolInfoInteger(_Symbol, SYMBOL_DIGITS) == 5) ? 10.0 * _Point : _Point;
   }
};
