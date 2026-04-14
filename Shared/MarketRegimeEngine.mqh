//+------------------------------------------------------------------+
//|                                           MarketRegimeEngine.mqh |
//|                                   Copyright 2026, LogicCrafterDz |
//|                                              https://example.com |
//|                                                                  |
//|  V2.1: Simple Regime Detection based on ADX & ATR relative size  |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property strict

#include "ArgusManifest.mqh"

class CMarketRegimeEngine
{
private:
   int m_adx_handle;
   int m_atr_handle;
   int m_atr_sma_handle;
   
   string m_symbol;
   ENUM_TIMEFRAMES m_period;

public:
   //+------------------------------------------------------------------+
   //| Initialize indicators (ADX 14, ATR 14, ATR SMA 20)               |
   //+------------------------------------------------------------------+
   bool Init(string symbol, ENUM_TIMEFRAMES period)
   {
      m_symbol = symbol;
      m_period = period;
      
      m_adx_handle = iADX(symbol, period, 14);
      m_atr_handle = iATR(symbol, period, 14);
      m_atr_sma_handle = iMA(symbol, period, 20, 0, MODE_SMA, m_atr_handle); // SMA of ATR
      
      if(m_adx_handle == INVALID_HANDLE || m_atr_handle == INVALID_HANDLE || m_atr_sma_handle == INVALID_HANDLE)
         return false;
         
      return true;
   }
   
   //+------------------------------------------------------------------+
   //| Release handles                                                  |
   //+------------------------------------------------------------------+
   void Deinit()
   {
      if(m_adx_handle != INVALID_HANDLE) IndicatorRelease(m_adx_handle);
      if(m_atr_handle != INVALID_HANDLE) IndicatorRelease(m_atr_handle);
      if(m_atr_sma_handle != INVALID_HANDLE) IndicatorRelease(m_atr_sma_handle);
   }

   //+------------------------------------------------------------------+
   //| Determine Market Regime                                          |
   //+------------------------------------------------------------------+
   int GetCurrentRegime()
   {
      double adx[1], atr[1], atr_sma[1];
      
      if(CopyBuffer(m_adx_handle, 0, 0, 1, adx) <= 0) return 0;
      if(CopyBuffer(m_atr_handle, 0, 0, 1, atr) <= 0) return 0;
      if(CopyBuffer(m_atr_sma_handle, 0, 0, 1, atr_sma) <= 0) return 0;

      double atr_ratio = (atr_sma[0] > 0) ? (atr[0] / atr_sma[0]) : 1.0;
      
      bool isTrend  = (adx[0] > 25.0);
      bool isExpand = (atr_ratio > 1.3);
      
      if(isTrend && isExpand) return REGIME_TREND | REGIME_EXPANSION;
      if(isTrend) return REGIME_TREND;
      if(isExpand) return REGIME_EXPANSION;
      
      // If neither trend nor expansion, it's a range.
      return REGIME_RANGE;
   }
   
   //+------------------------------------------------------------------+
   //| Get human readable name for dashboard                            |
   //+------------------------------------------------------------------+
   static string RegimeToString(int regime)
   {
      if ((regime & REGIME_TREND) && (regime & REGIME_EXPANSION)) return "Trend Expansion";
      if (regime & REGIME_TREND) return "Trend";
      if (regime & REGIME_EXPANSION) return "Expansion";
      if (regime & REGIME_RANGE) return "Range";
      if (regime & REGIME_COMPRESSION) return "Compression";
      if (regime & REGIME_REVERSAL) return "Reversal (Exhaustion)";
      return "Unknown";
   }
};
