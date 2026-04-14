import os
import glob
import re

base_dir = r"c:\Users\Hp\Desktop\Argus"
# Match EAs but exclude orchestrator
ea_files = glob.glob(os.path.join(base_dir, "*", "*.mq5"))

# Strategy logic mappings
manifest_data = {
    "TrendPullback": {"cat": "Trend Following", "reg": "REGIME_TREND | REGIME_EXPANSION", "sess": "SESSION_ALL", "req_trend": "true", "hates_vol": "false", "target": "Fixed RR"},
    "SR_Breakout_Retest": {"cat": "Breakout", "reg": "REGIME_EXPANSION | REGIME_TREND", "sess": "SESSION_ALL", "req_trend": "false", "hates_vol": "false", "target": "Next SR Level"},
    "ORB_Session": {"cat": "Breakout", "reg": "REGIME_EXPANSION", "sess": "SESSION_LONDON | SESSION_NY", "req_trend": "false", "hates_vol": "false", "target": "Fixed RR"},
    "Bollinger_MeanReversion": {"cat": "Mean Reversion", "reg": "REGIME_RANGE | REGIME_COMPRESSION", "sess": "SESSION_ASIAN | SESSION_LONDON", "req_trend": "false", "hates_vol": "true", "target": "Bollinger Middle"},
    "PriceAction_SR": {"cat": "Reversal", "reg": "REGIME_RANGE | REGIME_REVERSAL", "sess": "SESSION_ALL", "req_trend": "false", "hates_vol": "false", "target": "Fixed RR"},
    "Liquidity_Sweep_Breakout": {"cat": "Liquidity Hunting", "reg": "REGIME_ALL", "sess": "SESSION_LONDON | SESSION_NY", "req_trend": "false", "hates_vol": "false", "target": "Fixed RR"},
    "VWAP_MultiBand_Regime": {"cat": "Mean Reversion", "reg": "REGIME_RANGE", "sess": "SESSION_ALL", "req_trend": "false", "hates_vol": "true", "target": "VWAP Mean"},
    "Asian_Range_Fakeout": {"cat": "Liquidity Hunting", "reg": "REGIME_EXPANSION", "sess": "SESSION_LONDON", "req_trend": "false", "hates_vol": "false", "target": "Fixed RR"},
    "NY_Session_Reversal": {"cat": "Reversal", "reg": "REGIME_REVERSAL", "sess": "SESSION_NY", "req_trend": "false", "hates_vol": "false", "target": "50% London Retracement"},
    "Volatility_Squeeze": {"cat": "Breakout", "reg": "REGIME_COMPRESSION", "sess": "SESSION_ALL", "req_trend": "true", "hates_vol": "false", "target": "Measured Move"},
    "ORB_Hybrid": {"cat": "Breakout/Trap", "reg": "REGIME_EXPANSION | REGIME_REVERSAL", "sess": "SESSION_LONDON | SESSION_NY", "req_trend": "true", "hates_vol": "false", "target": "Dynamic"},
    "Smart_Swing_Bias": {"cat": "Trend Following", "reg": "REGIME_TREND", "sess": "SESSION_ALL", "req_trend": "true", "hates_vol": "false", "target": "Structural High/Low"},
    "SuperTrend_EMA": {"cat": "Trend Following", "reg": "REGIME_TREND", "sess": "SESSION_ALL", "req_trend": "true", "hates_vol": "false", "target": "Trailing SL"},
    "Hidden_Divergence": {"cat": "Trend Continuation", "reg": "REGIME_TREND", "sess": "SESSION_ALL", "req_trend": "true", "hates_vol": "false", "target": "Structural High/Low"},
    "ADX_TrendStrength": {"cat": "Trend Following", "reg": "REGIME_TREND | REGIME_EXPANSION", "sess": "SESSION_ALL", "req_trend": "true", "hates_vol": "false", "target": "Fixed RR"},
    "Donchian_Breakout": {"cat": "Trend Following", "reg": "REGIME_TREND | REGIME_EXPANSION", "sess": "SESSION_ALL", "req_trend": "true", "hates_vol": "false", "target": "Trailing Opposite Band"},
    "ICT_Killzone_Macro": {"cat": "Liquidity Hunting", "reg": "REGIME_EXPANSION | REGIME_REVERSAL", "sess": "SESSION_LONDON | SESSION_NY", "req_trend": "false", "hates_vol": "false", "target": "Mid Range / Extremes"},
    "PDH_PDL_BreakReversal": {"cat": "Breakout/Trap", "reg": "REGIME_EXPANSION | REGIME_REVERSAL", "sess": "SESSION_ALL", "req_trend": "false", "hates_vol": "false", "target": "Fixed RR"},
    "Liquidity_Sweep_FVG": {"cat": "SMC", "reg": "REGIME_TREND | REGIME_REVERSAL", "sess": "SESSION_LONDON | SESSION_NY", "req_trend": "true", "hates_vol": "false", "target": "Structural Limits"},
    "AVWAP_Confluence": {"cat": "Trend Pullback", "reg": "REGIME_TREND", "sess": "SESSION_ALL", "req_trend": "true", "hates_vol": "false", "target": "Fixed RR"}
}

for fpath in ea_files:
    folder_name = os.path.basename(os.path.dirname(fpath))
    if folder_name == "Argus_Orchestrator": continue
    
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    
    if "ArgusManifest.mqh" in content:
        print(f"Already injected: {folder_name}")
        continue
        
    cfg = manifest_data.get(folder_name, {
        "cat": "Unknown", "reg": "REGIME_ALL", "sess": "SESSION_ALL", 
        "req_trend": "false", "hates_vol": "false", "target": "Unknown"
    })
    
    # Extract Human Readable Name (guess from standard format or directory)
    name = folder_name.replace("_", " ")
    
    manifest_func = f"""
//+------------------------------------------------------------------+
//| Strategy Manifest Identity                                       |
//+------------------------------------------------------------------+
StrategyManifest GetManifest()
{{
   StrategyManifest m;
   m.name = "{name}";
   m.category = "{cfg['cat']}";
   m.magic_number = MagicNumber;
   m.regime_mask = {cfg['reg']};
   m.session_mask = {cfg['sess']};
   m.requires_trend = {cfg['req_trend']};
   m.hates_high_volatility = {cfg['hates_vol']};
   m.target_style = "{cfg['target']}";
   return m;
}}
"""

    # Inject include statement safely after the ArgusStructure.mqh include
    target_inc = '#include "..\\Shared\\ArgusStructure.mqh"'
    if target_inc in content:
       content = content.replace(target_inc, target_inc + '\n#include "..\\Shared\\ArgusManifest.mqh"')
    elif '#include "../Shared/ArgusStructure.mqh"' in content:
       target_inc = '#include "../Shared/ArgusStructure.mqh"'
       content = content.replace(target_inc, target_inc + '\n#include "../Shared/ArgusManifest.mqh"')
    else:
       # fallback to finding the last include
       lines = content.split('\n')
       last_inc = -1
       for i, l in enumerate(lines):
           if "#include" in l: last_inc = i
       if last_inc != -1:
           lines.insert(last_inc + 1, '#include "..\\Shared\\ArgusManifest.mqh"')
           content = "\n".join(lines)
           
    # Append the GetManifest function to the end of the file
    content += manifest_func
    
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)
        
    print(f"Injected into: {folder_name}")
