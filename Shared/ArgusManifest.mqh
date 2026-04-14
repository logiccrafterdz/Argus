//+------------------------------------------------------------------+
//|                                                ArgusManifest.mqh |
//|                                   Copyright 2026, LogicCrafterDz |
//|                                              https://example.com |
//|                                                                  |
//|  V2.0: Strategy Manifest Standard for the Artificial Meta-Engine |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, LogicCrafterDz"
#property link      "https://example.com"
#property strict

#ifndef ARGUS_MANIFEST_MQH
#define ARGUS_MANIFEST_MQH

//--- Regime Bitmasks
#define REGIME_TREND         1       // 00001
#define REGIME_RANGE         2       // 00010
#define REGIME_EXPANSION     4       // 00100
#define REGIME_COMPRESSION   8       // 01000
#define REGIME_REVERSAL      16      // 10000
#define REGIME_ALL           31      // 11111

//--- Session Bitmasks
#define SESSION_ASIAN        1       // 001
#define SESSION_LONDON       2       // 010
#define SESSION_NY           4       // 100
#define SESSION_ALL          7       // 111

//+------------------------------------------------------------------+
//| Strategy Manifest Structure                                      |
//+------------------------------------------------------------------+
struct StrategyManifest 
{
   string   name;
   string   category;
   int      magic_number;
   int      regime_mask;       
   int      session_mask;      
   bool     requires_trend;
   bool     hates_high_volatility;
   string   target_style;      
};

//+------------------------------------------------------------------+
//| Helper functions for decoding bitmasks                           |
//+------------------------------------------------------------------+
class CManifestUtils 
{
public:
   static bool IsRegimeMatch(int target_regime, int strat_mask) {
      return (target_regime & strat_mask) != 0;
   }
   
   static bool IsSessionMatch(int target_session, int strat_mask) {
      return (target_session & strat_mask) != 0;
   }
};

#endif
