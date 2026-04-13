//+------------------------------------------------------------------+
//|                                                     PDHUtils.mqh |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK.                                           |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property strict

class CPDHUtils
{
public:
   // Get Previous Day High
   static double GetPDH()
   {
      return iHigh(_Symbol, PERIOD_D1, 1);
   }

   // Get Previous Day Low
   static double GetPDL()
   {
      return iLow(_Symbol, PERIOD_D1, 1);
   }

   // Calculate ATR Ratio (Today's ATR / Avg ATR)
   static double GetATRRatio(int atr_handle, int avg_period)
   {
      double atr_daily[];
      if(CopyBuffer(atr_handle, 0, 0, avg_period + 1, atr_daily) <= avg_period) return 1.0;
      
      double current_atr = atr_daily[0];
      double sum = 0;
      for(int i = 1; i <= avg_period; i++) sum += atr_daily[i];
      double avg_atr = sum / avg_period;
      
      if(avg_atr <= 0) return 1.0;
      return current_atr / avg_atr;
   }

   // Identify Rejection (Pinbar or Rejection Wick)
   static bool IsRejection(ENUM_ORDER_TYPE type, int shift)
   {
      double high = iHigh(_Symbol, _Period, shift);
      double low = iLow(_Symbol, _Period, shift);
      double open = iOpen(_Symbol, _Period, shift);
      double close = iClose(_Symbol, _Period, shift);
      double body = MathAbs(open - close);
      double range = high - low;
      
      if(range <= 0) return false;

      if(type == ORDER_TYPE_BUY) // Bullish re-entry/rejection (Long wick at bottom)
      {
         return (MathMin(open, close) - low) > (range * 0.6);
      }
      else // Bearish re-entry/rejection (Long wick at top)
      {
         return (high - MathMax(open, close)) > (range * 0.6);
      }
   }
};
