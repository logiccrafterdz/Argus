import os
import glob
import re

base_dir = r"c:\Users\Hp\Desktop\Argus"

files = glob.glob(os.path.join(base_dir, "*", "*.mq5"))

for fpath in files:
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()

    original_content = content
    
    # 1. Update Includes
    # If the file imports 'Trade\Trade.mqh', insert our shared includes after it.
    if "#include <Trade\\Trade.mqh>" in content and "#include \"..\\Shared\\ArgusCore.mqh\"" not in content:
        content = content.replace("#include <Trade\\Trade.mqh>", 
                                  "#include <Trade\\Trade.mqh>\n#include \"..\\Shared\\ArgusCore.mqh\"\n#include \"..\\Shared\\ArgusStructure.mqh\"")
    
    # Remove any existing local Utils includes (e.g. #include "StructureUtils.mqh")
    content = re.sub(r'#include\s+"[A-Za-z0-9_]+Utils\.mqh"\s*\n', '', content)
    
    # 2. Delete Local Helpers
    # Find the start of the Standard Volume Calculation or Helpers
    # and cut the rest of the file, IF they exist.
    # Usually they follow: double CalculateLotSize or //+... Standard Volume...
    match_lot = re.search(r'//\+\-+\+\s*\n//\|\s*Standard Volume Calculation\s*\|\s*\n//\+\-+\+\s*\n|double CalculateLotSize', content)
    if match_lot:
        content = content[:match_lot.start()]
        
    # Also if the file used "double NormalizePrice" instead of standard block
    match_norm = re.search(r'double NormalizePrice\(', content)
    if match_norm:
        content = content[:match_norm.start()]

    # 3. Replace Function Calls via Regex
    # We must replace HasOpenPosition() with CArgusCore::HasOpenPosition(_Symbol, MagicNumber)
    content = re.sub(r'HasOpenPosition\(\)', r'CArgusCore::HasOpenPosition(_Symbol, MagicNumber)', content)
    
    # NormalizePrice(price, tick_size) -> CArgusCore::NormalizePrice(_Symbol, price, tick_size)
    content = re.sub(r'NormalizePrice\(([^,]+),\s*([^)]+)\)', r'CArgusCore::NormalizePrice(_Symbol, \1, \2)', content)

    # ValidateStopsLevel(price, target) -> CArgusCore::ValidateStopsLevel(_Symbol, price, target)
    content = re.sub(r'ValidateStopsLevel\(([^,]+),\s*([^)]+)\)', r'CArgusCore::ValidateStopsLevel(_Symbol, \1, \2)', content)
    
    # CalculateLotSize(risk_dist) -> CArgusCore::CalculateLotSize(_Symbol, RiskPercent, risk_dist, vol_precision)
    content = re.sub(r'CalculateLotSize\(([^)]+)\)', r'CArgusCore::CalculateLotSize(_Symbol, RiskPercent, \1, vol_precision)', content)

    # PipsToPriceDelta(pips) -> CArgusCore::PipsToPriceDelta(_Symbol, pips)
    content = re.sub(r'PipsToPriceDelta\(([^)]+)\)', r'CArgusCore::PipsToPriceDelta(_Symbol, \1)', content)
    
    # GetVolumePrecision
    content = re.sub(r'vol_precision\s*=\s*\(int\)MathMax\(0,\s*MathCeil\(MathLog10\(1\.0\s*/\s*step_vol\)\)\);', r'vol_precision = CArgusCore::GetVolumePrecision(_Symbol);', content)
    content = re.sub(r'double step_vol = SymbolInfoDouble\(_Symbol, SYMBOL_VOLUME_STEP\);\s*\n\s*vol_precision = CArgusCore::GetVolumePrecision\(_Symbol\);', r'vol_precision = CArgusCore::GetVolumePrecision(_Symbol);', content)

    # 4. Structure Utils Call Replacements
    # CStructureUtils -> CArgusStructure
    # E.g. CStructureUtils::IsBullishStructure(MarketStructurePeriod) -> CArgusStructure::IsBullishStructure(_Symbol, _Period, MarketStructurePeriod)
    # Since different files have different params, let's do targeted replaces
    
    content = re.sub(r'CStructureUtils::IsBullishStructure\(([^)]+)\)', r'CArgusStructure::IsBullishStructure(_Symbol, _Period, \1)', content)
    content = re.sub(r'CStructureUtils::IsBearishStructure\(([^)]+)\)', r'CArgusStructure::IsBearishStructure(_Symbol, _Period, \1)', content)
    content = re.sub(r'CStructureUtils::IsSwingHigh\(([^,]+),\s*([^)]+)\)', r'CArgusStructure::IsSwingHigh(_Symbol, _Period, \1, \2)', content)
    content = re.sub(r'CStructureUtils::IsSwingLow\(([^,]+),\s*([^)]+)\)', r'CArgusStructure::IsSwingLow(_Symbol, _Period, \1, \2)', content)
    content = re.sub(r'CStructureUtils::GetLiquidityHigh\(([^,]+),\s*([^,]+),\s*([^)]+)\)', r'CArgusStructure::GetLiquidityHigh(_Symbol, _Period, \1, \2, \3)', content)
    content = re.sub(r'CStructureUtils::GetLiquidityLow\(([^,]+),\s*([^,]+),\s*([^)]+)\)', r'CArgusStructure::GetLiquidityLow(_Symbol, _Period, \1, \2, \3)', content)
    
    # SmartSwingBias uses CStructureUtils::GetHTFBias(HTF_Period, ema_slow_htf, ema_fast_htf)
    content = re.sub(r'CStructureUtils::GetHTFBias\(([^,]+),\s*([^,]+),\s*([^)]+)\)', r'CArgusStructure::GetHTFBias(_Symbol, \1, \2, \3)', content)
    content = re.sub(r'CStructureUtils::FindLatestSwingLeg\(([^)]+)\)', r'CArgusStructure::FindLatestSwingLeg(_Symbol, _Period, \1)', content)
    
    # 5. Fix SMCUtils, ICTUtils, etc if they use CStructureUtils
    content = re.sub(r'CStructureUtils::', r'CArgusStructure::', content)

    if content != original_content:
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Refactored: {os.path.basename(fpath)}")

print("Done.")
