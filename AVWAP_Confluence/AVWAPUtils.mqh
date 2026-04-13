//+------------------------------------------------------------------+
//|                                                   AVWAPUtils.mqh |
//|                                  Copyright 2026, LogicCrafterDz |
//|                                             https://example.com |
//|                                                                  |
//|  WARNING: FOR EDUCATIONAL PURPOSES ONLY. NO WARRANTY PROVIDED.   |
//|  USE AT YOUR OWN RISK.                                           |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property strict

enum ENUM_ANCHOR_MODE {
   ANCHOR_SESSION,
   ANCHOR_SWING
};

class CAVWAPUtils
{
public:
   // Calculate Anchored VWAP starting from a specific time
   static double CalculateAVWAP(datetime anchorTime)
   {
      if(anchorTime <= 0) return 0;
      
      int anchorIdx = iBarShift(_Symbol, _Period, anchorTime);
      if(anchorIdx < 0) return 0;
      
      double sumPriceVol = 0;
      long sumVol = 0;
      
      // Loop from anchor bar to current bar (index 0)
      for(int i = anchorIdx; i >= 0; i--) {
         double high = iHigh(_Symbol, _Period, i);
         double low = iLow(_Symbol, _Period, i);
         double close = iClose(_Symbol, _Period, i);
         long vol = iTickVolume(_Symbol, _Period, i);
         
         double typicalPrice = (high + low + close) / 3.0;
         sumPriceVol += typicalPrice * vol;
         sumVol += vol;
      }
      
      return (sumVol > 0) ? (sumPriceVol / sumVol) : 0;
   }

   // Get the anchor timestamp based on mode
   static datetime GetAnchorTime(ENUM_ANCHOR_MODE mode, int sessionHour, int lookback)
   {
      if(mode == ANCHOR_SESSION) {
         MqlDateTime dt;
         TimeCurrent(dt);
         dt.hour = sessionHour;
         dt.min = 0;
         dt.sec = 0;
         datetime anchor = StructToTime(dt);
         // If anchor is in future compared to current server time, use yesterday
         if(anchor > TimeCurrent()) anchor -= 86400;
         return anchor;
      } else {
         // SWING mode: Find extreme of lookback
         int h_idx = iHighest(_Symbol, _Period, MODE_HIGH, lookback, 1);
         int l_idx = iLowest(_Symbol, _Period, MODE_LOW, lookback, 1);
         // Return the most recent one
         return (h_idx < l_idx) ? iTime(_Symbol, _Period, h_idx) : iTime(_Symbol, _Period, l_idx);
      }
   }

   // Verify bounce confirmation
   static bool IsBounceConfirmed(int i, double avwap, double min_body_atr)
   {
      double open = iOpen(_Symbol, _Period, i);
      double close = iClose(_Symbol, _Period, i);
      double body = MathAbs(close - open);
      
      if(body < min_body_atr) return false;
      
      // For Bullish: Close must be above VWAP
      // For Bearish: Close must be below VWAP
      // (This logic will be used in context by the EA)
      return true;
   }
};
